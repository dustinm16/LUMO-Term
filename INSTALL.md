# Installation Guide

This guide covers installing LUMO-Term on Linux, macOS, and Windows.

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

# macOS
brew install python3

# Windows
# Download from https://python.org, or: winget install Python.Python.3.12
```

### 2. A Supported Browser

LUMO-Term works with any one of: **Firefox, Chrome, Edge, or Chromium**. Install whichever you already use:

```bash
# Arch Linux
sudo pacman -S firefox            # or: google-chrome (AUR), microsoft-edge-stable-bin (AUR), chromium

# Ubuntu/Debian
sudo apt install firefox          # or: chromium-browser

# Fedora
sudo dnf install firefox          # or: chromium

# macOS
brew install --cask firefox       # or: google-chrome, microsoft-edge, chromium

# Windows
# Firefox/Chrome/Edge installers from their respective sites, or winget
```

You don't need to install a Selenium driver (geckodriver/chromedriver/msedgedriver) yourself —
LUMO-Term prefers a cached or PATH-available driver, and otherwise Selenium's built-in
Selenium Manager downloads and pairs the correct driver version automatically.

### 3. LUMO+ Access

You need an active Proton account with LUMO+ access, logged in to one of the browsers above:

1. Go to [lumo.proton.me](https://lumo.proton.me) in your browser
2. Log in with your Proton account
3. Complete any onboarding steps
4. Verify LUMO+ is working in the browser

## Installation

### Option A: Setup script (Recommended)

```bash
git clone https://github.com/dustinm16/LUMO-Term.git
cd LUMO-Term

./setup.sh          # Linux/macOS
# or
python install.py   # any OS, including Windows
# or
.\setup.ps1          # Windows PowerShell
```

This creates a virtual environment, installs dependencies, reports which supported
browsers were detected (and whether a profile was found for each), and installs a
`lumo` command onto your PATH (`~/.local/bin/lumo`, or `lumo.cmd` on Windows).

### Option B: Manual virtual environment

```bash
git clone https://github.com/dustinm16/LUMO-Term.git
cd LUMO-Term

python3 -m venv venv
source venv/bin/activate       # Linux/macOS
# venv\Scripts\activate        # Windows (Command Prompt)
# venv\Scripts\Activate.ps1    # Windows (PowerShell)

pip install -e .

# Optional: create a global symlink (Linux/macOS)
mkdir -p ~/.local/bin
ln -s "$(pwd)/venv/bin/lumo" ~/.local/bin/lumo
```

> **Important**: Without the symlink/global install, you must activate the virtual
> environment every time you open a new terminal session before using `lumo`:
> ```bash
> cd LUMO-Term
> source venv/bin/activate
> lumo
> ```

### Option C: Install without a virtual environment

```bash
git clone https://github.com/dustinm16/LUMO-Term.git
cd LUMO-Term
pip install --user -e .
```

## First Run Setup

### 1. Log in to LUMO+ in your browser

Before using LUMO-Term, log in normally in whichever browser you'll use:

```bash
firefox https://lumo.proton.me      # or your browser of choice
```

Log in and make sure LUMO+ is working.

### 2. Fully close that browser

LUMO-Term launches its automated instance directly against your browser's real
profile directory — no copying, no cookie extraction. That means the browser must
be **completely closed** (not just minimized) before running `lumo`; both Firefox
and Chromium-based browsers refuse a second process against a profile that's
already open.

### 3. Test the installation

```bash
# Basic test
lumo --help

# Test with visible browser (to verify it's working)
lumo --no-headless -m "Hello, LUMO!"

# Pick a specific browser explicitly if you have more than one installed
lumo --browser edge -m "Hello, LUMO!"
```

### 4. Run normally

Once verified, run in headless mode:

```bash
lumo
```

## Configuration

LUMO-Term stores configuration in `~/.config/lumo-term/config.json`.

### Specify a browser and/or profile

If you have more than one supported browser installed, or multiple profiles,
specify which to use:

```bash
lumo --browser chrome
lumo --browser firefox --profile ~/.mozilla/firefox/abc123.default-release
```

Or set defaults in `~/.config/lumo-term/config.json`:

```json
{
  "browser": "edge",
  "browser_profile": "/home/user/.config/microsoft-edge/Default"
}
```

`browser_profile`'s meaning depends on the browser: a Firefox profile directory
directly, or a Chromium-family (`.../User Data/Default`-style) profile directory.

## Troubleshooting

### "Not logged in to Proton" / landed on a guest session

**Problem**: LUMO-Term can't find (or can't use) an active session.

**Solution**:
1. Open your browser and go to [lumo.proton.me](https://lumo.proton.me)
2. Log in to your Proton account and confirm LUMO+ loads normally
3. A long-unused session can go stale server-side even if the cookie hasn't
   technically expired — if it's been months since you last opened LUMO+ in that
   browser, log out and back in to refresh it
4. Fully close the browser and try LUMO-Term again

### "\<Browser\> is currently open with this profile"

**Problem**: LUMO-Term detected the browser is already running against the profile
it needs to launch against.

**Solution**: Fully quit the browser (all windows) and try again. This is a hard
requirement of the direct-profile-launch approach, not a bug.

### "No \<Browser\> profile found"

**Problem**: The browser is installed, but LUMO-Term couldn't locate a profile
directory for it.

**Solution**: Make sure you've actually opened and logged into that browser at
least once. On Linux, snap/flatpak installs of Firefox and Chromium-family
browsers use different profile paths than native packages — LUMO-Term checks all
of these, but if detection still fails, pass `--profile` explicitly (run
`./setup.sh` again to see the paths it did detect).

### Slow startup

**Problem**: Browser takes a long time to start.

**Solution**: This is normal for the first run while Selenium Manager downloads a
matching driver. Subsequent runs should be faster since the driver gets cached.

### Rate limiting (HTTP 429)

**Problem**: Getting rate limited by Proton.

**Solution**: Wait a few minutes before retrying. LUMO-Term respects rate limits
automatically, but excessive usage may trigger limits.

## Updating

To update LUMO-Term:

```bash
cd LUMO-Term
source venv/bin/activate  # Activate venv first
git pull
pip install -e .
```

## Uninstalling

```bash
# If installed with pip
pip uninstall lumo-term

# Remove configuration
rm -rf ~/.config/lumo-term

# Remove cached driver downloads (optional)
rm -rf ~/.wdm ~/.cache/selenium
```
