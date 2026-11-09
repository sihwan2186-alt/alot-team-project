# 테스트와 검증 증거

## 실제 실행 결과
최종 pytest 실행: **24 passed in 11.00s**, 실패 0. 로그는 `verification-pytest.log`, 기계 판독 결과는 `verification/pytest-results.xml`이다. Ruff check 및 format check도 통과했으며 `verification/ruff-results.txt`에 저장했다. Python 3.14.7에서 실행했다.

## 필수 요구사항별 검사
1. 63개 공간·건물 수·room_id 중복: test_catalog.
2. 프로필 누락·유형 수·면적·부피·예외값·기존 파일 보존: test_profiles.
3. 1분 연속 시계·종료시각·시간대·잘못된 설정: test_clock.
4. 예약 비중복·운영시간·생성 시각·인원·현재 시점 가시성: test_reservations.
5. 정원 제한·운영시간 외 0명·노쇼·취소: test_occupancy.
6. CO₂ 인원 발생·환기 반응·HVAC 온도 반응·조명 조도 반응·수증기/습도: test_environment.
7. missing/stuck/spike/bias 측정값과 실제 상태 분리: test_sensors.
8. 센서 이상과 설비 이상·고밀도 이상 유형 구분: test_faults.
9. kW 구성합과 kWh 적산: test_energy.
10. 5분 경계·에너지 기반 소음 Leq·결측 비율: test_aggregator.
11. 단일 공간 통합·5분 출력 샘플링·고의 센서값 훼손 탐지·실행 ID 충돌·불완전 manifest·쓰기 실패 상태: test_single_room.
12. 63개 전체 공간 1일 생성·집계·검증: test_full_room_catalog.
13. 두 공간 처리 순서를 바꾼 CSV 전체 바이트 비교: test_reproducibility.
14. 제어 유무의 실제 환경 차이·최소 유지시간·센서 결측 시 제어 유지: test_control_feedback.

여러 요구를 하나의 물리 반응 또는 통합 테스트에서 함께 검증한다. 테스트 함수 수와 요구사항 항목 수는 일대일 대응하지 않는다.

## 실제 CLI 실행
- smoke-single: 원시 센서 1,440행, 집계 288행, 검증 통과.
- smoke-all: 원시 센서 90,720행, 집계 18,144행, 검증 통과.
- full-30d: 원시 센서 2,721,600행, 집계 544,320행. 최종 검증 결과 오류 0건·경고 0건으로 통과했다. 자세한 판정은 실행 폴더 `reports/validation_report.json` 참조.
- repro-single: 동일 단일 공간 조건으로 재생성·집계·검증. smoke-single과 CSV 12개 SHA-256/바이트 동일. `data/runs/reproducibility.json`에 해시 기록.

재현성 실제 비교는 1개 공간 1일 및 통합 테스트의 2개 공간 1일에서 수행했다. 30일 전체를 두 번 생성하여 비교했다고 주장하지 않는다.

## 검증 규칙과 한계
검증기는 마스터 집합·공간 수·유형·양수 면적·부피, 연속 시간·중복·행 수·시간대, 입퇴실 누적·정원·운영시간, 물리 상태 범위, 센서 결측 레이블, 에너지 구성합·시간 적산·전체 집계 에너지 보존을 확인한다. 같은 입력 스냅샷을 사용하므로 추후 마스터 변경에 영향받지 않는다.

센서값과 truth의 편차를 측정잡음 8σ + 분해능 허용오차로 감사하며, 정상 잡음 허용폭 밖의 값은 고장 레이블을 요구한다. spike/bias 크기와 stuck 고정값도 해당 구간에서 검사한다. 이는 합성 생성기의 품질 감사이며 가우시안 분포의 무한 꼬리 때문에 정상 잡음의 극히 드문 오탐 가능성이 이론적으로 0인 것은 아니다. 센서 이상값을 무조건 물리 범위로 잘라내지 않는다.

2°C/출력 간격을 넘는 온도 변화는 경고다. 이 값도 공인 기준이 아닌 품질 점검용 가정이다. 정답·이상 이벤트를 모델 입력에 결합하는 실수는 데이터 로더/모델 개발 단계에서도 별도로 방지해야 한다.
