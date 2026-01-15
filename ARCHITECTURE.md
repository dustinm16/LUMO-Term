# Architecture

This document explains the technical architecture of LUMO-Term.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        LUMO-Term                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐    ┌─────────┐    ┌─────────────────────────┐  │
│  │  CLI    │    │   TUI   │    │      Browser Module     │  │
│  │ (cli.py)│    │ (ui.py) │    │      (browser.py)       │  │
│  └────┬────┘    └────┬────┘    └────────────┬────────────┘  │
│       │              │                      │               │
│       └──────────────┴──────────────────────┘               │
│                          │                                  │
│              ┌───────────▼───────────┐                      │
│              │   Selenium + Firefox  │                      │
│              │   (Native Headless)   │                      │
│              └───────────┬───────────┘                      │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │    lumo.proton.me       │
              │   (E2E Encrypted API)   │
              └─────────────────────────┘
```

## Why Browser Automation?

### The Encryption Challenge

LUMO+ uses end-to-end encryption for all messages:

```
Request:
{
  "content": "c0UC9JqKEO5+29CmVJpw...",  // Encrypted
  "encrypted": true,
  "request_key": "wV4D598Sio/F3gQS..."    // Key exchange
}

Response:
{"type":"token_data","content":"eVaHcJ7FqaTQ+MBZ...", "encrypted":true}
```

Each message is encrypted client-side before being sent, and responses are encrypted per-token. The encryption uses:

- **Ephemeral key exchange** via `request_key`
- **Per-token symmetric encryption** (likely AES-GCM)
- **Proton's pmcrypto library** built on OpenPGP.js

### No Public API Exists

LUMO does **not** have a public REST API. Proton's "zero-access" architecture means:

- `api.lumo.proton.me` - Does not exist
- `lumo.proton.me/api/` - Returns 404
- No bearer token authentication available
- No OpenAI-compatible endpoints

This is by design. A public API would require either:
1. Transmitting encryption keys (defeats E2E encryption)
2. Server-side decryption (violates zero-access promise)

Browser automation is the only viable approach for programmatic access.

### The Solution: Browser as Crypto Provider

Instead of reverse-engineering Proton's encryption:

1. We use **Selenium** to control Firefox
2. Firefox runs in **native headless mode** - invisible to the user
3. Firefox loads LUMO's **web app with all crypto**
4. We interact via **DOM manipulation**
5. The browser handles **all encryption/decryption**

This approach:
- Works without understanding the crypto protocol
- Stays compatible with LUMO updates
- Keeps credentials secure in Firefox's storage
- Runs invisibly via Firefox's native headless mode

## Module Structure

```
lumo_term/
├── __init__.py      # Package metadata
├── __main__.py      # Entry point for `python -m lumo_term`
├── cli.py           # Command-line interface & REPL
├── ui.py            # Textual TUI application
├── browser.py       # Selenium browser automation
├── auth.py          # Firefox cookie extraction (for future use)
└── config.py        # Configuration management
```

### browser.py - Core Engine

The `LumoBrowser` class manages Firefox via Selenium in headless mode:

```python
class LumoBrowser:
    async def start(self, progress_callback=None):
        """Launch Firefox in headless mode with user's profile"""

    async def send_message(self, message, on_token=None):
        """Send message and stream response"""

    async def new_conversation(self):
        """Start fresh conversation"""

    async def stop(self):
        """Close browser and clean up"""
```

Key implementation details:

1. **Native Headless**: Uses Firefox's built-in `-headless` flag for invisible operation
2. **Profile Copying**: Copies essential Firefox profile files (cookies, Proton storage) to temp directory
3. **GeckoDriver**: Uses webdriver-manager to auto-download appropriate geckodriver
4. **DOM Polling**: Monitors response elements for streaming text updates

### cli.py - REPL Interface

Provides the interactive command-line experience:

```python
async def run_repl(client: LumoBrowser):
    while True:
        user_input = Prompt.ask("You")
        response = await client.send_message(user_input, on_token=on_token)
```

Features:
- Rich console output with markdown rendering
- Streaming token display
- Slash commands (`/new`, `/quit`, `/help`)

### ui.py - TUI Interface

Full terminal UI built with Textual:

```python
class LumoApp(App):
    async def send_message(self, message: str):
        """Send message and update UI with streaming response"""
```

Components:
- `ChatArea` - Scrollable message history
- `StreamingMessage` - Live-updating response display
- `ChatInput` - Input field with command handling

### auth.py - Cookie Extraction

Extracts authentication cookies from Firefox for potential future use:

```python
def get_auth_session(force_refresh=False):
    """Extract Proton cookies from Firefox profile"""
```

Currently used for:
- Detecting available Firefox profiles
- Validating user is logged in
- Future: Direct API access if encryption is solved

### config.py - Configuration

Manages user preferences and session state:

```python
class Config(BaseModel):
    firefox_profile: str | None = None
    theme: str = "dark"

class Session(BaseModel):
    uid: str | None = None
    cookies: dict[str, str] = {}
```

Storage locations:
- `~/.config/lumo-term/config.json`
- `~/.config/lumo-term/session.json`

## Data Flow

### Sending a Message

```
1. User types message in CLI/TUI
           │
           ▼
2. cli.py/ui.py calls browser.send_message()
           │
           ▼
3. browser.py fills input field via Selenium WebDriver
           │
           ▼
4. browser.py clicks send / presses Enter
           │
           ▼
5. LUMO web app encrypts message (in headless browser)
           │
           ▼
6. Encrypted message sent to lumo.proton.me
           │
           ▼
7. Encrypted response streamed back
           │
           ▼
8. LUMO web app decrypts tokens (in headless browser)
           │
           ▼
9. browser.py captures decrypted text via DOM polling
           │
           ▼
10. Text streamed to CLI/TUI via on_token callback
```

### Response Capture

The browser module uses Selenium to poll DOM elements for streaming responses:

```python
def _get_latest_response(self) -> str:
    """Get the latest assistant response text via CSS selectors."""
    selectors = [
        '[data-testid="message-content"]',
        '.message-content',
        '.assistant-message',
        '[data-role="assistant"]',
    ]
    for selector in selectors:
        elements = self._driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            return elements[-1].text  # Get most recent message
    return ""
```

Python detects response completion by:
1. Text stability (no changes for ~2 seconds)
2. Absence of "Stop generating" button

## Security Considerations

### Credential Handling

- Credentials **never leave Firefox's profile**
- No passwords or tokens stored by LUMO-Term
- Session state uses Firefox's secure storage

### Profile Isolation

The `--profile` option allows using a separate Firefox profile:

```bash
# Create dedicated profile
firefox -CreateProfile lumo-dedicated

# Use it with LUMO-Term
lumo --profile ~/.mozilla/firefox/xyz.lumo-dedicated
```

### Data Privacy

- All messages encrypted E2E (by LUMO web app)
- No logging of message content
- Config files contain only preferences, not messages

## Performance

### Startup Time

- First run: ~5-10 seconds (geckodriver download + Firefox init)
- Subsequent: ~3-5 seconds (browser launch in headless mode)
- Page load: ~2-3 seconds (LUMO app initialization)

### Response Latency

- Additional overhead: ~200-500ms vs native API
- Streaming works, with polling interval of ~300ms

### Memory Usage

- Firefox (headless): ~200-400MB RAM
- Python process: ~50-100MB RAM

## Future Improvements

### Potential Enhancements

1. **Direct API Access**: If we can extract encryption keys from IndexedDB, implement native crypto
2. **Response Caching**: Cache conversation history locally
3. **Multiple Conversations**: Tab management for parallel chats
4. **Keyboard Shortcuts**: More extensive keybindings in TUI
5. **Theming**: Customizable colors and styles

### Known Limitations

1. **Browser Dependency**: Requires Firefox to be installed
2. **DOM Selectors**: May break if LUMO updates its UI structure
3. **No Offline Mode**: Requires active internet connection
4. **Single Session**: One conversation at a time

## Contributing

When contributing, please:

1. Keep the browser automation selectors up-to-date
2. Test with both headless and visible modes
3. Maintain backwards compatibility with existing configs
4. Document any new configuration options
