import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from nbconvert.preprocessors.execute import CellExecutionError
REPO="/Volumes/PortableSSD/Github/day-trader"
src=f"{REPO}/03-trader-execution/03-trader-execution.ipynb"
out=f"{REPO}/outputs/03-trader-execution.executed.ipynb"
nb=nbformat.read(src, as_version=4)
patch=nbformat.v4.new_code_cell(
  "# [test harness] narrow the shared model zoo to LightGBM for a fast full-dataset pass.\n"
  "# Original notebook unchanged; this cell is injected only for the executed copy.\n"
  "import train_model as _tm\n"
  "_orig_bm=_tm.build_models\n"
  "_tm.build_models=lambda *a,**k:[(n,m) for (n,m) in _orig_bm(*a,**k) if n=='LightGBM']\n"
  "print('patched build_models -> LightGBM only')\n")
idx=next(i for i,c in enumerate(nb.cells)
         if c.cell_type=='code' and 'import train_model as tm' in ''.join(c.source))
nb.cells.insert(idx+1, patch)
ep=ExecutePreprocessor(timeout=3000, kernel_name="daytrader-venv", allow_errors=False)
status="OK"
try:
    ep.preprocess(nb, {"metadata":{"path":REPO}})
    print("NOTEBOOK_OK: all cells executed")
except CellExecutionError as e:
    status="ERROR"; print("CELL_EXECUTION_ERROR"); print(str(e)[:4000])
except Exception as e:
    status="ERROR"; print("OTHER_ERROR:", type(e).__name__, str(e)[:2000])
finally:
    nbformat.write(nb, out); print("wrote", out); print("STATUS:", status)
