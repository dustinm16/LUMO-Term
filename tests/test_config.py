"""Tests for configuration management."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from lumo_term.config import (
    Config,
    get_config_dir,
    get_config_path,
    load_config,
    save_config,
)


# ============================================================================
# Config Model Tests
# ============================================================================

class TestConfigModel:
    """Test Config Pydantic model."""

    def test_config_default_values(self):
        """Config should have sensible defaults."""
        config = Config()

        assert config.browser is None
        assert config.browser_profile is None
        assert config.theme == "dark"

    def test_config_custom_browser(self):
        """Config should accept a browser override."""
        config = Config(browser="chrome")

        assert config.browser == "chrome"

    def test_config_custom_profile(self):
        """Config should accept custom browser profile path."""
        config = Config(browser_profile="/path/to/profile")

        assert config.browser_profile == "/path/to/profile"

    def test_config_custom_theme(self):
        """Config should accept custom theme."""
        config = Config(theme="light")

        assert config.theme == "light"

    def test_config_serialization(self):
        """Config should serialize to JSON."""
        config = Config(browser="edge", browser_profile="/test/path", theme="light")

        json_str = config.model_dump_json()
        data = json.loads(json_str)

        assert data["browser"] == "edge"
        assert data["browser_profile"] == "/test/path"
        assert data["theme"] == "light"

    def test_config_deserialization(self):
        """Config should deserialize from dict."""
        data = {"browser": "firefox", "browser_profile": "/custom/path", "theme": "dark"}

        config = Config.model_validate(data)

        assert config.browser == "firefox"
        assert config.browser_profile == "/custom/path"
        assert config.theme == "dark"

    def test_config_partial_data(self):
        """Config should handle partial data with defaults."""
        data = {"theme": "light"}

        config = Config.model_validate(data)

        assert config.browser is None
        assert config.browser_profile is None
        assert config.theme == "light"

    def test_config_extra_fields_ignored(self):
        """Config should ignore unknown fields."""
        data = {"theme": "dark", "unknown_field": "value"}

        config = Config.model_validate(data)

        assert config.theme == "dark"
        assert not hasattr(config, "unknown_field")


# ============================================================================
# Path Functions Tests
# ============================================================================

class TestPathFunctions:
    """Test config directory and path functions."""

    def test_get_config_dir_creates_directory(self):
        """get_config_dir should create directory if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                config_dir = get_config_dir()

                assert config_dir.exists()
                assert config_dir.is_dir()
                assert config_dir == fake_home / ".config" / "lumo-term"

    def test_get_config_dir_existing_directory(self):
        """get_config_dir should work with existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            existing_dir = fake_home / ".config" / "lumo-term"
            existing_dir.mkdir(parents=True)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                config_dir = get_config_dir()

                assert config_dir.exists()
                assert config_dir == existing_dir

    def test_get_config_path(self):
        """get_config_path should return correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                config_path = get_config_path()

                assert config_path == fake_home / ".config" / "lumo-term" / "config.json"


# ============================================================================
# Config Persistence Tests
# ============================================================================

class TestConfigPersistence:
    """Test config save/load functionality."""

    def test_save_config(self):
        """save_config should write config to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                config = Config(browser_profile="/test/path", theme="light")
                save_config(config)

                config_path = fake_home / ".config" / "lumo-term" / "config.json"
                assert config_path.exists()

                data = json.loads(config_path.read_text())
                assert data["browser_profile"] == "/test/path"
                assert data["theme"] == "light"

    def test_load_config_existing(self):
        """load_config should load from existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            config_dir = fake_home / ".config" / "lumo-term"
            config_dir.mkdir(parents=True)

            config_data = {"browser_profile": "/saved/path", "theme": "light"}
            (config_dir / "config.json").write_text(json.dumps(config_data))

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                config = load_config()

                assert config.browser_profile == "/saved/path"
                assert config.theme == "light"

    def test_load_config_missing_file(self):
        """load_config should return defaults when file missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                config = load_config()

                assert config.browser_profile is None
                assert config.theme == "dark"

    def test_load_config_corrupted_json(self):
        """load_config should return defaults on corrupted JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            config_dir = fake_home / ".config" / "lumo-term"
            config_dir.mkdir(parents=True)

            # Write invalid JSON
            (config_dir / "config.json").write_text("{ invalid json }")

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                config = load_config()

                # Should return defaults, not crash
                assert config.browser_profile is None
                assert config.theme == "dark"

    def test_load_config_invalid_schema(self):
        """load_config should return defaults on invalid schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            config_dir = fake_home / ".config" / "lumo-term"
            config_dir.mkdir(parents=True)

            # Write JSON with wrong types
            (config_dir / "config.json").write_text('{"theme": 12345}')

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                config = load_config()

                # Should return defaults on validation error
                assert config.theme == "dark"

    def test_save_and_load_roundtrip(self):
        """Config should survive save/load roundtrip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                original = Config(browser="chrome", browser_profile="/roundtrip/test", theme="light")
                save_config(original)
                loaded = load_config()

                assert loaded.browser == original.browser
                assert loaded.browser_profile == original.browser_profile
                assert loaded.theme == original.theme


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_special_characters_in_values(self):
        """Config should handle special characters."""
        config = Config(browser_profile="/path/with spaces/and'quotes")
        json_str = config.model_dump_json()
        restored = Config.model_validate(json.loads(json_str))

        assert restored.browser_profile == "/path/with spaces/and'quotes"
