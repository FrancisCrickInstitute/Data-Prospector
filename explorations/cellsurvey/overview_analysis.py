# -*- coding: utf-8 -*-
"""Broad dataset overview of the CellSurvey tissue section, for a biologist reader.

Motivation: following the threshold-sensitivity report, a domain-expert colleague asked for a *visual
summary* rather than another methodological audit - specifically (1) cell populations / classification,
(2) spatial maps of where cell types and markers sit in the tissue, (3) neighbourhoods / clusters, and
(4) representative images tying the analysis back to the actual tissue. This script delivers all four as
a set of figures plus a markdown report, drawing on two sources:

  - `inputs/cellsurvey_processed/cells.csv` (repo-local): 362,736 segmented nuclei, each with x/y
    coordinates, area, a k-means cluster label, a spatial-community label, and ~32 marker intensities.
  - The source SpatialData zarr (Z: network path, supplied by the user): the full-resolution (and
    pyramid-downsampled) 32-channel image, used ONLY for the representative-image crops.

It is a hand-written, one-off follow-up (see docs/DEVELOPMENT_LOG.md rev. 91 / BACKLOG.md section 7 for
the `explorations/` convention) - no Docker, no judge, no gallery.

Run:  pixi run python explorations/cellsurvey/overview_analysis.py
Reads: inputs/cellsurvey_processed/cells.csv, and (for representative images only) the zarr at ZARR_URL.
Writes: explorations/cellsurvey/overview_analysis_report.md (tracked source) and explorations/cellsurvey/out_overview/*.png (gitignored figures).

The CD68 caveat (docs/DEVELOPMENT_LOG.md rev. 95 / section 15.9) is applied throughout: CD68 is treated
as autofluorescent/debris, not as a real macrophage lineage marker, so it is EXCLUDED from lineage
attribution and flagged where it would otherwise mislead.
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path("inputs/cellsurvey_processed")
CELLS_CSV = DATA_DIR / "cells.csv"
OUT_DIR = Path("explorations/cellsurvey/out_overview")
# The report markdown is the tracked source-of-truth and lives beside this script (matching the
# threshold-sensitivity report's convention); its figures live in the gitignored out_overview/ dir
# and are referenced relative to the report's own directory.
REPORT_MD = Path("explorations/cellsurvey/overview_analysis_report.md")

# zarr is optional: representative images need it, everything else doesn't. Keep it out of the
# default import path so the script still works (and still writes all tables/figures) if Z: is down.
ZARR_URL = (
    "Z:/working/barryd/hpc/projects/stps/lm/Spatial-Biology-Pipeline/outputs/"
    "20260629_170222_3_mBsc8s_EHP893_25_29plex_V2_EHP576_26_COMET_29PLEX_3.ome_seg.zarr"
)

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

# A plain-language label for each k-means cluster, hand-assigned from its dominant marker profile so
# the community-composition section can talk about "T-cell-rich regions" rather than "cluster 7". These
# are *descriptive* (a cluster may blend several cell types), and the three debris clusters (1/3/8) are
# marked as such rather than given a biological name.
CLUSTER_NAMES = {
    0: "immune (CD3/CD4/leukocyte)",
    1: "debris",
    2: "collagen-rich (fibroblast/matrix)",
    3: "debris",
    4: "leukocyte (CD45RA/CD20)",
    5: "mixed matrix (collagen/S100)",
    6: "endothelial/vascular (CD31)",
    7: "proliferative immune (Ki-67/CD3/CD8)",
    8: "debris",
    9: "epithelial (E-cadherin)",
}


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
    """Panel 1: cluster sizes + per-cluster marker heatmap (the 'who is in this tissue' figure)."""
    marker_cols = [f"marker_{m}" for m in CHANNEL_INDEX if m not in CONTROL_CHANNELS]
    prof, top = cluster_marker_profile(df)
    clusters = sorted(df["kmeans_cluster"].unique())
    sizes = df.groupby("kmeans_cluster").size()

    fig, axes = plt.subplots(1, 2, figsize=(18, 7), gridspec_kw={"width_ratios": [1, 2.2]})

    # left: cluster sizes
    ax = axes[0]
    ax.bar([str(c) for c in clusters], [sizes.get(c, 0) for c in clusters],
           color="#6C5B9E", alpha=0.85)
    ax.set_xlabel("k-means cluster")
    ax.set_ylabel("number of nuclei")
    ax.set_title("Cluster sizes", fontsize=12)
    for i, c in enumerate(clusters):
        ax.text(i, sizes.get(c, 0), f"{sizes.get(c, 0):,}", ha="center", va="bottom", fontsize=8)

    # right: marker profile heatmap (z-scored), clusters x markers
    ax = axes[1]
    disp_names = [m.replace("_", "-") for m in marker_cols]
    im = ax.imshow(prof.loc[[c for c in clusters]].to_numpy(), aspect="auto", cmap="RdBu_r",
                   vmin=-2, vmax=2)
    ax.set_xticks(range(len(disp_names)))
    ax.set_xticklabels(disp_names, rotation=90, fontsize=7)
    ax.set_yticks(range(len(clusters)))
    ax.set_yticklabels([f"Cluster {c} ({sizes.get(c, 0):,})" for c in clusters], fontsize=8)
    ax.set_title("Mean marker intensity per cluster (robust z-score)", fontsize=12)
    fig.colorbar(im, ax=ax, fraction=0.03)
    fig.suptitle("Cell populations: k-means clusters and their marker profiles", fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "populations_cluster_profile.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return prof, top, sizes


def figure_spatial_maps(df):
    """Panel 2: hexbin spatial maps - one per cluster and one per key lineage marker.

    Each cluster's cells span the whole tissue (they are not spatially separated), so a raw density
    map of the cluster alone looks identical to every other cluster. Instead each panel shows the
    cluster's LOCAL ENRICHMENT: (cluster density in a hex) / (total-cell density in that hex), so
    regions where the cluster is locally over- or under-represented become visible rather than being
    swamped by the shared tissue outline.
    """
    clusters = sorted(df["kmeans_cluster"].unique())
    # reference: total-cell density per hex (fixed gridsize, shared across all panels)
    grid = 140
    _, xedges, yedges = np.histogram2d(df["x"], df["y"], bins=grid)
    total_h, _, _ = np.histogram2d(df["x"], df["y"], bins=[xedges, yedges])

    fig, axes = plt.subplots(2, 5, figsize=(20, 8))
    for ax, c in zip(axes.ravel(), clusters):
        sel = df["kmeans_cluster"] == c
        # faint tissue outline (all cells) for orientation
        ax.hexbin(df["x"], df["y"], gridsize=grid, cmap="Greys", mincnt=1, edgecolors="none", alpha=0.15)
        cl_h, _, _ = np.histogram2d(df["x"][sel], df["y"][sel], bins=[xedges, yedges])
        # local enrichment = cluster density / total density, softened where total is sparse
        enrich = cl_h / np.maximum(total_h, 1.0)
        enrich[total_h < 10] = np.nan  # mask sparse cells so noise doesn't dominate
        im = ax.pcolormesh(xedges, yedges, enrich.T, cmap="RdBu_r", vmin=0.0, vmax=2.0,
                           shading="auto", alpha=0.9)
        ax.set_title(f"Cluster {int(c)} ({int(sel.sum()):,})", fontsize=9)
        ax.set_aspect("equal")
        ax.tick_params(labelsize=6)
    fig.suptitle("Spatial maps: local enrichment of each k-means cluster (red = locally over-represented)",
                 fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "spatial_cluster_maps.png", dpi=150)
    plt.close(fig)

    # lineage marker maps (CD68 excluded)
    lineage = [ln for ln in LINEAGE_MARKERS.values() if ln not in AUTOFLUORESCENT]
    fig, axes = plt.subplots(2, 5, figsize=(20, 8))
    for ax, m in zip(axes.ravel(), lineage):
        v = df[f"marker_{m}"].to_numpy()
        hi = robust_z(v) > 2.0
        n = int(hi.sum())
        ax.hexbin(df["x"], df["y"], gridsize=100, cmap="Greys", mincnt=1, edgecolors="none", alpha=0.25)
        ax.hexbin(df["x"][hi], df["y"][hi], gridsize=100, cmap="Reds", mincnt=1, edgecolors="none")
        ax.set_title(f"{m} (n={n:,})", fontsize=9)
        ax.set_aspect("equal")
        ax.tick_params(labelsize=6)
    fig.suptitle("Spatial maps: cells positive for each lineage marker (z>2)", fontsize=14)
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
    """Panel 3b: a stacked-bar of community composition, coloured by dominant cluster type, so the
    reader can see at a glance whether the tissue is organised into distinct, compositionally coherent
    regions (i.e. whether there are 'interesting patterns' in the spatial structure)."""
    comp, frac = community_composition(df)
    # order communities left->right by size; stack the cluster fractions
    comms_ordered = comp.sort_values("n", ascending=False).index.to_numpy()
    clusters = sorted(df["kmeans_cluster"].unique())
    frac_reord = frac.loc[comms_ordered, clusters]
    # colour each cluster by a stable palette; debris clusters get a grey
    cmap = plt.get_cmap("tab10")
    cluster_colors = {c: cmap(i) for i, c in enumerate(clusters)}
    for c in (1, 3, 8):
        cluster_colors[c] = (0.7, 0.7, 0.7)  # debris -> grey

    fig, ax = plt.subplots(figsize=(18, 6))
    bottom = np.zeros(len(comms_ordered))
    for c in clusters:
        vals = frac_reord[c].to_numpy()
        ax.bar(range(len(comms_ordered)), vals, bottom=bottom,
               color=cluster_colors[c], width=0.9, label=f"{c}: {CLUSTER_NAMES[c]}")
        bottom += vals
    ax.set_xticks(range(len(comms_ordered)))
    ax.set_xticklabels([f"{c}" for c in comms_ordered], fontsize=7)
    ax.set_xlabel("community (ranked by size)")
    ax.set_ylabel("fraction of community")
    ax.set_title("Community composition by k-means cluster (tissue regions are not uniform)", fontsize=12)
    ax.legend(fontsize=7, ncol=2, loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "community_composition.png", dpi=150)
    plt.close(fig)
    return comp


def figure_communities(df):
    """Panel 3: spatial-community overview - community histogram + community map."""
    comms = df.groupby("community").size().sort_values(ascending=False)
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))
    ax = axes[0]
    ax.bar(range(len(comms)), comms.to_numpy(), color="#2E7D6B", alpha=0.85)
    ax.set_xlabel("community (ranked by size)")
    ax.set_ylabel("number of nuclei")
    ax.set_title("Spatial communities (Leiden-style property communities)", fontsize=11)
    ax.tick_params(labelsize=7)

    ax = axes[1]
    # colour communities by index for spatial legibility
    comm_ids = sorted(df["community"].unique())
    cmap = plt.get_cmap("tab20")
    colors = {c: cmap(i % 20) for i, c in enumerate(comm_ids)}
    cvec = np.array([colors[c] for c in df["community"].to_numpy()])
    ax.scatter(df["x"], df["y"], c=cvec, s=0.3, alpha=0.6)
    ax.set_aspect("equal")
    ax.set_title("Spatial layout of communities", fontsize=11)
    ax.tick_params(labelsize=7)
    fig.suptitle("Neighbourhoods: the tissue's spatial-community structure", fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "communities.png", dpi=150)
    plt.close(fig)
    return comms


def figure_representative_images():
    """Panel 4: downsampled multi-channel composites from the zarr (optional; skip if Z: unavailable).

    Reads the s4 pyramid level (2775 x 2790), which is a ~16x downsample of full res, and renders a
    3-channel RGB composite (DAPI + two markers) plus a DAPI tissue outline. Kept to a few channels so
    the network read is tolerable.
    """
    import zarr

    try:
        g = zarr.open_group(ZARR_URL, mode="r")
    except Exception as e:
        print(f"[skip representative images] could not open zarr: {e}")
        return False

    imgpath = "images/20260629_170222_3_mBsc8s_EHP893_25_29plex_V2_EHP576_26_COMET_29PLEX_3"
    s4 = g[imgpath + "/s4"]

    # read the channels we need in one go: DAPI (0), CD3 (24), PD-L1 (25), E-cadherin (8), SMA (28)
    want = [0, 24, 25, 8, 28]
    print("[images] reading downsampled channels ...")
    stack = s4[want]  # (5, H, W) uint16 - one batched read
    H, W = stack.shape[1], stack.shape[2]
    dapi = stack[0]
    cd3 = stack[1]
    pdl1 = stack[2]
    ecad = stack[3]
    sma = stack[4]

    def norm(im, p_lo=1.0, p_hi=99.5):
        im = im.astype("float64")
        lo, hi = np.percentile(im, p_lo), np.percentile(im, p_hi)
        return np.clip((im - lo) / (hi - lo + 1e-9), 0, 1)

    # 3-channel composite: DAPI (blue), CD3 (green), PD-L1 (red)
    rgb = np.stack([norm(pdl1), norm(cd3), norm(dapi)], axis=-1)

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    axes[0].imshow(rgb)
    axes[0].set_title("Composite: DAPI (blue) / CD3 (green) / PD-L1 (red)", fontsize=11)
    axes[0].axis("off")
    axes[1].imshow(norm(dapi), cmap="gray")
    axes[1].set_title("DAPI (nuclei) — tissue outline", fontsize=11)
    axes[1].axis("off")
    fig.suptitle("Representative images (16x-downsampled full field of view)", fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "representative_images.png", dpi=150)
    plt.close(fig)

    # Also a second composite: E-cadherin (epithelial) vs SMA (stromal)
    rgb2 = np.stack([norm(ecad), norm(sma), norm(dapi)], axis=-1)
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(rgb2)
    ax.set_title("Composite: DAPI (blue) / E-cadherin (green) / SMA (red)", fontsize=11)
    ax.axis("off")
    fig.suptitle("Representative images (16x-downsampled full field of view)", fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "representative_images_epi_stromal.png", dpi=150)
    plt.close(fig)
    return True


def write_report(df, prof, top, sizes, comms, comp, images_ok):
    n = len(df)
    n_nonspecific = int(non_specific_mask(df).sum())
    debris = debris_mask(df)
    cluster_debris_frac = {
        c: float(debris[df["kmeans_cluster"].to_numpy() == c].mean())
        for c in sorted(sizes.index)
    }
    lines = []
    lines.append("# CellSurvey tissue — a broad overview\n")
    lines.append(f"One tissue section, **{n:,} segmented nuclei**, ~32 marker channels.\n")
    lines.append("This is a visual summary, not a single hypothesis test: who is in the tissue (cell\n"
                 "populations), where they are (spatial maps), how the tissue is organised\n"
                 "(communities), and what it looks like (representative images).\n")
    lines.append("## How to read this (in plain terms)\n")
    lines.append("**\"z-score\"** is just a way to put every marker on the same ruler. Raw brightness\n"
                 "numbers can't be compared directly — each marker is photographed at its own settings and\n"
                 "the slide is lit unevenly — so for each marker we centre every cell at \"0 = a typical\n"
                 "cell\" and count in steps of \"1 = one spread of the data\". A z-score of +2 means\n"
                 "\"noticeably brighter than the typical cell for that marker\"; it does **not** mean the\n"
                 "cell is definitively positive — the positive/negative line is a separate judgement call.\n"
                 "**\"Community\"** just means a cluster of nuclei that sit next to each other\n"
                 "in the tissue (found algorithmically); it's a way to ask \"what regions does this tissue\n"
                 "break into?\" without imposing a predefined map.\n")
    lines.append("## 1. Cell populations\n")
    lines.append(f"The nuclei fall into **10 k-means clusters** (clustering shipped with the data). The\n"
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
                 f"{n_nonspecific:,} nuclei\n> ({n_nonspecific/n*100:.1f}%) are bright in ≥8 markers "
                 "simultaneously and are flagged as non-specific.\n")
    lines.append("## 2. Spatial maps\n")
    lines.append("Where each cluster sits and where cells positive for each lineage marker sit:\n")
    lines.append("![Spatial map of each k-means cluster](out_overview/spatial_cluster_maps.png)\n")
    lines.append("![Spatial map of cells positive for each lineage marker](out_overview/spatial_lineage_maps.png)\n")
    lines.append("## 3. Neighbourhoods / communities\n")
    lines.append(f"The tissue is partitioned into **{len(comms)} spatial communities** (property-graph\n"
                 f"communities over neighbouring nuclei); the largest has {comms.iloc[0]:,} nuclei.\n")
    lines.append("![Community histogram and spatial layout](out_overview/communities.png)\n")
    # composition narrative: are communities compositionally coherent?
    dom_counts = comp["dominant_cluster"].value_counts()
    top_comms = dom_counts.head(3)
    top_str = ", ".join(f"{CLUSTER_NAMES[c]} ({v} communities)" for c, v in top_comms.items())
    n_pure = int((comp["dominant_share"] > 0.8).sum())
    lines.append("**Are there interesting patterns?** Yes, and the composition plot makes them visible:\n")
    lines.append(f"- The communities are **not all the same** — the most common community identities are\n"
                 f"  {top_str}.\n")
    lines.append(f"- {n_pure} of {len(comms)} communities are \"pure\" (over 80% one cluster), meaning the tissue\n"
                 f"  separates into **compositionally distinct regions** rather than an even mix everywhere.\n"
                 f"- The three debris clusters (1/3/8) hardly form their own regions — together they dominate\n"
                 f"  only {int(((dom_cluster := comp['dominant_cluster']).isin([1, 3, 8])).sum())} community —\n"
                 f"  consistent with them being scattered autofluorescent cells, not a tissue compartment.\n")
    lines.append("![Community composition by cluster](out_overview/community_composition.png)\n")
    lines.append("## 4. Representative images\n")
    if images_ok:
        lines.append("DAPI/CD3/PD-L1 and DAPI/E-cadherin/SMA composites of the actual tissue at 16x\n"
                     "downsampling:\n")
        lines.append("![Composite: DAPI / CD3 / PD-L1](out_overview/representative_images.png)\n")
        lines.append("![Composite: DAPI / E-cadherin / SMA](out_overview/representative_images_epi_stromal.png)\n")
    else:
        lines.append("*(skipped — source zarr not reachable at Z: this run)*\n")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading cells ...")
    df = load_cells()
    print(f"  {len(df):,} nuclei")

    print("Figure 1: populations ...")
    prof, top, sizes = figure_populations(df)

    print("Figure 2: spatial maps ...")
    figure_spatial_maps(df)

    print("Figure 3: communities ...")
    comms = figure_communities(df)
    comp = figure_community_composition(df)

    print("Figure 4: representative images ...")
    images_ok = figure_representative_images()

    write_report(df, prof, top, sizes, comms, comp, images_ok)
    print(f"Done. Outputs in {OUT_DIR}/")


if __name__ == "__main__":
    main()
