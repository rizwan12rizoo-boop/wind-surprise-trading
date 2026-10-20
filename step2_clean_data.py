# =====================================================================
# STEP 2 - Clean the data and make the "surprise" column
#
# What this does:
#   1. Makes sure there is exactly ONE row for every hour.
#   2. Counts and removes empty rows (missing data).
#   3. Adds local time (hour of day, weekday, month).
#   4. Makes the two most important new columns:
#        wind_surprise = wind_actual - wind_forecast
#            negative  -> LESS wind than expected (bad for supply)
#        spread = price_imbalance - price_da
#            positive  -> real-time price ended up HIGHER than day-ahead
#
# Run it:   python step2_clean_data.py
# =====================================================================
import pandas as pd

from settings import CLEAN_FILE, MAX_SURPRISE_STD, RAW_FILE, TIMEZONE, data_label

df = pd.read_csv(RAW_FILE, index_col="time_utc", parse_dates=True)
df.index = pd.to_datetime(df.index, utc=True)

# 1. One row per hour (fill gaps with empty rows so we can count them)
full_hours = pd.date_range(df.index.min(), df.index.max(), freq="1h", tz="UTC")
df = df.reindex(full_hours)
df.index.name = "time_utc"
print(f"Data source: {data_label()}")
print(f"Hours in period: {len(df):,}")

# 2. Count and remove missing data
print("\nMissing values per column:")
print(df.isna().sum())
needed = ["price_da", "wind_forecast", "wind_actual"]
before = len(df)
df = df.dropna(subset=needed)
print(f"Removed {before - len(df):,} hours with missing price or wind data")

# 3. Local time columns
local = df.index.tz_convert(TIMEZONE)
df["local_time"] = local
df["date"] = local.date
df["hour"] = local.hour
df["weekday"] = local.dayofweek          # 0 = Monday, 6 = Sunday
df["is_weekend"] = (df["weekday"] >= 5).astype(int)
df["month"] = local.strftime("%Y-%m")

# 4. The important new columns
df["spread"] = df["price_imbalance"] - df["price_da"]
df["wind_surprise_raw"] = df["wind_actual"] - df["wind_forecast"]

# 4b. Remove the "usual" forecast miss (bias).
#     If the forecast is ALWAYS ~800 MW too low, the market already knows that,
#     so only the UNEXPECTED part is a real surprise. We subtract the typical
#     miss of the previous 30 days (past data only - no peeking at the future).
print(f"\nAverage wind forecast: {df['wind_forecast'].mean():,.0f} MW   "
      f"average actual wind: {df['wind_actual'].mean():,.0f} MW")
print(f"Average forecast miss (bias): {df['wind_surprise_raw'].mean():+,.0f} MW")
usual_miss = (df["wind_surprise_raw"]
              .rolling("30D", min_periods=24 * 7).median()
              .shift(1))
df["wind_surprise"] = df["wind_surprise_raw"] - usual_miss
before = len(df)
df = df.dropna(subset=["wind_surprise"])
print(f"Corrected the bias using the previous 30 days "
      f"(first {before - len(df):,} hours dropped: not enough history yet)")
print(f"Average surprise after correction: {df['wind_surprise'].mean():+,.0f} MW")

# 5. Remove impossible wind surprises (gaps in the source data, not real weather).
#    Anything bigger than 6 standard deviations is treated as a data error.
limit = MAX_SURPRISE_STD * df["wind_surprise"].std()
bad = df["wind_surprise"].abs() > limit
print(f"\nRemoved {bad.sum():,} hours with impossible wind surprises "
      f"(bigger than +/-{limit:,.0f} MW = data errors)")
df = df[~bad]

df.to_csv(CLEAN_FILE)
print(f"\nSaved clean data: {len(df):,} rows -> {CLEAN_FILE}")
print("\nQuick summary (EUR/MWh for prices, MW for wind):")
print(df[["price_da", "price_imbalance", "spread",
          "wind_forecast", "wind_surprise"]].describe().round(1))
