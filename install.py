#!/usr/bin/env python3
"""Cross-platform installer for LUMO-Term.

Works on Linux, macOS, and Windows with nothing beyond a Python 3.10+
interpreter — no bash required. `setup.sh` on Linux/macOS is a thin wrapper
around this script; Windows users run it directly (`python install.py`) or
via `setup.ps1`.
"""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VENV_DIR = SCRIPT_DIR / "venv"
IS_WINDOWS = platform.system() == "Windows"


def info(msg: str) -> None:
    print(f"[INFO] {msg}")


def success(msg: str) -> None:
    print(f"[OK] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def error(msg: str) -> None:
    print(f"[ERROR] {msg}")
    sys.exit(1)


def venv_python() -> Path:
    if IS_WINDOWS:
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python3"


def venv_bin_dir() -> Path:
    return VENV_DIR / ("Scripts" if IS_WINDOWS else "bin")


def check_python_version() -> None:
    info("Checking Python version...")
    if sys.version_info < (3, 10):
        error(
            f"Python 3.10+ required, found {platform.python_version()}. "
            "Install a newer Python and re-run this script with it."
        )
    success(f"Python {platform.python_version()} found")


def create_venv() -> None:
    info("Setting up virtual environment...")
    if VENV_DIR.exists():
        success("Virtual environment already exists")
        return
    subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    success("Virtual environment created")


def install_dependencies() -> None:
    info("Installing dependencies...")
    py = str(venv_python())
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip", "-q"], check=True)
    subprocess.run([py, "-m", "pip", "install", "-e", str(SCRIPT_DIR), "-q"], check=True)
    success("Dependencies installed")


_BROWSER_PROBE_SCRIPT = """
import json
from lumo_term.browsers.profiles import (
    detect_installed_browsers,
    find_firefox_profile,
    find_chromium_profile,
)

installed = detect_installed_browsers()
profiles = {}
for name in installed:
    if name == "firefox":
        found = find_firefox_profile()
        profiles[name] = str(found) if found else None
    else:
        found = find_chromium_profile(name)
        profiles[name] = str(found[0] / found[1]) if found else None

print(json.dumps({"installed": installed, "profiles": profiles}))
"""


def check_browsers() -> None:
    info("Checking installed browsers...")
    py = str(venv_python())
    result = subprocess.run([py, "-c", _BROWSER_PROBE_SCRIPT], capture_output=True, text=True)

    if result.returncode != 0:
        warn(f"Could not probe installed browsers: {result.stderr.strip()}")
        return

    try:
        data = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        warn("Could not parse browser detection output")
        return

    installed = data.get("installed", [])
    profiles = data.get("profiles", {})

    if not installed:
        warn("No supported browser (Firefox, Chrome, Edge, Chromium) found.")
        print("  Install one of them and log in to LUMO+: https://lumo.proton.me")
        return

    for name in installed:
        profile = profiles.get(name)
        if profile:
            success(f"{name.capitalize()} found — profile: {profile}")
        else:
            warn(f"{name.capitalize()} is installed but no profile was found.")
            print(f"    Log in to LUMO+ in {name.capitalize()} first: https://lumo.proton.me")


def check_clipboard_tool() -> None:
    info("Checking clipboard tools...")
    if IS_WINDOWS or platform.system() == "Darwin":
        success("System clipboard available")
        return

    import shutil as sh
    for tool, label in (("xclip", "xclip"), ("xsel", "xsel"), ("wl-copy", "wl-copy (Wayland)")):
        if sh.which(tool):
            success(f"{label} found")
            return

    warn("No clipboard tool found. /copy and /code commands won't work.")
    print("  Install one of:")
    print("    sudo pacman -S xclip        # Arch (X11)")
    print("    sudo apt install xclip      # Debian/Ubuntu (X11)")
    print("    sudo pacman -S wl-clipboard # Arch (Wayland)")
    print("    sudo apt install wl-clipboard # Debian/Ubuntu (Wayland)")


def create_launcher() -> Path:
    info("Setting up global command...")

    if IS_WINDOWS:
        install_dir = Path(os.environ.get("USERPROFILE", Path.home())) / ".local" / "bin"
        install_dir.mkdir(parents=True, exist_ok=True)
        shim_path = install_dir / "lumo.cmd"
        # Symlinks need admin/dev-mode on Windows, so use a tiny shim instead.
        shim_path.write_text(f'@echo off\r\n"{venv_python()}" -m lumo_term.cli %*\r\n')
        success(f"Launcher created: {shim_path}")
        return install_dir

    install_dir = Path.home() / ".local" / "bin"
    install_dir.mkdir(parents=True, exist_ok=True)
    link_path = install_dir / "lumo"
    if link_path.is_symlink() or link_path.exists():
        link_path.unlink()
    link_path.symlink_to(venv_bin_dir() / "lumo")
    success(f"Symlink created: {link_path}")
    return install_dir


def check_path(install_dir: Path) -> None:
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    if str(install_dir) in path_entries:
        success(f"{install_dir} is in PATH")
        return

    warn(f"{install_dir} is not in your PATH")
    print()
    print("  Add it to your shell configuration:")
    print()

    if IS_WINDOWS:
        print("  PowerShell (add to your $PROFILE):")
        print(f'    $env:Path += ";{install_dir}"')
        print()
        print("  Or permanently, via System Properties > Environment Variables.")
        return

    shell = Path(os.environ.get("SHELL", "")).name
    if shell == "fish":
        print("  For fish, run:")
        print(f"    fish_add_path {install_dir}")
        print()
        print("  Or add to ~/.config/fish/config.fish:")
        print(f'    set -gx PATH {install_dir} $PATH')
    elif shell == "zsh":
        print("  Add to ~/.zshrc:")
        print(f'    export PATH="{install_dir}:$PATH"')
    elif shell == "bash":
        print("  Add to ~/.bashrc:")
        print(f'    export PATH="{install_dir}:$PATH"')
    else:
        print("  Add to your shell config:")
        print(f'    export PATH="{install_dir}:$PATH"')
    print()


def verify_install(install_dir: Path) -> None:
    info("Verifying installation...")
    lumo_cmd = install_dir / ("lumo.cmd" if IS_WINDOWS else "lumo")
    result = subprocess.run([str(lumo_cmd), "--help"], capture_output=True)
    if result.returncode != 0:
        error("Installation verification failed")
    success("lumo command is working!")


def main() -> int:
    print()
    print("=========================================")
    print("  LUMO-Term Setup")
    print("=========================================")
    print()

    check_python_version()
    check_clipboard_tool()
    create_venv()
    install_dependencies()
    check_browsers()

    install_dir = create_launcher()
    check_path(install_dir)
    verify_install(install_dir)

    print()
    print("=========================================")
    print("  Setup Complete!")
    print("=========================================")
    print()
    print("  Before first use, log into LUMO+ in your browser:")
    print("    https://lumo.proton.me")
    print()
    print("  Then run:")
    print("    lumo                       # Interactive REPL")
    print("    lumo -m 'Hello'            # Single message")
    print("    lumo --browser edge -m 'Hi' # Pick a specific browser")
    print("    lumo --help                # See all options")
    print()
    print("  For visible browser (debugging):")
    print("    lumo --no-headless")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
