"""Chromium-family backends (Chrome, Chromium, Edge).

Chrome and Edge need Selenium's separate driver/service/options classes
(they're not interchangeable), so they get thin, mostly-identical
subclasses that share profile discovery and argument-building.
"""

import platform
from pathlib import Path

from .base import BaseLumoBrowser, resolve_driver_path
from .profiles import find_chromium_binary, find_chromium_profile, is_chromium_locked

ChromiumProfile = tuple[Path, str]  # (user_data_dir, profile_directory_name)


def _build_chromium_args(user_data_dir: Path, profile_directory: str, headless: bool) -> list[str]:
    args = [
        f"--user-data-dir={user_data_dir}",
        f"--profile-directory={profile_directory}",
        # Without these, headless Chromium/Edge frequently fails to start at
        # all in containers/sandboxes/CI ("DevToolsActivePort file doesn't
        # exist") — restricted user namespaces break Chromium's own sandbox,
        # /dev/shm is often too small, and there's frequently no GPU/DRM
        # device available. Harmless on a normal desktop.
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        # Chromium hard-refuses to open a remote-debugging *port* against
        # what it recognizes as a real default profile directory ("DevTools
        # remote debugging requires a non-default data directory") — a
        # deliberate guard against exactly this kind of automation. Pipe
        # transport isn't subject to that check, so this is required (not
        # optional) whenever `user_data_dir` is the browser's real profile.
        "--remote-debugging-pipe",
    ]
    if headless:
        args.append("--headless=new")
    return args


class ChromeLumoBrowser(BaseLumoBrowser):
    """LUMO+ client automating the user's real Chrome (or Chromium) profile."""

    CHANNEL = "chrome"
    BROWSER_NAME = "Chrome"

    def _resolve_profile(self) -> ChromiumProfile:
        found = find_chromium_profile(self.CHANNEL, override=self.profile)
        if found is None:
            raise RuntimeError(
                f"No {self.BROWSER_NAME} profile found. Make sure {self.BROWSER_NAME} "
                f"is installed and you're logged in to LUMO+ ({self.LUMO_URL})."
            )
        return found

    def _is_profile_locked(self, profile: ChromiumProfile) -> bool:
        user_data_dir, _ = profile
        return is_chromium_locked(user_data_dir)

    def _build_driver(self, profile: ChromiumProfile):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        user_data_dir, profile_directory = profile
        options = Options()
        for arg in _build_chromium_args(user_data_dir, profile_directory, self.headless):
            options.add_argument(arg)

        binary = find_chromium_binary(self.CHANNEL)
        if binary:
            options.binary_location = binary

        driver_path = resolve_driver_path(
            wdm_subdir="chromedriver",
            binary_name="chromedriver.exe" if platform.system() == "Windows" else "chromedriver",
        )
        service = Service(executable_path=driver_path) if driver_path else Service()

        return webdriver.Chrome(service=service, options=options)


class ChromiumLumoBrowser(ChromeLumoBrowser):
    """LUMO+ client automating the user's real Chromium (not Google Chrome) profile."""

    CHANNEL = "chromium"
    BROWSER_NAME = "Chromium"


class EdgeLumoBrowser(BaseLumoBrowser):
    """LUMO+ client automating the user's real Microsoft Edge profile."""

    CHANNEL = "edge"
    BROWSER_NAME = "Edge"

    def _resolve_profile(self) -> ChromiumProfile:
        found = find_chromium_profile(self.CHANNEL, override=self.profile)
        if found is None:
            raise RuntimeError(
                f"No Edge profile found. Make sure Edge is installed and you're "
                f"logged in to LUMO+ ({self.LUMO_URL})."
            )
        return found

    def _is_profile_locked(self, profile: ChromiumProfile) -> bool:
        user_data_dir, _ = profile
        return is_chromium_locked(user_data_dir)

    def _build_driver(self, profile: ChromiumProfile):
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
        from selenium.webdriver.edge.service import Service

        user_data_dir, profile_directory = profile
        options = Options()
        for arg in _build_chromium_args(user_data_dir, profile_directory, self.headless):
            options.add_argument(arg)

        binary = find_chromium_binary(self.CHANNEL)
        if binary:
            options.binary_location = binary

        driver_path = resolve_driver_path(
            wdm_subdir="edgedriver",
            binary_name="msedgedriver.exe" if platform.system() == "Windows" else "msedgedriver",
        )
        service = Service(executable_path=driver_path) if driver_path else Service()

        return webdriver.Edge(service=service, options=options)
