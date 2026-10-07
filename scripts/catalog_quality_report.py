from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "data" / "catalog.json"


def material(book: dict, kind: str) -> dict | None:
    return next(
        (item for item in book.get("materials", []) if item.get("type") == kind),
        None,
    )


def build_report(data: dict) -> dict:
    books = data.get("books", [])
    school_counts = Counter(book.get("school_level") or "unknown" for book in books)
    publisher_counts = Counter(book.get("publisher") or "unknown" for book in books)

    ebs_school = [
        book for book in books
        if book.get("publisher") == "EBS"
        and book.get("publisher_site") in {"ebs_primary", "ebs_middle"}
    ]

    answer_direct = [
        book for book in ebs_school
        if (material(book, "answer") or {}).get("direct_url")
    ]
    answer_pending = [
        book for book in ebs_school
        if not (material(book, "answer") or {}).get("direct_url")
    ]
    cover_ok = [book for book in ebs_school if book.get("cover_image_url")]
    cover_pending = [book for book in ebs_school if not book.get("cover_image_url")]
    errata_available = [
        book for book in ebs_school
        if (material(book, "errata") or {}).get("availability") == "available"
    ]
    errata_hidden = [
        book for book in ebs_school
        if (material(book, "errata") or {}).get("availability") != "available"
    ]

    optional = []
    for book in books:
        for kind in ("mp3", "additional"):
            item = material(book, kind)
            if item:
                optional.append({
                    "book_id": book.get("book_id"),
                    "title": book.get("title"),
                    "type": kind,
                    "availability": item.get("availability") or "unknown",
                })

    return {
        "total_books": len(books),
        "school_counts": dict(sorted(school_counts.items())),
        "publisher_counts": dict(sorted(publisher_counts.items())),
        "ebs_school": {
            "total": len(ebs_school),
            "answer_direct": len(answer_direct),
            "answer_pending": len(answer_pending),
            "cover_ok": len(cover_ok),
            "cover_pending": len(cover_pending),
            "errata_available": len(errata_available),
            "errata_hidden": len(errata_hidden),
        },
        "pending": {
            "answers": [
                {
                    "book_id": book.get("book_id"),
                    "title": book.get("title"),
                    "publisher_site": book.get("publisher_site"),
                    "publisher_book_id": book.get("publisher_book_id"),
                }
                for book in answer_pending
            ],
            "covers": [
                {
                    "book_id": book.get("book_id"),
                    "title": book.get("title"),
                    "publisher_site": book.get("publisher_site"),
                    "publisher_book_id": book.get("publisher_book_id"),
                }
                for book in cover_pending
            ],
        },
        "optional_materials": optional,
    }


def markdown(report: dict) -> str:
    ebs = report["ebs_school"]
    school = report["school_counts"]
    lines = [
        "## Catalog 품질 현황",
        "",
        f"- 전체 교재: **{report['total_books']}권**",
        (
            "- 학교급: "
            f"초등 {school.get('elementary', 0)} / "
            f"중등 {school.get('middle', 0)} / "
            f"고등 {school.get('high', 0)}"
        ),
        "",
        "### EBS 초등·중등",
        f"- 등록: **{ebs['total']}권**",
        f"- 정답 direct 확인: **{ebs['answer_direct']}권**",
        f"- 정답 direct 미확인: **{ebs['answer_pending']}권**",
        f"- 공식 표지 확인: **{ebs['cover_ok']}권**",
        f"- 공식 표지 미확인: **{ebs['cover_pending']}권**",
        f"- 정오표 표시: **{ebs['errata_available']}권**",
        f"- 정오표 숨김(없음/미확인): **{ebs['errata_hidden']}권**",
    ]

    pending_answers = report["pending"]["answers"][:12]
    if pending_answers:
        lines += ["", "### 다음 정답 점검 후보"]
        lines += [
            f"- {item['title']} ({item['publisher_book_id']})"
            for item in pending_answers
        ]

    pending_covers = report["pending"]["covers"][:12]
    if pending_covers:
        lines += ["", "### 다음 표지 점검 후보"]
        lines += [
            f"- {item['title']} ({item['publisher_book_id']})"
            for item in pending_covers
        ]

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="catalog의 자료/표지 검증 진행률을 요약합니다.")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.catalog.read_text(encoding="utf-8"))
    report = build_report(data)

    if args.json_output:
        args.json_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.markdown:
        print(markdown(report), end="")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
