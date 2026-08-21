# Diverger plan — closed issue archive

This file holds the full text of **Live Issues that are closed, resolved, or confirmed** — split out of `DEVELOPMENT_LOG.md` to keep the main plan skimmable. Nothing here was deleted or edited; every entry below is moved verbatim, in its original numeric order, from that document's "Live issues" section.

**This is an archive, not a second living document.** `DEVELOPMENT_LOG.md` remains the one place to look for current/open issues, the run log, and every other section. A "Live Issue N — closed, see archive" one-liner in `DEVELOPMENT_LOG.md`'s Live Issues section is the index back to each entry below; there is no reverse index maintained here beyond issue number order.

---

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

**Run 33: the double-truncation path finally fired live, and it did the right thing — but it reveals the ladder top is now the binding constraint, not the transport.** `relative-dissatisfaction-item-networks` (an **8-function** architecture, the second-largest in the log after Run 29's 11) reached the compiler and truncated at both 16384 and then the doubled 32768, raising the exact message this entry predicted: *"Response truncated at max_tokens on both attempts (final budget=32768) - the model was still mid-generation when the token budget ran out, twice in a row."* That is the outcome the fix was written to produce — a loud, correctly-labelled failure at the compile stage, surfaced as `realization_error` with `stage='compile'`, rather than a mid-token `SyntaxError` that would have cost a compile attempt and misled the next repair. The untested branch is now tested and behaves as designed.

**But the failure itself is a new signal, not a happy confirmation.** Live Issue 23 removed the SDK's non-streaming ceiling by switching to `client.messages.stream(...)`, so the only remaining ceiling is the *budget* itself — and the compile-retry ladder tops out at `max_tokens * 2` = 32768. Run 33 hit that ceiling on the run's largest architecture. Run 29's 11-function architecture passed first time only by luck of the model's verbosity on that particular generation; Run 33 shows that when the compiler is asked to assemble a large design in one response, 16384→32768 is not reliably enough. **This is a live-data instance of the exact concern Live Issue 23's own entry flagged** ("raising budgets is no longer available as a remedy — the ladder now tops out"). **Resolved (rev. 52) by the first of the two candidate remedies: the compiler's explicit `max_tokens` is now 32768 (retry 65536), since streaming makes that sendable and the compiler is DeepSeek-routed (§5) so the cost stays cheap.** The structural alternative — cap/split large architectures in the orchestrator — is deliberately *not* taken, because the failure is verbosity-dependent (Run 29's 11-function design passed first time) rather than a deterministic function-count ceiling; revisit it only if a design still truncates at 65536.

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


**28. The `realization_error` tier asserts a cause it cannot know (Run 28).** `output.py` prints this above the fifth tier, unconditionally:

> _The script compiled, ran in the sandbox, and produced real output; only the final judging call failed. Not a provisioning gap - judge these yourself from the script/image(s) below._

That is true only when the failure happened at the **validate** stage. Run 28's `speaker-attendee-sector-alignment` failed at `stage='compile'`, so no script was written, nothing ran in the sandbox, and the entry carries **no script or image links** — the reader is told to judge from artifacts that do not exist. The parenthetical inside the entry records the correct stage, so the entry contradicts itself.

**This is Issue 21's original defect one level up.** Issue 21 was about a tier asserting the wrong *category* of failure; this is a tier asserting the wrong *stage* of it. The plan has now made the same mistake three times (Issue 21's `not_realisable` mislabelling, Issue 27's "aborted early" log, this) — **wording that describes the common case and is silently wrong in the others.**

**Why it matters more than one entry suggests.** Run 28 was lucky: the balance ran out on the last compile, so one angle was affected. Had it run out earlier, all four realisations would have failed identically and the gallery would have carried four entries each confidently claiming a compiled, executed script. The console makes an account failure obvious; the gallery is what gets read afterwards.

**Fix:** branch the wording on `stage`. For `stage='validate'`, the current text is correct. For earlier stages, say what is true — the pipeline failed before a script was produced — and suppress the "judge these yourself from the script/image(s) below" instruction when there are no artifacts to judge.

**FIXED (rev. 41).** `stage` is no longer trapped inside the free-text `realization_feedback` string — `_run_one_design`'s exception handler (`realization.py`) now returns it as a structured `error_stage` field too, threaded onto the angle dict by `generate_and_optimize` (`pipeline.py`). `output.py` branches on it at both sites that were asserting the unconditional claim:
- **Per-entry Note (`_gallery_entry`):** the original "the script and image(s) below are real; judge them yourself" wording is now used only when `error_stage == "validate"`. Two other cases, both new: if an earlier stage broke but a script still exists on disk (the edge case the original fix note didn't consider — a *later* compile attempt can raise after an *earlier* one already produced text, leaving a real but never-executed file behind), the Note says explicitly it's "from an earlier, unverified attempt, not a confirmed run"; if nothing survived at all, it says there is no script or output to show, rather than inviting the reader to look "below" at nothing.
- **Tier intro (`_write_gallery`):** dropped the blanket per-tier claim entirely, since a single run's `realization_error` tier can hold entries at different stages simultaneously (a mixed tier makes any one blanket sentence wrong for at least one entry) — it now says only that this is an infrastructure failure, not a provisioning gap, and points to each entry's own Note for specifics.

Verified offline (mocked `_write_gallery` call, three synthetic angles covering `error_stage="validate"` with real artifacts, `error_stage="compile"` with nothing produced, and `error_stage="compile"` with a stale unverified script) — all three renders came out as intended, including the tier intro no longer containing the old "script compiled, ran in the sandbox" claim; deleted after passing.

**CONFIRMED (Run 33).** Run 33 produced the exact case this entry has been waiting for — a `realization_error` at `stage='compile'` with nothing produced — and the gallery rendered it correctly. The tier intro reads *"How far it got before breaking varies per angle; see each entry's Note below"* (no blanket claim), and the entry Note reads *"the pipeline failed before a script was produced (at the 'compile' stage) - there is no script or output to show or judge for this angle."* That is the "no script or output to show" wording firing for real, not under a mock. **Closed.** (The one remaining branch — `error_stage="compile"` with a *stale* unverified script left on disk by an earlier attempt — remains unexercised, but it is a rare edge case and the wording was verified offline; do not keep this entry open for it.)


**30. Library versions are neither pinned nor described, and the same API-drift failure keeps recurring (Runs 22, 30).** Two of four compiles in Run 30 failed attempt 1 on the identical error:

```
ax.boxplot(box_data, labels=[...])    -> matplotlib deprecation
plt.boxplot(dist_data, labels=...)    -> matplotlib deprecation
```

matplotlib renamed `labels` to `tick_labels` in 3.9. Both recovered on attempt 2, so the cost is two wasted compile attempts rather than a lost angle — but it is repeated, predictable, and cheap to prevent. Run 22's boxplot deprecation was the same thing.

**This is the third instance of one failure shape, and naming that is the point of the entry.** §15's A2 was the data's *value* vocabulary, A5 the *response* vocabulary, and this is the library's *API* vocabulary — in every case the model writes against an assumed vocabulary that the description it was given does not pin down. §15.7's rule applies unchanged: **fix the description, not the model** — sharpened in rev. 46 to *derive* the description where it can be derived (Live Issue 31). Note this issue is the exception that proves the boundary: library versions are **not** derivable from the data, so a hand-written note pinned to a pinned Dockerfile is the correct instrument here.

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


**31. IMPLEMENTED — PROVISIONALLY CONFIRMED (Run 32). The strongest single piece of evidence in this document that the derive-don't-write approach works.**

Run 32 started at 09:10, four minutes after the profile commits landed at 09:06, so it is the first run with `data_profile` threaded into the realisation prefixes.

**The decisive evidence is not the clean-compile count — it is the role taxonomy.** `role-experience-boundary-blurring` hand-wrote a role→home-domain map, and every one of its nine keys matches a real value in the feedback data exactly:

```
Image/data analyst · Software engineer · Facility director/manager · Facility staff
Principal investigator · PhD student · Postdoctoral fellow
Research scientist/associate/staff · None of the above
```

**This is the same angle that failed as §15 A4 in Run 27**, where the model invented `["life scientist", "software developer", "computational analyst", "microscopist", "funder/manager"]` and rendered the life-scientist row unreachable. The taxonomy is idiosyncratic enough that guessing it correctly is implausible; the profile is the only new input. **A4's mechanism appears closed.**

Corroborating, but weaker on its own:
- The multi-select delimiter is right first time — `exp_raw.split(";")` against real values of the form `Chemistry/Biochemistry;Cell/Molecular Biology;Image Analysis/Processing;`. Pre-profile scripts sniffed for it or tried `re.split(r"[;,|\n,]")`.
- **4 of 4 compiles passed on attempt 1/3**, with no scale-detection errors, no unmapped values, and no format assumptions failing.

**Why this is provisional and not closed.** Runs 28 and 29 were also fully clean *before* the profile existed, so a clean-compile count alone proves nothing — only the role-key match is evidence a count could not produce. **The decisive test written into this entry is still unexercised:** no Run 32 angle touched the abstract `Keywords` field, whose two incompatible formats remain in neither `DOMAIN_NOTES` nor any patch. Leave open until a run handles that, or another quirk documented nowhere, unaided.

**Design notes worth keeping from the implementation**, both of which are judgement calls a naive version would have got wrong:
- **The cardinality cutoff is targeted, not arbitrary.** The failure class this profile addresses — an assumed response or category vocabulary — only ever occurs on low-cardinality columns, so enumerating free text would cost tokens for no benefit.
- **Programs is deliberately excluded from per-column enumeration.** It is headerless and ragged, so a column position means different things on different rows and there is no real category vocabulary to profile; and with ~20–30 rows per file every column falls under the cutoff by row-count coincidence, so the naive version dumped every speaker name and talk title verbatim. **No A/B/C-class failure in §15 has ever involved Programs**, which is the right test for whether a data source needs profiling at all.

**RUN 34 — an unclaimed benefit: the profile improves the *soundness judge*, not just the compiler.** `registration-block-size` was ruled **unsupportable** on the grounds that *"there is no order ID to group rows into orders, and available ticket_type_counts suggest quantities are predominantly 1 per row"* — both facts derived from the profile rather than guessed. Issue 31 argued the profile would stop the compiler writing against imagined data; it also lets the judge kill an angle *before* realisation for a reason it could previously only have discovered by paying for a run. That is a second, cheaper payoff and it should be counted when weighing the ~7.4k token cost.

**RUN 34 — the boundary of what the profile fixes is now visible.** §15 B5: a script silently skipped all 21 Likert columns because it gated on `is_object_dtype` and pandas loads them as `StringDtype`. The *values* were correct and profile-derived; the *dtype API assumption* was not. **The profile closes class A; class B remains open** and is now the larger of the two.

*Original entry follows.*

**31 (original). `DOMAIN_NOTES` is being hand-maintained to describe facts a script could derive — and it keeps falling one gap behind (Runs 24–31).** Two more instances in Run 31, both of the §15 class-A shape, both found by the model failing rather than by anyone noticing in advance:

- **`"Not Applicable"` also appears on the duration scale.** `DOMAIN_NOTES` lists it under the agreement scale only, so `satisfaction-driver-shift` raised on attempt 1: `Cannot determine response scale for column 'The duration of the poster sessions was...': ['about right', 'not app...']`. Verified: **7 of 8 duration columns across 2024/25 carry it** (all four in 2025; all but "average duration of the sessions" in 2024).
- **The abstract `Keywords` field has two incompatible formats.** `stakeholder-training-hybridity` used `ast.literal_eval` and died on it three times. Both formats are real:
  ```
  2022:  Keywords: ["Segmentation","Object Tracking","3D/4D/ ... nD Data\n"]
  2024:  Keywords: image quality, fluorescence microscopy, Analysis
  ```
  A JSON-style list in some years, plain comma-separated text in others. `DOMAIN_NOTES` describes the abstract files as `Label: value` lines and says nothing about this.

**The pattern is now unmistakable and the remedy needs to change shape.** Rev. 43 patched A2/A5, rev. 45 patched the library versions, and each fix worked *on its first run* — the approach is sound. But every one was a human transcribing, by hand, a fact a `df.unique()` call would have returned, and the list has never once been complete. **§15.7's rule should be sharpened from "fix the description" to "derive the description".**

**Root cause, stated plainly: the model never sees the data.** `compile_script` writes blind, Docker runs the result, and only the outcome returns. There is no inspect-then-write loop anywhere in the pipeline. `DOMAIN_NOTES` is not compensating for a model limitation — it is a hand-written substitute for an inspection the architecture never offers.

**Proposed fix: a mechanical data profile, generated per run and prepended to the compiler's cached prefix.** Pandas plus a file walker, no model in the loop, so it cannot hallucinate; regenerated from the data each run, so it cannot go stale — which is precisely the failure mode the hand-written notes keep hitting. Per CSV: column names verbatim, dtype, null count, and the full value set for columns under a cardinality cutoff. Per abstract folder: the label inventory with one sample value each.

**Measured on the current dataset: ~7,400 tokens for all four years and all four data types** at a cutoff of 25 distinct values. It belongs in the §4 cached prefix, so it is paid once per stage rather than per call.

**What it would have caught — the entire recurring category:**

| §15 entry | What the profile shows |
|---|---|
| A1 decoy columns | `Points - <q>` listed at 100% null |
| A2 numeric satisfaction | `[int64]` dtype |
| A3 `"academic"` absent from its own keyword list | ticket-type values listed verbatim, including `Academic` |
| A4 unreachable role category | `best describes you` values listed — *Facility staff*, *PhD student*, … |
| A5 `"Not applicable"` | present in the value set |
| Duration NA (this issue) | present in the value set |
| `Keywords` format (this issue) | both formats visible side by side |

**The boundary this implies, and it is the useful part of the proposal.** A profile answers *what is in the data*. `DOMAIN_NOTES` should then answer only *what it means and what has already been tried*:
- **Semantics no profile can derive** — that `"The ticket prices were appropriate"` and `"...were too high"` are one construct with inverted polarity. The profile lists both column names; it cannot tell you they are the same question.
- **Provenance** — "Eventbrite may split orders into one row per ticket" is about what a row *represents*.
- **Absence** — which fields anonymisation removed. A profile of what is present says nothing about what is gone.
- **The anti-target list** — pure judgement.

Everything the last five live issues bolted on was the first kind, which is why the file has felt increasingly like the wrong shape.

**Keep the fail-loud instruction alongside it.** Run 31 is the evidence: `satisfaction-driver-shift` *raised* on an unrecognised scale rather than silently dropping it — the A5 patch's instruction inducing correct behaviour on incomplete information. A profile stops the model guessing; fail-loud keeps the script honest when the profile is incomplete anyway. Complements, not alternatives.

**Do NOT reach for the two-phase version yet.** The maximal answer is a throwaway inspection script compiled and run in Docker, whose output feeds the real compile — a genuine read-eval loop, strictly more faithful, and it doubles the Docker round-trips and adds a stage. §13's rule applies: a static profile gets most of the value at a fraction of the cost. Revisit only if profiled runs still hit this class.

**Two honest risks:**
1. **The cheapness claim rests on caching that has never been measured** (Live Issue 5). 7.4k tokens per stage is fine if the prefix is hitting cache and material if it is not. **This change is the one that makes §4's outstanding measurement worth taking first.**
2. **The profile puts real data values into the prompt.** Fine for anonymised CBIAS; a config with sensitive data would need a redaction pass or a cardinality-only mode.

**Verify:** a run against a *deliberately* undocumented quirk — the `Keywords` format split is a ready-made test, since it is currently in neither `DOMAIN_NOTES` nor any patch — in which the compiler handles it correctly with no prior note.

**FIXED (rev. 47), the proposed mechanical profile, not the two-phase alternative.** `PipelineConfig` gained an optional `data_profile(data_dir) -> str` field (`None` by default — `bioimage`/`trello` unaffected); `cbias_config.generate_data_profile` implements it with pandas alone, no LLM: verbatim column name, dtype, null count, and the full value set for any column at or under the 25-distinct-value cutoff the ~7,400-token estimate above was measured at, for every Attendees/Feedback CSV; one real sample value per field label per Abstracts year-folder (this is what surfaces the `Keywords` format split without anyone transcribing it); Programs deliberately gets row/column counts only — see the rev. 47 top-of-document note for why full enumeration was tried and reverted (headerless-and-ragged plus small per-file row counts meant it silently dumped every speaker name and talk title verbatim, at real token cost, for a data type no A/B/C-class failure has ever touched). Threaded into the same three cached prefixes `domain_notes` already reaches — orchestrator, worker, compiler — never ideation, preserving the `available_libraries` precedent that realisation constraints don't narrow ideation.

**Directly re-verified against `inputs/cbias_data_anon/`, not just offline-mocked, and both of this issue's own Run 31 gaps are visible with nothing hand-written:** the duration scale's `Not Applicable` appears in the enumerated value list for every duration column, and both `Keywords` formats (2022/2023 JSON-list, 2024/2025 comma-text) appear side by side across the four Abstracts sections — exactly the "verify" case above, satisfied without adding either fact to `DOMAIN_NOTES`. Also directly confirms A2 (`int64` on the satisfaction column) and A3/A4 (ticket-type/role values enumerated) fire the same way. Total profile size: ~7,100 tokens, in line with the estimate. Offline: a mocked `_run_one_design` run confirmed the profile reaches all three prefixes and that the empty-string default (the `bioimage`/`trello` case) formats with no leftover `{data_profile}` placeholder — deleted after passing.

**`DOMAIN_NOTES` is untouched by this fix — additive, not a replacement**, matching the boundary this entry itself proposed: the profile answers "what is in the data", `DOMAIN_NOTES` keeps the semantics/provenance/absence/anti-target-list job a profile can't do. The fail-loud instruction this entry said to keep alongside the profile is likewise untouched.

**Two things this fix does NOT resolve, both already flagged above:** the caching-savings claim (this doubles as the reason to finally take the Live Issue 5 measurement — three new cached prefixes now carry ~7k more tokens each, cached or not is currently unmeasured) and the sensitive-data risk (moot for anonymised CBIAS, real for any future config with unredacted data).

**Needs a live run to confirm**, and the meaningful confirmation is narrower than "did it run" — it's whether a realised angle touching a duration-scale column or `Keywords` gets it right with **no** hand-written note about either, the same bar this entry's own "Verify" line set.


**33 (= §15 B5, Run 34). A dtype gate that silently skips everything.** `response-profile-archetypes` wrapped Likert scale-detection in `if pd.api.types.is_object_dtype(series):`; the Feedback CSVs load as pandas `str`-dtype columns, for which this returns `False`, so all 21 string columns were skipped and only the single `int64` satisfaction column reached the numeric branch — clustering ran on one item instead of the multi-item profile the angle described. Caught by the judge from two heatmap panels showing identical above/below-median lists, without seeing the code. **Live Issue 31's `data_profile` could not have prevented this** — the *values* it derived were correct; the *dtype API assumption* was wrong, which is a class-B (environment-assumption), not class-A (data-content), failure. See `§15.2` for the full entry.

**Both open questions from the original write-up are now resolved, by direct check rather than assumption.** First: is this a profile-rendering problem, or a genuinely new gap? `_profile_csv` renders dtype via plain `f"[{series.dtype}, ...]"`, and a live check against this project's pinned pandas (3.0.3 locally, matching the `3.0.5` pin) confirms `str(series.dtype)` for a `read_csv`-inferred text column prints the literal word `str` — about as legible a label as the profile could produce. **The information was present and correctly labelled; the gap is a coding-pattern pitfall, not a profile-format issue** — the same shape as B4a, not a new class of failure. Second: what actually caused it, and is it worth a numbered issue? Confirmed directly: `pd.api.types.is_object_dtype()` returns `False` and `pd.api.types.is_string_dtype()` returns `True` for these columns. Pandas 3.0 gave `read_csv`-inferred text columns their own native `str` dtype, distinct from the legacy `object` dtype it used to assign — and pinning to `pandas==3.0.5` (Issue 30's own fix) is what made this reachable at all, making B5 a plausible second-order regression from Issue 30 landing. **Graduated to this numbered issue**, matching the B4a → Issue 30 precedent exactly.

**FIXED (rev. 56), same fix shape as Issue 30 — a targeted `AVAILABLE_LIBRARIES` addition, no pipeline code touched.** `cbias_config.py`'s pandas bullet now states the `str`/`object` dtype split and instructs `pd.api.types.is_string_dtype()` over `is_object_dtype()` alone for text/categorical detection, right alongside the existing `applymap` note it shares a root cause class with. Verified offline: `ast.parse` clean, a real `import cbias_config` succeeds, and the rendered `AVAILABLE_LIBRARIES` string reads correctly with no formatting break. **Needs a live run to confirm** — the meaningful case is a future angle that does dtype-based text-column detection and gets it right with no dedicated patch, the same bar Issue 30's own confirmation used.

**CONFIRMED (rev. 59, Run 36). Closed.** Docker came back up for Run 36 (Run 35 had been the Docker-unavailable run) and the fix held on its first live exercise: the run log reports the Likert item count for this angle shape going from 1 (Run 34's silent skip) to ~18 — the full multi-item profile the angle always described, with no dedicated patch beyond the `AVAILABLE_LIBRARIES` note. Same confirmation bar Issue 30 used. Moved here from the Live Issues "Open" section (rev. 59) once the run log already carried the confirming evidence — a documentation-only cleanup, no code touched.


**5. Caching is unverified.** §4 asks for a single `cache_read_input_tokens` measurement. It has not been taken, so the entire §4 investment is unmeasured. Still an explicit D8 task.

**MEASURED (rev. 51, Run 33) — closed, with a sharper answer than the yes/no it was framed as.** The first live read of the cache fields is in the Run 33 console, and it splits cleanly by provider:

- **Anthropic behaves exactly as §4 predicts.** The Opus judges write `cache_write=6246` on their first 8 calls, then every subsequent call reads `cache_read=6246` (two of the calls read `6254` — the suffix-differing pair, since the individual angle lives in the suffix). The orchestrator (`cache_write=20218`) and validator (`cache_write=2762`) prefixes show the same write-then-read shape. This is the two-phase behaviour the whole `cache_prefix` convention exists to produce: the shared prefix is paid once, every reuse is a cache read.
- **DeepSeek reports a nonzero number, but it is not the breakpoint convention.** Every DeepSeek call shows a flat `cache_read=1280` from the very first call of the run — ideation iteration 1 included, before any prefix could have been written. That cannot be the explicit `cache_control` breakpoints this pipeline plants. It is almost certainly DeepSeek's endpoint reporting its own automatic prompt-cache metric for the system/prefix portion it deduplicates server-side, independent of the explicit breakpoints. So the "does DeepSeek report real cache numbers" question resolves to a *distinction*, not a yes or a no: **it reports a real number, but the number does not mean what `cache_read` means for Anthropic**, and the two must not be read interchangeably in a live console.
- **The one measurement the entry actually needed to settle does hold.** Within `relative-dissatisfaction-item-networks`' compile-retry loop the worker/compiler prefixes show `cache_read=12928` on reuse — the flat 1280 DeepSeek baseline *plus* the accumulated cached prefix (which carries Live Issue 31's ~7k-token `data_profile`). So the profile is not repaid per call: it is paid on the first (parallel, fan-out-defeated) use and read from cache thereafter, exactly the "paid once per stage, not per call" property §4 and Live Issue 31's cheapness claim both rest on.

The material consequence is the same one the entry's original framing already anticipated: the caching investment is real and working for the Frontier judges (where the shared-prefix saving is on the most expensive tier), and the `data_profile` addition is genuinely cached, so Live Issue 31's token cost is bounded rather than recurring. The DeepSeek `1280` figure is instrumentation noise to be aware of, not a caching failure — do not read it as "caching only saves 1280 tokens" any more than as "caching is broken."

**INSTRUMENTED (rev. 50) — not yet MEASURED.** `llm_call` (`llm.py`) now prints `usage.input_tokens`/`output_tokens`/`cache_read_input_tokens`/`cache_creation_input_tokens` on every successful call, unconditionally — no flag, matching the pipeline's existing per-stage console verbosity rather than adding a special debug mode. This is deliberately the minimal version §4 asked for (a measurement, not an accounting system): no return-type change to `llm_call` (still returns a plain `str`, so none of its ~15 call sites needed touching) and no run-level aggregation — a human tailing the console can eyeball whether `cache_read` climbs across a run's repeated-prefix calls (ideation, D5 judging, D6 orchestrator/workers/compiler), which is the actual question this entry asks. Handles the one real risk directly: `worker_model`/`compiler_model` are DeepSeek-routed (§5), and DeepSeek's Anthropic-Messages-API-compatible endpoint might not populate `cache_read_input_tokens`/`cache_creation_input_tokens` in its response the way Anthropic's own API does — verified this can't crash the log line, since `anthropic.types.Usage` defaults both fields to `None` (not a missing attribute) when a provider's response JSON omits them, so `usage.cache_read_input_tokens or 0` degrades to a legitimate "0" reading rather than raising. Verified offline with a mocked `client.messages.stream` for two cases: an Anthropic-shaped response with real cache numbers, and a DeepSeek-shaped response with both cache fields `None` — both logged correctly, neither raised. Deleted after passing, per convention.

**RESOLVED by Run 33 (the "actual next step" above), with the answer being the provider distinction above rather than a yes/no.** The original open question — "does DeepSeek report real cache numbers, or silently always read 0" — is settled: it reports a nonzero `cache_read`, but that number is its own internal prompt-cache, not the explicit-breakpoint convention the pipeline's `cache_prefix` argument and this entry's Anthropic numbers assume. See the "MEASURED" note directly above for the two-number table.

