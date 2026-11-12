import sys
from pathlib import Path
import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "scripts/flight_prediction_validation")
)
from ppq004_event_diagnostics import diagnose


def row(time, phase="after", present=True, spin=False, generation=1, events=()):
    return dict(
        source_ns=time,
        source_index=time,
        phase=phase,
        present=present,
        accepted=present,
        spin_available=spin,
        generation=generation,
        play_state="OPPONENT_SERVE",
        events=list(events),
    )


def event(generation=1, occurrence=10, available=20):
    return dict(
        id=1,
        generation=generation,
        kind="table_bounce",
        status=1,
        occurrence_ns=occurrence,
        available_ns=available,
    )


def test_repeated_event_rows_are_one_confirmed_event():
    contact = dict(occurrence_interval_ns=[9, 11], occurrence_estimate_ns=10)
    result = diagnose(
        [row(20, events=[event()]), row(21, events=[event()])], [], [contact]
    )
    assert result["status"] == "PASS"
    assert len(result["unique_confirmed_events"]) == 1
    match = result["contact_matches"][0]
    assert match["status"] == "MATCHED_PROXY"
    assert match["occurrence_error_to_proxy_estimate_ms"] == [0]


def test_timer_event_is_retained_and_future_credit_fails():
    result = diagnose([row(15, phase="after_expire", events=[event()])], [], [])
    assert result["status"] == "FAIL"
    assert result["unique_confirmed_events"][0]["first_seen_ns"] == 15
    assert {r["kind"] for r in result["invariant_violations"]} == {
        "future_confirmation"
    }


def test_wrong_generation_event_cannot_receive_current_credit():
    result = diagnose([row(20, generation=2, events=[event()])], [], [])
    assert result["status"] == "FAIL"
    assert result["invariant_violations"][0]["kind"] == "wrong_generation"


def test_spin_gap_latency_does_not_fabricate_zero_spin():
    result = diagnose(
        [row(1, present=False), row(2, present=False), row(3), row(4, spin=True)],
        [],
        [],
    )
    gap = result["gaps"][0]
    assert gap["missing_frames"] == 2
    assert gap["first_return_ns"] == 3
    assert not gap["spin_available_on_return"]
    assert gap["first_spin_available_after_ns"] == 4
    assert result["unqualified"]["spin_magnitude_accuracy"].startswith("NOT_COVERED")


def test_confirmation_delay_starts_at_annotation_availability():
    annotation = dict(
        begin_ns=1,
        end_ns=30,
        available_ns=20,
        expected_state="OPPONENT_SERVE",
        review_status="REVIEWED",
    )
    result = diagnose([row(10), row(25)], [annotation], [])
    scored = result["annotation_confirmation"][0]
    assert scored["causally_scored_frames"] == 1
    assert scored["first_correct_source_ns"] == 25
    assert scored["confirmation_delay_after_availability_ms"] == pytest.approx(5e-6)
