from pathlib import Path
import json, sys
import joblib
import pandas as pd
import streamlit as st

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import OUTPUT, PROFILE, SOURCE
from inference import predict_snapshot, ventilation_advice

st.set_page_config(page_title='김시환 스터디룸 개인 모델',layout='wide')
st.markdown('''<style>
.block-container {max-width:1200px; padding-top:2.5rem; padding-bottom:3rem;}
[data-testid="stMetricValue"] {font-size:1.8rem;}
[data-testid="stMetricLabel"] {font-size:0.95rem;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:14px;}
div[data-testid="stExpander"] {margin-top:0.5rem;}
@media (max-width:640px) {.block-container {padding:1.5rem 1rem;} }
</style>''', unsafe_allow_html=True)

@st.cache_data
def load_table(name,root=str(OUTPUT)):
    return pd.read_csv(Path(root)/f'{name}_inference_inputs.csv.gz',parse_dates=['asof','target_time'])

@st.cache_resource
def load_model(name,root=str(OUTPUT)):return joblib.load(Path(root)/f'{name}_model.joblib')

@st.cache_data
def room_names():
    rooms=pd.read_csv(SOURCE/'inputs/rooms.csv')
    return {r.room_id:f'{r.building_name} {r.room_number} ({r.room_id})' for _,r in rooms.iterrows()}

view=st.sidebar.radio('사용자 화면',['학생 · S1 추천','관리자 · S5 제어 검토'])
scenario='S1' if view.startswith('학생') else 'S5'
v2root=HERE/'experiments/v2/artifacts'
version='v1'
if scenario=='S1' and (v2root/'evaluation.json').exists():
    version=st.sidebar.radio('실험 데이터',['v1','v2'],format_func=lambda x:'기존 30일 자료' if x=='v1' else '상황별 가상 실험',key='S1_version')
active_root=v2root if version=='v2' else OUTPUT
frame=load_table(scenario,str(active_root));test=frame[frame.split=='test']
if version=='v2':
    v2plan=json.loads((v2root/'plan.json').read_text(encoding='utf-8'))
    runs=sorted(test.run_id.unique())
    run=st.sidebar.selectbox('가상 상황',runs,format_func=lambda x:
        f"{v2plan['scenarios'][x.split('_',2)[2]]['label']} · seed {x.split('_')[1]}")
    test=test[test.run_id==run]
    st.sidebar.caption('가상 63실 · 10~13시 실험 · 기존 개인 조건 유지')
times=sorted(test['asof'].unique())
asof=st.sidebar.selectbox('입력 기준 시각 (+09:00)',times,index=len(times)-1,key=scenario+'_'+version+'_asof',format_func=lambda t:t.strftime('%m/%d %H:%M'))
names=room_names()
snapshot=predict_snapshot(scenario,test,asof,load_model(scenario,str(active_root)))
rooms=sorted(snapshot.room_id.unique())
if not rooms:
    st.info('해당 시각의 유효 입력이 없습니다.');st.stop()
selected=st.sidebar.selectbox('스터디룸',rooms,key=scenario+'_'+version+'_room',format_func=lambda r:names.get(r,r))
row=snapshot[snapshot.room_id==selected].iloc[0]
if version=='v2':
    v2evaluation=json.loads((v2root/'evaluation.json').read_text(encoding='utf-8'))
    evaluation={'selected':v2evaluation['selected'],'rows':v2evaluation['rows'],
                'selected_test':v2evaluation['test']['selected']['overall'],
                'features':load_model('S1',str(active_root))['features']}
else:
    evaluation=json.loads((OUTPUT/f'{scenario}_evaluation.json').read_text(encoding='utf-8'))
if scenario=='S1':
    ranking_key='prediction'
    if version=='v2':
        decision_path=v2root/'operational_decision.json'
        ranking_key=json.loads(decision_path.read_text(encoding='utf-8'))['ranking_key'] if decision_path.exists() else 'score_current'
    eligible=snapshot[snapshot.eligible].sort_values([ranking_key,'room_id'],ascending=[False,True]).head(3)
    st.subheader('추천 스터디룸')
    st.caption('현재 환경 조건을 충족한 공간을 현재 환경 점수순으로 보여줍니다. 8분 뒤 예측은 참고값입니다.'
               if ranking_key=='score_current' else '현재 환경 조건을 충족한 공간을 다음 8분의 예상 점수순으로 보여줍니다.')
    if eligible.empty:
        st.info('지금은 조건을 충족하는 공간이 없습니다. 다른 시각을 선택해 보세요.')
        if version=='v2':
            from experiments.v2.policy import reference_alternatives
            alternatives=reference_alternatives(snapshot)
            if not alternatives.empty:
                with st.expander('조건이 부족한 참고 공간 · 추천 대상 아님'):
                    for _,alternative in alternatives.iterrows():
                        st.write(f"{names.get(alternative.room_id,alternative.room_id)} · 확인 필요: {alternative.exclusion_reason}")
                    st.caption('CO₂와 좌석 기준을 충족한 공간 중 미충족 항목이 적은 순입니다. 추천 조건을 완화한 목록이 아닙니다.')
    else:
        for card,(_,candidate) in zip(st.columns(len(eligible)),eligible.iterrows()):
            with card:
                with st.container(border=True):
                    st.markdown(f"**{names.get(candidate.room_id,candidate.room_id).split(' (')[0]}**")
                    st.metric('예상 환경 점수',f'{candidate.prediction:.1f} / 100')
                    if ranking_key=='score_current':st.caption(f'정렬 기준: 현재 환경 점수 {candidate.score_current:.1f}')
                    st.caption(f'CO₂ {candidate.co2:.0f} ppm · 소음 {candidate.noise:.1f} dB(A)')

    st.divider()
    st.subheader('선택한 공간의 상태')
    status,score=st.columns([2,1],gap='large')
    with status:
        if row.eligible:
            st.success('현재 추천 조건을 충족합니다.')
        else:
            st.info(f"확인이 필요한 항목: {row.exclusion_reason}")
        st.caption('왼쪽 메뉴에서 공간과 기준 시각을 바꿀 수 있습니다.')
    with score:
        st.metric('8분 뒤 예상 환경 점수',f'{row.prediction:.1f} / 100',
                  help='설정한 환경 선호 기준을 예측한 점수입니다. 실제 이용자 만족도가 아닙니다.')

    measures=[('CO₂',row.co2,'ppm',row.co2<PROFILE['ventilation_on_ppm'],f"{PROFILE['ventilation_on_ppm']} ppm 미만"),
              ('온도',row.temp,'℃',PROFILE['temperature_range_c'][0]<=row.temp<=PROFILE['temperature_range_c'][1],'20–26 ℃'),
              ('습도',row.humidity,'%',PROFILE['humidity_range_pct'][0]<=row.humidity<=PROFILE['humidity_range_pct'][1],'40–60 %'),
              ('소음',row.noise,'dB(A)',row.noise<=PROFILE['maximum_noise_dba'],'45 dB(A) 이하')]
    for col,(label,value,unit,passed,guide) in zip(st.columns(4),measures):
        with col:
            with st.container(border=True):
                st.metric(label,f'{value:.1f} {unit}')
                st.caption(f"{'✓ 충족' if passed else '• 확인 필요'} · {guide}")
    st.caption(f'조도 {row.light:.0f} lux / 기준 300 lux 이상 · 여유 좌석 {max(0,int(row.capacity-row.occupancy))}석 (합성 정원 기준)')

    with st.expander('전체 공간 비교'):
        comparison_columns=['room_id','prediction','eligible','co2','temp','humidity','light','noise','exclusion_reason']
        if ranking_key=='score_current':comparison_columns.insert(1,'score_current')
        table=snapshot.sort_values(['eligible',ranking_key,'room_id'],ascending=[False,False,True])[
            comparison_columns].copy()
        table['room_id']=table.room_id.map(names)
        table['eligible']=table.eligible.map({True:'조건 충족',False:'확인 필요'})
        table['exclusion_reason']=table.exclusion_reason.replace('', '—')
        table=table.rename(columns={'room_id':'공간','score_current':'현재 점수 (정렬 기준)','prediction':'예상 점수','eligible':'현재 상태','co2':'CO₂ (ppm)',
            'temp':'온도 (℃)','humidity':'습도 (%)','light':'조도 (lux)','noise':'소음 (dB(A))','exclusion_reason':'확인할 항목'})
        st.dataframe(table,hide_index=True,width='stretch',column_config={
            name:st.column_config.NumberColumn(format='%.1f') for name in
            ['현재 점수 (정렬 기준)','예상 점수','CO₂ (ppm)','온도 (℃)','습도 (%)','조도 (lux)','소음 (dB(A))'] if name in table.columns})

    with st.expander('추천 기준과 데이터 안내'):
        st.write('환경 기준: 온도 20–26℃ · 습도 40–60% · CO₂ 890ppm 미만 · 소음 45dB(A) 이하 · 조도 300lux 이상 · 여유 좌석 1석 이상.')
        st.write('점수의 목표값은 온도 23℃·습도 50%이며, 고정 설계 가중치로 만든 환경 점수를 예측합니다. 실제 만족도·실시간 예약 가능 여부를 뜻하지 않습니다.')
        if version=='v2':
            rec=v2evaluation['test']['selected']['recommendation']
            st.write(f"상황별 시험 {rec['instants']}시점 중 조건 충족 후보가 있는 시점은 {rec['qualified_instants']}개입니다. 난수 seed를 분리한 가상 실험이며 실제 학생 만족도를 검증한 결과는 아닙니다.")
            st.write('모델의 점수 예측 오차는 개선됐지만 검증 구간에서 추천 순위의 개선은 확인되지 않아 현재 점수 정렬을 유지합니다. 현재 조건 충족은 미래 조건 충족을 보장하지 않습니다.')
        else:
            review=json.loads((OUTPUT/'model_review.json').read_text(encoding='utf-8'))
            st.write(f"시험 {review['S1_test_instants']}시점 중 모든 조건을 만족한 시점은 {review['S1_eligible_instants']}개입니다. 습도 등 데이터 범위가 부족해 운영 적용은 보류 중입니다.")
        st.caption('저장된 합성 데이터의 시험 구간을 재현한 화면입니다.')
else:
    st.subheader('공간별 점검 현황')
    st.caption('대표 4실 · 저장된 합성 데이터 재현 · 실제 장치 제어 기능은 없습니다.')
    on=PROFILE['ventilation_on_ppm']
    off=PROFILE['ventilation_off_ppm']
    overview=snapshot.copy()
    overview['priority']=overview.apply(lambda r:0 if pd.isna(r.co2) or pd.isna(r.prediction) else
        1 if r.co2>=on else 2 if r.prediction>=on else 3,axis=1)
    overview['status']=overview.priority.map({0:'입력 확인',1:'현재 기준 초과',2:'8분 뒤 초과 예상',3:'기준 미만'})
    overview['action']=overview.apply(lambda r:ventilation_advice(r.co2,r.prediction,r.ventilation_on),axis=1)
    counts=st.columns(4)
    for col,label,value in zip(counts,['현재 확인 공간','현재 기준 초과','8분 뒤 초과 예상¹','환기 가동 중'],
        [len(overview),int((overview.co2>=on).sum()),int(((overview.co2<on)&(overview.prediction>=on)).sum()),
         int(overview.ventilation_on.sum())]):
        with col:
            with st.container(border=True):st.metric(label,f'{value}실')
    st.caption(f'¹ 현재 {on}ppm 미만이지만 예측값이 기준 이상인 공간입니다. 예측 경보는 점검 우선순위이며 제어 권고와 다를 수 있습니다.')
    queue=overview.sort_values(['priority','prediction','room_id'],ascending=[True,False,True])
    table=pd.DataFrame({'공간':queue.room_id.map(names),'점검 상태':queue.status,
        '현재 CO₂ (ppm)':queue.co2,'8분 뒤 (ppm)':queue.prediction,
        '환기':queue.ventilation_on.map({1.0:'켜짐',0.0:'꺼짐'}),'권고':queue.action})
    st.dataframe(table,hide_index=True,width='stretch',column_config={
        c:st.column_config.NumberColumn(format='%.0f') for c in ['현재 CO₂ (ppm)','8분 뒤 (ppm)']})

    st.divider()
    st.subheader('선택 공간 점검')
    st.caption('공간은 왼쪽 메뉴에서 선택합니다. 아래 추세와 점검 기록은 선택한 공간 기준입니다.')
    cols=st.columns(3)
    for col,label,value in zip(cols,['현재 CO₂','8분 뒤 예상 CO₂','관측된 환기 상태'],
        [f'{row.co2:.0f} ppm',f'{row.prediction:.0f} ppm','켜짐' if row.ventilation_on else '꺼짐']):
        with col:
            with st.container(border=True):st.metric(label,value)
    advice=ventilation_advice(row.co2,row.prediction,row.ventilation_on)
    if row.co2>=on:st.warning(advice)
    else:st.info(advice)
    st.caption(f'켜기 기준 {on}ppm 이상 · 해제 기준 {off}ppm 이하 · 실제 적용 전 센서·최소 가동시간·장치 응답 확인 필요')

    with st.expander('최근 2시간 CO₂ 추세',expanded=True):
        history=test[(test.room_id==selected)&(test['asof']<=asof)&
                     (test['asof']>=pd.Timestamp(asof)-pd.Timedelta(hours=2))][['asof','co2']].copy()
        history=history.sort_values('asof').set_index('asof').rename(columns={'co2':'관측 CO₂'})
        history['켜기 기준']=on
        history['해제 기준']=off
        st.line_chart(history,x_label='입력 기준 시각 (+09:00)',y_label='CO₂ (ppm)',height=240)
        st.caption('저장된 8분 간격 입력의 관측 추세입니다. 8분 뒤 예측값은 위 카드에서 확인합니다.')

    with st.expander('점검 메모'):
        note_key=f'S5_note_{selected}_{pd.Timestamp(asof).isoformat()}'
        st.text_area('확인 사항과 후속 조치',key=note_key,
                     placeholder='예: 센서 값 확인 필요 / 현장 환기 상태 확인 예정')
        st.caption('메모는 임시 입력입니다. 공간·시각 변경이나 새로고침 전에 필요한 기록을 내려받으세요.')
        record={'공간':names.get(selected,selected),'기준 시각':str(asof),'현재 CO₂ (ppm)':float(row.co2),
                '8분 뒤 CO₂ (ppm)':float(row.prediction),'관측 환기 상태':'켜짐' if row.ventilation_on else '꺼짐',
                '검토 권고':advice,'점검 메모':st.session_state.get(note_key,''),
                '자료 구분':'저장된 합성 데이터; 실제 장치 제어 기록 아님'}
        st.download_button('선택 공간 점검 기록 내려받기',pd.DataFrame([record]).to_csv(index=False).encode('utf-8-sig'),
                           file_name=f'점검_{selected}_{pd.Timestamp(asof).strftime("%Y%m%d_%H%M")}.csv',mime='text/csv')
    comparison=OUTPUT/'paired_simulation_comparison.json'
    if comparison.exists():
        compare=json.loads(comparison.read_text(encoding='utf-8'))
        with st.expander('예측 보조 정책의 효과 비교'):
            baseline=compare['results']['baseline'];predictive=compare['results']['predictive']
            metrics=[('재실 중 CO₂ 기준 초과 시간 (분)','occupied_co2_ge_890_minutes'),
                     ('총전력 (kWh)','total_energy_kwh'),('최대 CO₂ (ppm)','max_true_co2_ppm'),
                     ('환기 가동 시간 (분)','ventilation_minutes')]
            comparison_table=pd.DataFrame([{'지표':label,'개인 기준 정책':baseline[key],
                '예측 보조 정책':predictive[key],'변화 (예측 보조 − 기준)':predictive[key]-baseline[key]} for label,key in metrics])
            st.dataframe(comparison_table,hide_index=True,width='stretch',column_config={
                c:st.column_config.NumberColumn(format='%.2f') for c in
                ['개인 기준 정책','예측 보조 정책','변화 (예측 보조 − 기준)']})
            st.caption('9/26–30 · 10:00–21:00 · 대표 4실 합계. 선택 공간 한 곳의 결과가 아닙니다. 같은 고장·예약·인원 및 시험 전 상태에서 비교한 합성 실험이며 다른 59실 성능은 미확인입니다.')
with st.expander('모델별 학습·평가 정보'):
    st.write('선택 모델:',evaluation['selected'])
    st.write('학습/검증/시험 행 수:',evaluation['rows'])
    st.write('시험 MAE:',evaluation['selected_test']['mae'],'점' if scenario=='S1' else 'ppm')
    st.write('입력 특징:',evaluation['features'])
    st.caption('미래 실제값, 고장 정답, 회복 종료 시각은 모델 입력에 넣지 않았습니다. 미래 정답 표는 이 화면에 표시하지 않습니다.')
