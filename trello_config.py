"""Trello board analysis domain configuration for the pipeline."""

import json
from pathlib import Path

import pandas as pd

from config import PipelineConfig


AVAILABLE_LIBRARIES = """
Available libraries for imports. VERSIONS ARE PINNED (the sandbox image is the same pinned image
cbias_config uses - numpy 2.5.2, pandas 3.0.5, matplotlib 3.11.1), so target these APIs specifically:
- Standard library: os, sys, re, csv, json, pathlib, datetime, collections
- NumPy 2.5.2: for numerical computing
- Pandas 3.0.5: for data manipulation and analysis. DataFrame.applymap was REMOVED in pandas 3.0 -
  use .map. Text columns load as pandas' native str dtype, not object - detect them with
  pd.api.types.is_string_dtype(), not is_object_dtype() (the latter returns False for str).
- Matplotlib 3.11.1: for plotting and visualization. boxplot()'s labels= was renamed to tick_labels=
  in matplotlib 3.9 - use tick_labels=.
"""

DOMAIN_NOTES = """Process a Trello board exported as TWO files in the data directory (INPUT_FOLDER env
var), which carry DIFFERENT information and must be joined on Card ID:

1. <board>.json - the full board export (a JSON object / dict). Top-level keys: the board's own
   metadata (name, id, closed, dateLastActivity, prefs...) plus embedded collections - cards, lists,
   members, labels, customFields (field DEFINITIONS), checklists, memberships, and actions (activity
   history). ~335 cards, INCLUDING archived ones. There is no separate "boards" array.

2. <board>.csv - a flat card table (Trello's CSV export). ~216 rows, NON-ARCHIVED cards only. Every
   custom field is a populated column here. Join CSV "Card ID" -> JSON cards[].id.

KEY FACT: the list-type custom fields (Lab, Lead, Source) are NULL on every card in the JSON export,
but ARE populated in the CSV. The text field "Lab Name" is populated in BOTH (JSON ~72, CSV ~60).
So any lab/lead/source analysis must read the CSV, not the JSON - reading only the JSON makes those
fields look empty when they are not. Lab/lead/source analyses are limited to non-archived cards
(the CSV has no archived rows).

- custom fields (the report's stated focus; values verified, not assumed):
    - "Lab" (list): ~98 non-archived cards in the CSV. ~50 lab-name options (e.g. Anastasiou, Bauer,
      Bentley, Boulton, Devine, Downward, Heard, Hill, Kohl, Sahai, Swanton...).
    - "Lead" (list): ~99 cards. Values: Dave, Ken, Rocco, Sara, Stefania.
    - "Source" (list): ~83 cards. Values: Email, Help Desk, Slack, Training Workshop, Other STP.
    - "Lab Name" (text): free-text lab identifier, ~60 (CSV) / ~72 (JSON) cards, ~46 distinct
      spellings - inconsistent, so normalise before grouping by lab. Overlaps with "Lab" but is free
      text; the list "Lab" is the cleaner categorical signal.
    - "GitHub" (text): ~6 cards. "Project Agreement" / "PPMS Order" (text): ~1 card each.

- cards (JSON): id, name, desc, closed, idList (-> lists[].id), idMembers (-> members[].id), idLabels
  (-> labels[].id), due/start/dateLastActivity/dateClosed/dateCompleted (ISO-8601, for timing),
  customFieldItems (list of {idCustomField, value} - value is None for list-type fields, see above),
  attachments. Only ~2-4 cards have a due date; ~200 have members; ~146 have labels.

- lists (~10): the workflow stages, ordered by pos: Wishlist, Inbox, To Do, Ongoing, On Hold, Done,
  Billed, Training, Not required anymore, Catch Up Meetings. A card's CURRENT stage is its idList; its
  stage HISTORY is in `actions` (updateCard has data.listBefore/listAfter; moveCardFromBoard /
  moveInboxCardToBoard mark list transitions). Time-in-list metrics must reconstruct transitions from
  actions, not the final idList.

- members (~23): id -> fullName / username / initials.

- labels (~10): id -> name/color. User Support, Training, Workshop, Development, Grants, PR, Policy,
  Coaching, Experimentation!, Catch-up/Follow-up email.

- actions (list, CAPPED at 1000 by Trello): activity history for timing/velocity/bottleneck metrics.
  A truncated sample, not the complete history. Types include createCard, updateCard,
  updateCustomFieldItem, moveCardFromBoard, moveInboxCardToBoard, addMemberToCard, commentCard,
  addAttachmentToCard.

- checklists (~35): id, name, idCard, checkItems (state complete/incomplete).
"""


def extract_input_metadata(directory: str) -> str:
    """Extract metadata from the Trello JSON + CSV pair. The JSON carries board structure and
    activity history; the CSV carries the populated custom-field values (the JSON exports list-type
    custom fields as null, so reading the JSON alone makes Lab/Lead/Source look empty when they are
    not). Report both files' roles and the real custom-field population so ideation doesn't mistake a
    JSON-null custom field for a dead one."""
    json_file = None
    for f in sorted(Path(directory).glob('*.json')):
        json_file = f
        break
    if not json_file:
        return "No JSON file found in directory"

    csv_file = None
    for f in sorted(Path(directory).glob('*.csv')):
        csv_file = f
        break

    try:
        # encoding="utf-8" is required: the export is UTF-8 (lab names carry non-ASCII characters),
        # and the Windows host's default cp1252 would raise on the first umlaut, returning a garbage
        # error string to ideation/orchestrator instead of the metadata.
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        metadata = {
            "board_name": data.get("name", "Unknown"),
            "json_file": json_file.name,
            "json_card_count": len(data.get("cards", [])),  # includes archived
            "list_count": len(data.get("lists", [])),
            "member_count": len(data.get("members", [])),
            "label_count": len(data.get("labels", [])),
            "action_count": len(data.get("actions", [])),  # Trello caps this at 1000
            "lists": [l.get("name") for l in data.get("lists", [])],
        }

        # The list-type custom fields (Lab/Lead/Source) are null in the JSON and populated in the
        # CSV, so read the CSV's custom-field columns for the real population signal.
        if csv_file:
            df = pd.read_csv(csv_file, encoding="utf-8")
            metadata["csv_file"] = csv_file.name
            metadata["csv_card_count"] = len(df)  # non-archived only
            fields = []
            for col in ("Lab", "Lead", "Source", "Lab Name", "GitHub",
                        "Project Agreement", "PPMS Order"):
                if col in df.columns:
                    series = df[col].dropna()
                    fields.append({
                        "field": col,
                        "populated": int(len(series)),
                        "distinct_values": sorted(str(v) for v in series.unique())[:15],
                    })
            metadata["custom_fields_from_csv"] = fields

        return json.dumps(metadata, indent=2)

    except Exception as e:
        return f"Error reading Trello data: {str(e)}"


CONFIG = PipelineConfig(
    orchestrator_model="claude-opus-4-8",
    worker_model="deepseek-v4-pro",
    compiler_model="deepseek-v4-pro",
    requirements_evaluator_model="claude-sonnet-5",
    angle_model="deepseek-v4-pro",
    # D5 judging: frontier tier, matching orchestrator_model - once req_score is gone these two
    # judges (insight/soundness) are the entire quality bar (DIVERGER_PLAN.md §5).
    judge_model="claude-opus-4-8",
    # Reuses the pinned cbias-analysis image (numpy/pandas/matplotlib + more) rather than a dedicated
    # python-analysis target, which has no Dockerfile entry. A trello angle only ever imports the
    # numpy/pandas/matplotlib AVAILABLE_LIBRARIES lists, so the extra libraries are inert.
    docker_image="cbias-analysis:latest",
    available_libraries=AVAILABLE_LIBRARIES,
    domain_notes=DOMAIN_NOTES,
    extract_input_metadata=extract_input_metadata,
)
