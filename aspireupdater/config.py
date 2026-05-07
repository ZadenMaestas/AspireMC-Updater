import json
import os
import sys


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
            os.chmod(path, 0o600)
    except Exception:
        pass
