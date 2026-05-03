#!/usr/bin/env python3
"""
AspireMC-Updater build script.

On Linux: builds both a Linux executable and a Windows .exe (via Docker).
On Windows/macOS: builds only the native executable.

  Linux   → dist/AspireMC-Updater
  Windows → dist/AspireMC-Updater.exe

Requirements: Python 3.9–3.13  (PyInstaller does not yet support 3.14+)
PyInstaller is installed automatically if missing.
Windows cross-compilation requires Docker with the daemon running.
"""
import os
import shutil
import subprocess
import sys

APP_NAME = "AspireMC-Updater"
ENTRY    = "gui.py"

# Docker image used for Windows cross-compilation
# cdrx/pyinstaller-windows bundles Python + PyInstaller for Windows builds.
DOCKER_IMAGE = "cdrx/pyinstaller-windows:python3"


def run(cmd: list[str]) -> None:
    print("  $", " ".join(cmd))
    subprocess.run(cmd, check=True)


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[*] PyInstaller not found — installing...")
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])


def clean() -> None:
    for path in ("build", "dist", f"{APP_NAME}.spec"):
        if os.path.exists(path):
            print(f"[*] Removing {path}")
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)


def _pyinstaller_cmd(python: str, windowed: bool) -> list[str]:
    cmd = [
        python, "-m", "PyInstaller",
        "--onefile",
        "--name", APP_NAME,
        "--clean",
        "--noupx",
    ]
    if windowed:
        cmd.append("--windowed")
    cmd.append(ENTRY)
    return cmd


def build_linux() -> str:
    print(f"\n[*] Building Linux executable ({sys.version.split()[0]})...")
    run(_pyinstaller_cmd(sys.executable, windowed=False))
    return os.path.join("dist", APP_NAME)


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"], capture_output=True
    )
    return result.returncode == 0


def build_windows_via_docker() -> str | None:
    """Cross-compile a Windows .exe using a Docker container. Returns output path or None."""
    if not _docker_available():
        print(
            "\n[!] Docker not available — skipping Windows cross-compilation.\n"
            "    Install Docker and start the daemon to enable this target.\n"
            "    https://docs.docker.com/engine/install/"
        )
        return None

    print(f"\n[*] Building Windows .exe via Docker ({DOCKER_IMAGE})...")

    # Build the PyInstaller command to run inside the container.
    # The image mounts /src and outputs to /src/dist/windows/.
    pip_install = "pip install -r requirements.txt && " if os.path.exists("requirements.txt") else ""
    inner_cmd = (
        f"{pip_install}"
        f"pyinstaller --onefile --windowed --name {APP_NAME} --clean --noupx {ENTRY}"
    )

    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{os.getcwd()}:/src",
        DOCKER_IMAGE,
        inner_cmd,
    ]

    try:
        run(docker_cmd)
    except subprocess.CalledProcessError:
        print("[!] Docker Windows build failed.")
        return None

    # cdrx/pyinstaller-windows outputs to dist/windows/; move to dist/ for consistency.
    src = os.path.join("dist", "windows", APP_NAME + ".exe")
    dst = os.path.join("dist", APP_NAME + ".exe")
    if os.path.exists(src):
        shutil.move(src, dst)
        # Clean up the now-empty windows/ subdir if empty
        win_dir = os.path.join("dist", "windows")
        if os.path.isdir(win_dir) and not os.listdir(win_dir):
            os.rmdir(win_dir)
        return dst

    print(f"[!] Expected output not found: {src}")
    return None


def build_native_nonlinux() -> str:
    print(f"\n[*] Building for {sys.platform} ({sys.version.split()[0]})...")
    windowed = sys.platform in ("win32", "darwin")
    run(_pyinstaller_cmd(sys.executable, windowed=windowed))
    suffix = ".exe" if sys.platform == "win32" else ""
    return os.path.join("dist", APP_NAME + suffix)


def report(outputs: list[tuple[str, str]]) -> None:
    print()
    ok = True
    for label, path in outputs:
        if os.path.exists(path):
            mb = os.path.getsize(path) / 1_048_576
            print(f"[OK] {label:8s} {path}  ({mb:.1f} MB)")
        else:
            print(f"[ERROR] {label}: expected output not found: {path}")
            ok = False
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    ver = sys.version_info
    if ver >= (3, 14):
        print(
            f"[WARN] Python {ver.major}.{ver.minor} detected.\n"
            "       PyInstaller currently supports up to Python 3.13.\n"
            "       The build may fail — consider using Python 3.12 or 3.13.\n"
        )

    ensure_pyinstaller()
    clean()

    if sys.platform == "linux":
        outputs = []
        outputs.append(("Linux", build_linux()))
        win = build_windows_via_docker()
        if win:
            outputs.append(("Windows", win))
    else:
        label = "Windows" if sys.platform == "win32" else "macOS"
        outputs = [(label, build_native_nonlinux())]

    report(outputs)
