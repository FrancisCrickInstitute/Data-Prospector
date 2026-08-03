# Converger → Diverger conversion plan (rev. 3)

Working plan for `FrancisCrickInstitute/diverger-agents-template`.

**D1, D2 and D3 are complete.** This revision folds in what two live runs revealed, adds two corrective steps (D3a, D3b) before D4, and recalibrates the D4 threshold against real measurements.

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
- **Do not invent objective prompts.** Steps needing an ideation or judging prompt declare a human-owned constant with `# TODO(human)`, plus a `*_FALLBACK` so the pipeline stays runnable. Build the plumbing and the slots; leave the wording.
- **Do not delete dormant code.** See §6.
- **Follow the caching convention (§4) for every new prompt.**
- **Reuse, don't rewrite.** `_parse_xml_items`, `_jaccard`/`_token_set`, `_log_iteration_diversity`, `_angle_record`, `llm_call` (semaphore + images + `cache_prefix` + provider routing), `extract_xml`, `format_prompt`, the Docker sandbox and artifact copy-out all carry over.
- **Instrument before tuning.** Every threshold in this plan should be set from observed numbers, not guessed. The D4 recalibration below is the worked example of why.
- **Keep it a template.** No new frameworks, no tree-search controllers, no persistent Elo ratings, no async task queues.
- **Prompts live in `prompts.py`.**

### Out of scope

- Message Batches API integration (revisit once D5 judge prompts are stable).
- **External retrieval / literature enrichment.** Deferred deliberately — see §9. Q5 of the report has been reworded to drop the collaboration question that would have required it.
- The "team capability & horizon scanning" variant (a later, separate fork).
- Human-directed deepening ("go deep on angle 3") — deferred until after D8.

---

## 3. Progress and current state

### Done

**D1** — convergence spine stripped (no early exit, no mutate-the-best seeding, execution layer inert). `.gitignore` hardened; `anonymize_cbias_data.py` committed.

**D2** — ideation decoupled from execution. `generate_angles()`, `_parse_xml_items`, `ANGLE_GENERATION_*` human-owned constants with fallbacks, `angle_model` per config, `--angles-per-iteration`. The design/execution loop was replaced entirely, which is the correct reading of "no Docker in this step".

**D3** — fan-out to N concurrent one-angle calls, stance cycling, archive re-roled to hold proposed angles, `{existing_angles}` wired as cross-iteration divergence pressure, `_log_iteration_diversity` revived against angle text, `_angle_record` added, `pick_best_seed`/`pick_other_seed` deleted.

**Report rewritten** (twice) — plot taxonomy, metric counts, PNG counts, gallery styling and docstring conventions all removed. Guiding questions levelled. Anti-target list ("Already Explored — Do Not Repeat") inlined from `djpbarry/cbias-survey`. Programme CSVs pre-downloaded into the data directory so Q4 is answerable without network access. Q5 reworded to drop post-attendance collaboration.

### What two live runs showed

| Run | Within-iteration mean | Cross-iteration behaviour |
|---|---|---|
| Run 1 (pre-anti-target) | 0.13 | **Failed** — iteration 2 refined an iteration-1 angle (TF-IDF → sentence transformers) |
| Run 2 (post-anti-target) | **0.34** | **Working** — iteration 2 dropped to 0.17, two angles left the cluster |

Two findings, and they point in opposite directions:

1. **Cross-iteration divergence now works.** `{existing_angles}` pressure is doing its job. No further change needed.
2. **Within-iteration divergence is the failure mode.** Run 2's iteration 1 produced *four near-copies of one angle* (count multi-select training domains → proportion with 2+ → "boundary blurring"), all pairs 0.30–0.40.

**The mechanism matters for the fix.** The anti-target closed off abstract text and attendee demographics — most of the data. Q5's rewording simultaneously made one opportunity *concrete* (a specific named multi-select field, obviously computable). Four independent samples sharing an identical prefix, differentiated only by stance, all walked into it. **The most concrete remaining opportunity acts as an attractor, and stance alone is too weak to counteract it.** This is the trigger condition for the second cycling axis held in reserve in rev 2.

### Blocked diagnosis

Only one angle across both runs visibly reflects its stance. Stances cycle `m % 3`, so iteration 1 should have contained a depth-first and a contrarian; all four read as conventional. **Three explanations are indistinguishable without a stance log**: the stance isn't reaching the prompt, its placement in the fallback suffix is too weak to bite, or the attractor overwhelms it. Each has a different fix. Fixing this is D3a's first task.

### Still outstanding

Criteria extraction still emits a **script rubric** ("Auto-detects and loads input files", "Script runs end-to-end without errors", "Code is clean and minimal") and feeds it wholesale into the ideation prefix. It also correctly carries the anti-target list, so it isn't pure noise — but ideation is paying cached tokens for docstring conventions. D3b splits it by consumer.

### Data notes

The Programme CSVs are headerless and ragged: column 1 is a time *or* `Session N`, column 2 a speaker *or* session theme *or* "Registration & Exhibition", column 3 an affiliation *or* a chair, column 4 a title — and the shape drifts between years. Speaker names are real (public data, published by the Crick) and deliberately not anonymised. If realisation failures at D6 cluster on programme parsing, normalise these into a flat `speaker,affiliation,title,year,session` table rather than blaming the model.

---

## 4. Caching convention

`llm_call` takes a `cache_prefix`: content there is marked with an ephemeral cache breakpoint, content in `prompt` is not. **Every new prompt must be split the same way.**

**The rule:** anything *identical across the calls sharing this cache* goes in the `_PREFIX`. Anything that varies goes in the `_SUFFIX`. Images go after the breakpoint (`llm_call` handles this).

**The trap:** a growing accumulator in the prefix invalidates the cache every iteration while looking correct. `{existing_angles}` grows each round — it belongs in the **suffix**. Same for stance, and for the guiding question added in D3a.

| Stage | Prefix (cached) | Suffix (varies) |
|---|---|---|
| **Ideation** | `report`, ideation criteria, `input_data`, anti-targets | `stance`, `guiding_question`, `existing_angles`, `n` |
| **D5 judges** | `report`, ideation criteria, `input_data`/schema, anti-targets | the individual angle |
| **D6 realisation** | existing compiler/worker splits, unchanged | — |

**Parallel fan-out defeats the cache on first use.** N concurrent `generate_angles` calls all start before any writes the cache, so all N miss on iteration 1 and hit only from iteration 2. Warm the cache with one call before gathering the rest if it matters; otherwise note it when reading cost figures rather than concluding caching is broken.

**Verify empirically, once:** log `usage.cache_creation_input_tokens` and `cache_read_input_tokens`. A prefix below the provider minimum (1024 tokens Sonnet/Opus, 2048 Haiku) is silently ignored — no error, no saving. Ephemeral TTL is 5 minutes.

---

## 5. Model tiering

| Role | Tier | Rationale |
|---|---|---|
| `worker_model`, `compiler_model` | DeepSeek | Mechanical, high-volume, **oracle-protected** — Docker catches bad code |
| `angle_model` | cheap tier | Volume matters more than polish; dedup + judges filter downstream |
| `orchestrator_model` | frontier | Retained for D6 realisation |
| `judge_model` (D5) | **frontier Anthropic** | Once `req_score` is gone these two judges *are* the entire quality bar |
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
| `_candidate_score` | dormant | **delete at D5** |
| `compile_script`, `_call_worker`, `parse_tasks` | live (via `_run_one_design`) | D6 |
| `execute_script_in_docker`, `_format_artifacts` | live (via `_run_one_design`) | D6 |
| `_load_plot_images`, `_image_blocks` | live | D6 (multimodal realisation check) |
| `validate_execution`, `validate_requirements` | live | D6 → `validate_realization` |
| `_jaccard`, `_token_set`, `_log_iteration_diversity`, `_angle_record` | **live** (revived at D3) | — |

`pick_best_seed` / `pick_other_seed` were deleted at D3 as scheduled.

---

## 7. Remaining steps

### D3a — Fix within-iteration divergence

**Goal:** break the attractor collapse observed in run 2. Small, targeted, directly addresses a measured failure.

**Changes**

1. **Log stance per angle.** Print which stance produced which angle, alongside the existing `[diversity]` line. This unblocks the three-way diagnosis above and is a prerequisite for judging whether change 2 worked.
2. **Add a second cycling axis: guiding question.** Parse the guiding questions out of the report/criteria and cycle them across the concurrent calls independently of stance, so call *m* gets `(stance[m % S], question[m % Q])`. With 4 calls and 5 questions, four different questions get pointed at — which structurally prevents four calls converging on Q5.
   - Put the question in the **suffix** (§4), not the prefix.
   - If question parsing is unreliable, fall back to cycling nothing rather than cycling a mis-parsed list, and log that it fell back.
3. **Strengthen stance placement in the fallback suffix.** Currently `Approach for this batch: {stance}` sits between the archive dump and the task description, which is the weakest position in the prompt. Move it adjacent to the instruction it modifies. (The human-owned prompt supersedes this, but the fallback is what runs today.)

**Verify:** iteration-1 within-iteration mean drops materially below run 2's 0.34 — target the 0.13 seen in run 1, ideally lower. Stances and questions both visible in the log and visibly reflected in the angles. If the mean stays high *and* the log shows stances correctly assigned, the attractor is stronger than prompt-level differentiation and the next lever is separate prefixes per question, not more stances.

---

### D3b — Split criteria by consumer

**Goal:** stop feeding a script rubric to ideation. This is the last structural leak from the converger.

**Changes**

1. Criteria extraction produces **two** outputs rather than one:
   - **Ideation criteria** — guiding questions, stakeholders, anti-targets, data availability constraints. Consumed by `generate_angles` and (later) the D5 judges.
   - **Deliverable rubric** — runs without errors, labelled plots, clean code, saves PNGs. Held back for D6's realisation check.
2. Update `CRITERIA_SYSTEM`/`CRITERIA_PROMPT` to emit both, in separate tags. Keep the existing fallback-to-raw-report guard.
3. `generate_angles` receives only the ideation criteria. `validate_realization` (D6) receives only the deliverable rubric.
4. Retain the "if the report is silent on a dimension, say so rather than assuming a default" instruction — it is what stops the rubric manufacturing PNG counts.

**Verify:** the ideation prefix no longer contains data-loading or code-quality criteria; the anti-target list still reaches ideation intact.

---

### D4 — Dedup (Proximity)

**Goal:** selection optimises for distinct, not best.

**Changes**
1. Cluster candidate angles by similarity using the D3 token-set plumbing over `hypothesis` + `variables_involved` + `rough_method`; drop near-duplicates.
2. **`angle_similarity_threshold` default 0.22.** Measured from two live runs: near-duplicates scored 0.23 (run 1) and 0.30–0.40 (run 2); genuinely distinct angles scored 0.08–0.19. A threshold of 0.20–0.25 separates both correctly. *The 0.6 in earlier revisions of this plan would have merged nothing.*
   - One known borderline: 0.19 for two related-but-distinct angles. Expect occasional over-merging near the boundary; prefer that to under-merging.
3. Log merge counts **split within-iteration vs across-iteration**. These diagnose different failures: high within-iteration means D3a's differentiation is still too weak; high across-iteration means `{existing_angles}` pressure has weakened. Currently the former is the live problem and the latter is healthy.
4. Keep one representative per cluster: the most specific `why_non_obvious`, else the first. Mark `# TODO(human): tiebreak may want tuning`.
5. Consider weighting `hypothesis` and `variables_involved` above `rough_method` — run 1's duplicates shared a topic but differed in method wording, and `rough_method` carries most of the tokens, diluting the signal.

**Verify:** run 2's four boundary-blurring angles collapse to one; `program-abstract-alignment` survives.

---

### D5 — Insight + soundness judging

**Goal:** score surviving angles for non-obviousness and defensibility. Replaces `req_score` as the quality bar. **Both prompts are human-owned — they are the product.**

**Changes**
1. `judge_insight(...)` scores each surviving angle for non-obviousness. Declare `INSIGHT_JUDGE_SYSTEM` / `_PROMPT_PREFIX` / `_PROMPT_SUFFIX` as `# TODO(human)` with `*_FALLBACK` counterparts, following the D2 pattern.
   **Must be grounded:** pass the data schema / `input_metadata` **and the anti-target list** into the prefix. Run 2 showed every angle confidently asserting its own novelty in `why_non_obvious` while six of eight were near-identical — self-assessment is not evidence, and the judge needs the same anti-targets ideation has.
2. `judge_soundness(...)` flags angles whose "insight" would likely be a sampling artifact. Same structure and treatment.
   **Live test case:** six of run 2's eight angles rest on a survey question present only in 2024 and 2025, and several propose to "visualise the trend" across two points. A working soundness judge rejects these.
3. Add `judge_model` to `PipelineConfig`, no default, set per config, frontier Anthropic tier in practice (§5).
4. Selection is now **dedup → insight → soundness → ranked shortlist**.
5. Both judges run per-angle via `asyncio.gather(..., return_exceptions=True)`; a failed judgement scores "unranked" rather than killing the run.
6. **Delete** `_candidate_score` (§6).

**Verify:** the two-year-trend angles are flagged unsound; obvious angles score low; `program-abstract-alignment` ranks well. Confirm cache hits on the judge prefix.

---

### D6 — Selective execution

**Goal:** only now write and run code — for the top-k angles only. Revives the dormant execution layer.

**Changes**
1. Realise only the top-k ranked angles (`--realize-top-k`, default ~4; re-role or retire `--designs-per-iteration`). Revive `compile_script`, `_call_worker`, `execute_script_in_docker` and artifact copy-out **unchanged**, including their PREFIX/SUFFIX caching. Demoted from *scorer* to *validity gate*.
2. Rebuild `_run_one_design` around **one angle**: its `hypothesis` and `rough_method` become the brief the orchestrator/workers implement.
3. Re-role `validate_requirements` → `validate_realization`: from "meets criteria" to "does this legibly show the claimed pattern". Keep multimodal grounding (`_load_plot_images`, vision-capable model per §5). Feed it D3b's **deliverable rubric**.
4. An angle whose plot fails to show its claimed pattern is marked **"not realized"** and kept in the gallery flagged — not a run failure.
5. Keep `max_attempts` low.

**Verify:** exactly k Docker runs; confirm the token drop versus the converger; realised angles have real, legible PNGs.

---

### D7 — Gallery, not a winner

**Changes**
1. `generate_and_optimize` returns a structured result, not a string. **This ripples into `app.py`**, which currently writes `analysis_script_<ts>.py` — replace that path. (The console header "FINAL COMPILED SCRIPT" is also now inaccurate.)
2. Emit a self-contained gallery into `output_dir`: per realised angle, its plot(s), a one-line "what's surprising here", the soundness note, and which question/stakeholder it serves. Cluster by theme, rank by non-obviousness. Single-file HTML or Markdown.
3. Also write each angle's generated script.
4. Build it to skim in under a minute.

---

### D8 — Saturation stopping and economy instrumentation

**Changes**
1. Stopping criterion = **novelty saturation**, using D4's *across-iteration* merge fraction against a configurable threshold. Keep `max_iterations` as a hard cap. (Across-iteration is the right signal — within-iteration measures differentiation, not saturation.)
2. Instrument **cost per distinct angle surfaced**. Report cached vs uncached input tokens alongside it.
3. Confirm model tiering end to end against §5.
4. Update `README.md` and `CLAUDE.md` to describe the diverger.

---

## 8. Tuning notes

**The attractor effect is the main thing to watch.** Closing off explored territory (the anti-target list) concentrates ideation onto whatever remains most concrete. That is desirable — it is the anti-target working — but it means *narrowing the space raises within-iteration duplication*, and the counter-pressure has to come from differentiating the calls (D3a), not from loosening the anti-targets. Expect to re-tune after any substantial report change.

**The two merge counts diagnose different failures.** High within-iteration → differentiation too weak (stance/question cycling). High across-iteration → `{existing_angles}` pressure too weak (a prompt problem, not a threshold problem). As of run 2: the first is broken, the second is healthy.

**Thresholds are control parameters, not gauges.** D4's dedup threshold and D8's saturation threshold read the same Jaccard signal. Both should be set from logged numbers. Current evidence supports ~0.22 for dedup; D8's has no measurement yet — take one before setting it.

The D5 judge prompts are the entire quality bar once `req_score` is gone. The machinery is trivial; the wording is the whole game.

---

## 9. Deferred: external retrieval

Q5 originally asked for evidence of post-attendance collaboration, which needs literature data. That has been removed from the report, and retrieval is deliberately out of scope for this fork. When it returns, the architecture should be:

- **Enrichment, not agent capability.** A host-side script (sibling to `anonymize_cbias_data.py`) materialises external data into `inputs/.../Publications/`. Everything downstream works unchanged on local files and the sandbox keeps `--network none`.
- **A structured literature API** (OpenAlex, Europe PMC) beats generic web search — clean co-authorship records rather than prose about papers.
- **Scope is speakers, not attendees.** Programme CSVs retain real names; abstract author names were anonymised away. Roughly 15–20 named people per year.
- **Causality needs a design**: temporal precedence, exclusion of prior ties, and a control group of comparable non-co-attending pairs. Without the control it is an anecdote generator.

This is also the capability the horizon-scanning fork depends on, so getting the pattern right on a narrow checkable question is worthwhile groundwork.

---

## 10. Expectation setting

This will surface a wider, cheaper spread of angles than the converger, some non-obvious — a real improvement over a pipeline that reflects the author's own priors back at them. It will not out-think a domain expert on their own data. Treat it as a fast idea-generator that occasionally surprises, with the human at D7 as the actual evaluation function. Building around that division of labour, rather than trying to automate the judgement away, is what makes the compute worth spending.
