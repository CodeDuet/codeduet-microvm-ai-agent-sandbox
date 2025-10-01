"""
Comprehensive audit logging and compliance system for MicroVM management.
"""

import json
import logging
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
import uuid

from .security import SecurityError


class AuditEventType(Enum):
    """Types of audit events."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VM_OPERATION = "vm_operation"
    RESOURCE_ACCESS = "resource_access"
    SECURITY_VIOLATION = "security_violation"
    DATA_ACCESS = "data_access"
    CONFIGURATION_CHANGE = "configuration_change"
    SYSTEM_EVENT = "system_event"
    COMPLIANCE_CHECK = "compliance_check"


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Structured audit event."""
    event_id: str
    timestamp: datetime
    event_type: AuditEventType
    severity: AuditSeverity
    user_id: str
    source_ip: str
    action: str
    resource_type: str
    resource_id: str
    outcome: str  # SUCCESS, FAILURE, PARTIAL
    details: Dict[str, Any]
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['event_type'] = self.event_type.value
        data['severity'] = self.severity.value
        return data
    
    def to_json(self) -> str:
        """Convert audit event to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class ComplianceFramework(Enum):
    """Supported compliance frameworks."""
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"
    ISO27001 = "iso27001"
    NIST = "nist"


@dataclass
class ComplianceRequirement:
    """Compliance requirement definition."""
    framework: ComplianceFramework
    requirement_id: str
    description: str
    audit_events: List[AuditEventType]
    retention_days: int
    required_fields: List[str]
    severity_threshold: AuditSeverity


class AuditLogger:
    """Enhanced audit logging system with compliance support."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize audit logger."""
        self.config = config
        self.log_file = config.get('audit_log_file', 'audit.log')
        self.retention_days = config.get('retention_days', 2555)  # 7 years default
        self.enable_encryption = config.get('enable_encryption', True)
        self.compliance_frameworks = config.get('compliance_frameworks', [])
        self.buffer_size = config.get('buffer_size', 100)
        self.flush_interval = config.get('flush_interval_seconds', 30)
        
        # Initialize logging
        self.logger = logging.getLogger('audit')
        self._setup_logging()
        
        # Event buffer for batch processing
        self.event_buffer: List[AuditEvent] = []
        self.last_flush = time.time()
        
        # Compliance requirements
        self.compliance_requirements = self._load_compliance_requirements()
        
        # Statistics
        self.stats = {
            'total_events': 0,
            'events_by_type': {},
            'events_by_severity': {},
            'compliance_violations': 0
        }
    
    def _setup_logging(self):
        """Set up audit logging configuration."""
        # Create audit log directory
        log_path = Path(self.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure audit logger
        handler = logging.FileHandler(self.log_file)
        formatter = logging.Formatter(
            '%(asctime)s - AUDIT - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
        # Separate handler for console output in debug mode
        if self.config.get('debug', False):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
    def _load_compliance_requirements(self) -> Dict[ComplianceFramework, List[ComplianceRequirement]]:
        """Load compliance requirements for enabled frameworks."""
        requirements = {}
        
        # SOC 2 requirements
        if ComplianceFramework.SOC2 in self.compliance_frameworks:
            requirements[ComplianceFramework.SOC2] = [
                ComplianceRequirement(
                    framework=ComplianceFramework.SOC2,
                    requirement_id="CC6.1",
                    description="Logical and physical access controls",
                    audit_events=[AuditEventType.AUTHENTICATION, AuditEventType.AUTHORIZATION],
                    retention_days=2555,  # 7 years
                    required_fields=['user_id', 'source_ip', 'timestamp', 'outcome'],
                    severity_threshold=AuditSeverity.MEDIUM
                ),
                ComplianceRequirement(
                    framework=ComplianceFramework.SOC2,
                    requirement_id="CC7.1",
                    description="System operations monitoring",
                    audit_events=[AuditEventType.SYSTEM_EVENT, AuditEventType.VM_OPERATION],
                    retention_days=2555,
                    required_fields=['action', 'resource_type', 'timestamp', 'outcome'],
                    severity_threshold=AuditSeverity.LOW
                )
            ]
        
        # HIPAA requirements
        if ComplianceFramework.HIPAA in self.compliance_frameworks:
            requirements[ComplianceFramework.HIPAA] = [
                ComplianceRequirement(
                    framework=ComplianceFramework.HIPAA,
                    requirement_id="164.312(b)",
                    description="Audit controls",
                    audit_events=[AuditEventType.DATA_ACCESS, AuditEventType.AUTHENTICATION],
                    retention_days=2190,  # 6 years
                    required_fields=['user_id', 'resource_id', 'timestamp', 'action'],
                    severity_threshold=AuditSeverity.MEDIUM
                )
            ]
        
        # Add more frameworks as needed
        return requirements
    
    async def log_event(self, event: AuditEvent):
        """Log an audit event."""
        try:
            # Validate event
            self._validate_event(event)
            
            # Check compliance requirements
            await self._check_compliance(event)
            
            # Add to buffer
            self.event_buffer.append(event)
            
            # Update statistics
            self._update_stats(event)
            
            # Flush if buffer is full or time interval reached
            if (len(self.event_buffer) >= self.buffer_size or 
                time.time() - self.last_flush > self.flush_interval):
                await self._flush_events()
            
        except Exception as e:
            # Log audit system errors to system log
            logging.getLogger(__name__).error(f"Audit logging error: {e}")
    
    def _validate_event(self, event: AuditEvent):
        """Validate audit event structure."""
        required_fields = ['event_id', 'timestamp', 'event_type', 'user_id', 'action']
        
        for field in required_fields:
            if not getattr(event, field, None):
                raise SecurityError(f"Missing required audit field: {field}")
        
        # Validate event ID format
        if not event.event_id or len(event.event_id) < 8:
            raise SecurityError("Invalid event ID format")
        
        # Validate timestamp
        if event.timestamp > datetime.utcnow() + timedelta(minutes=5):
            raise SecurityError("Event timestamp is in the future")
    
    async def _check_compliance(self, event: AuditEvent):
        """Check event against compliance requirements."""
        for framework, requirements in self.compliance_requirements.items():
            for requirement in requirements:
                if event.event_type in requirement.audit_events:
                    # Check required fields
                    for field in requirement.required_fields:
                        if not getattr(event, field, None):
                            violation = f"Compliance violation: {framework.value} "
                            violation += f"requirement {requirement.requirement_id} "
                            violation += f"missing field {field}"
                            
                            await self._log_compliance_violation(violation, event)
                    
                    # Check severity threshold
                    if event.severity.value < requirement.severity_threshold.value:
                        # This is for reporting, not a violation per se
                        pass
    
    async def _log_compliance_violation(self, violation: str, original_event: AuditEvent):
        """Log compliance violation."""
        self.stats['compliance_violations'] += 1
        
        # Create compliance violation event
        violation_event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            event_type=AuditEventType.COMPLIANCE_CHECK,
            severity=AuditSeverity.HIGH,
            user_id="SYSTEM",
            source_ip="",
            action="COMPLIANCE_VIOLATION",
            resource_type="audit_system",
            resource_id="compliance_checker",
            outcome="VIOLATION",
            details={
                'violation': violation,
                'original_event_id': original_event.event_id,
                'original_event_type': original_event.event_type.value
            }
        )
        
        # Log immediately (don't buffer compliance violations)
        self.logger.critical(violation_event.to_json())
    
    def _update_stats(self, event: AuditEvent):
        """Update audit statistics."""
        self.stats['total_events'] += 1
        
        # Count by type
        event_type = event.event_type.value
        if event_type not in self.stats['events_by_type']:
            self.stats['events_by_type'][event_type] = 0
        self.stats['events_by_type'][event_type] += 1
        
        # Count by severity
        severity = event.severity.value
        if severity not in self.stats['events_by_severity']:
            self.stats['events_by_severity'][severity] = 0
        self.stats['events_by_severity'][severity] += 1
    
    async def _flush_events(self):
        """Flush buffered events to log file."""
        if not self.event_buffer:
            return
        
        try:
            for event in self.event_buffer:
                if self.enable_encryption:
                    log_entry = self._encrypt_log_entry(event.to_json())
                else:
                    log_entry = event.to_json()
                
                self.logger.info(log_entry)
            
            self.event_buffer.clear()
            self.last_flush = time.time()
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to flush audit events: {e}")
    
    def _encrypt_log_entry(self, log_entry: str) -> str:
        """Encrypt log entry for security."""
        # Simple hash-based "encryption" for demo
        # In production, use proper encryption
        hash_obj = hashlib.sha256(log_entry.encode())
        return f"ENCRYPTED:{hash_obj.hexdigest()}:{log_entry}"
    
    # Convenience methods for different event types
    async def log_authentication(self, user_id: str, success: bool, 
                               source_ip: str, details: Dict = None):
        """Log authentication event."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            event_type=AuditEventType.AUTHENTICATION,
            severity=AuditSeverity.MEDIUM if success else AuditSeverity.HIGH,
            user_id=user_id,
            source_ip=source_ip,
            action="LOGIN" if success else "LOGIN_FAILED",
            resource_type="authentication_system",
            resource_id="auth",
            outcome="SUCCESS" if success else "FAILURE",
            details=details or {}
        )
        await self.log_event(event)
    
    async def log_vm_operation(self, user_id: str, vm_name: str, action: str,
                             success: bool, source_ip: str = "", 
                             details: Dict = None):
        """Log VM operation event."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            event_type=AuditEventType.VM_OPERATION,
            severity=AuditSeverity.MEDIUM,
            user_id=user_id,
            source_ip=source_ip,
            action=action.upper(),
            resource_type="virtual_machine",
            resource_id=vm_name,
            outcome="SUCCESS" if success else "FAILURE",
            details=details or {}
        )
        await self.log_event(event)
    
    async def log_security_violation(self, user_id: str, violation_type: str,
                                   details: str, source_ip: str = ""):
        """Log security violation event."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=AuditSeverity.CRITICAL,
            user_id=user_id,
            source_ip=source_ip,
            action="SECURITY_VIOLATION",
            resource_type="security_system",
            resource_id=violation_type,
            outcome="VIOLATION",
            details={'violation_details': details}
        )
        await self.log_event(event)
    
    async def log_resource_access(self, user_id: str, resource_type: str,
                                resource_id: str, action: str,
                                success: bool, source_ip: str = "",
                                details: Dict = None):
        """Log resource access event."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            event_type=AuditEventType.RESOURCE_ACCESS,
            severity=AuditSeverity.LOW,
            user_id=user_id,
            source_ip=source_ip,
            action=action.upper(),
            resource_type=resource_type,
            resource_id=resource_id,
            outcome="SUCCESS" if success else "FAILURE",
            details=details or {}
        )
        await self.log_event(event)
    
    async def log_configuration_change(self, user_id: str, config_type: str,
                                     old_value: Any, new_value: Any,
                                     source_ip: str = ""):
        """Log configuration change event."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            event_type=AuditEventType.CONFIGURATION_CHANGE,
            severity=AuditSeverity.HIGH,
            user_id=user_id,
            source_ip=source_ip,
            action="CONFIG_CHANGE",
            resource_type="configuration",
            resource_id=config_type,
            outcome="SUCCESS",
            details={
                'old_value': str(old_value),
                'new_value': str(new_value),
                'config_type': config_type
            }
        )
        await self.log_event(event)
    
    async def get_audit_report(self, start_date: datetime, end_date: datetime,
                             event_types: List[AuditEventType] = None,
                             user_id: str = None) -> Dict[str, Any]:
        """Generate audit report for specified criteria."""
        # This would typically query a database
        # For now, return summary statistics
        return {
            'report_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'summary': self.stats.copy(),
            'compliance_frameworks': [f.value for f in self.compliance_frameworks],
            'generated_at': datetime.utcnow().isoformat()
        }
    
    async def cleanup_old_logs(self):
        """Clean up audit logs older than retention period."""
        # This would typically clean up database records
        # For file-based logs, implement log rotation
        retention_date = datetime.utcnow() - timedelta(days=self.retention_days)
        
        # Log the cleanup action
        await self.log_resource_access(
            user_id="SYSTEM",
            resource_type="audit_logs",
            resource_id="cleanup",
            action="CLEANUP",
            success=True,
            details={'retention_date': retention_date.isoformat()}
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get audit system statistics."""
        return {
            'statistics': self.stats.copy(),
            'configuration': {
                'retention_days': self.retention_days,
                'encryption_enabled': self.enable_encryption,
                'compliance_frameworks': [f.value for f in self.compliance_frameworks],
                'buffer_size': self.buffer_size,
                'flush_interval': self.flush_interval
            },
            'last_flush': self.last_flush,
            'buffer_events': len(self.event_buffer)
        }