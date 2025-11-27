import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import requests
import zipfile
import os
import threading

CONFIG_FILE = "config"
MODPACK_URL = "https://pub-2259c298a3f444afb40f45083b29b3e0.r2.dev/mods.zip"  # <-- your R2 URL

# -------------------------
# Load & Save Config
# -------------------------
def load_saved_folder():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return f.read().strip()
        except:
            return ""
    return ""


def save_folder(path):
    try:
        with open(CONFIG_FILE, "w") as f:
            f.write(path)
    except:
        pass


# -------------------------
# File Management Functions
# -------------------------
def delete_all_files_in_directory(directory_path, log):
    if not os.path.exists(directory_path):
        log.insert(tk.END, f"[ERROR] Directory '{directory_path}' does not exist.\n")
        return

    for filename in os.listdir(directory_path):
        filepath = os.path.join(directory_path, filename)
        if os.path.isfile(filepath):
            try:
                os.remove(filepath)
                log.insert(tk.END, f"[DELETE] {filepath}\n")
            except OSError as e:
                log.insert(tk.END, f"[ERROR] Could not delete {filepath}: {e}\n")


def extract_zip_to_folder(zip_file_path, destination_folder, log):
    os.makedirs(destination_folder, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(destination_folder)
        log.insert(tk.END, f"[EXTRACT] Installed new mods.\n")
    except Exception as e:
        log.insert(tk.END, f"[ERROR] Extraction failed: {e}\n")


# -------------------------
# Download
# -------------------------
def download_file(url, output, log):
    log.insert(tk.END, "[DOWNLOAD] Connecting to R2...\n")
    log.see(tk.END)

    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(output, "wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)

        log.insert(tk.END, "[DOWNLOAD] File downloaded.\n")
    except Exception as e:
        log.insert(tk.END, f"[ERROR] Download failed: {e}\n")
        return False

    if not zipfile.is_zipfile(output):
        log.insert(tk.END, "[ERROR] Downloaded file is not a ZIP.\n")
        return False

    return True


# -------------------------
# Main Process (Threaded)
# -------------------------
def run_modpack_update():
    zip_file = "mods.zip"
    mod_folder = mod_folder_var.get()

    log_box.insert(tk.END, "[SYSTEM] Initiating Modpack Sync...\n")
    log_box.see(tk.END)

    save_folder(mod_folder)

    if not download_file(MODPACK_URL, zip_file, log_box):
        return

    log_box.insert(tk.END, "[CLEAN] Purging outdated modules...\n")
    delete_all_files_in_directory(mod_folder, log_box)

    log_box.insert(tk.END, "[EXTRACT] Deploying new modules...\n")
    extract_zip_to_folder(zip_file, mod_folder, log_box)

    try:
        os.remove(zip_file)
        log_box.insert(tk.END, "[CLEAN] Temporary files deleted.\n")
    except:
        pass

    log_box.insert(tk.END, "\n>>> SYNCHRONIZATION COMPLETE <<<\n")
    log_box.see(tk.END)


def start_thread():
    if not mod_folder_var.get():
        messagebox.showerror("ERROR", "Select a mod folder first!")
        return
    threading.Thread(target=run_modpack_update, daemon=True).start()


def choose_mod_folder():
    folder = filedialog.askdirectory()
    if folder:
        mod_folder_var.set(folder)
        save_folder(folder)


# -------------------------
# EVA-01 COLOR THEME
# -------------------------
BG_MAIN   = "#1A0033"
BG_PANEL  = "#2D0057"
BTN_COLOR = "#39FF14"
TEXT_COLOR = "#A6FF4D"
ACCENT = "#00FF00"


# -------------------------
# GUI Setup
# -------------------------
root = tk.Tk()
root.title("Modpack Interface")
root.geometry("550x500")
root.configure(bg=BG_MAIN)

title = tk.Label(
    root,
    text="MODPACK SYNCHRONIZATION SYSTEM",
    font=("Eurostile", 16, "bold"),
    fg=TEXT_COLOR,
    bg=BG_MAIN
)
title.pack(pady=10)

panel = tk.Frame(root, bg=BG_PANEL, bd=4, relief="ridge")
panel.pack(pady=10, padx=10, fill="x")

tk.Label(
    panel,
    text="MOD FOLDER DIRECTORY",
    fg=TEXT_COLOR,
    bg=BG_PANEL,
    font=("Eurostile", 12, "bold")
).pack(pady=5)

mod_folder_var = tk.StringVar(value=load_saved_folder())
mod_entry = tk.Entry(panel, textvariable=mod_folder_var, width=55,
                     bg="#000000", fg=TEXT_COLOR,
                     insertbackground=TEXT_COLOR, relief="sunken")
mod_entry.pack(pady=5)

tk.Button(
    panel,
    text="BROWSE",
    command=choose_mod_folder,
    bg=BTN_COLOR,
    fg="black",
    font=("Eurostile", 11, "bold"),
    activebackground=ACCENT
).pack(pady=5)

tk.Button(
    root,
    text="BEGIN MODPACK UPDATE",
    command=start_thread,
    bg=BTN_COLOR,
    fg="black",
    font=("Eurostile", 14, "bold"),
    height=2,
    width=34,
    activebackground=ACCENT
).pack(pady=10)

tk.Label(root, text="OPERATION LOG", fg=TEXT_COLOR, bg=BG_MAIN,
         font=("Eurostile", 12, "bold")).pack()

log_box = scrolledtext.ScrolledText(
    root,
    width=65,
    height=13,
    bg="black",
    fg="#39FF14",
    insertbackground=TEXT_COLOR,
    borderwidth=3,
    relief="sunken"
)
log_box.pack(pady=5)

root.mainloop()
