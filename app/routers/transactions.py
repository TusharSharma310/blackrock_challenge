"""
Transactions Router: Endpoints for transaction parsing, validation, and filtering.
"""
from typing import List
from fastapi import APIRouter, HTTPException, status
import logging

from app.models.schemas import (
    ExpenseInput, ParseResponse,
    ValidatorRequest, ValidatorResponse,
    FilterRequest, FilterResponse,
)
from app.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/blackrock/challenge/v1",
    tags=["Transactions"],
)


@router.post(
    "/transactions:parse",
    response_model=ParseResponse,
    summary="Transaction Builder",
    description=(
        "Receives a list of expenses and returns enriched transactions with "
        "ceiling and remanent fields. Also calculates totals."
    ),
)
async def parse_transactions(expenses: List[ExpenseInput]):
    """
    Endpoint 1: Transaction Builder
    
    Processes a list of expenses and calculates:
    - ceiling: next multiple of 100 above the expense amount
    - remanent: ceiling - amount (the amount to be invested)
    - totals for amount, ceiling, and remanent
    """
    try:
        if not expenses:
            return ParseResponse(
                transactions=[],
                totalAmount=0.0,
                totalCeiling=0.0,
                totalRemanent=0.0,
            )

        result = TransactionService.parse_expenses(expenses)
        return result

    except Exception as e:
        logger.error(f"Error parsing transactions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing transactions: {str(e)}",
        )


@router.post(
    "/transactions:validator",
    response_model=ValidatorResponse,
    summary="Transaction Validator",
    description=(
        "Validates a list of transactions. Returns valid and invalid transactions. "
        "Invalid reasons: negative amounts, duplicate timestamps, inconsistent ceiling/remanent."
    ),
)
async def validate_transactions(request: ValidatorRequest):
    """
    Endpoint 2: Transaction Validator
    
    Validates transactions for:
    - Negative or zero amounts
    - Duplicate timestamps (tᵢ ≠ tⱼ constraint)
    - Ceiling/remanent consistency with the amount
    """
    try:
        result = TransactionService.validate_transactions(request.wage, request.transactions)
        return result

    except Exception as e:
        logger.error(f"Error validating transactions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating transactions: {str(e)}",
        )


@router.post(
    "/transactions:filter",
    response_model=FilterResponse,
    summary="Temporal Constraints Validator",
    description=(
        "Validates and filters transactions according to q (fixed amount), "
        "p (extra addition), and k (evaluation grouping) period rules."
    ),
)
async def filter_transactions(request: FilterRequest):
    """
    Endpoint 3: Temporal Constraints Filter
    
    Processing pipeline:
    1. Validate transactions (negatives, duplicates)
    2. Calculate ceiling and remanent
    3. Apply q period rules (fixed override, latest start wins)
    4. Apply p period rules (all matching, additive)
    5. Determine k period membership (inKPeriod flag)
    """
    try:
        result = TransactionService.filter_transactions(
            q_periods=request.q,
            p_periods=request.p,
            k_periods=request.k,
            wage=request.wage,
            transactions=request.transactions,
        )
        return result

    except Exception as e:
        logger.error(f"Error filtering transactions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error filtering transactions: {str(e)}",
        )
