"""Fit model-specific preprocessing on train only; choose on validation, freeze test."""
import argparse, json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from common import OUTPUT, PROFILE, digest, write_json

def bounds(name,pred):
    return np.clip(pred,0,100) if name=='S1' else np.maximum(pred,0)

def scores(name,y,pred):
    y=np.asarray(y);p=np.asarray(pred);error=p-y
    result={'n':len(y),'mae':float(np.abs(error).mean()),'rmse':float(np.sqrt((error**2).mean())),
            'bias':float(error.mean()),'p95_absolute_error':float(np.quantile(np.abs(error),.95))}
    if name=='S5':
        truth=y>=PROFILE['ventilation_on_ppm'];positive=p>=PROFILE['ventilation_on_ppm']
        tp=int((truth&positive).sum());fp=int((~truth&positive).sum());fn=int((truth&~positive).sum());tn=int((~truth&~positive).sum())
        result['future_co2_risk']={'TP':tp,'FP':fp,'FN':fn,'TN':tn,
            'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,
            'recall':tp/(tp+fn) if tp+fn else 0,'definition':'observed CO2 at t+8 >= 890, not sensor-fault truth'}
    return result

def rank_regret(frame,prediction):
    d=frame.copy();d['prediction']=prediction
    p=PROFILE
    eligible=(d.temp.between(*p['temperature_range_c']) & d.humidity.between(*p['humidity_range_pct']) &
              (d.co2<p['ventilation_on_ppm']) & (d.noise<=p['maximum_noise_dba']) &
              (d.light>=p['minimum_illuminance_lux']) & (d.capacity-d.occupancy>=1))
    d=d[eligible]
    if d.empty:return {'candidate_instants':0,'mean_regret':None}
    best=d.groupby('asof').target_score.max()
    chosen=d.sort_values(['asof','prediction','room_id'],ascending=[True,False,True]).groupby('asof').head(1).set_index('asof')
    regret=best-chosen.target_score
    return {'candidate_instants':len(chosen),'mean_regret':float(regret.mean()),
            'definition':'design-score regret among the same currently eligible candidates; not user satisfaction or reservation approval'}

def train(name):
    model_file=OUTPUT/f'{name}_model.joblib'
    if model_file.exists():raise FileExistsError(f'{model_file} already exists; use a new version before refitting test evidence')
    contract=json.loads((OUTPUT/'data_contract.json').read_text(encoding='utf-8'))['models'][name]
    frame=pd.read_csv(OUTPUT/f'{name}_dataset.csv.gz',parse_dates=['asof','target_time'])
    features=contract['features'];target=contract['target'];baseline=contract['baseline_feature']
    parts={s:frame[frame.split==s] for s in ['train','validation','test']}
    assert parts['train'].target_time.max()<parts['validation']['asof'].min()
    assert parts['validation'].target_time.max()<parts['test']['asof'].min()
    estimators={
       'ridge_train_only_scaled':make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler(),Ridge(alpha=10)),
       'hist_gradient_boosting':HistGradientBoostingRegressor(loss='absolute_error',max_iter=120,max_leaf_nodes=15,
            min_samples_leaf=30,l2_regularization=1,early_stopping=False,random_state=20261103),
    }
    validation={};fitted={}
    val=parts['validation']
    validation['persistence']=scores(name,val[target],bounds(name,val[baseline].to_numpy()))
    for label,model in estimators.items():
        model.fit(parts['train'][features],parts['train'][target])
        fitted[label]=model
        prediction=bounds(name,model.predict(val[features]))
        validation[label]=scores(name,val[target],prediction)
        print(name,label,'validation MAE',validation[label]['mae'],flush=True)
    best=min(validation,key=lambda key:validation[key]['mae'])
    # Predeclared 1% validation improvement gate prevents deploying a complex tie.
    if validation[best]['mae']>=.99*validation['persistence']['mae']:best='persistence'
    selected=None if best=='persistence' else fitted[best]
    # Selection is complete before the held-out test predictions below.
    test=parts['test'];predictions={};test_scores={}
    for label in ['persistence',*fitted]:
        prediction=bounds(name,test[baseline].to_numpy() if label=='persistence' else fitted[label].predict(test[features]))
        test_scores[label]=scores(name,test[target],prediction)
        predictions[label]=prediction
    export=test[['room_id','asof','target_time',target]].copy()
    export['selected_prediction']=predictions[best];export['persistence_prediction']=predictions['persistence']
    export.to_csv(OUTPUT/f'{name}_test_predictions.csv.gz',index=False,compression='gzip')
    bundle={'model':selected,'selected_name':best,'features':features,'baseline_feature':baseline,
            'scenario':name,'profile':PROFILE,'target_definition':contract['definition'],
            'training_dates':PROFILE['train_dates'],'validation_dates':PROFILE['validation_dates'],
            'test_dates':PROFILE['test_dates'],'dataset_sha256':digest(OUTPUT/f'{name}_dataset.csv.gz'),
            'selection':'validation MAE, at least 1% better than persistence; no train+validation refit',
            'prediction_clip':'0..100' if name=='S1' else '>=0'}
    joblib.dump(bundle,model_file)
    result={'scenario':name,'selected':best,'validation':validation,'test':test_scores,
            'selected_test':test_scores[best],'rows':{s:len(f) for s,f in parts.items()},
            'source':contract.get('source_root','see data contract'),
            'features':features,'target':target,'model_sha256':digest(model_file),
            'test_used_for_selection':False,'preference_learning':False,
            'limitation':'synthetic known-room future-time holdout; not independent campuses or actual satisfaction'}
    if name=='S1':result['test_rank_regret']={label:rank_regret(test,p) for label,p in predictions.items() if label in {best,'persistence'}}
    write_json(OUTPUT/f'{name}_evaluation.json',result)
    print(name,'SELECTED',best,'test MAE',test_scores[best]['mae'],flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--scenario',choices=['S1','S5','both'],default='both')
    args=parser.parse_args()
    with threadpool_limits(limits=2):
        for name in (['S1','S5'] if args.scenario=='both' else [args.scenario]):train(name)
