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
    SmsMessage,
)


class FakeModem:
    """Scripted stand-in for the Modem, returning canned CLCC/SMS snapshots."""

    def __init__(
        self,
        states: list[CallInfo | None] | None = None,
        sms: list[SmsMessage] | None = None,
    ) -> None:
        """Queue the CLCC snapshots and unread SMS the modem should report."""
        self._states = list(states) if states else [None]
        self._sms = list(sms) if sms else []
        self.dialed: str | None = None
        self.hung_up = False
        self.deleted: list[int] = []
        self.uploaded: bytes | None = None
        self.played = False
        self.play_volume: int | None = None
        self.stopped = False
        self.order: list[str] = []
        self.answered = False
        self.recording_started = False
        self.recording_stopped = False
        self.deleted_files: list[str] = []
        self.file_bytes = b""

    async def dial(self, number: str) -> None:
        """Record the dialed number."""
        self.dialed = number
        self.order.append("dial")

    async def upload_audio(self, data: bytes) -> None:
        """Record the uploaded audio payload."""
        self.uploaded = data
        self.order.append("upload")

    async def play_audio(self, volume: int = 90) -> None:
        """Record that playback started at the given volume."""
        self.played = True
        self.play_volume = volume
        self.order.append("play")

    async def stop_audio(self) -> None:
        """Record that playback was stopped."""
        self.stopped = True
        self.order.append("stop")

    async def hangup(self) -> None:
        """Record that a hang-up was requested."""
        self.hung_up = True

    async def get_current_call(self) -> CallInfo | None:
        """Return the next scripted snapshot, holding on the last one."""
        if len(self._states) > 1:
            return self._states.pop(0)
        return self._states[0] if self._states else None

    async def list_unread_sms(self) -> list[SmsMessage]:
        """Return queued unread SMS once, then nothing (as the modem would)."""
        pending = self._sms
        self._sms = []
        return pending

    async def delete_sms(self, index: int) -> None:
        """Record the deleted message index."""
        self.deleted.append(index)

    async def answer(self) -> None:
        """Record that the incoming call was answered."""
        self.answered = True
        self.order.append("answer")

    async def start_recording(self) -> None:
        """Record that in-call recording started."""
        self.recording_started = True
        self.order.append("start_recording")

    async def stop_recording(self) -> None:
        """Record that in-call recording stopped."""
        self.recording_stopped = True
        self.order.append("stop_recording")

    async def file_size(self, path: str) -> int:
        """Return the size of the canned recording payload."""
        self.order.append("file_size")
        _ = path
        return len(self.file_bytes)

    async def read_file(self, path: str, size: int) -> bytes:
        """Return the canned recording payload."""
        self.order.append("read_file")
        _ = (path, size)
        return self.file_bytes

    async def delete_file(self, path: str) -> None:
        """Record the deleted file path."""
        self.deleted_files.append(path)
        self.order.append("delete_file")


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


async def test_call_and_play_uploads_dials_then_plays_when_answered():
    hub = make_hub()
    # Ring, answer, then the call drops so unknown-duration playback returns fast.
    hub._modem = FakeModem(  # noqa: SLF001
        [
            CallInfo(CALL_DIR_OUTGOING, CALL_STAT_ALERTING, "+79990001122"),
            CallInfo(CALL_DIR_OUTGOING, CALL_STAT_ACTIVE, "+79990001122"),
            None,
        ]
    )
    result = await hub.async_call_and_play("+79990001122", b"AMRDATA", ring_duration=5)
    modem = hub._modem  # noqa: SLF001
    assert modem.uploaded == b"AMRDATA"
    assert modem.dialed == "+79990001122"
    # Upload must happen before dialing so the file is ready on connect.
    assert modem.order[:2] == ["upload", "dial"]
    assert modem.played is True
    assert modem.play_volume == 90
    assert modem.stopped is True
    assert modem.hung_up is True
    assert result.answered is True
    assert result.played is True
    assert result.final_state == "answered"
    assert hub.call_state == CALL_STATE_IDLE


async def test_call_and_play_does_not_play_when_unanswered():
    hub = make_hub()
    # Rings the whole time, never answered.
    hub._modem = FakeModem(  # noqa: SLF001
        [CallInfo(CALL_DIR_OUTGOING, CALL_STAT_ALERTING, "+79990001122")]
    )
    result = await hub.async_call_and_play(
        "+79990001122", b"AMRDATA", ring_duration=0.05
    )
    modem = hub._modem  # noqa: SLF001
    # Still uploaded up-front, but never played into a call that didn't connect.
    assert modem.uploaded == b"AMRDATA"
    assert "play" not in modem.order
    assert modem.played is False
    assert modem.stopped is False
    assert modem.hung_up is True
    assert result.answered is False
    assert result.played is False
    assert result.final_state == "no_answer"


async def test_call_and_play_honors_duration_and_volume(monkeypatch):
    # Drop the post-clip grace so the duration branch runs instantly.
    monkeypatch.setattr(hub_mod, "_PLAYBACK_TAIL", 0.0)
    hub = make_hub()
    hub._modem = FakeModem(  # noqa: SLF001
        [
            CallInfo(CALL_DIR_OUTGOING, CALL_STAT_ALERTING, "+79990001122"),
            CallInfo(CALL_DIR_OUTGOING, CALL_STAT_ACTIVE, "+79990001122"),
        ]
    )
    result = await hub.async_call_and_play(
        "+79990001122", b"AMRDATA", duration=0.0, ring_duration=5, volume=45
    )
    modem = hub._modem  # noqa: SLF001
    assert result.played is True
    assert modem.play_volume == 45
    assert modem.stopped is True


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


async def test_last_caller_persists_after_call_clears():
    hub = make_hub()
    hub._modem = FakeModem(  # noqa: SLF001
        [CallInfo(CALL_DIR_INCOMING, CALL_STAT_INCOMING, "+79990001122"), None]
    )
    await hub._refresh_call_state()  # noqa: SLF001
    assert hub.last_caller == "+79990001122"

    # Call ends: incoming state clears, but last_caller must persist.
    await hub._refresh_call_state()  # noqa: SLF001
    assert hub.incoming_call is False
    assert hub.incoming_number is None
    assert hub.last_caller == "+79990001122"


async def test_last_caller_not_overwritten_by_unknown_number():
    hub = make_hub()
    hub._modem = FakeModem(  # noqa: SLF001
        [
            CallInfo(CALL_DIR_INCOMING, CALL_STAT_INCOMING, "+79990001122"),
            None,
            CallInfo(CALL_DIR_INCOMING, CALL_STAT_INCOMING, None),
        ]
    )
    await hub._refresh_call_state()  # noqa: SLF001
    assert hub.last_caller == "+79990001122"

    # Call clears, then a new incoming call arrives with no caller ID.
    await hub._refresh_call_state()  # noqa: SLF001
    await hub._refresh_call_state()  # noqa: SLF001
    assert hub.incoming_call is True
    assert hub.incoming_number is None
    # A None-number call must not clobber the known last_caller.
    assert hub.last_caller == "+79990001122"


async def test_answer_and_record_returns_bytes_and_runs_sequence():
    hub = make_hub()
    fake = FakeModem(
        [
            CallInfo(CALL_DIR_INCOMING, CALL_STAT_INCOMING, "+79990001122"),
            # Caller drops after being answered, ending recording early.
            None,
        ]
    )
    fake.file_bytes = b"AMRDATA"
    hub._modem = fake  # noqa: SLF001

    data = await hub.async_answer_and_record(record_seconds=5)

    assert data == b"AMRDATA"
    assert fake.answered is True
    assert fake.recording_started is True
    assert fake.recording_stopped is True
    assert fake.hung_up is True
    # answer -> start_recording -> ... -> stop_recording -> read -> delete.
    assert fake.order[:2] == ["answer", "start_recording"]
    assert "stop_recording" in fake.order
    assert fake.order.index("file_size") < fake.order.index("read_file")
    assert fake.deleted_files == ["C:\\User\\rec.amr"]
    assert hub.call_state == CALL_STATE_IDLE


async def test_answer_and_record_returns_none_when_no_incoming_call():
    hub = make_hub()
    fake = FakeModem([None])
    hub._modem = fake  # noqa: SLF001

    result = await hub.async_answer_and_record(record_seconds=5)

    assert result is None
    assert fake.answered is False
    assert fake.recording_started is False


async def test_answer_and_record_returns_none_when_recording_empty():
    hub = make_hub()
    fake = FakeModem(
        [CallInfo(CALL_DIR_INCOMING, CALL_STAT_INCOMING, "+79990001122"), None]
    )
    fake.file_bytes = b""  # empty recording
    hub._modem = fake  # noqa: SLF001

    result = await hub.async_answer_and_record(record_seconds=5)

    assert result is None
    assert fake.answered is True
    assert "read_file" not in fake.order  # never read a zero-byte file
    assert fake.deleted_files == ["C:\\User\\rec.amr"]


def test_outgoing_state_mapping():
    assert hub_mod._outgoing_state(CALL_STAT_ACTIVE) == CALL_STATE_ACTIVE  # noqa: SLF001
    assert hub_mod._outgoing_state(CALL_STAT_ALERTING) == CALL_STATE_RINGING  # noqa: SLF001


async def test_poll_incoming_sms_emits_deletes_and_caches():
    received: list[SmsMessage] = []
    updates: list[int] = []
    hub = make_hub(
        on_state_change=lambda: updates.append(1),
        on_incoming_sms=received.append,
    )
    msg = SmsMessage(index=3, sender="+79990001122", timestamp="ts", text="Привет")
    hub._modem = FakeModem(sms=[msg])  # noqa: SLF001

    await hub.async_poll_incoming_sms()

    assert received == [msg]
    assert hub.last_sms == msg
    assert hub._modem.deleted == [3]  # noqa: SLF001
    assert updates  # sensor push happened

    # Second poll: nothing new, no extra event/state push.
    await hub.async_poll_incoming_sms()
    assert received == [msg]


async def test_poll_incoming_sms_no_messages_is_quiet():
    received: list[SmsMessage] = []
    updates: list[int] = []
    hub = make_hub(
        on_state_change=lambda: updates.append(1),
        on_incoming_sms=received.append,
    )
    hub._modem = FakeModem(sms=[])  # noqa: SLF001

    await hub.async_poll_incoming_sms()
    assert received == []
    assert updates == []
    assert hub.last_sms is None


async def test_poll_incoming_sms_multiple_deletes_each():
    received: list[SmsMessage] = []
    hub = make_hub(on_incoming_sms=received.append)
    msgs = [
        SmsMessage(index=1, sender="+79990001122", timestamp="t1", text="One"),
        SmsMessage(index=2, sender="+79990003344", timestamp="t2", text="Two"),
    ]
    hub._modem = FakeModem(sms=msgs)  # noqa: SLF001

    await hub.async_poll_incoming_sms()

    assert [m.text for m in received] == ["One", "Two"]
    assert hub._modem.deleted == [1, 2]  # noqa: SLF001
    assert hub.last_sms == msgs[-1]
