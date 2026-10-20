# =====================================================================
# check_markets.py - Which European markets have REAL-TIME prices on ENTSO-E?
#
# Our trading rule needs two prices: the day-ahead price AND the real-time
# (imbalance) price. ENTSO-E does not publish Germany's real-time price,
# so this script tests other markets for ONE week of data (takes ~1 minute).
#
# Run it:   python check_markets.py      (or open it in IDLE and press F5)
# =====================================================================
import pandas as pd

from step1_get_data import read_api_key

# market code -> name (all use Central European Time)
CANDIDATES = {
    "NL": "Netherlands",
    "BE": "Belgium",
    "DK_1": "Denmark West",
    "FR": "France",
    "AT": "Austria",
}

key = read_api_key()
if not key:
    raise SystemExit("No ENTSO-E key found in api_key.txt.")

from entsoe import EntsoePandasClient
client = EntsoePandasClient(api_key=key)

end = pd.Timestamp.now(tz="Europe/Berlin").normalize() - pd.Timedelta(days=30)
start = end - pd.Timedelta(days=7)


def works(func, code):
    try:
        data = func(code, start=start, end=end)
        return data is not None and len(data) > 0
    except Exception:
        return False


print(f"Testing one week of data ({start:%d %b} to {end:%d %b %Y}) ...\n")
print(f"{'market':<14}{'real-time price':<18}{'wind forecast':<16}{'day-ahead price'}")
good = []
for code, name in CANDIDATES.items():
    imb = works(client.query_imbalance_prices, code)
    wind = works(client.query_wind_and_solar_forecast, code)
    da = works(client.query_day_ahead_prices, code)
    tick = lambda ok: "yes" if ok else "no"
    print(f"{name:<14}{tick(imb):<18}{tick(wind):<16}{tick(da)}")
    if imb and wind and da:
        good.append((code, name))

print()
if good:
    code, name = good[0]
    print(f"Best choice: {name}. Open settings.py and change these two lines to:")
    print(f'    COUNTRY = "{code}"')
    print(f'    MARKET_NAME = "{name}"')
    print("Then run run_all.py again.")
else:
    print("None of these markets worked. Copy this whole window and send it to Claude.")
