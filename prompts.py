# System prompts for role-based agents (generic, domain-agnostic)
ORCHESTRATOR_SYSTEM = """You are an expert data analysis solutions architect. Your role is to design minimal, modular architectures.
- Prioritize simplicity and clear separation of concerns
- Design only essential functions
- Each function should have a single, well-defined responsibility
- Your designs are the blueprint for implementation"""

WORKER_SYSTEM = """You are an expert Python developer. Your role is to implement functions to specification.
- Write clean, minimal code
- Follow the function specification exactly
- No extra functions, no over-engineering
- Reuse other architecture functions when appropriate
- Each function should be production-ready and independently testable"""

COMPILER_SYSTEM = """You are an expert code integrator. Your role is to assemble modular functions into a cohesive script.
- Consolidate overlapping functions
- Remove redundancy and dead code
- Strip unnecessary complexity
- Ensure all functions work together seamlessly
- The output should be minimal, clean, and production-ready"""

EVALUATOR_SYSTEM = """You are an expert code reviewer and validator. Your role is to verify code meets requirements and works correctly.
- Assess task alignment, code quality, and execution correctness
- Check both the code and its actual behavior (if available)
- For a script realizing one candidate analysis angle, your PRIMARY judgment is a three-way
  classification of what the actual output shows: the claimed pattern legibly demonstrated, legibly
  and completely DISCONFIRMED (the script ran cleanly but the data don't support the claim - a real
  finding, not a failure), or not legibly shown at all (broken, blank, or unreadable output) - not
  just whether the code runs and superficially matches a checklist
- Be critical but fair - flag real issues, not style preferences
- Provide actionable feedback for improvement
- Your verdict determines if the code is production-ready"""

# D3b: distills the report into TWO separate outputs for two different consumers, so ideation
# (generate_angles, and later the D5 judges) stops paying cached tokens on script-delivery rubric
# text ("runs without errors", "clean code") that has nothing to do with whether an idea is good.
CRITERIA_SYSTEM = """You are an expert requirements analyst. Your role is to distill a task report into two separate, non-overlapping outputs for two different consumers: IDEATION CRITERIA (the substance an analysis idea must engage with) and a DELIVERABLE RUBRIC (the mechanical bar a finished script must clear).
- Extract only what the report actually asks for - never invent requirements it doesn't state
- Be concrete about counts, formats, and file types wherever the report is concrete
- If the report is silent on a dimension (e.g. it never mentions visualizations), say so rather than assuming a default
- Keep the two outputs cleanly separated: guiding questions, stakeholders, anti-targets, and data-availability constraints belong ONLY in the ideation criteria; run-without-errors, file-saving, and code-cleanliness belong ONLY in the deliverable rubric
- Anywhere the report specifies an anti-target list (things already explored / explicitly out of scope), carry it into the ideation criteria VERBATIM - ideation depends on knowing exactly what NOT to repeat, and paraphrasing risks losing the specifics"""

# Message prompts for LLM invocations (generic templates with placeholders for domain-specific content)
CRITERIA_PROMPT = """
Read this task report and extract two separate outputs.

Report: {report}

Input Data: {input_data}

FIRST - IDEATION CRITERIA: the substance a candidate analysis IDEA must engage with, not whether
code runs. Identify:
1. The guiding questions or stakeholders the analysis should serve, if the report states them
2. Any anti-target list - analyses already explored, or explicitly out of scope - carried over
   VERBATIM where the report is specific
3. Data availability constraints relevant to judging whether an idea is even answerable
4. What "non-obvious" or "insightful" means for this report, if it says so

SECOND - DELIVERABLE RUBRIC: the concrete, checkable criteria a finished script must satisfy once
an idea has already been chosen. Identify:
1. What the script must compute/produce (metrics, tables, summaries, etc.) and how many/which, if the report specifies
2. What artifacts it must save to disk, if any (file types, minimum counts, naming)
3. Structural or presentation requirements the report states (console output format, labeling, etc.)
4. Anything the report explicitly says to avoid or keep out of scope, at the CODE level

If the report is silent on a dimension for either output, say so rather than assuming a default.

Output ONLY the two XML blocks below, wrapping each output in its tag exactly as shown - no markdown
headings (e.g. "# IDEATION CRITERIA"), no other text before, between, or after them. This applies
even if the report itself is written with markdown headings - do not mirror the report's own
formatting back into this response.

<ideation_criteria>
[Concise bullet-point rubric for judging analysis IDEAS - guiding questions, stakeholders, anti-targets, data constraints]
</ideation_criteria>

<deliverable_rubric>
[Concise bullet-point rubric for judging a REALIZED script - what it must compute, save, and how it must look]
</deliverable_rubric>
"""

# Split in two so _run_one_design can cache the prefix: report/input_data/criteria (the
# deliverable_rubric, D3b) are identical across every angle realized in a run, so cached; the
# ANGLE being realized varies per call and stays in the suffix - see the cache_prefix argument to
# llm_call. D6: report stays the TRUE original report here (not the angle brief) precisely so this
# prefix - and WORKER_PROMPT_PREFIX below, which also takes the true report - actually hits cache
# across the top-k angles realized this run, not just within one angle's compile retries.
ORCHESTRATOR_PROMPT_PREFIX = """
You are an experienced solutions architect. Design a minimal, focused script to realize ONE
specific candidate analysis angle (given in full below).

Report (background context only - the angle below, not the whole report, is what this script must realize): {report}

Input Data: {input_data}

Domain notes (exact paths/columns of the real data - design against these, not an assumed layout):
{domain_notes}

Data profile (MECHANICALLY generated from the actual files this run - not a description, the real
column names/dtypes/null counts, and the full value set for any low-cardinality column. This is
ground truth for "what values does this column actually contain" - prefer it over an assumption
even if Domain notes above seems to say otherwise):
{data_profile}

Success Criteria (the finished script must satisfy every item below - no more, no less):
{criteria}
"""

ORCHESTRATOR_PROMPT_SUFFIX = """
THE ANGLE TO REALIZE (design a script that implements THIS ONE angle, not a general-purpose
analysis of the report above):
- Hypothesis: {hypothesis}
- Variables involved: {variables_involved}
- Rough method: {rough_method}
- Why non-obvious: {why_non_obvious}

STEP 1: ANALYZE THE DATA
Examine the available fields and structures.

STEP 2: PLAN THE APPROACH
Decide what the script needs to compute, produce, and save in order to (a) realize the angle above
and (b) satisfy every item in the Success Criteria. Do not add outputs, metrics, or visualizations
beyond what these two things call for.

STEP 3: DESIGN MINIMAL ARCHITECTURE
Design the smallest set of functions that implements your plan - prefer a single load_data() plus
main() unless the task genuinely needs more structure.

Return your response in this format:

<analysis>
1. Describe the data structure briefly
2. Summarize your plan and how it realizes the angle above and maps to each Success Criteria item
3. Brief overview of how the architecture implements the plan
</analysis>

<tasks>
    <task>
    <function>main</function>
    <description>Load data, compute required outputs, print results, save any required artifacts</description>
    <input>None</input>
    <output>None</output>
    </task>
    <task>
    <function>load_data</function>
    <description>Load the input data from the data directory</description>
    <input>None</input>
    <output>Parsed input data</output>
    </task>
</tasks>
"""

# Split in two so _call_worker can cache the prefix: original_report/input_data/library_notes/
# domain_notes/data_profile are identical across every task in a design (and across the whole
# run), while function/description/input/output vary per task - see the cache_prefix argument to
# llm_call.
WORKER_PROMPT_PREFIX = """
Shared context for this script (task, input data, and constraints):

Task: {original_report}
Data: {input_data}
Libraries: {library_notes}
Domain: {domain_notes}

Data profile (MECHANICALLY generated from the actual files this run - real column names/dtypes/
null counts and the full value set for low-cardinality columns; trust this over an assumed
vocabulary, including one implied by Domain above, when they disagree):
{data_profile}
"""

WORKER_PROMPT_SUFFIX = """
Implement the {function} function. Be direct—no defensive coding.

Architecture: {description}
Input: {input}
Output: {output}

CRITICAL RULES:
1. Implement ONLY the function '{function}', no helpers
2. Fail fast: if required data is missing, RAISE an error (e.g. FileNotFoundError/ValueError with the
   path/pattern you searched) - never print a "not found" message and return/exit normally. A clean
   exit on missing data is indistinguishable from a real success and defeats the execution check.
3. No try/except unless absolutely necessary - this includes NOT catching a missing-file/missing-column
   condition just to print a friendlier message; let rule 2's exception propagate
4. If locating input files: match paths/filenames case-insensitively and by substring against what the
   Domain notes above describe (they document real paths/columns) rather than requiring an exact
   case/format match, and do not assume a single directory level - use a recursive search
   (`Path.rglob`/`glob(..., recursive=True)`/`os.walk`) if the exact nesting isn't stated explicitly
5. Rule 2 also applies PER METRIC, not just to the whole function: if this function computes several
   values (e.g. one metric per year, or several named metrics) and one of them cannot be computed -
   a missing dependency, an empty subset of data, an unresolvable resource - do not catch that failure
   and silently write NA/None/0 and continue with the rest. Either raise (if the whole function's
   output would be misleading without it) or print an explicit, unmissable warning identifying which
   metric failed and why, so the gap is visible in the console output rather than indistinguishable
   from "computed, and the value happens to be missing"
6. One-line docstrings only
7. Clean, simple, direct code
8. Use only listed libraries + standard library
9. If implementing main(): make its FIRST line `sys.stdout.reconfigure(encoding='utf-8')` (and import sys) so UTF-8 output works on all platforms

Wrap your function in <response> tags like this:

<response>
def function_name(args):
    # docstring and code here
</response>

The tags are metadata markers only—do not include them in the actual Python code.
"""

# Split in two so compile_script can cache the prefix: it's identical across the (up to 3)
# sequential compile/execute retries for one design, since only error_feedback changes between
# attempts - see the cache_prefix argument to llm_call.
#
# domain_notes added (docs/DEVELOPMENT_LOG.md Live Issue 17): previously only WORKER_PROMPT_PREFIX carried
# the exact paths/columns, so when a worker got a path wrong and execution failed, the compile-retry
# loop rewrote the script from the traceback alone, with no way to see the real layout that would
# fix it - repairing blind. Now the compiler sees the same domain notes the worker did.
#
# data_profile added (Live Issue 31): a value-mapping bug (e.g. a Likert map missing a real
# response) is exactly the shape of error the compile-retry loop is worst at repairing from a
# traceback alone, since the traceback shows a symptom (all-NaN, a dropped year) with no value
# list to compare against. The compiler is the one call site that actually assembles this code, so
# it is the most direct place for the real value set to land.
COMPILER_PROMPT_PREFIX = """
Integrate these functions into one complete, executable Python script.

Architecture: {analysis}

Functions:
{functions}

Libraries: {library_notes}
Domain notes (exact paths/columns of the real data - fix any path/column bug against these, not a guess):
{domain_notes}

Data profile (MECHANICALLY generated from the actual files this run - real column names/dtypes/
null counts and the full value set for low-cardinality columns; if a value-mapping bug is why the
previous attempt failed, fix the map against this real value set, not against a guess):
{data_profile}
{seed_section}"""

COMPILER_PROMPT_SUFFIX = """{error_feedback}
RULES:
1. Write complete Python code (imports → functions → main() call)
2. One-line docstrings only
3. Minimal, clean code (no defensive try/except unless critical) - in particular, do NOT wrap a
   missing-file/missing-column condition in try/except to print a message and exit cleanly; a script
   that finds no usable data must raise, not exit 0, so the execution check can actually catch it
4. Same rule applies PER METRIC: if a worker function silently caught an exception to write NA/None/0
   for one of several computed values instead of raising or warning loudly, do not "clean up" that
   catch quietly while integrating it - either let the failure raise, or keep an explicit, unmissable
   console warning naming the metric and the reason. A script that reports four of five metrics with
   no indication the fifth failed is a silent partial failure, not a working script
5. Remove duplicate/unused functions

ENCODING (MANDATORY - always include these, non-negotiable):
- Line 1 MUST be exactly: # -*- coding: utf-8 -*-
- After imports, the FIRST line of main() MUST be: sys.stdout.reconfigure(encoding='utf-8')
- Always import sys
- You may freely use UTF-8 characters (—, ✓, →, etc.); the above guarantees they work on all platforms

Wrap the complete script in <response> tags exactly like this:

<response>
# -*- coding: utf-8 -*-
import sys
import ...

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ...

if __name__ == '__main__':
    main()
</response>

The <response> tags are METADATA MARKERS ONLY—do not include them in the Python code itself.
"""

# Split in two so validate_realization can cache the prefix: report + criteria (the
# deliverable_rubric) are identical across every angle realized in a run, so cached; claimed_pattern
# (the specific angle's hypothesis) and angle_scope (Live Issue 8 - variables/method, so the
# validator can skip rubric bullets that are out of scope for this one angle by design) vary per
# angle, same as script/execution output, so all three stay in the suffix - see the cache_prefix
# argument to llm_call.
REALIZATION_VALIDATOR_PROMPT_PREFIX = """
Check if this successfully-executed script's actual output satisfies the deliverable requirements
below, and legibly demonstrates its claimed pattern.

Task: {report}

Deliverable Requirements:
{criteria}
"""

REALIZATION_VALIDATOR_PROMPT_SUFFIX = """
Script: {content}
Execution Output: {execution_result}

This script exists to realize ONE specific candidate analysis angle, not the whole report. Its
declared scope is:
{angle_scope}

Its claimed pattern is:
{claimed_pattern}

If PNG images are attached to this message, they are the actual plots the script produced (up to a
few, in the order listed above) — inspect them directly.

FIRST, and most importantly: classify what the actual output (console output and/or attached images)
shows about the claimed pattern above. Judge what was actually produced, not whether the code looks
like it should produce this pattern. Distinguish THREE outcomes, not two - a broken/illegible run and
a clean disconfirmation are NOT the same thing, even though neither "shows the pattern":
- "shown": the output legibly demonstrates the claimed pattern.
- "disconfirmed": the output is legible, complete, and directly addresses the claim - but the data do
  NOT support it (e.g. a clear flat/opposite trend where a trend was claimed). This is a genuine,
  useful finding, not a failure - do not penalize it as if something went wrong.
- "not_shown": the output does not legibly show anything about the claim either way - blank,
  unreadable, contradicts itself, measures the wrong thing, or is otherwise uninterpretable.

<pattern_outcome>[shown, disconfirmed, or not_shown - exactly one of these three words, nothing else]</pattern_outcome>
<pattern_reasoning>[1-2 sentences on what the actual output does or doesn't show, and why that maps to the outcome chosen above. Also mention, as information alongside the finding rather than a reason to change the verdict above, whether the console output includes or omits a statistical test of the claim (e.g. a significance test, confidence interval) - a plausible four-point trend and a significance-tested one are both worth surfacing, but a reader should know which they're looking at]</pattern_reasoning>

SECOND, judge EACH bullet in the Deliverable Requirements above, in the same order, against the
ACTUAL output above (console output, the "Files actually produced on disk" listing, and any attached
images) — NOT against what the code merely claims to do. A file the requirements require that is
0-byte or missing is NOT met, even if the code calls a save function on it.

The Deliverable Requirements describe the WHOLE report, but this script only realizes the ONE angle
scoped above. Before judging a bullet, ask: is this bullet even ABOUT something this angle's declared
scope could touch (e.g. it names a variable/metric/comparison this angle doesn't involve, or a
deliverable format this angle was never going to produce by design)? If so, SKIP it - do not emit a
<criterion> tag for it at all, and do not count it in feedback either way. Do NOT skip a bullet just
because the script failed to satisfy it, produced a weak/null result, or you're unsure whether it
counts - skipping is only for bullets that are out of scope BY DESIGN, not for shortfalls. When in
doubt, judge it (met="false") rather than skip it.

Emit exactly one <criterion met="true"/> or <criterion met="false"/> tag per bullet that is in scope,
in the same order as the Deliverable Requirements, and nothing else inside this block:

<criteria_result>
<criterion met="true"/>
<criterion met="false"/>
</criteria_result>

<feedback>
For every criterion above marked met="false", or if pattern_outcome is "not_shown", explain
specifically what's missing/broken and what needs to change. Also note, without changing the verdicts
above, if the script adds outputs/metrics/files beyond what's needed, or if the code is not clean
(one-line docstrings, no bloat). If pattern_outcome is "disconfirmed", do NOT describe this as
something to fix - state plainly what the data actually showed instead of the claim. If everything is
met and the pattern is shown: "Realized successfully. Data gaps for future analysis: [list 2-3 things
that would help, if applicable]"
</feedback>
"""

# --- D2/D3a/D3b: Angle generation (ideation) --------------------------------------------------
# Human-owned - see docs/DEVELOPMENT_LOG.md guardrails ("Do not invent objective prompts"). The wording
# of these three constants determines the quality of every angle the pipeline ever proposes; left
# empty deliberately. Split per the caching convention (docs/DEVELOPMENT_LOG.md §4): PREFIX is
# report/ideation_criteria/input_data (identical across every angle-generation call in a run) -
# ideation_criteria is the IDEATION half of the D3b criteria split (guiding questions, stakeholders,
# anti-targets, data constraints) - the deliverable rubric (script-delivery mechanics) is withheld
# from ideation entirely and held for D6. SUFFIX is stance/guiding_question/existing_angles
# (per-call/per-iteration - both cycling axes vary call to call, so they must live here, not in the
# cached prefix).
#
# generate_angles() in pipeline.py logs a loud warning and falls back to the minimal built-in
# placeholder below when any of these three are empty, so the plumbing stays runnable while
# they're unfilled - that fallback is NOT a substitute for real ideation prompt design.
ANGLE_GENERATION_SYSTEM = (
    "You are an experienced data analyst, adept at identifying novel insights from both structured and unstructured "
    "data. You generate candidate data-analysis angles as structured XML. Each angle is a distinct question or method, "
    "not a full analysis plan. While novelty is encouraged, the calculation must be feasible with the given data. "
    "Avoid over-extrapolating or making assumptions not supported by the data."
)
ANGLE_GENERATION_PROMPT_PREFIX = """
Report: {report}

Ideation Criteria (guiding questions, stakeholders, anti-targets, data constraints):
{ideation_criteria}

Input Data: {input_data}
"""
ANGLE_GENERATION_PROMPT_SUFFIX = """
{existing_angles}

For this call, your assigned angle of attack is:
- Approach/stance: {stance}
- Guiding question or stakeholder to focus on: {guiding_question}

Propose {n} distinct candidate analysis angle(s) that concretely reflect the stance and question
above - do not default back to whichever opportunity in the data looks most obvious or most
concrete if it conflicts with this assignment. Each angle is an idea for a specific analysis - not
code, not a full script design - identified by what it would compute and why it might be
interesting, and it must be genuinely different from anything already listed above (if non-empty). However, do not 
suggest analysis angles that cannot be supported by the underlying data - candidate analyses must be feasible,
not just interesting.

Return your response as one <angles> block containing exactly {n} <angle> blocks:

<angles>
<angle>
<id>short descriptive slug naming what the angle actually analyses, e.g. "readability-trend" or "ticket-type-composition" - NOT a generic placeholder like "angle-1" or "angle-2"</id>
<variables_involved>which fields/columns this angle uses</variables_involved>
<hypothesis>what pattern or relationship this angle expects to find</hypothesis>
<question_or_stakeholder_served>which guiding question or stakeholder this serves</question_or_stakeholder_served>
<why_non_obvious>why this isn't just the first/obvious thing to check</why_non_obvious>
<rough_method>one or two sentences on how it'd be computed</rough_method>
<requires>comma-separated list of any Python libraries this method would need beyond numpy/pandas/matplotlib, if any (e.g. "networkx, scikit-learn, scipy"); this is for tracking only - propose the analysis that's genuinely best, don't limit yourself to what's already available</requires>
</angle>
</angles>
"""

# --- D5: Insight + soundness judging --------------------------------------------------------
# Human-owned - see docs/DEVELOPMENT_LOG.md guardrails ("Do not invent objective prompts") AND D5's own
# note: "Both prompts are human-owned - they are the product." Once req_score is gone, these two
# judges ARE the entire quality bar - the machinery is trivial, the wording is the whole game.
# Split per the caching convention (docs/DEVELOPMENT_LOG.md §4): PREFIX is report/ideation_criteria/
# input_data - the SAME triple generate_angles already caches, since D3b folded the anti-target
# list into ideation_criteria. SUFFIX is the individual angle being judged ({angle_text}).
#
# judge_insight()/judge_soundness() in pipeline.py log a loud warning and fall back to the minimal
# built-in placeholders below when their three constants are empty, so the plumbing stays runnable
# while they're unfilled - the fallback is NOT a substitute for real judge prompt design.
INSIGHT_JUDGE_SYSTEM = (
    "You judge whether a proposed data-analysis angle is genuinely non-obvious, grounded in what "
    "the data can actually support - not whether the angle's own self-description claims novelty."
)
INSIGHT_JUDGE_PROMPT_PREFIX = """
Report: {report}

Ideation Criteria (guiding questions, stakeholders, ANTI-TARGETS - analyses already explored, data constraints):
{ideation_criteria}

Input Data: {input_data}
"""
INSIGHT_JUDGE_PROMPT_SUFFIX = """
Judge the non-obviousness of this candidate analysis angle. Do NOT take its own why_non_obvious
field as evidence - judge independently against the anti-target list above and your own knowledge
of what's obvious to try first with this kind of data. An angle that overlaps the anti-target list,
even if phrased differently or using a different library/method, is NOT non-obvious.

Angle:
{angle_text}

<score>[0.0-1.0, where 0.0 = exactly what the anti-target list already covers, 1.0 = genuinely novel and non-obvious]</score>
<reasoning>[1-2 sentences justifying the score, referencing the anti-target list or data if relevant]</reasoning>
"""

SOUNDNESS_JUDGE_SYSTEM = (
    "You judge whether a proposed data-analysis angle's claimed pattern is likely a real, "
    "defensible finding given the data volume available, or a sampling artifact / overclaim. You also judge "
    "whether the angle is implementable, given the underlying data."
)
SOUNDNESS_JUDGE_PROMPT_PREFIX = """
Report: {report}

Ideation Criteria (guiding questions, stakeholders, anti-targets, data constraints):
{ideation_criteria}

Input Data: {input_data}
"""
SOUNDNESS_JUDGE_PROMPT_SUFFIX = """
Judge whether this candidate analysis angle's claimed pattern is defensible given the data volume
actually available (see Input Data above). Distinguish three cases, not two - a boolean sound/unsound
call collapses "needs a caveat" and "cannot be supported at all" into the same bucket, which is not
useful when almost nothing on a small dataset is unconditionally solid:
- "unsupportable": the claim cannot be supported at all - e.g. a "trend" over only 2 data points, a
  field that does not exist in the data for the years/groups being compared, a subgroup of 2-3, a
  method that isn't actually computable from what's available.
- "caveat": the claim is supportable but only with an explicit caveat about its limitations (small n,
  partial-year coverage, a confound not controlled for). Expect this to be the NORMAL case for a
  dataset this size, not a rare one.
- "solid": the claim is well-supported with no material caveat needed. Expect this to be rare.

Angle:
{angle_text}

<verdict>[unsupportable, caveat, or solid - exactly one of these three words, nothing else]</verdict>
<caveat>[the specific reason to carry forward and display alongside the angle later. For "caveat":
the limitation to hedge with (e.g. "n=37 respondents in 2022, treat as indicative, not conclusive").
For "unsupportable": the specific reason the claim cannot be supported at all (e.g. "only 2 data
points available, cannot support a trend claim"). Leave empty only if verdict is "solid".]</caveat>
<reasoning>[1-2 sentences justifying the verdict, citing the specific data limitation regardless of
which verdict was chosen]</reasoning>
"""
