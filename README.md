# AspireMC Updater
[![Build](https://github.com/ZadenMaestas/AspireMC-Updater/actions/workflows/build.yml/badge.svg)](https://github.com/ZadenMaestas/AspireMC-Updater/actions/workflows/build.yml)
#### v1.5.2
##### Updated 5/7/26

A GUI tool for keeping your AspireMC modpack up to date. Downloads the latest mods from the server and installs them into your Minecraft mods folder.

## Features

- One-click modpack update (download → wipe old mods → extract new mods)
- Auto-detects your mods folder for Prism Launcher (native + Flatpak/Steam Deck), MultiMC, and ATLauncher
- Modpack version tracking — notifies you when a new modpack version is available
- Admin panel (Ctrl+Shift+A) for uploading new modpack versions to Cloudflare R2
  - Smart update mode: only re-extracts mods that changed, leaving others untouched
  - Mod diff view: shows added, changed, and removed mods vs. last upload
- Self-updating: detects new app releases on GitHub and applies them automatically
- Progress bar and live operation log
- Saves your mods folder path between sessions
- Works on Linux, Windows, and macOS

## Running from source

```sh
pip install -r requirements.txt
python gui.py
```

Requires Python 3.9+.

### Running tests

```sh
pip install pytest
pytest
```

65 tests covering version parsing, password auth, config I/O, launcher detection, and the modpack update logic.

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

## Project structure

```
gui.py                        # Entry point
aspireupdater/
    constants.py              # URLs, version, repo
    theme.py                  # UI color constants
    version.py                # Version parsing and comparison
    config.py                 # Config file load/save
    launcher.py               # Launcher auto-detection
    auth.py                   # Password hashing (PBKDF2-HMAC-SHA256)
    updater.py                # Modpack download and extraction logic
    self_update.py            # App self-update logic
    widgets.py                # Shared button widget factory
    gui/
        admin_setup.py        # Admin account setup dialog
        admin_login.py        # Admin login dialog
        admin_panel.py        # Admin upload panel
        app.py                # Main application window
tests/
    test_auth.py
    test_config.py
    test_launcher.py
    test_updater.py
    test_version.py
```

## Changelog

### v1.5.1 — 2026-05-07
- **Fix:** Auto-update on Linux/Steam Deck failed with `[Errno 18] Invalid cross-device link` when `/tmp` and the app's location were on different filesystems. Replaced `os.replace` (atomic rename, same-device only) with `shutil.copy2` + cleanup.
- **Fix:** Steam Deck users with Flatpak Prism Launcher were not auto-detected. Added `~/.var/app/org.prismlauncher.PrismLauncher/data/PrismLauncher/instances` to both the folder auto-detect and admin panel instance scan.
- **Refactor:** Split monolithic `gui.py` (1200+ lines) into the `aspireupdater/` package — update logic, config, launcher detection, auth, and self-update are now independent modules with no GUI dependency.
- **Tests:** Added 65-test suite (`pytest`) covering all pure-logic modules.

### v1.5.0
- Modpack versioning: tracks installed version, shows banner when an update is available
- Admin panel (Ctrl+Shift+A): upload new modpack to Cloudflare R2, view mod diff vs. last upload
- Smart update mode for admins: skips mods that haven't changed

### v1.4.0
- Self-update: detects new GitHub releases and applies them in-place on Windows and Linux

### v1.3.0
- Auto-detect mods folder across Prism Launcher, MultiMC, and ATLauncher
- First-launch setup flow

### v1.2.0
- Initial release
