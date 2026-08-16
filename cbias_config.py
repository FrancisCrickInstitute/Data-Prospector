"""Crick Bioimage Analysis Symposium (CBIAS) domain configuration for the pipeline.

Analyses four years (2022-2025) of attendee registrations, post-event feedback surveys, and abstract
submissions to answer year-on-year trend questions (see inputs/cbias_report/task_report.md).

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
`trello_config.py`'s `python-analysis:latest` has the same build-it-yourself requirement, but no
Dockerfile target exists for it yet.
"""

import re
from pathlib import Path

import pandas as pd

from config import PipelineConfig

AVAILABLE_LIBRARIES = """
Available libraries for imports:
- Standard library: os, sys, re, csv, json, pathlib, datetime, collections, string
- NumPy: for numerical computing
- Pandas: for data manipulation and analysis
- Matplotlib: for plotting and visualization
- SciPy: for statistical tests and scientific computing
- scikit-learn: for clustering, dimensionality reduction, and other ML techniques
- NLTK: for text tokenization/stopword removal on free-text feedback and abstract fields (punkt,
  punkt_tab, and stopwords corpora are pre-downloaded; other corpora are not available)
- Seaborn: for statistical plotting on top of Matplotlib
- textstat: for readability metrics on free-text fields
"""

DOMAIN_NOTES = """
Analyse four years (2022-2025) of anonymised CBIAS data, in four sub-directories under the data
directory (or INPUT_FOLDER env var). This is anonymised data (see the module docstring) - some
identifying columns/fields present in the original raw data have been removed entirely; don't assume
fields like attendee name, email, or precise location exist. Programs/ is the one exception - see
below.

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
  per year, one per symposium day)
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
  anonymisation - do not expect them. Remaining fields present across all years: Institution, Title,
  Affiliation/Affiliations, Abstract, Keywords, Additional Keywords. 2024-2025 files additionally add
  "Themes" and "Gender of presenting author" (2025 sometimes also has "Special requirements"). Parse
  leniently by known field-label prefixes rather than assuming a fixed field order or a complete set per
  file - a few files also have one-off extra fields (e.g. "References", "doi"). The "Keywords" /
  "Additional Keywords" value is a Python-list-literal string (e.g.
  ["Segmentation","Object Tracking"]) with occasional stray "\\n" inside entries - strip whitespace after
  parsing.

- Programs/CBIAS_<year>_Program_Day_<n>.csv - one file per symposium day, two per year. HEADERLESS
  and RAGGED: do not assume column headers or a fixed column meaning. Column 1 holds a time OR a
  "Session N" label; column 2 holds a speaker name OR a session theme OR an agenda item like
  "Registration & Exhibition"; column 3 holds an affiliation OR a session chair; column 4 holds a
  talk title - and which of these a given row holds shifts between years, so parse defensively by
  row shape/content rather than by fixed column index. Speaker names here ARE real, unanonymised
  data (public information, published by the Crick) - the identifying-fields-removed caveat above
  does not apply to this file.
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
    # (DIVERGER_PLAN.md §5), which outweighs the anonymisation-driven cost reasoning that applies
    # to the high-volume roles above.
    judge_model="claude-opus-4-8",
    docker_image="cbias-analysis:latest",
    available_libraries=AVAILABLE_LIBRARIES,
    domain_notes=DOMAIN_NOTES,
    extract_input_metadata=extract_input_metadata,
)