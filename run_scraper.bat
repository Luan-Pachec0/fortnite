@echo off
echo ==========================================
echo Starting Fortnite Tracker Scraper
echo ==========================================

cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [WARNING] No virtual environment found at venv\. Using global python.
)

REM Run the scraper
python scraper\main.py

echo.
echo ==========================================
echo Scraping Finished! Check the logs above.
echo ==========================================

REM Pause the screen so the user can read the output if run manually via double-click
pause
