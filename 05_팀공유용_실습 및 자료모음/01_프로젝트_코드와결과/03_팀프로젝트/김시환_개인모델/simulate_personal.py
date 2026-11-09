"""Paired synthetic closed-loop runs; forecasts cannot access engine truth."""
import argparse
from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import math, sys
import joblib
import pandas as pd
from threadpoolctl import threadpool_limits
from common import HERE, SIMULATOR, PROFILE, OUTPUT, write_json

sys.path.insert(0,str(SIMULATOR/'src'))
from aiot_sim.config import load
from aiot_sim.engines.controller import decide as original_decide
from aiot_sim.pipeline.simulator import simulate
from aiot_sim.pipeline.validator import validate

class PersonalPolicy:
    def __init__(self,bundle=None):
        self.bundle=bundle
        self.history=defaultdict(lambda:deque(maxlen=9))
        self.forecasts={}
        self.trace=[]
        self.policy_name='kim_sihwan_predictive' if bundle else 'kim_sihwan_rule'

    def __call__(self,observation,occupancy,current,minute,rules,*,profile,timestamp,observed_facility):
        rid=profile['room_id'];co2=observation['co2_ppm']
        history=self.history[rid]
        history.append((minute,co2))
        # Outside the personal analysis window retain the provided common policy.
        if timestamp.hour<PROFILE['analysis_start_hour']:
            return original_decide(observation,occupancy,current,minute,rules)
        personal=dict(rules,ventilation_on_ppm=PROFILE['ventilation_on_ppm'],
                      ventilation_off_ppm=PROFILE['ventilation_off_ppm'],
                      lighting_target_lux=PROFILE['minimum_illuminance_lux'],
                      cooling_off_c=PROFILE['target_temperature_c'],heating_off_c=PROFILE['target_temperature_c'])
        new,changes=original_decide(observation,occupancy,current,minute,personal)
        # Rebuild ventilation decisions with explicit inclusive personal boundaries.
        changes=[change for change in changes if change[0]!='ventilation']
        new.ventilation_on=current.ventilation_on;new.ventilation_level=current.ventilation_level
        if 'ventilation' in current.last_changes:new.last_changes['ventilation']=current.last_changes['ventilation']
        else:new.last_changes.pop('ventilation',None)
        desired=current.ventilation_on
        valid=co2 is not None and math.isfinite(co2)
        if not occupancy:desired=False
        elif valid and co2>=PROFILE['ventilation_on_ppm']:desired=True
        elif valid and co2<=PROFILE['ventilation_off_ppm']:desired=False
        prediction=None
        # The selected model is fixed; test policy changes only on the held-out dates.
        closing_minutes=int(profile['closing_time'][:2])*60+int(profile['closing_time'][3:])
        if (self.bundle and timestamp.date().isoformat()>=PROFILE['test_dates'][0]
                and timestamp.hour*60+timestamp.minute+PROFILE['horizon_minutes']<closing_minutes
                and (timestamp.hour*60+timestamp.minute-600)%8==0 and valid):
            lag1=history[-2][1] if len(history)>=2 else None
            lag8=history[-9][1] if len(history)>=9 and history[-9][0]==minute-8 else None
            clock=(timestamp.hour*60+timestamp.minute)/1440*2*math.pi
            features={'co2':co2,'co2_lag1':lag1,'co2_lag8':lag8,
                'co2_trend':None if lag8 is None else (co2-lag8)/8,'occupancy':occupancy,
                'ventilation_on':float(observed_facility['ventilation_on']),
                'ventilation_level':observed_facility['ventilation_level'],
                'volume_m3':profile['volume_m3'],'ventilation_off_ach':profile['ventilation_off_ach'],
                'ventilation_on_ach':profile['ventilation_on_ach'],'hour_sin':math.sin(clock),'hour_cos':math.cos(clock),
                'weekday':timestamp.weekday()}
            prediction=float(self.bundle['model'].predict(pd.DataFrame([features],columns=self.bundle['features']))[0]) if self.bundle['model'] is not None else co2
            self.forecasts[rid]=(minute,prediction)
            self.trace.append(dict(room_id=rid,asof=timestamp.isoformat(),co2=co2,predicted_co2_8min=prediction))
        cached=self.forecasts.get(rid)
        if self.bundle and valid and occupancy and cached and minute-cached[0]<8:
            if PROFILE['ventilation_off_ppm']<co2<PROFILE['ventilation_on_ppm'] and cached[1]>=PROFILE['ventilation_on_ppm']:
                desired=True
        if desired!=current.ventilation_on and minute-current.last_changes.get('ventilation',-10000)>=rules['minimum_run_minutes']:
            new.ventilation_on=desired;new.ventilation_level=float(desired);new.last_changes['ventilation']=minute
            changes.append(('ventilation',current.ventilation_on,desired))
        return new,changes

def run(policy_name):
    run_id='personal_baseline' if policy_name=='baseline' else 'personal_predictive'
    output=HERE/'simulations'/run_id
    if output.exists():
        raise FileExistsError(f'{output} already exists; do not overwrite simulation evidence')
    cfg=load(SIMULATOR,{'room_ids':PROFILE['simulation_representative_rooms'],'days':30,'seed':20261102})
    cfg['output_path']=str(HERE/'simulations')
    cfg['personal_profile']=PROFILE
    cfg['policy_name']=policy_name
    bundle=None if policy_name=='baseline' else joblib.load(OUTPUT/'S5_model.joblib')
    policy=PersonalPolicy(bundle)
    with threadpool_limits(limits=2):
        path=simulate(SIMULATOR,cfg,run_id,controller_fn=policy)
    result=validate(path)
    assert result['valid'],result
    if policy.trace:pd.DataFrame(policy.trace).to_csv(path/'reports/forecast_trace.csv',index=False)
    write_json(path/'reports/personal_policy.json',{'policy':policy_name,'owner':PROFILE['owner'],
        'model_selected':None if bundle is None else bundle['selected_name'],
        'scope':'4 fixed representative rooms, synthetic 30-day run; test policy intervention from Sep 26; not all 63-room field validation',
        'forecast_rows':len(policy.trace),'validation':result})
    print(path,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--policy',choices=['baseline','predictive'],required=True)
    run(parser.parse_args().policy)
