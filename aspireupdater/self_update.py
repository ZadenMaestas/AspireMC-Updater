import os
import shutil
import subprocess
import sys
import tempfile

import requests

from .version import parse_version


def find_latest_release(repo, current_version, asset_name):
    """Query GitHub Releases for a newer version that has the given asset.

    Returns (tag_str, asset_url) or (None, None).
    """
    url = f"https://api.github.com/repos/{repo}/releases?per_page=10"
    r   = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github+json"})
    r.raise_for_status()
    best_tag   = None
    best_asset = None
    best_ver   = parse_version(current_version)
    for rel in r.json():
        tag = rel.get("tag_name", "")
        ver = parse_version(tag)
        if ver > best_ver:
            best_ver   = ver
            best_tag   = tag
            best_asset = None
            for asset in rel.get("assets", []):
                if asset["name"] == asset_name:
                    best_asset = asset["browser_download_url"]
                    break
    return best_tag, best_asset


def download_update(asset_url, on_progress=None):
    """Download update binary to a temp file. Returns the temp file path."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
    with requests.get(asset_url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total      = int(r.headers.get("content-length", 0))
        downloaded = 0
        for chunk in r.iter_content(65536):
            if chunk:
                tmp.write(chunk)
                downloaded += len(chunk)
                if on_progress and total:
                    pct = int(downloaded / total * 100)
                    on_progress(pct, f"Downloading update... {pct}%")
    tmp.close()
    return tmp.name


def apply_update_windows(tmp_path, current_exe):
    bat = os.path.join(tempfile.gettempdir(), "aspiremcupdate.bat")
    with open(bat, "w") as f:
        f.write(
            f"@echo off\r\n"
            f"timeout /t 2 /nobreak > nul\r\n"
            f"move /y \"{tmp_path}\" \"{current_exe}\"\r\n"
            f"start \"\" \"{current_exe}\"\r\n"
            f"del \"%~f0\"\r\n"
        )
    subprocess.Popen(
        ["cmd", "/c", bat],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
    )


def apply_update_unix(tmp_path, current_exe):
    os.chmod(tmp_path, 0o755)
    # os.replace is an atomic rename that fails with EXDEV (errno 18) when /tmp and
    # the target are on different filesystems (common on Linux/Steam Deck).
    # shutil.copy2 copies file content across devices, then we remove the temp file.
    shutil.copy2(tmp_path, current_exe)
    os.remove(tmp_path)
    os.execv(current_exe, sys.argv)
