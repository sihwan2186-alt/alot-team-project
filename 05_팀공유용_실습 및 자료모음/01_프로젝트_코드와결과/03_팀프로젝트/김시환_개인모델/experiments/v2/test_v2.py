"""Boundary and recommendation-contract checks for the new experimental path."""
from pathlib import Path
import sys
import pandas as pd

PERSONAL=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PERSONAL))
from experiments.v2.run_experiment import prepare_frame
from experiments.v2.policy import reference_alternatives

def test_last_complete_future_window_is_not_discarded():
    times=pd.date_range('2026-09-27 10:00+09:00',periods=180,freq='min')
    raw=pd.DataFrame({'timestamp':times,'room_id':'A','temperature_c':23,'humidity_pct':50,
        'co2_ppm':700,'noise_dba':35,'illuminance_lux':400,'occupancy_count':1})
    profiles=pd.DataFrame([{'room_id':'A','capacity':4,'opening_time':'09:00','closing_time':'21:00'}])
    job={'run_id':'test','scenario':'normal','split':'test','seed':3201}
    labeled,inputs=prepare_frame(raw,profiles,job)
    assert labeled['asof'].max()==pd.Timestamp('2026-09-27 12:48+09:00')
    assert labeled.target_time.max()==pd.Timestamp('2026-09-27 12:56+09:00')
    assert inputs.target_time.max()<=pd.Timestamp('2026-09-27 13:00+09:00')
    assert not any(c in inputs for c in ['target_score','future_eligible'])

def test_reference_cannot_include_full_high_co2_or_qualified_room():
    d=pd.DataFrame([
        {'room_id':'humid','eligible':False,'capacity':4,'occupancy':1,'co2':700,'exclusion_reason':'습도 범위','prediction':20},
        {'room_id':'full','eligible':False,'capacity':4,'occupancy':4,'co2':700,'exclusion_reason':'여유 좌석','prediction':99},
        {'room_id':'co2','eligible':False,'capacity':4,'occupancy':1,'co2':890,'exclusion_reason':'CO₂ 기준','prediction':99},
        {'room_id':'good','eligible':True,'capacity':4,'occupancy':1,'co2':700,'exclusion_reason':'','prediction':99}])
    original=d.copy(deep=True)
    references=reference_alternatives(d)
    assert references.room_id.tolist()==['humid']
    assert not references.eligible.any()
    pd.testing.assert_frame_equal(d,original)
