Wind Surprise → Price Jump
Do wind forecast errors move European real-time power prices, and can a simple rule trade it?
Market: Netherlands (NL) · Data: ENTSO-E Transparency Platform, hourly, Oct 2024 – Oct 2026 · Tools: Python, pandas, scikit-learn, matplotlib
---
1. Question
Every day, the power market agrees a day-ahead price for each hour of tomorrow, based partly on a wind forecast.
When the real wind turns out lower than forecast, the grid is short of power and the real-time (imbalance) price should rise above the day-ahead price.
Is that effect real, how big is it, and can a simple rule capture it using only information a trader would actually have?
2. Data
	
Source	ENTSO-E Transparency Platform via `entsoe-py`
Series	Day-ahead price, imbalance (real-time) price, day-ahead wind & solar forecast, actual onshore + offshore wind
Period	Oct 2024 – Oct 2026, 17,784 hourly rows after cleaning
Why the Netherlands? I started with Germany, but ENTSO-E does not publish German imbalance prices (I tested all five German area codes). I wrote `check_markets.py` to test other markets automatically. The Netherlands had every series needed.
Data-quality steps (see `step2_clean_data.py`):
15-minute data averaged to hourly, all times in UTC, with local time added
Missing hours counted and removed
Forecast bias removed: actual wind averaged 2,559 MW against a forecast of 1,766 MW, a constant +793 MW miss. A miss the market always sees is not a surprise, so I subtract the median miss of the previous 30 days (past data only, no look-ahead). Average surprise after correction: +156 MW.
Impossible values (wind surprises over 6 standard deviations) treated as data errors
3. Findings
![](charts/chart1_surprise_vs_spread.png)
Wind surprise vs price. For every 1,000 MW of wind missing against expectations, the real-time price ended up about €12.3/MWh higher than the day-ahead price.
![](charts/chart2_price_by_hour.png)
Price by hour. The most expensive hour is 19:00 (avg €147/MWh) and the cheapest is 13:00 (avg €48/MWh): solar pushes midday prices down, and the evening peak arrives after the sun sets.
![](charts/chart3_windy_vs_calm.png)
Windy vs calm days. Calm days averaged €116/MWh, windy days €75/MWh: about €41 cheaper when it's windy.
![](charts/chart4_model_forecast.png)
Forecast model. A linear regression on wind forecast, solar forecast, hour, weekend and yesterday's price was 6% worse than simply using yesterday's price (average error €35.6 vs €33.6/MWh).
The model learned sensible effects (+1 GW wind → −€13.2, +1 GW solar → −€25.5, weekend → −€21.0), but it has no gas price or demand data, and those drive most of the price level. "Yesterday's price" carries that information implicitly, which is why it wins.
4. Trade idea and backtest
Rule: in the evening (17:00–21:00 local time), if the wind surprise 2 hours earlier was below −1.5 standard deviations (−1,320 MW), buy 1 MW for that hour.
Profit per trade = imbalance price − day-ahead price − €1 cost.
Why 2 hours earlier? Actual wind is only known after the fact, so using the same hour's surprise would be look-ahead bias. Forecast errors are "sticky", so a recent miss predicts the next few hours.
Why standard deviations? A 1,500 MW miss is small in Germany but large in the Netherlands. Standard deviations make the rule work for any market size.
Metric	Signal	Every evening hour (no signal)
Trades	90	—
Average per trade	€89.7	−€4.5
Median (typical) trade	−€2.2	−€24.2
Average without the top 1% price spikes	+€2.4	−€21.5
Win rate	49%	—
Total profit (1 MW)	€8,076	—
Worst losing streak	12 trades	—
Max drawdown	−€1,394	—
Losing months	7 of 19	—
Robustness: the bigger the surprise, the bigger the move.
Threshold (std)	MW	Trades	Median trade	Avg without spikes	Win %
−0.5	−440	793	−€21.9	−€17.4	33%
−1.0	−880	273	−€18.1	−€11.3	37%
−1.5	−1,320	90	−€2.2	+€2.4	49%
−2.0	−1,760	28	+€49.7	+€29.1	75%
−2.5	−2,200	6	+€72.1	+€56.6	83%
![](charts/chart5_equity_curve.png)
![](charts/chart6_profit_by_month.png)
5. Conclusion
The effect is real. The typical result improves steadily as the wind miss grows (a "dose-response" pattern), and the signal shifts the typical evening outcome by about €22/MWh compared with no signal.
But it is not a standalone money machine. Most of the €8,076 comes from rare scarcity spikes. Without the top 1% of price moves, the edge is only +€2.4 per trade, and the typical trade is slightly negative.
Best use: a risk signal. Avoid being short power on evenings when wind is disappointing, or size positions up only on the biggest surprises (−2 std and beyond), where results are strongest but trades are rare (28 in two years).
6. Risks: why this might not work live
Simplified execution: real desks trade the intraday market rather than holding positions into imbalance settlement, which is risky and regulated.
Spike dependence: a few extreme hours dominate total profit, so I report the median and spike-free results alongside it.
Small samples at strong thresholds: 28 trades at −2 std and 6 at −2.5 std are too few for firm conclusions.
Data bias: the constant +793 MW forecast gap suggests the forecast and actual series may not cover exactly the same wind farms. Corrected statistically, but worth confirming.
One market, two years: results need testing on other markets and periods.
7. What I'd do next
Add gas prices (TTF) and the load forecast (also on ENTSO-E) to the model, since those drive price levels
Use intraday forecast updates instead of realised wind, a cleaner and earlier signal
Test Belgium and other markets with published imbalance prices
Size positions by signal strength instead of a flat 1 MW
---
How to run it (Windows)
Install Python 3.11+ from python.org (tick "Add Python to PATH").
Install the libraries: `py -m pip install -r requirements.txt`
Put your ENTSO-E token in `api_key.txt` (without one, the project runs on practice data).
Optional: `py check_markets.py` shows which markets have real-time prices. Set `COUNTRY` in `settings.py`.
`py run_all.py` downloads everything and runs all steps (10–15 minutes).
After changing settings or analysis code: `py run_analysis.py` re-runs steps 2–5 without downloading again.
File	What it does
`settings.py`	All settings: market, dates, threshold
`check_markets.py`	Tests which markets have the data needed
`step1_get_data.py`	Downloads real data (or makes practice data)
`step2_clean_data.py`	Cleans data, removes forecast bias, builds wind surprise and spread
`step3_charts.py`	Charts 1–3 and their captions
`step4_forecast_model.py`	Price forecast model vs. a "yesterday's price" baseline
`step5_backtest.py`	Trading rule backtest with spike and robustness checks
`run_all.py` / `run_analysis.py`	Run everything / re-run the analysis only
