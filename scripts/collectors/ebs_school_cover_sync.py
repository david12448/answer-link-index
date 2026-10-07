from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


def rotating_batch(items: list[dict], limit: int) -> list[dict]:
    if not limit or len(items) <= limit:
        return items

    today = date.today()
    monday_epoch = date(2020, 1, 6)
    week_index = (today.toordinal() - monday_epoch.toordinal()) // 7
    start = (week_index * limit) % len(items)
    return [
        items[(start + index) % len(items)]
        for index in range(min(limit, len(items)))
    ]


def collect_cover_candidates(page, book: dict) -> list[str]:
    textbook_id = book.get("publisher_book_id") or ""
    values = page.locator("img").evaluate_all(
        """els => els.flatMap(img => [
          img.getAttribute('src'),
          img.getAttribute('data-src'),
          img.getAttribute('data-original'),
          img.currentSrc
        ]).filter(Boolean)"""
    )
    try:
        og_image = page.locator('meta[property="og:image"]').get_attribute("content")
        if og_image:
            values.append(og_image)
    except Exception:
        pass

    candidates = []
    for raw in values:
        url = urljoin(page.url, raw)
        lowered = url.lower()
        if "cbox.ebs.co.kr/textbook/" not in lowered:
            continue
        if textbook_id.lower() not in lowered:
            continue
        if url not in candidates:
            candidates.append(url)
    return candidates


def verify_image(context, url: str, referer: str) -> dict:
    try:
        response = context.request.get(
            url,
            headers={"Referer": referer, "Accept": "image/*,*/*"},
            timeout=30000,
        )
        body = response.body()
        content_type = (response.headers.get("content-type") or "").lower()
        ok = response.ok and content_type.startswith("image/") and len(body) > 1000
        return {
            "ok": ok,
            "status": response.status,
            "content_type": content_type,
            "bytes": len(body),
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "content_type": None,
            "bytes": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EBS 초등·중학 공식 교재 페이지에서 표지 이미지를 확인해 catalog에 반영합니다."
    )
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.json"))
    parser.add_argument("--report", type=Path, default=Path("ebs-school-cover-sync-report.json"))
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
        and book.get("official_page")
        and not book.get("cover_image_url")
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
            site_books = [
                book for book in books
                if book.get("publisher_site") == site
            ]
            selected.extend(rotating_batch(site_books, args.limit_per_site))
        books = selected

    today = date.today().isoformat()
    checks = []
    changes = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ko-KR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        for book in books:
            try:
                page.goto(
                    book["official_page"],
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                page.wait_for_timeout(800)

                candidates = collect_cover_candidates(page, book)
                verifications = [
                    {
                        "url": url,
                        **verify_image(context, url, book["official_page"]),
                    }
                    for url in candidates[:5]
                ]
                good = [item for item in verifications if item["ok"]]
                accepted = len(good) == 1

                checks.append({
                    "book_id": book.get("book_id"),
                    "publisher_book_id": book.get("publisher_book_id"),
                    "title": book.get("title"),
                    "candidate_count": len(candidates),
                    "accepted": accepted,
                    "candidate": good[0]["url"] if accepted else None,
                    "verifications": verifications,
                    "error": None,
                })

                if accepted:
                    before = book.get("cover_image_url")
                    after = good[0]["url"]
                    if before != after:
                        book["cover_image_url"] = after
                        changes.append({
                            "book_id": book.get("book_id"),
                            "title": book.get("title"),
                            "before": before,
                            "after": after,
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
