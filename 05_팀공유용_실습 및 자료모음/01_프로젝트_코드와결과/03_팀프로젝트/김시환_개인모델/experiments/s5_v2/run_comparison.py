"""S5 multi-model comparison and separately selected paired closed-loop policies."""
from pathlib import Path
from time import perf_counter
import json
import sys
import warnings
import numpy as np
import pandas as pd
import joblib
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import confusion_matrix,precision_score,recall_score,f1_score
from sklearn.linear_model import Ridge
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parent
PERSONAL=HERE.parents[1]
sys.path.insert(0,str(PERSONAL))
sys.path.insert(0,str(HERE))
from common import SOURCE,SIMULATOR,digest
from build_datasets import S5_FEATURES
from experiments.v3.run_comparison import methods,hgb,linear
from simulation import SCENARIOS,simulate,dataset,forecast
from aiot_sim.config import load

OUT=HERE/'artifacts';FEATURES=S5_FEATURES
ABLATIONS={
 'full':FEATURES,'co2_only':['co2'],
 'co2_history':['co2','co2_lag1','co2_lag8','co2_trend'],
 'no_history':[f for f in FEATURES if f not in ['co2_lag1','co2_lag8','co2_trend']],
 'no_occupancy':[f for f in FEATURES if f!='occupancy'],
 'no_ventilation':[f for f in FEATURES if f not in ['ventilation_on','ventilation_level']],
 'no_geometry':[f for f in FEATURES if f not in ['volume_m3','ventilation_off_ach','ventilation_on_ach']],
 'no_clock':[f for f in FEATURES if f not in ['hour_sin','hour_cos','weekday']],
 'current_people_vent':['co2','occupancy','ventilation_on','ventilation_level'],
 'history_people_vent':['co2','co2_lag1','co2_lag8','co2_trend','occupancy','ventilation_on','ventilation_level'],
}
SEEDS={'train':[1301,1302],'validation':[2301],'audit':[6401,6402]}
DATES={'train':['2026-09-02','2026-09-16'],'validation':['2026-09-23'],'audit':['2026-09-30','2026-10-01']}
POLICIES={'rule_baseline':None,'forecast_0':0,'forecast_20':20,'forecast_40':40}

def write(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

def save(name,rows):pd.DataFrame(rows).to_csv(OUT/name,index=False,encoding='utf-8-sig')

def metrics(y,p):
    y=np.asarray(y);p=np.asarray(p);e=p-y
    truth=y>=890;positive=p>=890
    tn,fp,fn,tp=confusion_matrix(truth,positive,labels=[False,True]).ravel()
    return {'n':len(y),'mae_ppm':float(np.abs(e).mean()),'rmse_ppm':float(np.sqrt((e**2).mean())),
        'p95_error_ppm':float(np.quantile(np.abs(e),.95)),'bias_ppm':float(e.mean()),
        'TP':int(tp),'FP':int(fp),'FN':int(fn),'TN':int(tn),
        'future_exceedance_precision':float(precision_score(truth,positive,zero_division=0)),
        'future_exceedance_recall':float(recall_score(truth,positive,zero_division=0)),
        'future_exceedance_f1':float(f1_score(truth,positive,zero_division=0)),
        'true_exceedance_fraction':float(truth.mean())}

def fit(model,d,features=FEATURES,target='target_co2'):
    start=perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        if model is not None:model.fit(d[features],d[target])
    return {'fit_seconds':perf_counter()-start,'warnings':[str(w.message) for w in caught],
        'converged':not any(issubclass(w.category,ConvergenceWarning) for w in caught)}

def bundle(name,model,features=FEATURES):return {'name':name,'model':model,'features':features,'horizon_minutes':8}

def tagged(d,profiles):
    d=d.copy();lookup=profiles.set_index('room_id')
    d['building']=d.room_id.str.split('-').str[0]
    d['hour']=d['asof'].dt.hour.astype(str)
    d['capacity']=d.room_id.map(lookup.capacity)
    d['crowding']=pd.cut(d.occupancy/d.capacity,[-.001,.3,.7,1.01],labels=['low_0_30','mid_30_70','high_70_100']).astype(str)
    d['co2_band']=pd.cut(d.co2,[-np.inf,700,850,890,1100,np.inf],right=False,
        labels=['below700','700to850','850to890','890to1100','1100plus']).astype(str)
    d['ventilation_state']=np.where(d.ventilation_on>0,'on','off')
    d['volume_band']=pd.cut(d.volume_m3,[-np.inf,75,150,np.inf],right=False,labels=['below75','75to150','150plus']).astype(str)
    d['ach_band']=pd.cut(d.ventilation_on_ach,[-np.inf,2.5,3.5,np.inf],right=False,labels=['below2.5','2.5to3.5','3.5plus']).astype(str)
    d['past_missing']=np.where(d[['co2_lag1','co2_lag8','co2_trend']].isna().any(axis=1),'missing','complete')
    d['trend_band']=pd.cut(d.co2_trend,[-np.inf,-1,1,np.inf],labels=['falling','stable','rising']).astype('string').fillna('unknown')
    return d

def generate_split(split,profiles,config):
    parts=[];inputs=[];generation=[]
    for seed,date in zip(SEEDS[split],DATES[split]):
        for scenario in SCENARIOS:
            job={'split':split,'seed':seed,'date':date,'scenario':scenario,'run_id':f'{split}_{seed}_{scenario}'}
            root=OUT/'runs'/job['run_id']
            raw,facility,stats=simulate(config,profiles,scenario,seed,date,root)
            labeled,view=dataset(raw,facility,profiles,job)
            parts.append(labeled);inputs.append(view)
            generation.append({**job,**stats,'sensor_sha256':digest(root/'sensors.csv.gz'),
                'facility_sha256':digest(root/'facility.csv.gz'),'labeled_rows':len(labeled),'input_rows':len(view)})
            print('DATA',job['run_id'],len(labeled),flush=True)
    return pd.concat(parts,ignore_index=True),pd.concat(inputs,ignore_index=True),generation

def paired_controls(split,config,profiles,selected):
    results=[]
    for seed,date in zip(SEEDS[split],DATES[split]):
        for scenario in SCENARIOS:
            expected_hash=None
            for policy,margin in POLICIES.items():
                root=OUT/'controls'/split/f'{seed}_{scenario}_{policy}'
                stats=simulate(config,profiles,scenario,seed,date,root,
                    bundle=None if margin is None else selected,margin=margin or 0,collect=False)
                if expected_hash is None:expected_hash=stats['exogenous_sha256']
                assert stats['exogenous_sha256']==expected_hash
                assert stats['minimum_run_violations']==0
                results.append({'split':split,'seed':seed,'date':date,'scenario':scenario,'policy':policy,**stats})
                print('CONTROL',split,seed,scenario,policy,flush=True)
    return results

def aggregate_controls(rows):
    d=pd.DataFrame(rows)
    fields=['occupied_room_minutes','co2_ge_890_occupied_room_minutes','excess_ppm_room_minutes',
        'total_energy_kwh','ventilation_energy_kwh','ventilation_applied_room_minutes','ventilation_requested_switches',
        'blocked_on_room_minutes','missing_observation_room_minutes','minimum_run_violations']
    total=d.groupby('policy')[fields].sum()
    total['max_true_co2_ppm']=d.groupby('policy').max_true_co2_ppm.max()
    return total.reset_index()

def main():
    if OUT.exists():raise FileExistsError('Use a new version; existing evidence must not be overwritten')
    OUT.mkdir()
    profiles=pd.read_csv(SOURCE/'inputs/room_profiles.csv')
    # Fixed 12-room intervention cohort: low/middle/high capacity in each building.
    control_ids=[]
    for _,g in profiles.assign(building=profiles.room_id.str.split('-').str[0]).groupby('building'):
        g=g.sort_values(['capacity','room_id'])
        control_ids.extend(g.iloc[[0,len(g)//2,len(g)-1]].room_id.tolist())
    control_profiles=profiles[profiles.room_id.isin(control_ids)]
    candidates=methods();candidates['linear_trend']=None;candidates['mass_balance']=None
    plan={'created_date':'2026-11-05','scope':'synthetic S5 multi-method; actual measurements not used',
        'scenarios':SCENARIOS,'seeds':SEEDS,'dates':DATES,'features':FEATURES,'model_methods':list(candidates),
        'feature_ablations':ABLATIONS,'forecast_rooms':63,'control_rooms':sorted(control_ids),
        'hours':'09–10 warmup, 10–13 evaluation','personal_on_off_ppm':[890,850],'minimum_run_minutes':5,
        'model_selection':'validation MAE; >1% improvement over persistence; no convergence warnings',
        'control_policies':POLICIES,'control_selection':'validation excess exposure minimum with energy <= baseline*1.05; otherwise baseline',
        'physical_baseline':'8-minute analytical mass balance assuming constant current occupancy/ventilation and outdoor 425ppm',
        'generalization':'fixed HGB 15 leaves, omit building/scenario/train seed or late training hours',
        'residual_methods':['ridge_delta','hgb_delta'],'learning_fractions':[.1,.25,.5,1.0],
        'no_safety_claim':True,'no_actual_device_command':True,'no_type0_definition_assumed':True,
        'limitations':'one validation seed and two fresh audit seeds; synthetic occupancy/fault assumptions; no real-world significance'}
    write('plan.json',plan)
    frozen={str(p):digest(p) for folder in [PERSONAL/'results',HERE.parent/'v2/artifacts',HERE.parent/'v3/artifacts']
            for p in folder.glob('*model.joblib')}
    write('frozen_before.json',frozen)
    config=load(SIMULATOR)
    profiles.to_csv(OUT/'room_profiles.csv',index=False)
    with threadpool_limits(limits=2):
        train,tinputs,tgen=generate_split('train',profiles,config)
        val,vinputs,vgen=generate_split('validation',profiles,config)
        assert train.target_time.max()<val['asof'].min()
        keys=['run_id','scenario','split','seed','room_id','asof','target_time']
        pd.concat([train,val],ignore_index=True)[keys+FEATURES+['target_co2']].to_csv(OUT/'development_dataset.csv.gz',index=False,compression='gzip')
        validation=[];fitted={};ablations={}
        for name,model in candidates.items():
            info=fit(model,train)
            b=bundle(name,model);p=forecast(b,val)
            validation.append({'method':name,**metrics(val.target_co2,p),**info});fitted[name]=b
            save('model_validation.csv',validation)
            joblib.dump(b,OUT/f'model_{name}.joblib')
            print('MODEL',name,round(validation[-1]['mae_ppm'],3),flush=True)
        eligible=[r for r in validation if r['converged']]
        selected=min(eligible,key=lambda r:r['mae_ppm'])['method']
        base=next(r['mae_ppm'] for r in validation if r['method']=='persistence')
        if next(r['mae_ppm'] for r in validation if r['method']==selected)>=.99*base:selected='persistence'
        write('model_selection.json',{'selected':selected,'audit_used_for_selection':False,
            'selection_before_new_audit_generation':True})
        joblib.dump(fitted[selected],OUT/'selected_model.joblib')
        feature_val=[]
        for name,features in ABLATIONS.items():
            model=hgb();fit(model,train,features)
            b=bundle('feature_'+name,model,features);ablations[name]=b
            feature_val.append({'ablation':name,'feature_count':len(features),**metrics(val.target_co2,forecast(b,val))})
            print('FEATURE',name,flush=True)
        save('feature_validation.csv',feature_val)
        residual={};residual_rows=[]
        for name,model in [('ridge_delta',linear(Ridge(alpha=10))),('hgb_delta',hgb())]:
            tr=train.copy();tr['delta']=tr.target_co2-tr.co2
            fit(model,tr,target='delta');residual[name]=model
            p=np.maximum(val.co2.to_numpy()+model.predict(val[FEATURES]),0)
            residual_rows.append({'method':name,'split':'validation',**metrics(val.target_co2,p)})
        # Select the control policy solely from validation closed-loop effects.
        controls_val=paired_controls('validation',config,control_profiles,fitted[selected])
        save('closed_loop_validation.csv',controls_val)
        totals=aggregate_controls(controls_val)
        baseline=totals[totals.policy=='rule_baseline'].iloc[0]
        feasible=totals[(totals.total_energy_kwh<=baseline.total_energy_kwh*1.05)&
                       (totals.excess_ppm_room_minutes<baseline.excess_ppm_room_minutes)]
        selected_policy='rule_baseline' if feasible.empty else feasible.sort_values('excess_ppm_room_minutes').iloc[0].policy
        write('control_selection.json',{'selected_policy':selected_policy,'validation_totals':totals.to_dict('records'),
            'audit_used_for_selection':False,'selection_before_new_audit_generation':True})
        audit,ainputs,agen=generate_split('audit',profiles,config)
        assert val.target_time.max()<audit['asof'].min()
        audit[keys+FEATURES+['target_co2']].to_csv(OUT/'audit_dataset.csv.gz',index=False,compression='gzip')
        ainputs[keys+FEATURES].to_csv(OUT/'audit_inference_inputs.csv.gz',index=False,compression='gzip')
        write('generation.json',tgen+vgen+agen)
        predrows=audit[keys+['target_co2']].copy();model_rows=[];subgroups=[]
        grouped=tagged(audit,profiles)
        dimensions={'scenario':'scenario','building':'building','room':'room_id','hour':'hour','crowding':'crowding',
            'current_co2':'co2_band','ventilation':'ventilation_state','volume':'volume_band','on_ach':'ach_band',
            'seed':'seed','past_missing':'past_missing','trend':'trend_band'}
        for name,b in fitted.items():
            start=perf_counter();p=forecast(b,audit);predrows[name]=p
            model_rows.append({'method':name,**metrics(audit.target_co2,p),'predict_seconds':perf_counter()-start})
            grouped['_prediction']=p
            for dimension,column in dimensions.items():
                for label,g in grouped.groupby(column):
                    subgroups.append({'method':name,'dimension':dimension,'group':str(label),**metrics(g.target_co2,g._prediction)})
        save('model_audit.csv',model_rows);save('subgroup_audit.csv',subgroups)
        predrows.to_csv(OUT/'audit_predictions.csv.gz',index=False,compression='gzip')
        feature_rows=[{'ablation':name,'feature_count':len(b['features']),**metrics(audit.target_co2,forecast(b,audit))} for name,b in ablations.items()]
        save('feature_audit.csv',feature_rows)
        for name,model in residual.items():
            p=np.maximum(audit.co2.to_numpy()+model.predict(audit[FEATURES]),0)
            residual_rows.append({'method':name,'split':'audit',**metrics(audit.target_co2,p)})
        save('residual_forecast.csv',residual_rows)
        original=joblib.load(PERSONAL/'results/S5_model.joblib')
        old=bundle('v1_transfer',original['model'],original['features'])
        write('v1_transfer.json',metrics(audit.target_co2,forecast(old,audit)))
        tr=tagged(train,profiles);te=tagged(audit,profiles)
        general=[];cases=[]
        for dimension,column in [('building','building'),('scenario','scenario'),('seed','seed')]:
            for label in sorted(tr[column].unique()):
                cases.append((dimension,str(label),tr[tr[column]!=label],te[te[column]==label] if dimension!='seed' else te))
        for hour in [11,12]:cases.append(('time_cutoff',str(hour),tr[tr.target_time.dt.hour<hour],te[te['asof'].dt.hour>=hour]))
        for dimension,label,t,e in cases:
            model=hgb();fit(model,t)
            p=forecast(bundle('fixed_hgb',model),e)
            control=forecast(fitted['hgb_absolute15'],e)
            general.append({'dimension':dimension,'held_out':label,'train_rows':len(t),**metrics(e.target_co2,p),
                'full_train_control_mae_ppm':float(np.abs(control-e.target_co2).mean()),
                'persistence_mae_ppm':float(np.abs(e.co2-e.target_co2).mean())})
            print('GENERALIZATION',dimension,label,flush=True)
        save('generalization_audit.csv',general)
        learning=[]
        for fraction in [.1,.25,.5,1.]:
            t=train.groupby(['seed','scenario','room_id'],group_keys=False).sample(frac=fraction,random_state=7701)
            model=hgb();fit(model,t)
            learning.append({'train_fraction':fraction,'train_rows':len(t),**metrics(audit.target_co2,forecast(bundle('fixed_hgb',model),audit))})
        save('learning_curve.csv',learning)
        controls_audit=paired_controls('audit',config,control_profiles,fitted[selected])
        save('closed_loop_audit.csv',controls_audit)
        audit_totals=aggregate_controls(controls_audit)
        audit_totals.to_csv(OUT/'closed_loop_audit_totals.csv',index=False,encoding='utf-8-sig')
    assert frozen=={str(p):digest(p) for p in map(Path,frozen)}
    result={'completed_date':'2026-11-05','selected_model':selected,'selected_control_policy':selected_policy,
        'train_rows':len(train),'validation_rows':len(val),'fresh_audit_rows':len(audit),
        'forecast_rooms':63,'control_rooms':sorted(control_ids),'model_count':len(candidates),
        'feature_experiments':len(ABLATIONS),'residual_experiments':2,'generalization_experiments':len(general),
        'learning_experiments':len(learning),'control_policies':len(POLICIES),
        'closed_loop_runs':len(controls_val)+len(controls_audit),'subgroup_dimensions':len(dimensions),
        'subgroup_result_rows':len(subgroups),'frozen_models_unchanged':True,'no_actual_device_command':True,
        'model_audit':model_rows,'closed_loop_audit_totals':audit_totals.to_dict('records')}
    write('summary.json',result)
    print('COMPLETE',json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
