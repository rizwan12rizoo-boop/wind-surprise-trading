# =====================================================================
# STEP 5 - Test the trading rule on the past (a "backtest")
#
# THE RULE (simple version):
#   "If 2 hours ago the wind was much LOWER than expected (below -1.5
#    standard deviations), and it is now evening (5pm-9pm), BUY 1 MW."
#
# Why "2 hours ago"? Because in real life you only find out the wind was
# wrong AFTER it happens. Using the surprise from the SAME hour would be
# cheating (looking into the future) - interviewers check for this!
# It still works because forecast mistakes are "sticky": if the forecast
# is too high now, it's usually still too high a few hours later.
#
# Why standard deviations instead of MW? A 1,500 MW miss is small in
# Germany but huge in the Netherlands. "1.5 standard deviations" means
# "an unusually big miss for THIS market", whatever its size.
#
# PROFIT of one trade = real-time price - day-ahead price - trading cost
#   (simplified: we buy at the day-ahead price, the hour settles at
#    the real-time price)
#
# HONESTY CHECKS (traders always ask about these):
#   * Too few trades?  -> warning, the result may be luck.
#   * A few huge price spikes doing all the work? -> we also show the
#     result WITHOUT the biggest 1% of price moves, and the MEDIAN trade.
#
# Run it:   python step5_backtest.py
# =====================================================================
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from load_data import load_clean
from settings import (CHART_DIR, EVENING_HOURS, MIN_TRADES, SIGNAL_DELAY_HOURS,
                      THRESHOLD_STD, TRADING_COST_EUR, data_label)

df = load_clean().dropna(subset=["spread"])
if df.empty:
    raise SystemExit("No real-time (imbalance) prices were downloaded, so the backtest can't run.")
label = data_label()

# What we KNEW at decision time: the wind surprise from 2 hours earlier
df["surprise_known"] = (df["wind_surprise"]
                        .shift(SIGNAL_DELAY_HOURS, freq="h")
                        .reindex(df.index))
df = df.dropna(subset=["surprise_known"])
is_evening = df["hour"].isin(EVENING_HOURS)

std = df["wind_surprise"].std()                # how big a "normal" miss is
spike_limit = df["spread"].abs().quantile(0.99)  # the biggest 1% of price moves


def run_rule(threshold_std):
    """Return the profit of every trade for a threshold in standard deviations."""
    signal = is_evening & (df["surprise_known"] <= threshold_std * std)
    return df.loc[signal, "spread"] - TRADING_COST_EUR


def worst_losing_streak(pnl):
    streak = worst = 0
    for p in pnl:
        streak = streak + 1 if p < 0 else 0
        worst = max(worst, streak)
    return worst


def report(pnl):
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    daily = pnl.groupby(pnl.index.date).sum()
    equity = pnl.cumsum()
    calm = pnl[(pnl + TRADING_COST_EUR).abs() <= spike_limit]   # without spikes
    return {
        "trades": len(pnl),
        "total": pnl.sum(),
        "avg": pnl.mean() if len(pnl) else np.nan,
        "median": pnl.median() if len(pnl) else np.nan,
        "avg_no_spikes": calm.mean() if len(calm) else np.nan,
        "win_rate": 100 * len(wins) / max(len(pnl), 1),
        "profit_factor": wins.sum() / abs(losses.sum()) if len(losses) else np.inf,
        "streak": worst_losing_streak(pnl),
        "drawdown": (equity - equity.cummax()).min() if len(pnl) else 0,
        "sharpe": daily.mean() / daily.std() * np.sqrt(252) if len(daily) > 1 and daily.std() > 0 else np.nan,
    }


# ---- 1. Main result -------------------------------------------------
pnl = run_rule(THRESHOLD_STD)
r = report(pnl)
always = df.loc[is_evening, "spread"] - TRADING_COST_EUR   # no signal at all
a = report(always)

lines = [
    f"BACKTEST RESULTS  [{label} data]  (1 MW per trade, EUR)",
    f"Rule: buy evening hours when the wind surprise {SIGNAL_DELAY_HOURS}h earlier is below "
    f"{THRESHOLD_STD} std ({THRESHOLD_STD * std:,.0f} MW)",
    f"Trading cost assumed: {TRADING_COST_EUR} EUR/MWh",
    f"'Spikes' = the biggest 1% of price moves (bigger than +/-{spike_limit:,.0f} EUR/MWh)",
    "",
    f"Number of trades:          {r['trades']:,}",
    f"Total profit:              {r['total']:,.0f} EUR",
    f"Average per trade:         {r['avg']:.1f} EUR",
    f"Median (typical) trade:    {r['median']:.1f} EUR",
    f"Average WITHOUT spikes:    {r['avg_no_spikes']:.1f} EUR",
    f"Win rate:                  {r['win_rate']:.0f}%",
    f"Profit factor:             {r['profit_factor']:.2f}  (above 1 = wins bigger than losses)",
    f"Worst losing streak:       {r['streak']} trades in a row",
    f"Biggest drop (drawdown):   {r['drawdown']:,.0f} EUR",
    f"Sharpe ratio:              {r['sharpe']:.2f}",
]
if r["trades"] < MIN_TRADES:
    lines += ["", f"WARNING: only {r['trades']} trades - fewer than {MIN_TRADES}. "
                  "Too few to trust; the result could be luck."]

lines += [
    "",
    "Is the wind signal really helping? Compare with no signal at all:",
    f"  {'':24}{'avg':>8}{'median':>9}{'no spikes':>11}",
    f"  {'Buy EVERY evening hour':24}{a['avg']:>8.1f}{a['median']:>9.1f}{a['avg_no_spikes']:>11.1f}",
    f"  {'Buy only with signal':24}{r['avg']:>8.1f}{r['median']:>9.1f}{r['avg_no_spikes']:>11.1f}",
    "",
    "Does the result depend on the exact threshold? (robustness check)",
    f"  {'std':>5} {'MW':>7} {'trades':>7} {'avg':>7} {'median':>7} {'no spikes':>10} {'win %':>6}",
]
for t in [-0.5, -1.0, -1.5, -2.0, -2.5]:
    rr = report(run_rule(t))
    lines.append(f"  {t:>5} {t * std:>7,.0f} {rr['trades']:>7} {rr['avg']:>7.1f} "
                 f"{rr['median']:>7.1f} {rr['avg_no_spikes']:>10.1f} {rr['win_rate']:>6.0f}")

# ---- 2. When does it FAIL? ---------------------------------------
monthly = pnl.groupby(df.loc[pnl.index, "month"]).sum()
bad = monthly[monthly < 0]
lines += ["",
          f"Losing months: {len(bad)} of {len(monthly)}",
          "Worst month:  " + (f"{monthly.idxmin()} ({monthly.min():,.0f} EUR)" if len(monthly) else "-")]

text = "\n".join(lines)
(CHART_DIR / "backtest_results.txt").write_text(text, encoding="utf-8")
print(text)

# ---- 3. Charts ------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(pnl.cumsum().values, color="seagreen", lw=1.8)
ax.axhline(0, color="black", lw=0.8)
ax.set_xlabel("Trade number")
ax.set_ylabel("Total profit so far (EUR)")
ax.set_title(f"Wind-surprise rule: profit over time  [{label} data]")
fig.tight_layout()
fig.savefig(CHART_DIR / "chart5_equity_curve.png", dpi=130)
plt.close(fig)

fig, ax = plt.subplots(figsize=(11, 5))
ax.bar(monthly.index, monthly.values,
       color=["crimson" if v < 0 else "seagreen" for v in monthly.values])
ax.axhline(0, color="black", lw=0.8)
ax.set_ylabel("Profit in that month (EUR)")
ax.set_title(f"Profit by month - red bars show when the rule failed  [{label} data]")
plt.setp(ax.get_xticklabels(), rotation=60, ha="right")
fig.tight_layout()
fig.savefig(CHART_DIR / "chart6_profit_by_month.png", dpi=130)
plt.close(fig)
print("\nSaved chart5_equity_curve.png and chart6_profit_by_month.png")
