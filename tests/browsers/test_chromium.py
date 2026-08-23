"""Tests for the Chrome/Chromium/Edge backends."""

from unittest.mock import patch

import pytest

from lumo_term.browsers.chromium import (
    ChromeLumoBrowser,
    ChromiumLumoBrowser,
    EdgeLumoBrowser,
    _build_chromium_args,
)


class TestBuildChromiumArgs:
    """Test the shared Chromium-family argument builder."""

    def test_headless_adds_flag(self, tmp_path):
        args = _build_chromium_args(tmp_path, "Default", headless=True)

        assert f"--user-data-dir={tmp_path}" in args
        assert "--profile-directory=Default" in args
        assert "--headless=new" in args

    def test_non_headless_omits_flag(self, tmp_path):
        args = _build_chromium_args(tmp_path, "Default", headless=False)

        assert "--headless=new" not in args


class TestChromeInit:
    """Test Chrome backend initialization and profile resolution."""

    def test_creates_with_defaults(self):
        browser = ChromeLumoBrowser()
        assert browser.headless is True
        assert browser.CHANNEL == "chrome"

    def test_resolve_profile_raises_when_none_found(self):
        browser = ChromeLumoBrowser()

        with patch("lumo_term.browsers.chromium.find_chromium_profile", return_value=None):
            with pytest.raises(RuntimeError, match="No Chrome profile found"):
                browser._resolve_profile()

    def test_resolve_profile_returns_found_pair(self, tmp_path):
        browser = ChromeLumoBrowser()
        expected = (tmp_path, "Default")

        with patch("lumo_term.browsers.chromium.find_chromium_profile", return_value=expected):
            assert browser._resolve_profile() == expected

    def test_is_profile_locked_checks_user_data_dir(self, tmp_path):
        browser = ChromeLumoBrowser()

        with patch("lumo_term.browsers.chromium.is_chromium_locked", return_value=True) as mock_locked:
            assert browser._is_profile_locked((tmp_path, "Default")) is True
            mock_locked.assert_called_once_with(tmp_path)


class TestEdgeInit:
    """Test Edge backend initialization."""

    def test_creates_with_defaults(self):
        browser = EdgeLumoBrowser()
        assert browser.headless is True
        assert browser.CHANNEL == "edge"
        assert browser.BROWSER_NAME == "Edge"

    def test_resolve_profile_raises_when_none_found(self):
        browser = EdgeLumoBrowser()

        with patch("lumo_term.browsers.chromium.find_chromium_profile", return_value=None):
            with pytest.raises(RuntimeError, match="No Edge profile found"):
                browser._resolve_profile()


class TestChromiumChannel:
    """Test the plain-Chromium channel."""

    def test_uses_chromium_channel(self):
        browser = ChromiumLumoBrowser()
        assert browser.CHANNEL == "chromium"
        assert browser.BROWSER_NAME == "Chromium"
