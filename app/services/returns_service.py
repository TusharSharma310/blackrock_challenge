"""
Returns Service: Financial returns calculation for NPS and Index Fund investments.
Implements compound interest, inflation adjustment, and NPS tax benefit calculations.
"""
from datetime import datetime
from typing import List, Tuple, Dict
import math

from app.models.schemas import (
    QPeriod, PPeriod, KPeriod, ReturnsRequest, ReturnsResponse,
    SavingsByDate, FilterExpenseInput, DATETIME_FORMAT
)
from app.services.transaction_service import (
    calculate_ceiling_remanent,
    apply_q_rule_optimized,
    apply_p_rules,
)


# ---------------------------------------------------------------------------
# Financial Constants
# ---------------------------------------------------------------------------

NPS_RATE = 0.0711        # 7.11% annual compounded
INDEX_RATE = 0.1449      # 14.49% annual compounded
NPS_MAX_DEDUCTION = 200_000.0   # ₹2,00,000 max NPS deduction
NPS_INCOME_PERCENT = 0.10       # 10% of annual income


# ---------------------------------------------------------------------------
# Tax Calculation (Simplified Indian Tax Slabs)
# ---------------------------------------------------------------------------

def calculate_tax(income: float) -> float:
    """
    Calculate simplified Indian income tax.
    Slabs:
      ₹0 - ₹7,00,000: 0%
      ₹7,00,001 - ₹10,00,000: 10% on amount above ₹7L
      ₹10,00,001 - ₹12,00,000: 15% on amount above ₹10L
      ₹12,00,001 - ₹15,00,000: 20% on amount above ₹12L
      Above ₹15,00,000: 30% on amount above ₹15L
    """
    if income <= 0:
        return 0.0

    tax = 0.0

    if income > 1_500_000:
        tax += (income - 1_500_000) * 0.30
        income = 1_500_000

    if income > 1_200_000:
        tax += (income - 1_200_000) * 0.20
        income = 1_200_000

    if income > 1_000_000:
        tax += (income - 1_000_000) * 0.15
        income = 1_000_000

    if income > 700_000:
        tax += (income - 700_000) * 0.10

    return tax


def calculate_nps_tax_benefit(invested_amount: float, annual_income: float) -> float:
    """
    Calculate NPS tax benefit:
    NPS_Deduction = min(invested, 10% of annual_income, ₹2,00,000)
    Tax_Benefit = Tax(income) - Tax(income - NPS_Deduction)
    """
    if invested_amount <= 0 or annual_income <= 0:
        return 0.0

    nps_deduction = min(
        invested_amount,
        NPS_INCOME_PERCENT * annual_income,
        NPS_MAX_DEDUCTION,
    )

    tax_without = calculate_tax(annual_income)
    tax_with = calculate_tax(annual_income - nps_deduction)
    benefit = tax_without - tax_with

    return max(0.0, benefit)


# ---------------------------------------------------------------------------
# Compound Interest & Inflation
# ---------------------------------------------------------------------------

def compound_interest(principal: float, rate: float, years: int) -> float:
    """
    A = P * (1 + r)^t  (n=1, compounded annually)
    """
    if principal <= 0 or years <= 0:
        return principal
    return principal * math.pow(1 + rate, years)


def inflation_adjusted(amount: float, inflation: float, years: int) -> float:
    """
    A_real = A / (1 + inflation)^t
    """
    if years <= 0:
        return amount
    return amount / math.pow(1 + inflation, years)


def calculate_years_to_retirement(age: int) -> int:
    """
    t = 60 - age if age < 60, else 5 (minimum investment horizon)
    """
    if age < 60:
        return max(60 - age, 1)  # at least 1 year
    return 5


# ---------------------------------------------------------------------------
# Transaction Processing Pipeline
# ---------------------------------------------------------------------------

def process_transactions_for_returns(
    transactions: List[FilterExpenseInput],
    q_periods: List[QPeriod],
    p_periods: List[PPeriod],
    k_periods: List[KPeriod],
) -> Tuple[float, float, List[Tuple[datetime, float, float]]]:
    """
    Process transactions through the full pipeline:
    Step 1: Calculate ceiling/remanent
    Step 2: Apply q rules
    Step 3: Apply p rules
    Step 4: (k grouping done by caller)

    Returns:
        (total_valid_amount, total_valid_ceiling, [(date, amount, final_remanent)])
    """
    seen_dates: Dict[str, bool] = {}
    result = []
    total_amount = 0.0
    total_ceiling = 0.0

    for tx in transactions:
        date_key = tx.date.strftime(DATETIME_FORMAT)

        # Validation
        if tx.amount <= 0:
            continue  # Skip invalid (negative/zero) transactions
        if date_key in seen_dates:
            continue  # Skip duplicates

        seen_dates[date_key] = True

        # Step 1: Calculate ceiling and remanent
        ceiling, remanent = calculate_ceiling_remanent(tx.amount)

        total_amount += tx.amount
        total_ceiling += ceiling

        # Step 2: Apply q rules (fixed override)
        remanent = apply_q_rule_optimized(remanent, tx.date, q_periods)

        # Step 3: Apply p rules (extra addition)
        remanent = apply_p_rules(remanent, tx.date, p_periods)

        result.append((tx.date, tx.amount, remanent))

    return total_amount, total_ceiling, result


# ---------------------------------------------------------------------------
# Returns Service
# ---------------------------------------------------------------------------

class ReturnsService:
    """Service for investment returns calculations."""

    @staticmethod
    def calculate_returns(
        request: ReturnsRequest,
        investment_rate: float,
        is_nps: bool,
    ) -> ReturnsResponse:
        """
        Calculate investment returns for a given investment vehicle.

        Args:
            request: Full returns request with transactions, periods, and parameters
            investment_rate: Annual compound interest rate
            is_nps: True for NPS (applies tax benefit), False for Index Fund
        """
        # Process transactions through the pipeline
        total_amount, total_ceiling, processed = process_transactions_for_returns(
            request.transactions,
            request.q,
            request.p,
            request.k,
        )

        # Calculate years to retirement
        years = calculate_years_to_retirement(request.age)

        # Annual income for NPS calculations
        annual_income = request.wage * 12

        # Step 4: Group by k periods and calculate returns
        savings_by_dates = []

        for k_period in request.k:
            # Sum remanents for transactions within this k period
            period_remanent = 0.0
            for date, amount, remanent in processed:
                if k_period.start <= date <= k_period.end:
                    period_remanent += remanent

            period_remanent = max(0.0, period_remanent)

            # Calculate compound interest: A = P * (1 + r)^t
            final_value = compound_interest(period_remanent, investment_rate, years)

            # Adjust for inflation: A_real = A / (1 + inflation)^t
            real_value = inflation_adjusted(final_value, request.inflation / 100 if request.inflation > 1 else request.inflation, years)

            # Calculate profit
            profit = real_value - period_remanent

            # Calculate tax benefit (NPS only)
            tax_benefit = 0.0
            if is_nps:
                tax_benefit = calculate_nps_tax_benefit(period_remanent, annual_income)

            savings_by_dates.append(SavingsByDate(
                start=k_period.start.strftime(DATETIME_FORMAT),
                end=k_period.end.strftime(DATETIME_FORMAT),
                amount=round(period_remanent, 2),
                profit=round(profit, 2),
                taxBenefit=round(tax_benefit, 2),
            ))

        return ReturnsResponse(
            totalTransactionAmount=round(total_amount, 2),
            totalCeiling=round(total_ceiling, 2),
            savingsByDates=savings_by_dates,
        )

    @staticmethod
    def calculate_nps(request: ReturnsRequest) -> ReturnsResponse:
        """Calculate returns for NPS investment (7.11% annual, with tax benefit)."""
        return ReturnsService.calculate_returns(request, NPS_RATE, is_nps=True)

    @staticmethod
    def calculate_index(request: ReturnsRequest) -> ReturnsResponse:
        """Calculate returns for Index Fund investment (14.49% annual, no tax benefit)."""
        return ReturnsService.calculate_returns(request, INDEX_RATE, is_nps=False)
