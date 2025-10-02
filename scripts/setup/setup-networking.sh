#!/bin/bash
set -e

# Setup Networking for MicroVM Sandbox
# This script configures bridge networking for MicroVMs

BRIDGE_NAME="${BRIDGE_NAME:-chbr0}"
SUBNET="${SUBNET:-192.168.200.0/24}"
GATEWAY="${GATEWAY:-192.168.200.1}"

echo "Setting up MicroVM networking..."
echo "Bridge: $BRIDGE_NAME"
echo "Subnet: $SUBNET"
echo "Gateway: $GATEWAY"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

# Remove existing bridge if it exists
if ip link show "$BRIDGE_NAME" &> /dev/null; then
    echo "Removing existing bridge: $BRIDGE_NAME"
    ip link set "$BRIDGE_NAME" down 2>/dev/null || true
    ip link delete "$BRIDGE_NAME" 2>/dev/null || true
fi

# Create bridge
echo "Creating bridge: $BRIDGE_NAME"
ip link add name "$BRIDGE_NAME" type bridge

# Configure bridge IP
echo "Configuring bridge IP: $GATEWAY"
ip addr add "$GATEWAY/24" dev "$BRIDGE_NAME"

# Bring bridge up
echo "Bringing bridge up"
ip link set "$BRIDGE_NAME" up

# Enable IP forwarding
echo "Enabling IP forwarding"
echo 1 > /proc/sys/net/ipv4/ip_forward

# Make IP forwarding persistent
if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf; then
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi

# Configure iptables for NAT
echo "Configuring iptables rules"

# Allow forwarding for bridge
iptables -A FORWARD -i "$BRIDGE_NAME" -j ACCEPT 2>/dev/null || true
iptables -A FORWARD -o "$BRIDGE_NAME" -j ACCEPT 2>/dev/null || true

# Setup NAT
iptables -t nat -A POSTROUTING -s "$SUBNET" ! -d "$SUBNET" -j MASQUERADE 2>/dev/null || true

# Allow established connections
iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true

# Save iptables rules (Ubuntu/Debian)
if command -v iptables-save &> /dev/null; then
    if [ -d /etc/iptables ]; then
        iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
    fi
fi

# Create systemd service for persistent networking
cat > /etc/systemd/system/microvm-networking.service << EOF
[Unit]
Description=MicroVM Networking Setup
After=network.target
Before=microvm-sandbox.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c 'ip link add name $BRIDGE_NAME type bridge 2>/dev/null || true'
ExecStart=/bin/bash -c 'ip addr add $GATEWAY/24 dev $BRIDGE_NAME 2>/dev/null || true'
ExecStart=/bin/bash -c 'ip link set $BRIDGE_NAME up'
ExecStart=/bin/bash -c 'echo 1 > /proc/sys/net/ipv4/ip_forward'
ExecStop=/bin/bash -c 'ip link delete $BRIDGE_NAME 2>/dev/null || true'

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
systemctl daemon-reload
systemctl enable microvm-networking.service
systemctl start microvm-networking.service

# Verify setup
echo ""
echo "Verifying network setup..."

if ip link show "$BRIDGE_NAME" &> /dev/null; then
    echo "✓ Bridge $BRIDGE_NAME created successfully"
    ip addr show "$BRIDGE_NAME"
else
    echo "✗ Bridge creation failed"
    exit 1
fi

if [ "$(cat /proc/sys/net/ipv4/ip_forward)" = "1" ]; then
    echo "✓ IP forwarding enabled"
else
    echo "✗ IP forwarding not enabled"
fi

echo ""
echo "Network setup complete!"
echo "Bridge: $BRIDGE_NAME"
echo "Gateway: $GATEWAY"
echo "VM subnet: $SUBNET"
echo ""
echo "The bridge will be automatically created on system boot."