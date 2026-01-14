"""Rich TUI interface for LUMO-Term using Textual."""

import asyncio
from pathlib import Path
from typing import Optional

from rich.markdown import Markdown
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Input, Static, LoadingIndicator
from textual.message import Message

from .browser import LumoBrowser, create_lumo_client


class ChatMessage(Static):
    """A single chat message display."""

    def __init__(self, content: str, role: str = "user", **kwargs):
        super().__init__(**kwargs)
        self.content = content
        self.role = role

    def compose(self) -> ComposeResult:
        if self.role == "user":
            yield Static(
                Text(f"You: {self.content}", style="bold cyan"),
                classes="user-message"
            )
        else:
            yield Static(
                Text("LUMO:", style="bold magenta"),
                classes="assistant-label"
            )
            yield Static(
                Markdown(self.content),
                classes="assistant-message"
            )


class StreamingMessage(Static):
    """A message that updates as tokens stream in."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._content = ""
        self._label = Static(Text("LUMO:", style="bold magenta"))
        self._text = Static("")

    def compose(self) -> ComposeResult:
        yield self._label
        yield self._text

    def append(self, text: str) -> None:
        """Append text to the message."""
        self._content += text
        self._text.update(self._content)

    def finalize(self) -> None:
        """Convert to markdown when streaming is complete."""
        if self._content:
            self._text.update(Markdown(self._content))

    @property
    def content(self) -> str:
        return self._content


class ChatArea(VerticalScroll):
    """Scrollable chat history area."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._streaming_message: Optional[StreamingMessage] = None

    def add_user_message(self, content: str) -> None:
        """Add a user message to the chat."""
        self.mount(ChatMessage(content, role="user"))
        self.scroll_end(animate=False)

    def start_assistant_message(self) -> StreamingMessage:
        """Start a new streaming assistant message."""
        self._streaming_message = StreamingMessage()
        self.mount(self._streaming_message)
        self.scroll_end(animate=False)
        return self._streaming_message

    def finish_assistant_message(self) -> None:
        """Finalize the current streaming message."""
        if self._streaming_message:
            self._streaming_message.finalize()
            self._streaming_message = None
        self.scroll_end(animate=False)

    def clear_messages(self) -> None:
        """Clear all messages."""
        for child in list(self.children):
            child.remove()


class ChatInput(Input):
    """Custom input for chat messages."""

    class Submitted(Message):
        """Message emitted when user submits input."""
        def __init__(self, value: str):
            super().__init__()
            self.value = value

    def __init__(self, **kwargs):
        super().__init__(
            placeholder="Type your message... (Enter to send, Ctrl+N for new chat)",
            **kwargs
        )

    async def action_submit(self) -> None:
        """Handle submit action."""
        value = self.value.strip()
        if value:
            self.post_message(self.Submitted(value))
            self.value = ""


class LumoApp(App):
    """The main LUMO TUI application."""

    CSS = """
    ChatArea {
        height: 1fr;
        padding: 1;
        background: $surface;
    }

    .user-message {
        color: cyan;
        margin-bottom: 1;
    }

    .assistant-label {
        color: magenta;
        text-style: bold;
    }

    .assistant-message {
        margin-bottom: 1;
        margin-left: 2;
    }

    ChatInput {
        dock: bottom;
        margin: 1;
    }

    #status {
        dock: bottom;
        height: 1;
        background: $primary-background;
        color: $text-muted;
        text-align: center;
    }

    LoadingIndicator {
        dock: bottom;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+n", "new_chat", "New Chat"),
        Binding("ctrl+d", "quit", "Quit"),
        Binding("ctrl+c", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        firefox_profile: Optional[Path] = None,
        headless: bool = True,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.firefox_profile = firefox_profile
        self.headless = headless
        self._client: Optional[LumoBrowser] = None
        self._is_generating = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ChatArea(id="chat")
        yield Static("Connecting...", id="status")
        yield ChatInput(id="input")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize when app mounts."""
        self.initialize_client()

    @work(exclusive=True)
    async def initialize_client(self) -> None:
        """Initialize the browser client in background."""
        status = self.query_one("#status", Static)
        status.update("Starting browser...")

        try:
            self._client = await create_lumo_client(
                firefox_profile=self.firefox_profile,
                headless=self.headless,
            )
            status.update("Connected to LUMO+")
        except Exception as e:
            status.update(f"Error: {e}")
            self.notify(str(e), severity="error", timeout=10)

    @on(ChatInput.Submitted)
    async def handle_input(self, event: ChatInput.Submitted) -> None:
        """Handle user input submission."""
        if self._is_generating:
            self.notify("Please wait for the current response", severity="warning")
            return

        if not self._client:
            self.notify("Not connected yet", severity="warning")
            return

        message = event.value

        # Handle commands
        if message.startswith("/"):
            await self.handle_command(message)
            return

        # Send message
        chat = self.query_one("#chat", ChatArea)
        chat.add_user_message(message)

        self.send_message(message)

    @work(exclusive=True)
    async def send_message(self, message: str) -> None:
        """Send message and stream response."""
        self._is_generating = True
        status = self.query_one("#status", Static)
        status.update("Generating...")

        chat = self.query_one("#chat", ChatArea)
        streaming_msg = chat.start_assistant_message()

        try:
            def on_token(token: str) -> None:
                # Queue the UI update on the main thread
                self.call_from_thread(streaming_msg.append, token)

            response = await self._client.send_message(message, on_token=on_token)

            # If no streaming tokens were received, set the full response
            if not streaming_msg.content and response:
                streaming_msg.append(response)

        except Exception as e:
            streaming_msg.append(f"\n\n*Error: {e}*")
            self.notify(str(e), severity="error")
        finally:
            chat.finish_assistant_message()
            status.update("Ready")
            self._is_generating = False

    async def handle_command(self, command: str) -> None:
        """Handle slash commands."""
        cmd = command.lower().strip()
        status = self.query_one("#status", Static)

        if cmd in ("/new", "/n"):
            if self._client:
                status.update("Starting new conversation...")
                try:
                    await self._client.new_conversation()
                    self.query_one("#chat", ChatArea).clear_messages()
                    status.update("New conversation started")
                except Exception as e:
                    status.update(f"Error: {e}")
        elif cmd in ("/help", "/h", "/?"):
            self.notify(
                "/new - New conversation\n/quit - Exit\n/help - Show help",
                title="Commands",
                timeout=5,
            )
        elif cmd in ("/quit", "/q"):
            await self.action_quit()
        else:
            self.notify(f"Unknown command: {command}", severity="warning")

    async def action_new_chat(self) -> None:
        """Start a new chat."""
        await self.handle_command("/new")

    async def action_cancel(self) -> None:
        """Cancel current generation."""
        if self._is_generating:
            self.notify("Cancellation not yet implemented", severity="warning")

    async def action_quit(self) -> None:
        """Quit the application."""
        if self._client:
            await self._client.stop()
        self.exit()


async def run_tui(
    firefox_profile: Optional[Path] = None,
    headless: bool = True,
) -> int:
    """Run the TUI application.

    Args:
        firefox_profile: Path to Firefox profile.
        headless: Run browser in headless mode.

    Returns:
        Exit code.
    """
    app = LumoApp(firefox_profile=firefox_profile, headless=headless)
    await app.run_async()
    return 0
