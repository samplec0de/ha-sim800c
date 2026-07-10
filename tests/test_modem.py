import pytest

from custom_components.sim800c.modem.errors import (
    ModemError,
    ModemTimeout,
    NotRegistered,
    SmsSendError,
)
from custom_components.sim800c.modem.modem import Modem
from custom_components.sim800c.modem.transport import Transport
from tests.conftest import FakeSerial


def test_error_hierarchy():
    assert issubclass(ModemTimeout, ModemError)
    assert issubclass(NotRegistered, ModemError)
    assert issubclass(SmsSendError, ModemError)


def make_modem(rules):
    fake = FakeSerial(rules)
    transport = Transport("/dev/fake", 9600, serial_factory=lambda *a, **k: fake)
    return Modem(transport), transport, fake


async def test_initialize_sets_echo_off_and_text_mode():
    modem, transport, fake = make_modem(
        [("ATE0", b"\r\nOK\r\n"), ("AT\\+CMGF=1", b"\r\nOK\r\n")]
    )
    await transport.connect()
    await modem.initialize()
    joined = b"".join(fake.written)
    assert b"ATE0\r\n" in joined
    assert b"AT+CMGF=1\r\n" in joined


async def test_get_signal_parses_csq():
    modem, transport, _ = make_modem([("AT\\+CSQ", b"\r\n+CSQ: 20,0\r\n\r\nOK\r\n")])
    await transport.connect()
    # rssi = -113 + 2*20 = -73 dBm
    assert await modem.get_signal() == -73


async def test_get_signal_none_when_unknown():
    modem, transport, _ = make_modem([("AT\\+CSQ", b"\r\n+CSQ: 99,0\r\n\r\nOK\r\n")])
    await transport.connect()
    assert await modem.get_signal() is None


async def test_get_registration_true_when_registered():
    modem, transport, _ = make_modem(
        [("AT\\+CREG\\?", b"\r\n+CREG: 0,1\r\n\r\nOK\r\n")]
    )
    await transport.connect()
    assert await modem.get_registration() is True


async def test_get_registration_false_when_searching():
    modem, transport, _ = make_modem(
        [("AT\\+CREG\\?", b"\r\n+CREG: 0,2\r\n\r\nOK\r\n")]
    )
    await transport.connect()
    assert await modem.get_registration() is False


async def test_send_sms_gsm_ascii_returns_reference():
    rules = [
        ("AT\\+CREG\\?", b"\r\n+CREG: 0,1\r\n\r\nOK\r\n"),
        ('AT\\+CSCS="GSM"', b"\r\nOK\r\n"),
        ("AT\\+CSMP=", b"\r\nOK\r\n"),
        ('AT\\+CMGS="\\+79', b"\r\n> "),
        ("\x1a", b"\r\n+CMGS: 7\r\n\r\nOK\r\n"),
    ]
    modem, transport, fake = make_modem(rules)
    await transport.connect()
    ref = await modem.send_sms("+79990001122", "Hello")
    assert ref == 7
    # ASCII body sent verbatim, not UCS2-hex
    body_writes = b"".join(fake.written)
    assert b"Hello\x1a" in body_writes


async def test_send_sms_cyrillic_uses_ucs2():
    rules = [
        ("AT\\+CREG\\?", b"\r\n+CREG: 0,1\r\n\r\nOK\r\n"),
        ('AT\\+CSCS="UCS2"', b"\r\nOK\r\n"),
        ("AT\\+CSMP=", b"\r\nOK\r\n"),
        ("AT\\+CMGS=", b"\r\n> "),
        ("\x1a", b"\r\n+CMGS: 8\r\n\r\nOK\r\n"),
    ]
    modem, transport, fake = make_modem(rules)
    await transport.connect()
    ref = await modem.send_sms("+79990001122", "Привет")
    assert ref == 8
    body_writes = b"".join(fake.written)
    assert b"041F04400438043204350442\x1a" in body_writes


async def test_send_sms_raises_when_not_registered():
    rules = [("AT\\+CREG\\?", b"\r\n+CREG: 0,2\r\n\r\nOK\r\n")]
    modem, transport, _ = make_modem(rules)
    await transport.connect()
    with pytest.raises(NotRegistered):
        await modem.send_sms("+79990001122", "Hello")


async def test_send_sms_raises_on_cms_error():
    rules = [
        ("AT\\+CREG\\?", b"\r\n+CREG: 0,1\r\n\r\nOK\r\n"),
        ('AT\\+CSCS="GSM"', b"\r\nOK\r\n"),
        ("AT\\+CSMP=", b"\r\nOK\r\n"),
        ("AT\\+CMGS=", b"\r\n> "),
        ("\x1a", b"\r\n+CMS ERROR: 500\r\n"),
    ]
    modem, transport, _ = make_modem(rules)
    await transport.connect()
    with pytest.raises(SmsSendError):
        await modem.send_sms("+79990001122", "Hello")


async def test_dial_and_hangup_send_atd_and_ath():
    rules = [("ATD\\+79", b"\r\nOK\r\n"), ("ATH", b"\r\nOK\r\n")]
    modem, transport, fake = make_modem(rules)
    await transport.connect()
    await modem.dial("+79990001122")
    await modem.hangup()
    joined = b"".join(fake.written)
    assert b"ATD+79990001122;\r\n" in joined
    assert b"ATH\r\n" in joined
