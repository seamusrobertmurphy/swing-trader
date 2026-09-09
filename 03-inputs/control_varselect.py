"""The two interactive additions to panel A3, variable selection.

Operator instruction, 9 September 2026, in
05-research/tasks/eval-control-centre-v2.md. A3 reported each predictor fitted
alone and nothing about what happens when predictors are fitted together, which
is the question the elastic net answers by selection and never by estimate. Two
things go on the panel and they answer the same question two ways.

The coefficient path shows the order in which predictors survive a penalty.
variable_selection.plot_coefpath_interactive has drawn it since the module was
written and nothing had ever displayed it, because it wrote a whole HTML
document to disk and there was no reusable state behind it. The screen now dumps
the fitted path as JSON beside the picture, so the figure here is redrawn from
numbers carrying the sample size, the penalty mixing, the panel and the training
cut that produced them. The alternative was to re-serve the saved coefpath.html,
which is a run from 8 September whose settings nobody wrote down.

The multivariate table shows what the estimates become once several predictors
are in together. Tick a column, and the fit is redone: a few thousand rows by a
handful of columns is milliseconds, so it is served on demand rather than
precomputed.

Three things the table has to say rather than let pass.

The outcome is nought or one. An ordinary least squares fit on a binary outcome
is a linear probability model, and its coefficient is a change in the
probability of the barrier being hit, not a change in a continuous quantity. It
is the most readable thing to put in front of a reader and it is what the
operator asked for, so it leads, and it is named for what it is. Its classical
standard errors assume a constant error variance, which a binary outcome cannot
have, so the White HC1 standard error is reported beside each classical one and
a logistic fit of the same predictor set sits underneath.

The point is the change. Every predictor's univariate estimate, read from the
screen already on disk at 04-outputs/AA-evals/varselect/univariate-*.json, is
shown beside its current multivariate one with the difference between them. A
predictor whose sign flips when its neighbours are added is the finding, and
neither fit alone shows it. Both estimates are on standardised columns, which is
what makes them comparable at all, and the comparison is logistic against
logistic because a log-odds and a probability change are different quantities.

The training window only. train_model_1h.split holds out the configured blind
period and the fit never sees it.
"""

from __future__ import annotations

import glob
import html
import json
import os
import time
import warnings
from pathlib import Path

import numpy as np
from flask import Blueprint, jsonify, request

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "04-outputs" / "AA-evals"
VARSELECT = EVALS / "varselect"

# The cap on what a refit reads. The panel this page is pointed at can be the
# 1.64-million-row hourly one, and holding that whole frame to fit six columns
# is how this machine gets its process killed: it is already several gigabytes
# into swap before anything is read. bench_run caps at load and this caps again
# at the fit, on the most recent rows, and the panel prints the cap so a reader
# knows the estimate is not from every row in the window.
FIT_ROWS = 20_000

# One frame at a time, keyed by the settings that produced it. A second entry
# would double the memory for no gain, since every refit on a panel asks the
# same configuration for the same rows and only the column list changes.
_FRAME: dict = {}


# ---------------------------------------------------------------------------
# Fragments that say what is missing rather than raising
# ---------------------------------------------------------------------------

def _missing(why: str) -> str:
    return f'<div class="interactive"><div class="inote">{html.escape(why)}</div></div>'


def _newest(pattern: str) -> Path | None:
    hits = [h for h in sorted(glob.glob(str(VARSELECT / pattern)), reverse=True)
            if not os.path.basename(h).startswith("._")]
    return Path(hits[0]) if hits else None


def _pval(p: float) -> str:
    """The house floor: a p-value is never printed as zero."""
    if p is None or not np.isfinite(p):
        return "&#8195;"
    return "&lt; 0.001" if p < 0.001 else f"{p:.3f}"


# ---------------------------------------------------------------------------
# The coefficient path
# ---------------------------------------------------------------------------

def _plotly_div(fig, div_id: str, height: int) -> str:
    """A figure that draws once plotly has actually arrived.

    plotly.io.to_html emits a bare `Plotly.newPlot(...)` beside the div and
    expects the library to be defined by the time the browser reaches it. On
    this page it is not: card.html loads control_static/plotly.min.js in the
    scripts block at the foot of the document, which on a rendered A3 sits at
    character 109,118 while the figures' newPlot calls sit at 14,839 and 34,680.
    Every one of them throws ReferenceError: Plotly is not defined and leaves a
    box of the right height with nothing in it, which is what a headless render
    of A2 and A3 both showed on 9 September 2026. Waiting for the symbol rather
    than for an event covers the case where the fragment is inserted after the
    document has already finished loading, when neither DOMContentLoaded nor
    load will fire again.
    """
    # A literal </script> anywhere inside the JSON, in a column name or a hover
    # string, closes the script element early and the rest of the figure lands
    # on the page as text. Escaping the sequence costs nothing and the browser
    # reads "<\/" as "</" inside a string literal.
    spec = fig.to_json().replace("</", r"<\/")
    return (
        f'<div id="{div_id}" style="height:{height}px; width:100%;"></div>'
        f'<script>(function(){{'
        f'var spec = {spec};'
        f'var el = document.getElementById("{div_id}"); var tries = 0;'
        f'function draw(){{'
        f'  if (window.Plotly) {{'
        f'    Plotly.newPlot(el, spec.data, spec.layout,'
        f'      {{displaylogo:false, responsive:true,'
        f'        modeBarButtonsToRemove:["select2d","lasso2d"]}});'
        f'    return; }}'
        f'  if (++tries > 100) {{'
        f'    el.innerHTML = "<p class=\\"note\\">plotly did not load, so this '
        f'figure could not be drawn. The library is served from '
        f'/control_static/plotly.min.js.</p>"; return; }}'
        f'  setTimeout(draw, 100); }}'
        f'draw(); }})();</script>')


def coefficient_path() -> str:
    """The elastic-net paths, redrawn from the dumped fit."""
    import variable_selection as vs

    path = VARSELECT / "coefpath.json"
    if not path.exists():
        return _missing(
            "No coefficient path on disk. Run the elastic-net screen from the "
            "panel above; it writes coefpath.json beside its figures. Until it "
            "has run under settings this page recorded, there is nothing here "
            "whose provenance can be stated.")
    res = vs.load_coefpath(path)
    meta = res.get("meta") or {}
    fig = vs.coefpath_figure(res, top_k=14)
    fig.update_layout(
        template="simple_white", height=430,
        margin=dict(l=52, r=16, t=34, b=38),
        font=dict(family="Helvetica Neue, Helvetica, Arial, sans-serif",
                  size=11, color="#16202c"),
        title=dict(text="Which coefficients outlast the others as the penalty relaxes",
                   font=dict(size=13)),
        legend=dict(orientation="h", y=-0.30, font=dict(size=10)))
    body = _plotly_div(fig, "vs-coefpath", 430)

    mix = ("lasso" if res["l1_ratio"] == 1 else "ridge" if res["l1_ratio"] == 0
           else f"elastic net, mixing {res['l1_ratio']:g}")
    note = (
        f"Every offered column's coefficient against the log of the penalty, "
        f"fitted by {mix} on {meta.get('rows', res['n']):,} rows of "
        f"{html.escape(str(meta.get('source', 'the panel')))}, base rate "
        f"{float(meta.get('base_rate', float('nan'))):.3f}, "
        f"{meta.get('features', len(res['names']))} columns offered. Read it "
        f"right to left: at the strongest penalty every path is at zero, and a "
        f"column leaves zero at the penalty where it first earns its place. "
        f"&lambda;.1se keeps "
        f"{int(res['nonzero'][res['i_1se']])} of {len(res['names'])} and "
        f"&lambda;.min keeps {int(res['nonzero'][res['i_min']])}. Drag the "
        f"slider under the axis to a stretch of penalties, click a name in the "
        f"key to hide it, hover any line for its column and value. Fitted "
        f"{html.escape(str(res.get('stamped', ''))[:16].replace('T', ' '))}; "
        f"the blind period is not in it.")
    return (f'<div class="interactive"><div class="inote">{note}</div>{body}</div>')


def _enet_survivors() -> list[str]:
    """What the dumped path retained at lambda.1se, largest first."""
    path = VARSELECT / "coefpath.json"
    if not path.exists():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    row = doc["coefs"][doc["i_1se"]]
    keep = [(n, v) for n, v in zip(doc["names"], row) if abs(v) > 1e-8]
    return [n for n, _ in sorted(keep, key=lambda t: -abs(t[1]))]


# ---------------------------------------------------------------------------
# The training rows, and the univariate estimates to compare against
# ---------------------------------------------------------------------------

def offered() -> tuple[dict, list[str]]:
    """The configuration this page is set to, and the columns it offers."""
    import bench_config as bc
    import bench_run as br

    cfg = bc.load()
    _df, available = _panel(cfg)
    return cfg, br.choose_features(cfg, available, log=lambda *_a, **_k: None)


def _panel(cfg: dict):
    """The configured panel's training window, cached, capped, read once."""
    import bench_config as bc
    import bench_run as br
    import train_model_1h as t1

    key = json.dumps([cfg["data"], cfg["split"]["holdout_days"]], sort_keys=True,
                     default=str)
    if _FRAME.get("key") == key:
        return _FRAME["train"], _FRAME["available"]

    df, available = br.load_frame(cfg, log=lambda *_a, **_k: None)
    train, _test, cut = t1.split(df, oos_days=int(cfg["split"]["holdout_days"]))
    del df                                  # the blind rows are dropped here and
                                            # the whole frame released with them
    n_window = len(train)
    if n_window > FIT_ROWS:
        train = train.tail(FIT_ROWS)
    _FRAME.clear()
    _FRAME.update(key=key, train=train.reset_index(drop=True),
                  available=available,
                  meta=dict(cut=str(cut.date()), window=n_window,
                            rows=len(train), frame=cfg["data"]["frame"],
                            symbols=cfg["data"]["symbols"] or "every symbol",
                            describe=bc.describe(cfg)))
    return _FRAME["train"], available


def univariate() -> tuple[dict, dict]:
    """The screen already on disk: each predictor's estimate fitted alone."""
    path = _newest("univariate-*.json")
    if path is None:
        return {}, {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}, {}
    rows = {r["feature"]: r for r in doc.get("rows", [])}
    meta = dict(file=path.name, n_train=doc.get("n_train"),
                cut=doc.get("cut"), base_rate=doc.get("base_rate"),
                n=len(rows))
    return rows, meta


# ---------------------------------------------------------------------------
# The fit
# ---------------------------------------------------------------------------

def fit(cols: list[str]) -> dict:
    """One multivariate fit of the chosen columns on the training window.

    Ordinary least squares and logistic on the same standardised design, so the
    linear probability model's readable coefficients and the log-odds every
    other model in this repository speaks in can be read against each other.
    """
    import pandas as pd
    import statsmodels.api as sm

    cfg, feats = offered()
    unknown = [c for c in cols if c not in feats]
    if unknown:
        # A column name arriving from a browser is not trusted to be a column.
        # Without this the endpoint would read any field of the frame a caller
        # named, including the label itself, and a fit of the label on the
        # label would come back looking like a perfect model.
        return dict(error=f"not offered by this configuration: {', '.join(unknown[:6])}")
    if not cols:
        return dict(error="No column is ticked. Tick one or more and the fit runs.")

    train, _available = _panel(cfg)
    meta = dict(_FRAME["meta"])
    t0 = time.perf_counter()

    X = train[cols].astype(float)
    y = train["label"].astype(float)
    ok = np.isfinite(X.to_numpy()).all(axis=1) & np.isfinite(y.to_numpy())
    dropped = int((~ok).sum())
    X, y = X[ok], y[ok]
    if len(y) < 10 * (len(cols) + 1):
        return dict(error=f"{len(y):,} complete rows is too few for {len(cols)} "
                          f"predictors; ten rows per predictor is the floor here.")

    sd = X.std(ddof=0)
    flat = [c for c in cols if not np.isfinite(sd[c]) or sd[c] == 0]
    if flat:
        return dict(error="constant on these rows, so it has no estimate: "
                          + ", ".join(flat))
    # Standardised, because the univariate screen this table is compared against
    # standardised too, and a log-odds per standard deviation is the only form
    # in which coefficients on columns measured in different units can be read
    # against each other at all.
    Z = (X - X.mean()) / sd
    D = sm.add_constant(Z, has_constant="add")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            ols = sm.OLS(y, D).fit()
        except (np.linalg.LinAlgError, ValueError) as exc:
            return dict(error=f"the least-squares fit is singular at this "
                              f"selection ({type(exc).__name__}: {exc}). Two of "
                              f"the ticked columns carry the same information.")
        logit, logit_note = _logit(sm, D, y)

    ci = ols.conf_int()
    hc1 = pd.Series(ols.HC1_se, index=D.columns)
    uni, uni_meta = univariate()

    rows = []
    for name in cols:
        u = uni.get(name)
        lg = None
        if logit is not None:
            lg = dict(coef=float(logit.params[name]), se=float(logit.bse[name]),
                      z=float(logit.tvalues[name]), p=float(logit.pvalues[name]))
        change = flip = None
        if u is not None and lg is not None:
            change = lg["coef"] - float(u["coef"])
            flip = np.sign(lg["coef"]) != np.sign(float(u["coef"]))
        rows.append(dict(
            name=name,
            coef=float(ols.params[name]), se=float(ols.bse[name]),
            hc1=float(hc1[name]),
            lo=float(ci.loc[name, 0]), hi=float(ci.loc[name, 1]),
            t=float(ols.tvalues[name]), p=float(ols.pvalues[name]),
            logit=lg,
            uni=None if u is None else float(u["coef"]),
            uni_p=None if u is None else float(u["p"]),
            change=change, flip=flip))
    rows.sort(key=lambda r: -abs(r["t"]))

    cond = float(np.linalg.cond(Z.to_numpy()))
    summary = dict(
        n=int(len(y)), k=len(cols), dropped=dropped,
        base_rate=float(y.mean()),
        r2=float(ols.rsquared), r2_adj=float(ols.rsquared_adj),
        rse=float(np.sqrt(ols.mse_resid)),
        f=float(ols.fvalue), f_p=float(ols.f_pvalue),
        df_model=int(ols.df_model), df_resid=int(ols.df_resid),
        intercept=float(ols.params["const"]), cond=cond,
        logit_note=logit_note,
        pseudo_r2=None if logit is None else float(logit.prsquared),
        llr=None if logit is None else float(logit.llr),
        llr_p=None if logit is None else float(logit.llr_pvalue),
        univariate_file=uni_meta.get("file", ""),
        univariate_cut=uni_meta.get("cut", ""),
        missing_uni=[r["name"] for r in rows if r["uni"] is None],
        flips=[r["name"] for r in rows if r["flip"]],
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 1),
        **meta)
    return dict(rows=rows, summary=summary)


def _logit(sm, D, y):
    """The same predictor set fitted logistic, or a plain reason it was not.

    Newton first because its standard errors are the ones wanted. Two ticked
    columns can be collinear enough, or one can separate the outcome cleanly
    enough, that the matrix Newton inverts is singular; BFGS reaches the same
    estimates without inverting it. Where both fail the panel says so and the
    least-squares table still stands, which is the behaviour
    variable_selection.plot_coef_ci settled on for the same failure.
    """
    try:
        return sm.Logit(y, D).fit(disp=0), ""
    except Exception as exc:                                    # noqa: BLE001
        try:
            return (sm.Logit(y, D).fit(disp=0, method="bfgs", maxiter=500),
                    f"Newton's method failed ({type(exc).__name__}), so the "
                    f"logistic estimates below come from BFGS.")
        except Exception as exc2:                               # noqa: BLE001
            return None, (f"The logistic fit of this selection would not "
                          f"converge ({type(exc2).__name__}: {exc2}). The "
                          f"linear probability model above is unaffected, and "
                          f"the comparison with the univariate estimates needs "
                          f"the logistic fit, so it is not shown.")


# ---------------------------------------------------------------------------
# The fit as HTML
# ---------------------------------------------------------------------------

def table_html(res: dict) -> str:
    if res.get("error"):
        return f'<div class="cal"><b>Not fitted</b> {html.escape(res["error"])}</div>'
    rows, s = res["rows"], res["summary"]

    head = (
        f'<div class="cal info"><b>Linear probability model</b> '
        f'{s["k"]} predictor{"s" if s["k"] != 1 else ""} on {s["n"]:,} complete '
        f'training rows to {html.escape(str(s["cut"]))}, base rate '
        f'{s["base_rate"]:.3f}. The outcome is nought or one, so a least-squares '
        f'coefficient is a change in the probability of the barrier being hit '
        f'per one standard deviation of the column, not a change in a continuous '
        f'quantity. Fitted in {s["elapsed_ms"]:.0f} milliseconds.</div>')

    t1 = ['<table><thead><tr><th>predictor</th><th>coefficient</th>'
          '<th>standard error</th><th>robust standard error</th>'
          '<th>95% interval</th><th>t</th><th>p</th></tr></thead><tbody>']
    for r in rows:
        t1.append(
            f'<tr><td>{html.escape(r["name"])}</td>'
            f'<td>{r["coef"]:+.5f}</td><td>{r["se"]:.5f}</td>'
            f'<td>{r["hc1"]:.5f}</td>'
            f'<td>{r["lo"]:+.5f} to {r["hi"]:+.5f}</td>'
            f'<td>{r["t"]:+.2f}</td><td>{_pval(r["p"])}</td></tr>')
    t1.append('</tbody></table>')

    fit_line = (
        f'<p class="note">R squared {s["r2"]:.4f}, adjusted {s["r2_adj"]:.4f}, '
        f'residual standard error {s["rse"]:.4f} on {s["df_resid"]:,} degrees of '
        f'freedom. Against an intercept-only model, '
        f'F({s["df_model"]}, {s["df_resid"]:,}) = {s["f"]:.3f}, '
        f'p {_pval(s["f_p"])}. Intercept {s["intercept"]:+.4f}, which on '
        f'standardised columns is the fitted probability at the mean of every '
        f'one of them. Condition number of the design {s["cond"]:.1f}'
        + (', high enough that the ticked columns are close to carrying the same '
           'information and the individual estimates are unstable.'
           if s["cond"] > 30 else '.')
        + (f' {s["dropped"]:,} rows of the window were dropped for a gap in one '
           f'of the ticked columns.' if s["dropped"] else '')
        + ' The classical standard errors assume a constant error variance, '
          'which a nought-or-one outcome cannot have, so the robust column '
          'beside them is the one to read where the two differ.</p>')

    if s["logit_note"]:
        t2 = f'<div class="cal"><b>Logistic fit</b> {html.escape(s["logit_note"])}</div>'
    else:
        t2 = ['<div class="cal info"><b>The same set, logistic, against each '
              'predictor alone</b> Estimates are log-odds per standard deviation. '
              'The univariate column is that predictor fitted by itself, read from '
              f'{html.escape(str(s["univariate_file"]))}; the change is what the '
              'other ticked predictors did to it.</div>',
              '<table><thead><tr><th>predictor</th><th>log-odds, together</th>'
              '<th>standard error</th><th>z</th><th>p</th>'
              '<th>log-odds, alone</th><th>change</th></tr></thead><tbody>']
        for r in rows:
            lg = r["logit"]
            uni = "&#8195;" if r["uni"] is None else f'{r["uni"]:+.4f}'
            if r["change"] is None:
                chg = "not in the screen on disk"
            else:
                chg = f'{r["change"]:+.4f}'
                if r["flip"]:
                    chg += ' <b>sign flips</b>'
            t2.append(
                f'<tr><td>{html.escape(r["name"])}</td>'
                f'<td>{lg["coef"]:+.4f}</td><td>{lg["se"]:.4f}</td>'
                f'<td>{lg["z"]:+.2f}</td><td>{_pval(lg["p"])}</td>'
                f'<td>{uni}</td><td>{chg}</td></tr>')
        t2.append('</tbody></table>')
        t2.append(
            f'<p class="note">McFadden pseudo R squared {s["pseudo_r2"]:.4f}; '
            f'likelihood ratio against an intercept-only model '
            f'{s["llr"]:.2f} on {s["k"]} degrees of freedom, p {_pval(s["llr_p"])}.'
            + (f' {len(s["flips"])} predictor'
               f'{"s" if len(s["flips"]) != 1 else ""} changed sign between the '
               f'two fits: {", ".join(html.escape(n) for n in s["flips"])}. That '
               f'is the finding the table exists for, and neither fit alone shows '
               f'it.' if s["flips"] else
               ' No ticked predictor changed sign between the two fits, so on '
               'this selection the neighbours moved magnitudes and not '
               'directions.')
            + (f' Not in the screen on disk, so shown without a comparison: '
               f'{", ".join(html.escape(n) for n in s["missing_uni"])}. The '
               f'screen was run under a different feature selection; run it '
               f'again from this panel to compare them.'
               if s["missing_uni"] else '')
            + '</p>')
        t2 = "".join(t2)

    return head + "".join(t1) + fit_line + t2


# ---------------------------------------------------------------------------
# The panel fragment
# ---------------------------------------------------------------------------

_STYLE = """
<style>
#vs-multi .vsfams{ display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr));
                   gap:4px 14px; margin:0 0 10px 0; }
#vs-multi .vsfam{ font-size:11px; text-transform:uppercase; letter-spacing:0.3px;
                  color:var(--ink-soft); font-weight:800; grid-column:1/-1;
                  margin:6px 0 1px 0; }
#vs-multi label{ display:block; font-size:12px; cursor:pointer;
                 white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
#vs-multi label input{ margin-right:5px; }
#vs-multi .vsbtns{ display:flex; gap:8px; align-items:center; margin:0 0 10px 0;
                   flex-wrap:wrap; }
#vs-multi button{ font:inherit; font-size:11.5px; padding:3px 9px;
                  border:1px solid var(--rule); background:#fff; cursor:pointer;
                  border-radius:2px; color:var(--ink); }
#vs-multi button:hover{ background:var(--tuv-lt); }
#vs-multi .vscount{ font-size:11.5px; color:var(--ink-soft); margin-left:auto; }
</style>
"""


def multivariate_panel() -> str:
    """Checkboxes over the offered columns, and the fit beneath them."""
    cfg, feats = offered()
    train, _available = _panel(cfg)
    meta = _FRAME["meta"]
    uni, uni_meta = univariate()
    survivors = [n for n in _enet_survivors() if n in feats]
    ranked = [r["feature"] for r in sorted(
        (uni.get(f) or dict(feature=f, coef=0.0) for f in feats),
        key=lambda r: -abs(r["coef"]))]
    start = survivors or ranked[:6]

    fams: dict[str, list[str]] = {}
    for f in feats:
        fams.setdefault("_".join(f.split("_")[:2]) + "_", []).append(f)

    boxes = []
    for fam, names in fams.items():
        boxes.append(f'<div class="vsfam">{html.escape(fam)}</div>')
        for n in names:
            checked = " checked" if n in start else ""
            u = uni.get(n)
            title = (f"fitted alone: {u['coef']:+.4f} log-odds, p "
                     f"{'< 0.001' if u['p'] < 0.001 else format(u['p'], '.3f')}"
                     if u else "not in the univariate screen on disk")
            boxes.append(
                f'<label title="{html.escape(title)}">'
                f'<input type="checkbox" name="vscol" value="{html.escape(n)}"{checked}>'
                f'{html.escape(n)}</label>')

    note = (
        f"Tick a column and the fit is redone. {len(feats)} columns are offered "
        f"by the current configuration, and the fit runs on the "
        f"{meta['rows']:,} most recent of {meta['window']:,} training rows to "
        f"{html.escape(str(meta['cut']))}, capped so that reading a large panel "
        f"cannot take the page down. The blind period is never opened. "
        + (f"It opens on the {len(survivors)} columns the elastic net retained at "
           f"&lambda;.1se." if survivors else
           "It opens on the six largest univariate estimates, because the "
           "elastic net retained nothing at &lambda;.1se.")
        + " Hover a name for what it was worth alone.")

    return (
        f'{_STYLE}<div class="interactive" id="vs-multi">'
        f'<div class="inote">{note}</div>'
        f'<div class="vsbtns">'
        f'<button type="button" data-vsset="enet">elastic-net survivors</button>'
        f'<button type="button" data-vsset="top6">six largest alone</button>'
        f'<button type="button" data-vsset="all">all {len(feats)}</button>'
        f'<button type="button" data-vsset="none">none</button>'
        f'<span class="vscount" id="vs-count"></span></div>'
        f'<div class="vsfams">{"".join(boxes)}</div>'
        f'<div id="vs-table"><p class="note">Fitting.</p></div>'
        f'<script>window.VS_SETS = '
        f'{json.dumps(dict(enet=survivors, top6=ranked[:6], all=feats, none=[]))};'
        f'</script>{_SCRIPT}</div>')


_SCRIPT = """
<script>
// The table is built on the server and swapped in whole, so the fit and its
// wording have one definition rather than one in Python and another here. The
// alternative, returning numbers and formatting them in the browser, is how the
// same estimate ends up printed to two different precisions on two pages.
(function () {
  const root = document.getElementById('vs-multi');
  if (!root) { return; }
  const out = root.querySelector('#vs-table');
  const count = root.querySelector('#vs-count');
  const boxes = () => Array.from(root.querySelectorAll('input[name=vscol]'));
  let pending = 0;

  function chosen() {
    return boxes().filter(b => b.checked).map(b => b.value);
  }

  async function refit() {
    const cols = chosen();
    count.textContent = cols.length + ' ticked';
    const mine = ++pending;
    out.innerHTML = '<p class="note">Fitting ' + cols.length + ' predictors.</p>';
    try {
      const r = await fetch('/varselect/fit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({cols: cols})
      });
      const d = await r.json();
      // A slow fit that has been superseded must not overwrite a newer one.
      // Without this counter, ticking three boxes quickly can leave the table
      // showing the first selection while the checkboxes show the third.
      if (mine !== pending) { return; }
      out.innerHTML = d.html;
    } catch (err) {
      if (mine !== pending) { return; }
      out.innerHTML = '<div class="cal"><b>Not fitted</b> the fit did not answer: '
                      + err + '</div>';
    }
  }

  root.addEventListener('change', ev => {
    if (ev.target.name === 'vscol') { refit(); }
  });
  root.querySelectorAll('[data-vsset]').forEach(btn => {
    btn.addEventListener('click', () => {
      const want = new Set(window.VS_SETS[btn.dataset.vsset] || []);
      boxes().forEach(b => { b.checked = want.has(b.value); });
      refit();
    });
  });
  refit();
})();
</script>
"""


def fragment() -> str:
    """Both additions, in the order the operator put them in the specification.

    Wrapped, because a figure that raises must not take the panel down with it:
    this reads a configured panel off disk and fits two models, and the reader
    is better served by the failure named than by a page that will not render.
    """
    parts = []
    for name, fn in (("coefficient path", coefficient_path),
                     ("multivariate table", multivariate_panel)):
        try:
            parts.append(fn())
        except Exception as exc:                                # noqa: BLE001
            parts.append(_missing(f"The {name} could not be built: "
                                  f"{type(exc).__name__}: {exc}"))
    return "".join(parts)


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------

bp = Blueprint("varselect", __name__)


@bp.route("/varselect/fit", methods=["POST"])
def fit_endpoint():
    """Refit the chosen columns and return the table.

    Always a 200 with an explanation in it. A 500 here would leave the panel
    showing a browser error with nothing in it a reader could act on, and the
    thing that goes wrong most often, a selection two of whose columns carry the
    same information, is a fact about the data worth reading rather than a
    fault.
    """
    payload = request.get_json(silent=True) or {}
    cols = payload.get("cols") or []
    if not isinstance(cols, list) or not all(isinstance(c, str) for c in cols):
        return jsonify(html=table_html(dict(error="the column list was not a "
                                                  "list of column names")))
    try:
        res = fit(cols[:120])
    except Exception as exc:                                    # noqa: BLE001
        res = dict(error=f"{type(exc).__name__}: {exc}")
    return jsonify(html=table_html(res))
