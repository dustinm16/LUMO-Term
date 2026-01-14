"""Configuration management for LUMO-Term."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class Config(BaseModel):
    """Application configuration."""

    firefox_profile: str | None = None  # Override auto-detection
    theme: str = "dark"


class Session(BaseModel):
    """Cached session data."""

    uid: str | None = None
    cookies: dict[str, str] = {}
    conversation_id: str | None = None


def get_config_dir() -> Path:
    """Get the configuration directory, creating it if needed."""
    config_dir = Path.home() / ".config" / "lumo-term"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the config file path."""
    return get_config_dir() / "config.json"


def get_session_path() -> Path:
    """Get the session cache file path."""
    return get_config_dir() / "session.json"


def load_config() -> Config:
    """Load configuration from file, or return defaults."""
    config_path = get_config_path()
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
            return Config.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            pass
    return Config()


def save_config(config: Config) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    config_path.write_text(config.model_dump_json(indent=2))


def load_session() -> Session:
    """Load cached session data."""
    session_path = get_session_path()
    if session_path.exists():
        try:
            data = json.loads(session_path.read_text())
            return Session.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            pass
    return Session()


def save_session(session: Session) -> None:
    """Save session data to cache."""
    session_path = get_session_path()
    session_path.write_text(session.model_dump_json(indent=2))


def clear_session() -> None:
    """Clear cached session data."""
    session_path = get_session_path()
    if session_path.exists():
        session_path.unlink()
