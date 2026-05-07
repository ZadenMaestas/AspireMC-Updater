import sys


def parse_version(v):
    v = str(v).lstrip("v").split("-")[0]
    try:
        return tuple(int(x) for x in v.split(".")[:3])
    except ValueError:
        return (0, 0, 0)


def next_version(version):
    """Increment the last numeric component of a version string."""
    parts = version.split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
    except (ValueError, IndexError):
        return version + ".1"
    return ".".join(parts)


def get_release_asset_name():
    if sys.platform == "win32":
        return "AspireMC-Updater.exe"
    elif sys.platform == "darwin":
        return "AspireMC-Updater-macos"
    else:
        return "AspireMC-Updater-linux"
