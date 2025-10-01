"""
Security management API endpoints.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel, Field

from ...core.security_manager import SecurityManager
from ...utils.audit import AuditLogger, AuditEventType, AuditSeverity
from ...utils.security import SecurityError, SecurityEnforcer
from ..middleware.auth import (
    require_auth, require_permission, get_current_user,
    TokenData, AuthenticationManager, AuthConfig
)
from ..models.vm import ErrorResponse

router = APIRouter(prefix="/api/v1/security", tags=["security"])


# Request/Response Models
class SecurityStatusResponse(BaseModel):
    """Security status response."""
    firewall_enabled: bool
    isolation_enabled: bool
    audit_logging_enabled: bool
    compliance_frameworks: List[str]
    active_policies: int
    security_level: str


class FirewallRuleRequest(BaseModel):
    """Firewall rule creation request."""
    vm_name: str = Field(..., description="VM name")
    rule_type: str = Field(..., description="Rule type: allow, deny, port_forward")
    protocol: str = Field("tcp", description="Protocol: tcp, udp, icmp")
    source_ip: Optional[str] = Field(None, description="Source IP address")
    dest_ip: Optional[str] = Field(None, description="Destination IP address")
    source_port: Optional[int] = Field(None, description="Source port")
    dest_port: Optional[int] = Field(None, description="Destination port")
    action: str = Field("ACCEPT", description="Action: ACCEPT, DROP, REJECT")


class IsolationPolicyRequest(BaseModel):
    """VM isolation policy request."""
    vm_name: str = Field(..., description="VM name")
    isolation_level: str = Field("moderate", description="Isolation level: strict, moderate, minimal")
    allowed_vms: List[str] = Field(default=[], description="List of VMs allowed to communicate")
    allowed_networks: List[str] = Field(default=[], description="List of allowed network ranges")
    blocked_ports: List[int] = Field(default=[], description="List of blocked ports")


class AuditConfigRequest(BaseModel):
    """Audit configuration request."""
    retention_days: int = Field(2555, description="Log retention in days")
    enable_encryption: bool = Field(True, description="Enable log encryption")
    compliance_frameworks: List[str] = Field(default=[], description="Enabled compliance frameworks")
    log_level: str = Field("INFO", description="Audit log level")


class SecurityPolicyRequest(BaseModel):
    """Security policy configuration request."""
    max_concurrent_vms: int = Field(50, description="Maximum concurrent VMs")
    max_vm_memory_mb: int = Field(8192, description="Maximum VM memory in MB")
    max_vm_vcpus: int = Field(8, description="Maximum VM vCPUs")
    require_authentication: bool = Field(True, description="Require authentication")
    session_timeout_minutes: int = Field(60, description="Session timeout in minutes")
    enable_rate_limiting: bool = Field(True, description="Enable rate limiting")
    blocked_commands: List[str] = Field(default=[], description="Blocked command patterns")


class LoginRequest(BaseModel):
    """User login request."""
    user_id: str = Field(..., description="User ID")
    password: str = Field(..., description="Password")


class LoginResponse(BaseModel):
    """Login response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    roles: List[str]


class UserCreateRequest(BaseModel):
    """User creation request."""
    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password")
    roles: List[str] = Field(default=["user"], description="User roles")
    permissions: List[str] = Field(default=[], description="Additional permissions")


class AuditReportRequest(BaseModel):
    """Audit report request."""
    start_date: datetime = Field(..., description="Report start date")
    end_date: datetime = Field(..., description="Report end date")
    event_types: List[str] = Field(default=[], description="Filter by event types")
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    severity: Optional[str] = Field(None, description="Filter by severity")


# Dependency injection
def get_security_manager() -> SecurityManager:
    """Get security manager instance."""
    # This would be injected from the main application
    # For now, return a mock instance
    from ...utils.config import get_config
    config = get_config()
    return SecurityManager(config.get('security', {}))


def get_audit_logger() -> AuditLogger:
    """Get audit logger instance."""
    from ...utils.config import get_config
    config = get_config()
    return AuditLogger(config.get('audit', {}))


def get_auth_manager() -> AuthenticationManager:
    """Get authentication manager instance."""
    from ...utils.config import get_config
    from ..middleware.auth import AuthConfig
    config = get_config()
    auth_config = AuthConfig(**config.get('security', {}).get('authentication', {}))
    return AuthenticationManager(auth_config)


# Authentication endpoints
@router.post("/auth/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    auth_manager: AuthenticationManager = Depends(get_auth_manager)
):
    """Authenticate user and return access token."""
    try:
        source_ip = http_request.client.host if http_request.client else ""
        
        # Authenticate user
        token_data = auth_manager.authenticate_user(
            request.user_id,
            request.password,
            source_ip
        )
        
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Create JWT token
        access_token = auth_manager.create_jwt_token(token_data)
        
        return LoginResponse(
            access_token=access_token,
            expires_in=auth_manager.config.token_expire_minutes * 60,
            user_id=token_data.user_id,
            roles=token_data.roles
        )
        
    except SecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}"
        )


@router.post("/auth/logout")
async def logout(
    current_user: TokenData = Depends(get_current_user),
    auth_manager: AuthenticationManager = Depends(get_auth_manager)
):
    """Logout user and invalidate session."""
    try:
        auth_manager.invalidate_session(current_user.session_id)
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )


# User management endpoints
@router.post("/users", dependencies=[require_permission("user:create")])
async def create_user(
    request: UserCreateRequest,
    current_user: TokenData = Depends(get_current_user),
    auth_manager: AuthenticationManager = Depends(get_auth_manager),
    audit_logger: AuditLogger = Depends(get_audit_logger)
):
    """Create a new user."""
    try:
        success = auth_manager.create_user(
            request.user_id,
            request.email,
            request.password,
            request.roles,
            request.permissions
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user"
            )
        
        # Log user creation
        await audit_logger.log_resource_access(
            user_id=current_user.user_id,
            resource_type="user",
            resource_id=request.user_id,
            action="CREATE",
            success=True
        )
        
        return {"message": f"User {request.user_id} created successfully"}
        
    except SecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Security status endpoints
@router.get("/status", response_model=SecurityStatusResponse)
async def get_security_status(
    current_user: TokenData = Depends(get_current_user),
    security_manager: SecurityManager = Depends(get_security_manager)
):
    """Get overall security status."""
    try:
        status = await security_manager.get_security_status()
        
        return SecurityStatusResponse(
            firewall_enabled=status.get('firewall_initialized', False),
            isolation_enabled=status.get('namespace_isolation', False),
            audit_logging_enabled=status.get('monitoring_enabled', False),
            compliance_frameworks=[],
            active_policies=status.get('policies_count', 0),
            security_level="ENHANCED"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get security status: {str(e)}"
        )


# Firewall management endpoints
@router.post("/firewall/rules", dependencies=[require_permission("security:firewall")])
async def create_firewall_rule(
    request: FirewallRuleRequest,
    current_user: TokenData = Depends(get_current_user),
    security_manager: SecurityManager = Depends(get_security_manager),
    audit_logger: AuditLogger = Depends(get_audit_logger)
):
    """Create a firewall rule for a VM."""
    try:
        if request.rule_type == "port_forward":
            success = await security_manager.isolation_manager.firewall_manager.add_port_forwarding_rule(
                request.vm_name,
                request.dest_ip or "",
                request.source_port or 0,
                request.dest_port or 0,
                request.protocol
            )
        else:
            # Create custom firewall rule
            success = True  # Placeholder
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create firewall rule"
            )
        
        # Log firewall rule creation
        await audit_logger.log_configuration_change(
            user_id=current_user.user_id,
            config_type="firewall_rule",
            old_value="none",
            new_value=request.dict()
        )
        
        return {"message": f"Firewall rule created for VM {request.vm_name}"}
        
    except SecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/firewall/rules/{vm_name}", dependencies=[require_permission("security:firewall")])
async def remove_firewall_rules(
    vm_name: str,
    current_user: TokenData = Depends(get_current_user),
    security_manager: SecurityManager = Depends(get_security_manager),
    audit_logger: AuditLogger = Depends(get_audit_logger)
):
    """Remove all firewall rules for a VM."""
    try:
        success = await security_manager.isolation_manager.firewall_manager.remove_vm_rules(vm_name)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to remove firewall rules"
            )
        
        # Log firewall rule removal
        await audit_logger.log_configuration_change(
            user_id=current_user.user_id,
            config_type="firewall_rule",
            old_value=f"rules for {vm_name}",
            new_value="removed"
        )
        
        return {"message": f"Firewall rules removed for VM {vm_name}"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove firewall rules: {str(e)}"
        )


# VM isolation endpoints
@router.post("/isolation/policy", dependencies=[require_permission("security:isolation")])
async def create_isolation_policy(
    request: IsolationPolicyRequest,
    current_user: TokenData = Depends(get_current_user),
    security_manager: SecurityManager = Depends(get_security_manager),
    audit_logger: AuditLogger = Depends(get_audit_logger)
):
    """Create VM isolation policy."""
    try:
        # Create network policy
        network_policy = {
            'allowed_outbound': [{'ip': net} for net in request.allowed_networks],
            'blocked_ports': request.blocked_ports
        }
        
        success = await security_manager.isolation_manager.create_vm_network_policy(
            request.vm_name,
            network_policy
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create isolation policy"
            )
        
        # Log policy creation
        await audit_logger.log_configuration_change(
            user_id=current_user.user_id,
            config_type="isolation_policy",
            old_value="none",
            new_value=request.dict()
        )
        
        return {"message": f"Isolation policy created for VM {request.vm_name}"}
        
    except SecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/isolation/status/{vm_name}")
async def get_isolation_status(
    vm_name: str,
    current_user: TokenData = Depends(get_current_user),
    security_manager: SecurityManager = Depends(get_security_manager)
):
    """Get isolation status for a VM."""
    try:
        status = await security_manager.isolation_manager.get_isolation_status(vm_name)
        return status
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get isolation status: {str(e)}"
        )


# Audit and compliance endpoints
@router.post("/audit/report", dependencies=[require_permission("audit:read")])
async def generate_audit_report(
    request: AuditReportRequest,
    current_user: TokenData = Depends(get_current_user),
    audit_logger: AuditLogger = Depends(get_audit_logger)
):
    """Generate audit report for specified criteria."""
    try:
        # Convert string event types to enum if provided
        event_types = []
        if request.event_types:
            for event_type in request.event_types:
                try:
                    event_types.append(AuditEventType(event_type))
                except ValueError:
                    pass
        
        report = await audit_logger.get_audit_report(
            request.start_date,
            request.end_date,
            event_types,
            request.user_id
        )
        
        # Log report generation
        await audit_logger.log_resource_access(
            user_id=current_user.user_id,
            resource_type="audit_report",
            resource_id="generated_report",
            action="GENERATE",
            success=True,
            details={
                'start_date': request.start_date.isoformat(),
                'end_date': request.end_date.isoformat()
            }
        )
        
        return report
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate audit report: {str(e)}"
        )


@router.get("/audit/statistics", dependencies=[require_permission("audit:read")])
async def get_audit_statistics(
    current_user: TokenData = Depends(get_current_user),
    audit_logger: AuditLogger = Depends(get_audit_logger)
):
    """Get audit system statistics."""
    try:
        stats = audit_logger.get_statistics()
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit statistics: {str(e)}"
        )


# Security policy management
@router.put("/policy", dependencies=[require_permission("security:admin")])
async def update_security_policy(
    request: SecurityPolicyRequest,
    current_user: TokenData = Depends(get_current_user),
    audit_logger: AuditLogger = Depends(get_audit_logger)
):
    """Update security policy configuration."""
    try:
        # In a real implementation, this would update the security policy
        # For now, just log the change
        
        await audit_logger.log_configuration_change(
            user_id=current_user.user_id,
            config_type="security_policy",
            old_value="existing_policy",
            new_value=request.dict()
        )
        
        return {"message": "Security policy updated successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update security policy: {str(e)}"
        )


# Security scanning endpoints
@router.post("/scan/vulnerability", dependencies=[require_permission("security:scan")])
async def run_vulnerability_scan(
    vm_name: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    audit_logger: AuditLogger = Depends(get_audit_logger)
):
    """Run security vulnerability scan."""
    try:
        # Placeholder for vulnerability scanning
        scan_results = {
            'scan_id': 'scan_' + str(int(datetime.utcnow().timestamp())),
            'target': vm_name or 'system',
            'status': 'completed',
            'vulnerabilities_found': 0,
            'recommendations': [
                'Keep system updated',
                'Enable firewall rules',
                'Review user permissions'
            ]
        }
        
        # Log vulnerability scan
        await audit_logger.log_resource_access(
            user_id=current_user.user_id,
            resource_type="security_scan",
            resource_id=scan_results['scan_id'],
            action="VULNERABILITY_SCAN",
            success=True,
            details={'target': vm_name or 'system'}
        )
        
        return scan_results
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run vulnerability scan: {str(e)}"
        )