from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

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

    publisher_keys = [
        (book.get("publisher_site"), book.get("publisher_book_id"))
        for book in data["books"]
        if book.get("publisher_book_id")
    ]
    duplicated_publisher_keys = duplicate_values(publisher_keys)
    if duplicated_publisher_keys:
        print(
            "[DUPLICATE publisher_site/publisher_book_id]",
            *[f"{site}: {book_id}" for site, book_id in duplicated_publisher_keys],
            sep="\n- ",
        )
        raise SystemExit(1)

    valid_grades = {
        "elementary": set(range(1, 7)),
        "middle": set(range(1, 4)),
        "high": set(range(1, 4)),
    }
    ebs_hosts = {
        "ebsi": "www.ebsi.co.kr",
        "ebs_primary": "primary.ebs.co.kr",
        "ebs_middle": "mid.ebs.co.kr",
    }

    for book in data["books"]:
        level = book.get("school_level")
        grade = book.get("grade")
        if grade is not None and level in valid_grades and grade not in valid_grades[level]:
            print(
                f"[GRADE] {book['book_id']}: "
                f"{level} 학교급에 grade={grade}는 허용되지 않습니다."
            )
            raise SystemExit(1)

        if book.get("publisher") == "EBS":
            site = book.get("publisher_site")
            publisher_book_id = str(book.get("publisher_book_id") or "")
            if site == "ebsi" and publisher_book_id and not publisher_book_id.startswith("LB"):
                print(
                    f"[EBS ID] {book['book_id']}: "
                    "ebsi 교재 ID는 LB... 형식이어야 합니다."
                )
                raise SystemExit(1)
            if (
                site in {"ebs_primary", "ebs_middle"}
                and publisher_book_id
                and not publisher_book_id.startswith("TB")
            ):
                print(
                    f"[EBS ID] {book['book_id']}: "
                    f"{site} 교재 ID는 TB... 형식이어야 합니다."
                )
                raise SystemExit(1)

            expected_host = ebs_hosts.get(site)
            official_page = book.get("official_page") or ""
            if expected_host and official_page:
                actual_host = urlparse(official_page).hostname
                if actual_host != expected_host:
                    print(
                        f"[EBS HOST] {book['book_id']}: "
                        f"{site} official_page은 {expected_host} 이어야 합니다 "
                        f"(현재 {actual_host})."
                    )
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

    for book in data["books"]:
        for material in book.get("materials", []):
            availability = material.get("availability")
            if availability == "available":
                if material.get("status") != "ok":
                    print(
                        f"[AVAILABILITY] {material['resource_id']}: "
                        "available 자료는 status=ok 이어야 합니다."
                    )
                    raise SystemExit(1)
                if not (material.get("direct_url") or material.get("resource_page")):
                    print(
                        f"[AVAILABILITY] {material['resource_id']}: "
                        "available 자료에는 공식 링크가 필요합니다."
                    )
                    raise SystemExit(1)
            elif availability in {"unavailable", "unknown"} and material.get("direct_url"):
                print(
                    f"[AVAILABILITY] {material['resource_id']}: "
                    f"{availability} 자료에는 direct_url을 둘 수 없습니다."
                )
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
