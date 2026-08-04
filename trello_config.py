"""Trello board analysis domain configuration for the pipeline."""

import json
from pathlib import Path
from config import PipelineConfig


AVAILABLE_LIBRARIES = """
Available libraries for imports:
- Standard library: os, sys, re, csv, json, pathlib, datetime, collections
- NumPy: for numerical computing
- Pandas: for data manipulation and analysis
- Matplotlib: for plotting and visualization
"""

DOMAIN_NOTES = """Process Trello board JSON exports. Access board structure via cards, lists, members, and metadata fields. Cards contain fields like idMembers, labels, due dates, and custom field values. Use pandas for data aggregation and analysis. The Trello JSON file is located in the /data directory (or use the INPUT_FOLDER environment variable)."""


def extract_input_metadata(directory: str) -> str:
    """Extract metadata from Trello JSON export file."""
    json_file = None
    for file in sorted(Path(directory).glob('*.json')):
        json_file = file
        break

    if not json_file:
        return "No JSON file found in directory"

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        metadata = {
            "filename": json_file.name,
            "root_type": type(data).__name__,
        }

        # Extract structure info
        if isinstance(data, dict):
            metadata["top_level_keys"] = list(data.keys())

            # Count items in major collections
            if "cards" in data:
                metadata["card_count"] = len(data["cards"])
                if data["cards"]:
                    metadata["sample_card_keys"] = list(data["cards"][0].keys())

            if "lists" in data:
                metadata["list_count"] = len(data["lists"])

            if "members" in data:
                metadata["member_count"] = len(data["members"])

            if "boards" in data:
                metadata["board_count"] = len(data["boards"])
                if data["boards"]:
                    metadata["first_board_name"] = data["boards"][0].get("name", "Unknown")

        return json.dumps(metadata, indent=2)

    except Exception as e:
        return f"Error reading Trello JSON: {str(e)}"


CONFIG = PipelineConfig(
    orchestrator_model="claude-opus-4-8",
    worker_model="deepseek-v4-pro",
    compiler_model="deepseek-v4-pro",
    requirements_evaluator_model="claude-sonnet-5",
    angle_model="deepseek-v4-pro",
    # D5 judging: frontier tier, matching orchestrator_model - once req_score is gone these two
    # judges (insight/soundness) are the entire quality bar (DIVERGER_PLAN.md §5).
    judge_model="claude-opus-4-8",
    docker_image="python-analysis:latest",
    available_libraries=AVAILABLE_LIBRARIES,
    domain_notes=DOMAIN_NOTES,
    extract_input_metadata=extract_input_metadata,
)
