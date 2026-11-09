"""Inspect suitability and paired interventions without changing training choices."""
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from common import HERE, OUTPUT, PROFILE, digest, write_json

def model_review():
    d=pd.read_csv(OUTPUT/'S1_dataset.csv.gz',parse_dates=['asof'])
    test=d[d.split=='test'];p=PROFILE
    reasons={
        'temperature':~test.temp.between(*p['temperature_range_c']),
        'humidity':~test.humidity.between(*p['humidity_range_pct']),
        'co2':~(test.co2<p['ventilation_on_ppm']),
        'noise':~(test.noise<=p['maximum_noise_dba']),
        'light':~(test.light>=p['minimum_illuminance_lux']),
        'seats':~(test.capacity-test.occupancy>=1),
    }
    excluded=pd.DataFrame(reasons).any(axis=1)
    result={'owner':p['owner'],'preference_origin':p['preference_origin'],
        'S1_test_rows':len(test),'S1_eligible_rows':int((~excluded).sum()),
        'S1_test_instants':int(test['asof'].nunique()),
        'S1_eligible_instants':int(test.loc[~excluded,'asof'].nunique()),
        'S1_exclusion_counts_overlap':{k:int(v.sum()) for k,v in reasons.items()},
        'no_relaxation_to_fill_recommendations':True,
        'S1':json.loads((OUTPUT/'S1_evaluation.json').read_text(encoding='utf-8')),
        'S5':json.loads((OUTPUT/'S5_evaluation.json').read_text(encoding='utf-8')),
        'definitions':{'S1':'forecast next completed 8-minute design-score window; no satisfaction labels',
                       'S5':'forecast instantaneous observed CO2 at t+8; control outcome evaluated separately'},
        'personal_fault_type_0':'definition absent; not guessed or silently injected'}
    write_json(OUTPUT/'model_review.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['S1','S5']},ensure_ascii=False,indent=2))

def compare_simulations():
    base=HERE/'simulations/personal_baseline';other=HERE/'simulations/personal_predictive'
    comparisons={};results={}
    for name in ['events/reservations.csv','events/occupancy_events.csv','truth/anomaly_events.csv']:
        comparisons[name]={'baseline_sha256':digest(base/name),'predictive_sha256':digest(other/name)}
        assert comparisons[name]['baseline_sha256']==comparisons[name]['predictive_sha256'],name
    for date in pd.date_range('2026-09-01','2026-09-25'):
        filename=f'raw/sensors_1min/sensor_readings_{date:%Y-%m-%d}.csv'
        assert digest(base/filename)==digest(other/filename),f'Policy changed before test: {date}'
    for label,root in [('baseline',base),('predictive',other)]:
        total=dict(occupied_minutes=0,occupied_co2_ge_890_minutes=0,occupied_co2_excess_ppm_minutes=0.0,
                   occupied_co2_mean_sum=0.0,total_energy_kwh=0.0,max_true_co2_ppm=0.0,ventilation_minutes=0)
        for date in pd.date_range(*PROFILE['test_dates']):
            text=f'{date:%Y-%m-%d}'
            t=pd.read_csv(root/f'truth/environment_truth_1min/environment_truth_{text}.csv',usecols=['timestamp','room_id','true_co2_ppm','true_occupancy_count'])
            t['timestamp']=pd.to_datetime(t.timestamp)
            t=t[(t.timestamp.dt.hour>=PROFILE['analysis_start_hour'])&(t.timestamp.dt.hour<21)]
            occupied=t[t.true_occupancy_count>0]
            total['occupied_minutes']+=len(occupied)
            total['occupied_co2_ge_890_minutes']+=int((occupied.true_co2_ppm>=PROFILE['ventilation_on_ppm']).sum())
            total['occupied_co2_excess_ppm_minutes']+=float((occupied.true_co2_ppm-PROFILE['ventilation_on_ppm']).clip(lower=0).sum())
            total['occupied_co2_mean_sum']+=float(occupied.true_co2_ppm.sum())
            total['max_true_co2_ppm']=max(total['max_true_co2_ppm'],float(t.true_co2_ppm.max()))
            e=pd.read_csv(root/f'raw/energy_usage_1min/energy_usage_{text}.csv',usecols=['timestamp','interval_energy_kwh'])
            hour=pd.to_datetime(e.timestamp).dt.hour
            total['total_energy_kwh']+=float(e.loc[(hour>=10)&(hour<21),'interval_energy_kwh'].sum())
            f=pd.read_csv(root/f'raw/facility_states_1min/facility_states_{text}.csv',usecols=['timestamp','ventilation_on'])
            hour=pd.to_datetime(f.timestamp).dt.hour
            total['ventilation_minutes']+=int(f.loc[(hour>=10)&(hour<21),'ventilation_on'].sum())
        total['occupied_true_co2_mean_ppm']=total.pop('occupied_co2_mean_sum')/total['occupied_minutes']
        total['occupied_co2_ge_890_fraction']=total['occupied_co2_ge_890_minutes']/total['occupied_minutes']
        results[label]=total
    a=results['baseline'];b=results['predictive']
    outcome={'exogenous_inputs_identical':comparisons,'warmup_before_test_identical':True,
        'evaluation_dates':PROFILE['test_dates'],'daily_window':'10:00 inclusive to 21:00 exclusive',
        'rooms':PROFILE['simulation_representative_rooms'],'results':results,
        'delta_predictive_minus_baseline':{k:b[k]-a[k] for k in a},
        'decision':'retain personal rule baseline unless exposure improves with acceptable energy tradeoff; regression MAE alone is insufficient',
        'scope':'paired synthetic intervention on 4 fixed rooms; no actual equipment, no 63-room deployment claim'}
    # Prespecified descriptive gate, not post-hoc tuning of the frozen test model.
    exposure_better=b['occupied_co2_excess_ppm_minutes']<a['occupied_co2_excess_ppm_minutes']
    energy_ok=b['total_energy_kwh']<=a['total_energy_kwh']*1.05
    outcome['advisory_acceptance']={'exposure_reduced':exposure_better,'energy_increase_at_most_5pct':energy_ok,
        'provisional_synthetic_pilot_only':bool(exposure_better and energy_ok)}
    write_json(OUTPUT/'paired_simulation_comparison.json',outcome)
    print(json.dumps(outcome,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--simulation',action='store_true')
    args=parser.parse_args()
    if args.simulation:compare_simulations()
    else:model_review()
