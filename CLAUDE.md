# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **diverger**: given a task report and a dataset, it fans out many independent, LLM-generated analytical
**angles** (hypotheses about the data), judges each one for non-obviousness and soundness, selectively
realises the top-ranked few into Docker-verified Python scripts, and writes the result up as a tiered
markdown **gallery** — not a single "best" script. The goal is a skimmable spread of distinct, defensible,
non-obvious leads for a human to evaluate, not one winning analysis (see `DIVERGER_PLAN.md` §1 for the
full rationale — this fork inverted a converger that hill-climbed toward one script). The pipeline itself
(`pipeline.py`) never changes per use case; only the domain config and input data do.

**In practice this is a CBIAS research instrument, not a proven template.** `cbias_config.py` is the only
domain config that has ever been run — every calibrated threshold, prompt, and piece of tuning in
`DIVERGER_PLAN.md` is CBIAS-shaped. `bioimage_config.py` and `trello_config.py` still satisfy
`PipelineConfig` and import cleanly, but neither has ever produced a real run, and `app.py`'s bare-default
invocation (no `--config`) selects `bioimage_config`, whose default report/data paths do not exist in this
repository — that default is currently broken. Pass `--config cbias` explicitly.

## Commands

Dependency management is via **pixi**, not pip/requirements.txt (the README's `pip install -r
requirements.txt` is aspirational — no requirements.txt exists in the repo).

```bash
pixi install                              # install/sync the environment from pixi.toml/pixi.lock
pixi run python app.py --config cbias     # run the pipeline against the CBIAS domain config
pixi run python app.py --config cbias --report <path> --data-dir <path> --output-dir ./outputs \
    --max-iterations 2 --angles-per-iteration 12 --realize-top-k 4   # explicit defaults, for reference
```

Docker is required for the execution-validation step of the pipeline (not for running `app.py` itself):

```bash
docker build --target cbias-analysis -t cbias-analysis:latest .   # the image cbias_config.py uses
```

Without a running Docker daemon, `execute_script_in_docker` returns `None`, `validate_execution` reports
`SKIPPED` (never silently reported as `PASS`), and every angle that would have been realised ends up
`not_realisable` instead — no code is graded without a verified sandbox run.

There is no test suite, linter config, or CI in this repo currently — the closest thing to an oracle is
the Docker exit code (`validate_execution`, grounded in the container's exit code, no LLM involved); there
is no oracle for angle *quality* by design — that's the human reading the gallery.

`ANTHROPIC_API_KEY` must be set (`.env` file, loaded via `python-dotenv`, or exported in the shell).
`cbias_config.py` routes its `worker_model`/`compiler_model` to DeepSeek, which additionally needs
`DEEPSEEK_API_KEY` and `DEEPSEEK_BASE_URL` — those two roles are mechanical/high-volume and
oracle-protected by Docker, so they don't need a frontier model; ideation and judging do, and stay on
Anthropic models (see `DIVERGER_PLAN.md` §5 for the full per-role tiering rationale).

## Architecture

### Pipeline flow (`pipeline.py`, `generate_and_optimize`)

```
criteria split (1 call, once) → ideate (fan-out, N angles/iteration × max_iterations)
  → judge (insight + soundness, every angle) → dedup (measurement only, not acted on)
  → rank → realise top-k (orchestrate → workers → compile/execute loop → realisation judge)
  → gallery
```

- **Criteria split**: one `CRITERIA_PROMPT` call distills the raw report into two separate rubrics —
  `<ideation_criteria>` (guiding questions, stakeholders, anti-targets, data-availability constraints) and
  `<deliverable_rubric>` (script-delivery mechanics: what a realised script must actually do). This is
  what keeps the pipeline domain-agnostic and keeps ideation from paying attention on delivery-mechanics
  text that has nothing to do with idea quality. A missing/malformed/identical-tag response falls back
  loudly (a printed `WARNING`, not a silent default) to using the raw report for both.
- **Ideation** (`generate_angles`, fanned out via `asyncio.gather` in `generate_and_optimize`): each
  iteration fires `angles_per_iteration` fully independent one-angle calls in parallel — independent
  samples diverge more than one call asked for N ideas at once. Two cycling axes give intra-iteration
  diversity (`design_stances`, the guiding questions parsed out of the report), each offset by iteration
  so no slot repeats its own inputs. Cross-iteration diversity comes from `{existing_angles}` — the whole
  archive generated so far, fed back into the prompt suffix (it grows every iteration, so it must never be
  cached — see the caching table below). Angle schema (`_ANGLE_FIELDS`): `id`, `hypothesis`,
  `variables_involved`, `question_or_stakeholder_served`, `why_non_obvious`, `rough_method`, `requires`.
  `requires` is **instrumentation only** — it tracks what libraries an angle reaches for and feeds §10's
  provisioning decisions, but availability is a *realisation* constraint, never fed back to narrow
  ideation itself.
- **Judging** (`judge_insight`, `judge_soundness`, D5): every archived angle — not just a
  pre-filtered subset — is scored by two independent judges sharing one cached prefix. `judge_insight`
  returns a continuous `insight_score` (non-obviousness, grounded in the anti-target list, not the
  angle's own self-assessment). `judge_soundness` returns a three-way verdict — `solid` / `caveat` /
  `unsupportable` — plus reasoning and (for `caveat`/`unsupportable`) a caveat string carried through to
  the gallery. **Graded, not gated**: nothing is filtered out at this stage, and `solid` has been
  essentially unreachable on this dataset's sample sizes — treat that as a property of the data, not a
  prompt-tuning target.
- **Dedup** (`_dedup_angles`, D4 — **currently measurement-only**, Live Issue 24): clusters the judged
  archive by token-set Jaccard similarity over `hypothesis`/`variables_involved`/`rough_method`
  (`angle_similarity_threshold`, calibrated to 0.22) and logs what it *would* merge — but
  `generate_and_optimize` no longer acts on the result; `all_angles` is built from the full archive.
  This is a deliberate interim, not an oversight: dedup's original justification (saving downstream
  judging cost) disappeared once judging moved before it, several merges have since been shown to be
  false positives that removed real coverage, and the measurement is being kept running to decide whether
  to delete it outright or replace it with something semantic. See `DIVERGER_PLAN.md`'s Live Issue 24 for
  the live decision and its evidence.
- **Rank + select**: the full (undeduped) archive is sorted by `_judgment_sort_key` (soundness tier first,
  then insight). `--realize-top-k` (default 4) non-`unsupportable` angles get realised; everything else
  appears one line each in the gallery's closing "also generated" section, with full detail in the
  sibling `surfaced_angles_<ts>.md` dump.
- **Realise** (`_run_one_design`, D6, one call chain per selected angle): orchestrator designs a minimal
  architecture for *this one angle* (its hypothesis/variables/rough_method, not the whole report) →
  workers implement each function in parallel (`asyncio.gather(..., return_exceptions=True)` — one
  worker's failure degrades to a placeholder body rather than losing the other functions or the whole
  angle) → compile → Docker-execute → feedback loop (`max_compile_attempts`, default 3; aborts early if
  an error repeats verbatim, since that means the compiler is cycling, not repairing) → realisation
  judge (`validate_realization`) only on a verified execution PASS. The whole function body is wrapped in
  one `try`/`except` so an infrastructure failure at *any* stage still returns whatever real output
  exists rather than unwinding and getting mislabelled upstream.

### The five realisation outcomes — never conflate them

`realization_status` on a realised angle is exactly one of:

- **`realised`** — executed, and the claimed pattern was legibly shown.
- **`realised_null`** — executed and rendered legibly, but the data do **not** support the claimed
  pattern. A clean disconfirmation, not a failure — ranks *alongside* `realised` in the gallery, not
  beneath it, and is often the more useful result of the two.
- **`pattern_not_shown`** — executed, but the output doesn't legibly show anything about the claim either
  way (broken/blank/unreadable plot, or an unparseable judge response). The actual quality-failure
  outcome — deliberately not called "unsound", which is D5's soundness vocabulary answering a different
  question (can the *data* support this claim at all, before any code is written).
- **`not_realisable`** — never executed after exhausting compile attempts (e.g. a missing library), or
  execution was unverifiable (no `data_dir` / Docker unavailable). An **engineering/provisioning**
  outcome — shown with its `requires` field, since that's the signal for what to provision next.
- **`realization_error`** — the pipeline broke on this angle for an infrastructure reason at some stage
  (orchestrator/workers/compile/validate), unrelated to angle quality *or* provisioning. Kept strictly
  separate from `not_realisable` in the gallery and never shown with `requires` — labelling an
  infrastructure hiccup as a provisioning gap would misdirect a reader.

The gallery (`_write_gallery`, D7) renders these as five tiers: `realised`/`realised_null` together at
the top (ranked by **insight**, not soundness or realisation order — the highest-insight angles disconfirm
at least as often as they confirm, so a soundness-first sort would bury the most interesting result under
the safest one), then `pattern_not_shown`, then `realization_error`, then `not_realisable`, then
`unsupportable` (angles that never reached realisation at all, shown with their soundness reasoning —
knowing what the dataset can't support is itself a finding).

`delivered_score` (a rubric-compliance number computed by `validate_realization`) exists but is
**deliberately never displayed** in the gallery — across five separate runs it has been anti-correlated
with actual worth (e.g. a script that silently dropped half its data scoring `1.00`, the same run's best
result scoring `0.71`). `pattern_reasoning` is the gallery's real quality signal; trust the judges'
reasoning, not their scores.

### Docker sandboxing (`execute_script_in_docker`)

LLM-generated code is untrusted and is executed with `DOCKER_SANDBOX_FLAGS`: no network, capped
memory/CPU, read-only root filesystem (with a `tmpfs` for `/tmp`, `HOME`, and `MPLCONFIGDIR` since
matplotlib/font caches need somewhere writable), dropped capabilities, non-root user, and a process
limit. Treat these flags as a security boundary — don't loosen them without good reason.

### Adding a new domain

The pipeline is retargeted entirely through `PipelineConfig` (`config.py`) — no changes to `pipeline.py`
are needed. A domain config module must provide:

- `orchestrator_model`, `judge_model` — frontier Anthropic tier; with `req_score` gone, `judge_insight`
  and `judge_soundness` *are* the entire quality bar.
- `worker_model`, `compiler_model` — mechanical/high-volume and Docker-oracle-protected, so a cheap tier
  is fine (`cbias_config.py` routes these to DeepSeek — see Commands above for the extra env vars that
  needs).
- `angle_model` — cheap tier; volume matters more than polish here, since dedup/judges filter downstream.
- `requirements_evaluator_model` — used for the criteria-split call *and* `validate_realization`; **must
  be vision-capable**, since the realisation judge is passed the angle's actual PNG artifacts.
- `docker_image` — must already exist locally (built from a `Dockerfile` target with the domain's
  libraries pre-installed) and must match `available_libraries`, since the generated script is restricted
  to exactly what's installed in that image. Library availability is a *realisation* constraint —
  ideation never sees `available_libraries` and must not be narrowed to fit the image.
- `available_libraries`, `domain_notes` — free-text constraints injected into worker, compiler, *and*
  orchestrator prompts (all three need the real data layout to design/repair against; see the caching
  table below for which prefix each lands in). `domain_notes` is an interface, not a comment — a single
  wrong line in it can produce near-identical silent failures across multiple independently generated
  scripts (`DIVERGER_PLAN.md` Live Issue 25). Prefer "inspect the actual data before assuming X" phrasing
  over listing specific exceptions, which generalises to cases you haven't seen yet.
- `extract_input_metadata(data_dir) -> str` — scans the input directory and returns a description fed to
  ideation and the orchestrator (e.g. `cbias_config.py` summarizes the CSV/text layout under `data_dir`).
- `design_stances: list[str]` (optional — defaults to `DEFAULT_DESIGN_STANCES` in `config.py`). Ideation
  call `m` within an iteration gets `design_stances[(m + iteration) % len(...)]` as a one-line
  "Approach for this design:" steer (e.g. conventional/robust, depth-first, contrarian).
- `angle_similarity_threshold` (optional, defaults to the calibrated `0.22` in `config.py`) — the dedup
  Jaccard cutoff. Currently measurement-only everywhere (see Dedup above), so changing it per-domain has
  no behavioural effect until that interim is resolved.

Then wire the new config into `app.py`'s `--config` choices.

### Structured I/O convention

All system/message prompt templates (`ANGLE_GENERATION_*`, `INSIGHT_JUDGE_*`, `SOUNDNESS_JUDGE_*`,
`ORCHESTRATOR_*`, `WORKER_*`, `COMPILER_*`, `REALIZATION_VALIDATOR_*`, `CRITERIA_PROMPT`, and their
`*_SYSTEM` counterparts) live in `prompts.py`, imported into `pipeline.py` via `from prompts import *`.
`pipeline.py` itself holds no prompt text — only orchestration logic and parsing.

**`ANGLE_GENERATION_*`, `INSIGHT_JUDGE_*`, and `SOUNDNESS_JUDGE_*` are human-owned.** Do not rewrite them
directly — propose changes and let a human make them. Judge-prompt wording is the actual product here;
the machinery around it is comparatively trivial (`DIVERGER_PLAN.md` §8).

Most prompts that repeat across several calls are split into a prefix/suffix pair so the prefix can be
cached via `llm_call`'s `cache_prefix` argument instead of repaying full price every call. **The rule:
anything identical across the calls sharing a cache goes in the prefix; anything that varies goes in the
suffix** — a growing accumulator (like `{existing_angles}`) in the prefix would invalidate the cache every
call while looking correct.

| Stage | Prefix (cached) | Suffix (varies) |
|---|---|---|
| Ideation | `report`, ideation criteria, `input_data`, anti-targets | `stance`, `guiding_question`, `existing_angles`, `n` |
| Judging (`judge_insight`/`judge_soundness`) | `report`, ideation criteria, `input_data` | the individual angle |
| Realisation orchestrator | `report` (the true report, not the angle brief), `input_data`, deliverable rubric, `domain_notes` | the angle being realised |
| Realisation workers (`_call_worker`) | `report`, `input_data`, `available_libraries`, `domain_notes` | function/description/input/output |
| Realisation compiler (`compile_script`) | `analysis`, `functions` (the orchestrator/worker output being assembled), `available_libraries`, `domain_notes`, seed section (currently always empty — see note below) | `error_feedback` from the prior compile attempt |
| Realisation validator (`validate_realization`) | `report`, deliverable rubric | claimed pattern, angle scope, script, execution output, images |

`compile_script` still accepts a `seed_script` parameter (mutate-a-prior-script support, left over from
the converger's best-of-N seeding) but `_run_one_design` never passes one — every design is compiled from
scratch, and the seed section of `COMPILER_PROMPT_PREFIX` is always empty in current usage.

Parallel fan-out (ideation, and workers within one angle) defeats the cache on first use — N concurrent
calls all start before any of them has written the cache entry, so they all miss on iteration 1 and hit
only from iteration 2 onward. Expect this in cost figures; it isn't a caching bug.

All LLM prompts/responses use XML tags (`<angle>`, `<analysis>`, `<tasks>`, `<task>`, `<criteria>`,
`<ideation_criteria>`, `<deliverable_rubric>`, `<score>`, `<verdict>`, `<pattern_outcome>`,
`<pattern_reasoning>`, `<criterion met="...">`) parsed via `extract_xml()` / `_parse_xml_items()` in
`pipeline.py`, with regex/markdown-heading-based fallbacks if strict XML parsing fails (tolerating minor
formatting drift from the model). When editing prompts, preserve these tags — downstream parsing depends
on them.

### Generated-script conventions (enforced via prompts, not code)

Every compiled script is required (per `COMPILER_PROMPT_SUFFIX`) to start with `# -*- coding: utf-8 -*-`
and have `main()` call `sys.stdout.reconfigure(encoding='utf-8')` as its first line, so UTF-8 output
(emoji, special characters) is safe across platforms inside the Docker container. Scripts must fail loudly
rather than silently degrade — both for a whole-script no-op (missing data found and printed, then a
clean exit) and for a single dropped metric among several (compute it, or raise/warn unmissably naming
which one and why — never emit a silent `NA` and continue).

## Where the project's history lives

`DIVERGER_PLAN.md` is the living design/run/decision log for this fork — every calibrated threshold, live
issue, and run result is recorded there, not here. When debugging a specific behaviour (why a threshold is
what it is, why a status exists, what a prior run showed), check there before re-deriving it from the code.
