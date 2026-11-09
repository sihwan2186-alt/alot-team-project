import json
from datetime import datetime

import pytest

from aiot_sim.pipeline.writer import write_csv
from examples.scenario2_room_candidates import candidates


@pytest.fixture
def candidate_run(tmp_path):
    run = tmp_path
    (run / "reports").mkdir()
    (run / "reports/manifest.json").write_text(
        json.dumps(
            dict(
                status="complete",
                room_ids=["X"],
                config=dict(start_date="2026-09-01", days=1),
            )
        )
    )
    write_csv(
        run / "inputs/rooms.csv",
        [
            dict(
                room_id="X",
                building_code="STU",
                building_name="학생회관",
                room_number="X",
            )
        ],
    )
    write_csv(
        run / "inputs/room_profiles.csv",
        [
            dict(
                room_id="X",
                room_type="SMALL",
                capacity=6,
                area_m2=17,
                opening_time="09:00",
                closing_time="21:00",
                profile_source="synthetic_assumption",
                has_monitor=True,
                has_projector=False,
                has_whiteboard=True,
                has_outlets=True,
            )
        ],
    )
    write_csv(
        run / "raw/sensors_1min/sensor_readings_2026-09-01.csv",
        [
            dict(
                timestamp=f"2026-09-01T10:0{i}:00+09:00",
                room_id="X",
                temperature_c=24,
                humidity_pct=50,
                co2_ppm=500,
                illuminance_lux=400,
                noise_dba=35,
                occupancy_count=0 if i == 0 else 5,
            )
            for i in [0, 1]
        ],
    )
    write_csv(
        run / "events/reservations.csv",
        [],
        ["room_id", "created_at", "start_time", "end_time", "status", "is_no_show"],
    )
    return run


TIME = datetime.fromisoformat("2026-09-01T10:00:00+09:00")


def test_latest_observation_no_future(candidate_run):
    result = candidates(candidate_run, TIME, 4, 60, ("monitor",))
    assert result["eligible_count"] == 1
    assert result["rooms"][0]["occupancy_count"] == 0
    assert result["rooms"][0]["sensor_timestamp"] == TIME.isoformat()
    assert "true_co2_ppm" not in result["rooms"][0]


def reservation(created, start, end, no_show=True):
    return dict(
        room_id="X",
        created_at="2026-09-01T" + created + ":00+09:00",
        start_time="2026-09-01T" + start + ":00+09:00",
        end_time="2026-09-01T" + end + ":00+09:00",
        status="confirmed",
        is_no_show=no_show,
    )


@pytest.mark.parametrize(
    "booking,conflict",
    [
        (reservation("10:01", "10:30", "11:00"), False),
        (reservation("09:00", "10:30", "11:00"), True),
        (reservation("09:00", "11:00", "12:00"), False),
    ],
)
def test_point_in_time_overlap_and_no_show_not_used(candidate_run, booking, conflict):
    write_csv(candidate_run / "events/reservations.csv", [booking])
    result = candidates(candidate_run, TIME, 4)
    assert result["rooms"][0]["known_reservation_conflict"] == conflict
    assert result["eligible_count"] == int(not conflict)


def test_reduce_reservations_before_join(candidate_run):
    write_csv(
        candidate_run / "events/reservations.csv",
        [
            reservation("09:00", "12:00", "13:00"),
            reservation("09:00", "14:00", "15:00"),
        ],
    )
    assert len(candidates(candidate_run, TIME, 4)["rooms"]) == 1


def test_capacity_facility_hours_and_staleness(candidate_run):
    result = candidates(candidate_run, TIME, 7, 60, ("projector",))
    assert {"insufficient_capacity", "missing_projector"} <= set(
        result["rooms"][0]["exclusion_reasons"]
    )
    result = candidates(candidate_run, TIME.replace(hour=20, minute=30), 4, 60)
    assert {"outside_operating_hours", "stale_observation"} <= set(
        result["rooms"][0]["exclusion_reasons"]
    )


def test_naive_time_rejected(candidate_run):
    with pytest.raises(ValueError):
        candidates(candidate_run, TIME.replace(tzinfo=None), 4)
