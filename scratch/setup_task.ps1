$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument '/c "cd /d D:\PhD_Assistant_UTM && D:\PhD_Assistant_UTM\venv\Scripts\python.exe D:\PhD_Assistant_UTM\src\scout.py"'
$trigger = New-ScheduledTaskTrigger -Daily -At 2:00am
$settings = New-ScheduledTaskSettingsSet -WakeToRun
Register-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -TaskName "PhD_Assistant_Scout" -Description "PhD Assistant Scout Task" -Force
