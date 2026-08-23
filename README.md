# LUMO-Term

A terminal client for [Proton LUMO+](https://lumo.proton.me) AI assistant, bringing the power of LUMO to your command line.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License MIT](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- **Interactive REPL** - Chat with LUMO+ directly from your terminal
- **Rich TUI** - Full terminal UI with markdown rendering and syntax highlighting
- **Streaming Responses** - See responses as they're generated
- **Multi-Browser Support** - Works with Firefox, Chrome, Edge, or Chromium
- **Cross-Platform** - Linux, macOS, and Windows (any OS with Python 3.10+)
- **Session Persistence** - Leverages your existing browser login, whichever browser that is
- **Headless Operation** - Runs invisibly in the background
- **Code Extraction** - Extract and copy code blocks in 15 languages
- **Pipe Support** - Send files and command output to LUMO

## How It Works

LUMO+ uses end-to-end encryption for all messages. Rather than reverse-engineering Proton's encryption protocol, LUMO-Term uses [Selenium](https://www.selenium.dev/) to automate your real, already-logged-in browser profile in native headless mode — Firefox, Chrome, Edge, or Chromium. This approach:

- Leverages LUMO's built-in encryption seamlessly
- Keeps your credentials secure in your browser's own profile — nothing is copied or extracted
- Works with any future LUMO updates automatically
- Runs invisibly using the browser's native headless mode (no visible window)

> **Note:** Because LUMO-Term launches your browser directly against its real profile
> directory (rather than a copy), **the target browser must be fully closed** before
> running `lumo` — Firefox and Chromium-based browsers both refuse a second process
> against a profile that's already open.

### Why Browser Automation?

**LUMO has no public API.** Proton's "zero-access" architecture means:

- All messages are encrypted client-side before transmission
- Encryption keys are stored in browser IndexedDB
- The server never sees plaintext (by design)
- No API tokens can bypass this encryption

Browser automation is the **only way** to interact with LUMO programmatically while preserving E2E encryption. The browser handles all cryptographic operations transparently.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/dustinm16/LUMO-Term.git
cd LUMO-Term

# Run the setup script (installs globally) — Linux/macOS
./setup.sh
# Windows: python install.py   (or setup.ps1)

# Make sure you're logged into LUMO+ in a supported browser first,
# then close that browser completely
lumo
```

The setup script (`install.py`, wrapped by `setup.sh`/`setup.ps1`) will:
- Create a Python virtual environment
- Install all dependencies
- Detect which supported browsers (Firefox/Chrome/Edge/Chromium) are installed and report whether a usable profile was found for each
- Add `lumo` to `~/.local/bin` for global access (or a `lumo.cmd` shim on Windows)

### Manual Installation

If you prefer manual setup:

```bash
python3 -m venv venv
source venv/bin/activate      # venv\Scripts\activate on Windows
pip install -e .

# Optional: create symlink for global access (Linux/macOS)
mkdir -p ~/.local/bin
ln -s "$(pwd)/venv/bin/lumo" ~/.local/bin/lumo
```

> **Note**: If using manual installation without the symlink, activate the virtual environment (`source venv/bin/activate`) each time before running `lumo`.

## Current Status

**Functional**: LUMO-Term launches Firefox, Chrome, Edge, or Chromium in native headless mode directly against your real, already-authenticated profile.

- Headless mode is the default (browser runs invisibly)
- Use `--no-headless` flag for debugging (shows browser window)
- Use `--browser {firefox,chrome,edge,chromium}` to pick a specific browser (auto-detected otherwise)
- Your browser profile provides authentication automatically — **the browser must be closed** before `lumo` runs

## Usage

### REPL Mode (Default)

```bash
lumo
```

Interactive chat session with LUMO+. Type your message and press Enter.

### Single Message

```bash
lumo -m "Explain quantum computing in simple terms"
# Or use positional argument
lumo "Explain quantum computing in simple terms"
```

Send a single message and get the response.

### Pipe Input

```bash
# Pipe file content
cat script.py | lumo "Review this code"

# Pipe command output
git diff | lumo "Summarize these changes"

# Redirect file
lumo "Explain this error" < error.log
```

### File Context

```bash
# Include single file
lumo -f main.py "Add error handling"

# Include multiple files
lumo -f src/*.py "Find bugs in these files"

# Multiple -f flags
lumo -f config.py -f utils.py "How do these interact?"
```

### Output Options

```bash
# Save response to file
lumo -m "Write a Python script for X" -o script.py

# Append to file
lumo -m "Add more features" -o script.py --append

# Copy response to clipboard
lumo -m "Generate a command" --copy

# Plain text output (no markdown formatting)
lumo -m "List items" --plain

# Extract code only (strips "Here's the code:" etc.)
lumo -m "Write a factorial function" --code-only -o factorial.py

# Prefer specific language when extracting
lumo -m "Write a script" --code-only --language python -o script.py
```

### Full TUI

```bash
lumo --tui
```

Launch the full terminal user interface with markdown rendering.

### Debug Mode

```bash
lumo --no-headless
```

Show the browser window for debugging.

### CLI Options

| Option | Description |
|--------|-------------|
| `-m, --message TEXT` | Send single message and exit |
| `-f, --file FILE` | Include file content (supports globs, repeatable) |
| `-o, --output PATH` | Save response to file |
| `--append` | Append to output file instead of overwriting |
| `--copy` | Copy response to clipboard |
| `--plain` | Output plain text (no markdown) |
| `--code-only` | Extract only code, strip conversational text |
| `--language LANG` | Preferred language for code extraction |
| `--tui` | Launch full TUI interface |
| `--no-headless` | Show browser window |
| `--browser {firefox,chrome,edge,chromium}` | Browser to automate (auto-detected if not specified) |
| `--profile PATH` | Use specific browser profile |
| `--new` | Start a new conversation |

### REPL Commands

| Command | Description |
|---------|-------------|
| `/new` or `/n` | Start new conversation |
| `/retry` or `/r` | Resend last message |
| `/copy` or `/c` | Copy last response to clipboard |
| `/code` or `/k` | Copy last code block to clipboard |
| `/code <n>` | Copy nth code block (if multiple) |
| `/save <file>` | Save last response to file |
| `/quit` or `/q` | Exit |
| `/help` or `/?` | Show help |

### Code Extraction

The `/code` command intelligently extracts code from LUMO responses, even when not wrapped in markdown fences. It detects code by recognizing language-specific patterns like function definitions, imports, and common commands.

**Supported Languages (15):**

| Category | Languages |
|----------|-----------|
| **Scripting** | Python, Bash, PowerShell, Ruby, Batch |
| **Systems** | Rust, Go, C, C++ |
| **Web** | JavaScript, TypeScript |
| **Enterprise** | Java, SQL |
| **Config** | YAML, Dockerfile |

**What it detects:**
- Function/class definitions (`def`, `fn`, `func`, `function`)
- Shell commands with pipes (`ls | grep | awk`)
- PowerShell cmdlets (`Get-Process`, `Set-Item`)
- Import statements, shebangs, and more

```bash
# Example workflow
lumo
> Write a bash one-liner to find large files
# LUMO responds: "find . -type f -exec du -h {} + | sort -rh | head"
> /code
# Code copied to clipboard!

# Or extract specific block when multiple exist
> /code 2    # Copies the second code block
```

## Requirements

- Python 3.10+ (Linux, macOS, or Windows)
- One of: Firefox, Chrome, Edge, or Chromium
- Active Proton account with LUMO+ access, logged in to that browser
- Clipboard tool (for `/copy` and `/code` commands, Linux only — macOS/Windows use the system clipboard):
  - **X11**: `xclip` or `xsel`
  - **Wayland**: `wl-clipboard`

## Installation

See [INSTALL.md](INSTALL.md) for detailed installation instructions.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for technical details about how LUMO-Term works.

## Security & Privacy

- **No credential storage** - Your Proton credentials stay in your browser's own profile
- **No data collection** - All processing happens locally
- **E2E encryption preserved** - Messages remain encrypted end-to-end
- **No profile copying** - LUMO-Term launches directly against your real profile rather than extracting or duplicating cookies/session data

## Limitations

- Requires a supported browser (Firefox/Chrome/Edge/Chromium) with an active LUMO+ session
- **The target browser must be fully closed** before running `lumo` — it launches its own instance directly against your real profile, which the browser won't allow while it's already open
- Browser automation adds some overhead vs native API
- Rate limits apply as per Proton's terms of service
- Web Search toggle must be enabled manually in LUMO UI for internet queries
- Some UI features (model selection, toggles) not controllable via CLI

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## Disclaimer

This is an unofficial, personal project and is not affiliated with Proton AG. Use responsibly and in accordance with [Proton's Terms of Service](https://proton.me/legal/terms).

## License

MIT License - see [LICENSE](LICENSE) for details.
