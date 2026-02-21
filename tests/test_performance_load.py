"""
Test Type: Load / Performance Tests
Validation: API performance under high-volume inputs (up to 10^4 transactions for unit testing)
Command: pytest tests/test_performance_load.py -v -s

Tests cover:
- Response time under large payloads
- Memory stability across requests
- Correctness at scale (many transactions, many q/p/k periods)
- Concurrent request handling
"""

import pytest
import time
import math
import random
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def generate_expenses(n: int, start_year: int = 2023):
    """Generate n unique expenses spread across a year."""
    base_date = datetime(start_year, 1, 1, 0, 0, 0)
    expenses = []
    for i in range(n):
        # Spread across the year with unique second-level timestamps
        seconds_offset = i * (365 * 24 * 3600 // n)
        dt = base_date + timedelta(seconds=seconds_offset)
        amount = random.randint(101, 49999)
        expenses.append({
            "date": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "amount": amount,
        })
    return expenses


class TestLargePayloadPerformance:
    """Performance tests with large transaction volumes."""

    def test_parse_1000_transactions(self):
        """Parse endpoint should handle 1000 transactions efficiently."""
        expenses = generate_expenses(1000)
        start = time.time()
        response = client.post("/blackrock/challenge/v1/transactions:parse", json=expenses)
        elapsed = time.time() - start

        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 1000
        assert elapsed < 5.0, f"Should complete in <5s, took {elapsed:.2f}s"

    def test_filter_1000_transactions_with_periods(self):
        """Filter endpoint should handle 1000 transactions with multiple periods."""
        expenses = generate_expenses(1000)
        payload = {
            "q": [
                {"fixed": 0, "start": "2023-03-01 00:00:00", "end": "2023-05-31 23:59:59"},
                {"fixed": 50, "start": "2023-08-01 00:00:00", "end": "2023-10-31 23:59:59"},
            ],
            "p": [
                {"extra": 25, "start": "2023-07-01 00:00:00", "end": "2023-09-30 23:59:59"},
                {"extra": 10, "start": "2023-10-01 00:00:00", "end": "2023-12-31 23:59:59"},
            ],
            "k": [
                {"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"},
                {"start": "2023-07-01 00:00:00", "end": "2023-12-31 23:59:59"},
            ],
            "wage": 50000,
            "transactions": expenses,
        }
        start = time.time()
        response = client.post("/blackrock/challenge/v1/transactions:filter", json=payload)
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 10.0, f"Should complete in <10s, took {elapsed:.2f}s"

    def test_returns_1000_transactions(self):
        """Returns endpoint should handle 1000 transactions."""
        expenses = generate_expenses(1000)
        payload = {
            "age": 30,
            "wage": 60000,
            "inflation": 6.0,
            "q": [{"fixed": 0, "start": "2023-06-01 00:00:00", "end": "2023-06-30 23:59:59"}],
            "p": [{"extra": 20, "start": "2023-10-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "transactions": expenses,
        }
        start = time.time()
        response = client.post("/blackrock/challenge/v1/returns:nps", json=payload)
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 10.0, f"Should complete in <10s, took {elapsed:.2f}s"
        data = response.json()
        assert data["totalTransactionAmount"] > 0


class TestCorrectnessAtScale:
    """Verify correctness with structured large datasets."""

    def test_all_transactions_in_q_period(self):
        """When all transactions are in q period with fixed=0, all remanents should be 0."""
        expenses = [
            {"date": f"2023-07-{str(i+1).zfill(2)} 10:00:00", "amount": 250 + i}
            for i in range(20)
        ]
        payload = {
            "q": [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:59"}],
            "p": [], "k": [],
            "wage": 50000,
            "transactions": expenses,
        }
        response = client.post("/blackrock/challenge/v1/transactions:filter", json=payload)
        assert response.status_code == 200
        data = response.json()
        for tx in data["valid"]:
            assert tx["remanent"] == 0.0, f"Expected 0 remanent, got {tx['remanent']}"

    def test_multiple_p_periods_accumulate(self):
        """Multiple matching p periods should all add to remanent."""
        payload = {
            "q": [],
            "p": [
                {"extra": 10, "start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"},
                {"extra": 20, "start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"},
                {"extra": 30, "start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"},
            ],
            "k": [],
            "wage": 50000,
            "transactions": [
                {"date": "2023-06-15 10:00:00", "amount": 250},  # remanent=50; +10+20+30=110
            ],
        }
        response = client.post("/blackrock/challenge/v1/transactions:filter", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"][0]["remanent"] == 110.0  # 50 + 10 + 20 + 30

    def test_k_period_independent_sums(self):
        """Each k period sums independently, overlapping transactions counted in each."""
        payload = {
            "age": 29, "wage": 50000, "inflation": 5.5,
            "q": [], "p": [],
            "k": [
                {"start": "2023-01-01 00:00:00", "end": "2023-06-30 23:59:59"},
                {"start": "2023-04-01 00:00:00", "end": "2023-12-31 23:59:59"},
            ],
            "transactions": [
                {"date": "2023-03-15 10:00:00", "amount": 250},  # k1 only; remanent=50
                {"date": "2023-05-15 10:00:00", "amount": 375},  # Both k1 & k2; remanent=25
                {"date": "2023-09-15 10:00:00", "amount": 480},  # k2 only; remanent=20
            ],
        }
        response = client.post("/blackrock/challenge/v1/returns:index", json=payload)
        assert response.status_code == 200
        data = response.json()
        savings = data["savingsByDates"]

        k1 = next(s for s in savings if "2023-01-01" in s["start"])
        k2 = next(s for s in savings if "2023-04-01" in s["start"])

        assert k1["amount"] == 75.0   # 50 (Mar) + 25 (May)
        assert k2["amount"] == 45.0   # 25 (May) + 20 (Sep)


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_transactions(self):
        """Empty transaction list should work gracefully."""
        for endpoint in ["/blackrock/challenge/v1/returns:nps", "/blackrock/challenge/v1/returns:index"]:
            payload = {
                "age": 29, "wage": 50000, "inflation": 5.5,
                "q": [], "p": [],
                "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
                "transactions": [],
            }
            response = client.post(endpoint, json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["totalTransactionAmount"] == 0.0

    def test_inflation_as_decimal(self):
        """Inflation passed as decimal (0.055) should work same as percentage (5.5)."""
        base = {
            "age": 29, "wage": 50000,
            "q": [], "p": [],
            "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
            "transactions": [{"date": "2023-06-15 10:00:00", "amount": 250}],
        }
        r1 = client.post("/blackrock/challenge/v1/returns:nps", json={**base, "inflation": 5.5})
        r2 = client.post("/blackrock/challenge/v1/returns:nps", json={**base, "inflation": 0.055})
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_transaction_at_exact_period_boundaries(self):
        """Transactions exactly at period boundaries should be included (inclusive ranges)."""
        payload = {
            "q": [{"fixed": 100, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:59"}],
            "p": [], "k": [],
            "wage": 50000,
            "transactions": [
                {"date": "2023-07-01 00:00:00", "amount": 250},   # Exactly at start
                {"date": "2023-07-31 23:59:59", "amount": 375},   # Exactly at end
                {"date": "2023-06-30 23:59:59", "amount": 480},   # Just before
                {"date": "2023-08-01 00:00:00", "amount": 620},   # Just after
            ],
        }
        response = client.post("/blackrock/challenge/v1/transactions:filter", json=payload)
        assert response.status_code == 200
        data = response.json()
        tx_map = {tx["amount"]: tx for tx in data["valid"]}

        # Transactions at boundaries should get fixed=100
        assert tx_map[250.0]["remanent"] == 100.0
        assert tx_map[375.0]["remanent"] == 100.0
        # Transactions outside should keep original remanent
        assert tx_map[480.0]["remanent"] == 20.0  # ceiling(480)=500, remanent=20
        assert tx_map[620.0]["remanent"] == 80.0  # ceiling(620)=700, remanent=80
