$actionScout = New-ScheduledTaskAction -Execute "D:\PhD_Assistant_UTM\venv\Scripts\python.exe" -Argument "src\scout.py" -WorkingDirectory "D:\PhD_Assistant_UTM"
$triggerScout = New-ScheduledTaskTrigger -Daily -At 2:00am
$settingsScout = New-ScheduledTaskSettingsSet -WakeToRun
Register-ScheduledTask -Action $actionScout -Trigger $triggerScout -Settings $settingsScout -TaskName "PhD_Assistant_Scout" -Description "Runs the daily AI scout pipeline" -Force

$actionBackup = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c D:\PhD_Assistant_UTM\backup.bat" -WorkingDirectory "D:\PhD_Assistant_UTM"
$triggerBackup = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 3:00am
Register-ScheduledTask -Action $actionBackup -Trigger $triggerBackup -TaskName "PhD_Assistant_Backup" -Description "Weekly backup for PhD Assistant" -Force

$envFile = Get-Content "D:\PhD_Assistant_UTM\.env"
$match = $envFile | Select-String -Pattern "^SERPAPI\_KEY=(.*)"
if ($match) {
    $key = $match.Matches.Groups[1].Value
    Write-Output "SERPAPI_KEY Length: $($key.Length)"
} else {
    Write-Output "SERPAPI_KEY not found in .env"
}

schtasks /query /tn PhD_Assistant_Scout
schtasks /query /tn PhD_Assistant_Backup
