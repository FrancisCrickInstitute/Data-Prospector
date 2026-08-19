"""Diverger pipeline orchestration: criteria split -> ideate (fan-out) -> judge -> dedup
(measurement only) -> rank -> realise top-k -> gallery. See CLAUDE.md for the architecture and
DIVERGER_PLAN.md for the full design/run/decision history. This module holds only
generate_and_optimize - every stage's actual implementation lives in its own module (llm.py,
parsing.py, sandbox.py, ideation.py, judging.py, realization.py, output.py).
"""

import asyncio
from datetime import datetime
from pathlib import Path

from config import PipelineConfig
from ideation import _angle_record, _dedup_angles, _ensure_unique_id, _log_iteration_diversity, generate_angles
from judging import _judgment_sort_key, judge_insight, judge_soundness
from llm import llm_call
from output import _write_angle_dump, _write_gallery
from parsing import _ANGLE_FIELDS, _extract_markdown_section, _parse_guiding_questions, extract_xml, format_prompt
from prompts import CRITERIA_PROMPT, CRITERIA_SYSTEM
from realization import _run_one_design


async def generate_and_optimize(report: str, config: PipelineConfig, data_dir: str = None,
                                max_iterations: int = 2, output_dir: str = None,
                                realize_top_k: int = 4, angles_per_iteration: int = 12) -> dict:
    """Ideation loop, fanned out, then judged, then deduped (measurement only), then selectively
    realized, then written up as a gallery. Each iteration fires angles_per_iteration independent
    generate_angles calls (n=1 each) concurrently via asyncio.gather, cycling
    config.design_stances and the parsed guiding questions across calls independently for
    intra-iteration diversity - concurrent calls can't see each other, so these two cycling axes
    are the only lever within an iteration. Cross-iteration diversity instead comes from
    {existing_angles}: the accumulated archive of every angle proposed so far, fed back into the
    angle-generation prompt suffix. Once ideation finishes, judging scores every archived angle
    for non-obviousness (judge_insight) and soundness (judge_soundness), and dedup runs against
    the judged archive but MEASUREMENT ONLY (see DIVERGER_PLAN.md's Live Issue 24) - it logs what
    it would have merged and is not acted on, so every judged angle is ranked. Realisation then
    handles only the top realize_top_k non-unsupportable angles - code is written and run for that
    small selection only, never for the whole archive.

    Returns a dict:
    - "all_angles": every judged angle dict (dedup does not remove any - see Live Issue 24),
      ranked best-first by _judgment_sort_key, each carrying its judgment and (if realized) its
      realisation result fields.
    - "gallery_path" / "dump_path": paths to the two files written to output_dir (_write_gallery,
      _write_angle_dump), or "" if output_dir wasn't given.
    - "scripts_dir": the directory each realized angle's compiled script was written into, or None.
    """
    input_metadata = config.extract_input_metadata(data_dir) if data_dir else "(No input data provided)"
    # Live Issue 31: a mechanical, per-run profile of the real data (column names/dtypes/null
    # counts/full value sets - no LLM involved), computed once here and threaded only into
    # realisation (orchestrator/worker/compiler - the same reach domain_notes already has), never
    # into ideation - same "realisation constraint, not an ideation constraint" boundary
    # available_libraries already draws. config.data_profile is optional (None for configs that
    # haven't defined one yet), so this degrades to "(no data profile available)" rather than
    # erroring.
    data_profile = (
        config.data_profile(data_dir) if data_dir and config.data_profile
        else "(no data profile available)"
    )

    # Parse the report into two separate rubrics ONCE, shared by every call that needs them. This
    # is what actually makes the pipeline domain-agnostic - without it, the ideation and (later)
    # judging prompts would have to hardcode the shape of "success" for one specific kind of
    # report. Splitting by consumer stops ideation from paying cached tokens on deliverable rubric
    # text ("runs without errors", "clean code") that has nothing to do with idea quality:
    #   - ideation_criteria: guiding questions/stakeholders/anti-targets/data constraints - fed to
    #     generate_angles below (and, later, the judges).
    #   - deliverable_rubric: script-delivery mechanics - fed to _run_one_design/validate_realization
    #     below, only for the small top-k set of angles actually realized.
    # If extraction itself fails (e.g. a transient rate-limit error) OR comes back malformed (one
    # or both tags missing, or both tags collapsing to the same text), fall back to the raw report
    # for both instead of leaving either pointed at an empty rubric - a missing or duplicated tag
    # raises here and hits the same honest raw-report fallback as a call failure.
    try:
        criteria_input = format_prompt(CRITERIA_PROMPT, report=report, input_data=input_metadata)
        criteria_response = await llm_call(criteria_input, system_prompt=CRITERIA_SYSTEM,
                                           model=config.requirements_evaluator_model, cache_prompt=True)
        ideation_criteria = extract_xml(criteria_response, "ideation_criteria").strip()
        deliverable_rubric = extract_xml(criteria_response, "deliverable_rubric").strip()
        # The model occasionally ignores the <ideation_criteria>/<deliverable_rubric> tags and
        # mirrors the report's own markdown headers back instead (e.g. '# IDEATION CRITERIA') -
        # try recovering the same content under that heading before giving up and degrading to
        # the raw-report fallback below.
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
    print(f"\nDeliverable rubric extracted from report (fed to realization only):\n{deliverable_rubric}\n")

    # Guiding questions, the second cycling axis, parsed once from the raw report (they don't
    # change run to run). Empty means the report's guiding-questions section wasn't found/parseable
    # - every call falls back to a placeholder rather than cycling a mis-parsed list.
    guiding_questions = _parse_guiding_questions(report)
    if not guiding_questions:
        print(
            "WARNING: Could not parse guiding questions from the report (no heading matching "
            "'guiding question' with a numbered list under it) - the second cycling axis is "
            "disabled this run; every call gets a placeholder guiding_question."
        )

    stances = config.design_stances
    # Archive: every angle proposed so far across all iterations, as {angle, iteration, stance}
    # records - not executed scripts, so there's no score to cap by (dedup handles this instead,
    # below).
    archive: list[dict] = []
    # ids seen so far this run, across all iterations - collisions between independent concurrent
    # calls get suffixed here before the angle ever reaches the archive.
    seen_ids: set = set()

    for iteration in range(max_iterations):
        print(f"\n{'=' * 80}")
        print(f"ITERATION {iteration + 1}/{max_iterations}  ({angles_per_iteration} angles, fanned out)")
        print(f"{'=' * 80}")

        # {existing_angles} is the only cross-iteration divergence pressure (stance and guiding
        # question are the intra-iteration ones, below). It goes in the SUFFIX, not the PREFIX -
        # it grows every iteration and would invalidate the cache if it were cached (CLAUDE.md's
        # caching table).
        existing_angles_section = "\n".join(
            _angle_record(rec["angle"], rec["iteration"], rec["stance"]) for rec in archive
        ) or "(none yet)"

        def _stance_for(m: int) -> str:
            return stances[(m + iteration) % len(stances)]

        def _question_for(m: int) -> str:
            return guiding_questions[
                (m + iteration * angles_per_iteration) % len(guiding_questions)
            ] if guiding_questions else "(none identified this run - use your own judgement)"

        # N independent calls of one angle each, not one call asking for N - independent samples
        # diverge more than one sample self-organising within a single context. Call m gets
        # (stance[m % S], question[m % Q]) as two INDEPENDENT cycling axes - e.g. 4 calls over 5
        # questions structurally can't all land on the same question, unlike stance alone. A call
        # that raises is dropped with a logged warning rather than failing the iteration.
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
        return {"all_angles": [], "gallery_path": "", "dump_path": "", "scripts_dir": None}

    # Judge EVERY archived angle - not just the post-dedup subset - for non-obviousness and
    # soundness, BEFORE dedup runs (dedup used to run first and its representative-picking logic
    # broke ties on longest why_non_obvious, a text-length proxy that discarded the stronger of
    # two merged angles without it ever reaching a judge). Judge calls share one cached prefix
    # (report/ideation_criteria/input_data - the same triple generate_angles caches), so judging
    # all N archived angles instead of the deduped subset costs little extra. A failed call scores
    # that angle "unranked" (None) rather than failing the run or being penalised as if actually
    # judged.
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

    # Dedup is MEASUREMENT ONLY, not acted on (DIVERGER_PLAN.md Live Issue 24). _dedup_angles still
    # clusters the whole run's archive (all iterations) exactly as before, but its result no longer
    # filters all_angles - every judged angle proceeds to ranking regardless of what would have
    # merged.
    kept_records, merge_stats = _dedup_angles(archive, config.angle_similarity_threshold)
    print(
        f"[dedup] MEASUREMENT ONLY, not acted on - {len(archive)} angle(s), "
        f"{len(kept_records)} would remain after dedup (threshold={config.angle_similarity_threshold}); "
        f"would merge {merge_stats['within_iteration']} within-iteration, "
        f"{merge_stats['across_iteration']} across-iteration duplicate(s)"
    )
    for cluster in merge_stats["clusters"]:
        # One line per actual cluster, not per pairwise event (Live Issue 34): a cluster with 3+
        # members forms from several pairwise merges, and printing those in isolation misled a
        # reader on a chain - "merged A into B" then "would keep C" looked like a mismatched pair
        # even though C simply joined the same cluster via a later event. Report what would
        # actually happen instead: every member, the one representative, and the pairwise
        # similarities that built the cluster. None of this is applied - see the comment above.
        members = ", ".join(f"[{m}]" for m in cluster["members"])
        print(f"    cluster {{{members}}} -> would keep [{cluster['representative']}]")
        for pair in cluster["pairwise"]:
            print(
                f"        [{pair['record_id']}] -> [{pair['matched_id']}] "
                f"(similarity={pair['similarity']:.3f}, {pair['type']})"
            )
    print()
    all_angles = [rec["angle"] for rec in archive]

    if not all_angles:
        return {"all_angles": [], "gallery_path": "", "dump_path": "", "scripts_dir": None}

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

    # Realize only the top-k ranked, non-unsupportable angles - selective execution, not every
    # candidate. all_angles is already sorted best-first by _judgment_sort_key; unsupportable
    # angles are skipped entirely rather than paying a Docker run to visualize a claim the judge
    # already said the data can't support.
    realizable_angles = [a for a in all_angles if a.get("soundness_verdict") != "unsupportable"]
    to_realize = realizable_angles[:realize_top_k]
    skipped_unsupportable = len(all_angles) - len(realizable_angles)
    print(
        f"[realize] Realizing top {len(to_realize)} of {len(all_angles)} angle(s) "
        f"({skipped_unsupportable} unsupportable angle(s) skipped)\n"
    )

    # One timestamp shared by the gallery, the surfaced_angles dump, and the scripts directory for
    # this run, so the three files/dirs a human needs to cross-reference for one run all carry the
    # same run identifier instead of each stamping a fractionally different clock read.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifacts_base = Path(output_dir) / "artifacts" if output_dir else None
    scripts_dir = Path(output_dir) / "scripts" / timestamp if output_dir else None
    realize_calls = [
        _run_one_design(
            angle, report, deliverable_rubric, input_metadata, config, data_dir,
            data_profile=data_profile,
            artifacts_dir=str(artifacts_base / angle.get("id", "?")) if artifacts_base else None,
            label=angle.get("id", "?"),
        )
        for angle in to_realize
    ]
    realize_results = await asyncio.gather(*realize_calls, return_exceptions=True)

    # _run_one_design wraps its ENTIRE body in try/except and always returns a result dict
    # (status "realization_error" on failure, carrying whatever script/artifacts exist) rather
    # than raising - so this isinstance(result, Exception) branch should be unreachable in normal
    # operation. return_exceptions=True stays as defense-in-depth only (e.g. a bug inside
    # _run_one_design's own except handler); if this WARNING ever fires, that is itself a bug to
    # investigate, not a routine "an angle failed" message - "not_realisable" here would once
    # again mislabel an infrastructure failure as a provisioning gap.
    for angle, result in zip(to_realize, realize_results):
        if isinstance(result, Exception):
            print(f"WARNING: realization failed for angle {angle.get('id', '?')} - this should be "
                  f"unreachable now that _run_one_design catches its own exceptions: {result!r}")
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
        # Live Issue 28: only meaningful (non-None) when realization_status is "realization_error" -
        # tells output.py how far the pipeline actually got before breaking, so the gallery can stop
        # asserting a verified execution that may never have happened.
        angle["error_stage"] = result.get("error_stage")
        # Persist the compiled script itself, not just its judged output - written even for
        # not_realisable angles (the last compile attempt, however broken) since a human debugging
        # a provisioning gap wants to see what the compiler actually produced. Skipped only if
        # compile_script never returned anything at all (script is None/empty).
        if scripts_dir and result.get("script"):
            scripts_dir.mkdir(parents=True, exist_ok=True)
            script_path = scripts_dir / f"{angle.get('id', '?')}.py"
            script_path.write_text(result["script"], encoding="utf-8")
            angle["script_path"] = str(script_path)

    realised_count = sum(1 for a in to_realize if a.get("realization_status") == "realised")
    realised_null_count = sum(1 for a in to_realize if a.get("realization_status") == "realised_null")
    pattern_not_shown_count = sum(1 for a in to_realize if a.get("realization_status") == "pattern_not_shown")
    not_realisable_count = sum(1 for a in to_realize if a.get("realization_status") == "not_realisable")
    # Kept separate from not_realisable_count - conflating them in this log line would reproduce
    # the exact mislabelling the realization_error status exists to prevent, just one line up
    # instead of in the gallery.
    realization_error_count = sum(1 for a in to_realize if a.get("realization_status") == "realization_error")
    print(
        f"[realize] {realised_count} realised, {realised_null_count} realised-null (disconfirmed), "
        f"{pattern_not_shown_count} pattern not shown, {not_realisable_count} not realisable, "
        f"{realization_error_count} realization judge error(s)\n"
    )

    # Dump the ranked, judged AND realized angles for cross-run human curation - see
    # _write_angle_dump's docstring for why this is a file, not an automatic retirement. Written
    # here (after realization, not before it) so the dump carries realization_status/
    # delivered_score/pattern_reasoning for the angles that were realized, not just the judgments -
    # the gallery needs both halves, and there is no cost to waiting: the human never consults
    # this file mid-run, only after generate_and_optimize returns.
    dump_path = _write_angle_dump(all_angles, output_dir, timestamp)
    if dump_path:
        print(f"[dump] Surfaced angles (judged + realized) written to {dump_path} - curate into "
              f"the report's Already Explored section as needed.\n")

    # The actual deliverable - a skimmable markdown gallery, tiered by outcome and ranked by
    # insight within the top tier.
    gallery_path = _write_gallery(all_angles, output_dir, timestamp)
    if gallery_path:
        print(f"[gallery] Gallery written to {gallery_path}\n")

    return {
        "all_angles": all_angles,
        "gallery_path": gallery_path,
        "dump_path": dump_path,
        "scripts_dir": str(scripts_dir) if scripts_dir else None,
    }
