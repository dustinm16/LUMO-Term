"""Firefox cookie extraction for LUMO+ authentication."""

import re
import shutil
import sqlite3
import tempfile
from pathlib import Path

from .config import Session, load_config, load_session, save_session


class AuthError(Exception):
    """Authentication error."""

    pass


def find_firefox_profiles() -> list[Path]:
    """Find all Firefox profile directories."""
    firefox_dir = Path.home() / ".mozilla" / "firefox"
    if not firefox_dir.exists():
        return []

    profiles = []
    for path in firefox_dir.iterdir():
        if path.is_dir() and (path / "cookies.sqlite").exists():
            profiles.append(path)

    # Sort by modification time, most recent first
    profiles.sort(key=lambda p: (p / "cookies.sqlite").stat().st_mtime, reverse=True)
    return profiles


def get_firefox_profile() -> Path:
    """Get the Firefox profile to use for cookie extraction."""
    config = load_config()

    if config.firefox_profile:
        profile_path = Path(config.firefox_profile)
        if profile_path.exists() and (profile_path / "cookies.sqlite").exists():
            return profile_path
        raise AuthError(f"Configured Firefox profile not found: {config.firefox_profile}")

    profiles = find_firefox_profiles()
    if not profiles:
        raise AuthError(
            "No Firefox profiles found. Make sure Firefox is installed and has been used."
        )

    return profiles[0]  # Use most recently modified profile


def extract_cookies_from_profile(profile_path: Path, domain: str) -> dict[str, str]:
    """Extract cookies for a domain from a Firefox profile.

    Firefox locks its cookies.sqlite file, so we copy it to a temp location first.
    """
    cookies_db = profile_path / "cookies.sqlite"
    if not cookies_db.exists():
        raise AuthError(f"cookies.sqlite not found in profile: {profile_path}")

    cookies = {}

    # Copy database to temp file to avoid lock issues
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        shutil.copy2(cookies_db, tmp_path)

        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # Query cookies for the domain (including subdomains)
        cursor.execute(
            """
            SELECT name, value FROM moz_cookies
            WHERE host LIKE ? OR host LIKE ?
            """,
            (f"%{domain}", f".{domain}"),
        )

        for name, value in cursor.fetchall():
            cookies[name] = value

        conn.close()
    finally:
        tmp_path.unlink(missing_ok=True)

    return cookies


def extract_uid_from_cookies(cookies: dict[str, str]) -> str | None:
    """Extract the UID from AUTH-{uid} cookie name pattern."""
    for name in cookies:
        if name.startswith("AUTH-"):
            return name[5:]  # Remove "AUTH-" prefix
    return None


def get_auth_session(force_refresh: bool = False) -> Session:
    """Get authentication session, extracting from Firefox if needed.

    Args:
        force_refresh: If True, always extract fresh cookies from Firefox.

    Returns:
        Session object with uid and cookies populated.

    Raises:
        AuthError: If authentication cannot be obtained.
    """
    if not force_refresh:
        session = load_session()
        if session.uid and session.cookies:
            return session

    # Extract fresh cookies from Firefox
    profile = get_firefox_profile()
    cookies = extract_cookies_from_profile(profile, "proton.me")

    if not cookies:
        raise AuthError(
            "No Proton cookies found. Please log in to LUMO+ in Firefox first: "
            "https://lumo.proton.me"
        )

    uid = extract_uid_from_cookies(cookies)
    if not uid:
        raise AuthError(
            "AUTH cookie not found. Please log in to LUMO+ in Firefox: "
            "https://lumo.proton.me"
        )

    session = Session(uid=uid, cookies=cookies)
    save_session(session)

    return session


def format_cookie_header(cookies: dict[str, str]) -> str:
    """Format cookies dict as Cookie header value."""
    return "; ".join(f"{name}={value}" for name, value in cookies.items())
