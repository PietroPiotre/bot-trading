# config.py
import os
from datetime import datetime, timedelta
from typing import Tuple

from dotenv import load_dotenv

load_dotenv()

# ░░ API CONFIG ░░
API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
TEST_MODE = os.getenv("TEST_MODE", "True") == "True"

# ░░ TRADING CONFIG ░░
DEFAULT_SYMBOL = "BNBUSDT"
DEFAULT_INTERVAL = "1h"

# Interval choices explicitly supported by the CLI / utilities
ALLOWED_INTERVALS = ("1m", "5m", "15m", "1h", "4h", "1d")

# ░░ BACKTEST PERIOD CONFIG ░░
PERIOD_DEFINITIONS = {
    "1m": {"label": "Dernier mois", "days": 30},
    "6m": {"label": "6 mois", "days": 182},
    "1y": {"label": "1 an", "days": 365},
    "2y": {"label": "2 ans", "days": 730},
}

ALLOWED_PERIODS = tuple(PERIOD_DEFINITIONS.keys())
DEFAULT_PERIOD = "1y"


def compute_period_bounds(period_code: str, end: datetime | None = None) -> Tuple[str, str]:
    """Return ISO formatted start/end dates for a named period.

    Args:
        period_code: Key referencing :data:`PERIOD_DEFINITIONS`.
        end: Optional ``datetime`` used as the end bound. Defaults to *now*.

    Returns:
        Tuple of strings (start_date, end_date) formatted ``"YYYY-MM-DD HH:MM:SS"``.
    """

    if period_code not in PERIOD_DEFINITIONS:
        period_code = DEFAULT_PERIOD

    end_dt = end or datetime.utcnow()
    end_dt = end_dt.replace(microsecond=0)

    days = PERIOD_DEFINITIONS[period_code]["days"]
    start_dt = end_dt - timedelta(days=days)

    return (
        start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
    )

# ░░ RISKS / MARKET COSTS ░░
INITIAL_CAPITAL = 10000
TRADING_FEE = 0.00075      # 0.075% Binance
SLIPPAGE = 0.0003          # 0.03% execution slippage
SPREAD = 0.0002            # 0.02% bid/ask spread
LATENCY_SEC = 5            # Execution delay (simulation)

# ░░ RSI PARAMETERS ░░
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 80

# ░░ MACD PARAMETERS ░░
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ░░ MOVING AVERAGES ░░
MA_FAST = 10
MA_SLOW = 30

# ░░ BOLLINGER BANDS ░░
BB_PERIOD = 20
BB_STD = 2

# ░░ DURATION OPTIONS FOR OPTIMIZER / BACKTESTER ░░
DURATION_CHOICES = {
    1: ("30 jours", 30),
    2: ("90 jours", 90),
    3: ("6 mois", 182),
    4: ("1 an", 365),
    5: ("2 ans", 730),
}
