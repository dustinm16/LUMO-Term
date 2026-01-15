"""Command-line interface for LUMO-Term."""

import argparse
import asyncio
import glob
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from .browser import LumoBrowser
from .config import load_config


console = Console()

# Track last message/response for retry functionality
_last_message: str | None = None
_last_response: str | None = None


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="lumo",
        description="Terminal client for Proton LUMO+ AI assistant",
        epilog="Examples:\n"
               "  lumo                           # Interactive REPL\n"
               "  lumo -m 'Hello'                # Single message\n"
               "  cat file.py | lumo 'Review'   # Pipe file content\n"
               "  lumo -f src/*.py 'Find bugs'  # Include files\n"
               "  lumo -m 'Write script' -o out.py  # Save to file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show browser window (useful for debugging)",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        help="Firefox profile path (auto-detected if not specified)",
    )
    parser.add_argument(
        "--new",
        action="store_true",
        help="Start a new conversation",
    )
    parser.add_argument(
        "-m", "--message",
        type=str,
        help="Send a single message and exit",
    )
    parser.add_argument(
        "-f", "--file",
        action="append",
        dest="files",
        metavar="FILE",
        help="Include file content in message (supports globs, can use multiple times)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Save response to file",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to output file instead of overwriting",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy response to clipboard",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Launch full TUI interface",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Output plain text (no markdown formatting)",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Message prompt (alternative to -m)",
    )
    return parser.parse_args()


def read_stdin() -> str | None:
    """Read from stdin if data is piped."""
    if sys.stdin.isatty():
        return None
    try:
        return sys.stdin.read()
    except Exception:
        return None


def read_files(file_patterns: list[str]) -> str:
    """Read and concatenate file contents from patterns."""
    contents = []

    for pattern in file_patterns:
        # Expand globs
        matches = glob.glob(pattern, recursive=True)
        if not matches:
            # Try as literal path
            path = Path(pattern)
            if path.exists():
                matches = [pattern]
            else:
                console.print(f"[yellow]Warning: No files match '{pattern}'[/yellow]")
                continue

        for filepath in sorted(matches):
            path = Path(filepath)
            if path.is_file():
                try:
                    content = path.read_text()
                    contents.append(f"--- {filepath} ---\n{content}")
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not read '{filepath}': {e}[/yellow]")

    return "\n\n".join(contents)


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard. Returns True on success."""
    try:
        import subprocess
        # Try xclip first (Linux)
        try:
            proc = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            proc.communicate(text.encode())
            if proc.returncode == 0:
                return True
        except FileNotFoundError:
            pass

        # Try xsel (Linux alternative)
        try:
            proc = subprocess.Popen(
                ["xsel", "--clipboard", "--input"],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            proc.communicate(text.encode())
            if proc.returncode == 0:
                return True
        except FileNotFoundError:
            pass

        # Try wl-copy (Wayland)
        try:
            proc = subprocess.Popen(
                ["wl-copy"],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            proc.communicate(text.encode())
            if proc.returncode == 0:
                return True
        except FileNotFoundError:
            pass

        # Try pbcopy (macOS)
        try:
            proc = subprocess.Popen(
                ["pbcopy"],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            proc.communicate(text.encode())
            if proc.returncode == 0:
                return True
        except FileNotFoundError:
            pass

        return False
    except Exception:
        return False


def build_message(args: argparse.Namespace) -> str | None:
    """Build the complete message from args, stdin, and files."""
    parts = []

    # Add file contents first
    if args.files:
        file_content = read_files(args.files)
        if file_content:
            parts.append(file_content)

    # Add stdin content
    stdin_content = read_stdin()
    if stdin_content:
        parts.append(f"--- stdin ---\n{stdin_content}")

    # Add the prompt/message
    prompt = args.message or args.prompt
    if prompt:
        parts.append(prompt)

    if not parts:
        return None

    return "\n\n".join(parts)


async def run_repl(client: LumoBrowser, args: argparse.Namespace) -> None:
    """Run interactive REPL mode."""
    global _last_message, _last_response

    console.print(Panel(
        "[bold green]LUMO+ Terminal Client[/bold green]\n"
        "[dim]Type your message and press Enter. Use /help for commands.[/dim]",
        title="Welcome",
        border_style="green",
    ))

    while True:
        try:
            # Get user input
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
            if not user_input.strip():
                continue

            # Handle special commands
            cmd = user_input.strip().lower()

            if cmd in ("/new", "/n"):
                await client.new_conversation()
                _last_message = None
                _last_response = None
                console.print("[dim]Started new conversation[/dim]")
                continue

            elif cmd in ("/quit", "/q", "/exit"):
                break

            elif cmd in ("/help", "/h", "/?"):
                console.print(Panel(
                    "[bold]/new[/bold] or [bold]/n[/bold] - Start new conversation\n"
                    "[bold]/retry[/bold] or [bold]/r[/bold] - Resend last message\n"
                    "[bold]/copy[/bold] or [bold]/c[/bold] - Copy last response to clipboard\n"
                    "[bold]/save <file>[/bold] - Save last response to file\n"
                    "[bold]/quit[/bold] or [bold]/q[/bold] - Exit\n"
                    "[bold]/help[/bold] or [bold]/?[/bold] - Show this help",
                    title="Commands",
                    border_style="blue",
                ))
                continue

            elif cmd in ("/retry", "/r"):
                if _last_message:
                    user_input = _last_message
                    console.print(f"[dim]Retrying: {user_input[:50]}{'...' if len(user_input) > 50 else ''}[/dim]")
                else:
                    console.print("[yellow]No previous message to retry[/yellow]")
                    continue

            elif cmd in ("/copy", "/c"):
                if _last_response:
                    if copy_to_clipboard(_last_response):
                        console.print("[dim]Response copied to clipboard[/dim]")
                    else:
                        console.print("[yellow]Could not copy to clipboard (install xclip or xsel)[/yellow]")
                else:
                    console.print("[yellow]No response to copy[/yellow]")
                continue

            elif cmd.startswith("/save "):
                filepath = user_input[6:].strip()
                if _last_response and filepath:
                    try:
                        Path(filepath).write_text(_last_response)
                        console.print(f"[dim]Response saved to {filepath}[/dim]")
                    except Exception as e:
                        console.print(f"[red]Could not save: {e}[/red]")
                elif not _last_response:
                    console.print("[yellow]No response to save[/yellow]")
                else:
                    console.print("[yellow]Usage: /save <filename>[/yellow]")
                continue

            elif cmd.startswith("/"):
                console.print(f"[yellow]Unknown command: {cmd}. Type /help for available commands.[/yellow]")
                continue

            # Store message for retry
            _last_message = user_input

            # Send message and stream response
            console.print("\n[bold magenta]LUMO[/bold magenta]")

            response_parts = []

            def on_token(token: str) -> None:
                response_parts.append(token)
                # Print token immediately for streaming effect
                console.print(token, end="", markup=False)

            response = await client.send_message(user_input, on_token=on_token)
            console.print()  # Newline after streaming

            # Store response for copy/save
            _last_response = response

            # If we didn't get streaming tokens, show the full response
            if not response_parts and response:
                if args.plain:
                    console.print(response)
                else:
                    console.print(Markdown(response))

        except KeyboardInterrupt:
            console.print("\n[dim]Use /quit or Ctrl+D to exit[/dim]")
        except EOFError:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


async def run_single_message(client: LumoBrowser, message: str, args: argparse.Namespace) -> str:
    """Send a single message and return the response."""
    response = await client.send_message(message)

    # Display response
    if args.plain:
        console.print(response)
    else:
        console.print(Markdown(response))

    # Save to file if requested
    if args.output:
        try:
            mode = "a" if args.append else "w"
            with open(args.output, mode) as f:
                f.write(response)
                if args.append:
                    f.write("\n")
            console.print(f"[dim]Response saved to {args.output}[/dim]")
        except Exception as e:
            console.print(f"[red]Could not save to {args.output}: {e}[/red]")

    # Copy to clipboard if requested
    if args.copy:
        if copy_to_clipboard(response):
            console.print("[dim]Response copied to clipboard[/dim]")
        else:
            console.print("[yellow]Could not copy to clipboard (install xclip or xsel)[/yellow]")

    return response


async def async_main() -> int:
    """Async entry point."""
    args = parse_args()
    config = load_config()

    # Use TUI if requested
    if args.tui:
        from .ui import run_tui
        return await run_tui(
            firefox_profile=args.profile,
            headless=not args.no_headless,
        )

    # Build message from args, stdin, and files
    message = build_message(args)

    # If we have a message (from -m, positional arg, stdin, or files), run single message mode
    # Otherwise run REPL
    single_message_mode = message is not None

    # Initialize browser
    console.print("[dim]Starting browser...[/dim]")

    def on_progress(msg: str):
        console.print(f"[dim]  {msg}[/dim]")

    try:
        client = LumoBrowser(
            firefox_profile=args.profile or (Path(config.firefox_profile) if config.firefox_profile else None),
            headless=not args.no_headless,
        )
        await client.start(progress_callback=on_progress)
    except Exception as e:
        console.print(f"[red]Failed to start: {e}[/red]")
        return 1

    try:
        if args.new:
            await client.new_conversation()
            console.print("[dim]Started new conversation[/dim]")

        if single_message_mode:
            await run_single_message(client, message, args)
        else:
            await run_repl(client, args)

        return 0
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
    finally:
        console.print("[dim]Closing browser...[/dim]")
        await client.stop()


def main() -> int:
    """Entry point for the CLI."""
    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted[/dim]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
