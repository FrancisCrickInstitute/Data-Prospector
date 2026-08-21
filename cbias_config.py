"""Crick Bioimage Analysis Symposium (CBIAS) domain configuration for the pipeline.

Analyses six years of symposium programs (2020-2025), five years of abstract submissions (2021-2025),
and four years (2022-2025) of attendee registrations and post-event feedback surveys, to answer
year-on-year trend questions (see inputs/cbias_report/task_report.md). The 2020 and 2021 editions
were online-only (COVID) and are not directly comparable to the in-person 2022-2025 editions.

The data this points at (inputs/cbias_data_anon/, produced by anonymize_cbias_data.py from the raw,
gitignored inputs/cbias_data/) has had direct identifiers - names, emails, phone numbers, precise
location, ticket barcodes/seats, submission authorship - stripped or generalised. See
anonymize_cbias_data.py's module docstring for exactly what was removed and why. A handful of Abstract/
References fields may contain a literal "[EMAIL REDACTED]"/"[PHONE REDACTED]"/"[NAME REDACTED]"
placeholder where something was scrubbed inline - treat these as ordinary text, not an error.

NOTE: `docker_image` below is defined by the Dockerfile's `cbias-analysis` target (kept in sync with
AVAILABLE_LIBRARIES below) but is not built automatically - build/rebuild it locally before
execution-validation will work for this config, and again whenever the Dockerfile's package list
changes:
    docker build --target cbias-analysis -t cbias-analysis:latest .
`trello_config.py` reuses this same `cbias-analysis:latest` image rather than a dedicated target -
a trello angle only ever imports the numpy/pandas/matplotlib subset of AVAILABLE_LIBRARIES below,
so the extra CBIAS-specific libraries baked into this image are simply inert for it.
"""

import re
from pathlib import Path

import pandas as pd

from config import PipelineConfig

AVAILABLE_LIBRARIES = """
Available libraries for imports. VERSIONS ARE PINNED in the Docker image below - these are exactly
what will be installed, not a floor or a guess, so target this API generation specifically rather
than a version-agnostic "current" API (Live Issue 30 - two wasted compile attempts, Runs 22 and 30,
from assuming an older matplotlib API than what was actually installed):
- Standard library: os, sys, re, csv, json, pathlib, datetime, collections, string
- NumPy 2.5.2: for numerical computing
- Pandas 3.0.5: for data manipulation and analysis. DataFrame.applymap was REMOVED in pandas 3.0 -
  use DataFrame.map instead. Pandas 3.0 also gives text columns inferred by read_csv their own
  native `str` dtype, DISTINCT from the legacy `object` dtype - pd.api.types.is_object_dtype()
  returns False for them (Live Issue 33 - a script that gated Likert-scale detection on
  is_object_dtype() silently skipped every text column, Run 34). Use pd.api.types.is_string_dtype()
  when detecting text/categorical columns; it covers both `str` and legacy `object`-dtype text.
- Matplotlib 3.11.1: for plotting and visualization. boxplot()'s `labels=` keyword was renamed to
  `tick_labels` in matplotlib 3.9 (applies to both pyplot.boxplot and Axes.boxplot) - using `labels=`
  raises a deprecation warning at best and a TypeError in a future release; use `tick_labels=`.
- SciPy 1.18.0: for statistical tests and scientific computing
- scikit-learn 1.9.0: for clustering, dimensionality reduction, and other ML techniques
- NLTK 3.10.3: for text tokenization/stopword removal on free-text feedback and abstract fields
  (punkt, punkt_tab, and stopwords corpora are pre-downloaded; other corpora are not available)
- Seaborn 0.13.2: for statistical plotting on top of Matplotlib
- textstat 0.7.13: for readability metrics on free-text fields
"""

DOMAIN_NOTES = """
Analyse anonymised CBIAS data spanning UNEVEN years across the four data types (programs 2020-2025,
abstracts 2021-2025, attendees and feedback 2022-2025), in four sub-directories under the data
directory (or INPUT_FOLDER env var). This is anonymised data (see the module docstring) - some
identifying columns/fields present in the original raw data have been removed entirely; don't assume
fields like attendee name, email, or precise location exist. Programs/ is the one exception - see
below. The 2020 and 2021 editions were ONLINE-ONLY (COVID), not in-person like 2022-2025: do not
fold an online-only year's participation numbers into an in-person trend as if they were the same
quantity, and treat any trend that crosses the 2021->2022 online/in-person boundary as suspect (the
format change, not the field, may be doing the work).

EXACT PATHS - build globs against these, not an assumed/simplified layout. Getting this wrong means
zero files load and the script has nothing to analyse:
- Attendees: {INPUT_FOLDER}/Attendees/CBIAS_<year>_Attendees.csv
- Feedback:  {INPUT_FOLDER}/Feedback/CBIAS <year>Attendee Survey(<n>-<n>).csv  (note: no path
  separator, and sometimes no space, between "CBIAS" and the year - e.g. both "CBIAS 2022Attendee
  Survey(1-60).csv" and "CBIAS 2025 Attendee Survey(1-37).csv" occur; match on the substring
  "Attendee Survey" within the Feedback/ directory rather than a fixed literal filename)
- Abstracts:  {INPUT_FOLDER}/Abstracts/<year>_Abstracts/<n>_Abstract.txt  (one directory level PER
  YEAR under Abstracts/ - a flat glob directly on Abstracts/*.txt will find nothing; glob
  Abstracts/*_Abstracts/*.txt or walk one level down first)
- Programs:   {INPUT_FOLDER}/Programs/CBIAS_<year>_Program_Day_<n>.csv  (<n> is 1 or 2 - two files
  per year, one per symposium day, EXCEPT 2020 which has only Day 1)
All four sub-directories (Attendees/, Feedback/, Abstracts/, Programs/) are direct children of the
data directory/INPUT_FOLDER itself - do not search the top level for CSVs/txt files directly.

- Attendees/CBIAS_<year>_Attendees.csv - one row per registration. Columns: Order date, Purchaser
  country, Event name/ID/start date/start time/timezone/location, Ticket quantity/tier/type, Currency,
  Ticket price, Guest. All four files are plain UTF-8. Column headers are exactly as listed (e.g.
  "Order date" and "Event start date", lowercase "date") - read them verbatim from df.columns rather
  than guessing a snake_case or Title Case variant.
  "Ticket type" holds the registration category: Academic, Academic - early bird, Industry,
  Industry - early bird, Online Only, Sponsors. Treat "X" and "X - early bird" as the same category X
  (e.g. match on a substring/prefix) when computing category distributions; "Industry" plus
  "Industry - early bird" together are the industry-participation signal.

- Feedback/CBIAS <year>Attendee Survey(...).csv - one row per respondent, one file per year (converted
  from the original Microsoft Forms xlsx export to CSV during anonymisation - read with
  pandas.read_csv, not read_excel; the raw export's always-empty "Points - <question>"/
  "Feedback - <question>" companion columns are dropped during anonymisation, so every column
  remaining is a real answer - no need to filter any out). Question wording drifts slightly by year
  for the same underlying construct, and sometimes the RESPONSE SCALE changes along with it, not just
  the phrasing - e.g. "The ticket prices were appropriate" (2022-2023) becomes "The ticket prices were
  too high" (2024-2025), an inverted phrasing of the same Agree/Disagree question; separately, the
  session/poster-session duration questions are phrased "...was an appropriate length" (2022-2023,
  Agree/Disagree scale) but "The average duration of ... was..." (2024-2025, a DIFFERENT scale - see
  below). Match columns by keyword substring (e.g. "ticket price", "session"), not exact text, and
  account for both the polarity flip and the scale change when combining years into one trend - do
  not assume every year's version of a question shares the same response options.

  Most questions are Likert-style free-text strings needing a mapping to an ordinal scale before
  averaging - but not all of them (e.g. the overall-satisfaction question is already numeric), and the
  ones that are text do not all share ONE scale. INSPECT A COLUMN'S ACTUAL UNIQUE VALUES before
  deciding it needs a text-to-ordinal mapping (running that mapping against values that are already
  numeric finds no matching keys and silently produces all-NaN, which reads as missing data but is
  not), and build the mapping from those actual values, not from an assumed/textbook Likert vocabulary
  - a hand-written map that omits a real response value silently drops every respondent who chose it,
  which reads as a smaller sample, not as a bug. Two response scales are actually used across this
  survey (verified against all four years' data, not just described here - re-verify if a new year's
  export is added):
    - Agreement scale (most questions): Strongly Disagree, Disagree, Neither Agree nor Disagree,
      Agree, Strongly Agree, Not Applicable. "Not Applicable" is a real, frequently-chosen response
      (not a rare edge case) - treat it as its own category to exclude or report separately, not as
      an extra ordinal rung, and do not build a map that silently drops every row containing it.
    - Duration scale (session/poster-session duration questions, 2024-2025 wording only): Far Too
      Short, Too Short, About Right, Too Long, Far Too Long. Distinct from the agreement scale above -
      a map built for one will not match the other.

- Abstracts/<year>_Abstracts/<n>_Abstract.txt - one plain-text file per submission, "Label: value"
  lines, where a field's value may wrap onto further lines before the next label. Author-identifying
  fields (Name, Email, Authors, Presenting author) have been removed from every year during
  anonymisation - do not expect them. Remaining fields vary by year: Institution, Title, Abstract,
  Keywords, Additional Keywords are near-universal; Affiliation/Affiliations is common in 2022-2023
  but essentially absent from 2021 (present in 1 of 56 files); References is common in 2022-2023 but
  rare in 2021 (2 of 56). 2024-2025 files additionally add
  "Themes" and "Gender of presenting author" (2025 sometimes also has "Special requirements"). Parse
  leniently by known field-label prefixes rather than assuming a fixed field order or a complete set per
  file - a few files also have one-off extra fields (e.g. "References", "doi"). The "Keywords" /
  "Additional Keywords" value is a Python-list-literal string (e.g.
  ["Segmentation","Object Tracking"]) with occasional stray "\\n" inside entries - strip whitespace after
  parsing.

- Programs/CBIAS_<year>_Program_Day_<n>.csv - one file per symposium day, two per year (EXCEPT 2020,
  which has only Day 1). TWO DIFFERENT FORMATS are used, so inspect before assuming:
  - Headerless/ragged (2020, 2022-2025): no column headers, no fixed column meaning. Column 1 holds
    a time OR a "Session N" label; column 2 holds a speaker name OR a session theme OR an agenda item
    like "Registration & Exhibition"; column 3 holds an affiliation OR a session chair; column 4
    holds a talk title - and which of these a given row holds shifts between years, so parse
    defensively by row shape/content rather than by fixed column index.
  - Headed (2021 only): the file HAS a header row ("Start,Duration,End,..."), so the first three
    columns are start time, duration, and end time, with the remaining columns holding
    speaker/session, affiliation/theme, and title - still with the session-label-vs-speaker-name
    ambiguity in the name column, so still parse defensively rather than trusting the header.
  Speaker names here ARE real, unanonymised data (public information, published by the Crick) - the
  identifying-fields-removed caveat above does not apply to this file. The 2020 and 2021 programmes
  are for ONLINE-ONLY editions: their speaker pool, talk formats, and timing reflect a virtual event,
  so a speaker/affiliation/sector trend that crosses 2021->2022 mixes an online with an in-person
  programme - treat that boundary as a structural break, not a field shift.
"""

_ABSTRACT_FIELD_LABELS = [
    "Institution", "Title", "Affiliation", "Affiliations", "Abstract", "Keywords",
    "Additional Keywords", "Themes", "Gender of presenting author", "Special requirements",
    "References", "doi",
]
_ABSTRACT_FIELD_PATTERN = re.compile(
    r"^(" + "|".join(re.escape(label) for label in _ABSTRACT_FIELD_LABELS) + r"):", re.MULTILINE
)

# Microsoft Forms export columns that are metadata, not survey questions - dropped when
# summarizing "question_columns" below so the orchestrator sees the real questions, not response IDs.
_FEEDBACK_METADATA_COLUMNS = {
    "id", "start time", "completion time", "email", "name", "total points",
    "quiz feedback", "last modified time",
}


def _feedback_question_columns(columns: list[str]) -> list[str]:
    """Real survey-question columns: drop ID/timestamp metadata and the auto-generated
    'Points - '/'Feedback - ' companion columns Microsoft Forms adds per question."""
    return [
        c for c in columns
        if c.strip().lower() not in _FEEDBACK_METADATA_COLUMNS
        and not c.startswith("Points - ")
        and not c.startswith("Feedback - ")
    ]


def extract_input_metadata(directory: str) -> str:
    """Summarize the Attendees/Feedback/Abstracts sub-directories for the orchestrator."""
    base = Path(directory)

    attendees = []
    for f in sorted(base.glob("Attendees/*.csv")):
        df = pd.read_csv(f, encoding="utf-8")
        ticket_counts = df["Ticket type"].value_counts(dropna=False) if "Ticket type" in df.columns else {}
        attendees.append({
            "file": f.name,
            "rows": len(df),
            "columns": list(df.columns),
            "ticket_type_counts": {str(k): int(v) for k, v in ticket_counts.items()},
        })

    feedback = []
    for f in sorted(base.glob("Feedback/*.csv")):
        df = pd.read_csv(f, encoding="utf-8")
        feedback.append({
            "file": f.name,
            "respondents": len(df),
            "question_columns": _feedback_question_columns(list(df.columns)),
        })

    abstracts = []
    for year_dir in sorted(base.glob("Abstracts/*_Abstracts")):
        files = sorted(year_dir.glob("*_Abstract.txt"))
        fields_seen = set()
        for f in files:
            fields_seen.update(_ABSTRACT_FIELD_PATTERN.findall(f.read_text(encoding="utf-8")))
        abstracts.append({
            "folder": year_dir.name,
            "submissions": len(files),
            "fields_present": sorted(fields_seen),
        })

    return str({"Attendees": attendees, "Feedback": feedback, "Abstracts": abstracts})


# Live Issue 31: columns with more distinct values than this are almost always free text (comments,
# titles) - listing them in full would blow the token budget for no benefit, since the failure
# class this profile targets (an assumed response/category vocabulary) only ever occurs on
# low-cardinality columns. Applied to Attendees/Feedback (genuinely categorical columns); Programs
# is excluded from per-column enumeration entirely below, for the reason given there.
_PROFILE_CARDINALITY_CUTOFF = 25


def _profile_csv(f: Path, base: Path, header="infer") -> str:
    """One CSV's worth of DOMAIN_NOTES-style profiling: verbatim column name, dtype, null count,
    and (if low-cardinality) the FULL set of distinct values actually present - not a description
    of what a column is expected to contain, but what pandas actually found in it. This is what
    catches an omitted response value (A5), an already-numeric column mislabelled as text (A2), or
    an unreachable category (A3/A4) mechanically, without anyone having to notice and transcribe it
    by hand first."""
    df = pd.read_csv(f, encoding="utf-8", header=header)
    lines = [f"  {f.relative_to(base)} ({len(df)} rows):"]
    for col in df.columns:
        series = df[col]
        nulls = int(series.isna().sum())
        nunique = int(series.nunique(dropna=True))
        if nunique <= _PROFILE_CARDINALITY_CUTOFF:
            values = sorted(str(v) for v in series.dropna().unique())
            lines.append(f"    {col!r} [{series.dtype}, {nulls} null]: {values}")
        else:
            lines.append(f"    {col!r} [{series.dtype}, {nulls} null]: "
                         f"{nunique} distinct values, not enumerated (over the cutoff)")
    return "\n".join(lines)


_PROGRAM_TIME_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?\s*$")


def _program_has_header(df: pd.DataFrame) -> bool:
    """Heuristic flag for the program files' two formats. A headerless program file (2020, 2022-2025)
    starts its substantive content with a time in the first column (e.g. "08:30"); the headed format
    (2021) starts with column labels (e.g. "Start"). Return True when the first non-empty first-column
    value is NOT a time - i.e. it reads as a label row, not a data row. Deliberately a lightweight
    one-line signal, not a gate: it surfaces headed-vs-headerless drift without trusting DOMAIN_NOTES
    prose alone, but the ragged column meaning is still described there, not derived here."""
    first_values = df[0].dropna()
    if first_values.empty:
        return False
    first = str(first_values.iloc[0]).strip()
    return not bool(_PROGRAM_TIME_RE.match(first))


def generate_data_profile(directory: str) -> str:
    """Live Issue 31: a MECHANICAL per-run profile of the actual data - no LLM in the loop, so it
    cannot hallucinate a value that isn't there and cannot go stale, unlike the hand-maintained
    DOMAIN_NOTES vocabulary enumerations it supplements (each of which worked on its first live run
    - the A2/A5 fix at rev. 43, library-version pinning at rev. 45 - then was found incomplete by
    the very next run: Run 31 hit two more gaps of the identical shape). Answers ONLY "what is in
    the data"; DOMAIN_NOTES above stays the place for what this cannot derive - semantics,
    provenance, absence, and the anti-target list. Fed into the realisation stage's cached prefixes
    (orchestrator/worker/compiler - see realization.py), the same reach domain_notes already has,
    not into ideation - same "realisation constraint, not an ideation constraint" boundary as
    available_libraries."""
    base = Path(directory)
    sections = []

    attendee_lines = [_profile_csv(f, base) for f in sorted(base.glob("Attendees/*.csv"))]
    if attendee_lines:
        sections.append("Attendees:\n" + "\n".join(attendee_lines))

    feedback_lines = [_profile_csv(f, base) for f in sorted(base.glob("Feedback/*.csv"))]
    if feedback_lines:
        sections.append("Feedback:\n" + "\n".join(feedback_lines))

    # Programs gets row/column counts only, NOT the same full-enumeration treatment as the other
    # three - it's headerless AND ragged (a given column position means a different thing on
    # different rows, per Domain notes above), so the per-column-value-set profiling this function
    # otherwise does isn't measuring a real category vocabulary here. Worse, with only ~20-30 rows
    # per file, every column stays under the cardinality cutoff by row-count coincidence alone, so
    # the naive version silently dumped every speaker name and talk title verbatim - real content,
    # but not the kind of gap this profile exists to catch, at a genuinely large token cost for no
    # matching benefit (no A/B/C-class failure in DEVELOPMENT_LOG.md has ever involved Programs).
    # The one thing added since: a per-file header/headerless flag (see _program_has_header below),
    # because the 2021 files are headed while the rest are headerless - a one-line mechanical signal
    # for that format split, still not the value enumeration the above argues against.
    program_lines = []
    for f in sorted(base.glob("Programs/*.csv")):
        df = pd.read_csv(f, encoding="utf-8", header=None)
        kind = "header row" if _program_has_header(df) else "headerless"
        program_lines.append(
            f"  {f.relative_to(base)}: {len(df)} rows, {len(df.columns)} columns, {kind}"
        )
    if program_lines:
        sections.append(
            "Programs (row/column counts and a header/headerless flag only, not a value profile - "
            "see Domain notes above for the ragged column meaning):\n" + "\n".join(program_lines)
        )

    # Abstracts aren't tabular, so "profile" means something different here: one real sample value
    # per field label actually present in each year's folder, not a value set. This is what makes a
    # format split like Keywords' JSON-list-in-some-years/comma-text-in-others visible side by side
    # without anyone having noticed and written it down first (Live Issue 31's second Run 31 gap).
    abstract_lines = []
    for year_dir in sorted(base.glob("Abstracts/*_Abstracts")):
        files = sorted(year_dir.glob("*_Abstract.txt"))
        samples = {}
        for f in files:
            text = f.read_text(encoding="utf-8")
            for label in _ABSTRACT_FIELD_LABELS:
                if label in samples:
                    continue
                m = re.search(rf"^{re.escape(label)}:\s*(.*)$", text, re.MULTILINE)
                if m and m.group(1).strip():
                    samples[label] = m.group(1).strip()[:150]
        sample_text = "; ".join(f"{label}={value!r}" for label, value in samples.items())
        abstract_lines.append(f"  {year_dir.name} ({len(files)} submissions): {sample_text}")
    if abstract_lines:
        sections.append("Abstracts (one real sample value per field label present, not a full set):\n"
                        + "\n".join(abstract_lines))

    return "\n\n".join(sections) if sections else "(no data profile available)"


CONFIG = PipelineConfig(
    orchestrator_model="claude-opus-4-8",
    # worker/compiler: deliberately routed to DeepSeek (not the all-Anthropic default this config
    # used to have). This was withheld until inputs/cbias_data/ was anonymised - see
    # anonymize_cbias_data.py and the module docstring above - since these two roles see the most
    # data volume (one call per function, and every compile/execute retry). Judged acceptable once
    # direct identifiers were stripped; requirements_evaluator_model stays on Anthropic below since
    # it's the final quality gate and is passed images.
    worker_model="deepseek-v4-pro",
    compiler_model="deepseek-v4-pro",
    requirements_evaluator_model="claude-sonnet-5",
    # D2 ideation (generate_angles): same reasoning as worker/compiler above - anonymised data,
    # cheap high-volume tier.
    angle_model="deepseek-v4-pro",
    # D5 judging: frontier Anthropic tier, NOT DeepSeek like worker/compiler/angle_model above -
    # once req_score is gone these two judges (insight/soundness) are the entire quality bar
    # (DEVELOPMENT_LOG.md §5), which outweighs the anonymisation-driven cost reasoning that applies
    # to the high-volume roles above.
    judge_model="claude-opus-4-8",
    docker_image="cbias-analysis:latest",
    available_libraries=AVAILABLE_LIBRARIES,
    domain_notes=DOMAIN_NOTES,
    extract_input_metadata=extract_input_metadata,
    data_profile=generate_data_profile,
)