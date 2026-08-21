"""Startup preflight (Live Issue 29): verify every configured model is reachable and Docker is
available BEFORE a run commits its ~25-110 LLM calls to it.

Deliberately does NOT catch Run 28's actual failure (DeepSeek running out of credit mid-run) -
credit exhaustion partway through is out of scope for any startup check, and is obvious from the
console anyway when it happens (DEVELOPMENT_LOG.md's Live Issue 29 entry is explicit about this).
What this catches is a bad key, a stale model string, an empty account, or Docker not running -
all knowable in three-to-five trivial calls, before the real spend starts.
"""

import asyncio

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
    fix, and a generic message sends someone to the wrong one (DEVELOPMENT_LOG.md §15's F-class
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


async def run_preflight(config: PipelineConfig) -> bool:
    """Probe every distinct model string this config uses, plus Docker availability. Always
    prints a per-item report; returns True iff every check passed.

    Deduplicates model strings first (cbias currently has three distinct strings across six
    role fields) - one call per string, not per role, since two roles sharing a model string
    would otherwise pay for and report the identical check twice.
    """
    models = sorted({
        config.orchestrator_model, config.worker_model, config.compiler_model,
        config.requirements_evaluator_model, config.angle_model, config.judge_model,
    })

    print(f"[preflight] checking {len(models)} model(s) and Docker availability...")
    results = await asyncio.gather(*(_probe_model(m) for m in models))

    all_ok = True
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
