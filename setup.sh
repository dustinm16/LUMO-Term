#!/bin/bash
#
# LUMO-Term Setup Script
# Installs lumo-term and makes it available globally
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/bin"
VENV_DIR="$SCRIPT_DIR/venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "========================================="
echo "  LUMO-Term Setup"
echo "========================================="
echo ""

# Check Python version
info "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
        success "Python $PYTHON_VERSION found"
    else
        error "Python 3.10+ required, found $PYTHON_VERSION"
    fi
else
    error "Python 3 not found. Please install Python 3.10+"
fi

# Check Firefox
info "Checking Firefox..."
if command -v firefox &> /dev/null; then
    success "Firefox found"
else
    warn "Firefox not found. LUMO-Term requires Firefox to be installed."
    echo "  Install with: sudo pacman -S firefox (Arch) or sudo apt install firefox (Debian/Ubuntu)"
fi

# Create virtual environment
info "Setting up virtual environment..."
if [ -d "$VENV_DIR" ]; then
    success "Virtual environment already exists"
else
    python3 -m venv "$VENV_DIR"
    success "Virtual environment created"
fi

# Activate and install
info "Installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q
pip install -e "$SCRIPT_DIR" -q
success "Dependencies installed"

# Create install directory
info "Setting up global command..."
mkdir -p "$INSTALL_DIR"

# Create symlink
if [ -L "$INSTALL_DIR/lumo" ]; then
    rm "$INSTALL_DIR/lumo"
fi
ln -s "$VENV_DIR/bin/lumo" "$INSTALL_DIR/lumo"
success "Symlink created: $INSTALL_DIR/lumo"

# Check if ~/.local/bin is in PATH
if echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin"; then
    success "~/.local/bin is in PATH"
else
    warn "~/.local/bin is not in your PATH"
    echo ""
    echo "  Add it to your shell configuration:"
    echo ""

    # Detect shell and provide appropriate instructions
    CURRENT_SHELL=$(basename "$SHELL")
    case "$CURRENT_SHELL" in
        fish)
            echo "  For fish, run:"
            echo "    fish_add_path ~/.local/bin"
            echo ""
            echo "  Or add to ~/.config/fish/config.fish:"
            echo "    set -gx PATH \$HOME/.local/bin \$PATH"
            ;;
        zsh)
            echo "  Add to ~/.zshrc:"
            echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
            ;;
        bash)
            echo "  Add to ~/.bashrc:"
            echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
            ;;
        *)
            echo "  Add to your shell config:"
            echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
            ;;
    esac
    echo ""
fi

# Verify installation
echo ""
info "Verifying installation..."
if "$INSTALL_DIR/lumo" --help &> /dev/null; then
    success "lumo command is working!"
else
    error "Installation verification failed"
fi

# Final instructions
echo ""
echo "========================================="
echo -e "  ${GREEN}Setup Complete!${NC}"
echo "========================================="
echo ""
echo "  Before first use, log into LUMO+ in Firefox:"
echo "    firefox https://lumo.proton.me"
echo ""
echo "  Then run:"
echo "    lumo                    # Interactive REPL"
echo "    lumo -m 'Hello'         # Single message"
echo "    lumo --help             # See all options"
echo ""
echo "  For visible browser (debugging):"
echo "    lumo --no-headless"
echo ""
