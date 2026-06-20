# Notebook path migration (subfolders, and the move up)

The notebooks now live in chapter subfolders, and the repo is about to move up a level.
Both changes break working-directory-relative paths like `Path("outputs")`. The fix is
one cell that finds the repo root by walking up until it sees `inputs/` and `outputs/`,
then anchors every path to it. This survives both moves, so it is done once.

The `inputs/` scripts (`build_dataset.py`, `train_model.py`, `walkforward.py`) already
resolve paths from their own file location, so they need no change.

## The repo-root cell (all three notebooks)

Paste this at the top of each notebook's setup cell, right after the Python-version
check, before anything that reads `inputs/` or writes `outputs/`:

```python
# Find the repo root so paths work wherever this notebook lives or whatever the
# working directory is (it now sits in a chapter subfolder, and the repo may move).
from pathlib import Path
import os

def _find_root(markers=("inputs", "outputs")):
    here = Path(os.getcwd()).resolve()
    for d in (here, *here.parents):
        if all((d / m).is_dir() for m in markers):
            return d
    raise FileNotFoundError("repo root not found: no parent has both inputs/ and outputs/")

ROOT = _find_root()
INPUTS = ROOT / "inputs"
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(exist_ok=True)
print("repo root:", ROOT)
```

## 01-trader-metrics.ipynb

Setup cell: after pasting the root cell above, change the requirements line:

```python
# was: REQUIREMENTS = Path("inputs/requirements.txt")
REQUIREMENTS = INPUTS / "requirements.txt"
```

Chart-save cell (the one with `outputs/chart.html`):

```python
# was: fig.write_html('outputs/chart.html', include_plotlyjs=True, auto_open=False)
fig.write_html(OUTPUTS / "chart.html", include_plotlyjs=True, auto_open=False)
# was: print('saved outputs/chart.html')
print("saved", OUTPUTS / "chart.html")
```

Daily-signals cell:

```python
# was: path = f'./outputs/DailySignals_{stamp}.csv'
path = OUTPUTS / f"DailySignals_{stamp}.csv"
```

## 02-trader-controls.ipynb

Only the setup cell changes; every other cell already uses the `OUTPUTS` variable, so
those become correct automatically. After pasting the root cell:

```python
# was: REQUIREMENTS = Path("inputs/requirements.txt")
REQUIREMENTS = INPUTS / "requirements.txt"

# was: OUTPUTS = Path("outputs"); OUTPUTS.mkdir(exist_ok=True)
# (delete this line - OUTPUTS now comes from the root cell)
```

Reminder, separate from paths: when you fold in the earlier screen guide, the journal
and candidate writes should also move to the format folders with the sample naming
(`OUTPUTS / "CSV" / f"2A-sample_{stamp}.csv"`, journal under `OUTPUTS / "AA-journal"`).

## 03-trader-execution.ipynb

This one I authored, so I can edit it directly if you prefer; here is the paste-in for
consistency. In the setup cell, replace the `inputs`-search block and the OUTPUTS lines:

```python
# was:
#   for cand in ["inputs", os.path.join("..", "inputs")]:
#       if os.path.isdir(cand):
#           sys.path.insert(0, os.path.abspath(cand)); break
#   OUTPUTS = Path("outputs"); CSV = OUTPUTS / "CSV"; MODEL_DIR = OUTPUTS / "3B-model-training"
# now (after the root cell defines ROOT / INPUTS / OUTPUTS):
sys.path.insert(0, str(INPUTS))
CSV = OUTPUTS / "CSV"
MODEL_DIR = OUTPUTS / "3B-model-training"
for d in (CSV, MODEL_DIR):
    d.mkdir(parents=True, exist_ok=True)
```

And the requirements line:

```python
# was: REQ = Path("inputs/requirements.txt")
REQ = INPUTS / "requirements.txt"
```

Move `03-trader-execution.ipynb` into `03-trader-execution/` so it matches the other two.
With the root cell in place it runs correctly from there.

## Suggested order

1. Apply the root cell and the replacements above to all three notebooks.
2. Move 03 into its chapter folder.
3. Do the move up to the parent repo whenever ready.
4. Reconnect the new top-level folder so I regain access, then I re-survey and verify a
   clean run.
