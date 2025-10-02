#!/bin/bash
set -e

# Download VM Images for MicroVM Sandbox
# This script downloads or helps create VM images for testing

IMAGES_DIR="${IMAGES_DIR:-images}"
LINUX_DIR="$IMAGES_DIR/linux"
WINDOWS_DIR="$IMAGES_DIR/windows"

echo "Setting up VM images directory structure..."

# Create directories
mkdir -p "$LINUX_DIR"
mkdir -p "$WINDOWS_DIR"

echo "Created directories:"
echo "  - $LINUX_DIR"
echo "  - $WINDOWS_DIR"

# Create placeholder files and instructions
cat > "$LINUX_DIR/README.md" << 'EOF'
# Linux VM Images

This directory should contain the following files for Linux VMs:

## Required Files

### Kernel
- **vmlinux.bin** - Linux kernel binary (uncompressed)
  - Download from: https://github.com/cloud-hypervisor/linux-cloud-hypervisor
  - Or build from source with Cloud Hypervisor kernel config

### Root Filesystem
- **rootfs.ext4** - Linux root filesystem (ext4 format)
  - Create with: `dd if=/dev/zero of=rootfs.ext4 bs=1M count=1024`
  - Format with: `mkfs.ext4 rootfs.ext4`
  - Mount and install base system

## Example Creation Commands

```bash
# Download pre-built kernel (example)
wget https://github.com/cloud-hypervisor/linux-cloud-hypervisor/releases/download/ch-v6.2/vmlinux.bin

# Create root filesystem
dd if=/dev/zero of=rootfs.ext4 bs=1M count=1024
mkfs.ext4 rootfs.ext4

# Mount and setup (requires root)
sudo mkdir -p /mnt/rootfs
sudo mount -o loop rootfs.ext4 /mnt/rootfs
# Install base system (debootstrap, etc.)
sudo umount /mnt/rootfs
```

## Template Examples

See `config/vm-templates/` for examples of how these images are referenced.
EOF

cat > "$WINDOWS_DIR/README.md" << 'EOF'
# Windows VM Images

This directory should contain the following files for Windows VMs:

## Required Files

### UEFI Firmware
- **OVMF.fd** - UEFI firmware for Windows boot
  - Download from: Ubuntu package `ovmf` or build from source
  - Location: Usually `/usr/share/OVMF/OVMF_CODE.fd`

### Windows Disk Image
- **windows.qcow2** - Windows disk image (qcow2 format)
  - Create from Windows ISO using qemu-img
  - Pre-install Windows and configure for Cloud Hypervisor

### VirtIO Drivers
- **virtio-win.iso** - VirtIO drivers for Windows
  - Download from: https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/

## Example Creation Commands

```bash
# Copy UEFI firmware
cp /usr/share/OVMF/OVMF_CODE.fd OVMF.fd

# Create Windows disk image
qemu-img create -f qcow2 windows.qcow2 40G

# Download VirtIO drivers
wget https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/archive-virtio/virtio-win-0.1.240/virtio-win.iso
```

## Installation Notes

1. Install Windows in the qcow2 image using QEMU first
2. Install VirtIO drivers during Windows installation
3. Configure Windows for Cloud Hypervisor compatibility
4. Use the prepare-windows-image.sh script for automation

## Template Examples

See `config/vm-templates/` for examples of how these images are referenced.
EOF

# Create example configuration for CI/CD or testing
cat > "$IMAGES_DIR/download-test-images.sh" << 'EOF'
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
EOF

chmod +x "$IMAGES_DIR/download-test-images.sh"

# Create .gitkeep files to preserve directory structure
touch "$LINUX_DIR/.gitkeep"
touch "$WINDOWS_DIR/.gitkeep"

echo ""
echo "VM images directory setup complete!"
echo ""
echo "Directory structure created:"
echo "  $LINUX_DIR/ - For Linux kernel and rootfs"
echo "  $WINDOWS_DIR/ - For Windows UEFI, disk image, and drivers"
echo ""
echo "Next steps:"
echo "1. Read the README.md files in each directory"
echo "2. Download or create the required VM images"
echo "3. Run './images/download-test-images.sh' for test placeholders"
echo ""
echo "For automated test setup: ./images/download-test-images.sh"