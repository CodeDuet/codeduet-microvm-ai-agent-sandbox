#!/bin/bash
#
# Windows Guest Image Preparation Script
# Prepares Windows VM images with VirtIO drivers for MicroVM deployment
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGES_DIR="$PROJECT_ROOT/images/windows"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "This script should not be run as root"
        exit 1
    fi
}

# Check system requirements
check_requirements() {
    local missing_deps=()
    
    # Check for required tools
    for tool in qemu-img qemu-system-x86_64 wget curl; do
        if ! command -v "$tool" &> /dev/null; then
            missing_deps+=("$tool")
        fi
    done
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_info "Install with: sudo apt-get install qemu-utils qemu-system-x86 wget curl"
        exit 1
    fi
    
    # Check available disk space (need at least 20GB)
    local available_space
    available_space=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    local required_space=$((20 * 1024 * 1024)) # 20GB in KB
    
    if [[ $available_space -lt $required_space ]]; then
        log_error "Insufficient disk space. Need at least 20GB available."
        exit 1
    fi
}

# Create necessary directories
setup_directories() {
    log_info "Setting up directories..."
    
    mkdir -p "$IMAGES_DIR"
    mkdir -p "$IMAGES_DIR/iso"
    mkdir -p "$IMAGES_DIR/drivers"
    mkdir -p "$IMAGES_DIR/scripts"
    
    log_success "Directories created"
}

# Download OVMF UEFI firmware
download_ovmf() {
    log_info "Downloading OVMF UEFI firmware..."
    
    local ovmf_url="https://github.com/tianocore/edk2/releases/download/edk2-stable202211/OVMF-X64.zip"
    local ovmf_zip="$IMAGES_DIR/OVMF-X64.zip"
    
    if [[ ! -f "$IMAGES_DIR/OVMF.fd" ]]; then
        if ! wget -O "$ovmf_zip" "$ovmf_url"; then
            log_error "Failed to download OVMF firmware"
            return 1
        fi
        
        unzip -q "$ovmf_zip" -d "$IMAGES_DIR"
        mv "$IMAGES_DIR/OVMF.fd" "$IMAGES_DIR/OVMF.fd" 2>/dev/null || mv "$IMAGES_DIR"/*.fd "$IMAGES_DIR/OVMF.fd"
        rm -f "$ovmf_zip"
        
        log_success "OVMF firmware downloaded"
    else
        log_info "OVMF firmware already exists"
    fi
}

# Download VirtIO drivers
download_virtio_drivers() {
    log_info "Downloading VirtIO drivers for Windows..."
    
    local virtio_url="https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/virtio-win.iso"
    local virtio_iso="$IMAGES_DIR/virtio-win.iso"
    
    if [[ ! -f "$virtio_iso" ]]; then
        if ! wget -O "$virtio_iso" "$virtio_url"; then
            log_error "Failed to download VirtIO drivers"
            return 1
        fi
        
        log_success "VirtIO drivers downloaded"
    else
        log_info "VirtIO drivers already exist"
    fi
}

# Create Windows VM disk image
create_windows_disk() {
    log_info "Creating Windows VM disk image..."
    
    local disk_image="$IMAGES_DIR/windows.qcow2"
    local disk_size="20G"
    
    if [[ ! -f "$disk_image" ]]; then
        qemu-img create -f qcow2 "$disk_image" "$disk_size"
        log_success "Windows disk image created (${disk_size})"
    else
        log_info "Windows disk image already exists"
    fi
}

# Create Windows installation automation script
create_autounattend() {
    log_info "Creating Windows automated installation files..."
    
    local autounattend_file="$IMAGES_DIR/scripts/autounattend.xml"
    
    cat > "$autounattend_file" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend">
    <settings pass="windowsPE">
        <component name="Microsoft-Windows-International-Core-WinPE" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <SetupUILanguage>
                <UILanguage>en-US</UILanguage>
            </SetupUILanguage>
            <InputLocale>en-US</InputLocale>
            <SystemLocale>en-US</SystemLocale>
            <UILanguage>en-US</UILanguage>
            <UserLocale>en-US</UserLocale>
        </component>
        <component name="Microsoft-Windows-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <DiskConfiguration>
                <Disk wcm:action="add">
                    <CreatePartitions>
                        <CreatePartition wcm:action="add">
                            <Order>1</Order>
                            <Type>Primary</Type>
                            <Size>100</Size>
                        </CreatePartition>
                        <CreatePartition wcm:action="add">
                            <Order>2</Order>
                            <Type>Primary</Type>
                            <Extend>true</Extend>
                        </CreatePartition>
                    </CreatePartitions>
                    <ModifyPartitions>
                        <ModifyPartition wcm:action="add">
                            <Order>1</Order>
                            <PartitionID>1</PartitionID>
                            <Label>System Reserved</Label>
                            <Format>NTFS</Format>
                            <Active>true</Active>
                        </ModifyPartition>
                        <ModifyPartition wcm:action="add">
                            <Order>2</Order>
                            <PartitionID>2</PartitionID>
                            <Label>Windows</Label>
                            <Letter>C</Letter>
                            <Format>NTFS</Format>
                        </ModifyPartition>
                    </ModifyPartitions>
                    <DiskID>0</DiskID>
                    <WillWipeDisk>true</WillWipeDisk>
                </Disk>
            </DiskConfiguration>
            <ImageInstall>
                <OSImage>
                    <InstallTo>
                        <DiskID>0</DiskID>
                        <PartitionID>2</PartitionID>
                    </InstallTo>
                    <WillShowUI>OnError</WillShowUI>
                    <InstallToAvailablePartition>false</InstallToAvailablePartition>
                </OSImage>
            </ImageInstall>
            <UserData>
                <AcceptEula>true</AcceptEula>
                <FullName>MicroVM User</FullName>
                <Organization>MicroVM Sandbox</Organization>
                <ProductKey>
                    <WillShowUI>OnError</WillShowUI>
                </ProductKey>
            </UserData>
        </component>
    </settings>
    <settings pass="oobeSystem">
        <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <OOBE>
                <HideEULAPage>true</HideEULAPage>
                <HideOEMRegistrationScreen>true</HideOEMRegistrationScreen>
                <HideOnlineAccountScreens>true</HideOnlineAccountScreens>
                <HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE>
                <NetworkLocation>Work</NetworkLocation>
                <ProtectYourPC>1</ProtectYourPC>
            </OOBE>
            <UserAccounts>
                <AdministratorPassword>
                    <Value>microvm123!</Value>
                    <PlainText>true</PlainText>
                </AdministratorPassword>
                <LocalAccounts>
                    <LocalAccount wcm:action="add">
                        <Password>
                            <Value>microvm123!</Value>
                            <PlainText>true</PlainText>
                        </Password>
                        <Description>MicroVM Administrator</Description>
                        <DisplayName>Administrator</DisplayName>
                        <Group>Administrators</Group>
                        <Name>Administrator</Name>
                    </LocalAccount>
                </LocalAccounts>
            </UserAccounts>
            <AutoLogon>
                <Password>
                    <Value>microvm123!</Value>
                    <PlainText>true</PlainText>
                </Password>
                <Username>Administrator</Username>
                <Enabled>true</Enabled>
            </AutoLogon>
            <FirstLogonCommands>
                <SynchronousCommand wcm:action="add">
                    <CommandLine>powershell.exe -ExecutionPolicy Bypass -File C:\guest-agent-setup.ps1</CommandLine>
                    <Description>Install Guest Agent</Description>
                    <Order>1</Order>
                </SynchronousCommand>
            </FirstLogonCommands>
        </component>
    </settings>
</unattend>
EOF

    log_success "Windows autounattend.xml created"
}

# Create guest agent setup script
create_guest_agent_setup() {
    log_info "Creating guest agent setup script..."
    
    local setup_script="$IMAGES_DIR/scripts/guest-agent-setup.ps1"
    
    cat > "$setup_script" << 'EOF'
# Windows Guest Agent Setup Script
# This script installs and configures the MicroVM guest agent

$ErrorActionPreference = "Stop"

Write-Host "Setting up MicroVM Guest Agent..." -ForegroundColor Green

try {
    # Enable PowerShell execution policy
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Force
    
    # Install VirtIO drivers from D: drive (VirtIO ISO)
    if (Test-Path "D:\") {
        Write-Host "Installing VirtIO drivers..." -ForegroundColor Yellow
        
        # Install balloon driver
        if (Test-Path "D:\Balloon\w10\amd64\balloon.inf") {
            pnputil /add-driver "D:\Balloon\w10\amd64\balloon.inf" /install
        }
        
        # Install network driver
        if (Test-Path "D:\NetKVM\w10\amd64\netkvm.inf") {
            pnputil /add-driver "D:\NetKVM\w10\amd64\netkvm.inf" /install
        }
        
        # Install storage driver
        if (Test-Path "D:\viostor\w10\amd64\viostor.inf") {
            pnputil /add-driver "D:\viostor\w10\amd64\viostor.inf" /install
        }
        
        # Install serial driver
        if (Test-Path "D:\vioserial\w10\amd64\vioser.inf") {
            pnputil /add-driver "D:\vioserial\w10\amd64\vioser.inf" /install
        }
        
        Write-Host "VirtIO drivers installed successfully" -ForegroundColor Green
    }
    
    # Create guest agent directory
    $AgentDir = "C:\Program Files\MicroVM Guest Agent"
    New-Item -ItemType Directory -Path $AgentDir -Force | Out-Null
    
    # Download and install Python (for the guest agent)
    $PythonUrl = "https://www.python.org/ftp/python/3.11.0/python-3.11.0-amd64.exe"
    $PythonInstaller = "$env:TEMP\python-installer.exe"
    
    Write-Host "Downloading Python..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $PythonUrl -OutFile $PythonInstaller
    
    Write-Host "Installing Python..." -ForegroundColor Yellow
    Start-Process -FilePath $PythonInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
    
    # Create a simple guest agent service
    $ServiceScript = @'
import http.server
import socketserver
import json
import subprocess
import os
from urllib.parse import parse_qs, urlparse

class GuestAgentHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'healthy'}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/execute':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            try:
                result = subprocess.run(
                    ['powershell.exe', '-Command', data['command']],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                response = {
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    PORT = 8080
    with socketserver.TCPServer(("", PORT), GuestAgentHandler) as httpd:
        print(f"Guest Agent serving on port {PORT}")
        httpd.serve_forever()
'@
    
    $ServiceScript | Out-File -FilePath "$AgentDir\guest-agent.py" -Encoding UTF8
    
    # Create service wrapper
    $ServiceWrapper = @'
@echo off
cd "C:\Program Files\MicroVM Guest Agent"
python guest-agent.py
'@
    
    $ServiceWrapper | Out-File -FilePath "$AgentDir\start-agent.bat" -Encoding ASCII
    
    # Create Windows service
    $ServiceExe = "C:\Windows\System32\sc.exe"
    & $ServiceExe create "MicroVMGuestAgent" binPath= "`"$AgentDir\start-agent.bat`"" start= auto
    & $ServiceExe start "MicroVMGuestAgent"
    
    Write-Host "Guest Agent installed and started" -ForegroundColor Green
    
    # Enable RDP (optional)
    Enable-NetFirewallRule -DisplayGroup "Remote Desktop"
    Set-ItemProperty -Path "HKLM:\System\CurrentControlSet\Control\Terminal Server" -Name "fDenyTSConnections" -Value 0
    
    Write-Host "Windows Guest setup completed successfully!" -ForegroundColor Green
    
} catch {
    Write-Host "Error during setup: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
EOF

    log_success "Guest agent setup script created"
}

# Create ISO with automation files
create_automation_iso() {
    log_info "Creating automation ISO with Windows setup files..."
    
    local iso_dir="$IMAGES_DIR/iso"
    local automation_iso="$IMAGES_DIR/windows-automation.iso"
    
    # Copy automation files to ISO directory
    cp "$IMAGES_DIR/scripts/autounattend.xml" "$iso_dir/"
    cp "$IMAGES_DIR/scripts/guest-agent-setup.ps1" "$iso_dir/"
    
    # Create ISO using genisoimage if available
    if command -v genisoimage &> /dev/null; then
        genisoimage -o "$automation_iso" -J -R "$iso_dir"
        log_success "Automation ISO created"
    elif command -v mkisofs &> /dev/null; then
        mkisofs -o "$automation_iso" -J -R "$iso_dir"
        log_success "Automation ISO created"
    else
        log_warning "genisoimage/mkisofs not found. Please install to create automation ISO."
        log_info "Install with: sudo apt-get install genisoimage"
    fi
}

# Main function
main() {
    log_info "Starting Windows guest image preparation..."
    
    check_root
    check_requirements
    setup_directories
    download_ovmf
    download_virtio_drivers
    create_windows_disk
    create_autounattend
    create_guest_agent_setup
    create_automation_iso
    
    log_success "Windows guest image preparation completed!"
    log_info ""
    log_info "Next steps:"
    log_info "1. Obtain a Windows ISO file and place it in $IMAGES_DIR/"
    log_info "2. Use the QEMU command provided in the documentation to install Windows"
    log_info "3. The automation scripts will handle VirtIO driver installation"
    log_info ""
    log_info "Files created:"
    log_info "- $IMAGES_DIR/OVMF.fd (UEFI firmware)"
    log_info "- $IMAGES_DIR/virtio-win.iso (VirtIO drivers)"
    log_info "- $IMAGES_DIR/windows.qcow2 (VM disk image)"
    log_info "- $IMAGES_DIR/scripts/autounattend.xml (Automated installation)"
    log_info "- $IMAGES_DIR/scripts/guest-agent-setup.ps1 (Guest agent setup)"
}

# Run main function
main "$@"