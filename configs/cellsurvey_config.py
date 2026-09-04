"""CellSurvey spatial-omics domain configuration for the pipeline.

One tissue sample run through the CellSurvey pipeline (https://github.com/FrancisCrickInstitute/
CellSurvey): a 32-plex COMET multiplexed immunofluorescence image, nuclei segmented with Stardist,
each cell's per-marker mean intensity measured, cells grouped by a fixed-k KMeans clustering, and a
Delaunay spatial network built and partitioned into Louvain communities. 362,736 cells total.

CRITICAL FRAMING - read before writing ideation/judging prompts against this domain: `kmeans_cluster`
and `community` are NOT validated ground truth about this tissue's biology. They are one arbitrary
parameterisation the CellSurvey pipeline happened to run with (k=10 fixed, not chosen against any
biological criterion; Louvain resolution=0.1 and a hard Delaunay edge-distance cutoff of 1000, also
pipeline defaults, not tuned or validated). Unlike inputs/idr0028_report's `Published_*` columns
(a genuine prior finding to avoid re-deriving), these two columns are a candidate to INTERROGATE, not
a result to build on top of or avoid repeating. A central objective of this domain is proposing
alternative, more biologically-grounded ways to define cell populations and spatial niches - e.g.
canonical marker-positivity gating (using the marker glossary in DOMAIN_NOTES, since these are named
immunophenotyping markers with real, checkable biological meaning), a KNN or radius-based graph
instead of the hard distance cutoff, a resolution sweep, or neighbourhood-composition niches (each
cell's local marker/cluster mix within a radius) rather than a single global partition. See
inputs/cellsurvey_report/task_report.md's guiding questions for how this is put to the ideation stage.

The source data (a SpatialData Zarr store, `*_seg.zarr`, on a remote/network path) is genuinely
awkward for this pipeline to read directly - see preprocess_cellsurvey.py's module docstring for the
full account of why (needs `zarr` at minimum, would normally want `anndata`/`spatialdata`, neither of
which is in this project's pixi env or needed for a purely tabular per-cell analysis).
preprocess_cellsurvey.py (run ONCE, already done - see its docstring) extracts exactly the per-cell
table this config's `extract_input_metadata`/`data_profile` below actually read:
inputs/cellsurvey_processed/cells.csv (+ a marker_channel_names.csv sidecar mapping sanitised column
names back to the original acquisition channel names, for traceability only - not meant to be read by
generated scripts). Re-run preprocess_cellsurvey.py only if the source zarr changes.

NOTE: `docker_image` below reuses the cbias-analysis:latest image (see cbias_config.py's own note on
why trello_config.py/idr0028_config.py do the same) - the realised scripts here only ever touch the
flat CSV (all zarr/network-path handling already happened in preprocess_cellsurvey.py, outside
Docker), and this domain's AVAILABLE_LIBRARIES is a subset of what that image already has pinned
(numpy/pandas/matplotlib/scipy/scikit-learn - no NLTK/text-processing or image-processing libraries
are needed). No data-sensitivity reason to keep worker/compiler off DeepSeek: this sample carries no
patient/subject identifiers and was confirmed to need no special privacy/ethics handling.
"""

from pathlib import Path

import pandas as pd

from config import PipelineConfig

AVAILABLE_LIBRARIES = """
Available libraries for imports. VERSIONS ARE PINNED in the Docker image (same pinned image
cbias_config.py uses) - target these APIs specifically, not a version-agnostic "current" API:
- Standard library: os, sys, re, csv, json, pathlib, collections
- NumPy 2.5.2: for numerical computing
- Pandas 3.0.5: for data manipulation and analysis. DataFrame.applymap was REMOVED in pandas 3.0 -
  use DataFrame.map instead. Text columns read from CSV get pandas' native `str` dtype, DISTINCT from
  the legacy `object` dtype - pd.api.types.is_object_dtype() returns False for them; use
  pd.api.types.is_string_dtype() to detect text columns.
- Matplotlib 3.11.1: for plotting and visualization. boxplot()'s `labels=` keyword was renamed to
  `tick_labels` in matplotlib 3.9 - use `tick_labels=`. 362,736 points is too many to scatter-plot
  individually without overplotting/slow rendering - use alpha blending, hexbin/2D-histogram, or an
  explicit random subsample for any per-cell spatial scatter plot, and say in the plot which was used.
- SciPy 1.18.0: scipy.spatial.Delaunay / scipy.spatial.cKDTree for building an alternative spatial
  graph (the shipped `community` column used a hard distance-cutoff Delaunay graph - see DOMAIN_NOTES);
  scipy.stats for comparing marker-intensity or area distributions between groups.
- scikit-learn 1.9.0: sklearn.cluster (KMeans/AgglomerativeClustering/DBSCAN/GaussianMixture) for an
  alternative cell-grouping to compare against the shipped `kmeans_cluster`; sklearn.preprocessing
  (StandardScaler/RobustScaler, or a manual per-marker z-score/log1p) for standardising raw marker
  intensities BEFORE fitting a positivity threshold on them, not only before a distance-based method -
  see DOMAIN_NOTES on why raw per-channel intensities are not comparable or threshold-ready as stored.
No image-processing library (scikit-image, bioio, etc.) is available or needed - no raw microscopy
image or cell-boundary polygon is present in this data, see DOMAIN_NOTES below.
"""

# Canonical/typical biological role of each real marker in this panel, for background context only -
# NOT a claim that this specific panel/antibody was validated against these exact roles. Ideation
# should treat this as a starting glossary to reason from, and inspect the actual per-cell values
# before asserting a cell "is" a given type from one marker alone.
_MARKER_GLOSSARY = """
  marker_DAPI       - nuclear DNA counterstain. Present/high in EVERY cell by construction (it's how
                      nuclei were segmented) - NOT a cell-type marker; do not treat "DAPI-positive" as
                      a finding.
  marker_CD45       - pan-leukocyte (all immune cells).
  marker_CD45RA     - naive/some memory leukocyte subsets (a CD45 isoform).
  marker_CD3        - T cells (pan-T).
  marker_CD4        - helper T cells (also some myeloid cells at lower level).
  marker_CD8        - cytotoxic T cells.
  marker_FoxP3      - regulatory T cells (Tregs) - transcription factor, nuclear signal expected.
  marker_CD20       - B cells.
  marker_CD68       - macrophages.
  marker_CD11c      - dendritic cells / myeloid cells.
  marker_LY75       - dendritic cells (DEC-205).
  marker_HLADR      - antigen presentation - myeloid cells and activated/antigen-presenting cells.
  marker_CD56       - NK cells (also some neuroendocrine cells).
  marker_PD_1       - immune checkpoint receptor, exhausted/activated T cells.
  marker_PD_L1      - immune checkpoint ligand, expressed by both tumour and immune cells.
  marker_CD31       - vascular endothelium.
  marker_E_cadherin - epithelial cell-cell adhesion.
  marker_Vimentin   - mesenchymal/stromal cells (classically the epithelial/mesenchymal counterpoint
                      to E-cadherin).
  marker_Collagen_I - stromal/fibrous connective tissue matrix.
  marker_Collagen_IV- basement membrane matrix.
  marker_LamininA5  - basement membrane matrix.
  marker_Fibronectin- extracellular matrix, wound/remodelling contexts.
  marker_BCAM       - cell adhesion (Lutheran antigen); epithelial/endothelial contexts.
  marker_SMA        - (alpha-smooth-muscle actin - the leading alpha was stripped by preprocessing's
                      sanitiser, see marker_channel_names.csv) smooth muscle / myofibroblasts /
                      pericytes.
  marker_S100       - context-dependent (melanocytes, Schwann/nerve, some dendritic cells).
  marker_Ki_67      - proliferation (cycling cells).
  marker_p16        - senescence / cell-cycle arrest marker.
  marker_H2AX       - (gamma-H2AX) DNA damage response marker.
  marker_TP73       - p53-family transcription factor, differentiation/tumour-suppressor contexts.
  marker_TP63       - p53-family transcription factor, classically squamous/basal epithelial
                      differentiation.
NOT real biological markers - secondary-only/background acquisition channels with no primary antibody,
kept in the data for completeness but should NOT be treated as a cell-biology signal:
  marker_TRITC_1_TRITC, marker_Cy5_1_Cy5
"""

DOMAIN_NOTES = f"""
This is a PROCESSED, already-extracted derivative of one CellSurvey pipeline run (see this module's
docstring for the full provenance and the critical framing on `kmeans_cluster`/`community`). ONE file
lives directly under the data directory (INPUT_FOLDER):

- cells.csv - one row per segmented NUCLEUS (362,736 rows; called "cell" throughout below because
  that is the source pipeline's own terminology - see the SEGMENTATION REGION note right after this
  column list for what that actually means and why it matters), no plate/sample split (this is a
  single tissue sample, unlike idr0028's multi-plate data - there is nothing to concatenate or join
  across files here). Columns:
    cell_id              - unique identifier string for the segmented nucleus (not a bare integer -
                           do not assume it parses as one).
    area                 - segmented nucleus area. UNIT IS NOT DOCUMENTED in the source data (likely
                           pixels^2 at the image's native resolution, but this was not confirmed
                           against a pixel-size calibration) - treat as a relative/comparative
                           measure across cells in this one sample, not an absolute physical area,
                           unless you independently verify a pixel size.
    kmeans_cluster        - integer 0-9, the shipped clustering (see this module's docstring - k=10
                           was a pipeline default, not a validated choice). Highly imbalanced: cluster
                           sizes range from ~400 to ~113,000 cells - inspect the actual sizes before
                           assuming roughly-equal clusters.
    kmeans_cluster_label  - "Cluster_<N>", a purely cosmetic re-labelling of kmeans_cluster with no
                           extra information - do not treat this as a separate variable.
    community             - integer id, the shipped Louvain spatial-community partition (49 distinct
                           values in this sample) - see this module's docstring on how it was built
                           (Delaunay graph, max edge distance 1000, Louvain resolution 0.1) and why it
                           should be interrogated, not assumed correct. Sizes are strongly bimodal:
                           roughly 20 communities in the thousands of cells, and the rest (~15+)
                           singletons or near-singletons (1-4 cells) - very likely graph-construction
                           artefacts (cells isolated by the hard distance cutoff) rather than real
                           spatial niches; inspect this distribution directly rather than assuming
                           every community id represents a meaningful niche of comparable scale.
    x, y                  - per-cell centroid coordinates, in the same undocumented unit as area
                           (see above) - fine for relative/within-sample spatial analysis (distances,
                           neighbourhoods, clustering), do not present a raw coordinate difference as
                           a physical distance in a stated unit (e.g. microns) without independent
                           verification.
    marker_* (32 columns) - per-nucleus MEAN INTENSITY for each acquisition channel, stored RAW - no
                           per-channel background subtraction, exposure/gain correction, or
                           normalisation of any kind has been applied (the source pipeline's own
                           documentation does not describe any such step, and this project's
                           extraction adds none). Different channels were acquired with different
                           exposure/gain settings - visible directly in the original acquisition
                           channel names (see marker_channel_names.csv, e.g. "..._6000-..." vs
                           "..._100-...") - so raw intensities are NOT on a comparable scale across
                           markers. ANY script that fits a positivity threshold (GMM, Otsu, a
                           percentile/valley cutoff) directly on a raw per-marker intensity histogram
                           is fitting a cutpoint that partly reflects acquisition settings, not purely
                           biology - normalise each marker first (see AVAILABLE_LIBRARIES'
                           sklearn.preprocessing note) before treating a fitted cutpoint as a
                           biological positivity call, and state explicitly in the script whether this
                           was done. See the marker glossary below for each marker's typical
                           biological role, and note the two channels that are NOT real markers.

SEGMENTATION REGION - READ BEFORE TREATING ANY MARKER AS "POSITIVE" OR "NEGATIVE": every object in
this table is a Stardist NUCLEAR segmentation (see this module's docstring) - there is no whole-cell
or membrane boundary anywhere in this pipeline's output, only a nuclear one. Whether marker intensity
was measured strictly within that nuclear polygon, or within some expanded/dilated region
approximating a whole cell, is NOT documented by the source pipeline (checked directly - its own
README does not say) and was not independently verified here - inspect this yourself (e.g. compare
`area` against a plausible nuclear-vs-whole-cell size for this tissue) before assuming either way.
This matters most for markers with a non-nuclear expected localisation - which is MOST of this panel:
CD3, CD8, CD31, Collagen-I, Vimentin, E-cadherin, and most other lineage/structural markers are
membrane, cytoplasmic, or extracellular, not nuclear. A "positive"/"negative" call for these measures
signal in or immediately around the nucleus, not across the whole cell body, and may under- or
over-represent true expression depending on how much of that marker's real signal actually falls
within the measured region. Only marker_DAPI and (as a transcription factor) marker_FoxP3 have a
genuinely nuclear expected localisation - treat every other marker's absolute intensity, and any
threshold fitted to it, with this in mind.

{_MARKER_GLOSSARY}

WHAT IS NOT AVAILABLE, so as not to be assumed: no raw microscopy image is present locally (only the
per-nucleus mean-intensity table survived extraction) - no pixel-level texture/morphology feature
beyond `area` is computable. No WHOLE-CELL boundary polygon/shape exists anywhere in this pipeline's
output, not just in this extraction - only a Stardist NUCLEAR boundary was ever computed (see
SEGMENTATION REGION above), and even that nuclear polygon was not extracted into this table (only its
centroid + area survived - reading shapes/stardist_boundaries needs `pyarrow`, not in this project's
pixi env; see preprocess_cellsurvey.py's docstring). A hypothesis needing true WHOLE-CELL shape
(elongation, boundary curvature, aspect ratio) is not answerable from this data, or from this
pipeline's output at all, in principle - a hypothesis about NUCLEAR shape specifically could in
principle be answered by re-extracting shapes/stardist_boundaries, which this project currently does
not do. No raw Delaunay edge list is present - only the resulting `community` label survived
extraction, so a script wanting to inspect or rebuild the spatial graph must construct its own (e.g.
via scipy.spatial.Delaunay or cKDTree on the x/y columns) rather than assume edges are available
directly. There is only ONE sample/slide in this data - no cross-sample or cross-panel comparison is
possible, and no patient/clinical metadata of any kind is present (nor was any collected for this
sample).
"""


def extract_input_metadata(directory: str) -> str:
    """Summarize cells.csv for ideation/the orchestrator. Reads only the small, non-marker columns
    (usecols) to avoid pulling all 32 marker float columns into memory just for this summary -
    generate_data_profile below is where the full per-column profile lives."""
    base = Path(directory)
    cells_path = base / "cells.csv"
    if not cells_path.exists():
        return f"cells.csv not found under {directory} - has preprocess_cellsurvey.py been run?"

    cols = pd.read_csv(
        cells_path,
        usecols=["kmeans_cluster", "kmeans_cluster_label", "community", "area", "x", "y"],
    )

    cluster_sizes = cols["kmeans_cluster"].value_counts().sort_index()
    community_sizes = cols["community"].value_counts()
    small_communities = int((community_sizes <= 5).sum())

    marker_map_path = base / "marker_channel_names.csv"
    marker_columns = []
    if marker_map_path.exists():
        marker_columns = pd.read_csv(marker_map_path)["sanitized_column"].tolist()

    return str({
        "cells_csv": {
            "total_cells": len(cols),
            "n_marker_columns": len(marker_columns),
            "marker_columns": marker_columns,
            "kmeans_cluster_sizes": {str(k): int(v) for k, v in cluster_sizes.items()},
            "n_communities": int(cols["community"].nunique()),
            "communities_with_5_or_fewer_cells": small_communities,
            "community_size_range": [int(community_sizes.min()), int(community_sizes.max())],
            "area_range": [float(cols["area"].min()), float(cols["area"].max())],
            "x_range": [float(cols["x"].min()), float(cols["x"].max())],
            "y_range": [float(cols["y"].min()), float(cols["y"].max())],
        },
    })


# Live Issue 31 pattern, ported from cbias_config.py/idr0028_config.py: distinguish genuinely
# categorical columns from continuous measurements before deciding whether to enumerate values.
_PROFILE_CARDINALITY_CUTOFF = 25


def _profile_dataframe(df: pd.DataFrame, label: str) -> str:
    lines = [f"  {label} ({len(df)} rows):"]
    for col in df.columns:
        series = df[col]
        nulls = int(series.isna().sum())
        nunique = int(series.nunique(dropna=True))
        if nunique <= _PROFILE_CARDINALITY_CUTOFF:
            values = sorted(str(v) for v in series.dropna().unique())
            lines.append(f"    {col!r} [{series.dtype}, {nulls} null]: {values}")
        else:
            lines.append(f"    {col!r} [{series.dtype}, {nulls} null]: "
                         f"{nunique} distinct values, not enumerated (over the cutoff)")
    return "\n".join(lines)


def generate_data_profile(directory: str) -> str:
    """MECHANICAL per-run profile (Live Issue 31 pattern) of the actual processed data - no LLM
    involved, so it cannot hallucinate a value or go stale. Reads cells.csv in full (a few seconds,
    done once per run on the host, not inside the memory-capped Docker sandbox) so cluster/community
    cardinality and null counts are exact, not sampled."""
    base = Path(directory)
    cells_path = base / "cells.csv"
    if not cells_path.exists():
        return "(no data profile available)"
    return _profile_dataframe(pd.read_csv(cells_path), "cells.csv")


CONFIG = PipelineConfig(
    orchestrator_model="claude-opus-4-8",
    # worker/compiler: DeepSeek, matching cbias_config.py/idr0028_config.py's routing for these two
    # mechanical/high-volume, Docker-oracle-protected roles - no data-sensitivity carve-out applies
    # here (confirmed: no patient/subject privacy or ethics constraint on this sample).
    worker_model="deepseek-v4-pro",
    compiler_model="deepseek-v4-pro",
    requirements_evaluator_model="claude-sonnet-5",
    angle_model="deepseek-v4-pro",
    # D5 judging: frontier Anthropic tier, same reasoning as cbias_config.py/idr0028_config.py -
    # judge_insight/judge_soundness are the entire quality bar once req_score is gone (docs/
    # DEVELOPMENT_LOG.md Section 5).
    judge_model="claude-opus-4-8",
    # Reuses the pinned cbias-analysis image - see this module's docstring for why.
    docker_image="cbias-analysis:latest",
    available_libraries=AVAILABLE_LIBRARIES,
    domain_notes=DOMAIN_NOTES,
    extract_input_metadata=extract_input_metadata,
    data_profile=generate_data_profile,
)
