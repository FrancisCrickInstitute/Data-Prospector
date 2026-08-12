"""Generic multi-agent code-generation pipeline.

Orchestrator → Workers (parallel) → Compiler → Evaluator, with feedback loop.
Agnostic to domain — configure via PipelineConfig.
"""

import asyncio
import base64
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from anthropic import AsyncAnthropic
from datetime import datetime
from config import PipelineConfig
from dotenv import load_dotenv
from pathlib import Path
from prompts import *

load_dotenv(override=True)

# base_url is passed explicitly (rather than left to the SDK's default) so this client can
# never be silently rerouted by an ambient ANTHROPIC_BASE_URL - e.g. one set for the
# deepseek_client below via DEEPSEEK_BASE_URL. Anthropic's own SDK auto-detects
# ANTHROPIC_BASE_URL from the environment if it's not passed here.
anthropic_client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"], base_url="https://api.anthropic.com")

# DeepSeek exposes an Anthropic-Messages-API-compatible endpoint, so it can reuse the same
# AsyncAnthropic client shape/request logic below - just a different client instance, keyed by
# model name. None if DEEPSEEK_BASE_URL/DEEPSEEK_API_KEY aren't configured (only needed by
# domain configs that actually assign a deepseek* model to a role).
_deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")
_deepseek_base_url = os.environ.get("DEEPSEEK_BASE_URL")
deepseek_client = (
    AsyncAnthropic(api_key=_deepseek_api_key, base_url=_deepseek_base_url)
    if _deepseek_api_key and _deepseek_base_url else None
)

# Caps concurrent in-flight LLM requests across the whole pipeline (orchestrators, workers,
# compilers, evaluators all funnel through llm_call). Without this, angles_per_iteration parallel
# ideation calls, or realize_top_k parallel realizations (D6) x per-angle worker fan-out, can
# easily put 15-20+ requests in flight at once, tripping rate limits. Override via LLM_MAX_CONCURRENCY.
LLM_SEMAPHORE = asyncio.Semaphore(int(os.environ.get("LLM_MAX_CONCURRENCY", "8")))


def _client_for_model(model: str) -> AsyncAnthropic:
    """Route a model name to the client that can serve it - both speak the Anthropic Messages
    API, so only the client/credentials differ, not the request-building logic in llm_call."""
    if model.startswith("deepseek"):
        if deepseek_client is None:
            raise ValueError(
                f"Model '{model}' requires DEEPSEEK_API_KEY and DEEPSEEK_BASE_URL to be set "
                f"(in .env or the environment)."
            )
        return deepseek_client
    return anthropic_client


def _image_blocks(images: list[tuple[str, bytes]]) -> list[dict]:
    """Build Anthropic image content blocks from (media_type, raw_bytes) pairs."""
    return [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type,
                       "data": base64.standard_b64encode(data).decode("utf-8")},
        }
        for media_type, data in images
    ]


# Core LLM interface
async def llm_call(prompt: str, system_prompt: str = None, model: str = None, cache_prompt: bool = False,
                   max_tokens: int = 8192, images: list[tuple[str, bytes]] = None,
                   cache_prefix: str = None) -> str:
    """
    Calls the model with the given prompt and returns the response.

    Args:
        prompt (str): The user prompt to send to the model. If cache_prefix is given, this is
            just the variable tail appended after it - not the whole prompt.
        system_prompt (str, optional): The system prompt.
        model (str, optional): The model to use for the call.
        cache_prompt (bool): Enable prompt caching for this call's system prompt. Only useful if
            system_prompt is long enough to clear Anthropic's minimum cacheable size (1024 tokens
            for Sonnet/Opus, 2048 for Haiku) - the short role-description system prompts in this
            pipeline generally aren't, so this mostly matters for cache_prefix below instead.
        max_tokens (int): Maximum tokens in response (default 8192).
        images (list[tuple[str, bytes]], optional): (media_type, raw_bytes) pairs, e.g.
            [("image/png", data)], attached as image content blocks between cache_prefix (if any)
            and prompt.
        cache_prefix (str, optional): A stable prefix to mark as an ephemeral cache breakpoint,
            for callers that repeat the same large content across several calls (e.g. compiler
            retries within one design reusing the same analysis/functions, varying only the error
            feedback). Put content that's IDENTICAL across those calls here, and whatever varies
            in `prompt`. No effect (but harmless) if the combined prefix is under the provider's
            minimum cacheable size.

    Returns:
        str: The response from the language model.
    """
    if model is None:
        raise ValueError("model must be provided")

    client = _client_for_model(model)

    system_content = system_prompt
    if cache_prompt:
        system_content = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ]

    if cache_prefix:
        content = [{"type": "text", "text": cache_prefix, "cache_control": {"type": "ephemeral"}}]
        if images:
            content += _image_blocks(images)
        content.append({"type": "text", "text": prompt})
    elif images:
        content = _image_blocks(images)
        content.append({"type": "text", "text": prompt})
    else:
        content = prompt

    messages = [{"role": "user", "content": content}]

    # These models use adaptive thinking; if max_tokens is exhausted during the
    # thinking phase the response comes back with a thinking block but no text.
    # Retry once with a larger budget before giving up.
    async with LLM_SEMAPHORE:
        for attempt, tokens in enumerate((max_tokens, max_tokens * 2)):
            response = await client.messages.create(
                model=model,
                max_tokens=tokens,
                system=system_content,
                messages=messages,
            )
            text = "".join(block.text for block in response.content if block.type == "text")
            if text.strip():
                return text

            # No text produced. If we ran out of tokens (likely during thinking), retry bigger.
            if response.stop_reason != "max_tokens":
                break

    content_types = [block.type for block in response.content]
    raise ValueError(
        f"No text content in response (stop_reason={response.stop_reason}, "
        f"blocks={content_types}). The token budget was likely consumed by thinking; "
        f"try a larger max_tokens."
    )


# Helper functions for data extraction and processing
def extract_xml(text: str, tag: str) -> str:
    """Extracts the content of the specified XML tag from the given text (case-insensitive)."""
    match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else ""


def _extract_markdown_section(text: str, label: str, other_label: str) -> str:
    """Secondary extraction for generate_and_optimize's criteria call (Live Issue 18): recovers
    text under a markdown-style ATX heading naming `label` (e.g. '# IDEATION CRITERIA') when the
    model ignores the requested <ideation_criteria>/<deliverable_rubric> tags and instead mirrors
    the report's own markdown formatting back into its response - observed live (Run 20, Sonnet)
    against a report whose own text was heavily ATX-headed. Only tried after extract_xml() comes
    back empty for a given tag; captures from the end of the labeled heading line to the start of
    the next heading naming `other_label`, or end of text."""
    start_match = re.search(rf'^\s*#{{1,3}}\s*{re.escape(label)}\s*$', text, re.IGNORECASE | re.MULTILINE)
    if not start_match:
        return ""
    end_match = re.search(rf'^\s*#{{1,3}}\s*{re.escape(other_label)}\s*$', text[start_match.end():],
                           re.IGNORECASE | re.MULTILINE)
    end = start_match.end() + end_match.start() if end_match else len(text)
    return text[start_match.end():end].strip()


def format_prompt(template: str, **kwargs) -> str:
    """Format a prompt template, raising a clear error if a variable is missing."""
    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"Missing required prompt variable: {e}") from e


# Matches a bare `&` that isn't the start of a real XML entity/char reference - the model
# frequently writes plain prose (e.g. "cards & checklists") into <description> text, which is
# invalid XML and otherwise breaks the whole <tasks> block for a single stray character.
_BARE_AMPERSAND = re.compile(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)')


def _parse_xml_items(items_xml: str, item_tag: str, fallback_fields: tuple[str, ...]) -> list[dict]:
    """Parse a flat list of same-tag XML blocks (e.g. <task>...</task>, <angle>...</angle>) into
    dicts of their child-tag text. Falls back to a per-field regex scan if strict XML parsing
    fails (tolerates minor formatting drift from the model, e.g. a stray literal '<')."""
    items = []
    sanitized = _BARE_AMPERSAND.sub('&amp;', items_xml)
    try:
        root = ET.fromstring(f"<root>{sanitized}</root>")
        for item_elem in root.findall(item_tag):
            item = {}
            for child in item_elem:
                if child.text:
                    item[child.tag] = child.text.strip()
            if item:
                items.append(item)
    except ET.ParseError as e:
        print(f"Warning: Failed to parse <{item_tag}> XML: {e}")
        print(f"DEBUG: Raw {item_tag} xml (first 500 chars):\n{items_xml[:500]}")
        item_pattern = rf'<{item_tag}>(.*?)</{item_tag}>'
        for match in re.finditer(item_pattern, items_xml, re.DOTALL):
            item_content = match.group(1)
            item = {}
            for field in fallback_fields:
                field_match = re.search(f'<{field}>(.*?)</{field}>', item_content, re.DOTALL)
                if field_match:
                    item[field] = field_match.group(1).strip()
            if item:
                items.append(item)
    return items


def parse_tasks(tasks_xml: str) -> list[dict]:
    """Parse XML tasks into a list of task dictionaries."""
    return _parse_xml_items(tasks_xml, "task", ("function", "description", "input", "output"))


# D2/D5-calibrate: {id, variables_involved, hypothesis, question_or_stakeholder_served,
# why_non_obvious, rough_method, requires} - the angle schema ANGLE_GENERATION_PROMPT_SUFFIX asks
# the model for. requires (D5-calibrate item 6) is instrumentation only - what libraries ideation
# reaches for, not a constraint on it (DIVERGER_PLAN.md §10) - and is never used to filter.
_ANGLE_FIELDS = (
    "id", "variables_involved", "hypothesis", "question_or_stakeholder_served",
    "why_non_obvious", "rough_method", "requires",
)


def parse_angles(angles_xml: str) -> list[dict]:
    """Parse XML angles into a list of angle dictionaries."""
    return _parse_xml_items(angles_xml, "angle", _ANGLE_FIELDS)


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


def execute_script_in_docker(script: str, data_dir: str, docker_image: str, timeout: int = 300,
                             artifacts_dir: str = None) -> tuple[bool, str, list[dict]]:
    """
    Execute script in a sandboxed Docker container to verify it works and capture produced files.
    Returns (success, output_or_error, artifacts) or (None, message, []) if Docker unavailable.
    Each artifact is a dict: {"name": str, "size": int}. Files are copied to artifacts_dir if given.
    """
    try:
        subprocess.run(["docker", "ps"], capture_output=True, timeout=5, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
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

            # Live Issue 16: text=True with no encoding decodes via locale.getpreferredencoding(),
            # which on a Windows host is cp1252, not the UTF-8 the container actually emits (the
            # generated scripts are required to reconfigure stdout as UTF-8 - see CLAUDE.md). A
            # non-ASCII byte there raised UnicodeDecodeError inside subprocess's reader thread,
            # silently truncating/emptying exec_output - which feeds the execution verdict, the
            # near-empty-output backstop (Issue 11), and the compile-retry feedback. Pin the
            # encoding explicitly and replace undecodable bytes instead of crashing the read.
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


# Core async functions for the compilation pipeline
async def compile_script(orchestrator_results: dict, config: PipelineConfig, error_feedback: str = "",
                         seed_script: str = None) -> str:
    """Compile worker functions into a single executable script, optionally fixing a prior execution
    error and/or improving a seed_script (a prior working script this design is mutating) instead of
    assembling from scratch."""
    analysis = orchestrator_results["analysis"]

    functions_text = "\n\n".join([
        f"# Function: {result['function']}\n# Description: {result['description']}\n{result['result']}"
        for result in orchestrator_results["worker_results"]
    ])

    if not functions_text.strip():
        print("WARNING: No worker functions were generated!")

    error_section = ""
    if error_feedback:
        error_section = (
            f"\nThe PREVIOUS compilation FAILED to execute. Fix this error in your output:\n"
            f"{error_feedback}\n"
        )

    seed_section = ""
    if seed_script:
        seed_section = (
            "\nSEED SCRIPT (the working script this design is improving upon):\n"
            f"{seed_script}\n\n"
            "Integrate the functions above into an IMPROVED version of this seed script - carry over "
            "parts of the seed that still apply, replace or extend the parts the new/changed functions "
            "address, and remove anything superseded. Do not discard working seed logic that the "
            "architecture and functions above don't touch.\n"
        )

    # Split at the analysis/functions/library_notes/domain_notes/seed boundary: identical across
    # every sequential compile/execute retry for this design (only error_feedback changes attempt
    # to attempt), so it's passed as a cache_prefix rather than folded into one flat prompt.
    # domain_notes (Live Issue 17) lets a retry fix a path/column bug against the real layout
    # instead of guessing blind from the traceback alone.
    compiler_prefix = COMPILER_PROMPT_PREFIX.format(
        analysis=analysis,
        functions=functions_text,
        library_notes=config.available_libraries,
        domain_notes=config.domain_notes,
        seed_section=seed_section,
    )
    compiler_suffix = COMPILER_PROMPT_SUFFIX.format(error_feedback=error_section)

    compiled_response = await llm_call(compiler_suffix, system_prompt=COMPILER_SYSTEM, model=config.compiler_model,
                                       cache_prompt=True, max_tokens=16384, cache_prefix=compiler_prefix)
    compiled_script = extract_xml(compiled_response, "response")

    if not compiled_script.strip():
        # If no response tag found, extract by finding Python code block
        lines = compiled_response.split("\n")
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith("<") and not line.strip().startswith(">"):
                start_idx = i
                break
        end_idx = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() and not lines[i].strip().startswith("<"):
                end_idx = i + 1
                break
        compiled_script = "\n".join(lines[start_idx:end_idx])

    # Strip markdown code block markers if present
    compiled_script = compiled_script.strip()
    if compiled_script.startswith("```"):
        lines = compiled_script.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        compiled_script = "\n".join(lines).strip()

    return compiled_script


# Live-issue fix (input-routing follow-up): a script that finds no usable data and prints a
# message before returning normally exits 0, which an exit-code-only check cannot tell apart from
# a real success. This threshold is a heuristic, not a semantic judgment (still no LLM involved) -
# it exists to catch exactly that shape (nothing produced, almost nothing printed) and route it
# back through the same compile-retry loop a real FAIL would get, instead of only being caught much
# later - and more expensively - by the realization judge after the design's Docker budget is spent.
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


_CRITERION_PATTERN = re.compile(r'<criterion\s+met="(true|false)"\s*/?>', re.IGNORECASE)

# Cap how many rendered plots get attached to the requirements-validator call - enough to judge
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


# Live Issue 7 (DIVERGER_PLAN.md, post-D6-fix Run 12): a boolean pattern_shown conflated a clean
# disconfirmation (script ran fine, data just don't support the hypothesis - a real finding) with a
# broken/illegible run (blank plot, wrong measurement) - both read as "false" and landed in the same
# realization_status bucket. Three-way vocabulary, same shape as _SOUNDNESS_VERDICTS: "shown" ->
# realised, "disconfirmed" -> realised_null (ranks ALONGSIDE realised in D7's gallery, not beneath
# it), "not_shown" -> pattern_not_shown (the only one that's actually a quality problem).
_PATTERN_OUTCOMES = ("shown", "disconfirmed", "not_shown")
_PATTERN_OUTCOME_TO_STATUS = {
    "shown": "realised",
    "disconfirmed": "realised_null",
    "not_shown": "pattern_not_shown",
}


async def validate_realization(compiled_script: str, report: str, deliverable_rubric: str,
                                claimed_pattern: str, exec_output: str, config: PipelineConfig,
                                angle_scope: str = "", artifacts: list[dict] = None,
                                artifacts_dir: str = None) -> tuple[str, float, bool, str]:
    """D6: check whether a realized script's actual output legibly shows ONE angle's claimed
    pattern - the PRIMARY judgment (DIVERGER_PLAN.md D6 item 3), replacing the converger's "meets
    requirements" framing. The deliverable rubric's mechanical checklist (file counts, etc.) is
    still checked and reported, but graded alongside pattern_outcome rather than gating it - the
    same graded-not-gated shape as D5-calibrate's soundness verdict.

    angle_scope (DIVERGER_PLAN.md Live Issue 8) is the angle's own declared variables/method -
    deliverable_rubric is one shared checklist for the WHOLE report, cached identically across
    every angle in a run, so without this a narrow single-angle script gets graded (and penalized)
    against bullets it was never designed to touch. Passed to the validator so it can SKIP
    (not emit a <criterion> tag for) bullets that are out of scope for this angle by design,
    rather than either hardcoding a per-angle rubric (extra LLM call, breaks the prefix cache) or
    a blind mechanical cap. Varies per angle, so it lives in the suffix, not the cached prefix.

    Returns (pattern_outcome, delivered_score, delivered_pass, pattern_reasoning, feedback).
    pattern_outcome is one of _PATTERN_OUTCOMES, or None if the validator emitted anything outside
    that vocabulary (a warning is printed - _run_one_design treats None the same as "not_shown",
    the conservative default, since an unparseable response gives no positive evidence the pattern
    WAS shown or disconfirmed). delivered_score/delivered_pass are met/total across every
    <criterion> tag the validator emitted against the deliverable rubric (0.0/False if it emitted
    none - treated as a full miss, not a free pass). pattern_reasoning is the validator's own
    justification for the pattern_outcome verdict - distinct from feedback, which covers the
    deliverable-rubric checklist. Previously requested from the model and silently discarded
    (DIVERGER_PLAN.md Live Issue 9), which left Run 13's "0 disconfirmed" uninterpretable: with no
    reasoning surfaced, a pattern_not_shown result and a plausible disconfirmation looked identical.
    """
    artifacts = artifacts or []
    artifacts_listing = _format_artifacts(artifacts)

    # report + criteria (the deliverable_rubric) are identical across every angle realized this
    # run, so cached as a prefix; claimed_pattern varies per angle and stays in the suffix along
    # with script/execution output (see cache_prefix on llm_call).
    validator_prefix = REALIZATION_VALIDATOR_PROMPT_PREFIX.format(report=report, criteria=deliverable_rubric)
    validator_suffix = REALIZATION_VALIDATOR_PROMPT_SUFFIX.format(
        content=compiled_script,
        claimed_pattern=claimed_pattern,
        angle_scope=angle_scope or "(not specified)",
        # Keep the TAIL: the script prints metrics then data-gap suggestions at the very end
        execution_result=f"Console output:\n{exec_output[-3000:]}\n\nFiles actually produced on disk:\n{artifacts_listing}"
    )

    images = _load_plot_images(artifacts, artifacts_dir)
    validator_response = await llm_call(validator_suffix, system_prompt=EVALUATOR_SYSTEM,
                                        model=config.requirements_evaluator_model, cache_prompt=True,
                                        images=images or None, cache_prefix=validator_prefix)
    outcome_text = extract_xml(validator_response, "pattern_outcome").strip().lower()
    if outcome_text in _PATTERN_OUTCOMES:
        pattern_outcome = outcome_text
    else:
        print(f"WARNING: realization validator emitted no parseable <pattern_outcome> (first 300 "
              f"chars): {validator_response[:300]}")
        pattern_outcome = None
    verdicts = _CRITERION_PATTERN.findall(validator_response)
    feedback = extract_xml(validator_response, "feedback").strip()
    pattern_reasoning = extract_xml(validator_response, "pattern_reasoning").strip()

    if not verdicts:
        print(
            f"DEBUG: Realization validator emitted no <criterion> tags (first 800 chars):\n{validator_response[:800]}")
        if not feedback:
            feedback = validator_response.strip()

    total = len(verdicts)
    met = sum(1 for v in verdicts if v.lower() == "true")
    delivered_score = met / total if total else 0.0
    delivered_pass = total > 0 and met == total

    return pattern_outcome, delivered_score, delivered_pass, pattern_reasoning, feedback


async def _call_worker(task_info: dict, task_index: int, report: str, input_metadata: str,
                       config: PipelineConfig) -> dict:
    """Call worker for a single task. Used for parallel execution."""
    func_name = task_info.get("function", f"task_{task_index}")
    # report/input_data/library_notes/domain_notes are identical across every task in this design,
    # so they're cached as a prefix; function/description/input/output vary and stay in the suffix.
    worker_prefix = format_prompt(
        WORKER_PROMPT_PREFIX,
        original_report=report,
        input_data=input_metadata,
        library_notes=config.available_libraries,
        domain_notes=config.domain_notes,
    )
    worker_suffix = format_prompt(
        WORKER_PROMPT_SUFFIX,
        function=func_name,
        description=task_info.get("description", ""),
        input=task_info.get("input", ""),
        output=task_info.get("output", ""),
    )
    worker_response = await llm_call(worker_suffix, system_prompt=WORKER_SYSTEM, model=config.worker_model,
                                     cache_prompt=True, cache_prefix=worker_prefix)
    worker_content = extract_xml(worker_response, "response")
    return {
        "function": func_name,
        "description": task_info.get("description", ""),
        "result": worker_content,
    }


_TOKEN_PATTERN = re.compile(r'[a-z0-9]+')


def _token_set(text: str) -> set:
    """Lowercase, split on non-alphanumerics, drop tokens under 3 chars."""
    return {t for t in _TOKEN_PATTERN.findall(text.lower()) if len(t) >= 3}


def _jaccard(a: set, b: set) -> float:
    """Token-set Jaccard similarity. Two empty sets score 0.0 - no text means no evidence of
    similarity, not a false "identical designs" signal."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _log_iteration_diversity(angles: list[dict], iteration: int) -> None:
    """Measurement only - log pairwise token-set Jaccard similarity across this iteration's angle
    text (hypothesis + variables_involved + rough_method). Does not affect selection or fan-out.
    """
    entries = [
        (
            a.get("id", "?"),
            _token_set(" ".join(a.get(f, "") for f in ("hypothesis", "variables_involved", "rough_method"))),
        )
        for a in angles
    ]
    pairs = [
        (entries[i][0], entries[j][0], _jaccard(entries[i][1], entries[j][1]))
        for i in range(len(entries))
        for j in range(i + 1, len(entries))
    ]

    if not pairs:
        print(f"[diversity] iteration {iteration}: mean=n/a (fewer than 2 angles to compare)")
        return

    mean_similarity = sum(sim for _, _, sim in pairs) / len(pairs)
    pair_str = ", ".join(f"{a}~{b}={sim:.2f}" for a, b, sim in pairs)
    print(f"[diversity] iteration {iteration}: mean={mean_similarity:.2f}  pairs: {pair_str}")


def _angle_record(angle: dict, iteration: int, stance: str) -> str:
    """One line recording what was proposed, in which iteration, under which stance.

    Plain structured text, no LLM summarization. This is what accumulates into the archive and
    feeds back into ANGLE_GENERATION_PROMPT_SUFFIX's {existing_angles} slot, so later iterations
    are pushed toward angles different in kind from what's already been proposed.
    """
    angle_id = angle.get("id", "?")
    hypothesis = (angle.get("hypothesis") or "").strip()
    variables = (angle.get("variables_involved") or "").strip()

    entry = f"[Iteration {iteration}] {angle_id} (stance: {stance}): {hypothesis}"
    if variables:
        entry += f" | variables: {variables}"
    return entry


def _ensure_unique_id(angle: dict, seen_ids: set) -> None:
    """D5-calibrate item 4: mutate angle['id'] in place to stay unique within a run, suffixing
    -2, -3, ... on collision. Independent concurrent angle-generation calls can propose the same
    slug (run 7 produced two angles both called "angle-1") - nothing keys on id today, but D7's
    gallery will, so collisions are resolved here rather than left latent.
    """
    base = angle.get("id") or "angle"
    candidate = base
    suffix = 2
    while candidate in seen_ids:
        candidate = f"{base}-{suffix}"
        suffix += 1
    angle["id"] = candidate
    seen_ids.add(candidate)


def _angle_signature(angle: dict) -> set:
    """Token set for D4 dedup similarity. hypothesis/variables_involved are counted TWICE - run 1
    showed near-duplicate angles that shared topic but differed in method wording, and
    rough_method's extra tokens diluted the signal; this crude weighting biases the Jaccard score
    toward the fields that actually carry the topical signal.
    """
    hypothesis = angle.get("hypothesis", "")
    variables = angle.get("variables_involved", "")
    rough_method = angle.get("rough_method", "")
    return _token_set(f"{hypothesis} {variables} {hypothesis} {variables} {rough_method}")


def _pick_representative(cluster: list[dict]) -> dict:
    """Within a dedup cluster, keep the record whose angle scored highest on _judgment_sort_key
    (soundness_verdict rank, then insight_score) - REQUIRES judging to have already run on every
    record in the cluster (D6-fix item 2: judge before dedup, precisely so this can happen).

    Before D6-fix this picked the longest why_non_obvious text as a crude specificity proxy, which
    is exactly what discarded the stronger angle on Run 11 (DIVERGER_PLAN.md Live Issue 6):
    self-reported-role-trend (insight 0.35, the weakest in the realisable set) survived over
    cross-role-expertise-mapping purely because its why_non_obvious was longer, and the discarded
    angle never reached a judge at all. Ties on judgment (e.g. both unranked) fall back to the old
    longest-why_non_obvious heuristic as a stable secondary tiebreak.
    """
    def key(record: dict) -> tuple:
        angle = record["angle"]
        return (_judgment_sort_key(angle), len((angle.get("why_non_obvious") or "").strip()))

    return max(cluster, key=key)


def _dedup_angles(records: list[dict], threshold: float) -> tuple[list[dict], dict]:
    """D4: cluster archive records ({angle, iteration, stance}) by token-set Jaccard similarity
    over _angle_signature, dropping near-duplicates. Selection now optimises for distinct, not
    best - there is no score yet (that's D5).

    Greedy single-linkage clustering: each record joins the cluster containing its most similar
    previously-seen record if that similarity clears `threshold`, else it starts a new cluster.
    O(n^2) comparisons, fine at the angle counts this pipeline produces per run.

    Returns (kept_records, merge_stats) where merge_stats = {"within_iteration": int,
    "across_iteration": int, "merges": list[dict]} - counts split so within-iteration
    duplication (stance/question differentiation too weak, see D3a) and across-iteration
    duplication ({existing_angles} pressure too weak, see D3) can be diagnosed separately.
    "merges" records each individual merge event (record id, the id of the most-similar
    existing record it matched, the similarity score, the type, and - Live Issue 6 fix - the id of
    the cluster's eventual survivor) so which specific pair merged, AND which one was kept, can be
    read off the run log (see DIVERGER_PLAN.md §3/§4) without the two disagreeing.

    best_match is still the best-matching member AT MERGE TIME, not necessarily the survivor -
    _pick_representative runs after clustering completes and can pick a different cluster member on
    soundness/insight (D6-fix item 2). Run 11 printed "merged [self-reported-role-trend] ->
    [cross-role-expertise-mapping]" while self-reported-role-trend was the one actually kept,
    reading backwards. survivor_id is resolved from the finished clusters below and attached to
    every merge in that cluster, so the log line can report both without contradicting itself.
    """
    clusters: list[list[dict]] = []
    within_iteration = 0
    across_iteration = 0
    merges: list[dict] = []

    for record in records:
        record_tokens = _angle_signature(record["angle"])
        best_idx, best_sim, best_match = None, 0.0, None
        for idx, cluster in enumerate(clusters):
            for member in cluster:
                sim = _jaccard(record_tokens, _angle_signature(member["angle"]))
                if sim > best_sim:
                    best_idx, best_sim, best_match = idx, sim, member

        if best_idx is not None and best_sim >= threshold:
            merge_type = "within_iteration" if best_match["iteration"] == record["iteration"] else "across_iteration"
            if merge_type == "within_iteration":
                within_iteration += 1
            else:
                across_iteration += 1
            merges.append({
                "record_id": record["angle"].get("id", "?"),
                "matched_id": best_match["angle"].get("id", "?"),
                "similarity": best_sim,
                "type": merge_type,
                "cluster_idx": best_idx,
            })
            clusters[best_idx].append(record)
        else:
            clusters.append([record])

    kept = [_pick_representative(cluster) for cluster in clusters]

    # Live Issue 6 fix: resolve each merge's cluster to the representative _pick_representative
    # actually kept, now that clustering (and therefore the cluster's final membership) is
    # settled. cluster_idx was only ever needed to make this lookup possible - drop it from the
    # public dict so callers see the same shape as before plus survivor_id.
    for merge in merges:
        merge["survivor_id"] = kept[merge.pop("cluster_idx")]["angle"].get("id", "?")

    return kept, {
        "within_iteration": within_iteration,
        "across_iteration": across_iteration,
        "merges": merges,
    }


def _format_angle(angle: dict) -> str:
    """Render one angle's full fields as readable text, for a D5 judge suffix - unlike
    _angle_record's one-line archive-feed summary, this includes every _ANGLE_FIELDS value so the
    judge sees the whole idea, not just hypothesis + variables_involved."""
    lines = [f"id: {angle.get('id', '?')}"]
    for field in _ANGLE_FIELDS[1:]:
        if angle.get(field):
            lines.append(f"{field}: {angle[field]}")
    return "\n".join(lines)


async def judge_insight(angle: dict, report: str, ideation_criteria: str, input_metadata: str,
                        config: PipelineConfig) -> dict:
    """D5: score one angle for non-obviousness, grounded in input_metadata and the anti-target
    list (already folded into ideation_criteria by D3b) - not the angle's own why_non_obvious
    self-assessment. Two live runs showed every angle confidently claiming novelty while most were
    near-identical duplicates, so self-assessment is not evidence.

    Returns {"insight_score": float in [0, 1] or None, "insight_reasoning": str}. None means the
    judge call failed or emitted no parseable <score> - treated as "unranked", not zero.
    """
    # report/ideation_criteria/input_data are identical across every judge call in a run - the
    # SAME triple generate_angles caches - so cached as a prefix; the individual angle varies per
    # call and stays in the suffix (§4).
    prefix = format_prompt(INSIGHT_JUDGE_PROMPT_PREFIX, report=report, ideation_criteria=ideation_criteria,
                           input_data=input_metadata)
    suffix = format_prompt(INSIGHT_JUDGE_PROMPT_SUFFIX, angle_text=_format_angle(angle))

    response = await llm_call(suffix, system_prompt=INSIGHT_JUDGE_SYSTEM, model=config.judge_model,
                              cache_prompt=True, cache_prefix=prefix)
    reasoning = extract_xml(response, "reasoning").strip()
    score_text = extract_xml(response, "score").strip()
    try:
        score = max(0.0, min(1.0, float(score_text)))
    except ValueError:
        print(f"WARNING: insight judge emitted no parseable <score> for angle "
              f"{angle.get('id', '?')} (first 300 chars): {response[:300]}")
        score = None
    return {"insight_score": score, "insight_reasoning": reasoning}


# D5-calibrate item 2: three-way verdict instead of a boolean. A boolean sound/unsound collapses
# "needs a caveat" and "cannot be supported at all" into one bucket, which saturates near-constant
# on a small dataset (0/8, then 1/8 sound across live runs) and contributes nothing to ranking -
# structurally the converger's binary req_pass problem in new clothes (DIVERGER_PLAN.md "Live
# issues" #1). The caveat text is carried forward for D7 to DISPLAY, never to filter.
_SOUNDNESS_VERDICTS = ("unsupportable", "caveat", "solid")
_SOUNDNESS_RANK = {"solid": 3, "caveat": 2, "unsupportable": 1}


async def judge_soundness(angle: dict, report: str, ideation_criteria: str, input_metadata: str,
                          config: PipelineConfig) -> dict:
    """D5/D5-calibrate: judge whether one angle's claimed pattern is defensible given the actual
    data volume - graded, not gated (see _SOUNDNESS_VERDICTS above). Same prefix structure as
    judge_insight.

    Returns {"soundness_verdict": one of _SOUNDNESS_VERDICTS or None, "soundness_caveat": str,
    "soundness_reasoning": str}. verdict is None if the judge call failed or emitted anything
    outside the three-word vocabulary - treated as "unranked", not "unsupportable", so a prompt
    that drifts off-vocabulary stays visible instead of silently reading as a quality verdict
    (D5-calibrate item 3 - hardened from the old `verdict_text == "true"` boolean parse, which
    silently mapped anything unexpected to False).
    """
    prefix = format_prompt(SOUNDNESS_JUDGE_PROMPT_PREFIX, report=report, ideation_criteria=ideation_criteria,
                           input_data=input_metadata)
    suffix = format_prompt(SOUNDNESS_JUDGE_PROMPT_SUFFIX, angle_text=_format_angle(angle))

    response = await llm_call(suffix, system_prompt=SOUNDNESS_JUDGE_SYSTEM, model=config.judge_model,
                              cache_prompt=True, cache_prefix=prefix)
    reasoning = extract_xml(response, "reasoning").strip()
    caveat = extract_xml(response, "caveat").strip()
    verdict_text = extract_xml(response, "verdict").strip().lower()
    if verdict_text in _SOUNDNESS_VERDICTS:
        verdict = verdict_text
    else:
        print(f"WARNING: soundness judge emitted no parseable <verdict> for angle "
              f"{angle.get('id', '?')} (first 300 chars): {response[:300]}")
        verdict = None
    return {"soundness_verdict": verdict, "soundness_caveat": caveat, "soundness_reasoning": reasoning}


def _judgment_sort_key(angle: dict) -> tuple:
    """Rank angles for D5's final shortlist: (soundness_rank, insight_score). solid > caveat >
    unsupportable > unranked regardless of insight score - the same hard-gate-then-gradient shape
    as the deleted _candidate_score (exec_pass then req_score), re-pointed at the judged-angle
    domain instead of code execution.
    """
    soundness_rank = _SOUNDNESS_RANK.get(angle.get("soundness_verdict"), 0)
    insight_score = angle.get("insight_score")
    insight_rank = insight_score if insight_score is not None else -1.0
    return (soundness_rank, insight_rank)


def _write_angle_dump(all_angles: list[dict], output_dir: str, timestamp: str) -> str:
    """D5-calibrate item 5: dump this run's ranked, judged AND realized angles to a human-readable
    file. Called after D6's realize step (Live Issue 10 fix - previously called before it, so the
    dump only ever carried D5's soundness/insight judgments and never realization_status/
    delivered_score/pattern_reasoning, which is exactly what D7's gallery needs). Angles outside
    the realized top-k (skipped as unsupportable, or ranked below --realize-top-k) simply have no
    realization_* keys - the per-angle rendering below is guarded accordingly.

    {existing_angles} only gives cross-iteration memory WITHIN a run (DIVERGER_PLAN.md "Live
    issues" #3) - the report's "Already Explored" section is the only memory that persists across
    runs, and it's maintained by hand. This file is the raw material for that: a human skims it
    and copies entries worth retiring into the report themselves. Nothing here is applied
    automatically - automatic retirement would suppress angles that merely resemble a prior one,
    which the plan explicitly wants to avoid.

    timestamp is passed in (D7) rather than generated here, so this file, the gallery
    (_write_gallery) and the per-angle scripts directory for the same run all share one run
    identifier instead of each stamping a fractionally different clock read.

    Returns the path written, or "" if output_dir is falsy.
    """
    if not output_dir:
        return ""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = Path(output_dir) / f"surfaced_angles_{timestamp}.md"

    lines = [
        f"# Surfaced angles - {timestamp}", "",
        "Ranked best-first (soundness, then insight). Copy entries worth retiring into the "
        "report's Already Explored section.", "",
    ]
    for angle in all_angles:
        verdict = angle.get("soundness_verdict") or "unranked"
        insight = angle.get("insight_score")
        insight_str = f"{insight:.2f}" if insight is not None else "unranked"
        lines.append(f"## {angle.get('id', '?')}")
        lines.append(f"- soundness: {verdict}  |  insight: {insight_str}")
        if angle.get("hypothesis"):
            lines.append(f"- hypothesis: {angle['hypothesis']}")
        if angle.get("variables_involved"):
            lines.append(f"- variables: {angle['variables_involved']}")
        if angle.get("soundness_caveat"):
            lines.append(f"- caveat: {angle['soundness_caveat']}")
        if angle.get("soundness_reasoning"):
            lines.append(f"- soundness_reasoning: {angle['soundness_reasoning']}")
        if angle.get("requires"):
            lines.append(f"- requires: {angle['requires']}")
        if angle.get("realization_status"):
            lines.append(f"- realization_status: {angle['realization_status']}")
            if angle.get("delivered_score") is not None:
                lines.append(f"- delivered_score: {angle['delivered_score']:.2f}")
            if angle.get("pattern_reasoning"):
                lines.append(f"- pattern_reasoning: {angle['pattern_reasoning']}")
            if angle.get("artifacts"):
                lines.append(f"- artifacts: {_format_artifacts(angle['artifacts'])}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


# D7: status -> heading label for the top gallery tier. Both statuses share one tier (ranked by
# insight, not separated) - see _write_gallery's docstring for why a disconfirmation is not
# demoted beneath a confirmation.
_GALLERY_STATUS_LABELS = {"realised": "realised — pattern shown", "realised_null": "realised — disconfirmed"}


def _gallery_entry_images(angle: dict) -> list[str]:
    """Relative markdown image paths for one angle's non-empty PNG artifacts (D7 item 2), relative
    to output_dir - the gallery file lives there and artifacts sit under output_dir/artifacts/<id>/
    (execute_script_in_docker's artifacts_dir), so a plain relative path resolves for any viewer
    opened at output_dir without embedding/copying the images a second time."""
    artifacts = angle.get("artifacts") or []
    angle_id = angle.get("id", "?")
    return [
        f"artifacts/{angle_id}/{a['name']}"
        for a in artifacts
        if a["size"] > 0 and a["name"].lower().endswith(".png")
    ]


def _script_rel_path(script_path: str) -> str:
    """The scripts/<run_timestamp>/<angle_id>.py path relative to output_dir, as the gallery links
    it - script_path is stored absolute, so this strips it back to the two path segments the
    gallery lives alongside (the scripts dir is a sibling of the gallery file, both directly under
    output_dir)."""
    p = Path(script_path)
    return f"{p.parent.name}/{p.name}"


def _gallery_entry(angle: dict, top_tier: bool) -> list[str]:
    """Render one realized angle's markdown block - shared by the top tier (realised/realised_null)
    and the pattern_not_shown tier, just with a status label on the heading for the former.
    Deliberately omits delivered_score (DIVERGER_PLAN.md Live Issue 8/D7): even scoped to the
    angle, it can score a script that silently dropped half its data at 1.00, so displaying it as
    a quality number would mislead exactly the reader this gallery is for. pattern_reasoning is
    the substance - shown prominently as "Finding" instead.
    """
    angle_id = angle.get("id", "?")
    insight = angle.get("insight_score")
    insight_str = f"{insight:.2f}" if insight is not None else "unranked"

    if top_tier:
        label = _GALLERY_STATUS_LABELS.get(angle.get("realization_status"), angle.get("realization_status", "?"))
        heading = f"### {angle_id} — {label}"
    else:
        heading = f"### {angle_id}"
    lines = [heading, f"_insight: {insight_str}_", ""]
    if angle.get("hypothesis"):
        lines.append(f"- **Hypothesis:** {angle['hypothesis']}")
    if angle.get("question_or_stakeholder_served"):
        lines.append(f"- **Serves:** {angle['question_or_stakeholder_served']}")
    if angle.get("pattern_reasoning"):
        lines.append(f"- **Finding:** {angle['pattern_reasoning']}")
    if angle.get("soundness_caveat"):
        lines.append(f"- **Caveat:** {angle['soundness_caveat']}")
    for img in _gallery_entry_images(angle):
        lines.append(f"\n![{angle_id}]({img})")
    if angle.get("script_path"):
        lines.append(f"\n[script](scripts/{_script_rel_path(angle['script_path'])})")
    lines.append("")
    return lines


def _write_gallery(all_angles: list[dict], output_dir: str, timestamp: str) -> str:
    """D7: emit a self-contained, skimmable markdown gallery - the pipeline's actual deliverable.
    Replaces the plain-text ranked summary generate_and_optimize used to return as its whole
    result (D2-D6 placeholder - see that function's docstring). Four tiers, never flattened into
    one ranked list (D7 item 3), because the statuses answer different questions:

    - realised / realised_null TOGETHER, ranked by INSIGHT (not soundness, and not the
      realization order) - Run 20 showed the run's three highest-insight angles all came back
      realised_null while the single realised angle was second-lowest on insight, so a
      soundness-first or realised-first sort would bury the run's most interesting result under
      its safest one. A clean disconfirmation closes a question and is shown as a finding here,
      not demoted beneath a confirmation.
    - pattern_not_shown - executed, but illegible. A real quality outcome, shown secondary.
    - not_realisable - an ENGINEERING outcome, not a quality one (DIVERGER_PLAN.md D6 item 5).
      Listed prominently with `requires`, since that list is the signal for what to provision next
      (DIVERGER_PLAN.md §10).
    - unsupportable - never reaches realization, but the soundness reasoning is itself
      informative: what the dataset cannot support is a finding about the dataset, not a dead end.

    Angles judged but never selected for realization this run (below --realize-top-k) get one line
    each in a closing "also generated" section - full detail for those already lives in
    surfaced_angles_<timestamp>.md, which sits alongside this file.

    Returns the path written, or "" if output_dir is falsy.
    """
    if not output_dir:
        return ""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = Path(output_dir) / f"gallery_{timestamp}.md"

    realized_top = [a for a in all_angles if a.get("realization_status") in ("realised", "realised_null")]
    realized_top.sort(
        key=lambda a: a.get("insight_score") if a.get("insight_score") is not None else -1.0, reverse=True)
    not_shown = [a for a in all_angles if a.get("realization_status") == "pattern_not_shown"]
    not_realisable = [a for a in all_angles if a.get("realization_status") == "not_realisable"]
    unsupportable = [a for a in all_angles if a.get("soundness_verdict") == "unsupportable"]
    considered_ids = {a.get("id") for a in all_angles if a.get("realization_status") or a.get("soundness_verdict") == "unsupportable"}
    also_generated = [a for a in all_angles if a.get("id") not in considered_ids]

    lines = [
        f"# Diverger gallery — {timestamp}", "",
        f"{len(all_angles)} candidate angle(s) surfaced this run: {len(realized_top)} realised or "
        f"disconfirmed, {len(not_shown)} executed but illegible, {len(not_realisable)} not "
        f"realisable, {len(unsupportable)} unsupportable by the data.", "",
    ]

    if realized_top:
        lines.append("## Realised & disconfirmed — findings worth a look")
        lines.append("")
        lines.append("_Ranked by insight, not delivery mechanics - a clean disconfirmation ranks "
                      "alongside a confirmation, not beneath it._")
        lines.append("")
        for angle in realized_top:
            lines.extend(_gallery_entry(angle, top_tier=True))

    if not_shown:
        lines.append("## Pattern not shown — executed, but the output didn't legibly demonstrate the claim")
        lines.append("")
        for angle in not_shown:
            lines.extend(_gallery_entry(angle, top_tier=False))

    if not_realisable:
        lines.append("## Not realisable — engineering / provisioning gaps, not quality judgements")
        lines.append("")
        for angle in not_realisable:
            lines.append(f"### {angle.get('id', '?')}")
            if angle.get("hypothesis"):
                lines.append(f"- **Hypothesis:** {angle['hypothesis']}")
            if angle.get("requires"):
                lines.append(f"- **Requires:** {angle['requires']}")
            feedback = (angle.get("realization_feedback") or "").strip()
            if feedback:
                lines.append(f"- **Why blocked:** {feedback[:400]}")
            lines.append("")

    if unsupportable:
        lines.append("## Unsupportable — the data can't support these, by design")
        lines.append("")
        lines.append("_Never realised - knowing what this dataset cannot support is itself a finding._")
        lines.append("")
        for angle in unsupportable:
            lines.append(f"### {angle.get('id', '?')}")
            if angle.get("hypothesis"):
                lines.append(f"- **Hypothesis:** {angle['hypothesis']}")
            if angle.get("soundness_reasoning"):
                lines.append(f"- **Why:** {angle['soundness_reasoning']}")
            lines.append("")

    if also_generated:
        lines.append("## Also generated, not realised this run")
        lines.append("")
        lines.append("_Judged but ranked below this run's --realize-top-k cutoff, so no code was "
                      "written or run for these. Full detail (soundness/insight for every angle) "
                      "is in the surfaced_angles dump alongside this file._")
        lines.append("")
        for angle in also_generated:
            insight = angle.get("insight_score")
            insight_str = f"{insight:.2f}" if insight is not None else "unranked"
            lines.append(f"- **{angle.get('id', '?')}** (insight {insight_str}): {angle.get('hypothesis', '')}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


async def _run_one_design(angle: dict, report: str, deliverable_rubric: str, input_metadata: str,
                          config: PipelineConfig, data_dir: str, artifacts_dir: str, label: str,
                          max_compile_attempts: int = 3) -> dict:
    """D6: realize ONE judged angle (orchestrate -> workers -> compile/execute loop -> realization
    check). The angle's hypothesis/rough_method - not the whole report - is the brief the
    orchestrator designs against (DIVERGER_PLAN.md D6 item 2); report/deliverable_rubric stay the
    TRUE, identical background context shared by every angle realized this run, so
    ORCHESTRATOR_PROMPT_PREFIX and WORKER_PROMPT_PREFIX both still hit cache across the top-k
    angles, not just within one angle's own compile retries (D6 item 1's caching note).

    Returns {angle_id, realization_status, realization_feedback, pattern_reasoning, delivered_score,
    artifacts, artifacts_dir, script}. pattern_reasoning is the validator's justification for the
    pattern_outcome verdict (DIVERGER_PLAN.md Live Issue 9) - "" for the not_realisable early-returns
    below, since those never reach validate_realization. realization_status is one of:
    - "realised": executed, and the claimed pattern was legibly shown.
    - "realised_null": executed and rendered legibly, but the data do NOT support the claimed
      pattern - a clean disconfirmation, not a failure. Added post-D6-fix (Live Issue 7, Run 12):
      a boolean pattern_shown used to collapse this into the same bucket as a broken/illegible run,
      burying a genuine finding under what reads as a quality defect. Ranks ALONGSIDE "realised" in
      D7's gallery, not beneath it.
    - "pattern_not_shown": executed, but the output does not legibly show anything about the claim
      either way (broken/blank/unreadable, or the validator's response was itself unparseable - see
      validate_realization) - THIS is the actual quality judgement, not "realised_null" or a
      disconfirmation. Deliberately not named "unsound" (D6-fix item 3) - that word is D5's
      soundness-judge vocabulary (data can't support the claim), a different judge answering a
      different question; conflating the two would mislabel D7's gallery.
    - "not_realisable": never executed after max_compile_attempts (e.g. a missing library) or
      execution was unverifiable (no data_dir / Docker unavailable) - an engineering/provisioning
      outcome, never conflated with "pattern_not_shown" or "realised_null" (DIVERGER_PLAN.md D6
      item 5).
    """

    def log(msg):
        print(f"  [{label}] {msg}")

    # ORCHESTRATOR: design an architecture for THIS ONE angle.
    # report/input_data/criteria (deliverable_rubric) are identical across every angle realized
    # this run, so cached as a prefix; the angle itself varies per call and stays in the suffix.
    orchestrator_prefix = format_prompt(
        ORCHESTRATOR_PROMPT_PREFIX, report=report, criteria=deliverable_rubric, input_data=input_metadata,
        domain_notes=config.domain_notes,
    )
    orchestrator_suffix = format_prompt(
        ORCHESTRATOR_PROMPT_SUFFIX,
        hypothesis=angle.get("hypothesis", ""),
        variables_involved=angle.get("variables_involved", ""),
        rough_method=angle.get("rough_method", ""),
        why_non_obvious=angle.get("why_non_obvious", ""),
    )
    orchestrator_response = await llm_call(orchestrator_suffix, system_prompt=ORCHESTRATOR_SYSTEM,
                                           model=config.orchestrator_model, cache_prompt=True,
                                           cache_prefix=orchestrator_prefix)
    analysis = extract_xml(orchestrator_response, "analysis").strip()
    tasks = parse_tasks(extract_xml(orchestrator_response, "tasks"))
    log(f"Architecture: {len(tasks)} functions")

    # WORKERS: implement each function in parallel - unchanged from before D6 (item 1). Called
    # with the TRUE report (not the angle brief) so WORKER_PROMPT_PREFIX stays identical, and
    # cacheable, across every angle realized this run too.
    worker_results = await asyncio.gather(
        *[_call_worker(t, i, report, input_metadata, config) for i, t in enumerate(tasks, 1)]
    )
    orchestrator_results = {"analysis": analysis, "worker_results": worker_results}

    # COMPILER + (grounded) EXECUTION: retries up to max_compile_attempts, feeding the execution
    # error back into the next compile attempt. Live Issue 12 fix: log each attempt's FAIL reason
    # (same audit-gap pattern as pattern_reasoning - previously only the LAST attempt's feedback
    # was ever visible, in the eventual not_realisable message) and abort early if an error recurs
    # verbatim, since that means the compiler isn't repairing anything and the remaining attempts
    # would just spend Docker/LLM budget for no gain. Live Issue 13 fix: track every FAIL string
    # seen so far, not just the immediately preceding one - a consecutive-only comparison misses
    # an oscillating loop (attempt 1 error A, attempt 2 error B, attempt 3 error A again), which
    # is still going in circles even though no two *adjacent* attempts match.
    compiled_script, exec_output, artifacts = None, "", []
    execution_passed = False
    exec_verdict = "FAIL"
    compile_error = ""
    attempt_feedbacks = []
    seen_feedbacks = set()
    aborted_on_repeat = False
    for attempt in range(max_compile_attempts):
        log(f"Compile attempt {attempt + 1}/{max_compile_attempts}...")
        compiled_script = await compile_script(orchestrator_results, config, error_feedback=compile_error)
        exec_verdict, exec_feedback, exec_output, artifacts = validate_execution(
            compiled_script, config, data_dir, artifacts_dir=artifacts_dir)
        log(f"Execution: {exec_verdict}")
        # SKIPPED (no Docker) is terminal too - there's no error to fix, so retrying compiles
        # the same script again for nothing. It is NOT the same as a verified PASS though.
        if exec_verdict in ("PASS", "SKIPPED"):
            execution_passed = True
            break
        log(f"  Attempt {attempt + 1} FAIL reason: {exec_feedback[:500]}")
        attempt_feedbacks.append(exec_feedback)
        normalized_feedback = exec_feedback.strip()
        if normalized_feedback in seen_feedbacks:
            log("  This error already occurred in an earlier attempt - aborting remaining compile "
                "attempts (the compiler is cycling, not repairing).")
            aborted_on_repeat = True
            break
        seen_feedbacks.add(normalized_feedback)
        if attempt < max_compile_attempts - 1:
            compile_error = exec_feedback

    if not execution_passed:
        attempt_summary = "\n\n".join(
            f"Attempt {i + 1}: {fb[:1000]}" for i, fb in enumerate(attempt_feedbacks)
        )
        abort_note = " (aborted early - the same error recurred verbatim)" if aborted_on_repeat else ""
        log(f"[not_realisable] Did not execute after {len(attempt_feedbacks)} attempt(s){abort_note}.")
        return {
            "angle_id": angle.get("id", "?"), "realization_status": "not_realisable",
            "realization_feedback": f"Execution failed after {len(attempt_feedbacks)} compile attempt(s){abort_note}:\n\n{attempt_summary}",
            "pattern_reasoning": "", "delivered_score": None, "artifacts": artifacts,
            "artifacts_dir": artifacts_dir, "script": compiled_script,
        }

    if exec_verdict == "SKIPPED":
        # Execution was never verified (no data_dir / Docker unavailable), so there's no real
        # output to judge - a realization call here is a guaranteed-uninformative judge call paid
        # for nothing. Short-circuit instead of spending one per realized angle.
        log("[not_realisable] Execution unverified (no data_dir / Docker unavailable)")
        return {
            "angle_id": angle.get("id", "?"), "realization_status": "not_realisable",
            "realization_feedback": f"Execution was not verified, so realization cannot be checked: {exec_feedback}",
            "pattern_reasoning": "", "delivered_score": None, "artifacts": artifacts,
            "artifacts_dir": artifacts_dir, "script": compiled_script,
        }

    # REALIZATION CHECK: only reached on a verified execution PASS (FAIL returned above, SKIPPED
    # short-circuited above). PRIMARY judgment is a three-way classification of whether/how the
    # actual output shows THIS angle's claimed pattern (Live Issue 7); the deliverable-rubric
    # checklist is reported alongside but does not gate status - graded, not gated, matching
    # D5-calibrate's soundness verdict. An unparseable pattern_outcome (None) maps to
    # "pattern_not_shown" - the conservative default, since it gives no positive evidence either way.
    # Live Issue 8: the angle's own declared scope, not the whole report, is what the deliverable
    # rubric should be judged against for this script - see validate_realization's docstring.
    angle_scope = (
        f"Variables: {angle.get('variables_involved', '')}\n"
        f"Method: {angle.get('rough_method', '')}"
    )
    pattern_outcome, delivered_score, delivered_pass, pattern_reasoning, realization_feedback = await validate_realization(
        compiled_script, report, deliverable_rubric, angle.get("hypothesis", ""), exec_output, config,
        angle_scope=angle_scope, artifacts=artifacts, artifacts_dir=artifacts_dir)
    status = _PATTERN_OUTCOME_TO_STATUS.get(pattern_outcome, "pattern_not_shown")
    # Live Issue 9: pattern_reasoning is the whole point of the three-way split - without it,
    # pattern_not_shown and a plausible disconfirmation are indistinguishable from the console alone.
    log(f"Realization: {status} (delivered_score={delivered_score:.2f}) - {pattern_reasoning}")
    return {
        "angle_id": angle.get("id", "?"), "realization_status": status,
        "realization_feedback": realization_feedback, "pattern_reasoning": pattern_reasoning,
        "delivered_score": delivered_score, "artifacts": artifacts, "artifacts_dir": artifacts_dir,
        "script": compiled_script,
    }


# D3a: heading match is deliberately loose (any level, any wording containing "guiding
# question") since the only contract with the report author is that heading text, not its exact
# phrasing or markdown level.
_GUIDING_QUESTIONS_HEADING = re.compile(r'^#{1,6}\s*.*guiding question.*$', re.IGNORECASE | re.MULTILINE)
_NUMBERED_LIST_ITEM = re.compile(r'^\s*\d+\.\s+(.+)$', re.MULTILINE)

# Used when _parse_guiding_questions finds nothing - passed as the {guiding_question} value so the
# fallback suffix template still reads sensibly instead of showing a blank line.
_NO_GUIDING_QUESTION = "(none identified this run - use your own judgement)"


def _parse_guiding_questions(report: str) -> list[str]:
    """Pull the numbered guiding-question list out of the raw report's markdown - D3a's second
    cycling axis, alongside stance. Parsed from the report (deterministic markdown structure), not
    the LLM-paraphrased criteria. Looks for a heading mentioning "guiding question" (e.g. "##
    Guiding Questions for Analysis") and returns the numbered list items between it and the next
    heading. Returns [] if no such section is found or it contains no numbered items - callers
    must treat that as "cycle nothing", per DIVERGER_PLAN.md's D3a guardrail, not retry harder.
    """
    heading_match = _GUIDING_QUESTIONS_HEADING.search(report)
    if not heading_match:
        return []
    section_start = heading_match.end()
    next_heading = re.search(r'^#{1,6}\s', report[section_start:], re.MULTILINE)
    section_end = section_start + next_heading.start() if next_heading else len(report)
    section = report[section_start:section_end]
    return [item.strip() for item in _NUMBERED_LIST_ITEM.findall(section) if item.strip()]


async def generate_angles(report: str, ideation_criteria: str, input_metadata: str, config: PipelineConfig,
                          stance: str, guiding_question: str, existing_angles: str, n: int) -> list[dict]:
    """D3: generate n candidate analysis angles as structured text - no code, no Docker.

    Each angle: {id, variables_involved, hypothesis, question_or_stakeholder_served,
    why_non_obvious, rough_method} (see _ANGLE_FIELDS). stance and guiding_question are the two
    independent cycling axes generate_and_optimize assigns per concurrent call (D3/D3a);
    existing_angles is the accumulated archive, all three passed straight through to the suffix.

    ideation_criteria (D3b) is only the IDEATION half of the criteria split - guiding questions,
    stakeholders, anti-targets, data constraints - never the deliverable rubric (script-delivery
    mechanics), which is withheld here and held for D6's realisation check instead.

    """
    # report/ideation_criteria/input_data are identical across every angle-generation call in a
    # run, so they're cached as a prefix; stance/guiding_question/existing_angles/n vary per call
    # and stay in the suffix (see DIVERGER_PLAN.md §4 - both cycling axes belong here, not the prefix).
    prefix = format_prompt(ANGLE_GENERATION_PROMPT_PREFIX, report=report, ideation_criteria=ideation_criteria,
                           input_data=input_metadata)
    suffix = format_prompt(ANGLE_GENERATION_PROMPT_SUFFIX, stance=stance, guiding_question=guiding_question,
                           existing_angles=existing_angles, n=n)

    response = await llm_call(suffix, system_prompt=ANGLE_GENERATION_SYSTEM, model=config.angle_model,
                              cache_prompt=True, cache_prefix=prefix)
    return parse_angles(extract_xml(response, "angles"))


async def generate_and_optimize(report: str, config: PipelineConfig, data_dir: str = None,
                                max_iterations: int = 2, output_dir: str = None,
                                realize_top_k: int = 4, angles_per_iteration: int = 12) -> dict:
    """D3/D3a/D3b/D4/D5/D6/D7: ideation loop, fanned out, then judged, then deduped, then
    selectively realized, then written up as a gallery. Each iteration fires angles_per_iteration
    independent generate_angles calls (n=1 each) concurrently via asyncio.gather, cycling
    config.design_stances and the parsed guiding questions across calls independently (D3a) for
    intra-iteration diversity - concurrent calls can't see each other, so these two cycling axes
    are the only lever within an iteration. Cross-iteration diversity instead comes from
    {existing_angles}: the accumulated archive of every angle proposed so far, fed back into
    ANGLE_GENERATION_PROMPT_SUFFIX. Once ideation finishes, D5 scores every archived angle for
    non-obviousness (judge_insight) and soundness (judge_soundness), THEN D4 dedups the whole
    archive by token-set similarity (D6-fix item 2: judging first lets dedup keep the
    highest-scoring member of each cluster instead of a text-length proxy) and the survivors are
    ranked by both judgments. D6 then realizes only the top realize_top_k non-unsupportable angles
    - code is written and run for that small selection only, never for the whole archive.

    Returns a dict, not a script or plain-text summary (D7 - the pre-D7 versions of this function
    returned a formatted string, which app.py wrote out under a misleading analysis_script_<ts>.py
    filename since D2 stopped this pipeline from producing a single script):
    - "all_angles": every surviving (post-dedup) angle dict, ranked best-first by
      _judgment_sort_key, each carrying its D5 judgment and (if realized) D6 result fields.
    - "summary_text": the same plain-text ranked summary this function used to return outright -
      kept for console logging / non-visual consumers, not the deliverable itself anymore.
    - "gallery_path" / "dump_path": paths to the two files written to output_dir (_write_gallery,
      _write_angle_dump), or "" if output_dir wasn't given.
    - "scripts_dir": the directory each realized angle's compiled script was written into, or None.
    """
    input_metadata = config.extract_input_metadata(data_dir) if data_dir else "(No input data provided)"

    # Parse the report into two separate rubrics ONCE, shared by every call that needs them (D3b).
    # This is what actually makes the pipeline domain-agnostic: without it, the ideation and
    # (later) judging prompts would have to hardcode the shape of "success" for one specific kind
    # of report. Splitting by consumer stops ideation from paying cached tokens on deliverable
    # rubric text ("runs without errors", "clean code") that has nothing to do with idea quality:
    #   - ideation_criteria: guiding questions/stakeholders/anti-targets/data constraints - fed to
    #     generate_angles below (and, later, the D5 judges).
    #   - deliverable_rubric: script-delivery mechanics - fed to _run_one_design/validate_realization
    #     below (D6), only for the small top-k set of angles actually realized.
    # If extraction itself fails (e.g. a transient rate-limit error) OR comes back malformed (one
    # or both tags missing, or - Run 11, DIVERGER_PLAN.md Live Issue 0 - both tags collapsing to
    # the same text), fall back to the raw report for both instead of leaving either pointed at an
    # empty rubric. D6-fix item 1: this used to be `extract_xml(...) or criteria_response.strip()`
    # per field, which silently duplicated the WHOLE malformed response into both variables on a
    # missing tag rather than failing loudly - that's what broke Run 11's D6 realization (the
    # orchestrator designed against the whole report instead of a one-angle rubric). A missing or
    # duplicated tag now raises here and hits the same honest raw-report fallback as a call failure.
    try:
        criteria_input = format_prompt(CRITERIA_PROMPT, report=report, input_data=input_metadata)
        criteria_response = await llm_call(criteria_input, system_prompt=CRITERIA_SYSTEM,
                                           model=config.requirements_evaluator_model, cache_prompt=True)
        ideation_criteria = extract_xml(criteria_response, "ideation_criteria").strip()
        deliverable_rubric = extract_xml(criteria_response, "deliverable_rubric").strip()
        # Live Issue 18: the model occasionally ignores the <ideation_criteria>/<deliverable_rubric>
        # tags and mirrors the report's own markdown headers back instead (e.g. '# IDEATION
        # CRITERIA') - try recovering the same content under that heading before giving up and
        # degrading to the raw-report fallback below.
        if not ideation_criteria:
            ideation_criteria = _extract_markdown_section(
                criteria_response, "IDEATION CRITERIA", "DELIVERABLE RUBRIC")
        if not deliverable_rubric:
            deliverable_rubric = _extract_markdown_section(
                criteria_response, "DELIVERABLE RUBRIC", "IDEATION CRITERIA")
        if not ideation_criteria or not deliverable_rubric:
            raise ValueError(
                f"Criteria response missing <ideation_criteria> and/or <deliverable_rubric> "
                f"({len(ideation_criteria)} / {len(deliverable_rubric)} chars extracted) - first "
                f"500 chars of response: {criteria_response[:500]!r}"
            )
        if ideation_criteria == deliverable_rubric:
            raise ValueError(
                "Criteria response's <ideation_criteria> and <deliverable_rubric> extracted as "
                "identical text - the criteria split has collapsed."
            )
    except Exception as e:
        print(f"WARNING: Criteria extraction failed or malformed ({e!r}); falling back to the raw report as both criteria.")
        ideation_criteria = deliverable_rubric = report
    print(f"\nIdeation criteria extracted from report:\n{ideation_criteria}\n")
    print(f"\nDeliverable rubric extracted from report (fed to D6 realization only):\n{deliverable_rubric}\n")

    # D3a: guiding questions, the second cycling axis, parsed once from the raw report (they don't
    # change run to run). Empty means the report's guiding-questions section wasn't found/parseable
    # - every call falls back to _NO_GUIDING_QUESTION rather than cycling a mis-parsed list.
    guiding_questions = _parse_guiding_questions(report)
    if not guiding_questions:
        print(
            "WARNING: Could not parse guiding questions from the report (no heading matching "
            "'guiding question' with a numbered list under it) - the second cycling axis is "
            "disabled this run; every call gets a placeholder guiding_question."
        )

    stances = config.design_stances
    # Archive: every angle proposed so far across all iterations, as {angle, iteration, stance}
    # records - not executed scripts, so there's no score to cap by (D4 dedups instead, below).
    archive: list[dict] = []
    # D5-calibrate item 4: ids seen so far this run, across all iterations - collisions between
    # independent concurrent calls get suffixed here before the angle ever reaches the archive.
    seen_ids: set = set()

    for iteration in range(max_iterations):
        print(f"\n{'=' * 80}")
        print(f"ITERATION {iteration + 1}/{max_iterations}  ({angles_per_iteration} angles, fanned out)")
        print(f"{'=' * 80}")

        # {existing_angles} is the only cross-iteration divergence pressure (stance and guiding
        # question are the intra-iteration ones, below). It goes in the SUFFIX, not the PREFIX -
        # it grows every iteration and would invalidate the cache if it were cached (§4).
        existing_angles_section = "\n".join(
            _angle_record(rec["angle"], rec["iteration"], rec["stance"]) for rec in archive
        ) or "(none yet)"

        def _stance_for(m: int) -> str:
            return stances[(m + iteration) % len(stances)]

        def _question_for(m: int) -> str:
            return guiding_questions[
                (m + iteration * angles_per_iteration) % len(guiding_questions)
            ] if guiding_questions else _NO_GUIDING_QUESTION

        # N independent calls of one angle each, not one call asking for N - independent samples
        # diverge more than one sample self-organising within a single context. Call m gets
        # (stance[m % S], question[m % Q]) as two INDEPENDENT cycling axes (D3a) - e.g. 4 calls
        # over 5 questions structurally can't all land on the same question, unlike stance alone.
        # A call that raises is dropped with a logged warning rather than failing the iteration.
        calls = [
            generate_angles(
                report, ideation_criteria, input_metadata, config,
                stance=_stance_for(m), guiding_question=_question_for(m),
                existing_angles=existing_angles_section, n=1,
            )
            for m in range(angles_per_iteration)
        ]
        call_results = await asyncio.gather(*calls, return_exceptions=True)

        angles = []
        angle_meta = []
        for m, result in enumerate(call_results):
            call_stance, call_question = _stance_for(m), _question_for(m)
            if isinstance(result, Exception):
                print(f"WARNING: angle generation call {m} (stance={call_stance!r}, "
                      f"question={call_question!r}) failed: {result!r}")
                continue
            for angle in result:
                _ensure_unique_id(angle, seen_ids)
                angles.append(angle)
                angle_meta.append((call_stance, call_question))
                archive.append({"angle": angle, "iteration": iteration + 1, "stance": call_stance})

        print(f"\nGenerated {len(angles)} angle(s) this iteration:")
        for angle, (call_stance, call_question) in zip(angles, angle_meta):
            print(f"\n  [{angle.get('id', '?')}]  (stance: {call_stance}  |  question: {call_question})")
            for field in _ANGLE_FIELDS[1:]:
                if angle.get(field):
                    print(f"    {field}: {angle[field]}")

        _log_iteration_diversity(angles, iteration + 1)

    print(f"\n{'=' * 80}")
    print(f"Completed all {max_iterations} iteration(s). {len(archive)} angle(s) generated total.")
    print(f"{'=' * 80}\n")

    if not archive:
        return {"all_angles": [], "summary_text": "(No angles were generated.)", "gallery_path": "",
                "dump_path": "", "scripts_dir": None}

    # D5: judge EVERY archived angle - not just the post-dedup subset - for non-obviousness and
    # soundness, BEFORE dedup runs (D6-fix item 2, DIVERGER_PLAN.md Live Issue 6: dedup used to run
    # first and _pick_representative broke ties on longest why_non_obvious, a text-length proxy
    # that discarded the stronger of two merged angles on Run 11 without it ever reaching a judge).
    # Judge calls share one cached prefix (report/ideation_criteria/input_data - the same triple
    # generate_angles caches), so judging all N archived angles instead of the deduped subset costs
    # little extra. A failed call scores that angle "unranked" (None) rather than failing the run or
    # being penalised as if actually judged.
    judge_calls = []
    call_meta = []
    for record in archive:
        angle = record["angle"]
        judge_calls.append(judge_insight(angle, report, ideation_criteria, input_metadata, config))
        call_meta.append(("insight", angle))
        judge_calls.append(judge_soundness(angle, report, ideation_criteria, input_metadata, config))
        call_meta.append(("soundness", angle))

    judge_results = await asyncio.gather(*judge_calls, return_exceptions=True)

    for (kind, angle), result in zip(call_meta, judge_results):
        if isinstance(result, Exception):
            print(f"WARNING: judge_{kind} failed for angle {angle.get('id', '?')}: {result!r}")
            if kind == "insight":
                angle["insight_score"], angle["insight_reasoning"] = None, f"(judge call failed: {result!r})"
            else:
                angle["soundness_verdict"], angle["soundness_caveat"], angle["soundness_reasoning"] = (
                    None, "", f"(judge call failed: {result!r})"
                )
            continue
        angle.update(result)

    # D4: dedup - drop near-duplicate angles across the WHOLE run (all iterations), not per
    # iteration, so across-iteration duplicates are caught too. Now runs AFTER judging (D6-fix item
    # 2) so _pick_representative keeps the highest-scoring cluster member, not a text-length proxy.
    # Does not feed back into {existing_angles} above - that cross-iteration pressure already works
    # on the raw archive (see DIVERGER_PLAN.md §3), so dedup stays a separate, final selection step.
    kept_records, merge_stats = _dedup_angles(archive, config.angle_similarity_threshold)
    print(
        f"[dedup] {len(archive)} angle(s) -> {len(kept_records)} after dedup "
        f"(threshold={config.angle_similarity_threshold}); merged "
        f"{merge_stats['within_iteration']} within-iteration, "
        f"{merge_stats['across_iteration']} across-iteration duplicate(s)"
    )
    for merge in merge_stats["merges"]:
        # Live Issue 6 fix: "->" still points at the best match AT MERGE TIME, which is not
        # necessarily who survived - "kept" is the actual _pick_representative winner, so the line
        # is self-consistent even when they differ (D6-fix item 2 means dedup runs after judging,
        # so the winner is picked on soundness/insight, not on who matched whom first).
        print(
            f"    merged [{merge['record_id']}] -> [{merge['matched_id']}] "
            f"(similarity={merge['similarity']:.3f}, {merge['type']}) kept [{merge['survivor_id']}]"
        )
    print()
    all_angles = [rec["angle"] for rec in kept_records]

    if not all_angles:
        return {"all_angles": [], "summary_text": "(No angles were generated.)", "gallery_path": "",
                "dump_path": "", "scripts_dir": None}

    all_angles.sort(key=_judgment_sort_key, reverse=True)

    solid_count = sum(1 for a in all_angles if a.get("soundness_verdict") == "solid")
    caveat_count = sum(1 for a in all_angles if a.get("soundness_verdict") == "caveat")
    unsupportable_count = sum(1 for a in all_angles if a.get("soundness_verdict") == "unsupportable")
    unranked_count = sum(1 for a in all_angles if a.get("soundness_verdict") is None)
    print(
        f"[judge] {len(all_angles)} angle(s) scored - {solid_count} solid, {caveat_count} "
        f"needs-caveat, {unsupportable_count} unsupportable, {unranked_count} unranked "
        f"(judge call failed)\n"
    )

    # D6: realize only the top-k ranked, non-unsupportable angles - selective execution, not every
    # candidate (item 1). all_angles is already sorted best-first by _judgment_sort_key;
    # unsupportable angles are skipped entirely rather than paying a Docker run to visualize a
    # claim the judge already said the data can't support.
    realizable_angles = [a for a in all_angles if a.get("soundness_verdict") != "unsupportable"]
    to_realize = realizable_angles[:realize_top_k]
    skipped_unsupportable = len(all_angles) - len(realizable_angles)
    print(
        f"[realize] Realizing top {len(to_realize)} of {len(all_angles)} angle(s) "
        f"({skipped_unsupportable} unsupportable angle(s) skipped)\n"
    )

    # D7: one timestamp shared by the gallery, the surfaced_angles dump, and the scripts
    # directory for this run, so the three files/dirs a human needs to cross-reference for one
    # run all carry the same run identifier instead of each stamping a fractionally different
    # clock read.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifacts_base = Path(output_dir) / "artifacts" if output_dir else None
    scripts_dir = Path(output_dir) / "scripts" / timestamp if output_dir else None
    realize_calls = [
        _run_one_design(
            angle, report, deliverable_rubric, input_metadata, config, data_dir,
            artifacts_dir=str(artifacts_base / angle.get("id", "?")) if artifacts_base else None,
            label=angle.get("id", "?"),
        )
        for angle in to_realize
    ]
    realize_results = await asyncio.gather(*realize_calls, return_exceptions=True)

    for angle, result in zip(to_realize, realize_results):
        if isinstance(result, Exception):
            print(f"WARNING: realization failed for angle {angle.get('id', '?')}: {result!r}")
            angle["realization_status"] = "not_realisable"
            angle["realization_feedback"] = f"(realization call failed: {result!r})"
            angle["pattern_reasoning"] = ""
            continue
        angle["realization_status"] = result["realization_status"]
        angle["realization_feedback"] = result["realization_feedback"]
        angle["pattern_reasoning"] = result["pattern_reasoning"]
        angle["delivered_score"] = result["delivered_score"]
        angle["artifacts"] = result["artifacts"]
        angle["artifacts_dir"] = result["artifacts_dir"]
        # D7 item 4: persist the compiled script itself, not just its judged output - written even
        # for not_realisable angles (the last compile attempt, however broken) since a human
        # debugging a provisioning gap wants to see what the compiler actually produced. Skipped
        # only if compile_script never returned anything at all (script is None/empty).
        if scripts_dir and result.get("script"):
            scripts_dir.mkdir(parents=True, exist_ok=True)
            script_path = scripts_dir / f"{angle.get('id', '?')}.py"
            script_path.write_text(result["script"], encoding="utf-8")
            angle["script_path"] = str(script_path)

    realised_count = sum(1 for a in to_realize if a.get("realization_status") == "realised")
    realised_null_count = sum(1 for a in to_realize if a.get("realization_status") == "realised_null")
    pattern_not_shown_count = sum(1 for a in to_realize if a.get("realization_status") == "pattern_not_shown")
    not_realisable_count = sum(1 for a in to_realize if a.get("realization_status") == "not_realisable")
    print(
        f"[realize] {realised_count} realised, {realised_null_count} realised-null (disconfirmed), "
        f"{pattern_not_shown_count} pattern not shown, {not_realisable_count} not realisable\n"
    )

    # D5-calibrate item 5 / Live Issue 10 fix: dump the ranked, judged AND realized angles for
    # cross-run human curation - see _write_angle_dump's docstring for why this is a file, not an
    # automatic retirement. Written here (after realization, not before it) so the dump carries
    # realization_status/delivered_score/pattern_reasoning for the angles that were realized, not
    # just the D5 judgments - D7's gallery needs both halves, and there is no cost to waiting: the
    # human never consults this file mid-run, only after generate_and_optimize returns.
    dump_path = _write_angle_dump(all_angles, output_dir, timestamp)
    if dump_path:
        print(f"[dump] Surfaced angles (judged + realized) written to {dump_path} - curate into "
              f"the report's Already Explored section as needed.\n")

    # D7: the actual deliverable - a skimmable markdown gallery, tiered by outcome and ranked by
    # insight within the top tier, not the flat best-first list below (which stays as summary_text
    # for console logging / non-visual consumers - see this function's docstring).
    gallery_path = _write_gallery(all_angles, output_dir, timestamp)
    if gallery_path:
        print(f"[gallery] Gallery written to {gallery_path}\n")

    lines = [f"{len(all_angles)} candidate analysis angle(s) generated, ranked best-first:\n"]
    for angle in all_angles:
        lines.append(f"[{angle.get('id', '?')}]")
        for field in _ANGLE_FIELDS[1:]:
            if angle.get(field):
                lines.append(f"  {field}: {angle[field]}")
        if angle.get("insight_score") is not None:
            lines.append(f"  insight_score: {angle['insight_score']:.2f}")
        if angle.get("insight_reasoning"):
            lines.append(f"  insight_reasoning: {angle['insight_reasoning']}")
        if angle.get("soundness_verdict") is not None:
            lines.append(f"  soundness_verdict: {angle['soundness_verdict']}")
        if angle.get("soundness_caveat"):
            lines.append(f"  soundness_caveat: {angle['soundness_caveat']}")
        if angle.get("soundness_reasoning"):
            lines.append(f"  soundness_reasoning: {angle['soundness_reasoning']}")
        if angle.get("realization_status"):
            lines.append(f"  realization_status: {angle['realization_status']}")
            if angle.get("delivered_score") is not None:
                lines.append(f"  delivered_score: {angle['delivered_score']:.2f}")
            if angle.get("pattern_reasoning"):
                lines.append(f"  pattern_reasoning: {angle['pattern_reasoning']}")
            if angle.get("realization_feedback"):
                lines.append(f"  realization_feedback: {angle['realization_feedback']}")
            if angle.get("artifacts"):
                lines.append(f"  artifacts: {_format_artifacts(angle['artifacts'])}")
        lines.append("")

    return {
        "all_angles": all_angles,
        "summary_text": "\n".join(lines),
        "gallery_path": gallery_path,
        "dump_path": dump_path,
        "scripts_dir": str(scripts_dir) if scripts_dir else None,
    }
