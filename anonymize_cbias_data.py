# -*- coding: utf-8 -*-
"""One-off anonymisation pass for inputs/cbias_data/ before it is committed or used by the pipeline.

Strips direct identifiers (names, emails, phone numbers, precise location, ticket barcodes/seats)
from the raw Attendees/Feedback/Abstracts data, redacts obvious email/phone patterns found inside
free-text fields, and writes a report of possibly-name-like text spans in free-text fields for a
human to spot-check before anything derived from this data is committed or sent to an LLM.

Usage: pixi run python anonymize_cbias_data.py
The review report necessarily quotes flagged raw text for you to judge, so it's matched by a
.gitignore rule (*_REVIEW_FLAGGED.txt) rather than relying on where it happens to be written.

inputs/cbias_data/ itself is never modified and stays gitignored; this script only ever writes to
--dst (a fresh directory) and --review-report.
"""
import argparse
import re
from pathlib import Path

import pandas as pd

# Every known PII column name across all 4 years' schema variants (see cbias_config.py's
# DOMAIN_NOTES for the renames) - dropped with errors="ignore" so a name absent in a given year's
# file is simply skipped rather than raising.
ATTENDEE_DROP_COLUMNS = [
    "Order ID",
    "Attendee first name", "Attendee Surname", "Attendee last name", "Attendee email",
    "Phone number",
    "Purchaser town/city", "Purchaser city", "Purchaser county", "Purchaser state",
    "Buyer first name", "Buyer Surname", "Buyer last name", "Buyer email",
    "Seating location 1", "Seating location 2", "Seating location 3", "Barcode number",
]
# Purchaser country is deliberately kept (coarser geography) - see the "Geography" decision.

FEEDBACK_DROP_COLUMNS = [
    "ID", "Start time", "Completion time", "Email", "Name", "Total points", "Quiz feedback",
    "Last modified time",
]

# Abstract "Label: value" fields to drop entirely, including any continuation lines that wrap
# without repeating the label (Authors wraps in 310/207 files in this dataset - checked, not
# assumed - so a naive per-line filter would leave most author names in place).
ABSTRACT_DROP_LABELS = {"Name", "Email", "Authors", "Presenting author"}
ABSTRACT_ALL_LABELS = [
    "Name", "Email", "Institution", "Title", "Authors", "Affiliation", "Affiliations",
    "Abstract", "Keywords", "Additional Keywords", "Themes", "Gender of presenting author",
    "Special requirements", "References", "Presenting author", "doi",
]
_ABSTRACT_LABEL_START = re.compile(
    r"^(" + "|".join(re.escape(l) for l in ABSTRACT_ALL_LABELS) + r"):", re.IGNORECASE
)

# Fields kept verbatim by design (e.g. "keep Institution as-is") get the light scrub only - no
# name-flagging, since flagging expected proper nouns in a field the user already chose to keep
# would just flood the review report with noise instead of surfacing real incidental PII.
FULL_SCRUB_ABSTRACT_LABELS = {"Abstract", "References", "Special requirements"}

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Reviewed against real output: this matched bibliography page/issue numbers inside Abstracts'
# References text (e.g. "12(3):456-462") as false positives, and abstracts are extremely unlikely
# to contain a real phone number - so it's applied to Feedback free text only, not Abstracts.
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\-\s()]{6,}\d)(?!\d)")
# Two-or-more consecutive Capitalized Words - a crude, high-false-positive heuristic for possible
# personal names (also matches institution names, talk titles, etc). By design this only FLAGS
# for human review; it never auto-redacts.
_NAME_LIKE_RE = re.compile(r"\b(?:[A-Z][a-z]+\s+){1,3}[A-Z][a-z]+\b")


def load_manual_redactions(path: Path) -> list[str]:
    """Exact strings (one per line) found via human review of a prior REVIEW_FLAGGED report that
    the automated patterns missed - e.g. a name mentioned in someone else's abstract prose rather
    than in a labelled field. Deliberately NOT read from a tracked file: the strings here ARE the
    PII being removed, so keeping them in a gitignored side-file (not this committed script) means
    the fix survives a re-run without ever putting a real name in git history."""
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _redact_direct_patterns(text: str, manual_redactions: list[str], redact_phone: bool) -> str:
    """Auto-redact unambiguous PII patterns (emails, optionally phone-like digit runs, and any
    manually-confirmed strings from a prior review pass)."""
    text = _EMAIL_RE.sub("[EMAIL REDACTED]", text)
    if redact_phone:
        text = _PHONE_RE.sub("[PHONE REDACTED]", text)
    for name in manual_redactions:
        text = text.replace(name, "[NAME REDACTED]")
    return text


def _flag_name_like_spans(text: str, source: str, flagged: list[str]) -> None:
    """Record (not redact) capitalised-word runs with surrounding context for manual review."""
    for match in _NAME_LIKE_RE.finditer(text):
        start, end = max(0, match.start() - 40), match.end() + 40
        flagged.append(f"{source}: ...{text[start:end].strip()}...")


def scrub_text(value, source: str, flagged: list[str], flag_names: bool,
               manual_redactions: list[str], redact_phone: bool = True):
    """Redact direct-identifier patterns; optionally flag name-like spans for review."""
    if not isinstance(value, str) or not value.strip():
        return value
    scrubbed = _redact_direct_patterns(value, manual_redactions, redact_phone)
    if flag_names:
        _flag_name_like_spans(scrubbed, source, flagged)
    return scrubbed


def _read_attendees_csv(path: Path) -> pd.DataFrame:
    """Read an attendee CSV, falling back to latin-1 (matches cbias_config.py's own reader)."""
    try:
        return pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")


def anonymize_attendees(src_dir: Path, dst_dir: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    for f in sorted(src_dir.glob("*.csv")):
        df = _read_attendees_csv(f)
        df = df.drop(columns=ATTENDEE_DROP_COLUMNS, errors="ignore")
        df.to_csv(dst_dir / f.name, index=False, encoding="utf-8")
        print(f"  Attendees/{f.name}: {len(df)} rows, {len(df.columns)} columns kept")


def anonymize_feedback(src_dir: Path, dst_dir: Path, flagged: list[str], manual_redactions: list[str]) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    for f in sorted(src_dir.glob("*.xlsx")):
        df = pd.read_excel(f)
        df = df.drop(columns=FEEDBACK_DROP_COLUMNS, errors="ignore")
        free_text_cols = [c for c in df.columns if "anything else" in c.lower()]
        for col in free_text_cols:
            df[col] = df[col].apply(
                lambda v, col=col: scrub_text(
                    v, f"Feedback/{f.name}::{col}", flagged, flag_names=True,
                    manual_redactions=manual_redactions, redact_phone=True,
                )
            )
        df.to_csv(dst_dir / f"{f.stem}.csv", index=False, encoding="utf-8")
        print(f"  Feedback/{f.name}: {len(df)} rows, {len(df.columns)} columns kept, "
              f"{len(free_text_cols)} free-text column(s) scrubbed")


def _anonymize_abstract_file(path: Path, out_path: Path, source: str, flagged: list[str],
                             manual_redactions: list[str]) -> None:
    """Stateful line parser: a line starting with a known label switches the "current field";
    any following line that doesn't start a new label is a continuation of that field (Authors,
    Institution, and Abstract all wrap across multiple lines in this dataset - verified, not
    assumed). Dropped fields drop their continuation lines too; kept fields get scrubbed.

    redact_phone=False here: reviewed against real output, the phone-number pattern was matching
    bibliography page/issue numbers in References text (e.g. "12(3):456-462"), and a real phone
    number in an abstract is vanishingly unlikely - not worth that false-positive rate."""
    out_lines = []
    current_label = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _ABSTRACT_LABEL_START.match(line)
        if m:
            current_label = next(l for l in ABSTRACT_ALL_LABELS if l.lower() == m.group(1).lower())
        elif not line.strip():
            out_lines.append(line)
            continue

        if current_label in ABSTRACT_DROP_LABELS:
            continue

        flag_names = current_label in FULL_SCRUB_ABSTRACT_LABELS
        out_lines.append(scrub_text(
            line, f"{source}::{current_label}", flagged, flag_names,
            manual_redactions=manual_redactions, redact_phone=False,
        ))

    out_path.write_text("\n".join(out_lines), encoding="utf-8")


def anonymize_abstracts(src_dir: Path, dst_dir: Path, flagged: list[str], manual_redactions: list[str]) -> None:
    for year_dir in sorted(src_dir.glob("*_Abstracts")):
        out_dir = dst_dir / year_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(year_dir.glob("*_Abstract.txt"))
        for f in files:
            _anonymize_abstract_file(
                f, out_dir / f.name, f"Abstracts/{year_dir.name}/{f.name}", flagged, manual_redactions
            )
        print(f"  Abstracts/{year_dir.name}: {len(files)} files processed")


def main():
    parser = argparse.ArgumentParser(description="Anonymise inputs/cbias_data/ into a new directory.")
    parser.add_argument("--src", default="inputs/cbias_data")
    parser.add_argument("--dst", default="inputs/cbias_data_anon")
    parser.add_argument(
        "--review-report",
        default="cbias_data_anon_REVIEW_FLAGGED.txt",
        help="Where to write the flagged-for-review report (default: repo root). Matched by a "
             "*_REVIEW_FLAGGED.txt .gitignore rule so it can never be committed regardless of "
             "where it's pointed, since it necessarily quotes flagged raw text.",
    )
    parser.add_argument(
        "--manual-redactions",
        default="manual_redactions.txt",
        help="Optional file of exact strings (one per line) to redact, found via human review of "
             "a prior run's REVIEW_FLAGGED report but missed by the automated patterns. Gitignored "
             "- never put real names in a tracked file, including this script.",
    )
    args = parser.parse_args()

    src, dst = Path(args.src), Path(args.dst)
    flagged: list[str] = []
    manual_redactions = load_manual_redactions(Path(args.manual_redactions))
    if manual_redactions:
        print(f"Applying {len(manual_redactions)} manual redaction(s) from {args.manual_redactions}\n")

    print("Attendees:")
    anonymize_attendees(src / "Attendees", dst / "Attendees")
    print("Feedback:")
    anonymize_feedback(src / "Feedback", dst / "Feedback", flagged, manual_redactions)
    print("Abstracts:")
    anonymize_abstracts(src / "Abstracts", dst / "Abstracts", flagged, manual_redactions)

    review_path = Path(args.review_report)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text("\n".join(flagged) or "(nothing flagged)", encoding="utf-8")

    print(f"\nAnonymised data written to: {dst}")
    print(f"{len(flagged)} possibly-identifying text span(s) flagged for manual review: {review_path}")
    print("Spot-check the review report, then decide whether dst is safe to commit.")


if __name__ == "__main__":
    main()