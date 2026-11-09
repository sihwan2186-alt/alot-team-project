import hashlib

from aiot_sim.engines.controller import decide
from aiot_sim.pipeline.simulator import simulate
from aiot_sim.pipeline.validator import validate


def test_observation_hook_preserves_default_physics_and_reads_utf8(project, cfg):
    cfg['personal_profile']={'owner':'김시환'}
    default=simulate(project,cfg,'hook-default')
    calls=[]

    def policy(observation,occupancy,current,minute,rules,*,profile,timestamp,observed_facility):
        assert set(observed_facility)=={'ventilation_on','ventilation_level'}
        assert 'true_co2_ppm' not in observation and 'fault_active' not in observation
        assert profile['room_id']=='STU-B102A'
        calls.append(timestamp)
        return decide(observation,occupancy,current,minute,rules)

    hooked=simulate(project,cfg,'hook-custom',controller_fn=policy)
    assert len(calls)==1440
    for folder in ['raw','truth/environment_truth_1min','truth/thermal_balance_1min']:
        for path in (default/folder).rglob('*.csv'):
            other=hooked/path.relative_to(default)
            assert hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(other.read_bytes()).digest()
    assert validate(hooked)['valid']
