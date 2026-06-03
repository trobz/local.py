#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export PATH="$HOME/.local/bin:$PATH"

# Bootstrap script for trobz_local (tlc)
# Installs prerequisites: git, gh, uv, and trobz_local CLI
# Note: Tool installation (Odoo, PostgreSQL, etc.) is done separately via `tlc install-tools`

echo "=== Bootstrap trobz_local ==="

# Check not running as root
if [ "$(id -u)" -eq 0 ]; then
    echo "Error: Do not run this script as root."
    echo "Please run as a regular user with sudo access."
    exit 1
fi

# Check if user can sudo
check_sudo() {
    if ! sudo -v &>/dev/null; then
        echo "Error: This script requires sudo privileges."
        echo "Please run as a user with sudo access."
        exit 1
    fi
}

check_sudo

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/debian_version ]; then
            echo "debian"
        elif [ -f /etc/fedora-release ]; then
            echo "fedora"
        elif [ -f /etc/arch-release ]; then
            echo "arch"
        else
            echo "linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

OS=$(detect_os)
echo "Detected OS: $OS"

# Install git
install_git() {
    if command -v git &>/dev/null; then
        echo "git is already installed"
        return
    fi
    echo "Installing git..."
    case $OS in
        debian) sudo apt-get update && sudo apt-get install -y git ;;
        fedora) sudo dnf install -y git ;;
        arch) sudo pacman -S --noconfirm git ;;
        macos) brew install git ;;
        *) echo "Please install git manually"; exit 1 ;;
    esac
}

# Install gh (GitHub CLI)
install_gh() {
    if command -v gh &>/dev/null; then
        echo "gh is already installed"
        return
    fi
    echo "Installing gh (GitHub CLI)..."
    case $OS in
        debian)
            sudo mkdir -p -m 755 /etc/apt/keyrings
            curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
            sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
            sudo apt-get update && sudo apt-get install -y gh
            ;;
        fedora) sudo dnf install -y gh ;;
        arch) sudo pacman -S --noconfirm github-cli ;;
        macos) brew install gh ;;
        *) echo "Please install gh manually from https://cli.github.com/"; exit 1 ;;
    esac
}

# Install uv
install_uv() {
    if command -v uv &>/dev/null; then
        echo "uv is already installed"
        return
    fi
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
}

# Setup SSH known_hosts for GitHub
setup_github_ssh() {
    echo "Setting up SSH known_hosts for GitHub..."
    mkdir -p ~/.ssh
    chmod 700 ~/.ssh
    ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null
    echo "GitHub added to known_hosts"
}

# Install trobz_local
install_trobz_local() {
    echo "Installing trobz_local..."
    uv tool install git+https://github.com/trobz/local.py.git
    echo "trobz_local installed (CLI: tlc)"
}

# Install vercel-labs/skills (Claude Code skills)
install_vercel_skills() {
    if ! command -v nvm &>/dev/null; then
        echo "Installing nvm..."
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash
    fi
    if ! command -v npx &>/dev/null; then
        echo "Installing node and related commands..."
        . ~/.nvm/nvm.sh && nvm install --lts
    fi
    echo "Installing vercel-labs/skills..."
    npx -y skills > /dev/null
    echo "vercel-labs/skills installed"
}

# Main execution
install_git
install_gh
install_uv
setup_github_ssh
install_trobz_local
install_vercel_skills

echo ""
echo "=== Bootstrap complete ==="
echo ""
echo "Prerequisites installed successfully!"
echo "  ✓ git"
echo "  ✓ gh (GitHub CLI)"
echo "  ✓ uv"
echo "  ✓ trobz_local (tlc command available)"
echo "  ✓ nvm, node, and vercel-labs/skills (AI agent skills)"
echo ""
echo "Next steps:"
echo ""
echo "  1. Install development tools (Odoo, PostgreSQL, etc.):"
echo "     tlc install-tools"
echo ""
echo "  2. Initialize your development environment:"
echo "     tlc init              # Create directory structure"
echo "     tlc pull-repos        # Clone repositories"
echo "     tlc create-venvs      # Create virtual environments"
echo ""
echo "  3. Get help:"
echo "     tlc --help"
echo ""
