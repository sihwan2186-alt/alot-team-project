# 팀원별 데이터 활용 가이드

대상: 소프트웨어 v0.1.0 / 공통 백서 v1.0 / 2026-11-03 추가 가이드.
문서 1.0은 문서의 배포 버전이고, 소프트웨어 0.1.0은 초기 구현의 패키지 버전이다. 문서 버전이 물리 모델의 실측 검증이나 상용 수준 완성을 뜻하지 않는다.

## 공통 로딩 계약

데이터셋은 `data/runs/full-30d/` 아래에 있다. 각 실행의 `inputs/rooms.csv`, `inputs/room_profiles.csv`는 당시 마스터 스냅샷이다. 현재 `data/master`가 변경되었을 가능성에 대비해 분석에서는 스냅샷을 우선한다. 마스터의 조인 키는 `room_id`, 시계열 간 조인 키는 `timestamp`와 `room_id`이다. 예약·입퇴실처럼 한 공간에 여러 이벤트가 있는 파일은 그대로 센서 테이블에 조인하지 말고 시점별 상태로 먼저 요약한다.

CSV는 UTF-8이고 boolean은 `true/false` 문자열이다. `bool('false')`는 Python에서 True이므로 `value.lower() == 'true'`로 파싱한다. 센서 빈 문자열은 None이며 0으로 치환하지 않는다. 시간은 시간대가 있는 datetime으로 읽는다. 사건 구간과 예약은 [시작, 종료)다.

## 시나리오 1 개인 학습 환경 추천 · 김시환

- 입력 파일: `derived/sensors_5min/sensor_readings_YYYY-MM-DD.csv`와 입력 마스터 두 파일.
- 사용할 컬럼: `room_id`, `timestamp`, `temperature_c_mean`, `humidity_pct_mean`, `co2_ppm_mean`, `illuminance_lux_mean`, `noise_leq_dba`, `occupancy_count_last`와 각 `*_missing_ratio`.
- 별도 수집할 입력: 사용자 선호, 추천 선택 또는 만족도. 현재 CSV에 선호 정답은 없다.
- 09:00 집계는 09:05부터 사용 가능하다. 잡음 dB의 산술평균을 새로 만들지 않는다.

## 시나리오 2 목적 기반 공간 추천 · 김정훈

실행 예제는 `examples/scenario2_room_candidates.py`이다. Python 표준 라이브러리만 사용하며 기존 데이터와 시뮬레이터를 수정하지 않는다.

```bash
source .venv/bin/activate
python examples/scenario2_room_candidates.py \
  --run-id full-30d \
  --as-of 2026-09-01T10:00:00+09:00 \
  --people 4 --duration-minutes 60 --require monitor \
  --output deliverables/data_review/scenario2_demo.json
```

실제 실행 결과: 공간 63개를 한 번씩 출력하고, 조건을 충족한 후보 6개를 찾았다. 후보는 LIB-B101F, LIB-B101J, STU-201H, STU-B125, WON-701A, WON-703이다. 이는 합성 데이터의 규칙 기반 후보이며 실제 학교 예약 가능 여부나 ML 추천 점수가 아니다.

### 입력과 결합 과정

1. `inputs/rooms.csv`에서 건물·호실, `inputs/room_profiles.csv`에서 `capacity`, `area_m2`, `room_type`, `has_*`, `opening_time`, `closing_time`을 읽는다.
2. 해당 날짜 `raw/sensors_1min/sensor_readings_YYYY-MM-DD.csv`에서 `timestamp <= as_of`인 가장 최근 공간별 관측을 선택한다. 미래 관측은 사용하지 않는다.
3. `events/reservations.csv`는 `created_at <= as_of`인 기록만 읽고 `status == confirmed`인 예약 중 요청 구간과 겹치는 공간 ID 집합을 만든다. 미래에 생성될 예약은 입력에 노출하지 않는다.
4. 요청 구간 `[as_of, as_of+duration)`과 예약 구간 `[start_time, end_time)`이 겹치는 조건은 `start_time < requested_end and end_time > as_of`이다. 11:00부터 시작하는 예약은 [10:00,11:00) 요청과 충돌하지 않는다.
5. 정원, 필수 설비, 전체 요청 구간 운영시간, 이미 알려진 예약 충돌, 현재 빈 공간 여부와 관측 신선도를 필터링한다. 기본 정책은 실제 관측 인원 0명인 공간만 후보로 삼는다. 정원에서 현재 인원을 빼서 자동 합석을 허용하는 정책은 사용하지 않는다.
6. 예약을 먼저 공간별 충돌 여부로 줄인 다음 마스터·관측과 결합하므로 예약 수만큼 센서 행이 불어나는 다대다 조인을 피한다.

`is_no_show`와 `truth`는 읽지 않는다. 노쇼가 나중에 확인될 예약도 현재 confirmed이고 당시 알려져 있었다면 해당 시간은 예약 충돌로 처리한다. `sensor_timestamp`가 현재보다 오래되면 기본 2분 이후 `stale_observation`으로 제외한다. 비기본 5분 출력에서는 그 간격과 서비스 신선도 정책에 맞춰 `--max-age-minutes`를 설정해야 한다.

### 결과 해석

JSON의 `rooms`는 실행 대상 공간별 한 행이다. `eligible`과 `exclusion_reasons`는 예제의 규칙 판정이며 학습 정답이 아니다. 환경 센서값은 별도 특징으로 제공하지만 임의의 가중합 점수는 만들지 않았다. 현재 데이터에는 '발표 준비에 좋은 공간' 같은 목적 적합성 정답이 없으므로 실제 이용자 평가·목적별 설비 조건·팀원의 목적 분류 기준을 추가해야 한다.

예약이 없고 현재 비어 있어도 요청 기간 중 walk-in 입실이나 이후 신규 예약을 막는 잠금 기능은 없다. 후보 생성 결과를 예약 확정으로 간주하면 안 된다.

### 구조와 비용

`candidates()`는 시간 검증, 최신 관측 선택, 당시 예약 충돌 집계, 공간별 후보 판정을 분리한다. 실행 함수는 CLI와 독립적으로 호출할 수 있다. 하루 센서 행 수 S, 전체 예약 수 B, 대상 공간 수 R일 때 시간 O(S+B+R log R), 메모리 O(R)이다. 대규모 운영에서는 날짜·room_id 인덱스가 있는 저장소로 대체하는 것이 좋다.

## 시나리오 3 혼잡도·시간 예측 · 최선강

- 입력: `raw/sensors_1min/` 또는 `derived/sensors_5min/`, `events/occupancy_events.csv`, `events/reservations.csv`, `inputs/rooms.csv`.
- 특징: 관측 `occupancy_count` 또는 `occupancy_count_last`, CO₂·소음의 과거 변화, 요일·시간대·건물. 예약은 당시 `created_at`으로 가시성을 제한한다.
- 미래 30분 인원 정답은 `room_id`별 정확한 미래 시각으로 연결한다. 정렬하지 않은 전체 테이블에서 단순 shift하면 다른 공간의 값이 연결될 수 있다.
- train 9월 1–21일, validation 22–25일, test 26–30일을 권장한다. 미래 정답 시각이 다음 분할로 넘어가는 표본은 제외한다. 이 가이드는 미래 정답 생성기나 예측 모델을 구현한 것은 아니다.

## 시나리오 4 시설 관리·이상 탐지 · 이민재

- 입력: `raw/sensors_1min/`, `raw/facility_states_1min/`, `raw/energy_usage_1min/`.
- 특징: 관측 환경·인원, HVAC/환기/조명 상태, 전력. `equipment_fault_active`는 주입 고장 여부를 드러내므로 고장 탐지 모델 특징에서 제외한다.
- 평가용 정답: `truth/anomaly_events.csv`의 [start_time,end_time), `anomaly_type`, `is_sensor_fault`; 필요할 때만 `truth/environment_truth_1min/`와 비교한다.
- **센서 고장 주입 채널은 현재 CO₂뿐이다.** 온도·습도 센서 이상 탐지 성능을 현재 데이터로 평가했다고 주장할 수 없다. 온도·습도에는 기본 측정 잡음만 존재한다.
- `bias`는 매분 +4ppm으로 증가하는 편차다. 고밀도는 정원 초과가 아닌 정원 100% 주입이며, 고장 구간 종료와 환경 회복 시점은 다를 수 있다.

## 시나리오 5 자동 환경 제어 · 김시환·김정훈

- 입력: `raw/sensors_1min/`의 관측과 현재 인원, `raw/facility_states_1min/`의 설비 상태.
- 명령: `events/control_actions.csv`의 `target_device`, `previous_state`, `requested_state`, `applied_successfully`.
- 평가는 명령행만 확인하지 말고 이후 센서·정답 변화와 실제 적용 시설 상태로 확인한다. t에서 결정한 요청은 다음 구간에 적용되고 환경 효과는 그 적분 뒤 관측된다.
- 외기는 별도 CSV가 없다. 같은 설정·시드·시각의 `external_environment.outdoor()`로 재계산할 수 있다.
- 현재 모델은 제어 반응 확인용이다. 실제 설비 응답·쾌적성·안전성의 실측 검증은 별도다.

## 시나리오 6 에너지 최적화 · 최선강·이민재

- 입력: `raw/energy_usage_1min/` 또는 `derived/energy_5min/`, 시설 상태, 점유·가상 프로필.
- 특징/목표: `total_power_kw`는 구간 평균 전력, `interval_energy_kwh`는 구간 에너지 합이다. 파생 파일에서는 `mean_power_kw`를 사용한다.
- 동일 구간의 에너지 컬럼과 그 구성전력을 함께 넣어 에너지를 예측하면 계산식을 그대로 학습하는 문제가 생길 수 있다. 예측 시점에 실제로 알 수 있는 입력만 선택한다.
- 현재 HVAC 전력은 온도 응답에 연동되지 않는다. 가상 정책의 소비전력 집계 예제와 실제 설비 효율 검증을 구분해야 한다.

## 실제 테스트와 오류 진단

```bash
python -m pytest tests/examples -q
```

현재 예제 테스트 7개 통과. 미래 관측 차단, 예약 생성 시각 필터, 전체 구간 겹침과 반개구간 경계, 노쇼 필드 미사용, 중복 행 방지, 정원·시설·운영시간·신선도·시간대 오류를 검사했다. 기존 백서의 pytest 24개 기록과 별개의 추가 예제 테스트다.

- `as_of is outside...`: 생성 기간 안의 시간대 포함 시각을 지정한다.
- `Run is not complete`: manifest를 확인하고 완료된 실행을 선택한다.
- 후보 0개: 오류라고 단정하지 말고 `exclusion_reasons`를 확인한다. 요구 시설·시간·정원이 실제로 동시에 충족되는지 확인한다.
- 빈 환경값: 0으로 대체하지 말고 모델별 대체·제외 정책을 train 구간에서 정한다.

백서 v1.0과 소프트웨어 v0.1.0은 이 후속 검토에서 수정하지 않았다.
