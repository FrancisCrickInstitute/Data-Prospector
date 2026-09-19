# Is PD-L1 spread across several cell types — or is that an artefact of how we counted?

---

## Summary

PD-L1 is one of the most important molecules in cancer medicine: it is the on/off switch that many
tumours use to hide from the immune system, and it is the direct target of modern immunotherapy. So a
basic question — **which cells in a tumour actually carry PD-L1, and where do immune cells get close
to them?** — matters a great deal.

We measured this directly in a single tissue sample, using a technique that stains the DNA and ~30
protein markers in every cell at once (multiplexed immunofluorescence). The answer we got depends
surprisingly strongly on one technical step: **how we decide that a cell is "positive" for a given
marker.**

Here is what held up, and what did not:

- **Robust:** PD-L1 is *not* confined to a single cell type. It turns up on several — blood-vessel
  cells (CD31), epithelial cells (E-cadherin), macrophages (CD68) and stromal cells (SMA) — not just
  one. This conclusion survives every way we tried of drawing the positive/negative line.
- **Fragile:** the specific *size* of the effect, and one striking sub-claim — that immune cells are
  *kept out of* epithelial/PD-L1 regions (a possible "immune-exclusion" pocket) — did **not** survive.
  That sub-claim flips sign depending on how we normalise the data.

The take-home is not "the result is wrong". It is that **these single-marker "positive/negative"
calls are doing far more work than they are credited for**, and the most eye-catching conclusion is
exactly the part that is least robust.

---

## What the numbers actually rest on

Every downstream statement — "this cell type is enriched for PD-L1", "immune cells avoid this
region" — begins with a deceptively simple choice: for each marker, draw a line and call cells above
it "positive" and below it "negative".

The problem is that, for most markers in this tissue, **there is no obvious second peak to draw a
line at.** The brightness of most markers is one broad smear: most cells are dim, a tail is brighter,
and there is no clean "off" and "on" population to separate. Drawing a positive/negative line through
that smear is a judgement call — and small changes move a lot of cells from one side to the other.

### A quick note on what "normalisation" means here

Raw marker brightness numbers can't be compared directly, for two reasons that have nothing to do
with biology:

1. **Different markers are photographed at different brightness settings.** One marker's "dim" can be
   numerically larger than another marker's "bright", because the microscope was set up differently
   for each. So a marker's raw number on its own is meaningless — it only means anything *relative to*
   the other cells in the same image.
2. **The tissue is lit unevenly.** The image is a mosaic of many tiles stitched together, and the
   edges of each tile are slightly dimmer than the centre (plus other drift). So two identical cells —
   one in a bright spot, one in a dim spot — will read differently even for the *same* marker.

"Normalising" means adjusting the numbers to try to cancel out these technical effects, so that what
remains reflects actual biology. There is more than one way to do it, and **the choice matters** — which
is the whole point of this report.

The **original analysis** used this recipe: (i) apply a log-like transform (arcsinh) to tame the very
bright cells; (ii) subtract a *local* background estimate — for each small patch of the image, work
out a "typical" value and subtract it, to try to cancel the uneven lighting; (iii) rescale each marker
so a typical cell sits at zero and one unit is one "spread" of that marker; then (iv) draw the
positive/negative line automatically on the result.

We then compared that against **swapping step (ii) for a different principle** (dividing by the cell's
own DNA/DAPI signal instead) — see "What if we normalise differently?" below.

---

## Figure 1 — Where the cutoffs actually fall

![Marker brightness distributions with the positive/negative cutoffs overlaid](out_pd1pdl1_sensitivity/distributions_vs_cutpoints.png)

**What this plot is.** Each panel is a histogram for one marker: how many cells have a given
brightness for that marker.

**Reading the axes:**
- **Horizontal axis** — how bright a cell is for that marker, after a standard transformation
  (arcsinh, similar to a log scale but one that also handles zero and negatives) that squeezes the
  very bright cells in so the whole range fits on one plot. Values were then centred so that "0" is a
  typical (median) cell and one unit is one "spread" of the data. So this is a *relative* scale — the
  important thing is where a cell sits relative to the bulk of the tissue, not the raw number.
- **Vertical axis (log scale)** — how many cells have each brightness. Log scale lets us see the huge
  pile of dim cells and the small tail of bright cells on the same plot.
- **Red line** — the cutoff the original analysis actually used to call a cell "positive".
- **Blue dashed line** — a different, older method for choosing a cutoff (called "Otsu").

**What to notice.** For most markers there is **no clean second bump** to the right of the red line —
no separate "on" population. The histogram is one tall pile that just fades away. And the two methods
(red vs. blue) don't agree on where to draw the line. For two markers in particular — **FoxP3** and
**CD4** — there is effectively no usable split at all: the automatic line ended up flagging over half
of *all* cells (57% for CD4, 97% for FoxP3) as "positive", which tells us the analysis was not
genuinely identifying "CD4⁺/FoxP3⁺ cells", just "cells above some essentially arbitrary line".

---

## What if we normalise differently?

The original analysis tried to correct for the slide's uneven illumination by subtracting a local
"background" estimate and then rescaling. A natural alternative question is: **what if, instead, we
express every marker *relative to the cell's own DNA (DAPI) signal?***

The reasoning: DAPI stains every nucleus, so its brightness tracks *which part of the slide the cell
is in* (i.e. the uneven illumination) more than anything about the cell's biology. Dividing each
marker by the local DAPI level should therefore cancel out that positional variation.

This is a principled idea, so we tested it. Two things happened:

1. **The "PD-L1 across several cell types" finding got *stronger* and cleaner.** The odds ratios
   jumped (macrophages ~100×, blood-vessel ~33×, stromal ~25×, epithelial ~14×, vs. ~3–5× before),
   and the artefacts on the near-constant markers disappeared (FoxP3 went from 97% "positive" to a
   sensible 25%).

2. **The "immune cells are kept out of epithelial/PD-L1 regions" sub-claim vanished.** Under
   DAPI-normalisation, immune cells are *enriched* (not excluded) around epithelial PD-L1 cells, and
   all four compartments now behave essentially the same. The original, eye-catching "exclusion zone"
   does not survive this change.

**But DAPI-normalisation has its own problem**, and it is worth being honest about it: it made some
markers too homogeneous. Roughly half the tissue now reads as "CD3⁺", which is biologically
implausible — T cells should be a modest minority, not half the sample. Dividing by DAPI collapsed the
genuine dim-vs-bright split for these markers, so while it fixed the illumination artefact, it
over-corrected the actual biological signal for some markers.

**The point is not that one method is "right".** It is that two reasonable normalisation choices give
opposite answers to the same question. That is the definition of a conclusion that isn't ready to
report as a finding.

---

## Figure 2 — Does the "immune exclusion" pattern survive changing the method?

The original analysis's most striking claim was that immune cells (CD8⁺ cytotoxic T cells — the
tumour-killers) are *avoided* near PD-L1⁺ epithelial cells while gathering near other PD-L1⁺ cell
types. We re-ran that exact measurement several times, each time changing only *how cells are
normalised and how "positive" is decided*. Because the two normalisation strategies behave very
differently, we show them as two separate figures.

### Figure 2a — the original normalisation strategy

![Immune-cell enrichment near PD-L1-positive cells, original normalisation](out_pd1pdl1_sensitivity/enrichment_original_strategy.png)

Here we keep the original normalisation recipe (arcsinh → local background subtraction → rescale) and
change only the final **positivity rule** — the specific way the positive/negative line is drawn:

- `repro` — the positivity rule the original analysis actually used;
- `otsu-only` / `gmm-only` — the two individual decision rules the original blended together;
- `no-local-corr` — the original but *without* the local background subtraction step;
- `p90-fixed` — a blunt rule ("the brightest 10% of cells count as positive").

**Reading the axes (same for both figures):**
- **Horizontal axis** — neighbourhood radius: how far out (in the image's spatial units) we look
  around each PD-L1⁺ cell when counting nearby immune cells.
- **Vertical axis** — "enrichment". A value of **1.0** (the dashed grey line) means "immune cells are
  found here at exactly the rate you'd expect by chance". **Above 1** = more immune cells than chance;
  **below 1** = fewer than chance (a zone immune cells avoid).
- Each coloured line is a different cell compartment (the four PD-L1⁺ cell types).

**What to notice.** The overall story — immune cells are *more* common than chance near PD-L1⁺ cells —
is broadly similar across the five panels. **But whether the epithelial line dips *below* 1.0 (an
"exclusion zone") is not stable**: it drops just under baseline under `repro`, `otsu-only` and
`gmm-only`, but stays *above* baseline under `no-local-corr` and `p90-fixed`. The single most
interesting claim in the original analysis is the one that flips with a reasonable change of method.

### Figure 2b — the DAPI-ratio normalisation

![Immune-cell enrichment near PD-L1-positive cells, DAPI-ratio normalisation](out_pd1pdl1_sensitivity/enrichment_dapi_norm.png)

Here we switch the normalisation strategy entirely: instead of subtracting a local background, we
divide each marker by the cell's own **DNA (DAPI) signal** (smoothed across neighbours, so that it
tracks *where in the slide* the cell sits rather than the cell's own biology). To make the comparison
fair, we apply the **same four positivity rules** as in Figure 2a:

- `DAPI · repro` / `DAPI · otsu` / `DAPI · gmm` — the same automatic decision rules as before, now run
  on the DAPI-normalised numbers (note `repro` and `gmm` essentially coincide here);
- `DAPI · p90` — the same blunt "brightest 10%" rule.

**What to notice.** Three things stand out compared to Figure 2a:

1. **The epithelial line never dips below 1.0.** Under every positivity rule, immune cells are
   strongly *enriched* (roughly 3–4×) around epithelial PD-L1⁺ cells, just as around every other
   compartment. The "immune-exclusion zone" that appeared in some of Figure 2a's panels does not
   survive the switch to DAPI-normalisation — the whole differential "some compartments but not
   others" pattern disappears, and all four lines sit on top of each other.
2. **The curves are flatter and higher** than the original strategy's, and much less dependent on
   which positivity rule is used (the `p90` rule is again an outlier, inflating everything ~3×).
3. **This flattening is itself a warning.** DAPI-normalisation over-corrected: it made some markers
   too homogeneous (roughly half the tissue now reads as "CD3⁺", which is biologically implausible —
   T cells should be a modest minority). So this normalisation fixed the illumination artefact but
   partly destroyed the genuine dim-vs-bright biological signal for those markers.

The point is not that either figure is "the truth". It is that **two reasonable normalisation choices
give opposite answers** to the same question — which is the definition of a conclusion that isn't
ready to report as a finding.

### Why the DAPI-normalised curves look flat — and why "1.0" means less than it looks

Reading these figures requires knowing exactly what the "enrichment" number is:

> **enrichment(r)** = (average fraction of a PD-L1⁺ cell's neighbours that are T cells) **÷** (the
> fraction of the *whole tissue* that are T cells).

In other words, the number is a local density **divided by a global baseline**. The "1.0 = no
relationship" line only means what it says if that global baseline is itself a meaningful number.
It is not — it is a **product of three threshold decisions**:

> global T-cell fraction = `fraction(CD3⁺)` × `fraction(CD8⁺)` × `fraction(PD-1⁺)`

Each of those three fractions is a threshold-dependent positivity rate of exactly the kind this whole
report is about. And because they multiply, their instability compounds. How much the "no
relationship" baseline actually moves across the methods we tested:

| method | "T-cell" fraction of the tissue (the baseline) |
|---|---|
| `p90-fixed` | 1.2 % |
| `no-local-corr` | 3.2 % |
| `gmm-only` | 5.4 % |
| `repro` (original) | 8.3 % |
| `otsu-only` | 8.8 % |
| `dapi-gmm` | 13.1 % |
| `dapi-otsu` | 15.7 % |
| `dapi-repro` | 17.2 % |

That is a **~14-fold spread** in the very quantity that defines "no enrichment". It is not a measured
fact about how many T cells are in this tissue — it is a readout of how aggressively each method calls
cells "positive".

**This is why the DAPI-normalised curves never get near 1.0.** DAPI-ratio normalisation collapsed the
dim-vs-bright separation of CD3 and CD8 (as noted above) so badly that roughly half the tissue reads
as "CD3⁺", and the *baseline* jumped to ~15–17%. The enrichment curves are then normalised against
that inflated denominator. The result is a set of flat, high curves whose absolute height (3–4×) is
largely a property of the broken baseline, **not** of the biology. The original method's modest ~2–3×
values rest on an equally arbitrary (but smaller and less obviously broken) 8.3% baseline.

So the honest reading of Figures 2a and 2b together is:

- **The *direction* of the main result is robust** — immune cells are generally found *more* often
  than chance near PD-L1⁺ cells, under essentially every method. That holds.
- **The *magnitude* is not** — the numbers span a wide range, and none of them comes with a trustworthy
  "chance" baseline, because the baseline itself is a product of the very threshold choices under
  review.
- **The one *differential* claim** — that epithelial PD-L1⁺ regions are *specifically avoided*
  (an "exclusion zone", below 1.0) — appears in only some of Figure 2a's panels and in *none* of
  Figure 2b's. It is the least robust statement in the original analysis and should not be treated
  as established.

## Figure 3 — where each cell type actually sits in the tissue

![Spatial maps of each PD-L1-positive compartment, one panel per cell type](out_pd1pdl1_sensitivity/spatial_maps_per_compartment.png)

**What this is.** Eight maps of the same tissue section, laid out as a grid. **Each column is one
cell type** (the four PD-L1⁺ compartments), and **each row is one normalisation strategy** (original
on top, DAPI-ratio below). In every panel the pale grey background is the whole tissue (every cell),
and the coloured patches are the *PD-L1-positive* cells of that one type — so you can see at a glance
where each type lives:

- **Macrophage** (CD68⁺) — red
- **Epithelial** (E-cadherin⁺) — purple
- **Endothelial** (CD31⁺) — green
- **Stromal** (SMA⁺) — orange

Each panel's title carries a count, so you can also see how many cells each method *calls* positive.
The patches are "hexbins" (cells grouped into small hexagons) so the dense regions don't collapse
into an unreadable black smear.

**What to notice.** Compare down a column (same cell type, different normalisation) and across a row
(same normalisation, different cell types):

1. **Each cell type has its own, partly distinct spatial pattern.** Look at the top row: macrophages
   are broadly spread, but the endothelial and stromal panels show clear regional structure — the
   colour is not uniform, it concentrates in particular areas of the tissue. This is real localisation
   information that was invisible in the original report's single fused map (where the most numerous
   type drowned out the others).

2. **Down a column, the two normalisations disagree about *how much* is there, more than about
   *where*.** The bottom (DAPI) row is noticeably denser than the top for the macrophage, epithelial
   and stromal panels — the visual fingerprint of the over-correction this report describes, which
   calls ~2× more cells "positive". The *location* of the patches is broadly similar; the *amount* is
   not.

3. **The compartments overlap in space, they do not tile the tissue.** There is no clean
   "epithelial over there, blood-vessel over here". The coloured patches are interleaved, which is
   *why* the enrichment curves in Figure 2 sit broadly above 1.0: immune cells near one PD-L1⁺
   compartment are also near the others. This spatial mixing is the deeper reason the "epithelial
   exclusion" idea is fragile — it depends on how you carve up overlapping signals, not on the
   compartments being physically separate from one another.

---

## What this means for the biology

1. **Safe to trust:** "PD-L1 is expressed across several distinct cell compartments — endothelial,
   epithelial, macrophage and stromal — rather than confined to one." This is consistent and robust,
   and worth following up with proper methods.

2. **Also broadly stable:** "immune cells (CD8⁺ cytotoxic T cells) are generally found *more* often
   than chance close to PD-L1⁺ cells." This direction holds across almost every regime we tried —
   the disagreement is about how *much* more, and about whether one specific compartment (epithelial)
   is different from the rest.

3. **Do not trust yet:** the *magnitude* of any of these effects, and especially the idea of an
   "immune-exclusion zone around epithelial/PD-L1 regions". The magnitude is not robust because the
   "no relationship" baseline it is measured against is itself a product of the very threshold choices
   under review, and it swings ~14-fold between methods. The "epithelial exclusion" idea in particular
   appears in only some regimes and none of the DAPI-normalised ones. These need to be re-derived with
   an approach that does not force every marker into a hard on/off split — for example, treating each
   marker as a continuous quantity, or choosing thresholds with a biological (rather than a
   statistical-convenience) justification.

---

## Method (for the interested)

- **Sample:** a single tissue section, 362,736 segmented nuclei, each with ~30 protein-marker
  intensities plus a DNA stain (DAPI).
- **Two normalisation strategies, each crossed with several positivity rules.** *Original strategy*
  (arcsinh → local background subtraction → robust scaling) with four positivity rules: the Gaussian-
  mixture threshold with an Otsu fallback (`repro`), Otsu alone, Gaussian-mixture alone, and a "top
  10% brightest" rule — plus a variant with the background-subtraction step removed. *DAPI-ratio
  strategy* (each marker divided by the locally-smoothed DNA signal), with the same four positivity
  rules (`repro`, Otsu, Gaussian-mixture, top-10%).
- **What was compared:** for each strategy, the odds ratio of "PD-L1⁺ and also <lineage>⁺", and the
  spatial enrichment of CD8⁺ cytotoxic T cells around each PD-L1⁺ compartment at radii from 50 to 800
  spatial units.
- **Reproduce it:** `pixi run python explorations/cellsurvey/pd1pdl1_threshold_sensitivity.py`
  regenerates the four figures and the three CSV tables (`cutpoint_sweep.csv`,
  `method_comparison.csv`, `method_enrichment.csv`) that the numbers above came from.
