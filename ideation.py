"""D2/D3: generate candidate analysis angles as structured text (no code, no Docker), plus the
per-iteration diversity measurement (_log_iteration_diversity).
"""

import re

from config import PipelineConfig
from llm import llm_call
from parsing import extract_xml, format_prompt, parse_angles
from prompts import ANGLE_GENERATION_PROMPT_PREFIX, ANGLE_GENERATION_PROMPT_SUFFIX, ANGLE_GENERATION_SYSTEM


async def generate_angles(report: str, ideation_criteria: str, input_metadata: str, config: PipelineConfig,
                          stance: str, guiding_question: str, existing_angles: str, n: int) -> list[dict]:
    """D3: generate n candidate analysis angles as structured text - no code, no Docker.

    Each angle: {id, variables_involved, hypothesis, question_or_stakeholder_served,
    why_non_obvious, rough_method} (see parsing._ANGLE_FIELDS). stance and guiding_question are
    the two independent cycling axes generate_and_optimize assigns per concurrent call;
    existing_angles is the accumulated archive, all three passed straight through to the suffix.

    ideation_criteria (D3b) is only the IDEATION half of the criteria split - guiding questions,
    stakeholders, anti-targets, data constraints - never the deliverable rubric (script-delivery
    mechanics), which is withheld here and held for D6's realisation check instead.
    """
    # report/ideation_criteria/input_data are identical across every angle-generation call in a
    # run, so they're cached as a prefix; stance/guiding_question/existing_angles/n vary per call
    # and stay in the suffix (see docs/DEVELOPMENT_LOG.md §4 - both cycling axes belong here, not the prefix).
    prefix = format_prompt(ANGLE_GENERATION_PROMPT_PREFIX, report=report, ideation_criteria=ideation_criteria,
                           input_data=input_metadata)
    suffix = format_prompt(ANGLE_GENERATION_PROMPT_SUFFIX, stance=stance, guiding_question=guiding_question,
                           existing_angles=existing_angles, n=n)

    response = await llm_call(suffix, system_prompt=ANGLE_GENERATION_SYSTEM, model=config.angle_model,
                              cache_prompt=True, cache_prefix=prefix)
    return parse_angles(extract_xml(response, "angles"))


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
    """Mutate angle['id'] in place to stay unique within a run, suffixing -2, -3, ... on
    collision. Independent concurrent angle-generation calls can propose the same slug - nothing
    keys on id at ideation time, but D7's gallery does, so collisions are resolved here rather
    than left latent.
    """
    base = angle.get("id") or "angle"
    candidate = base
    suffix = 2
    while candidate in seen_ids:
        candidate = f"{base}-{suffix}"
        suffix += 1
    angle["id"] = candidate
    seen_ids.add(candidate)


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
