from custom_components.sim800c.modem.errors import (
    ModemError,
    ModemTimeout,
    NotRegistered,
    SmsSendError,
)


def test_error_hierarchy():
    assert issubclass(ModemTimeout, ModemError)
    assert issubclass(NotRegistered, ModemError)
    assert issubclass(SmsSendError, ModemError)
