# MicroVM Sandbox API Reference

This document provides a comprehensive reference for the MicroVM Sandbox REST API.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

The API uses JWT-based authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### Authentication Endpoints

#### POST /auth/register
Register a new user account.

**Request Body:**
```json
{
  "username": "string",
  "password": "string",
  "role": "user|admin"
}
```

**Response (201):**
```json
{
  "user_id": "string",
  "username": "string",
  "role": "string",
  "created_at": "2025-10-01T12:00:00Z"
}
```

#### POST /auth/login
Authenticate and receive JWT token.

**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response (200):**
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600
}
```

## Virtual Machine Management

### VM Lifecycle Operations

#### GET /vms
List all virtual machines.

**Query Parameters:**
- `status` (optional): Filter by VM status (`created`, `running`, `stopped`)
- `os_type` (optional): Filter by OS type (`linux`, `windows`)
- `limit` (optional): Maximum number of results (default: 50)
- `offset` (optional): Number of results to skip (default: 0)

**Response (200):**
```json
{
  "vms": [
    {
      "name": "string",
      "id": "string",
      "status": "created|running|stopped",
      "os_type": "linux|windows",
      "vcpus": 2,
      "memory_mb": 512,
      "created_at": "2025-10-01T12:00:00Z",
      "network_config": {
        "ip": "192.168.200.100",
        "bridge": "chbr0"
      }
    }
  ],
  "total": 10,
  "limit": 50,
  "offset": 0
}
```

#### POST /vms
Create a new virtual machine.

**Request Body:**
```json
{
  "name": "string",
  "os_type": "linux|windows",
  "vcpus": 2,
  "memory_mb": 512,
  "template": "linux-default|windows-default",
  "network_config": {
    "bridge": "chbr0",
    "ip": "192.168.200.100"
  },
  "storage_config": {
    "disk_size_gb": 10,
    "disk_type": "ssd"
  }
}
```

**Response (201):**
```json
{
  "name": "string",
  "id": "string",
  "status": "created",
  "os_type": "linux",
  "vcpus": 2,
  "memory_mb": 512,
  "created_at": "2025-10-01T12:00:00Z",
  "network_config": {
    "ip": "192.168.200.100",
    "bridge": "chbr0"
  }
}
```

#### GET /vms/{vm_name}
Get information about a specific virtual machine.

**Response (200):**
```json
{
  "name": "string",
  "id": "string",
  "status": "running",
  "os_type": "linux",
  "vcpus": 2,
  "memory_mb": 512,
  "created_at": "2025-10-01T12:00:00Z",
  "started_at": "2025-10-01T12:05:00Z",
  "uptime_seconds": 3600,
  "network_config": {
    "ip": "192.168.200.100",
    "bridge": "chbr0",
    "mac_address": "52:54:00:12:34:56"
  },
  "resource_usage": {
    "cpu_usage_percent": 15.2,
    "memory_used_mb": 256,
    "disk_usage_gb": 2.5
  }
}
```

#### POST /vms/{vm_name}/start
Start a virtual machine.

**Response (200):**
```json
{
  "message": "VM started successfully",
  "vm_name": "string",
  "status": "running",
  "started_at": "2025-10-01T12:05:00Z"
}
```

#### POST /vms/{vm_name}/stop
Stop a virtual machine gracefully.

**Request Body (optional):**
```json
{
  "force": false,
  "timeout_seconds": 30
}
```

**Response (200):**
```json
{
  "message": "VM stopped successfully",
  "vm_name": "string",
  "status": "stopped",
  "stopped_at": "2025-10-01T12:10:00Z"
}
```

#### POST /vms/{vm_name}/restart
Restart a virtual machine.

**Response (200):**
```json
{
  "message": "VM restarted successfully",
  "vm_name": "string",
  "status": "running",
  "restarted_at": "2025-10-01T12:15:00Z"
}
```

#### DELETE /vms/{vm_name}
Delete a virtual machine permanently.

**Response (204):** No content

### VM Command Execution

#### POST /vms/{vm_name}/execute
Execute a command in the virtual machine.

**Request Body:**
```json
{
  "command": "string",
  "timeout_seconds": 30,
  "working_directory": "/path/to/dir",
  "environment": {
    "VAR1": "value1",
    "VAR2": "value2"
  }
}
```

**Response (200):**
```json
{
  "exit_code": 0,
  "stdout": "command output",
  "stderr": "error output",
  "execution_time_seconds": 1.5,
  "command": "string",
  "executed_at": "2025-10-01T12:20:00Z"
}
```

### File Transfer Operations

#### POST /vms/{vm_name}/files/upload
Upload a file to the virtual machine.

**Request (multipart/form-data):**
- `file`: File to upload
- `path`: Target path in VM
- `permissions`: File permissions (optional, default: 644)

**Response (200):**
```json
{
  "message": "File uploaded successfully",
  "vm_name": "string",
  "remote_path": "/path/to/file",
  "size_bytes": 1024,
  "uploaded_at": "2025-10-01T12:25:00Z"
}
```

#### GET /vms/{vm_name}/files/download
Download a file from the virtual machine.

**Query Parameters:**
- `path`: Path to file in VM

**Response (200):** File content with appropriate headers

#### GET /vms/{vm_name}/files
List files in a directory on the virtual machine.

**Query Parameters:**
- `path`: Directory path (default: `/`)
- `recursive`: Include subdirectories (default: false)

**Response (200):**
```json
{
  "files": [
    {
      "name": "filename.txt",
      "path": "/path/to/filename.txt",
      "size_bytes": 1024,
      "is_directory": false,
      "permissions": "644",
      "modified_at": "2025-10-01T12:00:00Z"
    }
  ],
  "directory": "/path/to/dir"
}
```

## Snapshot Management

#### GET /vms/{vm_name}/snapshots
List snapshots for a virtual machine.

**Response (200):**
```json
{
  "snapshots": [
    {
      "name": "string",
      "vm_name": "string",
      "created_at": "2025-10-01T12:00:00Z",
      "size_bytes": 1073741824,
      "description": "string",
      "metadata": {
        "vm_status": "running",
        "vcpus": 2,
        "memory_mb": 512
      }
    }
  ]
}
```

#### POST /vms/{vm_name}/snapshots
Create a new snapshot.

**Request Body:**
```json
{
  "name": "string",
  "description": "string",
  "include_memory": true
}
```

**Response (201):**
```json
{
  "name": "string",
  "vm_name": "string",
  "created_at": "2025-10-01T12:30:00Z",
  "size_bytes": 1073741824,
  "description": "string",
  "checksum": "sha256:abc123..."
}
```

#### POST /vms/{vm_name}/snapshots/{snapshot_name}/restore
Restore VM from a snapshot.

**Response (200):**
```json
{
  "message": "VM restored successfully",
  "vm_name": "string",
  "snapshot_name": "string",
  "restored_at": "2025-10-01T12:35:00Z"
}
```

#### DELETE /vms/{vm_name}/snapshots/{snapshot_name}
Delete a snapshot.

**Response (204):** No content

## Resource Management

#### GET /vms/{vm_name}/metrics
Get resource usage metrics for a VM.

**Response (200):**
```json
{
  "vm_name": "string",
  "timestamp": "2025-10-01T12:40:00Z",
  "cpu": {
    "usage_percent": 15.2,
    "vcpus": 2,
    "cpu_time_seconds": 3600
  },
  "memory": {
    "allocated_mb": 512,
    "used_mb": 256,
    "usage_percent": 50.0,
    "available_mb": 256
  },
  "disk": {
    "allocated_gb": 10,
    "used_gb": 2.5,
    "usage_percent": 25.0,
    "available_gb": 7.5
  },
  "network": {
    "bytes_in": 1048576,
    "bytes_out": 2097152,
    "packets_in": 1024,
    "packets_out": 2048
  }
}
```

#### PUT /vms/{vm_name}/resources
Update VM resource allocation.

**Request Body:**
```json
{
  "vcpus": 4,
  "memory_mb": 1024,
  "cpu_limit_percent": 80,
  "memory_limit_percent": 90
}
```

**Response (200):**
```json
{
  "message": "Resources updated successfully",
  "vm_name": "string",
  "updated_at": "2025-10-01T12:45:00Z",
  "new_resources": {
    "vcpus": 4,
    "memory_mb": 1024
  }
}
```

#### GET /system/metrics
Get host system metrics.

**Response (200):**
```json
{
  "timestamp": "2025-10-01T12:50:00Z",
  "host": {
    "cpu_usage_percent": 45.2,
    "cpu_cores": 8,
    "memory_total_gb": 32,
    "memory_used_gb": 16,
    "memory_usage_percent": 50.0,
    "disk_total_gb": 500,
    "disk_used_gb": 200,
    "disk_usage_percent": 40.0
  },
  "vms": {
    "total_count": 5,
    "running_count": 3,
    "total_vcpus_allocated": 10,
    "total_memory_allocated_gb": 4
  }
}
```

## Network Management

#### GET /networks
List network configurations.

**Response (200):**
```json
{
  "networks": [
    {
      "name": "chbr0",
      "type": "bridge",
      "subnet": "192.168.200.0/24",
      "gateway": "192.168.200.1",
      "dhcp_enabled": true,
      "vms_connected": 3
    }
  ]
}
```

#### GET /vms/{vm_name}/network
Get network information for a VM.

**Response (200):**
```json
{
  "vm_name": "string",
  "ip_address": "192.168.200.100",
  "mac_address": "52:54:00:12:34:56",
  "bridge_name": "chbr0",
  "network_interface": "tap0",
  "connectivity_status": "connected",
  "port_forwards": [
    {
      "host_port": 8080,
      "guest_port": 80,
      "protocol": "tcp"
    }
  ]
}
```

#### POST /vms/{vm_name}/network/port-forward
Configure port forwarding for a VM.

**Request Body:**
```json
{
  "host_port": 8080,
  "guest_port": 80,
  "protocol": "tcp|udp",
  "description": "Web server"
}
```

**Response (201):**
```json
{
  "message": "Port forward configured",
  "vm_name": "string",
  "host_port": 8080,
  "guest_port": 80,
  "protocol": "tcp"
}
```

## Security Management

#### GET /security/audit-logs
Get audit logs.

**Query Parameters:**
- `start_time`: Start timestamp (ISO 8601)
- `end_time`: End timestamp (ISO 8601)
- `action_type`: Filter by action type
- `resource_type`: Filter by resource type
- `user_id`: Filter by user ID
- `limit`: Maximum results (default: 100)

**Response (200):**
```json
{
  "logs": [
    {
      "timestamp": "2025-10-01T12:55:00Z",
      "action_type": "vm_create",
      "resource_type": "vm",
      "resource_id": "test-vm",
      "user_id": "user123",
      "source_ip": "192.168.1.100",
      "details": {
        "vm_config": {
          "vcpus": 2,
          "memory_mb": 512
        }
      },
      "compliance_frameworks": ["SOC2", "ISO27001"]
    }
  ],
  "total": 1000,
  "limit": 100
}
```

#### POST /security/scan
Initiate security scan.

**Request Body:**
```json
{
  "scan_type": "vulnerability|compliance|configuration",
  "target": "vm_name|all",
  "frameworks": ["SOC2", "HIPAA", "PCI_DSS"]
}
```

**Response (202):**
```json
{
  "scan_id": "string",
  "status": "started",
  "started_at": "2025-10-01T13:00:00Z",
  "estimated_completion": "2025-10-01T13:30:00Z"
}
```

#### GET /security/scans/{scan_id}
Get security scan results.

**Response (200):**
```json
{
  "scan_id": "string",
  "status": "completed",
  "started_at": "2025-10-01T13:00:00Z",
  "completed_at": "2025-10-01T13:25:00Z",
  "scan_type": "vulnerability",
  "results": {
    "total_checks": 150,
    "passed": 140,
    "failed": 8,
    "warnings": 2,
    "risk_score": 85,
    "findings": [
      {
        "severity": "medium",
        "category": "configuration",
        "description": "SSH root login enabled",
        "recommendation": "Disable root SSH access",
        "affected_resource": "vm-name"
      }
    ]
  }
}
```

## Health and Status

#### GET /health
Health check endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-01T13:30:00Z",
  "version": "1.0.0",
  "components": {
    "api": "healthy",
    "database": "healthy",
    "cloud_hypervisor": "healthy",
    "network": "healthy"
  },
  "uptime_seconds": 86400
}
```

#### GET /status
Detailed system status.

**Response (200):**
```json
{
  "api_version": "1.0.0",
  "timestamp": "2025-10-01T13:35:00Z",
  "system": {
    "host_os": "Ubuntu 22.04",
    "cloud_hypervisor_version": "34.0",
    "python_version": "3.11.0"
  },
  "statistics": {
    "total_vms": 10,
    "running_vms": 7,
    "total_snapshots": 25,
    "api_requests_today": 5432,
    "average_response_time_ms": 45
  }
}
```

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "error": "bad_request",
  "message": "Invalid request parameters",
  "details": {
    "field": "vcpus",
    "issue": "must be between 1 and 16"
  }
}
```

### 401 Unauthorized
```json
{
  "error": "unauthorized",
  "message": "Authentication required"
}
```

### 403 Forbidden
```json
{
  "error": "forbidden",
  "message": "Insufficient permissions"
}
```

### 404 Not Found
```json
{
  "error": "not_found",
  "message": "VM 'test-vm' not found"
}
```

### 409 Conflict
```json
{
  "error": "conflict",
  "message": "VM 'test-vm' already exists"
}
```

### 422 Unprocessable Entity
```json
{
  "error": "validation_error",
  "message": "Request validation failed",
  "details": [
    {
      "field": "memory_mb",
      "error": "must be at least 128"
    }
  ]
}
```

### 429 Too Many Requests
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests",
  "retry_after_seconds": 60
}
```

### 500 Internal Server Error
```json
{
  "error": "internal_error",
  "message": "An unexpected error occurred",
  "request_id": "req_123456789"
}
```

### 503 Service Unavailable
```json
{
  "error": "service_unavailable",
  "message": "Cloud Hypervisor service unavailable"
}
```

## Rate Limiting

The API implements rate limiting to ensure fair usage:

- **Default limit**: 1000 requests per hour per user
- **Burst limit**: 100 requests per minute
- **Headers included in responses**:
  - `X-RateLimit-Limit`: Total limit
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Reset timestamp

## Pagination

List endpoints support pagination:

- `limit`: Maximum number of results (1-100, default: 50)
- `offset`: Number of results to skip (default: 0)

Example:
```
GET /api/v1/vms?limit=25&offset=50
```

## Filtering and Sorting

Many list endpoints support filtering and sorting:

**Filtering:**
```
GET /api/v1/vms?status=running&os_type=linux
```

**Sorting:**
```
GET /api/v1/vms?sort=created_at&order=desc
```

## WebSocket Endpoints

### Real-time VM Status Updates

#### WS /vms/{vm_name}/events
Subscribe to real-time events for a specific VM.

**Messages:**
```json
{
  "event_type": "status_change",
  "vm_name": "test-vm",
  "timestamp": "2025-10-01T14:00:00Z",
  "data": {
    "old_status": "stopped",
    "new_status": "running"
  }
}
```

#### WS /system/events
Subscribe to system-wide events.

**Messages:**
```json
{
  "event_type": "vm_created",
  "timestamp": "2025-10-01T14:05:00Z",
  "data": {
    "vm_name": "new-vm",
    "user_id": "user123"
  }
}
```