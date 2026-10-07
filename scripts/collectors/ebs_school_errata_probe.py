from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from ebs_school_material_probe import (
    GO_DETAIL_RE,
    collect_attachments,
    extract_go_detail_rows,
    normalize_title,
    rotating_batch,
    try_search_board,
)

BASES = {
    "ebs_primary": "https://primary.ebs.co.kr",
    "ebs_middle": "https://mid.ebs.co.kr",
}


def choose_strict_errata_row(rows: list[dict], title: str) -> dict | None:
    target = normalize_title(title)
    if not target:
        return None
    exact = []
    for row in rows:
        text = row.get("text") or ""
        normalized = normalize_title(text)
        if target in normalized:
            exact.append(row)
    if len(exact) == 1:
        return exact[0]
    # 동일 교재명의 정오표가 여러 개면 자동으로 하나를 고르지 않는다.
    return None


def inspect_one(page, book: dict) -> dict:
    site = book["publisher_site"]
    base = BASES[site]
    url = base + "/book/main/errataList"
    title = book["title"]
    textbook_id = book["publisher_book_id"]
    events = []

    def on_response(response):
        u = response.url
        ct = response.headers.get("content-type") or ""
        if (
            textbook_id in u
            or "errata" in u.lower()
            or "/board/common/download" in u
            or "octet-stream" in ct.lower()
            or "pdf" in ct.lower()
        ):
            events.append({
                "url": u,
                "status": response.status,
                "content_type": ct,
                "content_disposition": response.headers.get("content-disposition"),
            })

    page.on("response", on_response)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(700)

    rows = extract_go_detail_rows(page)
    matched = choose_strict_errata_row(rows, title)
    search = {"attempted": False, "input": None, "submitted": False}

    if matched is None:
        search = try_search_board(page, title)
        rows = extract_go_detail_rows(page)
        matched = choose_strict_errata_row(rows, title)

    post_id = None
    detail_clicked = False
    if matched:
        source = (matched.get("href") or "") + " " + (matched.get("onclick") or "")
        m = GO_DETAIL_RE.search(source)
        if m:
            post_id = m.group(1)

        try:
            target_text = matched.get("text") or ""
            page.locator("a").filter(has_text=target_text).first.click(timeout=5000)
            detail_clicked = True
            page.wait_for_timeout(1800)
        except Exception:
            if post_id:
                try:
                    page.evaluate(
                        "(id) => { if (typeof goDetail === 'function') goDetail(id, '-1'); }",
                        post_id,
                    )
                    detail_clicked = True
                    page.wait_for_timeout(1800)
                except Exception:
                    pass

    attachments = collect_attachments(page)
    direct_candidates = []
    for item in attachments:
        for direct in item.get("urls") or []:
            if "/board/common/download" not in direct:
                continue
            direct_candidates.append({
                "text": item.get("text") or "",
                "context": item.get("parent_text") or "",
                "url": direct,
            })

    body = page.locator("body").inner_text(timeout=10000)
    page.remove_listener("response", on_response)
    return {
        "book_id": book["book_id"],
        "publisher_site": site,
        "publisher_book_id": textbook_id,
        "title": title,
        "errata_page": url,
        "search": search,
        "row_count": len(rows),
        "matched_row": matched,
        "post_id": post_id,
        "detail_clicked": detail_clicked,
        "final_url": page.url,
        "attachments": attachments[:60],
        "direct_candidates": direct_candidates[:20],
        "network_events": events[-80:],
        "body_excerpt": body[-3500:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EBS 초등/중학 정오표 게시물과 첨부파일 존재 여부를 브라우저로 점검합니다."
    )
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.json"))
    parser.add_argument("--output", type=Path, default=Path("ebs-school-errata-probe.json"))
    parser.add_argument("--limit-per-site", type=int, default=4)
    args = parser.parse_args()
    if args.limit_per_site < 0:
        parser.error("--limit-per-site must be >= 0")

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    books = [
        b for b in catalog.get("books", [])
        if b.get("publisher") == "EBS"
        and b.get("publisher_site") in BASES
        and b.get("publisher_book_id")
        and any(m.get("type") == "errata" for m in b.get("materials", []))
    ]
    books.sort(key=lambda b: (
        b.get("publisher_site") or "",
        b.get("grade") or 99,
        b.get("subject") or "",
        b.get("title") or "",
    ))

    if args.limit_per_site:
        limited = []
        for site in ("ebs_primary", "ebs_middle"):
            site_books = [
                b for b in books
                if b.get("publisher_site") == site
            ]
            limited.extend(rotating_batch(site_books, args.limit_per_site))
        books = limited

    results = []
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
                results.append(inspect_one(page, book))
            except Exception as exc:
                results.append({
                    "book_id": book.get("book_id"),
                    "publisher_site": book.get("publisher_site"),
                    "publisher_book_id": book.get("publisher_book_id"),
                    "title": book.get("title"),
                    "error": f"{type(exc).__name__}: {exc}",
                })
        context.close()
        browser.close()

    payload = {"count": len(results), "results": results}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
