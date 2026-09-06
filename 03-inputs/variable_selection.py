"""Variable selection for the 1h model: native-Python analogues of the R
glmnet + coefplot workflow (elastic-net path, CV curve, coefficient screening).

This mirrors a common R idiom for elastic-net screening
(useful::build.x/build.y -> glmnet::cv.glmnet -> coefplot::coefpath / coefplot),
reimplemented in native Python and applied to the day-trader 1h feature set:

    R                                   Python (this module)
    useful::build.x / build.y           build_matrix()    patsy formula -> (X, y)
    glmnet::cv.glmnet(alpha=1|0|a)      enet_cv()         k-fold CV over a lambda grid
    plot(cv.glmnet)                     plot_cv_curve()   metric vs log-lambda, min/1se, nonzero axis
    coefplot::coefpath(...)             plot_coefpath()           static labeled paths (matplotlib)
                                        plot_coefpath_interactive() live paths + range slider (plotly)
    coefplot::coefplot(lm, "magnitude") plot_coef_ci()    estimate +/- CI, sorted (statsmodels OLS/Logit)

Two response families:
  family="gaussian"  continuous y (a real-valued target); MSE CV; OLS for the CI plot.
  family="binomial"  binary y (the day-trader triple-barrier label); binomial-deviance CV; Logit for CI.

glmnet standardizes predictors before fitting and reports coefficients back on the
original scale. We mirror that by z-scoring the continuous columns; columns that are
already 0/1 indicators are left raw by default (set standardize="all" to scale them too),
which is the usual choice when most predictors are categorical/binary.

lambda is glmnet's penalty strength. sklearn parameterizes ElasticNet by `alpha` (= lambda,
same 1/2n data scaling) and LogisticRegression by `C` (= 1 / (n * lambda)). We expose a
natural-log-lambda x-axis in both cases so the figures read like the R ones.

No orders, no trading. Outputs are PNG (matplotlib) and HTML (plotly). Run from the .venv:
    .venv/bin/python inputs/variable_selection.py            # day-trader subset, binomial
    .venv/bin/python inputs/variable_selection.py --sample 25000 --l1 1.0
"""
from __future__ import annotations

import argparse
import os
import warnings

import matplotlib
matplotlib.use("Agg")                      # headless; no style files (dodges the exFAT ._*.mplstyle crash)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet, LogisticRegression
from sklearn.model_selection import KFold
from sklearn.metrics import log_loss, mean_squared_error

RED = "#D7301F"
GREY = "#9C9C9C"


# --------------------------------------------------------------------------- model matrix
def build_matrix(df, formula=None, y_col=None, x_cols=None, standardize=True, drop_intercept=True):
    """R `build.x`/`build.y`. Either pass a patsy `formula` (R-style, e.g.
    "label ~ a + b + c*d - 1") OR `y_col` + `x_cols`. Returns (X, y, scale_info).
    Continuous columns are z-scored when standardize is truthy; 0/1 indicator columns are
    left raw unless standardize == "all"."""
    if formula:
        import patsy
        y, X = patsy.dmatrices(formula, df, return_type="dataframe")
        y = y.iloc[:, 0]
    else:
        if y_col is None or x_cols is None:
            raise ValueError("pass either formula= or both y_col= and x_cols=")
        X = df[list(x_cols)].copy()
        y = df[y_col].copy()
    if drop_intercept and "Intercept" in X.columns:
        X = X.drop(columns=["Intercept"])
    means, stds = {}, {}
    if standardize:
        for c in X.columns:
            col = X[c].astype(float)
            uniq = pd.unique(col.dropna())
            is_binary = set(uniq) <= {0.0, 1.0} or len(uniq) <= 2
            if standardize == "all" or not is_binary:
                m, s = col.mean(), col.std(ddof=0)
                if s and np.isfinite(s):
                    X[c] = (col - m) / s
                    means[c], stds[c] = m, s
    return X.astype(float), y.astype(float), dict(means=means, stds=stds)


# --------------------------------------------------------------------------- elastic-net CV
def _lambda_grid(X, y, l1_ratio, n_lambda=70, eps=1e-3):
    """glmnet-style grid: lambda_max is the smallest penalty that zeroes every coefficient,
    then geometric down to eps * lambda_max. For standardized X and centered y,
    lambda_max = max_j |<x_j, y-ybar>| / (n * l1_ratio)."""
    n = len(y)
    r = y.values - y.values.mean()
    dots = np.abs(X.values.T @ r) / n
    lam_max = dots.max() / max(l1_ratio, 1e-3)
    return np.geomspace(lam_max, eps * lam_max, n_lambda)


def _make(family, l1_ratio, warm=False):
    if family == "gaussian":
        return ElasticNet(alpha=1.0, l1_ratio=max(l1_ratio, 1e-3), max_iter=4000,
                          tol=1e-3, warm_start=warm)
    pen = "l2" if l1_ratio == 0 else "elasticnet"
    kw = dict(solver="saga", max_iter=500, tol=5e-3, warm_start=warm, penalty=pen)
    if pen == "elasticnet":
        kw["l1_ratio"] = l1_ratio
    return LogisticRegression(C=1.0, **kw)


def _set_penalty(est, family, lam, n):
    if family == "gaussian":
        est.set_params(alpha=max(lam, 1e-9))
    else:
        est.set_params(C=1.0 / max(lam * n, 1e-12))


def _score(est, Xte, yte, family):
    if family == "gaussian":
        return mean_squared_error(yte, est.predict(Xte))
    p = np.clip(est.predict_proba(Xte)[:, 1], 1e-7, 1 - 1e-7)
    return 2.0 * log_loss(yte, p, labels=[0, 1])      # binomial deviance


def enet_cv(X, y, family="gaussian", l1_ratio=1.0, n_lambda=60, n_folds=10, eps=1e-2,
            seed=0, verbose=True):
    """k-fold CV over a glmnet-style lambda grid (warm-started down the path for speed).
    Returns the CV curve (mean +/- se), lambda.min, lambda.1se, the full-data coefficient
    path, and the nonzero count per lambda. `eps` sets how far the grid reaches toward the
    unregularized end; 1e-2 keeps the slow large-C logistic fits out of the path."""
    lambdas = _lambda_grid(X, y, l1_ratio, n_lambda, eps)
    Xv, yv, n = X.values, y.values, len(y)
    kf = KFold(n_splits=n_folds, shuffle=True, random_state=seed)
    cv = np.full((n_lambda, n_folds), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for j, (tr, te) in enumerate(kf.split(Xv)):
            est = _make(family, l1_ratio, warm=True)
            for i, lam in enumerate(lambdas):          # large lambda -> small: warm start helps saga
                _set_penalty(est, family, lam, len(tr))
                est.fit(Xv[tr], yv[tr])
                cv[i, j] = _score(est, Xv[te], yv[te], family)
            if verbose:
                print(f"  fold {j + 1}/{n_folds} done", flush=True)
        full = _make(family, l1_ratio, warm=True)
        coefs = np.zeros((n_lambda, X.shape[1]))
        for i, lam in enumerate(lambdas):
            _set_penalty(full, family, lam, n)
            full.fit(Xv, yv)
            coefs[i] = np.ravel(full.coef_)
    mean, se = cv.mean(1), cv.std(1, ddof=1) / np.sqrt(n_folds)
    i_min = int(np.nanargmin(mean))
    thr = mean[i_min] + se[i_min]
    cand = np.where(mean[: i_min + 1] <= thr)[0]       # lambdas descending: first hit = most regularized
    i_1se = int(cand[0]) if len(cand) else i_min
    nonzero = (np.abs(coefs) > 1e-8).sum(1)
    return dict(lambdas=lambdas, loglam=np.log(lambdas), mean=mean, se=se, cv=cv,
                i_min=i_min, i_1se=i_1se, lambda_min=lambdas[i_min], lambda_1se=lambdas[i_1se],
                coefs=coefs, nonzero=nonzero, names=list(X.columns), family=family,
                l1_ratio=l1_ratio, n=n,
                metric="Mean-Squared Error" if family == "gaussian" else "Binomial Deviance")


def screen(res, which="1se"):
    """Variables retained at lambda.1se (default) or lambda.min, largest |coef| first."""
    i = res["i_1se"] if which == "1se" else res["i_min"]
    c = res["coefs"][i]
    keep = [(n, v) for n, v in zip(res["names"], c) if abs(v) > 1e-8]
    return sorted(keep, key=lambda t: abs(t[1]), reverse=True)


# --------------------------------------------------------------------------- plots
def plot_cv_curve(res, path):
    """R `plot(cv.glmnet)`: metric vs log-lambda, red dots + grey 1-se whiskers, dotted
    lines at lambda.min and lambda.1se, nonzero-coefficient counts along the top axis."""
    x = res["loglam"]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.errorbar(x, res["mean"], yerr=res["se"], fmt="o", ms=4, color=RED,
                ecolor=GREY, elinewidth=1, capsize=2, zorder=3)
    for i, style in [(res["i_min"], ":"), (res["i_1se"], ":")]:
        ax.axvline(x[i], ls=style, color="0.3", lw=1)
    ax.set_xlabel(r"Log($\lambda$)")
    ax.set_ylabel(res["metric"])
    ax.grid(alpha=0.2)
    top = ax.twiny()                                   # nonzero counts, glmnet's top axis
    top.set_xlim(ax.get_xlim())
    idx = np.linspace(0, len(x) - 1, 14).round().astype(int)
    top.set_xticks(x[idx])
    top.set_xticklabels([str(int(res["nonzero"][i])) for i in idx], fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def _label_idx(res, top_k):
    order = np.argsort(np.abs(res["coefs"][res["i_min"]]))[::-1]
    return list(order[:top_k])


def plot_coefpath(res, path, top_k=10):
    """R `coefplot::coefpath` (static): every coefficient's trajectory vs log-lambda,
    the top_k by |coef| labelled at the dense (small-lambda) end, dotted line at lambda.1se."""
    x = res["loglam"]
    fig, ax = plt.subplots(figsize=(7.5, 5))
    cmap = plt.cm.tab20(np.linspace(0, 1, res["coefs"].shape[1]))
    for k in range(res["coefs"].shape[1]):
        ax.plot(x, res["coefs"][:, k], color=cmap[k], lw=1.1, alpha=0.85)
    end = int(np.argmin(x))                    # small-lambda end, where the paths fan out
    for k in _label_idx(res, top_k):
        ax.annotate(res["names"][k], (x[end], res["coefs"][end, k]), fontsize=7,
                    xytext=(-3, 0), textcoords="offset points", ha="right", va="center",
                    color=cmap[k])
    xr = x.max() - x.min()
    ax.set_xlim(x.min() - 0.18 * xr, x.max() + 0.02 * xr)   # room for the left-edge labels
    ax.axvline(x[res["i_1se"]], ls=":", color="0.3", lw=1)
    ax.axhline(0, color="0.6", lw=0.6)
    ax.set_xlabel(r"Log($\lambda$)")
    ax.set_ylabel("Coefficient")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_coefpath_interactive(res, path, top_k=14):
    """R `coefplot::coefpath` (live): plotly line chart, hover shows variable + value, a
    range slider on the x-axis stands in for the dygraphs range selector in the R widget."""
    import plotly.graph_objects as go
    x = res["loglam"]
    label = set(_label_idx(res, top_k))
    fig = go.Figure()
    for k in range(res["coefs"].shape[1]):
        nm = res["names"][k]
        fig.add_trace(go.Scatter(x=x, y=res["coefs"][:, k], mode="lines", name=nm,
                                 legendgroup=nm, showlegend=k in label,
                                 hovertemplate=f"{nm}<br>logλ=%{{x:.2f}}<br>coef=%{{y:.4f}}<extra></extra>"))
    for i, nm in [(res["i_min"], "λ.min"), (res["i_1se"], "λ.1se")]:
        fig.add_vline(x=x[i], line_dash="dot", line_color="grey",
                      annotation_text=nm, annotation_position="top")
    fig.update_layout(title="Elastic-net coefficient paths (interactive)",
                      xaxis_title="Log(λ)", yaxis_title="Coefficient",
                      template="simple_white", height=520,
                      xaxis=dict(rangeslider=dict(visible=True)))
    fig.write_html(path, include_plotlyjs="cdn", full_html=True)
    return path


def plot_coef_ci(df, family, path, formula=None, y_col=None, x_cols=None, title=None):
    """R `coefplot::coefplot(lm, sort="magnitude")`: refit the screened model unpenalized
    with statsmodels to recover confidence intervals (which sklearn does not give), then
    draw each estimate as a dot with a 95% CI whisker, sorted by magnitude. Gaussian -> OLS,
    binomial -> Logit (coefficients are log-odds)."""
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    if formula:
        model = (smf.ols if family == "gaussian" else smf.logit)(formula, data=df)
    else:
        X = sm.add_constant(df[list(x_cols)].astype(float))
        y = df[y_col].astype(float)
        model = sm.OLS(y, X) if family == "gaussian" else sm.Logit(y, X)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = model.fit(disp=0) if family == "binomial" else model.fit()
    params, ci = res.params, res.conf_int()
    keep = [n for n in params.index if n.lower() not in ("intercept", "const")]
    params, ci = params[keep], ci.loc[keep]
    order = params.abs().sort_values().index           # smallest at bottom
    fig, ax = plt.subplots(figsize=(7.5, max(3, 0.4 * len(order) + 1)))
    yv = np.arange(len(order))
    lo, hi = ci.loc[order, 0].values, ci.loc[order, 1].values
    pv = params.loc[order].values
    ax.hlines(yv, lo, hi, color="#1F4E96", lw=2)
    ax.plot(pv, yv, "o", color="#1F4E96", ms=6)
    ax.axvline(0, ls="--", color="0.6")
    ax.set_yticks(yv)
    ax.set_yticklabels(order)
    ax.set_xlabel("Value" + ("" if family == "gaussian" else " (log-odds)"))
    ax.set_ylabel("Coefficient")
    ax.set_title(title or "Coefficient Plot")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- demo driver
def _demo_daytrader(sample, l1_ratio, out_dir, seed=0):
    import build_dataset_1h as b1
    df = b1.read_frame(b1.DATASET_PATH)
    if df is None:
        raise SystemExit(f"no dataset at {b1.DATASET_PATH}; build the subset first")
    if "in_sample" in df.columns:
        df = df[df["in_sample"]]
    feats = b1.feature_columns(df)
    df = df.dropna(subset=[*feats, "label"])
    if sample and len(df) > sample:
        df = df.sample(sample, random_state=seed)
    print(f"demo: {len(df):,} rows, {len(feats)} features, base rate {df['label'].mean():.3f}")
    X, y, _ = build_matrix(df, y_col="label", x_cols=feats, standardize=True)
    res = enet_cv(X, y, family="binomial", l1_ratio=l1_ratio, seed=seed)
    os.makedirs(out_dir, exist_ok=True)
    p1 = plot_cv_curve(res, os.path.join(out_dir, "cv_curve.png"))
    p2 = plot_coefpath(res, os.path.join(out_dir, "coefpath.png"))
    p3 = plot_coefpath_interactive(res, os.path.join(out_dir, "coefpath.html"))
    kept = screen(res, "1se")
    keep_names = [n for n, _ in kept] or [n for n, _ in screen(res, "min")][:12]
    p4 = plot_coef_ci(df, "binomial", os.path.join(out_dir, "coef_ci.png"),
                      y_col="label", x_cols=keep_names,
                      title="Screened coefficients (logit, 95% CI)")
    print(f"lambda.min={res['lambda_min']:.5g} (nonzero {res['nonzero'][res['i_min']]}), "
          f"lambda.1se={res['lambda_1se']:.5g} (nonzero {res['nonzero'][res['i_1se']]})")
    print("retained at 1se:", ", ".join(f"{n}({v:+.3f})" for n, v in kept[:15]) or "(none)")
    print("figures:", p1, p2, p3, p4, sep="\n  ")
    return res


def main():
    p = argparse.ArgumentParser(description="Elastic-net variable selection (glmnet/coefplot analogue)")
    p.add_argument("--sample", type=int, default=25000, help="row sample for the demo (0 = all)")
    p.add_argument("--l1", type=float, default=1.0, help="l1_ratio: 1=lasso, 0=ridge, between=elastic net")
    p.add_argument("--out", default=None, help="output dir (default: outputs/AA-evals/varselect)")
    a = p.parse_args()
    out = a.out or os.path.join(os.path.dirname(__file__), "..", "04-outputs", "AA-evals", "varselect")
    _demo_daytrader(a.sample or 0, a.l1, os.path.abspath(out))


if __name__ == "__main__":
    main()
