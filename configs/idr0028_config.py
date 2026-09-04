"""IDR0028 GEF/GAP siRNA screen domain configuration for the pipeline.

An LM2 (metastatic breast cancer, derived from MDA-MB-231) high-content siRNA screen: 170 Rho-family
GEF/GAP genes knocked down individually (Dharmacon ON-TARGETplus pools), cells fixed and stained for
YAP/TAZ, alpha-tubulin, F-actin and DNA, imaged, and segmented in CellProfiler. The biological
question the screen was built to answer: which GEF/GAP genes - regulators of Rho-GTPase activity, and
therefore of actomyosin/cytoskeletal tension - shift YAP/TAZ between the nucleus and cytoplasm when
knocked down. This matters because YAP/TAZ nuclear localisation is controlled by cytoskeletal tension
via a mechanotransduction route that acts independently of the canonical Hippo/LATS kinase cascade;
a GEF/GAP hit here is a candidate node in that route.

The raw data (inputs/idr0028/) is genuinely messy - see preprocess_idr0028.py's module docstring for
the full account - CellProfiler's own well/plate/site metadata columns are empty in every row (a
regex mismatch against the actual filenames), so well identity had to be recovered from a separate
PerkinElmer Columbus acquisition index, and gene/siRNA/control identity from a third file, the IDR's
own published screen annotation. preprocess_idr0028.py (run ONCE, already done - see its docstring)
joins all three into the two clean files this config's `extract_input_metadata`/`data_profile` below
actually read: inputs/idr0028_processed/wells.csv and inputs/idr0028_processed/<plate>_cells.csv.
Re-run it (`pixi run python preprocess_idr0028.py`) only if the raw inputs/idr0028/ data changes.

NOTE: `docker_image` below reuses the cbias-analysis:latest image (see cbias_config.py's own note on
why trello_config.py does the same) - this domain's AVAILABLE_LIBRARIES is a subset of what that
image already has pinned (numpy/pandas/matplotlib/scipy/scikit-learn), no NLTK/text-processing or
image-processing libraries are needed since no raw microscopy images are available locally (see
DOMAIN_NOTES below), and there is no data-sensitivity reason (this is public IDR data) to keep
worker/compiler off DeepSeek.
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
  `tick_labels` in matplotlib 3.9 - use `tick_labels=`.
- SciPy 1.18.0: for statistical tests (e.g. comparing NC_Ratio distributions between conditions)
- scikit-learn 1.9.0: for clustering/dimensionality reduction if a script wants to group genes by
  phenotype profile across the multiple measured/published metrics
No image-processing library (scikit-image, bioio, etc.) is available or needed - see DOMAIN_NOTES
below on why no raw microscopy images are present in this data.
"""

DOMAIN_NOTES = """
This is a PROCESSED, already-joined derivative of a CellProfiler high-content screen - NOT the raw
per-plate CellProfiler export. Two files live directly under the data directory (INPUT_FOLDER):

- wells.csv - one row per well, ACROSS ALL FOUR plate directories (1536 rows: the full annotated
  384-well layout x 4 plates, INCLUDING wells with zero imaged cells - e.g. a technical-control well
  the annotation itself records as unimaged due to a microscope error). Columns:
    PlateDir            - which of the four raw plate directories this well came from (see plate
                           structure below); acts as the plate identifier alongside Well.
    Well                - plate coordinate, e.g. "A2" (16 rows A-P x 24 columns 1-24, 384-well format).
    Gene_Symbol          - NaN for control/empty wells, else the knocked-down gene (170 distinct
                           genes total, each present on exactly one plate-SET - see below). Filter
                           with .notna(), not truthiness or `!= ""` - empty CSV fields load as NaN,
                           not empty string.
    siRNA_Pool_Identifier - Dharmacon catalog ID for the siRNA pool used (only populated alongside
                           Gene_Symbol).
    Control_Type        - NaN for gene-targeting wells, else one of: "negative control" (mock
                           transfection), "positive control", "technical control" (a cell-dilution
                           curve checking whether YAP/TAZ localisation depends on confluency, NOT a
                           gene perturbation), "empty well".
    Quality_Control      - "Pass" or "Fail" (normalised casing during preprocessing). Fail does NOT
                           always mean zero cells were imaged - some Fail wells still have a populated
                           Cell_Count; the ORIGINAL failure reason (e.g. "microscope error") is not
                           carried into this file, only the Pass/Fail flag itself.
    Published_Has_Phenotype, Published_Zscore_* (9 columns: Spindly, Large_Spread, Triangular, Fan,
                           Round_Small, High/Low_Nuclear_YAPTAZ, High/Low_Total_YAPTAZ) - THE ORIGINAL
                           STUDY'S OWN PUBLISHED HIT-CALLS, carried through for reference only. THESE
                           ARE ANTI-TARGETS: an angle that re-derives "which genes have an extreme
                           Z-score" or "which genes have Published_Has_Phenotype=yes" is re-finding
                           results the study already published, not proposing something non-obvious.
                           Populated only for the 480 wells with Published_Has_Phenotype="yes" - NaN
                           elsewhere (not zero - a NaN Z-score is "not scored", not "scored as zero").
    Cell_Count, Mean/Median/Std_NC_Ratio, Mean_Nuclear_YAPTAZ, Mean_Cytoplasm_YAPTAZ - MECHANICALLY
                           aggregated (this run's own computation, not the study's) from the per-cell
                           files below. All NaN for a well with zero imaged cells.

- <plate_dir>_cells.csv - one row per SEGMENTED CELL, one file PER plate directory (up to ~540k rows
  each - four separate files, not one combined file, so a script analysing one plate's worth of cells
  stays well inside the sandbox's memory cap; a cross-plate script reads and concatenates all four
  itself, tagging each with its own PlateDir since the per-cell files don't carry that column).
  Columns: ImageNumber, ObjectNumber (this cell's own id within its image - NOT globally unique
  without ImageNumber), Well, Gene_Symbol, Control_Type, Quality_Control, siRNA_Pool_Identifier (same
  meaning as in wells.csv), Nuclear_YAPTAZ_Mean, Cytoplasm_YAPTAZ_Mean, Cell_YAPTAZ_Mean (mean YAP/TAZ
  intensity in each of the three CellProfiler compartments for this one cell), NC_Ratio (=
  Nuclear_YAPTAZ_Mean / Cytoplasm_YAPTAZ_Mean; NaN, not inf, where the cytoplasmic mean was ~zero -
  a segmentation edge case, not a genuine extreme ratio), Nucleus_X/Nucleus_Y (pixel coordinates
  within that cell's own image - useful for within-image spatial questions, NOT for plate-position
  questions; plate position is Well, from wells.csv).

PLATE / REPLICATE STRUCTURE - four plate directories, LM2_GEFGAP_ONTARGETPlus_{1A,1B,2A,2B}, are FOUR
DISTINCT PHYSICAL PLATE BARCODES, not the same plate imaged four times. "1A"/"1B" are sister replicate
plates carrying an IDENTICAL gene layout ("plate-set 1"); "2A"/"2B" are sister replicates of a
DIFFERENT gene layout ("plate-set 2"). Each of the 170 genes lives on exactly one plate-set (never
both), at TWO well positions on that plate-set (e.g. ARHGAP1 sits at both I9 and M21 on plate-set 2),
each of those two positions replicated on both sister plates - so every gene has exactly 4 measured
wells total (2 positions x 2 sister plates), and a gene's replicate structure spans two files
(*_1A_cells.csv paired with *_1B_cells.csv, OR *_2A_cells.csv paired with *_2B_cells.csv - never a mix
of set 1 and set 2 files). Control wells (negative/positive/technical/empty) appear on ALL FOUR
plates at similar layout positions, since the plate LAYOUT (which wells hold controls vs which are
available for gene reagents) is shared across both plate-sets even though the genes filling the
gene-well positions differ between sets.

WHAT IS NOT AVAILABLE, so as not to be assumed: no raw microscopy image (TIFF) is present locally -
only the CellProfiler per-object measurements survived into this processed data, so no image-based
texture/morphology feature is computable, only what these two CSVs already contain. Critically, ONLY
THE YAPTAZ CHANNEL WAS QUANTIFIED PER OBJECT in the original CellProfiler run - alpha-tubulin, F-actin
and Hoechst/DNA were imaged (they're literally why this is a GEF/GAP-relevant screen, since GEFs/GAPs
act via the actin cytoskeleton) but were never measured per-cell, so a hypothesis like "does actin
intensity/organisation correlate with NC_Ratio" is NOT answerable from this data - there is no actin
intensity column anywhere in these files. Also unavailable: the original QC failure reason (only the
Pass/Fail flag survived preprocessing), and cell-level morphology (area/shape) - CellProfiler measured
only intensity/location for these objects, not size or shape features.
"""


def extract_input_metadata(directory: str) -> str:
    """Summarize wells.csv and the per-plate cell files for ideation/the orchestrator."""
    base = Path(directory)
    wells_path = base / "wells.csv"
    if not wells_path.exists():
        return f"wells.csv not found under {directory} - has preprocess_idr0028.py been run?"

    wells = pd.read_csv(wells_path)
    gene_wells = wells[wells["Gene_Symbol"].notna()]
    control_counts = wells["Control_Type"].value_counts(dropna=True)

    cell_files = []
    for f in sorted(base.glob("*_cells.csv")):
        # Row count only (not a full read) - these files run tens of MB each; a full profile of
        # their contents is generate_data_profile's job below, not this summary's.
        with open(f, encoding="utf-8") as fh:
            n_rows = sum(1 for _ in fh) - 1
        cell_files.append({"file": f.name, "cells": n_rows})

    return str({
        "wells_csv": {
            "total_wells": len(wells),
            "plates": sorted(wells["PlateDir"].unique()),
            "distinct_genes": int(gene_wells["Gene_Symbol"].nunique()),
            "gene_targeting_wells": len(gene_wells),
            "control_type_counts": {str(k): int(v) for k, v in control_counts.items()},
            "quality_control_counts": {str(k): int(v) for k, v in wells["Quality_Control"].value_counts(dropna=False).items()},
            "wells_with_published_phenotype": int((wells["Published_Has_Phenotype"] == "yes").sum()),
        },
        "per_plate_cell_files": cell_files,
    })


# Live Issue 31 pattern, ported from cbias_config.py/trello_config.py: distinguish genuinely
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
    involved, so it cannot hallucinate a value or go stale. wells.csv gets a full per-column profile
    (it's small - 1536 rows); the per-plate cell files get row/column/dtype/null-count only, NOT a
    full value-set enumeration - NC_Ratio and the intensity columns are continuous measurements with
    hundreds of thousands of distinct values each, so the cutoff above would already skip them, and
    reading all four ~50-80MB files in full on every run for that would be a large token/time cost
    for a profile that comes back near-identical to wells.csv's dtype/null picture anyway."""
    base = Path(directory)
    sections = []

    wells_path = base / "wells.csv"
    if wells_path.exists():
        sections.append(_profile_dataframe(pd.read_csv(wells_path), "wells.csv"))

    cell_lines = []
    for f in sorted(base.glob("*_cells.csv")):
        # nrows=5 for dtype inference only - see the module-level note above on why a full read of
        # these files isn't worth it for this profile.
        sample = pd.read_csv(f, nrows=5)
        with open(f, encoding="utf-8") as fh:
            n_rows = sum(1 for _ in fh) - 1
        nulls_in_sample = {c: int(sample[c].isna().sum()) for c in sample.columns}
        cell_lines.append(
            f"  {f.name} ({n_rows} rows): columns {list(sample.columns)}, "
            f"dtypes from a 5-row sample {dict(sample.dtypes.astype(str))} "
            f"(sample-row null counts {nulls_in_sample} - not representative of the full file, "
            f"since NC_Ratio/intensity nulls are data-dependent, not structural)"
        )
    if cell_lines:
        sections.append("per-plate cell files (row/column/dtype only, not a value profile - "
                         "see wells.csv profile above for the categorical columns these files "
                         "share):\n" + "\n".join(cell_lines))

    return "\n\n".join(sections) if sections else "(no data profile available)"


CONFIG = PipelineConfig(
    orchestrator_model="claude-opus-4-8",
    # worker/compiler: DeepSeek, matching cbias_config.py's routing for these two mechanical/
    # high-volume, Docker-oracle-protected roles - no data-sensitivity carve-out applies here since
    # this is public IDR screen data, not the anonymisation-gated case cbias_config.py documents.
    worker_model="deepseek-v4-pro",
    compiler_model="deepseek-v4-pro",
    requirements_evaluator_model="claude-sonnet-5",
    angle_model="deepseek-v4-pro",
    # D5 judging: frontier Anthropic tier, same reasoning as cbias_config.py - judge_insight/
    # judge_soundness are the entire quality bar once req_score is gone (docs/DEVELOPMENT_LOG.md §5).
    judge_model="claude-opus-4-8",
    # Reuses the pinned cbias-analysis image - see this module's docstring for why (a subset of
    # that image's libraries, no data-sensitivity reason to keep worker/compiler off DeepSeek).
    docker_image="cbias-analysis:latest",
    available_libraries=AVAILABLE_LIBRARIES,
    domain_notes=DOMAIN_NOTES,
    extract_input_metadata=extract_input_metadata,
    data_profile=generate_data_profile,
)
