@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set HF_HOME=%~dp0modeles
set HF_HUB_OFFLINE=1
cd /d "%~dp0"
python tester.py
pause
