"""Docker sandbox execution for untrusted, LLM-generated scripts: the sandbox flags, running a
script and capturing its artifacts, the mechanical (non-LLM) execution-verdict backstop, and
reading produced PNGs back in for the realisation judge.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from config import PipelineConfig

# Sandbox flags for running untrusted, LLM-generated code. Docker here provides both
# dependency pinning AND isolation. Tune these if a host/platform rejects a flag.
DOCKER_SANDBOX_FLAGS = [
    "--network", "none",  # no network access
    "--memory", "1g",  # cap RAM
    "--memory-swap", "1g",  # == memory, so swap is disabled
    "--cpus", "2",  # cap CPU
    "--pids-limit", "256",  # limit processes (fork-bomb guard)
    "--read-only",  # read-only root filesystem
    "--cap-drop", "ALL",  # drop all Linux capabilities
    "--security-opt", "no-new-privileges",  # block privilege escalation
    "--user", "1000:1000",  # run as non-root
    # Writable scratch for the non-root user under a read-only root (matplotlib/font cache, etc.)
    "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m",
]


def is_docker_available(timeout: int = 5) -> bool:
    """Cheap reachability check: is a Docker daemon actually there to run against? Shared by
    execute_script_in_docker's own pre-check below and the startup preflight (Live Issue 29,
    preflight.py) - Run 35 spent a full ~110-call run with Docker down and nothing checked first,
    so every realisation was SKIPPED for zero verified output; the preflight exists to catch
    exactly that before committing the run, using this same check.
    """
    try:
        subprocess.run(["docker", "ps"], capture_output=True, timeout=timeout, check=False)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def execute_script_in_docker(script: str, data_dir: str, docker_image: str, timeout: int = 300,
                             artifacts_dir: str = None) -> tuple[bool, str, list[dict]]:
    """
    Execute script in a sandboxed Docker container to verify it works and capture produced files.
    Returns (success, output_or_error, artifacts) or (None, message, []) if Docker unavailable.
    Each artifact is a dict: {"name": str, "size": int}. Files are copied to artifacts_dir if given.
    """
    if not is_docker_available():
        return None, "Docker not available - skipping execution test", []

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text(script, encoding="utf-8")

            docker_cmd = [
                "docker", "run", "--rm",
                *DOCKER_SANDBOX_FLAGS,
                "-v", f"{Path(data_dir).absolute()}:/data:ro",
                "-v", f"{tmpdir}:/work",
                "-w", "/work",
                "-e", "INPUT_FOLDER=/data",
                # Point HOME and matplotlib's cache at the writable tmpfs (root fs is read-only)
                "-e", "HOME=/tmp",
                "-e", "MPLCONFIGDIR=/tmp/mpl",
                docker_image,
                "python", "script.py"
            ]

            # text=True with no encoding decodes via locale.getpreferredencoding(), which on a
            # Windows host is cp1252, not the UTF-8 the container actually emits (generated
            # scripts are required to reconfigure stdout as UTF-8 - see CLAUDE.md). A non-ASCII
            # byte there raises UnicodeDecodeError inside subprocess's reader thread, silently
            # truncating/emptying exec_output - which feeds the execution verdict, the
            # near-empty-output backstop below, and the compile-retry feedback. Pin the encoding
            # explicitly and replace undecodable bytes instead of crashing the read.
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                timeout=timeout + 30,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            # List files the script produced in /work (everything except the script itself),
            # while the temp dir still exists, and persist them so they survive cleanup.
            # Clear the artifacts dir first so it only ever reflects the latest run.
            if artifacts_dir:
                adir = Path(artifacts_dir)
                adir.mkdir(parents=True, exist_ok=True)
                for stale in adir.iterdir():
                    if stale.is_file():
                        stale.unlink()

            artifacts = []
            for produced in sorted(Path(tmpdir).iterdir()):
                if produced.name == "script.py" or not produced.is_file():
                    continue
                artifacts.append({"name": produced.name, "size": produced.stat().st_size})
                if artifacts_dir:
                    shutil.copy2(produced, Path(artifacts_dir) / produced.name)

            if result.returncode == 0:
                return True, result.stdout or "Script executed successfully", artifacts
            else:
                return False, result.stderr or "Script execution failed with no error output", artifacts

    except subprocess.TimeoutExpired:
        return False, f"Script execution timed out (>{timeout}s)", []
    except Exception as e:
        if "daemon" in str(e).lower() or "pipe" in str(e).lower():
            return None, "Docker daemon not running - skipping execution test", []
        return False, f"Execution error: {str(e)}", []


# A script that finds no usable data and prints a message before returning normally exits 0,
# which an exit-code-only check cannot tell apart from a real success. This threshold is a
# heuristic, not a semantic judgment (still no LLM involved) - it exists to catch exactly that
# shape (nothing produced, almost nothing printed) and route it back through the same
# compile-retry loop a real FAIL would get, instead of only being caught much later - and more
# expensively - by the realization judge after the design's Docker budget is spent.
_MIN_SUCCESS_OUTPUT_CHARS = 200


def validate_execution(compiled_script: str, config: PipelineConfig, data_dir: str = None,
                       artifacts_dir: str = None) -> tuple[str, str, str, list[dict]]:
    """Check if script executes. Grounded directly in the Docker exit code - no LLM judgment, though
    a PASS with zero artifacts and near-empty output is treated as FAIL (see _MIN_SUCCESS_OUTPUT_CHARS)
    since that shape almost always means the script found no usable data and exited cleanly instead
    of raising, rather than a genuine success with nothing to report.

    Returns (PASS/FAIL/SKIPPED, feedback, execution_output, artifacts). SKIPPED means execution
    was never actually attempted (no data_dir, or Docker unavailable): this must never be reported
    as PASS, since nothing was verified to run.
    """
    if not data_dir:
        return "SKIPPED", "No data directory provided - execution was not verified.", "", []

    exec_success, exec_output, artifacts = execute_script_in_docker(
        compiled_script, data_dir, config.docker_image, artifacts_dir=artifacts_dir)

    if exec_success is None:
        return "SKIPPED", f"Docker unavailable - execution was not verified: {exec_output}", exec_output, artifacts
    if exec_success:
        if not artifacts and len(exec_output.strip()) < _MIN_SUCCESS_OUTPUT_CHARS:
            return "FAIL", (
                "Script exited successfully but produced no artifacts and almost no output "
                f"({len(exec_output.strip())} chars):\n{exec_output.strip()}\n\n"
                "This looks like the script found no usable input data and exited cleanly instead "
                "of raising - check file-discovery globs and column-name matching against the exact "
                "paths/names in the domain notes (case-insensitive/substring match, correct "
                "sub-directory nesting), and raise an error on missing data rather than printing a "
                "message and returning."
            ), exec_output, artifacts
        return "PASS", "Script executed successfully.", exec_output, artifacts
    # Keep the TAIL: Python puts the actual exception last, after the traceback frames
    return "FAIL", f"Script execution failed:\n{exec_output[-2000:]}", exec_output, artifacts


def _format_artifacts(artifacts: list[dict]) -> str:
    """Render the list of produced files with sizes; flag empty files as suspect."""
    if not artifacts:
        return "(No files were produced by the script.)"
    lines = []
    for a in artifacts:
        flag = "  [WARNING: 0 bytes - likely not a valid image]" if a["size"] == 0 else ""
        lines.append(f"- {a['name']} ({a['size']} bytes){flag}")
    return "\n".join(lines)


# Cap how many rendered plots get attached to the realisation-validator call - enough to judge
# whether the visualizations satisfy the criteria without ballooning the request on designs that
# produce many figures.
_MAX_VALIDATOR_IMAGES = 4


def _load_plot_images(artifacts: list[dict], artifacts_dir: str, limit: int = _MAX_VALIDATOR_IMAGES) -> list[
    tuple[str, bytes]]:
    """Read the first `limit` non-empty PNGs an artifacts_dir listing points at, for the validator to see."""
    if not artifacts_dir:
        return []
    images = []
    for a in artifacts:
        if len(images) >= limit:
            break
        if a["size"] == 0 or not a["name"].lower().endswith(".png"):
            continue
        try:
            images.append(("image/png", (Path(artifacts_dir) / a["name"]).read_bytes()))
        except OSError:
            continue
    return images
