"""Build an editable Korean technical white paper from verified project facts."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict,Counter
import json,re,csv
from docx import Document
from docx.shared import Mm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement,parse_xml
from docx.oxml.ns import qn,nsdecls
from PIL import Image
R=Path(__file__).resolve().parents[2];A=R/'deliverables/assets';OUT=R/'deliverables'
F=json.loads((A/'verified_facts.json').read_text())
DOC=Document();sec=DOC.sections[0]
sec.page_width=Mm(210);sec.page_height=Mm(297);sec.top_margin=Mm(20);sec.bottom_margin=Mm(19);sec.left_margin=Mm(22);sec.right_margin=Mm(22)
sec.header_distance=Mm(9);sec.footer_distance=Mm(9);sec.different_first_page_header_footer=True
W=166
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3','Caption','Header','Footer']:
 st=DOC.styles[name];st.font.name='Helvetica Neue';st.font.color.rgb=RGBColor(0,0,0)
 rf=st.element.get_or_add_rPr().get_or_add_rFonts()
 for key in list(rf.attrib):del rf.attrib[key]
 for key,value in [('ascii','Helvetica Neue'),('hAnsi','Helvetica Neue'),('eastAsia','Apple SD Gothic Neo'),('cs','Helvetica Neue')]:rf.set(qn('w:'+key),value)
normal=DOC.styles['Normal'];normal.font.size=Pt(10.2);normal.paragraph_format.line_spacing=1.17;normal.paragraph_format.space_after=Pt(7)
for n,size,before,after in [('Title',33,0,12),('Heading 1',21,0,14),('Heading 2',13.5,12,6),('Heading 3',11,9,5),('Caption',8.5,4,10)]:
 st=DOC.styles[n];st.font.size=Pt(size);st.font.bold=n.startswith('Heading');st.paragraph_format.space_before=Pt(before);st.paragraph_format.space_after=Pt(after)
 if n.startswith('Heading'):st.paragraph_format.keep_with_next=True
DOC.styles['Caption'].font.color.rgb=RGBColor.from_string('666666')
for name in ['Header','Footer']:
 DOC.styles[name].font.size=Pt(8);DOC.styles[name].font.color.rgb=RGBColor.from_string('777777')
# Header and automatic page number.
h=sec.header.paragraphs[0];h.text='SMART CAMPUS AIoT  /  TECHNOLOGY OVERVIEW';h.style='Header'
DOC.styles['Footer'].paragraph_format.tab_stops.clear_all()
f=sec.footer.paragraphs[0];f.style='Footer'
f.paragraph_format.tab_stops.clear_all()
f.paragraph_format.tab_stops.add_tab_stop(Mm(W),2)
f.add_run('Technical Documentation  ·  Version 1.0  ·  November 2026\t')
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');run=OxmlElement('w:r');t=OxmlElement('w:t');t.text='1';run.append(t);fld.append(run);f._p.append(fld)
# Editable cover text over a full-page black background image, anchored behind text.
Image.new('RGB',(210,297),'#111111').save(A/'cover_background.png')
hp=sec.first_page_header.paragraphs[0];hp.paragraph_format.space_after=Pt(0)
r=hp.add_run();r.add_picture(str(A/'cover_background.png'),width=Mm(210),height=Mm(297))
inline=r._r.xpath('.//wp:inline')[0]
anchor=OxmlElement('wp:anchor')
for k,v in {'distT':'0','distB':'0','distL':'0','distR':'0','simplePos':'0','relativeHeight':'0','behindDoc':'1','locked':'0','layoutInCell':'1','allowOverlap':'1'}.items():anchor.set(k,v)
a=OxmlElement('wp:simplePos');a.set('x','0');a.set('y','0');anchor.append(a)
for axis in ['H','V']:
 e=OxmlElement('wp:position'+axis);e.set('relativeFrom','page');o=OxmlElement('wp:posOffset');o.text='0';e.append(o);anchor.append(e)
for child in list(inline):
 if child.tag==qn('wp:extent'):anchor.append(child)
anchor.append(OxmlElement('wp:wrapNone'))
for child in list(inline):anchor.append(child)
inline.getparent().replace(inline,anchor)
sec.first_page_footer.paragraphs[0].text=''
props=DOC.core_properties;props.title='Smart Campus AIoT Shared Environmental Simulator Technology Overview';props.subject='공통 환경 시뮬레이터 구조와 데이터 인터페이스';props.author='Smart Campus AIoT Project Team';props.keywords='AIoT simulation synthetic data environmental model';props.version='1.0';props.created=datetime(2026,11,3,0,0);props.modified=datetime(2026,11,3,0,0)
# Save a native Word field with cached TOC paragraphs later patched from actual render pages.
contents=[];figures=[];tables=[];page=1;pending_break=False

def p(text='',style=None,size=None,bold=False,color=None,after=None):
 global pending_break
 x=DOC.add_paragraph(style=style)
 if pending_break:x.paragraph_format.page_break_before=True;pending_break=False
 run=x.add_run(text);run.bold=bold
 if size:run.font.size=Pt(size)
 if color:run.font.color.rgb=RGBColor.from_string(color)
 if after is not None:x.paragraph_format.space_after=Pt(after)
 return x

def heading(text,level=1,toc=False):
 x=p(text,'Heading '+str(level))
 if toc:
  bid=len(contents)+1;bm=OxmlElement('w:bookmarkStart');bm.set(qn('w:id'),str(bid));bm.set(qn('w:name'),f'chapter_{bid}');x._p.insert(0,bm);end=OxmlElement('w:bookmarkEnd');end.set(qn('w:id'),str(bid));x._p.append(end)
  contents.append(dict(title=text,bookmark=f'chapter_{bid}',page=page))
 return x

def newpage():
 global page,pending_break
 pending_break=True;page+=1

def source(text):p('근거  '+text,size=8,color='777777',after=5)
def eq(text):
 x=DOC.add_paragraph();x.paragraph_format.space_before=Pt(4);x.paragraph_format.space_after=Pt(7)
 om=OxmlElement('m:oMath')
 def run(text):
  rr=OxmlElement('m:r');props=OxmlElement('m:rPr');sty=OxmlElement('m:sty');sty.set(qn('m:val'),'p');props.append(sty);rr.append(props)
  wp=OxmlElement('w:rPr');sz=OxmlElement('w:sz');sz.set(qn('w:val'),'21');wp.append(sz);rr.append(wp)
  tt=OxmlElement('m:t');tt.text=text;tt.set(qn('xml:space'),'preserve');rr.append(tt);return rr
 for token in re.findall(r'[A-Za-zΑ-ω0-9]+(?:_\{[^}]+\})?(?:\^\{[^}]+\})?|[^A-Za-zΑ-ω]',text):
  m=re.fullmatch(r'([A-Za-zΑ-ω0-9]+)(?:_\{([^}]+)\})?(?:\^\{([^}]+)\})?',token)
  if m and (m[2] or m[3]):
   node=OxmlElement('m:sSubSup' if m[2] and m[3] else 'm:sSub' if m[2] else 'm:sSup')
   e=OxmlElement('m:e');e.append(run(m[1]));node.append(e)
   for tag,txt in [('sub',m[2]),('sup',m[3])]:
    if txt:
     child=OxmlElement('m:'+tag);child.append(run(txt));node.append(child)
   om.append(node)
  else:om.append(run(token))
 x._p.append(om)

def table(headers,rows,widths=None,size=9,caption=None,compact=False):
 if caption:
  cap=p(caption,'Caption');cap.paragraph_format.keep_with_next=True;tables.append(caption)
  if compact:cap.paragraph_format.space_before=Pt(5);cap.paragraph_format.space_after=Pt(4)
 t=DOC.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
 if widths is None:widths=[W/len(headers)]*len(headers)
 for col,w in zip(t.columns,widths):col.width=Mm(w)
 for i,h in enumerate(headers):t.rows[0].cells[i].text=h
 for row in rows:
  cells=t.add_row().cells
  for i,v in enumerate(row):cells[i].text=str(v)
 pr=t._tbl.tblPr
 borders=OxmlElement('w:tblBorders')
 for key in ['top','left','bottom','right','insideH','insideV']:
  e=OxmlElement('w:'+key);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'3');e.set(qn('w:color'),'D9D9D9');borders.append(e)
 pr.append(borders)
 for rowi,row in enumerate(t.rows):
  trpr=row._tr.get_or_add_trPr();trpr.append(OxmlElement('w:cantSplit'))
  if rowi==0:trpr.append(OxmlElement('w:tblHeader'))
  for ci,c in enumerate(row.cells):
   c.width=Mm(widths[ci]);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   tcp=c._tc.get_or_add_tcPr();margins=OxmlElement('w:tcMar')
   for k,v in [('top',('15' if size<=8.5 else '35') if compact else '60'),('bottom',('15' if size<=8.5 else '35') if compact else '60'),('left','80'),('right','80')]:
    e=OxmlElement('w:'+k);e.set(qn('w:w'),v);e.set(qn('w:type'),'dxa');margins.append(e)
   tcp.append(margins)
   if rowi==0:
    fill=OxmlElement('w:shd');fill.set(qn('w:fill'),'EEEEEE');tcp.append(fill)
   for para in c.paragraphs:
    if rowi>0 and re.fullmatch(r'[-+]?\d+(?:\.\d+)?',c.text):para.alignment=WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_after=Pt(0);para.paragraph_format.space_before=Pt(0);para.paragraph_format.line_spacing=1.07
    snap=OxmlElement('w:snapToGrid');snap.set(qn('w:val'),'false');para._p.get_or_add_pPr().append(snap)
    for rr in para.runs:
     rr.font.size=Pt(size);rr.bold=rowi==0
 return t

def image(name,width=166,caption=None):
 x=DOC.add_paragraph();x.paragraph_format.keep_with_next=True;x.paragraph_format.space_after=Pt(2)
 run=x.add_run();run.add_picture(str(A/(name+'.png')),width=Mm(width))
 dp=run._r.xpath('.//wp:docPr')[0];dp.set('descr',caption or name)
 if caption:p(caption,'Caption');figures.append(caption)

def code(text):
 x=p(text,size=9.0,after=8);x.paragraph_format.line_spacing=1.15
 for r in x.runs:r.font.name='Menlo'
 return x

# 1 Cover.
p('SMART CAMPUS AIoT',size=14,bold=True,color='FFFFFF',after=65)
x=p('Shared Environmental\nSimulator','Title',color='FFFFFF');x.paragraph_format.space_after=Pt(22)
p('Technology Overview',size=18,color='FFFFFF',after=240)
p('공통 환경 시뮬레이터 기술 백서',size=12,color='D0D0D0',after=16)
p('Technical Documentation\nVersion 1.0\nNovember 2026',size=10,color='B0B0B0')
# 2 Contents.
newpage();p('Contents','Title');p('목차',size=11,color='777777',after=18)
toc_p=DOC.add_paragraph();toc_start=OxmlElement('w:r');fc=OxmlElement('w:fldChar');fc.set(qn('w:fldCharType'),'begin');toc_start.append(fc);toc_p._p.append(toc_start)
ri=OxmlElement('w:r');ins=OxmlElement('w:instrText');ins.set(qn('xml:space'),'preserve');ins.text=' TOC \\o "1-1" \\h \\z \\u ';ri.append(ins);toc_p._p.append(ri)
rs=OxmlElement('w:r');fc=OxmlElement('w:fldChar');fc.set(qn('w:fldCharType'),'separate');rs.append(fc);toc_p._p.append(rs)
TOC_PLACEHOLDER=DOC.add_paragraph('TOC_CACHE_PLACEHOLDER')
end=DOC.add_paragraph();rr=OxmlElement('w:r');fc=OxmlElement('w:fldChar');fc.set(qn('w:fldCharType'),'end');rr.append(fc);end._p.append(rr)
p('문서 버전 1.0  /  대상 소프트웨어 0.1.0  /  기준일 2026년 11월 3일',size=8.5,color='777777')
# 3 Introduction + features.
newpage();heading('1  Introduction 소개',toc=True)
p('이 문서는 네 명의 팀원이 동일한 공간 ID와 시계열 데이터를 사용해 학습 환경 추천, 혼잡 예측, 이상 탐지와 에너지 분석을 개발할 수 있도록 시뮬레이터의 구조·수식·데이터 계약을 설명한다. 현재 구현은 63개 가상 공간의 30일 데이터를 생성하고 저장·집계·검증하는 공통 기반이다.')
heading('Project Background 개발 배경',2)
p('스터디룸 선택에는 이용 목적뿐 아니라 온습도, 공기질, 조도, 소음과 실제 인원이 함께 작용한다. 실제 센서를 모든 공간에 설치하고 연속 관측하기 전에는 공통 데이터 규격과 모델 연동을 검토할 데이터가 부족하다. 이 프로젝트는 상태 사이의 인과 관계를 설명할 수 있는 합성 시계열로 개발 인터페이스를 먼저 검증한다.')
p('호실 목록은 사용자 제공 시설 자료를 사용한다. 정원·면적·시설 보유 여부와 모든 모델 계수는 시뮬레이션 가정이다. 구현 검증의 통과는 실제 학교 환경과의 일치나 머신러닝 일반화 성능의 검증을 뜻하지 않는다.')
heading('2  Key Features 주요 기능',toc=True)
features=[('Multi Room Simulation','4개 건물 63개 공간에 서로 다른 고정 가상 프로필을 적용한다.'),('Time Series and Correlation','1분 내부 적분으로 인원·외기·환기·설비 상태의 영향을 연결한다.'),('Synthetic Sensor Measurements','실제 내부 상태와 잡음·결측·고장이 포함된 센서 관측을 분리한다.'),('Fault and Anomaly Simulation','CO₂ 센서 고장 네 종류, 설비 고장 두 종류, 정원 내 고밀도 이용을 주입한다.'),('Feedback and Energy','관측 기반 제어를 다음 구간에 적용하고 전력과 에너지를 별도로 기록한다.'),('Reproducible Data Generation','공간·모듈별 SHA 256 파생 시드와 일별 CSV 저장을 사용한다.')]
for title,text in features:
 x=p(title,size=10.5,bold=True,after=2);x.paragraph_format.keep_with_next=True;p(text,size=10,after=6)
source('README.md · pyproject.toml · configs/simulation.toml · src/aiot_sim/pipeline/simulator.py')
# 4 Architecture.
newpage();heading('3  System Architecture 시스템 구조',toc=True)
p('pipeline/simulator.py가 상태와 파일 수명을 관리하며, 엔진은 한 가지 계산 책임을 맡는다. 물리 상태 X(t), 센서 관측 Y(t), 제어 요청, 고장 마스킹 후 적용 설비를 서로 구분하는 것이 핵심이다. Figure 1은 실제 호출 관계를 요약한다.')
image('architecture',caption='Figure 1. Overall simulator architecture. 실제 코드의 책임과 데이터 흐름을 요약했다.')
heading('Execution Flow 실행 흐름',2)
p('CLI가 TOML 설정을 읽고 마스터를 준비한다. simulate는 기존 실행 ID를 거부하고 입력 마스터를 실행 폴더에 복사한다. 이후 날짜별 예약을 만들고 매분 공간별 인원·이상·관측·설비·에너지를 처리한다. 센서·정답·설비·에너지는 일별 CSV, 예약·입퇴실·제어·이상은 이벤트 CSV에 기록한다.')
p('aggregate, validate, report는 별도 명령이다. 따라서 원본 생성 완료와 집계·검증 완료는 서로 다른 단계다. manifest의 complete는 생성 루프 완료를 뜻하며 데이터 품질 판정은 validation_report.json에서 확인한다.')
heading('Memory and Failure Handling 메모리와 실패 처리',2)
p('시뮬레이션 상태는 공간별로 유지하고 전체 30일 센서 자료를 적재하지 않는다. 집계는 하루치를 사용하며 검증은 이벤트 조회를 메모리에 보유한다. 기본 계산량은 공간 수×분 수에 비례한다. 생성 루프의 예외는 failed로 기록하고, 강제 종료는 running으로 남을 수 있다. 실행 재개 기능은 없다. 초기 입력 준비 단계 오류는 manifest가 생성되기 전에 발생할 수도 있다.')
source('pipeline/simulator.py · simulate / pipeline/aggregator.py · aggregate / pipeline/validator.py · validate')
# 5 module responsibility first.
newpage();heading('Component Responsibilities 구성 요소 책임',2)
p('표의 경로는 src/aiot_sim/ 기준이다. 데이터 전달은 dataclass와 명시적 dictionary를 함께 사용한다. schemas.py가 CSV 전체를 자동 검증하는 런타임 스키마 엔진인 것은 아니다.',size=9.5)
modules=[
('진입점','__main__.py\ncli.py','CLI 인자','명령 분기·오류 처리','실행 상태','config, pipeline'),
('설정','config.py','TOML·CLI','규칙 로드·입력 검사','cfg dict','전체 엔진'),
('공통 규격','constants.py\nschemas.py','컬럼·기본값','상수·상태 모델 정의','dataclass','engines, writer'),
('실제 호실','catalog.py','고정 호실 목록','63개 ID 생성·확인','rooms.csv','profiles, CLI'),
('가상 프로필','profiles.py','규칙·고정 시드','유형·시설 특성 배정','room_profiles.csv','simulator'),
('난수','random_utils.py','seed·키','SHA 256→독립 RNG','Random','각 엔진'),
('시계','clock.py','날짜·간격','서울 시계 생성','datetime','simulator'),
('외기','engines/\nexternal_environment.py','시각·날짜·seed','공통 외기 생성','외기 dict','environment'),
('예약','engines/\nreservations.py','프로필·일자','비중복 일정·노쇼','예약 rows','occupancy'),
('인원','engines/\noccupancy.py','이전 인원·예약','입퇴실·정원 제한','인원·예약 ID','simulator'),
('환경','engines/\nenvironment.py','X·인원·외기·설비','열·수분·CO₂ 갱신','다음 X','sensors'),
('열·환기','engines/hvac.py\nengines/ventilation.py','모드·프로필','열효과·ACH 계산','계수','environment'),
('빛·소음','engines/lighting.py\nengines/noise.py','시설·인원·외기','조도·소음원 합성','lux·dB(A)','environment')]
table(['모듈','실제 파일 경로','입력','수행 기능','출력','연결'],modules,[19,48,23,29,21,26],size=8.1,caption='Table 1. Component responsibilities input and physical engines.')
source('표의 모든 파일은 실제 패키지에서 확인했다. 빈 __init__.py는 패키지 경계만 정의한다.')
# 6 remaining modules.
newpage();heading('Component Responsibilities 관측과 파이프라인',2)
modules2=[
('관측','engines/sensors.py','X·잡음·fault','측정·양자화·고장','센서 dict','simulator'),
('이상','engines/faults.py','RNG·현재 상태','고장 시작·설비 마스크','fault·설비','sensors, simulator'),
('제어','engines/controller.py','Y·인원·요청 상태','히스테리시스·유지시간','새 요청·변경','simulator'),
('에너지','engines/energy.py','적용 설비·프로필','구성전력·시간 적산','kW·kWh','simulator'),
('실행 조정','pipeline/simulator.py','cfg·마스터','분 단위 상태·I/O 조정','run 폴더','모든 엔진'),
('입출력','pipeline/writer.py','rows·JSON','UTF 8 CSV·JSON 교체','파일','전 파이프라인'),
('집계','pipeline/aggregator.py','일별 raw CSV','평균·Leq·합계','derived','CLI'),
('품질 검사','pipeline/validator.py','raw·truth·events','구조·물리·일관성','validation JSON','CLI, reporter'),
('파일 보고','pipeline/reporter.py','run 폴더','실제 행 수·크기 측정','summary JSON','CLI')]
table(['모듈','실제 파일 경로','입력','수행 기능','출력','연결'],modules2,[19,48,23,29,21,26],size=8.3,caption='Table 2. Component responsibilities observation control and export.')
heading('State Boundaries 상태 경계',2)
p('EnvironmentState는 온도·상대습도·CO₂·조도·소음과 내부 수증기 밀도를 보유한다. FacilityState에는 HVAC 모드, 환기·조명 수준, 설비 고장 상태와 최근 변경 시각이 있다. simulator는 제어기가 유지하는 요청 상태를 복사한 뒤 고장 마스크를 적용해 실제 구간 상태를 만든다.')
p('각 공간에는 sensor_rng, fault_rng, occupancy_rng가 독립적으로 유지된다. 예약은 공간·날짜 키의 별도 스트림을 쓴다. 한 엔진의 난수 소비가 다른 공간의 난수 순서를 바꾸지 않도록 구성했다.')
source('schemas.py / pipeline/simulator.py / random_utils.py')
# 7 Environment.
newpage();heading('4  Simulation Environment 시뮬레이션 환경',toc=True)
p('rooms.csv는 건물·호실과 자료 출처를 표현하고, room_profiles.csv는 같은 room_id에 가상 특성을 연결한다. ID는 공식 시설 코드가 아닌 프로젝트 내부 키다. 층은 호실 표기에서 추정했으며 63개 모두 floor_verified=false다.')
image('room_distribution',width=150,caption='Chart 1. Room distribution. rooms.csv에서 집계한 건물별 공간 수 38 / 12 / 9 / 4.')
table(['가상 유형','공간 수','정원 후보 명','면적 범위 m²'],[['SMALL',25,'4 / 6','12–18'],['MEDIUM',28,'8 / 12','22–36'],['LARGE',10,'16 / 20','42–60']],[40,32,47,47],caption='Table 3. Synthetic room profiles. 정원과 면적은 실제 학교 시설값이 아니다.')
p('프로필은 ID 정렬 후 고정 시드로 유형을 배정하며 기존 CSV가 있으면 재생성하지 않는다. STU-B102A는 SMALL·정원 6명·면적 17m²·09:00–21:00으로 고정한다. 천장 높이는 2.7–3.2m, 부피는 면적×높이다. 모니터·프로젝터·화이트보드 확률은 유형별로 다르며 콘센트는 기본 모두 존재한다.')
heading('Time Configuration 시간 설정',2)
p('기본 기간은 2026-09-01 00:00부터 09-30 23:59까지 연속 30일이다. 내부 적분 1분, 출력 기본 1분, 집계 기본 5분, 시간대 Asia/Seoul, seed 20261102다. 운영시간 외에도 환경·센서는 24시간 기록하고 일반 인원은 0명으로 만든다.')
source('data/master/*.csv / configs/room_profile_rules.toml / configs/simulation.toml / profiles.py')
# 8 Data engine.
newpage();heading('5  Data Generation Engine 데이터 생성 엔진',toc=True)
heading('Time and Reservations 시간과 예약',2)
p('clock.timestamps는 시작 자정부터 하루 1,440개 시각을 만든다. 출력 간격을 바꿔도 simulator의 내부 계산은 1분이다. 예약은 평일 0.75·주말 0.35의 기초 시도 확률에 3시간대 수요 계수를 곱한다. 길이는 30·60·90·120분 중 선택하고 운영시간 내 비중복 일정만 생성한다. 이 확률들은 실측 이용률이 아니다.')
p('생성 시각은 시작 1–72시간 전이며 취소 확률 0.08, 노쇼 확률 0.10을 적용한다. 취소는 생성 시점에 결정된다. start/end는 [시작, 종료) 구간이며, 향후 예측에서는 created_at이 입력 마감 시각 이전인 예약만 이용한다.')
heading('Occupancy Modeling 실제 이용 인원',2)
p('예약 인원과 실제 인원을 구분한다. confirmed 예약은 노쇼가 아니고 0–10분 도착 지연이 지난 뒤에만 점유를 만든다. 실제 인원은 예약 인원에서 0–2명을 줄이되 최소 1명이다. 빈 시간에는 이전 인원에 ±1·±2명 walk in 변화를 적용한다. 종료·폐실과 정원 제한 후 변화량을 입퇴실 이벤트로 기록한다.')
image('workflow',caption='Figure 2. Time step data generation workflow. 관측·구간 기록·다음 상태 갱신의 순서를 구분한다.')
p('센서가 관측하는 환경 X(t)는 직전 적분의 결과이고 인원은 현재 분의 입퇴실을 적용한 값이다. 현재 인원 증가가 CO₂에 미치는 효과는 다음 물리 상태에 반영된다. 현재 명령과 동일 행의 환경값 사이를 즉각적인 원인·결과로 해석하면 안 된다.',size=9.5)
source('clock.py / engines/reservations.py · generate / engines/occupancy.py · update / pipeline/simulator.py')
# 9 thermal humidity.
newpage();heading('6  Environmental Simulation Models 환경 모델',toc=True)
heading('6 1 Temperature Model 온도 모델',2)
p('실내를 하나의 구획으로 보고 외기와의 온도 차이, 공간 열응답, 인원 발열과 냉난방 효과를 1차 갱신식으로 합산한다. 이전 상태를 유지하므로 매분 독립적인 난수 온도를 만드는 방식과 다르다.')
eq('T_{t+1} = T_{t} + Δt [ k(T_{out} − T_{t}) + n q_{person} + q_{HVAC} ]')
p('T는 °C, Δt는 분, k는 min⁻¹, n은 명이다. qperson=0.012°C·명⁻¹·min⁻¹, qHVAC는 냉방 −0.10°C/min·난방 +0.10°C/min·정지 0이다. k는 공간 프로필의 0.003–0.009 범위다. 모두 실측 보정되지 않은 가정이다. 정밀 건물 열수지나 HVAC 성능 모델로 해석하지 않는다.')
heading('6 2 Humidity Model 습도 모델',2)
p('절대습도에 해당하는 수증기 밀도 A(g/m³)를 내부 상태로 보유하고, 환기로 외기 수증기량과 혼합한 뒤 인원 수분 발생을 더한다. 이때 상대습도는 새 온도에 따라 달라지므로 온도와 독립적이지 않다.')
eq('A_{sat}(T) = 216.7 × 6.112 × exp[17.67T / (T + 243.5)] / (273.15 + T)')
eq('A_{out} = A_{sat}(T_{out}) RH_{out} / 100')
eq('A* = A_{out} + (A_{t} − A_{out}) exp(−a Δt/60) + n m Δt/V')
eq('A_{t+1} = clip(A* × d_{cool}, 0, A_{sat}(T_{t+1}))')
eq('RH_{t+1} = 100 A_{t+1} / A_{sat}(T_{t+1})')
p('a는 ACH(h⁻¹), V는 m³, m=0.5g·명⁻¹·min⁻¹이다. dcool은 냉방 시 exp(−0.002Δt), 나머지는 1이다. 포화 초과분은 수치적으로 제거해 0–100%를 유지한다. 위 포화식·제습 인자와 발생계수는 현재 코드의 근사식이며 외부 표준 검증을 완료한 값으로 제시하지 않는다.')
source('engines/environment.py · evolve, saturation_g_m3 / engines/hvac.py · temperature_effect / configs/environment_rules.toml')
# 10 co2lightnoise.
newpage();heading('Environmental Models CO₂ 조도와 소음',2)
heading('6 3 CO₂ Concentration 질량보존 모델',2)
p('CO₂는 완전 혼합 구획의 발생·제거 질량수지를 사용한다. 사람의 발생량을 공간 부피로 나누므로 같은 인원이라도 작은 공간에서 더 빠르게 증가한다. 환기가 커지면 외기 농도로 더 빨리 접근한다.')
eq('a = a_{off} + (a_{on} − a_{off}) ventilation_level')
eq('S = n G × 10^{6} / V')
eq('C_{t+1} = C_{out} + (C_{t} − C_{out}) r + (S/a)(1 − r),   r = exp(−aΔt/60)')
p('C는 ppm, V는 m³, G=0.018m³·명⁻¹·h⁻¹, S는 ppm/h이다. a는 공기교환율 h⁻¹이며 Δt/60으로 시간을 맞춘다. 코드는 1−exp(−x)를 −expm1(−x)로 계산해 작은 x에서의 반올림 손실을 줄인다. a≤10⁻⁹이면 Cnext=C+SΔt/60의 발생량 적분만 적용한다.')
heading('6 4 Illuminance 조도',2)
eq('L = 700 d(t) exposure_factor + 450 lighting_level')
p('L은 lux다. d(t)=max(0, sin[π(hour−6)/12])이므로 자연광은 06–18시에만 존재한다. 공간별 자연광 계수와 조명 수준(현재 0/1)을 적용한다. 밝기 계수 700·450lux는 가정이다.')
heading('6 5 Noise 소음',2)
eq('L_{total} = 10 log_{10}[Σ 10^{L(i)/10}]')
p('독립 소음원을 에너지로 합성한다. 기본 소음과 외부 소음−25dB, 인원이 있을 때 36+10log₁₀(n)+4×activity, 환기 33dB(A), HVAC 35dB(A)를 합한다. activity는 공간별로 0.2–1.5의 고정 난수이며 시간에 따라 바뀌는 활동 유형 분류기는 구현하지 않았다. 복잡한 음향장·차음 모델은 아니다.')
source('engines/environment.py / ventilation.py / lighting.py / noise.py / external_environment.py')
# 11 Environmental chart.
newpage();heading('Environmental Time Series 실제 생성 예시',2)
p('Chart 2는 full-30d 실행의 STU-B102A, 2026-09-01 1분 자료다. 도표는 실행 CSV를 직접 읽었으며 관측 결과를 재현하도록 별도로 계산한 가상 곡선이 아니다. 검은 선은 내부 정답, 회색 파선은 센서값이다. 서로 다른 단위는 독립 패널로 표현했다.',size=9.5)
image('environment_series',caption='Chart 2. Environmental time series from a recorded run. STU-B102A / 2026-09-01 / Asia/Seoul.')
p('이용 인원은 CO₂·발열·수분·소음에 함께 영향을 준다. 조명과 HVAC는 환경값과 에너지를 연결한다. 첫날은 모든 공간이 공통 초기값에서 시작하므로 초반 구간을 실제 일상 운영의 정상상태로 단정하지 않는다.',size=9.5)
source('full-30d/raw/sensors_1min/sensor_readings_2026-09-01.csv 및 truth/environment_truth_1min 동 날짜 파일')
# 12 Sensor.
newpage();heading('7  Sensor Measurement and Fault Modeling',toc=True)
p('센서 관측과 고장 모델링',size=11,color='777777',after=10)
eq('y = resolution × round[(x + ε)/resolution],   ε ~ Normal(0, σ^{2})')
p('센서별 잡음 σ는 온도 0.15°C, 습도 0.7%, CO₂ 12ppm, 조도 4lux, 소음 0.5dB(A), 인원 0명이다. 분해능은 각각 0.1 / 0.1 / 1 / 1 / 0.1 / 1이다. 양자화 후 조도·소음은 0 이상으로 제한하며 습도는 관측 잡음으로 0–100% 밖에 나갈 수 있다.')
table(['유형','관측 또는 물리 상태에 미치는 영향','실제 건수'],[['missing','CO₂ 관측을 빈 칸으로 저장; 내부 상태 유지',531],['spike','CO₂ 관측 +1,200ppm; 1분',257],['stuck','시작 시점 내부 CO₂ 값으로 관측 고정',249],['bias','시작 분부터 +4ppm/분 오프셋 누적',256],['ventilation_failure','실제 환기 수준 0으로 마스킹',286],['hvac_failure','실제 HVAC off로 마스킹',297],['high_occupancy','운영시간 내 정원 100% 점유; 초과 없음',273]],[42,104,20],size=9,caption='Table 4. Injected fault events. full-30d의 2,149건을 직접 집계했다.')
image('sensor_bias',caption='Chart 3. Recorded sensor bias example. HEA-422 / 2026-09-01 / 00:32–00:50 미만.')
p('위 예시의 bias는 일정한 상수 편향이 아니라 경과 분에 비례하는 drift 형태다. 고장 동안 실제 CO₂와 관측값이 분리된다. 현재 센서 고장 네 종류는 CO₂에만 적용하고 공간당 동시에 하나의 이상만 주입한다. truth와 anomaly_events는 평가 전용으로 보관한다.',size=9.5)
source('engines/sensors.py · observe / faults.py · maybe_start / truth/anomaly_events.csv · A-HEA-422-32')
# 13 Controls.
newpage();heading('8  Facility Control and Energy Simulation',toc=True)
p('설비 제어와 에너지 시뮬레이션',size=11,color='777777',after=10)
table(['설비','가동·정지 규칙 가정','적용 특성'],[['HVAC','냉방 >26°C / 냉방 종료 <24.5°C\n난방 <20°C / 난방 종료 >21.5°C','off / cooling / heating'],['환기','가동 >1,000ppm / 정지 <750ppm','level 0 또는 1'],['조명','관측 <350lux이면 가동\n정지 기준 >400+450×현재 수준 lux','level 0 또는 1'],['공통','인원 0명이면 정지 요청\n설비별 마지막 변경 이후 최소 5분 유지','채널 결측 시 해당 판단 유지']],[26,98,42],size=9,caption='Table 5. Implemented controller policy. 공인 건강·안전 기준이 아닌 가정값이다.')
image('feedback',caption='Figure 3. Environmental control feedback loop. 현재 관측과 다음 구간 명령을 구분한다.')
heading('Control Timing 제어 명령의 시간 의미',2)
p('시각 t에서 관측 Y(t)를 얻고 새 요청 F(t+1)을 결정하지만, 같은 반복문의 적분은 기존 적용 설비 F(t)로 X(t+1)을 만든다. 새 요청은 다음 분의 구간 [t+1,t+2)에 적용되고, 그 효과가 누적된 환경은 X(t+2) 관측에서 나타난다. 제어 요청 CSV와 동일 시각의 환경 CSV를 즉시 효과로 해석하면 안 된다.')
p('설비 고장은 적용 상태를 off로 덮어쓰지만 요청 상태는 유지될 수 있다. applied_successfully는 요청 시점의 고장 차단 여부를 나타내며 실행 성공의 독립 확인 응답이 아니다. 실제 구간 상태는 facility_states CSV가 기준이다.')
source('engines/controller.py · decide / pipeline/simulator.py · applied, new, environment.evolve 순서')
# 14 Energy.
newpage();heading('Energy Consumption 전력과 소비 에너지',2)
eq('P_{total} = P_{HVAC} + P_{ventilation} + P_{lighting} + P_{standby}')
eq('P_{HVAC} = profile_hvac_power_kw × 0.8 × hvac_on')
eq('E_{interval} = Σ P_{minute} / 60')
p('P는 kW, E는 kWh다. 환기와 조명은 프로필 전력×수준, 대기전력은 상시 기본 부하다. 1분 출력은 E=P/60이며 N분 출력은 내부 1분 에너지를 합산하고 전력은 N분 평균으로 저장한다. enable_energy_model=false이면 에너지 파일의 구성전력과 적산값은 0이다.')
image('power_occupancy',caption='Chart 4. Recorded power and occupancy. STU-B102A / 2026-09-01. 단순한 인원 비례 부하 모델은 아니다.')
p('full-30d 전체 소비 에너지 합계는 17,898.357645kWh다. 이는 63개 가상 프로필·가상 운영 상태의 합성 결과이며 실제 학교 전력 사용량이 아니다. HVAC의 COP, 기동 전류, 비선형 부분부하와 전기요금은 모델링하지 않는다.')
source('engines/energy.py · energy / pipeline/simulator.py · energy_sum / reports/validation_report.json')
# 15 Data storage.
newpage();heading('9  Data Structure and Specifications',toc=True)
p('데이터 구조와 공통 규격',size=11,color='777777',after=10)
image('storage',caption='Figure 4. Data storage architecture. 학습용 관측과 평가용 정답을 별도 경로로 보관한다.')
table(['run 폴더 기준 경로','파일명 또는 규칙','행 수 전체'],[['inputs/','rooms.csv / room_profiles.csv','각 63'],['raw/sensors_1min/','sensor_readings_YYYY-MM-DD.csv','2,721,600'],['raw/facility_states_1min/','facility_states_YYYY-MM-DD.csv','2,721,600'],['raw/energy_usage_1min/','energy_usage_YYYY-MM-DD.csv','2,721,600'],['events/','reservations.csv / occupancy_events.csv','9,803 / 25,716'],['events/','control_actions.csv','63,562'],['truth/environment_truth_1min/','environment_truth_YYYY-MM-DD.csv','2,721,600'],['truth/','anomaly_events.csv','2,149'],['derived/sensors_5min/','sensor_readings_YYYY-MM-DD.csv','544,320'],['derived/energy_5min/','energy_usage_YYYY-MM-DD.csv','544,320']],[55,76,35],size=8.6,caption='Table 6. Actual output families. 일별 파일은 각 30개이며 실행 CSV 총 186개다.')
p('실행 루트는 data/runs/full-30d/다. CSV 총 크기는 1,061,294,892bytes이며 입력 스냅샷을 포함한다. 원본 마스터는 data/master/에 별도로 존재한다. 시계열 기본 키는 timestamp+room_id, 예약 키는 reservation_id다. UTF 8·헤더 포함이며 boolean은 true/false, 센서 결측은 빈 칸이다. 단위와 개별 컬럼은 Appendix B를 따른다.',size=9.5)
source('pipeline/simulator.py / reports/summary.json / 실제 CSV 헤더')
# 16 aggregation sample.
newpage();heading('Raw and Aggregated Data 원본과 집계',2)
p('1분 센서는 timestamp, room_id와 온도·습도·CO₂·조도·소음·인원을 가진다. 5분 창 09:00은 [09:00,09:05), 즉 09:00–09:04 표본을 포함한다. 집계 파일의 timestamp는 창 시작이지 데이터가 이용 가능해지는 시각이 아니다.')
table(['변수','5분 실제 집계 컬럼과 처리'],[['온도·습도·조도','*_mean; 유효 관측 산술평균'],['CO₂','co2_ppm_mean / co2_ppm_max / co2_ppm_last'],['인원','occupancy_count_last / occupancy_count_max'],['소음','noise_leq_dba = 10log₁₀(mean(10^(L/10)))'],['결측','변수별 *_missing_ratio = 빈 칸 수 / 전체 표본 수'],['에너지','interval_energy_kwh 합; mean_power_kw 평균']],[35,131],size=9.2,caption='Table 7. Implemented aggregation rules.')
p('마지막값은 마지막 시점이 결측이면 빈 칸이다. 모두 결측이면 평균·최댓값·Leq도 빈 칸이다. Leq는 유효 표본만의 등가 수준이므로 결측률과 함께 해석한다. dB 값을 단순 산술평균하지 않는다.')
rows=[x for x in F['day']['sensors'] if '09:00:00' in x['timestamp'] or '09:01:00' in x['timestamp'] or '09:02:00' in x['timestamp']]
table(['시각 KST','온도 °C','RH %','CO₂ ppm','lux','dB(A)','인원'],[[x['timestamp'][11:16],x['temperature_c'],x['humidity_pct'],x['co2_ppm'],x['illuminance_lux'],x['noise_dba'],x['occupancy_count']] for x in rows],[28,23,23,28,22,23,19],size=9,caption='Table 8. Actual CSV sample. STU-B102A / 2026-09-01, 3개 행만 발췌했다.')
heading('Metadata 메타데이터',2)
p('manifest.json은 실행 규칙·시드·대상 공간·입력 프로필 SHA 256·완료 상태를 보유한다. aggregation.json은 집계 간격·행 수, validation_report.json은 품질 판정·오류·경고, summary.json은 파일별 경로·bytes·rows를 보유한다. 비기본 출력·집계 간격에도 폴더명 _1min / _5min은 유지되므로 실제 간격은 메타데이터를 우선 확인한다.')
source('pipeline/aggregator.py · aggregate / pipeline/writer.py / reports/*.json')
# 17 ML.
newpage();heading('ML Integration 머신러닝 연동',2)
table(['시나리오 담당','공통 입력','결합 시 주의'],[['1 개인 환경 추천\n김시환','센서 환경·인원 + 별도 사용자 선호','선호 수집기는 별도 개발'],['2 목적 기반 추천\n김정훈','센서 + profiles + 예약·운영시간','실제 점유와 예약 가능성 구분'],['3 혼잡도 예측\n최선강','과거 센서·입퇴실·당시 알려진 예약','30분 미래 정답의 경계 누출 방지'],['4 이상 탐지\n이민재','센서·시설·에너지','truth·고장 여부를 특징에 넣지 않기'],['5 자동 환경 제어\n김시환·김정훈','분 단위 관측·인원·설비·외기','외기는 CSV가 아닌 엔진에서 재계산'],['6 에너지 최적화\n최선강·이민재','에너지·시설·점유·가상 프로필','kW와 kWh 의미 구분']],[45,73,48],size=9,caption='Table 9. Scenario input contracts. ML 모델 자체는 이번 패키지에 구현되지 않았다.')
heading('Temporal Split 시간 기준 분할',2)
p('기본 제안은 train 9월 1–21일, validation 22–25일, test 26–30일이다. 미래 30분 정답을 만들 때 다음 분할로 넘어가는 마지막 30분 표본을 제외한다. 스케일러·결측 대체값 등 학습 파라미터는 train에서만 추정한다. 09:00 집계 창은 09:05 이후에만 이용한다.')
p('예약은 created_at≤input_data_end_time인 기록만 사용한다. is_no_show는 합성 사후 특성이다. equipment_fault_active도 이상 정답에 직접 가까운 특징이므로 모델 목적에 따라 배제해야 한다. 외기 CSV는 없으며 configs·seed·timestamp로 external_environment.outdoor를 재계산할 수 있다.')
heading('Future Model Output 향후 JSON 계약',2)
p('공통 필수 메타데이터는 scenario_id, model_name, model_version, generated_at, room_id, input_data_end_time이다. prediction_target_time, predicted_label, score, confidence, reason_codes는 시나리오별 선택 필드다. score와 confidence의 의미·범위는 모델별로 정의하며 서로 같은 척도로 비교하지 않는다. 이 규격은 문서화된 향후 인터페이스이며 실제 추론 API는 없다.')
source('docs/interface_contracts.md / engines/reservations.py · visible_reservations / 실제 CSV 컬럼')
# 18 Validation.
newpage();heading('10  Data Validation and Reproducibility',toc=True)
p('검증과 재현성',size=11,color='777777',after=10)
p('검증기는 정확한 63개 ID·건물별 수·프로필 일치, 연속 시각·시간대·일별/전체 행 수, 입퇴실 누적·정원·운영시간, 실제 RH·CO₂·조도, 센서 이상 레이블과 에너지 구성합·적산·집계 에너지 보존을 검사한다. 센서 편차 감사 허용폭은 8σ+분해능이다. 이는 생성기 품질 점검용이며 극히 드문 정상 잡음의 오탐 가능성이 이론적으로 0인 것은 아니다.')
table(['실행 항목','검사 목적','확인 결과','근거'],[['pytest','단위·통합 테스트','24 passed / 실패 0','pytest-results.xml'],['smoke-single','1공간 1일','1,440 / 집계 288','validation_report'],['smoke-all','63공간 1일','90,720 / 집계 18,144','validation_report'],['full-30d','63공간 30일','2,721,600 / 집계 544,320','validation_report'],['전체 품질 판정','원본·정답·에너지 일관성','valid=true / 오류 0 / 경고 0','full-30d/reports/'],['Ruff','코드·포맷 검사','통과 / 47파일 포맷 일치','ruff-results.txt'],['반복 실행','1공간 1일 CSV 내용','12개 SHA 256 동일','reproducibility.json'],['공간 순서 변경','2공간 순서 반전','전체 CSV 바이트 일치','test_reproducibility']],[31,49,53,33],size=8.6,caption='Table 10. Actual verification results. 저장된 테스트·보고서와 테스트 코드를 대조했다.')
heading('Reproducibility Scope 재현성의 범위',2)
p('random_utils.rng는 seed와 키를 UTF 8로 결합한 SHA 256의 앞 16바이트를 정수 시드로 바꿔 독립 Random을 만든다. 실행 현재 시각·Python hash()에 의존하지 않는다. 동일 코드·설정·프로필·실행 환경에서 내용 재현성을 검증했다. 30일 전체를 두 번 생성하거나 다른 Python 버전까지 바이트 일치를 검증한 것은 아니다.')
p('기록된 pytest 시간은 11.00초이며 이는 테스트 실행 시간이지 30일 생성 성능 벤치마크가 아니다. 품질 판정은 물리 모델의 실측 타당성을 검증하지 않는다. 집계 평균·Leq는 단위 테스트로 확인하지만 전체 검증기가 모든 집계 평균을 원본에서 다시 계산해 비교하는 것은 아니다.')
source('verification/pytest-results.xml / verification-pytest.log / verification/ruff-results.txt / reports/validation_report.json')
# 19 Usage.
newpage();heading('11  Using the Simulator 사용 방법',toc=True)
p('확인된 시뮬레이터 실행 환경은 macOS의 Python 3.14.7이다. pyproject.toml은 Python 3.11 이상을 요구하며 핵심 실행 의존성은 표준 라이브러리뿐이다. 개발 도구는 pytest·Ruff, 패키징은 setuptools다. 문서 생성 도구의 의존성과 시뮬레이터 의존성을 구분한다.')
heading('Installation 설치',2)
code("python3 -m venv .venv\nsource .venv/bin/activate\npython -m pip install -e '.[dev]'\npython -m aiot_sim init")
p('VS Code에서 프로젝트 폴더를 열고 해당 폴더의 터미널에서 실행한다. 로컬 환경에서 editable 설치 경로 문제를 보완하기 위해 aiot_sim → src/aiot_sim 링크도 존재한다. 다른 폴더에서 실행할 때는 명령 앞에 --root /absolute/project/path를 지정한다.',size=9.5)
heading('Configuration and Master 설정과 마스터',2)
p('simulation.toml은 기간·출력 간격·시드·활성 기능을, 나머지 다섯 TOML은 프로필·환경·수요·고장·설비 정책을 관리한다. 프로필 생성 시 운영시간별 override를 적용할 수 있다. 기존 프로필은 자동 재생성하지 않으므로 변경 전 백업·버전 관리를 수행한다.')
code('python -m aiot_sim generate-master\npython -m aiot_sim generate-profiles')
heading('Run Aggregate Validate 실행과 확인',2)
code('python -m aiot_sim simulate --room-id STU-B102A \\\n  --days 1 --run-id team-demo\npython -m aiot_sim aggregate --run-id team-demo --minutes 5\npython -m aiot_sim validate --run-id team-demo\npython -m aiot_sim report --run-id team-demo')
p('전체 30일은 simulate --days 30 --run-id new-30d로 생성한다. 기존 full-30d는 이미 있으므로 덮어쓸 수 없다. simulate는 --start-date, --days, --seed, --step-minutes를 지원하고 --room-id는 반복 지정할 수 있다. 출력 간격은 1,440의 약수, 집계 간격은 출력 간격의 배수이며 기본 집계 설정과도 맞아야 한다. 검증 실패 종료코드는 1, 잘못된 입력·파일 오류는 2다.',size=9.5)
source('cli.py · main / config.py · load / pyproject.toml / docs/execution_guide.md')
# 20 specifications.
newpage();heading('12  Technical Specifications 기술 사양',toc=True)
spec=[('Project Name','Smart Campus AIoT Shared Environmental Simulator'),('Software / Document Version','0.1.0 / 1.0'),('Simulation Type','오프라인 합성 다중 공간 환경 시계열'),('Programming Language','Python; 핵심 실행은 표준 라이브러리'),('Python Version','요구 ≥3.11 / 확인한 실행 3.14.7'),('Execution Environment','macOS / VS Code 터미널 / 로컬 .venv'),('Buildings and Rooms','STU 38 + LIB 12 + WON 9 + HEA 4 = 63'),('Synthetic Profiles','SMALL 25 / MEDIUM 28 / LARGE 10'),('Simulation Duration','2026-09-01 00:00–09-30 23:59 / 연속 30일'),('Integration and Output','내부 1분 / 기본 출력 1분'),('Aggregation','기본 5분 / 좌측 포함·우측 제외 창'),('Environmental Variables','온도 °C / RH % / CO₂ ppm / 조도 lux / 소음 dB(A)'),('Occupancy and Facilities','인원·HVAC 모드·환기 수준·조명 수준·설비 고장'),('Data Formats','CSV 데이터 / JSON 보고서 / TOML 규칙'),('Timezone and Seed','Asia/Seoul +09:00 / 20261102'),('Output Structure','일별 raw·truth·derived + 단일 이벤트 CSV'),('Raw Sensor / Aggregated Rows','2,721,600 / 544,320'),('CSV Count and Size','186개 / 1,061,294,892 bytes, 입력 스냅샷 포함'),('Validation','24개 pytest 통과 / 전체 품질 오류 0·경고 0'),('Reproducibility','1공간 1일 12 CSV 동일 / 2공간 순서 변경 통과'),('Hardware and ML','실제 하드웨어·ML 학습·추론 API 없음')]
table(['Specification','Verified implementation'],spec,[58,108],size=9.4,caption='Table 11. Technical specifications. 가정값과 실제 생성 결과의 범위를 함께 표시했다.')
source('pyproject.toml / configs/*.toml / 마스터 / full-30d/reports/*.json / 검증 로그')
# 21 Limitations.
newpage();heading('13  Limitations and Future Development',toc=True)
p('한계와 향후 개발',size=11,color='777777',after=12)
heading('Synthetic Data 합성 데이터의 적용 범위',2)
p('이 모델은 실측으로 보정한 디지털 트윈이 아니다. 사용자 제공 호실 목록 이외의 정원·면적·설비·운영시간·수요·환경·고장 계수는 모두 가정이며, 실제 시설·날씨·행동 분포를 재현한다고 검증되지 않았다. 층수도 추정값이다. 합성 데이터에서 높은 F1 score가 나오더라도 실제 학교의 일반화 성능으로 해석할 수 없다.')
heading('Physical and Behavioral Models 물리와 행동의 단순화',2)
p('완전 혼합 단일 구획을 가정하며 복도·문·창문 공기 교환, 건물 축열, 세밀한 열획득과 음향장을 분리하지 않는다. 초기 조건은 공통값이고 외기는 단순 일주기 합성 모델이다. 예약 취소는 생성 시 확정되고 변경 이력이 없다. 실제 사람이나 개인정보는 생성하지 않는다.')
heading('Current Engineering Boundaries 구현의 경계',2)
p('센서 고장 주입은 CO₂만 지원하며 동시에 한 가지 이상만 활성화한다. 고밀도 레이블은 주입 구간이지 모든 환경 임계 초과의 사후 정답은 아니다. 공간 활동 강도는 고정이며 시간별 활동 유형은 없다. 조명은 0/1 정책이고 조명 제어의 450lux 보정값은 코드에 고정되어 있어 환경 조명 계수만 바꿀 때 두 로직이 불일치할 수 있다. 전력 모델에는 COP나 비선형 부하가 없다.')
p('전체 센서 데이터는 스트리밍하지만 날짜별 집계는 하루치, 검증은 이벤트 조회를 메모리에 유지한다. 장기간·다캠퍼스 확장에는 저장·조회 구조 변경이 필요하다. 실행 재개·실시간 전송·하드웨어 응답 확인·실제 ML·챗봇은 구현되지 않았다.')
heading('Future Work 다음 개발 단계',2)
p('먼저 승인된 실제 시설 메타데이터와 익명 환경 관측을 확보해 계수를 보정한다. 다음으로 시간 분할과 기준모델을 고정하고 실측 외부 테스트 세트에서 평가한다. 이후 복수 센서 고장·예약 변경 이력·복합 고장·MQTT 또는 HTTP 전송·실제 센서·ML/AI 추천 연동을 단계적으로 추가할 수 있다. 이 항목은 향후 방향이며 현재 기능이 아니다.')
source('실제 소스 흐름 / docs/known_limitations.md / docs/interface_contracts.md')
# 22/23 Appendix A exact 63 rows.
profiles={p['room_id']:p for p in F['profiles']};rooms=F['rooms']
for part,items in enumerate([rooms[:32],rooms[32:]]):
 newpage();heading('Appendix A  Room Master Data 공간 목록' if part==0 else 'Room Master Data 공간 목록 계속',toc=part==0,level=1 if part==0 else 2)
 p('호실·건물은 사용자 제공 목록이다. 층은 추정값이며 모든 floor_verified는 false다. 유형·정원은 가정값이다. room_id는 공식 시설 코드가 아니다.',size=9.2)
 table(['room_id','건물','호실','추정 층','가상 유형','가상 정원'],[[room['room_id'],room['building_name'],room['room_number'],room['floor'],profiles[room['room_id']]['room_type'],profiles[room['room_id']]['capacity']] for room in items],[42,29,23,20,31,21],size=8.8,compact=True,caption=f'Table {12+part}. Complete room master records {1 if part==0 else 33} to {32 if part==0 else 63}.')
 source('data/master/rooms.csv와 room_profiles.csv를 room_id로 결합했다. 누락·중복 없이 총 63개.')
# Appendix B Dictionary: all field names, compact explicit type/unit/range/null contracts.
# Short, code-aligned definitions rather than reproducing legacy wording errors.
info={
'room_id':('str','내부 공간 키; 결측 불가'), 'timestamp':('ISO 8601','+09:00; 시점/구간 시작; 결측 불가'),
'building_code':('enum','STU/LIB/WON/HEA; 사용자 자료'), 'building_name':('str','실제 건물명; 사용자 자료'),
'room_number':('str','사용자 제공 호실 표기'), 'floor':('str','B1/2/4/6/7; 호실에서 추정'), 'floor_verified':('bool','모두 false; 독립 확인하지 않음'),
'source_type':('str','user_provided_facility_screenshots'), 'source_url':('URL','학교 시설예약 목록 URL'), 'source_checked_date':('date','2026-11-02; 사용자 자료 기준일'), 'notes':('str','추가 확인 사항; 빈 문자열 허용'),
'room_type':('enum','SMALL/MEDIUM/LARGE; 합성 유형'), 'capacity':('int 명','유형별 4/6, 8/12, 16/20; 양수'), 'area_m2':('float m²','유형별 12–18, 22–36, 42–60; 합성'),
'ceiling_height_m':('float m','2.7–3.2; 합성'), 'volume_m3':('float m³','면적×높이; 양수'),
'opening_time':('HH:MM','기본 09:00 포함; 합성'), 'closing_time':('HH:MM','기본 21:00 제외; 합성'),
'ventilation_off_ach':('float h⁻¹','0.15–0.4; 합성'), 'ventilation_on_ach':('float h⁻¹','2–5; 합성'),
'noise_baseline_dba':('float dB(A)','28–36; 합성'), 'thermal_response_factor':('float min⁻¹','0.003–0.009; 합성'), 'daylight_exposure_factor':('float','0.1–0.8; 합성'),
'profile_source':('str','synthetic_assumption'), 'profile_version':('str','v0.1; 프로필 버전'),
'hvac_mode':('enum','off/cooling/heating; 실제 적용 상태'), 'hvac_on':('bool','실제 구간 HVAC 가동'), 'ventilation_on':('bool','실제 구간 환기 가동'), 'ventilation_level':('float','0/1; 환기 적용 수준'), 'lighting_on':('bool','실제 구간 조명 가동'), 'lighting_level':('float','0/1; 조명 적용 수준'), 'equipment_fault_active':('bool','설비 고장 주입 중; 누출 특징 주의'),
'hvac_power_kw':('float kW','프로필 정격 또는 구간 평균; ≥0'), 'ventilation_power_kw':('float kW','프로필 정격 또는 구간 평균; ≥0'), 'lighting_power_kw':('float kW','프로필 정격 또는 구간 평균; ≥0'), 'standby_power_kw':('float kW','대기전력; ≥0'), 'total_power_kw':('float kW','구성전력 네 항목 합; ≥0'), 'interval_energy_kwh':('float kWh','표시 구간의 에너지 합; ≥0'), 'mean_power_kw':('float kW','집계 창 평균 전력; ≥0'),
'reservation_id':('str','예약 키; 비예약 입퇴실에서만 빈 값'), 'created_at':('ISO 8601','예약 가시성 시작; start_time 이전'), 'start_time':('ISO 8601','예약/이상 시작 포함'), 'end_time':('ISO 8601','예약/이상 종료 제외'), 'reserved_count':('int 명','1–capacity; 예약 인원'), 'status':('enum','confirmed/cancelled; 생성 시 확정'), 'is_no_show':('bool','합성 사후 특성; 미래 입력 금지'),
'event_id':('str','이벤트 고유 식별자'), 'event_type':('enum','entry/exit'), 'count_delta':('int 명','입실 양수·퇴실 음수; 0 없음'), 'resulting_occupancy':('int 명','적용 후 0–capacity'),
'action_id':('str','공간·분·설비별 요청 키'), 'controller_type':('str','rule_based'), 'target_device':('enum','hvac/ventilation/lighting'), 'previous_state':('str','이전 요청; mode 또는 True/False'), 'requested_state':('str','새 요청; mode 또는 True/False'), 'action_reason':('str','observation_target_and_occupancy'), 'applied_successfully':('bool','요청 시 고장 차단 여부; 확인 응답 아님'),
'anomaly_type':('enum','missing/spike/stuck/bias + 설비·고밀도'), 'affected_variable':('enum','co2_ppm/ventilation/hvac/occupancy_count'), 'severity':('str','moderate; 가정 심각도'), 'cause':('str','synthetic_injection'), 'is_sensor_fault':('bool','센서 4종 true; 나머지 false'), 'sample_count':('int','집계 창 표본 수; 기본 5'),
}
for name in ['monitor','projector','whiteboard','outlets']:info['has_'+name]=('bool','가상 보유 여부; 실제 시설 확인값 아님')
units={'temperature_c':'°C','humidity_pct':'%','co2_ppm':'ppm','illuminance_lux':'lux','noise_dba':'dB(A)','occupancy_count':'명'}
for name,u in units.items():
 desc={'temperature_c':'관측 온도; 결측 허용','humidity_pct':'관측 RH; 잡음으로 범위 밖 가능','co2_ppm':'관측 CO₂; 고장으로 편차 가능','illuminance_lux':'관측 조도; ≥0; 결측 허용','noise_dba':'관측 소음; ≥0; 로그 단위','occupancy_count':'관측 인원; 기본 0–capacity'}[name]
 info[name]=('int '+u if name=='occupancy_count' else 'float '+u,desc)
 true_desc={'humidity_pct':'실제 RH 0–100','co2_ppm':'실제 CO₂ >0','illuminance_lux':'실제 조도 ≥0','noise_dba':'실제 소음 dB(A)','occupancy_count':'실제 인원 0–capacity','temperature_c':'실제 온도'}[name]
 info['true_'+name]=('int '+u if name=='occupancy_count' else 'float '+u,true_desc+'; 결측 없음·평가 전용')
 info[name+'_missing_ratio']=('float','0–1; 빈 관측 수/행 수')
 info[name+'_mean']=('float '+u,'결측 제외 평균; 전부 결측이면 빈 칸')
 for suffix in ['max','last']:info[name+'_'+suffix]=('int '+u if name=='occupancy_count' else 'float '+u,('유효값 최대; 전부 결측이면 빈 칸' if suffix=='max' else '마지막 시점 값; 해당 값 결측이면 빈 칸'))
info['noise_leq_dba']=('float dB(A)','유효 소음 에너지 평균; 전부 결측 시 빈 칸')
headers=F['headers']
def keymatch(needle):return next(k for k in headers if needle in k)
groups=[('Master Data 마스터',[keymatch('data/master/rooms'),keymatch('data/master/room_profiles')]),
 ('Raw and Truth 원본과 정답',[keymatch('raw/sensors_1min'),keymatch('raw/facility_states'),keymatch('raw/energy_usage'),keymatch('truth/environment_truth')]),
 ('Events 이벤트',[keymatch('events/reservations'),keymatch('events/occupancy'),keymatch('events/control'),keymatch('truth/anomaly')]),
 ('Aggregated Data 집계',[keymatch('derived/sensors'),keymatch('derived/energy')])]
for part,(title,paths) in enumerate(groups):
 newpage();heading('Appendix B  Data Dictionary 데이터 사전' if part==0 else 'Data Dictionary '+title,toc=part==0,level=1 if part==0 else 2)
 p('별도 표시가 없으면 결측 불가다. 동적 값은 모두 합성 데이터다. 센서 채널은 빈 칸을 허용하나 현재 결측 주입은 CO₂만 지원한다. 필드명은 실제 CSV 헤더와 대조했다.',size=8.7,after=5)
 for ki,path in enumerate(paths):
  short=path.replace('data/runs/full-30d/','').replace('data/master/','')
  short=short.replace('raw/','').replace('truth/','').replace('derived/','').replace('events/','')
  short=re.sub(r'_2026-09-\d\d','_YYYY-MM-DD',short)
  rows=[]
  for name in headers[path]:
   typ,desc=info[name];rows.append((name,typ,desc))
  table(['컬럼명','자료형 단위','의미 범위 결측'],rows,[65,27,74],size=8.3,compact=True,caption=f'Table {14+sum(len(g[1]) for g in groups[:part])+ki}. {short}')
# References final.
newpage();heading('Appendix C  References 참고 자료',toc=True)
heading('Project Evidence 프로젝트 근거',2)
for text in [
 'P1  src/aiot_sim/ 전체 29개 Python 모듈. 본문 수식과 실행 순서는 실제 함수의 계산 순서를 기준으로 작성했다.',
 'P2  configs/의 6개 TOML과 data/master/의 두 CSV. 공간·수치·제어 기준의 출처다. 수치는 검증된 외부 기준이 아니라 합성 가정이다.',
 'P3  data/runs/full-30d/reports/manifest.json, validation_report.json, aggregation.json, summary.json. 실제 생성·검증 규모의 근거다.',
 'P4  data/runs/full-30d/raw/와 truth/의 2026-09-01 CSV. Chart 2–4와 CSV 샘플의 원본이다. 이벤트 근거는 truth/anomaly_events.csv다.',
 'P5  tests/unit/, tests/integration/, verification/pytest-results.xml, verification-pytest.log, verification/ruff-results.txt, data/runs/reproducibility.json.',
 'P6  docs/의 기존 9개 기술 문서와 README.md, pyproject.toml. 코드와 충돌할 경우 실제 코드를 우선했다. 전체 원본 해시는 문서 assets/source_hashes_before.json에 보존한다.'
]:p(text,size=9.2,after=7)
heading('External References 실제 참고한 외부 자료',2)
refs=[('R1','선문대학교 시설예약 시스템','https://sisul.sunmoon.ac.kr/Page/Facilities/Apply_list.aspx?sgubun=H'),('R2','Python 3.14 random 및 hashlib','https://docs.python.org/3.14/library/random.html\nhttps://docs.python.org/3.14/library/hashlib.html'),('R3','Python 3.14 csv 및 tomllib','https://docs.python.org/3.14/library/csv.html\nhttps://docs.python.org/3.14/library/tomllib.html'),('R4','Python 3.14 zoneinfo','https://docs.python.org/3.14/library/zoneinfo.html'),('R5','pytest 공식 문서','https://docs.pytest.org/en/stable/')]
for tag,title,url in refs:p(tag+'  '+title+'\n'+url,size=8.8,after=7)
p('참고일 2026-11-03. 학교 공간 목록은 사용자 제공 63개 호실을 사용하며 이 작업에서 전체 목록을 사이트에서 독립 재검증한 것은 아니다. 환경 모델 계수의 타당성을 입증하는 논문·표준을 새로 적용하지 않았으며, 임의의 DOI나 실험 성능을 인용하지 않았다.',size=8.8)
heading('Design Reference 디자인 참고',2)
p('사용자 제공 PROLED XDR Display Technology Overview, October 2026, 20쪽. 표지 대비, 여백, 제목 계층, 기능 요약과 사양표의 구성만 참고했다. 로고·원문 문장·이미지·도표는 복제하지 않았다. 본문은 A4와 한국어 가독성에 맞춰 재구성했다.',size=9)
# Cached Word TOC with real heading bookmarks and field wrapper, updated after render.
cache=TOC_PLACEHOLDER._p;parent=cache.getparent();index=parent.index(cache)
for item in contents:
 pp=OxmlElement('w:p');pr=OxmlElement('w:pPr');tabs=OxmlElement('w:tabs');tab=OxmlElement('w:tab');tab.set(qn('w:val'),'right');tab.set(qn('w:leader'),'dot');tab.set(qn('w:pos'),str(int(Mm(W)/635)));tabs.append(tab);pr.append(tabs)
 spacing=OxmlElement('w:spacing');spacing.set(qn('w:after'),'160');pr.append(spacing);pp.append(pr)
 hl=OxmlElement('w:hyperlink');hl.set(qn('w:anchor'),item['bookmark'])
 for text in [item['title'],'\t',str(item['page'])]:
  rr=OxmlElement('w:r');tt=OxmlElement('w:tab') if text=='\t' else OxmlElement('w:t')
  if text!='\t':tt.text=text
  rr.append(tt);hl.append(rr)
 pp.append(hl);parent.insert(index,pp);index+=1
parent.remove(cache)
# Do not auto-refresh on open; cached page numbers are verified and Word can update after editing.
settings=DOC.settings.element
upd=OxmlElement('w:updateFields');upd.set(qn('w:val'),'false');settings.append(upd)
for border in DOC.element.xpath('.//w:pBdr')+DOC.styles.element.xpath('.//w:pBdr'):
 border.getparent().remove(border)
for pp in DOC.element.xpath('.//w:p'):
 pr=pp.find(qn('w:pPr'))
 if pr is None:pr=OxmlElement('w:pPr');pp.insert(0,pr)
 snap=OxmlElement('w:snapToGrid');snap.set(qn('w:val'),'false');pr.append(snap)
for rr in DOC.element.xpath('.//w:r'):
 rp=rr.find(qn('w:rPr'))
 if rp is None:rp=OxmlElement('w:rPr');rr.insert(0,rp)
 fonts=rp.find(qn('w:rFonts'))
 if fonts is None:fonts=OxmlElement('w:rFonts');rp.insert(0,fonts)
 iscode=any('Menlo' in str(v) for v in fonts.attrib.values())
 for key in list(fonts.attrib):del fonts.attrib[key]
 latin='Menlo' if iscode else 'Helvetica Neue'
 for key,value in [('ascii',latin),('hAnsi',latin),('eastAsia','Apple SD Gothic Neo')]:fonts.set(qn('w:'+key),value)
DOC.save(OUT/'Smart_Campus_AIoT_Simulator_Technology_Overview.docx')
(OUT/'assets/document_inventory.json').write_text(json.dumps(dict(planned_pages=page,contents=contents,figures=figures,tables=tables),ensure_ascii=False,indent=2))
print('Saved DOCX; planned pages',page,'figures',len(figures),'tables',len(tables))
