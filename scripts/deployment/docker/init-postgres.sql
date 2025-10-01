-- Initialize MicroVM Sandbox database schema

-- Create extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- VM state management table
CREATE TABLE IF NOT EXISTS vm_instances (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) UNIQUE NOT NULL,
    os_type VARCHAR(50) NOT NULL CHECK (os_type IN ('linux', 'windows')),
    state VARCHAR(50) NOT NULL DEFAULT 'stopped',
    vcpus INTEGER NOT NULL DEFAULT 2,
    memory_mb INTEGER NOT NULL DEFAULT 1024,
    disk_size_gb INTEGER DEFAULT 10,
    template_name VARCHAR(255),
    config JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_boot_time TIMESTAMP WITH TIME ZONE,
    boot_time_ms INTEGER,
    network_config JSONB,
    resource_allocation JSONB
);

-- Snapshots table
CREATE TABLE IF NOT EXISTS vm_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vm_id UUID NOT NULL REFERENCES vm_instances(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    file_path TEXT NOT NULL,
    file_size_bytes BIGINT,
    checksum VARCHAR(64),
    parent_snapshot_id UUID REFERENCES vm_snapshots(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB,
    UNIQUE(vm_id, name)
);

-- Resource allocations table
CREATE TABLE IF NOT EXISTS resource_allocations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vm_id UUID NOT NULL REFERENCES vm_instances(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    cpu_cores DECIMAL(4,2) NOT NULL,
    memory_mb INTEGER NOT NULL,
    disk_mb INTEGER NOT NULL,
    network_bandwidth_mbps INTEGER DEFAULT 100,
    allocated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deallocated_at TIMESTAMP WITH TIME ZONE,
    priority INTEGER DEFAULT 0,
    quota_limits JSONB
);

-- Network configurations table
CREATE TABLE IF NOT EXISTS network_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vm_id UUID NOT NULL REFERENCES vm_instances(id) ON DELETE CASCADE,
    interface_name VARCHAR(50) NOT NULL,
    ip_address INET,
    mac_address MACADDR,
    bridge_name VARCHAR(50),
    port_forwards JSONB,
    firewall_rules JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Audit logs table for compliance
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    user_id VARCHAR(255),
    vm_id UUID REFERENCES vm_instances(id),
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    correlation_id UUID,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    compliance_frameworks TEXT[]
);

-- Users and authentication table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    permissions TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    quota_limits JSONB
);

-- Session management table
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT,
    revoked BOOLEAN DEFAULT FALSE
);

-- Metrics storage for time-series data
CREATE TABLE IF NOT EXISTS vm_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vm_id UUID NOT NULL REFERENCES vm_instances(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,6) NOT NULL,
    metric_unit VARCHAR(20),
    labels JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Security events table
CREATE TABLE IF NOT EXISTS security_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    source_ip INET,
    target_resource VARCHAR(255),
    details JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by VARCHAR(255)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_vm_instances_state ON vm_instances(state);
CREATE INDEX IF NOT EXISTS idx_vm_instances_created_at ON vm_instances(created_at);
CREATE INDEX IF NOT EXISTS idx_vm_snapshots_vm_id ON vm_snapshots(vm_id);
CREATE INDEX IF NOT EXISTS idx_vm_snapshots_created_at ON vm_snapshots(created_at);
CREATE INDEX IF NOT EXISTS idx_resource_allocations_user_id ON resource_allocations(user_id);
CREATE INDEX IF NOT EXISTS idx_resource_allocations_vm_id ON resource_allocations(vm_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token_hash ON user_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_vm_metrics_vm_id ON vm_metrics(vm_id);
CREATE INDEX IF NOT EXISTS idx_vm_metrics_timestamp ON vm_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_security_events_timestamp ON security_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_security_events_severity ON security_events(severity);

-- Create update trigger for updated_at columns
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_vm_instances_updated_at 
    BEFORE UPDATE ON vm_instances 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_network_configs_updated_at 
    BEFORE UPDATE ON network_configs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create default admin user (password: admin123!)
INSERT INTO users (username, email, password_hash, role, permissions) 
VALUES (
    'admin', 
    'admin@microvm.local', 
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeVMDZe6Y0ZCm1b.S', -- admin123!
    'admin', 
    ARRAY['vm:*', 'user:*', 'system:*', 'security:*']
) ON CONFLICT (username) DO NOTHING;

-- Grant permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO microvm;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO microvm;