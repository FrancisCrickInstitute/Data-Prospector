# Spatial Tissue Phenotyping Analysis (CellSurvey Output) - Exploratory Task

## Objective

Analyse one 32-plex multiplexed immunofluorescence tissue sample (362,736 segmented cells) produced by
the CellSurvey spatial-omics pipeline. Each cell carries a mean intensity for 30 named immune/structural/
functional markers (plus 2 non-biological background channels - see the domain config's DOMAIN_NOTES),
a spatial centroid, and two pipeline-derived groupings: a fixed-k KMeans expression cluster and a
Louvain spatial-community label. The aim is to surface non-obvious, defensible leads about the tissue's
cellular composition and spatial organisation that would be informative to whoever is deciding how to
interpret or refine this pipeline's output - not to simply restate the two groupings it already shipped
with (see "About the Shipped Groupings" below).

## Input

One file in the data directory (INPUT_FOLDER):

- `cells.csv` - one row per segmented cell (362,736 rows). Carries cell identity (`cell_id`), a
  segmentation-derived `area`, spatial centroid (`x`, `y`), the pipeline's own `kmeans_cluster`(+label)
  and `community` assignments, and one `marker_*` column per acquisition channel (32 total - 30 real
  immunophenotyping markers plus 2 non-biological background channels). See the domain config's
  DOMAIN_NOTES for the full column reference, the marker glossary (each marker's typical biological
  role - immune lineage, structural/stromal, vascular, proliferation, senescence, DNA damage), and what
  is and is not available (no raw image, no cell-boundary polygon, no raw spatial-graph edge list, only
  one sample - no cross-sample comparison is possible).

## About the Shipped Groupings - Context for Questions 1-3 and 7

`kmeans_cluster` and `community` are NOT validated ground truth about this tissue's biology - they are
one arbitrary parameterisation the pipeline happened to run with (KMeans at a fixed k=10, not chosen
against any biological criterion; a Louvain spatial-community partition built on a Delaunay graph with a
hard 1000-unit edge-distance cutoff and resolution=0.1, also pipeline defaults, not tuned or validated).
This is important background for guiding questions 1-3 (and question 7's constructive follow-up) below -
but it is ONE thread among seven, not an overarching lens for the whole analysis.

Where an angle does engage with `kmeans_cluster`/`community` (mainly questions 1-3 and 7), treat them as
something to INTERROGATE, not build on top of uncritically - "which cluster/community has the highest
mean X" is a weak angle on its own; "does this cluster's marker profile correspond to a coherent, named
cell type" or "is this community's boundary better explained by the tissue's actual structure or by the
graph's distance cutoff" are the kind of question that thread wants. See "Already Explored" below,
though, before proposing another version of questions 1-3 specifically - the basic "does it hold up"
question has already been answered.

Guiding questions 4-6 do NOT need to reference either grouping at all - they ask about niches, marker
co-expression, and named-lineage spatial organisation as questions in their own right, answerable
directly from markers and coordinates. Forcing a `kmeans_cluster`/`community` comparison into an angle
that targets one of these three is not required, and often is not the strongest version of that angle.

## Guiding Questions for Analysis

1. **Cluster biological coherence**: Do cells within a `kmeans_cluster` share a coherent marker profile
   consistent with a real, named cell type (e.g. high CD3+CD8 for cytotoxic T cells, high CD68 for
   macrophages)? Are any clusters clearly mixing multiple cell types, or splitting one type across
   several clusters?
2. **Canonical gating vs. unsupervised clustering**: Using marker-positivity thresholds derived from the
   actual data (not arbitrary cutoffs - justify whatever threshold is chosen), how well does a
   canonical-gating cell-type call agree with `kmeans_cluster`? Where they disagree, which cells does
   that affect and does a pattern explain the disagreement?
3. **Community structure vs. graph artefact**: `community` sizes are strongly bimodal - roughly 20
   communities of real size, and ~15+ singletons/near-singletons. Is that split explained by genuine
   spatial isolation (e.g. cells at the tissue edge, or in a genuinely sparse region), or is it an
   artefact of the pipeline's hard distance cutoff? Would a different graph construction (e.g. k-nearest-
   neighbours) change which cells fall into tiny communities?
4. **Neighbourhood-composition niches**: Independent of `community`, does each cell's LOCAL neighbourhood
   (marker or cluster composition within a radius of its centroid) reveal spatial niches - e.g. an
   immune-infiltrate region, a stromal/vascular region, a tumour-dense region - that are more
   interpretable or more spatially coherent than the shipped `community` labels?
5. **Marker co-expression structure**: Beyond single-marker means per cluster, are there marker PAIRS or
   small combinations whose joint expression pattern (e.g. co-positivity, mutual exclusivity) reveals
   something about cell state or spatial organisation that looking at markers one at a time would miss?
6. **Spatial organisation of specific lineages**: For a specific, named cell population (e.g. CD8+ T
   cells, CD31+ endothelium), does its spatial distribution show clustering, exclusion, or proximity to
   another named population (e.g. immune cells excluded from or enriched near vascular regions) that
   would be biologically meaningful to report?
7. **Improved cell-type/niche definition**: Two independent runs have now each shown that the shipped
   `kmeans_cluster`/`community` groupings don't reliably correspond to real cell types or niches (see
   "Already Explored" below) - the useful next step is not another audit of that finding, but an actual
   ALTERNATIVE. Propose and compute a replacement grouping - e.g. a canonical-gating-based cell-type
   assignment, a marker-informed re-clustering, or a neighbourhood-composition-based niche map - and
   deliver it as the analysis's output, with a concrete comparison (coverage, internal coherence, or
   agreement rate) against the shipped grouping it's meant to improve on. The deliverable here is a
   usable alternative grouping, not a diagnosis of the existing one's flaws.

## Analysis Requirements

### 1. Suggest Key Metrics

Analyse the input data and suggest **key metrics** that help answer the guiding questions above. Choose
metrics that are:

- Computable from the available data (see the domain config's DOMAIN_NOTES for exactly what columns
  exist and what is NOT available - e.g. no raw image, no cell-boundary shape, no raw graph edges)
- Grounded in the marker glossary's biological meaning where a metric claims a cell type or tissue
  region, not just a bare cluster/community id
- More insightful than restating `kmeans_cluster`/`community` membership counts

### Already Explored - Do Not Repeat

Two independent runs (each using a different method - threshold-sensitivity purity curves, gating-vs-
kmeans agreement audits, within-cluster bimodality testing, and a direct community-graph-artefact test)
have each concluded that the shipped `kmeans_cluster`/`community` groupings do NOT reliably correspond
to coherent, real cell types or genuine spatial niches: some clusters/communities hold up under scrutiny,
most do not, and the disagreement is a mix of threshold-sensitivity and genuine multi-lineage mixing.
**This is now an established finding, not a new one:**

- An angle whose entire contribution is "re-confirming that `kmeans_cluster`/`community` doesn't match
  canonical gating / a real niche, via yet another statistical method" is NOT new - that conclusion has
  already been reached, repeatedly, by several different methods.
- Guiding question 7 is the constructive next step this finding points to: propose and actually deliver
  a better alternative, not another audit of the existing one.
- Guiding questions 1-3 remain legitimate ONLY for a genuinely new angle on this theme - e.g. a specific
  mechanism nobody has tested yet (which marker combinations drive the mixing, whether disagreement
  clusters at particular plate/tissue positions) - not a restatement of "the clustering doesn't hold up"
  under a different statistical method.

### 2. Create Visualisations (PNG files)

Create visualisations that illustrate the metrics chosen in section 1. Pick visualisations that help
answer the guiding questions and would be easily interpretable by a tissue biologist or pathologist
skimming the result, not just by someone who already knows this dataset's internal column names. Given
362,736 cells, any per-cell spatial scatter plot needs alpha blending, a 2D-histogram/hexbin, or an
explicit subsample - say in the plot which was used.

### 3. Identify Data Gaps

After analysis, make specific suggestions for additional data/fields that would improve future analysis:

- Focus on what data would help answer the guiding questions more clearly
- Format: bulleted list with a brief explanation of why each would be useful

## Output Requirements

The analysis should be independently implementable and:
- Load and parse `cells.csv`
- Compute metrics suggested in section 1
- Generate the visualisations suggested in section 2
- Save visualisations to the current working directory
- Handle the dataset's actual scale sensibly (362,736 rows - avoid unnecessary full-dataframe copies;
  see the domain config's AVAILABLE_LIBRARIES note on the sandbox's memory limit)

## Success Criteria

✅ Where an angle engages with `kmeans_cluster`/`community` (typically questions 1-3 and 7), it does so
   critically (1-3) or constructively (7) rather than simply restating that they don't hold up - see
   "Already Explored" above; angles addressing questions 4-6 are judged on their own terms and are not
   required to reference either grouping
✅ Metrics are grounded in the marker glossary's biological meaning where a cell-type or tissue-region
   claim is made
✅ Script runs without errors on the provided input data
✅ Visualisations are properly labelled (titles, axis labels, legends) and handle the cell count sensibly
✅ Code is clean and minimal (no unnecessary utilities or visualisations)
