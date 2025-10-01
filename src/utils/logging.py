import sys
from loguru import logger
from pathlib import Path
from src.utils.config import get_settings


def setup_logging():
    settings = get_settings()
    
    # Remove default handler
    logger.remove()
    
    # Console handler with colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level=settings.monitoring.log_level,
        colorize=True,
    )
    
    # File handler for all logs
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logger.add(
        log_dir / "microvm-sandbox.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="100 MB",
        retention="30 days",
        compression="gz",
        serialize=False,
    )
    
    # Error file handler
    logger.add(
        log_dir / "microvm-sandbox-error.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="ERROR",
        rotation="50 MB",
        retention="90 days",
        compression="gz",
        serialize=False,
    )
    
    # JSON structured logging for production
    logger.add(
        log_dir / "microvm-sandbox.json",
        format="{message}",
        level="INFO",
        rotation="100 MB",
        retention="30 days",
        compression="gz",
        serialize=True,
    )
    
    logger.info("Logging system initialized")


def get_logger(name: str):
    return logger.bind(component=name)