$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument '/c "D:\PhD_Assistant_UTM\backup.bat"'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 3:00am
$settings = New-ScheduledTaskSettingsSet -WakeToRun
Register-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -TaskName "PhD_Assistant_Backup" -Description "PhD Assistant Backup Task" -Force
