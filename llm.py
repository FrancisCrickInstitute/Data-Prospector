"""LLM transport layer: client routing (Anthropic direct + DeepSeek's Anthropic-Messages-API-compatible
endpoint), the core llm_call() interface (caching, images, streaming retry), and the concurrency
semaphore shared by every caller in the pipeline.
"""

import asyncio
import base64
import os
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

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
                   max_tokens: int = 16384, images: list[tuple[str, bytes]] = None,
                   cache_prefix: str = None, reject_truncated: bool = False) -> str:
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
        max_tokens (int): Maximum tokens in response (default 16384 - a floor for a thinking
            model, not a per-caller-tuned budget; callers with a genuinely light response can
            still pass a smaller value).
        images (list[tuple[str, bytes]], optional): (media_type, raw_bytes) pairs, e.g.
            [("image/png", data)], attached as image content blocks between cache_prefix (if any)
            and prompt.
        cache_prefix (str, optional): A stable prefix to mark as an ephemeral cache breakpoint,
            for callers that repeat the same large content across several calls (e.g. compiler
            retries within one design reusing the same analysis/functions, varying only the error
            feedback). Put content that's IDENTICAL across those calls here, and whatever varies
            in `prompt`. No effect (but harmless) if the combined prefix is under the provider's
            minimum cacheable size.
        reject_truncated (bool): If True, a response cut off mid-generation (stop_reason ==
            "max_tokens" but with non-empty text) is treated the same as no text at all - retried
            at double the budget rather than returned. Off by default: most callers extract a
            handful of tags with a parser that can recover from a partial response, and doubling
            their retry rate for that would be pure cost. Set True for callers where a truncated
            response is never usable, e.g. a script that must parse as a whole file (Live Issue
            26 - a mid-token cut compiler response reached the compiler as if it were complete
            and produced a truncation-shaped SyntaxError).

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
    #
    # Streamed rather than called via create() directly: the SDK refuses to send any
    # non-streaming request whose max_tokens implies a possible >10-minute response, and the
    # retry-at-double step below can reach that ceiling on its own once max_tokens is raised.
    # Streaming removes the ceiling instead of moving it again, so a genuine thinking-budget
    # exhaustion still gets a chance to recover on retry rather than failing outright.
    # get_final_message() returns the same Message-shaped object create() always did, so
    # nothing below this block - or any caller of llm_call - needs to change.
    async with LLM_SEMAPHORE:
        for attempt, tokens in enumerate((max_tokens, max_tokens * 2)):
            async with client.messages.stream(
                model=model,
                max_tokens=tokens,
                system=system_content,
                messages=messages,
            ) as stream:
                response = await stream.get_final_message()
            text = "".join(block.text for block in response.content if block.type == "text")
            truncated = response.stop_reason == "max_tokens"
            if text.strip() and not (reject_truncated and truncated):
                return text

            # Either no text at all, or (reject_truncated only) text that was cut off mid-
            # generation rather than finished - both mean the budget ran out. Retry bigger,
            # unless the stop reason rules out a budget problem entirely.
            if not truncated:
                break

    if reject_truncated and text.strip():
        raise ValueError(
            f"Response truncated at max_tokens on both attempts (final budget={tokens}) - the "
            f"model was still mid-generation when the token budget ran out, twice in a row. "
            f"Not a content problem; the caller needs a larger max_tokens or a smaller task."
        )

    content_types = [block.type for block in response.content]
    raise ValueError(
        f"No text content in response (stop_reason={response.stop_reason}, "
        f"blocks={content_types}). The token budget was likely consumed by thinking; "
        f"try a larger max_tokens."
    )
