"""
Pydantic schemas for all request/response models.
"""
from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, field_validator, model_validator
import math


DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_datetime(v: Any) -> datetime:
    """Parse datetime from various string formats."""
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        # Try various formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(v.strip(), fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse datetime: {v}")
    raise ValueError(f"Invalid datetime type: {type(v)}")


# ---------------------------------------------------------------------------
# Endpoint 1: Transaction Builder
# ---------------------------------------------------------------------------

class ExpenseInput(BaseModel):
    date: Any  # Will be validated as datetime
    amount: float

    @field_validator("date", mode="before")
    @classmethod
    def validate_date(cls, v):
        return parse_datetime(v)

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v):
        return float(v)


class TransactionOutput(BaseModel):
    date: str
    amount: float
    ceiling: float
    remanent: float

    @classmethod
    def from_values(cls, date: datetime, amount: float, ceiling: float, remanent: float):
        return cls(
            date=date.strftime(DATETIME_FORMAT),
            amount=amount,
            ceiling=ceiling,
            remanent=remanent,
        )


class ParseResponse(BaseModel):
    transactions: List[TransactionOutput]
    totalAmount: float
    totalCeiling: float
    totalRemanent: float


# ---------------------------------------------------------------------------
# Endpoint 2: Transaction Validator
# ---------------------------------------------------------------------------

class TransactionInput(BaseModel):
    date: Any
    amount: float
    ceiling: float
    remanent: float

    @field_validator("date", mode="before")
    @classmethod
    def validate_date(cls, v):
        return parse_datetime(v)

    @field_validator("amount", "ceiling", "remanent", mode="before")
    @classmethod
    def validate_float(cls, v):
        return float(v)


class ValidatorRequest(BaseModel):
    wage: float
    transactions: List[TransactionInput]

    @field_validator("wage", mode="before")
    @classmethod
    def validate_wage(cls, v):
        return float(v)


class InvalidTransaction(BaseModel):
    date: str
    amount: float
    ceiling: float
    remanent: float
    message: str


class ValidatorResponse(BaseModel):
    valid: List[TransactionOutput]
    invalid: List[InvalidTransaction]


# ---------------------------------------------------------------------------
# Endpoint 3: Temporal Constraints Filter
# ---------------------------------------------------------------------------

class QPeriod(BaseModel):
    fixed: float
    start: Any
    end: Any

    @field_validator("start", "end", mode="before")
    @classmethod
    def validate_datetime(cls, v):
        return parse_datetime(v)

    @field_validator("fixed", mode="before")
    @classmethod
    def validate_fixed(cls, v):
        return float(v)


class PPeriod(BaseModel):
    extra: float
    start: Any
    end: Any

    @field_validator("start", "end", mode="before")
    @classmethod
    def validate_datetime(cls, v):
        return parse_datetime(v)

    @field_validator("extra", mode="before")
    @classmethod
    def validate_extra(cls, v):
        return float(v)


class KPeriod(BaseModel):
    start: Any
    end: Any

    @field_validator("start", "end", mode="before")
    @classmethod
    def validate_datetime(cls, v):
        return parse_datetime(v)


class FilterExpenseInput(BaseModel):
    date: Any
    amount: float

    @field_validator("date", mode="before")
    @classmethod
    def validate_date(cls, v):
        return parse_datetime(v)

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v):
        return float(v)


class FilterRequest(BaseModel):
    q: List[QPeriod] = []
    p: List[PPeriod] = []
    k: List[KPeriod] = []
    wage: float = 0.0
    transactions: List[FilterExpenseInput]

    @field_validator("wage", mode="before")
    @classmethod
    def validate_wage(cls, v):
        return float(v)


class FilteredTransaction(BaseModel):
    date: str
    amount: float
    ceiling: float
    remanent: float
    inKPeriod: bool


class FilterInvalidTransaction(BaseModel):
    date: str
    amount: float
    message: str


class FilterResponse(BaseModel):
    valid: List[FilteredTransaction]
    invalid: List[FilterInvalidTransaction]


# ---------------------------------------------------------------------------
# Endpoint 4: Returns Calculation
# ---------------------------------------------------------------------------

class ReturnsRequest(BaseModel):
    age: int
    wage: float
    inflation: float
    q: List[QPeriod] = []
    p: List[PPeriod] = []
    k: List[KPeriod] = []
    transactions: List[FilterExpenseInput]

    @field_validator("wage", "inflation", mode="before")
    @classmethod
    def validate_float(cls, v):
        return float(v)

    @field_validator("age", mode="before")
    @classmethod
    def validate_age(cls, v):
        return int(v)


class SavingsByDate(BaseModel):
    start: str
    end: str
    amount: float
    profit: float
    taxBenefit: float


class ReturnsResponse(BaseModel):
    totalTransactionAmount: float
    totalCeiling: float
    savingsByDates: List[SavingsByDate]


# ---------------------------------------------------------------------------
# Endpoint 5: Performance Report
# ---------------------------------------------------------------------------

class PerformanceResponse(BaseModel):
    time: str
    memory: str
    threads: int
