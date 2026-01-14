"""Headless browser automation for LUMO+ interaction.

This module uses Playwright to automate Firefox with the user's existing
profile, leveraging LUMO's built-in encryption without needing to
reverse-engineer the crypto.
"""

import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator, Callable

from playwright.async_api import async_playwright, Page, Browser, BrowserContext


class LumoBrowser:
    """Headless browser client for LUMO+ AI assistant."""

    LUMO_URL = "https://lumo.proton.me"

    def __init__(self, firefox_profile: Path | None = None, headless: bool = True):
        """Initialize the LUMO browser client.

        Args:
            firefox_profile: Path to Firefox profile directory. If None, auto-detects.
            headless: Run browser in headless mode (no visible window).
        """
        self.firefox_profile = firefox_profile or self._find_firefox_profile()
        self.headless = headless
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

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

    async def start(self) -> None:
        """Start the browser and navigate to LUMO."""
        self._playwright = await async_playwright().start()

        # Launch Firefox with persistent context (uses profile's storage)
        self._context = await self._playwright.firefox.launch_persistent_context(
            user_data_dir=str(self.firefox_profile),
            headless=self.headless,
            viewport={"width": 1280, "height": 720},
            # Avoid modifying the original profile
            args=["--no-remote"],
        )

        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

        # Navigate to LUMO
        await self._page.goto(self.LUMO_URL, wait_until="networkidle")

        # Wait for the app to be ready
        await self._wait_for_lumo_ready()

    async def _wait_for_lumo_ready(self, timeout: float = 30.0) -> None:
        """Wait for LUMO to be fully loaded and ready."""
        # Wait for the main input to be visible
        try:
            await self._page.wait_for_selector(
                'textarea[placeholder*="Ask"], div[contenteditable="true"]',
                timeout=timeout * 1000
            )
        except Exception:
            # Check if we need to log in
            if "account.proton.me" in self._page.url:
                raise RuntimeError(
                    "Not logged in to Proton. Please log in to LUMO+ in Firefox first: "
                    f"{self.LUMO_URL}"
                )
            raise RuntimeError(f"LUMO failed to load. Current URL: {self._page.url}")

    async def stop(self) -> None:
        """Close the browser."""
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

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
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")

        # Find and fill the input
        input_selector = 'textarea[placeholder*="Ask"], div[contenteditable="true"]'
        await self._page.fill(input_selector, message)

        # Set up response capture before sending
        response_text = ""
        response_complete = asyncio.Event()

        # Inject script to capture streaming response
        await self._page.evaluate("""
            window.__lumoResponse = '';
            window.__lumoComplete = false;

            // Hook into the response display area
            const observer = new MutationObserver((mutations) => {
                const responseArea = document.querySelector('[data-testid="message-content"], .message-content, .assistant-message');
                if (responseArea) {
                    window.__lumoResponse = responseArea.innerText || responseArea.textContent;
                }
            });

            observer.observe(document.body, { childList: true, subtree: true, characterData: true });
            window.__lumoObserver = observer;
        """)

        # Click send button or press Enter
        send_button = await self._page.query_selector('button[type="submit"], button[aria-label*="Send"]')
        if send_button:
            await send_button.click()
        else:
            await self._page.keyboard.press("Enter")

        # Poll for response completion
        last_text = ""
        stable_count = 0
        max_wait = 120  # 2 minutes max
        poll_interval = 0.2

        for _ in range(int(max_wait / poll_interval)):
            await asyncio.sleep(poll_interval)

            current_text = await self._page.evaluate("window.__lumoResponse")

            if current_text and current_text != last_text:
                # New content
                if on_token and len(current_text) > len(last_text):
                    new_content = current_text[len(last_text):]
                    on_token(new_content)
                last_text = current_text
                stable_count = 0
            elif current_text:
                stable_count += 1
                # Consider complete after 1.5 seconds of stability
                if stable_count > 7:
                    break

            # Check if there's a "stop generating" button (indicates still streaming)
            stop_button = await self._page.query_selector('button[aria-label*="Stop"], button:has-text("Stop")')
            if not stop_button and current_text:
                stable_count += 2  # Speed up completion detection

        # Cleanup observer
        await self._page.evaluate("""
            if (window.__lumoObserver) {
                window.__lumoObserver.disconnect();
            }
        """)

        return last_text

    async def new_conversation(self) -> None:
        """Start a new conversation."""
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")

        # Look for new chat button
        new_chat = await self._page.query_selector(
            'button[aria-label*="New"], a[href*="/new"], button:has-text("New chat")'
        )
        if new_chat:
            await new_chat.click()
            await self._wait_for_lumo_ready()
        else:
            # Fallback: navigate to base URL
            await self._page.goto(self.LUMO_URL)
            await self._wait_for_lumo_ready()

    async def get_conversations(self) -> list[dict]:
        """Get list of recent conversations."""
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")

        # This would need to be adapted based on LUMO's actual DOM structure
        conversations = await self._page.evaluate("""
            () => {
                const items = document.querySelectorAll('[data-testid="conversation-item"], .conversation-item');
                return Array.from(items).map(item => ({
                    title: item.textContent?.trim() || 'Untitled',
                    href: item.querySelector('a')?.href || ''
                }));
            }
        """)
        return conversations


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
