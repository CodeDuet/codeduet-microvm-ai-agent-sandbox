import asyncio
import aiofiles
import secrets
import string
from pathlib import Path
from typing import Optional, Dict, Any
import uuid
import json
from datetime import datetime


def generate_vm_id() -> str:
    return str(uuid.uuid4())


def generate_request_id() -> str:
    return str(uuid.uuid4())


def generate_password(length: int = 12) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


async def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


async def read_file_async(file_path: Path) -> str:
    async with aiofiles.open(file_path, 'r') as f:
        return await f.read()


async def write_file_async(file_path: Path, content: str) -> None:
    await ensure_directory(file_path.parent)
    async with aiofiles.open(file_path, 'w') as f:
        await f.write(content)


async def read_json_async(file_path: Path) -> Dict[str, Any]:
    content = await read_file_async(file_path)
    return json.loads(content)


async def write_json_async(file_path: Path, data: Dict[str, Any]) -> None:
    content = json.dumps(data, indent=2, default=str)
    await write_file_async(file_path, content)


def format_bytes(bytes_value: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def validate_vm_name(name: str) -> bool:
    if not name:
        return False
    if len(name) > 64:
        return False
    if not name.replace('-', '').replace('_', '').isalnum():
        return False
    return True


def sanitize_vm_name(name: str) -> str:
    # Remove invalid characters and ensure length limit
    sanitized = ''.join(c for c in name if c.isalnum() or c in '-_')
    return sanitized[:64]


async def run_subprocess(cmd: list, timeout: Optional[int] = None, input: Optional[bytes] = None, capture_output: bool = True):
    """Run subprocess with optional input and capture settings."""
    if capture_output:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if input else None
        )
    else:
        process = await asyncio.create_subprocess_exec(*cmd)
    
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=input), 
            timeout=timeout
        )
        
        if capture_output:
            # Return object with returncode, stdout, stderr attributes
            class SubprocessResult:
                def __init__(self, returncode, stdout, stderr):
                    self.returncode = returncode
                    self.stdout = stdout.decode() if stdout else ""
                    self.stderr = stderr.decode() if stderr else ""
            
            return SubprocessResult(process.returncode, stdout, stderr)
        else:
            return process.returncode
            
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise