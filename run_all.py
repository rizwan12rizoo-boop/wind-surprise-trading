# Runs steps 1 to 5 one after another.   Run it:   python run_all.py
import runpy

for step in ["step1_get_data.py", "step2_clean_data.py", "step3_charts.py",
             "step4_forecast_model.py", "step5_backtest.py"]:
    print("\n" + "=" * 70 + f"\n RUNNING {step}\n" + "=" * 70)
    runpy.run_path(step, run_name="__main__")
print("\nAll done! Look in the charts/ folder.")
