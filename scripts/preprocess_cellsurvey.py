# -*- coding: utf-8 -*-
"""Preprocess one CellSurvey `.ome_seg.zarr` store into the flat per-cell CSV this repo's
cellsurvey config actually reads (`inputs/cellsurvey_processed/cells.csv`, plus a
`marker_channel_names.csv` sidecar).

WHY THIS EXISTS (and why the pipeline never reads the zarr itself)
------------------------------------------------------------------
The source is a SpatialData Zarr v3 store (produced by https://github.com/FrancisCrickInstitute/
CellSurvey, a 32-plex COMET multiplexed-immunofluorescence segmentation pipeline): a single tissue
sample, nuclei segmented with Stardist, each nucleus's per-marker MEAN intensity measured, cells
grouped by a fixed-k KMeans clustering, and a Delaunay spatial network partitioned into Louvain
communities. Reading it properly needs the `spatialdata`/`anndata` stack on top of `zarr`; neither
of those is in this project's pixi env, and NONE of it is needed for a purely tabular per-cell
analysis - this data is, after extraction, just a flat CSV. So this one-off script (run ONCE,
outside Docker, on the host where the Z: network path is mounted) pulls exactly the per-cell table
out of the zarr via `zarr` alone and writes it locally.

OUTPUT (what the config's `DOMAIN_NOTES` describes as one file under the data dir):
  cells.csv                 one row per segmented NUCLEUS (the CellSurvey pipeline's own "cell"
                            terminology; Stardist segments nuclei only - there is no whole-cell
                            boundary anywhere in this pipeline's output). Columns:
                              cell_id, area, x, y, kmeans_cluster, kmeans_cluster_label,
                              community, marker_* (32 columns, sanitised names)
  marker_channel_names.csv  traceability sidecar mapping each sanitised `marker_*` column name
                            back to the original acquisition-channel label (which carries the
                            exposure/gain/cycle/fluorophore metadata, e.g. the CYCLIC C1-C19
                            COMET protocol). NOT meant to be read by generated scripts.

The `marker_*` column names are SANITISED from the raw OME channel labels (e.g.
`αSMA_868_600-C17-CY3 - TRITC_ch_28` -> `marker_SMA`; `TRITC (1) - TRITC_ch_9` -> `marker_TRITC_1_TRITC`)
so they are valid, collision-free identifiers matching this project's cellsurvey config's marker
glossary. Non-ASCII (the leading α in αSMA) is stripped, hyphens become underscores, and the
trailing `_ch_<N>` + exposure/gain/cycle metadata is dropped, keeping only the marker name.

The `X`, `obsm/spatial`, and every `obs` array is read directly from the zarr group `tables/table`
(zarr v3, opened with `zarr>=3`). Categorical `obs` columns (`community`, `kmeans_cluster`,
`kmeans_cluster_label`) are `codes`/`categories` pairs, decoded to their integer/string values here.
`region` and `slide` (constant spatialdata-region bookkeeping) are dropped - the config's column
reference does not list them.

Run:  pixi run python scripts/preprocess_cellsurvey.py [--input <zarr_dir>] [--output <out_dir>]

Re-run only if the source zarr changes - the output is committed to `inputs/cellsurvey_processed/`
and the pipeline reads that flat CSV, never the zarr.
"""

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import zarr

sys.stdout.reconfigure(encoding="utf-8")

# Defaults matching the config's `data_dir_default` (`./inputs/cellsurvey_processed`) and the
# source zarr path currently mounted on this machine. Override with the CLI flags when either moves.
DEFAULT_INPUT = Path(
    "Z:/working/barryd/hpc/projects/stps/lm/Spatial-Biology-Pipeline/outputs/"
    "20260629_170222_3_mBsc8s_EHP893_25_29plex_V2_EHP576_26_COMET_29PLEX_3.ome_seg.zarr"
)
DEFAULT_OUTPUT = Path("inputs/cellsurvey_processed")

# Path to the anndata table inside the spatialdata store.
TABLE_PATH = "tables/table"

# The 32 sanitised marker-column names, in acquisition order. This is the EXPECTED output of
# `sanitize_marker_name` over `var/_index`, asserted at runtime so a wrong sanitisation fails
# loudly rather than silently producing a different schema than the config's glossary assumes.
EXPECTED_MARKERS = [
    "marker_DAPI",
    "marker_CD45RA",
    "marker_Collagen_I",
    "marker_HLADR",
    "marker_p16",
    "marker_CD45",
    "marker_CD31",
    "marker_CD20",
    "marker_E_cadherin",
    "marker_TRITC_1_TRITC",
    "marker_Cy5_1_Cy5",
    "marker_S100",
    "marker_TP73",
    "marker_CD68",
    "marker_LY75",
    "marker_H2AX",
    "marker_Vimentin",
    "marker_CD8",
    "marker_Collagen_IV",
    "marker_FoxP3",
    "marker_LamininA5",
    "marker_BCAM",
    "marker_TP63",
    "marker_PD_1",
    "marker_CD3",
    "marker_PD_L1",
    "marker_CD56",
    "marker_CD4",
    "marker_SMA",
    "marker_Ki_67",
    "marker_CD11c",
    "marker_Fibronectin",
]

_TRAILING_CH = re.compile(r"_ch_\d+$")


def sanitize_marker_name(raw_label: str) -> str:
    """Map a raw OME acquisition-channel label to a sanitised `marker_*` column name.

    The two background channels (`TRITC (1) - TRITC_ch_9`, `Cy5 (1) - Cy5_ch_10`) have no leading
    underscore-delimited marker token; every other label is `<marker>_<exposure>_<gain>-<cycle>-<fluor>
    - <channel>_ch_<N>` (or the bare `DAPI_ch_0`), so the marker name is the leading token up to the
    first underscore. Special-case the two background channels to their glossary names.
    """
    stripped = _TRAILING_CH.sub("", raw_label)
    # Background/secondary-only channels: "TRITC (1) - TRITC" / "Cy5 (1) - Cy5".
    if stripped in {"TRITC (1) - TRITC", "Cy5 (1) - Cy5"}:
        name = stripped.replace(" (1) - ", "_1_")
    else:
        name = stripped.split("_", 1)[0]
    # Non-ASCII (the leading α in αSMA) -> drop non-ASCII so the identifier is clean.
    name = "".join(ch for ch in name if ch.isascii())
    # Hyphens -> underscores (Collagen-I -> Collagen_I, PD-1 -> PD_1, Ki-67 -> Ki_67, etc.).
    name = name.replace("-", "_")
    return f"marker_{name}"


def _decode_categorical(group) -> np.ndarray:
    """Decode an anndata categorical `obs` group (codes + categories) to its string values."""
    categories = np.asarray(group["categories"][:])
    codes = np.asarray(group["codes"][:])
    return categories[codes]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT))
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Opening {input_path}")
    root = zarr.open(str(input_path), mode="r")
    if TABLE_PATH not in root:
        raise SystemExit(f"{TABLE_PATH!r} not found in the store - is this a `.ome_seg.zarr` directory?")
    t = root[TABLE_PATH]

    n_cells = t["X"].shape[0]
    print(f"Table has {n_cells} rows")

    # Marker columns: X is (n_cells, 32) float64, named by var/_index.
    var_index = [str(v) for v in t["var/_index"][:]]
    if len(var_index) != 32:
        raise SystemExit(f"Expected 32 marker channels, found {len(var_index)}")

    sanitised = [sanitize_marker_name(label) for label in var_index]
    if sanitised != EXPECTED_MARKERS:
        for raw, got, want in zip(var_index, sanitised, EXPECTED_MARKERS):
            if got != want:
                print(f"  MISMATCH: {raw!r} -> {got!r} (expected {want!r})")
        raise SystemExit(
            "Sanitised marker names do not match the config's expected schema (see above). "
            "Fix sanitize_marker_name / EXPECTED_MARKERS before writing output."
        )

    # Coordinates: obsm/spatial is (n_cells, 2) -> x, y.
    spatial = np.asarray(t["obsm/spatial"][:])
    if spatial.shape != (n_cells, 2):
        raise SystemExit(f"obsm/spatial shape {spatial.shape}, expected ({n_cells}, 2)")

    # Build the dataframe column by column, avoiding a full dense copy of X in one shot where
    # practical (X is ~93 MB of float64; a single DataFrame slice per column keeps peak memory in
    # check on the host, though this runs outside Docker here).
    data = {
        "cell_id": [str(c) for c in t["obs/cell_id"][:]],
        "area": np.asarray(t["obs/area"][:]),
        "x": spatial[:, 0],
        "y": spatial[:, 1],
        # community/kmeans_cluster are categorical with string-digit categories -> decode to ints
        # (the config treats them as integer ids, and their categories are '0'..'9' / '0'..'48').
        "community": _decode_categorical(t["obs/community"]).astype(np.int64),
        "kmeans_cluster": _decode_categorical(t["obs/kmeans_cluster"]).astype(np.int64),
        "kmeans_cluster_label": _decode_categorical(t["obs/kmeans_cluster_label"]),
    }
    # Marker columns.
    X = t["X"]
    for i, col in enumerate(sanitised):
        data[col] = np.asarray(X[:, i])

    # Column order: identity/geometry/shape first, grouping columns, then the 32 marker columns.
    order = ["cell_id", "area", "x", "y", "kmeans_cluster", "kmeans_cluster_label", "community"] + sanitised
    df = pd.DataFrame(data)[order]

    cells_path = output_dir / "cells.csv"
    df.to_csv(cells_path, index=False)
    print(f"Wrote {cells_path} ({len(df)} rows x {len(df.columns)} columns)")

    # Traceability sidecar: sanitised column name <-> original channel label.
    sidecar = pd.DataFrame(
        {"sanitized_column": sanitised, "channel_name": var_index}
    )
    sidecar_path = output_dir / "marker_channel_names.csv"
    sidecar.to_csv(sidecar_path, index=False)
    print(f"Wrote {sidecar_path} ({len(sidecar)} rows)")


if __name__ == "__main__":
    main()
