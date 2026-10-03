@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 launcher.py
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    python launcher.py
  ) else (
    echo No se encontro Python 3. Instalalo desde https://www.python.org/downloads/ marcando "Add Python to PATH".
  )
)
pause
