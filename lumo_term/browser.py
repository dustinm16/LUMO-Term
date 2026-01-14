"""Browser automation for LUMO+ interaction using Selenium.

This module uses Selenium to automate Firefox with the user's existing
profile, leveraging LUMO's built-in encryption without needing to
reverse-engineer the crypto.

Uses Firefox's native headless mode for invisible operation while
maintaining full browser functionality including IndexedDB access.
"""

import asyncio
import shutil
import tempfile
import time
from pathlib import Path
from typing import Callable

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.firefox import GeckoDriverManager


class LumoBrowser:
    """Browser client for LUMO+ AI assistant using Selenium."""

    LUMO_URL = "https://lumo.proton.me"

    def __init__(self, firefox_profile: Path | None = None, headless: bool = True):
        """Initialize the LUMO browser client.

        Args:
            firefox_profile: Path to Firefox profile directory. If None, auto-detects.
            headless: Run in headless mode (invisible) if True, visible window if False.
        """
        self.firefox_profile = firefox_profile or self._find_firefox_profile()
        self.headless = headless
        self._driver: webdriver.Firefox | None = None
        self._temp_profile: Path | None = None

    @staticmethod
    def _find_firefox_profile() -> Path:
        """Find the most recently used Firefox profile."""
        firefox_dir = Path.home() / ".mozilla" / "firefox"
        if not firefox_dir.exists():
            raise RuntimeError("Firefox not found. Please install Firefox and log in to LUMO+")

        profiles = []
        for path in firefox_dir.iterdir():
            if path.is_dir() and (path / "cookies.sqlite").exists():
                profiles.append(path)

        if not profiles:
            raise RuntimeError("No Firefox profiles found")

        # Use most recently modified profile
        profiles.sort(key=lambda p: (p / "cookies.sqlite").stat().st_mtime, reverse=True)
        return profiles[0]

    def _copy_profile(self) -> Path:
        """Copy essential Firefox profile files to temp directory."""
        # Use home directory instead of /tmp to avoid space issues
        temp_base = Path.home() / ".cache" / "lumo-term"
        temp_base.mkdir(parents=True, exist_ok=True)

        # Clean old temp profiles
        for old_profile in temp_base.glob("profile-*"):
            try:
                shutil.rmtree(old_profile, ignore_errors=True)
            except Exception:
                pass

        temp_dir = Path(tempfile.mkdtemp(prefix="profile-", dir=temp_base))

        # Essential files for authentication
        essential_files = [
            "cookies.sqlite",
            "cookies.sqlite-wal",
            "cookies.sqlite-shm",
            "prefs.js",
        ]

        # Copy essential files
        for filename in essential_files:
            src = self.firefox_profile / filename
            if src.exists():
                try:
                    shutil.copy2(src, temp_dir / filename)
                except (OSError, shutil.Error):
                    continue

        # Only copy proton.me storage (not all extensions)
        storage_src = self.firefox_profile / "storage" / "default"
        if storage_src.exists():
            storage_dest = temp_dir / "storage" / "default"
            storage_dest.mkdir(parents=True, exist_ok=True)

            for item in storage_src.iterdir():
                if "proton" in item.name.lower() or "lumo" in item.name.lower():
                    try:
                        if item.is_dir():
                            shutil.copytree(item, storage_dest / item.name,
                                          dirs_exist_ok=True,
                                          ignore_dangling_symlinks=True)
                    except (OSError, shutil.Error):
                        continue

        return temp_dir

    async def start(self, progress_callback: Callable[[str], None] | None = None) -> None:
        """Start the browser and navigate to LUMO."""
        def log(msg: str):
            if progress_callback:
                progress_callback(msg)

        log("Copying profile...")
        self._temp_profile = self._copy_profile()

        log("Configuring Firefox...")
        options = Options()
        options.profile = str(self._temp_profile)

        # Use Firefox's native headless mode
        if self.headless:
            options.add_argument('-headless')

        # Additional options for stability
        options.set_preference("browser.tabs.remote.autostart", False)
        options.set_preference("browser.tabs.remote.autostart.2", False)

        log("Installing geckodriver...")
        driver_path = GeckoDriverManager().install()
        service = Service(executable_path=driver_path)

        log("Launching Firefox...")
        self._driver = webdriver.Firefox(service=service, options=options)
        self._driver.set_window_size(1280, 720)

        log("Navigating to LUMO...")
        self._driver.get(self.LUMO_URL)

        log("Waiting for LUMO to load...")
        await self._wait_for_lumo_ready()

    async def _wait_for_lumo_ready(self, timeout: float = 60.0) -> None:
        """Wait for LUMO to be fully loaded and ready."""
        try:
            wait = WebDriverWait(self._driver, timeout)
            # Wait for TipTap/ProseMirror editor to appear
            wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR,
                'div.tiptap.ProseMirror, div[contenteditable="true"]'
            )))
            # Give UI a moment to stabilize
            await asyncio.sleep(2)
        except TimeoutException:
            current_url = self._driver.current_url
            if "account.proton.me" in current_url or "login" in current_url.lower():
                raise RuntimeError(
                    "Not logged in to Proton. Please log in to LUMO+ in Firefox first: "
                    f"{self.LUMO_URL}"
                )
            raise RuntimeError(f"LUMO failed to load (timeout). Current URL: {current_url}")

    async def stop(self) -> None:
        """Close the browser and clean up."""
        if self._driver:
            self._driver.quit()
            self._driver = None

        # Clean up temp profile
        if self._temp_profile and self._temp_profile.parent.exists():
            shutil.rmtree(self._temp_profile.parent, ignore_errors=True)

    def _find_input_element(self):
        """Find the message input element (TipTap/ProseMirror editor)."""
        selectors = [
            'div.tiptap.ProseMirror',  # LUMO's TipTap editor
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
                        # For contenteditable divs, check if it looks like a composer
                        classes = elem.get_attribute("class") or ""
                        if "composer" in classes or "ProseMirror" in classes or elem.tag_name == "textarea":
                            return elem
                        # Fallback: return first visible contenteditable
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
            'button:has(svg)',  # Often the send button has an icon
        ]

        for selector in selectors:
            try:
                elements = self._driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if elem.is_displayed() and elem.is_enabled():
                        return elem
            except NoSuchElementException:
                continue

        return None  # Will use Enter key instead

    async def send_message(
        self,
        message: str,
        on_token: Callable[[str], None] | None = None
    ) -> str:
        """Send a message to LUMO and get the response.

        Args:
            message: The message to send.
            on_token: Optional callback for streaming tokens.

        Returns:
            The complete response text.
        """
        if not self._driver:
            raise RuntimeError("Browser not started. Call start() first.")

        # Find the input element (TipTap editor)
        input_elem = self._find_input_element()

        # Click to focus
        input_elem.click()
        await asyncio.sleep(0.2)

        # Clear any existing content and type the message
        # For TipTap, select all and delete first
        from selenium.webdriver.common.action_chains import ActionChains
        actions = ActionChains(self._driver)
        actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
        await asyncio.sleep(0.1)

        # Type the message directly
        input_elem.send_keys(message)
        await asyncio.sleep(0.3)

        # Press Enter to send
        input_elem.send_keys(Keys.RETURN)

        # Poll for response
        last_text = ""
        stable_count = 0
        max_wait = 120  # 2 minutes max
        poll_interval = 0.3

        # Wait a moment for response to start
        await asyncio.sleep(1.0)

        for _ in range(int(max_wait / poll_interval)):
            await asyncio.sleep(poll_interval)

            # Try to find the latest response
            current_text = self._get_latest_response()

            if current_text and current_text != last_text:
                # New content
                if on_token and len(current_text) > len(last_text):
                    new_content = current_text[len(last_text):]
                    on_token(new_content)
                last_text = current_text
                stable_count = 0
            elif current_text:
                stable_count += 1
                # Consider complete after 2 seconds of stability
                if stable_count > 6:
                    break

            # Check if there's a "stop generating" button
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
            '.progressive-markdown-content',  # LUMO's actual response content
            '.lumo-markdown',
            '[data-testid="message-content"]',
            '.message-content',
        ]

        for selector in selectors:
            try:
                elements = self._driver.find_elements(By.CSS_SELECTOR, selector)
                # Filter to get only assistant responses (skip user messages)
                for elem in reversed(elements):
                    text = elem.text
                    if text:
                        # Check parent for assistant indicator
                        try:
                            parent_html = elem.find_element(By.XPATH, "../..").get_attribute("outerHTML")[:200]
                            # User messages have 'user-msg' class
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

        # Look for new chat button
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

        # Fallback: navigate to base URL
        self._driver.get(self.LUMO_URL)
        await self._wait_for_lumo_ready()


async def create_lumo_client(
    firefox_profile: Path | None = None,
    headless: bool = True
) -> LumoBrowser:
    """Create and initialize a LUMO browser client.

    Args:
        firefox_profile: Path to Firefox profile. Auto-detected if None.
        headless: Run without visible browser window.

    Returns:
        Initialized LumoBrowser instance.
    """
    client = LumoBrowser(firefox_profile=firefox_profile, headless=headless)
    await client.start()
    return client
