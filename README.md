# Diverger

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%203.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14+-green.svg)](https://www.python.org/downloads/)
[![Claude API](https://img.shields.io/badge/Claude-API-orange.svg)](https://www.anthropic.com)
[![Docker](https://img.shields.io/badge/Docker-containerized-blue.svg)](https://www.docker.com)

A pipeline that uses Claude to generate a **spread of distinct, defensible analytical angles** on a
dataset, rather than converging on one "best" script. Given a task report and input data, it fans out
many independent hypotheses, judges each for non-obviousness and soundness, selectively realises the
top-ranked few into Docker-verified Python scripts, and writes the whole run up as a tiered markdown
**gallery** for a human to skim and evaluate. There is no pass/fail oracle for idea quality — that
judgement belongs to the person reading the gallery, not the pipeline.

**This is currently a CBIAS research instrument, not a validated general-purpose template.** `cbias_config.py`
is the only domain config that has ever produced a real run; see [Adapting to a new domain](#adapting-to-a-new-domain)
for what that means for the other two configs shipped here.

## How it works

```
Task Report + Input Data
        ↓
Criteria split (once per run): report → <ideation_criteria> + <deliverable_rubric>
        ↓
┌─── Ideation (fanned out) ─────────────────────────────────────────────┐
│  max-iterations × angles-per-iteration independent one-angle calls,   │
│  each one hypothesis + variables + rough method + why it's non-obvious│
└─────────────────────────────────────────────────────────────────────┘
        ↓
Judging: every archived angle scored for insight (non-obviousness) AND
         soundness (solid / caveat / unsupportable) — graded, not gated
        ↓
Dedup (measurement only — logs near-duplicate clusters, doesn't remove them)
        ↓
Rank by soundness then insight → take the top `--realize-top-k`
        ↓
┌─── Realise (per selected angle) ──────────────────────────────────────┐
│  Orchestrator (architecture for THIS angle) → Workers (parallel,      │
│  one call per function) → Compiler → Docker execution                 │
│  (retried up to 3x on FAIL) → Realisation judge (does the output      │
│  legibly show the claimed pattern?)                                   │
└─────────────────────────────────────────────────────────────────────┘
        ↓
Gallery: realised/disconfirmed (top, by insight) → illegible → judge-failed
         → not realisable (provisioning gap) → unsupportable by the data
```

- **Selective execution**: code is only written and run for the `--realize-top-k` angles that rank best
  after judging — the rest of the archive stays text, judged but never compiled, and appears one line
  each in the gallery's closing summary.
- **Never one winner**: a clean disconfirmation (`realised_null`) ranks *alongside* a confirmation in the
  gallery, not beneath it — closing a question is often as useful as answering one, and burying the
  disconfirmations would defeat the point of running a diverger at all.
- **Five distinct outcomes per realised angle**, never conflated with each other: `realised`,
  `realised_null` (disconfirmed, not a failure), `pattern_not_shown` (a genuine quality failure — the
  output is illegible), `not_realisable` (an engineering/provisioning gap, e.g. a missing library — shown
  with what it needed), and `realization_error` (the pipeline itself broke on this angle, unrelated to the
  angle or the data — kept out of the provisioning tier so it doesn't misdirect what to provision next).
- **Role-based models**: a frontier Anthropic model for ideation-judging and realisation-orchestration (the
  two places quality is actually decided, now that no rubric-gate score exists), and a cheaper/high-volume
  tier for mechanical work — worker implementation and script compilation, both protected by the Docker
  execution check acting as a real oracle. Set per-role in each `*_config.py`; see `DIVERGER_PLAN.md` §5.
- **Containerized execution**: generated scripts run in a pre-built Docker image, sandboxed with no
  network access, capped memory/CPU, a read-only root filesystem, dropped capabilities, and a non-root
  user — both pinning dependencies and isolating untrusted LLM-generated code.
- **Structured I/O**: XML-tagged prompts/responses for reliable parsing and validation, with regex/markdown
  fallbacks that tolerate minor formatting drift.

## Adapting to a new domain

The pipeline itself (`pipeline.py`) never changes per use case — only the domain config and input data do.
Three domain configs currently exist, selected via `--config`:

| Config | Status |
|---|---|
| `cbias_config.py` | **The only one that has ever produced a real run.** Every calibrated threshold and tuned prompt in `DIVERGER_PLAN.md` is CBIAS-shaped. Sample input data ships in this repo (`inputs/cbias_report/`, `inputs/cbias_data_anon/`) and its Docker image target exists (`cbias-analysis`). |
| `trello_config.py` | Sample input data ships in this repo (`inputs/trello_reports/`, `inputs/trello_data/`), but it references a `python-analysis:latest` Docker image that the `Dockerfile` does not build — execution-validation has never actually been exercised for this config. |
| `bioimage_config.py` | Its default report/data paths (`inputs/report/`, `inputs/images/`) don't exist in this repo — no sample data ships for it, and no run has ever been done. No longer `app.py`'s default (see Flags below); pass `--config bioimage` only if you're supplying your own report/data. |

`PipelineConfig` (`config.py`) is the interface all three satisfy and the swap point for adding a fourth:

1. **Create a domain config** (e.g. `my_domain_config.py`):
   - Instantiate a `PipelineConfig` — see `config.py` for every field
   - Set the six model-role fields: `orchestrator_model`, `judge_model` (frontier — these two make the
     quality calls), `worker_model`, `compiler_model`, `angle_model` (cheap/high-volume, Docker- and
     judge-protected downstream), `requirements_evaluator_model` (must be vision-capable — it's passed
     the angle's actual PNG artifacts)
   - Define `available_libraries` (allowed imports for generated scripts) and `domain_notes`
     (domain-specific data-layout constraints) — treat `domain_notes` as an interface, not a comment; a
     single wrong line in it can silently break multiple independently generated scripts the same way
     (`DIVERGER_PLAN.md` Live Issue 25)
   - Provide `extract_input_metadata(data_dir)` — scans input files and returns a description fed to
     ideation and the orchestrator
   - Point `docker_image` at an image that **already exists locally** and matches `available_libraries`
   - Optionally override `design_stances` (defaults to `DEFAULT_DESIGN_STANCES` in `config.py`) or
     `angle_similarity_threshold` (defaults to `0.22`, currently inert everywhere — see Flags below)

2. **Update `app.py`**: add the new config to the `--config` choices.

3. **Update `Dockerfile`**: add a build target pre-installing the domain's required packages.

4. **Update `pixi.toml`** (optional): add the domain's Python dependencies.

See `cbias_config.py` for a concrete, fully working example.

## Setup

Requirements: [pixi](https://pixi.sh), Docker Desktop running, an Anthropic API key.

```bash
pixi install
docker build --target cbias-analysis -t cbias-analysis:latest .
```

Set `ANTHROPIC_API_KEY` — either export it in the shell or put it in a `.env` file (loaded automatically
via `python-dotenv`). `cbias_config.py` additionally routes its worker/compiler roles to DeepSeek, which
needs `DEEPSEEK_API_KEY` and `DEEPSEEK_BASE_URL` set the same way.

## Usage

### CBIAS symposium analysis

Sample report and anonymised input data already ship under `inputs/cbias_report/` and
`inputs/cbias_data_anon/`, so this runs out of the box:

```bash
pixi run python app.py --config cbias
```

### Flags

```
--config {bioimage,trello,cbias}   Domain configuration to use (default: cbias — the only config with
                                    sample data and a built Docker image in this repo; see Adapting to
                                    a new domain above)
--report PATH                      Path to task report file (defaults to the config's sample report)
--data-dir PATH                    Path to input data directory (defaults to the config's sample data)
--output-dir PATH                  Output directory for the gallery and its artifacts (default: ./outputs)
--max-iterations N                 Ideation iterations (default: 2). Each iteration generates
                                    angles-per-iteration candidate angles as TEXT ONLY — no code, no
                                    Docker — so this is cheap relative to realisation.
--angles-per-iteration N           Candidate angles generated per iteration (default: 12).
--realize-top-k N                  How many of the top-ranked, non-unsupportable judged angles to
                                    actually write and run code for (default: 4). Selective execution —
                                    the rest of the archive is judged as text only, never compiled or run.
```

At default settings that's `2 × 12 = 24` candidate angles generated and judged per run, with only the
top `4` actually compiled and executed — see `DIVERGER_PLAN.md` §12.4 for the full call-count/cost
breakdown.

The gallery is written to `outputs/gallery_<timestamp>.md`, alongside a sibling images directory and a
`surfaced_angles_<timestamp>.md` dump with full judge detail on every angle (not just the realised top-k).
Each realised angle's compiled script is written to `outputs/scripts/<timestamp>/<angle_id>.py` and linked
from its gallery entry.

### Notes

- Generated scripts are restricted to each config's pre-installed libraries — see `AVAILABLE_LIBRARIES`
  in the relevant `*_config.py` (for `cbias`: numpy, pandas, matplotlib, scipy, scikit-learn, nltk,
  seaborn, textstat, plus the standard library).
- Execution timeout: 300s per attempt, with up to 3 compile/execute retries per angle (both configurable
  in code), aborting early if an error repeats verbatim across attempts.
- Docker is required to validate execution — without it, every angle that would have been realised comes
  back `not_realisable` instead (reported honestly, never as a pass).
- No test suite, linter config, or CI currently exists in this repo — there is no oracle for angle
  *quality* by design; the Docker exit code is the only mechanical check, and the human reading the
  gallery is the rest of the test.
- `DIVERGER_PLAN.md` is the living design/run/decision log for this project — every calibrated threshold
  and known issue is recorded there.

## License

GPL-3.0 - See [LICENSE](LICENSE) for details.
