import tkinter as tk
from tkinter import messagebox

from aspireupdater.auth import verify_password
from aspireupdater.theme import (
    BG_MAIN, BG_PANEL, BG_ENTRY, BG_BANNER, BG_BANNER_LINE,
    BTN_GREEN, BTN_GREEN_HOV,
    TEXT_WHITE, TEXT_LIGHT, TEXT_GRAY, BORDER,
)
from aspireupdater.widgets import make_btn


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

        login_btn = make_btn(self, "LOGIN", self._login, BTN_GREEN, BTN_GREEN_HOV,
                             font=("Courier New", 11, "bold"))
        login_btn.config(pady=14)
        login_btn.pack(fill="x", padx=12, pady=(0, 12))

    def _login(self):
        if verify_password(self._pw_var.get(),
                           self._admin_config["password_hash"],
                           self._admin_config["password_salt"]):
            self.result = True
            self.destroy()
        else:
            messagebox.showerror("Login Failed", "Incorrect password.", parent=self)
            self._pw_var.set("")
