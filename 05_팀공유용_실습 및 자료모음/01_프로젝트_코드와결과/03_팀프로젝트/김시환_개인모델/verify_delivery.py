"""Read-only delivery checks; never fit or regenerate a model."""
from pathlib import Path
import hashlib
import json
import pandas as pd
from streamlit.testing.v1 import AppTest

HERE = Path(__file__).resolve().parent
OUT = HERE / 'results'
models = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*_model.joblib')}
contract = json.loads((OUT / 'data_contract.json').read_text(encoding='utf-8'))
checks = []
for name in ('S1', 'S5'):
    inputs = pd.read_csv(OUT / f'{name}_inference_inputs.csv.gz')
    allowed = {'room_id', 'asof', 'target_time', 'split', *contract['models'][name]['features']}
    assert set(inputs.columns) == allowed, (name, set(inputs.columns) ^ allowed)
    result = json.loads((OUT / f'{name}_latest_results.json').read_text(encoding='utf-8'))
    checks.append(f'{name}: label-free input rows={len(inputs)}; exported JSON parsed')
app = AppTest.from_file(str(HERE / 'app.py'), default_timeout=90).run()
assert not app.exception, app.exception
checks.append('PASS S1 label-free input display')
app.sidebar.radio[0].set_value('관리자 · S5 제어 검토').run()
assert not app.exception, app.exception
assert len(app.sidebar.selectbox[1].options) == 4
checks.append('PASS S5 four-room display')
app.sidebar.radio[0].set_value('학생 · S1 추천').run()
assert not app.exception, app.exception
checks.append('PASS role round trip')
assert models == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*_model.joblib')}
checks.append('PASS frozen model hashes unchanged')
(OUT / 'app_validation.txt').write_text('\n'.join(checks) + '\n', encoding='utf-8')
print('\n'.join(checks))
