"""Tests for OS-aware browser profile discovery (pure filesystem, no browser needed)."""

import os
from pathlib import Path
from unittest.mock import patch

from lumo_term.browsers import profiles


# ============================================================================
# Firefox profile discovery
# ============================================================================

class TestFirefoxProfileRoots:
    """Test Firefox profile root candidates per OS."""

    def test_linux_includes_native_snap_and_flatpak(self, tmp_path):
        with patch.object(profiles.Path, "home", return_value=tmp_path):
            with patch.object(profiles, "_system", return_value="Linux"):
                roots = profiles.firefox_profile_roots()

        assert tmp_path / ".mozilla" / "firefox" in roots
        assert tmp_path / "snap" / "firefox" / "common" / ".mozilla" / "firefox" in roots
        assert tmp_path / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox" in roots

    def test_macos_uses_application_support(self, tmp_path):
        with patch.object(profiles.Path, "home", return_value=tmp_path):
            with patch.object(profiles, "_system", return_value="Darwin"):
                roots = profiles.firefox_profile_roots()

        assert roots == [tmp_path / "Library" / "Application Support" / "Firefox" / "Profiles"]

    def test_windows_uses_appdata(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
        with patch.object(profiles, "_system", return_value="Windows"):
            roots = profiles.firefox_profile_roots()

        assert roots == [tmp_path / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "Profiles"]


class TestFindFirefoxProfile:
    """Test Firefox profile discovery and selection."""

    def test_finds_profile_with_cookies_sqlite(self, tmp_path):
        root = tmp_path / ".mozilla" / "firefox"
        profile = root / "abc123.default"
        profile.mkdir(parents=True)
        (profile / "cookies.sqlite").touch()

        with patch.object(profiles, "firefox_profile_roots", return_value=[root]):
            found = profiles.find_firefox_profile()

        assert found == profile

    def test_ignores_profile_dirs_without_cookies(self, tmp_path):
        root = tmp_path / ".mozilla" / "firefox"
        empty_profile = root / "empty.default"
        empty_profile.mkdir(parents=True)

        with patch.object(profiles, "firefox_profile_roots", return_value=[root]):
            found = profiles.find_firefox_profile()

        assert found is None

    def test_picks_most_recently_modified(self, tmp_path):
        import os
        import time

        root = tmp_path / ".mozilla" / "firefox"
        older = root / "older.default"
        newer = root / "newer.default"
        older.mkdir(parents=True)
        newer.mkdir(parents=True)
        (older / "cookies.sqlite").touch()
        (newer / "cookies.sqlite").touch()

        old_time = time.time() - 1000
        os.utime(older / "cookies.sqlite", (old_time, old_time))

        with patch.object(profiles, "firefox_profile_roots", return_value=[root]):
            found = profiles.find_firefox_profile()

        assert found == newer

    def test_override_used_when_valid(self, tmp_path):
        profile = tmp_path / "custom_profile"
        profile.mkdir()
        (profile / "cookies.sqlite").touch()

        found = profiles.find_firefox_profile(override=profile)

        assert found == profile

    def test_override_rejected_when_missing_cookies(self, tmp_path):
        profile = tmp_path / "custom_profile"
        profile.mkdir()

        found = profiles.find_firefox_profile(override=profile)

        assert found is None

    def test_no_roots_exist_returns_none(self, tmp_path):
        with patch.object(profiles, "firefox_profile_roots", return_value=[tmp_path / "nope"]):
            found = profiles.find_firefox_profile()

        assert found is None


class TestFirefoxLock:
    """Test Firefox profile lock detection."""

    def test_locked_when_parentlock_actually_held(self, tmp_path):
        import fcntl

        profile = tmp_path / "profile"
        profile.mkdir()
        lock_path = profile / ".parentlock"
        lock_path.touch()

        fd = os.open(lock_path, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            assert profiles.is_firefox_locked(profile) is True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def test_not_locked_when_parentlock_is_stale(self, tmp_path):
        """A .parentlock left over from a crashed Firefox isn't actually held."""
        profile = tmp_path / "profile"
        profile.mkdir()
        (profile / ".parentlock").touch()

        assert profiles.is_firefox_locked(profile) is False

    def test_not_locked_when_absent(self, tmp_path):
        profile = tmp_path / "profile"
        profile.mkdir()

        assert profiles.is_firefox_locked(profile) is False


# ============================================================================
# Chromium-family profile discovery
# ============================================================================

class TestChromiumProfileRoots:
    """Test Chromium-family profile root candidates per OS."""

    def test_linux_edge_includes_snap(self, tmp_path):
        with patch.object(profiles.Path, "home", return_value=tmp_path):
            with patch.object(profiles, "_system", return_value="Linux"):
                roots = profiles.chromium_profile_roots("edge")

        assert tmp_path / ".config" / "microsoft-edge" in roots
        assert tmp_path / "snap" / "microsoft-edge" / "common" / ".config" / "microsoft-edge" in roots

    def test_macos_chrome(self, tmp_path):
        with patch.object(profiles.Path, "home", return_value=tmp_path):
            with patch.object(profiles, "_system", return_value="Darwin"):
                roots = profiles.chromium_profile_roots("chrome")

        assert roots == [tmp_path / "Library" / "Application Support" / "Google" / "Chrome"]

    def test_windows_chrome(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
        with patch.object(profiles, "_system", return_value="Windows"):
            roots = profiles.chromium_profile_roots("chrome")

        assert roots == [tmp_path / "Local" / "Google" / "Chrome" / "User Data"]


class TestFindChromiumProfile:
    """Test Chromium-family profile discovery."""

    def test_finds_default_profile(self, tmp_path):
        root = tmp_path / ".config" / "google-chrome"
        default = root / "Default"
        default.mkdir(parents=True)
        (default / "Preferences").touch()

        with patch.object(profiles, "chromium_profile_roots", return_value=[root]):
            found = profiles.find_chromium_profile("chrome")

        assert found == (root, "Default")

    def test_picks_most_recently_used_profile(self, tmp_path):
        import os
        import time

        root = tmp_path / ".config" / "google-chrome"
        default = root / "Default"
        profile1 = root / "Profile 1"
        default.mkdir(parents=True)
        profile1.mkdir(parents=True)
        (default / "Preferences").touch()
        (profile1 / "Preferences").touch()

        old_time = time.time() - 1000
        os.utime(default / "Preferences", (old_time, old_time))

        with patch.object(profiles, "chromium_profile_roots", return_value=[root]):
            found = profiles.find_chromium_profile("chrome")

        assert found == (root, "Profile 1")

    def test_no_profile_found_returns_none(self, tmp_path):
        with patch.object(profiles, "chromium_profile_roots", return_value=[tmp_path / "nope"]):
            found = profiles.find_chromium_profile("chrome")

        assert found is None

    def test_override_resolves_to_parent_and_name(self, tmp_path):
        root = tmp_path / "User Data"
        default = root / "Default"
        default.mkdir(parents=True)
        (default / "Preferences").touch()

        found = profiles.find_chromium_profile("chrome", override=default)

        assert found == (root, "Default")


class TestChromiumLock:
    """Test Chromium-family profile lock detection."""

    def test_locked_when_lock_pid_is_alive(self, tmp_path):
        import os

        (tmp_path / "SingletonLock").symlink_to(f"somehost-{os.getpid()}")

        assert profiles.is_chromium_locked(tmp_path) is True

    def test_not_locked_when_lock_pid_is_dead(self, tmp_path):
        # A PID essentially guaranteed not to be alive right now.
        (tmp_path / "SingletonLock").symlink_to("somehost-999999")

        assert profiles.is_chromium_locked(tmp_path) is False

    def test_not_locked_when_absent(self, tmp_path):
        assert profiles.is_chromium_locked(tmp_path) is False

    def test_not_locked_when_not_a_symlink(self, tmp_path):
        (tmp_path / "SingletonLock").touch()

        assert profiles.is_chromium_locked(tmp_path) is False


# ============================================================================
# Installed browser detection
# ============================================================================

class TestDetectInstalledBrowsers:
    """Test cross-OS installed-browser detection."""

    def test_linux_uses_which(self):
        def fake_which(name):
            return f"/usr/bin/{name}" if name in ("firefox", "microsoft-edge-stable") else None

        with patch.object(profiles, "_system", return_value="Linux"):
            with patch.object(profiles.shutil, "which", side_effect=fake_which):
                found = profiles.detect_installed_browsers()

        assert "firefox" in found
        assert "edge" in found
        assert "chrome" not in found

    def test_macos_uses_application_bundles(self, tmp_path):
        (tmp_path / "Firefox.app").mkdir()
        (tmp_path / "Google Chrome.app").mkdir()

        with patch.object(profiles, "_system", return_value="Darwin"):
            with patch.object(profiles, "_MACOS_APPLICATIONS_DIR", tmp_path):
                found = profiles.detect_installed_browsers()

        assert "firefox" in found
        assert "chrome" in found
        assert "edge" not in found
