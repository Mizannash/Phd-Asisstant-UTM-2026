@echo off
setlocal

:: Get the absolute path to the project directory (where this script is located)
set "PROJECT_DIR=%~dp0"
:: Remove trailing backslash
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

:: Define paths
set "PYTHON_EXE=%PROJECT_DIR%\venv\Scripts\python.exe"
set "SCRIPT_PATH=%PROJECT_DIR%\src\scout.py"
set "TASK_NAME=PhD_Assistant_Scout"

:: Create the scheduled task with the working directory set to the project root
schtasks /create /tn "%TASK_NAME%" /tr "cmd.exe /c \"cd /d ^\"%PROJECT_DIR%^\" && ^\"%PYTHON_EXE%^\" ^\"%SCRIPT_PATH%^\"\"" /sc daily /st 02:00 /f

if %ERRORLEVEL% equ 0 (
    echo [SUCCESS] Windows Task Scheduler successfully configured.
    echo Task '%TASK_NAME%' will run every day at 02:00 AM.
    echo Ensure your PC is awake or configure 'Wake to Run' manually in Task Scheduler if needed.
) else (
    echo [ERROR] Failed to create the scheduled task. You may need to run this as Administrator.
)

pause
