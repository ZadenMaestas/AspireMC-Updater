import os
import zipfile

import requests


def download_modpack(url, dest_path, on_progress=None):
    """Download the modpack zip to dest_path. Raises on failure.

    on_progress(pct: int, label: str) is called as the download progresses.
    """
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        total      = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        if total:
                            pct  = int(downloaded / total * 100)
                            mb_d = downloaded / 1_048_576
                            mb_t = total      / 1_048_576
                            on_progress(pct, f"Downloading...  {mb_d:.1f} / {mb_t:.1f} MB  ({pct}%)")
                        else:
                            on_progress(50, f"Downloading...  {downloaded / 1_048_576:.1f} MB")


def smart_update(zip_path, mod_folder, on_progress=None):
    """Extract only new or size-changed mods from zip_path into mod_folder.

    Returns (updated_count, total_count).
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        members     = zf.infolist()
        total_files = len(members)
        updated     = 0
        for i, info in enumerate(members, 1):
            dest = os.path.join(mod_folder, info.filename)
            if os.path.isfile(dest) and os.path.getsize(dest) == info.file_size:
                if on_progress:
                    pct = int(i / total_files * 100)
                    on_progress(pct, f"Checking...  {i} / {total_files}  ({pct}%)")
                continue
            zf.extract(info, mod_folder)
            updated += 1
            if on_progress:
                pct = int(i / total_files * 100)
                on_progress(pct, f"Updating...  {i} / {total_files}  ({pct}%)")
    return updated, total_files


def standard_update(zip_path, mod_folder, on_log=None, on_progress=None):
    """Remove all existing mods then extract everything fresh from zip_path.

    Returns (deleted_count, extracted_count).
    """
    if on_progress:
        on_progress(0, "Removing old mods...")
    deleted = 0
    for filename in os.listdir(mod_folder):
        filepath = os.path.join(mod_folder, filename)
        if os.path.isfile(filepath):
            try:
                os.remove(filepath)
                deleted += 1
            except OSError as e:
                if on_log:
                    on_log(f"[WARN]  Could not delete {filename}: {e}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        members     = zf.namelist()
        total_files = len(members)
        for i, member in enumerate(members, 1):
            zf.extract(member, mod_folder)
            if on_progress:
                pct = int(i / total_files * 100)
                on_progress(pct, f"Extracting files...  {i} / {total_files}  ({pct}%)")
    return deleted, total_files
