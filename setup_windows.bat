@echo off
setlocal
cd /d "%~dp0"
echo === BloodTypeLab setup ===

rem 1. Find Python (prefer the py launcher with 3.12)
set "PY="
where py >nul 2>nul && (py -3.12 -c "import sys" >nul 2>nul && set "PY=py -3.12")
if not defined PY (where py >nul 2>nul && set "PY=py -3")
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
    echo [ERROR] Python was not found. Install Python 3.12 from https://www.python.org/downloads/
    echo         and tick "Add python.exe to PATH", then run this script again.
    pause
    exit /b 1
)
echo Using: %PY%

rem 2. Create the virtual environment only if it does not exist
if exist ".venv\Scripts\python.exe" (
    echo Existing .venv found - reusing it, nothing is overwritten.
) else (
    echo Creating .venv ...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
)

rem 3. Install the tested dependencies
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Check your internet connection and try again.
    pause
    exit /b 1
)

rem 4. Smoke test: genetics + engine tests (fast)
".venv\Scripts\python.exe" -m pytest -q tests\test_genetics.py tests\test_engine.py
if errorlevel 1 (
    echo [ERROR] Smoke tests failed - setup is NOT complete. See the output above.
    pause
    exit /b 1
)

echo.
echo === Setup succeeded. Start the app with run_local.bat ===
pause
endlocal
