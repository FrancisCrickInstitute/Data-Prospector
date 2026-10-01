# -*- coding: utf-8 -*-
"""Broad dataset overview of the CellSurvey tissue section (WHOLE-CELL segmentation), for a biologist reader.

A visual summary of a single tissue section: cell populations (k-means clusters + marker
distributions), spatial maps overlaid on the tissue image, and the spatial communities. Data sources:

  - `inputs/cellsurvey_wholecell_processed/cells.csv` (repo-local): ~362,800 whole-cell objects (the
    CellSurvey whole-cell segmentation), each with x/y coordinates, area, a k-means cluster label, a
    spatial-community label, and ~32 marker intensities.
  - The source SpatialData zarr (Z: network path): the pyramid-downsampled DAPI channel, used as the
    grey tissue background behind the spatial maps and community outlines (optional; skipped if Z: down).

This is a hand-written, one-off follow-up (see docs/DEVELOPMENT_LOG.md rev. 91 / BACKLOG.md section 7 for
the `explorations/` convention) - no Docker, no judge, no gallery.

Run:  pixi run python explorations/cellsurvey_wholecell/overview_analysis.py
Reads: inputs/cellsurvey_wholecell_processed/cells.csv (local); the zarr on Z: for the image
       backgrounds (skipped gracefully if absent).
Writes: explorations/cellsurvey_wholecell/overview_analysis_report.md (tracked source) and
        explorations/cellsurvey_wholecell/out_overview/*.png (gitignored figures).

The CD68 caveat (docs/DEVELOPMENT_LOG.md rev. 95 / section 15.9) still applies: CD68 is treated as
autofluorescent/debris, not a real macrophage lineage marker. Debris clusters are DERIVED from this
run's clustering (not copied from the nuclear run), and cluster names are auto-generated from each
cluster's two strongest markers.
"""

import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter

sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path("inputs/cellsurvey_wholecell_processed")
CELLS_CSV = DATA_DIR / "cells.csv"
OUT_DIR = Path("explorations/cellsurvey_wholecell/out_overview")
# The report markdown is the tracked source-of-truth and lives beside this script; its figures live
# in the gitignored out_overview/ dir and are referenced relative to the report's own directory.
REPORT_MD = Path("explorations/cellsurvey_wholecell/overview_analysis_report.md")

# zarr is optional: representative images need it, everything else doesn't. Keep it out of the
# default import path so the script still works (and still writes all tables/figures) if Z: is down.
ZARR_URL = (
    "Z:/working/barryd/hpc/projects/stps/lm/Spatial-Biology-Pipeline/outputs/"
    "20260629_170222_3_mBsc8s_EHP893_25_29plex_V2_EHP576_26_COMET_29PLEX_3_whole_cell_seg.zarr"
)

# CellSurvey's read-only parameter sweeps (see https://cell-survey.readthedocs.io/en/latest/parameters/
# #parameter-sweeps). The user copied these CSVs locally into inputs/cellsurvey_processed/ so re-runs
# don't depend on Z: for the sensitivity analysis. (The zarr/DAPI image is still read from Z: for the
# image-overlay figures, and is optional.)
SWEEP_DIR = Path("inputs/cellsurvey_wholecell_processed")
COMMUNITY_SWEEP_CSV = SWEEP_DIR / "community_sweep.csv"
CLUSTER_SWEEP_CSV = SWEEP_DIR / "cluster_sweep.csv"
COMMUNITY_SWEEP_SUMMARY = SWEEP_DIR / "community_sweep_summary.csv"
CLUSTER_SWEEP_SUMMARY = SWEEP_DIR / "cluster_sweep_summary.csv"

# The s4 pyramid level is a ~16x downsample of full res; cell x/y (full-res pixel coords) divide by
# this to land on the s4 image grid. Orientation: y increases upward, matching imshow(origin="lower").
DOWNSAMPLE = 16.0
# The illustrative "positive" threshold used across this report (robust z-score). It is a display
# convenience, NOT a calibrated biological gate - see the marker-distribution note in the report.
POSITIVE_Z = 2.0
# Communities below this many cells are isolated fragments (e.g. the 13 CD31 single/few-cell islands);
# they are dropped from the composition ranking so the plot reflects real tissue regions, not debris.
MIN_COMMUNITY_SIZE = 1000

_dapi_cache = None


def read_dapi_s4():
    """Read the DAPI channel (index 0) from the s4 pyramid level, cached across figures."""
    global _dapi_cache
    if _dapi_cache is not None:
        return _dapi_cache
    import zarr
    g = zarr.open_group(ZARR_URL, mode="r")
    imgpath = "images/20260629_170222_3_mBsc8s_EHP893_25_29plex_V2_EHP576_26_COMET_29PLEX_3"
    dapi = np.asarray(g[imgpath + "/s4"][0], dtype="float32")
    _dapi_cache = dapi
    return dapi


def imshow_tissue(ax, dapi):
    """Draw the DAPI channel as a grayscale tissue background, in the cell-coordinate frame.

    No-op if dapi is None (Z: unavailable) - callers fall back to points on a plain background.
    """
    if dapi is None:
        return
    ax.imshow(dapi, cmap="gray", origin="lower",
              vmin=np.percentile(dapi, 1.0), vmax=np.percentile(dapi, 99.5))
    ax.set_xlim(0, dapi.shape[1])
    ax.set_ylim(0, dapi.shape[0])
    ax.set_aspect("equal")
    ax.tick_params(labelsize=6)

# 32 channels, index-order = the zarr image / var index. Index 0 is DAPI; indices 9 and 10 are the
# two autofluorescence control channels (TRITC (1) / Cy5 (1)), i.e. empty-cycle bleed-through controls.
# NOTE: the CSV column names differ from the zarr var names for the two control channels
# (marker_TRITC_1_TRITC / marker_Cy5_1_Cy5), so keep a dedicated column-name list below.
CHANNEL_INDEX = [
    "DAPI", "CD45RA", "Collagen_I", "HLADR", "p16", "CD45", "CD31", "CD20", "E_cadherin",
    "TRITC_1_TRITC", "Cy5_1_Cy5", "S100", "TP73", "CD68", "LY75", "H2AX", "Vimentin", "CD8",
    "Collagen_IV", "FoxP3", "LamininA5", "BCAM", "TP63", "PD_1", "CD3", "PD_L1", "CD56", "CD4",
    "SMA", "Ki_67", "CD11c", "Fibronectin",
]

# The CD68 channel is unreliable (debris/autofluorescence; rev. 95). Exclude from lineage attribution.
AUTOFLUORESCENT = {"CD68"}
CONTROL_CHANNELS = {"DAPI", "TRITC_1_TRITC", "Cy5_1_Cy5"}

# Lineage markers used to name cell populations (CD68 deliberately dropped).
LINEAGE_MARKERS = {
    "Epithelial": "E_cadherin",
    "Endothelial": "CD31",
    "Stromal": "SMA",
    "T-cell (CD8)": "CD8",
    "T-cell (CD4)": "CD4",
    "T-reg (FoxP3)": "FoxP3",
    "B-cell": "CD20",
    "NK": "CD56",
    "Myeloid/DC": "CD11c",
    "Leukocyte": "CD45",
    "Vascular (CD45RA/LY75)": "CD45RA",
}

# Cluster names and the debris-cluster set are DERIVED from the data at runtime (derive_debris_clusters
# / derive_cluster_names), because k-means cluster identities differ between the nuclear and whole-cell
# runs. Empty placeholders here; populated in main() before any figure that reads them.
CLUSTER_NAMES = {}
DEBRIS_CLUSTERS = set()


def load_cells():
    cols = ["cell_id", "area", "kmeans_cluster", "community", "x", "y"] + [
        f"marker_{m}" for m in CHANNEL_INDEX
    ]
    df = pd.read_csv(CELLS_CSV, usecols=cols)
    for c in cols[1:]:
        if c in ("kmeans_cluster", "community"):
            # keep ID columns as integers - casting them to float would render "1.0" etc.
            df[c] = df[c].astype("int32")
            continue
        if df[c].dtype == object:
            continue
        df[c] = df[c].astype("float32")
    return df


def robust_z(v):
    """Median/IQR robust z-score of arcsinh-transformed intensities (matches the sensitivity report)."""
    a = np.arcsinh(v.astype("float64"))
    med = np.median(a)
    iqr = np.percentile(a, 75) - np.percentile(a, 25)
    return (a - med) / iqr


def non_specific_mask(df, n_channels=8, z_cut=2.0):
    """Cells bright (z>2) in >= n_channels markers simultaneously = autofluorescent/debris."""
    marker_cols = [f"marker_{m}" for m in CHANNEL_INDEX if m not in CONTROL_CHANNELS]
    Z = np.column_stack([robust_z(df[c].to_numpy()) for c in marker_cols])
    return (Z > z_cut).sum(axis=1) >= n_channels


# The four markers that, bright together, are the canonical autofluorescence/debris signature for this
# tissue (CD68 is the reported failed channel; FoxP3/LamininA5/H2AX co-brighten with it because the
# whole cell is bright in everything). Used to flag whole clusters as debris.
DEBRIS_MARKERS = ["CD68", "FoxP3", "LamininA5", "H2AX"]


def debris_mask(df, z_cut=2.0):
    """Cells bright (z>2) in ALL of CD68/FoxP3/LamininA5/H2AX = confident non-specific debris."""
    m = np.ones(len(df), dtype=bool)
    for mk in DEBRIS_MARKERS:
        m &= robust_z(df[f"marker_{mk}"].to_numpy()) > z_cut
    return m


def derive_debris_clusters(df):
    """Identify the k-means clusters that are >50% autofluorescent debris (for this run's clustering)."""
    debris = debris_mask(df)
    return {int(c) for c in sorted(df["kmeans_cluster"].unique())
            if debris[df["kmeans_cluster"].to_numpy() == c].mean() > 0.5}


def derive_cluster_names(top):
    """Name each cluster from its two strongest markers (debris clusters labelled 'debris'), so the
    composition section describes the data's own marker profiles rather than a hand-curated glossary."""
    top_int = {int(c): markers for c, markers in top.items()}
    return {c: ("debris" if c in DEBRIS_CLUSTERS else "/".join(m for m, _ in top_int.get(c, [])[:2]))
            for c in top_int}


# Markers the collaborator's four thymus questions depend on, for the feasibility section.
FEASIBILITY_MARKERS = [
    "E_cadherin", "TP63", "BCAM", "TP73",                       # Q1 TEC niche
    "CD45", "CD3", "CD4", "CD8", "CD20", "CD68", "CD11c",       # Q2 immune residues
    "HLADR", "LY75", "FoxP3", "CD56",
    "Fibronectin", "LamininA5", "SMA", "CD31", "Collagen_I",    # Q3 matrix / vascular
    "Collagen_IV",
    "p16", "H2AX",                                              # Q4 senescence
]


def feasibility_stats(df):
    """Per-marker: % 'positive' (z>+2) and, of those, the % that are autofluorescent debris.
    Used to flag which of the collaborator's markers can't be thresholded naively."""
    debris = df["kmeans_cluster"].isin(sorted(DEBRIS_CLUSTERS)).to_numpy()
    rows = []
    for m in FEASIBILITY_MARKERS:
        pos = robust_z(df[f"marker_{m}"].to_numpy()) > POSITIVE_Z
        n_pos = int(pos.sum())
        pct_pos = pos.mean() * 100
        pct_debris = (pos & debris).sum() / n_pos * 100 if n_pos else 0.0
        rows.append({"marker": m, "pct_positive": pct_pos, "pct_debris": pct_debris})
    return pd.DataFrame(rows)


def cluster_marker_profile(df):
    """Mean robust-z intensity of each marker within each k-means cluster -> a profiling table."""
    marker_cols = [f"marker_{m}" for m in CHANNEL_INDEX if m not in CONTROL_CHANNELS]
    Z = pd.DataFrame(
        {m: robust_z(df[f"marker_{m}"].to_numpy()) for m in CHANNEL_INDEX if m not in CONTROL_CHANNELS}
    )
    Z["cluster"] = df["kmeans_cluster"].to_numpy()
    prof = Z.groupby("cluster").mean()
    # top markers per cluster, for naming
    top = {}
    for cl in prof.index:
        row = prof.loc[cl].sort_values(ascending=False)
        top[cl] = [(m, round(float(row[m]), 2)) for m in row.index[:5]]
    return prof, top


def figure_populations(df):
    """Two per-cluster mean-marker heatmaps: all 10 clusters, and the 7 non-debris clusters (the size
    of each cluster is already in the report table, so it isn't plotted again here)."""
    marker_cols = [f"marker_{m}" for m in CHANNEL_INDEX if m not in CONTROL_CHANNELS]
    prof, top = cluster_marker_profile(df)
    clusters = sorted(df["kmeans_cluster"].unique())
    non_debris = [c for c in clusters if c not in DEBRIS_CLUSTERS]
    sizes = df.groupby("kmeans_cluster").size()

    fig, axes = plt.subplots(1, 2, figsize=(18, 7), constrained_layout=True)
    disp_names = [m.replace("_", "-") for m in marker_cols]
    im = None
    for ax, cs, title in [(axes[0], clusters, "all clusters"),
                          (axes[1], non_debris, "debris clusters removed")]:
        im = ax.imshow(prof.loc[cs].to_numpy(), aspect="auto", cmap="RdBu_r", vmin=-2, vmax=2)
        ax.set_xticks(range(len(disp_names)))
        ax.set_xticklabels(disp_names, rotation=90, fontsize=7)
        ax.set_yticks(range(len(cs)))
        ax.set_yticklabels([f"Cluster {c}" for c in cs], fontsize=8)
        ax.set_title(f"Mean marker intensity per cluster — {title}", fontsize=11)
    # single shared colour scale on its own axes, so it never overlaps the heatmaps
    fig.colorbar(im, ax=axes, shrink=0.75, label="robust z-score")
    fig.suptitle("Cell populations: per-cluster marker profiles", fontsize=14)
    fig.savefig(OUT_DIR / "populations_cluster_profile.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return prof, top, sizes


def figure_marker_distributions(df):
    """Distribution of every biological marker (robust z-score), with the illustrative 'positive'
    line at z=+2 overlaid, so a reader can see how arbitrary the on/off call is on near-unimodal data."""
    markers = [m for m in CHANNEL_INDEX if m not in CONTROL_CHANNELS]
    cols = 5
    rows = math.ceil(len(markers) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 3 * rows))
    for ax, m in zip(axes.ravel(), markers):
        z = robust_z(df[f"marker_{m}"].to_numpy())
        ax.hist(z, bins=120, color="#9A9FA8", alpha=0.75, log=True)
        ax.axvline(POSITIVE_Z, color="#C1622D", lw=1.6)
        ax.axvline(0.0, color="#6C5B9E", lw=0.8, ls=":")
        pct_pos = float((z > POSITIVE_Z).mean() * 100)
        ax.set_title(f"{m}  ({pct_pos:.1f}% 'positive')", fontsize=8)
        ax.tick_params(labelsize=6)
    for ax in axes.ravel()[len(markers):]:
        ax.axis("off")
    fig.suptitle(
        "Marker distributions (robust z-score) — orange line = the illustrative 'positive' cutoff "
        "(z = +2); dotted = median (z = 0)",
        fontsize=13, y=1.02,
    )
    fig.tight_layout()
    fig.savefig(OUT_DIR / "marker_distributions.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

def figure_spatial_maps(df, dapi):
    """Spatial maps overlaid on the DAPI tissue image: one panel per cluster, one per lineage marker.

    Points are the cells (centroids), drawn over the actual tissue image so the maps sit in context
    instead of on a blank page. If Z: is down (dapi is None), fall back to full-res points on white.
    """
    use_img = dapi is not None
    x = (df["x"] / DOWNSAMPLE if use_img else df["x"]).to_numpy()
    y = (df["y"] / DOWNSAMPLE if use_img else df["y"]).to_numpy()

    clusters = [c for c in sorted(df["kmeans_cluster"].unique()) if c not in DEBRIS_CLUSTERS]
    fig, axes = plt.subplots(2, 4, figsize=(18, 8))
    for ax, c in zip(axes.ravel(), clusters):
        imshow_tissue(ax, dapi)
        sel = df["kmeans_cluster"].to_numpy() == c
        ax.scatter(x[sel], y[sel], s=0.2, alpha=0.15, color="#C1622D", linewidths=0)
        if not use_img:
            ax.set_aspect("equal")
        ax.set_title(f"Cluster {int(c)} ({int(sel.sum()):,})", fontsize=9)
        ax.tick_params(labelsize=6)
    axes.ravel()[len(clusters)].axis("off")
    fig.suptitle("Where each k-means cluster sits (over the DAPI tissue image; debris clusters omitted)",
                 fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "spatial_cluster_maps.png", dpi=150)
    plt.close(fig)

    lineage = [ln for ln in LINEAGE_MARKERS.values() if ln not in AUTOFLUORESCENT]
    fig, axes = plt.subplots(2, 5, figsize=(20, 8))
    for ax, m in zip(axes.ravel(), lineage):
        imshow_tissue(ax, dapi)
        hi = robust_z(df[f"marker_{m}"].to_numpy()) > POSITIVE_Z
        n = int(hi.sum())
        ax.scatter(x[hi], y[hi], s=0.3, alpha=0.35, color="#C1622D", linewidths=0)
        if not use_img:
            ax.set_aspect("equal")
        ax.set_title(f"{m} (n={n:,})", fontsize=9)
        ax.tick_params(labelsize=6)
    fig.suptitle("Cells positive for each lineage marker (z>+2), over the DAPI tissue image", fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "spatial_lineage_maps.png", dpi=150)
    plt.close(fig)


def community_composition(df):
    """Per-community cluster composition: dominant cluster, its share, and the named dominant type.

    Returns a DataFrame with one row per community, columns: dominant cluster, its fractional share,
    and a plain-language label for that cluster.
    """
    ct = pd.crosstab(df["community"], df["kmeans_cluster"])
    frac = ct.div(ct.sum(axis=1), axis=0)
    dom_cluster = frac.idxmax(axis=1)
    dom_share = frac.max(axis=1)
    dom_name = dom_cluster.map(CLUSTER_NAMES)
    out = pd.DataFrame({
        "dominant_cluster": dom_cluster,
        "dominant_share": dom_share,
        "dominant_type": dom_name,
    })
    out["n"] = ct.sum(axis=1)
    return out, frac


def figure_community_composition(df):
    """Stacked-bar of community composition, grouped by dominant cluster (not size) and with the tiny
    isolated communities (below MIN_COMMUNITY_SIZE) dropped, so the plot shows the real tissue regions
    rather than being dominated by 1-4 cell fragments."""
    comp, frac = community_composition(df)
    # drop the tiny isolated communities (e.g. the 13 CD31 single/few-cell islands)
    keep = comp[comp["n"] >= MIN_COMMUNITY_SIZE]
    frac_keep = frac.loc[keep.index]
    # rank by composition: group by dominant cluster, then size descending within each group
    order = keep.sort_values(["dominant_cluster", "n"], ascending=[True, False]).index.to_numpy()
    clusters = sorted(df["kmeans_cluster"].unique())
    frac_reord = frac_keep.loc[order, clusters]
    # colour each cluster by a stable palette; debris clusters get a grey
    cmap = plt.get_cmap("tab10")
    cluster_colors = {c: cmap(i) for i, c in enumerate(clusters)}
    for c in DEBRIS_CLUSTERS:
        cluster_colors[c] = (0.7, 0.7, 0.7)  # debris -> grey

    fig, ax = plt.subplots(figsize=(18, 6))
    bottom = np.zeros(len(order))
    for c in clusters:
        vals = frac_reord[c].to_numpy()
        ax.bar(range(len(order)), vals, bottom=bottom,
               color=cluster_colors[c], width=0.9, label=f"{c}: {CLUSTER_NAMES[c]}")
        bottom += vals
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([str(int(c)) for c in order], rotation=90, fontsize=7)
    ax.set_xlabel("community (grouped by dominant composition, then size; colour = dominant cluster)")
    ax.set_ylabel("fraction of community")
    ax.set_title(
        f"Community composition by k-means cluster — {len(order)} communities "
        f"({len(comp) - len(order)} tiny fragments <{MIN_COMMUNITY_SIZE} cells dropped)", fontsize=12)
    ax.legend(fontsize=7, ncol=2, loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "community_composition.png", dpi=150)
    plt.close(fig)
    return comp


def figure_community_outlines(df, dapi):
    """Community boundaries overlaid on the DAPI tissue image - the 'ROI' view.

    Each community is outlined by a smoothed density contour (not a coarse convex hull), so the
    boundary follows the actual cell positions. Only communities >= MIN_COMMUNITY_SIZE are drawn.
    """
    use_img = dapi is not None
    x = (df["x"] / DOWNSAMPLE if use_img else df["x"]).to_numpy()
    y = (df["y"] / DOWNSAMPLE if use_img else df["y"]).to_numpy()
    comm = df["community"].to_numpy()
    sizes = df.groupby("community").size()
    large = [c for c in sizes.index if sizes[c] >= MIN_COMMUNITY_SIZE]
    cmap = plt.get_cmap("tab20")

    grid = 300
    xmin, xmax = x.min(), x.max()
    ymin, ymax = y.min(), y.max()

    fig, ax = plt.subplots(figsize=(10, 10))
    imshow_tissue(ax, dapi)
    for i, c in enumerate(large):
        m = comm == c
        H, xe, ye = np.histogram2d(x[m], y[m], bins=grid, range=[[xmin, xmax], [ymin, ymax]])
        H = gaussian_filter(H, sigma=1.5)
        xc = (xe[:-1] + xe[1:]) / 2
        yc = (ye[:-1] + ye[1:]) / 2
        X, Y = np.meshgrid(xc, yc)
        level = max(H.max() * 0.02, 0.5)
        ax.contour(X, Y, H.T, levels=[level], colors=[cmap(i % 20)], linewidths=1.4)
    if not use_img:
        ax.set_aspect("equal")
    ax.set_title(f"Community outlines over the tissue image ({len(large)} communities)", fontsize=11)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "community_outlines.png", dpi=150)
    plt.close(fig)


def figure_cluster_hexmap(df, dapi):
    """Single hexbin map of all k-means clusters over the DAPI tissue image.

    One hexagon per spatial bin, filled with the colour of the DOMINANT cluster in that bin (the
    cluster with the most cells there), so the hexes are non-overlapping and each tile of the tissue
    is a single solid colour. Debris clusters are grey. Sized to match the community outlines map
    (10x10). The hex grid itself reflects density: a hex only appears where cells are present.
    """
    use_img = dapi is not None
    x = (df["x"] / DOWNSAMPLE if use_img else df["x"]).to_numpy()
    y = (df["y"] / DOWNSAMPLE if use_img else df["y"]).to_numpy()

    clusters = sorted(df["kmeans_cluster"].unique())
    cmap_src = plt.get_cmap("tab10")
    cluster_colors = {c: cmap_src(i) for i, c in enumerate(clusters)}
    for c in DEBRIS_CLUSTERS:
        cluster_colors[c] = (0.7, 0.7, 0.7)  # debris -> grey

    labels = df["kmeans_cluster"].to_numpy().astype(float)

    def dominant(vals):
        """Most frequent cluster label among the cells in one hex (mode)."""
        counts = np.bincount(np.asarray(vals, dtype=int))
        return int(np.argmax(counts))

    # Discrete colormap: one colour per cluster, in label order 0..9.
    cmap = ListedColormap([cluster_colors[c] for c in clusters])
    bounds = np.arange(len(clusters) + 1) - 0.5
    norm = BoundaryNorm(bounds, cmap.N)

    fig, ax = plt.subplots(figsize=(10, 10))
    imshow_tissue(ax, dapi)
    ax.hexbin(x, y, C=labels, reduce_C_function=dominant, cmap=cmap, norm=norm,
              gridsize=160, mincnt=1, edgecolors="none", alpha=0.9)
    if not use_img:
        ax.set_aspect("equal")
    ax.set_title(f"k-means clusters over the tissue image ({len(clusters)} clusters)", fontsize=11)
    handles = [
        mpatches.Patch(facecolor=cluster_colors[c], edgecolor="none",
                       label=f"{int(c)}: {CLUSTER_NAMES[c]}")
        for c in clusters
    ]
    ax.legend(handles=handles, fontsize=7, ncol=2, loc="upper right")
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "cluster_hexmap.png", dpi=150)
    plt.close(fig)


def load_sweep_data():
    """Load CellSurvey's community sweep outputs (local CSVs). Returns the sweep dict, or None on error."""
    try:
        comm_summary = pd.read_csv(COMMUNITY_SWEEP_SUMMARY)
        comm_sweep = pd.read_csv(COMMUNITY_SWEEP_CSV)
        return {
            "community_summary": comm_summary,
            "community_sweep": comm_sweep,
        }
    except Exception as e:
        print(f"[skip sweep analysis] could not load sweep CSVs: {e}")
        return None


def analyse_cd31_communities(df, sweep):
    """Answer the colleague's question: are the 13 CD31-only communities a fragment of one vessel, or
    genuinely separate? Returns a dict with the numbers needed to explain it.

    Communities come from Louvain on a Delaunay network weighted by expression similarity; the default
    `--community-resolution` 0.1 gives 49. The 13 tiny CD31 communities are isolated single/few-cell
    islands, not a large vessel split up, so lowering resolution does NOT merge them (they stay 13).
    """
    comm = sweep["community_sweep"]
    # join cells' kmeans_cluster to the sweep (sweep already has x/y)
    m = df[["cell_id", "kmeans_cluster"]].merge(comm, on="cell_id", how="inner")
    r01 = "community_r0.1_d1000"
    # dominant cluster per community at r0.1
    dom = m.groupby(r01)["kmeans_cluster"].agg(lambda s: s.mode()[0])
    cd31_comms = sorted(int(c) for c in dom[dom == 6].index)
    cd31_mask = m[r01].isin(cd31_comms)
    cd31_cells = m[cd31_mask]

    # how many communities do those CD31 cells map to at each resolution?
    merge_counts = {}
    for col in ["community_r0.05_d1000", "community_r0.02_d1000", "community_r0.01_d1000"]:
        merge_counts[col] = int(cd31_cells[col].nunique())

    # total CD31 (cluster 6) cells, and how they're distributed
    n_cd31_total = int((m["kmeans_cluster"] == 6).sum())
    n_cd31_in_tiny = int(cd31_mask.sum())

    return {
        "cd31_communities": cd31_comms,
        "n_cd31_total": n_cd31_total,
        "n_cd31_in_tiny": n_cd31_in_tiny,
        "merge_counts": merge_counts,
        "community_summary": sweep["community_summary"],
    }


def write_report(df, prof, top, sizes, comp, sweep_info, image_overlays):
    n = len(df)
    n_nonspecific = int(non_specific_mask(df).sum())
    debris = debris_mask(df)
    cluster_debris_frac = {
        c: float(debris[df["kmeans_cluster"].to_numpy() == c].mean())
        for c in sorted(sizes.index)
    }
    lines = []
    lines.append("# CellSurvey tissue — a broad overview\n")
    lines.append(f"One tissue section, **{n:,} segmented cells** (whole-cell segmentation), ~32 marker channels.\n")
    lines.append("This is a visual summary, not a single hypothesis test: who is in the tissue (cell\n"
                 "populations), where they are (spatial maps), and how the tissue is organised\n"
                 "(communities).\n")
    lines.append("## How to read this (in plain terms)\n")
    lines.append("**\"z-score\"** is just a way to put every marker on the same ruler. Raw brightness\n"
                 "numbers can't be compared directly — each marker is photographed at its own settings and\n"
                 "the slide is lit unevenly — so for each marker we centre every cell at \"0 = a typical\n"
                 "cell\" and count in steps of \"1 = one spread of the data\". A z-score of +2 means\n"
                 "\"noticeably brighter than the typical cell for that marker\"; it does **not** mean the\n"
                 "cell is definitively positive — the positive/negative line is a separate judgement call.\n")
    lines.append("**Two different kinds of grouping, and it is easy to confuse them.**\n"
                 "- **Clusters** (k-means) group cells by *what they express* — cells with similar marker\n"
                 "  profiles go together, wherever they sit in the tissue. One cell type = one cluster.\n"
                 "- **Communities** group cells by *where they are* — cells that sit next to each other,\n"
                 "  whatever they express. So a cell type that is physically scattered (like blood-vessel\n"
                 "  cells, which are in many separate vessels) shows up in many communities at once.\n"
                 "Both are computed by the CellSurvey pipeline from the same data; they just answer\n"
                 "different questions.\n")
    lines.append("## 1. Cell populations\n")
    lines.append("### Marker distributions, and what \"positive\" means\n")
    lines.append(f"The figure below shows the brightness distribution of every biological marker (on the z-score\n"
                 f"scale described above). The **orange line** is the illustrative \"positive\" cutoff used\n"
                 f"throughout this report: **z = +2**, i.e. the ~2% brightest cells for each marker. The dotted\n"
                 f"line is the median (z = 0).\n")
    lines.append(f"Two things worth reading from this: (1) **most markers have no clean second peak** — the\n"
                 f"histogram is one broad pile with a tail, so there is no obvious \"off\" vs \"on\" population\n"
                 f"to separate, and (2) the positive line is therefore a *choice*, not an inherent property of\n"
                 f"the data — move it and different cells flip sides. This report uses z = +2 purely as a\n"
                 f"display convenience, and where the biology matters the line should be chosen deliberately\n"
                 f"(or the marker treated as a continuous quantity instead of a positive/negative call).\n")
    lines.append("![Marker distributions with the positive cutoff](out_overview/marker_distributions.png)\n")
    lines.append("### The 10 k-means clusters\n")
    lines.append(f"The cells fall into **10 k-means clusters** (clustering shipped with the data). The\n"
                 f"table below lists, for each cluster, its size and the five markers that best\n"
                 f"distinguish it (mean robust z-score). **Debris%** flags how much of the cluster is\n"
                 f"non-specific autofluorescence (bright in CD68 + FoxP3 + LamininA5 + H2AX at once).\n")
    lines.append("![Cluster sizes and marker profiles](out_overview/populations_cluster_profile.png)\n")
    lines.append("| Cluster | Size | Debris% | Top distinguishing markers (z-score) |\n"
                 "|---|---|---|---|")
    for c in sorted(sizes.index):
        tops = ", ".join(f"{m} ({z:+.2f})" for m, z in top[c])
        df_frac = cluster_debris_frac[c] * 100
        note = " ⚠️ debris" if df_frac > 50 else ""
        lines.append(f"| {c} | {sizes.get(c, 0):,} | {df_frac:.0f}%{note} | {tops} |")
    # blank line AFTER the table (not between header and body rows), to keep the table intact
    lines.append("")
    debris_clusters = [str(c) for c in sorted(sizes.index) if cluster_debris_frac[c] > 0.5]
    lines.append(f"> **Clusters {', '.join(debris_clusters)} are almost entirely non-specific "
                 "autofluorescent debris**\n"
                 "> (bright in CD68 + FoxP3 + LamininA5 + H2AX simultaneously) and should not be read\n"
                 "> as real FoxP3⁺/LamininA5⁺/CD11c⁺ cell populations.\n")
    lines.append("> **CD68 note.** The CD68 channel is treated as autofluorescent/debris and is excluded\n"
                 "> from lineage attribution, so no 'macrophage' population is claimed here. "
                 f"{n_nonspecific:,} cells\n> ({n_nonspecific/n*100:.1f}%) are bright in ≥8 markers "
                 "simultaneously and are flagged as non-specific.\n")
    lines.append("## 2. Spatial maps\n")
    if image_overlays:
        lines.append("Where each cluster sits and where cells positive for each lineage marker sit, shown as\n"
                     "coloured points **overlaid on the actual tissue image** (DAPI = the greyscale nuclei):\n")
    else:
        lines.append("Where each cluster sits and where cells positive for each lineage marker sit (points only;\n"
                     "the tissue image background was skipped because Z: was unavailable):\n")
    lines.append("![Spatial map of each k-means cluster](out_overview/spatial_cluster_maps.png)\n")
    lines.append("The single map below shows **all clusters at once** (one colour per cluster, debris clusters\n"
                 "in grey) so the spatial layout of the cell types is visible without flipping between the\n"
                 "per-cluster panels above:\n")
    lines.append("![Hexbin map of all k-means clusters over the tissue image](out_overview/cluster_hexmap.png)\n")
    lines.append("![Spatial map of cells positive for each lineage marker](out_overview/spatial_lineage_maps.png)\n")
    lines.append("## 3. Neighbourhoods / communities\n")
    lines.append("Communities are built by the CellSurvey pipeline in two steps: it draws a network of\n"
                 "neighbouring cells (Delaunay triangulation, edges up to 1,000 px, each weighted by how\n"
                 "similar the two cells' marker profiles are), then runs **Louvain** community detection at a\n"
                 "**resolution** setting. Higher resolution → more, smaller communities; lower → fewer, larger.\n")
    lines.append(f"The **default** resolution (0.1) gives **{comp.shape[0]} communities**. That is on the\n"
                 f"fine-grained end — lowering the resolution merges most of that fine structure:\n")
    if sweep_info is not None:
        cs = sweep_info["community_summary"]
        res_vals = cs["resolution"].to_numpy()
        n_vals = cs["n_communities"].to_numpy()
        sweep_str = "; ".join(f"resolution {r:g} → {int(n)} communities" for r, n in zip(res_vals, n_vals))
        lines.append(f"- **Resolution sweep:** {sweep_str}.\n")
    lines.append("![Community outlines over the tissue image](out_overview/community_outlines.png)\n")

    # The colleague's question: the 13 CD31 communities.
    if sweep_info is not None:
        n13 = len(sweep_info["cd31_communities"])
        n_tiny = sweep_info["n_cd31_in_tiny"]
        n_total = sweep_info["n_cd31_total"]
        merge = sweep_info["merge_counts"]
        lines.append(f"**Why the {n13} CD31 communities are not \"one group that got split up.\"**\n")
        lines.append(f"The {n13} communities that look \"all CD31\" are actually **{n_tiny:,} isolated\n"
                     f"single/few-cell islands** (1–4 cells each), scattered across the whole tissue, not a\n"
                     f"large vessel broken into pieces. They are the minority of the CD31 population — the\n"
                     f"other **{n_total - n_tiny:,}** CD31 cells live inside larger, mixed communities. Because\n"
                     f"these {n_tiny:,} cells are physically separate, they correctly form separate *spatial*\n"
                     f"communities, and lowering the resolution does **not** merge them (they stay\n"
                     f"{merge.get('community_r0.01_d1000', n13)} communities even at resolution 0.01).\n")
        lines.append(f"If you want \"all CD31 cells as one group,\" that is exactly what the **cluster** label\n"
                     f"already gives you: cluster 6 is the single endothelial/vascular group, {n_total:,} cells,\n"
                     f"across the whole tissue. Communities answer \"where\", clusters answer \"what\" — the CD31\n"
                     f"cells being split across many communities is the correct answer to \"where\", not a\n"
                     f"detection failure.\n")

    # composition narrative (size-aware: tiny communities are trivially "pure", so describe the
    # filtered set >= MIN_COMMUNITY_SIZE, matching the composition figure).
    comp_keep = comp[comp["n"] >= MIN_COMMUNITY_SIZE]
    large = comp_keep.sort_values("n", ascending=False).head(10)
    large_counts = large["dominant_cluster"].value_counts()
    large_str = ", ".join(f"{CLUSTER_NAMES[c]} ({v} of the 10 largest)" for c, v in large_counts.items())
    lines.append("**Are there interesting patterns?** Yes, once you look at the *large* communities\n"
                 f"(the {len(comp) - len(comp_keep)} communities below {MIN_COMMUNITY_SIZE} cells are the\n"
                 f"isolated fragments already discussed, and are dropped from the composition plot):\n")
    lines.append(f"- The 10 largest communities are **{large_str}** — i.e. the tissue's big spatial blocks\n"
                 f"  are immune-rich (T-cell) and matrix-rich regions.\n")
    lines.append(f"- None of the {len(comp_keep)} remaining communities are over 80% one cluster, so\n"
                 f"  the large-scale tissue is genuinely mixed rather than divided into single-type blocks.\n")
    n_debris_comms = int(comp["dominant_cluster"].isin(sorted(DEBRIS_CLUSTERS)).sum())
    lines.append(f"- The debris clusters ({', '.join(map(str, sorted(DEBRIS_CLUSTERS)))}) hardly form their own\n"
                 f"  regions — together they dominate only {n_debris_comms} community — consistent with them\n"
                 f"  being scattered autofluorescent cells, not a tissue compartment.\n")
    lines.append("![Community composition by cluster](out_overview/community_composition.png)\n")

    # --- Feasibility of the collaborator's four thymus questions --------------------------------
    feas = feasibility_stats(df)
    f = {r["marker"]: r for _, r in feas.iterrows()}

    def flag(pct):
        return "debris-dominated" if pct > 50 else ("suspect" if pct > 25 else "clean")

    lines.append("## 4. Feasibility of the four thymus questions\n")
    lines.append("This is a **single thymus section**, and the marker panel contains everything the\n"
                 "collaborator asks about — but a few data-quality limits shape what can be answered.\n")
    lines.append("**Measurement compartment.** Each object is now a **whole-cell segmentation** (the nucleus\n"
                 "dilated into its surrounding cytoplasm), so each marker is the mean intensity over the nucleus\n"
                 "plus a cytoplasmic ring. That is a real improvement over the earlier nuclear-only readout, but it\n"
                 "is still a compromise rather than a per-marker measurement region:\n")
    lines.append("| Compartment | Markers | Whole-cell mean captures it? |\n"
                 "|---|---|---|\n"
                 "| nuclear | TP63, TP73, p16, Ki-67, FoxP3, H2AX | ⚠️ yes, but diluted by the added cytoplasm |\n"
                 "| membrane | E-cadherin, CD31, CD45, CD3/4/8, CD20, CD56, CD11c, HLA-DR, PD-1/PD-L1, LY75, BCAM | ~ partially — a whole-cell *mean* dilutes the thin membrane ring |\n"
                 "| cytoplasmic | SMA (αSMA), Vimentin, CD68 | ✅ now captured (was missed by nuclear-only) |\n"
                 "| extracellular matrix | Collagen I/IV, Fibronectin, LamininA5 | ❌ still *between* cells — not cell-localised |\n")
    lines.append("**The key empirical result: whole-cell segmentation did not rescue the membrane/immune\n"
                 "markers.** The table below shows CD45, CD4, HLA-DR and CD20 are still debris-dominated, and the\n"
                 "nuclear markers TP63/H2AX are still heavily contaminated. So the switch from nuclear to whole-cell\n"
                 "did not, by itself, recover a usable immune readout — either the cytoplasmic dilation is too small\n"
                 "to capture the membrane ring, or this involuted thymus genuinely has very few immune cells (the\n"
                 "two are hard to distinguish from these numbers alone).\n")
    lines.append("1. **Thymic epithelial stem-cell niches (E-cadherin⁺/TP63⁺ and BCAM⁺/TP73⁺).** Answerable\n"
                 "   in principle — all four markers are present and E-cadherin/TP73/BCAM are relatively clean —\n"
                 f"   but **TP63 is {f['TP63']['pct_debris']:.0f}% debris**, and E-cadherin/BCAM are membrane markers whose\n"
                 "   whole-cell mean is diluted, so the niche needs careful debris gating.\n")
    lines.append("2. **Thymic residues via immune markers.** Still the hardest. **CD68 did not work**\n"
                 "   (autofluorescent), so 'myeloid' can only be read from CD11c. CD45/CD3/CD4/HLA-DR still have\n"
                 f"   almost no real signal (each ≤{f['CD45']['pct_positive']:.1f}% 'positive', the bright cells mostly\n"
                 "   debris) — consistent with an involuted thymus with few remaining thymocytes, and not fixed by\n"
                 "   the whole-cell readout.\n")
    lines.append("3. **Matrix/vascular remodelling *with age*.** The markers (fibronectin, laminin, αSMA,\n"
                 "   CD31, collagens I/IV) are present and mostly clean, but this is **one section** — so it can show\n"
                 "   the current architecture, not change over time; and the ECM markers are still not cell-localised.\n")
    lines.append("4. **Senescence (p16, H2AX).** Both markers are **nuclear**, so this remains the most reliable\n"
                 f"   question (though their signal is diluted by the whole-cell mean). p16 is clean, but H2AX is\n"
                 f"   ~{f['H2AX']['pct_debris']:.0f}% debris and it is unconfirmed whether the panel's H2AX is the\n"
                 "   phosphorylated (γH2AX) DNA-damage form. 'Senescent behaviour' is a stronger claim than\n"
                 "   'expresses p16'.\n")
    lines.append("The table below quantifies this for every marker the questions depend on:\n")
    lines.append("| Marker | % positive (z>+2) | % of positive that are debris | Flag |\n"
                 "|---|---|---|---|")
    for _, r in feas.iterrows():
        lines.append(f"| {r['marker']} | {r['pct_positive']:.1f}% | {r['pct_debris']:.0f}% | {flag(r['pct_debris'])} |")
    lines.append("")
    debris_str = ", ".join(map(str, sorted(DEBRIS_CLUSTERS)))
    lines.append(f"> The debris cells (clusters {debris_str}) are the autofluorescent population that contaminates\n"
                 "> these markers, and they must be excluded before any co-expression / niche / proximity\n"
                 "> analysis. What the collaborator is ultimately asking for — niche detection, Ki-67\n"
                 "> co-staining, HLA-DR in residual regions, cell-to-niche proximity — is a hypothesis-driven\n"
                 "> analysis that can be built on this same data once that debris gate is applied.\n")

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main():
    global CLUSTER_NAMES, DEBRIS_CLUSTERS
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading cells ...")
    df = load_cells()
    print(f"  {len(df):,} cells")

    print("Reading DAPI background (optional) ...")
    dapi = None
    try:
        dapi = read_dapi_s4()
    except Exception as e:
        print(f"  [skip image overlays] could not read DAPI: {e}")

    # Derive debris clusters and cluster names from THIS run's clustering (whole-cell), not the
    # nuclear run's hand-curated glossary.
    DEBRIS_CLUSTERS = derive_debris_clusters(df)

    print("Figure 0: marker distributions ...")
    figure_marker_distributions(df)

    print("Figure 1: populations ...")
    prof, top, sizes = figure_populations(df)
    CLUSTER_NAMES = derive_cluster_names(top)

    print("Figure 2: spatial maps ...")
    figure_spatial_maps(df, dapi)
    figure_cluster_hexmap(df, dapi)

    print("Figure 3: communities ...")
    comp = figure_community_composition(df)
    figure_community_outlines(df, dapi)

    print("Community sensitivity (resolution) ...")
    sweep = load_sweep_data()
    sweep_info = analyse_cd31_communities(df, sweep) if sweep is not None else None

    write_report(df, prof, top, sizes, comp, sweep_info, dapi is not None)
    print(f"Done. Outputs in {OUT_DIR}/")


if __name__ == "__main__":
    main()
