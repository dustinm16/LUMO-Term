"""OS-aware browser profile discovery.

No Selenium imports here — pure filesystem lookups so this module can be
unit-tested (and used by the installer) without a browser or webdriver
present.
"""

import os
import platform
import shutil
from pathlib import Path


def _system() -> str:
    return platform.system()  # "Linux", "Darwin", "Windows"


_MACOS_APPLICATIONS_DIR = Path("/Applications")


# ============================================================================
# Firefox
# ============================================================================

def firefox_profile_roots() -> list[Path]:
    """Candidate directories that contain Firefox profile subdirectories."""
    home = Path.home()
    system = _system()

    if system == "Darwin":
        return [home / "Library" / "Application Support" / "Firefox" / "Profiles"]

    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        roots = []
        if appdata:
            roots.append(Path(appdata) / "Mozilla" / "Firefox" / "Profiles")
        return roots

    # Linux (and other POSIX): native package, snap, and flatpak all use
    # different homes for the profile directory.
    return [
        home / ".mozilla" / "firefox",
        home / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
        home / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
    ]


def find_firefox_profiles(override: Path | None = None) -> list[Path]:
    """Find Firefox profile directories, most recently used first."""
    if override is not None:
        return [override] if (override / "cookies.sqlite").exists() else []

    profiles = []
    for root in firefox_profile_roots():
        if not root.exists():
            continue
        for path in root.iterdir():
            if path.is_dir() and (path / "cookies.sqlite").exists():
                profiles.append(path)

    profiles.sort(key=lambda p: (p / "cookies.sqlite").stat().st_mtime, reverse=True)
    return profiles


def find_firefox_profile(override: Path | None = None) -> Path | None:
    """Find the single best Firefox profile to use, or None if none found."""
    profiles = find_firefox_profiles(override)
    return profiles[0] if profiles else None


def is_firefox_locked(profile: Path) -> bool:
    """True if Firefox currently has this profile open.

    On POSIX, Firefox holds `.parentlock` with an advisory flock() rather
    than a PID-bearing symlink (unlike Chromium's SingletonLock) — its mere
    presence isn't enough to mean "locked": a crashed Firefox leaves the
    same empty file behind without releasing it. Actually attempt the lock
    ourselves (non-blocking) the same way Firefox itself would, rather than
    just checking existence.
    """
    lock_path = profile / ".parentlock"
    if not lock_path.exists():
        return False

    if _system() == "Windows":
        # Windows Firefox doesn't use flock() semantics; fall back to
        # existence, same as before.
        return True

    import fcntl

    fd = os.open(lock_path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False  # We could acquire it — nothing else is holding it.
    except OSError:
        return True  # Genuinely held by a live Firefox process.
    finally:
        os.close(fd)


# ============================================================================
# Chromium family (Chrome / Chromium / Edge)
# ============================================================================

# (channel -> per-OS directory name) tables. The "root" returned is the
# browser's "User Data" directory; profiles live in named subdirectories of
# it ("Default", "Profile 1", ...).
_CHROMIUM_LINUX_DIRS = {
    "chrome": ["google-chrome", "google-chrome-beta", "google-chrome-unstable"],
    "chromium": ["chromium"],
    "edge": ["microsoft-edge", "microsoft-edge-beta", "microsoft-edge-dev"],
}
_CHROMIUM_MACOS_DIRS = {
    "chrome": ["Google/Chrome"],
    "chromium": ["Chromium"],
    "edge": ["Microsoft Edge"],
}
_CHROMIUM_WINDOWS_DIRS = {
    # Forward slashes on purpose: pathlib splits on "/" on every platform
    # (including Windows), whereas a literal "\\" is only a separator under
    # WindowsPath — embedding it here would silently produce a single
    # bogus path component when tested (or run) under PosixPath.
    "chrome": ["Google/Chrome/User Data"],
    "chromium": ["Chromium/User Data"],
    "edge": ["Microsoft/Edge/User Data"],
}

# Linux binary names to probe with `shutil.which`, in priority order.
_CHROMIUM_LINUX_BINARIES = {
    "chrome": ["google-chrome-stable", "google-chrome"],
    "chromium": ["chromium", "chromium-browser"],
    "edge": ["microsoft-edge-stable", "microsoft-edge"],
}
_CHROMIUM_MACOS_APPS = {
    "chrome": "Google Chrome.app",
    "chromium": "Chromium.app",
    "edge": "Microsoft Edge.app",
}
_CHROMIUM_MACOS_APP_BINARIES = {
    "chrome": "Google Chrome",
    "chromium": "Chromium",
    "edge": "Microsoft Edge",
}
_CHROMIUM_WINDOWS_BINARIES = {
    "chrome": "chrome.exe",
    "chromium": "chrome.exe",
    "edge": "msedge.exe",
}


def find_chromium_binary(channel: str) -> str | None:
    """Find the actual installed browser executable for a Chromium channel.

    Selenium Manager will happily download and launch its *own* copy of the
    browser if it can't confidently resolve the system one — which then
    talks to a version of msedgedriver/chromedriver paired to that
    downloaded copy instead of the one actually holding the real profile.
    Pinning `options.binary_location` to this path keeps driver and browser
    versions matched to what's really installed.
    """
    system = _system()

    if system == "Darwin":
        app_name = _CHROMIUM_MACOS_APPS.get(channel)
        binary_name = _CHROMIUM_MACOS_APP_BINARIES.get(channel)
        if not app_name or not binary_name:
            return None
        candidate = _MACOS_APPLICATIONS_DIR / app_name / "Contents" / "MacOS" / binary_name
        return str(candidate) if candidate.exists() else None

    if system == "Windows":
        exe = _CHROMIUM_WINDOWS_BINARIES.get(channel)
        if not exe:
            return None
        program_dirs = {
            "chrome": "Google/Chrome/Application",
            "chromium": "Chromium/Application",
            "edge": "Microsoft/Edge/Application",
        }
        roots = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        for root in roots:
            if not root:
                continue
            candidate = Path(root) / program_dirs[channel] / exe
            if candidate.exists():
                return str(candidate)
        return None

    # Linux
    for name in _CHROMIUM_LINUX_BINARIES.get(channel, []):
        found = shutil.which(name)
        if found:
            return found
    return None


def chromium_profile_roots(channel: str) -> list[Path]:
    """Candidate "User Data" root directories for a Chromium-family browser."""
    home = Path.home()
    system = _system()

    if system == "Darwin":
        return [
            home / "Library" / "Application Support" / d
            for d in _CHROMIUM_MACOS_DIRS.get(channel, [])
        ]

    if system == "Windows":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if not local_appdata:
            return []
        return [Path(local_appdata) / d for d in _CHROMIUM_WINDOWS_DIRS.get(channel, [])]

    # Linux: native, snap, flatpak.
    linux_names = _CHROMIUM_LINUX_DIRS.get(channel, [])
    roots = []
    for name in linux_names:
        roots.append(home / ".config" / name)
        roots.append(home / "snap" / name / "common" / ".config" / name)
    flatpak_ids = {
        "chrome": "com.google.Chrome",
        "chromium": "org.chromium.Chromium",
        "edge": "com.microsoft.Edge",
    }
    flatpak_id = flatpak_ids.get(channel)
    if flatpak_id:
        roots.append(home / ".var" / "app" / flatpak_id / "config" / linux_names[0])
    return roots


def _profile_dirs_in_root(root: Path) -> list[Path]:
    if not root.exists():
        return []
    candidates = []
    default = root / "Default"
    if default.exists():
        candidates.append(default)
    for path in root.glob("Profile *"):
        if path.is_dir():
            candidates.append(path)
    return candidates


def find_chromium_profile(channel: str, override: Path | None = None) -> tuple[Path, str] | None:
    """Find a (user_data_dir, profile_directory_name) pair for a channel.

    Returns None if no profile could be located.
    """
    if override is not None:
        # override may point directly at a profile dir ("<root>/Default") —
        # the parent is the actual --user-data-dir.
        if (override / "Preferences").exists() or (override / "Cookies").exists():
            return override.parent, override.name
        return None

    best: tuple[Path, str] | None = None
    best_mtime = -1.0
    for root in chromium_profile_roots(channel):
        for profile_dir in _profile_dirs_in_root(root):
            pref_file = profile_dir / "Preferences"
            mtime = pref_file.stat().st_mtime if pref_file.exists() else profile_dir.stat().st_mtime
            if mtime > best_mtime:
                best_mtime = mtime
                best = (root, profile_dir.name)
    return best


def is_chromium_locked(user_data_dir: Path) -> bool:
    """True if this Chromium-family browser currently has the profile open.

    `SingletonLock` is a symlink to "<hostname>-<pid>" (POSIX; Windows
    Chromium doesn't use this file at all, so this always reports unlocked
    there). Its mere presence isn't enough — a crashed browser process
    leaves the same symlink behind without cleaning up, and Chromium itself
    treats that as stale rather than locked. Match that: only report locked
    if the pid it names is actually alive.
    """
    lock = user_data_dir / "SingletonLock"
    if not lock.is_symlink():
        return False

    target = os.readlink(lock)
    _, _, pid_str = target.rpartition("-")
    try:
        pid = int(pid_str)
    except ValueError:
        return True  # Unexpected format — assume locked rather than clobber a live session.

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False  # Stale lock from a crashed process.
    except PermissionError:
        return True  # Process exists, just owned by someone else.
    return True


# ============================================================================
# Installed-browser detection
# ============================================================================

def detect_installed_browsers() -> list[str]:
    """Return which of firefox/chrome/chromium/edge appear to be installed."""
    system = _system()
    found = []

    if system == "Darwin":
        if (_MACOS_APPLICATIONS_DIR / "Firefox.app").exists():
            found.append("firefox")
        for channel, app_name in _CHROMIUM_MACOS_APPS.items():
            if (_MACOS_APPLICATIONS_DIR / app_name).exists():
                found.append(channel)
        return found

    if system == "Windows":
        program_files = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        roots = [Path(p) for p in program_files if p]
        if any((r / "Mozilla Firefox" / "firefox.exe").exists() for r in roots):
            found.append("firefox")
        for channel, exe in _CHROMIUM_WINDOWS_BINARIES.items():
            search_dirs = [r / "Google" / "Chrome" / "Application" for r in roots] + \
                          [r / "Microsoft" / "Edge" / "Application" for r in roots] + \
                          [r / "Chromium" / "Application" for r in roots]
            if any((d / exe).exists() for d in search_dirs):
                found.append(channel)
        return found

    # Linux
    if shutil.which("firefox"):
        found.append("firefox")
    for channel, binaries in _CHROMIUM_LINUX_BINARIES.items():
        if any(shutil.which(b) for b in binaries):
            found.append(channel)
    return found
