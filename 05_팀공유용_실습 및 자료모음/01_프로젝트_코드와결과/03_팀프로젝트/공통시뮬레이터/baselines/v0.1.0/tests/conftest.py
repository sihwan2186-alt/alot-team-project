import shutil
from pathlib import Path

import pytest

from aiot_sim.catalog import generate
from aiot_sim.config import load
from aiot_sim.profiles import generate as profiles


@pytest.fixture
def project(tmp_path):
    source = Path(__file__).resolve().parents[1]
    shutil.copytree(source / "configs", tmp_path / "configs")
    cfg = load(tmp_path)
    generate(tmp_path)
    profiles(tmp_path, cfg["rules"]["room_profile"])
    return tmp_path


@pytest.fixture
def cfg(project):
    return load(project, {"days": 1, "room_ids": ["STU-B102A"]})


@pytest.fixture
def profile(project):
    from aiot_sim.profiles import load

    return next(p for p in load(project) if p["room_id"] == "STU-B102A")
