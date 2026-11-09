# 설치·실행 가이드

> v0.2.0에서는 [모델 변경과 사용 안내](v0.2.0_release.md)가 우선합니다. 이 문서의 기존 실행 통계는 별도 표기가 없으면 v0.1.0 기준선입니다. 추가된 truth 파일·회복 레이블·검증 결과는 변경 안내와 deliverables/v0.2.0을 확인하세요.


## 환경
현재 Windows 루트 `.venv`는 Python 3.14.3이다. 원본 제공 프로젝트의 Python 3.14.7 검증 기록은 당시 환경에 대한 기록이다. 핵심 실행 의존성은 표준 라이브러리뿐이다. Python 3.11 이상이 필요하다. 개발 검증에는 pytest와 Ruff를 사용한다.

현재 정리된 Windows 작업 폴더에서는 최상위 경로에서 다음을 실행한다. 실행기가 공통시뮬레이터의 `src`와 프로젝트 경로를 지정한다.

```powershell
.\시뮬레이터실행.ps1 --help
.\시뮬레이터실행.ps1 simulate --room-id STU-B102A --days 1 --run-id my-single
.\시뮬레이터실행.ps1 aggregate --run-id my-single --minutes 5
.\시뮬레이터실행.ps1 validate --run-id my-single
.\시뮬레이터실행.ps1 report --run-id my-single
```

다음은 별도 환경에서 공통시뮬레이터 폴더를 열어 새로 설치할 때의 예다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m aiot_sim init
```

현재 Windows 정리본에는 원본 macOS `.venv`와 `aiot_sim -> src/aiot_sim` 심볼릭 링크가 없다. 소스 구조는 `src/aiot_sim`이다. 패키지를 설치하지 않은 현재 환경에서는 Windows 실행기를 사용한다. 별도 환경에서 설치한 복사본으로 실행하는 경우 `--root /absolute/project/path`를 하위 명령 앞에 지정한다.

## 명령
아래 `python -m aiot_sim` 명령은 위와 같이 패키지를 설치한 환경 기준이다. 현재 Windows에서는 최상위 폴더에서 앞부분을 `.\시뮬레이터실행.ps1`로 바꿔 실행한다.
```bash
python -m aiot_sim generate-master
python -m aiot_sim generate-profiles
python -m aiot_sim simulate --room-id STU-B102A --days 1 --run-id my-single
python -m aiot_sim aggregate --run-id my-single --minutes 5
python -m aiot_sim validate --run-id my-single
python -m aiot_sim report --run-id my-single
python -m aiot_sim simulate --days 30 --run-id my-full-30d
python -m aiot_sim aggregate --run-id my-full-30d --minutes 5
python -m aiot_sim validate --run-id my-full-30d
python -m aiot_sim report --run-id my-full-30d
```

기존 실행 ID를 덮어쓰지 않는다. 제공된 `full-30d`, `smoke-single`, `smoke-all`을 다시 만들려면 새 ID를 사용한다. `--room-id`는 여러 번 지정할 수 있다. simulate는 `--start-date`, `--days`, `--seed`, `--step-minutes`로 TOML의 기본값을 덮어쓴다. 시간대는 이 프로젝트에서 Asia/Seoul로 제한한다. 출력 간격은 1440의 약수이며 5분 집계 간격은 출력 간격의 배수여야 한다.

규칙 수정은 `configs/*.toml`에서 수행한다. 기존 프로필은 자동 갱신하지 않으므로 프로필 규칙 변경 시 백업·버전 기록 후 명시적으로 재생성한다. 실제 실행의 규칙과 프로필은 manifest와 inputs 스냅샷으로 추적한다.

## 테스트·검사
현재 Windows에서는 최상위 작업 폴더에서 다음으로 전체 공통 테스트를 실행한다.

```powershell
.\.venv\Scripts\python.exe -m pytest .\03_팀프로젝트\공통시뮬레이터\tests -q
```

다음 명령은 공통시뮬레이터 폴더에서 개발 환경의 Python으로 실행한다. `scripts/smoke_test.py`와 `scripts/inspect_dataset.py`는 하위 프로세스에 이 폴더의 `src` 경로를 전달하므로 심볼릭 링크 없이 실행된다.
```bash
python -m pytest -q
ruff check src tests scripts
ruff format --check src tests scripts
python scripts/smoke_test.py new-smoke-id
python scripts/inspect_dataset.py --run-id full-30d
python scripts/check_reproducibility.py data/runs/smoke-single data/runs/repro-single --output data/runs/reproducibility.json
```

종료 코드 0은 명령 성공, validate의 1은 품질 검증 실패, 잘못된 입력·파일 오류의 2는 실행 오류다. 실행 중 날짜와 누적 센서 행 수를 출력한다. 시간이 오래 걸리면 manifest와 로그를 확인한다. `failed`나 `running` 실행을 정상 데이터셋으로 전달하지 않는다. 데이터가 크므로 전체 CSV를 Excel 한 시트에 합치지 말고 날짜별 파일을 확인한다.
