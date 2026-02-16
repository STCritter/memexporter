@echo off
title Shapes.inc Memory Exporter
cd /d "%~dp0"

if not exist ".installed" (
    echo Installing dependencies...
    pip install -r requirements.txt
    playwright install chromium
    echo. > .installed
    echo.
)

python memexporter.py %*
pause
