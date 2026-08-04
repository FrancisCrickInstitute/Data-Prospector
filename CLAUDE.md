3# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A reusable, domain-agnostic pipeline that uses Claude models in an orchestrator/worker/compiler/evaluator
pattern to generate, validate, and iteratively refine a **standalone Python analysis script** — not to
write general-purpose application code. The pipeline itself (`pipeline.py`) never changes per use case;
only the domain config (`bioimage_config.py`, `trello_config.py`, etc.) and input data change.

## Commands

Dependency management is via **pixi**, not pip/requirements.txt (the README's `pip install -r
requirements.txt` is aspirational — no requirements.txt exists in the repo).

```bash
pixi install                    # install/sync the environment from pixi.toml/pixi.lock
pixi run python app.py          # run the pipeline (bioimage config by default)
pixi run python app.py --config trello        # run against the Trello domain config
pixi run python app.py --config bioimage --report <path> --data-dir <path> --output-dir ./outputs --max-iterations 5
```

Docker is required for the execution-validation step of the pipeline (not for running `app.py` itself):

```bash
docker build -t bia-analysis:latest .    # build the sandbox image used by bioimage_config.py
```

Without a running Docker daemon, `execute_script_in_docker` returns `None` and the pipeline skips the
run step, evaluating code quality only (see `validate_execution` in `pipeline.py`).

There is no test suite, linter config, or CI in this repo currently.

`ANTHROPIC_API_KEY` must be set (`.env` file, loaded via `python-dotenv`, or exported in the shell).

## Architecture

### Pipeline flow (`pipeline.py`)

```
Criteria extraction (1 call, once)  →  Orchestrator (1 call)  →  Workers (parallel, 1 call per function)  →  Compiler+Execution loop  →  Requirements Evaluator
```

- **Criteria extraction**: before any design work starts, `generate_and_optimize` makes a single
  `CRITERIA_PROMPT` call that distills the raw report into a `<criteria>` rubric — the concrete,
  checkable success conditions the report actually states. This runs once per pipeline invocation
  (not per design, not per iteration) and the resulting `criteria` string is threaded into both the
  orchestrator and requirements-validator prompts below. This is what makes the pipeline genuinely
  domain-agnostic: without it, those two prompts would have to hardcode one report's specific shape of
  "success" (a fixed metric count, PNG count, `load_data()`/`main()`-only architecture) as if it were
  universal, which silently pre-decides every axis a design could vary on and defeats the purpose of
  swapping in a new `PipelineConfig` for a different domain.
- **Orchestrator**: given the task report + criteria + input metadata, designs a minimal architecture to
  satisfy exactly what the criteria calls for — no more, no less — typically `load_data()` and `main()`,
  but not hardcoded to only that shape (see `ORCHESTRATOR_PROMPT_PREFIX`/`_SUFFIX`). Returns an `<analysis>` block and a
  `<tasks>` list parsed by `parse_tasks()`.
- **Workers**: one parallel LLM call per task (`asyncio.gather` in `_call_worker`), each implementing a
  single function to spec with no helpers, no defensive try/except.
- **Compiler + execution loop** (`_run_one_design`): compiles worker output into one script
  (`compile_script`), then runs it in a sandboxed Docker container (`execute_script_in_docker`).
  `validate_execution` is grounded directly in the container's exit code — no LLM judges this step —
  and returns `PASS`/`FAIL`/`SKIPPED` (`SKIPPED` when no `data_dir` was given or Docker is unavailable;
  it is never reported as `PASS`, since nothing was actually verified to run). Retries up to
  `max_compile_attempts` (default 3) on `FAIL`, feeding the execution error back into the next compile
  attempt; `SKIPPED` is terminal too (there's no error to fix, so retrying wastes attempts).
- **Requirements Evaluator**: only runs after a verified execution `PASS`. A `SKIPPED` execution
  short-circuits straight to a failed candidate (`req_pass=False`, `req_score=0.0`) without a judge
  call, since there's no real output to grade. When it does run, it checks the script's actual output
  against every item in the extracted criteria, using the *actual on-disk file listing*, not just what
  the code claims to write (`_format_artifacts` flags 0-byte files as suspect). It returns a graded
  `req_score` (met/total across every `<criterion>` tag, 0.0 if none were emitted) alongside the
  boolean `req_pass`, so candidates can be ranked even when none pass outright.

### Best-of-N outer loop (`generate_and_optimize`)

Each iteration fans out `designs_per_iteration` (default 3) fully independent design attempts in
parallel via `_run_one_design`, each writing its artifacts to its own
`outputs/artifacts/iter_N/design_M/` subdirectory to avoid clobbering. Candidates are ranked by
`_candidate_score` — a lexicographic tuple `(exec_pass, req_score)` — so a Docker-verified execution
pass always outranks the noisier LLM requirements judgment, and `req_score` (graded met/total against
the extracted rubric, not just the boolean `req_pass`) breaks ties with a real gradient, including
between designs that both fail outright.

Every design's outcome — winners, losers, and exceptions alike — is recorded as a one-line entry
(`_journal_entry`) in `feedback_history` at the end of each iteration: label, one-line approach summary,
exec/requirements verdict, valid artifact count, and (for failures) the specific reason. The full
accumulated journal is passed into the next iteration's orchestrator prompt. This is deliberate: it
stops the model from oscillating (fixing issue A by reintroducing issue B) by making every orchestrator
redesign aware of everything tried so far, not just what went wrong most recently.

The single best candidate seen across *all* iterations (`best_candidate`, via `record_candidate`) is
returned even if the loop exhausts `max_iterations` without a pass — not just whatever the final
iteration produced.

**Archive + seed mutation**: every design that executes successfully (`exec_pass`) is added to a flat,
score-ranked `archive` capped at the top 5 candidates (`update_archive`). From the second iteration
onward, design 0 is seeded by mutating the best archived script (`pick_best_seed`) and design 1 (if
`designs_per_iteration >= 2`) mutates a different, randomly chosen archived script (`pick_other_seed`)
for diversity; any remaining designs stay from-scratch. A seeded design's orchestrator and compiler
prompts are told to *improve* the seed rather than redesign from nothing — this is mutation, not a
diff/patch. It's safe because the same Docker oracle in the compile/execute loop still catches any
regression the mutation introduces, exactly as it would for a from-scratch design; a regressed mutation
simply loses on `_candidate_score` and never overwrites a better archived node. This is orthogonal to
the `design_stances` cycling below — a design gets both a stance and (possibly) a seed.

### Docker sandboxing (`execute_script_in_docker`)

LLM-generated code is untrusted and is executed with `DOCKER_SANDBOX_FLAGS`: no network, capped
memory/CPU, read-only root filesystem (with a `tmpfs` for `/tmp`, `HOME`, and `MPLCONFIGDIR` since
matplotlib/font caches need somewhere writable), dropped capabilities, non-root user, and a process
limit. Treat these flags as a security boundary — don't loosen them without good reason.

### Adding a new domain

The pipeline is retargeted entirely through `PipelineConfig` (`config.py`) — no changes to
`pipeline.py` are needed. A domain config module must provide:

- `orchestrator_model`, `worker_model`, `compiler_model`, `requirements_evaluator_model` — role-based
  model selection (see `bioimage_config.py` / `trello_config.py` for current model assignments: Opus 4.8
  for architecture, Sonnet 5/Haiku 4.5 for compilation/implementation/evaluation). There is no
  `executor_evaluator_model` — execution pass/fail is grounded in the Docker exit code, not an LLM call.
- `docker_image` — must already exist locally (built from a `Dockerfile` with the domain's libraries
  pre-installed) and must match `available_libraries`, since the generated script is restricted to
  exactly what's installed in that image.
- `available_libraries`, `domain_notes` — free-text constraints injected into every worker/compiler
  prompt.
- `extract_input_metadata(data_dir) -> str` — scans the input directory and returns a description fed to
  the orchestrator (e.g. `bioimage_config.py` reads TIFF shape/channel metadata via `bioio.BioImage`;
  `trello_config.py` summarizes JSON export structure).
- `design_stances: list[str]` (optional — defaults to `DEFAULT_DESIGN_STANCES` in `config.py`, so no
  domain config needs to set it). Design `m` within an iteration gets `design_stances[m % len(...)]`,
  injected into its orchestrator prompt as a one-line "Approach for this design:" steer (e.g.
  conventional/robust, depth-first, contrarian) so the `designs_per_iteration` parallel designs explore
  different regions of the solution space with no extra LLM calls.

Then wire the new config into `app.py`'s `--config` choices. Note: `trello_config.py` currently
references a `python-analysis:latest` Docker image that this repo's `Dockerfile` does not build (it
defines `bia-analysis` and `cbias-analysis` targets, not `python-analysis`) — building that image
yourself is a prerequisite for the trello config to validate execution.

### Structured I/O convention

All system/message prompt templates (`ORCHESTRATOR_PROMPT_PREFIX`/`ORCHESTRATOR_PROMPT_SUFFIX`,
`WORKER_PROMPT_PREFIX`/`WORKER_PROMPT_SUFFIX`, `COMPILER_PROMPT_PREFIX`/`COMPILER_PROMPT_SUFFIX`,
`REQUIREMENTS_VALIDATOR_PROMPT_PREFIX`/`REQUIREMENTS_VALIDATOR_PROMPT_SUFFIX`, `CRITERIA_PROMPT`, and
their `*_SYSTEM` counterparts) live in `prompts.py`, imported into `pipeline.py` via
`from prompts import *`. `pipeline.py` itself holds no prompt text — only the orchestration logic and
the parsing helpers below.

The orchestrator, worker, compiler, and requirements-validator prompts are each split into a
prefix/suffix pair so their callers can cache the prefix via `llm_call`'s `cache_prefix` argument,
instead of repaying full price for it on every call:
- `_run_one_design`'s orchestrator call: prefix is report/input_data/criteria, identical across every
  design and iteration in a run; suffix is feedback (grows each iteration)/stance/seed_section, which vary.
- `_call_worker`: prefix is report/input_data/library_notes/domain_notes, identical across every task in
  a design; suffix is function/description/input/output, which vary per task. Weakest of the four to
  actually hit cache, since same-iteration workers fire in parallel via `asyncio.gather` and mostly race
  past each other - it pays off reliably from the second iteration onward instead.
- `compile_script`: prefix is analysis/functions/library_notes/seed_section, identical across a
  design's sequential compile/execute retries; suffix is error_feedback + the fixed rules/instructions.
- `validate_requirements`: prefix is report + criteria, identical across every design's validation call
  in an entire run; suffix is the script/execution output, which vary per design.

All LLM prompts/responses use XML tags (`<analysis>`, `<tasks>`, `<task>`, `<response>`, `<criteria>`,
`<criterion met="...">`, `<feedback>`) parsed via `extract_xml()` / `parse_tasks()` in `pipeline.py`,
with regex-based fallbacks if strict XML parsing fails (tolerating minor formatting drift from the
model). When editing prompts, preserve these tags — downstream parsing depends on them.

### Generated-script conventions (enforced via prompts, not code)

Every compiled script is required (per `COMPILER_PROMPT_SUFFIX`) to start with `# -*- coding: utf-8 -*-` and
have `main()` call `sys.stdout.reconfigure(encoding='utf-8')` as its first line, so UTF-8 output (emoji,
special characters) is safe across platforms inside the Docker container.