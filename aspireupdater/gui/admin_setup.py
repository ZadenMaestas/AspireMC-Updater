import tkinter as tk
from tkinter import messagebox

from aspireupdater.auth import hash_password
from aspireupdater.theme import (
    BG_MAIN, BG_PANEL, BG_ENTRY, BG_BANNER, BG_BANNER_LINE,
    BTN_GREEN, BTN_GREEN_HOV,
    TEXT_WHITE, TEXT_LIGHT, TEXT_GRAY, BORDER,
)
from aspireupdater.widgets import make_btn


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
        self._pw_var  = self._labeled_entry(pw_frame, "Password",        show="•")
        self._pw2_var = self._labeled_entry(pw_frame, "Confirm password", show="•")
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

        submit = make_btn(self, "CREATE ADMIN ACCOUNT", self._submit,
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
        hsh, salt = hash_password(pw)
        self.result = {
            "password_hash":        hsh,
            "password_salt":        salt,
            "r2_account_id":        acct,
            "r2_access_key_id":     akid,
            "r2_secret_access_key": skey,
            "r2_bucket_name":       bucket,
            "last_upload_manifest": [],
            "last_upload_version":  None,
        }
        self.destroy()
