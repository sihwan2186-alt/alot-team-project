from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SIMULATOR = HERE.parent / '공통시뮬레이터'
PROFILE = json.loads((HERE/'profile.json').read_text(encoding='utf-8'))
SOURCE = SIMULATOR/'data/runs'/PROFILE['source_run']
OUTPUT = HERE/'results'

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def preference_score(frame):
    p=PROFILE; w=p['weights']
    costs={
        'noise':((frame['noise']-30)/(p['maximum_noise_dba']-30)).clip(0,1),
        'crowding':(frame['occupancy']/frame['capacity']).clip(0,1),
        'co2':((frame['co2']-400)/(p['ventilation_on_ppm']-400)).clip(0,1),
        'temperature':((frame['temp']-p['target_temperature_c']).abs()/7).clip(0,1),
        'humidity':((frame['humidity']-p['target_humidity_pct']).abs()/20).clip(0,1),
        'light':((p['minimum_illuminance_lux']-frame['light'])/p['minimum_illuminance_lux']).clip(0,1),
    }
    # Propagate missing target channels; do not silently assign a favorable score.
    return 100*(1-sum(w[k]*v for k,v in costs.items()))

def add_clock(frame):
    minutes=frame['asof'].dt.hour*60+frame['asof'].dt.minute
    frame['hour_sin']=np.sin(2*np.pi*minutes/1440)
    frame['hour_cos']=np.cos(2*np.pi*minutes/1440)
    frame['weekday']=frame['asof'].dt.day_of_week
    return frame

def split_name(times):
    result=pd.Series('',index=times.index,dtype='str')
    day=times.dt.strftime('%Y-%m-%d')
    for label,field in [('train','train_dates'),('validation','validation_dates'),('test','test_dates')]:
        lower,upper=PROFILE[field]
        result.loc[day.between(lower,upper)]=label
    return result

def finalize(frame, features, target):
    frame['split']=split_name(frame['asof'])
    frame=frame[(frame['split']!='') & (split_name(frame['target_time'])==frame['split'])].copy()
    frame=frame.dropna(subset=[target])
    assert not frame.duplicated(['room_id','asof']).any()
    assert (frame['target_time']>frame['asof']).all()
    assert ((frame['target_time']-frame['asof']).dt.total_seconds()==60*PROFILE['horizon_minutes']).all()
    assert all(not any(s in f for s in ['target','future','truth','fault','no_show']) for f in features)
    bounds={label:{'rows':len(g),'asof_min':str(g['asof'].min()),'asof_max':str(g['asof'].max()),
                   'target_max':str(g.target_time.max())} for label,g in frame.groupby('split')}
    for earlier,later in [('train','validation'),('validation','test')]:
        assert frame.loc[frame.split==earlier,'target_time'].max()<frame.loc[frame.split==later,'asof'].min()
    return frame,bounds
