# Smart Campus AIoT — Shared Environmental Simulator

## 현재 Windows 작업 폴더에서 실행

이 프로젝트는 `03_팀프로젝트/공통시뮬레이터`로 정리했습니다. 최상위 작업 폴더의 `시뮬레이터실행.ps1 --help`를 사용하세요. 실행기는 루트 Windows .venv와 이 폴더의 src를 명시적으로 사용합니다. 압축에 포함된 macOS 가상환경과 Windows에서 텍스트로 풀린 심볼릭 링크는 삭제했습니다. 기존 검증·실행 통계는 제공 프로젝트의 원본 기록입니다.


선문대학교 사용자 제공 시설 목록(4개 건물·63개 호실)을 바탕으로 만든 재현 가능한 Python 합성 환경 시뮬레이터입니다. 기존 과제 파일은 수정하지 않았습니다. **정원·면적·설비·운영시간·환경 계수는 모두 가정값**이며 실제 학교 시설 사양이나 검증된 기상 자료가 아닙니다.

## 현재 버전

소프트웨어 **v0.2.0**은 HVAC 소비전력과 온도 반응을 현열 수지로 연결합니다. [v0.2 사용법과 검증](docs/v0.2.0_release.md)을 먼저 확인하세요. 아래 `full-30d` 통계는 보존된 **v0.1.0 기준선**입니다. 새 비교 실행은 `v02-full-30d`이며 원본을 덮어쓰지 않습니다.

## 바로 시작
최상위 작업 폴더에서 PowerShell로 실행합니다. 현재 루트 `.venv`는 Python 3.14.3이며, 원본 제공 자료의 Python 3.14.7 실행 기록과 구분합니다.

```powershell
.\시뮬레이터실행.ps1 --help
.\시뮬레이터실행.ps1 simulate --room-id STU-B102A --days 1 --run-id my-first-run
.\시뮬레이터실행.ps1 aggregate --run-id my-first-run --minutes 5
.\시뮬레이터실행.ps1 validate --run-id my-first-run
```

새 환경의 일반 설치 방법입니다. 이 절의 명령은 공통시뮬레이터 폴더에서 실행하며, Python 3.11 이상이 필요합니다. 실행 의존성은 표준 라이브러리뿐입니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m aiot_sim init
python -m pytest -q
```

현재 Windows 작업 폴더에는 `aiot_sim` 심볼릭 링크가 없습니다. 위 Windows 실행기 또는 새 환경의 패키지 설치로 모듈을 찾도록 합니다. 마스터는 존재하면 보존하며, 같은 실행 ID는 덮어쓰지 않습니다. 설정 변경 후에는 새 실행 ID를 사용하세요.

## 생성된 데이터
- `data/master/rooms.csv`: 정확히 63개 호실과 사용자 자료 출처·추정 층.
- `data/master/room_profiles.csv`: 고정 시드로 생성한 가상 시설 프로필.
- `data/runs/full-30d/raw/`: 30일 센서·실제 적용 설비·전력 데이터. 각각 2,721,600행.
- `data/runs/full-30d/derived/`: 5분 센서·에너지 집계. 각각 544,320행.
- `data/runs/full-30d/events/`: 예약 9,803건, 입퇴실 25,716건, 제어 요청 63,562건.
- `data/runs/full-30d/truth/`: 실제 내부 환경과 주입 이상 2,149건. **평가 전용으로 학습 입력과 분리하세요.**
- `data/runs/full-30d/reports/`: manifest, 집계 정보, 검증·파일별 요약.

기간은 2026-09-01 00:00부터 09-30 23:59까지이며 시각은 +09:00입니다. 전체 실행 CSV는 입력 스냅샷을 포함해 186개, 합계 1,061,294,892 bytes입니다. 원시 데이터는 날짜별 파일이므로 전체 기간을 한 번에 메모리에 적재할 필요가 없습니다.

## 기술 문서
- [설치·모든 CLI 명령](docs/execution_guide.md)
- [전체 구조·모듈 책임](docs/architecture.md)
- [모든 CSV 컬럼 사전](docs/data_dictionary.md)
- [실제 정보와 가정·변경 기록](docs/simulation_assumptions.md)
- [상태 기반 생성 수식](docs/data_generation_models.md)
- [팀 공통 인터페이스·시간 분할·모델 JSON](docs/interface_contracts.md)
- [테스트·검증 결과](docs/testing_and_validation.md)
- [한계와 후속 개발](docs/known_limitations.md)
- [실제 파일 기반 최종 보고](docs/final_report.md)

## 주의할 해석
합성 데이터의 예측·분류 성능은 실제 학교에서의 성능을 보장하지 않습니다. 실제 ML 모델·챗봇·실제 하드웨어 제어는 이번 범위에 포함하지 않았습니다. 고장 주입은 missing/spike/stuck/bias와 설비 고장, 정원 안의 고밀도 이용을 구분합니다. 센서 고장 주입 채널은 현재 CO₂입니다. 5분 집계는 창 종료 시점부터 이용 가능하며 미래 정보 누출을 막아야 합니다.
