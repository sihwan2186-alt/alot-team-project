"""Additional predeclared score-free feature removals and residual forecasting diagnostics."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from sklearn.inspection import permutation_importance

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from run_comparison import V2,FEATURES,OUT,hgb,fit_one,predict,errors,linear
from sklearn.linear_model import Ridge

DROP={'none':[], 'humidity':['humidity'],'temperature':['temp','temp_change'],
      'co2':['co2','co2_change','co2_missing_ratio'],'noise':['noise','noise_change'],
      'light':['light'],'seats':['capacity','occupancy']}
plan={'feature_removals':DROP,'remove_score_current_in_all_variants':True,
      'residual_methods':['ridge_delta','hgb_delta'],'new_candidates_not_used_to_change_primary_selection':True,
      'permutation_importance':'selected primary model on validation only; 3 repeats; not causal attribution'}
(OUT/'additional_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
data=pd.read_csv(V2/'S1_dataset.csv.gz',parse_dates=['asof','target_time'])
train=data[data.split=='train'].copy();val=data[data.split=='validation'].copy()
audit=pd.read_csv(OUT/'audit_dataset.csv.gz',parse_dates=['asof','target_time'])
rows=[]
with threadpool_limits(limits=2):
    for omitted,cols in DROP.items():
        features=[f for f in FEATURES if f!='score_current' and f not in cols]
        model=hgb();fit_one(model,train,features)
        for split,d in [('validation',val),('fresh_audit',audit)]:
            p=predict(model,d,features)
            rows.append({'experiment':'score_free_ablation','variant':omitted,'split':split,
                         'feature_count':len(features),**errors(d.target_score,p)})
    for name,model in [('ridge_delta',linear(Ridge(alpha=10))),('hgb_delta',hgb())]:
        features=[f for f in FEATURES if f!='score_current']
        residual=train.copy();residual['target_score']=residual.target_score-residual.score_current
        fit_one(model,residual,features)
        for split,d in [('validation',val),('fresh_audit',audit)]:
            p=np.clip(d.score_current.to_numpy()+model.predict(d[features]),0,100)
            rows.append({'experiment':'residual_forecast','variant':name,'split':split,
                         'feature_count':len(features),**errors(d.target_score,p)})
    pd.DataFrame(rows).to_csv(OUT/'additional_experiments.csv',index=False,encoding='utf-8-sig')
    import joblib
    selection=json.loads((OUT/'selection.json').read_text(encoding='utf-8'))
    selected=joblib.load(OUT/f"model_{selection['selected_model']}.joblib")['model']
    if selected is not None:
        imp=permutation_importance(selected,val[FEATURES],val.target_score,scoring='neg_mean_absolute_error',
            n_repeats=3,random_state=8801,n_jobs=1)
        pd.DataFrame({'feature':FEATURES,'validation_mae_increase':imp.importances_mean,
            'repeat_std':imp.importances_std}).to_csv(OUT/'validation_permutation_importance.csv',index=False,encoding='utf-8-sig')
print('Additional experiments:',len(rows),'metric rows',flush=True)
