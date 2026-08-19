# -*- coding: utf-8 -*-
"""One-off anonymisation of the public Trello board export.

Strategy (deliberately conservative - replace only what is confidently a person
or a lab, never software names / card titles / prose):

  People (-> "Person A", "Person B", ...):
    1. Board members (authoritative fullName + username from the JSON `members`).
    2. Every "Name <email>" sender/recipient in the emails embedded in comments
       and card descriptions, EXCLUDING group/service addresses.
    3. A curated list of real people mentioned in prose who have no email in the
       export (external collaborators).
    4. Bare email addresses whose local part maps to a real name (first.last),
       for emails that appear without a paired display name.

  Labs / PIs (-> "Lab A", "Lab B", ...): the distinct values of the CSV "Lab"
  and "Lab Name" fields (PI surnames plus a few facility/STP names), extended by
  "<Name> Lab" mentions that don't appear in those columns.

  Fixed redactions: internal IP / machine hostname / SMB & SharePoint personal
  paths / booking-link user tokens / Trello board-forward addresses.

Writes _anonymisation_map.json so the substitution is auditable and reversible.

Run:  pixi run python _anonymise_trello.py
"""

import csv
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path("inputs/trello_data")
JSON_PATH = DATA_DIR / "gtV6Qf7a - image-analysis-stuff.json"
CSV_PATH = DATA_DIR / "gtV6Qf7a - image-analysis-stuff.csv"
# Anonymised outputs are written to a SEPARATE directory; the originals in
# inputs/trello_data are left untouched.
OUT_DIR = Path("inputs/trello_data_anonymised")
OUT_JSON = OUT_DIR / JSON_PATH.name
OUT_CSV = OUT_DIR / CSV_PATH.name
MAP_PATH = Path("_anonymisation_map.json")

# Group / service / automation addresses that are NOT people.
NON_PERSON_EMAILS = {
    "bioimage-analysis@crick.ac.uk",
    "calm@crick.ac.uk",
    "bioinformatics@crick.ac.uk",
    "biostatistics@crick.ac.uk",
    "data-challenge@crick.ac.uk",
    "its-helpdesk@crick.ac.uk",
    "image-analysis-list@lists.crick.ac.uk",
    "noreply@wetransfer.com",
    "tech.meetings.events@zohomail.eu",
    "eusupport_imaris@andor.com",
    # opaque booking-link user tokens (handled separately below)
}

# Curated list of real people mentioned in prose (no email, or referred to by
# full name only). External collaborators and group PI / facility staff.
PROSE_NAMES = [
    "Jean-Yves Tinevez",
    "Christian Tischer",
    "Anna Klemm",
    "Damian Dalle Nogare",
    "Dan Gunton",
    "Phil Hobson",
    "Noor Sakki",
    "Omar Bouricha",
    "Keyu Shen",
    "Hale Phillips",
    "Harrison Crask",
    "Simon Cleary",
    "Patrick Phillips",
    "Freya Hoddle",
    "Dominic Simpson",
    "Bob Thomas",
    "Chris Tsantoulas",
    "Chris Hadjigeorgiou",
    "Mike Devine",
    "Andreas Schaefer",
    "Leanne Li",
    "Carola Vinuesa",
    "Edith Heard",
    "Alex Gould",
    "Cristina Lo Celso",
    "Virginia Silio",
    "Rute Ferreira",
    "Kim Meechan",
    "Georgia Golfis",
    "Zehua Dong",
    "Juqi Zou",
    "Beth Askham",
    "Mark Leake",
    "Aditya Shroff",
    "Julia Rodrigues",
    "Jing Zheng",
    "Katherine Courtis",
    "Anastassia Tchoumakova",
    "John Fadul",
    "Daniel Rolfe",
    "Rebecca Mitchell",
    "Georgina Fletcher",
    "Nicola Tapon",
    "Nic Tapon",
    "Shaimaa Hassan",
    "Jarod Zvartau-Hind",
    "Zuzanna Jablonska",
    "Benjamin Aleyakpo",
    "Gisela Tsoi",
    "Alisa Kinaret",
    "Aashika Sekar",
    "Bogdan Margineanu",
    "Mireia Larrosa-Godall",
    "Maria Benito-Jardon",
    "Solene Gilbert-Debaisieux",
    "Le He",
]

# Terms that look like "<Name> Lab" / PI surnames not already in CSV Lab columns
# and found in prose ("Devine's lab", "Garcia-Manyes Lab", ...). These are
# already largely covered by the CSV Lab/Lab Name columns; add any stragglers.
EXTRA_LABS = [
    "Garcia-Manyes",
    "Elosegui-Artola",
    "de Strooper",
    "Arancibia Carcamo",
]

# Bearer of the fixed redactions (hostnames / IPs / personal paths / tokens).
FIXED_PATTERNS = [
    (r"10\.2\.58\.205", "10.0.0.1"),
    (r"5T95M34(?:\.[a-z]+\.org)?", "WS3.example.org"),
    (r"smb://data2\.thecrick\.org/[^\s>\"'}]+", "smb://<fileshare>/<path>"),
    (r"\\\\data2\.thecrick\.org\\[^\s>\"'}]+", "\\\\<fileshare>\\<path>"),
    (r"ondemand001\.nemo\.thecrick\.org", "ondemand001.<cluster>.example.org"),
    (r"rodrigj1_crick_ac_uk", "<username>"),
    (r"6a2f989c9bc54d02a22b5797e647f357@crick\.ac\.uk", "<booking-user>@example.org"),
    (r"ccb43e5c3de741c680ff0a12ad8d91ec@crick\.ac\.uk", "<booking-user>@example.org"),
    (r"d4b915488d774ba3bb17791e0c9e1b93@crick\.ac\.uk", "<booking-user>@example.org"),
    # Trello board "email-to-board" forward addresses: username + '+' + opaque hash.
    # Generalised, since the hash rotates per card.
    (r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)?\+[0-9a-z]+(?:[+\-][0-9a-z]+)*@boards\.trello\.com",
     "<board-forward>@boards.trello.com"),
]


def excel_label(n: int) -> str:
    """0 -> A, 1 -> B, ..., 25 -> Z, 26 -> AA, ..."""
    s = ""
    n += 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        s = chr(ord("A") + rem) + s
    return s


def collect_blob(data):
    parts = []
    for c in data.get("cards", []):
        parts.append(c.get("name", "") or "")
        parts.append(c.get("desc", "") or "")
        parts.append(c.get("originalDesc", "") or "")
        for att in c.get("attachments", []) or []:
            if isinstance(att, dict):
                for k in ("name", "url", "fileName", "idMember"):
                    v = att.get(k)
                    if isinstance(v, str):
                        parts.append(v)
    for a in data.get("actions", []):
        t = a.get("data", {}).get("text")
        if t:
            parts.append(t)
        # capture member/memberCreator/attachment names too
        for pfx in ("memberCreator", "member"):
            sub = a.get(pfx)
            if isinstance(sub, dict):
                for k in ("fullName", "username", "name", "email"):
                    v = sub.get(k)
                    if isinstance(v, str):
                        parts.append(v)
        att = a.get("data", {}).get("attachment")
        if isinstance(att, dict):
            for k in ("name", "url", "fileName"):
                v = att.get(k)
                if isinstance(v, str):
                    parts.append(v)
    for ch in data.get("checklists", []):
        parts.append(ch.get("name", "") or "")
        for it in ch.get("checkItems", []):
            parts.append(it.get("name", "") or "")
    return "\n".join(parts)


def build_people(data, blob):
    """Return ordered list of (canonical_name, label)."""
    canon = []  # ordered canonical names

    # 1. Board members.
    for m in data.get("members", []):
        full = (m.get("fullName") or "").strip()
        if full and full not in canon:
            canon.append(full)

    # 2. "Name <email>" pairs and bare emails (excluding group/service).
    email_to_name = {}
    for m in re.finditer(
        r"([A-Z][A-Za-z'\-\.]+(?:\s+[A-Za-z'\-\.]+){1,4})\s*<\s*([^<>\s]+@[^<>\s]+)\s*>",
        blob,
    ):
        name = m.group(1).strip()
        em = m.group(2).lower()
        # strip stray "mailto:" appearing inside markdown link brackets
        if em.startswith("mailto:"):
            em = em[len("mailto:"):]
        email_to_name.setdefault(em, name)

    bare_emails = set(re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", blob))
    bare_emails = {e.lower() for e in bare_emails}

    def name_from_email(em):
        em = em.lower()
        if em in email_to_name:
            return email_to_name[em]
        local = em.split("@")[0]
        if local.startswith("mailto:"):
            local = local[len("mailto:"):]
        parts = re.split(r"[._\-+]+", local)
        words = [p for p in parts if p and not p.isdigit()]
        if not words:
            return None
        return " ".join(w.capitalize() for w in words)

    personal_emails = []
    for em in sorted(bare_emails):
        if em in NON_PERSON_EMAILS or em.startswith("mailto:"):
            continue
        # trello board-forward addresses (username+hash) treated as fixed, not a person
        if "@boards.trello.com" in em:
            continue
        # booking-link user tokens (opaque hex) - fixed redaction
        if re.fullmatch(r"[0-9a-f]{32}@crick\.ac\.uk", em):
            continue
        personal_emails.append(em)

    for em in personal_emails:
        name = name_from_email(em)
        if name and name not in canon:
            canon.append(name)

    # 3. Curated prose names.
    for name in PROSE_NAMES:
        if name and name not in canon:
            canon.append(name)

    return {name: "Person " + excel_label(i) for i, name in enumerate(canon)}


def build_labs(data, blob):
    """Distinct lab/PI values from CSV columns + prose '<Name> Lab' + extras."""
    labs = set()
    # CSV columns
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for col in ("Lab", "Lab Name"):
            v = (r.get(col) or "").strip()
            if v:
                labs.add(v)
    # "(Gould Lab)", "Garcia-Manyes Lab, NE302" style mentions in prose
    for m in re.finditer(r"\b([A-Z][A-Za-z'\-]+(?:[ \-][A-Za-z'\-]+)?)\s+Lab\b", blob):
        labs.add(m.group(1).strip())
    labs.update(EXTRA_LABS)
    # sort for stable labels; put pure-PI surnames first (short) doesn't matter,
    # but sort alphabetically for determinism.
    return {lab: "Lab " + excel_label(i) for i, lab in enumerate(sorted(labs))}


def main():
    data = json.load(open(JSON_PATH, "r", encoding="utf-8"))
    blob = collect_blob(data)
    people = build_people(data, blob)
    labs = build_labs(data, blob)

    # Build the master replacement table: string -> label.
    # people: full names; board member usernames -> same person.
    username_map = {}
    for m in data.get("members", []):
        full = (m.get("fullName") or "").strip()
        user = (m.get("username") or "").strip()
        if full in people:
            username_map[user] = people[full]

    # People: full names + board-member usernames -> "Person X". Case-sensitive
    # (these are proper nouns; safe to replace literally).
    people_ordered = sorted(
        [(name, label) for name, label in people.items()],
        key=lambda kv: len(kv[0]), reverse=True,
    )
    username_ordered = sorted(
        [(user, label) for user, label in username_map.items()],
        key=lambda kv: len(kv[0]), reverse=True,
    )

    # Emails: every real-person email -> "Person X", matched CASE-INSENSITIVELY.
    # Derive the canonical name for each email the same way build_people does.
    email_to_person = {}
    for name, label in people.items():
        pass  # name mapping already in `people`; below we bind emails -> label.

    def person_name_for_email(em):
        em = em.lower()
        if em.startswith("mailto:"):
            em = em[len("mailto:"):]
        # exact display-name pairing first (from "Name <email>")
        for name, label in people.items():
            # try to match email local part to a known person name cheaply:
            pass
        local = em.split("@")[0]
        parts = re.split(r"[._\-+]+", local)
        words = [p for p in parts if p and not p.isdigit()]
        guess = " ".join(w.capitalize() for w in words)
        if guess in people:
            return guess
        # fallback: match against known names by normalized comparison
        for name in people:
            nn = re.sub(r"[^a-z]", "", name.lower())
            gg = re.sub(r"[^a-z]", "", guess.lower())
            if nn and gg and (nn == gg or nn.startswith(gg) or gg.startswith(nn)):
                return name
        return None

    all_emails = sorted(set(re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", blob)))
    email_repl = {}  # lowercased email -> label
    # Track extra people discovered only via email, to keep labels stable and
    # complete. We append them to `people` so the audit map is complete.
    extra_names = {}
    next_idx = len(people)
    for em in all_emails:
        low = em.lower()
        if low in NON_PERSON_EMAILS or "@boards.trello.com" in low:
            continue
        if re.fullmatch(r"[0-9a-f]{32}@crick\.ac\.uk", low):
            continue
        if "@boards." in low:
            continue
        name = person_name_for_email(em)
        if name is None:
            # derive a name from the local part; it's a real person even if not
            # otherwise mentioned.
            local = low.split("@")[0]
            parts = re.split(r"[._\-+]+", local)
            words = [p for p in parts if p and not p.isdigit()]
            name = " ".join(w.capitalize() for w in words) if words else None
        if not name:
            continue
        if name not in people:
            label = "Person " + excel_label(next_idx)
            next_idx += 1
            people[name] = label
            people_ordered = sorted(people.items(), key=lambda kv: len(kv[0]), reverse=True)
        email_repl[low] = people[name]
    email_ordered = sorted(email_repl.items(), key=lambda kv: len(kv[0]), reverse=True)

    lab_ordered = sorted(labs.items(), key=lambda kv: len(kv[0]), reverse=True)

    # Board members' first-name and surname tokens (for sign-off "Stefania", or a
    # surname in an attachment filename "Marcotti_....pdf"). Derived from the
    # member fullNames AFTER people is finalised (it gained email-only extras above).
    # Also derive first-name tokens (>=4 chars) and surname tokens for EVERY
    # person, so greeting "Hi Rahma," or "Jean-Yves' group" get caught too. Short
    # first names (Ken, Amy, Joy, Sara...) are intentionally left: too ambiguous.
    member_tokens = {}
    for name, label in people.items():
        words = name.split()
        if not words:
            continue
        first = words[0].rstrip("'")
        if len(first) >= 4 and len(first) <= 40:
            member_tokens[first] = label                 # first name (>=4 chars)
        if len(words) >= 2:
            member_tokens[" ".join(words[1:])] = label    # surname(s)
            for w in words[1:]:
                if len(w) >= 4:
                    member_tokens[w] = label

    # Member first/last name tokens (for sign-offs and surnames in filenames).
    token_ordered = sorted(member_tokens.items(), key=lambda kv: len(kv[0]), reverse=True)

    def scrub(s):
        if not isinstance(s, str) or not s:
            return s
        for pat, repl in FIXED_PATTERNS:
            s = re.sub(pat, repl, s)
        # labs (word-boundary, skip ambiguous short tokens)
        for old, new in lab_ordered:
            if len(old) < 3:
                continue
            s = re.sub(r"(?<![A-Za-z0-9])" + re.escape(old) + r"(?![A-Za-z0-9])", new, s)
        # emails (case-insensitive)
        for old, new in email_ordered:
            s = re.sub(re.escape(old), new, s, flags=re.IGNORECASE)
        # people full names (literal, longest-first)
        for old, new in people_ordered:
            s = s.replace(old, new)
        # member first/last name tokens (word boundary)
        for old, new in token_ordered:
            s = re.sub(r"(?<![A-Za-z0-9])" + re.escape(old) + r"(?![A-Za-z0-9])", new, s)
        # usernames (literal)
        for old, new in username_ordered:
            s = s.replace(old, new)
        return s

    # Apply to JSON: generic depth-first scrub of every string value. This
    # catches nested member objects (memberCreator.nonPublic.fullName,
    # data.member.name/email, etc.) that a field-by-field pass misses. Opaque ids
    # (hex) never match a name/email pattern, so they pass through unchanged.
    def scrub_obj(o):
        if isinstance(o, dict):
            return {k: scrub_obj(v) for k, v in o.items()}
        if isinstance(o, list):
            return [scrub_obj(v) for v in o]
        if isinstance(o, str):
            return scrub(o)
        return o

    member_label = {}
    for m in data.get("members", []):
        full = (m.get("fullName") or "").strip()
        if full in people:
            member_label[m.get("id")] = people[full]
            m["fullName"] = people[full]
            m["username"] = people[full].replace(" ", "_").lower()
            m["initials"] = people[full].replace("Person ", "")[:2]

    data = scrub_obj(data)

    # Write anonymised JSON/CSV to the separate output directory.
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(data, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # Apply to CSV (whole-file text scrub, matching how it was read as UTF-8).
    csv_text = open(CSV_PATH, "r", encoding="utf-8").read()
    open(OUT_CSV, "w", encoding="utf-8").write(scrub(csv_text))

    # Audit map.
    audit = {
        "people": people,
        "labs": labs,
        "fixed_patterns": [{"pattern": p, "replacement": r} for p, r in FIXED_PATTERNS],
        "username_map": username_map,
    }
    json.dump(audit, open(MAP_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"Anonymised {len(people)} people, {len(labs)} labs.")
    print(f"Audit map -> {MAP_PATH}")


if __name__ == "__main__":
    main()
