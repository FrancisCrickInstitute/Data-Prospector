# Converger → Diverger conversion plan (rev. 15)

Working plan for `FrancisCrickInstitute/diverger-agents-template`.

**D1–D6 are complete.** The pipeline now ideates, diverges, dedups, judges — with a graded (not gated) soundness verdict — and selectively realises only the top-ranked angles into executed, Docker-verified scripts. What remains is the gallery (D7) and stopping/economy (D8). D6 is confirmed working end-to-end on a live `cbias` run — see §3 for what it implemented and the current live issues.

**Read this whole document before starting. Then implement ONE step at a time, stopping after each for review and a live run.**

---

## 1. Why this fork exists

The parent repo is a **converger**: it hill-climbs toward a single best-scoring analysis. Graded fitness (`req_score`), mutate-the-best-checkpoint seeding, and pass/fail gating all pull the population toward one conventional peak. That is correct behaviour for "produce a working, correct script".

It is the wrong behaviour for **exploratory analysis**. Insight lives in divergence — many angles, some strange, most discarded. A checklist-satisfying analysis is by construction a conventional one, so a pipeline that optimises checklist conformance will reliably produce obvious results, efficiently and expensively.

This fork inverts the machinery. The goal is a **skimmable gallery of distinct, defensible, non-obvious analytical angles** for a human to judge — not one winning script.

### The three inversions

| Axis | Converger (parent) | Diverger (this fork) |
|---|---|---|
| **Objective** | Maximise one score | Maximise *spread*; kill duplicates |
| **Operator** | Mutate the best node (exploit) | Generate *away from* the archive (explore) |
| **Timing** | Execute everything to score it | Judge ideas as *text* first; execute only the chosen few |

---

## 2. Guardrails

- **One step at a time.** Implement, commit, run on the `cbias` config, review output, then continue. There is no pass/fail oracle in a diverger — the human reading the output *is* the test.
- **Human-owned prompts stay human-owned.** `ANGLE_GENERATION_*`, `INSIGHT_JUDGE_*` and `SOUNDNESS_JUDGE_*` are now filled in. Do not rewrite them; propose changes and let the human make them. The `*_FALLBACK` counterparts have been removed (see §3) now that these are stable — a missing/empty human-owned prompt is a hard failure now, not a silent generic substitute.
- **Do not delete dormant code.** See §6.
- **Follow the caching convention (§4) for every new prompt.**
- **Reuse, don't rewrite.** `_parse_xml_items`, `_jaccard`/`_token_set`, `_log_iteration_diversity`, `_angle_record`, `_dedup_angles`, `llm_call` (semaphore + images + `cache_prefix` + provider routing), `extract_xml`, `format_prompt`, the Docker sandbox and artifact copy-out all carry over.
- **Instrument before tuning.** Every threshold here should be set from observed numbers. §3's run log is the evidence base.
- **Keep it a template.** No new frameworks, no tree-search controllers, no persistent Elo ratings, no async task queues.
- **Prompts live in `prompts.py`.**

### Out of scope

- Message Batches API integration (the diverger's wide fan-outs suit it, but batching during prompt calibration makes iteration miserable).
- **External retrieval / literature enrichment** — see §9.
- **Dynamic library provisioning** — see §10. Do not solve this by narrowing ideation.
- The "team capability & horizon scanning" variant (a later, separate fork).
- Human-directed deepening ("go deep on angle 3") — deferred until after D8.

---

## 3. Progress and current state

### Completed steps

**D1** — convergence spine stripped (no early exit, no mutate-the-best seeding, execution layer inert). `.gitignore` hardened; `anonymize_cbias_data.py` committed as the audit trail.

**D2** — ideation decoupled from execution. `generate_angles()`, `_parse_xml_items`, human-owned `ANGLE_GENERATION_*` (originally with a fallback safety net, removed in a later cleanup — see §3), `angle_model` per config, `--angles-per-iteration`. The design/execution loop was replaced entirely — the correct reading of "no Docker in this step".

**D3** — fan-out to N concurrent one-angle calls, stance cycling, archive re-roled to hold proposed angles, `{existing_angles}` as cross-iteration divergence pressure, `_log_iteration_diversity` revived against angle text, `pick_best_seed`/`pick_other_seed` deleted.

**D3a** — **worked.** Within-iteration mean fell 0.34 → 0.09–0.12 and has held there for five runs. Three parts: stance logging (which unblocked diagnosis), guiding-question cycling as a second axis, and moving the stance adjacent to the instruction it modifies.

> **Slot-determinism bug, and the fix — do not reintroduce.** Both cycles were originally pinned to the call index (`m % len(...)`), so with 4 calls the pairing was identical every iteration: Q5 never fired, and each slot regenerated its own previous output (`abstract-readability-complexity-trend` → `abstract-reading-level-and-complexity-trend`). The fix offsets by iteration — `stances[(m + iteration) % S]`, `questions[(m + iteration * n) % Q]` — so no slot repeats its inputs and all five questions are covered within two iterations.

**D3b** — **worked.** Criteria now split into ideation criteria (guiding questions, stakeholders, verbatim anti-targets, data-availability constraints) and a deliverable rubric held for D6. Unplanned bonus: the extraction now emits a per-year *field availability inventory* (e.g. "Themes" and "Gender of presenting author" only in 2024/25, "doi" only in 2024), which is real grounding ideation previously lacked. Keep it.

**D4** — implemented (`_dedup_angles`, `angle_similarity_threshold=0.22`) and **first exercised on Run 8**: one across-iteration merge, 8 → 7. Threshold now has one real data point rather than none.

> **Open: which pair merged is unrecorded, and the two candidates have opposite verdicts.** `early-bird-uptake-ratio` ~ `registration-lead-time-and-group-size-trend` (both registration-timing behaviour on the attendee CSVs) would be a true positive. `topic-evolution` ~ `feedback-lda-topic-evolution` (both LDA, but different corpus, different guiding question) would be a false positive of exactly the kind to avoid — collapsing two distinct analyses because they share a technique. **Log the merged pair and its score** before drawing any conclusion about the threshold.

See "Known ceiling" below.

**D5** — implemented (`judge_insight`, `judge_soundness`, `_rank_key`, `judge_model` per config). Prompts filled by the human. `_candidate_score` deleted as scheduled. **The judges are not yet calibrated** — see "Live issues".

**D5-calibrate** — implemented and **live-verified on Run 8**. All six items from the original spec:
1. Scores were already surfaced by D5 (ranked shortlist, per-angle reasoning) — nothing to change.
2. **Soundness graded instead of gated.** `judge_soundness` now returns a three-way `unsupportable`/`caveat`/`solid` verdict instead of a boolean, plus a `soundness_caveat` string carried forward for display, never used as a filter. `caveat` is written up as the *normal* case for a dataset this size, not a rare one. `_judgment_sort_key` now ranks `solid > caveat > unsupportable > unranked` (was `sound_rank`/boolean).
3. **Verdict parsing hardened.** Anything outside the three-word vocabulary maps to `None` (unranked) with a warning, not a default verdict — the same fix the old boolean parse needed (it silently mapped anything unexpected to `false`).
4. **Unique angle ids enforced.** `_ensure_unique_id` suffixes `-2`, `-3`, ... on collision before an angle reaches the archive.
5. **Cross-run curation aid added.** `_write_angle_dump` writes every run's ranked, judged angles to `output_dir/surfaced_angles_<ts>.md`. This does NOT give the pipeline cross-run memory — `{existing_angles}` still only persists within a run, and the report's Already Explored section is still hand-maintained — it just makes copying entries into that section a copy-paste instead of a re-transcription. No automatic retirement, by design.
6. **`requires` field added** to the angle schema (instrumentation only, §10) — tracks what libraries ideation reaches for; never constrains it.

The two prompt-wording changes this needed (`SOUNDNESS_JUDGE_PROMPT_SUFFIX`'s new `<verdict>`/`<caveat>` tags, `ANGLE_GENERATION_PROMPT_SUFFIX`'s new `<requires>` tag) were drafted directly into both the human-owned constants and their `_FALLBACK` counterparts (since removed — see below), at the human's request — still open to further editing, same as the rest of the human-owned prompts.

**Prompt cleanup (post-D5-calibrate)** — once the human-owned prompts proved stable through Run 8, the `*_FALLBACK` constants and their empty-check/warning/fallback-selection branches were removed entirely from `prompts.py` and `pipeline.py`. `generate_angles`, `judge_insight`, and `judge_soundness` now call `ANGLE_GENERATION_*`/`INSIGHT_JUDGE_*`/`SOUNDNESS_JUDGE_*` directly and unconditionally — an empty human-owned prompt is now a hard failure, not a silent generic substitute. Alongside this: `SOUNDNESS_JUDGE_PROMPT_SUFFIX`'s `<caveat>` tag now also carries the specific reason for an `unsupportable` verdict (previously populated only for `caveat`, left empty otherwise), `<reasoning>` is now requested for every verdict rather than just non-`solid` ones, and `_write_angle_dump` now surfaces `soundness_reasoning` per angle alongside `soundness_caveat`.

**D6** — implemented and **confirmed working end-to-end on a live `cbias` run**: selective execution over the top-ranked angles only, never the whole archive.
1. `--realize-top-k` (default 4, replacing the dead `--designs-per-iteration` relic) selects the top-k non-`unsupportable` angles off D5's already-ranked shortlist; `unsupportable` angles are skipped entirely rather than paying a Docker run to visualise a claim the judge already said the data can't support.
2. `_run_one_design` rebuilt around **one angle**: the orchestrator's brief is now the angle's hypothesis/variables_involved/rough_method/why_non_obvious, not the whole report. Workers still see the TRUE original report (not the angle brief), so `WORKER_PROMPT_PREFIX` stays cache-hit across every angle realised in a run, not just within one angle's own compile retries.
3. `validate_requirements` re-roled to `validate_realization`: its PRIMARY judgment is a new `<pattern_shown>` tag — does the actual output (console + attached plots) legibly demonstrate the angle's claimed pattern — checked ahead of, and independently from, the existing deliverable-rubric checklist. Fed D3b's **deliverable rubric** instead of the old undivided criteria.
4/5. **Three outcomes, never conflated**: `realised` (executed, pattern shown), `unsound` (executed, pattern NOT shown — a quality judgement), `not_realisable` (never executed after `max_compile_attempts` — an engineering/provisioning outcome). Status is driven purely by `pattern_shown`; the deliverable-rubric score is reported alongside but doesn't gate it — graded, not gated, the same shape as D5-calibrate's soundness verdict.
6. `max_compile_attempts` left at its existing default of 3 (already low).

`compile_script`, `_call_worker`, `execute_script_in_docker`, `_format_artifacts`, `_load_plot_images` were revived **unchanged**, per the spec's own instruction — see §6 (now empty of dormant code). Realised angles' artifacts land in `output_dir/artifacts/<angle_id>/`; the compiled script itself is kept in memory but not yet written to disk — D7 item 3's job, deliberately not pulled forward.

**Report** — rewritten three times: plot taxonomy, metric counts and PNG counts removed; guiding questions levelled; anti-target list inlined from `djpbarry/cbias-survey`; programme CSVs pre-downloaded so Q4 is answerable without network access; Q5 reworded to drop post-attendance collaboration; `<year>_Abstracts` notation replaced (it was producing XML parse failures every iteration when the model copied it into `<variables_involved>`).

### Run log

The evidence base for every threshold in this document.

| Run | Within-iter mean | Cross-iter | Note |
|---|---|---|---|
| 1 | 0.13 | **failed** | Pre-anti-target. Iteration 2 refined an iteration-1 angle |
| 2 | **0.34** | working (0.17) | Anti-target added. Four near-copies of one angle — attractor collapse |
| 3 | 0.12 | **failed** | D3a v1. Stances visibly firing, but slot determinism regenerated a duplicate |
| 4 | 0.10 / 0.11 | working | D3a offset fix. Q5 fires for the first time |
| 5 | 0.11 / 0.09 | working | D3b. Dedup 8→8 |
| 6 | 0.11 / 0.09 | working | D5 wired, fallback prompts. 0/8 sound |
| 7 | 0.12 / 0.10 | working | Human prompts filled. 1/8 sound; duplicate `angle-1` ids |
| 8 | 0.09 / 0.10 | working | D5-calibrate live. Dedup fires first time (8→7). 0 solid / 6 caveat / 1 unsupportable. Q1 attractor gone; LDA attractor forming |
| 9 | 0.10 / 0.11 | working | Dockerfile provisioning fix. Dedup 8→8. 0 solid / 6 caveat / 2 unsupportable. **Insight judge validated**: 0.20–0.72, floored the anti-target-adjacent angle |
| 10 | — | working | `soundness_reasoning` added; both rejections audited and correct. Insight 0.30–0.75 |
| 11 | 0.14 / 0.12 | working | **First end-to-end D6 run.** Dedup 8→7 (merge at 0.247). 0 solid / 5 caveat / 2 unsupportable. Realisation: 0 realised, 3 pattern-not-shown, 1 not realisable — **invalidated by the criteria-split regression below** |
| 12 | 0.11 / 0.10 | working | **D6-fix validated.** Criteria split confirmed distinct; `delivered_score` spread 0.09–0.94 (was clustered 0.29–0.33). Dedup 8→8. 0 solid / 5 caveat / 3 unsupportable. Realisation: **1 realised**, 3 pattern-not-shown, 0 not realisable |
| 13 | 0.12 / 0.10 | working | Three-way pattern outcome live. Dedup 8→7 (0.313, clean true positive). 0 solid / 6 caveat / 1 unsupportable. Realisation: 1 realised (`delivered_score=1.00`), **0 disconfirmed**, 2 pattern-not-shown, 1 not realisable |
| 14 | 0.09 / 0.14 | working | `pattern_reasoning` + post-realisation dump confirmed. Dedup 8→7 (0.326). Realisation: **0 realised** — all three failures were the *same* data-loading bug (Live Issue 11), diagnosable only because of `pattern_reasoning` |
| 15 | 0.13 / 0.14 | working | **Fail-fast fix validated. First `realised_null`.** Dedup 8→7 (0.240, `kept` line correct). 0 solid / 6 caveat / 1 unsupportable. Realisation: **1 realised_null** (`delivered_score=1.00`, real PNG), 0 pattern-not-shown, 3 not realisable. Insight floor a new low: 0.10 |
| 16 | 0.11 / 0.12 | working | **Per-attempt logging pays off immediately.** Dedup 8→6 (two merges, 0.285 + 0.413). 0 solid / 5 caveat / 1 unsupportable. Realisation: **2 realised_null**, 1 pattern-not-shown, 1 not realisable. Compile-loop oscillation exposed (Issue 13); nltk corpora found missing (Issue 14) |
| 17 | 0.08 / 0.11 | working | **First `realised` with a genuine confirmed finding.** Dedup 8→7 (0.497 — highest yet, unambiguous). 0 solid / 6 caveat / 1 unsupportable. Realisation: **1 realised, 1 realised_null**, 2 pattern-not-shown, 0 not realisable. New: cmudict gap (Issue 15), host-side Unicode crash (Issue 16) |
| 18 | 0.10 / 0.08 | working | **Regression: data discovery fails again, but now loudly.** Dedup 8→7 (0.382). 0 solid / 4 caveat / 3 unsupportable. Realisation: 1 realised, 0 realised_null, 0 pattern-not-shown, **3 not realisable** — two of them path-resolution failures (Issue 17), one still `sentence-transformers` |
| 19 | 0.09 / 0.12 | working | **Issue 17 confirmed. First 100% realisation rate in the project's history.** Dedup 8→7 (0.278). 0 solid / 6 caveat / 1 unsupportable. Realisation: **1 realised, 3 realised_null, 0 pattern-not-shown, 0 not realisable.** Readability decline replicates Run 17; stakeholder-blurring disconfirmed a third time |

**Divergence is solved.** Both axes are healthy and have been for sixteen consecutive runs. Do not spend further effort here.

> **The diversity log and dedup no longer measure the same thing.** `_log_iteration_diversity` uses `_token_set`; `_angle_signature` double-weights `hypothesis`/`variables_involved`. Run 8 capped at 0.16 in the diversity log while dedup found a pair above 0.22. Not a bug — but dedup behaviour can no longer be read off the diversity numbers, and the two must not be treated as interchangeable.

### Live issues

**0. RESOLVED (Run 12) — the D3b criteria split silently collapsed (Run 11).** Both printed blocks contained *identical* text, and that text contained both the `# IDEATION CRITERIA` and `# DELIVERABLE RUBRIC` sections. The extraction emitted everything inside one tag, and the fallback did the rest:

```python
deliverable_rubric = extract_xml(criteria_response, "deliverable_rubric").strip() or criteria_response.strip()
```

The `or` guard exists to survive a *failed* criteria call; here it silently masked a *malformed* one and assigned the whole response to both variables. Three consequences, all visible in Run 11:

1. **The D3b leak is back** — ideation's prefix again contains "PNG files", "properly labelled", "clean and minimal", the exact script-rubric contamination D3b removed.
2. **The D6 orchestrator designed the wrong artifact** — it receives `criteria=deliverable_rubric`, so instead of a rubric for one angle it got the entire report brief (all five guiding questions, "key metrics" plural, the data-gaps list) and built a general-purpose script.
3. **`delivered_score` measured the wrong target** — all three executed angles landed in 0.29–0.33, tight clustering consistent with a single-angle script being graded against a full-report checklist it was never meant to satisfy. A diluted script is also one whose specific claimed pattern won't read clearly, which plausibly explains `pattern_shown=false` across the board.

**Run 11's `0 realised` was therefore an artifact, not a result.** Fixed in D6-fix: extraction now raises on a missing *or* identical tag pair and falls through to the same loud raw-report fallback as a failed call. Run 12 confirmed it — the two printed blocks are genuinely different and `delivered_score` spread from the tight 0.29–0.33 cluster to **0.09–0.94**.

> **The fallback still degrades D6, just loudly now.** On a malformed extraction both variables still become the raw report, reproducing the Run 11 condition with a WARNING attached. Ideation stages are cheap, so that is fine there; D6 then spends real money (k compile chains + k Docker runs) producing structurally unusable realisations. Consider **skipping realisation** rather than running it on a known-bad rubric — the ideation output would still be perfectly good.

**1. Soundness — resolved as a two-level scale.** `solid` has now been empty for **three consecutive runs** (9, 10, 11). Treat it as unreachable at n=37–60 with four time points: keep the three-way vocabulary, but do not tune the prompt toward a tier the data cannot support. `unsupportable` is doing real work — 2 of 7–8 angles per run, correctly identified — and D6 now skips those angles entirely. Under the old boolean gate: 0/8 then 1/8 sound, contributing nothing to ranking (structurally the converger's binary `req_pass` problem in new clothes). The three-way verdict is now live and Run 8 returned **0 solid / 6 caveat / 1 unsupportable** — real separation, and the caveat text now exists for D7 to display.

But 6/7 in one bucket means ranking is still driven almost entirely by insight, and `solid` may simply be **unreachable** on n=37–60 respondents with four time points. If `solid` stays empty across the next few runs, treat this as a two-level scale in practice rather than tuning the prompt toward a tier the data cannot support.

**2. Insight discrimination — VALIDATED (Runs 9–11).** The judge separates cleanly and repeatably: 0.20–0.72 (Run 9), 0.30–0.75 (Run 10), 0.20–0.75 (Run 11). Two things it demonstrably gets right:

- **The anti-target generalises beyond its literal list.** `direct-self-reported-roles` (Run 9) and `attendee-role-composition` (Run 11) both proposed per-year category counts plotted as a trend — structurally the exhausted pattern, on columns not named in the list — and both scored **0.20**, the floor of their runs.
- **`soundness_reasoning` checks claims against actual data values**, not just sample size. Run 11 on `attendee-role-composition`: *"the specific hypothesis (increasing Industry share) is actually contradicted by the data (Industry falls to ~1 in 2025)."*

No further calibration needed. The `analysis_script_<ts>.py` misnaming (a D7 relic — `generate_and_optimize` still returns the ranked block as a string) remains outstanding and is fixed by D7.

**3. Cross-run memory is still manual, now with a curation aid.** `ticket-type-trend` appeared in four consecutive runs (always Q1 + Conventional); `readability-trend` and `registration-timing` three each.

> **Attractors are now being handled by the insight judge rather than needing curation.** The Q1 ticket-counting attractor stopped dominating after Run 8. The LDA attractor that formed in Runs 8–9 was scored **0.25** by the insight judge in Run 9 without any manual intervention — it may self-correct rather than needing retirement. Registration lead-time appeared in four separate runs across different stances and question slots and scored *well* (0.75 in Run 10), so it is a genuinely good angle rather than an attractor; retire it once realised, not before.

`{existing_angles}` still only persists *within* a run — the report's Already Explored section remains the only persistent cross-run memory, and it's still hand-maintained. D5-calibrate added `_write_angle_dump` so curating that section is a copy-paste from `surfaced_angles_<ts>.md` instead of a manual re-transcription; nothing retires an angle automatically, by design.

**4. Duplicate angle ids — fixed.** Run 7 produced two angles both called `angle-1`. `_ensure_unique_id` (D5-calibrate) now suffixes `-2`, `-3`, ... on collision before an angle reaches the archive.

**6. RESOLVED (D6-fix) — dedup preceded judging, so the representative was picked blind (Run 11).** The merge fired at 0.247 — `self-reported-role-trend` matched `cross-role-expertise-mapping` — and `_pick_representative` kept the former on the "longest `why_non_obvious`" heuristic. The survivor scored **0.35 insight**, the weakest angle in the realisable set; the discarded one (depth-first, role×training co-occurrence) never reached a judge, so its quality is unknown and unknowable.

**Ordering was the root cause, not the heuristic.** D5 now judges the whole archive before D4 dedups it, and `_pick_representative` breaks on `_judgment_sort_key` with the old text-length heuristic demoted to a stable secondary tiebreak. Judge calls share one cached prefix, so scoring all N rather than the deduped subset is close to free.

> **FIXED, unconfirmed on a live run — the merge log line could read backwards.** `merge_stats` records the best-matching member *at merge time*, but the survivor is chosen afterwards by score — Run 11 printed `merged [self-reported-role-trend] -> [cross-role-expertise-mapping]` while `self-reported-role-trend` was the one that survived. `_dedup_angles` now resolves each merge's `survivor_id` once `_pick_representative` has run (the `->` arrow still shows the merge-time best match, unchanged, since that's a legitimate separate fact), and the console line prints `... kept [X]` alongside it. Needs a live run to confirm the printed survivor actually matches the angle that carries through to realisation.

The merge itself is borderline: both angles use the same two feedback columns, but one is a four-year proportion trend and the other a two-year co-occurrence structure. Defensible on variables, expensive on quality.

**7. RESOLVED (Run 13) — `pattern_not_shown` conflated a failure with a finding (Run 12).** `validate_realization` asks whether the output legibly shows the *claimed* pattern, so an angle that ran perfectly and **disconfirmed its own hypothesis** gets the same status as one whose plot is broken or illegible.

Run 12 shows both in the same bucket: `industry-speakers-vs-attendees` at `delivered_score=0.69` (a well-delivered script whose claimed co-movement simply is not there) sits alongside `lda-topic-evolution` at 0.09. For a diverger this matters — a clean disconfirmation *closes a question* and is often more useful than a confirmation, but as things stand it will be buried below `realised` in the gallery.

**Split the status before building D7:**
- `realised` — pattern shown as claimed
- `realised_null` — executed and rendered legibly, but the data do not support the hypothesis
- `pattern_not_shown` — the output does not legibly show *anything* about the claim (broken plot, wrong measurement, unreadable)

The validator already sees the PNGs; it simply is not being asked to make this distinction. `realised_null` must rank **alongside** `realised` in the gallery, not below it.

Shipped as a three-way `<pattern_outcome>` (`shown` / `disconfirmed` / `not_shown`), same strict-vocabulary shape as `_SOUNDNESS_VERDICTS`, with an unparseable response mapping conservatively to `pattern_not_shown`. The prompt requires a disconfirmation to be *legible, complete, and directly addressing the claim*, which is what stops it becoming a soft landing for half-broken output, and instructs the feedback text not to frame a disconfirmation as something to fix. **Calibration CONFIRMED (Run 15).** Runs 13 and 14 returned 0 disconfirmed, which looked like a possibly over-strict bar — it was not. Run 14's zero was the data-loading bug (Issue 11); once that was fixed, Run 15 produced the project's first `realised_null`:

> `stakeholder-hybridity-depth` — hybridity **declining** 22.6% (2024) → 16.2% (2025), with individual roles dropping to 0% (Facility staff 23%→0%, Research scientist 28.6%→0%) — *"directly contradicting the claimed 'increasingly' or 'more pronounced in recent years' trend"*, and the judge bounded it unprompted: *"only two of the four symposium years have usable data, but within that legible window the trend runs opposite to the claim."*

Four things validated at once: the three-way split distinguishes disconfirmation from failure; `pattern_reasoning` makes it auditable; `delivered_score=1.00` on a *disconfirming* script proves the rubric grades **delivery, not agreement**; and the artifact listing confirmed the PNG genuinely exists. This is the diverger doing the job it was built for — a plausible, appealing hypothesis tested and refuted.

**8. BLOCKER for D7 — `delivered_score` grades structural compliance, not delivery (Runs 12, 16).** The extracted rubric demands loading *all four* data types across all years and emitting a data-gaps list. A readability angle needs Abstracts only and has no reason to produce a gaps list, so narrow angles lose criteria they were never meant to satisfy — `lda-topic-evolution` scored **0.09** while executing cleanly, which is a scope mismatch, not a quality signal.

**Run 16 makes this much sharper, and promotes it to a D7 blocker.** `feedback-latent-importance` scored **0.81** for a script that produced *one entirely blank PNG* and never created its second required plot. The rubric rewards structural compliance — auto-detects filenames, handles missing data gracefully, clean and minimal code — almost independently of whether anything was actually produced.

**Run 19 is decisive: `delivered_score` and `insight` are close to uncorrelated.** `angle-1` scored **1.00** delivered on 0.82 insight; `stakeholder-hybridity-analysis` scored **1.00** delivered while the judge's own `pattern_reasoning` notes that one of its three plots "resolves to a single year (2025) only... so it cannot support a trend either way". A script with a demonstrably broken plot took the maximum score. Meanwhile the genuinely confirmed finding (`readability-complexity-trend`) scored 0.93 and the sharpest disconfirmation (`industry-speaker-attendee-alignment`) 0.94 — a range of 0.93–1.00 spanning outputs of wildly different worth.

**The judge is doing the real quality work in `pattern_reasoning`; `delivered_score` measures rubric compliance and little else.** For D7 this settles three things: rank the top tier on **insight**, show `pattern_reasoning` prominently as the substance, and either fix `delivered_score` or omit it from the gallery entirely.

**Run 17 demonstrates it twice more, at the top of the scale.** `abstract-to-talk-conversion` produced acceptance rates of *exactly 0.00 for every year* — a degenerate all-zero result from a broken matching heuristic — and scored **0.87**. `role-training-hybridization` silently dropped half its data (charts titled "2024 vs 2025" containing only 2025) and scored **1.00**, the maximum. Three separate demonstrations now across Runs 12, 16 and 17.

It still gates nothing mechanically, but **a gallery displaying `1.00` beside a chart that silently lost half its data would actively mislead the reader**, which defeats the purpose of building one. Fix before D7 by scoping the rubric to the angle, or by telling `validate_realization` the script implements one angle rather than the full report — and consider making artifact-emptiness a hard cap on the score regardless of structural criteria met.

**FIXED, unconfirmed on a live run — scoped the rubric to the angle.** Chose the first of the three options above (user decision), not the hard artifact-emptiness cap. `validate_realization` now takes an `angle_scope` parameter (the angle's own `variables_involved` + `rough_method`, built in `_run_one_design` and passed alongside `claimed_pattern`) and `REALIZATION_VALIDATOR_PROMPT_SUFFIX` instructs the judge to SKIP — not emit a `<criterion>` tag for — any rubric bullet that is out of scope for this angle *by design*, while explicitly cautioning it not to skip a bullet the script merely failed to satisfy. Since `delivered_score` is computed purely as met/total over emitted `<criterion>` tags (`_CRITERION_PATTERN`), an omitted tag drops out of both numerator and denominator with no scoring-logic change in `pipeline.py`. `angle_scope` varies per angle so it lives in the suffix, not the cached prefix — zero extra LLM calls, no cache regression.

**Known limitation, deliberately not addressed by this fix:** this only corrects the *scope* mismatch (narrow angles penalised for rubric bullets they were never meant to satisfy). It does **not** add a mechanical floor for the blank-PNG/degenerate-result failure mode that produced Run 16's 0.81 (one blank PNG, second plot never created), Run 17's 0.87/1.00 (all-zero acceptance rates; half the data silently dropped), and Run 19's 1.00 (a plot that "resolves to a single year... cannot support a trend either way") — a script can still score well on in-scope bullets it technically executed while the actual output is worthless. The user selected "scope the rubric to the angle" over the hard-cap option; if degenerate-but-in-scope results keep scoring high after this lands, that's the next thing to revisit, not a sign this fix failed. Needs a live run to confirm the scoping behaves as intended (plausible failure mode to watch for: the judge over-skips, e.g. treating a bullet as "out of scope" because the script failed it rather than because it was never meant to touch it).

**9. FIXED, unconfirmed on a live run — `pattern_reasoning` is requested but never surfaced (Run 13).** The realisation validator was asked for `<pattern_reasoning>` and the field was discarded: the console printed `pattern_not_shown (delivered_score=0.67)` and nothing about why. **This was the same audit gap that existed for `unsupportable` verdicts before `soundness_reasoning` was added** — and fixing that one immediately proved the judge was right, so the precedent was direct.

It bit because Run 13 returned **0 disconfirmed**, and that was uninterpretable. The two `pattern_not_shown` results were plausible disconfirmation candidates: `readability-and-complexity-trends` (0.53) and `program-speaker-role-blur` (0.67) both executed, produced artifacts, and delivered most of the rubric. If readability came out flat across four years that is a `disconfirmed` finding; if the plot was unreadable it is `not_shown`. From that output alone the two were indistinguishable, so the three-way split couldn't be calibrated.

`validate_realization` now extracts `<pattern_reasoning>` (the tag was already in the prompt — it was simply never pulled out) and threads it through the whole call chain: the `Realization: ...` console log line, `_run_one_design`'s and `generate_and_optimize`'s result dicts, and the final ranked-summary block. `_write_angle_dump` also gained the rendering for it, guarded the same way as the other realisation fields — currently a no-op there since the dump is written before realisation (Live Issue 10), but it means Issue 10 won't need a second edit to make `pattern_reasoning` show up once that ordering changes.

**RESOLVED (Run 14).** All three `pattern_not_shown` angles in Run 14 (`angle-stakeholder-blurring`, `registration-lead-time-shift`, `lexical-diversity-trend`) printed a concrete, distinct `pattern_reasoning` in both the console and `surfaced_angles_<ts>.md` — e.g. *"The feedback-file glob pattern (`*Survey*.csv`) never matches the actual data files..."* — which is what made Live Issue 11 (below) diagnosable at all instead of three unexplained `pattern_not_shown` results.

**10. RESOLVED (Run 14) — the dump was written before realisation, so it carried no realisation data (Run 13).** `surfaced_angles_<ts>.md` had soundness verdict, reasoning, caveat and insight — but no `realization_status`, `delivered_score`, `pattern_reasoning`, or artifact paths, because `[dump]` fired before `[realize]`. That was fine for its stated purpose (curating anti-targets) but left **D7's gallery missing exactly the half it needs.**

Resolved by moving the single write point (not adding a second artifact — one file stays the source of truth, and nothing ever consulted the dump mid-run anyway, only after `generate_and_optimize` returns) to after the realize step. `_write_angle_dump` now runs against `all_angles` post-realization, so angles that were realized carry `realization_status`/`delivered_score`/`pattern_reasoning`/`artifacts` alongside their D5 judgment. Confirmed in Run 14 — all four realized angles in `surfaced_angles_20260809_090603.md` carry `realization_status`/`delivered_score`, and the three `pattern_not_shown` ones carry `pattern_reasoning` too (`angle-bertopic-trends`, `not_realisable`, correctly has no `pattern_reasoning` since it never executed).

**11. RESOLVED (Run 15) — generated scripts silently failed to find real input data, and a graceful no-op exit read as PASS (Run 14).** All three angles realised in Run 14 failed for the same underlying reason, only visible because of Issue 9's fix:
- `angle-stakeholder-blurring`: glob `*Survey*.csv` matched nothing (Feedback filenames are `CBIAS <year>Attendee Survey(...).csv`, inconsistently spaced, inside `Feedback/`)
- `registration-lead-time-shift`: found the Attendees CSVs but couldn't match the `Order date`/`Event start date` columns despite them existing verbatim
- `lexical-diversity-trend`: "No abstract data found" — `Abstracts/` nests one directory per year (`Abstracts/<year>_Abstracts/*.txt`), a flat glob on `Abstracts/*.txt` finds nothing

Docker mounting and `INPUT_FOLDER` routing were verified correct (`execute_script_in_docker` mounts the whole `data_dir` at `/data:ro` and sets `INPUT_FOLDER=/data`, `DOMAIN_NOTES` documents the real paths/columns accurately) — this is a worker/compiler code-generation reliability problem, not a data-routing bug. It compounds with a real pipeline gap: each script printed a "no data found" message and exited 0, which `validate_execution`'s exit-code-only check cannot distinguish from a real success, so the compile-retry loop never got a chance to fix it — the bug was only caught downstream by the realization judge, after the design's Docker budget was already spent.

Three fixes landed together:
1. `WORKER_PROMPT_SUFFIX`/`COMPILER_PROMPT_SUFFIX` (not human-owned prompts) now explicitly forbid the "print a not-found message and return/exit cleanly" pattern — missing data must raise, and file/column matching must be case-insensitive/substring/recursive rather than assuming an exact literal match or a single directory level.
2. `cbias_config.py`'s `DOMAIN_NOTES` now spells out the exact three sub-directory paths and glob shape up front, including the Feedback filename's inconsistent spacing and the Abstracts per-year nesting, instead of only describing them prose-style further down.
3. `validate_execution` gained a mechanical (still not LLM) backstop: exit 0 with zero artifacts and under `_MIN_SUCCESS_OUTPUT_CHARS` (200) of output is now treated as FAIL and fed back into the same compile-retry loop a crash would get, rather than silently passing through as PASS.

**Confirmed in Run 15.** Zero silent no-op passes: `pattern_not_shown` went to 0, and `stakeholder-hybridity-depth` loaded real data and produced a real PNG. Failures now surface as FAILs that retry through the compiler, exactly as intended. **But the fix has a cost — see Live Issue 12.**

**12. Fail-fast converts silent write-offs into 3× compile spend, and the retry loop is unaudited (Run 15).** Every Run 15 failure was a compile-loop exhaustion: `speaker-industry-alignment`, `survey-blind-spots` and `semantic-drift-similarity` each burned all three attempts before `not_realisable`. That is partly the fix working — scripts that used to exit 0 with no data now correctly FAIL — but it triples the compile budget spent to reach the same conclusion, and it hit the run's **highest-insight angle (`survey-blind-spots`, 0.78)**.

`pattern_reasoning` cannot help here: these angles never reach `validate_realization`. **The diagnostic gap has moved one stage upstream** — is the retry loop converging on a different error each attempt, or repeating the same one? The error feedback *is* threaded into `COMPILER_PROMPT`, so it should be repairing.

**FIXED, unconfirmed on a live run.** Both items landed in `_run_one_design`'s compile/execute loop:
1. **Per-attempt FAIL feedback is now logged** (`  Attempt N FAIL reason: ...`) as it happens, not just kept silently in `compile_error` for the next retry. The final `not_realisable` result's `realization_feedback` now joins every attempt's reason (`attempt_feedbacks`), not just the last one, so a human can tell at a glance whether the compiler was converging on a different bug each time or stuck repeating the same one.
2. **Fast-path abort on a verbatim repeat.** If attempt N+1's `exec_feedback` (stripped) is identical to attempt N's, the loop breaks immediately instead of spending the remaining attempts — `aborted_on_repeat` is threaded into both the log line and the returned feedback so it's visible this was an early exit, not attempt exhaustion.

**Not yet run live.** The next run should show, for any `not_realisable` angle, either a repeated-error abort (saving 1-2 wasted compile attempts) or a genuinely different error per attempt (proof the compiler is trying different repairs, just not succeeding) — confirm against Run 15's `speaker-industry-alignment`/`semantic-drift-similarity`/`survey-blind-spots` if they recur. Likely split, worth confirming from the logs rather than assuming: `semantic-drift-similarity` is almost certainly the `sentence-transformers` model-weights problem (§10 — requested in five consecutive runs now), while `speaker-industry-alignment` is likely the ragged Programme CSVs (see Data notes — headerless, column meanings drift between years). Neither is a code-quality failure and both have known remedies.

**13. RESOLVED (fixed; no oscillation arose in Run 17 to exercise it) — the verbatim abort compared consecutive attempts only, so an oscillating loop escaped it (Run 16).** Per-attempt logging (Issue 12's fix) immediately exposed a pathology that was previously invisible. `semantic-topic-shift`:

- Attempt 1 — `ModuleNotFoundError: transformers`
- Attempt 2 — `NameError: name 'os' is not defined` (the compiler dropped the import and broke something else)
- Attempt 3 — `ModuleNotFoundError: transformers` (back to the original)

That is cycling, not repairing. The abort did not fire because 1≠2 and 2≠3, even though 1 and 3 are identical. **Fix: keep a `set` of seen feedback strings and abort on any repeat, not just an immediate one.** One line.

**FIXED, unconfirmed on a live run.** `_run_one_design`'s compile/execute loop now tracks `seen_feedbacks` (a `set` of every stripped `exec_feedback` string seen so far this design) instead of only `previous_feedback`; the abort check is membership in that set, so attempt 3 repeating attempt 1's error now aborts exactly the same as an immediate repeat would. The log line distinguishes it ("this error already occurred in an earlier attempt... the compiler is cycling, not repairing") from the immediate case, but both set `aborted_on_repeat` and produce the same `not_realisable` abort-note text. Confirm on the next run against `semantic-topic-shift`'s exact 1→2→1 pattern if it recurs.

The oscillation also shows the abort cannot fix the underlying case: when the blocker is a missing library the compiler has no good move — removing the import breaks the analysis, keeping it fails execution. That is a §10 provisioning question, not a compile-loop question.

**14. RESOLVED (Run 17) — the nltk corpora were not actually in the image (Run 16).** §10 and Issue 11 record the corpora as baked in at build time (with the `inisec.py` workaround), but `abstract-convergence` attempt 1 failed with `Attempted to load 'corpora/stopwords.zip/stopwords/'` after searching `/tmp/nltk_data`, `/usr/local/nltk_data`, `/usr/share/nltk_data` and finding nothing. Either the build-time `nltk.download` silently failed or it wrote outside the search path.

**Root cause confirmed directly against the live image** (`docker run` with the real `DOCKER_SANDBOX_FLAGS` runtime conditions, not just reading source): the `RUN python -P -c "...nltk.download(...)"` step in the Dockerfile executes as root with no `HOME` override, so `nltk.download()`'s default target is `/root/nltk_data` — confirmed present there (`ls /root/nltk_data/corpora/stopwords*`). Two independent reasons that's unreachable at runtime:
1. **Wrong location.** The sandbox runs `--user 1000:1000` with `HOME=/tmp` (a fresh, empty tmpfs), so `nltk.data.path` at runtime is `[/tmp/nltk_data, /usr/local/nltk_data, /usr/local/share/nltk_data, /usr/local/lib/nltk_data, /usr/share/nltk_data, ...]` — `/root/nltk_data` is never on that list, for any `HOME` value the sandbox would plausibly set.
2. **Wrong permissions.** `/root` is mode `700` (root-only) regardless, so even a search-path match would have failed for the non-root runtime user.

**RESOLVED — rebuild confirmed.** `Dockerfile`'s `cbias-analysis` target now downloads straight into `/usr/local/share/nltk_data` (explicit `download_dir=`, a path unconditionally on nltk's default search list independent of `HOME`), `chmod -R a+rX`'s it so the non-root runtime user can read it, and sets `ENV NLTK_DATA=/usr/local/share/nltk_data` as a second, independent way to reach the same directory. Confirmed against a fresh `docker build --target cbias-analysis -t cbias-analysis:latest .` — `nltk.data.find('corpora/stopwords')` now returns `OK` under the real sandbox conditions (`--user 1000:1000`, `HOME=/tmp`, fresh tmpfs). Still to confirm on a live pipeline run: no compile attempt burned on this for any nltk-touching angle. The script self-healed on attempt 2 in Run 16 (presumably by inlining a stopword list), so this was not fatal — but it burned a compile attempt every time an angle touched nltk. **A regression, not an expansion request.**

**15. RESOLVED, unconfirmed on a live run — `textstat` needs the `cmudict` corpus, which was not baked in (Run 17).** The Dockerfile baked `punkt`, `punkt_tab` and `stopwords`, but `textstat` reaches for **cmudict** for syllable counting. `angle-readability-change` attempt 1 failed with `Error loading cmudict: refusing to connect by unvalidated hostname` — the sandbox correctly blocking a runtime download. The script self-healed on attempt 2, so this cost one compile attempt rather than the angle, but it would recur on every readability angle (a recurring family — five appearances across runs).

**Fix landed:** `Dockerfile`'s `cbias-analysis` target now also bakes `cmudict`, plus `wordnet` and `averaged_perceptron_tagger` (the plan's own "consider adding" suggestion — POS-tagging appeared once, in Run 10, and the marginal cost of baking these in alongside the already-required rebuild is near zero). Same `download_dir=$NLTK_DATA` / `chmod -R a+rX` treatment as the corpora Issue 14 fixed, so the location/permission fix already applies to all six. Needs a rebuild (`docker build --target cbias-analysis -t cbias-analysis:latest .`) and a live run with a readability angle to confirm no compile attempt is spent on this anymore.

**16. RESOLVED, unconfirmed on a live run — host-side `UnicodeDecodeError` corrupts the execution oracle (Run 17).** Twice during realisation:

```
UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 149
  File "...\subprocess.py", line 1614, in _readerthread
```

The Windows host was decoding container stdout as cp1252. **This kills the reader thread, so `exec_output` may be silently truncated or empty** — and `exec_output` feeds the execution verdict, the near-empty-output backstop (Issue 11), and the compile-retry feedback. That makes this a correctness bug in the oracle itself, not a cosmetic host annoyance: a script could fail, have its traceback lost to a decode error, and be judged on a blank string.

**Fix landed:** `execute_script_in_docker`'s `subprocess.run` call now passes `encoding="utf-8", errors="replace"` explicitly instead of relying on `text=True`'s locale-dependent default — the container emits UTF-8 (every generated script is required to reconfigure stdout as UTF-8, per `CLAUDE.md`), so this pins decoding to what's actually being sent rather than the Windows host's cp1252 preferred encoding, and `errors="replace"` means a genuinely malformed byte degrades to a replacement character instead of crashing the reader thread and losing the rest of the output. Compile-checked; needs a live run to confirm no further `UnicodeDecodeError`.

**17. RESOLVED (Run 19) — `domain_notes` reached only the workers, so the compile-retry loop repaired path bugs blind (Run 18).** Three of four realised angles failed to find data: `registration-timing-as-demographic-proxy` (`No *Attendees*.csv files found in current or data directory`, 3 attempts) and `abstract-readability-trend` (`No directories matching '*_Abstracts'`, 3 attempts). Meanwhile `ticket-type-composition` read the Attendees CSVs correctly, so the mount is fine — this is per-script path resolution.

**The instructions were already correct and already present.** `cbias_config.DOMAIN_NOTES` carries an `EXACT PATHS` block stating `{INPUT_FOLDER}/Attendees/...`, `{INPUT_FOLDER}/Abstracts/<year>_Abstracts/<n>_Abstract.txt`, and verbatim warnings — *"a flat glob directly on `Abstracts/*.txt` will find nothing"* and *"do not search the top level for CSVs/txt files directly."* Both failing scripts did precisely the forbidden thing. **Restating the paths is not the fix; they are already stated.**

The actual cause is distribution: `grep domain_notes pipeline.py` returns exactly one call site — `_call_worker`'s cached prefix. **Neither `compile_script` nor the orchestrator receives it.** So when the retry loop rewrites a script after a path failure it sees the traceback but not the layout that would fix it, and repairs blind. That matches the observed behaviour exactly: `registration-timing` failed three times with *worsening* path guesses, and `abstract-readability-trend` **realised at `delivered_score=1.00` in Run 17 and was `not_realisable` in Run 18** — same angle, same data, opposite outcome. Nondeterministic worker path handling with no compiler-side recovery.

**Fix:**
1. Thread `domain_notes` into `COMPILER_PROMPT_PREFIX` (and consider the orchestrator, which currently designs architectures without knowing the layout). It is run-stable, so it belongs in the cached prefix — no per-attempt cost.
2. **`DOMAIN_NOTES` is stale:** it says "three sub-directories" when there are now four. `Programs/` is absent from the `EXACT PATHS` block entirely, which likely explains why programme-parsing angles have been unreliable throughout (Runs 13, 15, 17). Add it and correct the count.

Note this is *not* a return of Issue 11: fail-fast worked correctly — these raised and burned attempts rather than exiting 0 with a fake success. The failure is visible precisely because the earlier fixes are working.

**CONFIRMED (Run 19).** 4/4 angles executed — zero `not_realisable`, zero data-discovery failures, the **first 100% realisation rate in the project's history**. `readability-complexity-trend` realised again, settling the Run 17/18 flip-flop: it was compiler blindness, not an impossible angle. Both parts landed:
1. `domain_notes` now flows into both prompts this issue named, not just the worker: `COMPILER_PROMPT_PREFIX` gained a `Domain notes:` block (`compile_script` passes `config.domain_notes`), and `ORCHESTRATOR_PROMPT_PREFIX` gained the same (`_run_one_design`'s orchestrator call passes it too — the "consider" from the fix list above was implemented, not just the compiler). Both are cache-prefix content, run-stable, no per-attempt or per-angle cost. A compile retry can now see the exact paths/columns it got wrong, not just the traceback.
2. `cbias_config.DOMAIN_NOTES` corrected: "three sub-directories" → "four", and a new `Programs/` entry added to both the `EXACT PATHS` block (`Programs/CBIAS_<year>_Program_Day_<n>.csv`) and a full descriptive bullet (headerless/ragged column meaning, drifts by year, and — the one exception in this file — speaker names here are real, unanonymised data, not scrubbed like every other source).

Needs a live run to confirm: fewer/no path-resolution `not_realisable` results, and specifically that `abstract-readability-trend`-style angles stop flip-flopping between runs on identical data.

**18. FIXED, unconfirmed on a live run — the criteria-extraction call mirrored the report's own markdown headers instead of emitting `<ideation_criteria>`/`<deliverable_rubric>` tags (Run 20).** `CRITERIA_PROMPT` asks for two tagged XML blocks, but the model (`requirements_evaluator_model`, Sonnet) responded with plain markdown instead — `# IDEATION CRITERIA` as an ATX heading followed by prose, no tags anywhere. `extract_xml` found nothing for either tag (`0 / 0 chars extracted`), so the existing loud-fallback (Live Issue 0) fired correctly and degraded both `ideation_criteria` and `deliverable_rubric` to the full raw report — not a crash, but a real quality loss: D6's realization validator judges the deliverable rubric bullet-by-bullet (and, since Live Issue 8, skips bullets out of scope for the angle), and "the whole report" is neither bulleted nor scoped, so that machinery has nothing to work with.

**Likely cause:** the task report itself is heavily markdown-formatted (`#`/`##` headings throughout), and `CRITERIA_PROMPT` labels its own two sections "FIRST - IDEATION CRITERIA" / "SECOND - DELIVERABLE RUBRIC" in a similar all-caps style just above the tag examples — plausibly enough to prime the model to echo the report's own formatting convention back instead of switching into the requested tags.

**Fix landed, two parts:**
1. `CRITERIA_PROMPT` now explicitly forbids markdown headings and any text outside the two tags, and explicitly calls out not to mirror the report's own formatting — the direct prompt-level fix.
2. Added `_extract_markdown_section()` as a secondary extraction pass, tried only when `extract_xml` comes back empty for a tag: it recovers the same content from under an ATX heading naming the section (`# IDEATION CRITERIA` / `# DELIVERABLE RUBRIC`), stopping at the next such heading or end of text. This is the same "tolerate minor formatting drift" pattern `_parse_xml_items` already uses for `<task>`/`<angle>` blocks, applied here so an exact repeat of this failure recovers the real content instead of degrading to the raw-report fallback. Verified standalone against the actual malformed response text from this run — both sections extract correctly.

Needs a live run to confirm no recurrence of the WARNING, and — if it does recur despite the prompt fix — that the markdown fallback recovers usable criteria instead of falling through to the raw-report degrade.

**5. Caching is unverified.** §4 asks for a single `cache_read_input_tokens` measurement. It has not been taken, so the entire §4 investment is unmeasured. Still an explicit D8 task.

### Known ceiling: dedup is lexical

`feedback-cooccurrence-networks` (co-occurrence graph, modularity) and `feedback-cluster-evolution` (embed → HDBSCAN → Hungarian matching) are the **same idea** — how does the thematic structure of free-text feedback reorganise over time — with entirely different method vocabulary. Token-set Jaccard scores them ~0.09.

**Do not fix this by lowering the threshold**: genuinely distinct pairs also sit at 0.14, so lowering it over-merges before it catches this. The fix, if the duplication becomes material, is embedding- or judge-based similarity on `hypothesis` alone. Documented here so nobody tunes it instead.

Threshold evidence to date: near-duplicates 0.23 / 0.247 / 0.30–0.40; distinct pairs 0.06–0.19. The 0.22 default sits correctly between them, and Run 9's highest non-merged pair (0.19, two angles on the same survey question) confirms it is holding the line about where it should.

### Data notes

Programme CSVs are headerless and ragged: column 1 is a time *or* `Session N`, column 2 a speaker *or* session theme *or* "Registration & Exhibition", column 3 an affiliation *or* a chair, column 4 a title — and the shape drifts between years. Speaker names are real (public data, published by the Crick) and deliberately not anonymised. If D6 realisation failures cluster on programme parsing, normalise these into a flat `speaker,affiliation,title,year,session` table rather than blaming the model.

---

## 4. Caching convention

`llm_call` takes a `cache_prefix`: content there is marked with an ephemeral cache breakpoint, content in `prompt` is not. **Every new prompt must be split the same way.**

**The rule:** anything *identical across the calls sharing this cache* goes in the `_PREFIX`. Anything that varies goes in the `_SUFFIX`. Images go after the breakpoint (`llm_call` handles this).

**The trap:** a growing accumulator in the prefix invalidates the cache every iteration while looking correct. `{existing_angles}` grows each round — suffix. Same for stance and guiding question.

| Stage | Prefix (cached) | Suffix (varies) |
|---|---|---|
| Ideation | `report`, ideation criteria, `input_data`, anti-targets | `stance`, `guiding_question`, `existing_angles`, `n` |
| D5 judges | `report`, ideation criteria, `input_data`/schema, anti-targets | the individual angle |
| D6 orchestrator | `report` (the TRUE report, not the angle brief), `input_data`, deliverable rubric, `domain_notes` (added Live Issue 17) | the angle being realised (hypothesis/variables/rough_method/why_non_obvious) |
| D6 workers/compiler | existing splits, `domain_notes` now also in the compiler prefix (added Live Issue 17, was worker-only) | — |
| D6 validator (`validate_realization`) | `report`, deliverable rubric | `claimed_pattern`, `angle_scope` (added Live Issue 8 — lets the judge skip rubric bullets out of scope for this angle), script, execution output |

**Parallel fan-out defeats the cache on first use.** N concurrent calls all start before any writes the cache, so all N miss on iteration 1 and hit only from iteration 2. Note it when reading cost figures rather than concluding caching is broken.

**Still to verify (D8):** log `usage.cache_creation_input_tokens` and `cache_read_input_tokens` once. A prefix below the provider minimum (1024 tokens Sonnet/Opus, 2048 Haiku) is silently ignored — no error, no saving. Ephemeral TTL is 5 minutes.

---

## 5. Model tiering

| Role | Tier | Rationale |
|---|---|---|
| `worker_model`, `compiler_model` | DeepSeek | Mechanical, high-volume, **oracle-protected** — Docker catches bad code |
| `angle_model` | cheap tier | Volume matters more than polish; dedup + judges filter downstream |
| `judge_model` | **frontier Anthropic** (Opus on cbias) | With `req_score` gone these two judges *are* the entire quality bar |
| `orchestrator_model` | frontier | Retained for D6 realisation |
| `requirements_evaluator_model` → `validate_realization` (D6) | **must be vision-capable** | It is passed `images=`; do not move it to a model whose image support is unverified |

`cbias_config` routes worker/compiler to DeepSeek, unblocked by the anonymisation (`inputs/cbias_data_anon/`). Keep that reasoning recorded in the config and the raw directory gitignored.

---

## 6. Dormant code register

D6 revived everything that used to be listed here: `_run_one_design` (rebuilt around a single angle), `compile_script`, `_call_worker`, `parse_tasks`, `execute_script_in_docker`, `_format_artifacts`, `_load_plot_images`, `_image_blocks`, and `validate_execution`/`validate_requirements` (the latter re-roled to `validate_realization`) are all live again. **Nothing remains dormant.**

The underlying guardrail (§2 — do not delete code a later step is scheduled to revive) still applies to any future step that leaves something temporarily unused; mark it with a banner comment if that happens again:

```python
# --- DORMANT: revived in D<n> (<reason>). Do not delete. ---
```

`pick_best_seed` / `pick_other_seed` (D3) and `_candidate_score` (D5) remain deleted, not dormant — those were retired on purpose, not carried over.

---

## 7. Remaining steps

**D6 is implemented and validated (Run 12).** The full pipeline now runs end-to-end: ideate → judge → dedup → rank → realise top-k. Run 12 produced 1 realised, 3 pattern-not-shown, 0 not realisable, with `delivered_score` spread 0.09–0.94.

**Before D7, three items:**
1. **Surface `pattern_reasoning`** (Live Issue 9) — **RESOLVED (Run 14).** Threaded through the console log line, both result dicts, the ranked-summary block, and the dump; Run 14 showed a distinct, legible reason on every `pattern_not_shown` angle.
2. **Fix the dump's data flow** (Live Issue 10) — **RESOLVED (Run 14).** `_write_angle_dump` now runs after realisation instead of before it; Run 14's dump carried `realization_status`/`delivered_score`/`pattern_reasoning` on every realized angle.
3. **Fix the merge-log direction** (Live Issue 6) — **RESOLVED (Runs 14–15).** `_dedup_angles` attaches each merge's actual survivor (`survivor_id`) and the console prints `kept [X]` alongside the merge-time `->` arrow. Both runs fired a merge and the line read self-consistently — Run 15: `merged [self-identified-role-shift] -> [stakeholder-hybridity-depth] (0.240, within_iteration) kept [stakeholder-hybridity-depth]`, with the higher-scoring member correctly surviving.

**Ordering before D7 (Run 19):**
1. **Issue 8 — `delivered_score`.** Demonstrated five times (0.09, 0.81, 0.87/1.00, Run 18's 0.92-on-insight-0.15, and Run 19's 1.00 for a script with a broken plot). **FIXED, unconfirmed on a live run** — scoped the rubric to the angle via a new `angle_scope` parameter on `validate_realization` (user-selected fix; see the Live Issues section). Does not address the blank-PNG/degenerate-result cases (Runs 16, 17, 19) — the hard-cap option was not selected. No longer blocks D7 pending confirmation, but watch the next run for over-skipping.
2. **Descriptive angle ids** — readability only, but `angle-1` reappeared in Run 19 *as the run's highest-insight angle* (0.82). It will look anonymous at the top of the gallery. **FIXED, unconfirmed on a live run.** `ANGLE_GENERATION_PROMPT_SUFFIX`'s `<id>` field (human-owned) now asks for a short descriptive slug naming what the angle analyses and explicitly rules out generic `angle-N` placeholders. `_ensure_unique_id`'s collision suffixing is unchanged, so a genuine duplicate still resolves the same way.
3. **§10 Tier 1 + Tier 2 library expansion.** No longer urgent — Run 19 had zero `not_realisable` angles — but `sentence-transformers` has been requested in five runs and will resurface.

Issue 17 is resolved and confirmed. Run 19 achieved 4/4 realisation with no data-discovery failures at all.

Issues 13, 14, 15 and 16 are resolved. Issues 15 and 16 were confirmed by Run 18 (no nltk corpus failures, no `UnicodeDecodeError`). Run 17 produced no `not_realisable` angles at all, but Run 18 produced three, so that was not a stable improvement — Issue 17 is why.

**Before the next run: rebuild the `cbias-analysis` image** (`docker build --target cbias-analysis -t cbias-analysis:latest .`) whenever the Dockerfile changes — pure-Python fixes need no rebuild.

**All other D7 prerequisites are resolved and confirmed (Runs 14–15).** Issues 9, 10, 6 and 11 are closed on live runs, and Issue 7's `disconfirmed` calibration is confirmed. **D7 now has real content to display**: Run 15 produced a top-tier `realised_null` with a plot and a genuine finding, plus three `not_realisable` entries whose `requires` fields are the provisioning signal (§10).

One new item, **not a D7 blocker**: Live Issue 12 (fail-fast costs 3× compile budget on impossible angles, and the retry loop was unaudited) — **fixed, unconfirmed on a live run.** Per-attempt FAIL feedback is now logged and returned, and the loop aborts early on a verbatim-repeated error. Same "surface the reasoning" fix that made Issues 9 and 11 tractable, one stage upstream; the gallery does not depend on it.

Also fixed, readability-only, unconfirmed on a live run: **descriptive angle ids** (`angle-1` reappeared in Run 12, and again as the top-insight angle in Run 19). Collisions were already handled mechanically, but the gallery is where the generic label shows — see the ordering list above.

Live Issue 8 (`delivered_score` scope mismatch) can wait; it gates nothing, but the number should not be *displayed* as a quality measure until it is fixed.

---

### D6-fix — Repair the criteria split and the dedup ordering — **DONE (Run 12)**

**Goal:** Run 11's D6 result was uninterpretable until these landed. All four items shipped and Run 12 validated them.

**Changes**
1. **Make `CRITERIA_PROMPT` reliably emit both `<ideation_criteria>` and `<deliverable_rubric>` tags**, and **remove the `or criteria_response.strip()` fallback on the second extraction** — a missing tag must fail loudly, not duplicate the whole response into both variables (live issue 0). Consider asserting the two extracted blocks are not identical.
2. **Judge before dedup**, keeping the highest-scoring member of each cluster instead of the longest `why_non_obvious` (live issue 6). Judge calls share a cached prefix, so scoring all N rather than the deduped subset is close to free.
3. **Rename D6's `unsound` status** — it currently collides with D5's soundness vocabulary. `pattern_not_shown` distinguishes "the plot didn't show the claimed pattern" (D6, one judge) from "the data can't support this claim" (D5, a different judge). D7's gallery must not conflate them.
4. Re-run and confirm `delivered_score` is no longer clustered at ~0.3 and that at least some angles reach `realised`.

**Outcome (Run 12):** criteria blocks distinct; `delivered_score` spread 0.09–0.94; 1 realised, 3 pattern-not-shown, 0 not realisable. Two follow-ups surfaced and are recorded as Live Issues 7 and 8; the merge-log direction fix (Live Issue 6) is still outstanding.

---

### D7 — Gallery, not a winner

**Prerequisites: Live Issues 9 and 10.** The status split (Issue 7) has shipped, but the gallery needs the *reasoning* behind each status (Issue 9) and a data source that actually contains realisation results (Issue 10). Building on a status label with no explanation would give the reader a verdict they cannot evaluate.

**Changes**
1. `generate_and_optimize` returns a structured result, not a string. **This ripples into `app.py`**, which currently writes `analysis_script_<ts>.py`; the console header "FINAL COMPILED SCRIPT" is also now inaccurate.
2. Emit a self-contained gallery into `output_dir`. Per angle: its plot(s), a one-line "what's surprising here", **the soundness caveat as a visible confidence note**, which question/stakeholder it serves, and its realisation status.
3. **Four presentation tiers, not one ranked list** — the statuses answer different questions and must not be flattened:
   - `realised` and `realised_null` **together at the top**, ranked by insight. A clean disconfirmation closes a question and is often more useful than a confirmation; label it as such rather than demoting it. Show `pattern_reasoning` alongside the plot — for a `realised_null` it *is* the finding.
   - `pattern_not_shown` — executed but the output does not show the claim. A quality outcome; show it, secondary.
   - `not_realisable` — an *engineering* outcome (missing library). List these prominently **with their `requires`**, because that list is the signal telling you what to provision next (§10).
   - `unsupportable` angles never reach realisation, but are worth listing with their `soundness_reasoning` — Run 12's three were the most *sophisticated* angles in the run, and knowing what the dataset cannot support is itself a finding.
4. Also write each angle's generated script.
5. Build it to skim in under a minute. The human makes the final "is this actually interesting" call.

**Do not display `delivered_score` as a quality number** until Live Issue 8 is confirmed fixed on a live run — a fix (scoping the rubric to the angle) has landed but is unconfirmed, and even once confirmed it only corrects the scope mismatch, not the blank-PNG/degenerate-result cases (Runs 16, 17, 19) — `pattern_reasoning` remains the primary signal for the gallery either way.

---

### D8 — Saturation stopping and economy instrumentation

**Changes**
1. Stopping criterion = **novelty saturation**, using D4's *across-iteration* merge fraction against a configurable threshold. Keep `max_iterations` as a hard cap. (Across-iteration is the right signal — within-iteration measures differentiation, not saturation.) Dedup has now fired in Runs 8 and 11 (both single across/within merges), so a measurement exists but the *fraction* is still tiny — take a run with more iterations before setting the threshold.
2. **Verify caching** (§4) — the outstanding one-off measurement.
3. Instrument **cost per distinct angle surfaced**, reporting cached vs uncached input tokens alongside it. Replaces `req_score` as the number to tune against.
4. Confirm model tiering end to end against §5.
5. Update `README.md` and `CLAUDE.md` to describe the diverger.

---

## 8. Tuning notes

**Divergence is solved; the judges are validated; realisation is the live frontier.** Eight consecutive runs at 0.09–0.14 within-iteration with healthy cross-iteration behaviour, and Runs 9–11 confirmed the insight judge discriminates and the soundness judge reasons from actual data. Effort now belongs in D6-fix and D7, not in stances, thresholds, or judge prompts.

**The attractor effect is a standing property.** Closing off explored territory concentrates ideation onto whatever remains most concrete — that is the anti-target *working*. Counter-pressure comes from differentiating the calls, not from loosening the anti-targets. Expect to re-check the diversity numbers after any substantial report change.

**Q1 + Conventional is a reliable obvious-angle generator — and that is now useful.** It reliably produces a ticket-type/role-counting angle, which the insight judge as reliably floors at 0.20 (Runs 9 and 11). It costs one slot per iteration and functions as a **standing control**: if that angle ever scores well, the insight judge has drifted. Leave it in place.

**Thresholds are control parameters, not gauges.** D4's dedup threshold (0.22 — now exercised twice, evidence in §3) and D8's saturation threshold (still unmeasured) read the same Jaccard signal. Set both from logged numbers.

**The dataset has a sophistication ceiling, and the judges have found it.** Run 12's three `unsupportable` angles were the *most* methodologically ambitious in the run — MCA + k-modes on ~90 respondents, factor analysis over 15–20 items at n=37, BERTopic on perhaps 30 comments — and scored 0.72 / 0.68 / 0.40 on insight. The soundness reasoning cites the 5–10-respondents-per-item rule and computes the effective corpus explicitly.

This is a property of the data, not a defect: **on n=37–60 with four time points, methodological sophistication and defensibility are in direct tension**, and the achievable frontier is *simple method, modest claim* — where Run 12's one realised angle sits. Expect ~3 of 8 angles per run to be spent on ambitious ideas the dataset cannot support. That is a meaningful fraction of the budget and worth surfacing in the gallery (D7 tier 4) rather than discarding, since "what this dataset cannot support" is itself useful to the organising committee.

**The pipeline has produced its first actionable finding (Run 17).** `angle-readability-change` came back `realised`, `delivered_score=1.00`: Flesch Reading Ease **12.35 → 10.40 → 8.80 → 7.88** and Flesch-Kincaid Grade Level **17.24 → 17.53 → 17.65 → 17.91**, monotonic across all four years. CBIAS abstracts have become steadily harder to read. A quantified four-year trend on a non-obvious metric, and the first output an organising committee could act on directly. Retire it into Already Explored once acted on.

**The `realised_null` judgments are getting sharper, not just more frequent.** Run 17's `angle-satisfaction-profile-clusters` did not merely report "no trend" — it diagnosed *why* the hypothesis failed: the two clusters found were a single satisfaction **gradient** (every item higher in Cluster 0 than Cluster 1) rather than the claimed trade-off archetypes, prevalence bounced without direction (63→73→51→73%), and χ² against self-reported role was non-significant (p=0.42). Three independent lines of refutation, unprompted.

**The judge distinguishes a degenerate result from a credible null.** Run 17's `abstract-to-talk-conversion` produced acceptance rates of exactly 0.00 for every year — which *looks* like disconfirmation. The judge classified it `pattern_not_shown`, reasoning that this was "almost certainly a pipeline/matching bug rather than a genuine finding that 'no abstracts became talks' — the output is uninterpretable with respect to the claimed pattern, not a credible disconfirmation of it." That is the hardest case the three-way split has to handle, and it handled it. It also caught `role-training-hybridization` plotting only 2025 data under a chart titled "2024 vs 2025" — an internal title-vs-content inconsistency.

**The readability decline has replicated.** Run 17 found Flesch Reading Ease 12.35 → 10.40 → 8.80 → 7.88; Run 19, via a different implementation, found 19.62 → 19.40 → 17.35 → 15.41. Different absolute values (different text-extraction and cleaning choices), **same direction and same monotonicity across all four years**. Two independent confirmations — the strongest positive finding the pipeline has produced.

**The stakeholder-blurring hypothesis has now been disconfirmed three times, independently.** Run 15's `stakeholder-hybridity-depth` found dual-discipline training falling 22.6% → 16.2%; Run 16's `hybrid-background-blurring` found multi-domain proportion falling 86.8% → 81.1%; Run 19's `stakeholder-hybridity-analysis` found an essentially flat ~70% rate. **Three angles, three hybridity definitions, no support for "increasingly blurred" in any of them.** Treat this as settled and **reframe guiding question 5 in the report** — the diverger has answered it, in the opposite direction from its premise. Leaving it as-is spends a question slot per iteration re-litigating a closed question.

**A new finding worth acting on (Run 19).** `industry-speaker-attendee-alignment` came back `realised_null` with ρ=−0.40: industry *speaker* share rising steadily while industry *attendee* share falls. The programme is moving toward industry as the audience moves away from it. Concrete and actionable for the organising committee, and the opposite of the angle's own hypothesis.

**The judge catches partial execution, not just wrong results.** Run 19's `angle-1` was marked `realised_null` on the theme that *did* have a clean surveyed→removed transition (mentions declining 0.033 → 0.019 → 0 → 0, opposite the claim) — and the reasoning separately notes the script "never identifies or tests 'added' topics... so that part is simply absent rather than supported." Half-answered claims are being flagged as half-answered rather than silently passing.

**The anti-target keeps sinking the same family further.** `ticket-type-composition-trend` scored **0.10** in Run 15 — a new floor, below the 0.20 that the same family scored in Runs 9 and 11. Six runs of progressively harder marking on per-year category counts, without any prompt change. The insight judge is not just discriminating; it is discriminating *consistently* against a family the anti-target names only obliquely.

**The anti-target curation loop is now due its first real use.** `reg-lead-time-by-ticket-type` has appeared in five separate runs across different stances and question slots, and Run 13 *realised* it at `delivered_score=1.00`. That is the loop working as designed: a genuinely good angle, now done. Retire it into the report's Already Explored section, or it will keep winning a slot. This is the intended human step — automatic retirement would suppress angles that merely resemble a prior one.

**Judge prompts are the product.** The machinery around them is trivial; the wording is the whole game. They are human-owned for that reason.

---

## 9. Deferred: external retrieval

Q5 originally asked for evidence of post-attendance collaboration, which needs literature data. Removed from the report; retrieval is out of scope for this fork. When it returns:

- **Enrichment, not agent capability.** A host-side script (sibling to `anonymize_cbias_data.py`) materialises external data into `inputs/.../Publications/`. Everything downstream works unchanged on local files and the sandbox keeps `--network none`.
- **A structured literature API** (OpenAlex, Europe PMC) beats generic web search — clean co-authorship records rather than prose about papers.
- **Scope is speakers, not attendees.** Programme CSVs retain real names; abstract author names were anonymised away. Roughly 15–20 named people per year.
- **Causality needs a design**: temporal precedence, exclusion of prior ties, and a control group of comparable non-co-attending pairs. Without the control it is an anecdote generator.

This is also the capability the horizon-scanning fork depends on, so getting the pattern right on a narrow checkable question is worthwhile groundwork.

---

## 10. Deferred: library provisioning

**Library availability is a realisation constraint, not an ideation constraint.** Putting `AVAILABLE_LIBRARIES` into the ideation prefix would re-couple exactly what D2 decoupled. Do not narrow ideation to fit the image.

**Interim floor raised, pre-D6.** Run 8 (the first with the `requires` field live) measured the gap at numpy/pandas/matplotlib only: exactly one of eight angles ran on the image. `scipy`, `scikit-learn`, `nltk`, `seaborn`, and `textstat` were added to the base image before D6 landed (see below) - the dynamic, build-time-provisioning system described in this section is still not implemented; this was the cheap interim fix only.

When implemented:

- **`requires` field on angles** (add now, in D5-calibrate) — instrumentation first, so the design is driven by what ideation actually asks for.
- **Provision at build time, not run time.** `--network none` forbids runtime installs, so the union of `requires` across the top-k angles resolves into a derived image (`FROM cbias-analysis; RUN pip install …`) before realisation. The build is trusted; execution stays isolated. That distinction is why this is safe.
- **Allowlist package names.** Hallucinated package names are a live supply-chain attack vector — attackers register the plausible-sounding names models invent. Grow the allowlist from observed `requires`.
- **`sentence-transformers` is now the live decision, not a hypothetical.** Requested in four consecutive runs (10–13), and Run 13's `semantic-drift-via-embeddings` burned three compile attempts before `not_realisable`. Embedding-based angles are a recurring, well-ranked family — they scored 0.55 in Runs 12 and 13. Either bake the weights in, or accept that the family is permanently unrealisable and ensure D7 surfaces it as a **provisioning gap**, not a quality failure. Note the wasted budget either way: three compile attempts per run on an angle that cannot run.

**Model weights are not pip installs.** `sentence-transformers` and BERTopic download weights on first use; with no runtime network they fail after a successful install. Baking weights into the image is a much heavier lift and a reasonable place to draw the line.
- **Cheap interim win — done, before D6.** `scipy`, `scikit-learn`, `nltk`, `seaborn` and `textstat` were added to the base image. Small relative to torch, and covered everything ideation asked for on Run 8 - avoided D6 reporting a ~7/8 failure rate that would have been purely provisioning and told nothing about angle quality.
- **The baked corpus list must track what libraries actually reach for.** `punkt`/`punkt_tab`/`stopwords` were not enough: Run 17 showed `textstat` wants `cmudict` (Issue 15). Treat this as the same moving target as the package list itself.
- **`nltk` corpora are not a pip install.** `nltk.download()` fetches stopwords/tokenisers at runtime — the model-weights problem in miniature. Under `--network none` the package installs fine and then fails on first use. Bake the corpora in at build time. **Run 16 showed this was broken; resolved — see Live Issue 14.**

### Expansion decision (Run 16)

Do the two repairs first (Issues 13 and 14), or the expansion's effect cannot be measured against a clean baseline.

**Tier 1 — pure pip, no weights, no runtime network. Add without debate.** `networkx`, `python-louvain`, `gensim`, `statsmodels`, `umap-learn`, `hdbscan`. All requested repeatedly across Runs 9–16, all install cleanly, none touch the network at runtime.

**Tier 2 — `sentence-transformers` plus one pinned model. Recommended.** Requested in six consecutive runs and the single most common blocker. Unlike open-ended `transformers` it has a *bounded* footprint: bake `all-MiniLM-L6-v2` (~90 MB) at build time, set `HF_HOME` to the baked path and `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` so a runtime download attempt fails loudly instead of hanging against `--network none`. Use the CPU-only torch wheel index or this adds gigabytes for nothing.

**Where to draw the line — no open-ended `transformers` zero-shot.** Run 16's `semantic-topic-shift` wanted an arbitrary Hugging Face pipeline with an unbounded model-download surface. That is precisely the case where `not_realisable` is the honest answer.

**What this actually buys — two caveats.** Ideation never sees the library list by design (a realisation constraint, not an ideation constraint), so expansion raises the conversion rate but does not reduce future asks: Run 16 introduced `transformers` as a brand-new one. And roughly half the library-hungry angles are rejected by the soundness judge before realisation anyway — BERTopic/HDBSCAN clustering on ~50 documents per year has been marked `unsupportable` repeatedly. Realistic gain from Tier 2 is converting perhaps one angle per run from `not_realisable` to realised. Meaningful at `top-k=4`; not transformative.

**Provisioning is a moving target, not a gap to be closed once.** Every run has asked for packages the previous run's provisioning did not cover: Run 8 → scipy/scikit-learn/nltk/seaborn/textstat (added); Run 9 → networkx, python-louvain, sentence-transformers; Run 10 → spacy, gensim, sentence-transformers; Run 11 → umap-learn, hdbscan, sentence-transformers; Run 16 → **transformers** (zero-shot classification), a brand-new and heavier ask than any prior one. Ideation's library appetite grows as the angles get more creative. Treat `not_realisable` as a **permanent, recurring outcome class** rather than a transient defect.

Keep "not realisable" strictly separate from "unsound"/"pattern_not_shown" in the gallery — the first is an engineering outcome, the second a quality judgement.

---

## 11. Expectation setting

This will surface a wider, cheaper spread of angles than the converger, some non-obvious — a real improvement over a pipeline that reflects the author's own priors back at them. It will not out-think a domain expert on their own data. Treat it as a fast idea-generator that occasionally surprises, with the human at D7 as the actual evaluation function. Building around that division of labour, rather than trying to automate the judgement away, is what makes the compute worth spending.
