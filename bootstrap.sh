#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export PATH="$HOME/.local/bin:$PATH"

# Bootstrap script for trobz_local (tlc)
# Installs: uv, git, gh, and the trobz_local package

echo "=== Bootstrap trobz_local ==="

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

# Install prerequisite packages (Debian/Ubuntu only)
install_prerequisites() {
    if [[ "$OS" != "debian" ]]; then
        return
    fi
    echo "Installing prerequisite packages..."
    sudo apt-get update
    sudo apt-get install -y apt-utils apt-transport-https lsb-release
}

# Add PostgreSQL APT repository (Debian/Ubuntu only)
setup_postgresql_repo() {
    if [[ "$OS" != "debian" ]]; then
        return
    fi
    if [ -f /usr/share/keyrings/postgresql-keyring.gpg ]; then
        echo "PostgreSQL APT repository already configured"
        return
    fi
    echo "Adding PostgreSQL APT repository..."
    local codename
    codename=$(lsb_release -cs)
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/postgresql-keyring.gpg] https://apt.postgresql.org/pub/repos/apt ${codename}-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list > /dev/null
    sudo apt-get update
}

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

# Main
install_prerequisites
setup_postgresql_repo
install_git
install_gh
install_uv
setup_github_ssh
install_trobz_local

echo ""
echo "=== Bootstrap complete ==="
echo "Run 'tlc --help' to get started"
