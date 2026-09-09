# -*- coding: utf-8 -*-
"""Convert the PD-L1 sensitivity-report markdown into a single self-contained HTML file.

Motivation: the report's readers are biologists who may not have a markdown viewer. A single .html
file opens in any web browser, embeds the figures inline (as base64 data URIs, so it is one
self-contained file that can be emailed/uploaded anywhere), and can be printed to PDF directly from
the browser with Ctrl/Cmd-P -> "Save as PDF".

The converter is intentionally small and specific to this report's subset of CommonMark (headings,
paragraphs, bold/italic, inline code, fenced-free table syntax, blockquotes, and `![...](...)` image
links with RELATIVE paths resolved against the report's directory). It is not a general markdown
engine; it exists to ship this one report.

Run:  pixi run python explorations/cellsurvey/make_report_html.py
Writes: explorations/cellsurvey/pd1pdl1_threshold_sensitivity_report.html
"""

import base64
import html
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPORT = Path("explorations/cellsurvey/pd1pdl1_threshold_sensitivity_report.md")
OUT = Path("explorations/cellsurvey/pd1pdl1_threshold_sensitivity_report.html")

CSS = """
:root { color-scheme: light; }
body {
  font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  max-width: 52rem; margin: 2rem auto; padding: 0 1.25rem;
  line-height: 1.55; color: #1a1a1a; font-size: 16px;
}
h1 { font-size: 1.9rem; line-height: 1.2; border-bottom: 2px solid #444; padding-bottom: .4rem; }
h2 { font-size: 1.45rem; margin-top: 2.2rem; border-bottom: 1px solid #ccc; padding-bottom: .3rem; }
h3 { font-size: 1.15rem; margin-top: 1.6rem; }
img { max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 4px; margin: .5rem 0; }
table { border-collapse: collapse; margin: 1rem 0; }
th, td { border: 1px solid #ccc; padding: .35rem .7rem; text-align: left; }
th { background: #f2f2f2; }
blockquote {
  margin: 1rem 0; padding: .2rem 1.2rem; border-left: 4px solid #999;
  background: #f7f7f7; color: #333;
}
code { background: #f0f0f0; padding: .1rem .3rem; border-radius: 3px; font-size: .92em; }
hr { border: none; border-top: 1px solid #ccc; margin: 2rem 0; }
strong { font-weight: 700; }
"""


def inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # superscript characters like CD8+ (already fine as literal) - leave as-is
    return text


def render_image(md: str) -> str:
    m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", md)
    alt, src = m.group(1), m.group(2)
    src_path = (REPORT.parent / src).resolve()
    if src_path.exists():
        b64 = base64.b64encode(src_path.read_bytes()).decode("ascii")
        ext = src_path.suffix.lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml"}.get(
            ext.replace(".", ""), "image/png"
        )
        return f'<img alt="{html.escape(alt)}" src="data:{mime};base64,{b64}">'
    return f'<p><em>[image not found: {html.escape(src)}]</em></p>'


def convert(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    in_table = False
    i = 0
    while i < len(lines):
        ln = lines[i]
        stripped = ln.strip()

        # blank
        if not stripped:
            if in_table:
                out.append("</table>")
                in_table = False
            i += 1
            continue

        # image (on its own line)
        if stripped.startswith("!["):
            out.append(render_image(stripped))
            i += 1
            continue

        # horizontal rule
        if stripped == "---":
            if in_table:
                out.append("</table>")
                in_table = False
            out.append("<hr>")
            i += 1
            continue

        # table: detect a header row followed by |---| separator
        if "|" in stripped and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:\-|]+\|?\s*$", lines[i + 1]):
            header = [c.strip() for c in stripped.strip("|").split("|")]
            sep = lines[i + 1]
            aligns = ["left", "left"]  # default; parse separators below
            aligns = []
            for c in sep.strip("|").split("|"):
                c = c.strip()
                aligns.append("left" if (c.startswith(":") and c.endswith(":")) else
                              ("right" if c.endswith(":") else "left"))
            rows = []
            j = i + 2
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            out.append("<table>")
            out.append("<thead><tr>" + "".join(
                f"<th style='text-align:{a}'>{inline(h)}</th>" for h, a in zip(header, aligns)) + "</tr></thead>")
            out.append("<tbody>")
            for r in rows:
                out.append("<tr>" + "".join(
                    f"<td style='text-align:{a}'>{inline(c)}</td>" for c, a in zip(r, aligns)) + "</tr>")
            out.append("</tbody></table>")
            i = j
            continue

        # headings
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            if in_table:
                out.append("</table>")
                in_table = False
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # blockquote (including multiline)
        if stripped.startswith(">"):
            if in_table:
                out.append("</table>")
                in_table = False
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + inline(" ".join(quote_lines)) + "</blockquote>")
            continue

        # unordered list items
        m = re.match(r"^- \s+(.*)$", stripped) or re.match(r"^\*\s+(.*)$", stripped)
        if m:
            if in_table:
                out.append("</table>")
                in_table = False
            items = [m.group(1)]
            i += 1
            while i < len(lines) and re.match(r"^- \s+", lines[i].strip()):
                items.append(re.match(r"^- \s+(.*)$", lines[i].strip()).group(1))
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue

        # ordered list items
        m = re.match(r"^\d+\. \s+(.*)$", stripped)
        if m:
            if in_table:
                out.append("</table>")
                in_table = False
            items = [m.group(1)]
            i += 1
            while i < len(lines) and re.match(r"^\d+\. \s+", lines[i].strip()):
                items.append(re.match(r"^\d+\. \s+(.*)$", lines[i].strip()).group(1))
                i += 1
            out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol>")
            continue

        # paragraph (accumulate until blank / next block element)
        if in_table:
            out.append("</table>")
            in_table = False
        para = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|!\[|>|\s*- \s|\s*\* |\d+\. \s|---$)", lines[i].strip()
        ):
            para.append(lines[i].strip())
            i += 1
        out.append("<p>" + inline(" ".join(para)) + "</p>")

    if in_table:
        out.append("</table>")
    return "\n".join(out)


def main() -> None:
    md = REPORT.read_text(encoding="utf-8")
    body = convert(md)
    doc = (
        "<!DOCTYPE html>\n<html lang='en'>\n<head>\n<meta charset='utf-8'>\n"
        f"<title>PD-L1 across cell types — how robust is it?</title>\n<style>{CSS}</style>\n"
        "</head>\n<body>\n" + body + "\n</body>\n</html>\n"
    )
    OUT.write_text(doc, encoding="utf-8")
    print(f"Wrote {OUT} ({len(doc):,} bytes, figures embedded inline)")


if __name__ == "__main__":
    main()
