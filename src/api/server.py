from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from typing import Dict, Any

from src.utils.logging import setup_logging
from src.utils.config import get_settings
from src.utils.metrics import MetricsCollector, metrics
from src.utils.database import get_database_service, close_database_service
from src.api.routes import vms, system, snapshots, network, guest, resources, health, cluster
from src.api.middleware.logging import LoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    
    # Initialize database service
    try:
        await get_database_service()
    except Exception as e:
        print(f"Warning: Failed to initialize database service: {e}")
    
    # Start metrics collection
    collector = MetricsCollector(metrics, interval=30)
    await collector.start()
    
    try:
        yield
    finally:
        # Stop metrics collection
        await collector.stop()
        
        # Close database service
        await close_database_service()


app = FastAPI(
    title="MicroVM Sandbox API",
    description="Cloud Hypervisor + Python MicroVM Sandbox with hardware-level isolation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LoggingMiddleware)

app.include_router(vms.router, prefix="/api/v1/vms", tags=["VMs"])
app.include_router(system.router, prefix="/api/v1/system", tags=["System"])
app.include_router(snapshots.router, prefix="/api/v1/snapshots", tags=["Snapshots"])
app.include_router(network.router, prefix="/api/v1/network", tags=["Network"])
app.include_router(guest.router, prefix="/api/v1", tags=["Guest"])
app.include_router(resources.router, tags=["Resources"])
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(cluster.router, prefix="/api/v1", tags=["Cluster"])


@app.get("/")
async def root() -> Dict[str, str]:
    return {"message": "MicroVM Sandbox API", "version": "0.1.0"}


@app.get("/health")
async def simple_health_check() -> Dict[str, Any]:
    """Simple health check for backwards compatibility."""
    return {
        "status": "healthy",
        "service": "microvm-sandbox",
        "version": "0.1.0"
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.api.server:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=True,
    )