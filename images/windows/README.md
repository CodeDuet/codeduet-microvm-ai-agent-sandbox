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
