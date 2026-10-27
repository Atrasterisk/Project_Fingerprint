@echo off
rem Klik dua kali file ini untuk menjalankan aplikasi.
rem Pertama kali dijalankan, library akan terpasang otomatis (butuh internet).
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
%PY% -m pip install -r requirements.txt --quiet --disable-pip-version-check
start "" %PY%w fingerprint_app.py
