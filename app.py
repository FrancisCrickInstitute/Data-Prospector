"""Entry point for the multi-agent code-generation pipeline.

Supports multiple domain configs (bioimage, trello, etc.) via --config flag.
"""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

from pipeline import generate_and_optimize


async def main(report_path: str, data_dir: str, output_dir: str, max_iterations: int,
               designs_per_iteration: int, angles_per_iteration: int):
    """Run the pipeline on a task report with domain-specific configuration."""
    with open(report_path, 'r', encoding='utf-8') as f:
        report_content = f.read()

    final_script = await generate_and_optimize(
        report=report_content,
        config=CONFIG,
        data_dir=data_dir,
        max_iterations=max_iterations,
        output_dir=output_dir,
        designs_per_iteration=designs_per_iteration,
        angles_per_iteration=angles_per_iteration,
    )

    # TODO(diverger): D2 onward, generate_and_optimize returns a text summary of generated angles,
    # not a script - this still writes it under analysis_script_<ts>.py (misleading filename/
    # extension) so the write path stays untouched. D7 formally ripples the real structured
    # gallery result into app.py per DIVERGER_PLAN.md; deliberately not anticipated here.
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = Path(output_dir) / f"analysis_script_{timestamp}.py"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_script)

    print("\n" + "=" * 80)
    print("FINAL COMPILED SCRIPT")
    print("=" * 80)
    print(f"\nScript saved to: {output_file}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Multi-agent code-generation pipeline"
    )
    parser.add_argument(
        "--config",
        default="bioimage",
        choices=["bioimage", "trello", "cbias"],
        help="Domain configuration to use (default: bioimage)"
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
        "--designs-per-iteration",
        type=int,
        default=3,
        help="D1/pre-D2 relic: unused as of D2 (ideation no longer generates full designs). "
             "Kept only as a CLI-compatible no-op and as the default reference point for "
             "--angles-per-iteration below; re-roled in D6 as the top-k realized-angle count."
    )
    parser.add_argument(
        "--angles-per-iteration",
        type=int,
        default=12,
        help="Candidate analysis angles generated per iteration (default: 12 - deliberately "
             "higher than the old --designs-per-iteration default of 3, since ideation-only "
             "generation (D2) is much cheaper than full design + compile + Docker execution."
    )

    args = parser.parse_args()

    # Load config module
    if args.config == "bioimage":
        from bioimage_config import CONFIG
        report_default = "./inputs/report/report_20260710_202254.md"
        data_dir_default = "./inputs/images"
    elif args.config == "trello":
        from trello_config import CONFIG
        report_default = "./inputs/trello_reports/task_report.md"
        data_dir_default = "./inputs/trello_data"
    elif args.config == "cbias":
        from cbias_config import CONFIG
        report_default = "./inputs/cbias_report/task_report.md"
        data_dir_default = "./inputs/cbias_data_anon"
    else:
        raise ValueError(f"Unknown config: {args.config}")

    # Use defaults if not specified
    report_path = args.report or report_default
    data_dir = args.data_dir or data_dir_default

    asyncio.run(main(report_path, data_dir, args.output_dir, args.max_iterations,
                     args.designs_per_iteration, args.angles_per_iteration))
