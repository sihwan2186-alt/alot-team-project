from pathlib import Path
import csv,json,hashlib,ast
from collections import Counter
import xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[2]
O=R/'deliverables/assets'
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
rooms=read(R/'data/master/rooms.csv');profiles=read(R/'data/master/room_profiles.csv')
run=R/'data/runs/full-30d';summary=json.loads((run/'reports/summary.json').read_text())
faults=read(run/'truth/anomaly_events.csv')
event=next(f for f in faults if f['anomaly_type']=='bias')
date=event['start_time'][:10];rid=event['room_id']
# Read only the selected room from a single daily file; no multi-day sensor table is loaded.
def selected(folder,stem,date,rid):
 p=run/f'{folder}/{stem}_{date}.csv'
 with p.open(encoding='utf-8-sig',newline='') as f:return [r for r in csv.DictReader(f) if r['room_id']==rid]
day='2026-09-01';room='STU-B102A'
data=dict(rooms=rooms,profiles=profiles,building_counts=dict(Counter(r['building_code'] for r in rooms)),type_counts=dict(Counter(p['room_type'] for p in profiles)),
 summary=summary,validation=json.loads((run/'reports/validation_report.json').read_text()),manifest=json.loads((run/'reports/manifest.json').read_text()),
 repro=json.loads((R/'data/runs/reproducibility.json').read_text()),fault_counts=dict(Counter(f['anomaly_type'] for f in faults)),fault_example=event,
 day=dict(date=day,room_id=room,sensors=selected('raw/sensors_1min','sensor_readings',day,room),truth=selected('truth/environment_truth_1min','environment_truth',day,room),energy=selected('raw/energy_usage_1min','energy_usage',day,room)),
 fault_day=dict(sensors=selected('raw/sensors_1min','sensor_readings',date,rid),truth=selected('truth/environment_truth_1min','environment_truth',date,rid)))
# Read all code and existing docs for traceability and non-modification evidence.
paths=[*R.glob('src/aiot_sim/**/*.py'),*R.glob('tests/**/*.py'),*R.glob('configs/*.toml'),*R.glob('docs/*.md'),R/'README.md',R/'pyproject.toml',R/'data/master/rooms.csv',R/'data/master/room_profiles.csv',*run.rglob('*.csv'),*run.glob('reports/*.json')]
hashes={}
for p in paths:
 if '__pycache__' in p.parts:continue
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 hashes[str(p.relative_to(R))]=h.hexdigest()
mods=[]
for p in sorted(R.glob('src/aiot_sim/**/*.py')):
 tree=ast.parse(p.read_text());mods.append(dict(path=str(p.relative_to(R)),functions=[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]))
data['modules']=mods
suite=ET.parse(R/'verification/pytest-results.xml').getroot()
data['test_cases']=[dict(n.attrib) for n in suite.iter('testcase')]
data['pytest_log']=(R/'verification-pytest.log').read_text()
# Actual headers from each file family; retain description text from existing data dictionary.
headers={}
for path in [R/'data/master/rooms.csv',R/'data/master/room_profiles.csv',*sorted((run/'events').glob('*.csv')),run/'truth/anomaly_events.csv']:
 with path.open(encoding='utf-8-sig') as f:headers[str(path.relative_to(R))]=next(csv.reader(f))
for folder in ['raw/sensors_1min','raw/facility_states_1min','raw/energy_usage_1min','truth/environment_truth_1min','derived/sensors_5min','derived/energy_5min']:
 path=next((run/folder).glob('*.csv'))
 with path.open(encoding='utf-8-sig') as f:headers[str(path.relative_to(R))]=next(csv.reader(f))
data['headers']=headers
O.joinpath('verified_facts.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
O.joinpath('source_hashes_before.json').write_text(json.dumps(hashes,indent=2))
print(data['building_counts'],data['type_counts'],len(data['test_cases']),event)
