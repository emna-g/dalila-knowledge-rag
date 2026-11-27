@echo off
rem Rafraichissement hebdomadaire des sources de Dalila (dalila/sources/hebdo.py).
rem A planifier dans le Planificateur de taches Windows, par exemple chaque lundi a 3 h :
rem   schtasks /create /tn "Dalila sources" /sc weekly /d MON /st 03:00 /tr "\"%~f0\""
rem Sur un serveur Linux (cron) :  0 3 * * 1  cd /chemin/du/depot && .venv/bin/python -m dalila.sources.hebdo
rem Rapport : donnees\sources\rapports\hebdo_<date>.md ; code de sortie 0 = ok, 1 = echec applique, 2 = alertes.
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
if not exist "donnees\sources" mkdir "donnees\sources"
".venv\Scripts\python.exe" -m dalila.sources.hebdo >> "donnees\sources\hebdo.log" 2>&1
exit /b %ERRORLEVEL%
