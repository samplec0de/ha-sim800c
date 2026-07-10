import pytest

from custom_components.sim800c.modem.errors import ModemError, ModemTimeout
from custom_components.sim800c.modem.transport import Transport
from tests.conftest import FakeSerial


def make_transport(rules):
    fake = FakeSerial(rules)
    return Transport("/dev/fake", 9600, serial_factory=lambda *a, **k: fake), fake


async def test_execute_reads_until_ok():
    transport, fake = make_transport([("AT", b"\r\nOK\r\n")])
    await transport.connect()
    resp = await transport.execute("AT")
    assert "OK" in resp
    assert fake.written[-1] == b"AT\r\n"


async def test_execute_raises_on_error_token():
    transport, _ = make_transport([("AT\\+BAD", b"\r\nERROR\r\n")])
    await transport.connect()
    with pytest.raises(ModemError):
        await transport.execute("AT+BAD")


async def test_execute_times_out_without_token():
    transport, _ = make_transport([])  # no response
    await transport.connect()
    with pytest.raises(ModemTimeout):
        await transport.execute("AT", timeout=0.3)


async def test_transaction_serializes_prompt_then_body():
    rules = [
        ('AT\\+CMGS="\\+7', b"\r\n> "),
        ("\x1a", b"\r\n+CMGS: 42\r\n\r\nOK\r\n"),
    ]
    transport, _fake = make_transport(rules)
    await transport.connect()
    async with transport.transaction() as txn:
        await txn.send_line('AT+CMGS="+70000000000"')
        prompt = await txn.read_until((">",), timeout=1.0)
        assert ">" in prompt
        await txn.write_raw(b"0041\x1a")
        final = await txn.read_until(("+CMGS",), timeout=2.0)
        assert "+CMGS: 42" in final
