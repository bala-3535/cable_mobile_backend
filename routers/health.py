from fastapi import APIRouter
from datetime import datetime
from core.utils import get_ist_now

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
def health_check():
    """
    Lightweight health check endpoint.
    """
    return {
        "status": "healthy",
        "timestamp": get_ist_now().isoformat(),
        "message": "Server is up and running"
    }

@router.get("/ping")
def ping():
    """
    Ping endpoint for keep-alive monitoring.
    """
    return {"status": "pong"}
