import pytest

from custom_components.sim800c.modem.errors import (
    ModemError,
    ModemTimeout,
    NotRegistered,
    SmsSendError,
)
from custom_components.sim800c.modem.modem import (
    CALL_DIR_INCOMING,
    CALL_DIR_OUTGOING,
    CALL_STAT_ACTIVE,
    CALL_STAT_ALERTING,
    CALL_STAT_INCOMING,
    Modem,
)
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


async def test_initialize_enables_caller_id():
    modem, transport, fake = make_modem(
        [
            ("ATE0", b"\r\nOK\r\n"),
            ("AT\\+CMGF=1", b"\r\nOK\r\n"),
            ("AT\\+CLIP=1", b"\r\nOK\r\n"),
        ]
    )
    await transport.connect()
    await modem.initialize()
    assert b"AT+CLIP=1\r\n" in b"".join(fake.written)


async def test_initialize_tolerates_clip_rejection():
    # Some SIM/network combos reject AT+CLIP=1; initialize must not blow up.
    modem, transport, _ = make_modem(
        [
            ("ATE0", b"\r\nOK\r\n"),
            ("AT\\+CMGF=1", b"\r\nOK\r\n"),
            ("AT\\+CLIP=1", b"\r\n+CME ERROR: 3\r\n"),
        ]
    )
    await transport.connect()
    await modem.initialize()  # must not raise


async def test_get_current_call_none_when_idle():
    modem, transport, _ = make_modem([("AT\\+CLCC", b"\r\nOK\r\n")])
    await transport.connect()
    assert await modem.get_current_call() is None


async def test_get_current_call_outgoing_alerting():
    modem, transport, _ = make_modem(
        [("AT\\+CLCC", b'\r\n+CLCC: 1,0,3,0,0,"+79990001122",145\r\n\r\nOK\r\n')]
    )
    await transport.connect()
    call = await modem.get_current_call()
    assert call is not None
    assert call.direction == CALL_DIR_OUTGOING
    assert call.state == CALL_STAT_ALERTING
    assert call.number == "+79990001122"
    assert not call.is_incoming
    assert not call.is_answered


async def test_get_current_call_outgoing_answered():
    modem, transport, _ = make_modem(
        [("AT\\+CLCC", b'\r\n+CLCC: 1,0,0,0,0,"+79990001122",145\r\n\r\nOK\r\n')]
    )
    await transport.connect()
    call = await modem.get_current_call()
    assert call is not None
    assert call.state == CALL_STAT_ACTIVE
    assert call.is_answered


async def test_get_current_call_incoming_with_number():
    modem, transport, _ = make_modem(
        [("AT\\+CLCC", b'\r\n+CLCC: 1,1,4,0,0,"+79990001122",145\r\n\r\nOK\r\n')]
    )
    await transport.connect()
    call = await modem.get_current_call()
    assert call is not None
    assert call.direction == CALL_DIR_INCOMING
    assert call.state == CALL_STAT_INCOMING
    assert call.number == "+79990001122"
    assert call.is_incoming


async def test_get_current_call_incoming_without_number():
    # Withheld / no-CLIP caller: number field absent.
    modem, transport, _ = make_modem(
        [("AT\\+CLCC", b"\r\n+CLCC: 1,1,4,0,0\r\n\r\nOK\r\n")]
    )
    await transport.connect()
    call = await modem.get_current_call()
    assert call is not None
    assert call.is_incoming
    assert call.number is None


async def test_list_unread_sms_none_returns_empty():
    modem, transport, _ = make_modem([('AT\\+CMGL="REC UNREAD"', b"\r\nOK\r\n")])
    await transport.connect()
    assert await modem.list_unread_sms() == []


async def test_list_unread_sms_gsm_ascii():
    resp = (
        b'\r\n+CMGL: 1,"REC UNREAD","+79990001122","","24/07/11,02:30:00+12",'
        b"145,4,0,0,,145,5\r\nHello\r\n\r\nOK\r\n"
    )
    modem, transport, _ = make_modem([('AT\\+CMGL="REC UNREAD"', resp)])
    await transport.connect()
    msgs = await modem.list_unread_sms()
    assert len(msgs) == 1
    assert msgs[0].index == 1
    assert msgs[0].sender == "+79990001122"
    assert msgs[0].timestamp == "24/07/11,02:30:00+12"
    assert msgs[0].text == "Hello"


async def test_list_unread_sms_ucs2_cyrillic_body_decoded():
    # DCS=8 (UCS2); body is UCS2 hex for "Привет".
    resp = (
        b'\r\n+CMGL: 2,"REC UNREAD","+79990001122","","24/07/11,02:31:00+12",'
        b"145,4,0,8,,145,12\r\n041F04400438043204350442\r\n\r\nOK\r\n"
    )
    modem, transport, _ = make_modem([('AT\\+CMGL="REC UNREAD"', resp)])
    await transport.connect()
    msgs = await modem.list_unread_sms()
    assert len(msgs) == 1
    assert msgs[0].text == "Привет"


async def test_list_unread_sms_without_csdh_dcs_absent_treated_as_text():
    # CSDH=0 header (no DCS): body used verbatim.
    resp = (
        b'\r\n+CMGL: 3,"REC UNREAD","+79990001122","",'
        b'"24/07/11,02:32:00+12"\r\nPlain text\r\n\r\nOK\r\n'
    )
    modem, transport, _ = make_modem([('AT\\+CMGL="REC UNREAD"', resp)])
    await transport.connect()
    msgs = await modem.list_unread_sms()
    assert len(msgs) == 1
    assert msgs[0].text == "Plain text"


async def test_list_unread_sms_multiple_messages():
    resp = (
        b'\r\n+CMGL: 1,"REC UNREAD","+79990001122","","24/07/11,02:30:00+12",'
        b"145,4,0,0,,145,3\r\nOne\r\n"
        b'+CMGL: 2,"REC UNREAD","+79990003344","","24/07/11,02:31:00+12",'
        b"145,4,0,0,,145,3\r\nTwo\r\n\r\nOK\r\n"
    )
    modem, transport, _ = make_modem([('AT\\+CMGL="REC UNREAD"', resp)])
    await transport.connect()
    msgs = await modem.list_unread_sms()
    assert [m.index for m in msgs] == [1, 2]
    assert [m.sender for m in msgs] == ["+79990001122", "+79990003344"]
    assert [m.text for m in msgs] == ["One", "Two"]


async def test_delete_sms_sends_cmgd():
    modem, transport, fake = make_modem([("AT\\+CMGD=4", b"\r\nOK\r\n")])
    await transport.connect()
    await modem.delete_sms(4)
    assert b"AT+CMGD=4\r\n" in b"".join(fake.written)


async def test_initialize_enables_csdh():
    modem, transport, fake = make_modem(
        [
            ("ATE0", b"\r\nOK\r\n"),
            ("AT\\+CMGF=1", b"\r\nOK\r\n"),
            ("AT\\+CLIP=1", b"\r\nOK\r\n"),
            ("AT\\+CSDH=1", b"\r\nOK\r\n"),
        ]
    )
    await transport.connect()
    await modem.initialize()
    assert b"AT+CSDH=1\r\n" in b"".join(fake.written)
