"""Label-free historical inference views: future target availability is irrelevant."""
import pandas as pd
from common import HERE, SOURCE, OUTPUT, PROFILE, digest, write_json
from build_datasets import SENSOR_COLUMNS, S1_FEATURES, S5_FEATURES, s1_day, s5_day

parts={'S1':[],'S5':[]}
for scenario in parts:
    root=SOURCE if scenario=='S1' else HERE/'simulations/personal_baseline'
    profiles=pd.read_csv(root/'inputs/room_profiles.csv')
    for date in pd.date_range(*PROFILE['test_dates']):
        text=f'{date:%Y-%m-%d}'
        path=root/f'raw/sensors_1min/sensor_readings_{text}.csv'
        columns=SENSOR_COLUMNS if scenario=='S1' else ['timestamp','room_id','co2_ppm','occupancy_count']
        raw=pd.read_csv(path,usecols=columns);raw['timestamp']=pd.to_datetime(raw.timestamp)
        if scenario=='S1':frame=s1_day(raw,profiles,include_targets=False)
        else:
            f=pd.read_csv(root/f'raw/facility_states_1min/facility_states_{text}.csv',
                          usecols=['timestamp','room_id','ventilation_on','ventilation_level'])
            f['timestamp']=pd.to_datetime(f.timestamp)
            frame=s5_day(raw,f,profiles,include_targets=False)
        frame['split']='test';features=S1_FEATURES if scenario=='S1' else S5_FEATURES
        parts[scenario].append(frame[['room_id','asof','target_time','split']+features])
    result=pd.concat(parts[scenario],ignore_index=True)
    assert 'target_score' not in result and 'target_co2' not in result
    assert not result.duplicated(['room_id','asof']).any()
    result.to_csv(OUTPUT/f'{scenario}_inference_inputs.csv.gz',index=False,compression='gzip')
    print(scenario,'label-free input rows',len(result))
write_json(OUTPUT/'inference_input_contract.json',{
    'origin':'current and past observed values only; no target-label availability filter',
    'scheduled_target_time':'known asof + 8 minutes; not an observed future value',
    'sha256':{s:digest(OUTPUT/f'{s}_inference_inputs.csv.gz') for s in parts},
    'test_dates':PROFILE['test_dates']})
