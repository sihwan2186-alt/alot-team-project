"""One command: train, evaluate, persist model, simulate and verify S1/S5."""
from pathlib import Path
import csv
import hashlib
import io
import json
import sqlite3
import unittest

from demo import Checks, SOURCE
from ml_model import infer, train_bundle
from simulation import run_simulation
import test_runtime
import test_system

HERE=Path(__file__).resolve().parent
OUT=HERE/'시뮬레이션_결과'


def write_csv(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main():
    OUT.mkdir(exist_ok=True)
    source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    bundle,rows=train_bundle()
    model_path=OUT/'trained_models.json'
    model_path.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
    # Inference uses the saved artifact, not a separately fitted in-memory tree.
    restored=json.loads(model_path.read_text(encoding='utf-8'))
    write_csv(OUT/'synthetic_ml_dataset.csv',rows)
    predictions=[]
    for row in rows:
        if row['split']=='test':
            p=infer(restored,row)
            predictions.append({'virtual_room':row['virtual_room'],'tick':row['tick'],
                                'environment_true':row['environment_suitable'],
                                'environment_predicted':p['environment']['prediction'],
                                'ventilation_true':row['ventilation_needed'],
                                'ventilation_predicted':p['ventilation']['prediction']})
    write_csv(OUT/'holdout_predictions.csv',predictions)
    simulation=run_simulation(restored,OUT)
    write_csv(OUT/'sensor_trace.csv',simulation['samples'])
    (OUT/'simulation_results.json').write_text(json.dumps(simulation,ensure_ascii=False,indent=2),encoding='utf-8')
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Checks),
                             unittest.defaultTestLoader.loadTestsFromModule(test_runtime),
                             unittest.defaultTestLoader.loadTestsFromModule(test_system)])
    stream=io.StringIO(); result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (OUT/'test_log.txt').write_text(stream.getvalue(),encoding='utf-8')
    with sqlite3.connect((OUT/'simulation.db').as_uri()+'?mode=ro',uri=True) as db:
        integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
        fk=db.execute('PRAGMA foreign_key_check').fetchall()
        counts={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0]
                for t in ('rooms','commands','audit','simulation_samples','simulation_events')}
    checks={'tests_run':result.testsRun,'tests_passed':result.wasSuccessful(),
            'original_snapshot_unchanged':source_hash==hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'sqlite_integrity':integrity,'foreign_key_violations':fk,'table_counts':counts}
    (OUT/'verification.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    success=result.wasSuccessful() and checks['original_snapshot_unchanged'] and integrity=='ok' and not fk
    lines=['# S1과 S5 소프트웨어 시뮬레이션 완성본','',
           '2026년 10월 18일 작성. 범위는 가상 센서·ML 판단·가상 장치·재관측으로 이어지는 소프트웨어 시뮬레이션이다. 실제 장치 연결은 프로젝트 완료 조건에 포함하지 않는다.',
           '',f'전체 자동 검사 {result.testsRun}개 '+('통과.' if success else '검토 필요.'),
           f"가상 방 6개, 가상 시간 30분, 30초 간격 관측 {len(simulation['samples'])}행. SQLite 무결성 {integrity}, 외래키 위반 {len(fk)}건. 원본 데이터 보존 확인.",
           '', '## 연결한 기능','',
           '- S1: 필수 환경·시각·예약 조건 → 학습된 환경 적합성 분류 → 사용자 선호 가중 점수 → 순위·근거.',
           '- S5: 현재 CO₂·증가 추세 → 학습된 환기 필요 분류 → 고정 경계와 수동·센서 상태 검사 → 가상 명령·ACK → 환경 방정식으로 다음 관측 생성 → 목표 도달 확인.',
           '- 환기 외 온도·습도·조명은 가상 목표값 23°C·50%RH·400lux를 적용하고 시간에 따라 수렴한다. 이 세 제어는 집약된 가상 명령·즉시 ACK 모델이며 환기처럼 개별 장애·이력 상태 머신을 갖추지는 않았다.',
           '', '## ML 학습과 시험','',
           '표준 라이브러리로 구현한 CART 의사결정나무 2개를 학습해 JSON으로 저장하고, 저장 파일을 다시 읽어 추론에 사용한다. 최대 깊이 8, 최소 잎 표본 6, 난수 시드 20261019를 고정했다. 필수 패키지 설치가 없다.',
           '', '가상 방 120개의 2,880행 중 학습 72방·1,728행, 검증 24방·576행, 최종 시험 24방·576행으로 방 단위 분리했다. 시험 방은 학습·검증에 사용하지 않았다. 설정은 미리 고정했고 시험 결과에 따라 조정하지 않았다.',
           '', '| 모델과 최종 시험 | TP | FP | FN | TN | Precision | Recall | F1 |',
           '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,label in [('environment','환경 적합성'),('ventilation','환기 필요')]:
        score=bundle['evaluation'][name]['test']
        lines.append(f"| {label} | {score['tp']} | {score['fp']} | {score['fn']} | {score['tn']} | {score['precision']:.4f} | {score['recall']:.4f} | {score['f1']:.4f} |")
    lines += ['', '이 수치는 설계 규칙으로 만든 합성 정답을 모방한 성능이다. 실제 사용자 만족도나 독립된 물리 환경의 예측 성능을 뜻하지 않는다. 환기 규칙이 단순하므로 높은 점수는 ML이 규칙보다 우수하다는 증거가 아니다. W07 교수 제공 입력의 과제 지표를 대체하지 않는다.',
              '', '환경 정답은 온도20~26°C·습도40~60%RH·CO₂<890ppm·조도≥300lux·소음≤45dB·혼잡도≤0.75의 동시 충족이다. 환기 정답은 CO₂≥890 또는 CO₂>850이면서 증가 추세≥12ppm/분이다. 모두 프로젝트용 가정이다. 학습 입력에 정답 열·방 ID·분할 정보는 넣지 않았다.',
              '', '## 가상 방별 피드백 결과','',
              '| 가상 방 | 초기 CO₂ | 30분 후 CO₂ | 추천 이력 | 재확인 결과 |', '|---|---:|---:|---|---|']
    for name,room in simulation['rooms'].items():
        states=', '.join(dict.fromkeys(v['status'] for v in room['verification'])) or '해당 없음'
        lines.append(f"| {name} | {room['initial_co2']:.1f} | {room['final_co2']:.1f} | {'있음' if room['ever_recommended'] else '없음'} | {states} |")
    early=next(e for e in simulation['events'] if e['event']=='virtual_ventilation_command' and e['room']=='F_ML조기환기' and e['desired'])
    lines += ['', f"ML 조기 환기 방은 {early['at']}초의 CO₂ {early['co2']:.3f}ppm에서 증가 추세를 반영해 환기를 시작했다. 고정 켜기 경계 890ppm에 도달하기 전이다. CO₂≤850이면 ML 출력과 관계없이 끄기 경계가 우선한다.",
              '', '정상 방의 환기 후 변화는 방정식으로 계산했다. ACK만 받고 CO₂가 개선되지 않는 방은 목표 미도달로 구분했고, 센서 오류·수동 모드는 자동 제어를 막았다. ACK 누락 방은 시간 초과 후 2분마다 가상 상태를 조회해 복구한다.',
              '', '## 시뮬레이션 가정','',
              '환기는 완전 혼합 단일 공간 모델을 사용한다. 외기 CO₂ 420ppm, 재실 1명당 CO₂ 증가 5ppm/분, 기본 공기교환 0.2회/시간, 정상 환기 6회/시간을 가정한다. C_next=C_eq+(C−C_eq)×exp(−k×Δt), C_eq=420+5×인원/k, k는 분당 공기교환율이다. 환기 효과 없음 시험에서는 팬이 켜져도 공기교환이 증가하지 않는다.',
              '', '온도·습도 목표 수렴 시간상수는 4분, 조명은 0.25분이다. 실제 교내 공간에 보정된 물리 모델이 아니다. 관측 간격이 30초이므로 ACK 후 8분이 지난 첫 관측인 약 8분30초에 결과를 확인한다. 환기 켜기 명령 뒤에는 그 검증창까지 상태를 유지하는 최소 가동 정책을 적용한다. 끄기 후에도 8분 검증을 예약하되 CO₂≥890이면 먼저 다시 켠다.',
              '', '가상 장치는 명령 틱에서 상태를 적용하고 ACK 시각을 1초 뒤로 기록한다. 환경 적분은 30초 단위로 수행하므로 1초 전송 지연의 물리 효과는 별도 적분하지 않는다. 수동·센서 오류 시나리오는 실행 중 상태 전환이 아닌 시작 시점부터 고정된 조건이다.',
              '', '## 실행과 산출물','',
              r'프로젝트 루트에서 `.\.venv\Scripts\python.exe .\03_팀프로젝트\S1_S5\run_system.py`를 실행한다. 기존 결과 파일은 재생성되며 원본 보고서·CSV·DB는 변경하지 않는다.',
              '', '- trained_models.json: 저장된 나무·특징 순서·학습 조건·분할별 혼동행렬',
              '- synthetic_ml_dataset.csv / holdout_predictions.csv: 생성 학습 자료와 시험 정답·예측',
              '- sensor_trace.csv / simulation_results.json: 시간별 센서·예측·명령·추천·재확인',
              '- simulation.db: 방 상태·명령·감사 이력·관측·시뮬레이션 이벤트',
              '- test_log.txt / verification.json: 검사 결과·원본 보존·DB 무결성',
              '', '## 내일 발표에 추가할 문장','',
              '“실제 장치를 쓰지 않는 조건에 맞춰 센서와 장치, 환경 변화를 모두 가상화했습니다. 의사결정나무를 합성 데이터로 학습해 추천 후보 판단과 조기 환기에 연결했습니다. 추천부터 명령, 응답, 환경 변화, 재관측까지 실행됩니다. 정상 환기뿐 아니라 응답 누락, 환기 효과 없음, 수동 모드, 센서 오류도 비교했습니다. ML 점수는 합성 규칙 재현 성능이고 실제 사용자 평가 결과는 아닙니다.”',
              '', '남은 팀 검토는 선호 가중치·환경 목표·ML 라벨 규칙·공통 공간 키·S5 공동 분담에 대한 합의다. 실제 장치 통신·실측 KPI는 이 프로젝트 범위에서 제외한다.']
    (HERE/'시뮬레이션_완성본_검토안내.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Software simulation: {"PASS" if success else "FAIL"}; {result.testsRun} tests; {len(simulation["samples"])} samples')
    print('Report: '+str(HERE/'시뮬레이션_완성본_검토안내.md'))
    if not success: raise SystemExit(1)


if __name__=='__main__': main()
