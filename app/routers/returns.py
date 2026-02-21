"""
Returns Router: Endpoints for investment returns calculation.
"""
from fastapi import APIRouter, HTTPException, status
import logging

from app.models.schemas import ReturnsRequest, ReturnsResponse
from app.services.returns_service import ReturnsService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/blackrock/challenge/v1",
    tags=["Returns"],
)


@router.post(
    "/returns:nps",
    response_model=ReturnsResponse,
    summary="NPS Returns Calculator",
    description=(
        "Calculates investment returns using National Pension Scheme (NPS) "
        "at 7.11% compounded annually. Includes tax benefit calculation. "
        "NPS deduction limited to min(invested, 10% annual income, ₹2,00,000)."
    ),
)
async def calculate_nps_returns(request: ReturnsRequest):
    """
    Endpoint 4a: NPS Returns Calculation
    
    Processes transactions through q/p/k rules, then for each k period:
    - Sums valid remanents
    - Applies compound interest: A = P * (1 + 0.0711)^t
    - Adjusts for inflation: A_real = A / (1 + inflation)^t
    - Calculates profit = A_real - P
    - Calculates NPS tax benefit
    
    t = (60 - age) if age < 60, else 5
    """
    try:
        result = ReturnsService.calculate_nps(request)
        return result

    except Exception as e:
        logger.error(f"Error calculating NPS returns: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating NPS returns: {str(e)}",
        )


@router.post(
    "/returns:index",
    response_model=ReturnsResponse,
    summary="Index Fund Returns Calculator",
    description=(
        "Calculates investment returns using NIFTY 50 Index Fund "
        "at 14.49% compounded annually. No restrictions or tax benefits."
    ),
)
async def calculate_index_returns(request: ReturnsRequest):
    """
    Endpoint 4b: Index Fund Returns Calculation
    
    Processes transactions through q/p/k rules, then for each k period:
    - Sums valid remanents
    - Applies compound interest: A = P * (1 + 0.1449)^t
    - Adjusts for inflation: A_real = A / (1 + inflation)^t
    - Calculates profit = A_real - P
    - Tax benefit is always 0 for Index Fund
    
    t = (60 - age) if age < 60, else 5
    """
    try:
        result = ReturnsService.calculate_index(request)
        return result

    except Exception as e:
        logger.error(f"Error calculating index returns: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating index returns: {str(e)}",
        )
