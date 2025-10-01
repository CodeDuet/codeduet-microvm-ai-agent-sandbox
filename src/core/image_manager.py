"""
Image Manager for MicroVM Sandbox
Handles VM image creation, validation, and management for both Linux and Windows.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import subprocess
import hashlib
import json
from datetime import datetime
import asyncio

from src.utils.config import get_settings
from src.utils.helpers import run_subprocess, validate_file_path
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ImageInfo:
    """Information about a VM image."""
    
    def __init__(self, name: str, path: str, os_type: str, size_bytes: int, 
                 checksum: str, created_at: datetime, metadata: Dict[str, Any] = None):
        self.name = name
        self.path = path
        self.os_type = os_type
        self.size_bytes = size_bytes
        self.checksum = checksum
        self.created_at = created_at
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "os_type": self.os_type,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }


class ImageManager:
    """Manages VM images for MicroVM deployment."""
    
    def __init__(self):
        self.settings = get_settings()
        self.images_dir = Path("images")
        self.linux_dir = self.images_dir / "linux"
        self.windows_dir = self.images_dir / "windows"
        self.metadata_file = self.images_dir / "image_registry.json"
        
        # Create directories
        for directory in [self.images_dir, self.linux_dir, self.windows_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        self._image_registry: Dict[str, ImageInfo] = {}
        self._load_image_registry()
    
    async def validate_image(self, image_path: str, os_type: str) -> bool:
        """Validate a VM image for the specified OS type."""
        logger.info(f"Validating {os_type} image: {image_path}")
        
        image_file = Path(image_path)
        if not image_file.exists():
            logger.error(f"Image file not found: {image_path}")
            return False
        
        if not image_file.is_file():
            logger.error(f"Path is not a file: {image_path}")
            return False
        
        # Check file size (must be > 100MB)
        size_mb = image_file.stat().st_size / (1024 * 1024)
        if size_mb < 100:
            logger.error(f"Image too small: {size_mb:.1f}MB (minimum 100MB)")
            return False
        
        if os_type.lower() == "windows":
            return await self._validate_windows_image(image_path)
        elif os_type.lower() == "linux":
            return await self._validate_linux_image(image_path)
        else:
            logger.error(f"Unsupported OS type: {os_type}")
            return False
    
    async def _validate_windows_image(self, image_path: str) -> bool:
        """Validate Windows VM image."""
        try:
            # Check if it's a valid QEMU image
            cmd = ["qemu-img", "info", image_path]
            result = await run_subprocess(cmd)
            
            if result.returncode != 0:
                logger.error(f"Invalid QEMU image: {image_path}")
                return False
            
            info_output = result.stdout
            if "qcow2" not in info_output and "raw" not in info_output:
                logger.error("Image must be in qcow2 or raw format")
                return False
            
            logger.info("Windows image validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Error validating Windows image: {e}")
            return False
    
    async def _validate_linux_image(self, image_path: str) -> bool:
        """Validate Linux VM image."""
        try:
            # For Linux, we might have separate kernel and rootfs files
            image_file = Path(image_path)
            
            if image_file.suffix == ".bin":
                # Likely a kernel file
                if image_file.stat().st_size < 1024 * 1024:  # At least 1MB
                    logger.error("Kernel image too small")
                    return False
            elif image_file.suffix in [".ext4", ".img"]:
                # Likely a rootfs file - check with file command
                cmd = ["file", image_path]
                result = await run_subprocess(cmd)
                
                if "filesystem" not in result.stdout.lower():
                    logger.warning("Rootfs might not be a valid filesystem")
            
            logger.info("Linux image validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Error validating Linux image: {e}")
            return False
    
    async def register_image(self, name: str, path: str, os_type: str, 
                           metadata: Dict[str, Any] = None) -> ImageInfo:
        """Register a VM image in the image registry."""
        logger.info(f"Registering image '{name}' at {path}")
        
        if not await self.validate_image(path, os_type):
            raise ValueError(f"Image validation failed: {path}")
        
        image_file = Path(path)
        size_bytes = image_file.stat().st_size
        checksum = await self._calculate_checksum(path)
        
        image_info = ImageInfo(
            name=name,
            path=path,
            os_type=os_type.lower(),
            size_bytes=size_bytes,
            checksum=checksum,
            created_at=datetime.now(),
            metadata=metadata or {}
        )
        
        self._image_registry[name] = image_info
        await self._save_image_registry()
        
        logger.info(f"Image '{name}' registered successfully")
        return image_info
    
    async def get_image(self, name: str) -> Optional[ImageInfo]:
        """Get image information by name."""
        return self._image_registry.get(name)
    
    async def list_images(self, os_type: Optional[str] = None) -> List[ImageInfo]:
        """List all registered images, optionally filtered by OS type."""
        images = list(self._image_registry.values())
        
        if os_type:
            images = [img for img in images if img.os_type == os_type.lower()]
        
        return sorted(images, key=lambda x: x.created_at, reverse=True)
    
    async def remove_image(self, name: str, delete_file: bool = False) -> None:
        """Remove an image from the registry and optionally delete the file."""
        if name not in self._image_registry:
            raise ValueError(f"Image '{name}' not found in registry")
        
        image_info = self._image_registry[name]
        
        if delete_file:
            image_file = Path(image_info.path)
            if image_file.exists():
                image_file.unlink()
                logger.info(f"Deleted image file: {image_info.path}")
        
        del self._image_registry[name]
        await self._save_image_registry()
        
        logger.info(f"Image '{name}' removed from registry")
    
    async def create_windows_image(self, name: str, size_gb: int = 20, 
                                 format_type: str = "qcow2") -> str:
        """Create a new Windows VM disk image."""
        logger.info(f"Creating Windows image '{name}' ({size_gb}GB)")
        
        image_path = str(self.windows_dir / f"{name}.{format_type}")
        
        cmd = [
            "qemu-img", "create", 
            "-f", format_type,
            image_path,
            f"{size_gb}G"
        ]
        
        result = await run_subprocess(cmd)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create image: {result.stderr}")
        
        await self.register_image(name, image_path, "windows", {
            "size_gb": size_gb,
            "format": format_type,
            "created_by": "image_manager"
        })
        
        logger.info(f"Windows image created: {image_path}")
        return image_path
    
    async def create_linux_rootfs(self, name: str, size_mb: int = 512, 
                                format_type: str = "ext4") -> str:
        """Create a new Linux rootfs image."""
        logger.info(f"Creating Linux rootfs '{name}' ({size_mb}MB)")
        
        image_path = str(self.linux_dir / f"{name}.{format_type}")
        
        # Create empty file
        cmd = ["dd", "if=/dev/zero", f"of={image_path}", "bs=1M", f"count={size_mb}"]
        result = await run_subprocess(cmd)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create rootfs file: {result.stderr}")
        
        # Format as ext4
        if format_type == "ext4":
            cmd = ["mkfs.ext4", "-F", image_path]
            result = await run_subprocess(cmd)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to format rootfs: {result.stderr}")
        
        await self.register_image(name, image_path, "linux", {
            "size_mb": size_mb,
            "format": format_type,
            "type": "rootfs",
            "created_by": "image_manager"
        })
        
        logger.info(f"Linux rootfs created: {image_path}")
        return image_path
    
    async def verify_image_integrity(self, name: str) -> bool:
        """Verify image integrity by checking checksum."""
        image_info = await self.get_image(name)
        if not image_info:
            logger.error(f"Image '{name}' not found")
            return False
        
        image_file = Path(image_info.path)
        if not image_file.exists():
            logger.error(f"Image file not found: {image_info.path}")
            return False
        
        current_checksum = await self._calculate_checksum(image_info.path)
        if current_checksum != image_info.checksum:
            logger.error(f"Checksum mismatch for image '{name}'")
            return False
        
        logger.info(f"Image '{name}' integrity verified")
        return True
    
    async def get_image_info(self, path: str) -> Dict[str, Any]:
        """Get detailed information about an image file."""
        try:
            cmd = ["qemu-img", "info", "--output=json", path]
            result = await run_subprocess(cmd)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                # Fallback to basic file info
                image_file = Path(path)
                return {
                    "filename": str(image_file),
                    "format": "unknown",
                    "virtual_size": image_file.stat().st_size,
                    "actual_size": image_file.stat().st_size
                }
                
        except Exception as e:
            logger.error(f"Error getting image info: {e}")
            return {}
    
    async def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of a file."""
        logger.debug(f"Calculating checksum for {file_path}")
        
        hash_sha256 = hashlib.sha256()
        
        def calculate():
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        checksum = await loop.run_in_executor(None, calculate)
        
        logger.debug(f"Checksum calculated: {checksum[:16]}...")
        return checksum
    
    def _load_image_registry(self) -> None:
        """Load image registry from disk."""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)
                
                for name, info_dict in data.items():
                    info_dict['created_at'] = datetime.fromisoformat(info_dict['created_at'])
                    self._image_registry[name] = ImageInfo(
                        name=info_dict['name'],
                        path=info_dict['path'],
                        os_type=info_dict['os_type'],
                        size_bytes=info_dict['size_bytes'],
                        checksum=info_dict['checksum'],
                        created_at=info_dict['created_at'],
                        metadata=info_dict.get('metadata', {})
                    )
                
                logger.info(f"Loaded {len(self._image_registry)} images from registry")
            
        except Exception as e:
            logger.warning(f"Failed to load image registry: {e}")
            self._image_registry = {}
    
    async def _save_image_registry(self) -> None:
        """Save image registry to disk."""
        try:
            data = {}
            for name, image_info in self._image_registry.items():
                data[name] = image_info.to_dict()
            
            with open(self.metadata_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug("Image registry saved")
            
        except Exception as e:
            logger.error(f"Failed to save image registry: {e}")