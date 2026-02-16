@echo off
title Shapes.inc Memory Exporter
cd /d "%~dp0"

if not exist ".installed" (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install dependencies. Make sure Python is installed.
        pause
        exit /b 1
    )
    playwright install chromium firefox
    echo. > .installed
    echo.
)

python memexporter.py %*
echo.
echo Exports are saved in: %cd%\exports\
echo.
pause
