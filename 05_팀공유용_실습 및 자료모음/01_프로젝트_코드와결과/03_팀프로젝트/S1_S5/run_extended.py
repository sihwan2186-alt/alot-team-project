"""Reproducible offline scenarios and test report; original files stay intact."""
from datetime import datetime, timedelta
from pathlib import Path
import csv
import hashlib
import io
import json
import tempfile
import unittest

from demo import SOURCE, Checks
from runtime import Controller, recommend_live
import test_runtime

HERE = Path(__file__).resolve().parent
BASE = datetime.fromisoformat('2026-10-18T10:00:00+09:00')


def at(seconds=0):
    return (BASE+timedelta(seconds=seconds)).isoformat()


def run():
    before=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    with SOURCE.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    # Replay assumption only: do not relabel the historical snapshot as current.
    replay=[{**r,'observed_at':r['time']+'+09:00','sensor_valid':True,
             'data_origin':'historical_synthetic_replay_timezone_assumed_Asia_Seoul',
             'reservation_available':None} for r in rows]
    clock='2026-09-22T23:30:00+09:00'
    comparisons={
        'historical_preference_only':recommend_live(replay,clock,min_light=None,temperature=None,humidity=None),
        'historical_required_light_temp_humidity':recommend_live(replay,clock),
        'historical_reservation_required':recommend_live(replay,clock,require_reservation=True),
        'historical_snapshot_used_on_review_day':recommend_live(replay,at()),
    }
    events=[]
    a=('team02','시연용가상건물','A'); b=('team02','시연용가상건물','B')
    def record(event,result): events.append({'event':event,'result':result})
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'offline.db'
        c=Controller(path)
        try:
            c.reconcile(a,False,at(),at()); c.reconcile(b,False,at(),at())
            ca=c.request(a,1000,at(),at()); cb=c.request(b,1000,at(),at())
            record('A_mock_on_request',ca); record('B_mock_on_request',cb)
            record('A_duplicate_blocked',c.request(a,1000,at(1),at(1)))
        finally:
            c.close()
        c=Controller(path)
        try:
            record('A_ack_after_storage_reopen',c.ack(a,ca['command_id'],True,at(2)))
            record('B_timeout',c.tick(b,at(5)))
            record('B_late_ack_ignored',c.ack(b,cb['command_id'],True,at(6)))
            record('B_unknown_state_blocks_request',c.request(b,1000,at(7),at(7)))
            c.reconcile(b,True,at(8),at(8)); record('B_fresh_device_state_reconciled',True)
            record('A_observation_before_due_time',c.verify(a,ca['command_id'],840,at(480),at(482)))
            record('A_target_at_due_time',c.verify(a,ca['command_id'],840,at(482),at(482)))
            off=c.request(a,840,at(483),at(483)); record('A_mock_off_request',off)
            record('A_mock_off_ack',c.ack(a,off['command_id'],False,at(484)))
            record('A_off_remeasurement',c.verify(a,off['command_id'],840,at(964),at(964)))
            db_export=c.export()
        finally:
            c.close()
    suite=unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(Checks),
        unittest.defaultTestLoader.loadTestsFromModule(test_runtime)])
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (HERE/'extended_test_log.txt').write_text(stream.getvalue(),encoding='utf-8')
    report={'origin':'Codex offline synthetic software execution 2026-10-18',
            'source_sha256':before,'source_unchanged':before==hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'timezone_assumption':'Historical naive timestamps interpreted as +09:00 only for offline replay.',
            'tests_run':result.testsRun,'tests_passed':result.wasSuccessful(),
            'recommendation_comparisons':comparisons,'control_events':events,'mock_database_export':db_export}
    (HERE/'extended_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# S1과 S5 추가 구현 실행 결과','',
           '2026-10-18 Codex 오프라인 실행. 실제 센서·예약·장치 통신 및 ML 모델 실행 결과가 아니다.',
           '',f'자동 검사 {result.testsRun}개: '+('모두 통과' if result.wasSuccessful() else '실패 있음'),
           '입력 원본 SHA-256 보존: '+str(report['source_unchanged']),'',
           '## 추천 조건별 비교','',
           '| 비교 조건 | 추천 후보 수 | 의미 |','|---|---:|---|']
    labels={
        'historical_preference_only':('과거 시각 재생, 선호 점수 중심','필수 밝기·온습도 필터 해제'),
        'historical_required_light_temp_humidity':('과거 시각 재생, 밝기·온습도 필수','300lux·20~26°C·40~60%RH 적용'),
        'historical_reservation_required':('과거 시각 재생, 예약 확인 필수','예약 unknown을 가능으로 인정하지 않음'),
        'historical_snapshot_used_on_review_day':('과거 데이터를 10월 18일 현재용으로 요청','120초 유효 시간 초과로 제외')}
    for name,data in comparisons.items():
        label,meaning=labels[name]
        lines.append(f"| {label} | {len(data['rankings'])} | {meaning} |")
    lines += ['', '필수 밝기·온습도 조건을 적용한 과거 재생 순위:', '',
              '| 순위 | 공간 | 선호 점수 | 조도 lux |', '|---|---|---:|---:|']
    for rank,row in enumerate(comparisons['historical_required_light_temp_humidity']['rankings'],1):
        lines.append(f"| {rank} | {row['building']} {row['room']} | {row['score']} | {row['values']['light']} |")
    lines += ['', '과거 원본 시각에는 시간대가 없어 재생 비교에서만 +09:00을 가정했다. sensor_valid=True도 재생용 시험 가정이며 센서 정상 판정의 실증이 아니다. 원본의 관측값이나 시각을 현재 값으로 변경하지 않았다.',
              '', '## 제어 시연 흐름','', '| 시험 단계 | 결과 |','|---|---|']
    for event in events:
        value=event['result']
        if isinstance(value,dict): value=value.get('status',str(value))
        lines.append(f"| {event['event']} | {value} |")
    lines += ['', 'A·B는 실제 방이 아닌 시험 키다. SQLite를 닫았다 다시 열어 A 명령 응답을 처리했다. B의 늦은 응답은 무시했고 새 장치 상태 확인을 명시적으로 수행한 뒤 미확인 상태를 해제했다.',
              '', '## 최신 범위와 실행본','',
              '- 실제 장치는 사용하지 않는 것으로 확정했다. 실제 통신은 남은 작업에 포함하지 않는다.',
              '- 이 문서는 중간 버전 결과다. 최신 run_system.py는 ML 학습·저장·추론과 동적 환경·가상 명령·재관측을 실행한다.',
              '- 최신 시뮬레이션_완성본_검토안내.md와 시뮬레이션_결과 폴더를 참고한다.',
              '- 상태 복구는 가상 장치의 상태 조회로 수행하며 스케줄러는 가상 시계로 구동한다.',
              '', r'실행: 프로젝트 루트에서 `.\.venv\Scripts\python.exe .\03_팀프로젝트\S1_S5\run_extended.py`. 결과 JSON과 검사 로그는 이 폴더에 갱신된다. DB 시험은 임시 폴더에서만 수행하며 기존 W06 DB를 수정하지 않는다.']
    (HERE/'추가구현_실행결과.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Tests: {result.testsRun}, passed: {result.wasSuccessful()}, source unchanged: {report["source_unchanged"]}')
    for name,data in comparisons.items(): print(name,len(data['rankings']))
    if not result.wasSuccessful() or not report['source_unchanged']: raise SystemExit(1)


if __name__=='__main__': run()
