# Bare Metal Deployment Guide

This guide covers deploying the MicroVM Sandbox directly on bare metal servers for maximum performance and control.

## Prerequisites

### Hardware Requirements

**Minimum:**
- CPU: 4 cores with VT-x/AMD-V support
- Memory: 8GB RAM
- Storage: 50GB SSD
- Network: 1Gbps interface

**Recommended:**
- CPU: 8+ cores with VT-x/AMD-V support
- Memory: 32GB+ RAM
- Storage: 200GB+ NVMe SSD
- Network: 10Gbps interface

### Software Requirements

- Ubuntu 20.04+ or RHEL 8+
- Python 3.9+
- KVM and libvirt
- Cloud Hypervisor 34.0+
- systemd (for service management)

## Installation

### 1. System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
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
    net-tools

# Verify KVM support
egrep -c '(vmx|svm)' /proc/cpuinfo
ls -la /dev/kvm

# Add user to required groups
sudo usermod -a -G kvm,libvirt $USER
```

### 2. Download and Setup

```bash
# Create application directory
sudo mkdir -p /opt/microvm-sandbox
sudo chown $USER:$USER /opt/microvm-sandbox

# Clone repository
cd /opt/microvm-sandbox
git clone https://github.com/your-org/microvm-sandbox.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Install Cloud Hypervisor

```bash
# Download Cloud Hypervisor
CH_VERSION="34.0"
curl -L "https://github.com/cloud-hypervisor/cloud-hypervisor/releases/download/v${CH_VERSION}/cloud-hypervisor-static" \
    -o cloud-hypervisor

# Install binary
sudo mv cloud-hypervisor /usr/local/bin/
sudo chmod +x /usr/local/bin/cloud-hypervisor

# Verify installation
cloud-hypervisor --version
```

### 4. Network Configuration

```bash
# Run network setup script
sudo ./scripts/setup/setup-networking.sh

# Or manual setup:
sudo ip link add chbr0 type bridge
sudo ip addr add 192.168.200.1/24 dev chbr0
sudo ip link set chbr0 up

# Enable IP forwarding
echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Configure iptables
sudo iptables -t nat -A POSTROUTING -s 192.168.200.0/24 -j MASQUERADE
sudo iptables -A FORWARD -i chbr0 -j ACCEPT
sudo iptables -A FORWARD -o chbr0 -j ACCEPT

# Save iptables rules
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

### 5. Configuration

```bash
# Copy default configuration
cp config/config.yaml.example config/config.yaml

# Edit configuration
nano config/config.yaml
```

Example production configuration:

```yaml
# config/config.yaml
server:
  host: "0.0.0.0"
  port: 8000
  workers: 8
  access_log: true
  
cloud_hypervisor:
  binary_path: "/usr/local/bin/cloud-hypervisor"
  api_socket_dir: "/var/run/microvm-sandbox/sockets"
  
networking:
  bridge_name: "chbr0"
  subnet: "192.168.200.0/24"
  gateway: "192.168.200.1"
  port_range:
    start: 10000
    end: 20000
    
resources:
  max_vms: 100
  max_memory_per_vm: 16384
  max_vcpus_per_vm: 16
  max_disk_per_vm: 100
  
storage:
  data_dir: "/var/lib/microvm-sandbox"
  images_dir: "/var/lib/microvm-sandbox/images"
  snapshots_dir: "/var/lib/microvm-sandbox/snapshots"
  
security:
  enable_authentication: true
  jwt_secret_key: "your-secret-key-here"
  api_key_required: false
  vm_isolation: true
  
monitoring:
  prometheus_port: 9090
  metrics_enabled: true
  log_level: "INFO"
  
database:
  url: "sqlite:///var/lib/microvm-sandbox/microvm.db"
  # For PostgreSQL:
  # url: "postgresql://microvm:password@localhost:5432/microvm_sandbox"
```

### 6. Create System Directories

```bash
# Create required directories
sudo mkdir -p /var/lib/microvm-sandbox/{images,snapshots,data}
sudo mkdir -p /var/log/microvm-sandbox
sudo mkdir -p /var/run/microvm-sandbox/sockets
sudo mkdir -p /etc/microvm-sandbox

# Set permissions
sudo chown -R $USER:$USER /var/lib/microvm-sandbox
sudo chown -R $USER:$USER /var/log/microvm-sandbox
sudo chown -R $USER:$USER /var/run/microvm-sandbox

# Copy configuration
sudo cp config/config.yaml /etc/microvm-sandbox/
```

## Service Configuration

### 1. Systemd Service

Create systemd service file:

```bash
# Create service file
sudo tee /etc/systemd/system/microvm-sandbox.service << EOF
[Unit]
Description=MicroVM Sandbox API Server
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=/opt/microvm-sandbox
Environment=PATH=/opt/microvm-sandbox/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=/opt/microvm-sandbox
Environment=CONFIG_PATH=/etc/microvm-sandbox/config.yaml
ExecStart=/opt/microvm-sandbox/venv/bin/python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/microvm-sandbox /var/log/microvm-sandbox /var/run/microvm-sandbox /tmp

# Resource limits
LimitNOFILE=65535
LimitNPROC=32768

[Install]
WantedBy=multi-user.target
EOF
```

### 2. Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable microvm-sandbox

# Start service
sudo systemctl start microvm-sandbox

# Check status
sudo systemctl status microvm-sandbox

# View logs
sudo journalctl -u microvm-sandbox -f
```

### 3. Log Rotation

```bash
# Create logrotate configuration
sudo tee /etc/logrotate.d/microvm-sandbox << EOF
/var/log/microvm-sandbox/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 $USER $USER
    postrotate
        systemctl reload microvm-sandbox
    endscript
}
EOF
```

## Database Setup

### 1. SQLite (Default)

SQLite is used by default and requires no additional setup.

### 2. PostgreSQL (Recommended for Production)

```bash
# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Start and enable PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE microvm_sandbox;
CREATE USER microvm WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE microvm_sandbox TO microvm;
\q
EOF

# Update configuration
sed -i 's|sqlite:///var/lib/microvm-sandbox/microvm.db|postgresql://microvm:secure_password_here@localhost:5432/microvm_sandbox|' /etc/microvm-sandbox/config.yaml

# Restart service
sudo systemctl restart microvm-sandbox
```

### 3. Database Initialization

```bash
# Initialize database schema
cd /opt/microvm-sandbox
source venv/bin/activate
python -m src.utils.database init

# Create admin user
python -m src.utils.database create-user --username admin --password AdminPass123! --role admin
```

## High Availability Setup

### 1. Load Balancer with HAProxy

```bash
# Install HAProxy
sudo apt install -y haproxy

# Configure HAProxy
sudo tee /etc/haproxy/haproxy.cfg << EOF
global
    daemon
    log 127.0.0.1:514 local0
    chroot /var/lib/haproxy
    stats socket /run/haproxy/admin.sock mode 660 level admin
    stats timeout 30s
    user haproxy
    group haproxy

defaults
    mode http
    log global
    option httplog
    option dontlognull
    option log-health-checks
    option forwardfor except 127.0.0.0/8
    option redispatch
    retries 3
    timeout connect 5000
    timeout client 50000
    timeout server 50000

frontend microvm_frontend
    bind *:80
    bind *:443 ssl crt /etc/ssl/certs/microvm-sandbox.pem
    redirect scheme https if !{ ssl_fc }
    default_backend microvm_backend

backend microvm_backend
    balance roundrobin
    option httpchk GET /health
    server microvm1 192.168.1.10:8000 check
    server microvm2 192.168.1.11:8000 check
    server microvm3 192.168.1.12:8000 check

listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s
    stats admin if TRUE
EOF

# Start HAProxy
sudo systemctl enable haproxy
sudo systemctl start haproxy
```

### 2. Database Replication

For PostgreSQL streaming replication:

```bash
# On primary server
sudo -u postgres psql << EOF
CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'replication_password';
\q
EOF

# Edit postgresql.conf
sudo nano /etc/postgresql/13/main/postgresql.conf
# Add:
# wal_level = replica
# max_wal_senders = 3
# archive_mode = on
# archive_command = 'cp %p /var/lib/postgresql/13/main/pg_wal_archive/%f'

# Edit pg_hba.conf
sudo nano /etc/postgresql/13/main/pg_hba.conf
# Add:
# host replication replicator 192.168.1.0/24 md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### 3. Shared Storage

Configure shared storage for VM images and snapshots:

```bash
# Install NFS client
sudo apt install -y nfs-common

# Mount shared storage
sudo mkdir -p /mnt/shared-storage
echo "nfs-server:/export/microvm-sandbox /mnt/shared-storage nfs defaults 0 0" | sudo tee -a /etc/fstab
sudo mount -a

# Update configuration to use shared storage
sed -i 's|/var/lib/microvm-sandbox/images|/mnt/shared-storage/images|' /etc/microvm-sandbox/config.yaml
sed -i 's|/var/lib/microvm-sandbox/snapshots|/mnt/shared-storage/snapshots|' /etc/microvm-sandbox/config.yaml
```

## Performance Optimization

### 1. System Tuning

```bash
# Create tuning script
sudo tee /etc/sysctl.d/99-microvm-sandbox.conf << EOF
# Network performance
net.core.rmem_max = 268435456
net.core.wmem_max = 268435456
net.ipv4.tcp_rmem = 4096 87380 268435456
net.ipv4.tcp_wmem = 4096 65536 268435456
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_congestion_control = bbr

# File descriptor limits
fs.file-max = 1048576

# Virtual memory
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5

# KVM optimizations
vm.mmap_min_addr = 65536
kernel.sched_migration_cost_ns = 5000000
EOF

# Apply settings
sudo sysctl -p /etc/sysctl.d/99-microvm-sandbox.conf
```

### 2. CPU Isolation

```bash
# Edit GRUB configuration for CPU isolation
sudo nano /etc/default/grub

# Add isolcpus parameter (reserve cores 4-7 for VMs)
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash isolcpus=4,5,6,7"

# Update GRUB
sudo update-grub

# Reboot to apply
sudo reboot
```

### 3. NUMA Optimization

```bash
# Install numactl
sudo apt install -y numactl

# Check NUMA topology
numactl --hardware

# Update systemd service for NUMA awareness
sudo systemctl edit microvm-sandbox

# Add:
[Service]
ExecStart=
ExecStart=/usr/bin/numactl --cpunodebind=0 --membind=0 /opt/microvm-sandbox/venv/bin/python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

## Monitoring Setup

### 1. Prometheus

```bash
# Create prometheus user
sudo useradd --no-create-home --shell /bin/false prometheus

# Download and install Prometheus
PROM_VERSION="2.37.0"
wget https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz
tar xzf prometheus-${PROM_VERSION}.linux-amd64.tar.gz
sudo cp prometheus-${PROM_VERSION}.linux-amd64/prometheus /usr/local/bin/
sudo cp prometheus-${PROM_VERSION}.linux-amd64/promtool /usr/local/bin/

# Create directories
sudo mkdir -p /etc/prometheus /var/lib/prometheus
sudo chown prometheus:prometheus /etc/prometheus /var/lib/prometheus

# Create configuration
sudo tee /etc/prometheus/prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'microvm-sandbox'
    static_configs:
      - targets: ['localhost:9090']
  
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']

rule_files:
  - "microvm-sandbox.rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - localhost:9093
EOF

# Create systemd service
sudo tee /etc/systemd/system/prometheus.service << EOF
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus \
    --config.file /etc/prometheus/prometheus.yml \
    --storage.tsdb.path /var/lib/prometheus/ \
    --web.console.templates=/etc/prometheus/consoles \
    --web.console.libraries=/etc/prometheus/console_libraries \
    --web.listen-address=0.0.0.0:9090 \
    --web.enable-lifecycle

[Install]
WantedBy=multi-user.target
EOF

# Start Prometheus
sudo systemctl enable prometheus
sudo systemctl start prometheus
```

### 2. Node Exporter

```bash
# Download and install Node Exporter
NODE_EXP_VERSION="1.3.1"
wget https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXP_VERSION}/node_exporter-${NODE_EXP_VERSION}.linux-amd64.tar.gz
tar xzf node_exporter-${NODE_EXP_VERSION}.linux-amd64.tar.gz
sudo cp node_exporter-${NODE_EXP_VERSION}.linux-amd64/node_exporter /usr/local/bin/

# Create user
sudo useradd --no-create-home --shell /bin/false node_exporter

# Create systemd service
sudo tee /etc/systemd/system/node_exporter.service << EOF
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
EOF

# Start Node Exporter
sudo systemctl enable node_exporter
sudo systemctl start node_exporter
```

### 3. Grafana

```bash
# Add Grafana repository
curl -fsSL https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list

# Install Grafana
sudo apt update
sudo apt install -y grafana

# Start Grafana
sudo systemctl enable grafana-server
sudo systemctl start grafana-server

# Access Grafana at http://your-server:3000 (admin/admin)
```

## Security Hardening

### 1. Firewall Configuration

```bash
# Install UFW
sudo apt install -y ufw

# Configure firewall rules
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH
sudo ufw allow ssh

# Allow API access
sudo ufw allow 8000/tcp

# Allow monitoring
sudo ufw allow 9090/tcp  # Prometheus
sudo ufw allow 9100/tcp  # Node Exporter
sudo ufw allow 3000/tcp  # Grafana

# Enable firewall
sudo ufw enable
```

### 2. SSL/TLS Configuration

```bash
# Install Certbot
sudo apt install -y certbot

# Generate certificate (for public domains)
sudo certbot certonly --standalone -d api.yourdomain.com

# Or create self-signed certificate
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/microvm-sandbox.key \
    -out /etc/ssl/certs/microvm-sandbox.crt

# Configure nginx reverse proxy with SSL
sudo apt install -y nginx

sudo tee /etc/nginx/sites-available/microvm-sandbox << EOF
server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/ssl/certs/microvm-sandbox.crt;
    ssl_certificate_key /etc/ssl/private/microvm-sandbox.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/microvm-sandbox /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 3. File Permissions

```bash
# Secure configuration files
sudo chmod 600 /etc/microvm-sandbox/config.yaml
sudo chown root:root /etc/microvm-sandbox/config.yaml

# Secure log files
sudo chmod 640 /var/log/microvm-sandbox/*.log
sudo chown $USER:adm /var/log/microvm-sandbox/*.log

# Secure data directories
sudo chmod 750 /var/lib/microvm-sandbox
sudo chown $USER:$USER /var/lib/microvm-sandbox
```

## Backup and Recovery

### 1. Backup Script

```bash
# Create backup script
sudo tee /usr/local/bin/microvm-backup.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/backup/microvm-sandbox"
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_PATH="$BACKUP_DIR/$DATE"

# Create backup directory
mkdir -p "$BACKUP_PATH"

# Backup configuration
cp -r /etc/microvm-sandbox "$BACKUP_PATH/"

# Backup database
if grep -q "postgresql" /etc/microvm-sandbox/config.yaml; then
    pg_dump microvm_sandbox > "$BACKUP_PATH/database.sql"
else
    cp /var/lib/microvm-sandbox/microvm.db "$BACKUP_PATH/"
fi

# Backup VM images and snapshots
rsync -av /var/lib/microvm-sandbox/images/ "$BACKUP_PATH/images/"
rsync -av /var/lib/microvm-sandbox/snapshots/ "$BACKUP_PATH/snapshots/"

# Create tarball
cd "$BACKUP_DIR"
tar czf "microvm-backup-$DATE.tar.gz" "$DATE"
rm -rf "$DATE"

# Clean old backups (keep 7 days)
find "$BACKUP_DIR" -name "microvm-backup-*.tar.gz" -mtime +7 -delete

echo "Backup completed: microvm-backup-$DATE.tar.gz"
EOF

# Make executable
sudo chmod +x /usr/local/bin/microvm-backup.sh

# Add to cron
echo "0 2 * * * /usr/local/bin/microvm-backup.sh" | sudo crontab -
```

### 2. Recovery Procedures

```bash
# Stop service
sudo systemctl stop microvm-sandbox

# Restore configuration
sudo tar xzf microvm-backup-20251001-020000.tar.gz
sudo cp -r 20251001-020000/microvm-sandbox /etc/

# Restore database
# For SQLite:
sudo cp 20251001-020000/microvm.db /var/lib/microvm-sandbox/

# For PostgreSQL:
sudo -u postgres psql microvm_sandbox < 20251001-020000/database.sql

# Restore images and snapshots
sudo rsync -av 20251001-020000/images/ /var/lib/microvm-sandbox/images/
sudo rsync -av 20251001-020000/snapshots/ /var/lib/microvm-sandbox/snapshots/

# Fix permissions
sudo chown -R $USER:$USER /var/lib/microvm-sandbox

# Start service
sudo systemctl start microvm-sandbox
```

## Maintenance

### 1. System Updates

```bash
# Create update script
sudo tee /usr/local/bin/microvm-update.sh << 'EOF'
#!/bin/bash

# Stop service
systemctl stop microvm-sandbox

# Update system packages
apt update && apt upgrade -y

# Update Python packages
cd /opt/microvm-sandbox
source venv/bin/activate
pip install --upgrade -r requirements.txt

# Update Cloud Hypervisor if needed
# Check for new version and update

# Start service
systemctl start microvm-sandbox

# Check status
systemctl status microvm-sandbox
EOF

sudo chmod +x /usr/local/bin/microvm-update.sh
```

### 2. Health Checks

```bash
# Create health check script
sudo tee /usr/local/bin/microvm-health.sh << 'EOF'
#!/bin/bash

# Check service status
if ! systemctl is-active --quiet microvm-sandbox; then
    echo "CRITICAL: MicroVM Sandbox service is not running"
    exit 2
fi

# Check API health
if ! curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "CRITICAL: API health check failed"
    exit 2
fi

# Check disk space
DISK_USAGE=$(df /var/lib/microvm-sandbox | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 90 ]; then
    echo "WARNING: Disk usage is at ${DISK_USAGE}%"
    exit 1
fi

# Check memory usage
MEM_USAGE=$(free | grep Mem | awk '{printf "%.0f", ($3/$2)*100}')
if [ "$MEM_USAGE" -gt 90 ]; then
    echo "WARNING: Memory usage is at ${MEM_USAGE}%"
    exit 1
fi

echo "OK: All checks passed"
exit 0
EOF

sudo chmod +x /usr/local/bin/microvm-health.sh

# Add to cron for regular checks
echo "*/5 * * * * /usr/local/bin/microvm-health.sh" | crontab -
```

## Troubleshooting

### 1. Service Issues

```bash
# Check service status
sudo systemctl status microvm-sandbox

# View recent logs
sudo journalctl -u microvm-sandbox -n 50

# Follow logs in real-time
sudo journalctl -u microvm-sandbox -f

# Check configuration
python -m src.utils.config validate
```

### 2. Network Issues

```bash
# Check bridge network
ip link show chbr0
ip addr show chbr0

# Check iptables rules
sudo iptables -L
sudo iptables -t nat -L

# Test connectivity
ping 192.168.200.1
```

### 3. Performance Issues

```bash
# Check system resources
top
htop
iotop

# Check disk I/O
iostat -x 1

# Check network traffic
iftop
nethogs

# Check running VMs
curl http://localhost:8000/api/v1/vms
```

This bare metal deployment provides maximum performance and control, ideal for production environments where you need direct hardware access and optimal resource utilization.