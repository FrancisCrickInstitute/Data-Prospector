"""D6: realise one judged angle end to end - orchestrator (architecture for this one angle) ->
workers (parallel, one call per function) -> compiler/execute retry loop -> realisation judge.
"""

import asyncio
import re

from config import PipelineConfig
from llm import llm_call
from parsing import extract_xml, format_prompt, parse_tasks
from prompts import (
    COMPILER_PROMPT_PREFIX, COMPILER_PROMPT_SUFFIX, COMPILER_SYSTEM,
    EVALUATOR_SYSTEM, ORCHESTRATOR_PROMPT_PREFIX, ORCHESTRATOR_PROMPT_SUFFIX, ORCHESTRATOR_SYSTEM,
    REALIZATION_VALIDATOR_PROMPT_PREFIX, REALIZATION_VALIDATOR_PROMPT_SUFFIX,
    WORKER_PROMPT_PREFIX, WORKER_PROMPT_SUFFIX, WORKER_SYSTEM,
)
from sandbox import _format_artifacts, _load_plot_images, validate_execution


async def compile_script(orchestrator_results: dict, config: PipelineConfig, error_feedback: str = "",
                         seed_script: str = None, data_profile: str = "") -> str:
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

    # Split at the analysis/functions/library_notes/domain_notes/data_profile/seed boundary:
    # identical across every sequential compile/execute retry for this design (only error_feedback
    # changes attempt to attempt), so it's passed as a cache_prefix rather than folded into one
    # flat prompt. domain_notes/data_profile let a retry fix a path/column/value-mapping bug
    # against the real layout instead of guessing blind from the traceback alone (data_profile:
    # Live Issue 31 - the mechanically-generated real value sets, vs. domain_notes' hand-maintained
    # description).
    compiler_prefix = COMPILER_PROMPT_PREFIX.format(
        analysis=analysis,
        functions=functions_text,
        library_notes=config.available_libraries,
        domain_notes=config.domain_notes,
        data_profile=data_profile,
        seed_section=seed_section,
    )
    compiler_suffix = COMPILER_PROMPT_SUFFIX.format(error_feedback=error_section)

    # reject_truncated=True: a compiled script must parse as a whole file, so a response cut off
    # mid-generation is never usable - retry rather than let a truncation-shaped SyntaxError reach
    # the compile/execute loop as if it were a genuine mistake (Live Issue 26).
    compiled_response = await llm_call(compiler_suffix, system_prompt=COMPILER_SYSTEM, model=config.compiler_model,
                                       cache_prompt=True, max_tokens=16384, cache_prefix=compiler_prefix,
                                       reject_truncated=True)
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


_CRITERION_PATTERN = re.compile(r'<criterion\s+met="(true|false)"\s*/?>', re.IGNORECASE)

# Live Issue 32: the compile-cycling detector compares exec_feedback strings verbatim, but the
# compiler regenerates the WHOLE script every attempt (never a diff/patch), so an identical bug at
# an identical call site still lands on a different source line the moment anything earlier in the
# file changes - which is the common case, not an edge case. Strip what varies between two
# otherwise-identical tracebacks (source line numbers, object memory addresses) before comparing,
# so the detector matches on "same file, same exception" rather than "byte-identical traceback".
_TRACEBACK_LINE_NUMBER = re.compile(r'(File "[^"]*", line )\d+')
_MEMORY_ADDRESS = re.compile(r'0x[0-9a-fA-F]{4,}')


def _normalize_exec_feedback(feedback: str) -> str:
    """Key for the repeat-detection comparison in _run_one_design's compile loop - NOT what's
    shown to the compiler or the reader, which always get the real feedback verbatim."""
    normalized = _TRACEBACK_LINE_NUMBER.sub(r'\1<N>', feedback)
    normalized = _MEMORY_ADDRESS.sub('<ADDR>', normalized)
    return normalized.strip()

# A boolean pattern_shown would conflate a clean disconfirmation (script ran fine, data just
# don't support the hypothesis - a real finding) with a broken/illegible run (blank plot, wrong
# measurement) - both would read as "false" and land in the same realization_status bucket.
# Three-way vocabulary, same shape as judging._SOUNDNESS_VERDICTS: "shown" -> realised,
# "disconfirmed" -> realised_null (ranks ALONGSIDE realised in D7's gallery, not beneath it),
# "not_shown" -> pattern_not_shown (the only one that's actually a quality problem).
_PATTERN_OUTCOMES = ("shown", "disconfirmed", "not_shown")
_PATTERN_OUTCOME_TO_STATUS = {
    "shown": "realised",
    "disconfirmed": "realised_null",
    "not_shown": "pattern_not_shown",
}


async def validate_realization(compiled_script: str, report: str, deliverable_rubric: str,
                                claimed_pattern: str, exec_output: str, config: PipelineConfig,
                                angle_scope: str = "", artifacts: list[dict] = None,
                                artifacts_dir: str = None) -> tuple[str, float, str, str]:
    """D6: check whether a realized script's actual output legibly shows ONE angle's claimed
    pattern - the PRIMARY judgment, replacing the converger's "meets requirements" framing. The
    deliverable rubric's mechanical checklist (file counts, etc.) is still checked and reported,
    but graded alongside pattern_outcome rather than gating it - the same graded-not-gated shape
    as the soundness verdict.

    angle_scope is the angle's own declared variables/method - deliverable_rubric is one shared
    checklist for the WHOLE report, cached identically across every angle in a run, so without
    this a narrow single-angle script gets graded (and penalized) against bullets it was never
    designed to touch. Passed to the validator so it can SKIP (not emit a <criterion> tag for)
    bullets that are out of scope for this angle by design, rather than either hardcoding a
    per-angle rubric (extra LLM call, breaks the prefix cache) or a blind mechanical cap. Varies
    per angle, so it lives in the suffix, not the cached prefix.

    Returns (pattern_outcome, delivered_score, pattern_reasoning, feedback). pattern_outcome is
    one of _PATTERN_OUTCOMES, or None if the validator emitted anything outside that vocabulary (a
    warning is printed - _run_one_design treats None the same as "not_shown", the conservative
    default, since an unparseable response gives no positive evidence the pattern WAS shown or
    disconfirmed). delivered_score is met/total across every <criterion> tag the validator emitted
    against the deliverable rubric (0.0 if it emitted none - treated as a full miss, not a free
    pass). pattern_reasoning is the validator's own justification for the pattern_outcome verdict -
    distinct from feedback, which covers the deliverable-rubric checklist.
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
    # This is the most context-heavy call in the pipeline (report + rubric + angle_scope + script
    # + console output + up to _MAX_VALIDATOR_IMAGES PNGs) - pass an explicit budget matching
    # compile_script's, rather than relying on the generic default being right for the heaviest
    # caller in the pipeline.
    validator_response = await llm_call(validator_suffix, system_prompt=EVALUATOR_SYSTEM,
                                        model=config.requirements_evaluator_model, cache_prompt=True,
                                        max_tokens=16384, images=images or None, cache_prefix=validator_prefix)
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

    return pattern_outcome, delivered_score, pattern_reasoning, feedback


async def _call_worker(task_info: dict, task_index: int, report: str, input_metadata: str,
                       config: PipelineConfig, data_profile: str = "") -> dict:
    """Call worker for a single task. Used for parallel execution."""
    func_name = task_info.get("function", f"task_{task_index}")
    # report/input_data/library_notes/domain_notes/data_profile are identical across every task in
    # this design, so they're cached as a prefix; function/description/input/output vary and stay
    # in the suffix.
    worker_prefix = format_prompt(
        WORKER_PROMPT_PREFIX,
        original_report=report,
        input_data=input_metadata,
        library_notes=config.available_libraries,
        domain_notes=config.domain_notes,
        data_profile=data_profile,
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


async def _run_one_design(angle: dict, report: str, deliverable_rubric: str, input_metadata: str,
                          config: PipelineConfig, data_dir: str, artifacts_dir: str, label: str,
                          max_compile_attempts: int = 3, data_profile: str = "") -> dict:
    """D6: realize ONE judged angle (orchestrate -> workers -> compile/execute loop -> realization
    check). The angle's hypothesis/rough_method - not the whole report - is the brief the
    orchestrator designs against; report/deliverable_rubric stay the TRUE, identical background
    context shared by every angle realized this run, so ORCHESTRATOR_PROMPT_PREFIX and
    WORKER_PROMPT_PREFIX both still hit cache across the top-k angles, not just within one angle's
    own compile retries. data_profile (Live Issue 31) is the mechanically-generated real-value
    counterpart to domain_notes, reaching the same three prefixes (orchestrator/worker/compiler);
    "" (its default) when config.data_profile isn't set, so this degrades gracefully for domain
    configs that haven't defined one.

    Returns {angle_id, realization_status, realization_feedback, pattern_reasoning, delivered_score,
    artifacts, artifacts_dir, script}. pattern_reasoning is the validator's justification for the
    pattern_outcome verdict - "" for the not_realisable early-returns below, since those never
    reach validate_realization. realization_status is one of:
    - "realised": executed, and the claimed pattern was legibly shown.
    - "realised_null": executed and rendered legibly, but the data do NOT support the claimed
      pattern - a clean disconfirmation, not a failure. Ranks ALONGSIDE "realised" in D7's
      gallery, not beneath it.
    - "pattern_not_shown": executed, but the output does not legibly show anything about the claim
      either way (broken/blank/unreadable, or the validator's response was itself unparseable).
      THIS is the actual quality judgement, not "realised_null" or a disconfirmation. Deliberately
      not named "unsound" - that word is D5's soundness-judge vocabulary (data can't support the
      claim), a different judge answering a different question; conflating the two would mislabel
      D7's gallery.
    - "not_realisable": never executed after max_compile_attempts (e.g. a missing library) or
      execution was unverifiable (no data_dir / Docker unavailable) - an engineering/provisioning
      outcome, never conflated with "pattern_not_shown" or "realised_null".
    - "realization_error": the pipeline broke on this angle for an infrastructure reason - not
      angle-quality, not provisioning - at some stage from the orchestrator call onward. If the
      break happened after a verified Docker execution PASS, script/artifacts are real and
      attached; earlier failures (e.g. a worker call exhausting its token budget) carry whatever
      of those exists, which may be nothing. A THIRD kind of "not good", distinct from both quality
      outcomes above and from "not_realisable" - unlike a provisioning gap, nothing about the angle
      or the environment is at fault, and unlike pattern_not_shown, no judge ever looked at the
      output.
    """

    def log(msg):
        print(f"  [{label}] {msg}")

    # Defined up front and populated as each stage completes, so the except clause at the bottom
    # can always return whatever real output exists, however far execution got - and `stage`
    # records which call raised, so a failure can be pinned to a call site without console-log
    # archaeology.
    compiled_script, exec_output, artifacts = None, "", []
    stage = "orchestrator"
    try:
        # ORCHESTRATOR: design an architecture for THIS ONE angle.
        # report/input_data/criteria (deliverable_rubric) are identical across every angle realized
        # this run, so cached as a prefix; the angle itself varies per call and stays in the suffix.
        orchestrator_prefix = format_prompt(
            ORCHESTRATOR_PROMPT_PREFIX, report=report, criteria=deliverable_rubric, input_data=input_metadata,
            domain_notes=config.domain_notes, data_profile=data_profile,
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

        # WORKERS: implement each function in parallel. return_exceptions=True means one worker
        # exhausting its token budget doesn't take the whole gather down with it, losing the N-1
        # functions that succeeded along with it - it degrades to a placeholder body that says so,
        # so the compiler sees an honest gap instead of a missing function it never knew was missing.
        stage = "workers"
        worker_raw = await asyncio.gather(
            *[_call_worker(t, i, report, input_metadata, config, data_profile=data_profile)
              for i, t in enumerate(tasks, 1)],
            return_exceptions=True,
        )
        worker_results = []
        failed_functions = []
        for task, result in zip(tasks, worker_raw):
            func_name = task.get("function", "?")
            if isinstance(result, Exception):
                failed_functions.append(func_name)
                worker_results.append({
                    "function": func_name,
                    "description": task.get("description", ""),
                    "result": (
                        f"# WORKER CALL FAILED: {result!r}\n"
                        f"# This function could not be implemented. Work around its absence - omit "
                        f"or simplify whatever depended on it - rather than assuming it exists."
                    ),
                })
            else:
                worker_results.append(result)
        if failed_functions:
            log(f"Workers: {len(tasks) - len(failed_functions)}/{len(tasks)} succeeded "
                f"- failed: {', '.join(failed_functions)}")
        orchestrator_results = {"analysis": analysis, "worker_results": worker_results}

        # COMPILER + (grounded) EXECUTION: retries up to max_compile_attempts, feeding the
        # execution error back into the next compile attempt. Log each attempt's FAIL reason as it
        # happens (previously only the LAST attempt's feedback was ever visible, in the eventual
        # not_realisable message) and abort early if an error recurs, since that means the compiler
        # isn't repairing anything and the remaining attempts would just spend Docker/LLM budget
        # for no gain. Track every FAIL string seen so far, not just the immediately preceding one -
        # a consecutive-only comparison misses an oscillating loop (attempt 1 error A, attempt 2
        # error B, attempt 3 error A again), which is still going in circles even though no two
        # *adjacent* attempts match.
        stage = "compile"
        execution_passed = False
        exec_verdict = "FAIL"
        compile_error = ""
        attempt_feedbacks = []
        seen_feedbacks = set()
        aborted_on_repeat = False
        for attempt in range(max_compile_attempts):
            log(f"Compile attempt {attempt + 1}/{max_compile_attempts}...")
            compiled_script = await compile_script(orchestrator_results, config, error_feedback=compile_error,
                                                   data_profile=data_profile)
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
            # Live Issue 32: normalize before comparing - the compiler regenerates the WHOLE
            # script every attempt, so an identical bug at an identical call site still lands on
            # a different source line the moment anything earlier in the file changes (the common
            # case, not an edge case). A verbatim .strip() comparison only ever matched when the
            # regenerated script happened to place the failing line at the same line number.
            normalized_feedback = _normalize_exec_feedback(exec_feedback)
            if normalized_feedback in seen_feedbacks:
                # Only an actual saving if attempts remain to skip - with max_compile_attempts=3,
                # the earliest a two-cycle (A, B, A) repeats is attempt 3, where the loop was
                # about to end anyway and there is nothing left to abort into (Live Issue 27).
                # Log accordingly rather than always claiming a saving that may not have happened.
                remaining = max_compile_attempts - 1 - attempt
                if remaining > 0:
                    log(f"  This error already occurred in an earlier attempt - aborting the "
                        f"{remaining} remaining compile attempt(s) (the compiler is cycling, "
                        f"not repairing).")
                else:
                    log("  This error already occurred in an earlier attempt - it was the "
                        "last attempt available, so nothing was saved by detecting it.")
                aborted_on_repeat = remaining > 0
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
        # actual output shows THIS angle's claimed pattern; the deliverable-rubric checklist is
        # reported alongside but does not gate status - graded, not gated, matching the soundness
        # verdict's shape. An unparseable pattern_outcome (None) maps to "pattern_not_shown" - the
        # conservative default, since it gives no positive evidence either way. The angle's own
        # declared scope, not the whole report, is what the deliverable rubric should be judged
        # against for this script - see validate_realization's docstring.
        angle_scope = (
            f"Variables: {angle.get('variables_involved', '')}\n"
            f"Method: {angle.get('rough_method', '')}"
        )
        stage = "validate"
        pattern_outcome, delivered_score, pattern_reasoning, realization_feedback = await validate_realization(
            compiled_script, report, deliverable_rubric, angle.get("hypothesis", ""), exec_output, config,
            angle_scope=angle_scope, artifacts=artifacts, artifacts_dir=artifacts_dir)
        status = _PATTERN_OUTCOME_TO_STATUS.get(pattern_outcome, "pattern_not_shown")
        # pattern_reasoning is the whole point of the three-way split - without it, pattern_not_shown
        # and a plausible disconfirmation are indistinguishable from the console alone.
        log(f"Realization: {status} (delivered_score={delivered_score:.2f}) - {pattern_reasoning}")
        return {
            "angle_id": angle.get("id", "?"), "realization_status": status,
            "realization_feedback": realization_feedback, "pattern_reasoning": pattern_reasoning,
            "delivered_score": delivered_score, "artifacts": artifacts, "artifacts_dir": artifacts_dir,
            "script": compiled_script,
        }
    except Exception as exc:
        # ANY exception from here on down - orchestrator, workers, compiler, or validator - lands
        # here rather than unwinding out of the function. `stage` says which call was in flight;
        # compiled_script/exec_output/artifacts carry whatever was produced before the break, which
        # is real output when the failure is late (validator) and legitimately empty when it's
        # early (orchestrator). Without this, an exception from any of these four call sites would
        # unwind past this function entirely, discard the script, and get relabelled
        # "not_realisable" one level up in generate_and_optimize - printing a phantom `requires`
        # gap for a run that had no provisioning problem at all.
        log(f"[realization_error] Pipeline failed at stage '{stage}': {exc!r}")
        return {
            "angle_id": angle.get("id", "?"), "realization_status": "realization_error",
            "realization_feedback": f"Pipeline failed at stage '{stage}' for this angle: {exc!r}",
            "pattern_reasoning": "", "delivered_score": None, "artifacts": artifacts,
            "artifacts_dir": artifacts_dir, "script": compiled_script,
            # Live Issue 28: the gallery's realization_error tier asserted a verified execution
            # unconditionally, which is only true when the break happened at "validate" - earlier
            # stages (orchestrator/workers/compile) never reached a verified PASS, so there is no
            # script or output to judge. Exposing the stage as its own field (rather than leaving
            # it embedded only in the feedback string above) lets output.py branch the gallery
            # wording on it instead of guessing from prose.
            "error_stage": stage,
        }
