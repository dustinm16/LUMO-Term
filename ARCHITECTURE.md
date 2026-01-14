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
│              │   Playwright/Firefox  │                      │
│              │   (Headless Browser)  │                      │
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

### The Solution: Browser as Crypto Provider

Instead of reverse-engineering Proton's encryption:

1. We use **Playwright** to control Firefox
2. Firefox loads LUMO's **web app with all crypto**
3. We interact via **DOM manipulation**
4. The browser handles **all encryption/decryption**

This approach:
- Works without understanding the crypto protocol
- Stays compatible with LUMO updates
- Keeps credentials secure in Firefox's storage

## Module Structure

```
lumo_term/
├── __init__.py      # Package metadata
├── __main__.py      # Entry point for `python -m lumo_term`
├── cli.py           # Command-line interface & REPL
├── ui.py            # Textual TUI application
├── browser.py       # Playwright browser automation
├── auth.py          # Firefox cookie extraction (for future use)
└── config.py        # Configuration management
```

### browser.py - Core Engine

The `LumoBrowser` class manages the headless Firefox instance:

```python
class LumoBrowser:
    async def start(self):
        """Launch Firefox with user's profile"""

    async def send_message(self, message, on_token=None):
        """Send message and stream response"""

    async def new_conversation(self):
        """Start fresh conversation"""
```

Key implementation details:

1. **Profile Reuse**: Uses `launch_persistent_context()` with the user's Firefox profile
2. **DOM Injection**: Injects JavaScript to capture streaming responses
3. **Polling**: Monitors for response completion via DOM changes

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
3. browser.py fills input field via Playwright
           │
           ▼
4. browser.py clicks send / presses Enter
           │
           ▼
5. LUMO web app encrypts message (in browser)
           │
           ▼
6. Encrypted message sent to lumo.proton.me
           │
           ▼
7. Encrypted response streamed back
           │
           ▼
8. LUMO web app decrypts tokens (in browser)
           │
           ▼
9. browser.py captures decrypted text via DOM
           │
           ▼
10. Text streamed to CLI/TUI via on_token callback
```

### Response Capture

The browser module injects JavaScript to capture streaming responses:

```javascript
// Injected observer
const observer = new MutationObserver((mutations) => {
    const responseArea = document.querySelector('.assistant-message');
    if (responseArea) {
        window.__lumoResponse = responseArea.innerText;
    }
});
observer.observe(document.body, { childList: true, subtree: true });
```

Python polls `window.__lumoResponse` and detects completion by:
1. Text stability (no changes for 1.5 seconds)
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

- First run: ~3-5 seconds (Playwright initialization)
- Subsequent: ~1-2 seconds (browser launch)
- Page load: ~2-3 seconds (LUMO app initialization)

### Response Latency

- Additional overhead: ~200-500ms vs native API
- Streaming works, but with slight delay from DOM polling

### Memory Usage

- Headless Firefox: ~200-400MB RAM
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
