# environment setup 06192026
REQUIREMENTS = Path("inputs/requirements.txt")
if not REQUIREMENTS.exists():
    raise FileNotFoundError(f"{REQUIREMENTS} not found — run from the repo root.")
subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
     "--break-system-packages", "--disable-pip-version-check",
     "-r", str(REQUIREMENTS)], check=True,)

# import package modules and naming
import warnings, numpy as np, pandas as pd
from datetime import datetime
import ccxt
import pandas_ta_classic as ta
from pykalman import KalmanFilter
import plotly, plotly.graph_objects as go, plotly.io as pio
warnings.filterwarnings("ignore")
pio.renderers.default = "plotly_mimetype+notebook_connected"  

# quick sanity check
print(f"Environment ready  ·  python {sys.version.split()[0]}  ({sys.executable})")
print(f"  ccxt {ccxt.__version__} · pandas {pd.__version__} · "
      f"numpy {np.__version__} · plotly {plotly.__version__}")