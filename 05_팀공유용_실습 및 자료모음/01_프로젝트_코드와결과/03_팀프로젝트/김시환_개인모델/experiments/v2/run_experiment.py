"""Isolated synthetic S1 benchmark using the existing physical engines; never alters v1."""
from pathlib import Path
from dataclasses import replace
from copy import deepcopy
import contextlib
import hashlib
import json
import sys
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parent
PERSONAL=HERE.parents[1]
sys.path.insert(0,str(PERSONAL))
from common import PROFILE, SOURCE, digest
from build_datasets import s1_day, S1_FEATURES
from inference import eligibility
from experiments.v2.policy import policy_metrics
SIM=PERSONAL.parent/'공통시뮬레이터'
sys.path.insert(0,str(SIM/'src'))
from aiot_sim.config import load
from aiot_sim.schemas import EnvironmentState, FacilityState
from aiot_sim.engines.environment import evolve, saturation_g_m3
from aiot_sim.engines.external_environment import outdoor
from aiot_sim.engines.controller import decide
from aiot_sim.engines.sensors import observe
from simulate_personal import PersonalPolicy

# Declared before any generation or metric inspection; not optimized on test.
SCENARIOS={
 'normal':{'label':'건조 외기','rh':45,'temp':23,'crowding':.30,'dark_fraction':0,'missing':False},
 'humid':{'label':'기존 다습 외기','rh':65,'temp':23,'crowding':.30,'dark_fraction':0,'missing':False},
 'crowded':{'label':'혼잡','rh':45,'temp':23,'crowding':.85,'dark_fraction':0,'missing':False},
 'dark':{'label':'일부 조명 고장','rh':45,'temp':23,'crowding':.30,'dark_fraction':.30,'missing':False},
 'missing':{'label':'센서 결측','rh':45,'temp':23,'crowding':.30,'dark_fraction':0,'missing':True},
 'hot_humid':{'label':'고온다습','rh':70,'temp':29,'crowding':.30,'dark_fraction':0,'missing':False},
}
SEEDS={'train':[1201,1202],'validation':[2201],'test':[3201,3202]}
DATES={'train':['2026-09-02','2026-09-16'],'validation':['2026-09-23'],
       'test':['2026-09-27','2026-09-29']}
CORE=['temp','humidity','co2','light','noise','occupancy','capacity','score_current','hour_sin','hour_cos','weekday']
PLAN={'version':'S1_v2_synthetic_benchmark','scenarios':SCENARIOS,'seeds':SEEDS,'dates':DATES,
 'scope':'63 fixed synthetic rooms, 09:00 warmup, 10:00–13:00 observation; not full-day validation',
 'preferences':PROFILE,'features':{'core':CORE,'full':S1_FEATURES},
 'candidates':['persistence','ridge_core','hgb_core','hgb_full','hgb_full_small'],
 'selection':'pooled validation MAE; complex model must improve persistence by >=1%; no test selection or refit',
 'policy':'strict unchanged; supplementary nearest-condition alternatives never called qualified recommendations',
 'missing_scenario':'minute 32..47 modulo 90, half of rooms: CO2 and humidity absent; no fault labels in X',
 'randomness':'independent occupancy and sensor RNGs; matched across scenarios within each seed',
 'known_limitations':['synthetic design-score target, no actual satisfaction',
  'existing weather and moisture equations remain unchanged',
  'scenario weather/occupancy/fault assumptions are interventions, not corrected campus measurements',
  'uniform 13:00 benchmark stop with complete observed future windows only']}

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

def generate(config,profiles,scenario,seed,date,output):
    """Reuse common engine physics, control and sensors; local scenario interventions only."""
    p=SCENARIOS[scenario]
    rules=deepcopy(config['rules'])
    erules=rules['environment']
    erules.update(outdoor_mean_c=p['temp'],outdoor_humidity_pct=p['rh'],
                  fault_spike=rules['fault']['spike'],fault_bias=rules['fault']['bias_per_minute'])
    frules=dict(rules['facility'],ventilation_on_ppm=890,ventilation_off_ppm=850,
                lighting_target_lux=300,cooling_off_c=23,heating_off_c=23)
    rooms=profiles.sort_values('room_id').to_dict('records')
    states={r['room_id']:EnvironmentState() for r in rooms}
    facilities={r['room_id']:FacilityState() for r in rooms}
    occ_rng={r['room_id']:np.random.default_rng(seed*1000+i) for i,r in enumerate(rooms)}
    # observe uses random.Random.gauss; local streams ensure scenario comparisons are paired.
    import random
    sensor_rng={r['room_id']:random.Random(seed*1000+i+100000) for i,r in enumerate(rooms)}
    counts={r['room_id']:0 for r in rooms}
    policy=PersonalPolicy()
    raw=[];truth=[];humidity_capped=0;control_changes=0
    for minute,t in enumerate(pd.date_range(f'{date} 09:00+09:00',f'{date} 12:59+09:00',freq='min')):
        weather=outdoor(t,seed,erules)
        for i,r in enumerate(rooms):
            rid=r['room_id'];state=states[rid]
            if minute%16==0:
                counts[rid]=int(occ_rng[rid].binomial(int(r['capacity']),p['crowding']))
            facility=facilities[rid]
            applied=replace(facility)
            if i<len(rooms)*p['dark_fraction']:
                applied.lighting_level=0
            evolve(state,r,applied,weather,counts[rid],erules,facility_rules=frules)
            humidity_capped+=int(state.humidity_pct>=99.999)
            obs=observe(state,counts[rid],sensor_rng[rid],erules)
            if p['missing'] and i%2==0 and 32<=minute%90<48:
                obs['co2_ppm']=None;obs['humidity_pct']=None
            facilities[rid],changes=policy(obs,counts[rid],facility,minute,frules,
                profile=r,timestamp=t,observed_facility={'ventilation_on':applied.ventilation_on,
                                                       'ventilation_level':applied.ventilation_level})
            control_changes+=len(changes)
            if t.hour>=10:
                raw.append({'timestamp':t.isoformat(),'room_id':rid,**obs})
                truth.append({'timestamp':t.isoformat(),'room_id':rid,'humidity_pct':state.humidity_pct,
                    'absolute_humidity_g_m3':state.absolute_humidity_g_m3,
                    'outdoor_humidity_pct':weather['outdoor_humidity_pct'],
                    'outdoor_temperature_c':weather['outdoor_temperature_c']})
    raw=pd.DataFrame(raw)
    raw.to_csv(output/'sensors.csv.gz',index=False,compression='gzip')
    pd.DataFrame(truth).to_csv(output/'humidity_diagnostics.csv.gz',index=False,compression='gzip')
    return raw,{'rows':len(raw),'humidity_capped_room_minutes':humidity_capped,'control_changes':control_changes,
        'humidity_median':float(raw.humidity_pct.median()),'humidity_pass_fraction':float(raw.humidity_pct.between(40,60).mean())}

def score(y,pred):
    error=np.asarray(pred)-np.asarray(y)
    return {'n':len(error),'mae':float(np.abs(error).mean()),'rmse':float(np.sqrt((error**2).mean())),
            'p95_error':float(np.quantile(np.abs(error),.95))}

def predict(model,features,frame):
    values=frame.score_current.to_numpy() if model is None else model.predict(frame[features])
    return np.clip(values,0,100)

def recommendation_metrics(frame,pred):
    d=frame.copy();d['prediction']=pred
    d['eligible'],_=eligibility(d)
    grouped=['run_id','asof']
    total=d.groupby(grouped).ngroups
    qualified=d[d.eligible]
    if qualified.empty:
        return {'instants':total,'qualified_instants':0,'coverage':0,'top1_regret':None,
                'current_constraint_violation_fraction':None,'future_violation_fraction':None}
    chosen=qualified.sort_values(['prediction','room_id'],ascending=[False,True]).groupby(grouped).head(1)
    best=qualified.groupby(grouped).target_score.max()
    actual=chosen.set_index(grouped).target_score
    return {'instants':total,'qualified_instants':len(chosen),'coverage':len(chosen)/total,
        'top1_regret':float((best-actual).mean()),'current_constraint_violation_fraction':0.0,
        'future_violation_fraction':float((~chosen.future_eligible).mean()),
        'future_condition_note':'future observed window conditions, offline evaluation only'}

def prepare_frame(raw,profiles,job):
    raw=raw.copy();raw['timestamp']=pd.to_datetime(raw.timestamp)
    labeled=s1_day(raw,profiles)
    inputs=s1_day(raw,profiles,include_targets=False)
    # Last incomplete future window cannot be shown as an evaluated benchmark forecast.
    stop=raw.timestamp.max()+pd.Timedelta(minutes=1)
    # Obtain future window condition only for offline recommendation evaluation.
    future=inputs[['room_id','asof','temp','humidity','co2','noise','light','occupancy','capacity']].copy()
    future['future_eligible'],_=eligibility(future)
    future=future[['room_id','asof','future_eligible']].rename(columns={'asof':'target_time'})
    labeled=labeled.merge(future,on=['room_id','target_time'],validate='one_to_one')
    inputs=inputs[inputs.target_time<=stop].copy()
    for frame in (labeled,inputs):
        frame['run_id']=job['run_id'];frame['scenario']=job['scenario'];frame['split']=job['split'];frame['seed']=job['seed']
    return labeled,inputs

def main():
    out=HERE/'artifacts'
    if out.exists():raise FileExistsError('v2 artifacts exist; create a new version before rerunning')
    out.mkdir()
    write(out/'plan.json',PLAN)
    before={p.name:digest(p) for p in (PERSONAL/'results').glob('*_model.joblib')}
    config=load(SIM)
    profiles=pd.read_csv(SOURCE/'inputs/room_profiles.csv')
    assert len(profiles)==63
    inputs_dir=out/'inputs';inputs_dir.mkdir()
    profiles.to_csv(inputs_dir/'room_profiles.csv',index=False)
    (inputs_dir/'rooms.csv').write_bytes((SOURCE/'inputs/rooms.csv').read_bytes())
    parts=[];views=[];generation=[]
    for split,seeds in SEEDS.items():
        for index,seed in enumerate(seeds):
            for scenario in SCENARIOS:
                job={'split':split,'seed':seed,'scenario':scenario,'date':DATES[split][index],
                     'run_id':f'{split}_{seed}_{scenario}'}
                run=out/'runs'/job['run_id'];run.mkdir(parents=True)
                raw,stats=generate(config,profiles,scenario,seed,job['date'],run)
                labeled,view=prepare_frame(raw,profiles,job)
                parts.append(labeled);views.append(view)
                generation.append({**job,**stats,'learning_rows':len(labeled),'inference_rows':len(view),
                    'sensor_sha256':digest(run/'sensors.csv.gz')})
                print('Generated',job['run_id'],len(labeled),flush=True)
    data=pd.concat(parts,ignore_index=True);view=pd.concat(views,ignore_index=True)
    assert not data.duplicated(['run_id','room_id','asof']).any()
    assert (data.target_time-data['asof']).eq(pd.Timedelta(minutes=8)).all()
    assert set(data[data.split=='train'].seed).isdisjoint(set(data[data.split=='test'].seed))
    keep=['run_id','scenario','split','seed','room_id','asof','target_time']+S1_FEATURES
    data[keep+['target_score','future_eligible']].to_csv(out/'S1_dataset.csv.gz',index=False,compression='gzip')
    view[keep].to_csv(out/'S1_inference_inputs.csv.gz',index=False,compression='gzip')
    write(out/'generation.json',generation)
    train=data[data.split=='train'];val=data[data.split=='validation']
    assert train.target_time.max()<val['asof'].min()
    candidates={
        'persistence':(None,CORE),
        'ridge_core':(make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler(),Ridge(alpha=10)),CORE),
        'hgb_core':(HistGradientBoostingRegressor(loss='absolute_error',max_iter=100,max_leaf_nodes=15,
            min_samples_leaf=30,l2_regularization=1,early_stopping=False,random_state=4401),CORE),
        'hgb_full':(HistGradientBoostingRegressor(loss='absolute_error',max_iter=100,max_leaf_nodes=15,
            min_samples_leaf=30,l2_regularization=1,early_stopping=False,random_state=4401),S1_FEATURES),
        'hgb_full_small':(HistGradientBoostingRegressor(loss='absolute_error',max_iter=100,max_leaf_nodes=7,
            min_samples_leaf=40,l2_regularization=2,early_stopping=False,random_state=4401),S1_FEATURES),
    }
    validation={}
    with threadpool_limits(limits=2):
        for name,(model,features) in candidates.items():
            if model is not None:model.fit(train[features],train.target_score)
            valpred=predict(model,features,val)
            validation[name]={'regression':score(val.target_score,valpred),
                              'recommendation':recommendation_metrics(val,valpred),
                              'strict_plus_reference_policy':policy_metrics(val,valpred)}
            print('Validated',name,validation[name]['regression']['mae'],flush=True)
        selected=min(validation,key=lambda n:validation[n]['regression']['mae'])
        if validation[selected]['regression']['mae']>=.99*validation['persistence']['regression']['mae']:
            selected='persistence'
        model,features=candidates[selected]
        bundle={'model':model,'features':features,'baseline_feature':'score_current','selected_name':selected,
            'scenario':'S1','version':'v2','profile':PROFILE,'selection':'validation only; no refit',
            'target_definition':'next 8-minute synthetic design score','dataset_sha256':digest(out/'S1_dataset.csv.gz')}
        joblib.dump(bundle,out/'S1_model.joblib')
        # Freeze selection before the first test metric calculation.
        write(out/'selection.json',{'selected':selected,'validation':validation,'test_used_for_selection':False})
        selected_rec=validation[selected]['recommendation']
        base_rec=validation['persistence']['recommendation']
        adopt_ranking=(selected_rec['top1_regret'] is not None and
            selected_rec['top1_regret']<=base_rec['top1_regret'] and
            selected_rec['future_violation_fraction']<=base_rec['future_violation_fraction'])
        write(out/'operational_decision.json',{'use_forecast_for_ranking':adopt_ranking,
            'ranking_key':'prediction' if adopt_ranking else 'score_current',
            'evidence':'validation recommendation regret and future violation; test not consulted',
            'note':'conservative operational review distinct from original MAE model-selection rule'})
        test=data[data.split=='test'].copy()
        assert val.target_time.max()<test['asof'].min()
        results={}
        for name,which,feats in [('selected',model,features),('persistence',None,CORE)]:
            pred=predict(which,feats,test)
            results[name]={'overall':score(test.target_score,pred),'recommendation':recommendation_metrics(test,pred),
                          'strict_plus_reference_policy':policy_metrics(test,pred),'by_scenario':{}}
            for scenario,g in test.groupby('scenario'):
                gp=predict(which,feats,g)
                results[name]['by_scenario'][scenario]={'regression':score(g.target_score,gp),
                    'recommendation':recommendation_metrics(g,gp)}
            if name=='selected':
                exported=test[['run_id','scenario','room_id','asof','target_time','target_score']].copy()
                exported['prediction']=pred
                exported.to_csv(out/'test_predictions.csv.gz',index=False,compression='gzip')
        # Evaluate the frozen v1 model on these same new cases: descriptive transfer only.
        v1=joblib.load(PERSONAL/'results/S1_model.joblib')
        oldpred=predict(v1['model'],v1['features'],test)
        results['v1_transfer_same_new_test']={'overall':score(test.target_score,oldpred),
            'recommendation':recommendation_metrics(test,oldpred),
            'note':'different training distribution and sample size; not a pure algorithm comparison'}
    assert before=={p.name:digest(p) for p in (PERSONAL/'results').glob('*_model.joblib')}
    review={'selected':selected,'rows':data.groupby('split').size().to_dict(),'test':results,
        'policy_comparison':'strict candidates unchanged; fallback alternatives must remain labelled nonqualified',
        'all_v1_model_hashes_unchanged':True,'model_sha256':digest(out/'S1_model.joblib'),
        'synthetic_only':True,'actual_satisfaction_learning':False}
    write(out/'evaluation.json',review)
    print('COMPLETE',json.dumps(review,ensure_ascii=False,default=str),flush=True)

if __name__=='__main__':main()
