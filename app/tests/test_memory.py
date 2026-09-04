"""Tests for the legacy turn DTO retained by conversation migration."""

from agent.turns.memory import TurnRecord


def test_turn_record_carries_id_and_timestamp_metadata():
    turn = TurnRecord(
        user_input="hi",
        assistant_output="hello",
        turn_id=7,
        timestamp="2026-04-25T10:00:00+00:00",
    )
    assert turn.turn_id == 7
    assert turn.timestamp == "2026-04-25T10:00:00+00:00"
    assert not hasattr(turn, "persist_target")
