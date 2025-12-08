param(
    [string]$backupDir = ($env:USERPROFILE | Join-Path -ChildPath "Dropbox" | Join-Path -ChildPath "CFiler-backup")
)

"Register scheduled task to backup cfiler.ini to ``{0}``" -f $backupDir | Write-Host -ForegroundColor Cyan
if ((Read-Host -Prompt "==> OK? (y/N)") -eq "y") {

    $config = Get-Content -Path $($PSScriptRoot | Join-Path -ChildPath "config.json") | ConvertFrom-Json
    
    $taskPath = ("\{0}\" -f $config.taskPath) -replace "^\\+", "\" -replace "\\+$", "\"
    
    $appDir = $env:APPDATA | Join-Path -ChildPath $config.appDirName
    if (-not (Test-Path $appDir -PathType Container)) {
        New-Item -Path $appDir -ItemType Directory > $null
    }
    
    $src = $PSScriptRoot | Join-Path -ChildPath "backup.ps1" | Copy-Item -Destination $appDir -PassThru
    
    $action = New-ScheduledTaskAction -Execute powershell.exe -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$src`" `"$backupDir`""
    $settings = New-ScheduledTaskSettingsSet -Hidden -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    
    $startupTaskName = "startup"
    $startupTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    
    Register-ScheduledTask -TaskName $startupTaskName `
        -TaskPath $taskPath `
        -Action $action `
        -Trigger $startupTrigger `
        -Description "Copy cfiler.ini to backup directory on startup." `
        -Settings $settings `
        -Force
}
else {
    Write-Host "Registered nothing."
}
