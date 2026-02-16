@echo off
cd /d "%~dp0"

if "%~1"=="" (
    echo Drag and drop your memories.json file onto this script!
    echo Or run: python json2txt.py memories.json
    echo.
    pause
    exit /b 1
)

python json2txt.py "%~1"
echo.
pause
