"""Crick Bioimage Analysis Symposium (CBIAS) domain configuration for the pipeline.

Analyses four years (2022-2025) of attendee registrations, post-event feedback surveys, and abstract
submissions to answer year-on-year trend questions (see inputs/cbias_report/task_report.md).

The data this points at (inputs/cbias_data_anon/, produced by anonymize_cbias_data.py from the raw,
gitignored inputs/cbias_data/) has had direct identifiers - names, emails, phone numbers, precise
location, ticket barcodes/seats, submission authorship - stripped or generalised. See
anonymize_cbias_data.py's module docstring for exactly what was removed and why. A handful of Abstract/
References fields may contain a literal "[EMAIL REDACTED]"/"[PHONE REDACTED]"/"[NAME REDACTED]"
placeholder where something was scrubbed inline - treat these as ordinary text, not an error.

NOTE: `docker_image` below does not exist yet. This repo's Dockerfile only builds `bia-analysis:latest`
(numpy/scipy/scikit-image/scikit-learn/pandas/bioio/bioio-tifffile - no matplotlib). Build a
`cbias-analysis:latest` image with pandas, numpy, and matplotlib before execution-validation will work
for this config - same gap already documented for `trello_config.py`'s `python-analysis:latest`.
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
Analyse four years (2022-2025) of anonymised CBIAS data, in three sub-directories under the data
directory (or INPUT_FOLDER env var). This is anonymised data (see the module docstring) - some
identifying columns/fields present in the original raw data have been removed entirely; don't assume
fields like attendee name, email, or precise location exist.

- Attendees/CBIAS_<year>_Attendees.csv - one row per registration. Columns: Order date, Purchaser
  country, Event name/ID/start date/start time/timezone/location, Ticket quantity/tier/type, Currency,
  Ticket price, Guest. All four files are plain UTF-8.
  "Ticket type" holds the registration category: Academic, Academic - early bird, Industry,
  Industry - early bird, Online Only, Sponsors. Treat "X" and "X - early bird" as the same category X
  (e.g. match on a substring/prefix) when computing category distributions; "Industry" plus
  "Industry - early bird" together are the industry-participation signal.

- Feedback/CBIAS <year>Attendee Survey(...).csv - one row per respondent, one file per year (converted
  from the original Microsoft Forms xlsx export to CSV during anonymisation - read with
  pandas.read_csv, not read_excel). Each survey question appears as a real answer column plus two
  auto-generated companion columns ("Points - <question>", "Feedback - <question>") that are
  quiz-scoring artifacts and almost always empty - ignore columns starting with "Points - " or
  "Feedback - " and read the plain question-text column for actual responses. Question wording drifts
  slightly by year for the same underlying construct - e.g. "The ticket prices were appropriate"
  (2022-2023) becomes "The ticket prices were too high" (2024-2025), an inverted phrasing of the same
  question - match columns by keyword substring (e.g. "ticket price"), not exact text, and account for
  the polarity flip when combining years into one trend. Likert-style answers are free-text strings
  (e.g. "Strongly agree"), not numbers - map them to an ordinal scale before averaging.

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