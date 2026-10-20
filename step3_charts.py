# =====================================================================
# STEP 3 - Draw pictures (charts)
#
# Makes 3 charts in the charts/ folder, and writes one sentence about
# each into charts/captions.md (use these sentences in your README).
#
#   chart1_surprise_vs_spread.png  Less wind than expected -> price jumps?
#   chart2_price_by_hour.png       Which hours are most expensive?
#   chart3_windy_vs_calm.png       Are windy days cheaper?
#
# Run it:   python step3_charts.py
# =====================================================================
import matplotlib
matplotlib.use("Agg")                # save charts to files, no pop-up windows
import matplotlib.pyplot as plt
import numpy as np

from load_data import load_clean
from settings import CHART_DIR, data_label

df = load_clean()
label = data_label()
captions = [f"# Chart captions ({label} data)\n"]

# ---------------------------------------------------------------------
# Chart 1: wind surprise vs spread
# ---------------------------------------------------------------------
d = df.dropna(subset=["spread"])
if d.empty:
    raise SystemExit("No real-time (imbalance) prices were downloaded, so charts can't be made.\n"
                     "Copy the step 1 messages and send them to Claude.")
sample = d.sample(min(6000, len(d)), random_state=1)

# average spread inside "buckets" of wind surprise (easier to read than dots)
buckets = np.arange(-6000, 6001, 1000)
d_b = d.assign(bucket=np.clip(np.round(d["wind_surprise"] / 1000) * 1000, -6000, 6000))
grouped = d_b.groupby("bucket")["spread"]
avg = grouped.mean()[grouped.count() >= 30]   # skip buckets with too few hours

slope = np.polyfit(d["wind_surprise"] / 1000, d["spread"], 1)[0]

fig, ax = plt.subplots(figsize=(9, 5.5))
ax.scatter(sample["wind_surprise"], sample["spread"], s=4, alpha=0.25,
           color="steelblue", label="one hour")
ax.plot(avg.index, avg.values, color="crimson", lw=2.5, marker="o",
        label="average per 1,000 MW bucket")
ax.axhline(0, color="black", lw=0.8)
ax.axvline(0, color="black", lw=0.8)
ax.set_ylim(d["spread"].quantile(0.01), d["spread"].quantile(0.99))
ax.set_xlabel("Wind surprise (MW)   <- less wind than forecast | more wind ->")
ax.set_ylabel("Real-time price minus day-ahead price (EUR/MWh)")
ax.set_title(f"When wind disappoints, the real-time price jumps  [{label} data]")
ax.legend()
fig.tight_layout()
fig.savefig(CHART_DIR / "chart1_surprise_vs_spread.png", dpi=130)
plt.close(fig)

captions.append(
    f"**Chart 1:** For every 1,000 MW of wind *missing* compared with the "
    f"forecast, the real-time price ended up about **{-slope:.1f} EUR/MWh higher** "
    f"than the day-ahead price.\n")

# ---------------------------------------------------------------------
# Chart 2: average day-ahead price by hour of day
# ---------------------------------------------------------------------
by_hour = df.groupby("hour")["price_da"].mean()
fig, ax = plt.subplots(figsize=(9, 5))
colors = ["darkorange" if h in (17, 18, 19, 20) else "grey" for h in by_hour.index]
ax.bar(by_hour.index, by_hour.values, color=colors)
ax.set_xticks(range(0, 24))
ax.set_xlabel("Hour of day (local time)")
ax.set_ylabel("Average day-ahead price (EUR/MWh)")
ax.set_title(f"Evening hours (orange) are the most expensive  [{label} data]")
fig.tight_layout()
fig.savefig(CHART_DIR / "chart2_price_by_hour.png", dpi=130)
plt.close(fig)

captions.append(
    f"**Chart 2:** The most expensive hour is **{by_hour.idxmax()}:00** "
    f"(avg {by_hour.max():.0f} EUR/MWh) and the cheapest is "
    f"**{by_hour.idxmin()}:00** (avg {by_hour.min():.0f} EUR/MWh). "
    f"Evenings are expensive because solar is gone but people still use power.\n")

# ---------------------------------------------------------------------
# Chart 3: windy days vs calm days
# ---------------------------------------------------------------------
daily = df.groupby("date").agg(wind=("wind_forecast", "mean"),
                               price=("price_da", "mean"))
calm_cut, windy_cut = daily["wind"].quantile([0.25, 0.75])
calm = daily[daily["wind"] <= calm_cut]["price"]
windy = daily[daily["wind"] >= windy_cut]["price"]

fig, ax = plt.subplots(figsize=(7, 5))
ax.boxplot([calm, windy], tick_labels=["Calm days\n(least wind 25%)",
                                       "Windy days\n(most wind 25%)"])
ax.set_ylabel("Daily average day-ahead price (EUR/MWh)")
ax.set_title(f"Windy days are cheaper  [{label} data]")
fig.tight_layout()
fig.savefig(CHART_DIR / "chart3_windy_vs_calm.png", dpi=130)
plt.close(fig)

captions.append(
    f"**Chart 3:** On calm days the average price was **{calm.mean():.0f} EUR/MWh**; "
    f"on windy days it was **{windy.mean():.0f} EUR/MWh**, "
    f"about {calm.mean() - windy.mean():.0f} EUR/MWh cheaper.\n")

(CHART_DIR / "captions.md").write_text("\n".join(captions), encoding="utf-8")
print("Saved 3 charts and captions to the charts/ folder:\n")
print("\n".join(captions))
