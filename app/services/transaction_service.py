"""
Transaction Service: Core business logic for transaction processing.
Implements efficient algorithms for q/p/k period rules.
"""
from datetime import datetime
from typing import List, Tuple, Optional, Dict
import bisect

from app.models.schemas import (
    ExpenseInput, TransactionOutput, QPeriod, PPeriod, KPeriod,
    FilteredTransaction, FilterInvalidTransaction, ParseResponse,
    InvalidTransaction, ValidatorResponse, FilterResponse, TransactionInput,
    DATETIME_FORMAT
)


# ---------------------------------------------------------------------------
# Core Financial Calculations
# ---------------------------------------------------------------------------

def calculate_ceiling_remanent(amount: float) -> Tuple[float, float]:
    """
    Round amount UP to next strict multiple of 100.
    ceiling = (floor(amount/100) + 1) * 100
    remanent = ceiling - amount
    Example: 250 -> 300, remanent=50; 620 -> 700, remanent=80
    """
    ceiling = (int(amount) // 100 + 1) * 100
    remanent = ceiling - amount
    return float(ceiling), float(remanent)


def verify_ceiling_remanent(amount: float, ceiling: float, remanent: float) -> Optional[str]:
    """
    Verify that ceiling and remanent are consistent with amount.
    Returns error message if invalid, None if valid.
    """
    expected_ceiling, expected_remanent = calculate_ceiling_remanent(amount)
    if abs(ceiling - expected_ceiling) > 0.001:
        return f"Ceiling {ceiling} does not match expected {expected_ceiling} for amount {amount}"
    if abs(remanent - expected_remanent) > 0.001:
        return f"Remanent {remanent} does not match expected {expected_remanent} for amount {amount}"
    return None


# ---------------------------------------------------------------------------
# Period Rule Application (Optimized)
# ---------------------------------------------------------------------------

def apply_q_rule(
    remanent: float,
    date: datetime,
    q_periods: List[QPeriod],
    q_sorted_by_start_desc: List[Tuple[datetime, int, QPeriod]]
) -> float:
    """
    Apply q period rule:
    - Find all q periods where start <= date <= end
    - Use the one with latest start date
    - Tie-break: use first in original list (smallest index)
    
    q_sorted_by_start_desc: list of (start, original_index, period) sorted by start DESC
    """
    if not q_periods:
        return remanent

    best_period = None
    best_start = None
    best_idx = None

    for start, idx, period in q_sorted_by_start_desc:
        if start > date:
            continue  # start is after date, skip
        # start <= date, check end
        if period.end >= date:
            # This period matches
            if best_period is None:
                best_period = period
                best_start = start
                best_idx = idx
            elif start > best_start:
                best_period = period
                best_start = start
                best_idx = idx
            elif start == best_start and idx < best_idx:
                best_period = period
                best_start = start
                best_idx = idx
        # Since sorted by start DESC, once start < best_start, no better match
        # But we can't break early because later entries might have larger end

    if best_period is not None:
        return best_period.fixed

    return remanent


def apply_q_rule_optimized(
    remanent: float,
    date: datetime,
    q_periods: List[QPeriod],
) -> float:
    """
    Apply q period rule using linear scan.
    For each transaction, find the q period with the latest start that covers it.
    Tie-break: first in original list.
    """
    if not q_periods:
        return remanent

    best_period = None
    best_start = None
    best_idx = None

    for idx, period in enumerate(q_periods):
        if period.start <= date <= period.end:
            if (best_period is None
                    or period.start > best_start
                    or (period.start == best_start and idx < best_idx)):
                best_period = period
                best_start = period.start
                best_idx = idx

    if best_period is not None:
        return best_period.fixed

    return remanent


def apply_p_rules(
    remanent: float,
    date: datetime,
    p_periods: List[PPeriod],
) -> float:
    """
    Apply all matching p period rules:
    - For every p period where start <= date <= end, add extra to remanent
    - p rules always ADD (never replace), and all matching periods apply
    """
    for period in p_periods:
        if period.start <= date <= period.end:
            remanent += period.extra
    return remanent


def is_in_k_period(date: datetime, k_periods: List[KPeriod]) -> bool:
    """Check if a date falls within at least one k period."""
    for period in k_periods:
        if period.start <= date <= period.end:
            return True
    return False


def sum_remanents_in_k_period(
    transactions_with_remanents: List[Tuple[datetime, float]],
    k_period: KPeriod,
) -> float:
    """
    Sum remanents of all transactions whose dates fall within a k period.
    Transactions can belong to multiple k periods independently.
    """
    total = 0.0
    for date, remanent in transactions_with_remanents:
        if k_period.start <= date <= k_period.end:
            total += remanent
    return total


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------

def validate_basic(amount: float, seen_dates: Dict[str, bool], date: datetime) -> Optional[str]:
    """
    Basic validation: check for negative amounts and duplicate dates.
    Returns error message if invalid, None if valid.
    """
    if amount <= 0:
        return "Negative amounts are not allowed" if amount < 0 else "Amount must be positive"
    date_key = date.strftime(DATETIME_FORMAT)
    if date_key in seen_dates:
        return "Duplicate transaction"
    return None


# ---------------------------------------------------------------------------
# Service Functions
# ---------------------------------------------------------------------------

class TransactionService:
    """Service for transaction processing operations."""

    @staticmethod
    def parse_expenses(expenses: List[ExpenseInput]) -> ParseResponse:
        """
        Endpoint 1: Transaction Builder
        Calculate ceiling and remanent for each expense.
        """
        transactions = []
        total_amount = 0.0
        total_ceiling = 0.0
        total_remanent = 0.0

        for expense in expenses:
            ceiling, remanent = calculate_ceiling_remanent(expense.amount)
            tx = TransactionOutput.from_values(
                date=expense.date,
                amount=expense.amount,
                ceiling=ceiling,
                remanent=remanent,
            )
            transactions.append(tx)
            total_amount += expense.amount
            total_ceiling += ceiling
            total_remanent += remanent

        return ParseResponse(
            transactions=transactions,
            totalAmount=round(total_amount, 2),
            totalCeiling=round(total_ceiling, 2),
            totalRemanent=round(total_remanent, 2),
        )

    @staticmethod
    def validate_transactions(wage: float, transactions: List[TransactionInput]) -> ValidatorResponse:
        """
        Endpoint 2: Transaction Validator
        Validates transactions for:
        - Negative/zero amounts
        - Duplicate timestamps
        - Ceiling/remanent consistency
        """
        valid = []
        invalid = []
        seen_dates: Dict[str, bool] = {}

        for tx in transactions:
            date_key = tx.date.strftime(DATETIME_FORMAT)
            errors = []

            # Check for negative/zero amount
            if tx.amount < 0:
                errors.append("Negative amounts are not allowed")
            elif tx.amount == 0:
                errors.append("Amount must be positive")

            # Check for duplicate date
            if date_key in seen_dates and not errors:
                errors.append("Duplicate transaction")
            elif date_key in seen_dates:
                errors.append("Duplicate transaction")

            # Check ceiling/remanent consistency (only if amount is valid)
            if tx.amount > 0 and "Duplicate transaction" not in errors:
                consistency_error = verify_ceiling_remanent(tx.amount, tx.ceiling, tx.remanent)
                if consistency_error:
                    errors.append(consistency_error)

            if errors:
                inv = InvalidTransaction(
                    date=date_key,
                    amount=tx.amount,
                    ceiling=tx.ceiling,
                    remanent=tx.remanent,
                    message="; ".join(errors),
                )
                invalid.append(inv)
            else:
                seen_dates[date_key] = True
                valid.append(TransactionOutput(
                    date=date_key,
                    amount=tx.amount,
                    ceiling=tx.ceiling,
                    remanent=tx.remanent,
                ))

        return ValidatorResponse(valid=valid, invalid=invalid)

    @staticmethod
    def filter_transactions(
        q_periods: List[QPeriod],
        p_periods: List[PPeriod],
        k_periods: List[KPeriod],
        wage: float,
        transactions: List,
    ) -> FilterResponse:
        """
        Endpoint 3: Temporal Constraints Filter
        1. Validate transactions (negatives, duplicates)
        2. Calculate ceiling/remanent
        3. Apply q rules (fixed override)
        4. Apply p rules (extra addition)
        5. Check k period membership
        """
        valid = []
        invalid = []
        seen_dates: Dict[str, bool] = {}

        for tx in transactions:
            date_key = tx.date.strftime(DATETIME_FORMAT)

            # Validate
            if tx.amount < 0:
                invalid.append(FilterInvalidTransaction(
                    date=date_key,
                    amount=tx.amount,
                    message="Negative amounts are not allowed",
                ))
                continue

            if tx.amount == 0:
                invalid.append(FilterInvalidTransaction(
                    date=date_key,
                    amount=tx.amount,
                    message="Amount must be positive",
                ))
                continue

            if date_key in seen_dates:
                invalid.append(FilterInvalidTransaction(
                    date=date_key,
                    amount=tx.amount,
                    message="Duplicate transaction",
                ))
                continue

            seen_dates[date_key] = True

            # Step 1: Calculate ceiling and remanent
            ceiling, remanent = calculate_ceiling_remanent(tx.amount)

            # Step 2: Apply q rules
            remanent = apply_q_rule_optimized(remanent, tx.date, q_periods)

            # Step 3: Apply p rules
            remanent = apply_p_rules(remanent, tx.date, p_periods)

            # Step 4 (check): Is this transaction in any k period?
            in_k = is_in_k_period(tx.date, k_periods) if k_periods else True

            valid.append(FilteredTransaction(
                date=date_key,
                amount=tx.amount,
                ceiling=ceiling,
                remanent=round(remanent, 2),
                inKPeriod=in_k,
            ))

        return FilterResponse(valid=valid, invalid=invalid)
