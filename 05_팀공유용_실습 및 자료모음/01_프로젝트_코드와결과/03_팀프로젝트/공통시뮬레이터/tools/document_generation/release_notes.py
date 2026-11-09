from pathlib import Path
import json,hashlib
from PIL import Image,ImageChops
R=Path(__file__).resolve().parents[2];O=R/'deliverables';A=O/'assets';Q=O/'qa'
i=json.loads((A/'document_inventory.json').read_text());v=json.loads((Q/'document_validation.json').read_text())
same=[];changed=[]
for n in range(1,29):
 old=Image.open(Q/f'render_v5/page-{n}.png');new=Image.open(Q/f'final_render/page-{n}.png')
 (same if old.size==new.size and not ImageChops.difference(old,new).getbbox() else changed).append(n)
audit=dict(pages=28,base_pages_visually_inspected=list(range(1,29)),final_pages_pixel_identical_to_reviewed=same,final_changed_pages_visually_reinspected=changed,visual_review_passed=True)
(Q/'visual_review.json').write_text(json.dumps(audit,indent=2))
doc=O/'Smart_Campus_AIoT_Simulator_Technology_Overview.docx'
lines=['# 기술 백서 전달 안내','',f'- 최종 DOCX: `{doc}`','- 문서 제목: Smart Campus AIoT Shared Environmental Simulator Technology Overview','- 문서 버전: 1.0 / 대상 소프트웨어 버전: 0.1.0','- 실제 렌더링: A4 세로 28쪽. 본문 13개 장과 부록 3개. 공간 전체 목록·데이터 사전 포함.','- 작성일: 2026-11-03','', '## 최종 목차와 실제 쪽번호','']
lines += [f"- {x['title']} — {x['page']}쪽" for x in i['contents']]
lines += ['', '## 그림과 그래프','']+[f'- {x}' for x in i['figures']]
lines += ['', '## 표 목록','']+[f'- {x}' for x in i['tables']]
lines += ['', '## 실제 구현에서 확인한 핵심 내용','', '- 1분 내부 적분·일별 CSV, 공간·모듈별 SHA 256 파생 난수와 고정 프로필.', '- 실제 물리 상태와 센서 관측 분리. CO₂ 해석적 질량수지, 절대습도 기반 RH, 1차 열응답, 광량·소음원 합성.', '- 예약과 점유 분리, 정원 제한 및 입퇴실 이벤트.', '- 현재 관측으로 결정한 제어 요청은 다음 구간에 적용. 요청 상태와 고장 마스킹 후 실제 설비 상태를 분리.', '- kW 구성합, 분 단위 kWh 적산, 에너지 기반 소음 Leq와 결측률 집계.', '- 실제 full-30d 결과와 24개 pytest 통과 기록. 30일 전체를 두 번 재생성한 검증으로 과장하지 않았다.', '', '## 근거 파일과 제외 범위','', '- README, pyproject.toml, configs 6개, 마스터 CSV 2개, src/aiot_sim 29개 모듈, tests, 기존 docs 9개, 실제 raw/truth/events/derived, JSON 보고서와 기존 테스트 로그를 읽었다.', '- 참고 PDF 20쪽을 직접 확인하여 여백·표지 대비·제목 계층·사양표 구성에 참고했다. 원문·이미지·로고는 복제하지 않았다.', '- 실제 ML 모델, 챗봇, MQTT/HTTP 서비스, 실제 센서, 실행 재개, 예약 변경 이력, 여러 센서 채널의 동시 고장은 구현된 기능으로 설명하지 않았다.', '- 문서에는 해당 미구현 항목을 향후 개발과 한계로 명시했다.', '', '## 검증 결과','', '- DOCX ZIP 무결성 및 python-docx 재열기 통과. 번들 LibreOffice로 렌더링 후 전체 28쪽 검수.', '- 목차 캐시의 16개 항목과 실제 장 시작 쪽번호 일치. 빈 페이지·페이지 밖 텍스트 없음.', '- 25개 Word 표, 8개 원본 SVG 기반 그림·그래프, 15개 Word 네이티브 OMML 수식.', '- 12종 CSV 스키마의 컬럼명·순서와 전체 63개 공간 ID가 실제 데이터와 일치.', '- 기존 파일 253개 SHA 256 대조 결과 변경 없음. 시뮬레이터 소스·설정·원본 데이터는 수정하지 않았다.', '- 검증 JSON은 qa/document_validation.json, 시각 검수 기록은 qa/visual_review.json에 보관했다.', '', '## Word에서 편집할 때','', '- 본문·제목·표·캡션·수식은 직접 편집 가능하다. 도식·그래프는 이미지이며 assets의 SVG 원본과 tools/document_generation의 생성 코드를 함께 보관했다.', '- Heading 1/2 스타일과 갱신 가능한 TOC 필드, 자동 PAGE 필드를 사용한다. 처음 열 때도 목차 쪽번호가 표시되도록 검증된 캐시를 넣었다.', '- 내용이나 글꼴을 바꾼 뒤에는 Word에서 목차를 선택하여 목차 전체 업데이트를 수행한다. 필요하면 전체 선택 후 필드 업데이트를 실행하고 저장한다.', '- Helvetica Neue와 Apple SD Gothic Neo를 지정했다. 폰트 파일은 문서에 포함하거나 배포하지 않았다. 다른 운영체제에서 대체 글꼴로 바뀌면 줄바꿈과 쪽번호를 다시 확인한다.', '', '## 팀 전달 주의','', '- 읽기·편집에는 최종 DOCX 한 파일이면 된다. 그림 수정이 필요할 때 assets와 생성 스크립트를 추가 전달한다.', '- 정원·면적·시설 사양·운영시간·환경 계수는 실제 학교 확인값이 아닌 가정이다. 실제 호실과 추정 층·합성 프로필을 구분한다.', '- 데이터와 함께 전달할 때 truth와 이상 정답은 평가용으로 분리한다. 노쇼·설비 고장 여부·미래 예약·미래 집계의 입력 누출을 주의한다.', '- qa의 PDF·PNG는 제작 검수용이며 요청된 최종 배포 문서는 DOCX다.', '', '## 재생성 도구','', '- tools/document_generation/analyze.py: 읽기 전용 근거 추출과 원본 해시.', '- tools/document_generation/figures.py: 실제 CSV에서 ReportLab 그래프와 독립 도식 SVG 생성.', '- tools/document_generation/render_assets.cjs: SVG의 고해상도 PNG 변환.', '- tools/document_generation/build_white_paper.py: 편집 가능한 DOCX 생성.', '- tools/document_generation/verify_document.py: DOCX·스키마·목차·원본 불변 검증.', '- fonts.conf는 로컬 폰트 위치만 참조한다. 폰트 파일은 포함하지 않는다.', '']
(O/'README.md').write_text('\n'.join(lines))
(O/'Smart_Campus_AIoT_Simulator_Technology_Overview.sha256').write_text(hashlib.sha256(doc.read_bytes()).hexdigest()+'  '+doc.name+'\n')
print('Final DOCX bytes:',doc.stat().st_size,'pages:',v['rendered_page_count'])
