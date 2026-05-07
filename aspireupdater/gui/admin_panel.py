import json
import os
import tempfile
import threading
import zipfile
from datetime import datetime, timezone

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import requests

from aspireupdater.config import save_admin_config, save_installed_modpack_version
from aspireupdater.constants import MODPACK_VERSION_URL
from aspireupdater.launcher import find_aspiremc_prism_instance
from aspireupdater.theme import (
    BG_MAIN, BG_PANEL, BG_ENTRY, BG_BANNER, BG_BANNER_LINE,
    BTN_GREEN, BTN_GREEN_HOV, BTN_GRAY, BTN_GRAY_HOV,
    TEXT_WHITE, TEXT_LIGHT, TEXT_GRAY, TEXT_LOG, BORDER,
)
from aspireupdater.version import next_version
from aspireupdater.widgets import make_btn


class AdminPanel(tk.Toplevel):
    def __init__(self, master, admin_config):
        super().__init__(master)
        self.title("AspireMC Admin Panel")
        self.geometry("740x700")
        self.resizable(True, True)
        self.configure(bg=BG_MAIN)
        self._app                = master
        self._admin_config       = admin_config
        self._instance_mods_path = None
        self._uploading          = False
        self._build_ui()
        self.after(300, self._refresh_hosted_version)

    # --- UI Construction ---

    def _build_ui(self):
        banner = tk.Frame(self, bg=BG_BANNER, height=55)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(banner, text="AspireMC Admin Panel", font=("Courier New", 18, "bold"),
                 fg=TEXT_WHITE, bg=BG_BANNER).pack(expand=True)
        tk.Frame(self, bg=BG_BANNER_LINE, height=4).pack(fill="x")

        # Hosted version
        hv_outer = tk.Frame(self, bg=BG_PANEL)
        hv_outer.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(hv_outer, text="  HOSTED MODPACK", font=("Courier New", 9, "bold"),
                 fg=TEXT_GRAY, bg=BG_PANEL, anchor="w").pack(fill="x", padx=2, pady=(6, 4))
        hv_row = tk.Frame(hv_outer, bg=BG_PANEL)
        hv_row.pack(fill="x", padx=10, pady=(0, 8))
        self._hosted_lbl = tk.Label(hv_row, text="Fetching...", font=("Courier New", 10),
                                    fg=TEXT_LIGHT, bg=BG_PANEL, anchor="w")
        self._hosted_lbl.pack(side="left", fill="x", expand=True)
        make_btn(hv_row, "Refresh", self._refresh_hosted_version,
                 BTN_GRAY, BTN_GRAY_HOV).pack(side="right")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(4, 0))

        # Prism instance
        inst_outer = tk.Frame(self, bg=BG_PANEL)
        inst_outer.pack(fill="x", padx=12, pady=(8, 0))
        inst_hdr = tk.Frame(inst_outer, bg=BG_PANEL)
        inst_hdr.pack(fill="x", padx=2, pady=(6, 4))
        tk.Label(inst_hdr, text="  PRISM LAUNCHER INSTANCE", font=("Courier New", 9, "bold"),
                 fg=TEXT_GRAY, bg=BG_PANEL, anchor="w").pack(side="left")
        make_btn(inst_hdr, "Scan Instance", self._scan_instance,
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

        # Upload section
        up_outer = tk.Frame(self, bg=BG_PANEL)
        up_outer.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(up_outer, text="  UPLOAD NEW MODPACK", font=("Courier New", 9, "bold"),
                 fg=TEXT_GRAY, bg=BG_PANEL, anchor="w").pack(fill="x", padx=2, pady=(6, 4))

        ver_row = tk.Frame(up_outer, bg=BG_PANEL)
        ver_row.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(ver_row, text="New version:", font=("Courier New", 9),
                 fg=TEXT_GRAY, bg=BG_PANEL).pack(side="left", padx=(0, 8))
        last = self._admin_config.get("last_upload_version")
        self._version_var = tk.StringVar(value=next_version(last) if last else "1.0")
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

        self._upload_btn = make_btn(up_outer, "UPLOAD MODPACK TO R2", self._start_upload,
                                    BTN_GREEN, BTN_GREEN_HOV, font=("Courier New", 11, "bold"))
        self._upload_btn.config(pady=14)
        self._upload_btn.pack(fill="x", padx=2, pady=(0, 8))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(4, 0))

        # Log
        tk.Label(self, text="  UPLOAD LOG", font=("Courier New", 9, "bold"),
                 fg=TEXT_GRAY, bg=BG_MAIN, anchor="w").pack(fill="x", padx=12, pady=(6, 2))
        self._log_box = scrolledtext.ScrolledText(
            self, height=5, bg="#0C0C0C", fg=TEXT_LOG, insertbackground=TEXT_LOG,
            font=("Courier New", 9), relief="flat", state="disabled",
            bd=0, highlightthickness=0, selectbackground=BG_PANEL,
        )
        self._log_box.pack(padx=12, pady=(0, 6), fill="both", expand=True)

        # Progress
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
        idir, mods_dir = find_aspiremc_prism_instance()
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
        self._version_var.set(next_version(last) if last else "1.0")

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
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        threading.Thread(target=self._run_upload, args=(version, notes), daemon=True).start()

    def _run_upload(self, version, notes):
        import boto3
        from botocore.exceptions import ClientError

        mods_dir = self._instance_mods_path
        zip_path = os.path.join(tempfile.gettempdir(), "AspireMC_upload_mods.zip")
        config   = self._admin_config

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
                pct  = 40 + int(uploaded[0] / zip_size * 55)
                mb_u = uploaded[0] / 1_048_576
                mb_t = zip_size    / 1_048_576
                self.after(0, self._admin_set_progress, pct,
                           f"Uploading Mods.zip...  {mb_u:.1f} / {mb_t:.1f} MB  ({pct}%)")

            s3.upload_file(zip_path, config["r2_bucket_name"], "Mods.zip",
                           Callback=_progress_cb)
            self._admin_log("[OK]    Mods.zip uploaded.")

            version_data = {
                "version":       version,
                "release_notes": notes,
                "uploaded_at":   datetime.now(timezone.utc).isoformat(),
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
