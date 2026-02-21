"""
Performance Router: System metrics reporting endpoint.
"""
from fastapi import APIRouter
import logging

from app.models.schemas import PerformanceResponse
from app.services.performance_service import performance_tracker

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/blackrock/challenge/v1",
    tags=["Performance"],
)


@router.get(
    "/performance",
    response_model=PerformanceResponse,
    summary="Performance Report",
    description="Reports system execution metrics: response time, memory usage, and thread count.",
)
async def get_performance():
    """
    Endpoint 5: Performance Report
    
    Returns:
    - time: Last request response time (HH:mm:ss.SSS format)
    - memory: Current memory usage in MB
    - threads: Number of active threads
    """
    metrics = performance_tracker.get_metrics()
    return PerformanceResponse(
        time=metrics["time"],
        memory=metrics["memory"],
        threads=metrics["threads"],
    )
