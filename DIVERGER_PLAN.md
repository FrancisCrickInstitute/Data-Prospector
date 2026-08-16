# Converger → Diverger conversion plan (rev. 45)

Working plan for `FrancisCrickInstitute/diverger-agents-template`.

**Rev. 45: Live Issue 30 fixed — library versions pinned, closing the third instance of the "assumed vocabulary" pattern.** Run 30 hit the same matplotlib `boxplot(labels=)` → `tick_labels=` deprecation (renamed in 3.9) that Run 22 already had, on an image whose `Dockerfile` pinned no versions and whose `AVAILABLE_LIBRARIES` stated none — so a rebuild could silently change the target API with nothing to notice. `Dockerfile`'s `cbias-analysis` target now pins every package to an exact, currently-current version (checked against PyPI directly, not assumed); `cbias_config.AVAILABLE_LIBRARIES` states the same versions and names the two renames that have actually bitten this project (`applymap`→`.map`, pandas 3.0; `labels=`→`tick_labels=`, matplotlib 3.9) rather than attempting an exhaustive changelog. Same shape as the A2/A5 `DOMAIN_NOTES` fixes, one layer further out — §15.7 item 2 now records all three recorded "environment description" layers fixed the same way. No pipeline code touched. **Needs a Dockerfile rebuild** (not done here — the user's own standing task) **and then a live run** to confirm no recurrence. See the Live Issue 30 entry for detail.

**Rev. 43: §15's A2/A5 "assumed vocabulary" pattern fixed in `DOMAIN_NOTES` — and the fix's own re-verification caught the original diagnosis undercounting the gap.** A5 (Run 29) traced to a hand-written Likert value map omitting `"Not Applicable"`; §15.7's prescribed fix (enumerate the real response vocabulary in `DOMAIN_NOTES` instead of leaving the model to assume one) was verified directly against `inputs/cbias_data_anon/Feedback/*.csv` before landing, which surfaced a second, larger gap the original A5 write-up had missed: the survey actually carries **two** disjoint Likert scales, not one — an agreement scale and a separate duration scale (`Far Too Short`...`Far Too Long`) that the 2024-2025 session/poster-session duration questions switch to, alongside a wording change from "...was an appropriate length" that was not previously documented as a *scale* change, just a phrasing one. `cbias_config.DOMAIN_NOTES` now enumerates both scales verbatim (exact casing — `"Not Applicable"`, not `"Not applicable"`), documents the duration-question wording/scale switch, and generalises the instruction to build any value map from the actual data, not an assumed vocabulary. No pipeline code touched. **Needs a live run** to confirm, ideally one exercising the duration-scale columns specifically. See §15's A5 entry for full detail, including the self-caught F-class near-miss.

**Rev. 41: Live Issue 28 fixed — the `realization_error` gallery tier no longer asserts a verified execution it can't confirm happened.** Both wording sites are now branched on the failure's actual stage instead of a single blanket claim: `_run_one_design` (`realization.py`) now returns a structured `error_stage` field on its `realization_error` result (previously the stage was only embedded inside the free-text `realization_feedback` string), threaded through `generate_and_optimize` (`pipeline.py`) onto the angle dict. `output.py`'s per-entry Note (`_gallery_entry`) now says one of three true things depending on `error_stage` and whether a script/artifact actually exists: the original "script and image(s) below are real" wording only when `error_stage == "validate"` (a verified PASS genuinely happened); "anything below is from an earlier, unverified attempt" when an earlier-stage break still left a stale script on disk (a compile attempt can raise after a *prior* attempt already produced text); and "there is no script or output to show" when nothing survived at all. The tier-level intro (`_write_gallery`) no longer makes a blanket claim either, since one run's realization_error tier can hold entries at different stages simultaneously — it now points the reader to each entry's own Note instead. Verified offline via a mocked `_write_gallery` call covering all three cases (deleted after passing, per convention); **needs a live run** to confirm the wording reads correctly against a real Docker/compiler failure, ideally reproducing Run 28's exact compile-stage case. See the Live Issue 28 entry for detail.

**D1–D7 are complete and confirmed on live runs.** The pipeline ideates, diverges, dedups, judges — with a graded (not gated) soundness verdict — selectively realises only the top-ranked angles into executed, Docker-verified scripts, and writes the result up as a tiered markdown gallery. **D7 confirmed on Run 21** (`gallery_20260812_204611.md`): all four tiers render, relative image paths resolve, script links are correct, `delivered_score` is absent as designed, and Issue 19's testing-status note appears in both top-tier Findings. **The functional programme is finished.**

**Live Issue 21 — CONFIRMED WORKING (Run 23).** The widened fix (raised `max_tokens` default, worker-gather resilience, whole-function try/except with per-stage tracking) fired exactly as designed on the first run after landing: worker resilience logged `Workers: 5/7 succeeded - failed: main, recode_items`, the resulting failure was labelled `realization_error` with `stage='compile'`, the fifth gallery tier rendered with a Note and no phantom `requires`, and the `[realize]` line counted it correctly. **Closed.** Live Issue 22 (silent metric drop, NLTK resource) also held with no recurrence. See §3 for the Run 23 evidence.

**Live Issue 23 — FIXED AND CONFIRMED IN SITU (Run 24). Closed.** Run 24 completed with no `('Streaming is required...')` error at any call site — including the DeepSeek-routed compiler, which is where Run 23 actually failed and which the original smoke test (against `claude-opus-4-8`) had not exercised. Original entry follows.

**Live Issue 23 — FIXED, confirmed via a direct live smoke test; not yet confirmed on a full pipeline run.** Run 23 also surfaced a new failure: the Issue 21 fix's own raised default (8192 → 16384) doubles to 32768 on retry, which crosses the Anthropic SDK's client-side guard against non-streaming requests that might exceed ~10 minutes — `('Streaming is required for operations that may take longer than 10 minutes...')`. `llm_call` now calls `client.messages.stream(...)` + `get_final_message()` instead of `client.messages.create(...)`, which removes the ceiling rather than moving it again; the return contract (a plain string) is unchanged, so no caller needed editing. Verified with a live call to `claude-opus-4-8` at `max_tokens=40000` (so a retry would reach 80000, well past the ceiling that failed at 32768) — confirmed no client-side error and a normal response. See §3 for detail.

**Rev. 39: Live Issue 27 fixed — the compile-cycling abort's log/feedback wording no longer claims a saving on the one-cycle it can't actually catch.** With `max_compile_attempts=3`, a two-cycle repeat can only be detected on the final attempt, where nothing is left to skip; `_run_one_design` now checks whether attempts genuinely remained before logging "aborting the N remaining..." versus "nothing was saved by detecting it", and the `not_realisable` feedback's "(aborted early...)" note follows the same distinction. Wording only — `max_compile_attempts` unchanged, the loop's break behaviour unchanged. Verified offline with a mocked run of both cases, deleted after passing. **Needs a live run** to confirm the two log paths read correctly against a real Docker/compiler cycle. See the Live Issue 27 entry.

**Rev. 38: Live Issue 26 fixed — `llm_call` no longer returns a truncated response as if it were complete.** New `reject_truncated` parameter on `llm_call` (default `False`, so every existing call site is unaffected); `compile_script`'s call is the one site that opts in, since a compiled script is the case the entry established as never usable when cut mid-generation. A double-truncation now raises its own error message instead of the misleading generic "No text content" one. Verified offline only (a mocked test of all four `llm_call` paths, deleted after passing) — **needs a live run** to confirm a truncating compile response actually retries instead of producing the mid-token `SyntaxError`s seen in Runs 26–27. See the Live Issue 26 entry for detail.

**Rev. 37: Run 27 — first live run on the eight-module split, confirming D-consolidate items 4–6 end to end, plus two new Live Issues.** 1 realised, 2 realised_null, 1 not realisable, 1 unsupportable, 0 judge errors. **Live Issue 26 (diagnosed, not yet fixed)**: `llm_call`'s retry-at-double only fires when a response has no text at all, so a response that produces text and is then truncated mid-token passes through as if complete — two truncation-shaped `SyntaxError`s across Runs 26–27. **Live Issue 27**: the compile-cycling abort's log line claims a saving that `max_compile_attempts=3` cannot actually deliver — a two-cycle can only be detected on the attempt that exhausts the budget, so there is nothing left to abort into. Not urgent, wording only. §15 gains **A4**, a second instance of the *unreachable category* pattern (A3's sibling): a keyword classifier whose rule order and assumed vocabulary silently drop the very category an angle's hypothesis is about, caught only by the realisation judge reading the artifact. See the Live Issue 26/27 entries and §15 for detail.

**Rev. 36: D-consolidate items 4–6 landed — `pipeline.py` split into eight modules, run-archaeology trimmed from comments, `summary_text`/`delivered_pass` deleted.** `pipeline.py` (1820 lines) is now `generate_and_optimize` alone (312 lines) plus seven single-purpose modules (`llm.py`, `parsing.py`, `sandbox.py`, `ideation.py`, `judging.py`, `realization.py`, `output.py`) per the module table item 4 already specified; `from prompts import *` replaced with explicit imports throughout. Verified offline — syntax, a real `import pipeline` exercising the whole chain, `app.py`/all three domain configs still importing cleanly, and a mocked end-to-end `generate_and_optimize` run (fake `llm_call`/`execute_script_in_docker`) producing the same result shape as before. **No behaviour change, all still needs a live run to confirm nothing was lost in translation** that offline mocking can't catch. See the item 4/5/6 entries for detail.

**Rev. 34: D-consolidate item 3, the default half — `app.py --config` now defaults to `cbias`, not the broken `bioimage`.** The bare-invocation happy path both docs describe now actually runs instead of pointing at `./inputs/report/`/`./inputs/images`, neither of which exists in this repo. This is only the default-flip half of item 3's option (a) — `bioimage_config.py`/`trello_config.py` are unchanged and still importable, and §2's "keep it a template" guardrail is not yet amended to match; see the item 3 entry. `README.md`/`CLAUDE.md` updated to match. Also backfills the rev. 33 banner below, which was omitted when that revision landed.

**Rev. 33: D-consolidate items 1–2 landed (`CLAUDE.md`/`README.md` rewritten), and a new §15 catalogues every model-vs-data failure across Runs 1–26.** Both docs now describe the diverger's real architecture — five realisation outcomes, dedup measurement-only, the human-owned-prompts guardrail — instead of the converger's. §15 groups every live issue into six failure classes (data misread from `DOMAIN_NOTES` alone, environment-assumption drift, silent degradation, model-output parsing, judge/heuristic score decay, and the analyst layer's own mistakes — including this document's own rev. 30 misdiagnosis of Live Issue 25) and states the governing rule explicitly: *the pipeline's outputs are evidence about the pipeline; only the data is evidence about the data.* Docs-only; no pipeline code changed.

**Rev. 32: Live Issue 25's first fix was flaky — replaced with a structural one.** The rev. 31 fix (name the satisfaction question as an exception in `DOMAIN_NOTES`) worked but was correctly challenged on review: a prompt note only helps if the model reads and applies it every time, and naming one exception doesn't generalise to the next numeric-scale question. Landed instead: (1) the always-empty `"Points -"`/`"Feedback -"` companion columns are now dropped structurally, in `anonymize_cbias_data.py`, removing the three-near-identical-names ambiguity from the data entirely rather than instructing around it; (2) `DOMAIN_NOTES` now teaches "inspect a column's actual values before assuming it needs Likert-text mapping" instead of listing satisfaction as a special case. **Needs `anonymize_cbias_data.py` re-run against local raw data** before this takes effect - not done here, the raw source isn't available in this environment. See the Issue 25 entry.

**Rev. 31: Live Issue 25 was wrong — corrected, not just resolved.** Recorded as a data defect ("overall satisfaction is unusable") on the strength of two independent generated scripts agreeing. Direct inspection of `inputs/cbias_data_anon/Feedback/*.csv` shows the underlying data is fine — fully populated every year — and the real cause is `DOMAIN_NOTES`'s Likert-text-mapping instruction (correct for every other survey question) being silently wrong for the one question that's already numeric, producing an all-NaN result indistinguishable from missing data at the console. Fixed in `cbias_config.DOMAIN_NOTES` only, no pipeline code touched. **The lesson generalises**: two independent scripts agreeing that data is bad is evidence the *scripts* share a wrong assumption, not evidence about the data — check the raw files before writing a data-gaps note. Needs a live run to confirm.

**Rev. 29: Live Issue 24 landed — the interim, option (b), not a delete.** `_dedup_angles` still clusters the full judged archive every run, unguarded — the guiding-question guard tried in rev. 26/27 is reverted outright, not just left unused, since Run 24 showed it only catches one of the three known false positives. But `generate_and_optimize` no longer acts on the result: `all_angles` is now built from the full archive, not the deduped survivors, and the `[dedup]` log line is reworded (`MEASUREMENT ONLY, not acted on`, `would merge [X] -> [Y] ... would keep [Z]`) so a human reading the console can't mistake the measurement for an action. This is the fallback the Issue 24 entry offered over deleting the ~115 lines outright, chosen to keep collecting "would this ever have fired correctly" evidence at zero cost to run coverage. Verified offline only. **Needs a live run**: the next `[dedup]` line is the first real data point for that measurement, and it is also the first check that near-duplicate angles surfacing side-by-side in the gallery is actually tolerable in practice, not just tolerable in theory.

**Rev. 27: Run 24 is the first fully clean run — no infrastructure failure at any stage.** 3 realised, 1 realised_null, 0 not realisable, 0 unsupportable, 0 judge errors. **Live Issue 23 is confirmed in situ** (no streaming error anywhere, including the DeepSeek-routed compiler that failed in Run 23), and Issue 21's machinery had nothing to catch. The functional programme and the reliability work are both finished. Two things changed as a result, neither of them code: **Live Issue 24's proposed guard is dead** — Run 24's two dedup false positives were *within* a guiding question, which the guard would not have caught — and **§8 loses a second "replicated" finding** to the same trap that caught readability.

**Rev. 26 added §13 and a deferred backlog step, D-simplify**, from re-reading the design against Anthropic's [*Building effective agents*](https://www.anthropic.com/engineering/building-effective-agents). It holds up better than §12's line-counting suggested — five of that post's named patterns composed, with no framework, which is the post's central recommendation. **Nothing implemented and working changed on account of it.** What changed is the standard applied to *outstanding* items.

**Rev. 19 added a structural review of the whole repository (§12) and a new step — D-consolidate — that acts on it.** The finding, in one line: *the architecture is not over-complex, but the repository around it has drifted badly out of step with what the code now does.* `README.md` and `CLAUDE.md` describe the converger and contain zero occurrences of the words "angle" or "gallery"; the documented default entrypoint is broken; `pipeline.py` has grown to 1681 lines of which roughly a third is run archaeology that duplicates this document. **D-consolidate runs before D8**, because `CLAUDE.md` is what briefs the coding agent making every future change, and a wrong brief is a cause of drift rather than a symptom of it. With D7 confirmed, D-consolidate and Issue 21 are the whole of the remaining near-term work.

**A note on how Issue 21 went wrong, worth generalising.** Rev. 20 diagnosed it from the *error text* of the two failed angles without evidence about *which call* raised it, and asserted the Docker spend had been paid and written off. Run 22's per-stage console logging shows the failure occurs before any Docker run. The lesson is the one this document already applies everywhere else: **§2 says "instrument before tuning" — the same rule applies to diagnosing.** When a failure is only visible as a caught exception at the top level, add the per-stage logging first (as Live Issue 12 did for the compile loop) and fix second.

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
- **Do not delete dormant code.** See §6. *Dormant* means "a later step is scheduled to revive it". It does **not** cover genuinely dead code — a value computed and never read, a formatted string no caller consumes. §6 records that nothing is currently dormant, so D-consolidate's deletions do not conflict with this guardrail; check §6 before deleting anything and add to it if you leave something temporarily unused.
- **Follow the caching convention (§4) for every new prompt.**
- **Reuse, don't rewrite.** `_parse_xml_items`, `_jaccard`/`_token_set`, `_log_iteration_diversity`, `_angle_record`, `_dedup_angles`, `llm_call` (semaphore + images + `cache_prefix` + provider routing), `extract_xml`, `format_prompt`, the Docker sandbox and artifact copy-out all carry over.
- **Instrument before tuning.** Every threshold here should be set from observed numbers. §3's run log is the evidence base.
- **Keep it a template.** No new frameworks, no tree-search controllers, no persistent Elo ratings, no async task queues. *This guardrail has held on the architecture and failed on the repository* — see §12.3. D-consolidate item 3 forces an explicit decision about whether "template" is still the honest description, because two of the three shipped domain configs are now vestigial and one of them is the broken default.
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

**D7 — implemented and CONFIRMED (Run 21).** `generate_and_optimize` now returns a dict (`all_angles`, `summary_text`, `gallery_path`, `dump_path`, `scripts_dir`) instead of a plain-text blob; `app.py` no longer writes a misleadingly-named `analysis_script_<ts>.py` and just points at what was written. All five D7 "Changes" items landed:
1. Structured return (above) — the ripple into `app.py` the spec called for.
2. `_write_gallery` emits `gallery_<ts>.md` into `output_dir`, markdown + a sibling images directory (the user's choice over a self-contained single-file HTML artifact, since this is a local CLI pipeline writing to disk, not a hosted page) — images are referenced via relative paths straight into the existing `artifacts/<angle_id>/` directories rather than copied a second time.
3. **Four tiers, not one ranked list**, exactly as specified: `realised`/`realised_null` together at the top, ranked by **insight** (not soundness, and not realization order — Run 20 showed the run's highest-insight angles disconfirm more often than they confirm, so this is a deliberate departure from `all_angles`'s own soundness-first sort); `pattern_not_shown` secondary; `not_realisable` shown prominently with `requires`; `unsupportable` shown with `soundness_reasoning`. A closing "also generated" section one-lines everything judged but below `--realize-top-k`, pointing at the full-detail dump alongside it.
4. Each realized angle's compiled script is now written to `output_dir/scripts/<run_ts>/<angle_id>.py` (previously kept in memory only, per D6's own note) and linked from its gallery entry.
5. `delivered_score` is deliberately **omitted** from the gallery entirely (not just de-prioritized) — the D7 spec's "do not display until Issue 8 is confirmed fixed" instruction, taken to its natural conclusion given Issue 8's fix only ever addressed the scope mismatch, not the blank-PNG/dropped-data cases. `pattern_reasoning` carries the substance instead, shown as "Finding" on every top-tier entry.

**Issue 19 bundled into this same pass** (cheap, same code path): `REALIZATION_VALIDATOR_PROMPT_SUFFIX`'s `<pattern_reasoning>` tag now also asks the judge to note whether the console output includes or omits a statistical test of the claim — informational only, not a verdict input, per Issue 19's own "do not add a significance requirement" conclusion.

`_write_angle_dump` now takes `timestamp` as a parameter instead of stamping its own, so the dump, the gallery, and the scripts directory for one run all share a single run identifier.

**Run 21 confirms it against a real archive.** `gallery_20260812_204611.md`: two top-tier entries (one `realised`, one `realised_null`, interleaved and insight-ranked), two `not_realisable`, an "also generated" section for the two below the cutoff. Relative image paths resolve; `[script](scripts/<run_ts>/<angle_id>.py)` is correctly single-prefixed, settling empirically the double-`scripts/` question raised at review time (§12.6); `delivered_score` appears nowhere. No fifth outcome shape was missed. **The insight-ranking decision is vindicated on its first real archive:** the 0.85 disconfirmation leads the 0.78 confirmation, exactly the Run 20 argument for interleaving rather than sorting `realised` first.

One presentation note, not a defect: the `Finding` and `Hypothesis` blocks are long — a full paragraph each — so the "skim in under a minute" criterion (D7 item 5) is met for the *structure* but is borderline for the *prose*. Both fields come straight from the judge and the angle schema, so shortening them is a prompt change, not a gallery change. Leave it until a human has skimmed two or three galleries and can say whether it actually gets in the way.

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
| 30 | 0.08 / 0.10 | working | **The A2/A5 `DOMAIN_NOTES` fix worked on its first run** — the generated `satisfaction-driver-importance-trend` carries both scales separately, handles `"not applicable"` explicitly, and reports unknown values as a data gap (§15 A2/A5). 2 realised, 2 realised_null, 0 not-realisable, 0 unsupportable, 0 judge errors. **But two of four compiles failed attempt 1 on the identical matplotlib `labels=` deprecation** — §15 B4 recurring, now Live Issue 30. Both recovered attempt 2. **Truncation-shaped syntax errors remain at zero for a third run** (Issue 26 unaffected — see its entry). Highest statistical rigour in the log: 2 of 4 realisations reported real tests (two permutation tests with p-values; Spearman rho+p for all six features). Dedup 6th data point: 1 would-merge at 0.247, false positive, zero cost — and `_pick_representative` kept the better angle |
| 29 | 0.11 / 0.07 | working | **Cleanest run in the log: 4/4 realised or disconfirmed — no not-realisable, no unsupportable, no pattern-not-shown, no judge errors.** Every compile passed on attempt 1/3 for the **second consecutive run** (8 straight first-attempt compiles, Runs 28–29 — Issue 26 further supported). Issues 27 and 28 both **unexercised** (no cycling, no realization errors), so both remain unconfirmed live. **Dedup produced zero would-merges for the first time since the measurement began.** New: an 11-function architecture compiled and passed first time, well above the previous max of 7. §15 A5 logged (`"Not applicable"` cost 2 of 4 years) |
| 28 | 0.09 / 0.09 | working | **Issue 26 provisionally confirmed: every compile succeeded on attempt 1/3 — no `Compile attempt 2/3` anywhere and zero syntax errors, the first such run since the pattern appeared.** 2 realised, 1 realised_null, 1 realization_error (DeepSeek 402, account balance — not a pipeline fault), 2 unsupportable. Issue 21's machinery caught and staged it correctly, but the fifth tier's boilerplate asserted a script and images that did not exist (Live Issue 28). Issue 27's branch not exercised. Third `<task>` XML parse failure (col 446). Dedup 4th data point: 1 would-merge at 0.265, within-question, false positive, zero cost. **§15 B1 partially self-corrected** — the TF-IDF fallback was declared in console and script, though not in the gallery |
| 27 | 0.09 / 0.08 | working | **First live run on the eight-module split — completed end to end, so D-consolidate 4–6 are confirmed, not just verified offline.** 1 realised, 2 realised_null, 1 not realisable, 1 unsupportable, 0 judge errors. **Two truncation-shaped `SyntaxError`s** (Live Issue 26). Compile-cycling abort fired for the first time but saved nothing (Live Issue 27). Dedup measurement, 3rd data point: 1 would-merge at 0.251, within-question, false positive, zero cost. Judge caught a second unreachable-category classifier bug (§15 A4) |
| 26 | 0.09 / 0.11 | working | `--angles-per-iteration 4`. **`pattern_not_shown` fires for the first time since D6** — the realisation judge caught a keyword-list bug in generated code from the plot alone (§15, A3). Dedup measurement, 2nd data point: 1 would-merge at **0.360, the highest similarity in the log, and still a false positive** (item-clustering vs respondent-clustering); both members judged unsupportable, so zero cost. 3 realised, 1 pattern_not_shown, 0 not realisable, 0 judge errors, 2 unsupportable. One generated-code `SyntaxError`, recovered attempt 2 |
| 25 | 0.10 / 0.10 | working | `--angles-per-iteration 4`. **Issue 24's measurement produces its first live data point** (see the Issue 24 entry): 2 would-merges, both across-iteration (0.225, 0.280), both within a single guiding question again, **neither pair consumed two realisation slots — but pair 1 missed by 0.02 insight**. 2 realised, 1 realised_null, **1 genuinely not-realisable** (first legitimate use of that tier: `satisfaction-driver-shift` exhausted 3/3 attempts, each one *raising* rather than faking — Issue 11's fail-fast working), **2 unsupportable — the highest yet, both well-argued**. Judge independently enforced §8's state-vs-trend distinction on stakeholder hybridity. Readability disconfirmed a 5th time; sector question produced a **third mutually inconsistent answer** (see §8) |
| 24 | 0.11 / 0.08 | working | `--angles-per-iteration 4`. **First fully clean run: 3 realised, 1 realised_null, 0 not realisable, 0 unsupportable, 0 judge errors — no infrastructure failure at any stage.** Issue 23 confirmed **in situ**, including on the DeepSeek-routed compiler that failed in Run 23 (the smoke test had only covered the Anthropic client). `max_compile_attempts=3` visibly earned its keep for the first time: `open-comment-triggers` recovered on attempt 3 after a silent-no-op catch then a pandas indexing error. **Dedup false-positived twice, both *within* a guiding question** — the evidence that killed the Issue 24 guard. `sentence_transformers` substitution visible end-to-end in the log (§15 B1). Second `<task>` XML parse failure (col 527) |
| 23 | 0.11 / 0.12 | working | `--angles-per-iteration 4`. **Dedup 8→5, three across-iteration merges (0.225, 0.242, 0.309)** — one of them a false positive that removed the run's only guiding-question-5 angle (see Issue 24). 0 solid / 5 caveat / 0 unsupportable. **Issue 21's widened fix fired correctly and completely**: worker resilience logged `Workers: 5/7 succeeded - failed: main, recode_items`, the failure was labelled `realization_error` with `stage='compile'`, the fifth gallery tier rendered with a Note line and no phantom `requires`. New failure though — Issue 23 (SDK streaming ceiling). Readability **disconfirmed** this run, correcting §8 |
| 22 | 0.10 / 0.10 | working | `--angles-per-iteration 4`. Dedup **8→8, 0 merges**. 0 solid / 7 caveat / 1 unsupportable. Realisation: **2 realised, 1 realised_null, 0 pattern-not-shown, 1 not realisable** — the last is Issue 21 recurring at the *worker* call site, so the Issue 21 fix did not fire (`0 realization judge error(s)`). **Iteration 2 contributed 2 of the 4 realised angles** — settles D-consolidate item 8. Readability decline replicates a fourth time; speaker/attendee sector divergence replicates Run 19. New: Issue 22 (silent metric drop) |
| 21 | — | — | **D7 CONFIRMED — the gallery is real.** Archive 6 post-dedup; realize-top-k 4. **1 realised, 1 realised_null, 0 pattern-not-shown, 2 not realisable — but both "not realisable" are Live Issue 21, not provisioning.** 0 unsupportable, a first. Issue 19's testing-status note present in both Findings. Stakeholder-blurring *confirmed* as a state claim after three disconfirmations of the trend claim (see §8) |
| 20 | 0.10 / 0.09 | working | **Second consecutive 100% realisation.** Dedup 8→6 (0.230 + 0.393). 0 solid / 5 caveat / 1 unsupportable. Realisation: **1 realised, 3 realised_null, 0 pattern-not-shown, 0 not realisable.** Issue 18's fix held (clean extraction, descriptive slugs). **The readability finding failed to replicate under significance testing — see Issue 19** |

**Divergence is solved.** Both axes are healthy and have been for seventeen consecutive runs. Do not spend further effort here.

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

**Resolved for D7's purposes by omission, not by trusting this fix as sufficient.** The scope-skip fix above is still live (it improves `delivered_score` as a number), but since it demonstrably doesn't close the degenerate-result gap, D7's gallery does not display `delivered_score` at all — see §3's D7 entry. This settles the "is `delivered_score` fixed enough to show" question without needing the scoping behaviour confirmed first; the scoping fix itself is still worth confirming on a live run on its own merits (it still feeds `_write_angle_dump`), just no longer a D7 blocker.

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

**18. RESOLVED (Run 20) — the criteria-extraction call mirrored the report's own markdown headers instead of emitting `<ideation_criteria>`/`<deliverable_rubric>` tags (Run 20).** `CRITERIA_PROMPT` asks for two tagged XML blocks, but the model (`requirements_evaluator_model`, Sonnet) responded with plain markdown instead — `# IDEATION CRITERIA` as an ATX heading followed by prose, no tags anywhere. `extract_xml` found nothing for either tag (`0 / 0 chars extracted`), so the existing loud-fallback (Live Issue 0) fired correctly and degraded both `ideation_criteria` and `deliverable_rubric` to the full raw report — not a crash, but a real quality loss: D6's realization validator judges the deliverable rubric bullet-by-bullet (and, since Live Issue 8, skips bullets out of scope for the angle), and "the whole report" is neither bulleted nor scoped, so that machinery has nothing to work with.

**Likely cause:** the task report itself is heavily markdown-formatted (`#`/`##` headings throughout), and `CRITERIA_PROMPT` labels its own two sections "FIRST - IDEATION CRITERIA" / "SECOND - DELIVERABLE RUBRIC" in a similar all-caps style just above the tag examples — plausibly enough to prime the model to echo the report's own formatting convention back instead of switching into the requested tags.

**Fix landed, two parts:**
1. `CRITERIA_PROMPT` now explicitly forbids markdown headings and any text outside the two tags, and explicitly calls out not to mirror the report's own formatting — the direct prompt-level fix.
2. Added `_extract_markdown_section()` as a secondary extraction pass, tried only when `extract_xml` comes back empty for a tag: it recovers the same content from under an ATX heading naming the section (`# IDEATION CRITERIA` / `# DELIVERABLE RUBRIC`), stopping at the next such heading or end of text. This is the same "tolerate minor formatting drift" pattern `_parse_xml_items` already uses for `<task>`/`<angle>` blocks, applied here so an exact repeat of this failure recovers the real content instead of degrading to the raw-report fallback. Verified standalone against the actual malformed response text from this run — both sections extract correctly.

Needs a live run to confirm no recurrence of the WARNING, and — if it does recur despite the prompt fix — that the markdown fallback recovers usable criteria instead of falling through to the raw-report degrade.

**19. Presentation note (NOT a blocker) — `realised` does not mean "statistically established" (Run 20).** Runs 17 and 19 reported a monotonic readability decline by eyeballing four annual means; Run 20 ran the same family with Kruskal–Wallis tests and got p=0.187 / 0.068 / 0.117 plus one marginal non-monotonic p=0.024. So whether a four-point trend lands as `realised` or `realised_null` depends partly on whether the generated method happened to include a test.

**This is worth surfacing, not gating.** `realised` means *the output legibly shows the claimed pattern* — a statement about whether the plot is readable and on-topic, not a truth claim about the effect. The human at D7 is the evaluation function (§11); the pipeline's job is to surface leads worth a second look.

**Do not add a significance requirement.** It was briefly proposed here and it is wrong on three counts:
1. It would make the realisation validator a fourth judge doing statistical review — scope creep, and duplicating the soundness judge, which already caveats four-point trends correctly ("treat as indicative") and kills genuinely uncomputable ones.
2. On n=37–60 across four years almost nothing clears p<0.05, so **the bar would select for boring**: it would push ideation toward angles with enough n to pass, which on this dataset means counting things — straight into anti-target territory.
3. "Declining but not significant on four points" is a perfectly good lead. Suppressing it loses exactly the output the diverger exists to produce.

**The only change worth making:** have `validate_realization` mention in `pattern_reasoning` whether the claim was statistically tested, as *information beside the plot*. No new machinery — the validator already sees the console output. Not a gate, not a ranking input, not a separate tier.

**RESOLVED (Run 21).** `REALIZATION_VALIDATOR_PROMPT_SUFFIX`'s `<pattern_reasoning>` tag now explicitly asks for this, worded the same way — informational only, no change to `pattern_outcome`'s three-way vocabulary or to how any tier is ranked. Both of Run 21's top-tier entries carry it unprompted and in the right register: `undefined-acronym-density-trend` reports bootstrap 95% CIs and reasons from their overlap; `stakeholder-hybridity-index` states plainly that *no formal significance test or confidence interval is reported; the finding is descriptive only*, then separately notes that the raw co-occurrence matrix corroborates the pattern independently of the weaker derived metric. That is exactly the intended shape — the reader can see which kind of evidence they are looking at without the verdict having moved.

**20. `applymap` — the compiler writes against an older pandas API than the image provides (Run 20).** `feedback-persona-mca` attempt 2 died on `profile.applymap(...)`, removed in pandas 3.0. Recovered on attempt 3, so it cost one attempt. If it recurs, add the installed pandas version (and the `applymap` → `map` note) to `DOMAIN_NOTES`, which now reaches the compiler as of Issue 17.

**21. A failed judge call is mislabelled as a provisioning gap, and discards a possibly-successful Docker run (Run 21).** Two of four realised angles — `feedback-satisfaction-driver-shift` and `program-abstract-alignment-vs-attendee-mix` — came back as:

```
ValueError("No text content in response (stop_reason=max_tokens,
  blocks=['thinking']). The token budget was likely consumed by thinking...")
```

That is `validate_realization` exhausting its budget in the thinking phase. Note `llm_call` **already retried at double** (8192 → 16384) before raising, so this is a two-strikes failure, not a one-off.

**Three separate problems, in ascending order of seriousness.**

1. **Wrong tier.** `generate_and_optimize`'s `isinstance(result, Exception)` branch sets `realization_status = "not_realisable"`, so the gallery files both under *"Not realisable — engineering / provisioning gaps"* and prints their `requires` fields (`scipy`, `statsmodels`) beside them. **Both libraries have been in the image since §10's interim fix.** A reader concludes there is a provisioning gap; there is none. This is a *third* failure class — infrastructure — leaking into a tier D6 item 5 and §10 both insist must stay clean. `requires` in particular should not be displayed for a failure that has nothing to do with libraries.

2. **The compiled script is discarded.** The exception branch `continue`s before reaching `if scripts_dir and result.get("script")`, so nothing is written to `scripts/<run_ts>/`. D7 item 4's rationale — *"a human debugging a provisioning gap wants to see what the compiler actually produced"* — applies with more force here, not less: the script is the only remaining evidence of what happened.

3. **The Docker spend is written off.** `validate_realization` is only reached after a verified execution PASS (FAIL returns early, SKIPPED short-circuits — see `_run_one_design`). So both angles very likely **compiled, ran in the sandbox, and produced artifacts**, and the whole chain was thrown away because the judge could not fit its reasoning in 16k. Run 21's 50% realisation rate is a `max_tokens` figure wearing a provisioning costume.

**Fix, three parts, all small:**
1. **Raise `validate_realization`'s `max_tokens`.** `compile_script` already passes `16384` explicitly; the validator uses the 8192 default and doubles to 16384 on retry, which was not enough twice in one run. It is the most context-heavy call in the pipeline (report + rubric + angle scope + script + console output + up to `_MAX_VALIDATOR_IMAGES` PNGs), so the default is simply wrong for it. Pass an explicit larger budget rather than raising the global default.
2. **Give infrastructure failure its own status.** A fourth value — `realization_error` — or at minimum a flag that keeps it out of the provisioning tier and suppresses `requires`. The plan has been strict about never conflating engineering outcomes with quality outcomes; this is the same principle one category further out.
3. **Persist whatever exists on the exception path.** Return a partial result from `_run_one_design` rather than letting the exception escape, so the script and artifacts survive. Cheapest version: wrap the `validate_realization` call in `_run_one_design` itself, so a judge failure degrades to a status rather than destroying the design's output.

**Verify:** a run in which a validator call fails should still write the script, list the real artifacts, and keep the angle out of the provisioning tier.

**FIXED, unconfirmed on a live run.** All three parts landed exactly as scoped, all in `pipeline.py`:
1. `validate_realization`'s `llm_call` now passes `max_tokens=16384` explicitly (was the 8192 default, doubling to 16384 only on retry — the same ceiling Run 21 hit twice). Matches `compile_script`'s existing explicit budget rather than leaving the heaviest call in the pipeline on the generic default.
2. New `realization_status` value: `"realization_error"` — executed (Docker-verified PASS) but the judge call itself failed, so there is no `pattern_outcome` to report. Kept strictly separate from `not_realisable` in `_write_gallery`: it gets its own fifth tier ("Executed, but unscored — the judge call failed, not the analysis"), which never renders `requires` and says plainly this is not a provisioning gap. `_gallery_entry` shows a **Note** line with the failure text in place of the (missing) **Finding** line, and still renders the real image(s) and script link, since both genuinely exist. `generate_and_optimize`'s `[realize]` console summary line and the gallery's intro-sentence counts both got a fifth count alongside it, so a run with a judge failure is visible from the log line, not just discoverable inside the gallery.
3. `_run_one_design` now wraps the `validate_realization` call itself in `try`/`except`, returning the same result shape as its other early-returns (`not_realisable` on FAIL/SKIPPED) but tagged `realization_error`, carrying the real `script` and `artifacts` that were already produced. The exception never reaches `generate_and_optimize`'s `asyncio.gather(..., return_exceptions=True)` handler at all for this failure mode — that handler now only ever fires for genuinely unexpected failures upstream of a verified execution (orchestrator/worker/compiler infra crashes), where `not_realisable` is still the correct label, since those never reached a verified PASS either.

`_write_gallery`/`_gallery_entry` verified standalone (synthetic angle data: one `realised`, one `realization_error` with a `requires` field and a real artifact/script, one `not_realisable` with its own `requires`) — confirmed the new tier renders the script/image, the `requires` field appears only under `not_realisable` and nowhere under the new tier, and the intro-sentence count picks up the new bucket correctly.

**RUN 22: the fix is correct and it did not fire. The same error recurred at a different call site.** `stakeholder-role-training-overlap` failed with the identical `ValueError`, was labelled `not_realisable`, printed a phantom `requires: scipy` — and the `[realize]` line reported **`0 realization judge error(s)`**. The new tier never rendered because nothing ever reached it.

**Console evidence pins the call site precisely.** Every angle that gets past the workers logs two lines; this one logs only the first:

```
[acronym-load-drift]              Architecture: 4 functions
[acronym-load-drift]              Compile attempt 1/3...
[stakeholder-role-training-overlap] Architecture: 2 functions
                                  (no compile attempt, ever)
```

So the exception is raised **between the orchestrator returning and the compile loop starting** — the worker fan-out at `_run_one_design`:

```python
worker_results = await asyncio.gather(
    *[_call_worker(t, i, report, input_metadata, config) for i, t in enumerate(tasks, 1)]
)
```

Two compounding causes. `_call_worker` uses `llm_call`'s **8192 default** (only `compile_script` and, now, `validate_realization` pass an explicit budget). And that `gather` has **no `return_exceptions=True`**, so one worker exhausting its thinking budget takes down its siblings and the whole design with it.

**The diagnosis in the entry above was too narrow — correct it here rather than editing history.** This is not a `validate_realization` problem. **Four** `llm_call` sites sit in the realization chain — orchestrator (`_run_one_design`), workers (`_call_worker`), compiler (`compile_script`), validator (`validate_realization`) — and any of them can raise this. Guarding the last one only moves the failure upstream.

Note also that **rev. 20's claim that Run 21 wrote off a paid-for Docker run was probably wrong.** It was inferred from the error text without evidence about which call raised it. Run 22 shows this error class fires *before* any Docker run, so Run 21's two failures most likely never reached the sandbox either. The other two problems in that entry — wrong tier, discarded script — stand unchanged.

**Widened fix:**
1. **`return_exceptions=True` on the worker gather**, with a partial-result path — one failed worker should not destroy the other N−1 that succeeded, and a design missing one function is still worth handing to the compiler with the gap noted in its error feedback.
2. **Wrap the whole body of `_run_one_design`**, not just the validator call, so *any* exception returns a status carrying whatever exists at that point rather than unwinding. `realization_error` is still the right label — the qualifier "executed (Docker-verified PASS)" in its docstring should be relaxed, since the honest meaning is "the pipeline broke on this angle for infrastructure reasons, not angle-quality or provisioning reasons", which is true at every stage.
3. **Give the workers an explicit `max_tokens`.** They are not as heavy as the validator, but the 8192 default is now demonstrably too low for a thinking model on this workload. Consider raising `llm_call`'s default instead and letting light callers stay light — three of the four heavy callers now override it, which suggests the default is simply wrong.
4. **Log each realisation stage**, not just architecture and compile attempts. The only reason this was diagnosable at all is that "Architecture:" and "Compile attempt" happen to bracket the workers. This is the same audit gap Live Issue 12 fixed for the compile loop, one stage further out.

**WIDENED FIX LANDED, unconfirmed on a live run.** All four items, all in `pipeline.py`:

1. **`llm_call`'s default `max_tokens` raised globally, 8192 → 16384** — took the "consider raising the default" option from item 3 above rather than patching orchestrator and workers individually, on the reasoning the widened diagnosis itself supplies: three of the four `llm_call` sites in the realisation chain had already needed an explicit override, which means the default was simply wrong, not that each caller was unusually heavy. `compile_script` and `validate_realization` keep their explicit `max_tokens=16384` (now numerically redundant, kept for self-documentation of "this is the heavy one") - orchestrator and worker calls, previously silently exposed on the old default, are now covered without call-site-by-call-site patching, including any future `llm_call` site that forgets to think about its budget.
2. **Worker gather now `return_exceptions=True`**, with a per-function placeholder on failure (`# WORKER CALL FAILED: {exc!r}` plus an instruction not to assume the function exists) instead of one failed worker taking down the other N−1 that succeeded. `functions_text` (what the compiler actually sees) still enumerates every task, so the compiler gets an honest, visible gap instead of a design that silently lost a function with no explanation. Verified standalone (synthetic `asyncio.gather` with two succeeding workers and one raising the exact Run 22 `ValueError`): all three functions survive into the joined output, the failed one carries the placeholder text and not the other two functions' code, and nothing is silently dropped.
3. **`_run_one_design`'s entire body wrapped in one `try`/`except`**, replacing the narrower validator-only guard from the Run 21 fix. A `stage` variable (`"orchestrator"` → `"workers"` → `"compile"` → `"validate"`) is set immediately before each stage's call and read in the `except` clause, so the log line and the returned `realization_feedback` both say which call broke - directly closing the diagnostic gap that made Run 22 need console-log archaeology (bracketing "Architecture:"/"Compile attempt" lines) to pin down the call site at all. `compiled_script`/`exec_output`/`artifacts` are initialised before the `try` so the `except` clause can always return whatever real output exists - empty for an orchestrator/worker-stage failure, real for a compile/validate-stage one. The docstring's `realization_error` bullet is reworded accordingly - it no longer claims "executed (Docker-verified PASS)" unconditionally.
4. **Per-stage logging** falls out of item 3 directly (the `stage` variable's transitions plus the existing `Architecture:`/`Workers:`/`Execution:`/`Realization:` log lines now bracket every stage, not just two of them) plus one new line: `Workers: N/M succeeded` prints whenever at least one worker fails, naming the failed function(s).

Also updated: `generate_and_optimize`'s own `realize_results = await asyncio.gather(*realize_calls, return_exceptions=True)` handler now carries a comment explaining it should be unreachable in normal operation - `_run_one_design` no longer raises past its own boundary, so this stays purely as defense-in-depth, and if its `WARNING: realization failed` line ever prints, that is itself a bug to chase (the exact `not_realisable`-mislabelling failure mode this whole issue exists to prevent), not a routine per-angle failure message.

**Not verified end-to-end.** The worker-resilience logic (item 2) was checked standalone against synthetic data; the `stage`-tracking wrap (item 3) and the raised default (item 1) were checked by code review and a full `py_compile` pass, not by exercising a real failure through the live pipeline - doing that requires either a live `max_tokens` failure (now less likely at 16384, which is the point) or deliberately injecting one, which wasn't done here. **Needs a live run to confirm:** ideally zero `realization_error` results (the raised default alone was sufficient); failing that, that any failure that does occur reports the correct `stage`, keeps the angle out of the provisioning tier, and - if it's a worker failure specifically - that the compiler received the placeholder text and the surviving functions rather than losing the whole design.

**22. A script can silently drop a metric and still be `realised` (Run 22).** `abstract-writing-style-drift` was marked `realised` at `delivered_score=0.71`, and the judge's own `pattern_reasoning` says passive-voice fraction was *"entirely unmeasured (NA for all years due to a missing NLTK resource, silently caught)"* — one of the five metrics the angle proposed, gone, with the script exiting 0.

Two distinct problems, both narrow:

1. **The resource is almost certainly `averaged_perceptron_tagger_eng`.** The Dockerfile bakes `averaged_perceptron_tagger` (added by Issue 15); modern nltk resolves POS tagging to the `_eng` suffixed resource instead. Same shape as Issues 14 and 15, and the same cheap fix — add it to the bake list and rebuild. **§10's "the baked corpus list must track what libraries actually reach for" is now three-for-three**; treat the list as a standing maintenance item rather than something that gets finished.
2. **Issue 11's fail-fast rule has a gap.** `WORKER_PROMPT_SUFFIX`/`COMPILER_PROMPT_SUFFIX` forbid the "print a not-found message and exit cleanly" pattern for *missing data*, and `validate_execution` backstops a whole-script no-op. Neither covers a script that computes four of five metrics and silently writes NA for the fifth. The angle still landed in the top tier.

**Do not fix this by adding a gate.** Per §7's scope check, the judge caught it and reported it plainly, which is the machinery working — the human reading the gallery can see exactly what happened. The proportionate fix is to extend the no-silent-failure instruction in the worker/compiler suffixes to cover per-metric degradation (compute it or say loudly that you cannot, do not emit NA and continue), and to bake the missing resource. Whether a partially-delivered angle should still rank in the top tier is a *presentation* question for after D-consolidate, not a status-vocabulary question.

**FIXED, unconfirmed on a live run (needs a Dockerfile rebuild - user is rebuilding manually).** Both parts landed:
1. `Dockerfile`'s `cbias-analysis` target now also downloads `averaged_perceptron_tagger_eng` alongside the existing `averaged_perceptron_tagger`, same `download_dir=$NLTK_DATA` / `chmod -R a+rX` treatment as the other five corpora. Same moving-target pattern as Issues 14/15 - modern nltk resolves POS tagging to the `_eng`-suffixed resource name, and baking only the bare name left it silently unreachable.
2. `WORKER_PROMPT_SUFFIX` and `COMPILER_PROMPT_SUFFIX` (prompts.py) each gained a new numbered rule extending the existing whole-script fail-fast instruction (Live Issue 11) to per-metric degradation: a function/script computing several values must not catch a failure on just one of them and silently continue with NA/None/0 - it must either raise or print an explicit, unmissable warning naming the metric and the reason. Worded as an extension of the existing rule, not a new gate, per the "do not fix this by adding a gate" framing above - the instruction is about visibility, not about refusing to run.

Needs a live run with a readability/style-drift-shaped angle to confirm: no NLTK resource-not-found warnings for POS-tagging, and - if any future metric genuinely can't be computed - that the script says so loudly in the console rather than reporting a silent NA.

**23. `llm_call`'s retry ladder can now build requests the SDK refuses to send (Run 23).** `closed-ended-covariance-themes` died at the compile stage on:

```
ValueError('Streaming is required for operations that may take longer than
  10 minutes. See .../anthropic-sdk-python#long-requests')
```

**This is not the `max_tokens` failure again — it is the fix for it hitting a ceiling.** `compile_script` has passed `max_tokens=16384` explicitly since well before rev. 23 and it has worked for 22 runs, so the refused request is not that one: it is the **retry at `max_tokens * 2` = 32768**. The Anthropic SDK refuses, client-side, any non-streaming request whose budget implies a possible >10-minute response, and 32768 crosses that line.

Two consequences:
- Raising `llm_call`'s default from 8192 to 16384 (rev. 23, Issue 21) doubled every call site's *retry* to 32768, so this failure mode is now reachable from all four realisation stages rather than only the two that already overrode the default.
- **Raising budgets is no longer available as a remedy.** The ladder now tops out above what the SDK will send without streaming, so the next occurrence of a genuine thinking-budget exhaustion has nowhere to go.

**Fix: stream.** `client.messages.stream()` is what the SDK's own error points to and it removes the ceiling rather than moving it. Accumulate text blocks from the stream and keep `llm_call`'s return contract identical, so no caller changes. As a stopgap if streaming is more work than it looks, bound the ladder — `min(max_tokens * 2, SDK_NON_STREAMING_CEILING)` — which converts a hard failure into the old, honest "no text content" error.

**Worth naming the pattern.** Issue 21 has now been fixed three times, each time at the site where it last appeared: the validator (rev. 21), then every stage (rev. 23), now the transport itself. Streaming addresses the class rather than the instance, which is the first fix in this sequence that does.

**Verify:** a run in which some call exhausts 16384 should recover on retry rather than raising, and no `realization_error` should carry a streaming message.

**FIXED, confirmed via a direct live smoke test (rev. 25).** `llm_call`'s inner request (`pipeline.py`) now opens `client.messages.stream(model=..., max_tokens=tokens, system=..., messages=...)` as an async context manager and awaits `stream.get_final_message()` in place of `await client.messages.create(...)`. `get_final_message()` returns the same `Message`-shaped object `create()` always did, so the surrounding retry-at-double loop, the `text`/`stop_reason` checks, and every caller of `llm_call` are untouched — this is a transport-only change, exactly as scoped ("keep `llm_call`'s return contract identical, so no caller changes").

Verified directly against the live Anthropic API (not just `py_compile`): a call to `claude-opus-4-8` with `max_tokens=40000` — chosen so a retry-at-double would reach 80000, well clear of the 32768 that failed in Run 23 — completed normally with no client-side error, confirming the SDK's non-streaming guard no longer applies to this call site. **Not yet confirmed on a full pipeline run**: the smoke test proves the mechanism, not that Issue 23 stops recurring in situ, since reproducing the exact Run 23 failure organically wasn't attempted (that would mean deliberately starving a real orchestrator/worker/compiler/validator call, which the raised default now makes rare by design). Needs a live run to confirm no `('Streaming is required...')` error recurs anywhere in the realisation chain.

**24. Dedup merged two angles serving different guiding questions, removing coverage (Run 23).** `8 → 5 after dedup`, three across-iteration merges:

```
[stakeholder-role-evaluative-separation] -> [closed-ended-covariance-themes]     (0.242)
[registration-group-size-structure]      -> [registration-lead-time-and-discount] (0.225)
[satisfaction-driver-shifts]             -> [closed-ended-covariance-themes]     (0.309)
```

The second is defensible (both read order-level attendee data) and the third is arguable. **The first is a false positive with a real cost.** `stakeholder-role-evaluative-separation` serves **guiding question 5** — does role identity still predict how attendees evaluate the event — while `closed-ended-covariance-themes` serves **question 3** — do feedback items cluster into themes. They share Likert-item vocabulary and almost nothing else, which is precisely the lexical-vs-semantic failure §3's "Known ceiling" predicts. The merge left **question 5 with no representative in the run at all**, and question 5 is the one §8 has the most open evidence on.

**Do not fix this by tuning the threshold.** §3's ceiling note already explains why 0.22 is not obviously wrong: these merged at 0.225–0.309, inside the near-duplicate band, and lowering it would let genuine duplicates through. The problem is not the number, it is that the measure has no idea what an angle is *for*.

**Fix: a structural guard, not a tuned constant.** Never merge two angles whose `question_or_stakeholder_served` maps to different guiding questions. The field is already on every angle and already parsed by `_parse_guiding_questions`; matching an angle to its question is a substring/index check, not a new model call. Angles serving the same question remain eligible for merging exactly as now.

This is cheap, domain-independent (any report with more than one guiding question benefits), and preserves what dedup is actually good at — collapsing two near-identical attacks on the *same* question — while removing its ability to silently narrow the run's coverage.

**REFRAMED (rev. 26, §13): delete or demonstrate — do not simply add the guard.** Rev. 24 concluded "keep it; add the guard." Read against the post's rule that complexity is added only where it demonstrably improves outcomes, that was too generous. Dedup's *original* justification was saving downstream judging cost; D6-fix removed that saving by moving judging before it, and no replacement justification was ever established. A component whose stated reason no longer applies, and which has since been shown to *remove* an outcome, does not get repaired by default.

Two honest options — a decision, not a recommendation:
- **(a) Delete it.** ~115 lines and a hand-calibrated constant go. Near-duplicates then appear in a gallery a human skims in a minute and dismisses in a second, and §3's lexical ceiling stops being a problem to solve later.
- **(b) Implement the guard, then measure.** If it is worth having, that is a claim to demonstrate on a full-width run — does the archive cover more guiding questions, and is the gallery better? — not to assume because it fixes the bug.

**RUN 24 KILLS OPTION (b). The guard would not have worked.** Two more false positives, and both are *within* a single guiding question:

```
merged [abstract-readability-complexity-trend] -> [semantic-convergence-trend] (0.234)   both Q2
merged [feedback-latent-theme-structure]       -> [open-comment-triggers]      (0.285)   both Q3
```

Neither is a near-duplicate by any reading. Readability metrics (sentence length, Flesch) and sentence-transformer embeddings are different kinds of measurement that happen to share the words *abstract*, *language*, *year* and *trend*. Likert-covariance clustering and commenter-vs-non-commenter effect sizes are different analyses of the same survey — and the second angle's own `why_non_obvious` field says so explicitly: *"It is also distinct from the previous commenter-vs-non-commenter trigger analysis because it uses the full pattern of structured responses rather than comment presence."* **The ideation model flagged the distinction in writing and dedup merged them anyway.**

That is now **three false positives across Runs 23–24, all in the 0.23–0.29 band** (0.234, 0.242, 0.285), and the guiding-question guard catches exactly one of them. The proposal is dead.

**Recommendation, no longer a toss-up: delete dedup (option (a)).** Its original justification is gone (D6-fix moved judging first), no replacement was ever established, it has removed useful coverage in two consecutive runs, and the one repair on offer does not work. ~115 lines and a hand-calibrated constant go with it; near-duplicates appear in a gallery a human skims in a minute and dismisses in a second; §3's lexical ceiling stops being a problem to solve later.

**If you would rather not delete it outright**, the honest interim is to *keep the code but stop acting on it* — log what it would have merged and merge nothing — which preserves the measurement (how often would it fire, and would the merges have been right?) at zero cost to coverage. That is a better bet than either deleting blind or repairing on faith.

**What is no longer on the table is "add the guard because Run 23 broke."** Repairing a component that has not earned its place is the pattern the post warns against. This also answers D-consolidate item 7: dedup does not earn its lines.

**IMPLEMENTED (rev. 29) — option (b), the interim, not option (a).** `_dedup_angles` is reverted to its pre-guard form (the guiding-question guard is removed entirely, not merely unused - it answers a question, "same guiding question or not", that Run 24 showed is the wrong question for two of three false positives). `generate_and_optimize` still calls it every run, over the full judged archive, so the "would this fire, and would it be right" measurement keeps running - but no longer treats the result as authoritative: `all_angles` is built from the full archive, not `kept_records`, so nothing a merge would have hidden is actually hidden. The console line is reworded to say so plainly (`MEASUREMENT ONLY, not acted on`, `would merge` / `would keep`). Verified offline (mocked) only.

**RUN 25 — first live data point, and the interim is already earning its keep.** No regression: 8 angles generated, 8 ranked, 8 in the gallery. The `[dedup]` line reported two would-merges:

```
would merge [transactional-behaviour-segment-shifts] -> [registration-lead-time-by-ticket-category]
            (similarity=0.225, across_iteration) would keep [registration-lead-time-by-ticket-category]
would merge [feedback-item-stakeholder-divergence]   -> [satisfaction-driver-shift]
            (similarity=0.280, across_iteration) would keep [satisfaction-driver-shift]
```

**The decisive question — would suppressing these have cost a realisation? — answers "no, but pair 1 missed by 0.02".**

| Pair | Would-keep | Would-merge-away | Outcome |
|---|---|---|---|
| 1 | `registration-lead-time-by-ticket-category` — **realised**, insight 0.72 | `transactional-behaviour-segment-shifts` — also-generated, insight **0.70** | 5th of 6 eligible; **one place outside top-k** |
| 2 | `satisfaction-driver-shift` — **not_realisable** | `feedback-item-stakeholder-divergence` — **unsupportable** | neither realised; merge would have cost nothing |

So dedup would not have hidden anything from the gallery's top tier this run. But pair 1 is a near miss on a 0.02 margin, which is well inside judge noise — on a different day that angle ranks 4th, both members of a would-merge pair get realised, and dedup's protective value becomes visible. **One run is not enough. Keep the measurement running.**

**Both would-merges are also false positives, and both are within-question again.** `transactional-behaviour-segment-shifts` clusters order-level features to *discover* segments; `registration-lead-time-by-ticket-category` computes lead-time medians *within pre-existing ticket labels*. The contrarian angle's whole premise is rejecting ticket type as ground truth — the two are closer to opposites than duplicates. Pair 2 is nearer but still distinct (who differs, versus what predicts satisfaction).

**Running total: 5 false positives across Runs 23–25** (0.225, 0.242, 0.280, 0.285, 0.309), of which the reverted guiding-question guard would have caught exactly one. Every one sits in the 0.22–0.31 band, immediately above the threshold — consistent with §3's "Known ceiling" rather than with a mis-set constant.

**RUN 26 — second data point, and it removes the last cheap fix.** One would-merge: `feedback-respondent-archetype-trajectories` → `feedback-covariance-theme-network` at **0.360, the highest similarity anywhere in the log**. Both were judged unsupportable, so nothing was lost. But it is another false positive — the first clusters *survey items* by co-variation, the second clusters *respondents* by response profile, and the second angle's own `why_non_obvious` states the distinction explicitly.

**Cumulative: 6 false positives across Runs 23–26, and the highest-scoring merge in the log is one of them.** That rules out raising the threshold as well as the guiding-question guard. Running cost of not deduping: 3 would-merge pairs across Runs 25–26, **zero realisation slots lost**, one near-miss at 0.02.

**What would settle it, in order of what the next runs should show:**
- **Delete** if two or three more runs pass with no would-merge pair reaching the top tier together.
- **Keep and fix** the first time a pair does — at which point the fix is a semantic signature, not a threshold and not a question guard, since all five false positives share topic vocabulary while differing in method.

**25. RESOLVED — miscategorised as a data defect; actually a `DOMAIN_NOTES` gap (Runs 24, 25).** Not a pipeline bug, and — despite the original framing below — not a data-quality finding either.

- **Run 24**: `open-comment-triggers` realised, and its judge noted `overall_satisfaction` is *entirely NaN across all four years* — nine other items carried the finding.
- **Run 25**: `satisfaction-driver-shift` exhausted all three compile attempts, each failing on the same wall:

```
Attempt 1: ValueError('No satisfaction-driver correlations could be computed from the feedback data')
Attempt 2: ValueError('Year 2022: overall satisfaction column not found or too few mappable responses')
Attempt 3: ValueError('Year 2022: overall satisfaction column has too few mappable responses')
```

**This looked like a genuine data defect, twice independently, and was recorded as one. Direct inspection of `inputs/cbias_data_anon/Feedback/*.csv` (not just the generated scripts' say-so) shows it is not.**

`"What was your overall level of satisfaction with the symposium?"` is fully populated in every year — 60/60 (2022), 52/52 (2023), 53/53 (2024), 37/37 (2025), real values (a numeric scale; distinct values 1/3/4/5/6/7 seen across the four years). What is empty is the two auto-generated `"Points - ..."`/`"Feedback - ..."` companion columns Microsoft Forms adds to *every* question, confirmed by checking all 23 `"Points -"` columns in the 2022 file — all 0/60 populated, not specific to satisfaction. `DOMAIN_NOTES` already tells scripts to ignore those companion columns and read the plain-named one, and already tells them Likert answers are free text needing an ordinal mapping — true for every other question in the survey (e.g. "The ticket prices were appropriate" answers are "Agree"/"Strongly Agree"/"Not Applicable"). But the satisfaction question is the *one* exception: it is already numeric, not Likert text. A script correctly following the (right, for every other question) instruction to map Likert text to an ordinal scale finds no text keys matching numeric strings like `"5"`/`"6"`/`"7"`, and silently produces all-NaN — indistinguishable, from the script's own error message, from the column genuinely being empty. Two independent generation attempts hit exactly this, in two different runs, which is why it read as a data defect rather than a code bug.

**First fix (superseded below) — `DOMAIN_NOTES` only.** Named the satisfaction question as an explicit exception to the general Likert-mapping instruction. Correct but flaky in two ways, both raised on review: a prompt note only works if the model reads and applies it every time, and naming one exception is brittle - it breaks again the next time a numeric-scale question appears. Superseded, not kept alongside.

**Fix landed, two parts, both stronger than the first attempt.**
1. **Structural: strip the ambiguity at the source, in `anonymize_cbias_data.py`.** The always-empty `"Points - <question>"`/`"Feedback - <question>"` companion columns (confirmed empty in every one, every year - 46/44/46/46 columns across 2022-2025, 0 non-empty) are now dropped during anonymisation itself, via `_drop_empty_companion_columns` - verify-then-drop, not blind-drop: it warns loudly and keeps a companion column rather than dropping it if a future year's export ever actually populates one. This removes the three-near-identical-column-names ambiguity from the data generated code ever sees, rather than hoping every generated script reads and obeys an instruction not to touch two of them. ~~**Needs `anonymize_cbias_data.py` re-run** against the local raw `inputs/cbias_data/` to regenerate `inputs/cbias_data_anon/Feedback/*.csv`~~ — **DONE (`e31a8c3`), and verified against the committed data at `2ed4463`:**

| File | Columns | `Points -`/`Feedback -` remaining | Satisfaction column |
|---|---:|---:|---|
| 2022 | 22 | **0** | 60/60 populated, `int64`, values {1,5,6,7} |
| 2023 | 21 | **0** | 52/52 populated, `int64`, values {3,5,6,7} |
| 2024 | 21 | **0** | 53/53 populated, `int64`, values {4,5,6,7} |
| 2025 | 21 | **0** | 37/37 populated, `int64`, values {3,5,6,7} |

Companion columns are gone from every file, and the satisfaction column is fully populated in all four years as an integer scale (apparently 1–7). This is the direct check the entry's own lesson asks for — read the CSVs, not the scripts' error messages. **No rebuild is outstanding; the next run can proceed.**
2. **Behavioural: teach the check, don't list the exception.** `DOMAIN_NOTES` no longer names the satisfaction question specifically - it states most Feedback questions are Likert text needing an ordinal mapping *but not all of them*, gives satisfaction as one example, and instructs inspecting a column's actual unique values before assuming the mapping applies. Generalises to any future numeric-scale question without needing another edit, which a hardcoded exception never would.

Needs a live run with a satisfaction-outcome angle, after the anonymisation re-run, to confirm no recurrence.

**The general lesson, worth keeping alongside Issue 17's:** an all-NaN or `not_realisable` result from a generated script is not itself evidence the underlying data is bad — it is evidence the generated code's assumptions about the data were wrong, and the two look identical from the console. Issue 17 established this for path/glob assumptions; this is the same failure mode for column *content-type* assumptions. Check the raw data before writing a data-gaps note, not just before writing a fix.

**How close this came to reaching the report, and why that matters.** Rev. 30 recorded this as a confirmed data defect and recommended adding *"overall satisfaction is unusable across all four years"* to the report's data-gaps section — a section that goes to the organising committee. It would have been a fabricated gap in a real deliverable, plus a `DOMAIN_NOTES` constraint telling ideation to stop proposing a perfectly good outcome variable. The inference was drawn from two scripts' error messages without opening a CSV. **The pipeline's outputs are evidence about the pipeline; only the data is evidence about the data.**

**And the sharper point, which belongs to D-simplify item 1: one wrong line in `DOMAIN_NOTES` produced effectively identical failures in two independently generated scripts, across two runs.** §8 records that judge prompts are the product. `DOMAIN_NOTES` is equally load-bearing — it is the pipeline's description of the world to every worker and compiler call — and it has never had the same scrutiny. It is not a comment; it is an interface.

**26. FIXED — PROVISIONALLY CONFIRMED (Runs 28, 29, 30). `llm_call` returned truncated responses as if they were complete (Runs 26, 27).**

**Run 30: the first-attempt-compile streak breaks, and it does NOT count against this issue.** Two compiles needed a retry, but both failed on a matplotlib deprecation with a complete traceback and complete syntax — a genuine runtime error, not a mid-token cutoff. **The measurement that bears on Issue 26 is truncation-shaped syntax errors, and that count is still zero across Runs 28–30.** The two are separate measurements and must not be conflated: a clean-compile streak is a proxy that also moves with unrelated causes (Live Issue 30), while the truncation count is the direct evidence. Recording this because reading the streak as the metric would have wrongly reopened a fixed issue.


**Run 29 extends the evidence to a second consecutive clean run: 8 straight first-attempt compiles across Runs 28–29, no `Compile attempt 2/3` and no syntax error of any kind.** One more run of this and the entry can be closed. The double-truncation `ValueError` has still never fired, so that path stays untested — do not treat closure of this issue as covering it.


**Run 28 evidence.** Every compile in the run succeeded on **attempt 1/3**: no `Compile attempt 2/3` appears anywhere in the log, and there were no syntax errors of any kind.

| Run | Truncation-shaped `SyntaxError`s | Compiles needing a retry |
|---|---|---|
| 26 | 1 | 1 |
| 27 | 2 | 2 |
| 28 | **0** | **0** |

Circumstantial rather than conclusive — a clean run can happen — but it is the first run since the pattern appeared in which *no* compile needed a second attempt, which is what a working `reject_truncated` should produce: the retry now happens inside `llm_call`, invisibly, instead of costing a compile attempt. **Leave open for two more runs**; close it if the pattern holds, and note that the new "Response truncated at max_tokens on both attempts" `ValueError` has still never been seen, so the double-truncation path remains untested.

*Original entry follows.*

**26 (original). `llm_call` returns truncated responses as if they were complete (Runs 26, 27).** The retry-at-double added for Issue 21 fires **only when the response contains no usable text**:

```python
text = "".join(block.text for block in response.content if block.type == "text")
if text.strip():
    return text                    # returns even when stop_reason == "max_tokens"

if response.stop_reason != "max_tokens":
    break                          # only reached when there is NO text at all
```

That is correct for the failure Issue 21 was written for — thinking consuming the whole budget, leaving a `thinking` block and nothing else. It is wrong for the other `max_tokens` case: a response that produces text and is then **cut off mid-generation**. The truncated text passes the `text.strip()` check, is returned, and reaches the compiler as though it were a finished script.

**The evidence is the shape of the errors, which is truncation-shaped rather than mistake-shaped:**

| Run | Angle | Attempt | Error |
|---|---|---|---|
| 26 | `program-abstract-attendee-sector-alignment` | 1 | `raise FileNotFoundError(` — `SyntaxError: '(' was never closed` |
| 27 | `feedback-aspect-rank-trend` | 1 | `fig, ax = plt.subplots(fig` — `SyntaxError: '(' was never closed` |
| 27 | `primary-role-vs-training-hybridity` | 2 | `"""Map a raw text fragment` — unterminated triple-quoted string |

All three stop **mid-token**. A model making a genuine mistake does not usually emit `plt.subplots(fig` and stop; a stream cut at its budget does exactly that. Three occurrences in two runs, each costing one of three compile attempts.

Corroborating: the delivered `primary-role-vs-training-hybridity.py` carries `# Map a raw text fragment to a canonical domain.` as a **comment** where the truncated attempt had a docstring — the repair worked around the symptom, which is what you would expect when the compiler is never told the response was cut off.

**Fix.** Check `stop_reason` before returning, not only when the text is empty:

```python
if text.strip() and response.stop_reason != "max_tokens":
    return text
```

A truncated script is never usable, so returning it is strictly worse than retrying at double. Two points of care:
- **Do not apply this blindly to every caller.** A judge or criteria response that hits `max_tokens` may still be usable if the parser recovers the fields it needs; a *script* never is. Either gate on the caller, or accept the extra retry cost globally and measure it — `compile_script` is the one that certainly needs it.
- **If both attempts truncate**, the code falls through to the "No text content" `ValueError`, whose message would then be misleading. Give truncation its own message, so a future §15-class diagnosis does not start from the wrong hypothesis.

**FIXED (rev. 38), gated on the caller rather than applied globally.** `llm_call` gained a `reject_truncated` parameter (default `False`, preserving the exact old behaviour for every existing call site) — when `True`, a `stop_reason == "max_tokens"` response is treated the same as an empty one and retried at double, rather than returned. `compile_script`'s `llm_call` (`realization.py`) is the only call site passing `reject_truncated=True`, per the fix's own "gate on the caller" option — judge/criteria/worker calls are unaffected, so this costs nothing beyond the compiler's own retry ladder. A response still truncated on both attempts now raises a truncation-specific `ValueError` instead of falling through to the generic "No text content" message, so a future diagnosis starting from that error won't chase the wrong hypothesis (thinking-budget exhaustion) the way this one almost did. Verified offline via a mocked test exercising all four paths (truncated-but-accepted under the old default, truncated-then-clean retry, truncated-twice raising the new message, and the pre-existing no-text/non-`max_tokens` path unchanged) — deleted after passing, per this project's convention.

**Verify:** a run in which a compile response truncates should retry rather than emit a mid-token `SyntaxError`, and no `realization_error` should carry thinking-budget wording when the real cause was truncation.

**27 and 28. BOTH FIXED, BOTH STILL UNCONFIRMED — neither exercised by Run 29.** Run 29 had no repeat compile feedback and no `realization_error` at all, so neither Issue 27's branch nor Issue 28's stage-dependent wording ran. **This is a structural problem with confirming either of them: both fixes only execute when something else goes wrong, and the pipeline has now had two consecutive flawless runs.** Neither is blocking; check opportunistically, and accept that a long confirmation lag here is a sign of health rather than neglect.

**27 (earlier note). FIXED, STILL UNCONFIRMED — not exercised by Run 28.** No repeat feedback occurred (every compile passed first time), so neither new branch ran. It needs a run in which a design actually cycles, which by its nature cannot be arranged on demand — leave open and check opportunistically rather than waiting on it.

**27 (original). The compile-cycling abort cannot save an attempt at the current budget (Run 27).** `abstract-register-accessibility` logged:

```
This error already occurred in an earlier attempt - aborting remaining compile attempts
  (the compiler is cycling, not repairing).
[not_realisable] Did not execute after 3 attempt(s) (aborted early - the same error recurred verbatim).
```

It had already used all three: attempt 1 `textstat`, attempt 2 nltk `sent_tokenize`, attempt 3 `textstat` again. The detector compares against **all** earlier attempts, which is right, but with `max_compile_attempts=3` the earliest a two-cycle can be caught is attempt 3 — where there is nothing left to abort. **It only saves work on a one-cycle**, where attempt 2 repeats attempt 1 verbatim.

Not urgent; the abort is still correct, it just did not help here. Two options, the second nearly free:
1. Raise `max_compile_attempts` so the detector has room to pay off. Costs tokens on genuinely-repairing designs — measure before doing it. **Not done** — deliberately left for a separate decision, since it trades tokens for a benefit that is still unmeasured.
2. **Soften the log wording.** "aborted early" and "aborting remaining compile attempts" both claim a saving that did not happen, and per §15's own lesson, a log overstating what occurred is how misdiagnosis starts.

**FIXED (rev. 39), option 2 only.** `_run_one_design`'s repeat-detection branch now computes `remaining = max_compile_attempts - 1 - attempt` before logging: with attempts genuinely left to skip, it logs `aborting the N remaining compile attempt(s)` (unchanged claim, still true); when the repeat lands on the last attempt — the case that actually happened in Run 27 — it logs `it was the last attempt available, so nothing was saved by detecting it` instead, and `aborted_on_repeat` (which drives the `(aborted early - the same error recurred verbatim)` note on the final `not_realisable` feedback) is only set `True` in the real-saving case. No change to when the loop breaks or to `max_compile_attempts` itself — this is wording only, exactly as scoped. Verified offline with a mocked `_run_one_design` run for both cases (repeat with 2 attempts remaining; repeat only on the final attempt of 3) — deleted after passing.

**28. The `realization_error` tier asserts a cause it cannot know (Run 28).** `output.py` prints this above the fifth tier, unconditionally:

> _The script compiled, ran in the sandbox, and produced real output; only the final judging call failed. Not a provisioning gap - judge these yourself from the script/image(s) below._

That is true only when the failure happened at the **validate** stage. Run 28's `speaker-attendee-sector-alignment` failed at `stage='compile'`, so no script was written, nothing ran in the sandbox, and the entry carries **no script or image links** — the reader is told to judge from artifacts that do not exist. The parenthetical inside the entry records the correct stage, so the entry contradicts itself.

**This is Issue 21's original defect one level up.** Issue 21 was about a tier asserting the wrong *category* of failure; this is a tier asserting the wrong *stage* of it. The plan has now made the same mistake three times (Issue 21's `not_realisable` mislabelling, Issue 27's "aborted early" log, this) — **wording that describes the common case and is silently wrong in the others.**

**Why it matters more than one entry suggests.** Run 28 was lucky: the balance ran out on the last compile, so one angle was affected. Had it run out earlier, all four realisations would have failed identically and the gallery would have carried four entries each confidently claiming a compiled, executed script. The console makes an account failure obvious; the gallery is what gets read afterwards.

**Fix:** branch the wording on `stage`. For `stage='validate'`, the current text is correct. For earlier stages, say what is true — the pipeline failed before a script was produced — and suppress the "judge these yourself from the script/image(s) below" instruction when there are no artifacts to judge.

**FIXED (rev. 41).** `stage` is no longer trapped inside the free-text `realization_feedback` string — `_run_one_design`'s exception handler (`realization.py`) now returns it as a structured `error_stage` field too, threaded onto the angle dict by `generate_and_optimize` (`pipeline.py`). `output.py` branches on it at both sites that were asserting the unconditional claim:
- **Per-entry Note (`_gallery_entry`):** the original "the script and image(s) below are real; judge them yourself" wording is now used only when `error_stage == "validate"`. Two other cases, both new: if an earlier stage broke but a script still exists on disk (the edge case the original fix note didn't consider — a *later* compile attempt can raise after an *earlier* one already produced text, leaving a real but never-executed file behind), the Note says explicitly it's "from an earlier, unverified attempt, not a confirmed run"; if nothing survived at all, it says there is no script or output to show, rather than inviting the reader to look "below" at nothing.
- **Tier intro (`_write_gallery`):** dropped the blanket per-tier claim entirely, since a single run's `realization_error` tier can hold entries at different stages simultaneously (a mixed tier makes any one blanket sentence wrong for at least one entry) — it now says only that this is an infrastructure failure, not a provisioning gap, and points to each entry's own Note for specifics.

Verified offline (mocked `_write_gallery` call, three synthetic angles covering `error_stage="validate"` with real artifacts, `error_stage="compile"` with nothing produced, and `error_stage="compile"` with a stale unverified script) — all three renders came out as intended, including the tier intro no longer containing the old "script compiled, ran in the sandbox" claim; deleted after passing. **Needs a live run** to confirm against a real failure, ideally reproducing Run 28's exact `speaker-attendee-sector-alignment` case (compile-stage break, nothing produced) to see the "no script or output to show" wording fire for real rather than only under a mock.

**29. No preflight check that every configured model is reachable.** Run 28's `APIStatusError("Error code: 402 - Insufficient Balance")` was an account state, not a pipeline fault, and the pipeline handled it correctly. But it exposes that nothing verifies the configured models are usable before ~110 calls are committed.

**Be honest about the scope: a preflight would NOT have caught Run 28.** DeepSeek worked for ideation and for three of four compiles, then ran out mid-run. Credit exhaustion partway through is out of scope for any startup check, and as noted when this was raised, it is obvious from the console anyway.

**What it does catch is a bad key, a stale model string, or an empty account — and the value depends entirely on tier depth**, because §5 puts different models at different points in the pipeline:

| Broken model | Fails after | Wasted before failure |
|---|---|---|
| criteria / `angle_model` | ~1 call | trivial |
| `judge_model` | ideation complete | ~9 calls |
| `orchestrator` / `worker` / `compiler` | ideation **and all judging** complete | ~25 calls, ~16 of them Opus |

The deepseek tier (worker and compiler on `cbias`) is the deepest, so it is exactly where a preflight repays itself. Three distinct model strings after deduplication, one trivial call each, against ~110 for a full run.

**Two implementation traps, both worth stating because each would make the check worse than nothing:**
1. **Do not route it through `llm_call` with a tiny `max_tokens`.** A minimal call to an adaptive-thinking model returns a thinking block and no text — precisely the Issue 21 failure — so the preflight would raise `ValueError` and report every model as broken. It must test the **transport**, not the content: catch `APIStatusError` and treat any successful HTTP response as a pass regardless of what came back.
2. **Distinguish the status codes in the message**, because they need different actions: 401/403 is a credential problem, 402 a balance problem, 404 usually a stale model string — and §5's tiering means model names here change more often than in most projects. A generic "model unavailable" sends someone to the wrong fix, which is the §15 F-class error in miniature.

Low priority; a natural companion to D8's economy instrumentation, since both are about knowing what a run costs before paying for it.

**30. Library versions are neither pinned nor described, and the same API-drift failure keeps recurring (Runs 22, 30).** Two of four compiles in Run 30 failed attempt 1 on the identical error:

```
ax.boxplot(box_data, labels=[...])    -> matplotlib deprecation
plt.boxplot(dist_data, labels=...)    -> matplotlib deprecation
```

matplotlib renamed `labels` to `tick_labels` in 3.9. Both recovered on attempt 2, so the cost is two wasted compile attempts rather than a lost angle — but it is repeated, predictable, and cheap to prevent. Run 22's boxplot deprecation was the same thing.

**This is the third instance of one failure shape, and naming that is the point of the entry.** §15's A2 was the data's *value* vocabulary, A5 the *response* vocabulary, and this is the library's *API* vocabulary — in every case the model writes against an assumed vocabulary that the description it was given does not pin down. §15.7's rule applies unchanged: **fix the description, not the model.**

Two contributing gaps:
- **`AVAILABLE_LIBRARIES` states no versions.** It says only "Matplotlib: for plotting and visualization". The compiler has no way to know which API generation it is targeting.
- **The Dockerfile pins nothing**, so the installed versions float with every rebuild — meaning even a correct note would go stale silently, and a rebuild can change behaviour without any commit recording it.

**Fix, in order:**
1. **Pin versions in the Dockerfile.** Without this the rest is unenforceable, and §10's "rebuild before the next run" instruction currently means "rebuild and get whatever is current".
2. **State the pinned versions in `AVAILABLE_LIBRARIES`**, one line each.
3. **Name the renames that have actually bitten** — `boxplot(labels=)` → `tick_labels`, and `DataFrame.applymap` → `DataFrame.map` (Live Issue 20, pandas 3.0). Do not attempt a general list of every deprecation; the value is in the two or three this project has actually hit, exactly as `DOMAIN_NOTES` enumerates only the response scales that actually occur.

**Verify:** a run in which no compile fails on a deprecation warning it could have known about from the environment description.

**FIXED (rev. 45), all three parts, in order.** `Dockerfile`'s `cbias-analysis` target now pins every package with an exact version (`numpy==2.5.2`, `pandas==3.0.5`, `matplotlib==3.11.1`, `scipy==1.18.0`, `scikit-learn==1.9.0`, `nltk==3.10.3`, `seaborn==0.13.2`, `textstat==0.7.13` — current stable releases at the time of pinning, checked against PyPI directly rather than assumed) instead of floating to whatever `pip install <name>` resolves on the day of a rebuild. `cbias_config.AVAILABLE_LIBRARIES` now states the same versions inline, one per library, and names the two renames that have actually bitten this project: `DataFrame.applymap` removed in pandas 3.0 (Live Issue 20) → use `.map`; `boxplot()`'s `labels=` renamed to `tick_labels=` in matplotlib 3.9 (this issue) → use `tick_labels=`. Deliberately not a general changelog of every deprecation either package has ever had — same "name what's actually been hit" scope as `DOMAIN_NOTES`'s response-scale fix. Both files edited together, per the Dockerfile's own new comment instructing future version bumps to update `AVAILABLE_LIBRARIES` in the same change rather than letting the two drift apart again.

**Needs a Dockerfile rebuild before it takes effect** (`docker build --target cbias-analysis -t cbias-analysis:latest .` — not done here; per this project's standing division of labour the user rebuilds Docker images), **then a live run to confirm**: no compile should fail attempt 1 on either named rename again, and any future rename this project hits should get added to this same two-line list rather than prompting a broader rewrite.

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

**Ordering before D7 (Run 20):**
1. **Issue 8 — `delivered_score`.** The remaining blocker, and only partly: scope-skipping shipped and works, but a script that silently dropped half its years still scored 1.00 (Run 20). If fixing it looks invasive, **omitting `delivered_score` from the gallery is a legitimate alternative** — the substance is in `pattern_reasoning`, and the number has never been the thing worth reading.
2. **Issue 19 — one line in `pattern_reasoning`** noting whether a claim was tested. Optional, cheap, informational only.
3. **§10 library expansion.** Not urgent — two consecutive runs with zero `not_realisable`.
4. **Issue 20 — pandas API drift.** Only if `applymap` recurs.

Issues 17 and 18 are resolved and confirmed. Runs 19 and 20 both achieved 100% realisation, with all four D6 outcome states now exercised.

**D7 itself is now implemented** (see §3) — all four ordering items above were resolved before or alongside it: Issue 8 resolved by omitting `delivered_score` from the gallery outright rather than trusting the scope-only fix as sufficient; Issue 19 bundled directly into the same pass; §10 and Issue 20 remain not-urgent, unchanged. **Needs a live run** to confirm the gallery reads as intended against a real archive covering all four tiers plus the "also generated" section.

**Ordering from here (rev. 26).** The D7 confirmation run is **done** (Run 21) and the functional programme with it. What is left:

1. **Live Issue 21, widened — CONFIRMED WORKING (Run 23). Closed.** Every part fired as designed: `Workers: 5/7 succeeded - failed: main, recode_items` (resilience), `Pipeline failed at stage 'compile'` (stage tracking), the angle landed in the fifth tier with a Note line and no phantom `requires` (correct categorisation), and `[realize] ... 0 not realisable, 1 realization judge error(s)` (correct counting). The infrastructure-failure class is now visible and correctly labelled wherever it occurs.
1a. **Live Issue 22 — FIXED (rev. 23), no recurrence in Run 23.** `averaged_perceptron_tagger_eng` baked; no-silent-failure instruction extended in both prompt suffixes.
1b. **Live Issue 23 — FIXED (rev. 25), confirmed via a direct live smoke test.** `llm_call` now streams (`client.messages.stream(...)` + `get_final_message()`) instead of `client.messages.create(...)`, removing the SDK's non-streaming 10-minute guard rather than moving it. Verified against the live API at `max_tokens=40000`. **Needs a full live run** to confirm no recurrence in situ, since the smoke test exercised the mechanism directly rather than reproducing Run 23's organic failure.
1d. **Live Issue 25 — FIXED (rev. 32), unconfirmed.** Turned out not to be a data-gaps note at all - direct inspection of the raw CSVs showed the "unusable" column is fully populated every year. Landed structurally: always-empty companion columns dropped in `anonymize_cbias_data.py`, plus a generalised (not exception-listing) `DOMAIN_NOTES` instruction. **Needs `anonymize_cbias_data.py` re-run against local raw data**, then a live run to confirm no recurrence. See the Issue 25 entry.
1c. **Live Issue 24 — IMPLEMENTED (rev. 29) as the interim, option (b). First data point collected (Run 25).** `_dedup_angles` still runs every run over the full archive, but `generate_and_optimize` no longer acts on its output - only logs what it would have merged. The guiding-question guard is reverted (Run 24 showed it doesn't answer the right question). **Run 25: no regression, and the first measurement is in — neither would-merge pair cost a realisation, but one missed by 0.02 insight.** Keep the measurement running for two or three more runs before deciding; the decision rule is in the Issue 24 entry.
2. **D-consolidate. Items 1–6 all done (rev. 33–36); item 7 (measure dedup) stays open, tracked via Live Issue 24 above.** Docs rewritten, the default entrypoint fixed (item 3's default half only), `pipeline.py` split into eight modules with `from prompts import *` replaced, run-archaeology trimmed from comments, and the two confirmed-dead items deleted. All verified offline (syntax, import chain, a mocked end-to-end run) but **items 4–6 have not yet run live** — that's the next thing this ordering list is waiting on.
3. **Report edit — guiding question 5.** Cheap, and overdue: retire it as *two* findings, not one (§8). Costs a question slot every iteration until done. Note Run 23's dedup false positive (Issue 24) removed this run's only question-5 angle, so the evidence base here is thinner than the run count suggests.
4. **D8** (saturation stopping, economy instrumentation). Its docs item moved into D-consolidate; rev. 26 adds a precondition — see D-simplify item 3, since D8 item 1 is where this pipeline stops being a pure workflow.
5. **D-simplify** — backlog only, nothing scheduled. The agent-patterns observations, chiefly the XML/ACI question. Explicitly after D-consolidate.

**Both of D-consolidate's measurement items are now answered** — iteration 2 earns its keep (Run 22, item 8) and dedup does not currently earn its lines (Run 23, item 7 / Issue 24). No further log archaeology is needed before acting on either.


**Deliberately NOT on this list, and the reasoning is worth keeping.** Run 23 also showed an angle declaring `requires: sentence-transformers` — a library not in the image — compiling and passing anyway, presumably by substituting something already available, and being marked `realised`. A review pass proposed making the framework detect this. **Rejected, correctly.** `requires` is instrumentation only, by explicit design (see the comment above `ANGLE_FIELDS` and the `<requires>` tag's own wording: *"this is for tracking only - propose the analysis that's genuinely best, don't limit yourself to what's already available"*). Having the realisation judge check method fidelity against `rough_method` would be a **gate**, which §2 and §7 both rule out, and it would bake one report's anti-target list into general pipeline code — exactly the CBIAS-specific-machinery-in-shared-code drift §12 exists to reverse. Whether a substituted method invalidates a finding is domain-dependent and interpretive: it belongs to the human reading the gallery, which is where this pipeline has always put questions of that kind. The script is linked from every gallery entry precisely so that call can be made.
**Scope check before starting D7.** The pipeline's job is to surface *leads worth a second look*, not results that survive rigorous scrutiny — that judgement is the human's at D7 (§11). Rev 16 of this plan briefly drifted the other way (a retraction, and a proposal to gate `realised` on significance testing); both are corrected in Issue 19. When a future issue proposes adding a judge, raising a bar, or suppressing an output, check it against this paragraph first. **On this dataset the achievable frontier is "interesting but caveated" — a stricter bar does not raise quality, it selects for boring.**

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

### D7 — Gallery, not a winner — **CONFIRMED (Run 21), exercised again (Run 22)**

**Prerequisites: Live Issues 9 and 10.** The status split (Issue 7) has shipped, but the gallery needs the *reasoning* behind each status (Issue 9) and a data source that actually contains realisation results (Issue 10). Building on a status label with no explanation would give the reader a verdict they cannot evaluate. Both resolved (Run 14) before this landed.

**Changes — all five shipped, see §3's D7 entry for the implementation detail:**
1. `generate_and_optimize` returns a structured result, not a string. **This rippled into `app.py`**, which used to write `analysis_script_<ts>.py`; it now just reports the paths `generate_and_optimize` wrote.
2. Emit a gallery into `output_dir` (markdown + a sibling images directory, not a single self-contained file — this is a local CLI pipeline writing to disk, not a hosted artifact). Per angle: its plot(s), the finding (`pattern_reasoning`), **the soundness caveat as a visible confidence note**, which question/stakeholder it serves, and its realisation status.
3. **Four presentation tiers, not one ranked list** — shipped as specified:
   - `realised` and `realised_null` **together at the top**, ranked by insight. A clean disconfirmation closes a question and is often more useful than a confirmation; label it as such rather than demoting it. `pattern_reasoning` shown alongside the plot — for a `realised_null` it *is* the finding.
   - `pattern_not_shown` — executed but the output does not show the claim. A quality outcome; shown secondary.
   - `not_realisable` — an *engineering* outcome (missing library). Listed prominently **with their `requires`**, because that list is the signal telling you what to provision next (§10).
   - `unsupportable` angles never reach realisation, but are listed with their `soundness_reasoning` — knowing what the dataset cannot support is itself a finding.
4. Each realized angle's compiled script is now written to disk (`output_dir/scripts/<run_ts>/<angle_id>.py`) and linked from its gallery entry.
5. Built to skim in under a minute — four short tiers plus a one-line-per-angle closing section, not a full data dump (the surfaced_angles file alongside it has that). The human makes the final "is this actually interesting" call.

**`delivered_score` is not displayed** — not merely de-prioritized. Live Issue 8's fix (scoping the rubric to the angle) landed but only ever corrected the scope mismatch, not the blank-PNG/degenerate-result cases (Runs 16, 17, 19) where a script that silently dropped data still scored 1.00, so trusting the number once "confirmed" would still mislead. `pattern_reasoning` is the gallery's only quality signal.

---

### D-consolidate — Repo hygiene, honest docs, and dead weight

**Goal:** close the gap between what the repository *says* it is and what the code now does. No behaviour change, no new capability — every item either deletes something, moves something, or corrects a statement that is currently false. Evidence for all of it is in §12.

**Run it before D8.** Not because D8 depends on it, but because item 1 changes the brief every future agent works from.

#### Changes

**1. Rewrite `CLAUDE.md`. Highest leverage item in this document.**

It currently diagrams `Criteria extraction → Orchestrator → Workers → Compiler+Execution → Requirements Evaluator` — the converger — and contains **zero occurrences of "angle" or "gallery"**. It documents `--max-iterations 5` as a redesign count and does not mention `--realize-top-k` or `--angles-per-iteration`. It says the pipeline produces "a **standalone Python analysis script**".

This is the file Claude Code reads before touching anything, so **the agent doing the work has been briefed on an architecture that no longer exists for the whole of D2–D7.** That is a plausible partial explanation for items 5–7 below: an agent told the system is a converger will add to it rather than restructure it. Rewrite it to describe the real flow:

```
criteria split → ideate (fan-out, N angles) → judge (insight + soundness)
  → dedup → rank → realise top-k → gallery
```

Include: the four `realization_status` outcomes and what each means, the three-way soundness vocabulary, the fact that `delivered_score` exists but is deliberately not displayed, and the human-owned-prompts guardrail (§2).

**2. Rewrite `README.md`.** Same drift, plus concrete falsehoods a new user would hit immediately:
- Claims the pipeline refines "a standalone Python analysis script" and ends "A design passes → Final Script". It returns a gallery.
- Documents `--designs-per-iteration` (removed in D6) and omits `--realize-top-k` and `--angles-per-iteration` (both live).
- Lists configs as `{bioimage, trello}`; there are three.
- Describes best-of-N and "seeded mutation" — both deleted in D1/D3 (`pick_best_seed`/`pick_other_seed`, §6).

**3. Fix or retire the default entrypoint — and decide the template question while you are there.**

`pixi run python app.py` with no arguments is the command both documents give as the primary entrypoint. It selects `bioimage_config`, which defaults to `./inputs/report/report_20260710_202254.md` and `./inputs/images` — **neither path exists in the repository.** The documented happy path is broken.

Behind that is the identity question this fork has been deferring. Two honest options, and the choice determines several items below:

- **(a) It is a CBIAS research instrument.** Make `cbias` the default config, delete or clearly mark `bioimage_config.py` and `trello_config.py` as untested examples, and amend §2's "keep it a template" guardrail to say what is actually being kept — a *simple, single-module, no-framework* pipeline, which is the property that has genuinely held.
- **(b) It is still a template.** Then the bioimage and trello paths must actually run, which means shipping sample inputs for at least one of them and confirming the diverger's ideation/judging stages produce something sensible on a domain that is not a four-year survey dataset. Note that no such run has ever been done: **every one of the twenty runs in §3 is `cbias`.**

Both configs currently *import* cleanly against `PipelineConfig` — that is real and worth keeping — but importing is not running. Recommendation is (a), on the evidence: the report format, the anti-target loop, `DOMAIN_NOTES`, the guiding-question parser and every calibrated threshold in this document are CBIAS-shaped.

**RESOLVED, the default half only (rev. 34).** `app.py`'s `--config` now defaults to `cbias` instead of `bioimage`, so the documented bare-invocation happy path actually runs. `README.md`/`CLAUDE.md` updated to match (neither claims a broken default anymore). **Not fully option (a):** `bioimage_config.py`/`trello_config.py` are untouched — not deleted, not marked untested in code, only described honestly in `README.md`'s config table — and §2's "keep it a template" guardrail still reads as if all three configs are on equal footing. Revisit if the template question needs settling further than "the default now works."

**4. Split `pipeline.py`. Lower priority than rev. 19 implied (§13).** The post's concern is whether prompts and responses are visible and debuggable, not file length — and on that measure diverger already scores about as well as a system can. This is a readability nicety, not a correctness issue; keep it behind items 1–3 and do not let it block anything. 1681 lines in one module, with a 349-line `generate_and_optimize` and a 166-line `_run_one_design`. Mechanical, no behaviour change; the seams already exist:

**DONE (rev. 36).** Split into exactly the eight modules below, plus `from prompts import *` replaced with explicit per-name imports in every one of them. Verified offline: `ast.parse` on all eight files, a real `import pipeline` exercising the full chain, `app.py`/all three domain configs still import cleanly, and a mocked end-to-end run (`llm_call` and `execute_script_in_docker` monkeypatched, real `generate_and_optimize` call) producing the same five-tier result shape as before — gallery/dump/scripts all written, one angle realised at `delivered_score=1.00`, 11 LLM calls in the expected 1+2+4+1+1+1+1 shape. Total line count 1820 → 1582 across the eight files (most of the drop is item 5's trim, below, done in the same pass). Needs a **live** run to confirm no regression beyond what offline mocking can exercise (real model responses, real Docker).

| Module | Contents |
|---|---|
| `llm.py` | `_client_for_model`, `llm_call`, `_image_blocks`, `LLM_SEMAPHORE` |
| `parsing.py` | `extract_xml`, `_extract_markdown_section`, `format_prompt`, `_parse_xml_items`, `parse_tasks`, `parse_angles`, `_parse_guiding_questions` |
| `sandbox.py` | `DOCKER_SANDBOX_FLAGS`, `execute_script_in_docker`, `validate_execution`, `_format_artifacts`, `_load_plot_images` |
| `ideation.py` | `generate_angles`, `_angle_record`, `_ensure_unique_id`, `_log_iteration_diversity`, `_token_set`, `_jaccard`, `_angle_signature`, `_pick_representative`, `_dedup_angles` |
| `judging.py` | `judge_insight`, `judge_soundness`, `_judgment_sort_key`, `_format_angle` |
| `realization.py` | `_run_one_design`, `compile_script`, `_call_worker`, `validate_realization` |
| `output.py` | `_write_gallery`, `_write_angle_dump`, `_gallery_entry`, `_gallery_entry_images`, `_script_rel_path` |
| `pipeline.py` | `generate_and_optimize` only — the orchestration, readable on one screen |

While doing it: **replace `from prompts import *`.** The star import makes 24 prompt constants unresolvable to any static check, so nothing will ever tell you when a prompt goes unused or a name is misspelled until it fails at runtime.

**5. Move run archaeology out of the code comments and into this document. Apply more conservatively than rev. 19 proposed (§13).** Some of what §12 counted as prose weight is the transparency record the post treats as a feature — the *reason* a status exists, or why a threshold is what it is, is load-bearing for anyone debugging a run. Cut citations, not reasoning, and when in doubt keep it. The 250–350 line estimate below is now an upper bound, not a target.

`pipeline.py` is ~34% comment and docstring, with **103 references** to Live Issue numbers, run numbers, or D-phase labels. `generate_and_optimize`'s docstring alone is 27 lines and names seven phases.

The comments are individually good — they record *why*, which is the valuable half and must survive. What should not survive in source is *when*: "Run 20 showed", "Live Issue 8", "D6-fix item 2". That history already lives here, in a document specifically maintained for it, and keeping it in both places means a reader has to reconstruct seven phases of project history to understand a six-stage pipeline.

**The rule to apply:** keep the reason, drop the citation. `# Ranked by insight, not delivery mechanics — a clean disconfirmation is often the more useful result` stays. `(DIVERGER_PLAN.md Live Issue 8/D7, Run 20)` goes. Where the history genuinely matters, one pointer to the section here is enough.

Rough estimate: 250–350 lines removed without losing a single decision.

**DONE (rev. 36), applied conservatively as instructed above.** Trimmed while writing each of the eight new modules (item 4), not as a separate pass: bare `Run N showed`/`Live Issue N:`-as-a-label citations dropped, the reasoning that followed each one kept verbatim or near-verbatim. Section pointers (`DIVERGER_PLAN.md §4`, `§10`) were kept, per the rule's own carve-out, as were the small number of deliberate single pointers to a Live Issue for readers who want the full history (e.g. dedup's measurement-only status pointing at Live Issue 24) — these are load-bearing orientation, not archaeology. A `grep` sweep for `Run \d+|Live Issue \d+:|D6-fix|D5-calibrate` across all eight files after the split caught one remaining case (`realization.py`'s `_PATTERN_OUTCOMES` comment), fixed. Total reduction (this item plus item 4's mechanical split overhead) was 1820 → 1582 lines, short of the 250–350 estimate on its own since some of that estimate's budget was absorbed by module docstrings the split itself required - the comment-density reduction inside surviving prose is the real measure, not the line count.

**6. Delete dead weight.** All three confirmed by inspection at `96d297f`:
- **`summary_text`** — ~25 lines of string formatting built at the end of `generate_and_optimize`, returned in the result dict, and consumed by nothing. `app.py` prints paths and counts only. Its docstring says it is "kept for console logging / non-visual consumers"; there are none. Delete it, or actually print it.
- **`delivered_pass`** — computed in `validate_realization` (`total > 0 and met == total`), returned, unpacked by its single caller, and never used. It is a vestige of the converger's boolean gate. Delete.
- The `_MIN_SUCCESS_OUTPUT_CHARS` / `_CRITERION_PATTERN` / `_PATTERN_OUTCOME_TO_STATUS` constants are all live and should stay — listing them here only so nobody sweeps them up with the above.

**DONE (rev. 36).** Both deleted exactly as scoped. `summary_text` no longer built or returned (`generate_and_optimize`'s result dict is now `all_angles`/`gallery_path`/`dump_path`/`scripts_dir` only); confirmed `app.py` never read it. `validate_realization` now returns a 4-tuple (`pattern_outcome, delivered_score, pattern_reasoning, feedback`), not 5 — its one caller (`_run_one_design`) updated to match. The three constants named above as "should stay" were left untouched, now living in `sandbox.py`/`realization.py` per item 4's module table.

**7. Measure, then decide: does dedup still earn its ~115 lines?**

`_dedup_angles` plus `_angle_signature`, `_pick_representative`, `_token_set` and `_jaccard` is roughly 115 lines with a hand-calibrated threshold (0.22, §3) and a documented lexical ceiling. It was originally justified by saving downstream cost.

**It no longer saves anything.** D6-fix item 2 correctly moved judging *before* dedup, so all N angles are judged either way. Realisation takes the top-k off a ranked list, and a merged duplicate would rank adjacent to its twin rather than displacing anything a human would miss. So dedup's entire remaining output is *removing a few rows from a gallery* — and the "also generated" section one-lines the survivors regardless.

Before deleting it, check the run log for the case it is actually protecting against: **has a merge ever removed an angle that would otherwise have entered the top-k and duplicated a slot?** Runs 8–20 record every merge and its score. If the answer is no across thirteen runs, dedup is a display nicety costing 115 lines and a calibrated constant, and the honest move is to delete it and let the gallery show near-duplicates — which a human skimming for leads can dismiss in a second, and which would incidentally make the lexical-ceiling problem (§3, "Known ceiling") disappear rather than needing an embedding-based fix later.

If the answer is yes, keep it and record the case here so the question stays settled.

**Run 22 adds to the case for deletion, weakly.** `8 → 8 after dedup, merged 0 within-iteration, 0 across-iteration` — zero merges. Weakly, because the run used `--angles-per-iteration 4`, so 8 angles is a thinner test than the default 12×2. Take the measurement above on a full-width run before deciding.

**Resolved as the interim, not settled outright (rev. 29) — see Live Issue 24.** `_dedup_angles` stays; `generate_and_optimize` no longer acts on its output, only logs what it would have merged. This keeps the "does it earn its lines" measurement running without committing to keep-and-enforce or delete while the evidence is still thin.

**8. Measure: does iteration 2 earn its keep?**

The default run is `--max-iterations 2 --angles-per-iteration 12 --realize-top-k 4` — **24 angles generated, 48 Opus judge calls, 4 realised**, roughly 110 LLM calls total (§12.4). Iteration 2's only divergence pressure is `{existing_angles}` in the prompt suffix.

**ANSWERED (Run 22) — keep `max_iterations=2`.** Two of the four realised angles came from iteration 2: `stakeholder-role-training-overlap` and `acronym-load-drift`, the latter at insight 0.78 and the gallery's second entry. Iteration 2 is not padding; it produces angles that reach the top-k and one of them was among the run's best. **Do not cut it, and do not spend further time on this question.** The original framing is kept below for the record.

> From the run logs: has any realised angle ever come from iteration 2? If not, `--max-iterations 1 --angles-per-iteration 16` produces a comparable archive for roughly two-thirds of the judging bill. Note the confound before concluding: cross-iteration divergence is reported "working" in every run since Run 4, so iteration 2 is demonstrably producing *different* angles — the question is narrower, whether any of them have ever been good enough to realise.

This interacted with D8 item 1, which wants the across-iteration merge fraction as a saturation signal. With iteration 2 confirmed productive, that signal is measuring a stage that genuinely exists — D8 item 1 proceeds as written.

#### Explicitly not in scope

- **Any change to the judge prompts, stances, thresholds or tiering.** Divergence is solved, the judges are validated (§8). This step touches structure and documentation only.
- **Adding tests or CI.** Worth wanting, but there is still no oracle in a diverger (§2) — the human reading the gallery is the test. A test suite here would pin plumbing, not quality, and the plumbing is about to move in item 4. Revisit after the split, when the module boundaries are stable enough to be worth pinning.
- **The `pipeline.py` rewrite as a redesign.** Item 4 is `git mv`-shaped: move functions, fix imports, change nothing else. If a split tempts you into restructuring the logic, stop and put the restructure in a separate commit.

**Verify:** a reader who has never seen this project can run the pipeline from `README.md` alone and get a gallery; `grep -c "Live Issue\|Run 1[0-9]" pipeline.py` returns something close to zero; `python -m pyflakes *.py` runs clean; no module exceeds ~400 lines.

---

### D8 — Saturation stopping and economy instrumentation

**Changes**
1. Stopping criterion = **novelty saturation**, using D4's *across-iteration* merge fraction against a configurable threshold. Keep `max_iterations` as a hard cap. (Across-iteration is the right signal — within-iteration measures differentiation, not saturation.) Dedup has now fired in Runs 8 and 11 (both single across/within merges), so a measurement exists but the *fraction* is still tiny — take a run with more iterations before setting the threshold.
2. **Verify caching** (§4) — the outstanding one-off measurement.
3. Instrument **cost per distinct angle surfaced**, reporting cached vs uncached input tokens alongside it. Replaces `req_score` as the number to tune against.
4. Confirm model tiering end to end against §5.
5. ~~Update `README.md` and `CLAUDE.md` to describe the diverger.~~ **Moved to D-consolidate**, and promoted — this was the lowest-numbered item of a deferred step, and it turned out to be the highest-leverage defect in the repository. See §12.1.

---

---

### D-simplify — Deferred: re-examine the design against external practice

**Status: BACKLOG. Nothing here is scheduled, and nothing already implemented and working should be touched on account of it.** This step exists so that observations from outside the project are recorded rather than lost, and re-read at the point where the pipeline is next opened up anyway. Two sources so far: Anthropic's [*Building effective agents*](https://www.anthropic.com/engineering/building-effective-agents) (§13) and the Crick's own [`lyra`](https://github.com/FrancisCrickInstitute/lyra) agentic-primitives repo (§14).

**Run it after D-consolidate, and not before.** D-consolidate is documentation and dead weight — no behaviour change. Everything below changes behaviour, and none of it is fixing something that is currently broken.

#### The standing rule that comes out of §13, and applies to every other step

**Transparency machinery is not complexity, and must not be stripped as though it were.** The post's second principle is to show the planning steps explicitly. A large part of the growth from 811 to 1681 lines is exactly that: the five-status vocabulary, `pattern_reasoning` on the console, per-attempt FAIL logging, `stage` tracking, the tiered gallery. §12 counted those lines as weight without asking what they bought, and that was a misreading. **Any future cleanup that would make the pipeline less legible from the outside is a regression, whatever it does to the line count.**

#### Items

**1. The agent–computer interface — the biggest unexamined surface, and the reason this step exists.**

Appendix 2 of the post reports that building the SWE-bench agent involved more time optimising tools than the overall prompt, and advises keeping formats close to what the model has seen naturally, with no formatting overhead.

Diverger's ACI is its XML schemas — `<task>` blocks nested inside `<tasks>`, alongside `<analysis>`, all carrying free prose. Three symptoms of one under-examined interface:
- Run 22: `Failed to parse <task> XML: mismatched tag: line 10, column 419` (recovered).
- Run 24: `Failed to parse <task> XML: mismatched tag: line 10, column 527` (recovered). Both failures land in the free-prose `<description>` field at a high column offset — consistent with the model's own prose containing characters the parser cannot take, which is exactly the "formatting overhead" the post warns about.
- Live Issue 18: tolerate formatting drift in the angle schema.
- Live Issue 20: `<pattern_outcome>` parse fallback to the conservative default.

**And the interface is wider than the XML.** Live Issue 25 established that `DOMAIN_NOTES` — the pipeline's description of the data to every worker and compiler call — is equally load-bearing and has never had comparable scrutiny: one wrong line in it produced effectively identical failures in two independently generated scripts across two runs. §15 classes A and B are almost entirely this. When this item is next opened, the data description belongs in scope alongside the schemas.

None of these is currently hurting a run badly enough to act on — the recovery paths work, which is why this is deferred. But they are the same problem seen three times, and the post says this is the surface that repays attention most. **When it is next worth opening: consider whether nested XML with prose inside is the right format at all**, versus something flatter with less escaping burden. Do not start by tuning the parser again.

**2. Dedup: delete or demonstrate — see Live Issue 24.** The post's rule is to add complexity only where it demonstrably improves outcomes. Dedup's original justification (saving judging cost) was removed when D6-fix moved judging before it, and no replacement justification was ever established. Issue 24 carries the reframed decision; this item exists only to record why the standard changed.

**3. D8 is where this pipeline stops being a workflow.** The post's architectural line is between *workflows* — LLMs orchestrated through predefined code paths — and *agents*, which direct their own processes. Diverger is unambiguously a workflow today, and that is a deliberate strength, not an accident.

**Saturation stopping is the first item on the plan that crosses the line**: it hands the system the decision about how many iterations to run. The post notes agents bring higher cost and the potential for compounding errors. So D8 item 1 gains a precondition: **the fixed `max_iterations=2` is the baseline any dynamic criterion must beat**, measured on realised-angle yield, not on merge fractions. If a saturation rule cannot be shown to beat "just run two", the honest answer is to keep the constant. Run 22 already established that iteration 2 earns its keep, which is the number to beat.

**4. Frameworks (LangGraph and similar) — revisit at D8, not before.**

The question was raised directly: would a graph runtime simplify this code? **Assessed and deferred, with a specific trigger condition rather than a flat no.** LangGraph's principles — explicit state, no hidden control flow, low abstraction — are good ones, and largely ones this pipeline already follows.

*Why not now.* Four reasons, in order of weight:

- **It would relocate code, not reduce it.** Measured at `d0cd5d3`: orchestration is ~364 of `pipeline.py`'s 1803 lines, and not all of that is sequencing (`generate_and_optimize` also does result assembly, tier bucketing, logging, file writing). A graph runtime would own perhaps 150–200 lines, replaced by state schema, node definitions and edge wiring of comparable size. The other ~1900 lines across `pipeline.py` and `prompts.py` are domain logic — prompts (466), the realization chain (396), gallery writers (240), ideation (184), Docker (134), parsing (76), judging (76) — none of which a framework touches.
- **`llm_call` does four custom things that do not map onto a framework's LLM node.** §4's `cache_prefix` breakpoint convention; the retry-at-double ladder for thinking-budget exhaustion; streaming (Issue 23); and two-client routing for DeepSeek, which is what makes §5's model tiering possible. You would wrap the existing `llm_call` in a custom node and keep all 118 lines — the framework *and* the code.
- **Debuggability, and this is not hypothetical here.** Issues 21 and 23 were diagnosed by reading `asyncio.gather`'s exception semantics directly and by reasoning about where a `max_tokens * 2` retry sits relative to an SDK guard. Issue 21 took two rounds *with* full visibility of the transport. A runtime layer puts "which of four call sites raised" one step further away.
- **It cuts against D-consolidate.** A migration executed by an agent reading a `CLAUDE.md` that describes the converger would be strictly worse than no migration.

*The trigger condition.* Graph runtimes earn their keep on **cycles and dynamic routing**. Diverger has neither: a straight line with one fan-out. If D8's saturation stopping grows into genuine dynamic control — choosing which guiding questions to pursue, re-ideating against what has been learned, routing between realise-now and refine-first — the topology acquires cycles and the case becomes strong rather than weak. **Revisit at D8 and let the answer be determined by whether cycles actually exist, not by preference.** This is the same crossing point as item 3.

*Two ideas worth stealing now, without the dependency:*
- **Explicit typed run state.** State is currently dicts threaded through `generate_and_optimize` — `angle_records`, `judgments`, `realizations` — assembled ad hoc. A single `@dataclass RunState` (~40 lines) would make the pipeline's shape legible in one place. Arguably a better version of D-consolidate item 4 than the module split, since it clarifies the data flow rather than relocating functions.
- **Checkpointing.** A run is ~110 calls. Persisting the judged archive to JSON with a `--resume` flag (~50 lines) captures most of what a framework's durable execution would give, and the angles are already independent so a failure costs one angle rather than the run.

**5. Adopt an explicit run-state contract (from `lyra`, §14).**

`lyra`'s Python conductor carries an *Information Passing Contracts* table naming exactly what each stage hands the next, under the instruction to assemble the packet explicitly rather than let the receiving agent infer it. Diverger threads bare dicts — `angle_records`, `judgments`, `realizations` — through `generate_and_optimize` and assembles them ad hoc.

This is the same idea as the typed `RunState` under item 4, arrived at independently and by a different route, which is the main reason to take it seriously. **Note it is achievable in two ways and they are not equivalent:** a `@dataclass RunState` makes the contract executable and impossible to drift from; a table in `CLAUDE.md` makes it readable and free. Given D-consolidate item 1 is rewriting `CLAUDE.md` anyway, the table is close to zero marginal cost and should probably come first, with the dataclass as the follow-up if the table proves it earns its place.

**6. Automate the template-sanity check instead of fixing leakage once (from `lyra`, §14). The highest-value item in this step.**

`lyra`'s hooks roadmap records an audit finding that a repo positioned as reusable bundles had hardcoded specific project names (`polaris`, `sequencing-demux`) throughout its agents and instructions, and concludes that the most valuable hook is not a workflow-enforcement one but a **template-sanity checker** that blocks commits reintroducing project-specific references.

**That is §12.3, discovered independently by another team at the same institute, with a better answer than this plan currently has.** D-consolidate item 3 fixes diverger's leakage *once, by hand*: the vestigial `bioimage`/`trello` configs, the broken default entrypoint, the README's domain-agnostic claim. Nothing stops it recurring — and the history says it will, because 24 runs of CBIAS-driven tuning is exactly the pressure that put `DOMAIN_NOTES`, the anti-target loop, and the 0.22 dedup threshold where they are - the same pressure that produced a guiding-question-match threshold for Issue 24 before it was tried and reverted (rev. 29).

**Sequence matters here.** Decide D-consolidate item 3's template-versus-instrument question *first*, because the check is only meaningful once there is an answer to encode:
- If diverger becomes an explicit **CBIAS instrument**, no check is needed — leakage stops being leakage.
- If it stays a **template**, a grep-level pre-commit check over `pipeline.py`/`prompts.py` for `cbias`, `symposium`, `abstract`, `attendee`, `bioimage` and similar is cheap and settles the question permanently. Configs are exempt by construction; that is what they are for.

Worth borrowing the framing as well as the mechanism: the check's value is *preventive*, so it is worth more than its size suggests and should not be judged on line count.

**7. Explicitly NOT in scope, now or later.** The following were checked against the post and are correct as they stand — do not revisit them as "simplification":
- **No framework.** Direct SDK calls, prompts as visible string constants. This is the post's central recommendation and diverger already follows it.
- **The two-judge split.** The post names "each LLM call evaluates a different aspect" as a canonical sectioning use.
- **Orchestrator-workers in `_run_one_design`.** Recommended precisely where subtask count is unpredictable; Run 23's architectures were 2, 3, 4 and 7 functions.
- **The compile→execute→feedback loop.** Textbook evaluator-optimizer with a genuine oracle.
- **Streaming, worker resilience, `realization_error`, the tiered gallery.** Implemented, working, confirmed on live runs.

## 8. Tuning notes

**Divergence is solved; the judges are validated; realisation is the live frontier.** Eight consecutive runs at 0.09–0.14 within-iteration with healthy cross-iteration behaviour, and Runs 9–11 confirmed the insight judge discriminates and the soundness judge reasons from actual data. Effort now belongs in D6-fix and D7, not in stances, thresholds, or judge prompts.

**The attractor effect is a standing property.** Closing off explored territory concentrates ideation onto whatever remains most concrete — that is the anti-target *working*. Counter-pressure comes from differentiating the calls, not from loosening the anti-targets. Expect to re-check the diversity numbers after any substantial report change.

**Q1 + Conventional is a reliable obvious-angle generator — and that is now useful.** It reliably produces a ticket-type/role-counting angle, which the insight judge as reliably floors at 0.20 (Runs 9 and 11). It costs one slot per iteration and functions as a **standing control**: if that angle ever scores well, the insight judge has drifted. Leave it in place.

**Thresholds are control parameters, not gauges.** D4's dedup threshold (0.22 — now exercised twice, evidence in §3) and D8's saturation threshold (still unmeasured) read the same Jaccard signal. Set both from logged numbers.

**The dataset has a sophistication ceiling, and the judges have found it.** Run 12's three `unsupportable` angles were the *most* methodologically ambitious in the run — MCA + k-modes on ~90 respondents, factor analysis over 15–20 items at n=37, BERTopic on perhaps 30 comments — and scored 0.72 / 0.68 / 0.40 on insight. The soundness reasoning cites the 5–10-respondents-per-item rule and computes the effective corpus explicitly.

This is a property of the data, not a defect: **on n=37–60 with four time points, methodological sophistication and defensibility are in direct tension**, and the achievable frontier is *simple method, modest claim* — where Run 12's one realised angle sits. Expect ~3 of 8 angles per run to be spent on ambitious ideas the dataset cannot support. That is a meaningful fraction of the budget and worth surfacing in the gallery (D7 tier 4) rather than discarding, since "what this dataset cannot support" is itself useful to the organising committee.

**The pipeline has produced its first actionable lead (Run 17).** `angle-readability-change` came back `realised`, `delivered_score=1.00`: Flesch Reading Ease **12.35 → 10.40 → 8.80 → 7.88**, monotonic across all four years. Replicated in Run 19 (19.62 → 15.41, different implementation) and qualified in Run 20 (tests underpowered — see below). A quantified four-point trend on a non-obvious metric, worth a human follow-up. Retire it into Already Explored once acted on.

**The `realised_null` judgments are getting sharper, not just more frequent.** Run 17's `angle-satisfaction-profile-clusters` did not merely report "no trend" — it diagnosed *why* the hypothesis failed: the two clusters found were a single satisfaction **gradient** (every item higher in Cluster 0 than Cluster 1) rather than the claimed trade-off archetypes, prevalence bounced without direction (63→73→51→73%), and χ² against self-reported role was non-significant (p=0.42). Three independent lines of refutation, unprompted.

**The judge distinguishes a degenerate result from a credible null.** Run 17's `abstract-to-talk-conversion` produced acceptance rates of exactly 0.00 for every year — which *looks* like disconfirmation. The judge classified it `pattern_not_shown`, reasoning that this was "almost certainly a pipeline/matching bug rather than a genuine finding that 'no abstracts became talks' — the output is uninterpretable with respect to the claimed pattern, not a credible disconfirmation of it." That is the hardest case the three-way split has to handle, and it handled it. It also caught `role-training-hybridization` plotting only 2025 data under a chart titled "2024 vs 2025" — an internal title-vs-content inconsistency.

**Readability has now replicated four times, across four independent implementations, and is the project's most robust output (Runs 17, 19, 20, 22).** Run 22's `abstract-writing-style-drift` found Flesch reading ease **18.7 → 17.2 → 15.2 → 12.7**, monotonic across all four years, and reported bootstrap 95% CIs that are *wide and overlapping between adjacent years even as the point estimates trend consistently in one direction* — which is precisely the picture Run 20's Kruskal–Wallis tests gave (p=0.068 on Flesch–Kincaid), arrived at by a different route. Four implementations, four monotonic declines, consistently underpowered inference. **That is a strong lead and should be the first thing taken to the organising committee**; more years, or a better-powered test on abstract-level rather than year-level data, is the obvious follow-up. Retire it into Already Explored once acted on.

**The readability decline is a lead, not a finding — and that is the correct outcome.** Runs 17 and 19 both reported monotonic Flesch Reading Ease decline (12.35 → 7.88 and 19.62 → 15.41). Run 20 ran the same family *with* Kruskal–Wallis tests: avg sentence length p=0.187, Flesch–Kincaid p=0.068, hapax legomena p=0.117, and Flesch Reading Ease p=0.024 but non-monotonic. `realised_null`.

Both results are true. A monotonic four-point decline is real in the data; it is also underpowered at n=40–62 across four years. The right characterisation for the gallery is **"abstract readability appears to be declining, though the trend is not statistically significant on four points"** — which is a perfectly good lead for a human to follow up with more years or a better-powered test.

**This plan briefly recorded a retraction here. That was an over-correction** (see the note on scope below): `realised` is not a truth claim, and the soundness judge's caveat on both earlier runs already said "4 points is a weak trend, treat as indicative". The machinery was handling this correctly.

**Bold angles disconfirm; safe angles confirm (Run 20).** The run's three highest-insight angles (0.78, 0.75, 0.75) all came back `realised_null`, while the single `realised` angle scored **0.55** — second-lowest in the run. This is not a defect: an angle is interesting *because* it hypothesises something non-obvious, and non-obvious hypotheses are more often wrong. But it means a gallery that leads with `realised` leads with its least interesting result. Reinforces ranking the top tier on **insight**, with `realised` and `realised_null` interleaved rather than separated.

**RUN 25: the judge enforced this distinction on its own, unprompted.** `stakeholder-hybridity-from-feedback-training-overlap` was ruled **unsupportable** — because it framed hybridity as a *temporal* claim (breadth rising 2024→2025), and the field exists in only two years. The soundness judge's reasoning: a 2-point trend cannot support a directional assertion, and pairwise co-occurrence testing on 37–53 respondents is too sparse; it added that *a descriptive single-year snapshot would be salvageable, but the hypothesis as stated is not*.

That is exactly the trend/state split recorded below, applied correctly to a new angle without anything in the prompts naming it. **The judges are doing the work this section documents**, which is the strongest evidence yet that the D5 pair is calibrated. It also means Already Explored can afford to be precise rather than blunt: retiring "hybridity" wholesale would suppress the answerable half.

**Stakeholder blurring: the trend is dead, the state is confirmed — and the distinction matters (Runs 15, 16, 19, 21).** Three independent disconfirmations of the *trend* claim: Run 15's `stakeholder-hybridity-depth` found dual-discipline training falling 22.6% → 16.2%; Run 16's `hybrid-background-blurring` found multi-domain proportion falling 86.8% → 81.1%; Run 19's `stakeholder-hybridity-analysis` found an essentially flat ~70% rate. Three angles, three hybridity definitions, no support for "increasingly blurred" in any of them.

**Run 21 then `realised` a fourth angle on the same territory — and it is not a contradiction.** `stakeholder-hybridity-index` (insight 0.78) tested whether boundaries *are* blurred rather than whether they are *becoming* blurred, and found extensive off-diagonal role×training-domain overlap: facility staff, PhD students, postdocs and research scientists all reporting meaningful counts across image analysis, machine learning, computer vision and cell/molecular biology alike, with non-trivial hybridity scores across virtually every role in both years. Cross-sectional, 2024/25 only (n=53, n=37), descriptive rather than tested — and the judge said all of that unprompted.

**So the retirement note for guiding question 5 needs to be more precise than "settled".** Write both halves into Already Explored: *the community is hybrid (established, four angles, one confirming state and three disconfirming trend); it is not becoming more hybrid over 2022–2025 (established, three independent definitions).* Retiring the question wholesale would discard the positive finding along with the dead premise; retiring it as "no trend" alone would leave the state claim open and it will keep being re-proposed. **This is the clearest demonstration yet that the anti-target list needs to name claims, not topics** — four angles on one topic produced two genuinely different, both-useful answers.

**A new finding worth acting on (Run 19), now replicated and quantified (Run 22).** Run 19's `industry-speaker-attendee-alignment` came back `realised_null` with ρ=−0.40: industry *speaker* share rising steadily while industry *attendee* share falls. Run 22's `speaker-attendee-sector-alignment` (insight 0.72, `realised`) found the same divergence as an explicit ratio — academic speaker:attendee ratio declining **1.49 → 1.15** while industry/vendor rises **0.87 → 3.00**, with academic speaker share exceeding academic attendee share every year (0.895 vs 0.601 in 2022). The programme is moving toward industry as the audience moves away from it.

**CORRECTION (Run 24): this has NOT cleared replication either, and the rev. 22 claim that it had is withdrawn.** Run 24's `speaker-submitter-attendee-sector-alignment` (insight 0.72, `realised`) measured Jensen–Shannon divergence between speaker, submitter and attendee sector distributions and found the gap **falling to near-zero by 2024** with a modest uptick in 2025 — i.e. the programme becoming *more* sector-representative. Runs 19 and 22 said divergence; Run 24 says convergence.

**RUN 25 GIVES A THIRD ANSWER, AND THAT IS THE ACTUAL FINDING.** `sector-alignment-gap` (insight 0.72, `realised`) computed a signed academic-share gap between programme speakers and both abstract authors and in-person attendees, and found it **widening sharply** — roughly −0.02/−0.07 in 2022 to −0.26/−0.39 across 2023–25.

Four runs, four operationalisations, three mutually inconsistent conclusions: diverge (19, 22), converge (24), diverge in the opposite sense (25 — the programme *under*-represents the academic majority, where Run 22 said it *over*-represented it).

**The honest reading is not "which run is right".** When one question yields contradictory answers under different but individually reasonable operationalisations of the same data, the data does not identify the quantity. The judges have been saying so in the caveats the whole time: industry-identifiable populations run to **1–10 people per year** (Run 25 notes a single Industry ticket in 2025), and sector must be inferred by keyword rules over free-text affiliations. A share built on n=1 is not a share.

**Record it that way in Already Explored: the sector-representativeness question is not answerable from this data, and four independent attempts establish that.** That is a genuine and useful result — it belongs in the report's data-gaps section as a request for an explicit sector field — but it is not a finding about the symposium.

The measures differ (a ratio between two populations versus a distance across three, one of which — abstract submitting institutions — is new in Run 24), so this is not a flat contradiction. But **the narrative flips**, and that is what matters for anyone about to act on it. The judge's caveat is the likely reason on both sides: industry-identifiable populations run to roughly one to ten people per year, so any sector share built on them is dominated by single-person changes.

**Do not take this to the organising committee.** Like readability, it is a recurring signal that has not survived a change of implementation.

**This is the second time the same mistake has been made in this document, so state the rule plainly:** two angles agreeing on *direction* is not replication when they do not share a definition. Before recording any future repeat as corroboration, check that the underlying quantity is the same quantity — same populations, same preprocessing, compatible absolute values — and not merely the same topic pointing the same way. Applied retrospectively, **this project currently has no finding that has cleared replication**, which is a fair result for four years of data at n≈40–60 per year and should be stated as such rather than papered over.

**The judge catches partial execution, not just wrong results.** Run 19's `angle-1` was marked `realised_null` on the theme that *did* have a clean surveyed→removed transition (mentions declining 0.033 → 0.019 → 0 → 0, opposite the claim) — and the reasoning separately notes the script "never identifies or tests 'added' topics... so that part is simply absent rather than supported." Half-answered claims are being flagged as half-answered rather than silently passing.

**The anti-target keeps sinking the same family further.** `ticket-type-composition-trend` scored **0.10** in Run 15 — a new floor, below the 0.20 that the same family scored in Runs 9 and 11. Six runs of progressively harder marking on per-year category counts, without any prompt change. The insight judge is not just discriminating; it is discriminating *consistently* against a family the anti-target names only obliquely.

**The anti-target curation loop is now due its first real use.** `reg-lead-time-by-ticket-type` has appeared in five separate runs across different stances and question slots, and Run 13 *realised* it at `delivered_score=1.00`. That is the loop working as designed: a genuinely good angle, now done. Retire it into the report's Already Explored section, or it will keep winning a slot. This is the intended human step — automatic retirement would suppress angles that merely resemble a prior one.

**`delivered_score` embarrassed itself again (Run 22), confirming D7's omit decision.** `acronym-load-drift` scored **1.00** for a noisy, non-monotonic disconfirmation; `abstract-writing-style-drift` scored **0.71** for the run's best result — which happened to have one metric silently unmeasured (Issue 22). The number is anti-correlated with worth here. Five runs of this now (12, 16, 17, 19, 22). Keep it out of the gallery; do not revisit unless someone proposes replacing it outright.

**Judge prompts are the product.** The machinery around them is trivial; the wording is the whole game. They are human-owned for that reason.


## 9. Deferred: external retrieval

Q5 originally asked for evidence of post-attendance collaboration, which needs literature data. Removed from the report; retrieval is out of scope for this fork. When it returns:

- **Enrichment, not agent capability.** A host-side script (sibling to `anonymize_cbias_data.py`) materialises external data into `inputs/.../Publications/`. Everything downstream works unchanged on local files and the sandbox keeps `--network none`.
- **A structured literature API** (OpenAlex, Europe PMC) beats generic web search — clean co-authorship records rather than prose about papers.
- **Scope is speakers, not attendees.** Programme CSVs retain real names; abstract author names were anonymised away. Roughly 15–20 named people per year.
- **Causality needs a design**: temporal precedence, exclusion of prior ties, and a control group of comparable non-co-attending pairs. Without the control it is an anecdote generator.

This is also the capability the horizon-scanning fork depends on, so getting the pattern right on a narrow checkable question is worthwhile groundwork.

---

## 10. Deferred: library provisioning

**RUN 24 — the `sentence-transformers` substitution is now visible end to end, and it is Tier 2 evidence, not a bug.** The full sequence appears in the console:

```
[semantic-convergence-trend] Compile attempt 1/3...
[semantic-convergence-trend] Execution: FAIL
  Attempt 1 FAIL reason: ModuleNotFoundError: No module named 'sentence_transformers'
[semantic-convergence-trend] Compile attempt 2/3...
[semantic-convergence-trend] Execution: PASS
```

The compiler wrote the declared import, Docker rejected it, the evaluator-optimizer loop fed the error back, and attempt 2 substituted something already in the image. **The reported "cosine similarities" are 0.0145–0.0179** — one to two orders of magnitude below what sentence-transformer embeddings give for same-domain abstracts, and characteristic of sparse high-dimensional vectors. Whatever attempt 2 used, it was almost certainly TF-IDF, which the anti-target list names as exhausted.

**Three things follow, and none of them is a code change.**
1. **The pipeline behaved correctly.** The FAIL reason is logged, the retry is logged, the numbers are in the gallery, the script is linked. Everything a human needs to notice this is already on screen — which is precisely why rev. 24 rejected adding a fidelity gate (see §7's "Deliberately NOT on this list").
2. **This is the strongest evidence yet for Tier 2.** `sentence-transformers` has been requested across many runs, and the substitution silently converts a genuinely novel angle into an anti-target one. Baking it removes the whole failure mode. Note the size: model weights are not pip installs (see below).
3. **Until it is baked, treat any embedding-angle result as suspect** unless the script's imports have been checked. The Run 23 `semantic-homogeneity-via-embeddings` result rests on the same substitution.


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


---

## 12. Structural review (at `96d297f`, rev. 19)

The evidence base for D-consolidate, in the same spirit as §3's run log: measured, not asserted. Taken against a clean clone at commit `96d297f` (206 commits).

### 12.1 The verdict

**The architecture is not over-complex. The repository around it is.**

Worth stating the negative first, because it is the part that could have gone wrong and did not. The control flow is still a straight line — criteria → ideate → judge → dedup → realise top-k → gallery. No supervisor, no asynchronous task queue, no Elo, no persistent ratings, no meta-review synthesiser, no multi-strategy reflection agent. §2's "no new frameworks, no tree-search controllers" guardrail held completely. Selective execution (top-k of 24) is a genuine cost control rather than a gesture, judging before dedup was the right ordering, and grading soundness rather than gating on it was the right call. All three domain configs still satisfy `PipelineConfig`.

What grew out of proportion is the file, the prose, and the distance between the documentation and the code.

### 12.2 Growth

| | fork point `fe6e197` (17 Jul) | `96d297f` (12 Aug) |
|---|---|---|
| `pipeline.py` | 811 lines | **1681** |
| `prompts.py` | 209 | 454 |
| `app.py` | 102 | 117 |
| largest function | — | `generate_and_optimize`, **349 lines** |
| second largest | — | `_run_one_design`, 166 lines |
| `pipeline.py` comment + docstring | — | **~34%** (196 comment, ~390 docstring lines) |
| references to Live Issues / run numbers / D-phases in `pipeline.py` | — | **103** |

A doubling of the core module is not obviously wrong for a fork that changed its output from one script to a tiered gallery. The 34% and the 103 are the numbers that matter: this document and the source are now maintaining the same history in parallel.

### 12.3 Documentation drift — the actual defect

Measured, not impressionistic: **`README.md` and `CLAUDE.md` contain zero occurrences of "angle" or "gallery".** They describe the converger, in detail, accurately, as of mid-July.

`CLAUDE.md` is the serious one because it is the brief Claude Code works from. For the whole of D2–D7 the agent implementing this plan has been told the system is an orchestrator/worker/compiler/evaluator pipeline producing a standalone script. That makes the drift self-reinforcing rather than merely untidy — and it is the single cheapest thing in this document to fix.

The documented default entrypoint (`pixi run python app.py`, no arguments) selects `bioimage_config`, whose default report and data directories do not exist in the repository.

Underneath both is the identity question. Every one of the twenty runs logged in §3 is `cbias`. The report format, the anti-target curation loop, `DOMAIN_NOTES`, the guiding-question parser, the 0.22 dedup threshold and the "n=37–60 across four time points" reasoning that shapes both judges are all CBIAS-specific. The repo still advertises itself as a reusable domain-agnostic template with two other configs; in practice it is a research instrument with two vestigial ones, and the broken default is the visible symptom of that. D-consolidate item 3 forces the choice.

### 12.4 Cost shape

At default settings (`--max-iterations 2 --angles-per-iteration 12 --realize-top-k 4`):

| Stage | Calls | Tier |
|---|---|---|
| Criteria extraction | 1 | Sonnet |
| Ideation | 24 | cheap (DeepSeek on cbias) |
| Judging (insight + soundness) | **48** | **Opus** |
| Realisation (4 × orchestrator + ~5 workers + ≤3 compilers + 1 validator) | ~36 | mixed |
| **Total** | **~110** | |

**Run 21 adds a third, sharper observation:** realisation spend can be lost *after* it is incurred. Two of four angles paid the full orchestrator + workers + compiler + Docker chain and then had the result discarded by a failed judge call (Live Issue 21), which does not show up anywhere in the table below because the calls all succeeded — only the last one did not return usable text. Any cost-per-distinct-angle figure (D8 item 3) must count realisations *retained*, not realisations *attempted*, or it will flatter the pipeline exactly when it is failing.

Two further observations rather than conclusions. Judging is 44% of the call count and sits on the most expensive tier — justified, since with `req_score` gone those two judges *are* the quality bar (§5), and they share a cached prefix. But 20 of the 24 judged angles are never realised and appear in the gallery as a single line each. And the generation-to-realisation ratio is 6:1, which is a defensible number for a diverger and an expensive one to leave unexamined. D-consolidate items 7 and 8 are the two measurements that would settle whether it is the right ratio.

### 12.5 Dead weight found

- `summary_text` — built, returned, consumed by nothing.
- `delivered_pass` — computed, returned, unpacked, never read.
- `from prompts import *` — 24 constants invisible to static analysis.

Small individually; listed because they are the tail end of the converger and their presence is the clearest single sign that deletions have lagged behind additions.

### 12.5b See also

§15 catalogues the failures that came from models misreading the data rather than from the pipeline's own bugs. It is the counterpart to this section: §12 measures the code, §15 measures what the code could not prevent.

### 12.6 Two prior concerns, closed

Both flagged during the D7 review and both resolve correctly on inspection, recorded here so they are not re-raised:

- **`_script_rel_path` does not double the `scripts/` prefix.** It returns `<run_ts>/<angle_id>.py` from an absolute path; the caller prepends `scripts/`. The resulting link is `scripts/<run_ts>/<angle_id>.py`, correct.
- **`considered_ids` does not over-exclude.** An angle with a failed soundness judge (`None`) and no realisation falls into "also generated", which is the correct catch-all for it.


---

## 13. Design review against *Building effective agents* (rev. 26)

Read against Anthropic's [*Building effective agents*](https://www.anthropic.com/engineering/building-effective-agents). Recorded here as the evidence base for D-simplify. **No implemented, working behaviour changes as a result of this section** — its effect is limited to the standard applied to outstanding items.

### 13.1 What the post measures, and what §12 measured instead

§12 assessed complexity by line count, function length, comment density and run-reference count. Those are code-hygiene metrics. The post's criteria are different: framework or direct API calls; does each added pattern demonstrably improve outcomes; is the system transparent; is the agent–computer interface any good. **Judged on the post's criteria, diverger comes out considerably better than §12's reading suggested.**

### 13.2 Diverger is a composition of the post's own patterns, with no framework

The post's central finding is that the most successful implementations avoid complex frameworks and specialised libraries in favour of simple, composable patterns, and it recommends calling the LLM APIs directly. Diverger uses no framework: raw `AsyncAnthropic` calls, prompts as visible string constants in one file, every response parsed in readable code. The specific harm the post attributes to frameworks — abstraction layers that obscure prompts and responses and make debugging harder — is the opposite of this repo's problem.

| Post's pattern | Where it appears in diverger |
|---|---|
| Prompt chaining | criteria → ideate → judge → dedup → realise → gallery |
| Parallelization (sectioning) | angle fan-out across stances/questions; the **two-judge split** |
| Orchestrator-workers | `_run_one_design`: orchestrator → workers → compiler |
| Evaluator-optimizer | compile → Docker → error feedback → recompile (×3) |
| Agents (autonomous loop) | **none** — deliberately |

**Run 29 extends the orchestrator-workers evidence:** `abstract-syntactic-readability-trajectory` produced an **11-function architecture** — well above the previous maximum of 7 — and compiled and executed on the first attempt. The pattern is scaling further than anything previously tested here, which is the property the post claims for it.

Two of these are worth recording precisely. The post gives "each LLM call evaluates a different aspect of the model's performance" as a canonical sectioning example, which is exactly the insight/soundness split arrived at independently in D5. And it recommends orchestrator-workers specifically where subtask count is *unpredictable*, in contrast to parallelization's pre-defined subtasks — Run 23's architectures were 2, 3, 4 and 7 functions, so that flexibility is being used rather than decorative.

### 13.3 The correction to §12: transparency was miscounted as weight

The post's second principle is to prioritise transparency by explicitly showing the planning steps.

A substantial share of the growth §12 flagged is that: the five-status vocabulary, `pattern_reasoning` on the console, per-attempt FAIL logging, `stage` tracking, the tiered gallery. Live Issues 9, 12 and 21 were all transparency fixes. §12 counted the lines without asking what they bought. **On the post's second principle these are the system's strongest feature, not its weight problem** — see D-simplify's standing rule, and the revised wording of D-consolidate items 4 and 5.

### 13.4 Where the post is harsher than this plan has been

*"Consider adding complexity only when it demonstrably improves outcomes."*

**Dedup fails this test.** Added to save downstream judging cost; D6-fix removed that saving by moving judging first; never re-justified; and Run 23 showed it removing a guiding question's only representative. Rev. 24's "keep it, add the guard" was too generous — Live Issue 24 now carries the delete-or-demonstrate framing.

Note what *passes* the same test, so the standard does not get applied selectively: `max_iterations=2` (Run 22 — iteration 2 produced two of four realised angles), selective realisation of top-k, graded-not-gated soundness, and the deletions this plan has already made (`pick_best_seed`, `req_score`, best-of-N).

### 13.5 The gap nobody has looked at

Appendix 2 reports that building the SWE-bench agent took more time optimising tools than the overall prompt, and advises formats close to what the model has seen naturally, without formatting overhead.

Diverger's equivalent is its XML schemas, and there are three symptoms of one under-examined interface: Run 22's `<task>` mismatched-tag failure, Live Issue 18 (formatting drift in the angle schema), Live Issue 20 (`<pattern_outcome>` parse fallback). Each has a working recovery path, which is why nothing is being changed now — but it is the same problem three times, on the surface the post says repays attention most. D-simplify item 1.

### 13.6 What does not change

The documentation drift (§12.3) is orthogonal to this post and remains the highest-leverage defect in the repository. `CLAUDE.md` describing the converger is a problem for reasons that have nothing to do with agent design.


---

## 14. Cross-project notes: `lyra` (rev. 28)

[`FrancisCrickInstitute/lyra`](https://github.com/FrancisCrickInstitute/lyra) is an agentic-primitives repository from elsewhere in the Crick — reusable agents, skills and instruction files for GitHub Copilot, distributed via Microsoft's [APM](https://github.com/microsoft/apm) package manager. Read at commit `27d22fb` (70 commits). Recorded here as the evidence base for D-simplify items 5 and 6.

**Why it is relevant despite solving a different problem.** Lyra automates *coding*; diverger automates *ideation over a fixed dataset*. But both are LLM pipelines with staged handoffs and gate conditions, both were built by small teams against real use, and they have converged on several of the same answers independently. Independent convergence is stronger evidence than either project's own reasoning.

### 14.1 Shape

A **conductor** agent (243 lines of markdown for Python, 290 for Nextflow) sequences 7 **subagents** — plan reviewer, test writer, code writer, code reviewer, formatter, acceptance, docs updater — through a fixed six-stage workflow with gate conditions and defined loop-back points. Alongside: `skills/` (markdown capability definitions with frontmatter), `instructions/` (language guidelines auto-applied by file type), and a `postToolUse` **hook** that runs `ruff check` and `pytest` after Python edits.

In the vocabulary of §13, lyra's conductor is the same orchestrator-workers pattern as `_run_one_design`, one level up.

### 14.2 What diverger should take (→ D-simplify items 5 and 6)

**The Information Passing Contracts table.** Lyra's conductor tabulates what each stage hands the next and instructs that the packet be assembled explicitly rather than inferred by the receiver. Diverger threads bare dicts. → item 5.

**The template-sanity hook.** Lyra audited itself, found hardcoded project names throughout supposedly reusable bundles, and concluded the most valuable hook is a preventive check rather than a workflow enforcer. This is §12.3 with a better remedy. → item 6, and it upgrades D-consolidate item 3 from a one-off cleanup to a decision plus a guard.

**Role purity in the conductor.** *"You do NOT write code, tests, or documentation yourself. Your only responsibilities are sequencing, gate enforcement, information passing, and issue progress reporting."* `generate_and_optimize` is 349 lines because it sequences *and* assembles results, buckets tiers, logs and writes files. Lyra states the separation as a rule; that is a cleaner target for D-consolidate item 4 than this plan's module table, which only moves functions between files.

### 14.3 What diverger has that lyra's authors would want

Offered as findings, not advice — and all of it is dearly bought, in the sense that this project paid for it over 24 runs.

- **The oracle asymmetry (§1, §11).** Lyra runs both kinds of check: `ruff`/`pytest` in the hook (a real oracle) and code-reviewer/acceptance subagents (LLM judges). D1–D5 established here that `req_score` — an LLM rubric judge — carried no information and was deleted, while the Docker exit code did the work. **Where a real oracle exists, spend complexity there and keep the LLM judges cheap and advisory.** Lyra's reviewer half-embodies this already by fixing advisory issues in place and rejecting only on blockers.
- **Numeric self-scores from LLM judges are unreliable.** `delivered_score` has been anti-correlated with worth across five runs (§8). Anything gated on a model's own quality number should be graded, not gated.
- **Separate infrastructure failure from quality judgement.** Live Issue 21 took three revisions to get right and produced two misleading galleries on the way. Lyra's gates are approved/rejected; a subagent that fails because a tool timed out currently looks like a rejection.
- **The replication trap (§8).** Two results agreeing in direction are not corroboration unless they share a definition. Applies directly to evaluating whether an agent workflow is improving.

### 14.4 One structural observation, and an open question

**Lyra puts its orchestration in the prompt; diverger puts it in code.** The conductor is an LLM instructed *"Execute all stages in this exact order. Do not skip, reorder, or merge stages"* and *"Never skip or reorder stages — the sequence is fixed."* Diverger's equivalent sequencing is Python.

Neither is simply better, and the §13 workflow-versus-agent distinction says which fits when: **if the sequence should adapt, prompt-level orchestration is right; if it genuinely must never vary, a code path enforces what an instruction can only request.** Lyra's stated requirement is the second while its mechanism is the first. Worth raising with them rather than assuming it is an oversight — they may want the flexibility in practice.

**The open question, which is §13's rule applied to someone else's project:** seven subagent invocations plus loop-backs for a one-line bugfix is substantial ceremony, and there is no escape hatch in the conductor. Is there evidence the full sequence beats a shorter path on small changes? That is the same question this plan asks of its own dedup step, and it is fairer asked than assumed.

### 14.5 Worth connecting the projects

Lyra has the packaging and reusability discipline diverger lacks — APM bundles, frontmatter'd skills, instruction files, a preventive check for exactly the leakage §12 documents. Diverger has 24 runs of evidence about what LLM evaluation actually buys you, which is the least-tested part of lyra's design. The exchange looks favourable in both directions.


---

## 15. Retrospective: where the models got the data wrong

A catalogue of every failure in this project's run history that came from a model **misreading the data, its environment, or its own output** — as distinct from the pipeline's own bugs, which are in §3's live-issue log. Compiled at rev. 33 across Runs 1–26.

**Why this is worth keeping.** The pipeline's headline claim (§1) is that a diverger is safe *because it has a real oracle* — Docker either runs the script or it doesn't. The failures below are the ones that oracle cannot see: **almost none of them are crashes.** They produce a script that exits 0, writes labelled PNGs, and reports numbers that are wrong for reasons invisible from the console. Every entry is an instance of the same underlying limitation — **the model never sees the data, only a description of it** — and the ones that survived longest are those where the wrong answer looked exactly like a right one.

### 15.1 Class A — the model cannot see the data, only `DOMAIN_NOTES`

The largest and most damaging class. In each case the description was accurate but incomplete, and the model filled the gap with a reasonable-sounding assumption.

| # | Failure | Runs | How it presented | How it was caught |
|---|---|---|---|---|
| A1 | **Decoy columns.** Microsoft Forms emits `Points - <question>` / `Feedback - <question>` companions beside every real question, always empty here. Substring column-matching selected them. | 24, 25 | "column not found or too few mappable responses" — looked like missing data | Human opened the CSVs (Issue 25) |
| A5 | **Response vocabulary assumed from the description, not the values.** `co-endorsed-feedback-theme-clusters` filtered Likert columns with `set(values) <= all_scales` — a strict subset test — against a hand-written map that omits **`"Not applicable"`**. Any column where even one respondent chose it was dropped whole. 2022 and 2024 kept 6 columns each; **2023 and 2025 kept 1**, tripping the `< 2` guard and losing both years. | 29 | Judge reported it prominently — the finding rests on a single 2022→2024 transition instead of a 4-year series |
| A2 | **Type assumed from category.** `DOMAIN_NOTES` said Likert answers are free text needing an ordinal map. True for every question *except* overall satisfaction, which is already numeric. The map found no matching keys and produced silent all-NaN. | 24, 25 | Judge reported the column "entirely NaN across all four years" | Human inspected `unique()` (Issue 25) |
| A3 | **Category label absent from its own keyword list.** `classify_affiliation()` matched "university", "college", etc. but never the literal string `"academic"` — so every attendee whose ticket type is `Academic` was bucketed as "other". | 26 | A fully legible chart measuring the programme's own share minus zero | **Realisation judge**, from the plot: no attendee bar in the Academic panel |
| A4 | **Category unreachable by rule order and assumed vocabulary.** `canonical_domain()` tests `microscop`/`imaging`/`image analysis` before the life-science patterns, and the survey's actual role values are *Facility staff*, *PhD student*, *Postdoctoral fellow* — which route to `funder/manager` via `"facility"` or fall through to `other`. The `life scientist` row was therefore absent from both years' matrices. | 27 | Heatmaps rendered fine; the row the hypothesis was *about* simply was not there | **Realisation judge**, and the script's own warning — it reported the gap rather than fabricating a row |

**A2 and A5 are the same recurring pattern too, and worth naming separately: the assumed vocabulary.** The model writes a value map from `DOMAIN_NOTES`' *description* of the data rather than from the values, and anything the description omits is handled wrongly — A2 mapped an already-numeric column as Likert text and got all-NaN; A5 omitted one response option and lost half the corpus. **Both failed silently at the point of loss** (A5's `< 2` guard did raise, but only after the columns had already been discarded, so the error names the symptom rather than the cause).

**The fix §15.7 already prescribes applies directly, and is nearly free: fix the description, not the model.** `DOMAIN_NOTES` describes the feedback CSVs in prose but never enumerates the response vocabulary. One line listing the distinct Likert values actually present — `Not applicable` included — would have prevented both A2 and A5, costs nothing at runtime, and is verifiable by a two-line script against the CSVs. **Verified for this dataset:** the only unmapped value across all four years' Likert columns is `"Not applicable"`.

*Verification note, and a §15 F-class near-miss worth recording:* a first pass at this attributed the loss to the venue question's wording change (`"The Francis Crick Institute was an appropriate venue"` → `"The venue was appropriate"`), reasoning from the criteria text. Checking the CSVs showed `venue` appears in both wordings and matched all four years — the hypothesis was wrong and the real cause was one absent response value. **Reasoning from the data description is exactly the error this whole class consists of; it applies to whoever is diagnosing it as much as to the model.**

**FIXED (rev. 43), and the fix's own re-verification found the diagnosis above was itself incomplete — a second F-class near-miss, self-caught this time.** Re-running the value-enumeration script directly against `inputs/cbias_data_anon/Feedback/*.csv` (not trusting the rev. 42 count) found the "Not applicable" line item was correct as far as it went, but understated the actual gap: **the Feedback CSVs carry two entirely separate Likert scales, not one.** Most questions use an agreement scale (`Strongly Disagree`/`Disagree`/`Neither Agree nor Disagree`/`Agree`/`Strongly Agree`/`Not Applicable` — note the capitalisation, `"Not Applicable"`, not `"Not applicable"` as first recorded), but the session/poster-session duration questions switch to a *different* scale entirely (`Far Too Short`/`Too Short`/`About Right`/`Too Long`/`Far Too Long`) — and, previously undocumented, they switch **wording at the same time**: 2022-2023 phrases these as "...was an appropriate length" on the agreement scale, 2024-2025 as "The average duration of ... was..." on the duration scale. A value map correctly covering `Not Applicable` would still have gone all-NaN on any duration-scale column, the identical failure shape one scale further out.

`cbias_config.DOMAIN_NOTES`'s Feedback section now: (1) documents the duration-question wording/scale change alongside the existing ticket-price polarity-flip example, so "wording drift" no longer implies "phrasing only"; (2) enumerates both scales verbatim, with a note that `Not Applicable` is a real, frequently-chosen response to be handled as its own category, not dropped or treated as an ordinal rung; (3) generalises the instruction to "build the mapping from the actual values, not an assumed/textbook Likert vocabulary," rather than resting on the single corrected example, on the same reasoning A2's fix already established. No pipeline code touched, no worker/compiler prompt changed — same shape as the A1/Issue 25 fix, a `DOMAIN_NOTES` correction only. **Needs a live run with a Likert-clustering or duration-question angle to confirm no recurrence**, ideally one touching the duration-scale columns specifically, since that half of the gap was never exercised by the original diagnosis.

**This is a `DOMAIN_NOTES` patch, not a general fix, and §15.7 item 7 says so plainly.** `DOMAIN_NOTES` already told the model to inspect a column's real values before assuming a mapping (added for A2, live for many runs before A5 happened anyway) — a general instruction that did not prevent this specific recurrence. Hand-enumerating the vocabulary here fixes what's known today; it does not stop the next new column or export year from reintroducing the same shape of bug. See §15.7 item 7 for the structural alternative (a fail-fast assertion on value-map coverage) that was considered but deliberately not implemented alongside this fix.

**A3 and A4 are the same recurring pattern, and it now has a name: the unreachable category.** A keyword classifier is written from the model's idea of what the values look like, not from the values; the category the hypothesis is *about* can then never be assigned. A3 omits the label outright; A4 shadows it by rule order plus a wrong guess at the vocabulary. Both produced well-formed, well-labelled charts. **Both were caught by the realisation judge reading the artifact — neither is detectable by any deterministic check the pipeline currently has**, because the script runs, exits 0, and writes valid PNGs. Expect more of these: every angle that bins free text into named categories is a candidate, and several per run do.

**A1 and A2 are the same root failure seen twice**, and it cost two runs plus a nearly-published fabricated data gap (§3, Issue 25). Note the asymmetry in how they were caught: A3 was caught automatically because the artifact *looked* wrong; A1 and A2 were not, because all-NaN and genuinely-missing are indistinguishable from the console.

**What worked as a fix:** removing the ambiguity from the data at source (A1 — companion columns dropped during anonymisation) beat instructing the model to ignore it. For A2, replacing "here is the exception" with "inspect the values before assuming" generalises; naming the one exception would not have.

### 15.2 Class B — the environment is not what the model assumed

| # | Failure | Runs | Effect |
|---|---|---|---|
| B1b | **B1a recurred, and the gap it leaves is now confirmed as structural (Run 30).** `authorial-voice-and-passive-shift` declared its fallback — `Analyzer: regex heuristic fallback (spaCy model unavailable)` — under its own Data gaps output. spaCy is indeed absent from the Dockerfile, so the "authorial voice" result rests on a regex matching `\b(?:is\|are\|was\|were)\s+\w+ed\b`, not dependency parsing. **The declaration reached the console and the script; the gallery entry and the judge's finding mention neither.** Second instance, same boundary — declaring the substitution is now reliable, surfacing it to the gallery reader is not. | 30 | A reader of the gallery alone cannot tell which method produced the finding |
| B1a | **B1, partially self-corrected (Run 28).** `abstract-similarity-network-topology.py` declared its fallback rather than hiding it — printing `Scientific sentence-transformer unavailable (...); falling back to TF-IDF embeddings` and listing it under its own data-gaps output. Presumably an effect of Issue 22's no-silent-failure prompt extension. **Not closed:** it surfaces in the console and the script only. The judge's `pattern_reasoning` does not mention it and the gallery caveat does not either, so a reader of the gallery alone still sees "semantic similarity network" with no sign the embeddings were TF-IDF. | 28 | Better than Runs 23–24, where nothing was declared at all |
| B1 | **Silent method substitution.** `sentence-transformers` declared in `requires`, absent from the image. Attempt 1 failed on `ModuleNotFoundError`; attempt 2 substituted something available. Reported cosine similarities of 0.0145–0.0179 — one to two orders of magnitude below sentence-transformer values, the signature of sparse TF-IDF. | 23, 24 | An angle justified entirely by *"embeddings capture meaning where term counts can't"* silently became a term-count method — which the anti-target list names as exhausted |
| B2 | **Missing NLTK resource, silently caught.** Passive-voice fraction unmeasurable, NA for all four years; script continued and was marked `realised` at 0.71. | 22 | One of five promised metrics vanished |
| B3 | **Corpus name drift.** `averaged_perceptron_tagger` baked; modern NLTK resolves to `averaged_perceptron_tagger_eng`. | 22 | B2's proximate cause |
| B4a | **B4 recurred, twice in one run (Run 30).** `ax.boxplot(..., labels=)` and `plt.boxplot(..., labels=)` — matplotlib renamed `labels` to `tick_labels` in 3.9. Both recovered on attempt 2. `AVAILABLE_LIBRARIES` names the library but not its version; the Dockerfile pins nothing, so the target API floats with every rebuild. **Same shape as A2/A5 one layer out: an assumed vocabulary the description does not pin down.** → Live Issue 30, **fixed rev. 45** (versions pinned in both the Dockerfile and `AVAILABLE_LIBRARIES`), pending rebuild + live confirmation | 30 | Two wasted compile attempts, no angle lost |
| B4 | **API version drift.** `applymap` (removed in pandas 3.0); a deprecated `matplotlib` boxplot kwarg. | 22, and Issue 20 | Hard failures — the good case, caught by Docker |

**B1 is the most instructive failure in this document.** The evaluator-optimizer loop worked *exactly as designed* — error fed back, script fixed, execution passed — and in doing so converted a novel angle into a forbidden one. **A recovery loop with no notion of method fidelity will repair a script into meaninglessness rather than fail.** The pipeline's own logs made it visible (FAIL reason, retry, numbers, linked script); nothing flagged it.

### 15.3 Class C — silent degradation and the fail-fast rule

| # | Failure | Runs | Caught by |
|---|---|---|---|
| C1 | **Clean exit on no data.** Script found nothing, printed 28 characters, exited 0. | 24 | `validate_execution`'s no-artifact backstop (Issue 11) |
| C2 | **Partial metric loss** (= B2). Four of five metrics computed, fifth silently NA. | 22 | Realisation judge, reported honestly but still ranked top-tier |

C1 is the class the pipeline defends against well and by design; C2 is the gap — the fail-fast instruction covers a *whole script* no-op, not the loss of one metric among several. **Counter-example worth recording:** Run 25's `satisfaction-driver-shift` raised on all three attempts rather than faking a result, and became the first legitimate `not_realisable` in the log. The instruction works when the failure is total.

### 15.4 Class D — the model's own output

| # | Failure | Runs | Note |
|---|---|---|---|
| D1 | **XML parse failures.** `<task>` mismatched tag at line 10, col 419 (Run 22) and col 527 (Run 24) — both deep inside the free-prose `<description>` field. | 22, 24 | Recovered both times. Evidence for D-simplify item 1: prose inside nested XML is a poor interface |
| D2 | **Thinking-budget exhaustion.** Response consumed `max_tokens` in thinking, returned no text block. | 21, 22, 23 | Three revisions of Issue 21 to categorise correctly, then Issue 23 to fix the transport |
| D3 | **Syntax error in generated code** — `SyntaxError: '(' was never closed`. | 26 | Recovered on attempt 2. Docker catches this class cleanly |

### 15.5 Class E — model-as-judge, and model-derived heuristics

| # | Failure | Evidence | Resolution |
|---|---|---|---|
| E1 | **`delivered_score` is anti-correlated with worth.** Scored 1.00 for a noisy disconfirmation and 0.71 for the run's best result. | 5 runs (12, 16, 17, 19, 22) | Omitted from the gallery (D7); never gated on |
| E2 | **`req_score` carried no information.** An LLM rubric judge over a real oracle's output. | D1–D5 | Deleted |
| E3 | **Lexical dedup conflates method with topic.** 6 false positives across Runs 23–26, all in the 0.22–0.36 band, all sharing topic vocabulary while differing in method. The highest-similarity merge in the whole log (0.360) is a false positive. | 23–26 | Reduced to measurement-only (Issue 24); fix, if any, must be semantic |

**The pattern across E:** every model-produced *number* in this project has needed downgrading — from gate, to rank, to display, to nothing. The model-produced *prose* (`pattern_reasoning`, soundness caveats) has held up far better, including catching A3. **Trust the judges' reasoning; distrust their scores.**

### 15.6 Class F — the analyst layer

Failures in interpreting the pipeline's output, committed while maintaining this document. Included because they are the same limitation one level up, and because three of them were nearly written into deliverables.

| # | Failure | Rev. | Nearly cost |
|---|---|---|---|
| F1 | **Concluded the data was defective from two scripts' error messages, without opening a CSV.** Recommended adding "overall satisfaction is unusable across all four years" to the report's data-gaps section. | 30 | A fabricated data gap in a document going to the organising committee, plus a `DOMAIN_NOTES` constraint suppressing a good variable |
| F2 | **Asserted a paid-for Docker run had been written off**, inferred from error text with no evidence of which call raised it. Run 22 showed the failure occurs before any Docker run. | 20 | A mis-scoped fix |
| F3 | **Reported "replicated four times"** for measurements that shared a name and nothing else — 2022 Flesch values of 12.35 / 19.62 / 18.70 on identical data. | 22 | Recommending an unreplicated result to the committee |
| F4 | **Measured complexity by line count**, counting transparency machinery as bloat. | 19 | Stripping the pipeline's most valuable property |

**The governing rule, and it generalises down to Class A:** *the pipeline's outputs are evidence about the pipeline; only the data is evidence about the data.* F1 and A1/A2 are the same error — inferring a property of the world from an artifact produced by a model that never saw the world.

### 15.7 What this says about agentic data interpretation

Seven observations, each supported by at least two entries above.

1. **Silence is the default failure mode.** Of the fourteen failures catalogued, three crashed (B4, D3, and C1's backstop). The rest produced plausible, well-labelled output. **A pipeline whose only oracle is "did it run" is blind to most of what goes wrong.**
2. **The description of the *environment* is a load-bearing interface at every layer, and now all three recorded layers have been fixed the same way.** Three instances of one shape are now recorded: A2 (the data's value types), A5 (its response vocabulary), B4/B4a (the libraries' API surface). In each, the model wrote against an assumed vocabulary that the description it was handed did not pin down. `DOMAIN_NOTES` was patched for A2 and A5 and **the fix worked on its first live run** (Run 30) — which was the evidence for pinning `AVAILABLE_LIBRARIES`'s versions too (Live Issue 30, **fixed rev. 45**, pending a Dockerfile rebuild and its own live confirmation). The original wording of this observation follows.

2a. **The description of the data is a load-bearing interface, and it is not treated like one.** A1, A2 and A3 all trace to `DOMAIN_NOTES` or to a keyword list. §8 records that judge prompts are the product; the *data* description has never had comparable scrutiny, and one wrong line in it produced effectively identical failures in two independently generated scripts across two runs.
3. **Fixing the data beats instructing the model.** A1's durable fix was structural (drop the decoys during anonymisation), after a prompt-level fix was tried and judged too flaky to keep. Instructions must be read and applied correctly every time; a removed column cannot be misread.
4. **Repair loops optimise for passing, not for meaning.** B1 is the clearest case: three attempts of automated recovery turned a novel method into a forbidden one, and every step was locally correct.
5. **Models are better critics than scorers.** *(Now two instances: A3 and A4.)* E1/E2 versus A3: the same models that produce unreliable numbers caught a bug a human reviewer would plausibly have missed, by looking at a chart and noticing an implausible zero — A4 repeats this from a different rule-order bug, again caught only by reading the artifact, not by any deterministic check the pipeline has. Separately, Run 27's `feedback-aspect-rank-trend` reported that two named aspect columns were absent every year rather than inventing them — a positive counter-example to C2, but a *generation*-time honesty, not a critic catching a scorer's mistake, so it isn't tallied here.
6. **The human is the last line, and needs the raw data to be one.** A1, A2, F1 were all resolved by someone opening a file. The gallery's linked scripts and artifacts exist for exactly this; the failures that persisted longest are the ones where nobody did.
7. **Telling the model to "inspect the data first" is not enough on its own — and A5 is the proof, not a hypothesis.** `DOMAIN_NOTES` has instructed exactly this ("INSPECT A COLUMN'S ACTUAL UNIQUE VALUES before deciding it needs a text-to-ordinal mapping") since the A2/Issue 25 fix (rev. 32) — a general rule, not tied to one column, live for many runs before Run 29. A5 happened anyway, on a different column, in the identical shape: a hand-written value map built from what a Likert scale is *expected* to contain, not from what `.unique()` on the real column would have returned. The instruction asks the model to adopt a habit of mind at code-generation time, when there is no dataframe in front of it to actually inspect — it is writing code that will run against real values later, and nothing checks whether the code it wrote actually earns the "inspected first" claim. Enumerating the exact vocabulary in `DOMAIN_NOTES` (rev. 43) fixes *this* instance but is a hand-maintained description that goes stale the moment a new column, or a new year's export, adds a value nobody re-verified — the identical maintenance burden A1's structural fix was chosen specifically to avoid. **The structural alternative, not yet implemented:** extend the existing no-silent-failure convention (Issue 11's whole-script fail-fast, Issue 22's per-metric version) to value-mapping code specifically — require any script that maps free-text values to an ordinal/category scale to assert its map covers every value the column actually contains, raising and naming whichever ones don't rather than silently dropping the rows that fail to match. That converts "figure out the vocabulary" from a request the model must remember to honour into a property Docker's exit code enforces on every run, self-correcting against whatever the data actually is rather than whatever `DOMAIN_NOTES` last said it was — observation 3 above, applied to the model's own code shape instead of to the input data. Worth a dedicated review pass (a `WORKER_PROMPT_SUFFIX`/`COMPILER_PROMPT_SUFFIX` rule change, human-owned-prompt-adjacent even though those suffixes aren't formally in that guardrail), not folded into rev. 43's fix.

**Scope note.** This section is about model limitations, not about what the CBIAS data says. Conclusions about the symposium belong in the report's Already Explored section, not here.

