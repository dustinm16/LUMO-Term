"""Tests for Firefox authentication and cookie extraction."""

import sqlite3
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from lumo_term.auth import (
    AuthError,
    find_firefox_profiles,
    get_firefox_profile,
    extract_cookies_from_profile,
    extract_uid_from_cookies,
    get_auth_session,
    format_cookie_header,
)
from lumo_term.config import Config, Session


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def fake_firefox_dir(tmp_path):
    """Create a fake Firefox directory structure."""
    firefox_dir = tmp_path / ".mozilla" / "firefox"
    firefox_dir.mkdir(parents=True)
    return firefox_dir


@pytest.fixture
def fake_profile(fake_firefox_dir):
    """Create a fake Firefox profile with cookies database."""
    profile = fake_firefox_dir / "abc123.default"
    profile.mkdir()

    # Create a real SQLite cookies database
    cookies_db = profile / "cookies.sqlite"
    conn = sqlite3.connect(cookies_db)
    conn.execute("""
        CREATE TABLE moz_cookies (
            id INTEGER PRIMARY KEY,
            name TEXT,
            value TEXT,
            host TEXT,
            path TEXT,
            expiry INTEGER,
            isSecure INTEGER,
            isHttpOnly INTEGER,
            sameSite INTEGER
        )
    """)
    conn.commit()
    conn.close()

    return profile


def add_cookies_to_profile(profile: Path, cookies: list[tuple[str, str, str]]):
    """Add cookies to a profile's database.

    Args:
        profile: Profile directory path
        cookies: List of (name, value, host) tuples
    """
    cookies_db = profile / "cookies.sqlite"
    conn = sqlite3.connect(cookies_db)
    for name, value, host in cookies:
        conn.execute(
            "INSERT INTO moz_cookies (name, value, host) VALUES (?, ?, ?)",
            (name, value, host)
        )
    conn.commit()
    conn.close()


# ============================================================================
# AuthError Tests
# ============================================================================

class TestAuthError:
    """Test AuthError exception."""

    def test_auth_error_is_exception(self):
        """AuthError should be an Exception."""
        assert issubclass(AuthError, Exception)

    def test_auth_error_message(self):
        """AuthError should preserve message."""
        error = AuthError("Test error message")
        assert str(error) == "Test error message"

    def test_auth_error_can_be_raised(self):
        """AuthError should be raisable."""
        with pytest.raises(AuthError, match="specific message"):
            raise AuthError("specific message")


# ============================================================================
# find_firefox_profiles Tests
# ============================================================================

class TestFindFirefoxProfiles:
    """Test Firefox profile discovery."""

    def test_no_firefox_dir(self, tmp_path):
        """Should return empty list if no Firefox directory."""
        with patch("lumo_term.auth.Path.home", return_value=tmp_path):
            profiles = find_firefox_profiles()
            assert profiles == []

    def test_empty_firefox_dir(self, fake_firefox_dir, tmp_path):
        """Should return empty list if Firefox dir has no profiles."""
        with patch("lumo_term.auth.Path.home", return_value=tmp_path):
            profiles = find_firefox_profiles()
            assert profiles == []

    def test_finds_single_profile(self, fake_profile, tmp_path):
        """Should find a single valid profile."""
        with patch("lumo_term.auth.Path.home", return_value=tmp_path):
            profiles = find_firefox_profiles()
            assert len(profiles) == 1
            assert profiles[0] == fake_profile

    def test_finds_multiple_profiles(self, fake_firefox_dir, tmp_path):
        """Should find multiple profiles."""
        # Create multiple profiles
        profiles_created = []
        for name in ["profile1.default", "profile2.work", "profile3.test"]:
            profile = fake_firefox_dir / name
            profile.mkdir()
            (profile / "cookies.sqlite").touch()
            profiles_created.append(profile)

        with patch("lumo_term.auth.Path.home", return_value=tmp_path):
            profiles = find_firefox_profiles()
            assert len(profiles) == 3

    def test_ignores_dirs_without_cookies(self, fake_firefox_dir, tmp_path):
        """Should ignore directories without cookies.sqlite."""
        # Profile with cookies
        valid_profile = fake_firefox_dir / "valid.default"
        valid_profile.mkdir()
        (valid_profile / "cookies.sqlite").touch()

        # Profile without cookies
        invalid_profile = fake_firefox_dir / "invalid.default"
        invalid_profile.mkdir()
        # No cookies.sqlite

        with patch("lumo_term.auth.Path.home", return_value=tmp_path):
            profiles = find_firefox_profiles()
            assert len(profiles) == 1
            assert profiles[0] == valid_profile

    def test_ignores_files(self, fake_firefox_dir, tmp_path):
        """Should ignore files in Firefox directory."""
        # Create a file instead of directory
        (fake_firefox_dir / "profiles.ini").touch()

        # Create valid profile
        valid_profile = fake_firefox_dir / "valid.default"
        valid_profile.mkdir()
        (valid_profile / "cookies.sqlite").touch()

        with patch("lumo_term.auth.Path.home", return_value=tmp_path):
            profiles = find_firefox_profiles()
            assert len(profiles) == 1

    def test_sorts_by_modification_time(self, fake_firefox_dir, tmp_path):
        """Should sort profiles by most recent first."""
        import time

        # Create older profile
        old_profile = fake_firefox_dir / "old.default"
        old_profile.mkdir()
        old_cookies = old_profile / "cookies.sqlite"
        old_cookies.touch()

        time.sleep(0.1)  # Ensure different mtime

        # Create newer profile
        new_profile = fake_firefox_dir / "new.default"
        new_profile.mkdir()
        new_cookies = new_profile / "cookies.sqlite"
        new_cookies.touch()

        with patch("lumo_term.auth.Path.home", return_value=tmp_path):
            profiles = find_firefox_profiles()
            assert profiles[0] == new_profile
            assert profiles[1] == old_profile


# ============================================================================
# get_firefox_profile Tests
# ============================================================================

class TestGetFirefoxProfile:
    """Test profile selection logic."""

    def test_uses_configured_profile(self, tmp_path):
        """Should use profile from config if specified."""
        # Create configured profile
        custom_profile = tmp_path / "custom-profile"
        custom_profile.mkdir()
        (custom_profile / "cookies.sqlite").touch()

        config = Config(firefox_profile=str(custom_profile))

        with patch("lumo_term.auth.load_config", return_value=config):
            profile = get_firefox_profile()
            assert profile == custom_profile

    def test_configured_profile_not_found(self, tmp_path):
        """Should raise AuthError if configured profile doesn't exist."""
        config = Config(firefox_profile="/nonexistent/profile")

        with patch("lumo_term.auth.load_config", return_value=config):
            with pytest.raises(AuthError, match="not found"):
                get_firefox_profile()

    def test_configured_profile_no_cookies(self, tmp_path):
        """Should raise AuthError if configured profile has no cookies."""
        # Create profile without cookies.sqlite
        profile = tmp_path / "no-cookies-profile"
        profile.mkdir()

        config = Config(firefox_profile=str(profile))

        with patch("lumo_term.auth.load_config", return_value=config):
            with pytest.raises(AuthError, match="not found"):
                get_firefox_profile()

    def test_auto_detects_profile(self, fake_profile, tmp_path):
        """Should auto-detect profile when not configured."""
        config = Config(firefox_profile=None)

        with patch("lumo_term.auth.load_config", return_value=config):
            with patch("lumo_term.auth.Path.home", return_value=tmp_path):
                profile = get_firefox_profile()
                assert profile == fake_profile

    def test_no_profiles_found(self, tmp_path):
        """Should raise AuthError when no profiles found."""
        config = Config(firefox_profile=None)

        with patch("lumo_term.auth.load_config", return_value=config):
            with patch("lumo_term.auth.Path.home", return_value=tmp_path):
                with pytest.raises(AuthError, match="No Firefox profiles found"):
                    get_firefox_profile()


# ============================================================================
# extract_cookies_from_profile Tests
# ============================================================================

class TestExtractCookiesFromProfile:
    """Test cookie extraction from Firefox profile."""

    def test_extracts_matching_cookies(self, fake_profile):
        """Should extract cookies matching domain."""
        add_cookies_to_profile(fake_profile, [
            ("session", "abc123", "proton.me"),
            ("auth", "xyz789", ".proton.me"),
        ])

        cookies = extract_cookies_from_profile(fake_profile, "proton.me")

        assert cookies["session"] == "abc123"
        assert cookies["auth"] == "xyz789"

    def test_extracts_subdomain_cookies(self, fake_profile):
        """Should extract cookies from subdomains."""
        add_cookies_to_profile(fake_profile, [
            ("token", "sub123", "lumo.proton.me"),
            ("api", "api456", "api.proton.me"),
        ])

        cookies = extract_cookies_from_profile(fake_profile, "proton.me")

        assert cookies["token"] == "sub123"
        assert cookies["api"] == "api456"

    def test_ignores_other_domains(self, fake_profile):
        """Should not extract cookies from other domains."""
        add_cookies_to_profile(fake_profile, [
            ("session", "proton123", "proton.me"),
            ("other", "google123", "google.com"),
            ("another", "github123", "github.com"),
        ])

        cookies = extract_cookies_from_profile(fake_profile, "proton.me")

        assert "session" in cookies
        assert "other" not in cookies
        assert "another" not in cookies

    def test_empty_database(self, fake_profile):
        """Should return empty dict for empty database."""
        cookies = extract_cookies_from_profile(fake_profile, "proton.me")
        assert cookies == {}

    def test_no_matching_cookies(self, fake_profile):
        """Should return empty dict when no cookies match domain."""
        add_cookies_to_profile(fake_profile, [
            ("session", "google123", "google.com"),
        ])

        cookies = extract_cookies_from_profile(fake_profile, "proton.me")
        assert cookies == {}

    def test_missing_cookies_database(self, tmp_path):
        """Should raise AuthError if cookies.sqlite doesn't exist."""
        empty_profile = tmp_path / "empty-profile"
        empty_profile.mkdir()

        with pytest.raises(AuthError, match="cookies.sqlite not found"):
            extract_cookies_from_profile(empty_profile, "proton.me")

    def test_handles_special_characters_in_values(self, fake_profile):
        """Should handle special characters in cookie values."""
        add_cookies_to_profile(fake_profile, [
            ("token", "abc=123&def=456", "proton.me"),
            ("unicode", "value_with_émojis_🎉", "proton.me"),
        ])

        cookies = extract_cookies_from_profile(fake_profile, "proton.me")

        assert cookies["token"] == "abc=123&def=456"
        assert cookies["unicode"] == "value_with_émojis_🎉"

    def test_multiple_cookies_same_name(self, fake_profile):
        """Should handle multiple cookies with same name (last wins)."""
        add_cookies_to_profile(fake_profile, [
            ("session", "first", "proton.me"),
            ("session", "second", ".proton.me"),
        ])

        cookies = extract_cookies_from_profile(fake_profile, "proton.me")
        # Dict will contain one of them
        assert "session" in cookies


# ============================================================================
# extract_uid_from_cookies Tests
# ============================================================================

class TestExtractUidFromCookies:
    """Test UID extraction from cookies."""

    def test_extracts_uid(self):
        """Should extract UID from AUTH-{uid} cookie."""
        cookies = {"AUTH-user123": "value", "other": "cookie"}

        uid = extract_uid_from_cookies(cookies)

        assert uid == "user123"

    def test_no_auth_cookie(self):
        """Should return None if no AUTH cookie."""
        cookies = {"session": "abc", "token": "xyz"}

        uid = extract_uid_from_cookies(cookies)

        assert uid is None

    def test_empty_cookies(self):
        """Should return None for empty cookies."""
        uid = extract_uid_from_cookies({})
        assert uid is None

    def test_auth_prefix_case_sensitive(self):
        """AUTH prefix should be case-sensitive."""
        cookies = {"auth-user123": "value", "Auth-user456": "value"}

        uid = extract_uid_from_cookies(cookies)

        assert uid is None

    def test_complex_uid(self):
        """Should handle complex UID values."""
        cookies = {"AUTH-abc123-def456-789": "value"}

        uid = extract_uid_from_cookies(cookies)

        assert uid == "abc123-def456-789"

    def test_first_auth_cookie_wins(self):
        """Should return first AUTH cookie found."""
        cookies = {"AUTH-first": "v1", "AUTH-second": "v2"}

        uid = extract_uid_from_cookies(cookies)

        # Should be one of them (dict ordering)
        assert uid in ["first", "second"]


# ============================================================================
# get_auth_session Tests
# ============================================================================

class TestGetAuthSession:
    """Test authentication session retrieval."""

    def test_returns_cached_session(self):
        """Should return cached session if valid."""
        cached = Session(uid="cached-uid", cookies={"key": "value"})

        with patch("lumo_term.auth.load_session", return_value=cached):
            session = get_auth_session(force_refresh=False)

            assert session.uid == "cached-uid"
            assert session.cookies == {"key": "value"}

    def test_extracts_fresh_when_no_cache(self, fake_profile, tmp_path):
        """Should extract fresh cookies when no cache."""
        add_cookies_to_profile(fake_profile, [
            ("AUTH-fresh-uid", "auth_value", "proton.me"),
            ("session", "session_value", "proton.me"),
        ])

        empty_session = Session()
        config = Config(firefox_profile=None)

        with patch("lumo_term.auth.load_session", return_value=empty_session):
            with patch("lumo_term.auth.load_config", return_value=config):
                with patch("lumo_term.auth.Path.home", return_value=tmp_path):
                    with patch("lumo_term.auth.save_session"):
                        session = get_auth_session(force_refresh=False)

                        assert session.uid == "fresh-uid"
                        assert "AUTH-fresh-uid" in session.cookies

    def test_force_refresh_ignores_cache(self, fake_profile, tmp_path):
        """Should ignore cache when force_refresh=True."""
        add_cookies_to_profile(fake_profile, [
            ("AUTH-refreshed-uid", "auth_value", "proton.me"),
        ])

        cached = Session(uid="old-uid", cookies={"old": "data"})
        config = Config(firefox_profile=None)

        with patch("lumo_term.auth.load_session", return_value=cached):
            with patch("lumo_term.auth.load_config", return_value=config):
                with patch("lumo_term.auth.Path.home", return_value=tmp_path):
                    with patch("lumo_term.auth.save_session"):
                        session = get_auth_session(force_refresh=True)

                        assert session.uid == "refreshed-uid"

    def test_raises_on_no_cookies(self, fake_profile, tmp_path):
        """Should raise AuthError if no Proton cookies found."""
        # Profile exists but no Proton cookies
        empty_session = Session()
        config = Config(firefox_profile=None)

        with patch("lumo_term.auth.load_session", return_value=empty_session):
            with patch("lumo_term.auth.load_config", return_value=config):
                with patch("lumo_term.auth.Path.home", return_value=tmp_path):
                    with pytest.raises(AuthError, match="No Proton cookies"):
                        get_auth_session()

    def test_raises_on_no_auth_cookie(self, fake_profile, tmp_path):
        """Should raise AuthError if no AUTH cookie found."""
        # Add non-AUTH cookies
        add_cookies_to_profile(fake_profile, [
            ("session", "value", "proton.me"),
            ("other", "value", "proton.me"),
        ])

        empty_session = Session()
        config = Config(firefox_profile=None)

        with patch("lumo_term.auth.load_session", return_value=empty_session):
            with patch("lumo_term.auth.load_config", return_value=config):
                with patch("lumo_term.auth.Path.home", return_value=tmp_path):
                    with pytest.raises(AuthError, match="AUTH cookie not found"):
                        get_auth_session()

    def test_saves_fresh_session(self, fake_profile, tmp_path):
        """Should save freshly extracted session."""
        add_cookies_to_profile(fake_profile, [
            ("AUTH-save-test", "value", "proton.me"),
        ])

        empty_session = Session()
        config = Config(firefox_profile=None)
        saved_sessions = []

        def capture_save(session):
            saved_sessions.append(session)

        with patch("lumo_term.auth.load_session", return_value=empty_session):
            with patch("lumo_term.auth.load_config", return_value=config):
                with patch("lumo_term.auth.Path.home", return_value=tmp_path):
                    with patch("lumo_term.auth.save_session", side_effect=capture_save):
                        get_auth_session()

        assert len(saved_sessions) == 1
        assert saved_sessions[0].uid == "save-test"


# ============================================================================
# format_cookie_header Tests
# ============================================================================

class TestFormatCookieHeader:
    """Test cookie header formatting."""

    def test_single_cookie(self):
        """Should format single cookie."""
        header = format_cookie_header({"session": "abc123"})
        assert header == "session=abc123"

    def test_multiple_cookies(self):
        """Should format multiple cookies with semicolon separator."""
        cookies = {"a": "1", "b": "2", "c": "3"}
        header = format_cookie_header(cookies)

        # Check all cookies present (order may vary)
        assert "a=1" in header
        assert "b=2" in header
        assert "c=3" in header
        assert header.count(";") == 2

    def test_empty_cookies(self):
        """Should return empty string for empty cookies."""
        header = format_cookie_header({})
        assert header == ""

    def test_special_characters(self):
        """Should handle special characters in values."""
        cookies = {"token": "abc=123&def=456"}
        header = format_cookie_header(cookies)
        assert header == "token=abc=123&def=456"

    def test_cookie_format(self):
        """Should use correct name=value; format."""
        cookies = {"first": "1", "second": "2"}
        header = format_cookie_header(cookies)

        parts = header.split("; ")
        assert len(parts) == 2
        for part in parts:
            assert "=" in part
            name, value = part.split("=", 1)
            assert name in ["first", "second"]
