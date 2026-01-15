# LUMO-Term

A terminal client for [Proton LUMO+](https://lumo.proton.me) AI assistant, bringing the power of LUMO to your command line.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License MIT](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- **Interactive REPL** - Chat with LUMO+ directly from your terminal
- **Rich TUI** - Full terminal UI with markdown rendering and syntax highlighting
- **Streaming Responses** - See responses as they're generated
- **Session Persistence** - Leverages your existing Firefox login
- **Headless Operation** - Runs invisibly in the background
- **Code Extraction** - Extract and copy code blocks in 15 languages
- **Pipe Support** - Send files and command output to LUMO

## How It Works

LUMO+ uses end-to-end encryption for all messages. Rather than reverse-engineering Proton's encryption protocol, LUMO-Term uses [Selenium](https://www.selenium.dev/) to automate Firefox in native headless mode. This approach:

- Leverages LUMO's built-in encryption seamlessly
- Keeps your credentials secure in Firefox's profile
- Works with any future LUMO updates automatically
- Runs invisibly using Firefox's native headless mode (no visible browser window)

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

# Run the setup script (installs globally)
./setup.sh

# Make sure you're logged into LUMO+ in Firefox first
firefox https://lumo.proton.me

# Run the terminal client
lumo
```

The setup script will:
- Create a Python virtual environment
- Install all dependencies
- Add `lumo` to `~/.local/bin` for global access

### Manual Installation

If you prefer manual setup:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Optional: create symlink for global access
mkdir -p ~/.local/bin
ln -s "$(pwd)/venv/bin/lumo" ~/.local/bin/lumo
```

> **Note**: If using manual installation without the symlink, activate the virtual environment (`source venv/bin/activate`) each time before running `lumo`.

## Current Status

**Functional**: LUMO-Term uses Firefox's native headless mode to run invisibly while maintaining full encryption support through browser automation.

- Headless mode is the default (browser runs invisibly)
- Use `--no-headless` flag for debugging (shows browser window)
- Your Firefox profile provides authentication automatically

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
| `--profile PATH` | Use specific Firefox profile |
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

The `/code` command intelligently extracts code from LUMO responses, even when not wrapped in markdown fences. Supported languages:

| Category | Languages |
|----------|-----------|
| **Scripting** | Python, Bash, PowerShell, Ruby, Batch |
| **Systems** | Rust, Go, C, C++ |
| **Web** | JavaScript, TypeScript |
| **Enterprise** | Java, SQL |
| **Config** | YAML, Dockerfile |

```bash
# Example workflow
lumo "Write a Python function to reverse a string"
# LUMO responds with code...
/code     # Copies the function to clipboard
```

## Requirements

- Python 3.10+
- Firefox browser
- Active Proton account with LUMO+ access
- Clipboard tool (for `/copy` and `/code` commands):
  - **X11**: `xclip` or `xsel`
  - **Wayland**: `wl-clipboard`

## Installation

See [INSTALL.md](INSTALL.md) for detailed installation instructions.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for technical details about how LUMO-Term works.

## Security & Privacy

- **No credential storage** - Your Proton credentials stay in Firefox
- **No data collection** - All processing happens locally
- **E2E encryption preserved** - Messages remain encrypted end-to-end
- **Profile isolation** - Option to use separate Firefox profile

## Limitations

- Requires Firefox with an active LUMO+ session
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
