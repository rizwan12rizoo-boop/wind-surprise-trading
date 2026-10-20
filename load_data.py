# Small helper so steps 3, 4 and 5 all load the clean data the same way.
import pandas as pd

from settings import CLEAN_FILE


def load_clean():
    df = pd.read_csv(CLEAN_FILE, index_col="time_utc")
    df.index = pd.to_datetime(df.index, utc=True)
    return df
