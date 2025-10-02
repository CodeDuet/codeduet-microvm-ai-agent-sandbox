"""
Security validation tests for py-microvm client.
"""

import pytest
from microvm_client import SecurityValidator, ValidationError


class TestSecurityValidator:
    """Test security validation functions."""
    
    def test_validate_command_success(self):
        """Test valid commands pass validation."""
        valid_commands = [
            "python --version",
            "ls -la",
            "echo hello world",
            "cat /tmp/file.txt",
        ]
        
        for cmd in valid_commands:
            result = SecurityValidator.validate_command(cmd)
            assert result == cmd.strip()
    
    def test_validate_command_dangerous_patterns(self):
        """Test dangerous command patterns are blocked."""
        dangerous_commands = [
            "ls; rm -rf /",
            "echo test && sudo su",
            "python `whoami`",
            "cat file | sudo tee /etc/passwd",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sda1",
        ]
        
        for cmd in dangerous_commands:
            with pytest.raises(ValidationError, match="forbidden pattern"):
                SecurityValidator.validate_command(cmd)
    
    def test_validate_command_empty(self):
        """Test empty commands are rejected."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            SecurityValidator.validate_command("")
        
        with pytest.raises(ValidationError, match="cannot be empty"):
            SecurityValidator.validate_command("   ")
    
    def test_validate_command_too_long(self):
        """Test overly long commands are rejected."""
        long_command = "a" * 10001
        with pytest.raises(ValidationError, match="too long"):
            SecurityValidator.validate_command(long_command)
    
    def test_validate_path_success(self):
        """Test valid paths pass validation."""
        valid_paths = [
            "/tmp/file.txt",
            "/home/user/script.py",
            "/workspace/data.json",
        ]
        
        for path in valid_paths:
            result = SecurityValidator.validate_path(path)
            assert result == path
    
    def test_validate_path_traversal(self):
        """Test path traversal attempts are blocked."""
        dangerous_paths = [
            "../../../etc/passwd",
            "/tmp/../../etc/shadow", 
            "../../usr/bin/sudo",
            "/etc/passwd",
            "/usr/bin/bash",
        ]
        
        for path in dangerous_paths:
            with pytest.raises(ValidationError, match="traversal|system directory"):
                SecurityValidator.validate_path(path)
    
    def test_validate_path_empty(self):
        """Test empty paths are rejected."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            SecurityValidator.validate_path("")
    
    def test_validate_vm_name_success(self):
        """Test valid VM names pass validation."""
        valid_names = [
            "test-vm",
            "ai_agent_123",
            "VM-001",
            "my-sandbox",
        ]
        
        for name in valid_names:
            result = SecurityValidator.validate_vm_name(name)
            assert result == name
    
    def test_validate_vm_name_invalid(self):
        """Test invalid VM names are rejected."""
        invalid_names = [
            "",
            "vm with spaces",
            "vm@domain.com",
            "vm/path",
            "vm;injection",
            "a" * 65,  # Too long
        ]
        
        for name in invalid_names:
            with pytest.raises(ValidationError):
                SecurityValidator.validate_vm_name(name)