#!/bin/bash
"""
Linux Guest Agent Installation Script
Installs the guest agent as a systemd service.
"""

set -e

AGENT_USER="guest-agent"
AGENT_DIR="/opt/guest-agent"
SERVICE_NAME="guest-agent"
SOCKET_PATH="/tmp/guest-agent.sock"

echo "Installing Linux Guest Agent..."

# Create user for the agent
if ! id "$AGENT_USER" &>/dev/null; then
    echo "Creating user: $AGENT_USER"
    useradd -r -s /bin/false -d "$AGENT_DIR" "$AGENT_USER"
fi

# Create directories
echo "Creating directories..."
mkdir -p "$AGENT_DIR"
mkdir -p /var/log/guest-agent

# Copy agent files
echo "Installing agent files..."
cp agent.py "$AGENT_DIR/"
chmod +x "$AGENT_DIR/agent.py"
chown -R "$AGENT_USER:$AGENT_USER" "$AGENT_DIR"
chown -R "$AGENT_USER:$AGENT_USER" /var/log/guest-agent

# Create systemd service file
echo "Creating systemd service..."
cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=Guest Agent for MicroVM
After=network.target

[Service]
Type=exec
User=$AGENT_USER
Group=$AGENT_USER
ExecStart=/usr/bin/python3 $AGENT_DIR/agent.py --socket $SOCKET_PATH
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=guest-agent

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/tmp /var/log/guest-agent
CapabilityBoundingSet=CAP_DAC_OVERRIDE CAP_SETUID CAP_SETGID

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
echo "Enabling and starting service..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

# Verify installation
echo "Verifying installation..."
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✓ Guest agent installed and running successfully"
    echo "Socket: $SOCKET_PATH"
    echo "Logs: journalctl -u $SERVICE_NAME"
else
    echo "✗ Failed to start guest agent"
    echo "Check logs: journalctl -u $SERVICE_NAME"
    exit 1
fi