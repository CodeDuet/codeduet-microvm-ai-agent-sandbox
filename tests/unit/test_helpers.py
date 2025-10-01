import pytest
import asyncio
from pathlib import Path
import json

from src.utils.helpers import (
    generate_vm_id, generate_request_id, validate_vm_name, sanitize_vm_name,
    format_bytes, ensure_directory, read_file_async, write_file_async,
    read_json_async, write_json_async, run_subprocess
)


class TestGenerators:
    def test_generate_vm_id(self):
        vm_id = generate_vm_id()
        assert isinstance(vm_id, str)
        assert len(vm_id) == 36  # UUID length with hyphens
        
        # Generate multiple IDs to ensure uniqueness
        ids = [generate_vm_id() for _ in range(10)]
        assert len(set(ids)) == 10

    def test_generate_request_id(self):
        request_id = generate_request_id()
        assert isinstance(request_id, str)
        assert len(request_id) == 36


class TestValidation:
    def test_validate_vm_name_valid(self):
        assert validate_vm_name("test-vm") is True
        assert validate_vm_name("test_vm") is True
        assert validate_vm_name("test123") is True
        assert validate_vm_name("vm-1") is True

    def test_validate_vm_name_invalid(self):
        assert validate_vm_name("") is False
        assert validate_vm_name("test vm") is False  # Space not allowed
        assert validate_vm_name("test@vm") is False  # Special char not allowed
        assert validate_vm_name("a" * 65) is False  # Too long

    def test_sanitize_vm_name(self):
        assert sanitize_vm_name("test vm") == "testvm"
        assert sanitize_vm_name("test@vm#1") == "testvm1"
        assert sanitize_vm_name("test-vm_1") == "test-vm_1"
        assert sanitize_vm_name("a" * 70) == "a" * 64  # Truncated


class TestFormatting:
    def test_format_bytes(self):
        assert format_bytes(0) == "0.0 B"
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1024 * 1024) == "1.0 MB"
        assert format_bytes(1024 * 1024 * 1024) == "1.0 GB"
        assert format_bytes(512) == "512.0 B"
        assert format_bytes(1536) == "1.5 KB"


class TestAsyncFileOperations:
    @pytest.mark.asyncio
    async def test_ensure_directory(self, temp_dir):
        test_dir = temp_dir / "nested" / "directory"
        await ensure_directory(test_dir)
        assert test_dir.exists()
        assert test_dir.is_dir()

    @pytest.mark.asyncio
    async def test_read_write_file_async(self, temp_dir):
        test_file = temp_dir / "test.txt"
        test_content = "Hello, World!"
        
        await write_file_async(test_file, test_content)
        assert test_file.exists()
        
        read_content = await read_file_async(test_file)
        assert read_content == test_content

    @pytest.mark.asyncio
    async def test_read_write_json_async(self, temp_dir):
        test_file = temp_dir / "test.json"
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        
        await write_json_async(test_file, test_data)
        assert test_file.exists()
        
        read_data = await read_json_async(test_file)
        assert read_data == test_data


class TestSubprocess:
    @pytest.mark.asyncio
    async def test_run_subprocess_success(self):
        returncode, stdout, stderr = await run_subprocess(["echo", "hello"])
        assert returncode == 0
        assert stdout.strip() == "hello"
        assert stderr == ""

    @pytest.mark.asyncio
    async def test_run_subprocess_failure(self):
        returncode, stdout, stderr = await run_subprocess(["false"])
        assert returncode != 0

    @pytest.mark.asyncio
    async def test_run_subprocess_timeout(self):
        with pytest.raises(asyncio.TimeoutError):
            await run_subprocess(["sleep", "10"], timeout=1)