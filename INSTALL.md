# Installation Guide

This guide covers installing LUMO-Term on Linux systems.

## Prerequisites

### 1. Python 3.10+

Check your Python version:

```bash
python3 --version
```

If you need to install Python:

```bash
# Arch Linux
sudo pacman -S python

# Ubuntu/Debian
sudo apt install python3 python3-pip python3-venv

# Fedora
sudo dnf install python3 python3-pip
```

### 2. Firefox Browser

LUMO-Term requires Firefox to be installed:

```bash
# Arch Linux
sudo pacman -S firefox

# Ubuntu/Debian
sudo apt install firefox

# Fedora
sudo dnf install firefox
```

### 3. LUMO+ Access

You need an active Proton account with LUMO+ access:

1. Go to [lumo.proton.me](https://lumo.proton.me)
2. Log in with your Proton account
3. Complete any onboarding steps
4. Verify LUMO+ is working in the browser

## Installation

### Option A: Install with pip (Recommended)

```bash
# Clone the repository
git clone https://github.com/dustinm16/LUMO-Term.git
cd LUMO-Term

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install the package
pip install -e .

# Install Playwright and Firefox browser
pip install playwright
playwright install firefox
```

### Option B: Install without virtual environment

```bash
# Clone the repository
git clone https://github.com/dustinm16/LUMO-Term.git
cd LUMO-Term

# Install with pip
pip install --user -e .

# Install Playwright
pip install --user playwright
playwright install firefox
```

### Option C: Run directly without installing

```bash
# Clone the repository
git clone https://github.com/dustinm16/LUMO-Term.git
cd LUMO-Term

# Install dependencies
pip install playwright textual rich pydantic
playwright install firefox

# Run directly
python -m lumo_term
```

## First Run Setup

### 1. Log in to LUMO+ in Firefox

Before using LUMO-Term, you must have an active session:

```bash
firefox https://lumo.proton.me
```

Log in and make sure LUMO+ is working.

### 2. Test the Installation

```bash
# Basic test
lumo --help

# Test with visible browser (to verify it's working)
lumo --no-headless -m "Hello, LUMO!"
```

### 3. Run Normally

Once verified, run in headless mode:

```bash
lumo
```

## Configuration

LUMO-Term stores configuration in `~/.config/lumo-term/`:

- `config.json` - User preferences
- `session.json` - Cached session data

### Specify Firefox Profile

If you have multiple Firefox profiles, specify which one to use:

```bash
# Find your profiles
ls ~/.mozilla/firefox/

# Use a specific profile
lumo --profile ~/.mozilla/firefox/abc123.default-release
```

Or set it in `~/.config/lumo-term/config.json`:

```json
{
  "firefox_profile": "/home/user/.mozilla/firefox/abc123.default-release"
}
```

## Troubleshooting

### "Not logged in to Proton"

**Problem**: LUMO-Term can't find an active session.

**Solution**:
1. Open Firefox and go to [lumo.proton.me](https://lumo.proton.me)
2. Log in to your Proton account
3. Make sure LUMO+ loads successfully
4. Try LUMO-Term again

### "Firefox not found"

**Problem**: No Firefox installation detected.

**Solution**:
```bash
# Install Firefox
sudo pacman -S firefox  # Arch
sudo apt install firefox  # Ubuntu/Debian
```

### "Playwright browser not installed"

**Problem**: Playwright's Firefox binary is missing.

**Solution**:
```bash
playwright install firefox
```

### Slow startup

**Problem**: Browser takes a long time to start.

**Solution**: This is normal for the first run as Playwright initializes. Subsequent runs should be faster. You can also try:

```bash
# Pre-warm the browser
lumo --no-headless &
# Then use normally
```

### Rate limiting (HTTP 429)

**Problem**: Getting rate limited by Proton.

**Solution**: Wait a few minutes before retrying. LUMO-Term respects rate limits automatically, but excessive usage may trigger limits.

## Updating

To update LUMO-Term:

```bash
cd LUMO-Term
git pull
pip install -e .
```

## Uninstalling

```bash
# If installed with pip
pip uninstall lumo-term

# Remove configuration
rm -rf ~/.config/lumo-term

# Remove Playwright browsers (optional)
playwright uninstall firefox
```
