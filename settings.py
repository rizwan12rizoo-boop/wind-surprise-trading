# =====================================================================
# settings.py  -  all the "knobs" of the project live here.
# If you want to change dates, the threshold, etc., change it HERE only.
# =====================================================================
from pathlib import Path

# ---- Which market ---------------------------------------------------
# Run check_markets.py to see which markets have real-time prices on ENTSO-E.
# Then type the market code here, e.g. "NL" (Netherlands) or "BE" (Belgium).
COUNTRY = "NL"               # Netherlands power market
MARKET_NAME = "Netherlands"  # used in chart titles and messages
TIMEZONE = "Europe/Berlin"   # Central European Time (same for NL, BE, FR, AT, DK)

# ---- Which dates (2 years of hourly data) ---------------------------
START = "2024-10-01"
END = "2026-10-19"

# ---- Your ENTSO-E key ----------------------------------------------
# Paste your key inside a file called api_key.txt (in this same folder).
# If that file is missing, the project uses PRACTICE (mock) data instead.
API_KEY_FILE = Path("api_key.txt")

# ---- Folders and files ----------------------------------------------
DATA_DIR = Path("data")
CHART_DIR = Path("charts")
RAW_FILE = DATA_DIR / "raw_hourly.csv"
CLEAN_FILE = DATA_DIR / "clean_hourly.csv"
SOURCE_FILE = DATA_DIR / "DATA_SOURCE.txt"   # says "REAL" or "PRACTICE"
COUNTRY_FILE = DATA_DIR / "DATA_COUNTRY.txt" # which market the saved data is for

# ---- Trading rule ----------------------------------------------------
# Signal: wind is much LOWER than expected. Measured in standard deviations,
# so it works for big markets (Germany) and small ones (Netherlands) alike.
THRESHOLD_STD = -1.5          # surprise below -1.5 standard deviations
MIN_TRADES = 30               # fewer trades than this = too few to trust
EVENING_HOURS = [17, 18, 19, 20]   # 5pm to 9pm, local time
SIGNAL_DELAY_HOURS = 2        # we only "see" the wind surprise 2 hours later
MAX_SURPRISE_STD = 6          # wind surprises bigger than 6 standard deviations = data errors
TRADING_COST_EUR = 1.0        # fee + slippage per trade (EUR per MWh)

DATA_DIR.mkdir(exist_ok=True)
CHART_DIR.mkdir(exist_ok=True)


def data_label():
    """Returns 'REAL' or 'PRACTICE' so charts can say which data they use."""
    if SOURCE_FILE.exists():
        return SOURCE_FILE.read_text().strip()
    return "UNKNOWN"
