"""Tests for ModemHub call orchestration and incoming-call monitoring."""

from __future__ import annotations

import pytest

from custom_components.sim800c import hub as hub_mod
from custom_components.sim800c.const import (
    CALL_STATE_ACTIVE,
    CALL_STATE_IDLE,
    CALL_STATE_INCOMING,
    CALL_STATE_RINGING,
)
from custom_components.sim800c.hub import ModemHub
from custom_components.sim800c.modem import (
    CALL_DIR_INCOMING,
    CALL_DIR_OUTGOING,
    CALL_STAT_ACTIVE,
    CALL_STAT_ALERTING,
    CALL_STAT_INCOMING,
    CallInfo,
)


class FakeModem:
    """Scripted stand-in for the Modem, returning canned CLCC snapshots."""

    def __init__(self, states: list[CallInfo | None]) -> None:
        """Queue the CLCC snapshots successive get_current_call calls return."""
        self._states = list(states)
        self.dialed: str | None = None
        self.hung_up = False

    async def dial(self, number: str) -> None:
        """Record the dialed number."""
        self.dialed = number

    async def hangup(self) -> None:
        """Record that a hang-up was requested."""
        self.hung_up = True

    async def get_current_call(self) -> CallInfo | None:
        """Return the next scripted snapshot, holding on the last one."""
        if len(self._states) > 1:
            return self._states.pop(0)
        return self._states[0] if self._states else None


def make_hub(**kwargs: object) -> ModemHub:
    return ModemHub("/dev/fake", 9600, **kwargs)


@pytest.fixture(autouse=True)
def _fast_poll(monkeypatch) -> None:
    """Speed up the outgoing-call poll loop for tests."""
    monkeypatch.setattr(hub_mod, "_CALL_POLL_INTERVAL", 0.01)


async def test_async_call_reports_answered():
    hub = make_hub()
    hub._modem = FakeModem(  # noqa: SLF001
        [
            CallInfo(CALL_DIR_OUTGOING, CALL_STAT_ALERTING, "+79990001122"),
            CallInfo(CALL_DIR_OUTGOING, CALL_STAT_ACTIVE, "+79990001122"),
        ]
    )
    result = await hub.async_call("+79990001122", ring_duration=5)
    assert hub._modem.dialed == "+79990001122"  # noqa: SLF001
    assert result.answered is True
    assert result.final_state == "answered"
    assert hub._modem.hung_up is True  # noqa: SLF001
    assert hub.call_state == CALL_STATE_IDLE


async def test_async_call_reports_no_answer_and_auto_hangs_up():
    hub = make_hub()
    # Rings the whole time, never answered.
    hub._modem = FakeModem(  # noqa: SLF001
        [CallInfo(CALL_DIR_OUTGOING, CALL_STAT_ALERTING, "+79990001122")]
    )
    result = await hub.async_call("+79990001122", ring_duration=0.05)
    assert result.answered is False
    assert result.final_state == "no_answer"
    assert hub._modem.hung_up is True  # noqa: SLF001


async def test_async_call_reports_remote_ended():
    hub = make_hub()
    # Saw a ringing call, then it disappears (remote rejected/hung up).
    hub._modem = FakeModem(  # noqa: SLF001
        [
            CallInfo(CALL_DIR_OUTGOING, CALL_STAT_ALERTING, "+79990001122"),
            None,
        ]
    )
    result = await hub.async_call("+79990001122", ring_duration=5)
    assert result.answered is False
    assert result.final_state == "ended"


async def test_incoming_call_sets_state_and_fires_event_once():
    events: list[str | None] = []
    updates: list[int] = []
    hub = make_hub(
        on_state_change=lambda: updates.append(1),
        on_incoming_call=events.append,
    )
    hub._modem = FakeModem(  # noqa: SLF001
        [CallInfo(CALL_DIR_INCOMING, CALL_STAT_INCOMING, "+79990001122")]
    )

    await hub._refresh_call_state()  # noqa: SLF001
    assert hub.incoming_call is True
    assert hub.incoming_number == "+79990001122"
    assert hub.call_state == CALL_STATE_INCOMING
    assert events == ["+79990001122"]
    assert updates  # a state-change push happened

    # Still ringing: no duplicate event on the next poll.
    await hub._refresh_call_state()  # noqa: SLF001
    assert events == ["+79990001122"]


async def test_incoming_call_clears_when_gone():
    hub = make_hub()
    hub._modem = FakeModem(  # noqa: SLF001
        [CallInfo(CALL_DIR_INCOMING, CALL_STAT_INCOMING, "+79990001122"), None]
    )
    await hub._refresh_call_state()  # noqa: SLF001
    assert hub.incoming_call is True
    await hub._refresh_call_state()  # noqa: SLF001
    assert hub.incoming_call is False
    assert hub.incoming_number is None
    assert hub.call_state == CALL_STATE_IDLE


def test_outgoing_state_mapping():
    assert hub_mod._outgoing_state(CALL_STAT_ACTIVE) == CALL_STATE_ACTIVE  # noqa: SLF001
    assert hub_mod._outgoing_state(CALL_STAT_ALERTING) == CALL_STATE_RINGING  # noqa: SLF001
