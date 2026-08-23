"""Browser-agnostic LUMO+ automation logic shared by all Selenium backends.

Every concrete backend (Firefox, Chrome, Edge) launches its webdriver
directly against the user's *real* profile directory rather than a copy —
this sidesteps having to reverse-engineer each browser's on-disk cookie/
IndexedDB/session format (which is what made the old copy-a-profile
approach fragile and, for Chromium, would have meant decrypting
OS-keychain-wrapped cookies). The one condition this imposes: the browser
must be fully closed before `start()` runs, since both Firefox and Chromium
refuse a second process against a profile they already have open.
"""

import asyncio
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def resolve_driver_path(wdm_subdir: str, binary_name: str) -> str | None:
    """Prefer a cached driver binary, then PATH; otherwise None.

    None tells the caller to build its Selenium `Service` with no explicit
    `executable_path`, which lets Selenium's own bundled Selenium Manager
    (4.6+) resolve and download the matching driver. That's the preferred
    path over `webdriver-manager` (this tool's former approach): Selenium
    Manager matches the driver version to the actually-installed browser
    automatically and, in practice, has proven more reliable here — the
    equivalent webdriver-manager lookup for Edge fails outright in network
    environments that can't reach msedgedriver.azureedge.net, even though
    the same environment reaches Selenium Manager's own endpoint fine.
    """
    wdm_root = Path.home() / ".wdm" / "drivers" / wdm_subdir
    if wdm_root.exists():
        candidates = [p for p in wdm_root.rglob(binary_name) if p.is_file()]
        if candidates:
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return str(candidates[0])

    which_name = binary_name[:-4] if binary_name.endswith(".exe") else binary_name
    return shutil.which(which_name)


class BaseLumoBrowser(ABC):
    """Selenium-driven LUMO+ client. Subclass per browser backend."""

    LUMO_URL = "https://lumo.proton.me"
    BROWSER_NAME = "browser"

    def __init__(self, profile: Path | None = None, headless: bool = True):
        self.profile = profile
        self.headless = headless
        self._driver: Any = None

    @abstractmethod
    def _resolve_profile(self) -> Any:
        """Locate the real browser profile to launch against.

        Raises RuntimeError with a user-facing message if none is found.
        """

    @abstractmethod
    def _is_profile_locked(self, profile: Any) -> bool:
        """True if the real browser currently has this profile open."""

    @abstractmethod
    def _build_driver(self, profile: Any):
        """Construct and return a started Selenium webdriver for `profile`."""

    async def start(self, progress_callback: Callable[[str], None] | None = None) -> None:
        """Start the browser and navigate to LUMO."""
        def log(msg: str):
            if progress_callback:
                progress_callback(msg)

        log("Locating browser profile...")
        profile = self._resolve_profile()

        if self._is_profile_locked(profile):
            raise RuntimeError(
                f"{self.BROWSER_NAME} is currently open with this profile. "
                f"Please fully quit {self.BROWSER_NAME} and try again — "
                "lumo launches its own instance directly against your real "
                "profile, which the browser won't allow while it's already running."
            )

        log(f"Launching {self.BROWSER_NAME}...")
        self._driver = self._build_driver(profile)
        self._driver.set_window_size(1280, 720)

        log("Navigating to LUMO...")
        self._driver.get(self.LUMO_URL)

        log("Waiting for LUMO to load...")
        await self._wait_for_lumo_ready()

    async def _wait_for_lumo_ready(self, timeout: float = 60.0) -> None:
        """Wait for LUMO to be fully loaded and authenticated."""
        try:
            wait = WebDriverWait(self._driver, timeout)
            # LUMO's composer is a `<textarea class="tiptap ProseMirror ...">`,
            # not a div — `.tiptap.ProseMirror` matches by class regardless of
            # tag. `div[contenteditable="true"]` stays as a fallback in case
            # LUMO ever reverts to a contenteditable-div editor. Missing the
            # textarea form here previously spun for the full timeout on an
            # otherwise fully-loaded, authenticated page.
            wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR,
                '.tiptap.ProseMirror, div[contenteditable="true"]'
            )))
            await asyncio.sleep(2)
        except TimeoutException:
            current_url = self._driver.current_url
            if "account.proton.me" in current_url or "login" in current_url.lower():
                raise RuntimeError(
                    "Not logged in to Proton. Please log in to LUMO+ in your "
                    f"browser first: {self.LUMO_URL}"
                )
            raise RuntimeError(f"LUMO failed to load (timeout). Current URL: {current_url}")

        current_url = self._driver.current_url
        if "/guest" in current_url:
            raise RuntimeError(
                "LUMO loaded but as a guest/anonymous session, not your logged-in "
                f"account. Please confirm you're logged in at {self.LUMO_URL} in "
                "this profile, then try again."
            )

    async def stop(self) -> None:
        """Close the browser."""
        if self._driver:
            self._driver.quit()
            self._driver = None

    def _find_input_element(self):
        """Find the message input element (TipTap/ProseMirror editor).

        Currently a `<textarea class="tiptap ProseMirror composer ...">`;
        the div-based selectors are kept as fallbacks in case LUMO reverts
        to a contenteditable-div editor.
        """
        selectors = [
            'textarea.tiptap.ProseMirror',
            '.tiptap.ProseMirror',
            'div[contenteditable="true"].composer',
            'div[contenteditable="true"]',
            'textarea',
            '[data-testid="composer-input"]',
        ]

        for selector in selectors:
            try:
                elements = self._driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if elem.is_displayed():
                        classes = elem.get_attribute("class") or ""
                        if "composer" in classes or "ProseMirror" in classes or elem.tag_name == "textarea":
                            return elem
                        if elem.get_attribute("contenteditable") == "true":
                            return elem
            except NoSuchElementException:
                continue

        raise RuntimeError("Could not find message input element")

    def _find_send_button(self):
        """Find the send button."""
        selectors = [
            'button[type="submit"]',
            'button[aria-label*="Send"]',
            'button[aria-label*="send"]',
            'button:has(svg)',
        ]

        for selector in selectors:
            try:
                elements = self._driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if elem.is_displayed() and elem.is_enabled():
                        return elem
            except NoSuchElementException:
                continue

        return None

    async def send_message(
        self,
        message: str,
        on_token: Callable[[str], None] | None = None
    ) -> str:
        """Send a message to LUMO and get the response."""
        if not self._driver:
            raise RuntimeError("Browser not started. Call start() first.")

        input_elem = self._find_input_element()

        input_elem.click()
        await asyncio.sleep(0.2)

        from selenium.webdriver.common.action_chains import ActionChains
        actions = ActionChains(self._driver)
        actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
        await asyncio.sleep(0.1)

        lines = message.split('\n')
        for i, line in enumerate(lines):
            input_elem.send_keys(line)
            if i < len(lines) - 1:
                actions = ActionChains(self._driver)
                actions.key_down(Keys.SHIFT).send_keys(Keys.RETURN).key_up(Keys.SHIFT).perform()
                await asyncio.sleep(0.05)

        await asyncio.sleep(0.3)

        input_elem.send_keys(Keys.RETURN)

        last_text = ""
        stable_count = 0
        max_wait = 120
        poll_interval = 0.3

        await asyncio.sleep(1.0)

        for _ in range(int(max_wait / poll_interval)):
            await asyncio.sleep(poll_interval)

            current_text = self._get_latest_response()

            if current_text and current_text != last_text:
                if on_token and len(current_text) > len(last_text):
                    new_content = current_text[len(last_text):]
                    on_token(new_content)
                last_text = current_text
                stable_count = 0
            elif current_text:
                stable_count += 1
                if stable_count > 6:
                    break

            try:
                stop_btns = self._driver.find_elements(By.CSS_SELECTOR,
                    'button[aria-label*="Stop"], button:contains("Stop")')
                if not stop_btns and current_text:
                    stable_count += 1
            except Exception:
                pass

        return last_text

    def _get_latest_response(self) -> str:
        """Get the latest assistant response text."""
        selectors = [
            '.progressive-markdown-content',
            '.lumo-markdown',
            '[data-testid="message-content"]',
            '.message-content',
        ]

        for selector in selectors:
            try:
                elements = self._driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in reversed(elements):
                    text = elem.text
                    if text:
                        try:
                            parent_html = elem.find_element(By.XPATH, "../..").get_attribute("outerHTML")[:200]
                            if "user-msg" not in parent_html:
                                return text
                        except Exception:
                            return text
            except Exception:
                continue

        return ""

    async def new_conversation(self) -> None:
        """Start a new conversation."""
        if not self._driver:
            raise RuntimeError("Browser not started. Call start() first.")

        selectors = [
            'button[aria-label*="New"]',
            'a[href*="/new"]',
            'button:contains("New chat")',
            '[data-testid="new-conversation"]',
        ]

        for selector in selectors:
            try:
                elements = self._driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if elem.is_displayed():
                        elem.click()
                        await self._wait_for_lumo_ready()
                        return
            except Exception:
                continue

        self._driver.get(self.LUMO_URL)
        await self._wait_for_lumo_ready()
