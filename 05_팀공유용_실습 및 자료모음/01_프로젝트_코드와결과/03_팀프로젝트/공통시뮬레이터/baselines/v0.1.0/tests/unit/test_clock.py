import itertools
from datetime import timedelta

import pytest

from aiot_sim.clock import timestamps
from aiot_sim.config import load


def test_clock():
    times = list(timestamps("2026-09-01"))
    assert len(times) == 1440 and times[-1].isoformat() == "2026-09-01T23:59:00+09:00"
    assert all(b - a == timedelta(minutes=1) for a, b in itertools.pairwise(times))


@pytest.mark.parametrize(
    "option", [{"days": 0}, {"step_minutes": 7}, {"timezone": "UTC"}]
)
def test_bad_configuration(project, option):
    with pytest.raises(ValueError):
        load(project, option)
