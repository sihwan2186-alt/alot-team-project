# 최종 개발 보고서

> v0.2.0에서는 [모델 변경과 사용 안내](v0.2.0_release.md)가 우선합니다. 이 문서의 기존 실행 통계는 별도 표기가 없으면 v0.1.0 기준선입니다. 추가된 truth 파일·회복 레이블·검증 결과는 변경 안내와 deliverables/v0.2.0을 확인하세요.


## 1. 실제 프로젝트 구조

기존 과제는 보존하고 `smart-campus-aiot-simulator/`에 독립 구축했다. 아래는 실제 소스·설정·문서·테스트 파일 목록이다. 가상환경·캐시·빌드 사본과 대용량 데이터 개별 목록은 생략한다.

```text
.gitignore
.python-version
README.md
configs/environment_rules.toml
configs/facility_rules.toml
configs/fault_rules.toml
configs/occupancy_rules.toml
configs/room_profile_rules.toml
configs/simulation.toml
docs/architecture.md
docs/data_dictionary.md
docs/data_generation_models.md
docs/execution_guide.md
docs/final_report.md
docs/interface_contracts.md
docs/known_limitations.md
docs/simulation_assumptions.md
docs/testing_and_validation.md
pyproject.toml
scripts/check_reproducibility.py
scripts/inspect_dataset.py
scripts/smoke_test.py
src/aiot_sim/__init__.py
src/aiot_sim/__main__.py
src/aiot_sim/catalog.py
src/aiot_sim/cli.py
src/aiot_sim/clock.py
src/aiot_sim/config.py
src/aiot_sim/constants.py
src/aiot_sim/engines/__init__.py
src/aiot_sim/engines/controller.py
src/aiot_sim/engines/energy.py
src/aiot_sim/engines/environment.py
src/aiot_sim/engines/external_environment.py
src/aiot_sim/engines/faults.py
src/aiot_sim/engines/hvac.py
src/aiot_sim/engines/lighting.py
src/aiot_sim/engines/noise.py
src/aiot_sim/engines/occupancy.py
src/aiot_sim/engines/reservations.py
src/aiot_sim/engines/sensors.py
src/aiot_sim/engines/ventilation.py
src/aiot_sim/pipeline/__init__.py
src/aiot_sim/pipeline/aggregator.py
src/aiot_sim/pipeline/reporter.py
src/aiot_sim/pipeline/simulator.py
src/aiot_sim/pipeline/validator.py
src/aiot_sim/pipeline/writer.py
src/aiot_sim/profiles.py
src/aiot_sim/random_utils.py
src/aiot_sim/schemas.py
tests/conftest.py
tests/integration/test_control_feedback.py
tests/integration/test_full_room_catalog.py
tests/integration/test_reproducibility.py
tests/integration/test_single_room.py
tests/unit/test_aggregator.py
tests/unit/test_catalog.py
tests/unit/test_clock.py
tests/unit/test_energy.py
tests/unit/test_environment.py
tests/unit/test_faults.py
tests/unit/test_occupancy.py
tests/unit/test_profiles.py
tests/unit/test_reservations.py
tests/unit/test_sensors.py
verification-pytest.log
verification/pytest-results.xml
verification/ruff-results.txt
```

기준선 데이터 구조: `data/master/{rooms,room_profiles}.csv`, `data/runs/{smoke-single,smoke-all,repro-single,full-30d}/`. 각 실행은 `inputs`, `raw`, `events`, `derived`, `truth`, `reports`를 포함한다. 원본 배포본의 루트 `aiot_sim`은 `src/aiot_sim`에 대한 심볼릭 링크였으며 현재 Windows 정리본에서는 제거됐다. 현재 버전의 실행 데이터는 `data/runs/v02-full-30d/`이고, 최상위 `시뮬레이터실행.ps1`이 소스 경로를 지정한다.

## 2. Python 모듈 역할

`docs/architecture.md`에 29개 Python 패키지 모듈의 책임과 관계를 설명했다. CLI/설정/마스터/시계/난수, 개별 환경·점유·설비 엔진, 저장·집계·검증·보고 파이프라인으로 분리했다.

## 3. 생성 알고리즘

고정 프로필 → 공간별 독립 예약·점유 이벤트 → 캠퍼스 공통 합성 외기 → 상태 기반 열·습도·CO₂·조도·소음 → 센서 잡음/고장 → 관측 기반 제어 → 다음 구간 실제 환경 갱신 → 설비 전력 적산 → 일별 CSV → 5분 집계. 수식과 단위는 `docs/data_generation_models.md`에 기록했다.

## 4. 생성된 CSV 파일

full-30d에는 186개 CSV가 있다. 실제 186개 파일의 전체 경로는 `data/runs/full-30d/reports/summary.json`의 `csv_files`에 수록했다. 각 일별 파일은 2026-09-01부터 09-30까지 30개다. 마스터 원본 2개는 실행 외부에도 있다.

## 5. 실제 행 수·파일 크기

- `derived/energy_5min`: 30개 파일, 544,320행, 36,312,701 bytes.
- `derived/sensors_5min`: 30개 파일, 544,320행, 68,986,935 bytes.
- `events/control_actions.csv`: 1개 파일, 63,562행, 8,267,959 bytes.
- `events/occupancy_events.csv`: 1개 파일, 25,716행, 1,893,404 bytes.
- `events/reservations.csv`: 1개 파일, 9,803행, 1,273,695 bytes.
- `inputs/room_profiles.csv`: 1개 파일, 63행, 11,680 bytes.
- `inputs/rooms.csv`: 1개 파일, 63행, 13,738 bytes.
- `raw/energy_usage_1min`: 30개 파일, 2,721,600행, 243,245,439 bytes.
- `raw/facility_states_1min`: 30개 파일, 2,721,600행, 195,983,992 bytes.
- `raw/sensors_1min`: 30개 파일, 2,721,600행, 173,000,776 bytes.
- `truth/anomaly_events.csv`: 1개 파일, 2,149행, 284,847 bytes.
- `truth/environment_truth_1min`: 30개 파일, 2,721,600행, 332,019,726 bytes.

실행 CSV 합계: **1,061,294,892 bytes** (약 1.061 GB, 0.988 GiB). 헤더는 행 수에서 제외했다. 가상환경과 다른 smoke 실행은 이 합계에서 제외했다.

## 6. 실제 테스트

pytest 24개 통과, 실패 0 (11.00초). Ruff check·format check 통과. `verification/`와 `verification-pytest.log`가 실행 증거다. 개별 검사 범위는 `docs/testing_and_validation.md` 참조.

## 7. 1분·5분 검증

예상/실제 센서 행 수 2,721,600, 5분 행 수 544,320. 에너지 적산 합계 17,898.35764516599 kWh는 가상 설비 모델의 결과이며 실제 학교 소비량이 아니다. 최종 검증 결과 **오류 0건·경고 0건으로 통과**했다. 판정·상세 검사는 `data/runs/full-30d/reports/validation_report.json` 참조.

## 8. 재현성

동일 설정의 단일 공간 1일 데이터 2회 실행에서 12개 CSV 전체 SHA-256/바이트 일치. 별도 통합 테스트는 두 공간 처리 순서를 뒤집어도 동일함을 확인했다. 30일 전체를 두 번 생성하지는 않았다. 메타데이터·실행 폴더 이름은 비교 제외.

## 9. 실행 명령

프로젝트 폴더에서 다음을 실행한다.

```bash
source .venv/bin/activate
python -m aiot_sim report --run-id full-30d
python -m aiot_sim simulate --room-id STU-B102A --days 1 --run-id new-demo
python -m aiot_sim aggregate --run-id new-demo --minutes 5
python -m aiot_sim validate --run-id new-demo
python -m pytest -q
```

전체 CLI와 새 환경 설치는 `docs/execution_guide.md` 참조.

## 10. 남은 범위·한계

실제 ML 모델·챗봇·실제 하드웨어 연결은 이번 구현 범위 밖이다. 수치 실측 보정, 여러 센서 채널 고장, 동시 복합 고장, 변경 가능한 예약 이력, 재개 실행, 건물 간 열/공기 흐름은 후속 확장이다. 자세한 한계는 `docs/known_limitations.md`에 명시했다.

## 11. 팀 전달 파일과 인터페이스

`data/master`, 실행 `inputs/raw/events/derived/reports`, `docs`와 소스·configs·tests를 전달한다. `.venv`는 공유하지 말고 각자 설치한다. `truth`는 평가용으로 분리 전달한다. 공통 키는 room_id, 시계열 키는 timestamp+room_id. 누락은 빈 칸, 시간은 +09:00, 전력 kW와 에너지 kWh를 구분한다. ML JSON 규격·시나리오별 입력·시간 분할은 `docs/interface_contracts.md` 참조.

## 12. 다음 개발 단계 추천

시간 분할(21/4/5일)과 컬럼 규격을 먼저 고정하고 팀원별 기준모델을 구현한다. 미래 30분 라벨의 분할 경계 누출과 생성 전 미래 예약 접근을 방지한다. 실제 관측 데이터 확보 후 계수를 보정하고 별도 실측 테스트 세트에서 일반화 성능을 평가한다. 합성 데이터 성능을 높이기 위해 정답이 입력에 드러나게 만드는 작업은 피한다.
