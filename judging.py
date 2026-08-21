"""D5: judge every archived angle for insight (non-obviousness) and soundness (defensibility given
the data), independently of each other and of the angle's own self-assessment.
"""

from config import PipelineConfig
from llm import llm_call
from parsing import _ANGLE_FIELDS, extract_xml, format_prompt
from prompts import (
    INSIGHT_JUDGE_PROMPT_PREFIX, INSIGHT_JUDGE_PROMPT_SUFFIX, INSIGHT_JUDGE_SYSTEM,
    SOUNDNESS_JUDGE_PROMPT_PREFIX, SOUNDNESS_JUDGE_PROMPT_SUFFIX, SOUNDNESS_JUDGE_SYSTEM,
)


def _format_angle(angle: dict) -> str:
    """Render one angle's full fields as readable text, for a D5 judge suffix - unlike the
    ideation archive's one-line summary, this includes every _ANGLE_FIELDS value so the judge
    sees the whole idea, not just hypothesis + variables_involved."""
    lines = [f"id: {angle.get('id', '?')}"]
    for field in _ANGLE_FIELDS[1:]:
        if angle.get(field):
            lines.append(f"{field}: {angle[field]}")
    return "\n".join(lines)


async def judge_insight(angle: dict, report: str, ideation_criteria: str, input_metadata: str,
                        config: PipelineConfig) -> dict:
    """D5: score one angle for non-obviousness, grounded in input_metadata and the anti-target
    list (already folded into ideation_criteria) - not the angle's own why_non_obvious
    self-assessment. Live runs showed every angle confidently claiming novelty while most were
    near-identical duplicates, so self-assessment is not evidence.

    Returns {"insight_score": float in [0, 1] or None, "insight_reasoning": str}. None means the
    judge call failed or emitted no parseable <score> - treated as "unranked", not zero.
    """
    # report/ideation_criteria/input_data are identical across every judge call in a run - the
    # SAME triple generate_angles caches - so cached as a prefix; the individual angle varies per
    # call and stays in the suffix (docs/DEVELOPMENT_LOG.md §4).
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


# Three-way verdict instead of a boolean. A boolean sound/unsound collapses "needs a caveat" and
# "cannot be supported at all" into one bucket, which saturates near-constant on a small dataset
# and contributes nothing to ranking - structurally the converger's binary req_pass problem in new
# clothes. The caveat text is carried forward for D7's gallery to DISPLAY, never to filter.
_SOUNDNESS_VERDICTS = ("unsupportable", "caveat", "solid")
_SOUNDNESS_RANK = {"solid": 3, "caveat": 2, "unsupportable": 1}


async def judge_soundness(angle: dict, report: str, ideation_criteria: str, input_metadata: str,
                          config: PipelineConfig) -> dict:
    """D5: judge whether one angle's claimed pattern is defensible given the actual data volume -
    graded, not gated (see _SOUNDNESS_VERDICTS above). Same prefix structure as judge_insight.

    Returns {"soundness_verdict": one of _SOUNDNESS_VERDICTS or None, "soundness_caveat": str,
    "soundness_reasoning": str}. verdict is None if the judge call failed or emitted anything
    outside the three-word vocabulary - treated as "unranked", not "unsupportable", so a prompt
    that drifts off-vocabulary stays visible instead of silently reading as a quality verdict.
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
    unsupportable > unranked regardless of insight score - a hard-gate-then-gradient shape,
    pointed at the judged-angle domain rather than code execution.
    """
    soundness_rank = _SOUNDNESS_RANK.get(angle.get("soundness_verdict"), 0)
    insight_score = angle.get("insight_score")
    insight_rank = insight_score if insight_score is not None else -1.0
    return (soundness_rank, insight_rank)
