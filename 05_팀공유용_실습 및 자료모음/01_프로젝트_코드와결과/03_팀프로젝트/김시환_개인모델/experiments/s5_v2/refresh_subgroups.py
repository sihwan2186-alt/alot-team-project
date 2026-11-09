"""Rebuild subgroup tables from saved predictions, retaining unknown trend rows; no fitting."""
from pathlib import Path
import json
import pandas as pd
from run_comparison import tagged,metrics

OUT=Path(__file__).resolve().parent/'artifacts'
d=pd.read_csv(OUT/'audit_dataset.csv.gz',parse_dates=['asof','target_time'])
p=pd.read_csv(OUT/'audit_predictions.csv.gz')
profiles=pd.read_csv(OUT/'room_profiles.csv')
models=pd.read_csv(OUT/'model_audit.csv').method.tolist()
g=tagged(d,profiles)
dimensions={'scenario':'scenario','building':'building','room':'room_id','hour':'hour','crowding':'crowding',
 'current_co2':'co2_band','ventilation':'ventilation_state','volume':'volume_band','on_ach':'ach_band',
 'seed':'seed','past_missing':'past_missing','trend':'trend_band'}
rows=[]
for method in models:
    g['_prediction']=p[method].to_numpy()
    for dimension,column in dimensions.items():
        count=0
        for label,part in g.groupby(column):
            rows.append({'method':method,'dimension':dimension,'group':str(label),**metrics(part.target_co2,part._prediction)})
            count+=len(part)
        assert count==len(d),(method,dimension)
pd.DataFrame(rows).to_csv(OUT/'subgroup_audit.csv',index=False,encoding='utf-8-sig')
summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
summary['subgroup_result_rows']=len(rows)
summary['subgroup_note']='Unknown past CO2 trend retained as an explicit subgroup, including 128 audit rows'
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print('Subgroup metric rows:',len(rows))
