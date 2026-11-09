"""Boundary and information-contract checks for S5 comparison helpers."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from simulation import forecast,dataset

def test_mass_balance_equilibrium_and_known_source():
    d=pd.DataFrame([{'co2':425.,'occupancy':0,'volume_m3':60.,'ventilation_off_ach':.3,
                    'ventilation_on_ach':3.,'ventilation_level':1.}])
    assert forecast({'name':'mass_balance'},d)[0]==425.
    d['occupancy']=2
    expected=425+(2*.018*1e6/60)*(-np.expm1(-3*8/60))/3
    assert np.isclose(forecast({'name':'mass_balance'},d)[0],expected)

def test_predictor_cannot_read_future_truth_columns():
    class Spy:
        def predict(self,x):
            assert x.columns.tolist()==['co2']
            return x.co2.to_numpy()+10
    d=pd.DataFrame({'co2':[800.],'target_co2':[2000.],'fault':[True]})
    b={'name':'learned','model':Spy(),'features':['co2']}
    a=forecast(b,d)
    d['target_co2']=-10000;d['fault']=False
    np.testing.assert_array_equal(a,forecast(b,d))

def test_missing_future_does_not_remove_current_inference_input():
    ts=pd.date_range('2026-09-30 09:52+09:00',periods=32,freq='min')
    values=[700.]*32;values[16]=np.nan
    raw=pd.DataFrame({'timestamp':ts,'room_id':'A','co2_ppm':values,'occupancy_count':1})
    facility=pd.DataFrame({'timestamp':ts,'room_id':'A','ventilation_on':False,'ventilation_level':0})
    profiles=pd.DataFrame([{'room_id':'A','volume_m3':60,'ventilation_off_ach':.3,'ventilation_on_ach':3.,
                           'opening_time':'09:00','closing_time':'21:00'}])
    job={'run_id':'audit','scenario':'missing','split':'audit','seed':6401}
    labeled,inputs=dataset(raw,facility,profiles,job)
    assert ts[8] not in labeled['asof'].tolist()
    assert ts[8] in inputs['asof'].tolist()
    assert 'target_co2' not in inputs
    assert inputs.target_time.max()<=ts[-1]

def test_unknown_trend_remains_in_grouped_population():
    from run_comparison import tagged
    d=pd.DataFrame({'room_id':['A'],'asof':[pd.Timestamp('2026-09-30 10:00+09:00')],
        'co2':[800.],'co2_lag1':[799.],'co2_lag8':[np.nan],'co2_trend':[np.nan],
        'occupancy':[1],'ventilation_on':[0.],'volume_m3':[60.],'ventilation_on_ach':[3.]})
    profiles=pd.DataFrame({'room_id':['A'],'capacity':[4]})
    result=tagged(d,profiles)
    assert result.trend_band.tolist()==['unknown']
    assert result.groupby('trend_band').size().sum()==len(d)
