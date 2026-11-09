from datetime import datetime
import math
import pandas as pd
from build_datasets import s1_day, s5_day
from simulate_personal import PersonalPolicy
from aiot_sim.schemas import FacilityState
from inference import predict_snapshot


def profile_frame():
    return pd.DataFrame([{'room_id':'A','capacity':4,'opening_time':'09:00','closing_time':'21:00',
                          'volume_m3':50,'ventilation_off_ach':.3,'ventilation_on_ach':3}])

def test_s1_uses_leq_and_completed_eight_minute_window():
    t=pd.date_range('2026-09-01 10:00+09:00',periods=16,freq='min')
    raw=pd.DataFrame({'timestamp':t,'room_id':'A','temperature_c':23,'humidity_pct':50,
        'co2_ppm':700,'illuminance_lux':400,'noise_dba':[30]*4+[40]*4+[30]*8,'occupancy_count':1})
    result=s1_day(raw,profile_frame())
    assert len(result)==1
    row=result.iloc[0]
    assert row['asof']==t[0]+pd.Timedelta(minutes=8)
    assert row['target_time']==t[0]+pd.Timedelta(minutes=16)
    assert abs(row['noise']-10*math.log10((10**3+10**4)/2))<1e-9
    assert row['noise']!=35

def test_s5_exact_future_time_survives_missing_past_sensor():
    t=pd.date_range('2026-09-01 09:52+09:00',periods=24,freq='min')
    co2=[600+i for i in range(24)];co2[3]=float('nan')
    raw=pd.DataFrame({'timestamp':t,'room_id':'A','co2_ppm':co2,'occupancy_count':1})
    facilities=pd.DataFrame({'timestamp':t,'room_id':'A','ventilation_on':False,'ventilation_level':0})
    result=s5_day(raw,facilities,profile_frame())
    row=result.iloc[0]
    assert row['asof']==t[8] and row['target_time']==t[16]
    assert row['co2_lag8']==600 and row['target_co2']==616

def test_personal_boundaries_and_lookback_do_not_change_source_policy_before_ten():
    rules={'cooling_on_c':26,'cooling_off_c':24.5,'heating_on_c':20,'heating_off_c':21.5,
           'ventilation_on_ppm':1000,'ventilation_off_ppm':750,'lighting_target_lux':350,
           'lighting_hysteresis_lux':50,'minimum_run_minutes':5}
    p=profile_frame().iloc[0].to_dict();policy=PersonalPolicy()
    kwargs={'profile':p,'timestamp':datetime.fromisoformat('2026-09-01T10:00:00+09:00'),
            'observed_facility':{'ventilation_on':False,'ventilation_level':0}}
    observation={'temperature_c':23,'co2_ppm':890,'illuminance_lux':400}
    state,changes=policy(observation,1,FacilityState(),600,rules,**kwargs)
    assert state.ventilation_on
    observation['co2_ppm']=850;kwargs['timestamp']=datetime.fromisoformat('2026-09-01T10:08:00+09:00')
    state,_=policy(observation,1,state,608,rules,**kwargs)
    assert not state.ventilation_on
    kwargs['timestamp']=datetime.fromisoformat('2026-09-01T09:59:00+09:00');observation['co2_ppm']=890
    state,_=policy(observation,1,FacilityState(),599,rules,**kwargs)
    assert not state.ventilation_on


def test_control_does_not_forecast_across_closing_boundary():
    class ForbiddenPrediction:
        def predict(self,rows):raise AssertionError('A forecast crossed the opening-hours contract')
    rules={'cooling_on_c':26,'cooling_off_c':24.5,'heating_on_c':20,'heating_off_c':21.5,
           'ventilation_on_ppm':1000,'ventilation_off_ppm':750,'lighting_target_lux':350,
           'lighting_hysteresis_lux':50,'minimum_run_minutes':5}
    policy=PersonalPolicy({'model':ForbiddenPrediction(),'features':[]})
    p=profile_frame().iloc[0].to_dict()
    state,_=policy({'temperature_c':23,'co2_ppm':870,'illuminance_lux':400},1,FacilityState(),20*60+56,rules,
        profile=p,timestamp=datetime.fromisoformat('2026-09-26T20:56:00+09:00'),
        observed_facility={'ventilation_on':False,'ventilation_level':0})
    assert not policy.trace and not state.ventilation_on


def test_inference_cannot_use_future_target_values():
    class SpyModel:
        def predict(self,rows):
            assert list(rows.columns)==['temp']
            return [55.0]*len(rows)
    t=pd.Timestamp('2026-09-26 10:08+09:00')
    frame=pd.DataFrame([{'room_id':'A','asof':t,'temp':23,'humidity':50,'co2':700,'noise':35,
                         'light':400,'capacity':4,'occupancy':1,'target_score':99}])
    bundle={'model':SpyModel(),'features':['temp'],'baseline_feature':'score_current'}
    a=predict_snapshot('S1',frame,t,bundle)
    frame['target_score']=-1000
    b=predict_snapshot('S1',frame,t,bundle)
    assert a.prediction.tolist()==b.prediction.tolist()==[55.0]


def test_s1_current_input_remains_available_when_future_label_is_missing():
    t=pd.date_range('2026-09-01 10:00+09:00',periods=16,freq='min')
    raw=pd.DataFrame({'timestamp':t,'room_id':'A','temperature_c':23,'humidity_pct':50,
        'co2_ppm':[700]*8+[float('nan')]*8,'illuminance_lux':400,'noise_dba':35,'occupancy_count':1})
    labeled=s1_day(raw,profile_frame())
    inputs=s1_day(raw,profile_frame(),include_targets=False)
    assert labeled.empty
    assert t[0]+pd.Timedelta(minutes=8) in inputs['asof'].tolist()
    assert 'target_score' not in inputs


def test_s5_missing_future_target_cannot_remove_current_inference_row():
    t=pd.date_range('2026-09-01 09:52+09:00',periods=24,freq='min')
    co2=[600+i for i in range(24)];co2[16]=float('nan')
    raw=pd.DataFrame({'timestamp':t,'room_id':'A','co2_ppm':co2,'occupancy_count':1})
    facilities=pd.DataFrame({'timestamp':t,'room_id':'A','ventilation_on':False,'ventilation_level':0})
    inputs=s5_day(raw,facilities,profile_frame(),include_targets=False)
    assert t[8] in inputs['asof'].tolist()
    assert 'target_co2' not in inputs
