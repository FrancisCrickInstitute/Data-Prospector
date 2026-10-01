# CellSurvey tissue — a broad overview

One tissue section, **362,793 segmented cells** (whole-cell segmentation), ~32 marker channels.

This is a visual summary, not a single hypothesis test: who is in the tissue (cell
populations), where they are (spatial maps), and how the tissue is organised
(communities).

## How to read this (in plain terms)

**"z-score"** is just a way to put every marker on the same ruler. Raw brightness
numbers can't be compared directly — each marker is photographed at its own settings and
the slide is lit unevenly — so for each marker we centre every cell at "0 = a typical
cell" and count in steps of "1 = one spread of the data". A z-score of +2 means
"noticeably brighter than the typical cell for that marker"; it does **not** mean the
cell is definitively positive — the positive/negative line is a separate judgement call.

**Two different kinds of grouping, and it is easy to confuse them.**
- **Clusters** (k-means) group cells by *what they express* — cells with similar marker
  profiles go together, wherever they sit in the tissue. One cell type = one cluster.
- **Communities** group cells by *where they are* — cells that sit next to each other,
  whatever they express. So a cell type that is physically scattered (like blood-vessel
  cells, which are in many separate vessels) shows up in many communities at once.
Both are computed by the CellSurvey pipeline from the same data; they just answer
different questions.

## 1. Cell populations

### Marker distributions, and what "positive" means

The figure below shows the brightness distribution of every biological marker (on the z-score
scale described above). The **orange line** is the illustrative "positive" cutoff used
throughout this report: **z = +2**, i.e. the ~2% brightest cells for each marker. The dotted
line is the median (z = 0).

Two things worth reading from this: (1) **most markers have no clean second peak** — the
histogram is one broad pile with a tail, so there is no obvious "off" vs "on" population
to separate, and (2) the positive line is therefore a *choice*, not an inherent property of
the data — move it and different cells flip sides. This report uses z = +2 purely as a
display convenience, and where the biology matters the line should be chosen deliberately
(or the marker treated as a continuous quantity instead of a positive/negative call).

![Marker distributions with the positive cutoff](out_overview/marker_distributions.png)

### The 10 k-means clusters

The cells fall into **10 k-means clusters** (clustering shipped with the data). The
table below lists, for each cluster, its size and the five markers that best
distinguish it (mean robust z-score). **Debris%** flags how much of the cluster is
non-specific autofluorescence (bright in CD68 + FoxP3 + LamininA5 + H2AX at once).

![Cluster sizes and marker profiles](out_overview/populations_cluster_profile.png)

| Cluster | Size | Debris% | Top distinguishing markers (z-score) |
|---|---|---|---|
| 0 | 34,605 | 0% | E_cadherin (+1.94), p16 (+1.20), TP63 (+0.78), TP73 (+0.69), CD68 (+0.52) |
| 1 | 987 | 100% ⚠️ debris | FoxP3 (+6.54), CD68 (+5.59), H2AX (+5.48), LamininA5 (+5.32), CD11c (+4.80) |
| 2 | 113,130 | 0% | Collagen_I (+0.31), S100 (+0.04), PD_1 (-0.01), CD31 (-0.02), BCAM (-0.10) |
| 3 | 90,402 | 0% | Ki_67 (+1.22), CD3 (+0.87), CD4 (+0.86), LY75 (+0.83), CD8 (+0.78) |
| 4 | 29,574 | 2% | CD31 (+2.78), Fibronectin (+1.42), Collagen_IV (+1.36), BCAM (+1.33), LamininA5 (+1.18) |
| 5 | 3,300 | 83% ⚠️ debris | FoxP3 (+4.68), SMA (+3.35), CD68 (+3.25), H2AX (+3.22), TP73 (+3.12) |
| 6 | 19,901 | 0% | SMA (+2.36), BCAM (+2.26), Collagen_IV (+1.82), PD_1 (+1.65), CD56 (+1.36) |
| 7 | 35,470 | 0% | CD45RA (+1.68), CD20 (+1.06), HLADR (+0.84), CD11c (+0.78), CD45 (+0.62) |
| 8 | 35,094 | 0% | Collagen_I (+2.01), CD56 (+0.69), PD_1 (+0.67), CD31 (+0.57), CD68 (+0.57) |
| 9 | 330 | 100% ⚠️ debris | FoxP3 (+7.65), CD68 (+7.52), H2AX (+7.33), LamininA5 (+7.31), CD31 (+6.56) |

> **Clusters 1, 5, 9 are almost entirely non-specific autofluorescent debris**
> (bright in CD68 + FoxP3 + LamininA5 + H2AX simultaneously) and should not be read
> as real FoxP3⁺/LamininA5⁺/CD11c⁺ cell populations.

> **CD68 note.** The CD68 channel is treated as autofluorescent/debris and is excluded
> from lineage attribution, so no 'macrophage' population is claimed here. 5,595 cells
> (1.5%) are bright in ≥8 markers simultaneously and are flagged as non-specific.

## 2. Spatial maps

Where each cluster sits and where cells positive for each lineage marker sit, shown as
coloured points **overlaid on the actual tissue image** (DAPI = the greyscale nuclei):

![Spatial map of each k-means cluster](out_overview/spatial_cluster_maps.png)

The single map below shows **all clusters at once** (one colour per cluster, debris clusters
in grey) so the spatial layout of the cell types is visible without flipping between the
per-cluster panels above:

![Hexbin map of all k-means clusters over the tissue image](out_overview/cluster_hexmap.png)

![Spatial map of cells positive for each lineage marker](out_overview/spatial_lineage_maps.png)

## 3. Neighbourhoods / communities

Communities are built by the CellSurvey pipeline in two steps: it draws a network of
neighbouring cells (Delaunay triangulation, edges up to 1,000 px, each weighted by how
similar the two cells' marker profiles are), then runs **Louvain** community detection at a
**resolution** setting. Higher resolution → more, smaller communities; lower → fewer, larger.

The **default** resolution (0.1) gives **48 communities**. That is on the
fine-grained end — lowering the resolution merges most of that fine structure:

![Community outlines over the tissue image](out_overview/community_outlines.png)

**Are there interesting patterns?** Yes, once you look at the *large* communities
(the 18 communities below 1000 cells are the
isolated fragments already discussed, and are dropped from the composition plot):

- The 10 largest communities are **Ki_67/CD3 (6 of the 10 largest), Collagen_I/S100 (4 of the 10 largest)** — i.e. the tissue's big spatial blocks
  are immune-rich (T-cell) and matrix-rich regions.

- None of the 30 remaining communities are over 80% one cluster, so
  the large-scale tissue is genuinely mixed rather than divided into single-type blocks.

- The debris clusters (1, 5, 9) hardly form their own
  regions — together they dominate only 1 community — consistent with them
  being scattered autofluorescent cells, not a tissue compartment.

![Community composition by cluster](out_overview/community_composition.png)

## 4. Feasibility of the four thymus questions

This is a **single thymus section**, and the marker panel contains everything the
collaborator asks about — but a few data-quality limits shape what can be answered.

**Measurement compartment.** Each object is now a **whole-cell segmentation** (the nucleus
dilated into its surrounding cytoplasm), so each marker is the mean intensity over the nucleus
plus a cytoplasmic ring. That is a real improvement over the earlier nuclear-only readout, but it
is still a compromise rather than a per-marker measurement region:

| Compartment | Markers | Whole-cell mean captures it? |
|---|---|---|
| nuclear | TP63, TP73, p16, Ki-67, FoxP3, H2AX | ⚠️ yes, but diluted by the added cytoplasm |
| membrane | E-cadherin, CD31, CD45, CD3/4/8, CD20, CD56, CD11c, HLA-DR, PD-1/PD-L1, LY75, BCAM | ~ partially — a whole-cell *mean* dilutes the thin membrane ring |
| cytoplasmic | SMA (αSMA), Vimentin, CD68 | ✅ now captured (was missed by nuclear-only) |
| extracellular matrix | Collagen I/IV, Fibronectin, LamininA5 | ❌ still *between* cells — not cell-localised |

**The key empirical result: whole-cell segmentation did not rescue the membrane/immune
markers.** The table below shows CD45, CD4, HLA-DR and CD20 are still debris-dominated, and the
nuclear markers TP63/H2AX are still heavily contaminated. So the switch from nuclear to whole-cell
did not, by itself, recover a usable immune readout — either the cytoplasmic dilation is too small
to capture the membrane ring, or this involuted thymus genuinely has very few immune cells (the
two are hard to distinguish from these numbers alone).

1. **Thymic epithelial stem-cell niches (E-cadherin⁺/TP63⁺ and BCAM⁺/TP73⁺).** Answerable
   in principle — all four markers are present and E-cadherin/TP73/BCAM are relatively clean —
   but **TP63 is 78% debris**, and E-cadherin/BCAM are membrane markers whose
   whole-cell mean is diluted, so the niche needs careful debris gating.

2. **Thymic residues via immune markers.** Still the hardest. **CD68 did not work**
   (autofluorescent), so 'myeloid' can only be read from CD11c. CD45/CD3/CD4/HLA-DR still have
   almost no real signal (each ≤0.1% 'positive', the bright cells mostly
   debris) — consistent with an involuted thymus with few remaining thymocytes, and not fixed by
   the whole-cell readout.

3. **Matrix/vascular remodelling *with age*.** The markers (fibronectin, laminin, αSMA,
   CD31, collagens I/IV) are present and mostly clean, but this is **one section** — so it can show
   the current architecture, not change over time; and the ECM markers are still not cell-localised.

4. **Senescence (p16, H2AX).** Both markers are **nuclear**, so this remains the most reliable
   question (though their signal is diluted by the whole-cell mean). p16 is clean, but H2AX is
   ~56% debris and it is unconfirmed whether the panel's H2AX is the
   phosphorylated (γH2AX) DNA-damage form. 'Senescent behaviour' is a stronger claim than
   'expresses p16'.

The table below quantifies this for every marker the questions depend on:

| Marker | % positive (z>+2) | % of positive that are debris | Flag |
|---|---|---|---|
| E_cadherin | 6.0% | 9% | clean |
| TP63 | 1.4% | 78% | debris-dominated |
| BCAM | 6.0% | 18% | clean |
| TP73 | 6.3% | 19% | clean |
| CD45 | 0.1% | 100% | debris-dominated |
| CD3 | 0.1% | 26% | suspect |
| CD4 | 0.0% | 88% | debris-dominated |
| CD8 | 1.9% | 43% | suspect |
| CD20 | 1.6% | 70% | debris-dominated |
| CD68 | 1.9% | 62% | debris-dominated |
| CD11c | 4.6% | 23% | clean |
| HLADR | 0.7% | 86% | debris-dominated |
| LY75 | 2.1% | 24% | clean |
| FoxP3 | 4.3% | 29% | suspect |
| CD56 | 2.5% | 44% | suspect |
| Fibronectin | 4.6% | 19% | clean |
| LamininA5 | 2.5% | 46% | suspect |
| SMA | 8.0% | 16% | clean |
| CD31 | 9.9% | 10% | clean |
| Collagen_I | 5.2% | 1% | clean |
| Collagen_IV | 5.0% | 12% | clean |
| p16 | 1.9% | 18% | clean |
| H2AX | 2.2% | 56% | debris-dominated |

> The debris cells (clusters 1, 5, 9) are the autofluorescent population that contaminates
> these markers, and they must be excluded before any co-expression / niche / proximity
> analysis. What the collaborator is ultimately asking for — niche detection, Ki-67
> co-staining, HLA-DR in residual regions, cell-to-niche proximity — is a hypothesis-driven
> analysis that can be built on this same data once that debris gate is applied.
