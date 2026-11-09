# ruff: noqa: F821
"""Build a complete updated white paper using verified v0.2 execution facts."""

from pathlib import Path

R = Path(__file__).resolve().parents[2]
original = (R / "tools/document_generation/build_white_paper.py").read_text()
prefix = original[: original.index("# 1 Cover.")]
prefix = prefix.replace("A=R/'deliverables/assets'", "A=R/'deliverables/v0.2.0/assets'")
prefix = prefix.replace(
    "F=json.loads((A/'verified_facts.json').read_text())",
    "A.mkdir(parents=True,exist_ok=True)",
)
prefix = prefix.replace("Version 1.0", "Version 1.1").replace(
    "props.version='1.0'", "props.version='1.1'"
)
# Reuse only the formatting helpers, never the historical body or its statistics.
exec(compile(prefix, str(R / "tools/document_generation/build_white_paper.py"), "exec"))
C = json.loads((R / "deliverables/v0.2.0/comparison.json").read_text())
V = json.loads(
    (R / "data/runs/v02-full-30d/reports/validation_report.json").read_text()
)
S = json.loads((R / "data/runs/v02-full-30d/reports/summary.json").read_text())
B, N = C["runs"]
P = V["physics_and_labels"]


def page_start(title):
    newpage()
    heading(title, toc=True)


def para(text):
    p(text)


def small(text):
    p(text, size=9, color="666666")


p("SMART CAMPUS AIoT", size=14, bold=True, color="FFFFFF", after=65)
p("Shared Environmental\nSimulator", "Title", color="FFFFFF", after=22)
p("Technology Overview", size=18, color="FFFFFF", after=205)
p("공통 환경 시뮬레이터 기술 백서", size=12, color="D0D0D0", after=16)
p(
    "Document Version 1.1\nSoftware Version 0.2.0\nNovember 2026",
    size=10,
    color="B0B0B0",
)

newpage()
p("Contents", "Title")
p("목차", size=11, color="777777", after=16)
TOC_PLACEHOLDER = DOC.add_paragraph("TOC_CACHE_PLACEHOLDER")
small("문서 v1.1  /  소프트웨어 v0.2.0  /  열 모델 one_zone_heat_balance_v0.2")

page_start("1  Introduction 소개")
para(
    "이 백서는 네 명의 팀원이 같은 공간 ID와 시계열 데이터로 환경 추천, 혼잡 예측, 이상 탐지와 에너지 분석을 개발할 수 있도록 시뮬레이터의 구조·물리 가정·CSV 계약·검증 결과를 설명한다. v0.2.0의 핵심 변경은 HVAC 전력과 실내 온도 반응을 하나의 현열 수지로 연결하고, 주입 고장과 환경 이상·회복을 구분하는 것이다."
)
para(
    "63개 공간의 30일 합성 데이터를 새 실행 ID v02-full-30d로 생성했다. 기존 v0.1.0 소스·설정과 full-30d 데이터, 문서 v1.0은 보존했다. 예약·이용 인원·주입 원인이 같은지 확인한 뒤 전후 결과를 비교했다."
)
heading("What the evidence establishes 검증 범위", 2)
para(
    "테스트와 전체 행 검증은 구현이 명시한 수식·단위·시간 계약을 지키는지 확인한다. 실제 캠퍼스의 온도·전력·사람 행동을 정확히 재현한다고 입증한 결과는 아니다. 정원·면적·설비 사양·열 계수는 가정이며 실측 보정은 아직 수행하지 않았다."
)
heading("Versions 버전의 구분", 2)
table(
    ["대상", "값", "의미"],
    [
        ["문서", "1.1", "본 백서의 개정판"],
        ["소프트웨어", "0.2.0", "열수지·레이블 구현 버전"],
        ["열 모델", "one_zone_heat_balance_v0.2", "단일 구획 현열 수지"],
        ["프로필", "기존 v0.1 표기 유지", "같은 공간 입력을 보존"],
        ["기준선", "v0.1.0 / full-30d", "비교용 기존 실행"],
    ],
    widths=[33, 60, 73],
    size=8.5,
)
source(
    "pyproject.toml · reports/manifest.json · baselines/v0.1.0/baseline_snapshot.json"
)

page_start("2  Key Features 주요 기능")
for title, text in [
    (
        "Fixed room catalog",
        "STU 38, LIB 12, WON 9, HEA 4로 총 63개 공간이다. SMALL 25, MEDIUM 28, LARGE 10 가상 프로필을 유지했다.",
    ),
    (
        "Coupled thermal model",
        "외피·환기·인원·기타 발열·HVAC 열량과 축열을 한 수지로 계산한다. 냉방·난방 열량은 같은 전기 입력과 COP로 결정한다.",
    ),
    (
        "Separate truth and observation",
        "실제 내부 상태와 센서 잡음·양자화·CO₂ 센서 고장 관측을 분리한다.",
    ),
    (
        "Fault and recovery labels",
        "주입 원인, 실제 임계 이탈, 고장 이후 회복 구간을 각각 기록한다. 회복은 시간적 연관이며 인과적 기여 추정은 아니다.",
    ),
    (
        "Minute trace and verification",
        "열수지를 내부 1분마다 저장하고 저장 열량 변화와 열유입 합을 비교한다.",
    ),
    (
        "Reproducible comparison",
        "공간·모듈별 파생 난수 스트림을 사용한다. 동일 조건의 두 실행을 CSV 단위로 비교하며 구버전도 보존한다.",
    ),
]:
    heading(title, 2)
    para(text)
source("src/aiot_sim · configs · deliverables/v0.2.0/comparison.json")

page_start("3  System Architecture 시스템 구조")
para(
    "pipeline/simulator.py가 시계와 공간 상태, 파일 수명을 관리한다. 물리 상태 X(t), 센서 관측 Y(t), 제어 요청, 고장을 적용한 설비 상태 F(t)를 나눈다. 상태 계산은 매분 수행하고 출력 간격만 별도로 설정한다."
)
# Original diagram remains valid at module responsibility level; explicitly add the new modules below.
oldA = A
A = R / "deliverables/assets"
image(
    "architecture",
    caption="Figure 1. 모듈 책임과 공통 데이터 흐름. 아래 표에 v0.2 추가 책임을 명시했다.",
)
A = oldA
table(
    ["모듈", "책임"],
    [
        ["engines/thermal.py", "해석적 현열 적분과 열량 기록"],
        ["engines/hvac.py", "전력과 부호 있는 냉난방 열률"],
        ["engines/energy.py", "동일 전력 함수로 에너지 계산"],
        ["pipeline/labeler.py", "원인·환경 이탈·회복 후처리"],
        ["pipeline/physics_validator.py", "열수지·COP·시간·레이블 검증"],
    ],
    widths=[65, 101],
    size=9,
)
para(
    "모든 시계열을 한 번에 적재하지 않는다. 상태는 공간별, 출력은 일별로 관리한다. 기본 시간 복잡도는 공간 수 R과 내부 분 수 M의 곱 O(RM)이다. 집계는 하루치, 이벤트 조회와 레이블 상태는 별도로 보유한다."
)

page_start("4  Simulation Workflow 실행 흐름")
para(
    "CLI는 TOML과 고정 마스터를 읽고, 새 실행 폴더에 입력 스냅샷을 복사한다. 각 날짜의 예약과 매분 인원·고장·관측·설비·환경을 처리한다. 같은 실행 ID는 덮어쓰지 않는다."
)
oldA = A
A = R / "deliverables/assets"
image("workflow", caption="Figure 2. 내부 계산은 항상 1분이며 출력 샘플링과 구분된다.")
A = oldA
heading("Time contract 시간 계약", 2)
para(
    "truth(t)는 직전 구간까지의 환경 누적 결과다. t에 기록한 실제 적용 설비와 열수지 행은 [t,t+1분)을 설명한다. t의 관측으로 결정한 새 제어 요청은 다음 구간에 적용된다. 따라서 고장 종료 시각에 설비가 복구되어도 그 시각의 온도는 여전히 높을 수 있다."
)
heading("Completion states 완료 상태", 2)
para(
    "manifest.complete는 원시 생성, labeling.complete는 레이블 후처리 완료다. aggregate와 validate는 별도 명령이다. 최종 사용 전 validation_report.valid와 physics_and_labels.valid를 모두 확인한다. 재개 기능은 없으며 실패한 실행은 새 ID로 다시 생성한다."
)
source("pipeline/simulator.py · pipeline/labeler.py · cli.py")

page_start("5  Room and Usage Models 공간과 이용 모델")
para(
    "호실 목록은 사용자 제공 시설 자료를 바탕으로 한다. 층 정보의 floor_verified는 false이며 실제 층을 확인한 값으로 취급하지 않는다. 프로필은 공간 ID를 키로 정원·면적·부피·자연광·환기량·설비 전력 등을 저장한다. STU-B102A의 정원 6명·면적 17m²도 가상 설정이다."
)
heading("Reservations and occupancy 예약과 인원", 2)
para(
    "평일·주말·시간대 수요와 30/60/90/120분 이용 길이를 조합해 운영시간 안의 겹치지 않는 예약을 생성한다. 취소·노쇼는 실제 점유를 만들지 않는다. 도착 지연과 일부 인원 불참, 빈 시간 walk-in을 반영한다. 인원은 정원 안으로 제한하고 실제 변동량을 입퇴실 이벤트에 기록한다."
)
heading("Reproducible inputs 비교 조건", 2)
para(
    "날짜·공간·모듈별 파생 시드가 난수를 분리한다. 열 모델 변경이 예약·점유 난수를 소모하는 순서를 바꾸지 않도록 했다. 30일 비교에서는 rooms, room_profiles, reservations, occupancy_events, anomaly_events의 파일 해시가 모두 같고 전체 truth의 시간·공간·인원도 일치했다."
)
heading("Outdoor state 외기", 2)
para(
    "외기는 일별 난수 편차와 일주기 사인파로 생성한다. 모든 공간이 같은 시각의 외기에 노출된다. 실제 2026년 9월 날씨가 아니며 방위별 일사·그늘·창문 개폐·복도 이동을 개별 모델링하지 않는다. v0.2 열수지에 외기 온도를 저장해 계산 입력을 추적한다."
)
source(
    "catalog.py · profiles.py · engines/reservations.py · engines/occupancy.py · engines/external_environment.py"
)

page_start("6  Thermal Balance 현열 수지")
para(
    "기존 모델은 냉난방의 분당 온도 효과와 소비전력을 따로 정했다. v0.2는 전력 변화가 열 공급에 직접 반영되도록 같은 전기 입력을 공유한다. 외피·환기 열교환과 사람·조명·기타 발열은 실내 현열 수지에 합산한다."
)
eq(
    "C_{eff} dT/ds = (UA_{env} + UA_{vent})(T_{out} − T) + Q_{people} + Q_{other} + Q_{HVAC}"
)
eq("Q_{HVAC} = −COP_{cool} P_{electric}  (cooling)")
eq("Q_{HVAC} = +COP_{heat} P_{electric}  (heating)")
table(
    ["항", "단위", "구현"],
    [
        ["C_eff", "kJ/K", "면적×유효 축열 계수 + 공기 열용량"],
        ["UA_env", "kW/K", "바닥 면적×종합 UA / 1000"],
        ["UA_vent", "kW/K", "공기 열용량×ACH / 3600"],
        ["Q_people", "kW", "인원×75 / 1000"],
        ["Q_other", "kW", "면적×2/1000 + 조명 + 대기 발열"],
        ["P_electric", "kW", "정격×부하율 0.8; off/고장은 0"],
    ],
    widths=[32, 25, 109],
    size=9,
)
para(
    "종합 UA의 면적은 바닥 면적이다. 개별 외벽의 열관류율 U를 측정한 값이 아니다. 유효 축열 계수는 벽·가구 등을 한 상태에 묶은 근사이며 공기 열용량은 별도로 더한다. 설비 고장을 적용한 실제 상태로 전력과 열량을 모두 계산한다."
)
source(
    "engines/thermal.py · engines/hvac.py · configs/environment_rules.toml [thermal]"
)

page_start("7  Integration and Coefficients 적분과 가정")
para(
    "1분 구간 안에서 외기·인원·적용 설비를 일정하다고 가정한다. UA가 양수이면 평형 온도와 지수 응답으로 정확히 적분하고, UA가 0이면 선형 해를 사용한다. 이 정확성은 구간 상수 입력 가정 아래의 수학적 정확성이다."
)
eq("T_{eq} = T_{out} + Q_{fixed}/UA")
eq("T_{end} = T_{eq} + (T_{start} − T_{eq}) exp(−UA Δs/C_{eff})")
eq("ΔE_{stored} = C_{eff}(T_{end} − T_{start})/3600")
para(
    "외피·환기 열교환은 해석적 구간 평균 온도로 적분한다. 잔차는 축열 변화에서 외피·환기·인원·기타·HVAC 열량 합을 뺀 값이다. kW×시간을 kWh로 변환하며 냉방은 음수다. 온도를 정상 범위로 강제 제한하지 않는다."
)
table(
    ["계수", "기본값", "선택의 성격"],
    [
        ["공기 제외 유효 축열", "120 kJ/(m²·K)", "초기 설계 가정"],
        ["바닥 면적당 종합 UA", "3 W/(m²·K)", "초기 설계 가정"],
        ["인체 현열", "75 W/인", "활동 차이 없는 고정 가정"],
        ["냉방 / 난방 COP", "3.2 / 3.0", "상수 성능 가정"],
        ["공기 밀도 / 비열", "1.2 / 1.006", "kg/m³ / kJ/(kg·K)"],
        ["기타 발열", "2 W/m²", "상시 기저 발열 가정"],
        ["조명 / 대기 발열 비율", "1.0 / 1.0", "전력 전량 실내 현열 가정"],
    ],
    widths=[59, 51, 56],
    size=8.5,
)
small(
    "계수는 학교 실측·장비 인증값이 아니다. 실제 건물 정확도를 주장하지 않는다. 잠열·일사·부분부하·다중 열노드는 범위 밖이다."
)

page_start("8  Other Environmental Models 다른 환경 변수")
heading("Carbon dioxide CO₂", 2)
para(
    "실내 완전 혼합 단일 구획을 가정한다. C는 ppm, V는 m³, G는 m³/(인·시간), a는 ACH다. 환기 수준에 따라 off/on ACH를 보간하고, 인원이 CO₂를 발생시킨다. 상수 구간 해석해와 expm1을 사용한다."
)
eq("dC/dh = nG 10^{6}/V + a(C_{out} − C)")
para(
    "G=0.018 m³/(인·시간)은 0.005 L/(인·초)와 같다. NIST 문헌의 활동·체격에 따른 발생량 논의와 양립하는 규모지만 모든 캠퍼스 이용자에 맞게 보정된 값은 아니다. CO₂ 모델과 환기 제어의 설정은 비교 실행에서 유지했다."
)
heading("Humidity 습도", 2)
para(
    "절대 수증기 밀도를 상태로 저장하고 외기 혼합·인원 수분 발생·냉방 제습 인자를 반영한다. 온도로 포화 밀도를 구한 뒤 상대습도로 변환한다. 포화 초과 수분은 응축으로 제거한다. 습도는 새 온도 궤적에 따라 바뀐다. 제습·응축 잠열을 현열 수지와 연결하지 않았으므로 열수지 통과를 총 에너지 검증으로 해석하면 안 된다."
)
heading("Light and noise 조도와 소음", 2)
para(
    "자연광 인자×공간 노출과 조명 수준으로 조도를 계산한다. 소음은 배경·인원 활동·설비를 독립 소음원으로 근사해 에너지를 더한다. dBA를 단순 산술 합산하지 않는다."
)
eq("L_{total} = 10 log_{10}(Σ 10^{L/10})")
source(
    "engines/environment.py · ventilation.py · lighting.py · NIST Persily and de Jonge 2017"
)

page_start("9  Sensors and Injected Faults 센서와 주입 원인")
para(
    "센서는 truth에 채널별 정규 잡음을 더하고 분해능으로 양자화한다. 관측 고장과 실제 물리 고장을 구분해야 이상 탐지 대상이 명확해진다. 한 공간에 동시에 하나의 주입 원인이 활성화된다."
)
table(
    ["분류", "유형", "영향"],
    [
        ["sensor", "missing / spike / stuck / bias", "현재 CO₂ 관측 채널만 변경"],
        ["equipment", "hvac_failure", "실제 HVAC 중단"],
        ["equipment", "ventilation_failure", "실제 환기 중단"],
        ["occupancy", "high_occupancy", "정원 안의 고밀도 이용"],
    ],
    widths=[31, 70, 65],
    size=9,
)
para(
    "온도·습도 센서 고장은 구현되어 있지 않다. CO₂ 센서 고장은 실제 CO₂를 바꾸지 않지만 왜곡된 관측으로 환기 제어에 간접 영향을 줄 수 있다. 설비 고장은 실제 적용 설비와 환경을 바꾼다."
)
heading("Original and normalized events 원본과 정규화 사건", 2)
para(
    "truth/anomaly_events.csv는 기존 주입 원인 계약과 내용 그대로 보존했다. fault_events.csv는 같은 원인에 fault_category를 추가한다. 원인 기간은 [start_time,end_time)이다. 이 기간이 실제 임계 이탈 기간이나 회복 기간과 같다는 뜻은 아니다."
)
para(
    "30일 주입 원인은 기존과 같은 2,149건이다. 새 레이블은 주입 횟수를 증가시킨 것이 아니라 상태의 의미를 나눈 것이다. 환경 이상은 주입 원인 없이도 발생할 수 있고 고장이 있어도 환경은 정상 범위일 수 있다."
)
source(
    "engines/faults.py · pipeline/labeler.py · truth/anomaly_events.csv · fault_events.csv"
)

page_start("10  Anomaly and Recovery 환경 이상과 회복")
para(
    "환경 이상은 truth의 설정 범위 이탈이다. 온도 18–28°C, 상대습도 20–80%, CO₂ 350–1000 ppm을 포함 범위로 두고 경계 바깥을 true로 기록한다. 24시간 모두 적용하며 운영·건강·법적 기준으로 인증된 경계가 아니다. 조도·소음은 아직 이 레이블에 포함하지 않는다."
)
heading("Recovery definition 회복 정의", 2)
para(
    "설비 또는 고밀도 원인이 끝난 직후 첫 관측에서 관련 변수가 범위 밖이면 회복 추적을 시작한다. HVAC는 온도, 환기·고밀도는 온도·습도·CO₂가 관련 변수다. 센서 고장만으로 물리 회복을 만들지 않는다. 범위 안에 처음 들어온 뒤 정상 관측이 5분 경과할 때까지 이어지면 recovered로 닫는다. 중간 이탈은 안정 시간 측정을 다시 시작한다."
)
table(
    ["status", "해석"],
    [
        ["recovered", "설정한 정상 안정 확인을 완료"],
        ["interrupted_by_fault", "새 관련 원인이 발생해 추적 중단"],
        ["right_censored", "실행 종료까지 회복 완료 여부를 알 수 없음"],
    ],
    widths=[59, 107],
    size=9,
)
para(
    "회복 구간은 정상 범위 진입 뒤의 안정 확인 시간도 포함한다. 정상 범위에 들어온 즉시 환경 이상은 false가 되지만 recovery_active는 잠시 true일 수 있다. 출력 간격이 5분이면 표본 사이 연속 상태까지 확인한 것은 아니다. 회복 사건은 고장과의 시간적 연관이며 인과적 기여를 증명하지 않는다."
)
para(
    f"이번 실행의 변수별 회복 사건은 {sum(C['recovery_status_counts'].values()):,}건이며 상태별 집계는 {', '.join(f'{k} {v:,}건' for k, v in C['recovery_status_counts'].items())}이다. 변수별 사건 수와 공간·분 플래그 수를 혼동하면 안 된다."
)
para(
    "이번 실행의 회복 사건은 모두 CO₂에 관한 것이다. 완료 124건의 회복 시간은 안정 확인을 포함해 중앙값 21.5분, 범위 6–373분이다. 온도 범위 이탈과 온도 회복 사건은 0건이므로 온도 이상 학습용 양성 사례는 별도 설계가 필요하다."
)
source(
    "configs/anomaly_label_rules.toml · truth/recovery_events.csv · environment_status_1min"
)

page_start("11  Control and Energy 제어와 에너지")
para(
    "규칙 제어는 관측 온도·CO₂와 현재 점유를 읽는다. ON/OFF 경계 차이인 히스테리시스와 최소 상태 유지 시간을 사용해 잦은 전환을 억제한다. 빈 공간은 설비 정지를 요청하고 결측 채널은 해당 판단을 유지한다. 고장이 요청을 가릴 수 있으므로 control_actions와 실제 facility_states를 나누어 읽는다."
)
eq("P_{total} = P_{HVAC} + P_{ventilation} + P_{lighting} + P_{standby}")
eq("E_{interval} = Σ P_{minute}/60")
para(
    "HVAC 전력은 정격×0.8이며 냉난방 열률과 같은 함수로 계산한다. 환기·조명은 정격×수준, 대기는 고정값이다. 5분 출력에서는 내부 5개 구간의 에너지를 합하고 전력은 평균한다. 5분 집계에서 에너지는 다시 합, 전력은 평균을 사용한다."
)
para(
    f"기준선 총 전력량은 {B['total_energy_kwh']:,.3f} kWh, 새 실행은 {N['total_energy_kwh']:,.3f} kWh다. 이 차이는 새 열응답에 따른 제어 작동 변화까지 포함한다. 실제 시설에서 절약한 에너지나 효율 개선율을 뜻하지 않는다."
)
heading("Accounting scope 계산 범위", 2)
para(
    "COP는 외기·부분부하에 따라 변하지 않는 가정이다. 환기 팬 전력의 실내 발열은 별도 항으로 넣지 않았다. 제습 잠열·실외기 열방출·실제 전기요금도 범위 밖이다. enable_energy_model=false는 에너지 CSV를 0으로 만드는 진단 옵션이며 설비 물리를 끄지 않는다. 에너지 비교 데이터는 true로 생성해야 한다."
)
source(
    "engines/controller.py · engines/energy.py · engines/hvac.py · configs/facility_rules.toml"
)

page_start("12  Data Interfaces 데이터 인터페이스")
para(
    "room_id는 rooms·room_profiles·예약·시계열의 공통 키다. 시계열은 timestamp와 room_id를 함께 사용하고 +09:00 시간대와 정렬을 유지한다. 모든 시계열을 날짜별 CSV로 저장한다. 기존 컬럼 계약은 유지하고 v0.2 truth 파일만 추가했다."
)
table(
    ["파일 계열", "주요 역할"],
    [
        ["inputs/rooms.csv", "실행에 사용한 공간 목록"],
        ["inputs/room_profiles.csv", "정원·면적·부피·설비 입력 스냅샷"],
        ["events/reservations.csv", "예약·생성 시각·예약 인원·상태"],
        ["events/occupancy_events.csv", "실제 입퇴실 변화"],
        ["events/control_actions.csv", "다음 구간 설비 변경 요청"],
        ["raw/sensors_1min", "잡음·결측·고장이 포함된 관측"],
        ["raw/facility_states_1min", "고장 적용 이후 실제 설비"],
        ["raw/energy_usage_1min", "성분별 kW와 구간 kWh"],
        ["truth/environment_truth_1min", "평가용 내부 환경과 실제 인원"],
        ["derived/*_5min", "센서와 에너지의 5분 집계"],
    ],
    widths=[74, 92],
    size=9,
)
heading("Aggregation 집계 계약", 2)
para(
    "기본 [09:00,09:05) 창은 09:00–09:04 표본이다. 평균은 유효 관측만 사용하고 전부 결측이면 빈 값이다. CO₂ 최대·마지막값, 마지막·최대 인원, 결측률과 표본 수를 함께 기록한다. 소음 Leq는 10log10(mean(10^(L/10)))으로 계산한다. 창 종료 전에는 완성 집계를 입력으로 사용할 수 없다."
)
small(
    "기존 경로의 _1min·_5min 이름은 비기본 간격에서도 유지된다. 반드시 manifest와 aggregation.json의 실제 간격을 읽는다."
)

page_start("13  Added Truth Files 추가 정답 파일")
table(
    ["파일", "핵심 필드와 의미"],
    [
        [
            "thermal_balance_1min",
            "timestamp, room_id, start/end/mean 온도, C, UA, 외기, 열률·열량, COP, 전력, 잔차",
        ],
        ["fault_events.csv", "원본 원인 필드 + fault_category"],
        [
            "environment_status_1min",
            "원인 분류 플래그, 변수별 이탈, 환경 OR, 회복 플래그·변수",
        ],
        [
            "environment_anomaly_events.csv",
            "변수별 연속 이탈 시작·종료, min/max, 경계, 상태",
        ],
        [
            "recovery_events.csv",
            "cause_event_id, 변수, 고장·회복 시각, duration_minutes, status",
        ],
    ],
    widths=[64, 102],
    size=8.8,
)
para(
    "열수지 행 t는 [t,t+1분)의 입력과 적분을 설명한다. 모든 출력 간격에서 열수지는 내부 1분마다 기록한다. 나머지 상태 truth는 설정 출력 간격이다. 열률은 kW, 열량은 kWh, 열용량은 kJ/K, UA는 kW/K다. 부호는 실내 열유입 양수다."
)
para(
    "environment_status의 fault_active는 원인이 활성인지, environment_anomaly_active는 하나 이상의 변수가 설정 범위 밖인지, recovery_active는 회복 추적 중인지를 뜻한다. 서로 독립적으로 평가해야 한다. recovery_variables는 여러 변수를 구분자로 연결한다."
)
heading("Evaluation only 평가 전용", 2)
para(
    "모든 truth와 회복 종료 시각은 내부 상태나 미래 결과를 포함한다. 운영 입력으로 자동 결합하지 않는다. 센서 이상 탐지는 sensor_fault_active, 설비 원인 탐지는 equipment_fault_active, 환경 범위 이탈 탐지는 환경 플래그처럼 목표를 먼저 고정해야 한다."
)
source(
    "정확한 전체 컬럼: docs/data_dictionary.md · docs/v0.2.0_release.md · 각 CSV 첫 행"
)

page_start("14  Team Usage 팀원별 활용")
for title, text in [
    (
        "학습 환경 점수화",
        "sensor 또는 완료된 5분 집계의 온습도·CO₂·조도·소음을 사용한다. 점수 가중치와 목표 범위는 별도 설계 가정이다.",
    ),
    (
        "목적 기반 공간 추천",
        "rooms와 room_profiles를 room_id로 결합하고 기준 시각 이전 최신 관측과 이미 생성된 예약만 읽는다. 정원·장비·운영시간·현재 빈 공간·전체 이용 시간 예약 충돌을 확인한다.",
    ),
    (
        "혼잡도 예측",
        "과거 인원·요일·시간대와 시점에 알려진 예약 인원을 사용한다. 미래 실제 인원·노쇼 여부를 특성에 넣지 않는다.",
    ),
    (
        "이상 탐지",
        "CO₂ 센서 고장과 설비 고장, 실제 환경 이상을 별도 목표로 평가한다. 회복 구간이 있는 평가와 없는 평가를 구분하고 학습 가능한 고장 채널의 범위를 명시한다.",
    ),
    (
        "에너지 분석과 제어 비교",
        "energy_usage와 실제 facility_states를 시간·공간 키로 연결한다. 같은 예약·인원·고장·외기 조건을 고정하고 쾌적 범위와 kWh를 함께 비교한다.",
    ),
    (
        "통합 안내와 설명",
        "추천·예측·이상 결과를 공통 room_id와 기준 시각으로 묶는다. 합성 데이터와 가정 계수라는 사실을 사용자에게 설명한다.",
    ),
]:
    heading(title, 2)
    para(text)
small(
    "실행 예제: examples/scenario2_room_candidates.py · 상세 가이드: docs/team_data_usage.md"
)

page_start("15  Validation 검증 결과")
para(
    "소프트웨어 테스트 46개가 통과했다. 전력 증가에 따른 냉난방 방향과 크기, COP·열용량 효과, 고장 중 전력·열량 0, 해석적 분할 적분과 열수지, 회복 상태 전이, 재현성을 포함한다. 열량과 고장 플래그를 의도적으로 훼손하면 검증이 실패하는지도 확인했다."
)
table(
    ["전체 30일 실행 검증", "결과"],
    [
        ["센서 행", f"{V['sensor_rows']:,}"],
        ["5분 센서 집계 행", f"{V['aggregate_rows']:,}"],
        ["내부 1분 열수지 행", f"{P['thermal_rows']:,}"],
        ["환경 상태 레이블 행", f"{P['label_rows']:,}"],
        ["최대 현열 수지 잔차", f"{P['max_thermal_balance_residual_kwh']:.3e} kWh"],
        ["검증 오류 / 경고", f"{len(V['errors'])} / {len(V['warnings'])}"],
        ["CSV 개수 / 바이트", f"{len(S['csv_files']):,} / {S['total_csv_bytes']:,}"],
    ],
    widths=[89, 77],
    size=9,
)
para(
    "전체 행에서 열용량·해석적 온도 응답·축열·열유입·COP 연계·전력 CSV 연계·분 연속성·truth 정렬과 환경 범위 플래그·원인 분류·회복 사건 구간을 대조했다. 잔차의 작은 값은 동일 현열 수식의 계산 일관성을 뜻하며 누락된 물리 과정의 정확성을 뜻하지 않는다."
)
para(
    "재현성은 현재 실행 환경의 같은 공간·하루 CSV 17개 전부 일치와, 테스트의 두 공간 순서 반전 비교로 확인했다. 전체 30일을 두 번 생성한 검증은 아니다. 다른 플랫폼의 부동소수점 문자열까지 같은지는 검증하지 않았다."
)
source(
    "deliverables/v0.2.0/tests.log · replay_verification.json · reports/validation_report.json"
)

page_start("16  Baseline Comparison 기준선 비교")
para(
    "2026년 9월 1–30일, 시드 20261102, 동일 63개 공간·예약·인원·주입 원인으로 비교했다. 전체 2,721,600개 truth 행의 timestamp·room_id·인원 불일치는 0이다. 기준선 소스 84개와 데이터·보고서 190개, 원본 백서의 보존 해시를 확인했다."
)
rr = []
for label, key in [("온도 최소", "min"), ("온도 평균", "mean"), ("온도 최대", "max")]:
    rr.append(
        [
            label,
            f"{B['statistics']['temperature_c'][key]:.3f}°C",
            f"{N['statistics']['temperature_c'][key]:.3f}°C",
        ]
    )
for item in C["runs"]:
    item["comfort_pct"] = (
        100 * item["counts"]["occupied_outside_20_26"] / item["counts"]["occupied_rows"]
    )
rr += [
    ["점유 중 20–26°C 이탈", f"{B['comfort_pct']:.2f}%", f"{N['comfort_pct']:.2f}%"],
    [
        "총 전력량",
        f"{B['total_energy_kwh']:,.3f} kWh",
        f"{N['total_energy_kwh']:,.3f} kWh",
    ],
]
table(["지표", "v0.1.0", "v0.2.0"], rr, widths=[65, 50, 51], size=9)
para(
    "점유 중 20–26°C 지표는 이전 검토와 비교하기 위한 기술 통계다. 새 환경 이상 온도 경계 18–28°C와 다르다. 온도·전력 변화는 열용량·UA·인체 발열·기타 발열·COP와 그에 따른 제어 반응을 함께 바꾼 결과다. 단일 계수만의 효과를 분리한 실험은 아니다."
)
para(
    "열 반응이 완만해졌다는 결과만으로 새 계수가 실제 학교에 더 정확하다고 결론 내릴 수 없다. 모델의 원인과 결과를 연결하고 가정을 노출했다는 것이 이번 변경의 검증 가능한 성과다."
)
source("deliverables/v0.2.0/comparison.json · tools/v02/compare_runs.py")

page_start("17  Extreme Case Review 최고온도 사례 재검토")
para(
    "기준선 최고온도는 STU-B131, 2026-09-14 18:29, 인원 15명일 때 41.018121°C다. 보존한 v0.1.0 소스로 해당 공간의 14일을 다시 생성했고 9월 14일 1,440개 truth 행이 기존 파일과 모두 같았다."
)
para(
    "HVAC 고장은 17:55–18:29의 반개구간이다. 18:29에 설비가 냉방으로 복구되어도 truth(18:29)는 직전 고장 구간의 누적 결과다. 따라서 이 최고값을 고장과 무관한 정상 냉방 중 고온으로 설명하면 시계열의 의미를 잘못 해석하게 된다."
)
para(
    "고장 시작 17:55의 기존 온도도 이미 37.764°C였다. 34분 고장 구간의 추가 상승은 기존 약 3.254°C, 새 모델 약 0.678°C다. 따라서 41.018°C 전체를 이 고장 하나의 영향으로 단정하지 않는다."
)
image(
    "extreme_comparison",
    caption="Figure 3. 같은 공간·같은 이용 조건의 온도 궤적. 검은 실선 v0.1.0, 회색 점선 v0.2.0. 고장 종료 후 열 반응 지연을 포함한다.",
)
window = json.loads((R / "deliverables/v0.2.0/extreme_window.json").read_text())
matched = next(r for r in window["v02"] if "T18:29:" in r["timestamp"])
para(
    f"새 모델의 같은 시각 온도는 {float(matched['true_temperature_c']):.3f}°C다. 온도를 잘라 낮춘 것이 아니라 유효 열용량·열교환·열 공급을 연결해 적분한 결과다. 다른 시드·공간·고장 지속시간에서의 극값과 민감도는 추가 검토 대상이다."
)
source("baseline-replay.log · replay_verification.json · extreme_window.json")

page_start("18  Limits and Next Steps 한계와 다음 단계")
para(
    "현재 시뮬레이터는 가정 조건 아래의 일관된 합성 데이터 생성기다. 실제 시설 성능을 입증하는 디지털 트윈은 아니다. 단일 구획·상수 COP·종합 UA·유효 열용량으로 벽체와 장비의 복잡한 반응을 근사한다. 실제 일사, 문·창문·공간 간 이동, 활동별 발열과 제습 잠열은 충분히 모델링하지 않는다."
)
heading("Sensitivity before calibration 민감도와 보정", 2)
para(
    "다음 단계에서는 열용량·UA·COP·인체 발열의 범위를 바꾸되 예약·인원·외기를 고정해 온도·쾌적 시간·전력·회복 시간의 변화량을 비교한다. 가능하면 허용된 절차로 익명 인원과 실내외 온도·전력 관측을 확보해 계수를 보정하고 별도 기간에서 검증한다."
)
heading("Machine learning readiness 학습 준비", 2)
para(
    "인터페이스 개발과 합성 실험에는 새 실행을 사용할 수 있다. 팀 공통 데이터 버전·시간 분할·입력 계약을 고정한 뒤 단순 기준모델부터 평가한다. F1-score가 높아도 주입 규칙을 학습한 결과일 수 있으므로 실제 센서 성능과 동일시하지 않는다. 회복 구간 포함 여부, 고장 유형별 성능과 오경보를 따로 보고한다."
)
heading("Remaining implementation scope 남은 구현", 2)
para(
    "온도·습도 센서 고장, 복수 동시 고장, 지연·센서 교체, 취소 이력, 생성 중 재개와 데이터 묶음 원자적 커밋은 아직 없다. 장기 데이터는 CSV의 용량과 하루치 집계 메모리 사용을 고려해 Parquet·DB 저장을 검토할 수 있다."
)

page_start("Appendix A 실행과 점검")
para(
    "프로젝트 폴더에서 가상환경을 활성화하고 새 실행 ID를 사용한다. 기존 데이터 ID는 보존한다. 아래는 새로 실행하는 예시이며 실제 검증한 실행은 v02-full-30d다."
)
code(
    "source .venv/bin/activate\npython -m aiot_sim simulate --days 30 --seed 20261102 --run-id my-v02-run\npython -m aiot_sim aggregate --run-id my-v02-run --minutes 5\npython -m aiot_sim validate --run-id my-v02-run\npython -m aiot_sim report --run-id my-v02-run"
)
para(
    '실행 의존성은 Python 3.11 이상 표준 라이브러리다. 현재 검증 환경은 Python 3.14.7, pytest 9.2다. 새 환경은 python3 -m venv .venv 후 pip install -e ".[dev]"로 개발 도구를 설치한다. 프로젝트 루트의 aiot_sim 링크로 모듈을 바로 실행할 수 있다.'
)
heading("Review files 검토 파일", 2)
for text in [
    "docs/v0.2.0_release.md는 새 파일·레이블과 시간 계약을 설명한다.",
    "comparison.json은 입력 일치·통계·원본 보존 결과다.",
    "validation_report.json은 전체 행 검증 결과다.",
    "tests.log와 replay_verification.json은 테스트·재현 범위의 근거다.",
    "baselines/v0.1.0은 코드·설정 스냅샷이며 full-30d는 기존 데이터다.",
]:
    para(text)

page_start("Appendix B Sources and Provenance 근거와 출처")
para(
    "구현·실행 결과는 이 프로젝트의 소스와 실제 생성 파일을 근거로 했다. 문헌은 방법과 개념을 지원하며 여기서 사용한 모든 계수가 캠퍼스에 적합하다고 보증하지 않는다."
)
heading("Heat balance and capacitance 열수지와 열용량", 2)
para(
    "EnergyPlus Engineering Reference 22.1.0의 zone air heat balance와 유효 열용량 개념을 참고했다. 본 프로젝트는 EnergyPlus를 실행하거나 그 결과와 교차 검증하지 않았다."
)
small(
    "https://energyplus.net/assets/nrel_custom/pdfs/pdfs_v22.1.0/EngineeringReference.pdf"
)
heading("COP definition COP 정의", 2)
para(
    "미국 에너지부 FEMP는 COP를 같은 단위의 열 출력과 전기 입력의 비로 설명한다. 본 프로젝트의 3.2·3.0은 장비 인증값이 아닌 상수 가정이다."
)
small(
    "https://www.energy.gov/cmei/femp/incorporate-minimum-efficiency-requirements-heating-and-cooling-products-federal"
)
heading("Carbon dioxide generation CO₂ 발생량", 2)
para(
    "Persily and de Jonge, Carbon dioxide generation rates for building occupants, Indoor Air, 2017. DOI 10.1111/ina.12383. 활동과 체격에 따른 차이를 다루므로 단일 발생계수의 한계를 함께 해석해야 한다."
)
small("https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=920870")
heading("Design reference 디자인 참고", 2)
para(
    "사용자 제공 PROLED XDR Display Technical Paper는 표지 대비·여백·제목 계층의 구성 참고로만 사용했다. 본문·로고·사진을 복제하지 않았다. 본 문서의 수식·표는 Word에서 편집 가능하며 그래프는 실제 CSV에서 작성했다."
)

# Native cached contents with verified manual page breaks; renderer checks actual pages.
cache = TOC_PLACEHOLDER._p
parent = cache.getparent()
index = parent.index(cache)
for item in contents:
    pp = OxmlElement("w:p")
    pr = OxmlElement("w:pPr")
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:leader"), "dot")
    tab.set(qn("w:pos"), str(int(Mm(W) / 635)))
    tabs.append(tab)
    pr.append(tabs)
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:after"), "115")
    pr.append(spacing)
    pp.append(pr)
    hl = OxmlElement("w:hyperlink")
    hl.set(qn("w:anchor"), item["bookmark"])
    for text in [item["title"], "\t", str(item["page"])]:
        rr = OxmlElement("w:r")
        tt = OxmlElement("w:tab") if text == "\t" else OxmlElement("w:t")
        if text != "\t":
            tt.text = text
        rr.append(tt)
        hl.append(rr)
    pp.append(hl)
    parent.insert(index, pp)
    index += 1
parent.remove(cache)
for border in DOC.element.xpath(".//w:pBdr") + DOC.styles.element.xpath(".//w:pBdr"):
    border.getparent().remove(border)
for pp in DOC.element.xpath(".//w:p"):
    pr = pp.get_or_add_pPr() if hasattr(pp, "get_or_add_pPr") else pp.find(qn("w:pPr"))
    if pr is None:
        pr = OxmlElement("w:pPr")
        pp.insert(0, pr)
    snap = OxmlElement("w:snapToGrid")
    snap.set(qn("w:val"), "false")
    pr.append(snap)
DOC.save(OUT / "Smart_Campus_AIoT_Simulator_Technology_Overview_v1_1.docx")
(R / "deliverables/v0.2.0/document_inventory.json").write_text(
    json.dumps(
        dict(planned_pages=page, contents=contents), ensure_ascii=False, indent=2
    )
)
print("Saved complete v1.1 white paper", page, "planned pages")
