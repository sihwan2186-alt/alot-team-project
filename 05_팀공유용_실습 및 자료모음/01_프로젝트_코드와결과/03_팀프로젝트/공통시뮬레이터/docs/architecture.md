# 시스템 구조와 모듈 책임

> v0.2.0에서는 [모델 변경과 사용 안내](v0.2.0_release.md)가 우선합니다. 이 문서의 기존 실행 통계는 별도 표기가 없으면 v0.1.0 기준선입니다. 추가된 truth 파일·회복 레이블·검증 결과는 변경 안내와 deliverables/v0.2.0을 확인하세요.


## 목표와 경계
이 패키지는 네 건물 63개 공간의 합성 데이터 생성기다. 실제 하드웨어, 실시간 학교 예약 API, ML 학습 및 챗봇은 연결하지 않는다. 실제 호실 목록과 가상 시설 프로필을 서로 다른 CSV로 분리한다.

## 처리 순서
1. config가 TOML을 읽고 입력을 검증한다. catalog는 사용자 제공 63개 호실을 고정하며 profiles는 안정적인 시드로 가상 특성을 생성한다.
2. 각 날짜 시작에 공간별 예약 일정을 생성한다. 예약 생성 시각·취소·노쇼와 실제 인원을 구분한다.
3. 매분 현재 예약·이전 인원에 입퇴실을 적용한다. 같은 캠퍼스 시점의 외기 상태는 모든 공간이 공유한다.
4. 실제 환경의 현재 상태를 센서로 관측한다. 센서 잡음 및 센서 고장은 이 단계에만 적용한다.
5. 현재 설비의 구간 전력·에너지를 기록한다. 제어기는 관측값에서 명령을 결정한다. 현재 설비로 다음 환경 상태를 계산한 뒤 새 제어 상태는 다음 구간부터 사용한다.
6. 공간 상태를 유지하며 일별 파일에 즉시 기록한다. 원본과 truth는 별도 경로에 저장한다.
7. 일별 집계, 품질 검증, 실제 파일 수·크기 보고서를 생성한다.

## 모듈
- `__main__.py`, `cli.py`: 여덟 명령(init, generate-master, generate-profiles, simulate, aggregate, validate, report, label)의 진입점, 옵션과 오류 메시지.
- `config.py`, `constants.py`, `schemas.py`: 설정 검증, 공통 컬럼·출처, dataclass 기반 전달 모델. 파일 CSV 및 내부 실행 구성은 명시적 dictionary도 사용한다. dataclass는 외부 CSV를 자동 검증하는 스키마 라이브러리는 아니다.
- `catalog.py`, `profiles.py`: 실제 호실 마스터, 고정 가상 프로필 생성·읽기.
- `random_utils.py`, `clock.py`: SHA-256 파생 난수와 Asia/Seoul의 연속 시계.
- `engines/external_environment.py`: 합성 캠퍼스 외기와 주야 패턴.
- `engines/reservations.py`, `occupancy.py`: 비중복 일정과 이벤트 기반 인원 변화.
- `engines/environment.py`: CO₂ 질량수지, 열응답, 절대습도 및 상대습도 계산.
- `engines/hvac.py`, `ventilation.py`, `lighting.py`, `noise.py`: 설비별 환경 영향과 소음원 에너지 합성.
- `engines/thermal.py`: HVAC 전력·COP와 외피·환기·인원·조명·기타 발열을 연결한 v0.2.0 현열 수지.
- `engines/sensors.py`, `faults.py`: 측정 잡음·분해능, 센서 고장·설비 고장·고밀도 이용 주입.
- `engines/controller.py`, `energy.py`: 관측 기반 히스테리시스 제어와 전력 적산.
- `pipeline/simulator.py`: 상태·파일 수명 관리, 진행 로그, 실패 상태 처리.
- `pipeline/writer.py`: UTF-8 CSV와 원자적 JSON 교체.
- `pipeline/aggregator.py`: 일별 센서·에너지 집계.
- `pipeline/validator.py`: 공간·시간·인원·정답·결측 레이블·에너지 검사.
- `pipeline/labeler.py`, `physics_validator.py`: 원인·환경 이탈·회복 레이블 생성과 열수지·레이블 계약 검증.
- `pipeline/reporter.py`: 실제 파일별 행 수·크기 측정.

## 재현성과 저장
각 공간·모듈은 별도 `random.Random` 스트림을 쓴다. SHA-256(seed, room_id, module/date)로 파생하며 Python `hash()`와 현재 시각을 쓰지 않는다. 공간 순서는 정렬한다. 따라서 선택 공간의 순서와 다른 공간의 추가 여부가 해당 공간의 난수열을 변경하지 않는다. CSV 바이트 재현성은 동일 코드·설정·프로필·Python 환경에서 보장하며 다른 Python 버전의 장기 비트 단위 호환성은 보장하지 않는다.

manifest에는 전체 규칙, 시드, 대상 공간, 상태, 누적 행 수, 프로필 SHA-256을 기록한다. 입력 마스터 스냅샷을 실행 폴더에 복사한다. 실행 ID 재사용은 거부한다. 쓰기 중 오류·중단은 `failed`로 기록하며 강제 프로세스 종료로 finally를 실행할 수 없으면 `running`으로 남는다. 둘 다 검증에서 정상 완료로 처리하지 않는다. 재개 기능은 없다.

## 복잡도
R개 공간, D일에 대해 1분 내부 계산 시간은 O(R×D×1440)이다. 상태·현재 예약은 O(R), 날짜 시계·집계는 하루치 O(R×1440/step) 메모리를 사용한다. 검증기는 시계열 행을 스트리밍하며 입퇴실·이상 이벤트는 조회를 위해 메모리에 보유한다. 전체 기간의 센서 데이터를 한꺼번에 적재하지 않는다.
