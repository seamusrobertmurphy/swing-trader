import sys, nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from nbconvert.preprocessors.execute import CellExecutionError
REPO="/Volumes/PortableSSD/Github/day-trader"
src=f"{REPO}/03-trader-execution/03-trader-execution.ipynb"
out=f"{REPO}/outputs/03-trader-execution.executed.ipynb"
nb=nbformat.read(src, as_version=4)
ep=ExecutePreprocessor(timeout=3000, kernel_name="daytrader-venv", allow_errors=False)
status="OK"
try:
    ep.preprocess(nb, {"metadata":{"path":REPO}})
    print("NOTEBOOK_OK: all cells executed")
except CellExecutionError as e:
    status="ERROR"
    print("CELL_EXECUTION_ERROR")
    print(str(e)[:4000])
except Exception as e:
    status="ERROR"
    print("OTHER_ERROR:", type(e).__name__, str(e)[:2000])
finally:
    nbformat.write(nb, out)
    print("wrote executed notebook ->", out)
    print("STATUS:", status)
