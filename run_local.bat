@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Missing Python environment. Run setup_windows.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1
if errorlevel 1 (
    echo BloodTypeLab failed to launch. Review the error above.
    pause
    exit /b 1
)
endlocal
