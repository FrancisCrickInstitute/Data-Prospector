# Converger → Diverger conversion plan (rev. 7)

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

**Divergence is solved.** Both axes are healthy and have been for five consecutive runs. Do not spend further effort here.

> **The diversity log and dedup no longer measure the same thing.** `_log_iteration_diversity` uses `_token_set`; `_angle_signature` double-weights `hypothesis`/`variables_involved`. Run 8 capped at 0.16 in the diversity log while dedup found a pair above 0.22. Not a bug — but dedup behaviour can no longer be read off the diversity numbers, and the two must not be treated as interchangeable.

### Live issues

**1. Soundness — partially resolved.** Under the old boolean gate: 0/8 then 1/8 sound, contributing nothing to ranking (structurally the converger's binary `req_pass` problem in new clothes). The three-way verdict is now live and Run 8 returned **0 solid / 6 caveat / 1 unsupportable** — real separation, and the caveat text now exists for D7 to display.

But 6/7 in one bucket means ranking is still driven almost entirely by insight, and `solid` may simply be **unreachable** on n=37–60 respondents with four time points. If `solid` stays empty across the next few runs, treat this as a two-level scale in practice rather than tuning the prompt toward a tier the data cannot support.

**2. Insight discrimination is still unread — not unplumbed.** Per-angle `insight_score` is computed and written to *two* places: `output_dir/surfaced_angles_<ts>.md`, and — because `generate_and_optimize` still returns the ranked block as a string — the misnamed `analysis_script_<ts>.py` that `app.py` writes (a D7 relic). The blocker is that nobody has read them.

**This remains the next number to look at.** Run 8 test pair: `early-bird-uptake-ratio` (conventional stance, derived but simple) should score clearly below `feedback-correlation-themes` (contrarian, structural). If they score similarly, the insight prompt needs work before anything else.

**3. Cross-run memory is still manual, now with a curation aid.** `ticket-type-trend` appeared in four consecutive runs (always Q1 + Conventional); `readability-trend` and `registration-timing` three each.

> **The Q1 attractor is gone, and a new one is forming.** Run 8 produced `early-bird-uptake-ratio` and `registration-lead-time-and-group-size-trend` from the demographics question — both *behavioural* rather than label-counting — so whatever changed in the prompts pushed the conventional stance off the trivially obvious. Meanwhile **LDA appeared twice in Run 8, both depth-first**: the natural successor once TF-IDF and word frequency are on the anti-target list. If an LDA angle gets realised, retire it into Already Explored promptly, or it becomes the next `ticket-type-trend`.

`{existing_angles}` still only persists *within* a run — the report's Already Explored section remains the only persistent cross-run memory, and it's still hand-maintained. D5-calibrate added `_write_angle_dump` so curating that section is a copy-paste from `surfaced_angles_<ts>.md` instead of a manual re-transcription; nothing retires an angle automatically, by design.

**4. Duplicate angle ids — fixed.** Run 7 produced two angles both called `angle-1`. `_ensure_unique_id` (D5-calibrate) now suffixes `-2`, `-3`, ... on collision before an angle reaches the archive.

**5. Caching is unverified.** §4 asks for a single `cache_read_input_tokens` measurement. It has not been taken, so the entire §4 investment is unmeasured. Still an explicit D8 task.

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
| D6 orchestrator | `report` (the TRUE report, not the angle brief), `input_data`, deliverable rubric | the angle being realised (hypothesis/variables/rough_method/why_non_obvious) |
| D6 workers/compiler | existing splits, unchanged | — |
| D6 validator (`validate_realization`) | `report`, deliverable rubric | `claimed_pattern`, script, execution output |

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

**D6 is done (§3).** §10's interim library additions and D4's merge-pair logging (both flagged as outstanding before D6) landed first — the base image now has `scipy`/`scikit-learn`/`nltk`/`seaborn`/`textstat`, and `_dedup_angles` reports which specific pair merged. `insight_score` spread is still worth a deliberate read before leaning further on the ranking (Live Issue 2), but D6 itself is confirmed working end-to-end. One small item from the original D5-calibrate spec remains undone as optional polish: nudging `ANGLE_GENERATION_PROMPT_SUFFIX` toward descriptive slugs (id collisions are already handled mechanically, so this only affects readability, not correctness).

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

**Interim floor raised, pre-D6.** Run 8 (the first with the `requires` field live) measured the gap at numpy/pandas/matplotlib only: exactly one of eight angles ran on the image. `scipy`, `scikit-learn`, `nltk`, `seaborn`, and `textstat` were added to the base image before D6 landed (see below) - the dynamic, build-time-provisioning system described in this section is still not implemented; this was the cheap interim fix only.

When implemented:

- **`requires` field on angles** (add now, in D5-calibrate) — instrumentation first, so the design is driven by what ideation actually asks for.
- **Provision at build time, not run time.** `--network none` forbids runtime installs, so the union of `requires` across the top-k angles resolves into a derived image (`FROM cbias-analysis; RUN pip install …`) before realisation. The build is trusted; execution stays isolated. That distinction is why this is safe.
- **Allowlist package names.** Hallucinated package names are a live supply-chain attack vector — attackers register the plausible-sounding names models invent. Grow the allowlist from observed `requires`.
- **Model weights are not pip installs.** `sentence-transformers` and BERTopic download weights on first use; with no runtime network they fail after a successful install. Baking weights into the image is a much heavier lift and a reasonable place to draw the line.
- **Cheap interim win — done, before D6.** `scipy`, `scikit-learn`, `nltk`, `seaborn` and `textstat` were added to the base image. Small relative to torch, and covered everything ideation asked for on Run 8 - avoided D6 reporting a ~7/8 failure rate that would have been purely provisioning and told nothing about angle quality.
- **`nltk` corpora are not a pip install.** `nltk.download()` fetches stopwords/tokenisers at runtime — the model-weights problem in miniature. Under `--network none` the package installs fine and then fails on first use. Bake the corpora in at build time.

Keep "not realisable" strictly separate from "unsound" in the gallery — the first is an engineering outcome, the second a quality judgement.

---

## 11. Expectation setting

This will surface a wider, cheaper spread of angles than the converger, some non-obvious — a real improvement over a pipeline that reflects the author's own priors back at them. It will not out-think a domain expert on their own data. Treat it as a fast idea-generator that occasionally surprises, with the human at D7 as the actual evaluation function. Building around that division of labour, rather than trying to automate the judgement away, is what makes the compute worth spending.
