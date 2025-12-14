$drive = $args[0]
$driveEject = New-Object -comObject Shell.Application
$driveEject.Namespace(17).ParseName($drive).InvokeVerb("Eject")
Start-Sleep -Seconds 2
