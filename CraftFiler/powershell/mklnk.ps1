$from = $args[0]
$to = $args[1]
$wsShell = New-Object -ComObject WScript.Shell
$shortcut = $WsShell.CreateShortcut($to)
$shortcut.TargetPath = $from
$shortcut.Save()