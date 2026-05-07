import os
import sys


def get_launcher_instance_dirs():
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
        xdg     = os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local", "share"))
        flatpak = os.path.join(home, ".var", "app", "org.prismlauncher.PrismLauncher",
                               "data", "PrismLauncher", "instances")
        return [
            ("Prism Launcher",          os.path.join(xdg, "PrismLauncher", "instances")),
            ("Prism Launcher (Flatpak)", flatpak),
            ("MultiMC",                 os.path.join(xdg, "multimc",        "instances")),
            ("ATLauncher",              os.path.join(xdg, "ATLauncher",      "instances")),
        ]


def instance_matches_version(instance_dir, version):
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


def instance_mods_dir(instance_dir):
    for subdir in (".minecraft", "minecraft"):
        mc = os.path.join(instance_dir, subdir)
        if os.path.isdir(mc):
            return os.path.join(mc, "mods")
    return os.path.join(instance_dir, ".minecraft", "mods")


def detect_mods_folder(version):
    """Scan known launchers for an instance matching version. Returns (launcher_name, mods_path) or (None, None)."""
    for launcher_name, instances_dir in get_launcher_instance_dirs():
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
            if instance_matches_version(instance_dir, version):
                return launcher_name, instance_mods_dir(instance_dir)
    return None, None


def find_aspiremc_prism_instance():
    """Find the Prism Launcher instance whose directory name contains 'aspiremc' (case-insensitive).
    Checks native install and Flatpak (Steam Deck). Returns (instance_dir, mods_dir) or (None, None)."""
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming"))
        prism_dirs = [os.path.join(appdata, "PrismLauncher", "instances")]
    elif sys.platform == "darwin":
        prism_dirs = [
            os.path.join(home, "Library", "Application Support", "PrismLauncher", "instances"),
        ]
    else:
        xdg = os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local", "share"))
        prism_dirs = [
            os.path.join(xdg, "PrismLauncher", "instances"),
            os.path.join(home, ".var", "app", "org.prismlauncher.PrismLauncher",
                         "data", "PrismLauncher", "instances"),
        ]

    for prism_dir in prism_dirs:
        if not os.path.isdir(prism_dir):
            continue
        try:
            for entry in sorted(os.listdir(prism_dir)):
                if "aspiremc" in entry.lower():
                    idir = os.path.join(prism_dir, entry)
                    if os.path.isdir(idir):
                        return idir, instance_mods_dir(idir)
        except OSError:
            pass
    return None, None
