# Handoff: notebook won't render in Positron

## Symptom
`day-metrics.ipynb` runs but charts don't render; repeated errors:
`externally-managed-environment`, `Mime type rendering requires nbformat>=4.2.0`,
blank Plotly chart in exported HTML.

## Root cause (one thing)
Positron starts the notebook kernel on **uv's managed base Python 3.11**
(`~/.local/share/uv/python/cpython-3.11.13-macos-aarch64-none`), not on the
project virtualenv `./.venv` (Python 3.12) where packages get installed.
- uv's base Python is PEP-668 "externally managed" -> `pip install` is refused.
- That interpreter is missing `nbformat`, so Plotly's inline `.show()` fails.
Every other error is downstream of this interpreter mismatch.

## The real fix (pick ONE)

### Option A - point Positron at a proper venv (recommended)
1. In a terminal, from the repo root:
   ```
   uv venv --python 3.12 .venv
   uv pip install -r inputs/requirements.txt
   .venv/bin/python -m ipykernel install --user --name day-trader
   ```
2. In Positron: Command Palette -> "Python: Select Interpreter" -> choose
   `./.venv/bin/python`. Then pick the "day-trader" kernel for the notebook.
3. Restart the kernel. Run all. Charts render inline.

### Option B - just produce the output, skip Positron entirely
Runs the whole notebook headless in a throwaway env and writes HTML:
```
uv run --python 3.12 --with-requirements inputs/requirements.txt \
  --with nbconvert --with ipykernel --with pip \
  jupyter nbconvert --to html --execute day-metrics.ipynb \
  --output day-metrics.html --output-dir outputs
```
For PDF: replace `--to html` with `--to webpdf --allow-chromium-download`.

## Notes / gotchas
- Plotly inline rendering needs `nbformat`; install it BEFORE the kernel starts
  (it's cached at import), so always restart the kernel after installing.
- `inputs/requirements.txt` must list each package once. A duplicate
  `nbformat` line was making `pip install -r` abort (fixed).
- The repo lives on an exFAT external drive, which sprays `._*` sidecar files
  and triggers "invalid distribution" pip warnings (cosmetic).
- Standalone chart already works: `fig.write_html("outputs/chart.html")` needs
  no nbformat and opens in any browser.

## Where to get help (human / community)
- Posit Community forum: https://forum.posit.co  (Positron category)
- Positron issues: https://github.com/posit-dev/positron/issues
- uv docs (environments/kernels): https://docs.astral.sh/uv
- Search terms that match this exact problem:
  "Positron Jupyter kernel uv venv select interpreter nbformat"
