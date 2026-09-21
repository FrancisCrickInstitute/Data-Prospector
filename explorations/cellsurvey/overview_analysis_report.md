# CellSurvey tissue — a broad overview

One tissue section, **362,736 segmented nuclei**, ~32 marker channels.

This is a visual summary, not a single hypothesis test: who is in the tissue (cell
populations), where they are (spatial maps), how the tissue is organised
(communities), and what it looks like (representative images).

## How to read this (in plain terms)

**"z-score"** is just a way to put every marker on the same ruler. Raw brightness
numbers can't be compared directly — each marker is photographed at its own settings and
the slide is lit unevenly — so for each marker we centre every cell at "0 = a typical
cell" and count in steps of "1 = one spread of the data". A z-score of +2 means
"noticeably brighter than the typical cell for that marker"; it does **not** mean the
cell is definitively positive — the positive/negative line is a separate judgement call.
**"Community"** just means a cluster of nuclei that sit next to each other
in the tissue (found algorithmically); it's a way to ask "what regions does this tissue
break into?" without imposing a predefined map.

## 1. Cell populations

The nuclei fall into **10 k-means clusters** (clustering shipped with the data). The
table below lists, for each cluster, its size and the five markers that best
distinguish it (mean robust z-score). **Debris%** flags how much of the cluster is
non-specific autofluorescence (bright in CD68 + FoxP3 + LamininA5 + H2AX at once).

![Cluster sizes and marker profiles](out_overview/populations_cluster_profile.png)

| Cluster | Size | Debris% | Top distinguishing markers (z-score) |
|---|---|---|---|
| 0 | 70,311 | 0% | CD45RA (+0.50), CD3 (+0.50), CD4 (+0.35), CD45 (+0.31), HLADR (+0.31) |
| 1 | 2,211 | 93% ⚠️ debris | FoxP3 (+5.53), SMA (+3.70), TP73 (+3.51), CD68 (+3.49), LamininA5 (+3.48) |
| 2 | 16,627 | 0% | Collagen_I (+2.53), CD56 (+0.83), PD_1 (+0.76), CD68 (+0.76), H2AX (+0.76) |
| 3 | 400 | 100% ⚠️ debris | FoxP3 (+8.13), LamininA5 (+7.51), CD68 (+7.33), CD11c (+7.18), H2AX (+7.12) |
| 4 | 16,236 | 0% | CD45RA (+3.00), CD20 (+1.28), CD45 (+0.82), HLADR (+0.81), CD3 (+0.32) |
| 5 | 113,492 | 0% | Collagen_I (+0.61), S100 (+0.39), PD_1 (+0.28), Collagen_IV (+0.26), CD31 (+0.22) |
| 6 | 41,468 | 2% | CD31 (+2.11), BCAM (+1.58), Fibronectin (+1.43), SMA (+1.40), Collagen_IV (+1.33) |
| 7 | 71,835 | 0% | Ki_67 (+1.32), LY75 (+0.98), CD4 (+0.87), CD3 (+0.82), CD8 (+0.78) |
| 8 | 1,022 | 100% ⚠️ debris | FoxP3 (+7.52), LamininA5 (+5.68), CD11c (+5.59), CD68 (+5.46), H2AX (+5.39) |
| 9 | 29,134 | 0% | E_cadherin (+2.13), p16 (+1.56), TP73 (+0.86), TP63 (+0.84), CD68 (+0.43) |

> **Clusters 1, 3, 8 are almost entirely non-specific autofluorescent debris**
> (bright in CD68 + FoxP3 + LamininA5 + H2AX simultaneously) and should not be read
> as real FoxP3⁺/LamininA5⁺/CD11c⁺ cell populations.

> **CD68 note.** The CD68 channel is treated as autofluorescent/debris and is excluded
> from lineage attribution, so no 'macrophage' population is claimed here. 5,695 nuclei
> (1.6%) are bright in ≥8 markers simultaneously and are flagged as non-specific.

## 2. Spatial maps

Where each cluster sits and where cells positive for each lineage marker sit:

![Spatial map of each k-means cluster](out_overview/spatial_cluster_maps.png)

![Spatial map of cells positive for each lineage marker](out_overview/spatial_lineage_maps.png)

## 3. Neighbourhoods / communities

The tissue is partitioned into **49 spatial communities** (property-graph
communities over neighbouring nuclei); the largest has 25,067 nuclei.

![Community histogram and spatial layout](out_overview/communities.png)

**Are there interesting patterns?** Yes, and the composition plot makes them visible:

- The communities are **not all the same** — the most common community identities are
  mixed matrix (collagen/S100) (24 communities), endothelial/vascular (CD31) (13 communities), proliferative immune (Ki-67/CD3/CD8) (7 communities).

- 16 of 49 communities are "pure" (over 80% one cluster), meaning the tissue
  separates into **compositionally distinct regions** rather than an even mix everywhere.
- The three debris clusters (1/3/8) hardly form their own regions — together they dominate
  only 1 community —
  consistent with them being scattered autofluorescent cells, not a tissue compartment.

![Community composition by cluster](out_overview/community_composition.png)

## 4. Representative images

DAPI/CD3/PD-L1 and DAPI/E-cadherin/SMA composites of the actual tissue at 16x
downsampling:

![Composite: DAPI / CD3 / PD-L1](out_overview/representative_images.png)

![Composite: DAPI / E-cadherin / SMA](out_overview/representative_images_epi_stromal.png)
