# Architecture

This document explains the technical architecture of LUMO-Term.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        LUMO-Term                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐    ┌─────────┐    ┌─────────────────────────┐  │
│  │  CLI    │    │   TUI   │    │   browsers/ package      │  │
│  │ (cli.py)│    │ (ui.py) │    │  (factory + backends)   │  │
│  └────┬────┘    └────┬────┘    └────────────┬────────────┘  │
│       │              │                      │               │
│       └──────────────┴──────────────────────┘               │
│                          │                                  │
│              ┌───────────▼───────────┐                      │
│              │  Selenium + Firefox / │                      │
│              │  Chrome / Edge /      │                      │
│              │  Chromium (headless)  │                      │
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

1. We use **Selenium** to control the user's real, already-authenticated browser (Firefox, Chrome, Edge, or Chromium)
2. The browser runs in **native headless mode** - invisible to the user
3. The browser loads LUMO's **web app with all crypto**
4. We interact via **DOM manipulation**
5. The browser handles **all encryption/decryption**

This approach:
- Works without understanding the crypto protocol
- Stays compatible with LUMO updates
- Keeps credentials secure in the browser's own storage — nothing is copied out
- Runs invisibly via the browser's native headless mode

### Direct Profile Launch (not a profile copy)

LUMO-Term launches each backend **directly against the browser's real profile
directory** rather than copying cookies/storage into a scratch profile. An
earlier version of this tool copied a curated subset of Firefox's profile files,
which was fragile (easy to miss a file the storage/quota manager needed) and
would have been substantially harder for Chromium, whose cookie values are
encrypted using an OS-keychain-derived key rather than being plainly readable
from disk.

This has one hard consequence: **the target browser must be fully closed**
before `start()` runs — both Firefox and Chromium refuse a second process
against a profile that's already open (`.parentlock` / `SingletonLock`).
`browsers/profiles.py` checks this before launching and raises a clear error
rather than letting Selenium fail obscurely; both checks verify the lock is
actually held by a *live* process rather than trusting file existence alone,
since a crashed prior attempt leaves the same lock file behind without
releasing it.

Chromium-family browsers add one more wrinkle: they hard-refuse to open a
remote-debugging **port** against what they recognize as a default profile
directory ("DevTools remote debugging requires a non-default data directory") —
a deliberate anti-automation guard. `browsers/chromium.py` works around this
the sanctioned way, via `--remote-debugging-pipe` instead of a TCP port, which
isn't subject to that check.

## Module Structure

```
lumo_term/
├── __init__.py         # Package metadata
├── __main__.py         # Entry point for `python -m lumo_term`
├── cli.py              # Command-line interface & REPL
├── ui.py               # Textual TUI application
├── extract.py          # Code extraction & response parsing
├── config.py           # Configuration management
└── browsers/
    ├── __init__.py      # create_browser_client() factory + auto-detection
    ├── base.py          # BaseLumoBrowser: driver-agnostic Selenium logic
    ├── firefox.py        # FirefoxLumoBrowser backend
    ├── chromium.py        # ChromeLumoBrowser / EdgeLumoBrowser / ChromiumLumoBrowser
    └── profiles.py        # OS-aware profile discovery, lock detection, browser detection
```

### browsers/ - Core Engine

`BaseLumoBrowser` (in `base.py`) holds everything that's actually driver-agnostic —
the same Selenium `By.CSS_SELECTOR` calls work identically regardless of which
browser is under the hood:

```python
class BaseLumoBrowser(ABC):
    async def start(self, progress_callback=None):
        """Resolve + lock-check the profile, then launch (backend-specific)"""

    async def send_message(self, message, on_token=None):
        """Send message and stream response"""

    async def new_conversation(self):
        """Start fresh conversation"""

    async def stop(self):
        """Close browser and clean up"""

    # Implemented per backend:
    def _resolve_profile(self): ...
    def _is_profile_locked(self, profile): ...
    def _build_driver(self, profile): ...
```

Each concrete backend (`FirefoxLumoBrowser`, `ChromeLumoBrowser`,
`EdgeLumoBrowser`, `ChromiumLumoBrowser`) only implements those three hooks;
`create_browser_client()` in `browsers/__init__.py` picks the right one from an
explicit `--browser` flag/config value, or auto-detects by checking which
supported browser is installed (`browsers/profiles.py`), in priority order
firefox → chrome → edge → chromium.

Key implementation details:

1. **Native Headless**: Uses each browser's built-in headless flag for invisible operation
2. **No Profile Copying**: Launches directly against the real profile directory (see above)
3. **Driver Resolution**: Prefers a cached driver binary or one on PATH; otherwise lets Selenium's built-in Selenium Manager (4.6+) resolve and download a version-matched driver — this is more reliable across network environments than `webdriver-manager` (previously used), particularly for Edge, whose driver-download host isn't always reachable everywhere Selenium Manager's own endpoint is
4. **DOM Polling**: Monitors response elements for streaming text updates

### cli.py - REPL Interface

Provides the interactive command-line experience:

```python
async def run_repl(client: BaseLumoBrowser):
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

### extract.py - Code Extraction

Intelligent extraction of code from LUMO responses:

```python
def extract_code_blocks(text: str) -> list[CodeBlock]:
    """Extract markdown-fenced code blocks."""

def extract_code_section(text: str) -> str | None:
    """Extract inline code without fences using language detection."""

def _detect_language(line: str) -> str | None:
    """Detect programming language from code patterns."""
```

**Multi-language Support (15 languages):**

The module uses language-specific patterns to detect code:

| Language | Start Patterns |
|----------|----------------|
| Python | `def func(`, `class Foo:`, `import`, decorators |
| Bash | `func() {`, `function name`, shebangs, command pipelines |
| PowerShell | `Get-*`, `Set-*`, `$var =`, `function` |
| Rust | `fn`, `struct`, `impl`, `use` |
| JavaScript | `const`, `let`, `function`, `=>` |
| And 10 more... | See `LANGUAGE_PATTERNS` in source |

**How extraction works:**

1. First tries to find markdown code fences (`` ```lang ... ``` ``)
2. If none found, scans for language-specific start patterns
3. Continues collecting lines while they match continuation patterns
4. Stops when conversational text is detected ("How it works:", etc.)

### config.py - Configuration

Manages user preferences:

```python
class Config(BaseModel):
    browser: str | None = None          # "firefox" | "chrome" | "edge" | "chromium"
    browser_profile: str | None = None  # override profile auto-detection
    theme: str = "dark"
```

Storage location: `~/.config/lumo-term/config.json`

There's no separate session cache — since backends launch directly against the
real browser profile, the browser itself is the source of truth for
authentication state; there's nothing for LUMO-Term to extract or cache.

## Data Flow

### Sending a Message

```
1. User types message in CLI/TUI
           │
           ▼
2. cli.py/ui.py calls client.send_message() (BaseLumoBrowser)
           │
           ▼
3. base.py fills input field via Selenium WebDriver
           │
           ▼
4. base.py clicks send / presses Enter
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
9. base.py captures decrypted text via DOM polling
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

- Credentials **never leave the browser's own profile** — no copying, no cookie extraction
- No passwords or tokens stored by LUMO-Term
- Session state uses the browser's own secure storage

### Profile Isolation

The `--profile` option allows using a separate profile:

```bash
# Create a dedicated Firefox profile
firefox -CreateProfile lumo-dedicated

# Use it with LUMO-Term
lumo --browser firefox --profile ~/.mozilla/firefox/xyz.lumo-dedicated
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

1. **Browser Dependency**: Requires Firefox, Chrome, Edge, or Chromium to be installed
2. **Browser Must Be Closed**: The target browser can't be running when `lumo` starts (direct-profile launch)
3. **DOM Selectors**: May break if LUMO updates its UI structure
4. **No Offline Mode**: Requires active internet connection
5. **Single Session**: One conversation at a time
6. **macOS/Windows Profile Paths**: Implemented from documented OS conventions but primarily tested on Linux

## Contributing

When contributing, please:

1. Keep the browser automation selectors up-to-date
2. Test with both headless and visible modes
3. Maintain backwards compatibility with existing configs
4. Document any new configuration options
