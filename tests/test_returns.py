"""
Test Type: Integration + Unit Tests
Validation: Returns calculation for NPS and Index Fund investments
Command: pytest tests/test_returns.py -v

Tests cover:
- NPS returns with correct interest rate (7.11%)
- Index Fund returns with correct interest rate (14.49%)
- Inflation adjustment
- Tax benefit calculation (NPS only)
- Full pipeline integration (q/p/k rules + returns)
- Edge cases: age >= 60, zero investments, large amounts
"""

import pytest
import math
from fastapi.testclient import TestClient
from app.main import app
from app.services.returns_service import (
    calculate_tax,
    calculate_nps_tax_benefit,
    compound_interest,
    inflation_adjusted,
    calculate_years_to_retirement,
    NPS_RATE,
    INDEX_RATE,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit Tests: Tax Calculation
# ---------------------------------------------------------------------------

class TestTaxCalculation:
    """Unit tests for simplified Indian income tax calculation."""

    def test_income_below_7L(self):
        """Income up to 7L: 0% tax."""
        assert calculate_tax(600_000) == 0.0
        assert calculate_tax(700_000) == 0.0
        assert calculate_tax(0) == 0.0

    def test_income_in_7L_to_10L_slab(self):
        """Income 7L-10L: 10% on amount above 7L."""
        # 8L income: (8L - 7L) * 10% = 10,000
        assert calculate_tax(800_000) == 10_000.0
        # 10L income: (10L - 7L) * 10% = 30,000
        assert calculate_tax(1_000_000) == 30_000.0

    def test_income_in_10L_to_12L_slab(self):
        """Income 10L-12L: 30k + 15% on amount above 10L."""
        # 11L: 30k + (11L - 10L) * 15% = 30k + 15k = 45,000
        assert calculate_tax(1_100_000) == 45_000.0

    def test_income_in_12L_to_15L_slab(self):
        """Income 12L-15L: 60k + 20% on amount above 12L."""
        # 13L: (3L*10% + 2L*15% + 1L*20%) = 30k + 30k + 20k = 80k
        expected = 300_000 * 0.10 + 200_000 * 0.15 + 100_000 * 0.20
        assert abs(calculate_tax(1_300_000) - expected) < 0.01

    def test_income_above_15L(self):
        """Income above 15L: includes 30% slab."""
        # 16L: 30k + 30k + 60k + 30k = 150k
        expected = 300_000 * 0.10 + 200_000 * 0.15 + 300_000 * 0.20 + 100_000 * 0.30
        assert abs(calculate_tax(1_600_000) - expected) < 0.01

    def test_income_zero(self):
        """Zero income: 0 tax."""
        assert calculate_tax(0) == 0.0

    def test_negative_income(self):
        """Negative income: 0 tax."""
        assert calculate_tax(-1000) == 0.0


# ---------------------------------------------------------------------------
# Unit Tests: NPS Tax Benefit
# ---------------------------------------------------------------------------

class TestNPSTaxBenefit:
    """Unit tests for NPS tax benefit calculation."""

    def test_income_below_7L_no_benefit(self):
        """Income in 0% slab → no tax benefit."""
        benefit = calculate_nps_tax_benefit(145, 600_000)
        assert benefit == 0.0

    def test_nps_deduction_capped_by_income_10pct(self):
        """NPS deduction capped at 10% of annual income."""
        # Annual income = 10L, 10% = 1L → deduction = min(2L, 1L, invested)
        # If invested = 2L, deduction = 1L
        benefit = calculate_nps_tax_benefit(200_000, 1_000_000)
        # Tax(10L) = 30,000; Tax(10L - 1L = 9L) = 20,000
        expected = calculate_tax(1_000_000) - calculate_tax(900_000)
        assert abs(benefit - expected) < 0.01

    def test_nps_deduction_capped_at_2L(self):
        """NPS deduction capped at ₹2,00,000."""
        # High income, invested = 3L → deduction = min(3L, 10% of income, 2L) = 2L
        annual_income = 5_000_000  # 50L (high income)
        benefit = calculate_nps_tax_benefit(300_000, annual_income)
        expected = calculate_tax(annual_income) - calculate_tax(annual_income - 200_000)
        assert abs(benefit - expected) < 0.01

    def test_nps_deduction_capped_by_invested(self):
        """NPS deduction capped by actual invested amount."""
        # Low investment: 50k, income: 50L → deduction = min(50k, 5L, 2L) = 50k
        benefit = calculate_nps_tax_benefit(50_000, 5_000_000)
        expected = calculate_tax(5_000_000) - calculate_tax(4_950_000)
        assert abs(benefit - expected) < 0.01

    def test_zero_investment_no_benefit(self):
        """Zero investment → no tax benefit."""
        benefit = calculate_nps_tax_benefit(0, 1_000_000)
        assert benefit == 0.0


# ---------------------------------------------------------------------------
# Unit Tests: Compound Interest & Inflation
# ---------------------------------------------------------------------------

class TestCompoundInterest:
    """Unit tests for compound interest and inflation calculations."""

    def test_compound_interest_basic(self):
        """Basic compound interest calculation."""
        # A = 145 * (1.0711)^31 ≈ 1219 (from docs)
        result = compound_interest(145, NPS_RATE, 31)
        assert result > 1000  # Should be significantly larger
        assert result < 2000

    def test_compound_interest_zero_principal(self):
        """Zero principal → zero result."""
        assert compound_interest(0, NPS_RATE, 31) == 0.0

    def test_compound_interest_zero_years(self):
        """Zero years → principal unchanged."""
        assert compound_interest(1000, NPS_RATE, 0) == 1000.0

    def test_inflation_adjustment(self):
        """Inflation adjustment should reduce value."""
        nominal = compound_interest(145, NPS_RATE, 31)
        real = inflation_adjusted(nominal, 0.055, 31)
        # Real value should be less than nominal
        assert real < nominal
        # Should match approximately the doc example: ≈ 231.9
        assert 220 < real < 245

    def test_nps_full_calculation_matches_docs(self):
        """Full NPS calculation for docs example."""
        # P=145, r=7.11%, t=31, inflation=5.5%
        A = compound_interest(145, NPS_RATE, 31)
        real = inflation_adjusted(A, 0.055, 31)
        profit = real - 145
        # Docs say profit ≈ 86.88
        assert 80 < profit < 95

    def test_index_full_calculation_matches_docs(self):
        """Full Index Fund calculation for docs example."""
        # P=145, r=14.49%, t=31, inflation=5.5%
        A = compound_interest(145, INDEX_RATE, 31)
        real = inflation_adjusted(A, 0.055, 31)
        # Docs say real ≈ 1829.5
        assert 1700 < real < 1950


# ---------------------------------------------------------------------------
# Unit Tests: Years to Retirement
# ---------------------------------------------------------------------------

class TestYearsToRetirement:
    """Tests for retirement years calculation."""

    def test_age_29_gives_31_years(self):
        """Age 29 → 31 years (from docs example)."""
        assert calculate_years_to_retirement(29) == 31

    def test_age_below_60(self):
        """Age < 60 → 60 - age."""
        assert calculate_years_to_retirement(40) == 20
        assert calculate_years_to_retirement(55) == 5

    def test_age_60_or_above_gives_5(self):
        """Age >= 60 → minimum 5 years."""
        assert calculate_years_to_retirement(60) == 5
        assert calculate_years_to_retirement(70) == 5

    def test_very_young_age(self):
        """Young person has many years to retirement."""
        assert calculate_years_to_retirement(20) == 40


# ---------------------------------------------------------------------------
# Integration Tests: /returns:nps
# ---------------------------------------------------------------------------

class TestNPSReturns:
    """Integration tests for NPS returns endpoint."""

    BASE_PAYLOAD = {
        "age": 29,
        "wage": 50000,
        "inflation": 5.5,
        "q": [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:59"}],
        "p": [{"extra": 25, "start": "2023-10-01 08:00:00", "end": "2023-12-31 19:59:59"}],
        "k": [
            {"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"},
            {"start": "2023-03-01 00:00:00", "end": "2023-11-30 23:59:59"},
        ],
        "transactions": [
            {"date": "2023-02-28 15:49:20", "amount": 375},
            {"date": "2023-07-01 21:59:00", "amount": 620},
            {"date": "2023-10-12 20:15:30", "amount": 250},
            {"date": "2023-12-17 08:09:45", "amount": 480},
            {"date": "2023-12-17 08:09:45", "amount": -10},  # Invalid: negative & duplicate
        ],
    }

    def test_nps_returns_full_example(self):
        """Test NPS returns with the complete example from PDF."""
        response = client.post("/blackrock/challenge/v1/returns:nps", json=self.BASE_PAYLOAD)
        assert response.status_code == 200
        data = response.json()

        # Verify totals (only valid transactions: 375+620+250+480 = 1725)
        assert data["totalTransactionAmount"] == 1725.0
        assert data["totalCeiling"] == 1900.0

        # Verify savings by dates
        savings = data["savingsByDates"]
        assert len(savings) == 2

        # Full year k period: amount=145
        full_year = next(s for s in savings if "2023-01-01" in s["start"])
        assert full_year["amount"] == 145.0
        # profit should be approximately 86.88 (per docs)
        assert 80 < full_year["profit"] < 95
        # taxBenefit = 0 (income=6L, in 0% slab)
        assert full_year["taxBenefit"] == 0.0

        # Mar-Nov k period: amount=75
        mar_nov = next(s for s in savings if "2023-03-01" in s["start"])
        assert mar_nov["amount"] == 75.0
        assert 40 < mar_nov["profit"] < 55  # ~44.94

    def test_nps_empty_k_periods(self):
        """No k periods → empty savings list."""
        payload = {**self.BASE_PAYLOAD, "k": []}
        response = client.post("/blackrock/challenge/v1/returns:nps", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["savingsByDates"] == []

    def test_nps_all_invalid_transactions(self):
        """All invalid transactions → zero savings."""
        payload = {
            "age": 29, "wage": 50000, "inflation": 5.5,
            "q": [], "p": [],
            "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "transactions": [
                {"date": "2023-01-01 10:00:00", "amount": -100},
            ],
        }
        response = client.post("/blackrock/challenge/v1/returns:nps", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["totalTransactionAmount"] == 0.0
        assert data["savingsByDates"][0]["amount"] == 0.0

    def test_nps_high_income_tax_benefit(self):
        """High income should produce NPS tax benefit."""
        payload = {
            "age": 30, "wage": 150000, "inflation": 5.5,  # 18L annual
            "q": [], "p": [],
            "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "transactions": [
                {"date": "2023-06-15 10:00:00", "amount": 250},
            ],
        }
        response = client.post("/blackrock/challenge/v1/returns:nps", json=payload)
        assert response.status_code == 200
        data = response.json()
        # Annual income = 18L (above 15L slab), should get tax benefit
        assert data["savingsByDates"][0]["taxBenefit"] > 0


# ---------------------------------------------------------------------------
# Integration Tests: /returns:index
# ---------------------------------------------------------------------------

class TestIndexReturns:
    """Integration tests for Index Fund returns endpoint."""

    def test_index_returns_full_example(self):
        """Test Index Fund returns with the complete example from PDF."""
        payload = {
            "age": 29,
            "wage": 50000,
            "inflation": 5.5,
            "q": [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:59"}],
            "p": [{"extra": 25, "start": "2023-10-01 08:00:00", "end": "2023-12-31 19:59:59"}],
            "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "transactions": [
                {"date": "2023-02-28 15:49:20", "amount": 375},
                {"date": "2023-07-01 21:59:00", "amount": 620},
                {"date": "2023-10-12 20:15:30", "amount": 250},
                {"date": "2023-12-17 08:09:45", "amount": 480},
            ],
        }
        response = client.post("/blackrock/challenge/v1/returns:index", json=payload)
        assert response.status_code == 200
        data = response.json()

        savings = data["savingsByDates"]
        assert len(savings) == 1
        full_year = savings[0]

        # amount should be 145 (same as NPS since same q/p processing)
        assert full_year["amount"] == 145.0

        # Index profit should be much higher: ~1829.5 - 145 = 1684.5
        assert full_year["profit"] > 1000
        assert full_year["profit"] < 2500

        # Tax benefit should be 0 for Index Fund
        assert full_year["taxBenefit"] == 0.0

    def test_index_higher_return_than_nps(self):
        """Index Fund should produce higher returns than NPS."""
        payload = {
            "age": 29, "wage": 50000, "inflation": 5.5,
            "q": [], "p": [],
            "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "transactions": [
                {"date": "2023-06-15 10:00:00", "amount": 450},
            ],
        }
        nps_response = client.post("/blackrock/challenge/v1/returns:nps", json=payload)
        index_response = client.post("/blackrock/challenge/v1/returns:index", json=payload)

        nps_profit = nps_response.json()["savingsByDates"][0]["profit"]
        index_profit = index_response.json()["savingsByDates"][0]["profit"]

        # Index Fund rate (14.49%) >> NPS rate (7.11%)
        assert index_profit > nps_profit

    def test_age_above_60_uses_5_years(self):
        """Person aged >= 60 should use 5 years for investment calculation."""
        payload = {
            "age": 65, "wage": 50000, "inflation": 5.5,
            "q": [], "p": [],
            "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "transactions": [
                {"date": "2023-06-15 10:00:00", "amount": 250},
            ],
        }
        response = client.post("/blackrock/challenge/v1/returns:index", json=payload)
        assert response.status_code == 200
        # Should succeed with 5-year calculation
        data = response.json()
        assert data["savingsByDates"][0]["amount"] > 0

    def test_transaction_overlap_k_periods(self):
        """Transactions in overlapping k periods should be counted in each independently."""
        payload = {
            "age": 29, "wage": 50000, "inflation": 5.5,
            "q": [], "p": [],
            "k": [
                {"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"},
                {"start": "2023-06-01 00:00:00", "end": "2023-12-31 23:59:59"},
            ],
            "transactions": [
                {"date": "2023-03-15 10:00:00", "amount": 250},  # In k1 only
                {"date": "2023-07-15 10:00:00", "amount": 450},  # In both k1 and k2
            ],
        }
        response = client.post("/blackrock/challenge/v1/returns:index", json=payload)
        assert response.status_code == 200
        data = response.json()
        savings = data["savingsByDates"]

        # k1 (full year): both transactions → 50 + 50 = 100
        k1 = next(s for s in savings if "2023-01-01" in s["start"])
        assert k1["amount"] == 100.0  # remanent(250)=50 + remanent(450)=50

        # k2 (Jun-Dec): only Jul transaction → 50
        k2 = next(s for s in savings if "2023-06-01" in s["start"])
        assert k2["amount"] == 50.0  # remanent(450)=50


# ---------------------------------------------------------------------------
# Integration Tests: /performance
# ---------------------------------------------------------------------------

class TestPerformanceEndpoint:
    """Tests for the performance metrics endpoint."""

    def test_performance_returns_metrics(self):
        """Performance endpoint should return valid metrics."""
        response = client.get("/blackrock/challenge/v1/performance")
        assert response.status_code == 200
        data = response.json()
        assert "time" in data
        assert "memory" in data
        assert "threads" in data

    def test_performance_memory_format(self):
        """Memory should be in MB format."""
        response = client.get("/blackrock/challenge/v1/performance")
        data = response.json()
        assert "MB" in data["memory"]

    def test_performance_threads_positive(self):
        """Thread count should be positive."""
        response = client.get("/blackrock/challenge/v1/performance")
        data = response.json()
        assert data["threads"] > 0
