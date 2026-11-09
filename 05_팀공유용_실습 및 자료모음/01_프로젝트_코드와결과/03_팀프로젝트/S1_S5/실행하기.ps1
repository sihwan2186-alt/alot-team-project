$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
python (Join-Path $PSScriptRoot 'run_system.py')
if ($LASTEXITCODE -ne 0) { throw '자동 검사 실패: 시뮬레이션_결과/test_log.txt를 확인하세요.' }
Get-Content -LiteralPath (Join-Path $PSScriptRoot '시뮬레이션_완성본_검토안내.md') -Encoding UTF8
