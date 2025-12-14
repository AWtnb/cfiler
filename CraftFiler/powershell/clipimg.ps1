$path = $args[0]
Add-Type -AssemblyName System.Windows.Forms
[Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile($path))