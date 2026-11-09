from pathlib import Path
p=Path(__file__).with_name('build_white_paper.py');s=p.read_text()
s=s.replace("def table(headers,rows,widths=None,size=9,caption=None):","def table(headers,rows,widths=None,size=9,caption=None,compact=False):")
s=s.replace("for k,v in [('top','60'),('bottom','60'),('left','80'),('right','80')]:","for k,v in [('top','35' if compact else '60'),('bottom','35' if compact else '60'),('left','80'),('right','80')]:")
s=s.replace("para.paragraph_format.line_spacing=1.07","para.paragraph_format.line_spacing=1.07\n    snap=OxmlElement('w:snapToGrid');snap.set(qn('w:val'),'false');para._p.get_or_add_pPr().append(snap)")
s=s.replace("size=9.1,caption=f'Table {12+part}.","size=9.1,compact=True,caption=f'Table {12+part}.")
s=s.replace("size=8.0,caption=f'Table {14+sum", "size=8.3,compact=True,caption=f'Table {14+sum")
# Native math objects with actual subscript/superscript nodes, never Unicode subscript glyphs.
start=s.index('def eq(text):');end=s.index('\ndef table(',start)
s=s[:start]+'''def eq(text):
 x=DOC.add_paragraph();x.paragraph_format.space_before=Pt(4);x.paragraph_format.space_after=Pt(7)
 om=OxmlElement('m:oMath')
 def run(text):
  rr=OxmlElement('m:r');props=OxmlElement('m:rPr');sty=OxmlElement('m:sty');sty.set(qn('m:val'),'p');props.append(sty);rr.append(props)
  wp=OxmlElement('w:rPr');sz=OxmlElement('w:sz');sz.set(qn('w:val'),'21');wp.append(sz);rr.append(wp)
  tt=OxmlElement('m:t');tt.text=text;tt.set(qn('xml:space'),'preserve');rr.append(tt);return rr
 for token in re.findall(r'[A-Za-zΑ-ω]+(?:_\\{[^}]+\\})?(?:\\^\\{[^}]+\\})?|[^A-Za-zΑ-ω]',text):
  m=re.fullmatch(r'([A-Za-zΑ-ω]+)(?:_\\{([^}]+)\\})?(?:\\^\\{([^}]+)\\})?',token)
  if m and (m[2] or m[3]):
   node=OxmlElement('m:sSubSup' if m[2] and m[3] else 'm:sSub' if m[2] else 'm:sSup')
   e=OxmlElement('m:e');e.append(run(m[1]));node.append(e)
   for tag,txt in [('sub',m[2]),('sup',m[3])]:
    if txt:
     child=OxmlElement('m:'+tag);child.append(run(txt));node.append(child)
   om.append(node)
  else:om.append(run(token))
 x._p.append(om)
''' + s[end:]
replacements={
'Tₜ₊₁ = Tₜ + Δt [ k(Tout − Tₜ) + n qperson + qHVAC ]':'T_{t+1} = T_{t} + Δt [ k(T_{out} − T_{t}) + n q_{person} + q_{HVAC} ]',
'Asat(T) = 216.7 × 6.112 × exp[17.67T / (T + 243.5)] / (273.15 + T)':'A_{sat}(T) = 216.7 × 6.112 × exp[17.67T / (T + 243.5)] / (273.15 + T)',
'Aout = Asat(Tout) RHout / 100':'A_{out} = A_{sat}(T_{out}) RH_{out} / 100',
'A* = Aout + (Aₜ − Aout) exp(−a Δt/60) + n m Δt/V':'A* = A_{out} + (A_{t} − A_{out}) exp(−a Δt/60) + n m Δt/V',
'Aₜ₊₁ = clip(A* × dcool, 0, Asat(Tₜ₊₁))':'A_{t+1} = clip(A* × d_{cool}, 0, A_{sat}(T_{t+1}))',
'RHₜ₊₁ = 100 Aₜ₊₁ / Asat(Tₜ₊₁)':'RH_{t+1} = 100 A_{t+1} / A_{sat}(T_{t+1})',
'a = aoff + (aon − aoff) ventilation_level':'a = a_{off} + (a_{on} − a_{off}) ventilation_level',
'S = n G × 10⁶ / V':'S = n G × 10^{6} / V',
'Cₜ₊₁ = Cout + (Cₜ − Cout)e⁻ᵃΔᵗ⁄⁶⁰ + (S/a)(1 − e⁻ᵃΔᵗ⁄⁶⁰)':'C_{t+1} = C_{out} + (C_{t} − C_{out}) r + (S/a)(1 − r),   r = exp(−aΔt/60)',
'Ltotal = 10 log₁₀[Σᵢ 10^(Lᵢ/10)]':'L_{total} = 10 log_{10}[Σ 10^{L_i/10}]',
'Ptotal = PHVAC + Pventilation + Plighting + Pstandby':'P_{total} = P_{HVAC} + P_{ventilation} + P_{lighting} + P_{standby}',
'PHVAC = profile_hvac_power_kw × 0.8 × hvac_on':'P_{HVAC} = profile_hvac_power_kw × 0.8 × hvac_on',
'Einterval = Σminute Pminute / 60':'E_{interval} = Σ P_{minute} / 60',
}
for old,new in replacements.items():s=s.replace(old,new)
# Make footer page number genuinely right aligned with a full width tab.
s=s.replace("f.paragraph_format.tab_stops.add_tab_stop(Mm(W),WD_ALIGN_PARAGRAPH.RIGHT)","f.paragraph_format.tab_stops.add_tab_stop(Mm(W),2)")
# Enforce grid opt-out globally so CJK table lines follow intended size, not 18-point document grid.
s=s.replace("for rr in DOC.element.xpath('.//w:r'):","for pp in DOC.element.xpath('.//w:p'):\n pr=pp.find(qn('w:pPr'))\n if pr is None:pr=OxmlElement('w:pPr');pp.insert(0,pr)\n snap=OxmlElement('w:snapToGrid');snap.set(qn('w:val'),'false');pr.append(snap)\nfor rr in DOC.element.xpath('.//w:r'):")
p.write_text(s)
