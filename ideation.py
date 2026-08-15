"""D2/D3: generate candidate analysis angles as structured text (no code, no Docker), and D4's
dedup measurement over the judged archive.
"""

import re

from config import PipelineConfig
from judging import _judgment_sort_key
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
    # and stay in the suffix (see DIVERGER_PLAN.md §4 - both cycling axes belong here, not the prefix).
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


def _angle_signature(angle: dict) -> set:
    """Token set for D4 dedup similarity. hypothesis/variables_involved are counted TWICE -
    near-duplicate angles have been observed sharing topic but differing in method wording, and
    rough_method's extra tokens dilute the signal; this crude weighting biases the Jaccard score
    toward the fields that actually carry the topical signal.
    """
    hypothesis = angle.get("hypothesis", "")
    variables = angle.get("variables_involved", "")
    rough_method = angle.get("rough_method", "")
    return _token_set(f"{hypothesis} {variables} {hypothesis} {variables} {rough_method}")


def _pick_representative(cluster: list[dict]) -> dict:
    """Within a dedup cluster, keep the record whose angle scored highest on _judgment_sort_key
    (soundness_verdict rank, then insight_score) - REQUIRES judging to have already run on every
    record in the cluster (judging happens before dedup, precisely so this can happen).

    Ties on judgment (e.g. both unranked) fall back to the longest why_non_obvious text as a
    stable secondary tiebreak.
    """
    def key(record: dict) -> tuple:
        angle = record["angle"]
        return (_judgment_sort_key(angle), len((angle.get("why_non_obvious") or "").strip()))

    return max(cluster, key=key)


def _dedup_angles(records: list[dict], threshold: float) -> tuple[list[dict], dict]:
    """D4: cluster archive records ({angle, iteration, stance}) by token-set Jaccard similarity
    over _angle_signature, identifying near-duplicates.

    MEASUREMENT ONLY (see DIVERGER_PLAN.md's Live Issue 24 for the full history and decision
    rule): the caller (generate_and_optimize) logs what this function would have merged and does
    not act on it - every judged angle proceeds to ranking regardless of what is returned here.
    Several attempted repairs (a guiding-question guard, chiefly) have been shown to be false
    positives that removed real coverage, and dedup's original justification (saving downstream
    judging cost) no longer applies now that judging runs before dedup - so this preserves the
    "would it ever have fired correctly" measurement at zero cost to run coverage without
    committing to either "keep and enforce" or "delete" while the question is open.

    Greedy single-linkage clustering: each record joins the cluster containing its most similar
    previously-seen record if that similarity clears `threshold`, else it starts a new cluster.
    O(n^2) comparisons, fine at the angle counts this pipeline produces per run.

    Returns (kept_records, merge_stats) where merge_stats = {"within_iteration": int,
    "across_iteration": int, "merges": list[dict]} - counts split so within-iteration
    duplication (stance/question differentiation too weak) and across-iteration duplication
    ({existing_angles} pressure too weak) can be diagnosed separately. "merges" records each
    individual merge event (record id, the id of the most-similar existing record it matched, the
    similarity score, the type, and the id of the cluster's eventual survivor) so which specific
    pair merged, AND which one was kept, can be read off the run log without the two disagreeing.

    best_match is still the best-matching member AT MERGE TIME, not necessarily the survivor -
    _pick_representative runs after clustering completes and can pick a different cluster member
    on soundness/insight, so survivor_id is resolved from the finished clusters below and attached
    to every merge in that cluster.
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

    # Resolve each merge's cluster to the representative _pick_representative actually kept, now
    # that clustering (and therefore the cluster's final membership) is settled. cluster_idx was
    # only ever needed to make this lookup possible - drop it from the public dict so callers see
    # the same shape as before plus survivor_id.
    for merge in merges:
        merge["survivor_id"] = kept[merge.pop("cluster_idx")]["angle"].get("id", "?")

    return kept, {
        "within_iteration": within_iteration,
        "across_iteration": across_iteration,
        "merges": merges,
    }
