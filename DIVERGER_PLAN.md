# Converger → Diverger conversion plan (rev. 4)

Working plan for `FrancisCrickInstitute/diverger-agents-template`.

**D1–D5 are complete.** The pipeline now ideates, diverges, dedups and judges — with no code executed anywhere in it. What remains is realisation (D6), the gallery (D7), and stopping/economy (D8), plus calibration of the two judges.

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
- **Human-owned prompts stay human-owned.** `ANGLE_GENERATION_*`, `INSIGHT_JUDGE_*` and `SOUNDNESS_JUDGE_*` are now filled in. Do not rewrite them; propose changes and let the human make them. The `*_FALLBACK` counterparts stay as the runnable-without-them safety net.
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

**D2** — ideation decoupled from execution. `generate_angles()`, `_parse_xml_items`, human-owned `ANGLE_GENERATION_*` with fallbacks, `angle_model` per config, `--angles-per-iteration`. The design/execution loop was replaced entirely — the correct reading of "no Docker in this step".

**D3** — fan-out to N concurrent one-angle calls, stance cycling, archive re-roled to hold proposed angles, `{existing_angles}` as cross-iteration divergence pressure, `_log_iteration_diversity` revived against angle text, `pick_best_seed`/`pick_other_seed` deleted.

**D3a** — **worked.** Within-iteration mean fell 0.34 → 0.10–0.12 and has held there for four runs. Three parts: stance logging (which unblocked diagnosis), guiding-question cycling as a second axis, and moving the stance adjacent to the instruction it modifies.

> **Slot-determinism bug, and the fix — do not reintroduce.** Both cycles were originally pinned to the call index (`m % len(...)`), so with 4 calls the pairing was identical every iteration: Q5 never fired, and each slot regenerated its own previous output (`abstract-readability-complexity-trend` → `abstract-reading-level-and-complexity-trend`). The fix offsets by iteration — `stances[(m + iteration) % S]`, `questions[(m + iteration * n) % Q]` — so no slot repeats its inputs and all five questions are covered within two iterations.

**D3b** — **worked.** Criteria now split into ideation criteria (guiding questions, stakeholders, verbatim anti-targets, data-availability constraints) and a deliverable rubric held for D6. Unplanned bonus: the extraction now emits a per-year *field availability inventory* (e.g. "Themes" and "Gender of presenting author" only in 2024/25, "doi" only in 2024), which is real grounding ideation previously lacked. Keep it.

**D4** — implemented (`_dedup_angles`, `angle_similarity_threshold=0.22`) but **never exercised**: 0 merges in every run since, because all observed pairs score 0.06–0.19. The threshold is calibrated against historical duplicates but unvalidated in the direction that matters. See "Known ceiling" below.

**D5** — implemented (`judge_insight`, `judge_soundness`, `_rank_key`, `judge_model` per config). Prompts filled by the human. `_candidate_score` deleted as scheduled. **The judges are not yet calibrated** — see "Live issues".

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

**Divergence is solved.** Both axes are healthy and have been for four consecutive runs. Do not spend further effort here.

### Live issues

**1. Soundness is saturated (highest priority).** 0/8 then 1/8 sound. `_rank_key` is `(sound_rank, insight_score)`, so a near-constant soundness signal contributes nothing to ranking — structurally the converger's binary `req_pass` problem in new clothes. With n=37–60 feedback respondents per year over four years, *almost nothing on this dataset is statistically robust*, so any "would this need a caveat?" bar rejects nearly everything, permanently. See D5-calibrate.

**2. Insight discrimination is unmeasured.** Per-angle `insight_score` is computed and printed, but the ranked block hasn't appeared in reviewed output. **This is the next number to look at.** If `ticket-type-trend` and `satisfaction-driver-shifts` score similarly, the insight prompt needs work before anything else.

**3. Cross-run memory is absent.** `ticket-type-trend` has appeared in four consecutive runs (always Q1 + Conventional); `readability-trend` and `registration-timing` three each. `{existing_angles}` only persists *within* a run. See D5-calibrate.

**4. Duplicate angle ids.** Run 7 produced two angles both called `angle-1`. Nothing keys on `id` today, so it is currently harmless — but it is a D7 prerequisite.

**5. Caching is unverified.** §4 asks for a single `cache_read_input_tokens` measurement. It has not been taken, so the entire §4 investment is unmeasured. Promoted to an explicit D8 task.

### Known ceiling: dedup is lexical

`feedback-cooccurrence-networks` (co-occurrence graph, modularity) and `feedback-cluster-evolution` (embed → HDBSCAN → Hungarian matching) are the **same idea** — how does the thematic structure of free-text feedback reorganise over time — with entirely different method vocabulary. Token-set Jaccard scores them ~0.09.

**Do not fix this by lowering the threshold**: genuinely distinct pairs also sit at 0.14, so lowering it over-merges before it catches this. The fix, if the duplication becomes material, is embedding- or judge-based similarity on `hypothesis` alone. Documented here so nobody tunes it instead.

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
| D6 realisation | existing compiler/worker splits, unchanged | — |

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

Currently unreferenced but **must not be deleted**. Mark each with a banner comment so intent survives without this document:

```python
# --- DORMANT: revived in D6 (selective execution). Do not delete. ---
```

| Symbol | Status | Revived by |
|---|---|---|
| `_run_one_design` | dormant | D6 — rebuilt around a single angle |
| `compile_script`, `_call_worker`, `parse_tasks` | dormant | D6 |
| `execute_script_in_docker`, `_format_artifacts` | dormant | D6 |
| `_load_plot_images`, `_image_blocks` | dormant | D6 (multimodal realisation check) |
| `validate_execution`, `validate_requirements` | dormant | D6 → `validate_realization` |

`pick_best_seed` / `pick_other_seed` (D3) and `_candidate_score` (D5) were deleted as scheduled.

---

## 7. Remaining steps

### D5-calibrate — Fix the judges before building on them

**Goal:** make soundness informative and confirm insight discriminates. No new stages; this is calibration plus two small mechanical changes. **Do this before D6** — realisation spends real money on whatever the ranking selects, so the ranking must mean something first.

**Changes**

1. **Surface the scores.** Ensure the ranked shortlist prints per-angle `insight_score`, `sound`, and both reasonings at the end of a run. Everything below depends on being able to see them.
2. **Grade soundness instead of gating it.** The judge should separate three cases rather than emit a boolean:
   - *Cannot support the claim at all* — a two-point "trend", a field that does not exist, a subgroup of three, "forecast backward via simulated annealing"
   - *Supportable if appropriately caveated* — the normal case on this dataset
   - *Solid* — rare here

   Emit a score (or three-level verdict) and carry the caveat text forward. **The caveat is something D7 displays, not something that filters** — D7's premise is that the human is the evaluation function, and "n=37/year, treat as indicative" next to a plot is more useful than a silently dropped angle. Prompt wording is human-owned; wire the plumbing and propose.
3. **Harden verdict parsing.** `sound = verdict_text == "true"` means anything that is not literally `true` becomes *unsound*, silently — so a prompt that drifts to yes/no, or a model that emits `True.`, produces total rejection that looks like a quality verdict. Anything outside the expected vocabulary should map to `None`/unranked so prompt problems stay visible.
4. **Enforce unique angle ids** at parse time (suffix a counter on collision). D7 prerequisite; also nudge the angle prompt toward descriptive slugs, since the call that produced `angle-1` also produced `semantic-topic-shift`.
5. **Add the cross-run anti-target loop.** Dump each run's surfaced angles to a file for human curation; curated entries are appended to the report's "Already Explored" section. The anti-target list is the only cross-run memory, and this converts review effort into permanent pressure — the same mechanism that stopped `abstract-analysis.ipynb`'s contents reappearing. Keep the human in the loop: automatic retirement would suppress angles that merely *resemble* a prior one.
6. **Add a `requires` field to the angle schema** (instrumentation only — see §10). Free, and it tells you what ideation actually reaches for before D6 makes it expensive.

**Verify:** `ticket-type-trend` (fourth consecutive appearance, close cousin of an anti-target) scores clearly below `satisfaction-driver-shifts` on insight. Soundness produces a spread rather than a near-constant. If the two example angles score similarly, the insight prompt needs work before proceeding.

---

### D6 — Selective execution

**Goal:** only now write and run code — for the top-k angles only. Revives the dormant execution layer.

**Changes**
1. Realise only the top-k ranked angles (`--realize-top-k`, default ~4; re-role or retire `--designs-per-iteration`). Revive `compile_script`, `_call_worker`, `execute_script_in_docker` and artifact copy-out **unchanged**, including their PREFIX/SUFFIX caching. Demoted from *scorer* to *validity gate*.
2. Rebuild `_run_one_design` around **one angle**: its `hypothesis` and `rough_method` become the brief the orchestrator/workers implement.
3. Re-role `validate_requirements` → `validate_realization`: from "meets criteria" to "does this legibly show the claimed pattern". Keep multimodal grounding (`_load_plot_images`, vision-capable model per §5). Feed it D3b's **deliverable rubric**.
4. An angle whose plot fails to show its claimed pattern is marked **"not realized"** and kept in the gallery flagged — not a run failure.
5. **Distinguish three outcomes**, and never conflate the last two: *realised*, *not realisable* (missing library — a provisioning outcome, see §10), *unsound* (a quality judgement). Expect availability failures to dominate initially: the cbias image is numpy/pandas/matplotlib only, and roughly half of recent angles reach for sentence-transformers, HDBSCAN, networkx, nltk or scipy.
6. Keep `max_attempts` low.

**Verify:** exactly k Docker runs; confirm the token drop versus the converger; realised angles have real, legible PNGs.

---

### D7 — Gallery, not a winner

**Changes**
1. `generate_and_optimize` returns a structured result, not a string. **This ripples into `app.py`**, which currently writes `analysis_script_<ts>.py`; the console header "FINAL COMPILED SCRIPT" is also now inaccurate.
2. Emit a self-contained gallery into `output_dir`: per realised angle, its plot(s), a one-line "what's surprising here", **the soundness caveat as a visible confidence note**, which question/stakeholder it serves, and its realisation status. Cluster by theme, rank by insight.
3. Also write each angle's generated script.
4. Build it to skim in under a minute. The human makes the final "is this actually interesting" call.

---

### D8 — Saturation stopping and economy instrumentation

**Changes**
1. Stopping criterion = **novelty saturation**, using D4's *across-iteration* merge fraction against a configurable threshold. Keep `max_iterations` as a hard cap. (Across-iteration is the right signal — within-iteration measures differentiation, not saturation.) Note this is currently unmeasurable: dedup has merged 0 in every run, so take a measurement before setting the threshold.
2. **Verify caching** (§4) — the outstanding one-off measurement.
3. Instrument **cost per distinct angle surfaced**, reporting cached vs uncached input tokens alongside it. Replaces `req_score` as the number to tune against.
4. Confirm model tiering end to end against §5.
5. Update `README.md` and `CLAUDE.md` to describe the diverger.

---

## 8. Tuning notes

**Divergence is solved; the judges are the live frontier.** Four consecutive runs at 0.09–0.12 within-iteration with healthy cross-iteration behaviour. Effort now belongs in D5-calibrate, not in more stances or thresholds.

**The attractor effect is a standing property.** Closing off explored territory concentrates ideation onto whatever remains most concrete — that is the anti-target *working*. Counter-pressure comes from differentiating the calls, not from loosening the anti-targets. Expect to re-check the diversity numbers after any substantial report change.

**Q1 + Conventional is a reliable obvious-angle generator.** Four runs, four ticket-type-count angles. Arguably the stance working as designed, but it spends a slot per iteration on something the insight judge should score near zero. Leave it until the insight scores are visible — if it scores low, it is functioning as a useful control.

**Thresholds are control parameters, not gauges.** D4's dedup threshold (0.22, calibrated, unexercised) and D8's saturation threshold (unmeasured) read the same Jaccard signal. Set both from logged numbers.

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

Current floor: numpy, pandas, matplotlib only. Roughly half of recent angles reach beyond it.

When implemented:

- **`requires` field on angles** (add now, in D5-calibrate) — instrumentation first, so the design is driven by what ideation actually asks for.
- **Provision at build time, not run time.** `--network none` forbids runtime installs, so the union of `requires` across the top-k angles resolves into a derived image (`FROM cbias-analysis; RUN pip install …`) before realisation. The build is trusted; execution stays isolated. That distinction is why this is safe.
- **Allowlist package names.** Hallucinated package names are a live supply-chain attack vector — attackers register the plausible-sounding names models invent. Grow the allowlist from observed `requires`.
- **Model weights are not pip installs.** `sentence-transformers` and BERTopic download weights on first use; with no runtime network they fail after a successful install. Baking weights into the image is a much heavier lift and a reasonable place to draw the line.
- **Cheap interim win:** add scipy, scikit-learn and nltk to the base image. Small relative to torch, and covers most of what ideation has reached for across seven runs.

Keep "not realisable" strictly separate from "unsound" in the gallery — the first is an engineering outcome, the second a quality judgement.

---

## 11. Expectation setting

This will surface a wider, cheaper spread of angles than the converger, some non-obvious — a real improvement over a pipeline that reflects the author's own priors back at them. It will not out-think a domain expert on their own data. Treat it as a fast idea-generator that occasionally surprises, with the human at D7 as the actual evaluation function. Building around that division of labour, rather than trying to automate the judgement away, is what makes the compute worth spending.
