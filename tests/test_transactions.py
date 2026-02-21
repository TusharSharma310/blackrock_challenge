"""
Test Type: Integration + Unit Tests
Validation: Transaction Builder, Validator, and Temporal Constraints Filter endpoints
Command: pytest tests/test_transactions.py -v

Tests cover:
- Transaction Builder (ceiling/remanent calculation)
- Transaction Validator (negatives, duplicates, consistency)
- Temporal Constraints Filter (q, p, k period rules)
- Edge cases: exact multiples of 100, empty lists, all invalid, etc.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.transaction_service import (
    calculate_ceiling_remanent,
    apply_q_rule_optimized,
    apply_p_rules,
    is_in_k_period,
)
from app.models.schemas import QPeriod, PPeriod, KPeriod
from datetime import datetime

client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit Tests: Core Financial Functions
# ---------------------------------------------------------------------------

class TestCalculateCeilingRemanent:
    """Unit tests for the core ceiling/remanent calculation."""

    def test_basic_rounding_250(self):
        ceiling, remanent = calculate_ceiling_remanent(250)
        assert ceiling == 300.0
        assert remanent == 50.0

    def test_basic_rounding_375(self):
        ceiling, remanent = calculate_ceiling_remanent(375)
        assert ceiling == 400.0
        assert remanent == 25.0

    def test_basic_rounding_620(self):
        ceiling, remanent = calculate_ceiling_remanent(620)
        assert ceiling == 700.0
        assert remanent == 80.0

    def test_basic_rounding_480(self):
        ceiling, remanent = calculate_ceiling_remanent(480)
        assert ceiling == 500.0
        assert remanent == 20.0

    def test_example_from_docs_1519(self):
        ceiling, remanent = calculate_ceiling_remanent(1519)
        assert ceiling == 1600.0
        assert remanent == 81.0

    def test_exact_multiple_of_100(self):
        """Exact multiples should round to next multiple (strictly next)."""
        ceiling, remanent = calculate_ceiling_remanent(500)
        assert ceiling == 600.0
        assert remanent == 100.0

    def test_amount_1(self):
        ceiling, remanent = calculate_ceiling_remanent(1)
        assert ceiling == 100.0
        assert remanent == 99.0

    def test_amount_99(self):
        ceiling, remanent = calculate_ceiling_remanent(99)
        assert ceiling == 100.0
        assert remanent == 1.0

    def test_large_amount(self):
        ceiling, remanent = calculate_ceiling_remanent(499999)
        assert ceiling == 500000.0
        assert remanent == 1.0

    def test_amount_100(self):
        ceiling, remanent = calculate_ceiling_remanent(100)
        assert ceiling == 200.0
        assert remanent == 100.0


# ---------------------------------------------------------------------------
# Unit Tests: Q Period Rules
# ---------------------------------------------------------------------------

class TestQPeriodRules:
    """Unit tests for q period (fixed override) logic."""

    def test_no_q_periods(self):
        """Without q periods, remanent is unchanged."""
        remanent = apply_q_rule_optimized(50.0, datetime(2023, 7, 1, 12, 0), [])
        assert remanent == 50.0

    def test_q_period_matches(self):
        """Transaction within q period uses fixed amount."""
        q = [QPeriod(fixed=0.0, start=datetime(2023, 7, 1), end=datetime(2023, 7, 31, 23, 59))]
        remanent = apply_q_rule_optimized(80.0, datetime(2023, 7, 1, 21, 59), q)
        assert remanent == 0.0

    def test_q_period_no_match(self):
        """Transaction outside q period keeps original remanent."""
        q = [QPeriod(fixed=0.0, start=datetime(2023, 7, 1), end=datetime(2023, 7, 31, 23, 59))]
        remanent = apply_q_rule_optimized(50.0, datetime(2023, 10, 12, 20, 15), q)
        assert remanent == 50.0

    def test_q_period_inclusive_start(self):
        """Start date is inclusive."""
        q = [QPeriod(fixed=10.0, start=datetime(2023, 7, 1, 0, 0), end=datetime(2023, 7, 31))]
        remanent = apply_q_rule_optimized(80.0, datetime(2023, 7, 1, 0, 0), q)
        assert remanent == 10.0

    def test_q_period_inclusive_end(self):
        """End date is inclusive."""
        q = [QPeriod(fixed=10.0, start=datetime(2023, 7, 1), end=datetime(2023, 7, 31, 23, 59))]
        remanent = apply_q_rule_optimized(80.0, datetime(2023, 7, 31, 23, 59), q)
        assert remanent == 10.0

    def test_q_multiple_periods_latest_start_wins(self):
        """When multiple q periods match, the one with latest start wins."""
        q = [
            QPeriod(fixed=0.0, start=datetime(2023, 7, 1), end=datetime(2023, 12, 31)),
            QPeriod(fixed=50.0, start=datetime(2023, 10, 1), end=datetime(2023, 12, 31)),
        ]
        # Oct 12 is in both; second has later start → fixed=50
        remanent = apply_q_rule_optimized(80.0, datetime(2023, 10, 12), q)
        assert remanent == 50.0

    def test_q_tie_on_start_first_in_list_wins(self):
        """When q periods tie on start date, first in list wins."""
        q = [
            QPeriod(fixed=30.0, start=datetime(2023, 10, 1), end=datetime(2023, 12, 31)),
            QPeriod(fixed=99.0, start=datetime(2023, 10, 1), end=datetime(2023, 12, 31)),
        ]
        remanent = apply_q_rule_optimized(80.0, datetime(2023, 10, 12), q)
        assert remanent == 30.0  # First in list


# ---------------------------------------------------------------------------
# Unit Tests: P Period Rules
# ---------------------------------------------------------------------------

class TestPPeriodRules:
    """Unit tests for p period (extra addition) logic."""

    def test_no_p_periods(self):
        """Without p periods, remanent is unchanged."""
        remanent = apply_p_rules(50.0, datetime(2023, 10, 12), [])
        assert remanent == 50.0

    def test_p_period_adds_extra(self):
        """P period adds extra amount to remanent."""
        p = [PPeriod(extra=25.0, start=datetime(2023, 10, 1, 8, 0), end=datetime(2023, 12, 31, 19, 59))]
        remanent = apply_p_rules(50.0, datetime(2023, 10, 12, 20, 15), p)
        assert remanent == 75.0

    def test_p_period_no_match(self):
        """Transaction outside p period keeps original remanent."""
        p = [PPeriod(extra=25.0, start=datetime(2023, 10, 1, 8, 0), end=datetime(2023, 12, 31, 19, 59))]
        remanent = apply_p_rules(25.0, datetime(2023, 2, 28, 15, 49), p)
        assert remanent == 25.0

    def test_p_multiple_periods_all_add(self):
        """All matching p periods add their extra amounts."""
        p = [
            PPeriod(extra=25.0, start=datetime(2023, 10, 1), end=datetime(2023, 12, 31)),
            PPeriod(extra=15.0, start=datetime(2023, 10, 1), end=datetime(2023, 12, 31)),
        ]
        remanent = apply_p_rules(50.0, datetime(2023, 10, 12), p)
        assert remanent == 90.0  # 50 + 25 + 15

    def test_p_applied_after_q_zero(self):
        """P adds to whatever remanent q set (even 0)."""
        # After q sets remanent to 0, p adds extra
        remanent = apply_p_rules(0.0, datetime(2023, 10, 12), [
            PPeriod(extra=25.0, start=datetime(2023, 10, 1), end=datetime(2023, 12, 31))
        ])
        assert remanent == 25.0


# ---------------------------------------------------------------------------
# Integration Tests: /transactions:parse
# ---------------------------------------------------------------------------

class TestParseEndpoint:
    """Integration tests for the Transaction Builder endpoint."""

    def test_parse_basic_example_from_docs(self):
        """Test the exact example from the design challenge PDF."""
        response = client.post("/blackrock/challenge/v1/transactions:parse", json=[
            {"date": "2023-10-12 20:15:30", "amount": 250},
            {"date": "2023-02-28 15:49:20", "amount": 375},
            {"date": "2023-07-01 21:59:00", "amount": 620},
            {"date": "2023-12-17 08:09:45", "amount": 480},
        ])
        assert response.status_code == 200
        data = response.json()
        transactions = data["transactions"]
        assert len(transactions) == 4

        # Verify each transaction
        tx_map = {tx["amount"]: tx for tx in transactions}
        assert tx_map[250]["ceiling"] == 300.0
        assert tx_map[250]["remanent"] == 50.0
        assert tx_map[375]["ceiling"] == 400.0
        assert tx_map[375]["remanent"] == 25.0
        assert tx_map[620]["ceiling"] == 700.0
        assert tx_map[620]["remanent"] == 80.0
        assert tx_map[480]["ceiling"] == 500.0
        assert tx_map[480]["remanent"] == 20.0

        # Verify totals
        assert data["totalAmount"] == 1725.0
        assert data["totalCeiling"] == 1900.0
        assert data["totalRemanent"] == 175.0

    def test_parse_empty_list(self):
        """Empty list should return zero totals."""
        response = client.post("/blackrock/challenge/v1/transactions:parse", json=[])
        assert response.status_code == 200
        data = response.json()
        assert data["totalAmount"] == 0.0
        assert data["totalCeiling"] == 0.0
        assert data["totalRemanent"] == 0.0

    def test_parse_single_expense(self):
        """Single expense should work correctly."""
        response = client.post("/blackrock/challenge/v1/transactions:parse", json=[
            {"date": "2023-01-01 10:00:00", "amount": 1519},
        ])
        assert response.status_code == 200
        data = response.json()
        tx = data["transactions"][0]
        assert tx["ceiling"] == 1600.0
        assert tx["remanent"] == 81.0

    def test_parse_exact_multiple_of_100(self):
        """Amount that is an exact multiple of 100 goes to next multiple."""
        response = client.post("/blackrock/challenge/v1/transactions:parse", json=[
            {"date": "2023-01-01 10:00:00", "amount": 500},
        ])
        assert response.status_code == 200
        data = response.json()
        tx = data["transactions"][0]
        assert tx["ceiling"] == 600.0
        assert tx["remanent"] == 100.0

    def test_parse_large_dataset(self):
        """Test with many transactions for performance."""
        expenses = [
            {"date": f"2023-01-{str(i+1).zfill(2)} 10:00:00", "amount": 100 + i}
            for i in range(28)  # Jan has 31 days, keep within range
        ]
        response = client.post("/blackrock/challenge/v1/transactions:parse", json=expenses)
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 28


# ---------------------------------------------------------------------------
# Integration Tests: /transactions:validator
# ---------------------------------------------------------------------------

class TestValidatorEndpoint:
    """Integration tests for the Transaction Validator endpoint."""

    def test_validator_negative_amount(self):
        """Negative amounts should be marked invalid."""
        response = client.post("/blackrock/challenge/v1/transactions:validator", json={
            "wage": 50000,
            "transactions": [
                {"date": "2023-07-10 09:15:00", "amount": -250, "ceiling": 200, "remanent": 30},
            ],
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["valid"]) == 0
        assert len(data["invalid"]) == 1
        assert "Negative" in data["invalid"][0]["message"]

    def test_validator_mixed_valid_invalid(self):
        """Mix of valid and invalid transactions."""
        response = client.post("/blackrock/challenge/v1/transactions:validator", json={
            "wage": 50000,
            "transactions": [
                {"date": "2023-01-15 10:30:00", "amount": 2000, "ceiling": 2100, "remanent": 100},
                {"date": "2023-03-20 14:45:00", "amount": 3500, "ceiling": 3600, "remanent": 100},
                {"date": "2023-06-10 09:15:00", "amount": 1500, "ceiling": 1600, "remanent": 100},
                {"date": "2023-07-10 09:15:00", "amount": -250, "ceiling": 200, "remanent": 30},
            ],
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["valid"]) == 3
        assert len(data["invalid"]) == 1

    def test_validator_duplicate_date(self):
        """Duplicate timestamps should be marked invalid."""
        response = client.post("/blackrock/challenge/v1/transactions:validator", json={
            "wage": 50000,
            "transactions": [
                {"date": "2023-01-15 10:30:00", "amount": 2000, "ceiling": 2100, "remanent": 100},
                {"date": "2023-01-15 10:30:00", "amount": 2000, "ceiling": 2100, "remanent": 100},
            ],
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["valid"]) == 1
        assert len(data["invalid"]) == 1
        assert "Duplicate" in data["invalid"][0]["message"]

    def test_validator_incorrect_ceiling(self):
        """Incorrect ceiling/remanent should be marked invalid."""
        response = client.post("/blackrock/challenge/v1/transactions:validator", json={
            "wage": 50000,
            "transactions": [
                {"date": "2023-01-15 10:30:00", "amount": 250, "ceiling": 400, "remanent": 150},
            ],
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["invalid"]) == 1
        assert "Ceiling" in data["invalid"][0]["message"] or "does not match" in data["invalid"][0]["message"]


# ---------------------------------------------------------------------------
# Integration Tests: /transactions:filter
# ---------------------------------------------------------------------------

class TestFilterEndpoint:
    """Integration tests for the Temporal Constraints Filter endpoint."""

    def test_filter_full_example_from_docs(self):
        """Test the complete example from the design challenge PDF."""
        payload = {
            "q": [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:59"}],
            "p": [{"extra": 25, "start": "2023-10-01 08:00:00", "end": "2023-12-31 19:59:59"}],
            "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "wage": 50000,
            "transactions": [
                {"date": "2023-02-28 15:49:20", "amount": 375},
                {"date": "2023-07-01 21:59:00", "amount": 620},
                {"date": "2023-10-12 20:15:30", "amount": 250},
                {"date": "2023-12-17 08:09:45", "amount": 480},
            ],
        }
        response = client.post("/blackrock/challenge/v1/transactions:filter", json=payload)
        assert response.status_code == 200
        data = response.json()

        valid = data["valid"]
        assert len(valid) == 4

        # Find each transaction by date
        tx_by_amount = {tx["amount"]: tx for tx in valid}

        # 375 (Feb 28): no q or p match → remanent=25
        assert tx_by_amount[375.0]["remanent"] == 25.0
        assert tx_by_amount[375.0]["inKPeriod"] is True

        # 620 (Jul 1): in q period → remanent=0; not in p
        assert tx_by_amount[620.0]["remanent"] == 0.0

        # 250 (Oct 12): not in q; in p (+25) → original=50, final=75
        assert tx_by_amount[250.0]["remanent"] == 75.0

        # 480 (Dec 17 08:09:45): not in q; in p (+25) → original=20, final=45
        assert tx_by_amount[480.0]["remanent"] == 45.0

    def test_filter_negative_amount_invalid(self):
        """Negative amounts should be marked invalid."""
        payload = {
            "q": [], "p": [], "k": [],
            "wage": 50000,
            "transactions": [
                {"date": "2023-10-12 20:15:30", "amount": -480},
            ],
        }
        response = client.post("/blackrock/challenge/v1/transactions:filter", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["valid"]) == 0
        assert len(data["invalid"]) == 1
        assert "Negative" in data["invalid"][0]["message"]

    def test_filter_duplicate_transaction_invalid(self):
        """Duplicate timestamps should be marked invalid."""
        payload = {
            "q": [], "p": [], "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "wage": 50000,
            "transactions": [
                {"date": "2023-10-12 20:15:30", "amount": 250},
                {"date": "2023-10-12 20:15:30", "amount": 250},
            ],
        }
        response = client.post("/blackrock/challenge/v1/transactions:filter", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["valid"]) == 1
        assert len(data["invalid"]) == 1
        assert "Duplicate" in data["invalid"][0]["message"]

    def test_filter_q_period_fix_to_zero(self):
        """Q period with fixed=0 sets remanent to 0."""
        payload = {
            "q": [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:59"}],
            "p": [], "k": [],
            "wage": 50000,
            "transactions": [
                {"date": "2023-07-15 10:00:00", "amount": 620},
            ],
        }
        response = client.post("/blackrock/challenge/v1/transactions:filter", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"][0]["remanent"] == 0.0

    def test_filter_p_adds_to_q_result(self):
        """P period adds to the remanent after q has been applied."""
        payload = {
            "q": [{"fixed": 0, "start": "2023-10-01 00:00:00", "end": "2023-10-31 23:59:59"}],
            "p": [{"extra": 30, "start": "2023-10-01 00:00:00", "end": "2023-10-31 23:59:59"}],
            "k": [],
            "wage": 50000,
            "transactions": [
                {"date": "2023-10-12 10:00:00", "amount": 250},
            ],
        }
        response = client.post("/blackrock/challenge/v1/transactions:filter", json=payload)
        assert response.status_code == 200
        data = response.json()
        # q sets to 0, then p adds 30 → remanent = 30
        assert data["valid"][0]["remanent"] == 30.0

    def test_filter_not_in_k_period(self):
        """Transactions outside k periods should have inKPeriod=False."""
        payload = {
            "q": [], "p": [],
            "k": [{"start": "2023-03-01 00:00:00", "end": "2023-11-30 23:59:59"}],
            "wage": 50000,
            "transactions": [
                {"date": "2023-02-28 15:49:20", "amount": 375},  # Before k period
                {"date": "2023-12-17 08:09:45", "amount": 480},  # After k period
                {"date": "2023-07-15 10:00:00", "amount": 250},  # Inside k period
            ],
        }
        response = client.post("/blackrock/challenge/v1/transactions:filter", json=payload)
        assert response.status_code == 200
        data = response.json()
        valid = data["valid"]
        tx_by_amount = {tx["amount"]: tx for tx in valid}

        assert tx_by_amount[375.0]["inKPeriod"] is False
        assert tx_by_amount[480.0]["inKPeriod"] is False
        assert tx_by_amount[250.0]["inKPeriod"] is True

    def test_filter_q_latest_start_wins(self):
        """Among multiple matching q periods, the latest start date wins."""
        payload = {
            "q": [
                {"fixed": 100.0, "start": "2023-07-01 00:00:00", "end": "2023-12-31 23:59:59"},
                {"fixed": 50.0, "start": "2023-10-01 00:00:00", "end": "2023-12-31 23:59:59"},
            ],
            "p": [], "k": [],
            "wage": 50000,
            "transactions": [
                {"date": "2023-10-12 10:00:00", "amount": 250},  # In both q periods
            ],
        }
        response = client.post("/blackrock/challenge/v1/transactions:filter", json=payload)
        assert response.status_code == 200
        data = response.json()
        # Second q period has later start (Oct 1 vs Jul 1) → fixed=50
        assert data["valid"][0]["remanent"] == 50.0


# ---------------------------------------------------------------------------
# Integration Tests: Health & Root
# ---------------------------------------------------------------------------

class TestHealthEndpoints:
    """Tests for health and root endpoints."""

    def test_root_endpoint(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_endpoint(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "memory" in data
        assert "threads" in data
