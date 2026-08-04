# Multi-Agent Code Generation Pipeline

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%203.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14+-green.svg)](https://www.python.org/downloads/)
[![Claude API](https://img.shields.io/badge/Claude-API-orange.svg)](https://www.anthropic.com)
[![Docker](https://img.shields.io/badge/Docker-containerized-blue.svg)](https://www.docker.com)

A reusable, domain-agnostic pipeline that uses Claude to generate, validate, and iteratively refine a **standalone Python analysis script**. Given a task report and input data, it extracts a success rubric, designs an architecture, implements it in parallel, assembles it, and runs a best-of-N search until a design passes validation.

## How It Works

```
Task Report + Input Data
        ↓
Criteria Extraction (distill the report into a checkable rubric — once per run)
        ↓
┌─── Best-of-N iteration ─────────────────────────────────────┐
│  N parallel designs, each:                                  │
│    Orchestrator (architecture design)                       │
│          ↓                                                  │
│    Workers (parallel implementation, one call per function) │
│          ↓                                                  │
│    Compiler → Docker execution  (retried up to 3x on FAIL)  │
│          ↓                                                  │
│    Requirements Evaluator (checks output against criteria)  │
└───────────────────────────────────────────────────────────┘
        ↓
  A design passes → Final Script
  None pass → journal every design's outcome → next iteration
```

- **Best-of-N per iteration**: each iteration fans out `designs_per_iteration` (default 3) fully
  independent designs in parallel and ranks them by execution pass, then requirements score. The best
  candidate seen across *all* iterations is kept even if the loop exhausts `max_iterations` without a
  full pass.
- **Seeded mutation**: once a design executes successfully it's added to a scored archive; later
  iterations can seed a new design by mutating a top archived script instead of always starting from
  scratch.
- **Role-based models**: Opus 4.8 (architecture), Sonnet 5 (compilation/evaluation), Haiku 4.5
  (implementation) — matched to task complexity. Swap per-domain in each `*_config.py`.
- **Containerized execution**: generated scripts run in a pre-built Docker image, sandboxed with no
  network access, capped memory/CPU, a read-only root filesystem, dropped capabilities, and a non-root
  user — both pinning dependencies and isolating untrusted LLM-generated code.
- **Structured I/O**: XML-tagged prompts/responses for reliable parsing and validation.

## Adapting to a New Domain

The pipeline itself (`pipeline.py`) never changes per use case — only the domain config and input data
do. Two domain configs currently ship with this repo, selected via `--config`: `bioimage_config.py`
(default) and `trello_config.py`.

To add a new one:

1. **Create a domain config** (e.g. `my_domain_config.py`):
   - Instantiate a `PipelineConfig` (see `config.py` for the interface)
   - Set `orchestrator_model`, `worker_model`, `compiler_model`, `requirements_evaluator_model`
   - Define `available_libraries` (allowed imports for the generated script) and `domain_notes`
     (domain-specific constraints for the LLM)
   - Provide `extract_input_metadata(data_dir)` — scans input files and returns a description fed to
     the orchestrator
   - Point `docker_image` at an image that **already exists locally** and matches `available_libraries`
   - Optionally override `design_stances` (defaults to `DEFAULT_DESIGN_STANCES` in `config.py`)

2. **Update `app.py`**: add the new config to the `--config` choices.

3. **Update `Dockerfile`** (if using different libraries): pre-install the domain's required packages.

4. **Update `pixi.toml`** (optional): add the domain's Python dependencies.

See `bioimage_config.py` for a concrete example.

## Setup

Requirements: [pixi](https://pixi.sh), Docker Desktop running, an Anthropic API key.

```bash
pixi install
docker build -t bia-analysis:latest .
```

Set `ANTHROPIC_API_KEY` — either export it in the shell or put it in a `.env` file (loaded
automatically via `python-dotenv`).

## Usage

### Bioimage analysis (default config)

Place a task report and sample TIFF images under `inputs/`:

```
inputs/report/report_YYYYMMDD_HHMMSS.md
inputs/images/*.tif
```

Then run:

```bash
pixi run python app.py
```

### Trello board analysis

```bash
pixi run python app.py --config trello --report <path> --data-dir <path>
```

Note: `trello_config.py` references a `python-analysis:latest` Docker image that this repo's
`Dockerfile` does not build (it defines `bia-analysis` and `cbias-analysis` targets, not
`python-analysis`) — build that image yourself before execution-validation will work for this config.

### Flags

```
--config {bioimage,trello}   Domain configuration to use (default: bioimage)
--report PATH                Path to task report file
--data-dir PATH               Path to input data directory
--output-dir PATH             Output directory for the generated script (default: ./outputs)
--max-iterations N            Max redesign iterations (default: 2)
--designs-per-iteration N     Parallel design attempts per iteration (default: 3); the
                               best-scoring one is kept. Set to 1 for a single design per iteration.
```

Total design attempts per run is `max-iterations x designs-per-iteration`, each with its own
orchestrator + worker + compiler calls — this multiplies fast, especially with Opus in those roles.

The final validated script is written to `outputs/analysis_script_<timestamp>.py`. Intermediate
per-design artifacts land under `outputs/artifacts/iter_N/design_M/`.

### Notes

- Generated scripts are restricted to pre-installed libraries: numpy, scipy, scikit-image,
  scikit-learn, pandas, bioio, bioio-tifffile, and standard library for bioimage; numpy, pandas,
  matplotlib, and standard library for trello.
- Execution timeout: 300s per attempt, with up to 3 compile/execute retries per design (both
  configurable in code).
- Docker is required to validate execution — without it, evaluation skips the run step (reported as
  `SKIPPED`, never as a pass) and checks code quality only.
- No test suite, linter config, or CI currently exists in this repo.

## License

GPL-3.0 - See [LICENSE](LICENSE) for details.