from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

from ebsi_optional_material_probe import inspect_one


def mp3_material(book: dict) -> dict | None:
    return next(
        (item for item in book.get("materials", []) if item.get("type") == "mp3"),
        None,
    )


def valid_mp3_result(book: dict, result: dict) -> bool:
    book_id = book.get("publisher_book_id") or ""
    files = result.get("mp3_files") or []
    if not result.get("detail_clicked"):
        return False
    if book_id not in (result.get("final_url") or ""):
        return False
    if not files:
        return False
    expected_prefix = f"https://wdown.ebsi.co.kr/bookmp3/{book_id}/"
    return all(
        (item.get("url") or "").startswith(expected_prefix)
        for item in files
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EBSi 고등 영어 교재의 MP3 존재를 확인하고 교재별 MP3 페이지를 catalog에 연결합니다."
    )
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.json"))
    parser.add_argument("--report", type=Path, default=Path("ebsi-mp3-sync-report.json"))
    args = parser.parse_args()

    data = json.loads(args.catalog.read_text(encoding="utf-8"))
    books = [
        book for book in data.get("books", [])
        if book.get("publisher") == "EBS"
        and book.get("publisher_site") == "ebsi"
        and book.get("subject") == "영어"
        and book.get("publisher_book_id")
    ]
    books.sort(key=lambda book: book.get("title") or "")

    today = date.today().isoformat()
    checks = []
    changes = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ko-KR",
            accept_downloads=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        for book in books:
            try:
                result = inspect_one(page, book, "mp3")
                accepted = valid_mp3_result(book, result)
                checks.append({
                    "book_id": book.get("book_id"),
                    "publisher_book_id": book.get("publisher_book_id"),
                    "title": book.get("title"),
                    "accepted": accepted,
                    "mp3_file_count": result.get("mp3_file_count", 0),
                    "whole_file_count": len(result.get("whole_file_candidates", [])),
                    "resource_page": result.get("final_url"),
                    "error": None,
                })

                if not accepted:
                    continue

                material = mp3_material(book)
                if material is None:
                    material = {
                        "resource_id": f"{book['book_id']}-mp3",
                        "type": "mp3",
                        "title": "영어 MP3",
                        "resource_page": None,
                        "direct_url": None,
                        "access": "public",
                        "status": "needs_review",
                        "last_checked": None,
                        "availability": "unknown",
                    }
                    book.setdefault("materials", []).append(material)

                before = {
                    "resource_page": material.get("resource_page"),
                    "direct_url": material.get("direct_url"),
                    "access": material.get("access"),
                    "status": material.get("status"),
                    "availability": material.get("availability"),
                }
                after = {
                    "resource_page": result["final_url"],
                    "direct_url": None,
                    "access": "public",
                    "status": "ok",
                    "availability": "available",
                }

                if before != after:
                    material.update(after)
                    material["last_checked"] = today
                    changes.append({
                        "book_id": book.get("book_id"),
                        "title": book.get("title"),
                        "before": before,
                        "after": after,
                        "mp3_file_count": result.get("mp3_file_count", 0),
                        "whole_file_count": len(result.get("whole_file_candidates", [])),
                    })

            except Exception as exc:
                checks.append({
                    "book_id": book.get("book_id"),
                    "publisher_book_id": book.get("publisher_book_id"),
                    "title": book.get("title"),
                    "accepted": False,
                    "error": f"{type(exc).__name__}: {exc}",
                })

        context.close()
        browser.close()

    if changes:
        data.setdefault("meta", {})["generated_at"] = today
        args.catalog.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    report = {
        "checked_at": today,
        "checked_count": len(checks),
        "accepted_count": sum(1 for item in checks if item.get("accepted")),
        "changed_count": len(changes),
        "changes": changes,
        "checks": checks,
    }
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
