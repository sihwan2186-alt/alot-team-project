from pathlib import Path
from common import ROOT

p=ROOT/'실습시작.ps1'
t=p.read_text(encoding='utf-8-sig')
if '[switch]$Textbook' not in t:
    t=t.replace('param([switch]$Prepare)','param([switch]$Prepare,[switch]$Textbook)')
    t=t.replace('if ($Prepare) {', '''if (-not $Textbook) {
    if ($Prepare) {
        Write-Output '개인 모델은 동결된 학습 결과를 사용합니다. 재학습은 03_팀프로젝트/김시환_개인모델/README.md를 확인하세요.'
        exit 0
    }
    & $pythonPath -m streamlit run (Join-Path $PSScriptRoot '03_팀프로젝트\\김시환_개인모델\\app.py')
    exit $LASTEXITCODE
}
if ($Prepare) {''',1)
    p.write_text(t,encoding='utf-8-sig')
p=ROOT/'README.md';t=p.read_text(encoding='utf-8')
t=t.replace('**현재 작업은 W10 학생·관리자 화면 실습입니다.**',
    '**현재 작업은 김시환 개인 조건의 S1·S5 모델입니다.** [개인 모델과 데이터 검토](03_팀프로젝트/김시환_개인모델/README.md)를 먼저 확인하세요. 교재 W10 재실 예측은 `실습시작.ps1 -Textbook`으로 분리했습니다.')
t=t.replace('입력 데이터를 다시 만들 때만 다음을 실행합니다.', '교재 W10 입력을 다시 만들 때만 다음을 실행합니다.')
t=t.replace('.\\실습시작.ps1 -Prepare','.\\실습시작.ps1 -Textbook -Prepare')
p.write_text(t,encoding='utf-8')
p=ROOT/'00_여기부터_자료찾기.html';t=p.read_text(encoding='utf-8')
t=t.replace('현재 W10 실습','김시환 개인 모델').replace('href="02_실습/W10_Lab/"','href="03_팀프로젝트/김시환_개인모델/"')
t=t.replace('63실 학생·관리자 화면, 입력과 캡처 안내','S1·S5별 데이터 선택·학습·시뮬레이션 결과')
t=t.replace('지금 할 일: W10 학생·관리자 화면 실습','지금 할 일: 김시환 개인 조건의 S1·S5 모델 검토')
t=t.replace('입력 재생성은','교재 입력 재생성은').replace('.\\실습시작.ps1 -Prepare','.\\실습시작.ps1 -Textbook -Prepare')
p.write_text(t,encoding='utf-8')
print('Personal-model navigation updated.')
