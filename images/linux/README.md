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
