from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ebs_browser_probe import collect

DEFAULT_NO = "5"


def existing_answer_detail(book: dict) -> tuple[str | None, str]:
    for material in book.get("materials", []):
        if material.get("type") != "answer":
            continue
        resource = material.get("resource_page") or ""
        if "detailBkAnsInfo.ebs" in resource:
            query = parse_qs(urlparse(resource).query)
            return resource, (query.get("no") or [DEFAULT_NO])[0]
    return None, DEFAULT_NO


def main() -> int:
    parser = argparse.ArgumentParser(
        description="현재 catalog의 EBS 교재 정답 PDF direct URL 후보를 일괄 수집합니다."
    )
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.json"))
    parser.add_argument("--output", type=Path, default=Path("ebs-seed-answers.json"))
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    results = []

    for book in catalog.get("books", []):
        if book.get("publisher") != "EBS":
            continue
        book_id = (book.get("publisher_book_id") or "").strip()
        if not book_id:
            continue

        detail, answer_no = existing_answer_detail(book)
        try:
            probe = collect(book_id, answer_no, detail)
            resolved = [
                item for item in probe.get("resolved_files", [])
                if item.get("direct_url")
            ]
            results.append({
                "book_id": book.get("book_id"),
                "title": book.get("title"),
                "publisher_book_id": book_id,
                "answer_no": answer_no,
                "resource_page": probe.get("final_url") or detail,
                "resolved_files": resolved,
                "book_file_ids": probe.get("book_file_ids", []),
                "ok": bool(resolved),
                "error": None,
            })
        except Exception as exc:
            results.append({
                "book_id": book.get("book_id"),
                "title": book.get("title"),
                "publisher_book_id": book_id,
                "answer_no": answer_no,
                "resource_page": detail,
                "resolved_files": [],
                "book_file_ids": [],
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            })

    payload = {
        "count": len(results),
        "success_count": sum(1 for item in results if item["ok"]),
        "results": results,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    args.output.write_text(rendered + "\n", encoding="utf-8")

    # 일부 실패가 있어도 결과 artifact를 남길 수 있도록 0.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
