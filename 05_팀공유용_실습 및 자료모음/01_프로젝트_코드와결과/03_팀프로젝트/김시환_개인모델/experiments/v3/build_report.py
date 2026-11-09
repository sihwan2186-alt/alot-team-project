"""Render comparison tables and plots from saved experiment results, without fitting."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
OUT=HERE/'artifacts'
summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
selected=summary['selected_model']
model=pd.read_csv(OUT/'model_audit.csv').sort_values('mae')
val=pd.read_csv(OUT/'model_validation.csv')
sub=pd.read_csv(OUT/'subgroup_audit.csv')
features=pd.read_csv(OUT/'feature_audit.csv')
general=pd.read_csv(OUT/'generalization_audit.csv')
ranking=pd.read_csv(OUT/'ranking_audit.csv')
learning=pd.read_csv(OUT/'learning_curve.csv')
extra=pd.read_csv(OUT/'additional_experiments.csv')
importance=pd.read_csv(OUT/'validation_permutation_importance.csv')

def table(d):
    frame=d.copy()
    for c in frame.select_dtypes(include='number'):
        frame[c]=frame[c].map(lambda x:f'{x:.3f}' if pd.notna(x) else '—')
    return '| '+' | '.join(frame.columns)+' |\n| '+' | '.join(['---']*len(frame.columns))+' |\n'+'\n'.join(
        '| '+' | '.join(str(x).replace('|','/') for x in row)+' |' for row in frame.itertuples(index=False,name=None))

fig,axes=plt.subplots(2,2,figsize=(18,15),layout='constrained')
axes[0,0].barh(model.method.iloc[::-1],model.mae.iloc[::-1],color=['#b6c2d1' if n!=selected else '#2775cc' for n in model.method.iloc[::-1]])
axes[0,0].set(title='18 methods: new synthetic audit',xlabel='MAE (design-score points)')
axes[0,0].grid(axis='x',alpha=.2)
pivot=sub[sub.dimension=='scenario'].pivot(index='method',columns='group',values='mae').reindex(model.method)
im=axes[0,1].imshow(pivot.to_numpy(),aspect='auto',cmap='YlOrRd')
axes[0,1].set_yticks(range(len(pivot)),pivot.index,fontsize=9)
axes[0,1].set_xticks(range(len(pivot.columns)),pivot.columns,rotation=40,ha='right')
axes[0,1].set_title('MAE by synthetic scenario')
fig.colorbar(im,ax=axes[0,1],label='MAE')
axes[1,0].plot(learning.train_rows,learning.mae,marker='o',color='#2775cc')
axes[1,0].set(title='Training size: fixed HGB (15 leaves)',xlabel='Training rows',ylabel='Audit MAE')
axes[1,0].grid(alpha=.2)
g=general.copy();g['label']=g.dimension+': '+g.held_out.astype(str)
g['delta']=g.mae-g.full_train_control_mae
axes[1,1].barh(g.label.iloc[::-1],g.delta.iloc[::-1],color='#da8c3e')
axes[1,1].set(title='Omitting training groups: paired degradation',xlabel='MAE minus full-training control')
axes[1,1].axvline(0,color='gray',linewidth=.8)
if not (OUT/'comparison_overview.png').exists():
    fig.savefig(OUT/'comparison_overview.png',dpi=150)
plt.close(fig)

chosen=sub[sub.method==selected].copy()
sections=[]
labels={'scenario':'가상 상황','building':'건물','hour':'시간대','occupancy_ratio':'혼잡도','humidity':'습도 구간',
        'co2':'CO₂ 구간','noise':'소음 구간','seat_availability':'여유좌석 여부','seed':'새 시험 seed',
        'current_eligibility':'현재 조건 충족 여부','past_feature_missing':'과거 변화 특징 결측',
        'current_co2_missing':'현재 창 CO₂ 일부 결측'}
for dim,label in labels.items():
    d=chosen[chosen.dimension==dim][['group','n','mae','rmse','p95_absolute_error']]
    d=d.rename(columns={'group':'구분','n':'평가 행 수','mae':'MAE','rmse':'RMSE','p95_absolute_error':'절대오차95%값'})
    sections.append(f'### {label}\n\n'+table(d))
rooms=chosen[chosen.dimension=='room'].sort_values('mae',ascending=False)
sections.append('### 공간별 차이\n\n63실 전체 값은 `artifacts/subgroup_audit.csv`의 dimension=room에 있다. 아래는 오차가 큰10실이다. 실제 건물의 품질 순위가 아닌 가상 모델의 예측 오차다.\n\n'+table(rooms[['group','n','mae','p95_absolute_error']].head(10)))

main=model.merge(val[['method','mae','converged']],on='method',suffixes=('_audit','_validation'))
main=main[['method','mae_validation','mae_audit','rmse','p95_absolute_error','converged']]
main=main.rename(columns={'method':'방법','mae_validation':'검증 MAE','mae_audit':'새 시험 MAE','rmse':'새 시험 RMSE',
 'p95_absolute_error':'새 시험 절대오차95%값','converged':'수렴 경고 없음'})
feature_table=features[['ablation','feature_count','mae']].rename(columns={'ablation':'제외/구성','feature_count':'특징 수','mae':'새 시험 MAE'})
clean=extra[(extra.experiment=='score_free_ablation')&(extra.split=='fresh_audit')][['variant','feature_count','mae']]
clean=clean.rename(columns={'variant':'현재점수 제거 후 추가 제외','feature_count':'특징 수','mae':'새 시험 MAE'})
residual=extra[extra.experiment=='residual_forecast'][['variant','split','mae']]
ranktable=ranking[['policy','qualified_instants','regret','future_violation']].copy()
ranktable.future_violation*=100
ranktable=ranktable.rename(columns={'policy':'정렬 방식','qualified_instants':'추천 가능 시점','regret':'순위 손실','future_violation':'미래 조건 위반율 (%)'})
general_table=general[['dimension','held_out','train_rows','audit_rows','mae','full_train_control_mae']].rename(columns={
 'dimension':'분리 기준','held_out':'학습 제외 그룹','train_rows':'학습 행','audit_rows':'시험 행',
 'mae':'제외 학습 MAE','full_train_control_mae':'같은 시험 행 전체학습 MAE'})
best=float(model.iloc[0].mae)
base=float(model.loc[model.method=='persistence','mae'].iloc[0])
report=f'''# S1 다방면 비교 실험 v3

실험 시작 2026-11-04, 결과 검수 2026-11-05. 실제 센서·만족도·예약 기록을 사용하지 않았다. 선문대 공간 식별 목록에 대응하는 63실의 센서·정원·환경 프로필은 가상이다. 기존 v1/v2와 앱의 추천 방식은 변경하지 않았다.

## 먼저 확인할 결과

- **검증에서 선택한 `{selected}`가 새 시험에서도 MAE {best:.3f}점으로 가장 낮았다.** 같은 시험의 지속값은{base:.3f}점이다. 실제 만족도 정확도가 아니라 다음8분의 가상 설계 환경 점수 오차다.
- 혼잡 상황을 학습에서 빼면 고정 HGB의 해당 상황 MAE가 **1.683→6.749점**으로 증가했다. 여러 모델을 바꾸는 것만큼 학습 데이터에 다양한 상황을 포함하는 것이 중요하다.
- 현재점수를 제거한 추가 특징 실험에서는 좌석/재실을 더 제거했을 때 **3.008→4.177점**, 습도를 제거하면 **3.008→3.508점**으로 증가했다. 이 데이터 생성·점수 규칙에서 유용한 정보이지 모든 실제 학생에게 적용되는 인과적 중요도는 아니다.
- 예측점수 정렬은 현재점수 정렬보다 새 시험의 순위 손실은 작았지만 미래 조건 위반율은 **15.10%→23.96%**로 높았다. 검증에서도 예측 정렬 채택 기준을 통과하지 못해 **현재점수 정렬 유지**가 선택됐다.
- 18모델·10기본 특징 구성·7추가 특징 구성·2잔차 예측·14그룹 제외·4학습량·8정렬 방식, 총63개 실험/비교 설정을 계산했다. 일부 설정은 공통 기준선을 재사용하며 독립적인63개 데이터셋이나 통계 검정이 아니다. 13개 분류 축으로 **1,764개 세부 성능 행**도 저장했다.

![모델·상황·학습량·그룹 제외 비교](artifacts/comparison_overview.png)

## 1. 공정하게 비교한 범위

v2의 train15,492행·validation7,746행으로 모든 후보를 비교했다. 입력 조건은p=2·q=3, 10시 시작·8분 창·890/850ppm·기존 선호 가중치를 유지했다. 전처리는 train에서만 fit했다. HGB 조기종료의 무작위 내부 분할과 MLP의 내부 무작위 검증은 사용하지 않았다.

모델과 추천정렬을 validation에서 선택한 뒤 `selection.json`을 저장했다. 그 다음 새 seed5401/5402, 9/30·10/1의6개 상황을 생성했다. 새 시험은15,492행, 12개 실행, 252개 실행·시각이다. 원시 관측은136,080행이다. 알려진v2 시험 자료를 새 최종 선택에 재사용하지 않았다.

주요 모델은 같은15특징·같은학습행·같은새시험행을 사용했다. 트리 복잡도와 후보 설정은 `plan.json`에 먼저 기록했다. 추가 특징/잔차 실험은 주 모델 선택을 변경하지 않는 진단용이다. 광범위 비교를 했지만 모든 하이퍼파라미터를 탐색한 것은 아니다.

## 2. 모델18개 비교

낮을수록 좋다. 검증에서 수렴 경고가 있는 후보는 선택 대상에서 제외했다. 시험 결과가 가장 좋은 방법을 사후에 채택한 것이 아니다.

{table(main)}

모델별 원본 수치는 `artifacts/model_validation.csv`, `model_audit.csv`다. 실행시간도 저장했으나 단일 장비·한 번의 실행값으로 안정적인 속도 순위나 배포 지연시간을 주장하지 않는다.

## 3. 데이터를13개 기준으로 나눠 확인

아래는 검증에서 선택한 모델의 **같은 새 시험 데이터 내부 세부 비교**다. 각 그룹의 행 수가 다르므로 이를 독립 실험·실제 건물 평가로 해석하지 않는다. 그룹별 가장 좋은 모델은 탐색적 결과일 뿐 새 모델 선택 근거로 쓰지 않았다.

{chr(10).join(sections)}

혼잡도는 재실/가상 정원 비율을0~30%, 30~70%, 70~100%로 나눴다. 습도 구간40to60은40이상60미만, co2 구간700to890은700이상890미만 등이다. 분석용 구간 경계와 후보 검사(습도40~60 포함)는 다를 수 있다. 매우 작은 그룹의 오차는 안정적인 비교 근거가 아니다.

## 4. 입력 특징을 바꾸면

고정 HGB(15개 잎)를 사용해 모델 차이와 특징 차이를 분리했다. `no_score`는현재점수, `no_changes`는과거변화, `no_clock`은시각·요일을제외한다.

{table(feature_table)}

**현재점수에는 이미 온습도·CO₂·소음·조도·혼잡 정보가 요약되어 있다.** 따라서 습도열만 빼도 습도 정보가 완전히 없어진 것은 아니다. 이를 보완해 현재점수를 모든 구성에서 먼저 제거하고 각 정보를 추가 제거했다.

{table(clean)}

CO₂ 제거 시 오차가 조금 낮아진 결과는 다른 특징과의 중복·이번 생성 패턴·추정 변동의 영향을 포함한다. 후보 검사에서CO₂를 없애도 된다는 의미가 아니다. 습도와 좌석/재실 정보는 이번 점수 예측에서 제거 손실이 컸다. 조도는 영향이 작게 관측됐지만 실제 저조도 방을 추천하는 것을 허용한다는 결론은 아니다.

검증 자료의 순열 중요도도 `validation_permutation_importance.csv`에 저장했다. 현재점수·재실·소음 순으로 값이 컸다. 상관된 파생 특징의 중요도는 서로 나뉠 수 있으며 인과 효과가 아니다. train 날짜가 모두수요일이므로 weekday 중요도0은요일이항상불필요하다는 증거가 아니다.

## 5. 점수 대신 변화량을 예측하면

목표를 미래점수−현재점수로 바꿔 학습하고 추론 시 현재점수를 더했다. 원래 선택 모델의 채택을 바꾸지 않는 추가 실험이다.

{table(residual)}

HGB잔차 예측은 새시험2.822점으로 주 모델2.819점과 비슷했다. 이 차이는 두seed만으로 우열을 확정할 근거가 아니다. Ridge잔차 예측은 개선되지 않았다.

## 6. 학습에서 특정 그룹을 제외하면

고정 HGB(15개 잎)로 학습을 반복했다. building/scenario는 해당건물/상황을train에서제외하고 새시험의같은그룹을평가한다. seed는train seed한개를빼고 새시험전체를평가한다. time_cutoff는목표시각이11시/12시이전인train만학습하고 새시험의그이후시간을평가한다. 모든경우전체학습모델을**같은시험행**에적용한대조값을함께기록했다.

{table(general_table)}

혼잡 상황 누락에서 가장 큰 악화가 나타났다. 건물 제외는 손실이 상대적으로 작았으나 공간 수·프로필이 가상 고정값이므로 실제 미관측 건물 일반화 성능을 뜻하지 않는다. 이 실험은 주 선택 모델을 다시 고른 교차검증이 아니라 고정 알고리즘의 누락 민감도 검사다.

## 7. 학습량을 줄이면

seed·상황·공간별로 결정적인 난수표본을 뽑아 학습 비율을 비교했다. 작은 그룹의 반올림 때문에 실제행수가 명목비율과 조금 다르다. 입력행은 시간적으로 연관되어 있으므로 학습행을 늘리는 것과 독립seed를 늘리는 것은 다르다.

{table(learning[['train_fraction','train_rows','mae','rmse']])}

추가 행이 도움이 됐지만10%자료에서도 기본 패턴을 어느정도 학습했다. 향후에는 동일조건행 복제보다 **새seed·시간대·미포함 상황**을 늘리는 쪽을 우선 검토할 근거가 된다.

## 8. 추천 정렬 방식8개 비교

모든 방식은 현재 개인 조건을 충족한 후보 안에서만 정렬한다. CO₂최소·소음최소·현재점수·예측점수·검증상위3모델평균·위험감점5/10/20을비교했다. 위험모델은train의미래조건충족여부를학습했으며 특징에는미래정답을넣지않았다. 출력은확률보정하지않은점수로, 실제안전확률이아니다.

{table(ranktable)}

순위 손실은 같은 현재 유효 후보 중 미래 설정 점수가 가장 좋은 공간과 선택 공간의 차이다. 미래 조건 위반율은 선택 공간이 다음 8분 창에 하나 이상의 설계 조건을 충족하지 못한 비율이다. 둘은 평가 목적이 다르다. 모든 방식의 현재 조건 위반은 0이었다. 후보가 있는 시점은 192/252이며, 후보 없는 60시점은 이 비율의 분모에 포함하지 않는다.

검증에서는 미래 위반율이 현재 점수 기준선 이하인 방식 중 순위 손실이 작은 방식을 선택했고 현재 점수 정렬이 남았다. 새 시험에서 일부 방식의 순위 손실이 더 낮아도 선택을 뒤집지 않았다. 예측 모델의 MAE 개선만으로 학생 추천 전체가 개선됐다고 말할 수 없다.

## 9. 현재 판단 및 한계

1. 점수 예측용으로는 HGB 계열이 이번 데이터에서 유리했다. 선형·이웃·신경망이 자동으로 더 좋아지는 것은 아니었다.
2. 재실/좌석·습도·소음과 다양한 혼잡 상황을 유지한다. 단일 환경 항목의 최소값만으로 전체 선호를 대체하지 않는다.
3. 추천 정렬은 현재 점수 기준을 유지하고 미래 예측을 보조 정보로 사용하는 기존 판단을 유지한다. v3 모델은 비교 결과로 저장했고 앱 모델을 자동 교체하지 않았다.
4. 이번 실험은 63실·10~13시·한정된 가상 재실 발생기다. 가상 규칙을 학습한 결과이며 실제 만족도·전일·다른 계절 성능이 아니다. 새 시험 seed는 2개뿐이므로 유의성·보편적 우열은 주장하지 않는다.
5. 결측 상황의 평가는 미래 정답이 유효한 행에서 이뤄진다. 결측으로 학습/평가에서 빠진 행이 있으며 모든 결측 상황을 해결했다는 뜻은 아니다. 가상 선호 유형을 다수 학습한 개인화 실험도 아니다.

방법근거: 시간·공간적으로연관된자료는그룹/시간분리를고려하고전처리를train에서만학습해야한다는 [scikit-learn 교차검증 지침](https://scikit-learn.org/stable/modules/cross_validation.html)을참고했다. 실제분할·설정은`plan.json`과`selection.json`에있다.

## 10. 결과 파일

- `model_validation.csv`, `model_audit.csv`:18모델의검증/새시험전체성능
- `subgroup_audit.csv`:13분류축·1,764개세부결과(공간별63실포함)
- `feature_validation.csv`, `feature_audit.csv`:10가지특징구성
- `additional_experiments.csv`:현재점수없는7가지추가제거와2잔차예측
- `generalization_audit.csv`:14개그룹/시간제외실험
- `learning_curve.csv`:4가지학습량
- `ranking_validation.csv`, `ranking_audit.csv`:8가지정렬방법
- `audit_dataset.csv.gz`, `audit_predictions.csv.gz`:동일키로추적가능한새시험입력·정답·18모델예측
- `validation_permutation_importance.csv`:검증자료순열중요도
- `plan.json`, `selection.json`, `summary.json`:실험조건·사전선택·결과요약

실행도구는`run_comparison.py`, `run_additional.py`, `build_report.py`다. 기존실험결과가있으면주실험은덮어쓰지않고중단한다. 원본DOCX·v1/v2모델·기존앱은교체하지않았다.
'''
for old,new in {
 '18모델':'18개 모델','10기본 특징':'10개 기본 특징','7추가 특징':'7개 추가 특징',
 '2잔차 예측':'2개 잔차 예측','14그룹 제외':'14개 그룹 제외','4학습량':'4개 학습량',
 '8정렬 방식':'8개 정렬 방식','현재점수':'현재 점수','미래점수':'미래 점수','새시험':'새 시험',
 '검증자료':'검증 자료','순열중요도':'순열 중요도','전체학습':'전체 학습','같은시험행':'같은 시험 행',
 '학습행':'학습 행','학습비율':'학습 비율','재실/좌석':'재실·좌석','같은학습행':'같은 학습 행',
 '시각·요일을제외한다':'시각·요일을 제외한다','과거변화':'과거 변화',
 '목표시각':'목표 시각','미래조건위반율':'미래 조건 위반율','미래조건충족여부':'미래 조건 충족 여부',
 '가상재실발생기':'가상 재실 발생기','시간분리':'시간 분리','그룹/시간분리':'그룹·시간 분리',
}.items():
    report=report.replace(old,new)
(HERE/'README.md').write_text(report,encoding='utf-8')
save=main.copy()
save.to_csv(OUT/'모델비교_요약.csv',index=False,encoding='utf-8-sig')
print('Report and plot saved:',HERE/'README.md')
