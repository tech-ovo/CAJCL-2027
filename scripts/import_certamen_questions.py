"""Bulk importer for Certamen questions into Turso or local SQLite.

Usage:
    # Import a JSON file into local/configured Turso DB:
    python scripts/import_certamen_questions.py --file questions.json

    # Import into remote Turso database:
    TURSO_CERTAMEN_DATABASE_URL="libsql://..." TURSO_CERTAMEN_AUTH_TOKEN="..." \
        python scripts/import_certamen_questions.py --file questions.json

    # Replace existing questions:
    python scripts/import_certamen_questions.py --file questions.json --replace
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.lib import certamen_db


def parse_answers(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(a).strip() for a in raw if str(a).strip()]
    text = str(raw or "").strip()
    parts = re.split(r"\s*\(or\s+|\s+or\s+|\s*;\s*|\s*,\s*", text, flags=re.IGNORECASE)
    cleaned = [p.strip().rstrip(")").strip().strip("'\"`") for p in parts]
    return [c for c in cleaned if c]


def flatten_question(q: dict) -> list[dict]:
    """Ensure tossups and any boni are converted to standalone 10-pt tossups."""
    base_id = str(q.get("id") or f"q_{abs(hash(q.get('tossup', '')))}")
    cat = str(q.get("category", "grammar")).lower().strip()
    diff = str(q.get("difficulty") or q.get("level", "novice")).lower().strip()
    tossup = str(q.get("tossup") or q.get("question", "")).strip()
    answers = parse_answers(q.get("answers", []))
    expl = q.get("explanation")
    source = q.get("source")
    pmark = q.get("powerMarkIndex") or q.get("power_mark_index")

    results = []
    if tossup and answers:
        results.append({
            "id": base_id,
            "category": cat,
            "difficulty": diff,
            "tossup": tossup,
            "answers": answers,
            "explanation": expl,
            "source": source,
            "powerMarkIndex": pmark,
        })

    # Flatten boni if provided
    boni = q.get("boni") or []
    for idx, b in enumerate(boni, start=1):
        b_prompt = str(b.get("prompt", "")).strip()
        b_answers = parse_answers(b.get("answers", []))
        if b_prompt and b_answers:
            results.append({
                "id": f"{base_id}-b{idx}",
                "category": cat,
                "difficulty": diff,
                "tossup": b_prompt,
                "answers": b_answers,
                "explanation": expl,
                "source": source,
                "powerMarkIndex": None,
            })

    return results


def load_from_json(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("JSON file must contain an array of question objects")
    questions = []
    for item in data:
        questions.extend(flatten_question(item))
    return questions


def load_from_csv(path: Path, default_cat: str = "grammar", default_diff: str = "novice") -> list[dict]:
    questions = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = None
        for row in reader:
            if not row or not any(row):
                continue
            if header is None:
                # Check if first line is header
                lowered = [c.lower().strip() for c in row]
                if "tossup" in lowered or "question" in lowered:
                    header = lowered
                    continue
                else:
                    header = []
            if header and len(header) >= 2:
                row_dict = dict(zip(header, row))
                questions.extend(flatten_question(row_dict))
            else:
                # Fallback to column indices: [id, tossup, answers, category, difficulty]
                qid = row[0].strip() if len(row) > 0 else ""
                tossup = row[1].strip() if len(row) > 1 else ""
                ans = row[2].strip() if len(row) > 2 else ""
                cat = row[3].strip() if len(row) > 3 else default_cat
                diff = row[4].strip() if len(row) > 4 else default_diff
                if tossup and ans:
                    questions.extend(flatten_question({
                        "id": qid or None,
                        "tossup": tossup,
                        "answers": parse_answers(ans),
                        "category": cat,
                        "difficulty": diff,
                    }))
    return questions


def main():
    parser = argparse.ArgumentParser(description="Import Certamen questions into Turso/SQLite")
    parser.add_argument("--file", "-f", type=Path, required=True, help="Path to JSON or CSV file")
    parser.add_argument("--replace", action="store_true", help="Delete existing questions before importing")
    parser.add_argument("--category", default="grammar", help="Default category if missing in CSV")
    parser.add_argument("--difficulty", default="novice", help="Default difficulty if missing in CSV")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    suffix = args.file.suffix.lower()
    if suffix == ".json":
        questions = load_from_json(args.file)
    elif suffix in (".csv", ".tsv"):
        questions = load_from_csv(args.file, args.category, args.difficulty)
    else:
        print(f"Error: Unsupported file format {suffix}. Use .json or .csv.", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(questions)} questions from {args.file}")
    res = certamen_db.import_questions(questions, replace=args.replace)
    url, _, is_remote = certamen_db.get_certamen_db_config()
    print(f"Successfully imported {res['imported']} questions into {'Turso (' + url + ')' if is_remote else 'local database (' + url + ')'}!")


if __name__ == "__main__":
    main()
