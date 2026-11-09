"""Build readable saved-result tables and scientific plots, without training."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
OUT=HERE/'artifacts'
s=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
plan=json.loads((OUT/'plan.json').read_text(encoding='utf-8'))
model=pd.read_csv(OUT/'model_audit.csv').sort_values('mae_ppm')
validation=pd.read_csv(OUT/'model_validation.csv')
sub=pd.read_csv(OUT/'subgroup_audit.csv')
features=pd.read_csv(OUT/'feature_audit.csv')
general=pd.read_csv(OUT/'generalization_audit.csv')
learning=pd.read_csv(OUT/'learning_curve.csv')
residual=pd.read_csv(OUT/'residual_forecast.csv')
controls=pd.read_csv(OUT/'closed_loop_audit.csv')
totals=pd.read_csv(OUT/'closed_loop_audit_totals.csv')
chosen=model[model.method==s['selected_model']].iloc[0]
base=model[model.method=='persistence'].iloc[0]
cb=totals[totals.policy=='rule_baseline'].iloc[0]
cp=totals[totals.policy==s['selected_control_policy']].iloc[0]

def table(d):
    frame=d.copy()
    for c in frame.select_dtypes(include='number'):
        if pd.api.types.is_integer_dtype(frame[c]):frame[c]=frame[c].map(str)
        else:frame[c]=frame[c].map(lambda v:f'{v:.3f}' if pd.notna(v) else '—')
    return '| '+' | '.join(frame.columns)+' |\n| '+' | '.join(['---']*len(frame.columns))+' |\n'+'\n'.join(
        '| '+' | '.join(str(x).replace('|','/') for x in row)+' |' for row in frame.itertuples(index=False,name=None))

if not (OUT/'comparison_overview.png').exists():
    fig,axes=plt.subplots(2,2,figsize=(18,16),layout='constrained')
    reversed_model=model.iloc[::-1]
    axes[0,0].barh(reversed_model.method,reversed_model.mae_ppm,
        color=['#2775cc' if n==s['selected_model'] else '#afbecd' for n in reversed_model.method])
    axes[0,0].set(title='S5: 20 forecast methods',xlabel='New synthetic audit MAE (ppm)')
    axes[0,0].grid(axis='x',alpha=.2)
    pivot=sub[sub.dimension=='scenario'].pivot(index='method',columns='group',values='mae_ppm').reindex(model.method)
    im=axes[0,1].imshow(pivot.to_numpy(),aspect='auto',cmap='YlOrRd')
    axes[0,1].set_yticks(range(len(pivot)),pivot.index,fontsize=9)
    axes[0,1].set_xticks(range(len(pivot.columns)),pivot.columns,rotation=40,ha='right')
    axes[0,1].set_title('Scenario-specific forecast errors')
    fig.colorbar(im,ax=axes[0,1],label='MAE (ppm)')
    axes[1,0].barh(features.ablation.iloc[::-1],features.mae_ppm.iloc[::-1],color='#559581')
    axes[1,0].set(title='Feature subsets: fixed HGB',xlabel='New audit MAE (ppm)')
    axes[1,0].grid(axis='x',alpha=.2)
    for _,r in totals.iterrows():
        dx=(r.total_energy_kwh/cb.total_energy_kwh-1)*100
        dy=(r.excess_ppm_room_minutes/cb.excess_ppm_room_minutes-1)*100
        axes[1,1].scatter(dx,dy,s=85)
        axes[1,1].annotate(r.policy,(dx,dy),xytext=(8,8),textcoords='offset points')
    axes[1,1].axhline(0,color='gray',linewidth=.8)
    axes[1,1].axvline(0,color='gray',linewidth=.8)
    axes[1,1].set(title='12-room paired closed-loop audit',xlabel='Total energy change (%)',ylabel='Occupied CO2 excess exposure change (%)')
    axes[1,1].margins(.3)
    axes[1,1].grid(alpha=.2)
    fig.savefig(OUT/'comparison_overview.png',dpi=150)
    plt.close(fig)

model_table=model.merge(validation[['method','mae_ppm','converged']],on='method',suffixes=('_audit','_validation'))
model_table=model_table[['method','mae_ppm_validation','mae_ppm_audit','rmse_ppm','future_exceedance_f1','future_exceedance_recall','converged']]
model_table=model_table.rename(columns={'method':'방법','mae_ppm_validation':'검증 MAE','mae_ppm_audit':'새 시험 MAE',
    'rmse_ppm':'새 시험 RMSE','future_exceedance_f1':'미래 초과 F1','future_exceedance_recall':'미래 초과 재현율','converged':'수렴 경고 없음'})
sections=[]
dimensions={'scenario':'가상 상황','building':'건물','hour':'시간대','crowding':'재실 비율',
    'current_co2':'현재 CO₂ 구간','ventilation':'현재 관측 환기 상태','volume':'가상 부피',
    'on_ach':'환기 켜짐 시 가상 ACH','seed':'새 시험 seed','past_missing':'과거 이력 결측','trend':'현재 CO₂ 추세'}
selected_sub=sub[sub.method==s['selected_model']]
for dimension,label in dimensions.items():
    d=selected_sub[selected_sub.dimension==dimension][['group','n','mae_ppm','future_exceedance_f1','future_exceedance_recall','true_exceedance_fraction']]
    d=d.rename(columns={'group':'구분','n':'행 수','mae_ppm':'MAE (ppm)','future_exceedance_f1':'미래 초과 F1',
        'future_exceedance_recall':'초과 재현율','true_exceedance_fraction':'실제 미래 초과 비율'})
    sections.append(f'### {label}\n\n'+table(d))
rooms=selected_sub[selected_sub.dimension=='room'].sort_values('mae_ppm',ascending=False)
sections.append('### 공간별 차이\n\n63실 전체는 subgroup_audit.csv에 있다. 아래는 예측 오차가 큰 10실이며 실제 시설 품질 순위가 아니다.\n\n'+table(rooms[['group','n','mae_ppm','future_exceedance_f1']].head(10)))

ct=totals[['policy','co2_ge_890_occupied_room_minutes','excess_ppm_room_minutes','total_energy_kwh','ventilation_energy_kwh',
           'ventilation_requested_switches','max_true_co2_ppm']].rename(columns={
 'policy':'제어 방식','co2_ge_890_occupied_room_minutes':'재실 중 기준 초과 공간·분',
 'excess_ppm_room_minutes':'초과 노출 ppm·공간·분','total_energy_kwh':'총전력 kWh',
 'ventilation_energy_kwh':'환기 전력 kWh','ventilation_requested_switches':'환기 전환 요청','max_true_co2_ppm':'최대 CO₂ ppm'})
by_scenario=controls.groupby(['scenario','policy'])[['co2_ge_890_occupied_room_minutes','excess_ppm_room_minutes','total_energy_kwh']].sum()
control_differences=[]
for scenario in plan['scenarios']:
    a=by_scenario.loc[(scenario,'rule_baseline')];b=by_scenario.loc[(scenario,s['selected_control_policy'])]
    control_differences.append({'상황':scenario,'초과 공간·분 변화':b.co2_ge_890_occupied_room_minutes-a.co2_ge_890_occupied_room_minutes,
        '초과 노출 변화 (%)':100*(b.excess_ppm_room_minutes/a.excess_ppm_room_minutes-1),
        '총전력 변화 (%)':100*(b.total_energy_kwh/a.total_energy_kwh-1)})
old=json.loads((OUT/'v1_transfer.json').read_text(encoding='utf-8'))
feature_table=features[['ablation','feature_count','mae_ppm','future_exceedance_f1']].rename(columns={
 'ablation':'특징 구성','feature_count':'특징 수','mae_ppm':'새 시험 MAE ppm','future_exceedance_f1':'미래 초과 F1'})
general_table=general[['dimension','held_out','train_rows','n','mae_ppm','full_train_control_mae_ppm','persistence_mae_ppm']].rename(columns={
 'dimension':'제외 기준','held_out':'제외 그룹','train_rows':'학습 행','n':'시험 행',
 'mae_ppm':'제외 학습 MAE','full_train_control_mae_ppm':'같은 행 전체학습 MAE','persistence_mae_ppm':'지속값 MAE'})
report=f'''# S5 다방면 비교 분석

검토일 2026-11-05. 가상 센서·재실·공간 프로필과 가상 환기 제어만 사용했다. 기존 S5 v1 및 S1 실험·앱 모델은 교체하지 않았다.

## 결과 요약

- 검증에서 선택한 **{s['selected_model']}**의 새 시험 MAE는 **{chosen.mae_ppm:.3f}ppm**, 지속값은 **{base.mae_ppm:.3f}ppm**이다. 같은 자료의 미래 CO₂≥890ppm 판정 F1은 **{chosen.future_exceedance_f1:.3f}**, 지속값은 **{base.future_exceedance_f1:.3f}**다.
- S1에서 유리했던 HGB와 달리 이번 S5에서는 MLP가 검증에서 선택됐다. 모든 문제에 한 모델이 가장 좋은 것은 아니다.
- 예측20방식·특징10구성·잔차예측2방식·그룹/시간제외14설정·학습량4단계·제어4방식을 비교했다. **54개 실험/비교 설정**이며 일부는 공통 기준선을 재사용한다. {s['subgroup_dimensions']}개 분류 축의 세부 결과 {s['subgroup_result_rows']:,}행을 저장했다.
- 실제 제어 효과는 **고정 12실**에서 같은 외기·인원·고장 조건의 72개 폐루프 실행으로 비교했다. 검증에서 선택한 **{s['selected_control_policy']}**를 새 시험에도 그대로 적용했다.
- 새 시험에서 선택 정책의 초과 공간·분은 **{int(cb.co2_ge_890_occupied_room_minutes):,}→{int(cp.co2_ge_890_occupied_room_minutes):,}**, 총전력은 **{cb.total_energy_kwh:.3f}→{cp.total_energy_kwh:.3f}kWh**였다. 다른 지표와 상황별 차이는 아래 표를 함께 봐야 한다.

![S5 예측 모델·상황·특징·제어 비교](artifacts/comparison_overview.png)

## 1. 실험 범위와 데이터 분리

예측은63실, 제어는 각 건물의 가상 정원이 작은·중간·큰 공간을 사전에 선택한12실이다. 제어 공간 ID: `{', '.join(plan['control_rooms'])}`. 나머지51실의 제어 효과를 검증한 것은 아니다.

train seed1301/1302, validation2301, 새 시험6401/6402를 분리했다. 날짜는 train9/2·9/16, validation9/23, 새 시험9/30·10/1이다. 09~10시 워밍업, 10~13시만 평가한다. 각 공간의 재실은 상황별 이항분포로 생성하며 실제 예약 자료가 아니다.

상황6개: 보통 재실·높은 재실·급격한 입실·빠른 인원 변화·CO₂ 결측·일부 환기 작동 실패. 고장 상황은 이 비교를 위한 인위적 설정이며 교수의 미확보된 유형0 정의를 구현한 것이 아니다.

학습{s['train_rows']:,}행, 검증{s['validation_rows']:,}행, 새 시험{s['fresh_audit_rows']:,}행이다. 목표는 정확히8분 뒤 **관측 CO₂**다. 현재 CO₂ 또는 미래 목표가 결측인 학습/평가 행은 제외하지만, 화면용 입력은 미래 정답 유무로 제외하지 않는다. 결측 상황의 낮은 오차가 모든 결측을 해결했다는 의미는 아니다.

13개 특징은 현재/과거 CO₂, 현재 재실, 관측 환기 상태, 가상 부피/ACH, 시각·요일이다. 미래 인원·미래 설비·truth·고장 플래그·에너지는 모델 입력이 아니다. 모델 전처리는 train에서만 fit했다. 모델 선택과 제어 선택을 검증에서 끝내고 기록한 뒤 새 시험을 생성했다.

## 2. 예측 방식20개

MAE/RMSE는ppm 단위로 낮을수록 좋다. F1은 미래 관측 CO₂가890ppm 이상인지의 판정으로 높을수록 좋다. 센서 고장 탐지 F1이나 공식 안전 기준 판정이 아니다. MLP는 표준화된 입력과 목표를 사용하고, HGB는 다양한 잎 수·손실함수를 비교했다.

{table(model_table)}

단순 추세는 현재 CO₂+8×과거 분당 변화, 물질수지는 현재 인원·환기량이8분간 유지된다고 가정한 해석식이다. 실제 가상 환경에서는 인원과 환기 명령이 변하므로 이 가정이 깨진다. 해석식의 오차가 컸다고 물리 모델 전체가 쓸모없다는 뜻은 아니다.

기존 v1 모델을 같은 새 시험에 그대로 적용한 MAE는 **{old['mae_ppm']:.3f}ppm**이었다. v1은 대표4실·다른 기간과 분포에서 학습했으므로 순수 알고리즘 우열 비교가 아니다. 원래 v1 시험 MAE19.126ppm과 이번 새 시험 값을 직접 비교해 개선/악화를 단정하지 않는다.

## 3. 데이터를 나눠 확인한 결과

아래는 선택 모델의 새 시험 내부 비교다. 각 그룹의 분모와 실제 미래 초과 비율을 같이 본다. 초과 사례가 없는 그룹의 F1/재현율은 계산 규칙상0으로 저장되며 그 자체로 예측 실패를 뜻하지 않는다. 그룹별 수치는 기술통계이며 독립적인 검정 결과가 아니다.

{chr(10).join(sections)}

재실 비율은0~30%,30~70%,70~100%로, 부피는75/150m³, 켜짐ACH는2.5/3.5를 경계로 나눴다. CO₂ 구간은 하한 포함·상한 미포함이다. 추세는 과거8분 평균 변화율−1~1ppm/분을 안정 구간으로 두었다. 과거 관측이 없어 추세를 계산하지 못하는128행은 unknown(추세 미확인)으로 포함했다. 모든 분류별 행 수 합계가 새 시험16,248행과 일치하는 것을 검증했다. 이 분석 구간은 제어 기준을 변경하지 않는다.

## 4. 어떤 입력이 필요한가

고정 HGB를 사용해 특징의 영향을 비교했다. `no_history`는lag1/lag8/추세, `no_ventilation`은관측 환기 켜짐/단계, `no_geometry`는부피/ACH를 제외한다.

{table(feature_table)}

현재 CO₂만 쓰는 것보다 과거 이력·재실·환기 상태·가상 공간 특성을 함께 쓰는 쪽이 이번 예측에 도움이 됐다. 특정 특징을 제거했을 때 작은 차이가 났다는 이유로 실제 제어에 필요한 현재 상태 정보까지 삭제하면 안 된다. 이 실험의 가상 ACH/정원을 실제 측정값으로 해석하지 않는다.

## 5. 변화량 예측·학습량 비교

미래 CO₂−현재 CO₂를 학습한 뒤 현재값을 더하는 잔차 방식도 별도로 비교했다. 주 모델의 선택을 사후 변경하지 않았다.

{table(residual[['method','split','mae_ppm','future_exceedance_f1']])}

학습량 비교는 고정 HGB와 같은 새 시험을 사용했다. seed·상황·공간별 층화 표본이며 동일 seed의 연관된 행을 늘리는 것과 독립적인 상황/seed를 늘리는 것은 다르다.

{table(learning[['train_fraction','train_rows','mae_ppm','future_exceedance_f1']])}

## 6. 학습에서 특정 그룹을 빼면

고정 HGB로 특정 건물·상황·학습 seed를 제외했다. 시간 제외는 목표시각이11시/12시 이전인 행만 학습하고 새 시험의 그 이후 시간대를 평가했다. 전체학습 대조 모델도 반드시 같은 시험 행에서 계산했다.

{table(general_table)}

이 결과는 학습에 포함하지 않은 상황의 민감도를 보여 준다. 그룹 제외 진단으로 모델을 다시 선택한 것은 아니다. 많은 행이 있어도 급격한 입실·혼잡·고장 같은 상황이 빠지면 일반화에 한계가 생길 수 있다.

## 7. 예측이 실제 가상 제어에 도움이 되는가

이 부분은 예측 CSV의 오차 비교와 별도로 엔진을 다시 실행한 **폐루프 비교**다. 각 정책의 명령이 다음 분의 환경을 바꾸고, 새 센서 관측을 보고 다시 판단한다. CO₂ 노출은 환경truth, 전력은 적용된 설비 상태로 평가한다. 이 평가용 truth·고장 정보는 정책 입력에 전달하지 않는다.

모든 정책은 현재 CO₂≥890ppm 켜기, ≤850ppm 해제, 최소 가동5분을 유지한다. 예측 보조는 현재850~890ppm의 상태유지 구간에서만 미리 켤 수 있다. `forecast_20/40`은 예측값에20/40ppm을 더해890과 비교한다. 이는 제어 여유값 실험이며 보정된 신뢰구간이나 안전 보장이 아니다.

검증에서는 기본 정책보다 초과 노출이 줄고 총전력이5% 이내 증가하는 후보 중 초과 노출이 가장 작은 방식을 선택했다. 새 시험 결과로 정책을 바꾸지 않았다. 고장 상황에서는 환기 켜기 요청과 실제 적용 상태를 구분했고, 작동 실패한 장치를 예측만으로 복구하지 않는다.

### 새 시험12실 합계

{table(ct)}

선택 정책의 초과 노출 변화는 **{100*(cp.excess_ppm_room_minutes/cb.excess_ppm_room_minutes-1):.2f}%**, 총전력 변화는 **{100*(cp.total_energy_kwh/cb.total_energy_kwh-1):.2f}%**, 환기 전력 변화는 **{100*(cp.ventilation_energy_kwh/cb.ventilation_energy_kwh-1):.2f}%**다. 총전력에는 냉난방·조명·대기전력도 들어가므로 환기 전력과 따로 본다.

공간·분은 여러 공간의 재실 시간을 더한 단위다. 초과 노출은max(CO₂−890,0)을 재실 공간·분에 누적한 값이다. 이 수치는 한 공간의 실제 경과시간·학교 전체 절감량이 아니다. 전환 요청 수는 가상 제어 명령의 변화 횟수다.

### 상황별로 선택 정책과 기본 정책 비교

{table(pd.DataFrame(control_differences))}

전체 합계가 좋아도 특정 상황의 모든 지표가 좋아진 것은 아니다. 환기 실패·미관측 구간에서 남는 초과 노출, 전력과 전환 횟수 증가를 함께 확인해야 한다. 검증의5% 전력 기준은 선택 기준이지 새 시험에서도 자동으로 보장되는 조건이 아니다.

## 8. 현재 결론과 제한

1. 예측 모델 선택, 미래 초과 분류, 제어 효과를 별도로 평가했다. 한 지표만으로 모든 성능을 주장하지 않는다.
2. 예측은63실이지만 제어 효과는12실·10~13시·한정된 가상 인원/고장 규칙이다. 기존4실 실험보다 범위를 넓혔으나 나머지51실·전일·다른 계절을 검증하지 않았다.
3. 새 시험 seed는2개이며 통계적 유의성이나 실제 장치 효과를 주장하지 않는다. 전력·공기질은 합성 가정에 따른 결과다.
4. 모델이 미래 실제 인원이나 고장 발생 시각을 미리 알지 못하므로 빠른 인원 변화와 결측에서 성능 한계가 남는다. 가상 유형0 정의를 임의로 채우지 않았다.
5. 기존 S5 앱과 모델은 그대로 유지했다. 비교 실험의 모델·제어 정책을 실제 장치나 기존 앱에 자동 적용하지 않았다.

## 9. 결과 파일

- `model_validation.csv`, `model_audit.csv`:20개 방식의 예측·초과판정 성능
- `subgroup_audit.csv`:12개 분류 축·공간별63실 등 세부 결과
- `feature_validation.csv`, `feature_audit.csv`:10가지 특징 구성
- `generalization_audit.csv`:14가지 그룹/시간 제외 실험
- `residual_forecast.csv`, `learning_curve.csv`:잔차예측·학습량 비교
- `closed_loop_validation.csv`, `closed_loop_audit.csv`, `closed_loop_audit_totals.csv`:72개 제어 실행과 효과
- `controls/*/trace.csv.gz`:현재 관측·평가용 환경truth·예측·다음 요청·적용 상태
- `audit_dataset.csv.gz`, `audit_predictions.csv.gz`, `audit_inference_inputs.csv.gz`:새 시험 근거와 정답 없는 입력
- `plan.json`, `model_selection.json`, `control_selection.json`, `summary.json`, `verification.json`:계획·선택·검증 근거

재현 도구는 `run_comparison.py`, 결과 검증은 `verify_results.py`, 이 문서 생성은 `build_report.py`다. 주 실험은 기존 결과가 있으면 덮어쓰지 않는다.

검증 결과: 신규 테스트4개 통과. 저장된20모델 예측에서MAE와F1을 다시 계산했고, 72개 제어 추적에서 재실 중 초과 노출·환기 전력을 재구성했다. 같은 외생 조건·최소가동시간·검증 자료만 이용한 선택·기존 모델 해시도 확인했다. 총전력의 냉난방/조명/대기전력 항목은 엔진 적산값이며, 환기 전력 항목은 적용 상태와 가상 정격전력으로 독립 재계산했다.
'''
(HERE/'README.md').write_text(report,encoding='utf-8')
model_table.to_csv(OUT/'모델비교_요약.csv',index=False,encoding='utf-8-sig')
print('S5 comparison report saved:',HERE/'README.md')
