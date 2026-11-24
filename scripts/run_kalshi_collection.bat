@echo off
setlocal

cd /d "C:\Users\besho\Documents\kalshi-sports-edge"
if errorlevel 1 exit /b 1

if not exist "logs" mkdir "logs"

set "PYTHON=C:\Users\besho\anaconda3\envs\kalshi-sports-edge\python.exe"
set "LOG=logs\kalshi_collection.log"

echo. >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo START: %date% %time% >> "%LOG%"

"%PYTHON%" -u "src\kalshi\collect_events.py" >> "%LOG%" 2>&1
if errorlevel 1 goto collection_failed

"%PYTHON%" -u "src\kalshi\build_research_calendar.py" >> "%LOG%" 2>&1
if errorlevel 1 goto calendar_failed

echo SUCCESS: %date% %time% >> "%LOG%"
exit /b 0

:collection_failed
echo ERROR: Collector returned a failure. Calendar build skipped. >> "%LOG%"
exit /b 1

:calendar_failed
echo ERROR: Calendar builder returned a failure. >> "%LOG%"
exit /b 1