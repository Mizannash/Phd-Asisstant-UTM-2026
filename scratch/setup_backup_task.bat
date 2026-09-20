@echo off
setlocal
set "PROJECT_DIR=D:\PhD_Assistant_UTM"
set "SCRIPT_PATH=%PROJECT_DIR%\backup.bat"
set "TASK_NAME=PhD_Assistant_Backup"

schtasks /create /tn "%TASK_NAME%" /tr "cmd.exe /c \"cd /d ^\"%PROJECT_DIR%^\" && ^\"%SCRIPT_PATH%^\"\"" /sc weekly /d SUN /st 03:00 /f

if %ERRORLEVEL% equ 0 (
    echo [SUCCESS] Windows Task Scheduler successfully configured.
    echo Task '%TASK_NAME%' will run every Sunday at 03:00 AM.
) else (
    echo [ERROR] Failed to create the scheduled task. You may need to run this as Administrator.
)
pause
