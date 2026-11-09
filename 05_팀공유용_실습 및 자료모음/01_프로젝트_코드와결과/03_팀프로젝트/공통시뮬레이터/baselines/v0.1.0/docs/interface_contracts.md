# 공통 데이터·모델 인터페이스

## 필수 참조 규칙
`room_id`는 대문자 건물 코드-호실이다. 공식 시설 코드가 아니다. 모든 CSV 조인은 `room_id` 또는 `(timestamp, room_id)`로 수행한다. 날짜는 ISO 8601 +09:00, 인원은 명, 온도 °C, 상대습도 %, CO₂ ppm, 조도 lux, 소음 dB(A), 전력 kW, 에너지 kWh다. 컬럼명을 팀원별로 바꾸지 않는다.

결측값은 CSV 빈 칸이다. 0은 유효한 측정값일 수 있으므로 일괄 결측 치환하지 않는다. boolean은 `true`/`false`. truth는 평가용이며 모델 입력에 자동 결합하지 않는다. `is_no_show`, future occupancy, fault type, 실제 환경 truth는 실시간으로 알 수 있는 특징이 아니다. 예약은 `created_at <= input_data_end_time`인 기록만 사용한다. 본 모델은 취소가 생성 시점에 확정되어 생성 시점 이후 상태가 바뀌는 취소 이력은 없다.

## 시나리오별 입력
1. 개인 추천(김시환): 관측 환경·인원·별도 수집 사용자 선호.
2. 목적 추천(김정훈): 관측 환경 + 프로필의 가상 정원·면적·시설·운영시간 + 현재 시점에 생성되어 있는 예약. 예약 여부와 실제 인원은 별도 판단한다.
3. 혼잡 예측(최선강): 과거 관측, 시간·건물, 당시 알려진 예약, 과거 입퇴실. 30분 미래 정답은 분할 안에서만 shift한다.
4. 이상 탐지(이민재): 관측·시설·에너지 입력. 이상 정답 및 실제 환경 truth는 평가 전용.
5. 자동 제어(김시환·김정훈): 분 단위 관측·점유·현재 시설·외기. 외기 값은 현재 엔진이 내부 계산하며 별도 CSV로 내보내지는 않는다. 동일 config·seed·timestamp로 `outdoor()`를 재계산할 수 있다.
6. 에너지(최선강·이민재): 에너지 및 시설 시계열·점유·가상 프로필.

## 시간 분할과 전처리
기본 30일: train 09-01–09-21, validation 09-22–09-25, test 09-26–09-30. 날짜 경계는 현지 자정이다. 미래 30분 정답이 다음 분할로 넘어가는 마지막 30분 표본은 제외한다. 5분 집계는 창 종료 후에 이용 가능하다. 예를 들어 09:00 창은 09:05 이전 예측에 사용하면 누출이다. 스케일러·대체값·특징 선택·임계값 학습은 train에서만 수행한다.

## 향후 모델 결과 JSON
공통 필수: `scenario_id`, `model_name`, `model_version`, `generated_at`, `room_id`, `input_data_end_time`. 시각은 시간대 포함 ISO 8601. 생성 시점 이전에 이용 가능한 입력만 사용한다.

시나리오별 선택: `prediction_target_time`, `predicted_label`, `score`, `confidence`, `reason_codes`. score와 confidence의 의미·범위·보정 방법은 각 모델 버전 명세에서 정의한다. 분류의 confidence를 추천 점수와 동일하게 해석하지 않는다. 회귀는 별도 `predicted_value`, `unit`을 명시하는 확장을 권장한다.

다음은 구조 예시일 뿐 실제 ML 추론 결과가 아니다.

```json
{
  "scenario_id": "3",
  "model_name": "future-model-placeholder",
  "model_version": "draft",
  "generated_at": "2026-09-26T10:00:00+09:00",
  "prediction_target_time": "2026-09-26T10:30:00+09:00",
  "room_id": "STU-B102A",
  "input_data_end_time": "2026-09-26T09:59:00+09:00",
  "reason_codes": []
}
```

## 팀 전달
전체 `data/master`, 실행의 `inputs`, `raw`, `events`, `derived`, `reports/manifest.json`, 검증 보고서 및 이 문서를 전달한다. `truth`는 평가 담당자에게 별도로 공유하고 일반 학습 입력 경로에서 제외한다. 원본을 개인별로 덮어쓰지 않고 새 파생 폴더를 사용한다. 합성 데이터 결과를 실측 학교 성능으로 발표하지 않는다.
