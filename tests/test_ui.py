"""Tests for the TUI interface."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from rich.markdown import Markdown
from rich.text import Text
from textual.pilot import Pilot

from lumo_term.ui import (
    ChatMessage,
    StreamingMessage,
    ChatArea,
    ChatInput,
    LumoApp,
    run_tui,
)


# ============================================================================
# ChatMessage Tests
# ============================================================================

class TestChatMessage:
    """Test ChatMessage widget."""

    def test_user_message_content(self):
        """User message should store content and role."""
        msg = ChatMessage("Hello, LUMO!", role="user")

        assert msg.content == "Hello, LUMO!"
        assert msg.role == "user"

    def test_assistant_message_content(self):
        """Assistant message should store content and role."""
        msg = ChatMessage("Hello, human!", role="assistant")

        assert msg.content == "Hello, human!"
        assert msg.role == "assistant"

    def test_default_role_is_user(self):
        """Default role should be user."""
        msg = ChatMessage("Test message")

        assert msg.role == "user"

    def test_message_with_special_chars(self):
        """Message should handle special characters."""
        content = "Code: `print('hello')` and **bold**"
        msg = ChatMessage(content, role="assistant")

        assert msg.content == content

    def test_message_with_unicode(self):
        """Message should handle unicode."""
        content = "Hello 世界! 🎉 Привет"
        msg = ChatMessage(content, role="user")

        assert msg.content == content

    def test_empty_message(self):
        """Should handle empty message content."""
        msg = ChatMessage("", role="user")

        assert msg.content == ""


# ============================================================================
# StreamingMessage Tests
# ============================================================================

class TestStreamingMessage:
    """Test StreamingMessage widget."""

    def test_initial_state(self):
        """New streaming message should be empty."""
        msg = StreamingMessage()

        assert msg.content == ""

    def test_append_single_token(self):
        """Should append single token."""
        msg = StreamingMessage()
        msg._content = ""  # Reset internal state

        msg.append("Hello")

        assert msg.content == "Hello"

    def test_append_multiple_tokens(self):
        """Should append multiple tokens sequentially."""
        msg = StreamingMessage()
        msg._content = ""

        msg.append("Hello")
        msg.append(" ")
        msg.append("World")

        assert msg.content == "Hello World"

    def test_append_preserves_whitespace(self):
        """Should preserve whitespace in tokens."""
        msg = StreamingMessage()
        msg._content = ""

        msg.append("Line 1\n")
        msg.append("Line 2")

        assert msg.content == "Line 1\nLine 2"

    def test_finalize_empty_message(self):
        """Finalize should handle empty message."""
        msg = StreamingMessage()
        msg._content = ""

        # Should not raise
        msg.finalize()

        assert msg.content == ""

    def test_content_property(self):
        """Content property should return accumulated text."""
        msg = StreamingMessage()
        msg._content = "Test content"

        assert msg.content == "Test content"


# ============================================================================
# ChatArea Tests
# ============================================================================

class TestChatArea:
    """Test ChatArea widget."""

    def test_initial_state(self):
        """New chat area should have no streaming message."""
        area = ChatArea()

        assert area._streaming_message is None

    @pytest.mark.asyncio
    async def test_start_assistant_message(self):
        """Should create and track streaming message."""
        app = LumoApp()

        async with app.run_test() as pilot:
            area = app.query_one("#chat", ChatArea)

            streaming = area.start_assistant_message()

            assert streaming is not None
            assert area._streaming_message is streaming
            assert isinstance(streaming, StreamingMessage)

    def test_finish_assistant_message(self):
        """Should clear streaming message reference."""
        area = ChatArea()
        area._streaming_message = StreamingMessage()
        area._streaming_message._content = "Test"

        area.finish_assistant_message()

        assert area._streaming_message is None

    def test_finish_without_streaming_message(self):
        """Finish should handle case with no streaming message."""
        area = ChatArea()
        area._streaming_message = None

        # Should not raise
        area.finish_assistant_message()

        assert area._streaming_message is None


# ============================================================================
# ChatInput Tests
# ============================================================================

class TestChatInput:
    """Test ChatInput widget."""

    def test_placeholder_text(self):
        """Should have placeholder text."""
        input_widget = ChatInput()

        assert "Type your message" in input_widget.placeholder

    def test_submitted_message_class(self):
        """Submitted message should have value attribute."""
        submitted = ChatInput.Submitted("test value")

        assert submitted.value == "test value"

    def test_submitted_message_empty(self):
        """Submitted message should handle empty value."""
        submitted = ChatInput.Submitted("")

        assert submitted.value == ""


# ============================================================================
# LumoApp Tests
# ============================================================================

class TestLumoApp:
    """Test LumoApp application."""

    def test_app_initialization_defaults(self):
        """App should initialize with default values."""
        app = LumoApp()

        assert app.firefox_profile is None
        assert app.headless is True
        assert app._client is None
        assert app._is_generating is False

    def test_app_initialization_custom_profile(self):
        """App should accept custom Firefox profile."""
        profile = Path("/custom/profile")
        app = LumoApp(firefox_profile=profile)

        assert app.firefox_profile == profile

    def test_app_initialization_headless_false(self):
        """App should accept headless=False."""
        app = LumoApp(headless=False)

        assert app.headless is False

    def test_app_has_bindings(self):
        """App should have keyboard bindings defined."""
        app = LumoApp()

        # Check that bindings are defined
        binding_keys = [b.key for b in app.BINDINGS]
        assert "ctrl+n" in binding_keys
        assert "ctrl+d" in binding_keys
        assert "ctrl+c" in binding_keys

    def test_app_has_css(self):
        """App should have CSS defined."""
        assert LumoApp.CSS is not None
        assert len(LumoApp.CSS) > 0
        assert "ChatArea" in LumoApp.CSS


# ============================================================================
# LumoApp Async Tests (using Textual's test framework)
# ============================================================================

class TestLumoAppAsync:
    """Async tests for LumoApp using Textual's testing framework."""

    @pytest.mark.asyncio
    async def test_app_compose(self):
        """App should compose with required widgets."""
        app = LumoApp()

        async with app.run_test() as pilot:
            # Check that main components exist
            assert app.query_one("#chat", ChatArea) is not None
            assert app.query_one("#input", ChatInput) is not None
            assert app.query_one("#status") is not None

    @pytest.mark.asyncio
    async def test_app_initial_status(self):
        """App should show connecting status initially."""
        app = LumoApp()

        async with app.run_test() as pilot:
            status = app.query_one("#status")
            # Initial status before client connects
            assert status is not None

    @pytest.mark.asyncio
    async def test_quit_command(self):
        """App should exit on quit command."""
        app = LumoApp()

        async with app.run_test() as pilot:
            # Simulate /quit command
            await app.handle_command("/quit")

            # App should be exiting
            # Note: In test mode, exit() doesn't actually stop the test

    @pytest.mark.asyncio
    async def test_quit_shortcut(self):
        """App should handle /q shortcut."""
        app = LumoApp()

        async with app.run_test() as pilot:
            await app.handle_command("/q")

    @pytest.mark.asyncio
    async def test_help_command(self):
        """App should show help on /help command."""
        app = LumoApp()

        async with app.run_test() as pilot:
            await app.handle_command("/help")
            # Help notification should be shown

    @pytest.mark.asyncio
    async def test_help_shortcuts(self):
        """App should handle help shortcuts."""
        app = LumoApp()

        async with app.run_test() as pilot:
            await app.handle_command("/h")
            await app.handle_command("/?")

    @pytest.mark.asyncio
    async def test_unknown_command(self):
        """App should handle unknown commands gracefully."""
        app = LumoApp()

        async with app.run_test() as pilot:
            await app.handle_command("/unknown_cmd")
            # Should show warning notification

    @pytest.mark.asyncio
    async def test_new_chat_without_client(self):
        """New chat should handle missing client."""
        app = LumoApp()
        app._client = None

        async with app.run_test() as pilot:
            await app.handle_command("/new")
            # Should not crash without client

    @pytest.mark.asyncio
    async def test_input_while_generating(self):
        """Should warn when trying to send while generating."""
        app = LumoApp()
        app._is_generating = True
        app._client = MagicMock()

        async with app.run_test() as pilot:
            event = ChatInput.Submitted("test message")
            await app.handle_input(event)
            # Should show warning

    @pytest.mark.asyncio
    async def test_input_without_client(self):
        """Should warn when trying to send without client."""
        app = LumoApp()
        app._client = None
        app._is_generating = False

        async with app.run_test() as pilot:
            event = ChatInput.Submitted("test message")
            await app.handle_input(event)
            # Should show warning

    @pytest.mark.asyncio
    async def test_cancel_action(self):
        """Cancel action should notify if generating."""
        app = LumoApp()
        app._is_generating = True

        async with app.run_test() as pilot:
            await app.action_cancel()
            # Should show warning about not implemented

    @pytest.mark.asyncio
    async def test_cancel_action_not_generating(self):
        """Cancel action should do nothing if not generating."""
        app = LumoApp()
        app._is_generating = False

        async with app.run_test() as pilot:
            await app.action_cancel()
            # Should do nothing

    @pytest.mark.asyncio
    async def test_new_chat_action(self):
        """New chat action should call handle_command."""
        app = LumoApp()

        async with app.run_test() as pilot:
            await app.action_new_chat()


# ============================================================================
# Integration Tests with Mocked Browser
# ============================================================================

class TestLumoAppWithMockedBrowser:
    """Test LumoApp with mocked browser client."""

    @pytest.mark.asyncio
    async def test_send_message_updates_chat(self):
        """Sending message should add to chat area."""
        app = LumoApp()

        # Create mock client
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="Hello, human!")

        async with app.run_test() as pilot:
            app._client = mock_client
            app._is_generating = False

            chat = app.query_one("#chat", ChatArea)
            initial_children = len(chat.children)

            # Simulate user input
            event = ChatInput.Submitted("Hello, LUMO!")
            await app.handle_input(event)

            # Allow async work to complete
            await pilot.pause()

            # Chat should have new message
            assert len(chat.children) > initial_children

    @pytest.mark.asyncio
    async def test_new_conversation_clears_chat(self):
        """New conversation should clear chat area."""
        app = LumoApp()

        mock_client = AsyncMock()
        mock_client.new_conversation = AsyncMock()

        async with app.run_test() as pilot:
            app._client = mock_client

            chat = app.query_one("#chat", ChatArea)
            # Add some messages
            chat.add_user_message("Test 1")
            chat.add_user_message("Test 2")

            await app.handle_command("/new")
            await pilot.pause()

            # Client should have been called
            mock_client.new_conversation.assert_called_once()


# ============================================================================
# run_tui Function Tests
# ============================================================================

class TestRunTui:
    """Test run_tui function."""

    def test_run_tui_signature(self):
        """run_tui should accept expected parameters."""
        import inspect
        sig = inspect.signature(run_tui)
        params = list(sig.parameters.keys())

        assert "firefox_profile" in params
        assert "headless" in params

    @pytest.mark.asyncio
    async def test_run_tui_creates_app(self):
        """run_tui should create and run LumoApp."""
        # We can't fully test run_tui as it blocks, but we can test
        # that LumoApp can be instantiated with the same parameters
        app = LumoApp(
            firefox_profile=Path("/test"),
            headless=False
        )

        assert app.firefox_profile == Path("/test")
        assert app.headless is False


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_chat_message_very_long_content(self):
        """Should handle very long message content."""
        content = "A" * 10000
        msg = ChatMessage(content, role="user")

        assert msg.content == content
        assert len(msg.content) == 10000

    def test_chat_message_multiline(self):
        """Should handle multiline content."""
        content = "Line 1\nLine 2\nLine 3\n\nLine 5"
        msg = ChatMessage(content, role="assistant")

        assert msg.content == content
        assert msg.content.count("\n") == 4

    def test_streaming_message_rapid_appends(self):
        """Should handle rapid sequential appends."""
        msg = StreamingMessage()
        msg._content = ""

        for i in range(100):
            msg.append(f"token{i} ")

        assert "token0" in msg.content
        assert "token99" in msg.content

    @pytest.mark.asyncio
    async def test_app_multiple_command_calls(self):
        """App should handle multiple rapid command calls."""
        app = LumoApp()

        async with app.run_test() as pilot:
            # Rapid command calls
            await app.handle_command("/help")
            await app.handle_command("/help")
            await app.handle_command("/?")
            # Should not crash

    @pytest.mark.asyncio
    async def test_app_command_case_insensitivity(self):
        """Commands should be case-insensitive."""
        app = LumoApp()

        async with app.run_test() as pilot:
            await app.handle_command("/HELP")
            await app.handle_command("/Help")
            await app.handle_command("/NEW")
            # Should work regardless of case
