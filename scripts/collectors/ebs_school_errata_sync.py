from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

from ebs_school_errata_probe import inspect_one


def errata_material(book: dict) -> dict | None:
    return next(
        (item for item in book.get("materials", []) if item.get("type") == "errata"),
        None,
    )


def verify_download(context, url: str, referer: str) -> dict:
    try:
        response = context.request.get(
            url,
            headers={
                "Referer": referer,
                "Accept": "application/pdf,application/octet-stream,*/*",
            },
            timeout=30000,
        )
        body = response.body()
        content_type = (response.headers.get("content-type") or "").lower()
        disposition = (response.headers.get("content-disposition") or "").lower()
        ok = (
            response.ok
            and len(body) > 500
            and (
                body.startswith(b"%PDF")
                or body.startswith(b"PK\x03\x04")
                or "application/pdf" in content_type
                or "octet-stream" in content_type
                or "attachment" in disposition
            )
        )
        return {
            "ok": ok,
            "status": response.status,
            "content_type": content_type,
            "content_disposition": disposition,
            "bytes": len(body),
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "content_type": None,
            "content_disposition": None,
            "bytes": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EBS 초등/중학의 새 정오표 첨부파일을 안전하게 찾아 catalog에 반영합니다."
    )
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.json"))
    parser.add_argument("--report", type=Path, default=Path("ebs-school-errata-sync-report.json"))
    parser.add_argument("--limit-per-site", type=int, default=6)
    args = parser.parse_args()
    if args.limit_per_site < 0:
        parser.error("--limit-per-site must be >= 0")

    data = json.loads(args.catalog.read_text(encoding="utf-8"))
    books = [
        book for book in data.get("books", [])
        if book.get("publisher") == "EBS"
        and book.get("publisher_site") in {"ebs_primary", "ebs_middle"}
        and book.get("publisher_book_id")
        and errata_material(book)
        and errata_material(book).get("availability") != "available"
    ]
    books.sort(key=lambda book: (
        book.get("publisher_site") or "",
        book.get("grade") or 99,
        book.get("subject") or "",
        book.get("title") or "",
    ))

    if args.limit_per_site:
        selected = []
        for site in ("ebs_primary", "ebs_middle"):
            selected.extend(
                [book for book in books if book.get("publisher_site") == site][
                    : args.limit_per_site
                ]
            )
        books = selected

    checks = []
    changes = []
    today = date.today().isoformat()

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
            material = errata_material(book)
            try:
                result = inspect_one(page, book)
                candidates = result.get("direct_candidates", [])
                candidate = candidates[0] if len(candidates) == 1 else None
                exact_post = bool(
                    result.get("matched_row")
                    and result.get("post_id")
                    and result.get("detail_clicked")
                )
                verification = None
                direct_url = None

                # 정오표 게시물 자체가 정확히 확인되면 뱃지는 표시한다.
                # 첨부가 정확히 하나이고 실제 파일 응답까지 확인되면 direct_url도 사용한다.
                if exact_post and candidate:
                    verification = verify_download(
                        context,
                        candidate["url"],
                        result.get("final_url") or result.get("errata_page"),
                    )
                    if verification["ok"]:
                        direct_url = candidate["url"]

                checks.append({
                    "book_id": book.get("book_id"),
                    "publisher_book_id": book.get("publisher_book_id"),
                    "title": book.get("title"),
                    "matched_row": (result.get("matched_row") or {}).get("text"),
                    "post_id": result.get("post_id"),
                    "candidate_count": len(candidates),
                    "candidate": candidate,
                    "verification": verification,
                    "exact_post": exact_post,
                    "accepted": exact_post,
                    "error": None,
                })

                if not exact_post:
                    continue

                before = {
                    "direct_url": material.get("direct_url"),
                    "resource_page": material.get("resource_page"),
                    "status": material.get("status"),
                    "access": material.get("access"),
                    "availability": material.get("availability"),
                }
                after = {
                    "direct_url": direct_url,
                    "resource_page": result.get("final_url") or result.get("errata_page"),
                    "status": "ok",
                    "access": "public",
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
                        "post_id": result.get("post_id"),
                        "filename": candidate.get("text"),
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
        "available_post_count": sum(1 for item in checks if item.get("accepted")),
        "direct_file_count": sum(
            1 for item in checks
            if item.get("verification") and item["verification"].get("ok")
        ),
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
