"""D7: the pipeline's actual deliverable - a skimmable, tiered markdown gallery - plus the
per-run surfaced-angles dump used for cross-run curation.
"""

from pathlib import Path

from sandbox import _format_artifacts


def _write_angle_dump(all_angles: list[dict], output_dir: str, timestamp: str) -> str:
    """Dump this run's ranked, judged AND realized angles to a human-readable file. Called after
    D6's realize step so the dump carries realization_status/delivered_score/pattern_reasoning,
    not just D5's soundness/insight judgments. Angles outside the realized top-k (skipped as
    unsupportable, or ranked below --realize-top-k) simply have no realization_* keys - the
    per-angle rendering below is guarded accordingly.

    {existing_angles} only gives cross-iteration memory WITHIN a run - the report's "Already
    Explored" section is the only memory that persists across runs, and it's maintained by hand.
    This file is the raw material for that: a human skims it and copies entries worth retiring
    into the report themselves. Nothing here is applied automatically - automatic retirement would
    suppress angles that merely resemble a prior one, which is explicitly not wanted.

    timestamp is passed in rather than generated here, so this file, the gallery
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


# status -> heading label for the top gallery tier. Both statuses share one tier (ranked by
# insight, not separated) - see _write_gallery's docstring for why a disconfirmation is not
# demoted beneath a confirmation.
_GALLERY_STATUS_LABELS = {"realised": "realised — pattern shown", "realised_null": "realised — disconfirmed"}


def _gallery_entry_images(angle: dict) -> list[str]:
    """Relative markdown image paths for one angle's non-empty PNG artifacts, relative to
    output_dir - the gallery file lives there and artifacts sit under
    output_dir/artifacts/<id>/ (execute_script_in_docker's artifacts_dir), so a plain relative
    path resolves for any viewer opened at output_dir without embedding/copying the images a
    second time."""
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
    Deliberately omits delivered_score: even scoped to the angle, it can score a script that
    silently dropped half its data at 1.00, so displaying it as a quality number would mislead
    exactly the reader this gallery is for. pattern_reasoning is the substance - shown prominently
    as "Finding" instead.
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
    elif angle.get("realization_status") == "realization_error":
        # There is no pattern_reasoning here - the judge call that would have produced it is
        # exactly what failed - but the script/images below are real, so say so rather than
        # silently showing an entry with no Finding line and no explanation why.
        feedback = (angle.get("realization_feedback") or "").strip()
        lines.append(
            f"- **Note:** the realisation judge failed after a verified execution, so there is no "
            f"automated finding for this angle - the script and image(s) below are real; judge "
            f"them yourself. ({feedback[:300]})"
        )
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
    Five tiers, never flattened into one ranked list, because the statuses answer different
    questions:

    - realised / realised_null TOGETHER, ranked by INSIGHT (not soundness, and not the
      realization order) - the highest-insight angles have been observed disconfirming at least
      as often as they confirm, so a soundness-first or realised-first sort would bury the run's
      most interesting result under its safest one. A clean disconfirmation closes a question and
      is shown as a finding here, not demoted beneath a confirmation.
    - pattern_not_shown - executed, but illegible. A real quality outcome, shown secondary.
    - realization_error - executed (Docker-verified) but the judge call itself failed. Kept OUT of
      the not_realisable tier and never shown with `requires` - unlike a provisioning gap, nothing
      about the angle or the environment was at fault, so labelling it as one would misdirect a
      reader deciding what to provision next.
    - not_realisable - an ENGINEERING outcome, not a quality one. Listed prominently with
      `requires`, since that list is the signal for what to provision next
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
    realization_errors = [a for a in all_angles if a.get("realization_status") == "realization_error"]
    not_realisable = [a for a in all_angles if a.get("realization_status") == "not_realisable"]
    unsupportable = [a for a in all_angles if a.get("soundness_verdict") == "unsupportable"]
    considered_ids = {a.get("id") for a in all_angles if a.get("realization_status") or a.get("soundness_verdict") == "unsupportable"}
    also_generated = [a for a in all_angles if a.get("id") not in considered_ids]

    lines = [
        f"# Diverger gallery — {timestamp}", "",
        f"{len(all_angles)} candidate angle(s) surfaced this run: {len(realized_top)} realised or "
        f"disconfirmed, {len(not_shown)} executed but illegible, {len(realization_errors)} executed "
        f"but unscored (judge failure), {len(not_realisable)} not realisable, {len(unsupportable)} "
        f"unsupportable by the data.", "",
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

    if realization_errors:
        lines.append("## Executed, but unscored — the judge call failed, not the analysis")
        lines.append("")
        lines.append("_The script compiled, ran in the sandbox, and produced real output; only the "
                      "final judging call failed. Not a provisioning gap - judge these yourself "
                      "from the script/image(s) below._")
        lines.append("")
        for angle in realization_errors:
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
