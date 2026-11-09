"""Export the team's shared result contract, without future actual labels."""
from datetime import datetime, timezone
import joblib
import pandas as pd
from common import OUTPUT, PROFILE, write_json
from inference import predict_snapshot, ventilation_advice

for scenario,identifier in [('S1','1'),('S5','5')]:
    frame=pd.read_csv(OUTPUT/f'{scenario}_inference_inputs.csv.gz',parse_dates=['asof','target_time'])
    frame=frame[frame.split=='test']
    asof=frame['asof'].max()
    bundle=joblib.load(OUTPUT/f'{scenario}_model.joblib')
    snapshot=predict_snapshot(scenario,frame,asof,bundle)
    rows=[]
    for _,row in snapshot.iterrows():
        result={'scenario_id':identifier,'model_name':bundle['selected_name'],
            'model_version':'kim_sihwan_20261103_v1','generated_at':datetime.now(timezone.utc).isoformat(),
            'room_id':row.room_id,'input_data_end_time':row['asof'].isoformat(),
            'prediction_target_time':row.target_time.isoformat(),
            'mode':'retrospective_heldout_replay','data_origin':'synthetic',
            'reason_codes':['not_observed_user_satisfaction'] if scenario=='S1' else ['forecast_not_device_ack']}
        if scenario=='S1':
            result.update(score=float(row.prediction),score_range=[0,100],eligible=bool(row.eligible),
                exclusion_reasons=row.exclusion_reason.split(', ') if row.exclusion_reason else [],
                target_definition='design-preference score of the next completed 8-minute window',
                operational_adoption='withheld_due_to_preference_coverage')
        else:
            result.update(predicted_value=float(row.prediction),unit='ppm',
                target_definition='observed CO2 at exactly t+8 minutes',
                advisory=ventilation_advice(row.co2,row.prediction,row.ventilation_on),
                verified_scope=PROFILE['simulation_representative_rooms'],actual_device_command_sent=False)
        rows.append(result)
    write_json(OUTPUT/f'{scenario}_latest_results.json',{'owner':PROFILE['owner'],'results':rows})
    print(scenario,len(rows),asof)
