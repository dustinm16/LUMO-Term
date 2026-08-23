"""Browser backend selection for LUMO-Term."""

from pathlib import Path

from .base import BaseLumoBrowser
from .chromium import ChromeLumoBrowser, ChromiumLumoBrowser, EdgeLumoBrowser
from .firefox import FirefoxLumoBrowser
from .profiles import detect_installed_browsers

BROWSER_CHOICES = ("firefox", "chrome", "edge", "chromium")

_BACKENDS: dict[str, type[BaseLumoBrowser]] = {
    "firefox": FirefoxLumoBrowser,
    "chrome": ChromeLumoBrowser,
    "edge": EdgeLumoBrowser,
    "chromium": ChromiumLumoBrowser,
}

# Preference order when nothing was explicitly requested.
_AUTO_DETECT_PRIORITY = ("firefox", "chrome", "edge", "chromium")


def _auto_detect_browser() -> str:
    installed = set(detect_installed_browsers())
    for name in _AUTO_DETECT_PRIORITY:
        if name in installed:
            return name
    raise RuntimeError(
        "No supported browser (Firefox, Chrome, Edge, Chromium) was found. "
        "Install one of them and log in to LUMO+, then try again."
    )


def create_browser_client(
    browser: str | None = None,
    profile: Path | None = None,
    headless: bool = True,
) -> BaseLumoBrowser:
    """Create the LUMO+ browser client for the given (or auto-detected) browser.

    Args:
        browser: One of BROWSER_CHOICES, or None to auto-detect.
        profile: Explicit profile path override (meaning is backend-specific:
            a Firefox profile dir, or a Chromium `.../User Data/Default` dir).
        headless: Run without a visible window.
    """
    name = browser or _auto_detect_browser()
    if name not in _BACKENDS:
        raise ValueError(f"Unknown browser {name!r}. Choose from: {', '.join(BROWSER_CHOICES)}")

    backend_cls = _BACKENDS[name]
    return backend_cls(profile=profile, headless=headless)


async def create_lumo_client(
    browser: str | None = None,
    profile: Path | None = None,
    headless: bool = True,
) -> BaseLumoBrowser:
    """Create and start a LUMO+ browser client."""
    client = create_browser_client(browser=browser, profile=profile, headless=headless)
    await client.start()
    return client
