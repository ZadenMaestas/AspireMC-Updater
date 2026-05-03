import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import requests
import zipfile
import os
import sys
import subprocess
import threading
import tempfile
import webbrowser

MODPACK_URL = "https://pub-2259c298a3f444afb40f45083b29b3e0.r2.dev/Mods.zip"
TARGET_VERSION = "26.1.2" # Version of minecraft that autodetect searches for

APP_VERSION = "1.4.0"
GITHUB_REPO = "ZadenMaestas/AspireMC-Updater"


def _get_release_asset_name():
    if sys.platform == "win32":
        return "AspireMC-Updater.exe"
    elif sys.platform == "darwin":
        return "AspireMC-Updater-macos"
    else:
        return "AspireMC-Updater-linux"


def _parse_version(v):
    v = v.lstrip("v").split("-")[0]
    try:
        return tuple(int(x) for x in v.split(".")[:3])
    except ValueError:
        return (0, 0, 0)

# -------------------------
# Launcher auto-detection
# -------------------------
def _get_launcher_instance_dirs():
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming"))
        localappdata = os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local"))
        return [
            ("Prism Launcher", os.path.join(appdata, "PrismLauncher", "instances")),
            ("MultiMC",        os.path.join(appdata, "MultiMC", "instances")),
            ("ATLauncher",     os.path.join(localappdata, "ATLauncher", "instances")),
        ]
    elif sys.platform == "darwin":
        sup = os.path.join(home, "Library", "Application Support")
        return [
            ("Prism Launcher", os.path.join(sup, "PrismLauncher", "instances")),
            ("MultiMC",        os.path.join(sup, "multimc", "instances")),
        ]
    else:
        xdg = os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local", "share"))
        return [
            ("Prism Launcher", os.path.join(xdg, "PrismLauncher", "instances")),
            ("MultiMC",        os.path.join(xdg, "multimc", "instances")),
            ("ATLauncher",     os.path.join(xdg, "ATLauncher", "instances")),
        ]


def _instance_matches_version(instance_dir, version):
    if version in os.path.basename(instance_dir):
        return True
    cfg = os.path.join(instance_dir, "instance.cfg")
    if os.path.isfile(cfg):
        try:
            with open(cfg, "r", encoding="utf-8", errors="ignore") as f:
                if version in f.read():
                    return True
        except Exception:
            pass
    return False


def _instance_mods_dir(instance_dir):
    for subdir in (".minecraft", "minecraft"):
        mc = os.path.join(instance_dir, subdir)
        if os.path.isdir(mc):
            return os.path.join(mc, "mods")
    return os.path.join(instance_dir, ".minecraft", "mods")


def detect_mods_folder(version=TARGET_VERSION):
    """Scan known launchers for an instance matching version. Returns (launcher_name, mods_path) or (None, None)."""
    for launcher_name, instances_dir in _get_launcher_instance_dirs():
        if not os.path.isdir(instances_dir):
            continue
        try:
            entries = os.listdir(instances_dir)
        except OSError:
            continue
        for entry in entries:
            instance_dir = os.path.join(instances_dir, entry)
            if not os.path.isdir(instance_dir):
                continue
            if _instance_matches_version(instance_dir, version):
                return launcher_name, _instance_mods_dir(instance_dir)
    return None, None

# -------------------------
# Config (platform-aware)
# -------------------------
def get_config_path():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    config_dir = os.path.join(base, "AspireMC-Updater")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "mods_folder.txt")

def load_saved_folder():
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except Exception:
            return ""
    return ""

def save_folder(folder):
    try:
        with open(get_config_path(), "w") as f:
            f.write(folder)
    except Exception:
        pass

# -------------------------
# Minecraft Launcher Theme
# -------------------------
BG_MAIN        = "#1E1E1E"   # Stone gray
BG_PANEL       = "#2D2D2D"   # Slightly lighter gray
BG_ENTRY       = "#141414"   # Near-black for inputs
BG_BANNER      = "#3B5E00"   # Grass top (dark green)
BG_BANNER_LINE = "#5F9500"   # Bright grass stripe
BTN_GREEN      = "#4E7A00"   # Minecraft grass green
BTN_GREEN_HOV  = "#6AAB00"
BTN_GRAY       = "#4A4A4A"
BTN_GRAY_HOV   = "#636363"
TEXT_WHITE      = "#FFFFFF"
TEXT_LIGHT      = "#CCCCCC"
TEXT_GRAY       = "#888888"
TEXT_LOG        = "#55FF55"  # Classic MC green text
BORDER          = "#3A3A3A"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AspireMC Updater")
        self.geometry("620x590")
        self.resizable(False, False)
        self.configure(bg=BG_MAIN)
        self._updating = False
        self._build_ui()
        saved = load_saved_folder()
        self.mod_folder_var.set(saved)
        if not saved:
            self.after(150, self._first_launch)
        self.after(2000, self._check_for_update_async)

    # --- Label-based button (no OS borders) ---
    def _make_btn(self, parent, text, command, bg, hover_bg, font=("Courier New", 10, "bold"), **kw):
        btn = tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=TEXT_WHITE,
            font=font,
            cursor="hand2",
            padx=14,
            pady=7,
            **kw,
        )
        btn.bind("<Enter>", lambda _: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda _: btn.config(bg=bg))
        btn.bind("<Button-1>", lambda _: command())
        btn._bg_normal = bg
        btn._bg_hover  = hover_bg
        return btn

    def _build_ui(self):
        # --- Banner ---
        banner = tk.Frame(self, bg=BG_BANNER, height=70)
        banner.pack(fill="x")
        banner.pack_propagate(False)

        tk.Label(
            banner,
            text="AspireMC Updater",
            font=("Courier New", 24, "bold"),
            fg=TEXT_WHITE,
            bg=BG_BANNER,
        ).pack(expand=True)

        # Grass stripe
        tk.Frame(self, bg=BG_BANNER_LINE, height=4).pack(fill="x")

        # Subtitle
        tk.Label(
            self,
            text=f"Modpack Synchronization Tool  •  v{APP_VERSION}",
            font=("Courier New", 9),
            fg=TEXT_GRAY,
            bg=BG_MAIN,
        ).pack(pady=(6, 2))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=12)

        # --- Mods folder panel ---
        panel = tk.Frame(self, bg=BG_PANEL)
        panel.pack(fill="x", padx=12, pady=10)

        tk.Label(
            panel,
            text="  MODS FOLDER",
            font=("Courier New", 9, "bold"),
            fg=TEXT_GRAY,
            bg=BG_PANEL,
            anchor="w",
        ).pack(fill="x", padx=2, pady=(8, 4))

        row = tk.Frame(panel, bg=BG_PANEL)
        row.pack(fill="x", padx=10, pady=(0, 10))

        self.mod_folder_var = tk.StringVar()
        # Entry wrapped in a thin border frame
        entry_border = tk.Frame(row, bg=BORDER, padx=1, pady=1)
        entry_border.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Entry(
            entry_border,
            textvariable=self.mod_folder_var,
            bg=BG_ENTRY,
            fg=TEXT_LIGHT,
            insertbackground=TEXT_WHITE,
            relief="flat",
            font=("Courier New", 10),
            bd=0,
            highlightthickness=0,
        ).pack(fill="x", expand=True, ipady=5)

        auto_btn = self._make_btn(row, "Auto-detect", self._auto_detect, BTN_GRAY, BTN_GRAY_HOV)
        auto_btn.pack(side="left", padx=(0, 6))

        browse_btn = self._make_btn(row, "Browse...", self._choose_folder, BTN_GRAY, BTN_GRAY_HOV)
        browse_btn.pack(side="left")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=12)

        # --- Update button ---
        self.update_btn = self._make_btn(
            self,
            "UPDATE MODPACK",
            self._start_update,
            BTN_GREEN,
            BTN_GREEN_HOV,
            font=("Courier New", 15, "bold"),
        )
        self.update_btn.config(pady=18)
        self.update_btn.pack(fill="x", padx=12, pady=10)

        # --- Progress ---
        prog_frame = tk.Frame(self, bg=BG_MAIN)
        prog_frame.pack(fill="x", padx=12, pady=(0, 6))

        self.progress_label = tk.Label(
            prog_frame,
            text="",
            font=("Courier New", 9),
            fg=TEXT_GRAY,
            bg=BG_MAIN,
            anchor="w",
        )
        self.progress_label.pack(fill="x")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "mc.Horizontal.TProgressbar",
            troughcolor=BG_PANEL,
            background=BTN_GREEN_HOV,
            bordercolor=BG_MAIN,
            lightcolor=BTN_GREEN_HOV,
            darkcolor=BTN_GREEN_HOV,
            thickness=14,
        )
        self.progress = ttk.Progressbar(
            prog_frame,
            style="mc.Horizontal.TProgressbar",
            orient="horizontal",
            mode="determinate",
        )
        self.progress.pack(fill="x", pady=(2, 0))

        # --- Log ---
        tk.Label(
            self,
            text="  OPERATION LOG",
            font=("Courier New", 9, "bold"),
            fg=TEXT_GRAY,
            bg=BG_MAIN,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(6, 2))

        self.log_box = scrolledtext.ScrolledText(
            self,
            height=11,
            bg="#0C0C0C",
            fg=TEXT_LOG,
            insertbackground=TEXT_LOG,
            font=("Courier New", 9),
            relief="flat",
            state="disabled",
            bd=0,
            highlightthickness=0,
            selectbackground="#2D2D2D",
        )
        self.log_box.pack(padx=12, pady=(0, 12), fill="both", expand=True)

    # --- First launch ---
    def _first_launch(self):
        launcher, path = detect_mods_folder()
        if launcher and path:
            self.mod_folder_var.set(path)
            save_folder(path)
            messagebox.showinfo(
                "Welcome to AspireMC Updater",
                f"Detected {launcher} instance v{TARGET_VERSION}.\n\nMods folder set automatically:\n{path}",
            )
        else:
            messagebox.showinfo(
                "Welcome to AspireMC Updater",
                "First launch detected!\n\nNo matching launcher instance found. Please select your mods folder manually.",
            )
            self._choose_folder()

    def _auto_detect(self):
        launcher, path = detect_mods_folder()
        if launcher and path:
            self.mod_folder_var.set(path)
            save_folder(path)
            messagebox.showinfo(
                "Auto-detect",
                f"Found {launcher} instance v{TARGET_VERSION}:\n{path}",
            )
        else:
            messagebox.showwarning(
                "Auto-detect",
                f"Could not find a launcher instance matching version {TARGET_VERSION}.\n\nPlease select the mods folder manually.",
            )

    def _choose_folder(self):
        folder = filedialog.askdirectory(title="Select Minecraft Mods Folder")
        if folder:
            self.mod_folder_var.set(folder)
            save_folder(folder)

    # --- Logging ---
    def _log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")

    def _set_progress(self, value, label=""):
        self.progress["value"] = value
        self.progress_label.config(text=label)

    # --- Update flow ---
    def _start_update(self):
        if self._updating:
            return
        if not self.mod_folder_var.get():
            messagebox.showerror("No Folder Set", "Please select your mods folder first.")
            return
        self._updating = True
        self.update_btn.config(text="UPDATING...", bg=BTN_GRAY, cursor="")
        self.update_btn.unbind("<Enter>")
        self.update_btn.unbind("<Leave>")
        self._set_progress(0, "Starting...")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", tk.END)
        self.log_box.configure(state="disabled")
        threading.Thread(target=self._run_update, daemon=True).start()

    def _run_update(self):
        mod_folder = self.mod_folder_var.get()
        zip_path = os.path.join(tempfile.gettempdir(), "aspiremcpacks_mods.zip")

        # Download
        self._log("[INFO]  Connecting to server...")
        try:
            with requests.get(MODPACK_URL, stream=True, timeout=30) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                pct = int(downloaded / total * 100)
                                mb_d = downloaded / 1_048_576
                                mb_t = total / 1_048_576
                                self.after(0, self._set_progress, pct,
                                           f"Downloading...  {mb_d:.1f} / {mb_t:.1f} MB  ({pct}%)")
                            else:
                                self.after(0, self._set_progress, 50,
                                           f"Downloading...  {downloaded / 1_048_576:.1f} MB")
        except Exception as e:
            self._log(f"[ERROR] Download failed: {e}")
            self.after(0, self._finish, False)
            return

        if not zipfile.is_zipfile(zip_path):
            self._log("[ERROR] Downloaded file is not a valid ZIP archive.")
            self.after(0, self._finish, False)
            return

        self._log("[OK]    Download complete.")

        # Clean old mods
        self._log("[INFO]  Removing old mods...")
        self.after(0, self._set_progress, 0, "Removing old mods...")
        os.makedirs(mod_folder, exist_ok=True)
        deleted = 0
        for filename in os.listdir(mod_folder):
            filepath = os.path.join(mod_folder, filename)
            if os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                    deleted += 1
                except OSError as e:
                    self._log(f"[WARN]  Could not delete {filename}: {e}")
        self._log(f"[OK]    Removed {deleted} file(s).")

        # Extract
        self._log("[INFO]  Installing new mods...")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                members = zf.namelist()
                total_files = len(members)
                for i, member in enumerate(members, 1):
                    zf.extract(member, mod_folder)
                    pct = int(i / total_files * 100)
                    self.after(0, self._set_progress, pct,
                               f"Extracting files...  {i} / {total_files}  ({pct}%)")
        except Exception as e:
            self._log(f"[ERROR] Extraction failed: {e}")
            self.after(0, self._finish, False)
            return

        try:
            os.remove(zip_path)
        except Exception:
            pass

        self._log("[OK]    Modpack updated successfully!")
        self.after(0, self._finish, True)

    # --- Self-update ---
    def _check_for_update_async(self):
        threading.Thread(target=self._do_update_check, daemon=True).start()

    def _do_update_check(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            r = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github+json"})
            r.raise_for_status()
            data = r.json()
            latest = data["tag_name"]
            if _parse_version(latest) > _parse_version(APP_VERSION):
                asset_url = None
                asset_name = _get_release_asset_name()
                for asset in data.get("assets", []):
                    if asset["name"] == asset_name:
                        asset_url = asset["browser_download_url"]
                        break
                self.after(0, self._prompt_update, latest.lstrip("v"), asset_url)
        except Exception:
            pass

    def _prompt_update(self, latest_version, asset_url):
        can_auto = getattr(sys, "frozen", False) and asset_url is not None
        msg = f"Version {latest_version} is available (you have {APP_VERSION}).\n\n"
        msg += "Update and restart now?" if can_auto else "Open the releases page to download?"
        if not messagebox.askyesno("Update Available", msg):
            return
        if not can_auto:
            webbrowser.open(f"https://github.com/{GITHUB_REPO}/releases/latest")
            return
        threading.Thread(target=self._download_and_apply_update, args=(asset_url,), daemon=True).start()

    def _download_and_apply_update(self, asset_url):
        self.after(0, self._log, "[INFO]  Downloading update...")
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
            with requests.get(asset_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                for chunk in r.iter_content(65536):
                    if chunk:
                        tmp.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = int(downloaded / total * 100)
                            self.after(0, self._set_progress, pct, f"Downloading update... {pct}%")
            tmp.close()
        except Exception as e:
            self.after(0, self._log, f"[ERROR] Update download failed: {e}")
            return

        self.after(0, self._log, "[INFO]  Applying update and restarting...")
        current_exe = sys.executable

        if sys.platform == "win32":
            bat = os.path.join(tempfile.gettempdir(), "aspiremcupdate.bat")
            with open(bat, "w") as f:
                f.write(
                    f"@echo off\r\n"
                    f"timeout /t 2 /nobreak > nul\r\n"
                    f"move /y \"{tmp.name}\" \"{current_exe}\"\r\n"
                    f"start \"\" \"{current_exe}\"\r\n"
                    f"del \"%~f0\"\r\n"
                )
            subprocess.Popen(
                ["cmd", "/c", bat],
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True,
            )
            self.after(0, self.destroy)
        else:
            try:
                os.chmod(tmp.name, 0o755)
                os.replace(tmp.name, current_exe)
                os.execv(current_exe, sys.argv)
            except Exception as e:
                self.after(0, self._log, f"[ERROR] Failed to apply update: {e}")

    def _finish(self, success):
        self._updating = False
        self.update_btn.config(text="UPDATE MODPACK", bg=BTN_GREEN, cursor="hand2")
        self.update_btn.bind("<Enter>", lambda _: self.update_btn.config(bg=BTN_GREEN_HOV))
        self.update_btn.bind("<Leave>", lambda _: self.update_btn.config(bg=BTN_GREEN))
        if success:
            self._set_progress(100, "Update complete!")
        else:
            self._set_progress(0, "Update failed — check the log above.")


if __name__ == "__main__":
    app = App()
    app.mainloop()
