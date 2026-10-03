@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto run
where py >nul 2>nul
if errorlevel 1 goto python
py -3 -m venv .venv
if errorlevel 1 goto fail
goto install
:python
python -m venv .venv
if errorlevel 1 goto fail
:install
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
:run
.venv\Scripts\python.exe -c "import yaml" >nul 2>nul
if errorlevel 1 goto install
.venv\Scripts\python.exe -X utf8 gui\backend\app.py --open
if errorlevel 1 goto fail
goto end
:fail
echo.
echo Studio could not start. Check Python 3.10+, network access for PyYAML, and port 8787.
echo Manual: python -m pip install -r requirements.txt
pause
:end
endlocal
