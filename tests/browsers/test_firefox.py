"""Tests for the Firefox backend."""

from pathlib import Path
from unittest.mock import patch

import pytest

from lumo_term.browsers.firefox import FirefoxLumoBrowser


class TestFirefoxInit:
    """Test Firefox backend initialization and profile resolution."""

    def test_creates_with_defaults(self):
        browser = FirefoxLumoBrowser()
        assert browser.headless is True
        assert browser.profile is None
        assert browser._driver is None

    def test_creates_with_custom_headless(self):
        browser = FirefoxLumoBrowser(headless=False)
        assert browser.headless is False

    def test_accepts_custom_profile(self, tmp_path):
        fake_profile = tmp_path / "fake_profile"
        fake_profile.mkdir()
        (fake_profile / "cookies.sqlite").touch()

        browser = FirefoxLumoBrowser(profile=fake_profile)
        resolved = browser._resolve_profile()

        assert resolved == fake_profile

    def test_resolve_profile_raises_when_none_found(self):
        browser = FirefoxLumoBrowser(profile=None)

        with patch("lumo_term.browsers.firefox.find_firefox_profile", return_value=None):
            with pytest.raises(RuntimeError, match="No Firefox profile found"):
                browser._resolve_profile()

    def test_resolve_profile_rejects_invalid_dir(self, tmp_path):
        not_a_profile = tmp_path / "not_a_profile"
        not_a_profile.mkdir()

        browser = FirefoxLumoBrowser(profile=not_a_profile)

        with pytest.raises(RuntimeError, match="Not a valid Firefox profile"):
            browser._resolve_profile()

    def test_is_profile_locked_delegates_to_profiles_module(self, tmp_path):
        browser = FirefoxLumoBrowser()

        with patch("lumo_term.browsers.firefox.is_firefox_locked", return_value=True) as mock_locked:
            assert browser._is_profile_locked(tmp_path) is True
            mock_locked.assert_called_once_with(tmp_path)


@pytest.mark.integration
class TestFirefoxRealProfile:
    """Tests that require a real Firefox profile on this machine."""

    def test_browser_finds_firefox_profile(self):
        browser = FirefoxLumoBrowser()
        profile = browser._resolve_profile()

        assert profile.exists()
        assert (profile / "cookies.sqlite").exists()
