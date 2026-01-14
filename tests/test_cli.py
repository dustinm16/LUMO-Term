"""Tests for CLI and REPL functionality."""

import asyncio
import pytest
from io import StringIO
from unittest.mock import Mock, AsyncMock, patch

from lumo_term.cli import parse_args, run_repl, run_single_message


# ============================================================================
# Argument Parsing Tests
# ============================================================================

class TestArgumentParsing:
    """Test CLI argument parsing."""

    def test_default_args(self):
        """Default arguments should have sensible values."""
        with patch("sys.argv", ["lumo"]):
            args = parse_args()

        assert args.no_headless is False
        assert args.profile is None
        assert args.new is False
        assert args.message is None
        assert args.tui is False

    def test_no_headless_flag(self):
        """--no-headless flag should set headless to False."""
        with patch("sys.argv", ["lumo", "--no-headless"]):
            args = parse_args()

        assert args.no_headless is True

    def test_profile_argument(self):
        """--profile should accept a path."""
        with patch("sys.argv", ["lumo", "--profile", "/path/to/profile"]):
            args = parse_args()

        assert str(args.profile) == "/path/to/profile"

    def test_new_flag(self):
        """--new flag should be parsed."""
        with patch("sys.argv", ["lumo", "--new"]):
            args = parse_args()

        assert args.new is True

    def test_message_argument(self):
        """--message should accept a string."""
        with patch("sys.argv", ["lumo", "-m", "Hello, LUMO!"]):
            args = parse_args()

        assert args.message == "Hello, LUMO!"

    def test_tui_flag(self):
        """--tui flag should be parsed."""
        with patch("sys.argv", ["lumo", "--tui"]):
            args = parse_args()

        assert args.tui is True

    def test_combined_args(self):
        """Multiple arguments should work together."""
        with patch("sys.argv", ["lumo", "--no-headless", "--new", "-m", "Test"]):
            args = parse_args()

        assert args.no_headless is True
        assert args.new is True
        assert args.message == "Test"


# ============================================================================
# REPL Command Tests
# ============================================================================

class TestREPLCommands:
    """Test REPL command handling."""

    @pytest.mark.asyncio
    async def test_quit_command(self):
        """REPL should exit on /quit command."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="Response")

        with patch("lumo_term.cli.Prompt.ask", side_effect=["/quit"]):
            with patch("lumo_term.cli.console"):
                await run_repl(mock_client)

        # Should not have sent any messages
        mock_client.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_q_shortcut(self):
        """REPL should exit on /q shortcut."""
        mock_client = AsyncMock()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["/q"]):
            with patch("lumo_term.cli.console"):
                await run_repl(mock_client)

        mock_client.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_command(self):
        """REPL should start new conversation on /new."""
        mock_client = AsyncMock()
        mock_client.new_conversation = AsyncMock()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["/new", "/quit"]):
            with patch("lumo_term.cli.console"):
                await run_repl(mock_client)

        mock_client.new_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_n_shortcut(self):
        """REPL should handle /n shortcut for new conversation."""
        mock_client = AsyncMock()
        mock_client.new_conversation = AsyncMock()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["/n", "/quit"]):
            with patch("lumo_term.cli.console"):
                await run_repl(mock_client)

        mock_client.new_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_help_command(self):
        """REPL should show help on /help."""
        mock_client = AsyncMock()
        console_mock = Mock()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["/help", "/quit"]):
            with patch("lumo_term.cli.console", console_mock):
                await run_repl(mock_client)

        # Should have printed help panel
        assert any("Panel" in str(call) for call in console_mock.print.call_args_list)

    @pytest.mark.asyncio
    async def test_empty_input_ignored(self):
        """REPL should ignore empty input."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="Response")

        with patch("lumo_term.cli.Prompt.ask", side_effect=["", "  ", "/quit"]):
            with patch("lumo_term.cli.console"):
                await run_repl(mock_client)

        mock_client.send_message.assert_not_called()


# ============================================================================
# Single Message Tests
# ============================================================================

class TestSingleMessage:
    """Test single message mode."""

    @pytest.mark.asyncio
    async def test_single_message_sends(self):
        """Single message mode should send and display response."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="Test response")

        with patch("lumo_term.cli.console") as console_mock:
            await run_single_message(mock_client, "Hello")

        mock_client.send_message.assert_called_once_with("Hello")

    @pytest.mark.asyncio
    async def test_single_message_displays_markdown(self):
        """Single message response should be rendered as markdown."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="# Header\n\nBody text")

        with patch("lumo_term.cli.console") as console_mock:
            with patch("lumo_term.cli.Markdown") as markdown_mock:
                await run_single_message(mock_client, "Test")

        # Should have used Markdown for rendering
        markdown_mock.assert_called_once()


# ============================================================================
# Streaming Tests
# ============================================================================

class TestStreaming:
    """Test streaming response handling."""

    @pytest.mark.asyncio
    async def test_streaming_tokens_printed(self):
        """Streaming tokens should be printed as they arrive."""
        mock_client = AsyncMock()
        tokens_received = []

        async def mock_send(message, on_token=None):
            if on_token:
                for token in ["Hello", " ", "World"]:
                    on_token(token)
                    tokens_received.append(token)
            return "Hello World"

        mock_client.send_message = mock_send

        console_prints = []
        console_mock = Mock()
        console_mock.print = Mock(side_effect=lambda *args, **kwargs: console_prints.append(args))

        with patch("lumo_term.cli.Prompt.ask", side_effect=["Test message", "/quit"]):
            with patch("lumo_term.cli.console", console_mock):
                await run_repl(mock_client)

        # Tokens should have been collected
        assert tokens_received == ["Hello", " ", "World"]


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestCLIErrorHandling:
    """Test CLI error handling."""

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_handled(self):
        """KeyboardInterrupt should show help message."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(side_effect=[KeyboardInterrupt, "Response"])

        console_mock = Mock()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["Test", "Test2", "/quit"]):
            with patch("lumo_term.cli.console", console_mock):
                await run_repl(mock_client)

        # Should have printed interrupt message
        assert any("Ctrl+D" in str(call) or "quit" in str(call).lower()
                   for call in console_mock.print.call_args_list)

    @pytest.mark.asyncio
    async def test_general_exception_displayed(self):
        """General exceptions should be displayed."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(side_effect=[Exception("Test error"), "OK"])

        console_mock = Mock()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["Test", "Test2", "/quit"]):
            with patch("lumo_term.cli.console", console_mock):
                await run_repl(mock_client)

        # Should have printed error
        assert any("error" in str(call).lower() for call in console_mock.print.call_args_list)
