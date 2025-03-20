# README

[cfiler](https://github.com/crftwr/cfiler) (内骨格) customization.

## Install

```PowerShell
$d = "CraftFiler"; New-Item -Path ($env:APPDATA | Join-Path -ChildPath $d) -Value ($pwd.Path | Join-Path -ChildPath $d) -ItemType Junction
```

With [Syncthing](https://syncthing.net/), append below on `.stignore` to skip syncing local history.

```
(?d)cfiler.ini
```
