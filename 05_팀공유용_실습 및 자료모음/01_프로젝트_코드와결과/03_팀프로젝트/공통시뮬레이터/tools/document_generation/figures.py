"""Original grayscale diagrams and ReportLab scientific plots from verified CSV data."""
from pathlib import Path
import json,math,html
from reportlab.graphics.shapes import Drawing,String,Line,Rect
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics import renderSVG
from reportlab.lib.colors import HexColor,Color
ROOT=Path(__file__).resolve().parents[2];A=ROOT/'deliverables/assets'
D=json.loads((A/'verified_facts.json').read_text())
def diagram(name,w,h,boxes,arrows,labels=()):
 out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="white"/><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0 0 L7 3 L0 6" fill="none" stroke="#333"/></marker></defs>']
 for points in arrows:out.append(f'<polyline points="{points}" fill="none" stroke="#444" stroke-width="1.6" marker-end="url(#arrow)"/>')
 for x,y,bw,bh,title,detail in boxes:
  out.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" fill="#f6f6f6" stroke="#999" rx="2"/>')
  for i,line in enumerate([title,*detail.split('|')]):
   out.append(f'<text x="{x+bw/2}" y="{y+24+i*19}" text-anchor="middle" font-family="Helvetica Neue,Arial,sans-serif" font-size="{15 if i==0 else 12}" font-weight="{600 if i==0 else 400}" fill="{ "#111" if i==0 else "#555"}">{html.escape(line)}</text>')
 for x,y,text in labels:out.append(f'<text x="{x}" y="{y}" font-family="Helvetica Neue,Arial,sans-serif" font-size="12" fill="#555">{html.escape(text)}</text>')
 out.append('</svg>');(A/f'{name}.svg').write_text(''.join(out))
diagram('architecture',900,440,[(15,20,190,80,'Configuration','configs/*.toml'),(240,20,190,80,'Room inputs','catalog + profiles'),(465,20,190,80,'Clock and streams','clock + random_utils'),(690,20,195,80,'Shared outdoor state','external_environment'),(15,165,190,92,'Use of rooms','reservations | occupancy'),(240,165,190,92,'Physical state X(t)','environment | hvac / ventilation / lighting'),(465,165,190,92,'Observed values Y(t)','sensors | faults'),(690,165,195,92,'Control and power','controller + energy'),(240,335,415,80,'Daily CSV export','raw / events / truth  ->  aggregator  ->  derived'),(690,335,195,80,'Quality evidence','validator + reporter')],['205,60 240,60','655,60 690,60','110,100 110,165','335,100 335,165','560,100 560,165','785,100 785,130 335,130 335,165','205,210 240,210','430,210 465,210','655,210 690,210','785,257 785,290 335,290 335,257','560,257 560,335','655,375 690,375'],[(365,283,'Next-interval facility command'),(15,325,'simulator.py coordinates all components')])
diagram('workflow',900,390,[(20,20,255,80,'1  Daily schedule','profile + date + reservation stream'),(325,20,255,80,'2  Occupancy and fault','select injection; apply entry / exit'),(630,20,250,80,'3  Observe state at t','X(t) -> noise / fault -> Y(t)'),(630,175,250,80,'4  Record interval','raw / truth / facility / energy'),(325,175,255,80,'5  Request control','Y(t), occupancy -> F(t+1)'),(20,175,255,80,'6  Evolve physical state','X(t), applied F(t) -> X(t+1)')],['275,60 325,60','580,60 630,60','755,100 755,175','630,215 580,215','325,215 275,215','140,255 140,315 890,315 890,135 452,135 452,100'],[(210,349,'Repeat each minute; output sampling does not change integration step')])
diagram('feedback',900,330,[(20,30,230,85,'Physical state X(t)','truth is retained for evaluation'),(335,30,230,85,'Sensor observation Y(t)','noise and CO2 sensor faults'),(650,30,230,85,'Rule-based controller','thresholds + hysteresis + dwell'),(650,210,230,85,'Requested F(t+1)','separate from fault-masked state'),(335,210,230,85,'Applied facility F(t)','fault mask + interval power'),(20,210,230,85,'State integrator','X(t+1) = f(X(t), F(t))')],['250,70 335,70','565,70 650,70','765,115 765,210','650,250 565,250','335,250 250,250','135,210 135,115'],[(343,163,'New command is used in the NEXT interval')])
diagram('storage',900,325,[(20,25,210,85,'Master and inputs','rooms.csv | room_profiles.csv'),(340,25,220,85,'Run identity','manifest.json | input snapshots'),(665,25,215,85,'Raw time series','sensors / facilities / energy'),(20,215,210,85,'Events','reservations / occupancy / control'),(340,215,220,85,'Evaluation only','environment truth / anomalies'),(665,215,215,85,'Derived and reports','5-minute CSV / quality evidence')],['230,65 340,65','560,65 665,65','450,110 450,150 125,150 125,215','450,150 450,215','775,110 775,215'],[(550,180,'Never auto-join truth into model features')])
# Distribution as vector bar chart, with actual catalog counts.
d=Drawing(600,160)
for i,(name,n) in enumerate([('STU',38),('LIB',12),('WON',9),('HEA',4)]):
 y=125-i*32;d.add(String(0,y,name,fontName='Helvetica',fontSize=11));d.add(Rect(55,y-3,n*11,13,fillColor=HexColor('#333333'),strokeColor=None));d.add(String(65+n*11,y,str(n),fontName='Helvetica',fontSize=11))
renderSVG.drawToFile(d,str(A/'room_distribution.svg'))

def plot_panels(name,panels,width=720,panel_h=150):
 d=Drawing(width,len(panels)*panel_h+15)
 palette=[HexColor('#111111'),HexColor('#888888'),HexColor('#aaaaaa')]
 for idx,p in enumerate(panels):
  bottom=(len(panels)-1-idx)*panel_h+28
  lp=LinePlot();lp.x=65;lp.y=bottom;lp.width=width-90;lp.height=panel_h-52
  lp.data=p['series'];lp.xValueAxis.valueMin=p.get('xmin',0);lp.xValueAxis.valueMax=p.get('xmax',24)
  lp.xValueAxis.valueSteps=p.get('xticks',[0,6,12,18,24]);lp.xValueAxis.labels.fontName='Helvetica';lp.xValueAxis.labels.fontSize=9
  lp.yValueAxis.valueMin=p['ymin'];lp.yValueAxis.valueMax=p['ymax'];lp.yValueAxis.valueSteps=p['yticks'];lp.yValueAxis.labels.fontName='Helvetica';lp.yValueAxis.labels.fontSize=9
  lp.xValueAxis.strokeColor=HexColor('#cccccc');lp.yValueAxis.strokeColor=HexColor('#cccccc');lp.yValueAxis.gridStrokeColor=HexColor('#eeeeee');lp.yValueAxis.visibleGrid=True
  for j in range(len(p['series'])):
   lp.lines[j].strokeColor=palette[j%3];lp.lines[j].strokeWidth=1.1 if j==0 else 0.8
   if j==1:lp.lines[j].strokeDashArray=[4,2]
  d.add(lp);d.add(String(65,bottom+lp.height+13,p['title'],fontName='Helvetica',fontSize=11))
  if 'legend' in p:d.add(String(width-260,bottom+lp.height+13,p['legend'],fontName='Helvetica',fontSize=8,fillColor=HexColor('#666666')))
 d.add(String(width-100,1,'Hour (KST)',fontName='Helvetica',fontSize=9))
 renderSVG.drawToFile(d,str(A/f'{name}.svg'))
truth=D['day']['truth'];sensor=D['day']['sensors'];energy=D['day']['energy']
def seq(rows,key):return [(i/60,float(row[key])) for i,row in enumerate(rows) if row[key]!='']
plot_panels('environment_series',[
 dict(title='Temperature (deg C)',series=[seq(truth,'true_temperature_c'),seq(sensor,'temperature_c')],ymin=15,ymax=30,yticks=[15,20,25,30],legend='Black: truth  |  Gray dashed: sensor'),
 dict(title='CO2 concentration (ppm)',series=[seq(truth,'true_co2_ppm'),seq(sensor,'co2_ppm')],ymin=300,ymax=1200,yticks=[400,800,1200]),
 dict(title='Relative humidity (%)',series=[seq(truth,'true_humidity_pct')],ymin=20,ymax=100,yticks=[20,40,60,80,100]),
 dict(title='Illuminance (lux)',series=[seq(truth,'true_illuminance_lux')],ymin=0,ymax=1100,yticks=[0,300,600,900]),
 dict(title='Noise level (dBA)',series=[seq(truth,'true_noise_dba')],ymin=25,ymax=60,yticks=[30,40,50,60]),
 dict(title='Occupancy (persons)',series=[seq(truth,'true_occupancy_count')],ymin=0,ymax=6,yticks=[0,2,4,6])],panel_h=110)
# A real recorded bias example, 00:20-01:05 on 2026-09-01, HEA-422.
f=D['fault_day'];series=[]
for rows,key in [(f['truth'],'true_co2_ppm'),(f['sensors'],'co2_ppm')]:series.append([(i,float(row[key])) for i,row in enumerate(rows) if 20<=i<=65 and row[key]!=''])
plot_panels('sensor_bias',[dict(title='Recorded CO2 sensor bias (ppm)',series=series,ymin=380,ymax=550,yticks=[400,450,500,550],xmin=20,xmax=65,xticks=[20,30,40,50,60],legend='Black: truth  |  Gray dashed: sensor')],panel_h=230)
# Correct the fault chart x-axis unit, replacing the generic hour label.
p=A/'sensor_bias.svg';p.write_text(p.read_text().replace('Hour (KST)','Minute after 00:00'))
plot_panels('power_occupancy',[
 dict(title='Interval mean power (kW)',series=[seq(energy,'total_power_kw')],ymin=0,ymax=max(float(e['total_power_kw']) for e in energy)*1.2,yticks=[0,1,2,3,4]),
 dict(title='Occupancy (persons)',series=[seq(truth,'true_occupancy_count')],ymin=0,ymax=6,yticks=[0,2,4,6])],panel_h=130)
print('SVG figures created:',len(list(A.glob('*.svg'))))
