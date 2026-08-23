"""Firefox backend: launches directly against the user's real profile."""

import platform
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

from .base import BaseLumoBrowser, resolve_driver_path
from .profiles import find_firefox_profile, is_firefox_locked


class FirefoxLumoBrowser(BaseLumoBrowser):
    """LUMO+ client automating the user's real Firefox profile."""

    BROWSER_NAME = "Firefox"

    def _resolve_profile(self) -> Path:
        profile = self.profile or find_firefox_profile()
        if profile is None:
            raise RuntimeError(
                "No Firefox profile found. Make sure Firefox is installed, "
                f"you're logged in to LUMO+ ({self.LUMO_URL}), and — if Firefox "
                "was installed via snap/flatpak — that its profile directory is "
                "readable."
            )
        if not (profile / "cookies.sqlite").exists():
            raise RuntimeError(f"Not a valid Firefox profile (no cookies.sqlite): {profile}")
        return profile

    def _is_profile_locked(self, profile: Path) -> bool:
        return is_firefox_locked(profile)

    def _build_driver(self, profile: Path):
        options = Options()
        options.profile = str(profile)

        if self.headless:
            options.add_argument('-headless')

        driver_path = resolve_driver_path(
            wdm_subdir="geckodriver",
            binary_name="geckodriver.exe" if platform.system() == "Windows" else "geckodriver",
        )
        service = Service(executable_path=driver_path) if driver_path else Service()

        return webdriver.Firefox(service=service, options=options)
