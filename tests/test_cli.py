"""Tests for CLI and REPL functionality."""

import asyncio
import pytest
from io import StringIO
from unittest.mock import Mock, AsyncMock, patch
from argparse import Namespace

from lumo_term.cli import parse_args, run_repl, run_single_message


def make_mock_args(**kwargs):
    """Create mock args with defaults."""
    defaults = {
        "no_headless": False,
        "profile": None,
        "new": False,
        "message": None,
        "files": None,
        "output": None,
        "append": False,
        "copy": False,
        "tui": False,
        "plain": False,
        "prompt": None,
    }
    defaults.update(kwargs)
    return Namespace(**defaults)


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

    def test_file_argument(self):
        """--file should accept file paths."""
        with patch("sys.argv", ["lumo", "-f", "test.py", "-f", "other.py"]):
            args = parse_args()

        assert args.files == ["test.py", "other.py"]

    def test_output_argument(self):
        """--output should accept a path."""
        with patch("sys.argv", ["lumo", "-o", "output.txt", "-m", "Test"]):
            args = parse_args()

        assert str(args.output) == "output.txt"

    def test_copy_flag(self):
        """--copy flag should be parsed."""
        with patch("sys.argv", ["lumo", "--copy", "-m", "Test"]):
            args = parse_args()

        assert args.copy is True

    def test_plain_flag(self):
        """--plain flag should be parsed."""
        with patch("sys.argv", ["lumo", "--plain", "-m", "Test"]):
            args = parse_args()

        assert args.plain is True

    def test_positional_prompt(self):
        """Positional prompt should be parsed."""
        with patch("sys.argv", ["lumo", "Hello world"]):
            args = parse_args()

        assert args.prompt == "Hello world"


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
        mock_args = make_mock_args()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["/quit"]):
            with patch("lumo_term.cli.console"):
                await run_repl(mock_client, mock_args)

        # Should not have sent any messages
        mock_client.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_q_shortcut(self):
        """REPL should exit on /q shortcut."""
        mock_client = AsyncMock()
        mock_args = make_mock_args()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["/q"]):
            with patch("lumo_term.cli.console"):
                await run_repl(mock_client, mock_args)

        mock_client.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_command(self):
        """REPL should start new conversation on /new."""
        mock_client = AsyncMock()
        mock_client.new_conversation = AsyncMock()
        mock_args = make_mock_args()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["/new", "/quit"]):
            with patch("lumo_term.cli.console"):
                await run_repl(mock_client, mock_args)

        mock_client.new_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_n_shortcut(self):
        """REPL should handle /n shortcut for new conversation."""
        mock_client = AsyncMock()
        mock_client.new_conversation = AsyncMock()
        mock_args = make_mock_args()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["/n", "/quit"]):
            with patch("lumo_term.cli.console"):
                await run_repl(mock_client, mock_args)

        mock_client.new_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_help_command(self):
        """REPL should show help on /help."""
        mock_client = AsyncMock()
        console_mock = Mock()
        mock_args = make_mock_args()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["/help", "/quit"]):
            with patch("lumo_term.cli.console", console_mock):
                await run_repl(mock_client, mock_args)

        # Should have printed help panel
        assert any("Panel" in str(call) for call in console_mock.print.call_args_list)

    @pytest.mark.asyncio
    async def test_empty_input_ignored(self):
        """REPL should ignore empty input."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="Response")
        mock_args = make_mock_args()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["", "  ", "/quit"]):
            with patch("lumo_term.cli.console"):
                await run_repl(mock_client, mock_args)

        mock_client.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_command(self):
        """REPL should retry last message on /retry."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="Response")
        mock_args = make_mock_args()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["Hello", "/retry", "/quit"]):
            with patch("lumo_term.cli.console"):
                await run_repl(mock_client, mock_args)

        # Should have sent message twice
        assert mock_client.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_copy_command(self):
        """REPL should copy response on /copy."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="Test response")
        mock_args = make_mock_args()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["Hello", "/copy", "/quit"]):
            with patch("lumo_term.cli.console"):
                with patch("lumo_term.cli.copy_to_clipboard", return_value=True) as mock_copy:
                    await run_repl(mock_client, mock_args)

        mock_copy.assert_called_once_with("Test response")

    @pytest.mark.asyncio
    async def test_unknown_command(self):
        """REPL should warn on unknown commands."""
        mock_client = AsyncMock()
        console_mock = Mock()
        mock_args = make_mock_args()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["/unknown", "/quit"]):
            with patch("lumo_term.cli.console", console_mock):
                await run_repl(mock_client, mock_args)

        # Should have printed warning
        assert any("Unknown command" in str(call) for call in console_mock.print.call_args_list)


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
        mock_args = make_mock_args()

        with patch("lumo_term.cli.console") as console_mock:
            await run_single_message(mock_client, "Hello", mock_args)

        mock_client.send_message.assert_called_once_with("Hello")

    @pytest.mark.asyncio
    async def test_single_message_displays_markdown(self):
        """Single message response should be rendered as markdown."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="# Header\n\nBody text")
        mock_args = make_mock_args()

        with patch("lumo_term.cli.console") as console_mock:
            with patch("lumo_term.cli.Markdown") as markdown_mock:
                await run_single_message(mock_client, "Test", mock_args)

        # Should have used Markdown for rendering
        markdown_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_single_message_plain_mode(self):
        """Single message with --plain should not use markdown."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="Plain text")
        mock_args = make_mock_args(plain=True)

        with patch("lumo_term.cli.console") as console_mock:
            with patch("lumo_term.cli.Markdown") as markdown_mock:
                await run_single_message(mock_client, "Test", mock_args)

        # Should NOT have used Markdown
        markdown_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_message_with_copy(self):
        """Single message with --copy should copy response."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="Response to copy")
        mock_args = make_mock_args(copy=True)

        with patch("lumo_term.cli.console"):
            with patch("lumo_term.cli.copy_to_clipboard", return_value=True) as mock_copy:
                await run_single_message(mock_client, "Test", mock_args)

        mock_copy.assert_called_once_with("Response to copy")


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
        mock_args = make_mock_args()

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
                await run_repl(mock_client, mock_args)

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
        mock_args = make_mock_args()

        console_mock = Mock()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["Test", "Test2", "/quit"]):
            with patch("lumo_term.cli.console", console_mock):
                await run_repl(mock_client, mock_args)

        # Should have printed interrupt message
        assert any("Ctrl+D" in str(call) or "quit" in str(call).lower()
                   for call in console_mock.print.call_args_list)

    @pytest.mark.asyncio
    async def test_general_exception_displayed(self):
        """General exceptions should be displayed."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(side_effect=[Exception("Test error"), "OK"])
        mock_args = make_mock_args()

        console_mock = Mock()

        with patch("lumo_term.cli.Prompt.ask", side_effect=["Test", "Test2", "/quit"]):
            with patch("lumo_term.cli.console", console_mock):
                await run_repl(mock_client, mock_args)

        # Should have printed error
        assert any("error" in str(call).lower() for call in console_mock.print.call_args_list)
