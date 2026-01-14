"""Command-line interface for LUMO-Term."""

import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from .browser import LumoBrowser, create_lumo_client
from .config import load_config


console = Console()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="lumo",
        description="Terminal client for Proton LUMO+ AI assistant",
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
        "--tui",
        action="store_true",
        help="Launch full TUI interface",
    )
    return parser.parse_args()


async def run_repl(client: LumoBrowser) -> None:
    """Run interactive REPL mode."""
    console.print(Panel(
        "[bold green]LUMO+ Terminal Client[/bold green]\n"
        "[dim]Type your message and press Enter. Use Ctrl+D to exit.[/dim]",
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
            if user_input.strip().lower() in ("/new", "/n"):
                await client.new_conversation()
                console.print("[dim]Started new conversation[/dim]")
                continue
            elif user_input.strip().lower() in ("/quit", "/q", "/exit"):
                break
            elif user_input.strip().lower() in ("/help", "/h", "/?"):
                console.print(Panel(
                    "[bold]/new[/bold] or [bold]/n[/bold] - Start new conversation\n"
                    "[bold]/quit[/bold] or [bold]/q[/bold] - Exit\n"
                    "[bold]/help[/bold] or [bold]/?[/bold] - Show this help",
                    title="Commands",
                    border_style="blue",
                ))
                continue

            # Send message and stream response
            console.print("\n[bold magenta]LUMO[/bold magenta]")

            response_parts = []

            def on_token(token: str) -> None:
                response_parts.append(token)
                # Print token immediately for streaming effect
                console.print(token, end="", markup=False)

            response = await client.send_message(user_input, on_token=on_token)
            console.print()  # Newline after streaming

            # If we didn't get streaming tokens, show the full response
            if not response_parts and response:
                console.print(Markdown(response))

        except KeyboardInterrupt:
            console.print("\n[dim]Use /quit or Ctrl+D to exit[/dim]")
        except EOFError:
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


async def run_single_message(client: LumoBrowser, message: str) -> None:
    """Send a single message and print the response."""
    response = await client.send_message(message)
    console.print(Markdown(response))


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

    # Initialize browser
    console.print("[dim]Starting browser...[/dim]")

    try:
        client = await create_lumo_client(
            firefox_profile=args.profile or (Path(config.firefox_profile) if config.firefox_profile else None),
            headless=not args.no_headless,
        )
    except Exception as e:
        console.print(f"[red]Failed to start: {e}[/red]")
        return 1

    try:
        if args.new:
            await client.new_conversation()
            console.print("[dim]Started new conversation[/dim]")

        if args.message:
            await run_single_message(client, args.message)
        else:
            await run_repl(client)

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
