# Windows Guest Agent Installation Script
# Installs the guest agent as a Windows service

param(
    [string]$ServiceName = "GuestAgent",
    [string]$AgentPath = "C:\Program Files\GuestAgent",
    [string]$PipeName = "\\.\pipe\guest-agent"
)

Write-Host "Installing Windows Guest Agent..." -ForegroundColor Green

# Check if running as administrator
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "This script must be run as Administrator"
    exit 1
}

# Create directories
Write-Host "Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $AgentPath | Out-Null
New-Item -ItemType Directory -Force -Path "C:\ProgramData\GuestAgent\Logs" | Out-Null

# Copy agent files
Write-Host "Installing agent files..." -ForegroundColor Yellow
Copy-Item "agent.py" -Destination $AgentPath -Force
Copy-Item "requirements.txt" -Destination $AgentPath -Force -ErrorAction SilentlyContinue

# Install Python dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
$pythonExe = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonExe) {
    $pythonExe = Get-Command python3 -ErrorAction SilentlyContinue
}

if (-not $pythonExe) {
    Write-Error "Python not found. Please install Python 3.7+ before running this script."
    exit 1
}

$requirementsFile = Join-Path $AgentPath "requirements.txt"
if (Test-Path $requirementsFile) {
    & $pythonExe.Source -m pip install -r $requirementsFile
} else {
    # Install required packages directly
    & $pythonExe.Source -m pip install psutil wmi pywin32
}

# Create Windows service wrapper script
$serviceScript = @"
import sys
import os
import asyncio
import win32serviceutil
import win32service
import win32event
import servicemanager
import logging

# Add agent directory to path
sys.path.insert(0, r'$AgentPath')

from agent import WindowsGuestAgent

class GuestAgentService(win32serviceutil.ServiceFramework):
    _svc_name_ = '$ServiceName'
    _svc_display_name_ = 'Guest Agent for MicroVM'
    _svc_description_ = 'Provides host-to-guest communication for MicroVM'
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.agent = None
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(r'C:\ProgramData\GuestAgent\Logs\service.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.logger.info("Service stop requested")
        
        if self.agent:
            asyncio.create_task(self.agent.stop())
        
        win32event.SetEvent(self.hWaitStop)
    
    def SvcDoRun(self):
        self.logger.info("Service starting")
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        try:
            self.main()
        except Exception as e:
            self.logger.error(f"Service error: {e}")
            servicemanager.LogErrorMsg(f"Service error: {e}")
    
    def main(self):
        self.agent = WindowsGuestAgent(pipe_name=r'$PipeName')
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.agent.start())
        except Exception as e:
            self.logger.error(f"Agent error: {e}")
        finally:
            loop.close()

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(GuestAgentService)
"@

$serviceScriptPath = Join-Path $AgentPath "service.py"
$serviceScript | Out-File -FilePath $serviceScriptPath -Encoding UTF8

# Install the service
Write-Host "Installing Windows service..." -ForegroundColor Yellow
& $pythonExe.Source $serviceScriptPath install

# Start the service
Write-Host "Starting service..." -ForegroundColor Yellow
& $pythonExe.Source $serviceScriptPath start

# Verify installation
Write-Host "Verifying installation..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq "Running") {
    Write-Host "✓ Guest agent installed and running successfully" -ForegroundColor Green
    Write-Host "Service Name: $ServiceName" -ForegroundColor Cyan
    Write-Host "Pipe Name: $PipeName" -ForegroundColor Cyan
    Write-Host "Logs: C:\ProgramData\GuestAgent\Logs\service.log" -ForegroundColor Cyan
} else {
    Write-Error "✗ Failed to start guest agent service"
    Write-Host "Check Windows Event Log for details" -ForegroundColor Red
    exit 1
}

Write-Host "Installation completed successfully!" -ForegroundColor Green