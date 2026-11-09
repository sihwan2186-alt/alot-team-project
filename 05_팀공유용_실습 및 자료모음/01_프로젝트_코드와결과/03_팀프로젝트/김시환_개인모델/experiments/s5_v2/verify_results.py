"""Verify saved forecast metrics and independently reconstruct exposure from intervention traces."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score
import joblib
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from simulation import forecast,SCENARIOS
PERSONAL=HERE.parents[1]
sys.path.insert(0,str(PERSONAL))
from common import digest
from build_datasets import S5_FEATURES

OUT=HERE/'artifacts'
plan=json.loads((OUT/'plan.json').read_text(encoding='utf-8'))
summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
d=pd.read_csv(OUT/'audit_dataset.csv.gz',parse_dates=['asof','target_time'])
inputs=pd.read_csv(OUT/'audit_inference_inputs.csv.gz')
p=pd.read_csv(OUT/'audit_predictions.csv.gz',parse_dates=['asof','target_time'])
models=pd.read_csv(OUT/'model_audit.csv')
assert d.room_id.nunique()==63 and set(d.seed)=={6401,6402}
assert not d.duplicated(['run_id','room_id','asof']).any()
assert (d.target_time-d['asof']).eq(pd.Timedelta(minutes=8)).all()
assert not {'target_co2','fault','true_co2_ppm'}&set(inputs)
assert not {'scenario','seed','run_id','target_co2'}&set(S5_FEATURES)
keys=['run_id','room_id','asof','target_time']
assert d[keys].equals(p[keys])
for _,r in models.iterrows():
    pred=p[r.method].to_numpy()
    assert np.isfinite(pred).all() and (pred>=0).all()
    assert np.isclose(np.abs(pred-d.target_co2).mean(),r.mae_ppm)
    assert np.isclose(f1_score(d.target_co2>=890,pred>=890,zero_division=0),r.future_exceedance_f1)
sub=pd.read_csv(OUT/'subgroup_audit.csv')
for _,g in sub.groupby(['method','dimension']):assert g.n.sum()==len(d)
v=pd.read_csv(OUT/'model_validation.csv')
best=v[v.converged].sort_values('mae_ppm').iloc[0]
baseline=v[v.method=='persistence'].iloc[0].mae_ppm
selected=best.method if best.mae_ppm<.99*baseline else 'persistence'
assert selected==summary['selected_model']
with threadpool_limits(limits=2):
    chosen=joblib.load(OUT/'selected_model.joblib')
    np.testing.assert_allclose(forecast(chosen,d),p[selected],rtol=1e-9,atol=1e-9)
frozen=json.loads((OUT/'frozen_before.json').read_text(encoding='utf-8'))
assert frozen=={name:digest(Path(name)) for name in frozen}
profiles=pd.read_csv(OUT/'room_profiles.csv')
profiles=profiles[profiles.room_id.isin(plan['control_rooms'])].sort_values('room_id')
cohorts={}
def expected_counts(seed,date,scenario):
    """Rebuild external occupancy only, without running the physical/control simulator."""
    rows=profiles.to_dict('records');rngs=[np.random.default_rng(seed*1000+i) for i in range(len(rows))]
    counts=[0]*len(rows);output=[];s=SCENARIOS[scenario]
    for minute,t in enumerate(pd.date_range(f'{date} 09:00+09:00',f'{date} 12:59+09:00',freq='min')):
        if minute%s['interval']==0:
            probability=s['probability']
            if scenario=='arrival':probability=.10 if t.hour*60+t.minute<630 else .85 if t.hour*60+t.minute<690 else .30
            if scenario=='turnover':probability=.15 if (minute//8)%2==0 else .85
            counts=[int(rng.binomial(int(r['capacity']),probability)) for r,rng in zip(rows,rngs)]
        if t.hour>=10:
            output.extend({'timestamp':t,'room_id':r['room_id'],'occupancy':count} for r,count in zip(rows,counts))
    return pd.DataFrame(output)

checked=0
for split in ['validation','audit']:
    effects=pd.read_csv(OUT/f'closed_loop_{split}.csv')
    for (seed,scenario),group in effects.groupby(['seed','scenario']):
        assert group.exogenous_sha256.nunique()==1
        assert group.minimum_run_violations.eq(0).all()
        count_frame=expected_counts(int(seed),group.iloc[0].date,scenario)
        for _,r in group.iterrows():
            trace=pd.read_csv(OUT/'controls'/split/f'{seed}_{scenario}_{r.policy}'/'trace.csv.gz',parse_dates=['timestamp'])
            t=trace.merge(count_frame,on=['timestamp','room_id'],validate='one_to_one')
            assert len(t)==180*12
            occupied=t[t.occupancy>0]
            true=occupied.true_co2_ppm_evaluation_only
            assert len(occupied)==r.occupied_room_minutes
            assert (true>=890).sum()==r.co2_ge_890_occupied_room_minutes
            assert np.isclose((true-890).clip(lower=0).sum(),r.excess_ppm_room_minutes)
            assert np.isclose(t.true_co2_ppm_evaluation_only.max(),r.max_true_co2_ppm)
            assert np.isclose(true.mean(),r.occupied_co2_mean_ppm)
            power=t.room_id.map(profiles.set_index('room_id').ventilation_power_kw)
            vent_kwh=(power*t.applied_ventilation.astype(int)/60).sum()
            assert np.isclose(vent_kwh,r.ventilation_energy_kwh)
            assert r.total_energy_kwh>=r.ventilation_energy_kwh>=0
            checked+=1
    if split=='validation':
        totals=effects.groupby('policy')[['excess_ppm_room_minutes','total_energy_kwh']].sum()
        base=totals.loc['rule_baseline']
        possible=totals[(totals.total_energy_kwh<=base.total_energy_kwh*1.05)&
                        (totals.excess_ppm_room_minutes<base.excess_ppm_room_minutes)]
        policy='rule_baseline' if possible.empty else possible.sort_values('excess_ppm_room_minutes').index[0]
        assert policy==summary['selected_control_policy']
result={'pass':True,'models_checked':len(models),'subgroup_rows_checked':len(sub),'closed_loop_traces_checked':checked,
    'forecast_labels_are_exact_t_plus_8':True,'new_seed_forecast_metrics_reproduced':True,
    'exposure_and_ventilation_energy_recomputed':True,'same_exogenous_inputs_and_minimum_run_verified':True,
    'frozen_models_unchanged':True,'validation_only_choices_reproduced':True,
    'total_energy_note':'total is engine-integrated HVAC/lighting/standby/ventilation; ventilation term independently reconstructed'}
(OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
