# cfiler (内骨格) customization

With [Syncthing](https://syncthing.net/), append below on `.stignore` to skip syncing local history.

```
cfiler.ini
```

## Install

```PowerShell
$d = "CraftFiler"; New-Item -Path ($env:APPDATA | Join-Path -ChildPath $d) -Value ($pwd.Path | Join-Path -ChildPath $d) -ItemType Junction
```

If necessary, place (or make symlink of) [`theme.ini`](theme.ini) on `theme/black` .

---

https://sites.google.com/site/craftware/cfiler

https://github.com/crftwr/cfiler
