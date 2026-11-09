# 설치·실행 가이드 (macOS / VS Code)

## 환경
확인한 Python: 3.14.7. 핵심 실행 의존성은 표준 라이브러리뿐이다. Python 3.11 이상이 필요하다. 개발 검증에는 pytest와 Ruff를 사용한다.

프로젝트 폴더를 VS Code에서 열고 터미널에서 실행한다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m aiot_sim init
```

이 작업에서는 가상환경과 개발 도구 설치를 실제 완료했다. 로컬 Python에서 editable 설치의 `.pth` 경로가 인식되지 않는 현상이 있어 프로젝트 루트에 `aiot_sim -> src/aiot_sim` 심볼릭 링크도 제공한다. 따라서 이 프로젝트 루트에서 실행하면 소스 코드를 직접 읽는다. 소스 구조는 `src/aiot_sim`이다. 다른 디렉터리에서 설치된 복사본으로 실행하는 경우 `--root /absolute/project/path`를 명령 앞에 지정한다.

## 명령
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
```bash
python -m pytest -q
ruff check src tests scripts
ruff format --check src tests scripts
python scripts/smoke_test.py new-smoke-id
python scripts/inspect_dataset.py --run-id full-30d
python scripts/check_reproducibility.py data/runs/smoke-single data/runs/repro-single --output data/runs/reproducibility.json
```

종료 코드 0은 명령 성공, validate의 1은 품질 검증 실패, 잘못된 입력·파일 오류의 2는 실행 오류다. 실행 중 날짜와 누적 센서 행 수를 출력한다. 시간이 오래 걸리면 manifest와 로그를 확인한다. `failed`나 `running` 실행을 정상 데이터셋으로 전달하지 않는다. 데이터가 크므로 전체 CSV를 Excel 한 시트에 합치지 말고 날짜별 파일을 확인한다.
