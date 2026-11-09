"""Read-only frozen experiment verification and auxiliary policy report."""
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
from inference import eligibility
from experiments.v2.policy import policy_metrics

out=HERE/'artifacts'
evaluation=json.loads((out/'evaluation.json').read_text(encoding='utf-8'))
plan=json.loads((out/'plan.json').read_text(encoding='utf-8'))
data=pd.read_csv(out/'S1_dataset.csv.gz',parse_dates=['asof','target_time'])
inputs=pd.read_csv(out/'S1_inference_inputs.csv.gz',parse_dates=['asof','target_time'])
bundle=joblib.load(out/'S1_model.joblib')
assert bundle['dataset_sha256']==digest(out/'S1_dataset.csv.gz')
assert evaluation['model_sha256']==digest(out/'S1_model.joblib')
assert not {'target_score','future_eligible'}&set(inputs.columns)
assert not set(bundle['features'])&{'seed','scenario','run_id','target_score','future_eligible','target_time','split'}
assert (data.target_time-data['asof']).eq(pd.Timedelta(minutes=8)).all()
assert not data.duplicated(['run_id','room_id','asof']).any()
assert inputs.target_time.dt.hour.le(13).all()
assert data.groupby('split').room_id.nunique().eq(63).all()
assert set(data[data.split=='train'].seed).isdisjoint(data[data.split=='test'].seed)
results={}
with threadpool_limits(limits=2):
    for split in ['validation','test']:
        d=data[data.split==split].copy()
        pred=d.score_current.to_numpy() if bundle['model'] is None else bundle['model'].predict(d[bundle['features']])
        pred=np.clip(pred,0,100)
        results[split]=policy_metrics(d,pred)
        if split=='test':
            assert np.isclose(np.abs(pred-d.target_score).mean(),evaluation['test']['selected']['overall']['mae'])
gen=pd.DataFrame(json.loads((out/'generation.json').read_text(encoding='utf-8')))
humidity=gen.groupby('scenario').agg(median_rh=('humidity_median','mean'),
    mean_fraction_rh_in_range=('humidity_pass_fraction','mean')).to_dict('index')
verification={'checks_passed':True,'frozen_hashes_match':True,'no_label_or_scenario_features':True,
              'separate_seed_and_date_splits':True,'policy_comparison':results,
              'scenario_humidity':humidity,'raw_rows':int(gen.rows.sum()),
              'note':'humidity summaries average run-level summaries; synthetic only'}
(out/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(verification,ensure_ascii=False,indent=2))
