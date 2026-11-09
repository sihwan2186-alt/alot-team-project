@echo off
set PYTHONIOENCODING=utf-8
python "%~dp0run_system.py"
if errorlevel 1 exit /b 1
echo Review report: additional results are in the same folder.
