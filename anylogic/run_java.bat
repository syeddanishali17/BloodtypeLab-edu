@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
    echo Usage: run_java.bat NEW_OUTPUT_FOLDER [REPLICATES] [SEED]
    echo Run this from an exported bundle. Requires Java 11 or newer on PATH.
    exit /b 2
)
set "REPS=%~2"
if not defined REPS set "REPS=20"
set "RUNSEED=%~3"
if not defined RUNSEED set "RUNSEED=10001"
java BloodTypeModel.java . "%~1" %REPS% %RUNSEED%
exit /b %ERRORLEVEL%
