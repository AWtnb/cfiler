# cfiler (内骨格) customization

With [Syncthing](https://syncthing.net/), append below on `.stignore` to skip syncing local history.

```
cfiler.ini
```

## Install

```PowerShell
$d = "CraftFiler"; New-Item -Path ($env:APPDATA | Join-Path -ChildPath $d) -Value ($pwd.Path | Join-Path -ChildPath $d) -ItemType Junction
```

Run [`set-startup.ps1`](set-startup.ps1) makes shortcut (.lnk) to windows startup.

---

https://sites.google.com/site/craftware/cfiler

https://github.com/crftwr/cfiler
