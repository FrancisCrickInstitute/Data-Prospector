# Literature

A standing reading list of external papers relevant to this project, split out the same way
`BACKLOG.md` was split from `DEVELOPMENT_LOG.md`: a distinct kind of content that doesn't belong in
either — not a decision made (`DEVELOPMENT_LOG.md`), not a deferred work item (`BACKLOG.md`), just a
pointer to something worth reading and why. Nothing here is a commitment to act; entries move to
`BACKLOG.md` (as a concrete item) or `DEVELOPMENT_LOG.md` (as a decision) once someone actually reads
one and it changes something.

Sourced from a 2026-09-06 scan of the user's Papers-app library (685 entries) against this project's
actual technical surface — the CellSurvey `configs/cellsurvey_config.py` `DOMAIN_NOTES` gaps and the
diverger pipeline's own architecture — not a general bioimage-analysis reading list (the library is
mostly that, and most of it doesn't touch what this project does).

**Two of the architecture papers below are already cited in `README.md`'s "Design influences"
section (refs 3 and 4) — Co-Scientist and "The AI Scientist"** — so they're not new leads, they're
the project's own stated prior art. Worth re-reading now that Run 42 exists to compare their design
choices against (e.g. their hypothesis-ranking/tournament mechanics vs. this project's graded-not-gated
insight/soundness judges), but they don't belong in this list as "unexamined" — noted here only so
nobody re-discovers them as new.

---

## 1. CellSurvey domain — `DOMAIN_NOTES` / clustering / spatial-analysis literature

Candidates for sharpening `configs/cellsurvey_config.py`'s `DOMAIN_NOTES`, or for critiquing/improving
angles like `continuous-vascular-proximity-cd8-pd1-gradient` and the shipped `kmeans_cluster`
preprocessing (rev. 81, Live Issue 39, Live Issue 38).

- **Bruhns, M., et al. (2025). Effects of segmentation errors on downstream-analysis in
  highly-multiplexed tissue imaging.** *PLOS Computational Biology*.
  `doi:10.1371/journal.pcbi.1013350`
  Quantifies how much segmentation error actually distorts downstream marker quantification —
  turns rev. 78's hand-written "nuclear-not-cell" caveat into something with a measured, citable
  magnitude instead of an assumption.

- **Zhang, W., et al. (2022). CELESTA — Identification of cell types in multiplexed in situ images
  by combining protein expression and spatial information.** *Nature Methods*.
  `doi:10.1038/s41592-022-01498-z`
  Unsupervised typing that folds spatial context into the assignment itself — a concrete alternative
  to critique the shipped `kmeans_cluster` (all 32 channels, `StandardScaler`, no spatial term)
  against. Relevant to rev. 81's weakness and Live Issue 38's search for better alternative groupings.

- **Amitay, Y., et al. (2023). CellSighter: a neural network to classify cells in highly multiplexed
  images.** *Nature Communications*. `doi:10.1038/s41467-023-40066-7`
  Same territory as CELESTA — supervised cell classification, another concrete comparator.

- **Brand, J., et al. (2025). Fluoro-forest: a random forest workflow for cell type annotation in
  high-dimensional immunofluorescence imaging with limited training data.** *Bioinformatics
  Advances*. `doi:10.1093/bioadv/vbaf320`
  Explicitly targets the exact pattern rev. 81 flags — unsupervised clustering followed by
  cluster-level marker-average annotation, "which can result in misclassification" — almost a
  direct citation for that weakness.

- **Magness, A., et al. (2024). Deep cell phenotyping and spatial analysis of multiplexed imaging
  with TRACERx-PHLEX.** *Nature Communications*. `doi:10.1038/s41467-024-48870-5`
  End-to-end segmentation → typing → spatial-analysis reference pipeline — useful structural
  comparator for what a more rigorous version of the whole CellSurvey analysis chain looks like.

- **Canete, N. P., et al. (2022). spicyR: spatial analysis of in situ cytometry data in R.**
  *Bioinformatics*. `doi:10.1093/bioinformatics/btac268`
  Purpose-built package for the same kind of cell-neighbourhood analysis
  `continuous-vascular-proximity-cd8-pd1-gradient` hand-rolls with `cKDTree` + Gaussian weighting —
  worth comparing methodology against.

- **Summers, H. D., Wills, J. W., & Rees, P. (2022). Spatial statistics is a comprehensive tool for
  quantifying cell neighbor relationships and biological processes via tissue image analysis.**
  *Cell Reports Methods*. `doi:10.1016/j.crmeth.2022.100348`
  General methodological grounding for the kNN/point-process approach already in use in the
  vascular-proximity angle and its `explorations/cellsurvey/` follow-up.

- **Harris, C. R., et al. (2022). Quantifying and correcting slide-to-slide variation in multiplexed
  immunofluorescence images.** *Bioinformatics*. `doi:10.1093/bioinformatics/btab877`
  A more rigorous, published alternative to rev. 78/79's per-marker robust normalisation and
  local-baseline mitigation — currently hand-described in `DOMAIN_NOTES` as "an approximate
  mitigation, not a calibrated flat-field correction."

- **Graf, J., et al. (2021). FLINO — A new method for immunofluorescence bioimage normalization.**
  *Bioinformatics*. `doi:10.1093/bioinformatics/btab686`
  Same territory as Harris et al. above — a purpose-built IF batch-effect normalisation method.

- **Berry, S., et al. (2021). Analysis of multispectral imaging with the AstroPath platform informs
  efficacy of PD-1 blockade.** *Science*. `doi:10.1126/science.aba2609`
  Not a methods paper — a real multispectral-imaging study of PD-1 spatial biology. Closest thing in
  the library to a domain-literature sanity check on whether the vascular-proximity/PD-1 angle's
  underlying biology is plausible.

---

## 2. Diverger pipeline architecture

- **Messeri, L., & Crockett, M. J. (2024). Artificial intelligence and illusions of understanding in
  scientific research.** *Nature*. `doi:10.1038/s41586-024-07146-0`
  Not cited anywhere in this repo. Directly relevant to the `delivered_score`-is-anti-correlated-
  with-actual-worth finding (CLAUDE.md, "The five realisation outcomes") and to the graded-not-gated
  soundness-judge design — a good candidate citation for *why* that design choice exists.

- **Hao, Q., Xu, F., Li, Y., & Evans, J. (2026). Artificial intelligence tools expand scientists'
  impact but contract science's focus.** *Nature*. `doi:10.1038/s41586-025-09922-y`
  Also uncited. Empirically documents the exact narrowing failure mode README's "Why diverge instead
  of converge" section is explicitly built to counter — strong citation candidate for that section.

- **Pylvänäinen, J. W., Grobe, H., & Jacquemet, G. (2025). Practical considerations for data
  exploration in quantitative cell biology.** *Journal of Cell Science*. `doi:10.1242/jcs.263801`
  Practical opinion piece on exploratory-analysis workflow for bioimage data. Relevant to the
  `explorations/` follow-up pattern (see `explorations/cellsurvey/vascular_proximity.py`), not the
  core pipeline design — a separate use case from the two above.

---

*Already cited in `README.md`, not repeated here as new leads:*
- Gottweis, J., et al. (2026). Accelerating scientific discovery with Co-Scientist. *Nature*.
  `doi:10.1038/s41586-026-10644-y`
- Lu, C., et al. (2026). Towards end-to-end automation of AI research ("The AI Scientist"). *Nature*.
  `doi:10.1038/s41586-026-10265-5`
