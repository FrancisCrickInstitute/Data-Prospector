# Plan: split the CellSurvey analysis out into its own project

Status: **proposed, not yet executed.** This is a handoff plan for the agent (or human) that
performs the split. It was written after the whole-cell CellSurvey exploration
(`explorations/cellsurvey_wholecell/`) had clearly grown beyond "follow up a Data-Prospector gallery
result" into standalone, collaborator-facing analysis of the CellSurvey tissue.

## Goal

Move the CellSurvey *analysis* work — in particular the whole-cell overview + thymus-feasibility
analysis, and arguably the nuclear overview — out of Data Prospector into a new, focused project
(tentatively named **CellSurveyThymusAnalysis**), while keeping everything that is genuinely
Data-Prospector pipeline machinery (and its "go deep on a gallery angle" `explorations/` follow-ups)
in this repo.

The split is fuzzy in a few places (see "Open decisions"). This plan enumerates exactly what is
where, and what a fresh agent must do to execute it.

## Mechanism

Clone-and-prune, to retain the full git history in both copies:

1. `git clone` this repository to a new directory (and later rename the clone's GitHub repo).
2. In **each** copy, `git rm` the files that don't belong to that copy and commit.
3. History is preserved in both: pruning files from a working tree does not delete them from the
   commit history, so nothing is lost by pruning.

Do **not** do a history rewrite (`filter-repo` etc.) — same "forward-only" rationale as the 2026-09-09
privacy cleanup already recorded in `docs/DEVELOPMENT_LOG.md`: pruning forward is cheap and reversible;
rewriting history is expensive and risky.

## Current tracked-file inventory

Everything below is `git ls-files` at the time this plan was written.

Top level: `.gitignore`, `.gitmessage`, `CLAUDE.md`, `Dockerfile`, `LICENSE`, `README.md`, `app.py`,
`config.py`, `ideation.py`, `judging.py`, `llm.py`, `output.py`, `parsing.py`, `pipeline.py`,
`pixi.lock`, `pixi.toml`, `preflight.py`, `prompts.py`, `realization.py`, `sandbox.py`.

Directories:

- `assets/` — `generate_pipeline_figure.py`, `pipeline_diagram.png`, `pipeline_diagram.svg`
- `configs/` — `__init__.py`, `bioimage_config.py`, `cellprofiler_config.py`, `cellsurvey_config.py`
- `docs/` — `BACKLOG.md`, `DEVELOPMENT_LOG.md`, `DEVELOPMENT_LOG_ARCHIVE.md`, `LITERATURE.md`
- `inputs/` — `cellsurvey_report/task_report.md`, `idr0028_report/task_report.md`
- `scripts/` — `preprocess_cellsurvey.py`
- `explorations/cellsurvey/` — `make_report_html.py`, `overview_analysis.py`,
  `overview_analysis_report.md`, `pd1pdl1_threshold_sensitivity.py`,
  `pd1pdl1_threshold_sensitivity_report.md`
- `explorations/cellsurvey_wholecell/` — `make_report_html.py`, `overview_analysis.py`,
  `overview_analysis_report.md`

## What will NOT carry over (gitignored, regenerable)

These are `.gitignore`d and therefore **absent from any clone** — only the source and the tracked
markdown reports move. A fresh clone must regenerate them locally:

- `inputs/cellsurvey_processed/` and `inputs/cellsurvey_wholecell_processed/` — the extracted `cells.csv`
  (+ `marker_channel_names.csv` sidecar). Regenerate with `scripts/preprocess_cellsurvey.py`
  (nuclear) / `--whole-cell`.
- `explorations/*/out_*/` — the PNG figures and CSV tables the analysis scripts write.
- `explorations/*/*.html` — the self-contained HTML reports (`make_report_html.py` regenerates them).
- `outputs/` — pipeline galleries (irrelevant to the clone).
- `.idea/`.

Net effect: the new project will be **source + markdown reports only** until `preprocess_cellsurvey.py
--whole-cell` and the overview script are re-run against the Z: zarr.

## File disposition

### Keep in Data Prospector (the pipeline)

- Everything that is the diverger pipeline: `app.py`, `config.py`, `pipeline.py`, `ideation.py`,
  `judging.py`, `realization.py`, `output.py`, `llm.py`, `parsing.py`, `sandbox.py`, `preflight.py`,
  `prompts.py`.
- `configs/` (all four, including `cellsurvey_config.py` — it is a pipeline config importing
  `config.PipelineConfig`, and the pipeline's `--config cellsurvey` still runs against nuclear data).
- `inputs/` (the two `task_report.md` files — they are pipeline reports).
- `assets/`, `Dockerfile`, `pixi.toml`/`pixi.lock`, `LICENSE`.
- `docs/DEVELOPMENT_LOG.md`, `docs/DEVELOPMENT_LOG_ARCHIVE.md`, `docs/BACKLOG.md` (pipeline history).
- `explorations/cellsurvey/pd1pdl1_threshold_sensitivity.py` + `pd1pdl1_threshold_sensitivity_report.md`
  — this is a genuine "go deep on a gallery angle" follow-up (rev. 92); it stays.

### Move to CellSurveyThymusAnalysis (the analysis)

- `explorations/cellsurvey_wholecell/` (all three tracked files) — unambiguous: whole-cell
  segmentation the pipeline never ran on, done for a collaborator's thymus questions.
- **Recommended, but a decision:** `explorations/cellsurvey/overview_analysis.py` +
  `overview_analysis_report.md` (the nuclear overview) — it is descriptive QC of the pipeline's own
  data, but its *purpose* ("what is in this tissue before we pattern-hunt") is the same as the
  whole-cell overview's, and it reads more naturally as part of the CellSurvey analysis project than
  as a Data-Prospector artifact. If kept here, it stays as the "overview/QC preamble" that
  `DEVELOPMENT_LOG.md` §15.10 explicitly left open.

### Copy to both (shared, not moved)

- `scripts/preprocess_cellsurvey.py` — the clone needs it to regenerate `cells.csv`; Data Prospector
  needs it to feed `--config cellsurvey`. Keep it in both (they will drift apart over time; that is
  acceptable and expected for a fork).

### Drop from the clone (pipeline-specific, no meaning in the analysis project)

- The pipeline core (`app.py`, `pipeline.py`, `ideation.py`, `judging.py`, `realization.py`,
  `output.py`, `llm.py`, `parsing.py`, `sandbox.py`, `preflight.py`, `prompts.py`, `config.py`).
- `configs/` (no `PipelineConfig` base to import — the analysis scripts hardcode their own
  marker lists, so nothing imports from `configs/`).
- `Dockerfile` (the analysis runs on the host, not in a sandbox).
- `assets/` (pipeline figure).
- `inputs/*/task_report.md` (pipeline reports — though `cellsurvey_report/task_report.md` carries the
  domain framing; a distilled version could be copied instead).

## The `docs/DEVELOPMENT_LOG.md` decision

This is the one genuinely consequential choice. `DEVELOPMENT_LOG.md` is ~1900 lines, ~95% about the
Data-Prospector *pipeline* (converger→diverger conversion, D1–D7, live issues, the §15 failure
taxonomy). Only rev. 92/95/96 and §15.9/15.10 are about CellSurvey.

Recommendation: **`git rm docs/DEVELOPMENT_LOG.md` (and `DEVELOPMENT_LOG_ARCHIVE.md`, `BACKLOG.md`)
from the clone's working tree**, and write a short, focused README/notes for CellSurveyThymusAnalysis
that pulls in just the CellSurvey-relevant findings (dead CD68, the debris population, the
overview-before-analysis lesson). The commit history still contains the full log, so nothing is lost.

## Rename surface

If the clone becomes `CellSurveyThymusAnalysis`:

- `pixi.toml` `name` (currently the odd `"agents"`) and the environment name — note the env name is
  tied to `.pixi/envs/` on disk, so a rename requires a `pixi install` re-run (same caveat rev. 64
  already recorded for the `diverger` env).
- `README.md` — rewrite for the analysis project (drop the "Data Prospector" framing, the pipeline
  diagram, the config table).
- `CLAUDE.md` — either drop it or rewrite it as the analysis project's own briefing.
- `LICENSE` — keep (GPL-3.0).
- GitHub repo name — done in the GitHub UI / `gh repo create`.

## Execution checklist (for the agent doing the split)

1. Confirm the three open decisions below with the human.
2. `git clone <this repo> <cell-survey-thymus-analysis>` (clone to a sibling directory).
3. In the clone: `git rm` everything in "Drop from the clone" + per the DEVELOPMENT_LOG decision;
   copy in `scripts/preprocess_cellsurvey.py` if not already there; rewrite `README.md`/`pixi.toml`/
   `CLAUDE.md`; commit.
4. In this repo: `git rm` the files marked "Move to CellSurveyThymusAnalysis"; commit.
5. Regenerate data + figures in the clone: `pixi run python scripts/preprocess_cellsurvey.py
   --whole-cell`, then the overview script, then `make_report_html.py`.
6. Verify neither repo references files it no longer has (e.g. the clone's analysis scripts must not
   import from `configs/`).

## Open decisions (need a human answer before executing)

1. **Move scope** — whole-cell only, or whole-cell **plus** the nuclear `overview_analysis.py`/`.md`?
   (Recommended: move both overviews; keep only `pd1pdl1_threshold_sensitivity.py` here.)
2. **`docs/DEVELOPMENT_LOG.md`** — drop from the clone's working tree (recommended) or keep it in full?
3. **Clone project name** — `CellSurveyThymusAnalysis`, or something narrower (e.g.
   `CellSurveyWholeCellAnalysis`) if only the whole-cell work moves?

See `CLAUDE.md` (this repo) for the pointer that hands this plan to the next agent.
