#!/bin/bash
set -e

# Install Dependencies for MicroVM Sandbox
# This script installs all required system dependencies

echo "Installing MicroVM Sandbox dependencies..."

# Detect OS
if command -v apt-get &> /dev/null; then
    # Ubuntu/Debian
    echo "Detected Ubuntu/Debian system"
    
    # Update package list
    sudo apt-get update
    
    # Install required packages
    sudo apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        git \
        curl \
        wget \
        build-essential \
        qemu-kvm \
        libvirt-daemon-system \
        libvirt-clients \
        bridge-utils \
        iptables \
        iproute2 \
        net-tools \
        jq \
        htop
    
    echo "Adding user to kvm and libvirt groups..."
    sudo usermod -a -G kvm,libvirt $USER
    
elif command -v yum &> /dev/null; then
    # RHEL/CentOS/Fedora
    echo "Detected RHEL/CentOS/Fedora system"
    
    # Install required packages
    sudo yum install -y \
        python3 \
        python3-pip \
        git \
        curl \
        wget \
        gcc \
        qemu-kvm \
        libvirt \
        bridge-utils \
        iptables \
        iproute \
        jq \
        htop
    
    echo "Adding user to kvm and libvirt groups..."
    sudo usermod -a -G kvm,libvirt $USER
    
else
    echo "Unsupported operating system. Please install dependencies manually."
    echo "Required packages: python3, python3-pip, qemu-kvm, libvirt, bridge-utils, iptables"
    exit 1
fi

# Verify KVM support
echo "Verifying KVM support..."
if [ -e /dev/kvm ]; then
    echo "✓ KVM device found: /dev/kvm"
else
    echo "✗ KVM device not found. Please ensure:"
    echo "  1. Hardware virtualization is enabled in BIOS"
    echo "  2. KVM kernel modules are loaded"
    echo "  Run: sudo modprobe kvm kvm_intel  # or kvm_amd"
fi

# Check virtualization support
if egrep -c '(vmx|svm)' /proc/cpuinfo > /dev/null; then
    echo "✓ Hardware virtualization support detected"
else
    echo "✗ Hardware virtualization not detected"
    echo "  Please enable VT-x/AMD-V in BIOS settings"
fi

echo ""
echo "Dependencies installation complete!"
echo ""
echo "IMPORTANT: Please log out and log back in for group changes to take effect."
echo "Then verify KVM access with: ls -la /dev/kvm"