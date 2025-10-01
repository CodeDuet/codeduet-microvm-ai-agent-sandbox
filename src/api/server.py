from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from typing import Dict, Any

from src.utils.logging import setup_logging
from src.utils.config import get_settings
from src.api.routes import vms, system, snapshots, network, guest, resources
from src.api.middleware.logging import LoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


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


@app.get("/")
async def root() -> Dict[str, str]:
    return {"message": "MicroVM Sandbox API", "version": "0.1.0"}


@app.get("/health")
async def health_check() -> Dict[str, Any]:
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