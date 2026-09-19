# -*- coding: utf-8 -*-
"""Threshold-robustness audit of `pd1-pdl1-lineage-compartment-spatial-coexpression`.

The gallery result (`outputs/gallery_20260909_090339.md`) claims PD-L1 positivity is not confined to
one lineage compartment (CD68+/E-cadherin+/CD31+/SMA+ all show elevated co-positivity) and that
cytotoxic T cells are differentially enriched near some PD-L1+ compartments but not others. Every
number in that claim descends from a set of per-marker BINARY positivity masks, each produced by:

    arcsinh -> 25x25 spatial-grid local-median subtraction -> robust (median/IQR) scaling
             -> 2-component GMM decision boundary, with an Otsu fallback when the GMM is "degenerate".

This script exists because NONE of the following is shown anywhere in that gallery's output:
  - what the actual cutpoints are, and whether they sit on a real bimodal trough or just slice a
    shoulder of a unimodal distribution;
  - why one marker used the GMM boundary while a neighbouring one used Otsu;
  - whether the headline odds ratios / enrichment survive moving the cutpoint, or switching the
    thresholding method entirely.

It reproduces the exact pipeline above, then (a) illustrates each marker's scaled distribution with
every cutpoint overlaid, (b) sweeps each cutpoint across a percentile grid and recomputes the odds
ratios + enrichment, and (c) re-runs the compartment attribution under several alternative
thresholding methods. It does NOT re-derive the biological claim in the abstract - only how much the
*reported* numbers move as a function of the thresholding choices.

Run:  pixi run python explorations/cellsurvey/pd1pdl1_threshold_sensitivity.py
      (reads inputs/cellsurvey_processed/cells.csv; writes PNGs + a summary CSV into
       explorations/cellsurvey/out_pd1pdl1_sensitivity/)

This is a one-off follow-up, not a pipeline realisation - no Docker, no judge, no gallery. See
docs/DEVELOPMENT_LOG.md rev. 91 / BACKLOG.md section 7 for where the `explorations/` convention sits
relative to the (still-backlogged) "human-directed deepening" idea.
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.mixture import GaussianMixture

sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path("inputs/cellsurvey_processed")
CELLS_CSV = DATA_DIR / "cells.csv"
OUT_DIR = Path("explorations/cellsurvey/out_pd1pdl1_sensitivity")

MARKERS = [
    "marker_PD_L1", "marker_CD68", "marker_E_cadherin", "marker_CD31", "marker_SMA",
    "marker_PD_1", "marker_CD8", "marker_CD3", "marker_FoxP3", "marker_CD4",
]
COMPARTMENTS = {
    "Macrophage (CD68+)": "marker_CD68",
    "Epithelial (E-cad+)": "marker_E_cadherin",
    "Endothelial (CD31+)": "marker_CD31",
    "Stromal (SMA+)": "marker_SMA",
}
CYTO_MARKERS = ["marker_CD3", "marker_CD8", "marker_PD_1"]
TREG_MARKERS = ["marker_CD3", "marker_CD4", "marker_FoxP3"]
RADII = [50, 100, 200, 400, 800]


def load():
    cols = ["x", "y", "marker_DAPI"] + MARKERS
    df = pd.read_csv(CELLS_CSV, usecols=cols).astype({c: "float32" for c in cols})
    x = df["x"].to_numpy(float)
    y = df["y"].to_numpy(float)
    return df, x, y


def _local_median_vals(v, x, y, n_bins=25):
    """Per-cell value of a 25x25 spatial-grid median smooth of `v` (used for the DAPI baseline)."""
    xb = np.clip(((x - x.min()) / (x.max() - x.min()) * n_bins).astype(int), 0, n_bins - 1)
    yb = np.clip(((y - y.min()) / (y.max() - y.min()) * n_bins).astype(int), 0, n_bins - 1)
    bid = xb * n_bins + yb
    bm = np.full(n_bins * n_bins, np.nan)
    for b in range(n_bins * n_bins):
        vals = v[bid == b]
        if vals.size:
            bm[b] = np.median(vals)
    bm[np.isnan(bm)] = np.median(v)
    return bm[bid]


# --- exact reproduction of the realised script's normalise + threshold ---------------------------

def _otsu_cutpoint(vals, n_bins=256):
    hist, edges = np.histogram(vals, bins=n_bins)
    centers = (edges[:-1] + edges[1:]) / 2.0
    total = hist.sum()
    s_t = np.dot(centers, hist)
    wb, sb, best, cut = 0.0, 0.0, -np.inf, edges[0]
    for i in range(1, len(hist)):
        wb += hist[i - 1]
        if wb == 0:
            continue
        wf = total - wb
        if wf == 0:
            break
        sb += centers[i - 1] * hist[i - 1]
        mb, mf = sb / wb, (s_t - sb) / wf
        between = wb * wf * (mb - mf) ** 2
        if between > best:
            best, cut = between, edges[i]
    return cut


def _local_median_correct(transformed, x, y, n_bins=25):
    xb = np.clip(((x - x.min()) / (x.max() - x.min()) * n_bins).astype(int), 0, n_bins - 1)
    yb = np.clip(((y - y.min()) / (y.max() - y.min()) * n_bins).astype(int), 0, n_bins - 1)
    bid = xb * n_bins + yb
    bm = np.full(n_bins * n_bins, np.nan)
    for b in range(n_bins * n_bins):
        v = transformed[bid == b]
        if v.size:
            bm[b] = np.median(v)
    gm = np.median(transformed)
    bm[np.isnan(bm)] = gm
    return transformed - bm[bid]


def scaled_values(marker, x, y, local_correct=True):
    t = np.arcsinh(marker)
    if local_correct:
        t = _local_median_correct(t, x, y)
    med, iqr = np.median(t), np.percentile(t, 75) - np.percentile(t, 25)
    return (t - med) / iqr


# Returns (cutpoint, method, low_mean, high_mean, w_low, w_high)
def gmm_otsu_threshold(scaled):
    gmm = GaussianMixture(2, random_state=0, reg_covar=1e-6).fit(scaled.reshape(-1, 1))
    m = gmm.means_.ravel(); v = gmm.covariances_[:, 0, 0]; w = gmm.weights_
    li, hi = int(np.argmin(m)), int(np.argmax(m))
    ml, mh = m[li], m[hi]; vl, vh = v[li], v[hi]; wl, wh = w[li], w[hi]
    degenerate = (
        not np.isfinite(ml) or not np.isfinite(mh)
        or vl < 1e-12 or vh < 1e-12 or mh - ml < 1e-9 or wl < 1e-6 or wh < 1e-6
    )
    otsu = _otsu_cutpoint(scaled)
    if degenerate:
        return otsu, "otsu-fallback", ml, mh, wl, wh
    A = 1 / (2 * vh) - 1 / (2 * vl)
    B = -mh / vh + ml / vl
    C = (mh ** 2) / (2 * vh) - (ml ** 2) / (2 * vl) + np.log(wl / wh) + 0.5 * np.log(vh / vl)
    root = None
    if abs(A) < 1e-12:
        if abs(B) > 1e-12:
            c = -C / B
            if ml < c < mh:
                root = c
    else:
        d = B * B - 4 * A * C
        if d >= 0:
            s = np.sqrt(d)
            cand = [(-B + s) / (2 * A), (-B - s) / (2 * A)]
            valid = [c for c in cand if ml < c < mh]
            if valid:
                root = float(np.median(valid))
    if root is not None:
        return root, "gmm", ml, mh, wl, wh
    return otsu, "otsu", ml, mh, wl, wh


def percentile_cutpoint(scaled, p):
    return np.percentile(scaled, p)


# --- headline metrics (recomputed under any set of masks) -----------------------------------------

def odds_ratio(pdl1, lineage):
    a = int((pdl1 & lineage).sum())
    b = int((pdl1 & ~lineage).sum())
    c = int((~pdl1 & lineage).sum())
    d = int((~pdl1 & ~lineage).sum())
    if b * c == 0:
        return np.inf
    return (a * d) / (b * c)


def neighbourhood_enrichment(source_xy, target_xy, all_xy, radii=RADII):
    ttree = cKDTree(target_xy)
    atree = cKDTree(all_xy)
    exp = target_xy.shape[0] / all_xy.shape[0]
    out = []
    for r in radii:
        tc = ttree.query_ball_point(source_xy, r, return_length=True)
        ac = atree.query_ball_point(source_xy, r, return_length=True)
        out.append(np.mean(tc / np.maximum(ac, 1)) / exp)
    return out


def build_masks(df, x, y, method="repro", local_correct=True, percentile=None):
    """Return dict marker -> bool mask. 'repro' uses the realised GMM/Otsu; 'otsu-gmm' is the
    realised method too (kept as an alias). Other methods override."""
    masks = {}
    # Normalisation strategy: either the original arcsinh + local-subtraction + robust-scale family,
    # or a DAPI-ratio ("each marker / the cell's own local DNA signal") alternative. Both then feed
    # the SAME positivity rule (otsu / gmm / repro / percentile) so the two figures are comparable.
    dapi_smooth = None
    if method in ("dapi-otsu", "dapi-gmm", "dapi-repro", "dapi-p90"):
        dapi_smooth = _local_median_vals(np.arcsinh(df["marker_DAPI"].to_numpy(float)), x, y)
    for mk in MARKERS:
        if method in ("dapi-otsu", "dapi-gmm", "dapi-repro", "dapi-p90"):
            sc = np.arcsinh(df[mk].to_numpy(float)) - dapi_smooth
            sc = (sc - np.median(sc)) / (np.percentile(sc, 75) - np.percentile(sc, 25))
            rule = method.split("-", 1)[1]
        else:
            sc = scaled_values(df[mk].to_numpy(float), x, y, local_correct=local_correct)
            rule = method

        if rule == "repro":
            cut, _, _, _, _, _ = gmm_otsu_threshold(sc)
        elif rule == "otsu":
            cut = _otsu_cutpoint(sc)
        elif rule == "gmm":
            # GMM decision boundary only (no Otsu fallback), matching the realised script's
            # non-degenerate path. Degenerate fits fall back to the higher mean (a high cut).
            g = GaussianMixture(2, random_state=0, reg_covar=1e-6).fit(sc.reshape(-1, 1))
            means = g.means_.ravel(); v = g.covariances_[:, 0, 0]; w = g.weights_
            li, hi = int(np.argmin(means)), int(np.argmax(means))
            ml, mh = means[li], means[hi]; vl, vh = v[li], v[hi]; wl, wh = w[li], w[hi]
            A = 1 / (2 * vh) - 1 / (2 * vl)
            B = -mh / vh + ml / vl
            C = (mh ** 2) / (2 * vh) - (ml ** 2) / (2 * vl) + np.log(wl / wh) + 0.5 * np.log(vh / vl)
            d = B * B - 4 * A * C
            if np.isfinite(A) and abs(A) >= 1e-12 and np.isfinite(d) and d >= 0:
                cand = [(-B + np.sqrt(d)) / (2 * A), (-B - np.sqrt(d)) / (2 * A)]
                valid = [c for c in cand if ml < c < mh]
                cut = float(np.median(valid)) if valid else float(mh)
            elif abs(A) < 1e-12 and abs(B) > 1e-12 and np.isfinite(B):
                c = -C / B
                cut = float(c) if ml < c < mh else float(mh)
            else:
                cut = float(mh)
        elif rule == "p90":
            cut = percentile_cutpoint(sc, 90)
        else:
            raise ValueError(f"unknown method {method}")
        masks[mk] = sc >= cut
    return masks


def run_attribution(df, x, y, masks, pdl1_key="marker_PD_L1"):
    pdl1 = masks[pdl1_key]
    pdl1_count = int(pdl1.sum())
    attrs, odds = {}, {}
    for comp, lm in COMPARTMENTS.items():
        lineage = masks[lm]
        cmp = pdl1 & lineage
        attrs[comp] = int(cmp.sum()) / pdl1_count if pdl1_count else 0.0
        odds[comp] = odds_ratio(pdl1, lineage)
    return attrs, odds, pdl1


def immune_pop(masks):
    cyto = masks["marker_CD3"] & masks["marker_CD8"] & masks["marker_PD_1"]
    treg = masks["marker_CD3"] & masks["marker_CD4"] & masks["marker_FoxP3"]
    return {"cytotoxic": cyto, "treg": treg}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df, x, y = load()
    coords = np.column_stack((x, y))
    n = len(df)

    print(f"Loaded {n} cells")
    print("Reproducing the realised script's per-marker thresholds")
    print(f"{'marker':22s} {'method':14s} {'cut':>8s} {'low_mean':>9s} {'high_mean':>9s} {'wlow':>6s} {'whigh':>6s}")
    cuts = {}
    for m in MARKERS:
        sc = scaled_values(df[m].to_numpy(float), x, y)
        cut, meth, ml, mh, wl, wh = gmm_otsu_threshold(sc)
        cuts[m] = cut
        print(f"{m:22s} {meth:14s} {cut:8.3f} {ml:9.3f} {mh:9.3f} {wl:6.3f} {wh:6.3f}")

    # (a) illustrate distributions vs cutpoints
    fig, axes = plt.subplots(2, 5, figsize=(20, 8))
    for ax, m in zip(axes.ravel(), MARKERS):
        sc = scaled_values(df[m].to_numpy(float), x, y)
        ax.hist(sc, bins=256, color="grey", alpha=0.6, log=True)
        ax.axvline(cuts[m], color="red", lw=1.5, label="repro cut")
        # also show otsu and gmm-only for comparison
        oc = _otsu_cutpoint(sc)
        ax.axvline(oc, color="blue", lw=1, ls="--", label="otsu")
        ax.set_title(m.replace("marker_", ""), fontsize=9)
        ax.tick_params(labelsize=7)
    axes[0, 0].legend(fontsize=7)
    fig.suptitle("Scaled marker intensity distributions with cutpoints (log y)", fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "distributions_vs_cutpoints.png", dpi=150)
    plt.close(fig)

    # (b) sweep each marker's cutpoint across percentiles, recompute odds ratios + enrichment
    pct_grid = [50, 60, 70, 75, 80, 85, 90, 92, 95, 97, 99]
    # For the sweep, hold every OTHER marker at its repro cutpoint and move one at a time
    # (the cleanest way to attribute sensitivity to each marker separately).
    base_masks = build_masks(df, x, y, method="repro")

    sweep_rows = []
    for sweep_marker in MARKERS:
        sc = scaled_values(df[sweep_marker].to_numpy(float), x, y)
        for p in pct_grid:
            m = dict(base_masks)
            m[sweep_marker] = sc >= percentile_cutpoint(sc, p)
            attrs, odds, pdl1 = run_attribution(df, x, y, m)
            for comp, v in odds.items():
                sweep_rows.append({
                    "swept_marker": sweep_marker, "percentile": p,
                    "compartment": comp, "odds_ratio": v,
                    "pdl1_positive_fraction": float(pdl1.mean()),
                })
    sweep_df = pd.DataFrame(sweep_rows)
    sweep_df.to_csv(OUT_DIR / "cutpoint_sweep.csv", index=False)

    # how much does the odds ratio range as the marker's cutpoint moves?
    spread = sweep_df.groupby(["swept_marker", "compartment"])["odds_ratio"].agg(
        ["min", "max"]).reset_index()
    spread["max_over_min"] = spread["max"] / spread["min"].replace(0, np.nan)
    print("\nOdds-ratio range across cutpoint sweep (per swept marker, per compartment):")
    print(spread.pivot(index="swept_marker", columns="compartment", values="max_over_min")
          .round(2).to_string())

    # (c) compare methods: two normalisation strategies, each crossed with several positivity rules
    methods = {
        "repro": build_masks(df, x, y, method="repro"),
        "otsu-only": build_masks(df, x, y, method="otsu"),
        "gmm-only": build_masks(df, x, y, method="gmm"),
        "no-local-corr": build_masks(df, x, y, method="repro", local_correct=False),
        "p90-fixed": build_masks(df, x, y, method="p90"),
        "dapi-repro": build_masks(df, x, y, method="dapi-repro"),
        "dapi-otsu": build_masks(df, x, y, method="dapi-otsu"),
        "dapi-gmm": build_masks(df, x, y, method="dapi-gmm"),
        "dapi-p90": build_masks(df, x, y, method="dapi-p90"),
    }
    method_rows = []
    for mname, masks in methods.items():
        attrs, odds, pdl1 = run_attribution(df, x, y, masks)
        for comp in COMPARTMENTS:
            method_rows.append({
                "method": mname, "compartment": comp,
                "attribution_fraction": attrs[comp], "odds_ratio": odds[comp],
                "pdl1_positive_fraction": float(pdl1.mean()),
            })
    method_df = pd.DataFrame(method_rows)
    method_df.to_csv(OUT_DIR / "method_comparison.csv", index=False)
    print("\nCompartment attribution by method (fraction of PD-L1+ cells):")
    print(method_df.pivot(index="method", columns="compartment", values="attribution_fraction")
          .round(3).to_string())
    print("\nOdds ratios by method:")
    print(method_df.pivot(index="method", columns="compartment", values="odds_ratio")
          .round(2).to_string())

    # Spatial enrichment under each method (cytotoxic + treg around each PD-L1+ compartment)
    enrich_rows = []
    for mname, masks in methods.items():
        pdl1 = masks["marker_PD_L1"]
        for pop_name, pop in immune_pop(masks).items():
            tidx = np.flatnonzero(pop)
            if tidx.size == 0:
                continue
            txy = coords[tidx]
            for comp, lm in COMPARTMENTS.items():
                sidx = np.flatnonzero(pdl1 & masks[lm])
                if sidx.size == 0:
                    continue
                sxy = coords[sidx]
                vals = neighbourhood_enrichment(sxy, txy, coords)
                for r, v in zip(RADII, vals):
                    enrich_rows.append({"method": mname, "population": pop_name,
                                        "compartment": comp, "radius": r, "enrichment": v})
    enrich_df = pd.DataFrame(enrich_rows)
    enrich_df.to_csv(OUT_DIR / "method_enrichment.csv", index=False)

    # Diagnostic: the enrichment ratio normalises by a GLOBAL target fraction, which is itself a
    # product of three threshold decisions (CD3+ x CD8+ x PD-1+). Print it per method so the reader
    # can see how much the "no enrichment = 1.0" baseline moves between methods - it is the thing that
    # makes the DAPI-normalised curves scale differently, not the local measurement.
    print("\nGlobal 'cytotoxic T-cell' fraction used as the enrichment baseline, per method:")
    print(f"{'method':16s} {'CD3+':>6s} {'CD8+':>6s} {'PD1+':>6s} {'cyto (product)':>16s}")
    for mname, masks in methods.items():
        f_cd3 = masks["marker_CD3"].mean()
        f_cd8 = masks["marker_CD8"].mean()
        f_pd1 = masks["marker_PD_1"].mean()
        cyto = (masks["marker_CD3"] & masks["marker_CD8"] & masks["marker_PD_1"]).mean()
        print(f"{mname:16s} {f_cd3*100:5.1f}% {f_cd8*100:5.1f}% {f_pd1*100:5.1f}% {cyto*100:15.2f}%")

    # Illustrate the enrichment under each method (does the 'epithelial dips below 1' hold?)
    # Split into two figures so the two *normalisation strategies* aren't lumped together, and
    # give each strategy the SAME set of positivity-rule variations so the two are comparable.
    original_family = ["repro", "otsu-only", "gmm-only", "no-local-corr", "p90-fixed"]
    dapi_family = ["dapi-repro", "dapi-otsu", "dapi-gmm", "dapi-p90"]

    def plot_enrich_panel(ax, masks):
        pdl1 = masks["marker_PD_L1"]
        for comp, lm in COMPARTMENTS.items():
            sidx = np.flatnonzero(pdl1 & masks[lm])
            if sidx.size == 0:
                continue
            sxy = coords[sidx]
            cyto = immune_pop(masks)["cytotoxic"]
            txy = coords[np.flatnonzero(cyto)] if cyto.sum() else np.empty((0, 2))
            if txy.shape[0]:
                vals = neighbourhood_enrichment(sxy, txy, coords)
                ax.plot(RADII, vals, marker="o", label=comp)

    def panel_titles(names):
        return [n.replace("dapi-", "DAPI · ").replace("-only", "").replace("-fixed", "")
                  .replace("no-local-corr", "no local subtraction") for n in names]

    # Figure 2a: original normalisation strategy family (5 panels)
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    for i, mname in enumerate(original_family):
        ax = axes.ravel()[i]
        plot_enrich_panel(ax, methods[mname])
        ax.axhline(1, color="grey", ls="--")
        ax.set_xlabel("radius")
        ax.set_title(panel_titles(original_family)[i], fontsize=10)
        ax.tick_params(labelsize=8)
    axes.ravel()[5].axis("off")
    axes[1, 0].set_ylabel("cytotoxic enrichment (obs/exp)", fontsize=10)
    axes[0, 0].legend(fontsize=7, loc="best")
    fig.suptitle(
        "Cytotoxic T-cell enrichment around PD-L1+ compartments —\n"
        "original normalisation (arcsinh + local background subtraction), "
        "varying the positivity rule",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(OUT_DIR / "enrichment_original_strategy.png", dpi=150)
    plt.close(fig)

    # Figure 2b: DAPI-ratio normalisation, same positivity-rule variations (4 panels)
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    for i, mname in enumerate(dapi_family):
        ax = axes.ravel()[i]
        plot_enrich_panel(ax, methods[mname])
        ax.axhline(1, color="grey", ls="--")
        ax.set_xlabel("radius")
        ax.set_title(panel_titles(dapi_family)[i], fontsize=10)
        ax.tick_params(labelsize=8)
    axes[0, 0].set_ylabel("cytotoxic enrichment (obs/exp)", fontsize=10)
    axes[1, 0].set_ylabel("cytotoxic enrichment (obs/exp)", fontsize=10)
    axes[0, 0].legend(fontsize=7, loc="best")
    fig.suptitle(
        "Cytotoxic T-cell enrichment around PD-L1+ compartments —\n"
        "DAPI-ratio normalisation (each marker / the cell's DNA signal), "
        "varying the positivity rule",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(OUT_DIR / "enrichment_dapi_norm.png", dpi=150)
    plt.close(fig)

    # Figure 3: spatial maps (hexbin), ONE PANEL PER COMPARTMENT, showing where each PD-L1+
    # compartment sits in the tissue. Two rows: original normalisation (top) vs DAPI (bottom). A
    # single fused map was tried and rejected - the most numerous compartment (SMA/stromal) drowned
    # the others out, so per-compartment panels are the only way to see localisation at all.
    compartment_colors = {
        "Macrophage (CD68+)": "Reds",
        "Epithelial (E-cad+)": "Purples",
        "Endothelial (CD31+)": "Greens",
        "Stromal (SMA+)": "Oranges",
    }
    short_names = {
        "Macrophage (CD68+)": "Macrophage",
        "Epithelial (E-cad+)": "Epithelial",
        "Endothelial (CD31+)": "Endothelial",
        "Stromal (SMA+)": "Stromal",
    }

    def draw_compartment_map(ax, masks, cmap):
        # tissue background: all cells
        ax.hexbin(x, y, gridsize=140, cmap="Greys", mincnt=1, edgecolors="none", alpha=0.35)
        return ax

    def overlay_compartment(ax, masks, lm, cmap):
        sidx = np.flatnonzero(masks["marker_PD_L1"] & masks[lm])
        n = sidx.size
        if n:
            ax.hexbin(x[sidx], y[sidx], gridsize=140, cmap=cmap, mincnt=1,
                      edgecolors="none", alpha=0.85)
        return n

    fig, axes = plt.subplots(2, 4, figsize=(20, 10))
    for row, (mname, masks) in enumerate([("repro", methods["repro"]),
                                           ("dapi-otsu", methods["dapi-otsu"])]):
        for col, (comp, lm) in enumerate(COMPARTMENTS.items()):
            ax = axes[row, col]
            draw_compartment_map(ax, masks, compartment_colors[comp])
            n = overlay_compartment(ax, masks, lm, compartment_colors[comp])
            ax.set_title(f"{short_names[comp]}\n(n={n:,})", fontsize=10)
            ax.tick_params(labelsize=7)
    for ax in axes[0]:
        ax.set_title(ax.get_title(), fontsize=10)
    axes[0, 0].set_ylabel("original normalisation\n\ny (spatial units)", fontsize=9)
    axes[1, 0].set_ylabel("DAPI normalisation\n\ny (spatial units)", fontsize=9)
    for ax in axes[1]:
        ax.set_xlabel("x (spatial units)")
    fig.suptitle("Where each PD-L1⁺ compartment actually sits in the tissue (one panel per cell type)",
                 fontsize=14)
    fig.tight_layout(rect=[0, 0.03, 1, 0.97])
    fig.savefig(OUT_DIR / "spatial_maps_per_compartment.png", dpi=150)
    plt.close(fig)

    print(f"\nOutputs written to {OUT_DIR}/")


if __name__ == "__main__":
    main()
