"""Text/XML extraction and parsing helpers shared across the pipeline: pulling tagged content out
of LLM responses (with regex/markdown fallbacks that tolerate minor formatting drift), formatting
prompt templates, and parsing the report's guiding-questions section.
"""

import re
import xml.etree.ElementTree as ET


def extract_xml(text: str, tag: str) -> str:
    """Extracts the content of the specified XML tag from the given text (case-insensitive)."""
    match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else ""


def _extract_markdown_section(text: str, label: str, other_label: str) -> str:
    """Secondary extraction for the criteria-split call: recovers text under a markdown-style ATX
    heading naming `label` (e.g. '# IDEATION CRITERIA') when the model ignores the requested
    <ideation_criteria>/<deliverable_rubric> tags and instead mirrors the report's own markdown
    formatting back into its response - observed live against a report whose own text was heavily
    ATX-headed. Only tried after extract_xml() comes back empty for a given tag; captures from the
    end of the labeled heading line to the start of the next heading naming `other_label`, or end
    of text."""
    start_match = re.search(rf'^\s*#{{1,3}}\s*{re.escape(label)}\s*$', text, re.IGNORECASE | re.MULTILINE)
    if not start_match:
        return ""
    end_match = re.search(rf'^\s*#{{1,3}}\s*{re.escape(other_label)}\s*$', text[start_match.end():],
                           re.IGNORECASE | re.MULTILINE)
    end = start_match.end() + end_match.start() if end_match else len(text)
    return text[start_match.end():end].strip()


def format_prompt(template: str, **kwargs) -> str:
    """Format a prompt template, raising a clear error if a variable is missing."""
    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"Missing required prompt variable: {e}") from e


# Matches a bare `&` that isn't the start of a real XML entity/char reference - the model
# frequently writes plain prose (e.g. "cards & checklists") into <description> text, which is
# invalid XML and otherwise breaks the whole <tasks> block for a single stray character.
_BARE_AMPERSAND = re.compile(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)')


def _parse_xml_items(items_xml: str, item_tag: str, fallback_fields: tuple[str, ...]) -> list[dict]:
    """Parse a flat list of same-tag XML blocks (e.g. <task>...</task>, <angle>...</angle>) into
    dicts of their child-tag text. Falls back to a per-field regex scan if strict XML parsing
    fails (tolerates minor formatting drift from the model, e.g. a stray literal '<')."""
    items = []
    sanitized = _BARE_AMPERSAND.sub('&amp;', items_xml)
    try:
        root = ET.fromstring(f"<root>{sanitized}</root>")
        for item_elem in root.findall(item_tag):
            item = {}
            for child in item_elem:
                if child.text:
                    item[child.tag] = child.text.strip()
            if item:
                items.append(item)
    except ET.ParseError as e:
        print(f"Warning: Failed to parse <{item_tag}> XML: {e}")
        print(f"DEBUG: Raw {item_tag} xml (first 500 chars):\n{items_xml[:500]}")
        item_pattern = rf'<{item_tag}>(.*?)</{item_tag}>'
        for match in re.finditer(item_pattern, items_xml, re.DOTALL):
            item_content = match.group(1)
            item = {}
            for field in fallback_fields:
                field_match = re.search(f'<{field}>(.*?)</{field}>', item_content, re.DOTALL)
                if field_match:
                    item[field] = field_match.group(1).strip()
            if item:
                items.append(item)
    return items


def parse_tasks(tasks_xml: str) -> list[dict]:
    """Parse XML tasks into a list of task dictionaries."""
    return _parse_xml_items(tasks_xml, "task", ("function", "description", "input", "output"))


# Angle schema: {id, variables_involved, hypothesis, question_or_stakeholder_served,
# why_non_obvious, rough_method, requires} - the fields ANGLE_GENERATION_PROMPT_SUFFIX asks the
# model for. requires is instrumentation only - what libraries ideation reaches for, not a
# constraint on it (DIVERGER_PLAN.md §10) - and is never used to filter.
_ANGLE_FIELDS = (
    "id", "variables_involved", "hypothesis", "question_or_stakeholder_served",
    "why_non_obvious", "rough_method", "requires",
)


def parse_angles(angles_xml: str) -> list[dict]:
    """Parse XML angles into a list of angle dictionaries."""
    return _parse_xml_items(angles_xml, "angle", _ANGLE_FIELDS)


# Heading match is deliberately loose (any level, any wording containing "guiding question")
# since the only contract with the report author is that heading text, not its exact phrasing or
# markdown level.
_GUIDING_QUESTIONS_HEADING = re.compile(r'^#{1,6}\s*.*guiding question.*$', re.IGNORECASE | re.MULTILINE)
_NUMBERED_LIST_ITEM = re.compile(r'^\s*\d+\.\s+(.+)$', re.MULTILINE)

# Used when _parse_guiding_questions finds nothing - passed as the {guiding_question} value so the
# fallback suffix template still reads sensibly instead of showing a blank line.
_NO_GUIDING_QUESTION = "(none identified this run - use your own judgement)"


def _parse_guiding_questions(report: str) -> list[str]:
    """Pull the numbered guiding-question list out of the raw report's markdown - the second
    ideation cycling axis, alongside stance. Parsed from the report (deterministic markdown
    structure), not the LLM-paraphrased criteria. Looks for a heading mentioning "guiding
    question" (e.g. "## Guiding Questions for Analysis") and returns the numbered list items
    between it and the next heading. Returns [] if no such section is found or it contains no
    numbered items - callers must treat that as "cycle nothing", not retry harder.
    """
    heading_match = _GUIDING_QUESTIONS_HEADING.search(report)
    if not heading_match:
        return []
    section_start = heading_match.end()
    next_heading = re.search(r'^#{1,6}\s', report[section_start:], re.MULTILINE)
    section_end = section_start + next_heading.start() if next_heading else len(report)
    section = report[section_start:section_end]
    return [item.strip() for item in _NUMBERED_LIST_ITEM.findall(section) if item.strip()]
