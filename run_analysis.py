# Runs steps 2 to 5 ONLY - re-uses the data you already downloaded.
# Use this after changing a setting or the analysis code. No waiting for downloads!
#   Run it:   python run_analysis.py      (or open in IDLE and press F5)
import runpy

for step in ["step2_clean_data.py", "step3_charts.py",
             "step4_forecast_model.py", "step5_backtest.py"]:
    print("\n" + "=" * 70 + f"\n RUNNING {step}\n" + "=" * 70)
    runpy.run_path(step, run_name="__main__")
print("\nAll done! Look in the charts/ folder.")
