from datetime import datetime, timedelta

from aiot_sim.pipeline.labeler import RoomLabels

START = datetime.fromisoformat("2026-09-01T09:00:00+09:00")


def cause(kind="hvac_failure"):
    return dict(
        event_id="F1",
        room_id="R",
        start_time=START.isoformat(),
        end_time=(START + timedelta(minutes=30)).isoformat(),
        anomaly_type=kind,
    )


def values(temp=30, co2=600):
    return dict(temperature_c=temp, humidity_pct=50, co2_ppm=co2)


def test_fault_environment_recovery_are_separate(cfg):
    labels = RoomLabels("R", cfg["rules"]["anomaly_label"])
    fault = cause()
    active, _, _ = labels.update(START + timedelta(minutes=29), values(), fault)
    assert (
        active["equipment_fault_active"]
        and active["temperature_anomaly_active"]
        and not active["recovery_active"]
    )
    t = START + timedelta(minutes=30)
    recovery, _, _ = labels.update(t, values(), None, [fault])
    assert (
        not recovery["fault_active"]
        and recovery["recovery_active"]
        and recovery["environment_anomaly_active"]
    )
    # First normal observation at minute 31; observed five-minute stabilization ends at 36.
    for minute in range(31, 36):
        status, closed, _ = labels.update(
            START + timedelta(minutes=minute), values(27), None
        )
        assert (
            status["recovery_active"]
            and not status["environment_anomaly_active"]
            and not closed
        )
    status, closed, _ = labels.update(START + timedelta(minutes=36), values(27), None)
    assert not status["recovery_active"] and closed[0]["status"] == "recovered"
    assert closed[0]["duration_minutes"] == 6


def test_sensor_fault_does_not_create_physical_recovery(cfg):
    labels = RoomLabels("R", cfg["rules"]["anomaly_label"])
    fault = cause("bias")
    status, _, _ = labels.update(START, values(24), fault)
    assert status["sensor_fault_active"] and not status["equipment_fault_active"]
    status, _, _ = labels.update(
        START + timedelta(minutes=30), values(30), None, [fault]
    )
    assert status["environment_anomaly_active"] and not status["recovery_active"]


def test_recovery_right_censor_and_interruption(cfg):
    labels = RoomLabels("R", cfg["rules"]["anomaly_label"])
    fault = cause()
    t = START + timedelta(minutes=30)
    labels.update(t, values(), None, [fault])
    _, closed, _ = labels.update(
        t + timedelta(minutes=1), values(), dict(fault, event_id="F2")
    )
    assert closed[0]["status"] == "interrupted_by_fault"
    labels.update(t + timedelta(minutes=2), values(), None, [fault])
    recovered, episodes = labels.finish(t + timedelta(minutes=3))
    assert (
        recovered[0]["status"] == "right_censored"
        and episodes[0]["status"] == "right_censored"
    )


def test_environment_episode_can_exist_without_fault(cfg):
    labels = RoomLabels("R", cfg["rules"]["anomaly_label"])
    status, _, _ = labels.update(START, values(30), None)
    assert (
        status["environment_anomaly_active"]
        and not status["fault_active"]
        and not status["recovery_active"]
    )
    _, _, closed = labels.update(START + timedelta(minutes=1), values(24), None)
    assert (
        closed[0]["start_time"] == START.isoformat()
        and closed[0]["end_time"] == (START + timedelta(minutes=1)).isoformat()
    )
