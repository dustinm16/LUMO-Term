"""Configuration management for LUMO-Term."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class Config(BaseModel):
    """Application configuration."""

    browser: str | None = None  # "firefox" | "chrome" | "edge" | "chromium"; None = auto-detect
    browser_profile: str | None = None  # Override profile auto-detection
    theme: str = "dark"


def get_config_dir() -> Path:
    """Get the configuration directory, creating it if needed."""
    config_dir = Path.home() / ".config" / "lumo-term"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the config file path."""
    return get_config_dir() / "config.json"


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
