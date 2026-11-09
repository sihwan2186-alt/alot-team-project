"""Synthetic S5 observations and paired interventions; policy sees observations only."""
from pathlib import Path
from dataclasses import replace
from collections import deque
from copy import deepcopy
import hashlib
import random
import sys
import math
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PERSONAL=HERE.parents[1]
sys.path.insert(0,str(PERSONAL))
from common import SIMULATOR
from build_datasets import S5_FEATURES,s5_day
from simulate_personal import PersonalPolicy
from aiot_sim.engines.environment import evolve
from aiot_sim.engines.external_environment import outdoor
from aiot_sim.engines.sensors import observe
from aiot_sim.engines.energy import energy
from aiot_sim.schemas import EnvironmentState,FacilityState

SCENARIOS={
 'normal':{'label':'보통 재실','probability':.30,'interval':16},
 'crowded':{'label':'높은 재실','probability':.85,'interval':16},
 'arrival':{'label':'급격한 입실','probability':.30,'interval':8},
 'turnover':{'label':'빠른 인원 변화','probability':.30,'interval':8},
 'missing':{'label':'CO₂ 센서 결측','probability':.30,'interval':16},
 'vent_failure':{'label':'일부 환기 작동 실패','probability':.30,'interval':16},
}

def forecast(bundle,frame):
    name=bundle['name'];current=frame.co2.to_numpy(float)
    if name=='persistence':return current
    if name=='linear_trend':return np.maximum(current+8*frame.co2_trend.fillna(0).to_numpy(),0)
    if name=='mass_balance':
        ach=frame.ventilation_off_ach+(frame.ventilation_on_ach-frame.ventilation_off_ach)*frame.ventilation_level
        source=frame.occupancy*.018*1e6/frame.volume_m3
        decay=np.exp(-ach*8/60)
        return np.maximum(425+(current-425)*decay+source*(-np.expm1(-ach*8/60))/ach,0).to_numpy()
    return np.maximum(bundle['model'].predict(frame[bundle['features']]),0)

def simulate(config,profiles,scenario,seed,date,root,*,bundle=None,margin=0,collect=True):
    """One-hour warmup; record 09:52–12:59; control effects measured 10:00–13:00."""
    root.mkdir(parents=True,exist_ok=True)
    rows=profiles.sort_values('room_id').to_dict('records')
    erules=deepcopy(config['rules']['environment'])
    erules.update(fault_spike=config['rules']['fault']['spike'],fault_bias=config['rules']['fault']['bias_per_minute'])
    frules=config['rules']['facility']
    states={r['room_id']:EnvironmentState() for r in rows}
    facilities={r['room_id']:FacilityState() for r in rows}
    occ_rng={r['room_id']:np.random.default_rng(seed*1000+i) for i,r in enumerate(rows)}
    obs_rng={r['room_id']:random.Random(seed*1000+i+100000) for i,r in enumerate(rows)}
    occupancy={r['room_id']:0 for r in rows}
    history={r['room_id']:deque(maxlen=9) for r in rows}
    policy=PersonalPolicy();cached={}
    sensor_rows=[];facility_rows=[];trace=[]
    exogenous=hashlib.sha256()
    total={'occupied_room_minutes':0,'co2_ge_890_occupied_room_minutes':0,'excess_ppm_room_minutes':0.,
           'co2_occupied_sum':0.,'max_true_co2_ppm':0.,'total_energy_kwh':0.,'ventilation_energy_kwh':0.,
           'ventilation_applied_room_minutes':0,'ventilation_requested_switches':0,'blocked_on_room_minutes':0,
           'minimum_run_violations':0,'missing_observation_room_minutes':0}
    last_switch={r['room_id']:-10000 for r in rows}
    scenario_config=SCENARIOS[scenario]
    for minute,t in enumerate(pd.date_range(f'{date} 09:00+09:00',f'{date} 12:59+09:00',freq='min')):
        weather=outdoor(t,seed,erules)
        if minute%scenario_config['interval']==0:
            probability=scenario_config['probability']
            if scenario=='arrival':probability=.10 if t.hour*60+t.minute<630 else .85 if t.hour*60+t.minute<690 else .30
            if scenario=='turnover':probability=.15 if (minute//8)%2==0 else .85
            for r in rows:
                rid=r['room_id'];occupancy[rid]=int(occ_rng[rid].binomial(int(r['capacity']),probability))
        exogenous.update(repr((t.isoformat(),weather,[occupancy[r['room_id']] for r in rows],scenario)).encode())
        observations={};applied_states={}
        for i,r in enumerate(rows):
            rid=r['room_id'];state=states[rid];command=facilities[rid]
            applied=replace(command)
            blocked=scenario=='vent_failure' and i<len(rows)/3 and 630<=t.hour*60+t.minute<720
            if blocked:applied.ventilation_on=False;applied.ventilation_level=0.
            applied_states[rid]=applied
            evolve(state,r,applied,weather,occupancy[rid],erules,facility_rules=frules)
            obs=observe(state,occupancy[rid],obs_rng[rid],erules)
            if scenario=='missing' and i%2==0 and 32<=minute%90<48:obs['co2_ppm']=None
            observations[rid]=obs;history[rid].append((minute,obs['co2_ppm']))
            if t.hour>=10:
                power=energy(r,applied,frules)
                total['total_energy_kwh']+=power['interval_energy_kwh']
                total['ventilation_energy_kwh']+=power['ventilation_power_kw']/60
                total['ventilation_applied_room_minutes']+=int(applied.ventilation_on)
                total['blocked_on_room_minutes']+=int(blocked and command.ventilation_on)
                total['missing_observation_room_minutes']+=int(obs['co2_ppm'] is None)
                total['max_true_co2_ppm']=max(total['max_true_co2_ppm'],state.co2_ppm)
                if occupancy[rid]>0:
                    total['occupied_room_minutes']+=1
                    total['co2_occupied_sum']+=state.co2_ppm
                    total['co2_ge_890_occupied_room_minutes']+=int(state.co2_ppm>=890)
                    total['excess_ppm_room_minutes']+=max(state.co2_ppm-890,0)
            if collect and minute>=52:
                sensor_rows.append({'timestamp':t,'room_id':rid,'co2_ppm':obs['co2_ppm'],'occupancy_count':obs['occupancy_count']})
                facility_rows.append({'timestamp':t,'room_id':rid,'ventilation_on':applied.ventilation_on,'ventilation_level':applied.ventilation_level})
        # Predictions are batched; neither environment truth, future counts nor failure flags are passed.
        if bundle and t.hour>=10 and (t.hour*60+t.minute-600)%8==0 and t.hour*60+t.minute+8<780:
            features=[]
            for r in rows:
                rid=r['room_id'];obs=observations[rid];co2=obs['co2_ppm'];h=history[rid]
                if co2 is None:continue
                lag1=h[-2][1] if len(h)>=2 else None
                lag8=h[-9][1] if len(h)>=9 and h[-9][0]==minute-8 else None
                phase=(t.hour*60+t.minute)/1440*2*math.pi
                features.append({'room_id':rid,'co2':co2,'co2_lag1':lag1,'co2_lag8':lag8,
                    'co2_trend':None if lag8 is None else (co2-lag8)/8,'occupancy':obs['occupancy_count'],
                    'ventilation_on':float(applied_states[rid].ventilation_on),
                    'ventilation_level':applied_states[rid].ventilation_level,
                    'volume_m3':r['volume_m3'],'ventilation_off_ach':r['ventilation_off_ach'],
                    'ventilation_on_ach':r['ventilation_on_ach'],'hour_sin':math.sin(phase),'hour_cos':math.cos(phase),'weekday':t.weekday()})
            if features:
                f=pd.DataFrame(features)
                for rid,pred in zip(f.room_id,forecast(bundle,f)):
                    cached[rid]=(minute,float(pred))
        for r in rows:
            rid=r['room_id'];old=facilities[rid];obs=observations[rid];actual=applied_states[rid]
            new,changes=policy(obs,obs['occupancy_count'],old,minute,frules,profile=r,timestamp=t,
                observed_facility={'ventilation_on':actual.ventilation_on,'ventilation_level':actual.ventilation_level})
            co2=obs['co2_ppm'];estimate=cached.get(rid)
            if (bundle and t.hour>=10 and estimate and minute-estimate[0]<8 and co2 is not None and occupancy[rid]>0
                and 850<co2<890 and estimate[1]+margin>=890 and not new.ventilation_on
                and minute-old.last_changes.get('ventilation',-10000)>=frules['minimum_run_minutes']):
                new.ventilation_on=True;new.ventilation_level=1.;new.last_changes['ventilation']=minute
            if new.ventilation_on!=old.ventilation_on:
                if t.hour>=10:
                    total['ventilation_requested_switches']+=1
                    total['minimum_run_violations']+=int(minute-last_switch[rid]<frules['minimum_run_minutes'])
                last_switch[rid]=minute
            facilities[rid]=new
            if not collect and t.hour>=10:
                trace.append({'timestamp':t,'room_id':rid,'observed_co2_ppm':co2,
                    'true_co2_ppm_evaluation_only':states[rid].co2_ppm,
                    'predicted_co2_ppm':None if estimate is None else estimate[1],
                    'applied_ventilation':actual.ventilation_on,'next_requested_ventilation':new.ventilation_on})
    total['occupied_co2_mean_ppm']=total.pop('co2_occupied_sum')/max(total['occupied_room_minutes'],1)
    total['exogenous_sha256']=exogenous.hexdigest()
    if collect:
        raw=pd.DataFrame(sensor_rows);facility=pd.DataFrame(facility_rows)
        raw.to_csv(root/'sensors.csv.gz',index=False,compression='gzip')
        facility.to_csv(root/'facility.csv.gz',index=False,compression='gzip')
        return raw,facility,total
    pd.DataFrame(trace).to_csv(root/'trace.csv.gz',index=False,compression='gzip')
    return total

def dataset(raw,facility,profiles,job):
    labeled=s5_day(raw,facility,profiles)
    inputs=s5_day(raw,facility,profiles,include_targets=False)
    stop=raw.timestamp.max()
    inputs=inputs[inputs.target_time<=stop].copy()
    for d in (labeled,inputs):
        d['run_id']=job['run_id'];d['scenario']=job['scenario'];d['split']=job['split'];d['seed']=job['seed']
    return labeled,inputs
