# MicroVM Sandbox Production Dockerfile
FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CLOUD_HYPERVISOR_VERSION=34.0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    curl \
    wget \
    git \
    kvm \
    qemu-kvm \
    libvirt-daemon-system \
    libvirt-clients \
    bridge-utils \
    iptables \
    iproute2 \
    net-tools \
    socat \
    jq \
    ca-certificates \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Create app user and directories
RUN useradd -m -u 1000 microvm && \
    mkdir -p /app /app/data /app/logs /app/snapshots /app/images && \
    chown -R microvm:microvm /app

# Install Cloud Hypervisor
RUN curl -L https://github.com/cloud-hypervisor/cloud-hypervisor/releases/download/v${CLOUD_HYPERVISOR_VERSION}/cloud-hypervisor-static -o /usr/local/bin/cloud-hypervisor && \
    chmod +x /usr/local/bin/cloud-hypervisor

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/setup/ ./scripts/setup/

# Copy startup script
COPY scripts/deployment/docker/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Set up proper permissions
RUN chown -R microvm:microvm /app

# Create necessary directories with proper permissions
RUN mkdir -p /var/lib/microvm /var/log/microvm /tmp/ch-sockets && \
    chown -R microvm:microvm /var/lib/microvm /var/log/microvm /tmp/ch-sockets

# Switch to app user
USER microvm

# Expose ports
EXPOSE 8000 9090 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

# Set entrypoint
ENTRYPOINT ["./entrypoint.sh"]
CMD ["server"]