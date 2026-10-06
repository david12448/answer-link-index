from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

BASE = "https://www.ebsi.co.kr"


def detail_url(book_id: str) -> str:
    return f"{BASE}/ebs/pot/potg/DetailBkErrInfo.ebs?{urlencode({'bookId': book_id})}"


def search_url(title: str) -> str:
    params = {
        "ctgryCd": "",
        "connectionBookYn": "",
        "bookNm": title,
        "currentPage": "1",
    }
    return f"{BASE}/ebs/pot/potg/bkErrChrgMngList.ebs?{urlencode(params)}"


def download_url(book_id: str) -> str:
    return f"{BASE}/ebs/lms/lmsx/bkErrChrgMngFLdown.ebs?{urlencode({'bookId': book_id})}"


def probe_one(context, page, book: dict) -> dict:
    book_id = book["publisher_book_id"]
    title = book["title"]
    detail = detail_url(book_id)
    search = search_url(title)
    download = download_url(book_id)

    result = {
        "book_id": book.get("book_id"),
        "publisher_book_id": book_id,
        "title": title,
        "detail_url": detail,
        "search_url": search,
        "download_url": download,
        "detail_status": None,
        "detail_contains_title": False,
        "detail_text_excerpt": "",
        "search_status": None,
        "search_input_value": None,
        "search_contains_title": False,
        "download_status": None,
        "download_content_type": None,
        "download_content_disposition": None,
        "download_bytes": 0,
        "download_looks_like_file": False,
        "error": None,
    }

    try:
        response = page.goto(detail, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(1200)
        text = page.locator("body").inner_text(timeout=10000)
        result["detail_status"] = response.status if response else None
        result["detail_contains_title"] = title in text or book_id in page.content()
        result["detail_text_excerpt"] = text[:2000]
    except Exception as exc:
        result["error"] = f"detail: {type(exc).__name__}: {exc}"

    try:
        response = page.goto(search, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(1200)
        result["search_status"] = response.status if response else None
        locator = page.locator('input[name="bookNm"]')
        if locator.count():
            result["search_input_value"] = locator.first.input_value()
        text = page.locator("body").inner_text(timeout=10000)
        result["search_contains_title"] = title in text
    except Exception as exc:
        if not result["error"]:
            result["error"] = f"search: {type(exc).__name__}: {exc}"

    try:
        response = context.request.get(
            download,
            headers={
                "Referer": detail,
                "Accept": "application/pdf,application/octet-stream,*/*",
            },
            timeout=30000,
        )
        body = response.body()
        content_type = response.headers.get("content-type")
        disposition = response.headers.get("content-disposition")
        result["download_status"] = response.status
        result["download_content_type"] = content_type
        result["download_content_disposition"] = disposition
        result["download_bytes"] = len(body)
        result["download_looks_like_file"] = (
            response.ok
            and len(body) > 500
            and (
                (content_type and "pdf" in content_type.lower())
                or (content_type and "octet-stream" in content_type.lower())
                or (disposition and "attachment" in disposition.lower())
                or body.startswith(b"%PDF")
            )
        )
    except Exception as exc:
        if not result["error"]:
            result["error"] = f"download: {type(exc).__name__}: {exc}"

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="현재 EBS catalog의 정오표 상세/검색/다운로드 경로를 일괄 점검합니다.")
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.json"))
    parser.add_argument("--output", type=Path, default=Path("ebs-errata-probe.json"))
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    books = [
        book for book in catalog.get("books", [])
        if book.get("publisher") == "EBS" and book.get("publisher_book_id")
    ]

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ko-KR",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        for book in books:
            results.append(probe_one(context, page, book))
        context.close()
        browser.close()

    payload = {
        "count": len(results),
        "direct_download_count": sum(1 for item in results if item["download_looks_like_file"]),
        "search_prefill_count": sum(
            1 for item in results
            if item["search_input_value"] and item["search_input_value"].strip()
        ),
        "results": results,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
