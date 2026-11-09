"""Read-only inference using input columns only; future labels never enter a model."""
from datetime import timedelta
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from common import OUTPUT, PROFILE

def eligibility(frame):
    p=PROFILE
    checks={
        '온도 범위':frame.temp.between(*p['temperature_range_c']),
        '습도 범위':frame.humidity.between(*p['humidity_range_pct']),
        'CO₂ 기준':frame.co2<p['ventilation_on_ppm'],
        '소음 기준':frame.noise<=p['maximum_noise_dba'],
        '조도 기준':frame.light>=p['minimum_illuminance_lux'],
        '여유 좌석':frame.capacity-frame.occupancy>=1,
    }
    result=pd.DataFrame(checks,index=frame.index)
    return result.all(axis=1),result.apply(lambda r:', '.join(r.index[~r].tolist()),axis=1)

def predict_snapshot(scenario, frame, asof, bundle=None):
    bundle=bundle or joblib.load(OUTPUT/f'{scenario}_model.joblib')
    timestamp=pd.Timestamp(asof)
    if timestamp.tzinfo is None:raise ValueError('Timezone-aware asof is required')
    if timestamp.strftime('%Y-%m-%d')<PROFILE['test_dates'][0]:
        raise ValueError('This demonstration exposes frozen held-out dates only')
    # Require a window/instant at the requested time; do not pass a stale row as current.
    snapshot=frame[frame['asof']==timestamp].copy()
    if snapshot.empty:return snapshot
    x=snapshot[bundle['features']]
    with threadpool_limits(limits=2):
        value=snapshot[bundle['baseline_feature']].to_numpy() if bundle['model'] is None else bundle['model'].predict(x)
    snapshot['prediction']=np.clip(value,0,100) if scenario=='S1' else np.maximum(value,0)
    if scenario=='S1':snapshot['eligible'],snapshot['exclusion_reason']=eligibility(snapshot)
    return snapshot

def ventilation_advice(co2,predicted,currently_on):
    if not np.isfinite(co2) or not np.isfinite(predicted):return '입력 확인 필요'
    if co2>=PROFILE['ventilation_on_ppm']:return '현재 기준 초과: 환기 켜기 검토'
    if co2<=PROFILE['ventilation_off_ppm']:return '현재 해제 기준: 환기 끄기 검토'
    if predicted>=PROFILE['ventilation_on_ppm']:return '8분 뒤 초과 예상: 조기 환기 검토'
    return '이전 상태 유지 검토'
