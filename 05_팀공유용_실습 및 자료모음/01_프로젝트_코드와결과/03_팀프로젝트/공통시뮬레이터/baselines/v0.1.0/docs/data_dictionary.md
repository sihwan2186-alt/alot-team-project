# 데이터 사전

CSV는 UTF-8, 헤더 포함, boolean은 true/false, 센서 결측은 빈 칸이다. timestamp+room_id는 각 시계열 파일의 유일 키다. 프로필 값은 모두 가상이다. 원시 센서에 정답·이상 유형을 자동 결합하지 않는다.

## data/master/rooms.csv

- `room_id`: string; 프로젝트 내부 기본 키. 대문자 건물코드-호실. 결측 금지.
- `building_code`: enum; STU/LIB/WON/HEA. 결측 금지.
- `building_name`: string; 사용자 제공 건물명. 결측 금지.
- `room_number`: string; 원본 호실 표기. 결측 금지.
- `floor`: string; 호실에서 추정한 B1/2/4/6/7. 실제 확인값 아님.
- `floor_verified`: boolean; 현재 모두 false. 실제 층 독립 검증 여부.
- `source_type`: string; user_provided_facility_screenshots.
- `source_url`: URL string; 사용자 지정 시설 목록 출처.
- `source_checked_date`: date string; 자료 기준일 2026-11-02.
- `notes`: string; 추가 확인 사항. 빈 문자열 허용.

## data/master/room_profiles.csv

- `room_id`: string; 프로젝트 내부 기본 키. 대문자 건물코드-호실. 결측 금지.
- `room_type`: enum; SMALL/MEDIUM/LARGE. 합성 유형.
- `capacity`: integer, 명; 4/6/8/12/16/20, 양수. 실제 정원 아님.
- `area_m2`: float, ㎡; SMALL 12–18, MEDIUM 22–36, LARGE 42–60. 합성 면적.
- `ceiling_height_m`: float, m; 2.7–3.2. 합성 천장 높이.
- `volume_m3`: float, m³; area_m2×ceiling_height_m, 양수.
- `has_monitor`: boolean; 가상의 시설 보유 여부. 실제 학교 확인값 아님.
- `has_projector`: boolean; 가상의 시설 보유 여부. 실제 학교 확인값 아님.
- `has_whiteboard`: boolean; 가상의 시설 보유 여부. 실제 학교 확인값 아님.
- `has_outlets`: boolean; 가상의 시설 보유 여부. 실제 학교 확인값 아님.
- `opening_time`: HH:MM string; 기본 09:00, 당일 영업 시작 포함.
- `closing_time`: HH:MM string; 기본 21:00, 당일 영업 종료 제외.
- `ventilation_off_ach`: float, hour⁻¹; 정지 시 기본 공기교환율, 합성 양수.
- `ventilation_on_ach`: float, hour⁻¹; 환기 최대 가동 공기교환율, 합성 양수.
- `hvac_power_kw`: float, kW; 프로필에서는 정격/가정 소비전력, 원시 에너지에서는 해당 구간 평균 구성전력. 0 이상.
- `ventilation_power_kw`: float, kW; 프로필에서는 정격/가정 소비전력, 원시 에너지에서는 해당 구간 평균 구성전력. 0 이상.
- `lighting_power_kw`: float, kW; 프로필에서는 정격/가정 소비전력, 원시 에너지에서는 해당 구간 평균 구성전력. 0 이상.
- `standby_power_kw`: float, kW; 프로필에서는 정격/가정 소비전력, 원시 에너지에서는 해당 구간 평균 구성전력. 0 이상.
- `noise_baseline_dba`: float, dB(A); 공간 기본 소음 가정.
- `thermal_response_factor`: float, minute⁻¹; 외기와의 온도 차이에 곱하는 계수.
- `daylight_exposure_factor`: float, 0–1; 자연광 노출 가정 계수.
- `profile_source`: string; synthetic_assumption.
- `profile_version`: string; 초기 v0.1, 프로필 변경 시 버전 관리.

## data/runs/<run_id>/raw/sensors_1min/sensor_readings_2026-09-01.csv

- `timestamp`: ISO 8601 string; +09:00 포함. 원시값은 시점 상태, 에너지는 이 시점에서 시작하는 구간. 집계는 창 시작.
- `room_id`: string; 프로젝트 내부 기본 키. 대문자 건물코드-호실. 결측 금지.
- `temperature_c`: float, °C; 센서 관측 온도. 고장·잡음으로 정답과 다를 수 있음. 센서 CSV 빈 칸은 결측.
- `humidity_pct`: float, %; 관측 상대습도. 실제 상태 범위는 0–100, 센서 잡음은 범위 밖 가능. 센서 CSV 빈 칸은 결측.
- `co2_ppm`: float, ppm; 관측 CO₂. 고장 주입 대상이며 실제 환경 농도와 구분. 센서 CSV 빈 칸은 결측.
- `illuminance_lux`: float, lux; 관측 조도, 정상 0 이상. 센서 CSV 빈 칸은 결측.
- `noise_dba`: float, dB(A); 관측 소음. 로그 단위. 센서 CSV 빈 칸은 결측.
- `occupancy_count`: integer, 명; 관측 인원. 기본 정확한 인원 센서, 0–capacity. 센서 CSV 빈 칸은 결측.

## data/runs/<run_id>/raw/facility_states_1min/facility_states_2026-09-01.csv

- `timestamp`: ISO 8601 string; +09:00 포함. 원시값은 시점 상태, 에너지는 이 시점에서 시작하는 구간. 집계는 창 시작.
- `room_id`: string; 프로젝트 내부 기본 키. 대문자 건물코드-호실. 결측 금지.
- `hvac_mode`: enum; off/cooling/heating, 실제 적용 모드.
- `hvac_on`: boolean; 실제 적용 HVAC 가동 여부.
- `ventilation_on`: boolean; 실제 적용 환기 가동 여부.
- `ventilation_level`: float, 0–1; 실제 적용 환기 수준. 현재 정책 0 또는 1.
- `lighting_on`: boolean; 실제 적용 조명 가동 여부.
- `lighting_level`: float, 0–1; 실제 적용 조명 수준. 현재 정책 0 또는 1.
- `equipment_fault_active`: boolean; 설비 고장 주입 활성 여부. 센서 고장과 별개. 이상 탐지 사용 시 직접 정답 대용 특징으로 사용하지 않도록 주의.

## data/runs/<run_id>/raw/energy_usage_1min/energy_usage_2026-09-01.csv

- `timestamp`: ISO 8601 string; +09:00 포함. 원시값은 시점 상태, 에너지는 이 시점에서 시작하는 구간. 집계는 창 시작.
- `room_id`: string; 프로젝트 내부 기본 키. 대문자 건물코드-호실. 결측 금지.
- `hvac_power_kw`: float, kW; 프로필에서는 정격/가정 소비전력, 원시 에너지에서는 해당 구간 평균 구성전력. 0 이상.
- `ventilation_power_kw`: float, kW; 프로필에서는 정격/가정 소비전력, 원시 에너지에서는 해당 구간 평균 구성전력. 0 이상.
- `lighting_power_kw`: float, kW; 프로필에서는 정격/가정 소비전력, 원시 에너지에서는 해당 구간 평균 구성전력. 0 이상.
- `standby_power_kw`: float, kW; 프로필에서는 정격/가정 소비전력, 원시 에너지에서는 해당 구간 평균 구성전력. 0 이상.
- `total_power_kw`: float, kW; 구성전력 네 항목 합. 0 이상.
- `interval_energy_kwh`: float, kWh; 0 이상. 해당 출력/집계 구간의 소비 에너지 합.

## data/runs/<run_id>/truth/environment_truth_1min/environment_truth_2026-09-01.csv

- `timestamp`: ISO 8601 string; +09:00 포함. 원시값은 시점 상태, 에너지는 이 시점에서 시작하는 구간. 집계는 창 시작.
- `room_id`: string; 프로젝트 내부 기본 키. 대문자 건물코드-호실. 결측 금지.
- `true_temperature_c`: float, °C; 센서 정답 온도.  실제 내부 상태, 결측 없음. 평가 전용.
- `true_humidity_pct`: float, %; 정답 상대습도. 실제 상태 범위는 0–100, 센서 잡음은 범위 밖 가능. 실제 내부 상태, 결측 없음. 평가 전용.
- `true_co2_ppm`: float, ppm; 정답 CO₂.  실제 내부 상태, 결측 없음. 평가 전용.
- `true_illuminance_lux`: float, lux; 정답 조도, 정상 0 이상. 실제 내부 상태, 결측 없음. 평가 전용.
- `true_noise_dba`: float, dB(A); 정답 소음. 로그 단위. 실제 내부 상태, 결측 없음. 평가 전용.
- `true_occupancy_count`: integer, 명; 정답 인원. 기본 정확한 인원 센서, 0–capacity. 실제 내부 상태, 결측 없음. 평가 전용.

## data/runs/<run_id>/derived/sensors_5min/sensor_readings_2026-09-01.csv

- `timestamp`: ISO 8601 string; +09:00 포함. 원시값은 시점 상태, 에너지는 이 시점에서 시작하는 구간. 집계는 창 시작.
- `room_id`: string; 프로젝트 내부 기본 키. 대문자 건물코드-호실. 결측 금지.
- `sample_count`: integer; 집계 창 내 원시 행 수, 기본 5.
- `temperature_c_missing_ratio`: float, 0–1; 빈 측정값 수/원시 행 수.
- `temperature_c_mean`: float; temperature_c와 동일 단위. 결측 제외 산술평균. 유효 표본 없으면 빈 칸.
- `humidity_pct_missing_ratio`: float, 0–1; 빈 측정값 수/원시 행 수.
- `humidity_pct_mean`: float; humidity_pct와 동일 단위. 결측 제외 산술평균. 유효 표본 없으면 빈 칸.
- `co2_ppm_missing_ratio`: float, 0–1; 빈 측정값 수/원시 행 수.
- `co2_ppm_mean`: float; co2_ppm와 동일 단위. 결측 제외 산술평균. 유효 표본 없으면 빈 칸.
- `co2_ppm_max`: float/integer; co2_ppm와 동일 단위. 결측 제외 최댓값. 전부 결측이면 빈 칸.
- `co2_ppm_last`: float/integer; co2_ppm와 동일 단위. 창 마지막 시점의 관측값. 마지막 시점 결측이면 빈 칸.
- `illuminance_lux_missing_ratio`: float, 0–1; 빈 측정값 수/원시 행 수.
- `illuminance_lux_mean`: float; illuminance_lux와 동일 단위. 결측 제외 산술평균. 유효 표본 없으면 빈 칸.
- `noise_dba_missing_ratio`: float, 0–1; 빈 측정값 수/원시 행 수.
- `noise_leq_dba`: float, dB(A); 유효 소음 표본의 에너지 기반 등가 수준. 전부 결측이면 빈 칸.
- `occupancy_count_missing_ratio`: float, 0–1; 빈 측정값 수/원시 행 수.
- `occupancy_count_last`: float/integer; occupancy_count와 동일 단위. 창 마지막 시점의 관측값. 마지막 시점 결측이면 빈 칸.
- `occupancy_count_max`: float/integer; occupancy_count와 동일 단위. 결측 제외 최댓값. 전부 결측이면 빈 칸.

## data/runs/<run_id>/derived/energy_5min/energy_usage_2026-09-01.csv

- `timestamp`: ISO 8601 string; +09:00 포함. 원시값은 시점 상태, 에너지는 이 시점에서 시작하는 구간. 집계는 창 시작.
- `room_id`: string; 프로젝트 내부 기본 키. 대문자 건물코드-호실. 결측 금지.
- `mean_power_kw`: float, kW; 0 이상. 집계 구간 평균 소비전력.
- `interval_energy_kwh`: float, kWh; 0 이상. 해당 출력/집계 구간의 소비 에너지 합.

## data/runs/<run_id>/events/control_actions.csv

- `action_id`: string; 공간·분·설비별 제어 요청 식별자.
- `timestamp`: ISO 8601 string; +09:00 포함. 원시값은 시점 상태, 에너지는 이 시점에서 시작하는 구간. 집계는 창 시작.
- `room_id`: string; 프로젝트 내부 기본 키. 대문자 건물코드-호실. 결측 금지.
- `controller_type`: enum; 현재 rule_based.
- `target_device`: enum; hvac/ventilation/lighting.
- `previous_state`: string; 이전 요청 상태. HVAC 모드 또는 Python bool 문자열.
- `requested_state`: string; 새 요청 상태. HVAC 모드 또는 Python bool 문자열.
- `action_reason`: string; 현재 observation_target_and_occupancy. 관측·점유·유지시간에 근거한 규칙.
- `applied_successfully`: boolean; 고장으로 차단되지 않은 요청인지 여부. 실제 시설 CSV와 함께 확인.

## data/runs/<run_id>/events/occupancy_events.csv

- `event_id`: string; 공간·시간별 이벤트 식별자.
- `timestamp`: ISO 8601 string; +09:00 포함. 원시값은 시점 상태, 에너지는 이 시점에서 시작하는 구간. 집계는 창 시작.
- `room_id`: string; 프로젝트 내부 기본 키. 대문자 건물코드-호실. 결측 금지.
- `event_type`: enum; entry/exit.
- `count_delta`: integer, 명; 입실 양수, 퇴실 음수, 0 이벤트 없음.
- `resulting_occupancy`: integer, 명; 이벤트 적용 후 0–capacity.
- `reservation_id`: string; 예약 키. 비예약 입퇴실 이벤트에서는 빈 문자열.

## data/runs/<run_id>/events/reservations.csv

- `reservation_id`: string; 예약 키. 비예약 입퇴실 이벤트에서는 빈 문자열.
- `room_id`: string; 프로젝트 내부 기본 키. 대문자 건물코드-호실. 결측 금지.
- `created_at`: ISO 8601 string; 예약이 시스템에서 알려지는 시각. start_time 이전.
- `start_time`: ISO 8601 string; 예약/이상 구간의 시작 포함.
- `end_time`: ISO 8601 string; 예약/이상 구간의 종료 제외.
- `reserved_count`: integer, 명; 1–capacity. 실제 인원과 다름.
- `status`: enum; confirmed/cancelled. 생성 시 취소가 확정되며 이후 변경 이력 없음.
- `is_no_show`: boolean; 예약했으나 미방문한 합성 사후 특성. 실제 예측 입력에 사용 금지.

## data/runs/<run_id>/truth/anomaly_events.csv

- `event_id`: string; 공간·시간별 이벤트 식별자.
- `room_id`: string; 프로젝트 내부 기본 키. 대문자 건물코드-호실. 결측 금지.
- `start_time`: ISO 8601 string; 예약/이상 구간의 시작 포함.
- `end_time`: ISO 8601 string; 예약/이상 구간의 종료 제외.
- `anomaly_type`: enum; missing/spike/stuck/bias/ventilation_failure/hvac_failure/high_occupancy.
- `affected_variable`: enum; 현재 co2_ppm/ventilation/hvac/occupancy_count.
- `severity`: string; 설정된 가정 심각도, 현재 moderate. 물리적 위험도 검증값 아님.
- `cause`: string; 현재 synthetic_injection.
- `is_sensor_fault`: boolean; missing/spike/stuck/bias는 true, 나머지 false.

## JSON 보고서

- `manifest.json`: status(running/failed/complete), config(실행 TOML과 규칙), room_ids, sensor_rows, profile_sha256. inputs 폴더는 실행 당시 마스터 스냅샷.
- `aggregation.json`: minutes(집계 간격), rows(센서 집계 행 수).
- `validation_report.json`: valid, errors, warnings, sensor_rows, expected_sensor_rows, aggregate_rows, total_energy_kwh.
- `summary.json`: run_id, csv_files(path/bytes/rows), total_csv_bytes, validation.
- 재현성 JSON: identical, files_compared, 비교 경로, 파일별 SHA-256. 실행 폴더 이름과 메타데이터를 비교에서 제외한다.
