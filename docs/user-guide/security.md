# Security Guide

This guide covers security features, configuration, and best practices for the MicroVM Sandbox.

## Security Overview

The MicroVM Sandbox provides enterprise-grade security with multiple layers of protection:

- **Hardware-level isolation** via KVM hypervisor
- **Network isolation** with separate namespaces
- **Authentication and authorization** with JWT and RBAC
- **Audit logging** for compliance and monitoring
- **Input validation** and sanitization
- **Encrypted storage** for sensitive data

## Authentication and Authorization

### JWT Authentication

The system uses JSON Web Tokens (JWT) for secure API access:

```bash
# Register a new user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "SecurePassword123!",
    "role": "admin"
  }'

# Login and get token
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "SecurePassword123!"
  }' | jq -r '.access_token')

# Use token for API requests
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/vms
```

### Role-Based Access Control (RBAC)

Available roles and permissions:

- **Admin**: Full system access including user management
- **User**: VM creation, management, and monitoring
- **Viewer**: Read-only access to system status

## Network Security

### VM Isolation

Each VM is isolated at multiple levels:

```yaml
# Network isolation configuration
networking:
  bridge_name: "chbr0"
  vm_isolation: true
  firewall_rules:
    - action: "ACCEPT"
      source: "192.168.200.0/24"
      destination: "0.0.0.0/0"
    - action: "DROP"
      source: "0.0.0.0/0"
      destination: "192.168.200.0/24"
```

### Firewall Configuration

```bash
# View current firewall rules
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/security/firewall/rules

# Add firewall rule
curl -X POST http://localhost:8000/api/v1/security/firewall/rules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "block-external",
    "action": "DROP",
    "source": "0.0.0.0/0",
    "destination": "192.168.200.0/24",
    "port": "22"
  }'
```

## Compliance and Audit Logging

### Supported Compliance Frameworks

- **SOC 2** - Security, availability, processing integrity
- **ISO 27001** - Information security management
- **HIPAA** - Healthcare data protection
- **PCI DSS** - Payment card data security
- **GDPR** - Data protection and privacy

### Audit Log Configuration

```yaml
security:
  audit_logging:
    enabled: true
    retention_days: 2555  # 7 years for compliance
    log_level: "INFO"
    include_request_data: true
    frameworks:
      - "SOC2"
      - "ISO27001"
      - "HIPAA"
```

### Viewing Audit Logs

```bash
# Get audit logs
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/security/audit-logs?start_time=2025-10-01T00:00:00Z&end_time=2025-10-01T23:59:59Z"

# Filter by action type
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/security/audit-logs?action_type=vm_create"

# Get compliance report
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/security/compliance/report
```

## Vulnerability Management

### Security Scanning

```bash
# Run vulnerability scan
curl -X POST http://localhost:8000/api/v1/security/scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scan_type": "vulnerability",
    "target": "all",
    "frameworks": ["SOC2", "ISO27001"]
  }'

# Check scan results
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/security/scans/{scan_id}
```

### Security Policies

```bash
# Update security policy
curl -X PUT http://localhost:8000/api/v1/security/policy \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "password_policy": {
      "min_length": 12,
      "require_uppercase": true,
      "require_lowercase": true,
      "require_numbers": true,
      "require_symbols": true
    },
    "session_policy": {
      "timeout_minutes": 60,
      "max_sessions_per_user": 3
    }
  }'
```

## Best Practices

### 1. Authentication
- Use strong passwords (12+ characters with mixed case, numbers, symbols)
- Implement multi-factor authentication where possible
- Rotate passwords regularly
- Use service accounts for automated access

### 2. Network Security
- Enable VM isolation for production environments
- Use firewalls to restrict unnecessary network access
- Monitor network traffic for anomalies
- Implement network segmentation

### 3. Access Control
- Follow principle of least privilege
- Regularly review user permissions
- Use role-based access control (RBAC)
- Implement just-in-time access where possible

### 4. Monitoring and Logging
- Enable comprehensive audit logging
- Monitor for security events and anomalies
- Set up alerts for suspicious activities
- Regularly review audit logs

### 5. System Hardening
- Keep all components updated
- Disable unnecessary services
- Use secure configurations
- Implement defense in depth

## Security Configuration Examples

### Production Security Configuration

```yaml
security:
  enable_authentication: true
  jwt_secret_key: "your-256-bit-secret-key"
  password_policy:
    min_length: 12
    require_uppercase: true
    require_lowercase: true
    require_numbers: true
    require_symbols: true
  session_timeout_minutes: 60
  max_failed_login_attempts: 5
  account_lockout_duration_minutes: 30
  api_rate_limiting:
    enabled: true
    requests_per_minute: 100
  vm_isolation: true
  audit_logging:
    enabled: true
    retention_days: 2555
    include_request_data: true
```

### High Security Environment

```yaml
security:
  enable_authentication: true
  require_mfa: true
  jwt_secret_key: "your-512-bit-secret-key"
  password_policy:
    min_length: 16
    require_uppercase: true
    require_lowercase: true
    require_numbers: true
    require_symbols: true
    no_dictionary_words: true
  session_timeout_minutes: 30
  max_failed_login_attempts: 3
  account_lockout_duration_minutes: 60
  api_rate_limiting:
    enabled: true
    requests_per_minute: 50
  vm_isolation: true
  network_encryption: true
  storage_encryption: true
  audit_logging:
    enabled: true
    retention_days: 3650  # 10 years
    include_request_data: true
    include_response_data: true
```

## Incident Response

### Security Event Detection

Monitor for these security events:

- Multiple failed login attempts
- Unusual API access patterns
- VM creation outside business hours
- Privilege escalation attempts
- Network scanning activities

### Response Procedures

1. **Immediate Response**
   - Isolate affected systems
   - Preserve evidence
   - Notify security team

2. **Investigation**
   - Review audit logs
   - Analyze network traffic
   - Check system integrity

3. **Recovery**
   - Remove threat
   - Restore from clean backups
   - Update security measures

4. **Post-Incident**
   - Document incident
   - Update procedures
   - Implement improvements

## Compliance Reporting

### Generating Reports

```bash
# SOC 2 compliance report
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/security/compliance/soc2"

# HIPAA compliance report
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/security/compliance/hipaa"

# Custom compliance report
curl -X POST http://localhost:8000/api/v1/security/compliance/report \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "frameworks": ["SOC2", "ISO27001"],
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "include_evidence": true
  }'
```

For additional security information, see:
- [API Security Reference](../api/reference.md#security-management)
- [Deployment Security](../deployment/bare-metal.md#security-hardening)
- [Troubleshooting Security Issues](troubleshooting.md#authentication-and-authorization-issues)