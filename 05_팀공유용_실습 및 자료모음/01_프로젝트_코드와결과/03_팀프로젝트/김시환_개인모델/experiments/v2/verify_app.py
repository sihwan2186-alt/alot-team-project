"""Exercise the version switch, six virtual cases and S5 round trip without fitting."""
from pathlib import Path
import sys
import hashlib
from streamlit.testing.v1 import AppTest

HERE=Path(__file__).resolve().parent
PERSONAL=HERE.parents[1]
sys.path.insert(0,str(PERSONAL))
paths=[*list((PERSONAL/'results').glob('*_model.joblib')),HERE/'artifacts/S1_model.joblib']
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
app=AppTest.from_file(str(PERSONAL/'app.py'),default_timeout=90).run()
assert not app.exception,app.exception
app.sidebar.radio[1].set_value('v2').run()
assert not app.exception,app.exception
assert len(app.sidebar.selectbox[0].options)==12
messages=['PASS v1 to v2 switch; 12 held-out scenario runs']
for scenario in ['normal','humid','crowded','dark','missing','hot_humid']:
    app.sidebar.selectbox[0].set_value(f'test_3201_{scenario}').run()
    assert not app.exception,app.exception
    assert any('현재 환경 점수순' in c.value for c in app.caption)
    table=app.dataframe[0].value
    for _,group in table.groupby('현재 상태'):
        assert group['현재 점수 (정렬 기준)'].dropna().is_monotonic_decreasing
    expected_cards=[f"**{name.split(' (')[0]}**" for name in
        table.loc[table['현재 상태']=='조건 충족','공간'].head(3)]
    actual_cards=[m.value for m in app.markdown if m.value.startswith('**') and m.value.endswith('**')]
    assert actual_cards==expected_cards, (scenario, actual_cards, expected_cards)
    messages.append('PASS scenario '+scenario+'; comparison order matches recommendation cards')
app.sidebar.radio[0].set_value('관리자 · S5 제어 검토').run()
assert not app.exception,app.exception
assert len(app.sidebar.selectbox[1].options)==4
app.sidebar.radio[0].set_value('학생 · S1 추천').run()
assert not app.exception,app.exception
assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
messages.append('PASS S5 round trip and frozen v1/v2 model hashes')
(HERE/'artifacts/app_validation.txt').write_text('\n'.join(messages)+'\n',encoding='utf-8')
print('\n'.join(messages))
