import time, nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from nbconvert.preprocessors.execute import CellExecutionError
REPO="/Volumes/PortableSSD/Github/day-trader"
src=f"{REPO}/03-trader-execution/03-trader-execution.ipynb"
out=f"{REPO}/outputs/03-trader-execution.fullsuite.ipynb"
nb=nbformat.read(src, as_version=4)
# full zoo, unpatched. Tight per-cell timeout so a stuck RandomForest fails fast.
ep=ExecutePreprocessor(timeout=900, kernel_name="daytrader-venv", allow_errors=False)
status="OK"; t0=time.time()
try:
    ep.preprocess(nb, {"metadata":{"path":REPO}})
    print(f"NOTEBOOK_OK: all cells executed in {time.time()-t0:.0f}s")
except CellExecutionError as e:
    status="ERROR"; print("CELL_EXECUTION_ERROR after %.0fs"%(time.time()-t0)); print(str(e)[:4000])
except Exception as e:
    status="ERROR"; print("OTHER_ERROR:", type(e).__name__, str(e)[:2000])
finally:
    nbformat.write(nb, out); print("wrote", out); print("STATUS:", status)
