"""Independent saved-output checks; no fitting and no changes to experiment selection."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import joblib
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parent
PERSONAL=HERE.parents[1]
sys.path.insert(0,str(PERSONAL))
from common import digest
from build_datasets import S1_FEATURES

OUT=HERE/'artifacts'
summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
selection=json.loads((OUT/'selection.json').read_text(encoding='utf-8'))
audit=pd.read_csv(OUT/'audit_dataset.csv.gz',parse_dates=['asof','target_time'])
inputs=pd.read_csv(OUT/'audit_inference_inputs.csv.gz')
preds=pd.read_csv(OUT/'audit_predictions.csv.gz',parse_dates=['asof','target_time'])
metrics=pd.read_csv(OUT/'model_audit.csv')
sub=pd.read_csv(OUT/'subgroup_audit.csv')
assert set(audit.seed)=={5401,5402}
assert audit.room_id.nunique()==63 and audit.run_id.nunique()==12
assert not audit.duplicated(['run_id','room_id','asof']).any()
assert (audit.target_time-audit['asof']).eq(pd.Timedelta(minutes=8)).all()
assert not {'target_score','future_eligible'}&set(inputs.columns)
assert not any(f in S1_FEATURES for f in ['run_id','seed','scenario','future_eligible'])
assert audit[['run_id','room_id','asof','target_time']].equals(preds[['run_id','room_id','asof','target_time']])
assert len(metrics)==18 and len(sub)==1764
for _,r in metrics.iterrows():
    p=preds[r.method].to_numpy()
    assert np.isfinite(p).all() and ((p>=0)&(p<=100)).all()
    assert np.isclose(np.abs(p-audit.target_score).mean(),r.mae)
    for dimension,g in sub[sub.method==r.method].groupby('dimension'):
        assert int(g.n.sum())==len(audit),(r.method,dimension)
val=pd.read_csv(OUT/'model_validation.csv')
converged=val[val.converged]
best=converged.sort_values('mae').iloc[0].method
baseline=val[val.method=='persistence'].iloc[0].mae
if converged.mae.min()>=.99*baseline:best='persistence'
assert selection['selected_model']==best
ranking=pd.read_csv(OUT/'ranking_validation.csv')
base=ranking[ranking.policy=='current'].iloc[0]
feasible=ranking[ranking.future_violation<=base.future_violation]
assert selection['selected_ranking']==feasible.sort_values('regret').iloc[0].policy
bundle=joblib.load(OUT/'selected_model.joblib')
with threadpool_limits(limits=2):
    fresh=np.clip(bundle['model'].predict(audit[bundle['features']]),0,100)
assert np.allclose(fresh,preds[best],rtol=1e-9,atol=1e-9)
for scenario in ['S1','S5']:
    evaluation=json.loads((PERSONAL/f'results/{scenario}_evaluation.json').read_text(encoding='utf-8'))
    assert evaluation['model_sha256']==digest(PERSONAL/f'results/{scenario}_model.joblib')
v2=HERE.parent/'v2/artifacts'
v2evaluation=json.loads((v2/'evaluation.json').read_text(encoding='utf-8'))
assert v2evaluation['model_sha256']==digest(v2/'S1_model.joblib')
result={'pass':True,'checks':['12 new-seed runs, 63 rooms, exact 8-minute labels',
 'inference labels excluded','18 model metrics independently recomputed from saved predictions',
 '13 subgroup dimensions reconcile to identical row totals','validation-only model and ranking choices reproduced',
 'selected model inference reproduced','v1 S1/S5 and v2 model hashes unchanged'],
 'completed_date':'2026-11-05'}
(OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
