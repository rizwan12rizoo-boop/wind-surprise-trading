# =====================================================================
# STEP 4 - A simple forecast model (linear regression = "best-fit line")
#
# Question: can we guess tomorrow's day-ahead price using only things we
# KNOW before the auction? (wind forecast, solar forecast, hour, weekend)
#
# Fair test:
#   * Train (learn) on the first 80% of the dates.
#   * Test on the last 20% - data the model has NEVER seen.
#   * Compare with a "lazy" guess: "same price as yesterday, same hour".
#     If our model can't beat the lazy guess, it's useless.
#
# Run it:   python step4_forecast_model.py
# =====================================================================
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

from load_data import load_clean
from settings import CHART_DIR, data_label

df = load_clean()
label = data_label()

# "Lazy guess": price at the same hour yesterday
df["price_yesterday"] = df["price_da"].shift(24, freq="h").reindex(df.index)

# Inputs to the model (everything is known BEFORE the day-ahead auction)
X = pd.DataFrame({
    "wind_forecast_GW": df["wind_forecast"] / 1000,
    "solar_forecast_GW": df["solar_forecast"].fillna(0) / 1000,
    "is_weekend": df["is_weekend"],
    "price_yesterday": df["price_yesterday"],
})
X = X.join(pd.get_dummies(df["hour"], prefix="hour", drop_first=True).astype(int))
y = df["price_da"]

ok = X.notna().all(axis=1) & y.notna()
X, y = X[ok], y[ok]

# Split by TIME, not randomly (never let the model peek into the future)
cut = int(len(X) * 0.8)
X_train, X_test = X.iloc[:cut], X.iloc[cut:]
y_train, y_test = y.iloc[:cut], y.iloc[cut:]

model = LinearRegression().fit(X_train, y_train)
pred = pd.Series(model.predict(X_test), index=X_test.index)

mae_model = mean_absolute_error(y_test, pred)
mae_lazy = mean_absolute_error(y_test, X_test["price_yesterday"])
better = (1 - mae_model / mae_lazy) * 100 if mae_lazy else 0.0

results = [
    f"Data: {label}",
    f"Trained on {X_train.index.min():%Y-%m-%d} to {X_train.index.max():%Y-%m-%d}",
    f"Tested on  {X_test.index.min():%Y-%m-%d} to {X_test.index.max():%Y-%m-%d}",
    "",
    f"Average error, lazy guess (yesterday's price): {mae_lazy:6.1f} EUR/MWh",
    f"Average error, my model:                      {mae_model:6.1f} EUR/MWh",
    f"-> My model is {better:.0f}% more accurate than the lazy guess.",
    "",
    "What the model learned (effect on price, EUR/MWh):",
    f"  +1 GW more wind forecast  -> {model.coef_[0]:+.2f}",
    f"  +1 GW more solar forecast -> {model.coef_[1]:+.2f}",
    f"  weekend instead of weekday -> {model.coef_[2]:+.2f}",
]
text = "\n".join(results)
(CHART_DIR / "model_results.txt").write_text(text, encoding="utf-8")
print(text)

# Chart: two weeks of real vs predicted prices from the test period
window = slice(0, 24 * 14)
fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(y_test.iloc[window].index, y_test.iloc[window], label="Actual price", lw=1.6)
ax.plot(pred.iloc[window].index, pred.iloc[window], label="Model forecast", lw=1.6)
ax.set_ylabel("Day-ahead price (EUR/MWh)")
ax.set_title(f"Model forecast vs actual price, 2 test weeks  [{label} data]")
ax.legend()
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(CHART_DIR / "chart4_model_forecast.png", dpi=130)
plt.close(fig)
print("\nSaved chart4_model_forecast.png")
