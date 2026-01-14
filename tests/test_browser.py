"""Tests for browser automation functionality."""

import asyncio
import pytest
from pathlib import Path

from lumo_term.browser import LumoBrowser


# ============================================================================
# Browser Initialization Tests
# ============================================================================

class TestBrowserInit:
    """Test browser initialization and configuration."""

    def test_browser_creates_with_defaults(self):
        """Browser should create with default settings."""
        browser = LumoBrowser()
        assert browser.headless is True
        assert browser.firefox_profile is not None
        assert browser._driver is None

    def test_browser_creates_with_custom_headless(self):
        """Browser should accept headless parameter."""
        browser = LumoBrowser(headless=False)
        assert browser.headless is False

    def test_browser_finds_firefox_profile(self):
        """Browser should auto-detect Firefox profile."""
        browser = LumoBrowser()
        assert browser.firefox_profile.exists()
        assert (browser.firefox_profile / "cookies.sqlite").exists()

    def test_browser_accepts_custom_profile(self, tmp_path):
        """Browser should accept custom profile path."""
        # Create a fake profile
        fake_profile = tmp_path / "fake_profile"
        fake_profile.mkdir()
        (fake_profile / "cookies.sqlite").touch()

        browser = LumoBrowser(firefox_profile=fake_profile)
        assert browser.firefox_profile == fake_profile


# ============================================================================
# Browser Lifecycle Tests
# ============================================================================

@pytest.mark.integration
class TestBrowserLifecycle:
    """Test browser start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_browser_starts_successfully(self, browser):
        """Browser should start and connect to LUMO."""
        assert browser._driver is not None
        assert "lumo.proton.me" in browser._driver.current_url

    @pytest.mark.asyncio
    async def test_browser_stops_cleanly(self, firefox_profile):
        """Browser should stop and clean up resources."""
        client = LumoBrowser(firefox_profile=firefox_profile, headless=True)
        await client.start()

        # Verify started
        assert client._driver is not None
        temp_profile = client._temp_profile

        # Stop
        await client.stop()

        # Verify stopped
        assert client._driver is None
        # Temp profile should be cleaned up
        assert temp_profile is None or not temp_profile.exists()

    @pytest.mark.asyncio
    async def test_browser_handles_multiple_start_stop_cycles(self, firefox_profile):
        """Browser should handle multiple start/stop cycles."""
        for i in range(2):
            client = LumoBrowser(firefox_profile=firefox_profile, headless=True)
            await client.start()
            assert client._driver is not None
            await client.stop()
            assert client._driver is None

    @pytest.mark.asyncio
    async def test_start_progress_callback(self, firefox_profile):
        """Browser should call progress callback during startup."""
        client = LumoBrowser(firefox_profile=firefox_profile, headless=True)
        progress_messages = []

        def on_progress(msg: str):
            progress_messages.append(msg)

        try:
            await client.start(progress_callback=on_progress)

            # Should have multiple progress updates
            assert len(progress_messages) >= 4
            assert any("profile" in msg.lower() for msg in progress_messages)
            assert any("firefox" in msg.lower() for msg in progress_messages)
            assert any("lumo" in msg.lower() for msg in progress_messages)
        finally:
            await client.stop()


# ============================================================================
# Message Sending Tests
# ============================================================================

@pytest.mark.integration
class TestMessageSending:
    """Test sending messages to LUMO."""

    @pytest.mark.asyncio
    async def test_send_simple_message(self, browser, test_messages):
        """Should send a simple message and get a response."""
        response = await browser.send_message(test_messages["simple"])

        assert response is not None
        assert len(response) > 0
        # Response should contain acknowledgment
        assert "test" in response.lower() or "passed" in response.lower()

    @pytest.mark.asyncio
    async def test_send_math_question(self, browser, test_messages):
        """Should correctly answer a math question."""
        response = await browser.send_message(test_messages["math"])

        assert response is not None
        assert "4" in response

    @pytest.mark.asyncio
    async def test_send_longer_message(self, browser, test_messages):
        """Should handle longer messages."""
        response = await browser.send_message(test_messages["long"])

        assert response is not None
        assert len(response) > 50  # Should have a substantial response
        assert "recursion" in response.lower() or "function" in response.lower()

    @pytest.mark.asyncio
    async def test_send_empty_message_handling(self, browser):
        """Should handle empty or whitespace messages gracefully."""
        # The input element might not accept empty strings,
        # so we test with minimal input
        response = await browser.send_message(".")

        # Should still get some response
        assert response is not None

    @pytest.mark.asyncio
    async def test_send_special_characters(self, browser):
        """Should handle special characters in messages."""
        message = "What is 5 * 3? (asterisk test) & also 'quotes'"
        response = await browser.send_message(message)

        assert response is not None
        assert "15" in response

    @pytest.mark.asyncio
    async def test_send_multiline_message(self, browser):
        """Should handle multiline messages."""
        message = "Line 1\nLine 2\nLine 3\nCount these lines."
        response = await browser.send_message(message)

        assert response is not None
        assert "3" in response or "three" in response.lower()


# ============================================================================
# Streaming Response Tests
# ============================================================================

@pytest.mark.integration
class TestStreamingResponses:
    """Test streaming token callbacks."""

    @pytest.mark.asyncio
    async def test_streaming_callback_called(self, browser, response_collector):
        """Streaming callback should be called with tokens."""
        collector = response_collector()
        collector.start()

        response = await browser.send_message(
            "Count from 1 to 5",
            on_token=collector.on_token
        )

        # Should have received multiple tokens
        assert collector.token_count > 0
        # Collected tokens should form the response
        assert len(collector.full_response) > 0

    @pytest.mark.asyncio
    async def test_streaming_time_to_first_token(self, browser, response_collector):
        """Should receive first token within reasonable time."""
        collector = response_collector()
        collector.start()

        await browser.send_message(
            "Say hello",
            on_token=collector.on_token
        )

        # First token should arrive within 30 seconds
        assert collector.time_to_first_token is not None
        assert collector.time_to_first_token < 30.0

    @pytest.mark.asyncio
    async def test_no_callback_still_works(self, browser):
        """Should work without streaming callback."""
        response = await browser.send_message("Say OK")

        assert response is not None
        assert len(response) > 0


# ============================================================================
# New Conversation Tests
# ============================================================================

@pytest.mark.integration
class TestNewConversation:
    """Test starting new conversations."""

    @pytest.mark.asyncio
    async def test_new_conversation_clears_context(self, browser):
        """New conversation should clear previous context."""
        # Set context
        await browser.send_message("Remember: test value is XYZ123")

        # Verify context is set
        response1 = await browser.send_message("What is the test value?")
        assert "XYZ123" in response1

        # Start new conversation
        await browser.new_conversation()

        # Context should be cleared
        response2 = await browser.send_message("What is the test value?")
        # Should not remember XYZ123 from previous conversation
        # (or should indicate it doesn't know)
        assert "XYZ123" not in response2 or "don't" in response2.lower() or "haven't" in response2.lower()


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.integration
class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_send_before_start_raises_error(self, firefox_profile):
        """Should raise error if sending message before start."""
        client = LumoBrowser(firefox_profile=firefox_profile, headless=True)

        with pytest.raises(RuntimeError, match="not started"):
            await client.send_message("test")

    @pytest.mark.asyncio
    async def test_new_conversation_before_start_raises_error(self, firefox_profile):
        """Should raise error if new_conversation called before start."""
        client = LumoBrowser(firefox_profile=firefox_profile, headless=True)

        with pytest.raises(RuntimeError, match="not started"):
            await client.new_conversation()

    @pytest.mark.asyncio
    async def test_double_stop_is_safe(self, firefox_profile):
        """Should handle double stop gracefully."""
        client = LumoBrowser(firefox_profile=firefox_profile, headless=True)
        await client.start()
        await client.stop()
        # Second stop should not raise
        await client.stop()
