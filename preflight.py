"""Startup preflight (Live Issue 29): verify every configured model is reachable and Docker is
available BEFORE a run commits its ~25-110 LLM calls to it.

Deliberately does NOT catch Run 28's actual failure (DeepSeek running out of credit mid-run) -
credit exhaustion partway through is out of scope for any startup check, and is obvious from the
console anyway when it happens (docs/DEVELOPMENT_LOG.md's Live Issue 29 entry is explicit about this).
What this catches is a bad key, a stale model string, an empty account, Docker not running, or a
bad --report/--data-dir - all knowable instantly and locally, before the real spend starts.

The report/data-dir checks exist because both failure modes were previously either late or silent:
a bad --report currently isn't caught until main()'s plain open()/read() call, which runs AFTER
preflight's model/Docker probes have already spent their (small, but nonzero) cost; a bad --data-dir
is worse - confirmed against cbias_config.py's extract_input_metadata, Path.glob against a
nonexistent directory doesn't raise, it silently yields nothing, so the run would sail through every
LLM call producing a gallery built from no real data instead of failing anywhere at all.
"""

import asyncio
from pathlib import Path

import anthropic

from config import PipelineConfig
from llm import _client_for_model
from sandbox import is_docker_available

# Bounded and cheap on purpose - this is a reachability probe, not a real call. max_tokens=8 is
# enough to round-trip a response without paying for a real generation; a network genuinely down
# should fail well inside this window rather than hang the whole run at the very first step.
_PROBE_MAX_TOKENS = 8
_PROBE_TIMEOUT_SECONDS = 15


def _describe_status_error(e: anthropic.APIStatusError) -> str:
    """Turn a status code into the specific action it implies, not a generic "model unavailable" -
    401/403 (credential), 402 (balance) and 404 (usually a stale model string, and §5's per-role
    tiering means model names here change more often than in most projects) all need a different
    fix, and a generic message sends someone to the wrong one (docs/DEVELOPMENT_LOG.md §15's F-class
    error, in miniature).
    """
    code = e.status_code
    if code in (401, 403):
        return f"HTTP {code} - credential problem, check the API key"
    if code == 402:
        return f"HTTP {code} - insufficient balance / payment required"
    if code == 404:
        return f"HTTP {code} - not found, likely a stale or misspelled model string"
    return f"HTTP {code}: {e}"


async def _probe_model(model: str) -> tuple[str, bool, str]:
    """One trivial, minimal-cost call per model - tests the TRANSPORT only, never the content.

    Deliberately does NOT go through llm_call. A minimal call to an adaptive-thinking model (e.g.
    deepseek-v4-pro, cbias's worker/compiler tier) returns a thinking block and no text at a small
    max_tokens - confirmed live, not assumed - which is exactly the shape llm_call's "no text
    content" ValueError exists to catch (Live Issue 21). Routed through llm_call, this preflight
    would raise on that response and misreport every such model as broken. Calling the client
    directly and catching only request-level errors means a successful HTTP response is a pass
    regardless of what came back - only an actual transport/auth/model-string failure counts.
    """
    client = _client_for_model(model)
    try:
        await client.messages.create(
            model=model,
            max_tokens=_PROBE_MAX_TOKENS,
            messages=[{"role": "user", "content": "ping"}],
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
        return model, True, "reachable"
    except anthropic.APIStatusError as e:
        return model, False, _describe_status_error(e)
    except anthropic.APIConnectionError as e:
        return model, False, f"network unreachable: {e}"


def _check_report_path(report_path: str) -> tuple[bool, str]:
    """report_path must exist and be a file - main()'s first act is a plain open()/read() with no
    error handling of its own, so this is the only thing standing between a typo'd --report and a
    raw traceback after the model/Docker probes below have already run."""
    p = Path(report_path)
    if not p.is_file():
        return False, f"not found: {p}"
    return True, f"found ({p})"


def _check_data_dir(data_dir: str) -> tuple[bool, str]:
    """data_dir must exist and contain at least one entry. Deliberately just an existence/non-empty
    check, not a domain-specific shape check (that's what each config's own extract_input_metadata
    does at ideation time) - this only exists to catch the case that check can't: a directory that
    isn't there at all, which every domain config's real-data scan (confirmed against
    cbias_config.py) silently tolerates rather than raising on."""
    p = Path(data_dir)
    if not p.is_dir():
        return False, f"not found: {p}"
    if not any(p.iterdir()):
        return False, f"exists but is empty: {p}"
    return True, f"found and non-empty ({p})"


async def run_preflight(config: PipelineConfig, report_path: str, data_dir: str) -> bool:
    """Probe every distinct model string this config uses, plus Docker availability and the
    --report/--data-dir paths. Always prints a per-item report; returns True iff every check passed.

    Path checks run first and short-circuit the rest on failure - they're free and local, so a bad
    --report/--data-dir is reported immediately rather than making someone wait on network probes
    (small cost each, but nonzero, and pointless to spend on a run that can't proceed anyway).

    Deduplicates model strings first (cbias currently has three distinct strings across six
    role fields) - one call per string, not per role, since two roles sharing a model string
    would otherwise pay for and report the identical check twice.
    """
    print("[preflight] checking --report/--data-dir...")

    path_results = [
        ("report", *_check_report_path(report_path)),
        ("data_dir", *_check_data_dir(data_dir)),
    ]
    for label, ok, detail in path_results:
        print(f"  [{'OK' if ok else 'FAIL'}] {label}: {detail}")
    if not all(ok for _, ok, _ in path_results):
        print("[preflight] one or more checks FAILED\n")
        return False

    models = sorted({
        config.orchestrator_model, config.worker_model, config.compiler_model,
        config.requirements_evaluator_model, config.angle_model, config.judge_model,
    })

    print(f"[preflight] checking {len(models)} model(s) and Docker availability...")

    all_ok = True
    results = await asyncio.gather(*(_probe_model(m) for m in models))

    for model, ok, detail in results:
        print(f"  [{'OK' if ok else 'FAIL'}] {model}: {detail}")
        all_ok = all_ok and ok

    docker_ok = is_docker_available()
    docker_detail = (
        "daemon reachable" if docker_ok
        else "not available - every realisation this run attempts would be SKIPPED, not just failed"
    )
    print(f"  [{'OK' if docker_ok else 'FAIL'}] docker: {docker_detail}")
    all_ok = all_ok and docker_ok

    print(f"[preflight] {'all checks passed' if all_ok else 'one or more checks FAILED'}\n")
    return all_ok
