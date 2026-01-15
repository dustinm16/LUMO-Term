"""Tests for configuration management."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from lumo_term.config import (
    Config,
    Session,
    get_config_dir,
    get_config_path,
    get_session_path,
    load_config,
    save_config,
    load_session,
    save_session,
    clear_session,
)


# ============================================================================
# Config Model Tests
# ============================================================================

class TestConfigModel:
    """Test Config Pydantic model."""

    def test_config_default_values(self):
        """Config should have sensible defaults."""
        config = Config()

        assert config.firefox_profile is None
        assert config.theme == "dark"

    def test_config_custom_profile(self):
        """Config should accept custom Firefox profile path."""
        config = Config(firefox_profile="/path/to/profile")

        assert config.firefox_profile == "/path/to/profile"

    def test_config_custom_theme(self):
        """Config should accept custom theme."""
        config = Config(theme="light")

        assert config.theme == "light"

    def test_config_serialization(self):
        """Config should serialize to JSON."""
        config = Config(firefox_profile="/test/path", theme="light")

        json_str = config.model_dump_json()
        data = json.loads(json_str)

        assert data["firefox_profile"] == "/test/path"
        assert data["theme"] == "light"

    def test_config_deserialization(self):
        """Config should deserialize from dict."""
        data = {"firefox_profile": "/custom/path", "theme": "dark"}

        config = Config.model_validate(data)

        assert config.firefox_profile == "/custom/path"
        assert config.theme == "dark"

    def test_config_partial_data(self):
        """Config should handle partial data with defaults."""
        data = {"theme": "light"}

        config = Config.model_validate(data)

        assert config.firefox_profile is None
        assert config.theme == "light"

    def test_config_extra_fields_ignored(self):
        """Config should ignore unknown fields."""
        data = {"theme": "dark", "unknown_field": "value"}

        config = Config.model_validate(data)

        assert config.theme == "dark"
        assert not hasattr(config, "unknown_field")


# ============================================================================
# Session Model Tests
# ============================================================================

class TestSessionModel:
    """Test Session Pydantic model."""

    def test_session_default_values(self):
        """Session should have empty defaults."""
        session = Session()

        assert session.uid is None
        assert session.cookies == {}
        assert session.conversation_id is None

    def test_session_with_uid(self):
        """Session should accept UID."""
        session = Session(uid="user123")

        assert session.uid == "user123"

    def test_session_with_cookies(self):
        """Session should accept cookies dict."""
        cookies = {"session": "abc123", "auth": "xyz789"}
        session = Session(cookies=cookies)

        assert session.cookies == cookies
        assert session.cookies["session"] == "abc123"

    def test_session_with_conversation_id(self):
        """Session should accept conversation ID."""
        session = Session(conversation_id="conv-456")

        assert session.conversation_id == "conv-456"

    def test_session_full_data(self):
        """Session should accept all fields."""
        session = Session(
            uid="user123",
            cookies={"key": "value"},
            conversation_id="conv-789"
        )

        assert session.uid == "user123"
        assert session.cookies == {"key": "value"}
        assert session.conversation_id == "conv-789"

    def test_session_serialization(self):
        """Session should serialize to JSON."""
        session = Session(
            uid="test-user",
            cookies={"token": "secret"},
            conversation_id="chat-123"
        )

        json_str = session.model_dump_json()
        data = json.loads(json_str)

        assert data["uid"] == "test-user"
        assert data["cookies"]["token"] == "secret"
        assert data["conversation_id"] == "chat-123"

    def test_session_deserialization(self):
        """Session should deserialize from dict."""
        data = {
            "uid": "restored-user",
            "cookies": {"auth": "token123"},
            "conversation_id": "restored-conv"
        }

        session = Session.model_validate(data)

        assert session.uid == "restored-user"
        assert session.cookies["auth"] == "token123"
        assert session.conversation_id == "restored-conv"


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

    def test_get_session_path(self):
        """get_session_path should return correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                session_path = get_session_path()

                assert session_path == fake_home / ".config" / "lumo-term" / "session.json"


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
                config = Config(firefox_profile="/test/path", theme="light")
                save_config(config)

                config_path = fake_home / ".config" / "lumo-term" / "config.json"
                assert config_path.exists()

                data = json.loads(config_path.read_text())
                assert data["firefox_profile"] == "/test/path"
                assert data["theme"] == "light"

    def test_load_config_existing(self):
        """load_config should load from existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            config_dir = fake_home / ".config" / "lumo-term"
            config_dir.mkdir(parents=True)

            config_data = {"firefox_profile": "/saved/path", "theme": "light"}
            (config_dir / "config.json").write_text(json.dumps(config_data))

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                config = load_config()

                assert config.firefox_profile == "/saved/path"
                assert config.theme == "light"

    def test_load_config_missing_file(self):
        """load_config should return defaults when file missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                config = load_config()

                assert config.firefox_profile is None
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
                assert config.firefox_profile is None
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
                original = Config(firefox_profile="/roundtrip/test", theme="light")
                save_config(original)
                loaded = load_config()

                assert loaded.firefox_profile == original.firefox_profile
                assert loaded.theme == original.theme


# ============================================================================
# Session Persistence Tests
# ============================================================================

class TestSessionPersistence:
    """Test session save/load functionality."""

    def test_save_session(self):
        """save_session should write session to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                session = Session(
                    uid="test-uid",
                    cookies={"auth": "token"},
                    conversation_id="conv-123"
                )
                save_session(session)

                session_path = fake_home / ".config" / "lumo-term" / "session.json"
                assert session_path.exists()

                data = json.loads(session_path.read_text())
                assert data["uid"] == "test-uid"
                assert data["cookies"]["auth"] == "token"

    def test_load_session_existing(self):
        """load_session should load from existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            config_dir = fake_home / ".config" / "lumo-term"
            config_dir.mkdir(parents=True)

            session_data = {
                "uid": "saved-uid",
                "cookies": {"key": "value"},
                "conversation_id": "saved-conv"
            }
            (config_dir / "session.json").write_text(json.dumps(session_data))

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                session = load_session()

                assert session.uid == "saved-uid"
                assert session.cookies["key"] == "value"
                assert session.conversation_id == "saved-conv"

    def test_load_session_missing_file(self):
        """load_session should return defaults when file missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                session = load_session()

                assert session.uid is None
                assert session.cookies == {}
                assert session.conversation_id is None

    def test_load_session_corrupted_json(self):
        """load_session should return defaults on corrupted JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            config_dir = fake_home / ".config" / "lumo-term"
            config_dir.mkdir(parents=True)

            (config_dir / "session.json").write_text("not valid json at all")

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                session = load_session()

                assert session.uid is None
                assert session.cookies == {}

    def test_save_and_load_session_roundtrip(self):
        """Session should survive save/load roundtrip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                original = Session(
                    uid="roundtrip-user",
                    cookies={"session": "abc", "auth": "xyz"},
                    conversation_id="roundtrip-conv"
                )
                save_session(original)
                loaded = load_session()

                assert loaded.uid == original.uid
                assert loaded.cookies == original.cookies
                assert loaded.conversation_id == original.conversation_id


# ============================================================================
# Clear Session Tests
# ============================================================================

class TestClearSession:
    """Test session clearing functionality."""

    def test_clear_session_removes_file(self):
        """clear_session should remove session file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            config_dir = fake_home / ".config" / "lumo-term"
            config_dir.mkdir(parents=True)

            session_path = config_dir / "session.json"
            session_path.write_text('{"uid": "to-be-deleted"}')
            assert session_path.exists()

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                clear_session()

                assert not session_path.exists()

    def test_clear_session_nonexistent_file(self):
        """clear_session should not error on missing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                # Should not raise
                clear_session()

    def test_clear_session_then_load(self):
        """Loading after clear should return defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                # Save session
                session = Session(uid="will-be-cleared", cookies={"key": "val"})
                save_session(session)

                # Clear it
                clear_session()

                # Load should return defaults
                loaded = load_session()
                assert loaded.uid is None
                assert loaded.cookies == {}


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_cookies_dict(self):
        """Session should handle empty cookies dict."""
        session = Session(uid="user", cookies={})
        json_str = session.model_dump_json()
        restored = Session.model_validate(json.loads(json_str))

        assert restored.cookies == {}

    def test_special_characters_in_values(self):
        """Config should handle special characters."""
        config = Config(firefox_profile="/path/with spaces/and'quotes")
        json_str = config.model_dump_json()
        restored = Config.model_validate(json.loads(json_str))

        assert restored.firefox_profile == "/path/with spaces/and'quotes"

    def test_unicode_in_session(self):
        """Session should handle unicode in cookies."""
        session = Session(cookies={"name": "José", "city": "東京"})
        json_str = session.model_dump_json()
        restored = Session.model_validate(json.loads(json_str))

        assert restored.cookies["name"] == "José"
        assert restored.cookies["city"] == "東京"

    def test_large_cookies_dict(self):
        """Session should handle large cookies dict."""
        cookies = {f"cookie_{i}": f"value_{i}" for i in range(100)}
        session = Session(cookies=cookies)

        assert len(session.cookies) == 100
        assert session.cookies["cookie_50"] == "value_50"

    def test_none_values_preserved(self):
        """None values should be preserved through roundtrip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("lumo_term.config.Path.home", return_value=fake_home):
                original = Session(uid=None, conversation_id=None)
                save_session(original)
                loaded = load_session()

                assert loaded.uid is None
                assert loaded.conversation_id is None
