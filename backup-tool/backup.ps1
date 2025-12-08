param([parameter(Mandatory)]$backupDir)

$maxGen = 15

if (-not $backupDir) {
    $log = "{0} Backup dest path is not specified." -f (Get-Date -Format "yyyyMMdd-HH:mm:ss")
    $log | Out-File -FilePath ($env:USERPROFILE | Join-Path -ChildPath "Desktop\CFiler-backup-error.log") -Append
    [System.Environment]::exit(1)
}

if (-not (Test-Path $backupDir -PathType Container)) {
    New-Item -Path $backupDir -ItemType Directory > $null
}

function logWrite {
    param (
        [switch]$asError
    )
    $log = $input -join ""
    if ($asError) {
        $log = "[ERROR] " + $log
    }
    $log = (Get-Date -Format "yyyyMMdd-HH:mm:ss ") + $log
    $log | Out-File -FilePath ($backupDir | Join-Path -ChildPath "backup.log") -Append
}

$src = $env:APPDATA | Join-Path -ChildPath "CraftFiler\cfiler.ini"
if (-not (Test-Path $src)) {
    "'{0}' not found." -f $src | logWrite -asError
    [System.Environment]::exit(1)
}

try {

    "Starting backup for '{0}'..." -f $src | Write-Host

    $backups = @(Get-ChildItem $backupDir -Filter "*.txt")
    if ($backups.Count -gt 0) {
        $lastHash = ($backups | Sort-Object -Property LastWriteTime | Select-Object -Last 1 | Get-FileHash).Hash
        if ((Get-FileHash -Path $src).Hash -eq $lastHash) {
            "skipped (cfiler.ini not updated since last backup)" -f $src | logWrite
            [System.Environment]::exit(0)
        }
    }

    $backupCountBeforeRun = $backups.Count

    $backupName = "{0}{1}.txt" -f (Get-Item $src).BaseName, (Get-Date -Format "yyyyMMddHHmmss")
    $backupPath = $backupDir | Join-Path -ChildPath $backupName
    Get-Item $src | Copy-Item -Destination $backupPath
    "created backup '{0}'." -f $backupName | logWrite

    if ($backupCountBeforeRun -eq $maxGen) {
        $oldest = $backups | Sort-Object -Property LastWriteTime | Select-Object -First 1
        $oldest | Remove-Item -ErrorAction stop
        "removed oldest backup '{0}'." -f $oldest.Name | logWrite
    }
}
catch {
    $_ | logWrite -asError
    [System.Environment]::exit(1)
}

[System.Environment]::exit(0)
