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
import json
import hashlib
import secrets
from datetime import datetime, timezone

MODPACK_URL         = "https://pub-2259c298a3f444afb40f45083b29b3e0.r2.dev/Mods.zip"
MODPACK_VERSION_URL = "https://pub-2259c298a3f444afb40f45083b29b3e0.r2.dev/modpack_version.json"
TARGET_VERSION      = "26.1.2"  # Minecraft version that autodetect searches for

APP_VERSION  = "1.5.0"
GITHUB_REPO  = "ZadenMaestas/AspireMC-Updater"


def _get_release_asset_name():
    if sys.platform == "win32":
        return "AspireMC-Updater.exe"
    elif sys.platform == "darwin":
        return "AspireMC-Updater-macos"
    else:
        return "AspireMC-Updater-linux"


def _parse_version(v):
    v = str(v).lstrip("v").split("-")[0]
    try:
        return tuple(int(x) for x in v.split(".")[:3])
    except ValueError:
        return (0, 0, 0)


def _next_version(version):
    """Increment the last numeric component of a version string."""
    parts = version.split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
    except (ValueError, IndexError):
        return version + ".1"
    return ".".join(parts)


# -------------------------
# Launcher auto-detection
# -------------------------
def _get_launcher_instance_dirs():
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        appdata      = os.environ.get("APPDATA",      os.path.join(home, "AppData", "Roaming"))
        localappdata = os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local"))
        return [
            ("Prism Launcher", os.path.join(appdata,      "PrismLauncher", "instances")),
            ("MultiMC",        os.path.join(appdata,      "MultiMC",        "instances")),
            ("ATLauncher",     os.path.join(localappdata, "ATLauncher",      "instances")),
        ]
    elif sys.platform == "darwin":
        sup = os.path.join(home, "Library", "Application Support")
        return [
            ("Prism Launcher", os.path.join(sup, "PrismLauncher", "instances")),
            ("MultiMC",        os.path.join(sup, "multimc",        "instances")),
        ]
    else:
        xdg = os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local", "share"))
        return [
            ("Prism Launcher", os.path.join(xdg, "PrismLauncher", "instances")),
            ("MultiMC",        os.path.join(xdg, "multimc",        "instances")),
            ("ATLauncher",     os.path.join(xdg, "ATLauncher",      "instances")),
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


def _find_aspireMC_prism_instance():
    """Find the Prism Launcher instance whose directory name contains 'aspiremc' (case-insensitive).
    Returns (instance_dir, mods_dir) or (None, None)."""
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        appdata   = os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming"))
        prism_dir = os.path.join(appdata, "PrismLauncher", "instances")
    elif sys.platform == "darwin":
        prism_dir = os.path.join(home, "Library", "Application Support", "PrismLauncher", "instances")
    else:
        xdg       = os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local", "share"))
        prism_dir = os.path.join(xdg, "PrismLauncher", "instances")

    if not os.path.isdir(prism_dir):
        return None, None
    try:
        for entry in sorted(os.listdir(prism_dir)):
            if "aspiremc" in entry.lower():
                idir = os.path.join(prism_dir, entry)
                if os.path.isdir(idir):
                    return idir, _instance_mods_dir(idir)
    except OSError:
        pass
    return None, None


# -------------------------
# Config (platform-aware)
# -------------------------
def get_config_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    config_dir = os.path.join(base, "AspireMC-Updater")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def get_config_path():
    return os.path.join(get_config_dir(), "mods_folder.txt")


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


def load_installed_modpack_version():
    try:
        with open(os.path.join(get_config_dir(), "installed_modpack_version.txt")) as f:
            v = f.read().strip()
            return v or None
    except Exception:
        return None


def save_installed_modpack_version(version):
    try:
        with open(os.path.join(get_config_dir(), "installed_modpack_version.txt"), "w") as f:
            f.write(version)
    except Exception:
        pass


def load_admin_config():
    path = os.path.join(get_config_dir(), "admin_config.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def save_admin_config(config):
    path = os.path.join(get_config_dir(), "admin_config.json")
    try:
        with open(path, "w") as f:
            json.dump(config, f, indent=2)
        if sys.platform != "win32":
            os.chmod(path, 0o600)  # owner read/write only
    except Exception:
        pass


# -------------------------
# Password hashing (PBKDF2-HMAC-SHA256, 260k iterations)
# -------------------------
def _hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_bytes(32)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return digest.hex(), salt.hex()


def _verify_password(password, stored_hash, stored_salt):
    try:
        salt   = bytes.fromhex(stored_salt)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
        return secrets.compare_digest(digest.hex(), stored_hash)
    except Exception:
        return False


# -------------------------
# Shared button factory
# -------------------------
def _make_btn(parent, text, command, bg, hover_bg, font=("Courier New", 10, "bold"), **kw):
    btn = tk.Label(
        parent, text=text, bg=bg, fg="#FFFFFF", font=font,
        cursor="hand2", padx=14, pady=7, **kw,
    )
    btn.bind("<Enter>",   lambda _: btn.config(bg=hover_bg))
    btn.bind("<Leave>",   lambda _: btn.config(bg=bg))
    btn.bind("<Button-1>", lambda _: command())
    btn._bg_normal = bg
    btn._bg_hover  = hover_bg
    return btn


# -------------------------
# Minecraft Launcher Theme
# -------------------------
BG_MAIN        = "#1E1E1E"
BG_PANEL       = "#2D2D2D"
BG_ENTRY       = "#141414"
BG_BANNER      = "#3B5E00"
BG_BANNER_LINE = "#5F9500"
BTN_GREEN      = "#4E7A00"
BTN_GREEN_HOV  = "#6AAB00"
BTN_GRAY       = "#4A4A4A"
BTN_GRAY_HOV   = "#636363"
BTN_RED        = "#7A1500"
BTN_RED_HOV    = "#A31F00"
TEXT_WHITE      = "#FFFFFF"
TEXT_LIGHT      = "#CCCCCC"
TEXT_GRAY       = "#888888"
TEXT_LOG        = "#55FF55"
BORDER          = "#3A3A3A"
BG_NOTICE       = "#5A3000"
TEXT_NOTICE     = "#FFD700"


# =========================================================
# Admin Setup Dialog
# =========================================================
class AdminSetupDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Admin Setup")
        self.configure(bg=BG_MAIN)
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window()

    def _labeled_entry(self, parent, label, show=""):
        tk.Label(parent, text=label, font=("Courier New", 9), fg=TEXT_GRAY,
                 bg=BG_PANEL, anchor="w").pack(fill="x", padx=10, pady=(6, 0))
        border = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        border.pack(fill="x", padx=10, pady=(2, 0))
        var = tk.StringVar()
        tk.Entry(border, textvariable=var, show=show, bg=BG_ENTRY, fg=TEXT_LIGHT,
                 insertbackground=TEXT_WHITE, relief="flat", font=("Courier New", 10),
                 bd=0, highlightthickness=0).pack(fill="x", ipady=5)
        return var

    def _build(self):
        banner = tk.Frame(self, bg=BG_BANNER, height=55)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(banner, text="Admin Setup", font=("Courier New", 18, "bold"),
                 fg=TEXT_WHITE, bg=BG_BANNER).pack(expand=True)
        tk.Frame(self, bg=BG_BANNER_LINE, height=4).pack(fill="x")
        tk.Label(self, text="  Credentials are stored locally in your config directory.",
                 font=("Courier New", 9), fg=TEXT_GRAY, bg=BG_MAIN,
                 anchor="w").pack(fill="x", padx=12, pady=(8, 4))

        pw_frame = tk.Frame(self, bg=BG_PANEL)
        pw_frame.pack(fill="x", padx=12, pady=(0, 8))
        tk.Label(pw_frame, text="  ADMIN PASSWORD", font=("Courier New", 9, "bold"),
                 fg=TEXT_GRAY, bg=BG_PANEL, anchor="w").pack(fill="x", padx=2, pady=(8, 4))
        self._pw_var  = self._labeled_entry(pw_frame, "Password",         show="•")
        self._pw2_var = self._labeled_entry(pw_frame, "Confirm password",  show="•")
        tk.Frame(pw_frame, height=8, bg=BG_PANEL).pack()

        r2_frame = tk.Frame(self, bg=BG_PANEL)
        r2_frame.pack(fill="x", padx=12, pady=(0, 8))
        tk.Label(r2_frame, text="  CLOUDFLARE R2 CREDENTIALS", font=("Courier New", 9, "bold"),
                 fg=TEXT_GRAY, bg=BG_PANEL, anchor="w").pack(fill="x", padx=2, pady=(8, 4))
        self._acct_var   = self._labeled_entry(r2_frame, "Account ID")
        self._akid_var   = self._labeled_entry(r2_frame, "Access Key ID")
        self._skey_var   = self._labeled_entry(r2_frame, "Secret Access Key", show="•")
        self._bucket_var = self._labeled_entry(r2_frame, "Bucket Name")
        tk.Frame(r2_frame, height=8, bg=BG_PANEL).pack()

        submit = _make_btn(self, "CREATE ADMIN ACCOUNT", self._submit,
                           BTN_GREEN, BTN_GREEN_HOV, font=("Courier New", 11, "bold"))
        submit.config(pady=14)
        submit.pack(fill="x", padx=12, pady=(0, 12))

    def _submit(self):
        pw  = self._pw_var.get()
        pw2 = self._pw2_var.get()
        if len(pw) < 8:
            messagebox.showerror("Error", "Password must be at least 8 characters.", parent=self)
            return
        if pw != pw2:
            messagebox.showerror("Error", "Passwords do not match.", parent=self)
            return
        acct   = self._acct_var.get().strip()
        akid   = self._akid_var.get().strip()
        skey   = self._skey_var.get().strip()
        bucket = self._bucket_var.get().strip()
        if not all([acct, akid, skey, bucket]):
            messagebox.showerror("Error", "All Cloudflare R2 fields are required.", parent=self)
            return
        hsh, salt = _hash_password(pw)
        self.result = {
            "password_hash":       hsh,
            "password_salt":       salt,
            "r2_account_id":       acct,
            "r2_access_key_id":    akid,
            "r2_secret_access_key": skey,
            "r2_bucket_name":      bucket,
            "last_upload_manifest": [],
            "last_upload_version": None,
        }
        self.destroy()


# =========================================================
# Admin Login Dialog
# =========================================================
class AdminLoginDialog(tk.Toplevel):
    def __init__(self, master, admin_config):
        super().__init__(master)
        self.title("Admin Login")
        self.configure(bg=BG_MAIN)
        self.resizable(False, False)
        self.grab_set()
        self._admin_config = admin_config
        self.result = False
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window()

    def _build(self):
        banner = tk.Frame(self, bg=BG_BANNER, height=55)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(banner, text="Admin Login", font=("Courier New", 18, "bold"),
                 fg=TEXT_WHITE, bg=BG_BANNER).pack(expand=True)
        tk.Frame(self, bg=BG_BANNER_LINE, height=4).pack(fill="x")

        frame = tk.Frame(self, bg=BG_PANEL)
        frame.pack(fill="x", padx=12, pady=12)
        tk.Label(frame, text="  ADMIN PASSWORD", font=("Courier New", 9, "bold"),
                 fg=TEXT_GRAY, bg=BG_PANEL, anchor="w").pack(fill="x", padx=2, pady=(8, 4))
        tk.Label(frame, text="Password", font=("Courier New", 9),
                 fg=TEXT_GRAY, bg=BG_PANEL, anchor="w").pack(fill="x", padx=10, pady=(0, 2))
        border = tk.Frame(frame, bg=BORDER, padx=1, pady=1)
        border.pack(fill="x", padx=10, pady=(0, 8))
        self._pw_var = tk.StringVar()
        pw_entry = tk.Entry(border, textvariable=self._pw_var, show="•",
                            bg=BG_ENTRY, fg=TEXT_LIGHT, insertbackground=TEXT_WHITE,
                            relief="flat", font=("Courier New", 10), bd=0, highlightthickness=0)
        pw_entry.pack(fill="x", ipady=5)
        pw_entry.bind("<Return>", lambda _: self._login())
        pw_entry.focus_set()

        login_btn = _make_btn(self, "LOGIN", self._login, BTN_GREEN, BTN_GREEN_HOV,
                              font=("Courier New", 11, "bold"))
        login_btn.config(pady=14)
        login_btn.pack(fill="x", padx=12, pady=(0, 12))

    def _login(self):
        if _verify_password(self._pw_var.get(),
                            self._admin_config["password_hash"],
                            self._admin_config["password_salt"]):
            self.result = True
            self.destroy()
        else:
            messagebox.showerror("Login Failed", "Incorrect password.", parent=self)
            self._pw_var.set("")


# =========================================================
# Admin Panel
# =========================================================
class AdminPanel(tk.Toplevel):
    def __init__(self, master, admin_config):
        super().__init__(master)
        self.title("AspireMC Admin Panel")
        self.geometry("740x700")
        self.resizable(True, True)
        self.configure(bg=BG_MAIN)
        self._app              = master
        self._admin_config     = admin_config
        self._instance_mods_path = None
        self._uploading        = False
        self._build_ui()
        self.after(300, self._refresh_hosted_version)

    # --- UI Construction ---
    def _build_ui(self):
        # Banner
        banner = tk.Frame(self, bg=BG_BANNER, height=55)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(banner, text="AspireMC Admin Panel", font=("Courier New", 18, "bold"),
                 fg=TEXT_WHITE, bg=BG_BANNER).pack(expand=True)
        tk.Frame(self, bg=BG_BANNER_LINE, height=4).pack(fill="x")

        # --- Hosted version ---
        hv_outer = tk.Frame(self, bg=BG_PANEL)
        hv_outer.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(hv_outer, text="  HOSTED MODPACK", font=("Courier New", 9, "bold"),
                 fg=TEXT_GRAY, bg=BG_PANEL, anchor="w").pack(fill="x", padx=2, pady=(6, 4))
        hv_row = tk.Frame(hv_outer, bg=BG_PANEL)
        hv_row.pack(fill="x", padx=10, pady=(0, 8))
        self._hosted_lbl = tk.Label(hv_row, text="Fetching...", font=("Courier New", 10),
                                    fg=TEXT_LIGHT, bg=BG_PANEL, anchor="w")
        self._hosted_lbl.pack(side="left", fill="x", expand=True)
        _make_btn(hv_row, "Refresh", self._refresh_hosted_version,
                  BTN_GRAY, BTN_GRAY_HOV).pack(side="right")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(4, 0))

        # --- Prism instance ---
        inst_outer = tk.Frame(self, bg=BG_PANEL)
        inst_outer.pack(fill="x", padx=12, pady=(8, 0))
        inst_hdr = tk.Frame(inst_outer, bg=BG_PANEL)
        inst_hdr.pack(fill="x", padx=2, pady=(6, 4))
        tk.Label(inst_hdr, text="  PRISM LAUNCHER INSTANCE", font=("Courier New", 9, "bold"),
                 fg=TEXT_GRAY, bg=BG_PANEL, anchor="w").pack(side="left")
        _make_btn(inst_hdr, "Scan Instance", self._scan_instance,
                  BTN_GRAY, BTN_GRAY_HOV).pack(side="right", padx=4)

        self._instance_lbl = tk.Label(inst_outer, text="No instance detected",
                                      font=("Courier New", 9), fg=TEXT_GRAY,
                                      bg=BG_PANEL, anchor="w")
        self._instance_lbl.pack(fill="x", padx=10, pady=(0, 4))

        list_frame = tk.Frame(inst_outer, bg=BG_ENTRY)
        list_frame.pack(fill="both", padx=10, pady=(0, 4), expand=True)
        list_sb = tk.Scrollbar(list_frame, bg=BG_PANEL, troughcolor=BG_MAIN,
                               highlightthickness=0, bd=0)
        list_sb.pack(side="right", fill="y")
        self._diff_list = tk.Listbox(
            list_frame, height=7, bg=BG_ENTRY, fg=TEXT_GRAY,
            font=("Courier New", 9), selectbackground=BG_PANEL,
            relief="flat", bd=0, highlightthickness=0, activestyle="none",
            yscrollcommand=list_sb.set,
        )
        self._diff_list.pack(side="left", fill="both", expand=True)
        list_sb.config(command=self._diff_list.yview)

        self._diff_summary = tk.Label(inst_outer, text="Scan an instance to compare mods.",
                                      font=("Courier New", 9), fg=TEXT_GRAY,
                                      bg=BG_PANEL, anchor="w")
        self._diff_summary.pack(fill="x", padx=10, pady=(0, 8))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(4, 0))

        # --- Upload section ---
        up_outer = tk.Frame(self, bg=BG_PANEL)
        up_outer.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(up_outer, text="  UPLOAD NEW MODPACK", font=("Courier New", 9, "bold"),
                 fg=TEXT_GRAY, bg=BG_PANEL, anchor="w").pack(fill="x", padx=2, pady=(6, 4))

        ver_row = tk.Frame(up_outer, bg=BG_PANEL)
        ver_row.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(ver_row, text="New version:", font=("Courier New", 9),
                 fg=TEXT_GRAY, bg=BG_PANEL).pack(side="left", padx=(0, 8))
        last = self._admin_config.get("last_upload_version")
        self._version_var = tk.StringVar(value=_next_version(last) if last else "1.0")
        vborder = tk.Frame(ver_row, bg=BORDER, padx=1, pady=1)
        vborder.pack(side="left")
        tk.Entry(vborder, textvariable=self._version_var, bg=BG_ENTRY, fg=TEXT_LIGHT,
                 insertbackground=TEXT_WHITE, relief="flat", font=("Courier New", 10),
                 bd=0, highlightthickness=0, width=12).pack(ipady=4)

        tk.Label(up_outer, text="Release notes (optional):", font=("Courier New", 9),
                 fg=TEXT_GRAY, bg=BG_PANEL, anchor="w").pack(fill="x", padx=10, pady=(4, 0))
        nborder = tk.Frame(up_outer, bg=BORDER, padx=1, pady=1)
        nborder.pack(fill="x", padx=10, pady=(2, 8))
        self._notes_text = tk.Text(nborder, height=2, bg=BG_ENTRY, fg=TEXT_LIGHT,
                                   insertbackground=TEXT_WHITE, relief="flat",
                                   font=("Courier New", 9), bd=0, highlightthickness=0)
        self._notes_text.pack(fill="x", ipady=4)

        self._upload_btn = _make_btn(up_outer, "UPLOAD MODPACK TO R2", self._start_upload,
                                     BTN_GREEN, BTN_GREEN_HOV,
                                     font=("Courier New", 11, "bold"))
        self._upload_btn.config(pady=14)
        self._upload_btn.pack(fill="x", padx=2, pady=(0, 8))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(4, 0))

        # --- Log ---
        tk.Label(self, text="  UPLOAD LOG", font=("Courier New", 9, "bold"),
                 fg=TEXT_GRAY, bg=BG_MAIN, anchor="w").pack(fill="x", padx=12, pady=(6, 2))
        self._log_box = scrolledtext.ScrolledText(
            self, height=5, bg="#0C0C0C", fg=TEXT_LOG, insertbackground=TEXT_LOG,
            font=("Courier New", 9), relief="flat", state="disabled",
            bd=0, highlightthickness=0, selectbackground=BG_PANEL,
        )
        self._log_box.pack(padx=12, pady=(0, 6), fill="both", expand=True)

        # --- Progress ---
        prog_frame = tk.Frame(self, bg=BG_MAIN)
        prog_frame.pack(fill="x", padx=12, pady=(0, 12))
        self._prog_label = tk.Label(prog_frame, text="", font=("Courier New", 9),
                                    fg=TEXT_GRAY, bg=BG_MAIN, anchor="w")
        self._prog_label.pack(fill="x")
        style = ttk.Style()
        style.configure("adm.Horizontal.TProgressbar", troughcolor=BG_PANEL,
                        background=BTN_GREEN_HOV, bordercolor=BG_MAIN,
                        lightcolor=BTN_GREEN_HOV, darkcolor=BTN_GREEN_HOV, thickness=10)
        self._progress = ttk.Progressbar(prog_frame, style="adm.Horizontal.TProgressbar",
                                         orient="horizontal", mode="determinate")
        self._progress.pack(fill="x", pady=(2, 0))

    # --- Helpers ---
    def _admin_log(self, text):
        def _do():
            self._log_box.configure(state="normal")
            self._log_box.insert(tk.END, text + "\n")
            self._log_box.see(tk.END)
            self._log_box.configure(state="disabled")
        self.after(0, _do)

    def _admin_set_progress(self, value, label=""):
        self._progress["value"] = value
        self._prog_label.config(text=label)

    # --- Hosted version ---
    def _refresh_hosted_version(self):
        threading.Thread(target=self._do_refresh_hosted, daemon=True).start()

    def _do_refresh_hosted(self):
        try:
            r    = requests.get(MODPACK_VERSION_URL, timeout=10)
            r.raise_for_status()
            data = r.json()
            ver  = data.get("version", "?")
            ts   = data.get("uploaded_at", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    ts = dt.strftime("%Y-%m-%d %H:%M UTC")
                except Exception:
                    pass
            text = f"Version: {ver}   Uploaded: {ts}" if ts else f"Version: {ver}"
        except Exception as e:
            text = f"Could not fetch  ({e})"
        self.after(0, lambda t=text: self._hosted_lbl.config(text=t))

    # --- Scan instance ---
    def _scan_instance(self):
        idir, mods_dir = _find_aspireMC_prism_instance()
        if not idir:
            messagebox.showwarning(
                "Not Found",
                "No Prism Launcher instance whose folder name contains 'AspireMC' was found.",
                parent=self,
            )
            return
        if not os.path.isdir(mods_dir):
            messagebox.showwarning(
                "No Mods Folder",
                f"Instance found:\n{idir}\n\nThe mods folder does not exist yet:\n{mods_dir}",
                parent=self,
            )
            return

        self._instance_mods_path = mods_dir
        self._instance_lbl.config(
            text=f"Instance: {os.path.basename(idir)}   ({mods_dir})", fg=TEXT_LIGHT)

        try:
            current = {
                f: os.path.getsize(os.path.join(mods_dir, f))
                for f in os.listdir(mods_dir)
                if os.path.isfile(os.path.join(mods_dir, f))
            }
        except OSError as e:
            messagebox.showerror("Error", f"Cannot read mods folder:\n{e}", parent=self)
            return

        manifest  = self._admin_config.get("last_upload_manifest", [])
        uploaded  = {m["name"]: m["size"] for m in manifest}

        added     = sorted(f for f in current  if f not in uploaded)
        removed   = sorted(f for f in uploaded if f not in current)
        changed   = sorted(f for f in current  if f in uploaded and current[f] != uploaded[f])
        unchanged = sorted(f for f in current  if f in uploaded and current[f] == uploaded[f])

        self._diff_list.delete(0, tk.END)
        for f in added:
            self._diff_list.insert(tk.END, f"+ {f}")
            self._diff_list.itemconfig(tk.END, fg="#55FF55")
        for f in changed:
            self._diff_list.insert(tk.END, f"~ {f}")
            self._diff_list.itemconfig(tk.END, fg="#FFD700")
        for f in removed:
            self._diff_list.insert(tk.END, f"- {f}")
            self._diff_list.itemconfig(tk.END, fg="#FF5555")
        for f in unchanged:
            self._diff_list.insert(tk.END, f"  {f}")
            self._diff_list.itemconfig(tk.END, fg=TEXT_GRAY)

        n = len(current)
        self._diff_summary.config(
            fg=TEXT_LIGHT,
            text=f"{n} mod(s) total  +{len(added)} new  ~{len(changed)} changed  -{len(removed)} removed",
        )

        last = self._admin_config.get("last_upload_version")
        self._version_var.set(_next_version(last) if last else "1.0")

    # --- Upload ---
    def _start_upload(self):
        if self._uploading:
            return
        version = self._version_var.get().strip()
        if not version:
            messagebox.showerror("Error", "Enter a version number.", parent=self)
            return
        if not self._instance_mods_path:
            messagebox.showerror("Error", "Scan a Prism instance first.", parent=self)
            return
        try:
            import boto3  # noqa: F401
        except ImportError:
            messagebox.showerror(
                "Missing Dependency",
                "boto3 is required for R2 upload.\n\nInstall it with:\n  pip install boto3",
                parent=self,
            )
            return
        notes = self._notes_text.get("1.0", tk.END).strip()
        if not messagebox.askyesno(
            "Confirm Upload",
            f"Upload modpack v{version} to Cloudflare R2?\n\n"
            "This will replace the currently hosted modpack for all users.",
            parent=self,
        ):
            return

        self._uploading = True
        self._upload_btn.config(text="UPLOADING...", bg=BTN_GRAY, cursor="")
        self._upload_btn.unbind("<Enter>")
        self._upload_btn.unbind("<Leave>")
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", tk.END)
        self._log_box.configure(state="disabled")
        self._admin_set_progress(0, "Preparing...")
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # Block close during upload
        threading.Thread(target=self._run_upload, args=(version, notes), daemon=True).start()

    def _run_upload(self, version, notes):
        import boto3
        from botocore.exceptions import ClientError

        mods_dir = self._instance_mods_path
        zip_path = os.path.join(tempfile.gettempdir(), "AspireMC_upload_mods.zip")
        config   = self._admin_config

        # Package mods into zip
        self._admin_log("[INFO]  Creating Mods.zip...")
        try:
            mod_files = sorted(
                f for f in os.listdir(mods_dir)
                if os.path.isfile(os.path.join(mods_dir, f))
            )
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, fname in enumerate(mod_files, 1):
                    zf.write(os.path.join(mods_dir, fname), fname)
                    pct = int(i / len(mod_files) * 40)
                    self.after(0, self._admin_set_progress, pct,
                               f"Packaging...  {i} / {len(mod_files)}")
            self._admin_log(f"[OK]    Packed {len(mod_files)} mods.")
        except Exception as e:
            self._admin_log(f"[ERROR] Failed to create zip: {e}")
            self.after(0, self._finish_upload, False)
            return

        # Upload to Cloudflare R2
        self._admin_log("[INFO]  Connecting to Cloudflare R2...")
        try:
            endpoint = f"https://{config['r2_account_id']}.r2.cloudflarestorage.com"
            s3 = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=config["r2_access_key_id"],
                aws_secret_access_key=config["r2_secret_access_key"],
                region_name="auto",
            )

            zip_size = os.path.getsize(zip_path)
            uploaded = [0]

            def _progress_cb(chunk):
                uploaded[0] += chunk
                pct   = 40 + int(uploaded[0] / zip_size * 55)
                mb_u  = uploaded[0] / 1_048_576
                mb_t  = zip_size   / 1_048_576
                self.after(0, self._admin_set_progress, pct,
                           f"Uploading Mods.zip...  {mb_u:.1f} / {mb_t:.1f} MB  ({pct}%)")

            s3.upload_file(zip_path, config["r2_bucket_name"], "Mods.zip",
                           Callback=_progress_cb)
            self._admin_log("[OK]    Mods.zip uploaded.")

            version_data = {
                "version":      version,
                "release_notes": notes,
                "uploaded_at":  datetime.now(timezone.utc).isoformat(),
            }
            s3.put_object(
                Bucket=config["r2_bucket_name"],
                Key="modpack_version.json",
                Body=json.dumps(version_data),
                ContentType="application/json",
            )
            self._admin_log(f"[OK]    Version metadata set to v{version}.")

        except (ClientError, Exception) as e:
            self._admin_log(f"[ERROR] Upload failed: {e}")
            self.after(0, self._finish_upload, False)
            return
        finally:
            try:
                os.remove(zip_path)
            except Exception:
                pass

        # Persist updated manifest so future scans show accurate diffs
        try:
            manifest = [
                {"name": f, "size": os.path.getsize(os.path.join(mods_dir, f))}
                for f in mod_files
            ]
            config["last_upload_manifest"] = manifest
            config["last_upload_version"]  = version
            save_admin_config(config)
            self._admin_config = config
        except Exception as e:
            self._admin_log(f"[WARN]  Could not update local manifest: {e}")

        # Mark admin machine as up-to-date with the version just published
        save_installed_modpack_version(version)
        self.after(0, self._app._hide_modpack_notice)

        self._admin_log(f"[OK]    Modpack v{version} is now live.")
        self.after(0, self._finish_upload, True)

    def _finish_upload(self, success):
        self._uploading = False
        self._upload_btn.config(text="UPLOAD MODPACK TO R2", bg=BTN_GREEN, cursor="hand2")
        self._upload_btn.bind("<Enter>", lambda _: self._upload_btn.config(bg=BTN_GREEN_HOV))
        self._upload_btn.bind("<Leave>", lambda _: self._upload_btn.config(bg=BTN_GREEN))
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        if success:
            self._admin_set_progress(100, "Upload complete!")
            self._refresh_hosted_version()
        else:
            self._admin_set_progress(0, "Upload failed — check log above.")


# =========================================================
# Main Application
# =========================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AspireMC Updater")
        self.geometry("620x590")
        self.resizable(False, False)
        self.configure(bg=BG_MAIN)
        self._updating               = False
        self._latest_modpack_version = None
        self._build_ui()
        saved = load_saved_folder()
        self.mod_folder_var.set(saved)
        if not saved:
            self.after(150, self._first_launch)
        self.after(2000, self._check_for_update_async)
        self.after(2500, self._check_modpack_version_async)
        self.bind("<Control-Shift-A>", self._open_admin_login)
        self.bind("<Control-Shift-a>", self._open_admin_login)

    def _build_ui(self):
        # --- Banner ---
        banner = tk.Frame(self, bg=BG_BANNER, height=70)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(
            banner, text="AspireMC Updater",
            font=("Courier New", 24, "bold"), fg=TEXT_WHITE, bg=BG_BANNER,
        ).pack(expand=True)

        # Grass stripe
        tk.Frame(self, bg=BG_BANNER_LINE, height=4).pack(fill="x")

        # Subtitle
        tk.Label(
            self,
            text=f"Modpack Synchronization Tool  •  v{APP_VERSION}",
            font=("Courier New", 9), fg=TEXT_GRAY, bg=BG_MAIN,
        ).pack(pady=(6, 2))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=12)

        # --- Mods folder panel ---
        panel = tk.Frame(self, bg=BG_PANEL)
        panel.pack(fill="x", padx=12, pady=10)
        tk.Label(
            panel, text="  MODS FOLDER",
            font=("Courier New", 9, "bold"), fg=TEXT_GRAY, bg=BG_PANEL, anchor="w",
        ).pack(fill="x", padx=2, pady=(8, 4))

        row = tk.Frame(panel, bg=BG_PANEL)
        row.pack(fill="x", padx=10, pady=(0, 10))

        self.mod_folder_var = tk.StringVar()
        entry_border = tk.Frame(row, bg=BORDER, padx=1, pady=1)
        entry_border.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Entry(
            entry_border, textvariable=self.mod_folder_var,
            bg=BG_ENTRY, fg=TEXT_LIGHT, insertbackground=TEXT_WHITE,
            relief="flat", font=("Courier New", 10), bd=0, highlightthickness=0,
        ).pack(fill="x", expand=True, ipady=5)

        _make_btn(row, "Auto-detect", self._auto_detect, BTN_GRAY, BTN_GRAY_HOV).pack(
            side="left", padx=(0, 6))
        _make_btn(row, "Browse...",   self._choose_folder, BTN_GRAY, BTN_GRAY_HOV).pack(
            side="left")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=12)

        # Modpack update notice bar (hidden when text is empty)
        self._modpack_notice = tk.Label(
            self, text="", font=("Courier New", 9, "bold"),
            fg=TEXT_NOTICE, bg=BG_MAIN, anchor="w", padx=12,
        )
        self._modpack_notice.pack(fill="x")

        # --- Update button ---
        self.update_btn = _make_btn(
            self, "UPDATE MODPACK", self._start_update, BTN_GREEN, BTN_GREEN_HOV,
            font=("Courier New", 15, "bold"),
        )
        self.update_btn.config(pady=18)
        self.update_btn.pack(fill="x", padx=12, pady=10)

        # --- Progress ---
        prog_frame = tk.Frame(self, bg=BG_MAIN)
        prog_frame.pack(fill="x", padx=12, pady=(0, 6))
        self.progress_label = tk.Label(
            prog_frame, text="", font=("Courier New", 9), fg=TEXT_GRAY, bg=BG_MAIN, anchor="w",
        )
        self.progress_label.pack(fill="x")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "mc.Horizontal.TProgressbar",
            troughcolor=BG_PANEL, background=BTN_GREEN_HOV,
            bordercolor=BG_MAIN, lightcolor=BTN_GREEN_HOV,
            darkcolor=BTN_GREEN_HOV, thickness=14,
        )
        self.progress = ttk.Progressbar(
            prog_frame, style="mc.Horizontal.TProgressbar",
            orient="horizontal", mode="determinate",
        )
        self.progress.pack(fill="x", pady=(2, 0))

        # --- Log ---
        tk.Label(
            self, text="  OPERATION LOG",
            font=("Courier New", 9, "bold"), fg=TEXT_GRAY, bg=BG_MAIN, anchor="w",
        ).pack(fill="x", padx=12, pady=(6, 2))
        self.log_box = scrolledtext.ScrolledText(
            self, height=11, bg="#0C0C0C", fg=TEXT_LOG, insertbackground=TEXT_LOG,
            font=("Courier New", 9), relief="flat", state="disabled",
            bd=0, highlightthickness=0, selectbackground="#2D2D2D",
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
            messagebox.showinfo("Auto-detect", f"Found {launcher} instance v{TARGET_VERSION}:\n{path}")
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

    # --- Modpack version check ---
    def _check_modpack_version_async(self):
        threading.Thread(target=self._do_modpack_version_check, daemon=True).start()

    def _do_modpack_version_check(self):
        try:
            r = requests.get(MODPACK_VERSION_URL, timeout=10)
            r.raise_for_status()
            data   = r.json()
            latest = data.get("version", "")
            if not latest:
                return
            self._latest_modpack_version = latest
            installed = load_installed_modpack_version()
            if installed is None or _parse_version(latest) > _parse_version(installed):
                self.after(0, self._show_modpack_notice, latest)
        except Exception:
            pass

    def _show_modpack_notice(self, latest_version):
        installed = load_installed_modpack_version()
        if installed:
            msg = f"  ▲ Modpack v{latest_version} available (installed: v{installed}) — click UPDATE MODPACK"
        else:
            msg = f"  ▲ Modpack v{latest_version} available — click UPDATE MODPACK to install"
        self._modpack_notice.config(text=msg, bg=BG_NOTICE, pady=5)

    def _hide_modpack_notice(self):
        self._modpack_notice.config(text="", bg=BG_MAIN, pady=0)

    # --- Admin access (Ctrl+Shift+A) ---
    def _open_admin_login(self, event=None):
        config = load_admin_config()
        if config is None:
            dlg = AdminSetupDialog(self)
            if dlg.result:
                save_admin_config(dlg.result)
                messagebox.showinfo("Admin Setup", "Admin account created successfully.")
                AdminPanel(self, dlg.result)
        else:
            dlg = AdminLoginDialog(self, config)
            if dlg.result:
                AdminPanel(self, config)

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
        zip_path   = os.path.join(tempfile.gettempdir(), "aspiremcpacks_mods.zip")

        # Download
        self._log("[INFO]  Connecting to server...")
        try:
            with requests.get(MODPACK_URL, stream=True, timeout=30) as r:
                r.raise_for_status()
                total      = int(r.headers.get("content-length", 0))
                downloaded = 0
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                pct  = int(downloaded / total * 100)
                                mb_d = downloaded / 1_048_576
                                mb_t = total      / 1_048_576
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

        os.makedirs(mod_folder, exist_ok=True)
        is_admin = load_admin_config() is not None

        if is_admin:
            # Smart update: only extract mods that are new or have changed size.
            # Existing mods not in the zip are left untouched.
            self._log("[INFO]  Admin mode — syncing changed mods only...")
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    members     = zf.infolist()
                    total_files = len(members)
                    updated     = 0
                    for i, info in enumerate(members, 1):
                        dest = os.path.join(mod_folder, info.filename)
                        if os.path.isfile(dest) and os.path.getsize(dest) == info.file_size:
                            pct = int(i / total_files * 100)
                            self.after(0, self._set_progress, pct,
                                       f"Checking...  {i} / {total_files}  ({pct}%)")
                            continue
                        zf.extract(info, mod_folder)
                        updated += 1
                        pct = int(i / total_files * 100)
                        self.after(0, self._set_progress, pct,
                                   f"Updating...  {i} / {total_files}  ({pct}%)")
            except Exception as e:
                self._log(f"[ERROR] Extraction failed: {e}")
                self.after(0, self._finish, False)
                return
            self._log(f"[OK]    Updated {updated} mod(s), {total_files - updated} already current.")
        else:
            # Standard update: wipe mods folder then extract everything fresh.
            self._log("[INFO]  Removing old mods...")
            self.after(0, self._set_progress, 0, "Removing old mods...")
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

            self._log("[INFO]  Installing new mods...")
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    members     = zf.namelist()
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
            r   = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github+json"})
            r.raise_for_status()
            data   = r.json()
            latest = data["tag_name"]
            if _parse_version(latest) > _parse_version(APP_VERSION):
                asset_url  = None
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
        msg  = f"Version {latest_version} is available (you have {APP_VERSION}).\n\n"
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
                total      = int(r.headers.get("content-length", 0))
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
            if self._latest_modpack_version:
                save_installed_modpack_version(self._latest_modpack_version)
                self._hide_modpack_notice()
        else:
            self._set_progress(0, "Update failed — check the log above.")


if __name__ == "__main__":
    app = App()
    app.mainloop()
