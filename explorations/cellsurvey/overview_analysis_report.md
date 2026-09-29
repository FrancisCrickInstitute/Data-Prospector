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

Where each cluster sits and where cells positive for each lineage marker sit, shown as
coloured points **overlaid on the actual tissue image** (DAPI = the greyscale nuclei):

![Spatial map of each k-means cluster](out_overview/spatial_cluster_maps.png)

![Spatial map of cells positive for each lineage marker](out_overview/spatial_lineage_maps.png)

## 3. Neighbourhoods / communities

Communities are built by the CellSurvey pipeline in two steps: it draws a network of
neighbouring nuclei (Delaunay triangulation, edges up to 1,000 px, each weighted by how
similar the two cells' marker profiles are), then runs **Louvain** community detection at a
**resolution** setting. Higher resolution → more, smaller communities; lower → fewer, larger.

The **default** resolution (0.1) gives **49 communities**. That is on the
fine-grained end, and the sensitivity sweep below shows what happens as the resolution is
lowered:

- **Resolution sweep:** resolution 0.1 → 49 communities; resolution 0.05 → 36 communities; resolution 0.02 → 28 communities; resolution 0.01 → 26 communities.

![Community resolution sweep](out_overview/community_resolution_sweep.png)

![Community histogram and community map over the tissue](out_overview/communities.png)

**Why the 13 CD31 communities are not "one group that got split up."**

The 13 communities that look "all CD31" are actually **26 isolated
single/few-cell islands** (1–4 cells each), scattered across the whole tissue, not a
large vessel broken into pieces. They are the minority of the CD31 population — the
other **41,442** CD31 cells live inside larger, mixed communities. Because
these 26 cells are physically separate, they correctly form separate *spatial*
communities, and lowering the resolution does **not** merge them (they stay
13 communities even at resolution 0.01).

If you want "all CD31 cells as one group," that is exactly what the **cluster** label
already gives you: cluster 6 is the single endothelial/vascular group, 41,468 cells,
across the whole tissue. Communities answer "where", clusters answer "what" — the CD31
cells being split across many communities is the correct answer to "where", not a
detection failure.

**Are there interesting patterns?** Yes, once you look at the *large* communities
(the 18 communities below 1000 cells are the
isolated fragments already discussed, and are dropped from the composition plot):

- The 10 largest communities are **proliferative immune (Ki-67/CD3/CD8) (4 of the 10 largest), mixed matrix (collagen/S100) (4 of the 10 largest), immune (CD3/CD4/leukocyte) (2 of the 10 largest)** — i.e. the tissue's big spatial blocks
  are immune-rich (T-cell) and matrix-rich regions.

- None of the 31 remaining communities are over 80% one cluster, so
  the large-scale tissue is genuinely mixed rather than divided into single-type blocks.

- The three debris clusters (1/3/8) hardly form their own regions — together they dominate
  only 1 community —
  consistent with them being scattered autofluorescent cells, not a tissue compartment.

![Community composition by cluster](out_overview/community_composition.png)

**Cluster sensitivity (k-means elbow).** The k-means `k` is also a free choice; the
sweep shows inertia falls smoothly as `k` grows with no sharp elbow at `k=10` (the
shipped value) — 10 is a reasonable but not special choice.

![K-means inertia vs k](out_overview/cluster_elbow.png)

## 4. Representative images

DAPI/CD3/PD-L1 and DAPI/E-cadherin/SMA composites of the actual tissue at 16x
downsampling:

![Composite: DAPI / CD3 / PD-L1](out_overview/representative_images.png)

![Composite: DAPI / E-cadherin / SMA](out_overview/representative_images_epi_stromal.png)
