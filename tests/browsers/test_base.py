"""Tests for browser-agnostic LUMO+ automation logic in BaseLumoBrowser.

Error-path tests use a minimal concrete subclass since they never actually
start a driver. Lifecycle/messaging tests are real integration tests (marked
`integration`) that exercise whichever browser the `browser` fixture resolves
to (config override, or auto-detected) — they live here rather than per
backend because the behavior under test is the shared base-class logic.
"""

import pytest

from lumo_term.browsers.base import BaseLumoBrowser


class _StubLumoBrowser(BaseLumoBrowser):
    """Minimal concrete subclass for exercising base-class logic without Selenium."""

    BROWSER_NAME = "Stub"

    def _resolve_profile(self):
        return "stub-profile"

    def _is_profile_locked(self, profile) -> bool:
        return False

    def _build_driver(self, profile):
        raise NotImplementedError("not needed for these tests")


# ============================================================================
# Error Handling Tests (no real browser needed)
# ============================================================================

class TestErrorHandling:
    """Test error handling scenarios that don't require a running browser."""

    @pytest.mark.asyncio
    async def test_send_before_start_raises_error(self):
        """Should raise error if sending message before start."""
        client = _StubLumoBrowser()

        with pytest.raises(RuntimeError, match="not started"):
            await client.send_message("test")

    @pytest.mark.asyncio
    async def test_new_conversation_before_start_raises_error(self):
        """Should raise error if new_conversation called before start."""
        client = _StubLumoBrowser()

        with pytest.raises(RuntimeError, match="not started"):
            await client.new_conversation()

    @pytest.mark.asyncio
    async def test_double_stop_is_safe(self):
        """Should handle double stop gracefully even without starting."""
        client = _StubLumoBrowser()
        await client.stop()
        # Second stop should not raise
        await client.stop()

    @pytest.mark.asyncio
    async def test_start_raises_when_profile_locked(self):
        """start() should raise a clear error when the real browser has the profile open."""

        class LockedStub(_StubLumoBrowser):
            def _is_profile_locked(self, profile) -> bool:
                return True

        client = LockedStub()

        with pytest.raises(RuntimeError, match="fully quit"):
            await client.start()


# ============================================================================
# Browser Lifecycle Tests (real browser via the `browser` fixture)
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
    async def test_browser_stops_cleanly(self, browser_name, browser_profile):
        """Browser should stop and clean up resources."""
        from lumo_term.browsers import create_browser_client

        client = create_browser_client(browser=browser_name, profile=browser_profile, headless=True)
        await client.start()

        assert client._driver is not None

        await client.stop()

        assert client._driver is None

    @pytest.mark.asyncio
    async def test_browser_handles_multiple_start_stop_cycles(self, browser_name, browser_profile):
        """Browser should handle multiple start/stop cycles."""
        from lumo_term.browsers import create_browser_client

        for _ in range(2):
            client = create_browser_client(browser=browser_name, profile=browser_profile, headless=True)
            await client.start()
            assert client._driver is not None
            await client.stop()
            assert client._driver is None

    @pytest.mark.asyncio
    async def test_start_progress_callback(self, browser_name, browser_profile):
        """Browser should call progress callback during startup."""
        from lumo_term.browsers import create_browser_client

        client = create_browser_client(browser=browser_name, profile=browser_profile, headless=True)
        progress_messages = []

        def on_progress(msg: str):
            progress_messages.append(msg)

        try:
            await client.start(progress_callback=on_progress)

            assert len(progress_messages) >= 2
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
        assert len(response) > 50
        assert "recursion" in response.lower() or "function" in response.lower()

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

        await browser.send_message("Count from 1 to 5", on_token=collector.on_token)

        assert collector.token_count > 0
        assert len(collector.full_response) > 0

    @pytest.mark.asyncio
    async def test_streaming_time_to_first_token(self, browser, response_collector):
        """Should receive first token within reasonable time."""
        collector = response_collector()
        collector.start()

        await browser.send_message("Say hello", on_token=collector.on_token)

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
        await browser.send_message("Remember: test value is XYZ123")

        response1 = await browser.send_message("What is the test value?")
        assert "XYZ123" in response1

        await browser.new_conversation()

        response2 = await browser.send_message("What is the test value?")
        assert "XYZ123" not in response2 or "don't" in response2.lower() or "haven't" in response2.lower()
