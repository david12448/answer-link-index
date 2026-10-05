from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "catalog.json"
SCHEMA = ROOT / "schema" / "book.schema.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def duplicate_values(values):
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def main():
    data = load_json(CATALOG)
    schema = load_json(SCHEMA)

    try:
        import jsonschema
    except ImportError as exc:
        raise SystemExit("jsonschema가 필요합니다: pip install jsonschema") from exc

    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        for error in errors:
            location = ".".join(map(str, error.path)) or "<root>"
            print(f"[SCHEMA] {location}: {error.message}")
        raise SystemExit(1)

    book_ids = [book["book_id"] for book in data["books"]]
    duplicated_books = duplicate_values(book_ids)
    if duplicated_books:
        print("[DUPLICATE book_id]", *duplicated_books, sep="\n- ")
        raise SystemExit(1)

    resource_ids = [
        material["resource_id"]
        for book in data["books"]
        for material in book.get("materials", [])
    ]
    duplicated_resources = duplicate_values(resource_ids)
    if duplicated_resources:
        print("[DUPLICATE resource_id]", *duplicated_resources, sep="\n- ")
        raise SystemExit(1)

    course_ids = [
        course["course_id"]
        for book in data["books"]
        for course in book.get("courses", [])
    ]
    duplicated_courses = duplicate_values(course_ids)
    if duplicated_courses:
        print("[DUPLICATE course_id]", *duplicated_courses, sep="\n- ")
        raise SystemExit(1)

    print(
        f"OK: {len(book_ids)} books / "
        f"{len(resource_ids)} resources / "
        f"{len(course_ids)} courses"
    )


if __name__ == "__main__":
    main()
