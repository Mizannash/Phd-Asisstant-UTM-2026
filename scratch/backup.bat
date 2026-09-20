@echo off
set "TARGET_PARENT=C:\Users\user\OneDrive"
set "TARGET=C:\Users\user\OneDrive\PhD_Backups\PhD_Assistant_UTM"

if not exist "%TARGET_PARENT%\" (
    echo [ERROR] Backup target parent directory %TARGET_PARENT% does not exist.
    exit /b 1
)

if not exist "%TARGET%\" (
    mkdir "%TARGET%"
)

robocopy "D:\PhD_Assistant_UTM" "%TARGET%" /E /XD venv /XD __pycache__ /XD .git
exit /b 0
