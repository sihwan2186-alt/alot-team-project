"""Causal scenario-specific datasets; no truth, fault labels, or future device states."""
from pathlib import Path
import argparse, json
import numpy as np
import pandas as pd
from common import HERE, SOURCE, OUTPUT, PROFILE, add_clock, digest, finalize, preference_score, write_json

SENSOR_COLUMNS=['timestamp','room_id','temperature_c','humidity_pct','co2_ppm','illuminance_lux','noise_dba','occupancy_count']
S1_FEATURES=['temp','humidity','co2','light','noise','occupancy','capacity','score_current',
             'co2_change','noise_change','temp_change','co2_missing_ratio','hour_sin','hour_cos','weekday']
S5_FEATURES=['co2','co2_lag1','co2_lag8','co2_trend','occupancy','ventilation_on','ventilation_level',
             'volume_m3','ventilation_off_ach','ventilation_on_ach','hour_sin','hour_cos','weekday']

def s1_day(raw, profiles, include_targets=True):
    h=PROFILE['horizon_minutes']
    f=raw[(raw.timestamp.dt.hour>=PROFILE['analysis_start_hour'])].merge(
        profiles[['room_id','capacity','opening_time','closing_time']],on='room_id',validate='many_to_one')
    minute=f.timestamp.dt.hour*60+f.timestamp.dt.minute
    closing=f.closing_time.str[:2].astype(int)*60+f.closing_time.str[3:].astype(int)
    opening=f.opening_time.str[:2].astype(int)*60+f.opening_time.str[3:].astype(int)
    f=f[(minute>=opening)&(minute<closing)].copy()
    f['window_start']=f.timestamp.dt.normalize()+pd.Timedelta(hours=PROFILE['analysis_start_hour'])+pd.to_timedelta(((minute.loc[f.index]-PROFILE['analysis_start_hour']*60)//h)*h,unit='min')
    f['noise_energy']=10**(f.noise_dba/10)
    a=f.groupby(['room_id','window_start'],as_index=False).agg(
        temp=('temperature_c','mean'),humidity=('humidity_pct','mean'),co2=('co2_ppm','mean'),
        light=('illuminance_lux','mean'),noise_energy=('noise_energy','mean'),occupancy=('occupancy_count','last'),
        capacity=('capacity','first'),samples=('timestamp','size'),co2_valid=('co2_ppm','count'),
        closing_time=('closing_time','first'))
    a=a[a.samples==h].copy();a['noise']=10*np.log10(a.noise_energy)
    a['co2_missing_ratio']=1-a.co2_valid/h
    a['asof']=a.window_start+pd.Timedelta(minutes=h)
    a=a.sort_values(['room_id','asof']);g=a.groupby('room_id')
    a['score_current']=preference_score(a)
    for column in ['co2','noise','temp']: a[column+'_change']=g[column].diff()
    if not include_targets:
        # Inference availability may depend only on current/past observations.
        a['target_time']=a['asof']+pd.Timedelta(minutes=h)
        end=a['target_time'].dt.hour*60+a['target_time'].dt.minute
        closing=a.closing_time.str[:2].astype(int)*60+a.closing_time.str[3:].astype(int)
        return add_clock(a[(a.co2_missing_ratio<=.25)&(end<closing)].copy())
    a['target_score']=g.score_current.shift(-1)
    a['target_time']=g['asof'].shift(-1)
    a['target_missing_ratio']=g.co2_missing_ratio.shift(-1)
    a=a[(a.target_time-a['asof'])==pd.Timedelta(minutes=h)]
    a=a[(a.co2_missing_ratio<=.25)&(a.target_missing_ratio<=.25)]
    return add_clock(a)

def s5_day(raw, facility, profiles, include_targets=True):
    h=PROFILE['horizon_minutes']
    start=PROFILE['analysis_start_hour']*60
    minute=raw.timestamp.dt.hour*60+raw.timestamp.dt.minute
    f=raw[minute>=start-h].sort_values(['room_id','timestamp']).copy()
    g=f.groupby('room_id')
    # All raw minute rows stay in the series; missing sensor values do not move time indexes.
    assert g.timestamp.diff().dropna().eq(pd.Timedelta(minutes=1)).all()
    f['co2_lag1']=g.co2_ppm.shift(1);f['co2_lag8']=g.co2_ppm.shift(h)
    if include_targets:
        f['target_co2']=g.co2_ppm.shift(-h);f['target_time']=g.timestamp.shift(-h)
    else:
        f['target_time']=f.timestamp+pd.Timedelta(minutes=h)
    f['co2_trend']=(f.co2_ppm-f.co2_lag8)/h
    minute=f.timestamp.dt.hour*60+f.timestamp.dt.minute
    f=f[(minute>=start)&((minute-start)%h==0)]
    f=f.merge(facility,on=['timestamp','room_id'],validate='one_to_one').merge(
        profiles[['room_id','volume_m3','ventilation_off_ach','ventilation_on_ach','opening_time','closing_time']],
        on='room_id',validate='many_to_one')
    closing=f.closing_time.str[:2].astype(int)*60+f.closing_time.str[3:].astype(int)
    opening=f.opening_time.str[:2].astype(int)*60+f.opening_time.str[3:].astype(int)
    now=f.timestamp.dt.hour*60+f.timestamp.dt.minute
    future=f.target_time.dt.hour*60+f.target_time.dt.minute
    f=f[(now>=opening)&(now<closing)&(future<closing)&(f.target_time.dt.date==f.timestamp.dt.date)].copy()
    f=f.rename(columns={'timestamp':'asof','co2_ppm':'co2','occupancy_count':'occupancy'})
    for c in ['ventilation_on']:
        if f[c].dtype!='bool': f[c]=f[c].astype(str).str.lower().map({'true':True,'false':False})
        f[c]=f[c].astype(float)
    f=f.dropna(subset=['co2','target_co2'] if include_targets else ['co2'])
    return add_clock(f)

def build_personal_s5():
    if (OUTPUT/'S5_model.joblib').exists():
        raise FileExistsError('Frozen S5 model exists; prepare a fresh version directory before rebuilding data')
    run_root=HERE/'simulations/personal_baseline'
    manifest=json.loads((run_root/'reports/manifest.json').read_text(encoding='utf-8'))
    validation=json.loads((run_root/'reports/validation_report.json').read_text(encoding='utf-8'))
    assert manifest['status']=='complete' and validation['valid']
    profiles=pd.read_csv(run_root/'inputs/room_profiles.csv')
    expected=set(PROFILE['simulation_representative_rooms'])
    parts=[];counts=[];hashes={}
    for path in sorted((run_root/'raw/sensors_1min').glob('*.csv')):
        raw=pd.read_csv(path,usecols=['timestamp','room_id','co2_ppm','occupancy_count'])
        raw['timestamp']=pd.to_datetime(raw.timestamp)
        assert set(raw.room_id)==expected and not raw.duplicated(['timestamp','room_id']).any()
        facility_path=run_root/'raw/facility_states_1min'/path.name.replace('sensor_readings_','facility_states_')
        facility=pd.read_csv(facility_path,usecols=['timestamp','room_id','ventilation_on','ventilation_level'])
        facility['timestamp']=pd.to_datetime(facility.timestamp)
        part=s5_day(raw,facility,profiles);parts.append(part)
        counts.append({'date':path.stem[-10:],'raw_sensor_rows':len(raw),'s5_candidates':len(part)})
        for p in [path,facility_path]:hashes[str(p.relative_to(run_root))]=digest(p)
    frame,bounds=finalize(pd.concat(parts,ignore_index=True),S5_FEATURES,'target_co2')
    frame[['room_id','asof','target_time','split']+S5_FEATURES+['target_co2']].to_csv(OUTPUT/'S5_dataset.csv.gz',index=False,compression='gzip')
    contract=json.loads((OUTPUT/'data_contract.json').read_text(encoding='utf-8'))
    contract['models']['S1']['source_root']=str(SOURCE)
    contract['models']['S5']={'features':S5_FEATURES,'target':'target_co2','baseline_feature':'co2','rows':len(frame),
        'splits':bounds,'source_root':str(run_root),'rooms':sorted(expected),
        'definition':'CO2 eight minutes ahead under personal 890/850 policy; four fixed representative rooms',
        'origin':'new synthetic personal baseline; not all common-run rooms or actual observations'}
    contract['personal_s5_daily_counts']=counts;contract['personal_s5_source_sha256']=hashes
    contract['personal_s5_sampling']='Every 8 minutes from 10:00 to before closing, exact t+8 target; 8-minute observed lookback allowed'
    write_json(OUTPUT/'data_contract.json',contract)
    print('Personal S5 dataset',len(frame),bounds,flush=True)

def main():
    OUTPUT.mkdir(exist_ok=True)
    if (OUTPUT/'S1_model.joblib').exists():
        raise FileExistsError('Frozen S1 model exists; prepare a fresh version directory before rebuilding data')
    manifest=json.loads((SOURCE/'reports/manifest.json').read_text(encoding='utf-8'))
    assert manifest['status']=='complete' and manifest['software_version']=='0.2.0'
    profiles=pd.read_csv(SOURCE/'inputs/room_profiles.csv')
    rooms=pd.read_csv(SOURCE/'inputs/rooms.csv')
    assert len(rooms)==63 and set(profiles.room_id)==set(rooms.room_id)
    source_hashes={str(p.relative_to(SOURCE)):digest(p) for p in [SOURCE/'inputs/room_profiles.csv',SOURCE/'inputs/rooms.csv']}
    s1=[];counts=[]
    for path in sorted((SOURCE/'raw/sensors_1min').glob('*.csv')):
        raw=pd.read_csv(path,usecols=SENSOR_COLUMNS)
        raw['timestamp']=pd.to_datetime(raw.timestamp)
        assert not raw.duplicated(['timestamp','room_id']).any()
        assert set(raw.room_id)==set(rooms.room_id)
        # S1 never reads facility states, energy, reservations, or truth.
        a=s1_day(raw,profiles)
        s1.append(a)
        counts.append({'date':path.stem[-10:],'raw_sensor_rows':len(raw),'s1_candidates':len(a)})
        source_hashes[str(path.relative_to(SOURCE))]=digest(path)
        print(path.stem[-10:],len(a),flush=True)
    frames={}; contracts={}
    for name,parts,features,target in [('S1',s1,S1_FEATURES,'target_score')]:
        frame,bounds=finalize(pd.concat(parts,ignore_index=True),features,target)
        keep=['room_id','asof','target_time','split']+features+[target]
        # Extra raw channels and other scenario fields never reach the learning table.
        frame[keep].to_csv(OUTPUT/f'{name}_dataset.csv.gz',index=False,compression='gzip')
        contracts[name]={'features':features,'target':target,'rows':len(frame),'splits':bounds,
                         'baseline_feature':'score_current' if name=='S1' else 'co2',
                         'definition':'future design-preference proxy score, not satisfaction' if name=='S1' else 'future observed CO2 under logged control policy',
                         'origin':'synthetic v0.2 observations, source snapshot unchanged'}
    write_json(OUTPUT/'data_contract.json',{'profile':PROFILE,'models':contracts,'daily_counts':counts,
               'source_sha256':source_hashes,'source_root':str(SOURCE),
               'excluded_files':['truth/*','events/reservations.csv','raw/energy_usage_1min/*'],
               'sampling':'10:00 to synthetic profile closing time; 8-minute forecast; S5 may use 8 minutes of earlier observed context'})
    print('Datasets saved.',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--scenario',choices=['initial','S5'],default='initial')
    args=parser.parse_args()
    if args.scenario=='S5':build_personal_s5()
    else:main()
