"""Entry point for the multi-agent code-generation pipeline.

Supports multiple domain configs (bioimage, trello, etc.) via --config flag.
"""

import argparse
import asyncio
import sys

from pipeline import generate_and_optimize
from preflight import run_preflight


async def main(report_path: str, data_dir: str, output_dir: str, max_iterations: int,
               realize_top_k: int, angles_per_iteration: int, skip_preflight: bool = False):
    """Run the pipeline on a task report with domain-specific configuration."""
    # Live Issue 29: verify every configured model is reachable and Docker is available before
    # committing this run's ~25-110 LLM calls (Run 35 spent a full run finding out Docker was
    # down only at the very end, with zero verified output to show for it). Hard-stops rather
    # than warning-and-continuing, on the same "fail loudly, not silently degrade" convention the
    # generated scripts themselves are held to - --skip-preflight is the deliberate opt-out for
    # e.g. testing ideation/judging only with Docker known to be unavailable.
    if not skip_preflight and not await run_preflight(CONFIG, report_path, data_dir):
        sys.exit(
            "Preflight check failed - see the [preflight] report above for which check(s) and "
            "why. Fix the problem, or pass --skip-preflight to run anyway (e.g. deliberately "
            "testing ideation/judging only, with Docker known to be unavailable)."
        )

    with open(report_path, 'r', encoding='utf-8') as f:
        report_content = f.read()

    result = await generate_and_optimize(
        report=report_content,
        config=CONFIG,
        data_dir=data_dir,
        max_iterations=max_iterations,
        output_dir=output_dir,
        realize_top_k=realize_top_k,
        angles_per_iteration=angles_per_iteration,
    )

    # D7: generate_and_optimize returns a structured result (all_angles + the paths it wrote),
    # not a script or a plain-text blob - there is nothing left for app.py to write itself. The
    # gallery is the deliverable; this is just pointing the user at it and the two files/dir that
    # sit alongside it for anyone who wants the full detail behind the skim.
    print("\n" + "=" * 80)
    print("RUN COMPLETE")
    print("=" * 80)
    print(f"\n{len(result['all_angles'])} angle(s) surfaced this run.")
    if result["gallery_path"]:
        print(f"Gallery:         {result['gallery_path']}")
    if result["dump_path"]:
        print(f"Surfaced angles: {result['dump_path']}")
    if result["scripts_dir"]:
        print(f"Scripts:         {result['scripts_dir']}")
    if not result["gallery_path"]:
        print("(No output_dir given, so nothing was written to disk - see the console log above.)")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Multi-agent code-generation pipeline"
    )
    parser.add_argument(
        "--config",
        default="cbias",
        choices=["bioimage", "trello", "cbias", "idr0028", "cellsurvey"],
        # cbias is the only config with sample data in this repo and an existing Docker image
        # target - bioimage_config's default paths don't exist here (docs/DEVELOPMENT_LOG.md
        # D-consolidate item 3). Was "bioimage" until that was flagged as a broken default.
        help="Domain configuration to use (default: cbias)"
    )
    parser.add_argument(
        "--report",
        help="Path to task report file"
    )
    parser.add_argument(
        "--data-dir",
        help="Path to input data directory"
    )
    parser.add_argument(
        "--output-dir",
        default="./outputs",
        help="Path to output directory for generated script"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=2,
        help="Maximum ideation iterations (default: 2). Each iteration generates "
             "angles-per-iteration candidate angles as text (D2) - no code, no Docker."
    )
    parser.add_argument(
        "--realize-top-k",
        type=int,
        default=4,
        help="D6: how many of the top-ranked, non-unsupportable judged angles to actually write "
             "and run code for (default: 4). Selective execution - the rest of the archive is "
             "judged as text only, never compiled or run."
    )
    parser.add_argument(
        "--angles-per-iteration",
        type=int,
        default=12,
        help="Candidate analysis angles generated per iteration (default: 12 - deliberately "
             "higher than the pre-D6 --designs-per-iteration default of 3, since ideation-only "
             "generation (D2) is much cheaper than full design + compile + Docker execution."
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip the startup check that every configured model is reachable and Docker is "
             "available (Live Issue 29). Use this to deliberately run ideation/judging only "
             "with Docker known to be unavailable; otherwise leave it on so a bad key, a stale "
             "model string, or a down daemon fails fast instead of after ~25-110 wasted calls."
    )

    args = parser.parse_args()

    # Load config module. Wrapped in try/except: --config's choices=[...] above already catches a
    # typo'd config name before this point, but not a listed config whose module file is itself
    # missing or broken (e.g. renamed/deleted configs/*.py) - without this, that fails here with a
    # raw ImportError traceback instead of a clear, actionable message.
    try:
        if args.config == "bioimage":
            from configs.bioimage_config import CONFIG
            report_default = "./inputs/report/report_20260710_202254.md"
            data_dir_default = "./inputs/images"
        elif args.config == "trello":
            from configs.trello_config import CONFIG
            report_default = "./inputs/trello_reports/task_report.md"
            # The ANONYMISED export (see _anonymise_trello.py) - not the raw inputs/trello_data/,
            # which was removed from the repo (docs/DEVELOPMENT_LOG.md) and is now gitignored,
            # matching the cbias branch below.
            data_dir_default = "./inputs/trello_data_anonymised"
        elif args.config == "cbias":
            from configs.cbias_config import CONFIG
            report_default = "./inputs/cbias_report/task_report.md"
            data_dir_default = "./inputs/cbias_data_anon"
        elif args.config == "idr0028":
            from configs.idr0028_config import CONFIG
            report_default = "./inputs/idr0028_report/task_report.md"
            # The PROCESSED derivative (see scripts/preprocess_idr0028.py) - not the raw
            # inputs/idr0028/, which this config's DOMAIN_NOTES doesn't describe and which the
            # pipeline was never meant to join itself. Run scripts/preprocess_idr0028.py first if
            # this directory doesn't exist yet.
            data_dir_default = "./inputs/idr0028_processed"
        elif args.config == "cellsurvey":
            from configs.cellsurvey_config import CONFIG
            report_default = "./inputs/cellsurvey_report/task_report.md"
            # The PROCESSED derivative (see scripts/preprocess_cellsurvey.py) - not the source zarr
            # on the remote Z: path, which this config's DOMAIN_NOTES doesn't describe and which the
            # pipeline was never meant to read itself. Run scripts/preprocess_cellsurvey.py first if
            # this directory doesn't exist yet (needs the Z: network path mounted and reachable).
            data_dir_default = "./inputs/cellsurvey_processed"
        else:
            raise ValueError(f"Unknown config: {args.config}")
    except ImportError as e:
        sys.exit(
            f"Could not load config '{args.config}': {e}. Check that "
            f"configs/{args.config}_config.py exists and imports cleanly."
        )

    # Use defaults if not specified
    report_path = args.report or report_default
    data_dir = args.data_dir or data_dir_default

    asyncio.run(main(report_path, data_dir, args.output_dir, args.max_iterations,
                     args.realize_top_k, args.angles_per_iteration, args.skip_preflight))
