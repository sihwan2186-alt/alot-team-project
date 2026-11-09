import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "deliverables/data_review"
s = json.loads((OUT / "dataset_audit.json").read_text())
t = json.loads((OUT / "thermal_extremes.json").read_text())
c = s["counts"]
n = c["occupied_room_minutes"]


def pct(x, den):
    return 100 * x / den


st = s["truth_statistics"]
design = s["design"]
ex = s["counterfactual_experiments"]["hvac_power_sensitivity"]
text = f"""# 공통 데이터셋 검토와 보정 우선순위

기준일 2026-11-03. 소프트웨어 v0.1.0 / 데이터 full-30d / 백서 v1.0.
이 검토는 기존 코드·설정·CSV를 바꾸지 않은 상태에서 수행했다. 백서의 디자인 평가는 반복하지 않고 실제 데이터와 생성 알고리즘을 대조했다.

## 결론

현재 데이터는 파일 규격·파이프라인·추천 후보 필터의 연동 개발에 사용할 수 있다. 그러나 **물리 모델의 실측 타당성과 실제 학교에서의 ML 일반화 성능은 미검증**이다. 우선순위는 온도·설비 소비전력의 연결을 보완하고 이상 구간과 환경 회복 시점을 분리하는 것이다. 제어·에너지 최적화의 실제 효율을 이 데이터만으로 입증해서는 안 된다.

## 실제 재검사 범위

- 2026-09-01–09-30, 63개 공간의 truth·센서·에너지 파일을 날짜별로 순회했다.
- 각 스트림의 timestamp+room_id 일치를 직접 검사했다.
- 읽은 정답·센서 행은 각각 {c["rows"]:,}개, 하루 {s["days"][0]["rows"]:,}개다.
- 기존 전체 validation_report는 valid=true, 오류 0·경고 0이다. 그 보고서를 물리적 현실성의 증거로 간주하지 않았다.
- 센서와 정답을 분석용으로 비교했으나 후보 추천 예제 입력에는 truth를 넣지 않았다.

## 관측된 합성 데이터 분포

분모가 다르므로 전체 시간, 운영 시간, 실제 이용 시간이 섞이지 않도록 구분했다.

- 실제 내부 온도: {st["temperature_c"]["min"]:.2f}–{st["temperature_c"]["max"]:.2f}°C, 전체 평균 {st["temperature_c"]["mean"]:.2f}°C.
- 실제 RH: {st["humidity_pct"]["min"]:.2f}–{st["humidity_pct"]["max"]:.2f}%, 전체 평균 {st["humidity_pct"]["mean"]:.2f}%.
- 실제 CO₂: {st["co2_ppm"]["min"]:.2f}–{st["co2_ppm"]["max"]:.2f}ppm, 전체 평균 {st["co2_ppm"]["mean"]:.2f}ppm.
- 실제 조도: {st["illuminance_lux"]["min"]:.2f}–{st["illuminance_lux"]["max"]:.2f}lux. 소음: {st["noise_dba"]["min"]:.2f}–{st["noise_dba"]["max"]:.2f}dB(A).
- 운영시간 공간·분 {c["operating_room_minutes"]:,}개 중 인원이 1명 이상인 공간·분 {n:,}개, 비율 {pct(n, c["operating_room_minutes"]):.2f}%.
- 평일 운영시간 점유율 {pct(s["demand"]["weekday"]["occupied_minutes"], s["demand"]["weekday"]["room_minutes"]):.2f}%, 주말 {pct(s["demand"]["weekend"]["occupied_minutes"], s["demand"]["weekend"]["room_minutes"]):.2f}%. 이는 예약 시도 확률 0.75/0.35와 다른 지표다.
- 운영시간 외 점유는 {c["outside_hours_occupied"]:,}개다.
- 이용 중 공간·분 {n:,}개 중 CO₂>1,000ppm은 {c["co2_gt_1000_occupied"]:,}개({pct(c["co2_gt_1000_occupied"], n):.2f}%), >1,500ppm은 {c["co2_gt_1500_occupied"]:,}개({pct(c["co2_gt_1500_occupied"], n):.3f}%)다. 이 선은 분포 점검용이며 보건·법정 기준으로 판정하지 않았다.
- 이용 중 20–26°C 밖은 {c["temperature_outside_config_targets_occupied"]:,}개({pct(c["temperature_outside_config_targets_occupied"], n):.2f}%)다. 20–26°C는 현재 정책의 가정 목표 구간이지 보편적 쾌적성 기준이 아니다.
- RH>80%는 전체 {c["rh_gt_80_all"]:,}개이나 이용 중에는 {c["rh_gt_80_occupied"]:,}개다. 전체와 이용 중 분포는 다르다.
- CO₂ 센서 결측 {s["sensor_missing"]["co2_ppm"]:,}개, 전체 센서 행 대비 {pct(s["sensor_missing"]["co2_ppm"], c["rows"]):.3f}%. 다른 센서 결측 주입은 없다.
- 총 에너지 {s["total_energy_kwh"]:.6f}kWh, 인원 0명인 구간 에너지 {s["unoccupied_energy_kwh"]:.6f}kWh({pct(s["unoccupied_energy_kwh"], s["total_energy_kwh"]):.2f}%). 대기전력·최소 가동시간을 포함하므로 이 합계를 모두 낭비로 정의하지 않는다.

## 우선순위 1 온도 응답과 HVAC 전력의 연결

**코드 사실:** environment.evolve는 `hvac_power_kw`를 온도 계산에 사용하지 않는다. 냉방 효과는 모든 공간에서 −0.10°C/min이고, 인원 효과는 부피·열용량과 무관하게 1명당 +0.012°C/min이다. 소비전력은 energy.energy에서 따로 계산한다.

**실제 함수 실험:** 같은 공간·외기·인원·설비 상태에서 프로필 HVAC 소비전력만 10배 바꿨다. HVAC 전력은 {ex["hvac_kw_first"]:.6f}→{ex["hvac_kw_second"]:.6f}kW로 바뀌었지만 다음 온도는 두 경우 모두 {ex["temperature_first_c"]:.6f}°C로 같았다. 임의로 만든 곡선이 아니라 실제 evolve와 energy 함수를 호출한 결과다.

**추론:** 현재 모델에서는 더 많은 전기를 쓰는 HVAC가 더 큰 냉각 효과를 내지 않는다. 설비 효율·부하·제어 정책 간 물리적 에너지 최적화의 타당성을 이 구조로 검증할 수 없다. 외기와 실내 온도가 같다면 9명부터 인원 발열항이 고정 냉방항을 초과한다. 이는 외기 열손실을 제외한 코드 계수 비교이며 모든 상태에서 냉방 불가능하다는 뜻은 아니다.

**보완 제안:** 유효 열용량 C_eff, 외피 열전달 UA, 인원 현열 W, 설비 소비전력과 COP/가용 열출력의 관계를 명시한 에너지 수지로 바꾼다. 실측 응답 또는 근거가 없는 계수는 범위와 민감도를 함께 표시한다. 목표를 맞추려고 온도를 강제로 clip하는 방식은 피한다.

근거: src/aiot_sim/engines/environment.py, hvac.py, energy.py. EnergyPlus도 사람의 열발생을 현열·잠열 및 공간 열수지와 연결해 다룬다. 이는 현재 모델에 특정 EnergyPlus 계수를 그대로 적용했다는 뜻은 아니다.
https://energyplus.readthedocs.io/en/v26.2.0/guides/input-output-reference/1.14-group-internal-gains-people-lights-other-internal-zone-equipment.html

## 우선순위 2 온도 극값의 원인과 정답 구간 해석

실제 최대 온도는 STU-B131의 2026-09-14 18:29 +09:00에서 41.018121°C, 현재 인원 15명이다. 이 시각에는 HVAC가 cooling이고 주입 고장 여부가 false다. **그러나 이것만 보고 정상 가동 중 원인 없는 이상이라고 판단하면 잘못이다.**

이 공간에는 17:55–18:29 미만의 hvac_failure가 있었다. 18:27과 18:28 설비는 off·equipment_fault_active=true였고, 이 구간의 열 누적이 18:29 정답에 반영된다. 고장 구간 종료 즉시 환경이 정상으로 돌아오는 것은 아니다. 현재 truth(t)는 이전 구간 적분의 결과이고 시설(t)은 다음 구간에 적용될 상태다.

**권장:** 시나리오 4의 정답을 (a) 고장 주입 원인 구간, (b) 실제 환경 임계 초과 구간, (c) 회복 구간으로 구분한다. 현재 anomaly_events는 (a)이며 모든 (b)를 포함한다고 해석하지 않는다. 41°C 값 하나만으로 모델 전체를 오류로 단정하지 않되, 위의 열응답 구조와 큰 공간의 부하를 함께 보정해야 한다.

유형별 이용 중 가정 목표 20–26°C 밖 비율:
"""
for kind, g in t["by_type"].items():
    text += f"- {kind}: {g['outside_20_26']:,}/{g['occupied']:,} 공간·분, {pct(g['outside_20_26'], g['occupied']):.2f}%.\n"
text += f"""
유형 차이는 정원·점유·설비·외기·주입 고장이 혼합된 관측 결과다. 이 비율만으로 한 요인의 인과 효과를 추정하지 않았다.

## 우선순위 3 CO₂ 계수의 근거 수준 정리

`G=0.018m³/인·시간 = 0.005L/인·초`다. Persily와 de Jonge의 연구는 가정한 건물 이용자 조건에 따라 약 0.003–0.006L/s·person의 평균 발생량을 제시한다. 따라서 현재 G는 규모상 문헌과 양립 가능하지만, 이 학교 이용자의 연령·신체·활동·온압 조건을 확인한 보정값은 아니다. **사후 문헌 비교를 초기 설정 당시 검증 근거로 소급해 쓰지 않는다.**

환기 ON 프로필을 부피·정원으로 환산한 최대 유량은 {min(d["maximum_ventilation_l_s_person"] for d in design):.2f}–{max(d["maximum_ventilation_l_s_person"] for d in design):.2f}L/s·person이다. 설정 ACH만 보고 적정 환기를 단정할 수 없으며 인원당 유량과 함께 보아야 한다.

전원 정원 이용·외기 425ppm·최대 환기를 장시간 고정한다고 가정한 질량수지 평형 `425 + capacity×G×10⁶/(ACH×V)`에서는 {sum(d["full_capacity_equilibrium_co2_ppm"] > 1000 for d in design)}/63개 공간이 1,000ppm보다 높다. 이는 실제 관측 초과 공간 수가 아니라 계산한 가상 평형이다. 제어의 ON 기준과 달리 모든 부하에서 1,000ppm 이하를 보장하는 설계는 아니다. 1,000ppm을 모든 환경의 보편적 건강 판정선으로 해석하지 않는다.

근거 연구: Persily A, de Jonge L. 2017. Carbon dioxide generation rates for building occupants. Indoor Air 27:868–879. DOI 10.1111/ina.12383. NIST 제공 원문:
https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=920870

## 나머지 계수의 현재 근거 수준

- 정원·면적·천장·시설·운영시간: 사용자 지정 가상 프로필 규칙. 실제 학교 시설 사양으로 검증되지 않았다.
- 온도 계수·고정 냉방효과·대기전력·설비 전력·수요·고장 빈도·센서 잡음: TOML의 시뮬레이션 가정. 제조사 사양·실측 추정·통계 적합 자료가 없다.
- 수분 발생 0.5g/min, 냉방 제습 0.002/min, 포화식: 구현 수식은 확인했지만 학교 관측에 대한 보정 또는 이번 작업의 문헌 기반 독립 타당성 검증은 하지 않았다.
- 소음원 가정과 공간별 고정 activity: 시간에 따라 달라지는 실제 활동 종류를 재현한다고 검증되지 않았다.
- 외기 425ppm·온도 일주기: 실제 2026년 9월 캠퍼스 관측이 아니다. 분포 모양이 자연스럽다는 이유만으로 실측과 동등하다고 평가하지 않는다.

## 팀 전달과 버전 정책

현재 데이터는 '합성 데이터 기반 인터페이스 개발용'으로 전달한다. 보정 전 실제 설비 효율이나 학교 환경 예측 성능의 근거로 사용하지 않는다. 목적 기반 추천에는 docs/team_data_usage.md와 examples/scenario2_room_candidates.py를 함께 전달한다.

백서 v1.0과 소프트웨어 v0.1.0, full-30d 원본은 그대로 보존했다. 모델을 수정한다면 별도 소프트웨어·프로필 버전과 새 run_id를 사용해 다시 생성하고 비교한다. 기록을 바꾸지 않고 v1.0의 24개 테스트 기록과 새 예제 테스트를 구분한다.

## 재실행과 증거 파일

```bash
source .venv/bin/activate
python tools/data_review/audit_dataset.py --output deliverables/data_review/dataset_audit.json
python tools/data_review/inspect_thermal_extremes.py
python -m pytest tests/examples -q
```

- dataset_audit.json: 날짜별 실제 행 수, 분포, 분모, 센서 결측·에너지 합, 실제 함수 실험.
- thermal_extremes.json: 최대 온도 위치와 앞뒤 시설·정답, 직전 고장 구간.
- scenario2_demo.json: 실제 실행한 목적 기반 후보 예제 전체 63개 공간의 판정.
- example_tests.log / all_tests.log / all_tests.xml / code_check.log: 새 테스트·코드 검사 증거.

시간·메모리: 전체 감사는 날짜별 CSV를 스트리밍하며 분포 최소·최대·합계·건수만 유지한다. 정밀 분위수나 다변량 분포 적합·실측 비교를 수행했다고 주장하지 않는다. 이번 결과는 구현·내부 분포 검토이며 실측 환경 타당성 검증의 완료가 아니다.
"""
(OUT / "model_review.md").write_text(text)
print("wrote model_review.md")
