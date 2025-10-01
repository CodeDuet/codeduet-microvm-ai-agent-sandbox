# Docker Deployment Guide

This guide covers deploying the MicroVM Sandbox using Docker containers.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Host with KVM support
- 8GB+ RAM, 4+ CPU cores

## Quick Start

### 1. Pull the Official Image

```bash
# Pull the latest stable release
docker pull microvm-sandbox:latest

# Or pull a specific version
docker pull microvm-sandbox:v1.0.0
```

### 2. Run with Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  microvm-sandbox:
    image: microvm-sandbox:latest
    container_name: microvm-sandbox
    privileged: true
    restart: unless-stopped
    ports:
      - "8000:8000"
      - "9090:9090"  # Prometheus metrics
    volumes:
      - /dev/kvm:/dev/kvm
      - ./config:/app/config
      - ./data:/var/lib/microvm-sandbox
      - ./logs:/var/log/microvm-sandbox
      - vm_images:/app/images
    environment:
      - LOG_LEVEL=INFO
      - CONFIG_PATH=/app/config/config.yaml
    networks:
      - microvm-net

  redis:
    image: redis:7-alpine
    container_name: microvm-redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    networks:
      - microvm-net

  postgres:
    image: postgres:15-alpine
    container_name: microvm-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: microvm_sandbox
      POSTGRES_USER: microvm
      POSTGRES_PASSWORD: secure_password_here
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - microvm-net

volumes:
  vm_images:
  redis_data:
  postgres_data:

networks:
  microvm-net:
    driver: bridge
```

### 3. Start the Services

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f microvm-sandbox
```

## Building from Source

### 1. Clone Repository

```bash
git clone https://github.com/your-org/microvm-sandbox.git
cd microvm-sandbox
```

### 2. Build Image

```bash
# Build with default settings
docker build -t microvm-sandbox:local .

# Build with custom configuration
docker build \
  --build-arg PYTHON_VERSION=3.11 \
  --build-arg CLOUD_HYPERVISOR_VERSION=34.0 \
  -t microvm-sandbox:custom .
```

### 3. Multi-stage Build

The Dockerfile uses multi-stage builds for optimization:

```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Install Cloud Hypervisor
ARG CLOUD_HYPERVISOR_VERSION=34.0
RUN curl -L https://github.com/cloud-hypervisor/cloud-hypervisor/releases/download/v${CLOUD_HYPERVISOR_VERSION}/cloud-hypervisor-static \
    -o /usr/local/bin/cloud-hypervisor && \
    chmod +x /usr/local/bin/cloud-hypervisor

# Runtime stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    kvm \
    qemu-utils \
    bridge-utils \
    iptables \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Copy built dependencies
COPY --from=builder /root/.local /root/.local
COPY --from=builder /usr/local/bin/cloud-hypervisor /usr/local/bin/

# Create user and directories
RUN useradd -m -s /bin/bash microvm && \
    usermod -a -G kvm microvm && \
    mkdir -p /var/lib/microvm-sandbox /var/log/microvm-sandbox

# Copy application code
COPY src/ /app/src/
COPY config/ /app/config/
COPY scripts/ /app/scripts/

WORKDIR /app

# Set environment variables
ENV PATH="/root/.local/bin:$PATH"
ENV PYTHONPATH="/app"

# Expose ports
EXPOSE 8000 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
  CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["python", "-m", "uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Configuration

### 1. Environment Variables

```bash
# Core configuration
export CONFIG_PATH="/app/config/config.yaml"
export LOG_LEVEL="INFO"
export DEBUG_MODE="false"

# Database configuration
export DATABASE_URL="postgresql://microvm:password@postgres:5432/microvm_sandbox"
export REDIS_URL="redis://redis:6379/0"

# Security configuration
export JWT_SECRET_KEY="your-secret-key-here"
export ENCRYPTION_KEY="your-encryption-key-here"

# Cloud Hypervisor configuration
export CH_BINARY_PATH="/usr/local/bin/cloud-hypervisor"
export CH_SOCKET_DIR="/tmp/ch-sockets"

# Networking configuration
export BRIDGE_NAME="docker0"
export VM_SUBNET="172.20.0.0/16"
```

### 2. Volume Mounts

Essential volumes for persistent data:

```yaml
volumes:
  # KVM device access (required)
  - /dev/kvm:/dev/kvm

  # Configuration files
  - ./config:/app/config:ro

  # Persistent data
  - ./data:/var/lib/microvm-sandbox

  # Logs
  - ./logs:/var/log/microvm-sandbox

  # VM images
  - vm_images:/app/images

  # Snapshots
  - ./snapshots:/var/lib/microvm-sandbox/snapshots

  # Temporary files
  - ./tmp:/tmp
```

### 3. Network Configuration

```yaml
# Custom network for better isolation
networks:
  microvm-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
          gateway: 172.20.0.1
```

## Production Deployment

### 1. Docker Swarm

```yaml
# docker-stack.yml
version: '3.8'

services:
  microvm-sandbox:
    image: microvm-sandbox:latest
    deploy:
      replicas: 3
      placement:
        constraints:
          - node.labels.kvm == true
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
    ports:
      - "8000:8000"
    volumes:
      - /dev/kvm:/dev/kvm
      - config:/app/config
      - data:/var/lib/microvm-sandbox
    networks:
      - microvm-net
    secrets:
      - jwt_secret
      - db_password

  nginx:
    image: nginx:alpine
    deploy:
      replicas: 2
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    networks:
      - microvm-net

secrets:
  jwt_secret:
    external: true
  db_password:
    external: true

volumes:
  config:
  data:

networks:
  microvm-net:
    driver: overlay
    attachable: true
```

Deploy the stack:

```bash
# Create secrets
echo "your-jwt-secret" | docker secret create jwt_secret -
echo "your-db-password" | docker secret create db_password -

# Deploy stack
docker stack deploy -c docker-stack.yml microvm-sandbox

# Check services
docker service ls
docker stack ps microvm-sandbox
```

### 2. High Availability Setup

```yaml
# ha-docker-compose.yml
version: '3.8'

services:
  # Load balancer
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx-ha.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - microvm-sandbox-1
      - microvm-sandbox-2

  # Primary instance
  microvm-sandbox-1:
    image: microvm-sandbox:latest
    privileged: true
    hostname: microvm-1
    volumes:
      - /dev/kvm:/dev/kvm
      - ./config:/app/config
      - data1:/var/lib/microvm-sandbox
    environment:
      - INSTANCE_ID=1
      - HA_MODE=true
      - HA_PEER=microvm-sandbox-2

  # Secondary instance
  microvm-sandbox-2:
    image: microvm-sandbox:latest
    privileged: true
    hostname: microvm-2
    volumes:
      - /dev/kvm:/dev/kvm
      - ./config:/app/config
      - data2:/var/lib/microvm-sandbox
    environment:
      - INSTANCE_ID=2
      - HA_MODE=true
      - HA_PEER=microvm-sandbox-1

  # Shared database
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: microvm_sandbox
      POSTGRES_USER: microvm
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # Redis for session storage
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

volumes:
  data1:
  data2:
  postgres_data:
  redis_data:
```

### 3. Monitoring and Logging

```yaml
# monitoring-docker-compose.yml
version: '3.8'

services:
  # Prometheus for metrics
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  # Grafana for dashboards
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

  # ELK Stack for logging
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.5.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data

  logstash:
    image: docker.elastic.co/logstash/logstash:8.5.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:8.5.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch

volumes:
  prometheus_data:
  grafana_data:
  elasticsearch_data:
```

## Security Hardening

### 1. Non-Root User

```dockerfile
# Run as non-root user
RUN useradd -m -u 1000 microvm && \
    usermod -a -G kvm microvm

USER microvm
```

### 2. Security Context

```yaml
# docker-compose.yml
services:
  microvm-sandbox:
    image: microvm-sandbox:latest
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_ADMIN
      - SYS_ADMIN  # Required for KVM
    read_only: true
    tmpfs:
      - /tmp
      - /var/tmp
```

### 3. Network Security

```yaml
# Restrict network access
services:
  microvm-sandbox:
    networks:
      microvm-net:
        ipv4_address: 172.20.0.10
    ports:
      - "127.0.0.1:8000:8000"  # Bind only to localhost

networks:
  microvm-net:
    driver: bridge
    internal: true  # No external access
```

## Maintenance and Updates

### 1. Rolling Updates

```bash
# Update to new version
docker-compose pull microvm-sandbox

# Rolling update with zero downtime
docker-compose up -d --no-deps microvm-sandbox

# Verify update
docker-compose exec microvm-sandbox curl http://localhost:8000/health
```

### 2. Backup and Restore

```bash
# Backup script
#!/bin/bash
BACKUP_DIR="/backup/$(date +%Y%m%d-%H%M%S)"
mkdir -p $BACKUP_DIR

# Backup data volumes
docker run --rm -v microvm_data:/data -v $BACKUP_DIR:/backup \
  alpine tar czf /backup/data.tar.gz -C /data .

# Backup database
docker-compose exec postgres pg_dump -U microvm microvm_sandbox > $BACKUP_DIR/database.sql

# Backup configuration
cp -r ./config $BACKUP_DIR/
```

### 3. Health Monitoring

```bash
# Health check script
#!/bin/bash
CONTAINER_NAME="microvm-sandbox"

# Check container status
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo "Container $CONTAINER_NAME is not running"
    docker-compose restart $CONTAINER_NAME
fi

# Check API health
if ! curl -f http://localhost:8000/health; then
    echo "API health check failed"
    docker-compose restart $CONTAINER_NAME
fi

# Check resource usage
MEMORY_USAGE=$(docker stats --no-stream --format "{{.MemPerc}}" $CONTAINER_NAME | sed 's/%//')
if (( $(echo "$MEMORY_USAGE > 90" | bc -l) )); then
    echo "High memory usage: ${MEMORY_USAGE}%"
    # Send alert
fi
```

## Troubleshooting

### 1. Common Issues

**Container won't start:**
```bash
# Check logs
docker-compose logs microvm-sandbox

# Check permissions
ls -la /dev/kvm
groups $(whoami)
```

**KVM not accessible:**
```bash
# Ensure KVM module is loaded
sudo modprobe kvm
sudo modprobe kvm_intel  # or kvm_amd

# Check device permissions
sudo chmod 666 /dev/kvm
```

**Network issues:**
```bash
# Check bridge network
docker network ls
docker network inspect microvm_microvm-net

# Restart networking
docker-compose down
docker-compose up -d
```

### 2. Debug Mode

```yaml
# Enable debug mode
services:
  microvm-sandbox:
    environment:
      - LOG_LEVEL=DEBUG
      - DEBUG_MODE=true
    volumes:
      - ./debug:/app/debug
```

### 3. Performance Tuning

```yaml
# Optimize for performance
services:
  microvm-sandbox:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
    sysctls:
      - net.core.somaxconn=65535
      - net.ipv4.ip_local_port_range=1024 65535
    ulimits:
      nofile:
        soft: 65535
        hard: 65535
```

## Best Practices

1. **Use specific image tags** instead of `latest` in production
2. **Set resource limits** to prevent resource exhaustion
3. **Use health checks** for automatic recovery
4. **Implement monitoring** and alerting
5. **Regular backups** of data and configuration
6. **Keep images updated** for security patches
7. **Use secrets management** for sensitive data
8. **Network isolation** for security
9. **Log rotation** to prevent disk space issues
10. **Test disaster recovery** procedures regularly