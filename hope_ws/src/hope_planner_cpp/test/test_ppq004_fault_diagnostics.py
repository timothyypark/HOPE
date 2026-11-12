import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "scripts/flight_prediction_validation")
)
from ppq004_fault_diagnostics import assess


def raw(fault):
    return dict(
        source=dict(
            transformation=fault,
            epoch_ns=0,
            rows=[
                dict(
                    source_ns=3000000000,
                    source_index=900,
                    original_present=True,
                    present=True,
                )
            ],
        ),
        received=dict(commands=[], full=[], candidates=[], decoded=[]),
    )


def test_missing_orientation_requires_actual_forecast_exposure():
    r = raw("missing_orientation")
    assert assess(r, None, [], [])["status"] == "NOT_COVERED"
    r["received"]["full"] = [
        dict(physical=True, trajectory=[dict(spin_available=True)])
    ]
    assert assess(r, None, [], [])["status"] == "FAIL"
    r["received"]["full"][0]["trajectory"][0]["spin_available"] = False
    assert assess(r, None, [], [])["status"] == "PASS"


def test_wrong_frame_acceptance_is_a_failure_even_without_commands():
    r = raw("wrong_frame")
    rows = [
        dict(stage=name, source_ns=3000000000)
        for name in ("planner_received", "tracker_accepted")
    ]
    assert assess(r, None, rows, [])["status"] == "FAIL"
    rows[-1]["stage"] = "tracker_rejected"
    assert assess(r, None, rows, [])["status"] == "PASS"


def test_duplicate_fixture_must_duplicate_an_actual_ball_observation():
    r = raw("duplicate")
    assert assess(r, None, [], [])["status"] == "NOT_COVERED"
    r["source"]["rows"].append(dict(r["source"]["rows"][0], source_index=901))
    rows = [
        dict(stage=name, source_ns=3000000000)
        for name in ("tracker_accepted", "tracker_rejected")
    ]
    assert assess(r, None, rows, [])["status"] == "PASS"
    rows.append(dict(stage="tracker_accepted", source_ns=3000000000))
    assert assess(r, None, rows, [])["status"] == "FAIL"


def test_delayed_decoder_must_use_remaining_absolute_deadline():
    r = raw("decoder_delay")
    wire = [0.0] * 20
    wire[1] = 1
    wire[14] = 17
    wire[10] = 0.4
    r["received"]["commands"] = [wire]
    decoded = [0.0] * 15
    decoded[0] = 17
    decoded[9] = 0.28
    decoded[14] = 120000000
    r["received"]["decoded"] = [decoded]
    stages = [dict(stage="command_published", sequence=17, source_ns=0, wall_ns=0)]
    assert assess(r, None, stages, [])["status"] == "PASS"
    decoded[9] = 0.4
    assert assess(r, None, stages, [])["status"] == "FAIL"
    r["received"]["decoded"] = []
    assert assess(r, None, stages, [])["status"] == "NOT_COVERED"
