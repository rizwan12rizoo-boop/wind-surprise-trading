# =====================================================================
# STEP 1 - Get the data
#
# What this does (simple version):
#   * If you have an ENTSO-E key in api_key.txt -> downloads REAL data.
#   * If not -> makes PRACTICE data that behaves like the real market,
#     so you can learn and test everything today.
#
# It saves 5 columns, one row per hour:
#   price_da         day-ahead price (EUR/MWh) - price agreed the day before
#   price_imbalance  "real-time" price (EUR/MWh) - price on the actual hour
#   wind_forecast    how much wind power was EXPECTED (MW)
#   wind_actual      how much wind power REALLY came (MW)
#   solar_forecast   how much solar power was expected (MW)
#
# Run it:   python step1_get_data.py
# =====================================================================
import numpy as np
import pandas as pd

from settings import (API_KEY_FILE, COUNTRY, COUNTRY_FILE, END, MARKET_NAME,
                      RAW_FILE, SOURCE_FILE, START, TIMEZONE)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def read_api_key():
    """Read the key from api_key.txt. Returns None if there is no key."""
    if not API_KEY_FILE.exists():
        return None
    key = API_KEY_FILE.read_text().strip()
    if not key or "PASTE" in key.upper():
        return None
    return key


def month_ranges():
    """ENTSO-E does not like huge requests, so we ask one month at a time."""
    starts = pd.date_range(START, END, freq="MS", tz=TIMEZONE)
    for s in starts:
        e = min(s + pd.offsets.MonthBegin(1), pd.Timestamp(END, tz=TIMEZONE))
        if s < e:
            yield s, e


def flatten_columns(piece):
    """Some months come back with 2-level column names. Make them 1-level."""
    if isinstance(piece, pd.DataFrame) and isinstance(piece.columns, pd.MultiIndex):
        piece = piece.copy()
        piece.columns = [" - ".join(str(x) for x in col if str(x)) for col in piece.columns]
    return piece


def download_month_by_month(name, func, clean=None, area=COUNTRY, **kwargs):
    """Call an entsoe-py function for every month and glue the pieces together.
    'clean' (optional) turns each month's piece into the same simple shape first,
    because ENTSO-E sometimes returns different table shapes for different months."""
    print(f"Downloading {name} ...")
    pieces = []
    for s, e in month_ranges():
        try:
            piece = func(area, start=s, end=e, **kwargs)
            piece = clean(piece) if clean else flatten_columns(piece)
            pieces.append(piece)
            print(f"   ok   {s:%Y-%m}")
        except Exception as error:          # e.g. no data for that month
            print(f"   skip {s:%Y-%m}  ({type(error).__name__}: {str(error)[:80]})")
    if not pieces:
        return None
    data = pd.concat(pieces)
    return data[~data.index.duplicated(keep="first")]


def to_hourly(series):
    """Data often comes every 15 minutes. We take the hourly average."""
    series = series.copy()
    series.index = pd.to_datetime(series.index, utc=True)
    return series.sort_index().resample("1h").mean()


def only_actual_generation(df):
    """query_generation can return extra columns. Keep 'Actual Aggregated' only."""
    if isinstance(df, pd.Series):
        return df
    if isinstance(df.columns, pd.MultiIndex):
        cols = [c for c in df.columns if "Actual Aggregated" in c]
        if cols:
            df = df[cols]
    else:
        cols = [c for c in df.columns if "Consumption" not in str(c)]
        df = df[cols]
    return df.sum(axis=1, min_count=1)


# Real-time (imbalance) prices can be stored under different area names.
# For Germany we also try the four grid operators' areas.
IMBALANCE_AREAS = [COUNTRY]
if COUNTRY.startswith("DE"):
    IMBALANCE_AREAS += ["DE_TENNET", "DE_AMPRION", "DE_50HZ", "DE_TRANSNET"]


def fetch_imbalance(client):
    """Try each area name. Test one week first, then download everything."""
    test_end = pd.Timestamp(END, tz=TIMEZONE) - pd.Timedelta(days=30)
    test_start = test_end - pd.Timedelta(days=7)
    for area in IMBALANCE_AREAS:
        try:
            test = client.query_imbalance_prices(area, start=test_start, end=test_end)
            if test is None or len(test) == 0:
                raise ValueError("empty answer")
        except Exception as error:
            print(f"   no imbalance prices under {area}  ({type(error).__name__}: {str(error)[:80]})")
            continue
        print(f"   found imbalance prices under {area}")
        data = download_month_by_month(f"imbalance prices ({area})",
                                       client.query_imbalance_prices, area=area)
        if data is not None:
            imb = data.mean(axis=1, numeric_only=True) if isinstance(data, pd.DataFrame) else data
            return to_hourly(imb)
    print(f"WARNING: ENTSO-E has no real-time (imbalance) prices for {MARKET_NAME}.")
    print("         Run check_markets.py to find a market that has them.")
    return None


def already_have_real_data():
    """True if a previous REAL download exists and only the imbalance prices are missing."""
    if not (RAW_FILE.exists() and SOURCE_FILE.exists() and COUNTRY_FILE.exists()
            and SOURCE_FILE.read_text().strip() == "REAL"
            and COUNTRY_FILE.read_text().strip() == COUNTRY):
        return None   # no earlier download for THIS market -> download everything
    old = pd.read_csv(RAW_FILE, index_col="time_utc", parse_dates=True)
    if old["price_da"].notna().any() and old["price_imbalance"].isna().all():
        old.index = pd.to_datetime(old.index, utc=True)
        return old
    return None


# ---------------------------------------------------------------------
# REAL data from ENTSO-E
# ---------------------------------------------------------------------
def get_real_data(key):
    from entsoe import EntsoePandasClient   # only needed for real data
    client = EntsoePandasClient(api_key=key)

    prices = download_month_by_month("day-ahead prices",
                                     client.query_day_ahead_prices)
    forecast = download_month_by_month("wind & solar forecast",
                                       client.query_wind_and_solar_forecast)
    onshore = download_month_by_month("actual onshore wind", client.query_generation,
                                      clean=only_actual_generation, psr_type="B19")
    offshore = download_month_by_month("actual offshore wind", client.query_generation,
                                       clean=only_actual_generation, psr_type="B18")
    print("Looking for imbalance (real-time) prices ...")
    imbalance = fetch_imbalance(client)

    if prices is None or forecast is None or onshore is None:
        raise RuntimeError("Could not download the main data. Check your key.")

    table = pd.DataFrame()
    table["price_da"] = to_hourly(prices)
    wind_cols = [c for c in forecast.columns if "Wind" in str(c)]
    table["wind_forecast"] = to_hourly(forecast[wind_cols].sum(axis=1, min_count=1))
    table["solar_forecast"] = to_hourly(forecast["Solar"]) if "Solar" in forecast else np.nan

    actual = only_actual_generation(onshore)
    if offshore is not None:
        actual = actual.add(only_actual_generation(offshore), fill_value=0)
    table["wind_actual"] = to_hourly(actual)

    table["price_imbalance"] = imbalance if imbalance is not None else np.nan
    return table


# ---------------------------------------------------------------------
# PRACTICE data (made-up, but behaves like the real market)
# ---------------------------------------------------------------------
def make_practice_data():
    print("No API key found -> making PRACTICE data (not real prices!).")
    rng = np.random.default_rng(42)
    idx = pd.date_range(START, END, freq="1h", tz="UTC", inclusive="left")
    n = len(idx)
    local = idx.tz_convert(TIMEZONE)
    hour = local.hour.values
    day_of_year = local.dayofyear.values
    weekend = (local.dayofweek.values >= 5).astype(float)

    def slow_wave(phi, size):
        """Random numbers that change slowly, like weather does."""
        out = np.zeros(n)
        shocks = rng.normal(0, size, n)
        for i in range(1, n):
            out[i] = phi * out[i - 1] + shocks[i]
        return out

    # Wind forecast: windier in winter, moves in slow "weather waves"
    winter = 1 + 0.4 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
    wind_forecast = np.clip(17000 * winter + slow_wave(0.98, 1800), 800, 58000)

    # The forecast is wrong in a "sticky" way: if it's wrong now,
    # it's probably still wrong 2 hours later.
    surprise = slow_wave(0.85, 800)
    wind_actual = np.clip(wind_forecast + surprise, 0, None)

    # Solar: only in daytime, stronger in summer, cloudy days are random
    summer = 0.7 + 0.3 * np.cos(2 * np.pi * (day_of_year - 172) / 365)
    sun_shape = np.clip(np.sin((hour - 6) / 13 * np.pi), 0, None)
    clouds = np.repeat(rng.uniform(0.4, 1.0, n // 24 + 1), 24)[:n]
    solar_forecast = 45000 * summer * sun_shape * clouds

    # Day-ahead price: high in the evening, low when windy or sunny
    evening = np.isin(hour, [17, 18, 19, 20]).astype(float)
    morning = np.isin(hour, [7, 8, 9]).astype(float)
    price_da = (105 + 30 * evening + 12 * morning - 12 * weekend
                - 1.7 * wind_forecast / 1000 - 1.1 * solar_forecast / 1000
                + rng.normal(0, 9, n))

    # Real-time price: jumps UP when wind is lower than forecast
    # (and the jump is bigger in the busy evening hours)
    strength = 0.006 * (1 + 0.5 * evening)
    price_imbalance = (price_da - strength * surprise
                       + rng.standard_t(3, n) * 30)

    return pd.DataFrame({
        "price_da": price_da.round(2),
        "price_imbalance": price_imbalance.round(2),
        "wind_forecast": wind_forecast.round(0),
        "wind_actual": wind_actual.round(0),
        "solar_forecast": solar_forecast.round(0),
    }, index=idx)


# ---------------------------------------------------------------------
if __name__ == "__main__":
    key = read_api_key()
    old = already_have_real_data() if key else None
    if old is not None:
        print("Re-using your earlier download. Only fetching the missing imbalance prices ...")
        from entsoe import EntsoePandasClient
        imbalance = fetch_imbalance(EntsoePandasClient(api_key=key))
        table = old
        if imbalance is not None:
            table["price_imbalance"] = imbalance.reindex(table.index)
        SOURCE_FILE.write_text("REAL")
    elif key:
        table = get_real_data(key)
        SOURCE_FILE.write_text("REAL")
    else:
        table = make_practice_data()
        SOURCE_FILE.write_text("PRACTICE")

    COUNTRY_FILE.write_text(COUNTRY)
    table.index.name = "time_utc"
    table.to_csv(RAW_FILE)
    print(f"\nSaved {len(table):,} hourly rows to {RAW_FILE}")
    print(table.head())
