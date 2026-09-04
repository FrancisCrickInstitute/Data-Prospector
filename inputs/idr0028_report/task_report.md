# GEF/GAP siRNA Screen Analysis (IDR0028) - Exploratory Task

## Objective

Analyse a processed high-content siRNA screen: 170 Rho-family GEF/GAP genes individually knocked down
in the LM2 metastatic breast cancer cell line, with YAP/TAZ nuclear-vs-cytoplasmic localisation as the
readout. GEF/GAP genes regulate Rho-GTPase activity and therefore actomyosin/cytoskeletal tension,
which controls YAP/TAZ nuclear localisation through a mechanotransduction route that acts independently
of the canonical Hippo/LATS kinase cascade - a gene that shifts YAP/TAZ localisation on knockdown here
is a candidate node in that route. The aim is to surface non-obvious, defensible leads about which
genes matter and how - not to re-derive the screen's own already-published hit calls (see "Already
Explored" below) - that would be informative to cell biologists studying Hippo pathway/mechanotransduction
signalling, and to whoever runs quality control on this kind of plate-based screen.

## Input

Two files in the data directory (INPUT_FOLDER):

- `wells.csv` - one row per well, across four plate directories (1536 rows total: a full annotated
  384-well layout x 4 plates). Carries well identity (PlateDir, Well), gene/reagent/control identity
  (Gene_Symbol, siRNA_Pool_Identifier, Control_Type, Quality_Control), the original study's own
  published Z-score/phenotype hit calls (`Published_*` columns), and mechanically-aggregated per-well
  statistics (Cell_Count, Mean/Median/Std_NC_Ratio, Mean_Nuclear_YAPTAZ, Mean_Cytoplasm_YAPTAZ).
- `<plate_dir>_cells.csv` - one row per segmented cell, one file per plate directory (up to ~540k rows
  each). Carries per-cell YAP/TAZ intensity in each of three compartments (nucleus/cell/cytoplasm), the
  derived nuclear:cytoplasmic ratio (NC_Ratio), within-image spatial coordinates, and the same
  gene/control/QC identity columns as wells.csv.

Four plate directories are FOUR DISTINCT PHYSICAL PLATES, not one plate imaged four times: "1A"/"1B"
are sister replicates sharing one gene layout, "2A"/"2B" sister replicates of a different gene layout.
Every gene sits at two well positions on its plate-set, each replicated on both sister plates - four
measured wells per gene in total. Control wells (negative/positive/technical/empty) appear on all four
plates at shared layout positions. See the domain config's DOMAIN_NOTES for full column-level detail,
what is and isn't available (notably: no raw microscopy image, and only YAP/TAZ - not actin/tubulin -
was quantified per cell), and known data quirks (e.g. a "Fail" QC well is not always cell-empty).

## Guiding Questions for Analysis

1. **Gene-level hits**: Which GEF/GAP genes show a robust, replicate-concordant shift in nuclear:cytoplasmic
   YAP/TAZ ratio on knockdown - beyond what the study's own published Z-scores/phenotype calls already say?
2. **Replicate reliability**: How concordant is a gene's phenotype across its two within-plate well
   positions, and across its two sister plates? Does discordance itself carry information (e.g. about
   siRNA off-target effects, or which "hits" are actually borderline)?
3. **Population heterogeneity**: Within a well, is the cell-to-cell YAP/TAZ response unimodal or
   bimodal/heterogeneous? Does a gene that shifts the WHOLE population differ qualitatively from one
   where only a SUBPOPULATION of cells responds? (The published Z-scores are well-level means - they
   cannot distinguish these two cases.)
4. **Functional-class patterns**: GEFs activate Rho-GTPases; GAPs inactivate them - opposite biochemical
   roles. Do GEF-family and GAP-family gene knockdowns show systematically different (e.g. opposite-signed)
   NC_Ratio shifts, consistent with that opposition? (Gene family can be inferred from the gene symbol
   prefix, e.g. ARHGEF*/ARHGAP*/ARAP*/etc. - state and justify whatever classification rule is used.)
5. **Plate-position / technical artifacts**: Does well position (edge vs. interior, specific
   rows/columns) or QC-fail status show spatial clustering across the 384-well layout, suggestive of an
   imaging/technical artifact rather than a biological effect?
6. **Control-well baseline drift**: How consistent are negative-control wells' NC_Ratio across the four
   plates? Is there plate-to-plate systematic drift that a gene-level hit call ought to be normalised
   against, rather than comparing raw values across plates directly?

## Analysis Requirements

### 1. Suggest Key Metrics

Analyse the input data and suggest **key metrics** that help answer the guiding questions above. Choose
metrics that are:

- Computable from the available data (see the domain config's DOMAIN_NOTES for exactly what columns
  exist and what is NOT available - e.g. no actin/tubulin intensity per cell)
- Relevant to at least one of the guiding questions
- More insightful than a raw mean or count

### Already Explored - Do Not Repeat

The screen's own analysis is already carried through into `wells.csv` as the `Published_*` columns:

- Per-well Z-scores across five morphology classes: Spindly, Large/spread, Triangular, Fan, Round/small
- Per-well Z-scores across four YAP/TAZ intensity/localisation classes: High nuclear, Low nuclear, High
  total, Low total
- A binary `Published_Has_Phenotype` flag, populated for 480 of the 1536 wells

Proposed metrics must be materially different in kind - not a refinement, re-implementation, or
alternative-library recomputation of anything above. In particular: "which genes have an extreme
`Published_Zscore_*` value" and "which genes have `Published_Has_Phenotype == 'yes'`" are NOT new
findings - they are already in the data verbatim. Favour axes the published columns do not appear to
score at all: replicate concordance/discordance, within-well distributional shape (not just the mean),
GEF-vs-GAP subfamily-level directional patterns, plate-position/edge effects, QC-fail structure, or
cross-plate control-well drift.

### 2. Create Visualisations (PNG files)

Create visualisations that illustrate the metrics chosen in section 1. Pick visualisations that help
answer the guiding questions and would be easily interpretable by a cell biologist skimming the result,
not just by someone who already knows this dataset's internal column names.

### 3. Identify Data Gaps

After analysis, make specific suggestions for additional data/fields that would improve future analysis:

- Focus on what data would help answer the guiding questions more clearly
- Format: bulleted list with a brief explanation of why each would be useful

## Output Requirements

The analysis should be independently implementable and:
- Load and parse `wells.csv` and however many `*_cells.csv` files are present in the data directory
  (auto-detect - do not assume exactly four, or their exact filenames)
- Compute metrics suggested in section 1
- Generate the visualisations suggested in section 2
- Save visualisations to the current working directory
- Handle missing data gracefully - `Gene_Symbol`/`Control_Type` are NaN (not empty string) for the
  wells that don't have them; a QC-"Fail" well may still have a populated `Cell_Count`

## Success Criteria

✅ Suggested metrics are genuinely novel (not a `Published_*` column restated) and would help prioritise
   which genes to follow up experimentally
✅ Script runs without errors on the provided input data
✅ Visualisations are properly labelled (titles, axis labels, legends)
✅ Code is clean and minimal (no unnecessary utilities or visualisations)
