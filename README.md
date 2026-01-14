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

## How It Works

LUMO+ uses end-to-end encryption for all messages. Rather than reverse-engineering Proton's encryption protocol, LUMO-Term uses [Playwright](https://playwright.dev/) to automate a headless Firefox browser with your existing profile. This approach:

- Leverages LUMO's built-in encryption seamlessly
- Keeps your credentials secure in Firefox's profile
- Works with any future LUMO updates automatically

## Quick Start

```bash
# Install dependencies
pip install playwright
playwright install firefox

# Install lumo-term
pip install -e .

# Make sure you're logged into LUMO+ in Firefox first
firefox https://lumo.proton.me

# Run the terminal client
lumo
```

## Usage

### REPL Mode (Default)

```bash
lumo
```

Interactive chat session with LUMO+. Type your message and press Enter.

### Single Message

```bash
lumo -m "Explain quantum computing in simple terms"
```

Send a single message and get the response.

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
| `--tui` | Launch full TUI interface |
| `--no-headless` | Show browser window |
| `--profile PATH` | Use specific Firefox profile |
| `--new` | Start a new conversation |
| `-m, --message TEXT` | Send single message and exit |

### REPL Commands

| Command | Description |
|---------|-------------|
| `/new` or `/n` | Start new conversation |
| `/quit` or `/q` | Exit |
| `/help` or `/?` | Show help |

## Requirements

- Python 3.10+
- Firefox browser
- Active Proton account with LUMO+ access

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

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## Disclaimer

This is an unofficial, personal project and is not affiliated with Proton AG. Use responsibly and in accordance with [Proton's Terms of Service](https://proton.me/legal/terms).

## License

MIT License - see [LICENSE](LICENSE) for details.
