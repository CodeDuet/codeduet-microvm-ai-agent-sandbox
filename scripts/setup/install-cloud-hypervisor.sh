#!/bin/bash
set -e

# Install Cloud Hypervisor
# This script downloads and installs Cloud Hypervisor VMM

CLOUD_HYPERVISOR_VERSION="${CLOUD_HYPERVISOR_VERSION:-34.0}"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"

echo "Installing Cloud Hypervisor v${CLOUD_HYPERVISOR_VERSION}..."

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        CH_ARCH="x86_64"
        ;;
    aarch64|arm64)
        CH_ARCH="aarch64"
        ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

echo "Detected architecture: $ARCH"

# Create temporary directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Download Cloud Hypervisor
DOWNLOAD_URL="https://github.com/cloud-hypervisor/cloud-hypervisor/releases/download/v${CLOUD_HYPERVISOR_VERSION}/cloud-hypervisor-static"

echo "Downloading Cloud Hypervisor from: $DOWNLOAD_URL"
curl -L "$DOWNLOAD_URL" -o cloud-hypervisor

# Verify download
if [ ! -f cloud-hypervisor ]; then
    echo "Error: Failed to download Cloud Hypervisor"
    exit 1
fi

# Make executable
chmod +x cloud-hypervisor

# Install to system
echo "Installing to $INSTALL_DIR/cloud-hypervisor"
sudo mv cloud-hypervisor "$INSTALL_DIR/cloud-hypervisor"

# Verify installation
if command -v cloud-hypervisor &> /dev/null; then
    echo "✓ Cloud Hypervisor installed successfully"
    cloud-hypervisor --version
else
    echo "✗ Installation failed. Please check PATH includes $INSTALL_DIR"
    exit 1
fi

# Cleanup
cd /
rm -rf "$TEMP_DIR"

echo ""
echo "Cloud Hypervisor installation complete!"
echo "Version: $(cloud-hypervisor --version)"
echo "Location: $(which cloud-hypervisor)"