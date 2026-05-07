import os
import sys
import tempfile
import threading
import webbrowser
import zipfile

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from aspireupdater.config import (
    load_admin_config,
    load_installed_modpack_version,
    load_saved_folder,
    save_admin_config,
    save_folder,
    save_installed_modpack_version,
)
from aspireupdater.constants import (
    APP_VERSION, GITHUB_REPO, MODPACK_URL, MODPACK_VERSION_URL, TARGET_VERSION,
)
from aspireupdater.launcher import detect_mods_folder
from aspireupdater.self_update import (
    apply_update_unix,
    apply_update_windows,
    download_update,
    find_latest_release,
)
from aspireupdater.theme import (
    BG_MAIN, BG_PANEL, BG_ENTRY, BG_BANNER, BG_BANNER_LINE,
    BTN_GREEN, BTN_GREEN_HOV, BTN_GRAY, BTN_GRAY_HOV,
    TEXT_WHITE, TEXT_LIGHT, TEXT_GRAY, TEXT_LOG, BORDER,
    BG_NOTICE, TEXT_NOTICE,
)
from aspireupdater.updater import download_modpack, smart_update, standard_update
from aspireupdater.version import get_release_asset_name, parse_version
from aspireupdater.widgets import make_btn


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
        # Banner
        banner = tk.Frame(self, bg=BG_BANNER, height=70)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(
            banner, text="AspireMC Updater",
            font=("Courier New", 24, "bold"), fg=TEXT_WHITE, bg=BG_BANNER,
        ).pack(expand=True)

        tk.Frame(self, bg=BG_BANNER_LINE, height=4).pack(fill="x")

        tk.Label(
            self,
            text=f"Modpack Synchronization Tool  •  v{APP_VERSION}",
            font=("Courier New", 9), fg=TEXT_GRAY, bg=BG_MAIN,
        ).pack(pady=(6, 2))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=12)

        # Mods folder panel
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

        make_btn(row, "Auto-detect", self._auto_detect, BTN_GRAY, BTN_GRAY_HOV).pack(
            side="left", padx=(0, 6))
        make_btn(row, "Browse...",   self._choose_folder, BTN_GRAY, BTN_GRAY_HOV).pack(
            side="left")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=12)

        # Modpack update notice bar (hidden when text is empty)
        self._modpack_notice = tk.Label(
            self, text="", font=("Courier New", 9, "bold"),
            fg=TEXT_NOTICE, bg=BG_MAIN, anchor="w", padx=12,
        )
        self._modpack_notice.pack(fill="x")

        # Update button
        self.update_btn = make_btn(
            self, "UPDATE MODPACK", self._start_update, BTN_GREEN, BTN_GREEN_HOV,
            font=("Courier New", 15, "bold"),
        )
        self.update_btn.config(pady=18)
        self.update_btn.pack(fill="x", padx=12, pady=10)

        # Progress
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

        # Log
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
        launcher, path = detect_mods_folder(TARGET_VERSION)
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
        launcher, path = detect_mods_folder(TARGET_VERSION)
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
        import requests
        try:
            r = requests.get(MODPACK_VERSION_URL, timeout=10)
            r.raise_for_status()
            data   = r.json()
            latest = data.get("version", "")
            if not latest:
                return
            self._latest_modpack_version = latest
            installed = load_installed_modpack_version()
            if installed is None or parse_version(latest) > parse_version(installed):
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
        from aspireupdater.gui.admin_login import AdminLoginDialog
        from aspireupdater.gui.admin_panel import AdminPanel
        from aspireupdater.gui.admin_setup import AdminSetupDialog

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

        self._log("[INFO]  Connecting to server...")
        try:
            download_modpack(
                MODPACK_URL, zip_path,
                on_progress=lambda p, l: self.after(0, self._set_progress, p, l),
            )
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
            self._log("[INFO]  Admin mode — syncing changed mods only...")
            try:
                updated, total = smart_update(
                    zip_path, mod_folder,
                    on_progress=lambda p, l: self.after(0, self._set_progress, p, l),
                )
            except Exception as e:
                self._log(f"[ERROR] Extraction failed: {e}")
                self.after(0, self._finish, False)
                return
            self._log(f"[OK]    Updated {updated} mod(s), {total - updated} already current.")
        else:
            self._log("[INFO]  Removing old mods...")
            try:
                deleted, total = standard_update(
                    zip_path, mod_folder,
                    on_log=self._log,
                    on_progress=lambda p, l: self.after(0, self._set_progress, p, l),
                )
            except Exception as e:
                self._log(f"[ERROR] Extraction failed: {e}")
                self.after(0, self._finish, False)
                return
            self._log(f"[OK]    Removed {deleted} file(s).")
            self._log(f"[INFO]  Installing new mods...")
            self._log(f"[OK]    {total} mod(s) installed.")

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
            tag, asset_url = find_latest_release(
                GITHUB_REPO, APP_VERSION, get_release_asset_name()
            )
            if tag:
                clean_tag = tag.lstrip("v").split("-")[0]
                self.after(0, self._prompt_update, clean_tag, asset_url)
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
        threading.Thread(
            target=self._download_and_apply_update, args=(asset_url,), daemon=True
        ).start()

    def _download_and_apply_update(self, asset_url):
        self.after(0, self._log, "[INFO]  Downloading update...")
        try:
            tmp_path = download_update(
                asset_url,
                on_progress=lambda p, l: self.after(0, self._set_progress, p, l),
            )
        except Exception as e:
            self.after(0, self._log, f"[ERROR] Update download failed: {e}")
            return

        self.after(0, self._log, "[INFO]  Applying update and restarting...")
        current_exe = sys.executable

        if sys.platform == "win32":
            apply_update_windows(tmp_path, current_exe)
            self.after(0, self.destroy)
        else:
            try:
                apply_update_unix(tmp_path, current_exe)
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
