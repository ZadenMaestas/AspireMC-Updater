# AspireMC Updater
[![Build](https://github.com/ZadenMaestas/AspireMC-Updater/actions/workflows/build.yml/badge.svg)](https://github.com/ZadenMaestas/AspireMC-Updater/actions/workflows/build.yml)
#### v1.2.0
##### Updated 5/2/26

A GUI tool for keeping your AspireMC modpack up to date. Downloads the latest mods from the server and installs them into your Minecraft mods folder, replacing whatever was there before.

## Features

- One-click modpack update (download → wipe old mods → extract new mods)
- Auto-detects your mods folder for Prism Launcher, MultiMC, and ATLauncher
- Progress bar and live operation log
- Saves your mods folder path between sessions
- Works on Linux, Windows, and macOS (TBD)

## Running from source

```sh
pip install -r requirements.txt
python gui.py
```

Requires Python 3.9+.

## Building executables

The build script produces a standalone executable. On Linux it builds both a Linux binary and a Windows `.exe`; on other platforms it builds natively.

### Prerequisites

- Python 3.9–3.13 (PyInstaller does not support 3.14+)
- Docker with the daemon running (Linux only, for the Windows cross-compile)

### Build

```sh
# Start Docker daemon (Linux)
sudo systemctl start docker

python build.py
```

Outputs:

| Platform | Path |
|----------|------|
| Linux    | `dist/AspireMC-Updater` |
| Windows  | `dist/AspireMC-Updater.exe` |

The Windows `.exe` is built inside a `cdrx/pyinstaller-windows` Docker container — no Wine setup required. If Docker is unavailable the Windows build is skipped and the Linux build still completes.
