"""Read-only checks on project sources and the final editable document."""
from pathlib import Path
from collections import Counter
from zipfile import ZipFile
from lxml import etree
import json,hashlib,re
import pdfplumber
from docx import Document
R=Path(__file__).resolve().parents[2];A=R/'deliverables/assets';Q=R/'deliverables/qa';D=R/'deliverables/Smart_Campus_AIoT_Simulator_Technology_Overview.docx'
facts=json.loads((A/'verified_facts.json').read_text());inventory=json.loads((A/'document_inventory.json').read_text())
checks={}
with ZipFile(D) as z:
 checks['zip_integrity']=z.testzip() is None
 xml=etree.fromstring(z.read('word/document.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
 math=xml.xpath('//m:oMath',namespaces=ns)
 checks['native_editable_equations']=len(math)
 checks['no_raw_math_braces']=not any('{' in t or '}' in t for t in xml.xpath('//m:t/text()',namespaces=ns))
 checks['toc_field_present']=any('TOC' in t for t in xml.xpath('//w:instrText/text()',namespaces=ns))
 checks['no_embedded_font_files']=not any(p.startswith('word/fonts/') for p in z.namelist())
 checks['heading_count']=len(xml.xpath('//w:pStyle[@w:val="Heading1"]',namespaces=ns))
doc=Document(D);checks['table_count']=len(doc.tables)
actual_fields=[tuple(row.cells[0].text for row in t.rows[1:]) for t in doc.tables if t.rows[0].cells[0].text=='컬럼명']
checks['all_csv_headers_match']=Counter(actual_fields)==Counter(tuple(v) for v in facts['headers'].values())
checks['csv_schema_families']=len(actual_fields)
rooms=[row.cells[0].text for t in doc.tables if t.rows[0].cells[0].text=='room_id' for row in t.rows[1:]]
checks['all_63_room_records_match']=len(rooms)==len(set(rooms))==63 and set(rooms)=={r['room_id'] for r in facts['rooms']}
checks['graph_files_exist']=all((A/(n+'.svg')).exists() and (A/(n+'.png')).exists() for n in ['architecture','workflow','feedback','storage','room_distribution','environment_series','sensor_bias','power_occupancy'])
pdf=next((Q/'final_render').glob('*.pdf'))
def norm(s):return re.sub(r'\s+','',s)
with pdfplumber.open(pdf) as p:
 checks['rendered_page_count']=len(p.pages)
 texts=[page.extract_text() or '' for page in p.pages]
 checks['korean_visible_and_extractable']='공통 환경 시뮬레이터 기술 백서' in texts[0] and '노쇼' in texts[7]
 checks['no_blank_body_pages']=all(len(t)>200 for t in texts[1:])
 checks['toc_pages_match']=all(norm(item['title']) in norm(texts[item['page']-1]) for item in inventory['contents'])
 bounds=[]
 for i,page in enumerate(p.pages):
  outside=[c for c in page.chars if c['text'].strip() and (c['x0'] < 0 or c['x1']>page.width+1 or c['top']<0 or c['bottom']>page.height+1)]
  if outside:bounds.append(i+1)
 checks['text_within_page_bounds']=not bounds
 checks['pages_with_outside_text']=bounds
# Check original files and every full dataset CSV against pre-authoring SHA-256.
original=json.loads((A/'source_hashes_before.json').read_text());changed=[]
for name,expected in original.items():
 h=hashlib.sha256()
 with (R/name).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 if h.hexdigest()!=expected:changed.append(name)
checks['original_files_checked']=len(original);checks['source_and_dataset_unchanged']=not changed;checks['changed_original_files']=changed
must=['zip_integrity','no_raw_math_braces','toc_field_present','no_embedded_font_files','all_csv_headers_match','all_63_room_records_match','graph_files_exist','korean_visible_and_extractable','no_blank_body_pages','toc_pages_match','text_within_page_bounds','source_and_dataset_unchanged']
checks['passed']=all(checks[k] for k in must) and checks['native_editable_equations']>=10 and checks['rendered_page_count']==28
(Q/'document_validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
print(json.dumps(checks,ensure_ascii=False,indent=2))
assert checks['passed']
