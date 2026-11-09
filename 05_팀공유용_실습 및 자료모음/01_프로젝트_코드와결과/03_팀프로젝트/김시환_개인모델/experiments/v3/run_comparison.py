"""Predeclared multi-method S1 benchmark, new seed audit, and subgroup diagnostics."""
from pathlib import Path
from time import perf_counter
import json
import sys
import warnings
import numpy as np
import pandas as pd
import joblib
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (ExtraTreesRegressor,RandomForestRegressor,GradientBoostingRegressor,
                             HistGradientBoostingRegressor,HistGradientBoostingClassifier)
from sklearn.linear_model import Ridge,ElasticNet
from sklearn.neighbors import KNeighborsRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.svm import LinearSVR
from sklearn.neural_network import MLPRegressor
from sklearn.compose import TransformedTargetRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parent
PERSONAL=HERE.parents[1]
sys.path.insert(0,str(PERSONAL))
from common import SOURCE,SIMULATOR,digest
from build_datasets import S1_FEATURES
from inference import eligibility
from experiments.v2.run_experiment import generate,prepare_frame,SCENARIOS,CORE
from aiot_sim.config import load

OUT=HERE/'artifacts'
V2=HERE.parent/'v2/artifacts'
FEATURES=S1_FEATURES
ABLATIONS={
 'full':FEATURES,
 'no_score':[f for f in FEATURES if f!='score_current'],
 'no_humidity':[f for f in FEATURES if f!='humidity'],
 'no_noise':[f for f in FEATURES if f not in ['noise','noise_change']],
 'no_co2':[f for f in FEATURES if f not in ['co2','co2_change','co2_missing_ratio']],
 'no_light':[f for f in FEATURES if f!='light'],
 'no_seats':[f for f in FEATURES if f not in ['occupancy','capacity']],
 'no_clock':[f for f in FEATURES if f not in ['hour_sin','hour_cos','weekday']],
 'no_changes':[f for f in FEATURES if f not in ['co2_change','noise_change','temp_change']],
 'sensors_only':['temp','humidity','co2','light','noise','occupancy','capacity'],
}
PLAN={'version':'S1_v3_multimethod','synthetic_only':True,'conditions_unchanged':True,
 'source':'v2 frozen train and validation; prior test is not used for selection',
 'fresh_audit_seeds':[5401,5402],'fresh_audit_dates':['2026-09-30','2026-10-01'],
 'scenarios':list(SCENARIOS),'rooms':63,'observation_hours':'10:00–13:00 with 09:00 warmup',
 'features':FEATURES,'feature_ablations':ABLATIONS,
 'primary_selection':'validation MAE, at least 1% improvement over persistence; exclude convergence warnings',
 'ranking_selection':'validation only: future violation <= current-score baseline; minimize regret; otherwise baseline',
 'ranking_methods':['current','forecast','min_co2','min_noise','ensemble','risk_5','risk_10','risk_20'],
 'risk':'train-only HGB classifier of future_eligible; raw scores not calibrated probabilities',
 'generalization':'fixed HGB full model; leave one building or scenario or train seed out; evaluate fresh audit',
 'time_generalization':'fit before 11:00 and 12:00 (target strictly before cutoff), evaluate later fresh-audit hours',
 'subgroups':['scenario','building','room','hour','occupancy_ratio','humidity','co2','noise','seat_availability',
              'seed','current_eligibility','past_feature_missing','current_co2_missing'],
 'interpretation':'all fixed candidates are descriptively reported on the same new audit; no winner chosen on audit',
 'ablation_warning':'score_current already summarizes channels; removing one channel alone does not fully remove its information',
 'uncertainty':'only two fresh seeds; no statistical significance or real-world performance claim'}

def write(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

def save_csv(name,rows):
    pd.DataFrame(rows).to_csv(OUT/name,index=False,encoding='utf-8-sig')

def linear(model):
    return make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler(),model)

def hgb(**kwargs):
    return HistGradientBoostingRegressor(loss='absolute_error',max_iter=100,max_leaf_nodes=15,
        min_samples_leaf=30,l2_regularization=1,early_stopping=False,random_state=6601,**kwargs)

def methods():
    return {
      'persistence':None,
      'train_median':DummyRegressor(strategy='median'),
      'ridge_1':linear(Ridge(alpha=1)),
      'ridge_100':linear(Ridge(alpha=100)),
      'elastic_net':linear(ElasticNet(alpha=.03,l1_ratio=.3,max_iter=5000,random_state=6601)),
      'knn_15':linear(KNeighborsRegressor(n_neighbors=15,weights='distance',n_jobs=2)),
      'knn_51':linear(KNeighborsRegressor(n_neighbors=51,weights='distance',n_jobs=2)),
      'tree_depth6':make_pipeline(SimpleImputer(strategy='median',add_indicator=True),DecisionTreeRegressor(max_depth=6,min_samples_leaf=20,random_state=6601)),
      'tree_depth12':make_pipeline(SimpleImputer(strategy='median',add_indicator=True),DecisionTreeRegressor(max_depth=12,min_samples_leaf=20,random_state=6601)),
      'random_forest':make_pipeline(SimpleImputer(strategy='median',add_indicator=True),RandomForestRegressor(n_estimators=120,max_depth=14,min_samples_leaf=10,n_jobs=2,random_state=6601)),
      'extra_trees':make_pipeline(SimpleImputer(strategy='median',add_indicator=True),ExtraTreesRegressor(n_estimators=120,max_depth=18,min_samples_leaf=10,n_jobs=2,random_state=6601)),
      'hgb_absolute15':hgb(),
      'hgb_squared15':HistGradientBoostingRegressor(loss='squared_error',max_iter=100,max_leaf_nodes=15,min_samples_leaf=30,l2_regularization=1,early_stopping=False,random_state=6601),
      'hgb_absolute7':HistGradientBoostingRegressor(loss='absolute_error',max_iter=100,max_leaf_nodes=7,min_samples_leaf=40,l2_regularization=2,early_stopping=False,random_state=6601),
      'hgb_absolute31':HistGradientBoostingRegressor(loss='absolute_error',max_iter=100,max_leaf_nodes=31,min_samples_leaf=30,l2_regularization=1,early_stopping=False,random_state=6601),
      'gradient_huber':make_pipeline(SimpleImputer(strategy='median',add_indicator=True),GradientBoostingRegressor(loss='huber',n_estimators=100,max_depth=3,min_samples_leaf=20,random_state=6601)),
      'linear_svr':linear(LinearSVR(C=1,max_iter=10000,random_state=6601)),
      'mlp_64_32':TransformedTargetRegressor(regressor=linear(MLPRegressor(hidden_layer_sizes=(64,32),max_iter=200,
          early_stopping=False,alpha=.01,random_state=6601)),transformer=StandardScaler()),
    }

def predict(model,d,features=FEATURES):
    return np.clip(d.score_current.to_numpy() if model is None else model.predict(d[features]),0,100)

def errors(y,p):
    e=np.asarray(p)-np.asarray(y)
    return {'n':len(e),'mae':float(np.abs(e).mean()),'rmse':float(np.sqrt(np.square(e).mean())),
        'p95_absolute_error':float(np.quantile(np.abs(e),.95)),'bias':float(e.mean())}

def ranking(d,utility):
    frame=d.copy();frame['_utility']=utility
    good,_=eligibility(frame)
    q=frame[good]
    total=frame.groupby(['run_id','asof']).ngroups
    if q.empty:return {'instants':total,'qualified_instants':0,'coverage':0.,'regret':None,'future_violation':None}
    chosen=q.sort_values(['_utility','room_id'],ascending=[False,True]).groupby(['run_id','asof']).head(1)
    best=q.groupby(['run_id','asof']).target_score.max()
    actual=chosen.set_index(['run_id','asof']).target_score
    return {'instants':total,'qualified_instants':len(chosen),'coverage':len(chosen)/total,
        'regret':float((best-actual).mean()),'future_violation':float((~chosen.future_eligible).mean()),
        'current_violation':0.0}

def fit_one(model,train,features=FEATURES):
    start=perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        if model is not None:model.fit(train[features],train.target_score)
    return {'fit_seconds':perf_counter()-start,'warnings':[str(w.message) for w in caught],
            'converged':not any(issubclass(w.category,ConvergenceWarning) for w in caught)}

def tag_groups(d):
    d=d.copy()
    d['building']=d.room_id.str.split('-').str[0]
    d['hour']=d['asof'].dt.hour.astype(str)
    d['occupancy_ratio']=pd.cut(d.occupancy/d.capacity,[-.001,.3,.7,1.01],labels=['low_0_30','mid_30_70','high_70_100']).astype(str)
    d['humidity_band']=pd.cut(d.humidity,[-np.inf,40,60,75,np.inf],right=False,labels=['below40','40to60','60to75','75plus']).astype(str)
    d['co2_band']=pd.cut(d.co2,[-np.inf,700,890,1100,np.inf],right=False,labels=['below700','700to890','890to1100','1100plus']).astype(str)
    d['noise_band']=np.where(d.noise<=45,'within45','over45')
    d['seats_band']=np.where(d.capacity-d.occupancy>=1,'available','full')
    d['current_eligibility']=np.where(eligibility(d)[0],'qualified','unqualified')
    d['past_feature_missing']=np.where(d[['temp_change','co2_change','noise_change']].isna().any(axis=1),'missing','complete')
    d['current_co2_missing']=np.where(d.co2_missing_ratio>0,'some_missing','complete')
    return d

def main():
    if OUT.exists():raise FileExistsError('Do not overwrite a completed or partial experiment; use a new version')
    OUT.mkdir()
    candidates=methods()
    PLAN['model_methods']=list(candidates)
    write('plan.json',PLAN)
    frozen={str(p):digest(p) for folder in [PERSONAL/'results',V2] for p in folder.glob('*_model.joblib')}
    data=pd.read_csv(V2/'S1_dataset.csv.gz',parse_dates=['asof','target_time'])
    train=data[data.split=='train'].copy();val=data[data.split=='validation'].copy()
    assert train.target_time.max()<val['asof'].min()
    validation=[];fitted={};valpred={};ablation_models={};ablation_val=[]
    with threadpool_limits(limits=2):
        for name,model in candidates.items():
            info=fit_one(model,train)
            p=predict(model,val)
            row={'method':name,**errors(val.target_score,p),**info}
            validation.append(row);fitted[name]=model;valpred[name]=p
            save_csv('model_validation.csv',validation)
            print('MODEL',name,'validation',round(row['mae'],4),'seconds',round(info['fit_seconds'],1),flush=True)
            joblib.dump({'model':model,'features':FEATURES},OUT/f'model_{name}.joblib')
        eligible=[r for r in validation if r['converged']]
        selected=min(eligible,key=lambda r:r['mae'])['method']
        baseline=next(r['mae'] for r in validation if r['method']=='persistence')
        if next(r['mae'] for r in validation if r['method']==selected)>=.99*baseline:selected='persistence'
        for name,features in ABLATIONS.items():
            model=hgb();info=fit_one(model,train,features)
            p=predict(model,val,features)
            ablation_models[name]=model
            ablation_val.append({'ablation':name,'feature_count':len(features),**errors(val.target_score,p),**info})
            print('ABLATION',name,flush=True)
        save_csv('feature_validation.csv',ablation_val)
        risk=HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=15,min_samples_leaf=30,l2_regularization=2,
            early_stopping=False,random_state=6601)
        risk.fit(train[FEATURES],train.future_eligible.astype(int))
        risk_val=risk.predict_proba(val[FEATURES])[:,1]
        best_three=[r['method'] for r in sorted(eligible,key=lambda r:r['mae'])[:3]]
        ensemble=np.mean([valpred[n] for n in best_three],axis=0)
        def utilities(frame,pred,ens,risk_score):
            return {'current':frame.score_current.to_numpy(),'forecast':pred,'min_co2':-frame.co2.to_numpy(),
                    'min_noise':-frame.noise.to_numpy(),'ensemble':ens,
                    **{f'risk_{a}':pred-a*(1-risk_score) for a in [5,10,20]}}
        vr=[{'policy':name,**ranking(val,u)} for name,u in utilities(val,valpred[selected],ensemble,risk_val).items()]
        base=next(r for r in vr if r['policy']=='current')
        feasible=[r for r in vr if r['future_violation'] is not None and r['future_violation']<=base['future_violation']]
        selected_policy=min(feasible,key=lambda r:r['regret'])['policy']
        selection={'selected_model':selected,'selected_ranking':selected_policy,'ensemble_members':best_three,
            'validation_ranking':vr,'new_audit_used_for_selection':False,
            'selection_complete_before_new_generation':True}
        write('selection.json',selection)
        save_csv('ranking_validation.csv',vr)
        # Generate brand-new seeds only after both selections have been persisted.
        config=load(SIMULATOR);profiles=pd.read_csv(V2/'inputs/room_profiles.csv')
        audit_parts=[];audit_views=[];runs=[]
        for seed,date in zip(PLAN['fresh_audit_seeds'],PLAN['fresh_audit_dates']):
            for scenario in SCENARIOS:
                job={'split':'audit','seed':seed,'date':date,'scenario':scenario,'run_id':f'audit_{seed}_{scenario}'}
                root=OUT/'runs'/job['run_id'];root.mkdir(parents=True)
                raw,stats=generate(config,profiles,scenario,seed,date,root)
                labels,view=prepare_frame(raw,profiles,job)
                audit_parts.append(labels);audit_views.append(view);runs.append({**job,**stats,'source_sha256':digest(root/'sensors.csv.gz')})
                print('NEW AUDIT',job['run_id'],flush=True)
        audit=pd.concat(audit_parts,ignore_index=True)
        keys=['run_id','scenario','split','seed','room_id','asof','target_time']
        audit[keys+FEATURES+['target_score','future_eligible']].to_csv(OUT/'audit_dataset.csv.gz',index=False,compression='gzip')
        pd.concat(audit_views,ignore_index=True)[keys+FEATURES].to_csv(OUT/'audit_inference_inputs.csv.gz',index=False,compression='gzip')
        write('generation.json',runs)
        assert val.target_time.max()<audit['asof'].min()
        predictions={};test_rows=[];subgroups=[]
        tagged=tag_groups(audit)
        groups={'scenario':'scenario','building':'building','room':'room_id','hour':'hour','occupancy_ratio':'occupancy_ratio',
            'humidity':'humidity_band','co2':'co2_band','noise':'noise_band','seat_availability':'seats_band',
            'seed':'seed','current_eligibility':'current_eligibility','past_feature_missing':'past_feature_missing','current_co2_missing':'current_co2_missing'}
        for name,model in fitted.items():
            start=perf_counter();p=predict(model,audit);predictions[name]=p
            test_rows.append({'method':name,**errors(audit.target_score,p),'predict_seconds':perf_counter()-start,
                'macro_scenario_mae':float(pd.DataFrame({'scenario':audit.scenario,'e':np.abs(p-audit.target_score)}).groupby('scenario').e.mean().mean()),
                'macro_room_mae':float(pd.DataFrame({'room':audit.room_id,'e':np.abs(p-audit.target_score)}).groupby('room').e.mean().mean())})
            tagged['_pred']=p
            for dimension,column in groups.items():
                for label,g in tagged.groupby(column):
                    subgroups.append({'method':name,'dimension':dimension,'group':str(label),**errors(g.target_score,g._pred)})
        save_csv('model_audit.csv',test_rows);save_csv('subgroup_audit.csv',subgroups)
        feature_rows=[]
        for name,model in ablation_models.items():
            p=predict(model,audit,ABLATIONS[name])
            feature_rows.append({'ablation':name,'feature_count':len(ABLATIONS[name]),**errors(audit.target_score,p)})
        save_csv('feature_audit.csv',feature_rows)
        ens=np.mean([predictions[n] for n in best_three],axis=0)
        risk_audit=risk.predict_proba(audit[FEATURES])[:,1]
        rr=[{'policy':name,**ranking(audit,u)} for name,u in utilities(audit,predictions[selected],ens,risk_audit).items()]
        save_csv('ranking_audit.csv',rr)
        # Fixed reference algorithm; each diagnostic omits groups only from original train.
        general=[]
        train=tag_groups(train);audit=tag_groups(audit)
        cases=[]
        for dimension,column in [('building','building'),('scenario','scenario'),('seed','seed')]:
            for label in sorted(train[column].unique()):
                tr=train[train[column]!=label]
                te=audit[audit[column]==label] if dimension!='seed' else audit
                cases.append((dimension,str(label),tr,te))
        for hour in [11,12]:
            tr=train[train.target_time.dt.hour<hour]
            te=audit[audit['asof'].dt.hour>=hour]
            cases.append(('time_cutoff',str(hour),tr,te))
        for dimension,label,tr,te in cases:
            if tr.empty or te.empty:continue
            model=hgb();fit_one(model,tr)
            p=predict(model,te)
            # Paired, same-audit-row control with all original training rows.
            control=predict(fitted['hgb_absolute15'],te)
            general.append({'dimension':dimension,'held_out':label,'train_rows':len(tr),'audit_rows':len(te),
                **errors(te.target_score,p),'full_train_control_mae':float(np.abs(control-te.target_score).mean()),
                'persistence_mae':float(np.abs(te.score_current-te.target_score).mean())})
            print('GENERALIZATION',dimension,label,flush=True)
        save_csv('generalization_audit.csv',general)
        # Learning curves use fixed reference algorithm and deterministic room/seed-balanced row samples.
        learning=[]
        for fraction in [.1,.25,.5,1.0]:
            tr=train.groupby(['seed','scenario','room_id'],group_keys=False).sample(frac=fraction,random_state=7701)
            model=hgb();fit_one(model,tr)
            p=predict(model,audit)
            learning.append({'train_fraction':fraction,'train_rows':len(tr),**errors(audit.target_score,p)})
        save_csv('learning_curve.csv',learning)
        exported=audit[keys+['target_score','future_eligible']].copy()
        for name,p in predictions.items():exported[name]=p
        exported.to_csv(OUT/'audit_predictions.csv.gz',index=False,compression='gzip')
        joblib.dump({'model':fitted[selected],'features':FEATURES,'selected_name':selected,
            'selection':'v2 validation only; fresh v3 audit untouched at selection time'},OUT/'selected_model.joblib')
        joblib.dump({'model':risk,'features':FEATURES,'target':'future_eligible'},OUT/'risk_model.joblib')
    assert frozen=={str(p):digest(p) for p in map(Path,frozen)}
    summary={'selected_model':selected,'selected_ranking':selected_policy,'train_rows':len(train),'validation_rows':len(val),
        'fresh_audit_rows':len(audit),'model_count':len(candidates),'feature_experiments':len(ABLATIONS),
        'generalization_experiments':len(general),'subgroup_results':len(subgroups),
        'learning_experiments':len(learning),'ranking_experiments':len(rr),
        'v1_v2_models_unchanged':True,'all_sources_synthetic':True,'statistical_significance_claim':False,
        'model_audit':test_rows,'ranking_audit':rr,'learning_curve':learning}
    write('summary.json',summary)
    print('COMPLETE',json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
