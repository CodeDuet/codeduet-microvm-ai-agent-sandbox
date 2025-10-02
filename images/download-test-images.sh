#!/bin/bash
# Download minimal test images for CI/CD or testing

set -e

echo "Downloading minimal test images..."

# Create minimal Linux kernel (placeholder)
if [ ! -f "linux/vmlinux.bin" ]; then
    echo "Creating minimal Linux kernel placeholder..."
    # This is a placeholder - replace with actual kernel download
    touch linux/vmlinux.bin
    echo "⚠️  Please replace linux/vmlinux.bin with actual kernel binary"
fi

# Create minimal rootfs (placeholder)
if [ ! -f "linux/rootfs.ext4" ]; then
    echo "Creating minimal rootfs placeholder..."
    dd if=/dev/zero of=linux/rootfs.ext4 bs=1M count=100 2>/dev/null
    echo "⚠️  Please replace linux/rootfs.ext4 with actual root filesystem"
fi

# Create UEFI firmware placeholder
if [ ! -f "windows/OVMF.fd" ]; then
    echo "Creating UEFI firmware placeholder..."
    if [ -f "/usr/share/OVMF/OVMF_CODE.fd" ]; then
        cp /usr/share/OVMF/OVMF_CODE.fd windows/OVMF.fd
        echo "✓ Copied UEFI firmware from system"
    else
        touch windows/OVMF.fd
        echo "⚠️  Please install OVMF package and copy OVMF_CODE.fd"
    fi
fi

# Create Windows disk placeholder
if [ ! -f "windows/windows.qcow2" ]; then
    echo "Creating Windows disk placeholder..."
    touch windows/windows.qcow2
    echo "⚠️  Please create actual Windows qcow2 image"
fi

echo ""
echo "Test images setup complete!"
echo "⚠️  NOTE: These are placeholder files for testing."
echo "    For production use, replace with actual VM images."
