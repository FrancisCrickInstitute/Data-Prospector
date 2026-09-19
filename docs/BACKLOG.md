# Backlog

Deferred, not-yet-scheduled work items, split out of `DEVELOPMENT_LOG.md` (rev. 68) — see that document's
rev. 68 banner for why and what deliberately stayed behind. **Nothing here is scheduled, and nothing
already implemented and working should be touched on account of anything in this file.** It exists so
ideas are recorded rather than lost — the same role §9/§10/§16 and the D8/D-simplify subsections played
inside the main log before this split. Everything below was moved verbatim; nothing was summarised or
reworded away, beyond updating stale cross-references to the log's own rev. 68 rename
(`DIVERGER_PLAN.md`/`DIVERGER_PLAN_ARCHIVE.md` → `DEVELOPMENT_LOG.md`/`DEVELOPMENT_LOG_ARCHIVE.md`) and
making section-number references explicit about which file they point into, since a `§N` reference is now
potentially cross-file. `Live Issue N` / run-number / `D<n>`-label references are unchanged — those
already work the same way whichever file holds the surrounding prose, exactly as they do for closed Live
Issues pointing at `DEVELOPMENT_LOG_ARCHIVE.md`.

---

## 1. Deferred: external retrieval

Q5 originally asked for evidence of post-attendance collaboration, which needs literature data. Removed from the report; retrieval is out of scope for this fork. When it returns:

- **Enrichment, not agent capability.** A host-side script (sibling to `anonymize_cbias_data.py`) materialises external data into `inputs/.../Publications/`. Everything downstream works unchanged on local files and the sandbox keeps `--network none`.
- **A structured literature API** (OpenAlex, Europe PMC) beats generic web search — clean co-authorship records rather than prose about papers.
- **Scope is speakers, not attendees.** Programme CSVs retain real names; abstract author names were anonymised away. Roughly 15–20 named people per year.
- **Causality needs a design**: temporal precedence, exclusion of prior ties, and a control group of comparable non-co-attending pairs. Without the control it is an anecdote generator.

This is also the capability the horizon-scanning fork depends on, so getting the pattern right on a narrow checkable question is worthwhile groundwork.

---

## 2. Deferred: library provisioning

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
1. **The pipeline behaved correctly.** The FAIL reason is logged, the retry is logged, the numbers are in the gallery, the script is linked. Everything a human needs to notice this is already on screen — which is precisely why rev. 24 rejected adding a fidelity gate (see `DEVELOPMENT_LOG.md` §7's "Deliberately NOT on this list").
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

## 3. D8 — Saturation stopping and economy instrumentation

**Changes**
1. Stopping criterion = **novelty saturation**, using D4's *across-iteration* merge fraction against a configurable threshold. Keep `max_iterations` as a hard cap. (Across-iteration is the right signal — within-iteration measures differentiation, not saturation.) Dedup has now fired in Runs 8 and 11 (both single across/within merges), so a measurement exists but the *fraction* is still tiny — take a run with more iterations before setting the threshold.
2. **Verify caching** (`DEVELOPMENT_LOG.md` §4) — the outstanding one-off measurement.
3. Instrument **cost per distinct angle surfaced**, reporting cached vs uncached input tokens alongside it. Replaces `req_score` as the number to tune against.
4. Confirm model tiering end to end against `DEVELOPMENT_LOG.md` §5.
5. ~~Update `README.md` and `CLAUDE.md` to describe the diverger.~~ **Moved to D-consolidate**, and promoted — this was the lowest-numbered item of a deferred step, and it turned out to be the highest-leverage defect in the repository. See `DEVELOPMENT_LOG.md` §12.1.

---

## 4. D-simplify — Deferred: re-examine the design against external practice

**Status: BACKLOG. Nothing here is scheduled, and nothing already implemented and working should be touched on account of it.** This step exists so that observations from outside the project are recorded rather than lost, and re-read at the point where the pipeline is next opened up anyway. Two sources so far: Anthropic's [*Building effective agents*](https://www.anthropic.com/engineering/building-effective-agents) (`DEVELOPMENT_LOG.md` §13) and the Crick's own [`lyra`](https://github.com/FrancisCrickInstitute/lyra) agentic-primitives repo (`DEVELOPMENT_LOG.md` §14).

**Run it after D-consolidate, and not before.** D-consolidate is documentation and dead weight — no behaviour change. Everything below changes behaviour, and none of it is fixing something that is currently broken.

#### The standing rule that comes out of `DEVELOPMENT_LOG.md` §13, and applies to every other step

**Transparency machinery is not complexity, and must not be stripped as though it were.** The post's second principle is to show the planning steps explicitly. A large part of the growth from 811 to 1681 lines is exactly that: the five-status vocabulary, `pattern_reasoning` on the console, per-attempt FAIL logging, `stage` tracking, the tiered gallery. `DEVELOPMENT_LOG.md` §12 counted those lines as weight without asking what they bought, and that was a misreading. **Any future cleanup that would make the pipeline less legible from the outside is a regression, whatever it does to the line count.**

#### Items

**1. The agent–computer interface — the biggest unexamined surface, and the reason this step exists.**

Appendix 2 of the post reports that building the SWE-bench agent involved more time optimising tools than the overall prompt, and advises keeping formats close to what the model has seen naturally, with no formatting overhead.

Diverger's ACI is its XML schemas — `<task>` blocks nested inside `<tasks>`, alongside `<analysis>`, all carrying free prose. Three symptoms of one under-examined interface:
- Run 22: `Failed to parse <task> XML: mismatched tag: line 10, column 419` (recovered).
- Run 24: `Failed to parse <task> XML: mismatched tag: line 10, column 527` (recovered). Both failures land in the free-prose `<description>` field at a high column offset — consistent with the model's own prose containing characters the parser cannot take, which is exactly the "formatting overhead" the post warns about.
- Live Issue 18: tolerate formatting drift in the angle schema.
- Live Issue 20: `<pattern_outcome>` parse fallback to the conservative default.

**And the interface is wider than the XML.** Live Issue 25 established that `DOMAIN_NOTES` — the pipeline's description of the data to every worker and compiler call — is equally load-bearing and has never had comparable scrutiny: one wrong line in it produced effectively identical failures in two independently generated scripts across two runs. `DEVELOPMENT_LOG.md` §15 classes A and B are almost entirely this. When this item is next opened, the data description belongs in scope alongside the schemas.

None of these is currently hurting a run badly enough to act on — the recovery paths work, which is why this is deferred. But they are the same problem seen three times, and the post says this is the surface that repays attention most. **When it is next worth opening: consider whether nested XML with prose inside is the right format at all**, versus something flatter with less escaping burden. Do not start by tuning the parser again.

**2. Dedup: delete or demonstrate — see Live Issue 24.** The post's rule is to add complexity only where it demonstrably improves outcomes. Dedup's original justification (saving judging cost) was removed when D6-fix moved judging before it, and no replacement justification was ever established. Issue 24 carries the reframed decision; this item exists only to record why the standard changed.

**3. D8 is where this pipeline stops being a workflow.** The post's architectural line is between *workflows* — LLMs orchestrated through predefined code paths — and *agents*, which direct their own processes. Diverger is unambiguously a workflow today, and that is a deliberate strength, not an accident.

**Saturation stopping is the first item on the plan that crosses the line**: it hands the system the decision about how many iterations to run. The post notes agents bring higher cost and the potential for compounding errors. So D8 item 1 gains a precondition: **the fixed `max_iterations=2` is the baseline any dynamic criterion must beat**, measured on realised-angle yield, not on merge fractions. If a saturation rule cannot be shown to beat "just run two", the honest answer is to keep the constant. Run 22 already established that iteration 2 earns its keep, which is the number to beat.

**4. Frameworks (LangGraph and similar) — revisit at D8, not before.**

The question was raised directly: would a graph runtime simplify this code? **Assessed and deferred, with a specific trigger condition rather than a flat no.** LangGraph's principles — explicit state, no hidden control flow, low abstraction — are good ones, and largely ones this pipeline already follows.

*Why not now.* Four reasons, in order of weight:

- **It would relocate code, not reduce it.** Measured at `d0cd5d3`: orchestration is ~364 of `pipeline.py`'s 1803 lines, and not all of that is sequencing (`generate_and_optimize` also does result assembly, tier bucketing, logging, file writing). A graph runtime would own perhaps 150–200 lines, replaced by state schema, node definitions and edge wiring of comparable size. The other ~1900 lines across `pipeline.py` and `prompts.py` are domain logic — prompts (466), the realization chain (396), gallery writers (240), ideation (184), Docker (134), parsing (76), judging (76) — none of which a framework touches.
- **`llm_call` does four custom things that do not map onto a framework's LLM node.** `DEVELOPMENT_LOG.md` §4's `cache_prefix` breakpoint convention; the retry-at-double ladder for thinking-budget exhaustion; streaming (Issue 23); and two-client routing for DeepSeek, which is what makes `DEVELOPMENT_LOG.md` §5's model tiering possible. You would wrap the existing `llm_call` in a custom node and keep all 118 lines — the framework *and* the code.
- **Debuggability, and this is not hypothetical here.** Issues 21 and 23 were diagnosed by reading `asyncio.gather`'s exception semantics directly and by reasoning about where a `max_tokens * 2` retry sits relative to an SDK guard. Issue 21 took two rounds *with* full visibility of the transport. A runtime layer puts "which of four call sites raised" one step further away.
- **It cuts against D-consolidate.** A migration executed by an agent reading a `CLAUDE.md` that describes the converger would be strictly worse than no migration.

*The trigger condition.* Graph runtimes earn their keep on **cycles and dynamic routing**. Diverger has neither: a straight line with one fan-out. If D8's saturation stopping grows into genuine dynamic control — choosing which guiding questions to pursue, re-ideating against what has been learned, routing between realise-now and refine-first — the topology acquires cycles and the case becomes strong rather than weak. **Revisit at D8 and let the answer be determined by whether cycles actually exist, not by preference.** This is the same crossing point as item 3.

*Two ideas worth stealing now, without the dependency:*
- **Explicit typed run state.** State is currently dicts threaded through `generate_and_optimize` — `angle_records`, `judgments`, `realizations` — assembled ad hoc. A single `@dataclass RunState` (~40 lines) would make the pipeline's shape legible in one place. Arguably a better version of D-consolidate item 4 than the module split, since it clarifies the data flow rather than relocating functions.
- **Checkpointing.** A run is ~110 calls. Persisting the judged archive to JSON with a `--resume` flag (~50 lines) captures most of what a framework's durable execution would give, and the angles are already independent so a failure costs one angle rather than the run.

**5. Adopt an explicit run-state contract (from `lyra`, `DEVELOPMENT_LOG.md` §14).**

`lyra`'s Python conductor carries an *Information Passing Contracts* table naming exactly what each stage hands the next, under the instruction to assemble the packet explicitly rather than let the receiving agent infer it. Diverger threads bare dicts — `angle_records`, `judgments`, `realizations` — through `generate_and_optimize` and assembles them ad hoc.

This is the same idea as the typed `RunState` under item 4, arrived at independently and by a different route, which is the main reason to take it seriously. **Note it is achievable in two ways and they are not equivalent:** a `@dataclass RunState` makes the contract executable and impossible to drift from; a table in `CLAUDE.md` makes it readable and free. Given D-consolidate item 1 is rewriting `CLAUDE.md` anyway, the table is close to zero marginal cost and should probably come first, with the dataclass as the follow-up if the table proves it earns its place.

**6. Automate the template-sanity check instead of fixing leakage once (from `lyra`, `DEVELOPMENT_LOG.md` §14). The highest-value item in this step.**

`lyra`'s hooks roadmap records an audit finding that a repo positioned as reusable bundles had hardcoded specific project names (`polaris`, `sequencing-demux`) throughout its agents and instructions, and concludes that the most valuable hook is not a workflow-enforcement one but a **template-sanity checker** that blocks commits reintroducing project-specific references.

**That is `DEVELOPMENT_LOG.md` §12.3, discovered independently by another team at the same institute, with a better answer than this plan currently has.** D-consolidate item 3 fixes diverger's leakage *once, by hand*: the vestigial `bioimage`/`trello` configs, the broken default entrypoint, the README's domain-agnostic claim. Nothing stops it recurring — and the history says it will, because 24 runs of CBIAS-driven tuning is exactly the pressure that put `DOMAIN_NOTES`, the anti-target loop, and the 0.22 dedup threshold where they are - the same pressure that produced a guiding-question-match threshold for Issue 24 before it was tried and reverted (rev. 29).

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

---

## 5. Deferred: per-run token-usage summary, by model and stage

User-requested (rev. 67). Not started — nothing below is implemented; this is a to-do, parked the same way the other items in this file hold not-yet-scheduled ideas.

**The ask:** a summary of how many tokens a run actually used, broken down by model and by pipeline stage, surfaced somewhere in the written outputs — the gallery itself, or a sibling file alongside it (the way `surfaced_angles_<ts>.md` sits next to the gallery now) — not just visible transiently in the console.

**What already exists to build on.** Live Issue 5 (closed, `DEVELOPMENT_LOG_ARCHIVE.md`) instrumented exactly the per-call numbers this would need: `llm_call` (`llm.py`) already prints `input_tokens`/`output_tokens`/`cache_read_input_tokens`/`cache_creation_input_tokens` unconditionally on every successful call, for every model, every stage. Rev. 51 measured this live and found Anthropic's cache fields behave as documented (a real write-once/read-many pattern) while DeepSeek's endpoint reports its own automatic KV-cache metric under the same field names — a real difference, not a bug, and anything built on top of these numbers needs to keep treating the two providers' `cache_read`/`cache_write` as answering different questions, not add them together as if they meant the same thing.

**What's actually missing is aggregation and attribution, not raw data.** Three gaps, all still open:
1. **No aggregation across a run.** Every call logs its own numbers; nothing sums them. `llm_call` is the single chokepoint every stage funnels through (ideation, judging, orchestrator, workers, compiler, validator, the one-off criteria split), so it's the natural place to accumulate a running total — but it currently returns a plain `str` (deliberately, per Live Issue 5's own rev. 50 note, to avoid touching ~15 call sites' return-type contracts), and any aggregation design needs to either extend that contract or accumulate via a side channel (e.g. a module-level counter, or a run-scoped object threaded through `generate_and_optimize`) rather than reopen it carelessly.
2. **No stage attribution.** `llm_call` doesn't currently know which stage or role is calling it — that context lives in the caller (`ideation.py`, `judging.py`, `realization.py`, `pipeline.py`'s criteria split), not in the call itself. A model-only breakdown falls out of the existing `model` argument for free; a *stage* breakdown needs each call site to identify itself somehow (an explicit `stage=` kwarg is the obvious shape, but decide deliberately rather than bolting it on ad hoc — this is exactly the kind of interface change the caching table in `CLAUDE.md` documents carefully, and this would be a sibling concern to it).
3. **No output surface.** Even fully aggregated and attributed, the numbers currently have nowhere to land in the written outputs — `output.py`'s `_write_gallery`/`_write_angle_dump` don't take a usage summary as input at all yet.

**Open design questions for whoever picks this up, not yet decided:**
- **Tokens only, or a cost estimate too?** A raw token count (by model, by stage) is cheap to keep accurate. A dollar figure needs a hardcoded $/token rate per model that goes stale the moment pricing changes and nobody notices — same "assumed vocabulary that goes stale" shape `DEVELOPMENT_LOG.md` §15.7 observation 2 already warns about, just applied to pricing instead of data. If cost is wanted, prefer deriving it from a small, clearly-dated rate table over hand-asserting it once and forgetting it.
- **Where exactly in the gallery.** The gallery already opens with a one-line outcome-count summary (`_write_gallery`'s header, e.g. "8 candidate angle(s) surfaced this run: 2 realised...") — a token summary could sit right alongside that, or live in its own small section/file if it turns out to be too much detail for the top of a document meant to be skimmed in a few minutes (README's own framing).
- **Parallel fan-out caveat carries over.** `CLAUDE.md`'s caching table already notes that parallel calls (ideation's fan-out, workers within one angle) defeat the cache on first use — N concurrent calls all miss before any of them has written the cache entry. A per-run summary needs to report this honestly (e.g. cache misses concentrated in iteration/design 1) rather than presenting an average that quietly launders a known, expected pattern.


---

## 6. Cross-project notes: `karpathy/autoresearch`

[`karpathy/autoresearch`](https://github.com/karpathy/autoresearch) — an agent given a single-GPU LLM training setup and told to improve it overnight, unattended. Read at commit `228791f` (36 commits, **1,225 lines total across every file**). Recorded here as a counterpart to `DEVELOPMENT_LOG.md` §14's `lyra` notes.

### 6.1 Why a converger is the right design *there*, and the argument this makes for here

**autoresearch is precisely the converger this project abandoned in D1–D5**, and it works: mutate one file, train for a fixed 5 minutes, keep the commit if `val_bpb` improved, `git reset` if not, repeat. Try → measure → keep-or-revert, with no judges, no scoring, no dedup, no tiering, no diversity mechanism.

It works because of the oracle:

| | autoresearch | Data Prospector |
|---|---|---|
| Oracle | `val_bpb` — one scalar, unambiguous, ~5 min | Docker exit code (correctness only) + two LLM judges (quality) |
| Iterations | ~100 overnight | 4 realisations per ~110-call run |
| Evaluation machinery | none | insight + soundness judges, five-status vocabulary, tiered gallery |
| Total size | ~1,225 lines, all files | ~2,300 lines of pipeline alone |

**That size ratio is almost entirely oracle-driven, and it is `DEVELOPMENT_LOG.md` §1's founding argument arriving from the opposite direction:** the amount of evaluation machinery a system needs is inversely proportional to the quality of its oracle. A perfect oracle permits hill-climbing and needs nothing else; Co-Scientist has no oracle and spends everything on tournaments and debate; this project sits between and its machinery budget sits between. Three independent systems, one relationship.

**The loop itself is therefore not borrowable, and the reason should be stated plainly so nobody re-proposes it:** hill-climbing needs cheap iterations and an instant verdict. Here an iteration costs ~110 LLM calls and the verdict is a human reading a gallery. Adopting the loop would buy roughly one hill-climb step per morning.

### 6.2 The one item worth acting on: a cumulative results ledger

autoresearch keeps `results.tsv` — five columns, machine-readable, append-only, written by the agent as part of its own loop, deliberately untracked by git:

```
commit	val_bpb	memory_gb	status	description
a1b2c3d	0.997900	44.0	keep	baseline
c3d4e5f	1.005000	44.0	discard	switch to GeLU activation
d4e5f6g	0.000000	0.0	crash	double model width (OOM)
```

**This is the cheapest possible form of the thing Run 34 identified as this project's actual bottleneck.** That finding is worth restating because it is easy to mis-remember: **the repetition problem was never a diversity failure.** Diversity measured 0.07–0.12 throughout, comfortably inside the working band, while lead-time analysis reappeared across Runs 25, 26, 30, 31 and 33 — because nothing told ideation it had been answered. It stopped only once a *human* hand-copied the finding into the report's anti-target list, and Run 34 confirmed the mechanism works end to end.

**Proposal.** A cumulative, machine-readable ledger appended at the end of every run — `run_ts`, `angle_id`, `insight`, `soundness`, `realization_status`, one-line finding — fed to ideation as structured prior art. **Every field already exists**; `surfaced_angles_<ts>.md` carries all of them. What is missing is only that it is per-run prose rather than cumulative and parseable. That makes this a genuinely small change, and it sits naturally alongside §5's token-usage work since both are "collect what the run already knows and put it somewhere durable".

**The caveat is the important half, and it is why this must not auto-retire anything.** The sector question produced **four mutually inconsistent answers** across Runs 19, 22, 24 and 25 under four different operationalisations. An automatic "already explored — do not propose again" rule would have retired it after Run 19, and the actual finding — that the data does not identify the quantity — would never have surfaced. So: **the ledger informs judgement; the human still decides what is retired.** That preserves `DEVELOPMENT_LOG.md` §8's distinction between *this claim is settled* and *this topic has been touched*, which is the distinction the whole Already Explored mechanism turns on.

### 6.3 Two smaller observations, both with reservations

**The simplicity criterion is unusually well operationalised**, and is worth reading in full in `program.md`. Not "prefer simple code" but worked examples with signs and magnitudes: *a 0.001 improvement costing 20 lines of hacky code is probably not worth it; a 0.001 improvement from deleting code definitely is; a ~0 improvement that simplifies is a keep.*

This project has the identical concern everywhere — §13's demonstrably-improves-outcomes rule, D-simplify's standing rule — but always addressed to the **human maintainer**, never to the pipeline. §15's C3 (a generated metric that could not fail, because hybridity was scored as "any domain outside the home domain" and respondents select 3–7) is arguably what its absence looks like in generated code. **Flagging, not proposing:** prompts are human-owned under §2, and a compiler-suffix change is exactly the kind of thing that should be decided deliberately rather than borrowed because it reads well elsewhere.

**autoresearch's memory gap is instructive by contrast, and favours this project's design.** Its loop *writes* `results.tsv` but never says to *read* it. Over ~100 experiments the agent's context overflows long before the ledger does, and the only durable state is the git branch — which encodes accumulated wins but not discards, so a failed idea can be retried indefinitely with nothing to prevent it. **This project does not have that failure mode, because each run is stateless by construction and the anti-target list is explicit external memory.** Worth recording: the stateless design has occasionally looked like a limitation, and it is in fact protecting against a real one.

### 6.4 A data point for `DEVELOPMENT_LOG.md` §14.4's open question

§14.4 records that `lyra` puts orchestration in the prompt while this project puts it in code, and asks which fits when. **autoresearch is the extreme case** — 114 lines of markdown *is* the entire agent, with no orchestration code at all — and its `program.md` contains this:

> **NEVER STOP**: … do NOT pause to ask the human if you should continue. Do NOT ask "should I keep going?" or "is this a good stopping point?" … You are autonomous.

**That paragraph is in capitals and repeats itself because prompt-level orchestration has a compliance failure mode that needs shouting at.** `while attempt < max_compile_attempts` cannot decide to stop and ask permission. It is the clearest evidence yet for §14.4's framing: **prompt-level orchestration when the sequence should adapt; code when it genuinely must not vary.** Note the same document's D-simplify item 4 flags D8's saturation stopping as the point where this pipeline first acquires a decision that *should* adapt — so this distinction becomes live at exactly that step, not before.

---

## 7. Human-directed deepening ("go deep on angle N")

**Status: BACKLOG, and the `explorations/` convention is the stop-gap that covers the common case today.**

The idea, recorded in `DEVELOPMENT_LOG.md` §2 as out of scope and previously "deferred until after D8": give the pipeline a mode where, pointing it at a result already surfaced in a gallery, it drills into *that one angle* — re-generating from the angle as a seed, deepening or refining it rather than fanning out a new spread. D8 never had a deepening component of its own, and its sibling items (saturation stopping, economy instrumentation) were themselves moved here in rev. 68, so the "after D8" precondition has been dangling.

**The honest interim, already in use:** a one-off, hand-written follow-up script under `explorations/<domain>/<name>.py`. This is the pattern used for `explorations/trello/group_management_review.py` (rev. 85) and `explorations/trello/domain_technology_review.py` (rev. 86), and it is the mechanism the `cellsurvey` domain's own `LITERATURE.md` entry points at (`explorations/cellsurvey/vascular_proximity.py`). It differs from the pipeline's deepening *in kind*, not just degree: a human decides what to follow up, writes the script, reads the answer — there is no seeded re-ideation, no judge, no Docker-oracle loop at all. That keeps a follow-up cheap and fully under human control, at the cost of the pipeline's own breadth.

**Two things that are NOT on offer without real evidence:**
- **Auto-retirement of a followed-up angle.** `BACKLOG.md` §6 (the `autoresearch` ledger) and `DEVELOPMENT_LOG.md` §8's sector question both establish why: a finding that has been followed up once by hand does not automatically become "already explored — never propose again". The human curates the report's Already Explored section on the merits of *what the follow-up found*, not the fact that a follow-up ran.
- **A pipeline "deepening" mode as a thin wrapper over `explorations/`.** That would be D8-adjacent machinery (seeded re-ideation, a judge over a refinement) added to solve a problem the `explorations/` convention already covers for the cases that have actually arisen. Revisit only if hand-follow-ups start recurring on the *same* angle so often that automating the seed-and-rejudge cycle demonstrably beats writing another script.

**Reopen when:** a specific gallery result is worth pursuing further and (a) a hand `explorations/` script would be genuinely burdensome rather than a few hours, or (b) the same angle keeps winning realisation slots across runs without anyone hand-following it up — at which point the "human is the deepening loop" assumption is failing and automation earns its place.


