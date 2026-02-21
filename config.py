"""
Application configuration management.
Uses environment variables for production deployments.
"""
import os
from typing import Optional


class Settings:
    """Application settings loaded from environment variables."""

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "5477"))
    WORKERS: int = int(os.getenv("WORKERS", "1"))

    # Investment rates (fixed per problem specification)
    NPS_ANNUAL_RATE: float = 0.0711      # 7.11%
    INDEX_ANNUAL_RATE: float = 0.1449    # 14.49%

    # NPS Tax constraints
    NPS_MAX_DEDUCTION: float = 200_000.0    # ₹2,00,000
    NPS_INCOME_PERCENT: float = 0.10        # 10%

    # Retirement settings
    RETIREMENT_AGE: int = 60
    MIN_INVESTMENT_YEARS: int = 5

    # Performance tracking
    MAX_REQUEST_HISTORY: int = 1000

    # API prefix
    API_PREFIX: str = "/blackrock/challenge/v1"

    # Debug
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


settings = Settings()
