#!/usr/bin/env bash
# BugPilot CLI installer for Linux and macOS
# Usage: curl -fsSL https://get.bugpilot.com/install.sh | bash
#        or: bash install.sh [--version v1.0.0] [--dir /usr/local/bin]

set -euo pipefail

REPO="skonlabs/bugpilot"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
VERSION="${VERSION:-}"

# Colours
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()    { echo -e "${GREEN}[bugpilot]${NC} $*"; }
warning() { echo -e "${YELLOW}[bugpilot]${NC} $*"; }
error()   { echo -e "${RED}[bugpilot] ERROR:${NC} $*" >&2; exit 1; }

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --version) VERSION="$2"; shift 2 ;;
    --dir)     INSTALL_DIR="$2"; shift 2 ;;
    *) error "Unknown argument: $1" ;;
  esac
done

# Detect OS and arch — names must match release asset filenames from release.yml
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "$ARCH" in
  x86_64)        ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) error "Unsupported architecture: $ARCH" ;;
esac

case "$OS" in
  linux)  ;;
  darwin) OS="macos" ;;
  *) error "Unsupported OS: $OS (use install.ps1 for Windows)" ;;
esac

# Fetch latest version if not specified
if [[ -z "$VERSION" ]]; then
  info "Fetching latest version..."
  VERSION=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" | \
            grep '"tag_name"' | sed 's/.*"tag_name": "\(.*\)".*/\1/')
  if [[ -z "$VERSION" ]]; then
    error "Could not determine latest version"
  fi
fi

info "Installing bugpilot $VERSION for $OS/$ARCH..."

# Download binary
ASSET_NAME="bugpilot-${OS}-${ARCH}"
DOWNLOAD_URL="https://github.com/$REPO/releases/download/$VERSION/$ASSET_NAME"
TMP_FILE=$(mktemp)

info "Downloading $DOWNLOAD_URL..."
if ! curl -fsSL "$DOWNLOAD_URL" -o "$TMP_FILE"; then
  error "Download failed: $DOWNLOAD_URL"
fi

chmod +x "$TMP_FILE"

# Verify binary
if ! "$TMP_FILE" version &>/dev/null; then
  warning "Version check failed — binary may be corrupt"
fi

# Install
INSTALL_PATH="$INSTALL_DIR/bugpilot"
if [[ -w "$INSTALL_DIR" ]]; then
  mv "$TMP_FILE" "$INSTALL_PATH"
else
  info "Requesting sudo to install to $INSTALL_DIR..."
  sudo mv "$TMP_FILE" "$INSTALL_PATH"
fi

info "✓ Installed bugpilot $VERSION to $INSTALL_PATH"
echo ""
echo "  Get started:"
echo "    bugpilot init"
echo "    bugpilot investigate TICKET-123"
