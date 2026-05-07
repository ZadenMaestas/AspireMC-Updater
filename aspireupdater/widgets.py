import tkinter as tk


def make_btn(parent, text, command, bg, hover_bg, font=("Courier New", 10, "bold"), **kw):
    btn = tk.Label(
        parent, text=text, bg=bg, fg="#FFFFFF", font=font,
        cursor="hand2", padx=14, pady=7, **kw,
    )
    btn.bind("<Enter>",    lambda _: btn.config(bg=hover_bg))
    btn.bind("<Leave>",    lambda _: btn.config(bg=bg))
    btn.bind("<Button-1>", lambda _: command())
    btn._bg_normal = bg
    btn._bg_hover  = hover_bg
    return btn
