# config.py
import os
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

# Used by main menu backtests
START_DATE = "2024-01-01"
END_DATE = "2025-11-01"

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
