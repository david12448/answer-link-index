from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

BASE = "https://www.ebsi.co.kr"
BOOK_FL_RE = re.compile(r"fncDownFile\s*\(\s*['\"]?([^'\"\)\s]+)", re.IGNORECASE)
PDF_RE = re.compile(r"\.pdf(?:$|[?#])", re.IGNORECASE)


def detail_url(book_id: str, answer_no: str) -> str:
    params = {
        "year_n": "",
        "bookId": book_id,
        "no": answer_no,
        "devonTargetRow": "1",
        "catGbn": "",
        "connectionBookYn": "",
        "bookNm": "",
        "currentPage": "",
    }
    return f"{BASE}/ebs/pot/potg/detailBkAnsInfo.ebs?{urlencode(params)}"


def normalize_file_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("//"):
        return "https:" + value
    if value.startswith("/"):
        return BASE + value
    return value


def collect(book_id: str, answer_no: str, url: str | None = None) -> dict:
    target = url or detail_url(book_id, answer_no)
    network = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="ko-KR",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/154.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        def on_response(response):
            u = response.url
            if (
                "bkAnsMngFLdown" in u
                or "detailBkAnsInfo" in u
                or u.lower().endswith(".pdf")
            ):
                network.append({
                    "url": u,
                    "status": response.status,
                    "content_type": response.headers.get("content-type"),
                })

        page.on("response", on_response)
        page.goto(target, wait_until="domcontentloaded", timeout=60000)

        # EBS가 첨부파일 영역을 추가 요청으로 채우는 경우를 위해 잠시 기다린다.
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(2500)

        html = page.content()
        body_text = page.locator("body").inner_text(timeout=10000)

        candidates = page.locator("a, button, input").evaluate_all(
            """els => els.map(el => ({
                tag: el.tagName,
                text: (el.innerText || el.value || el.textContent || '').trim(),
                href: el.getAttribute('href'),
                onclick: el.getAttribute('onclick'),
                id: el.id || null,
                name: el.getAttribute('name'),
                data: Object.fromEntries([...el.attributes]
                  .filter(a => a.name.startsWith('data-'))
                  .map(a => [a.name, a.value]))
            })).filter(x => {
                const s = JSON.stringify(x).toLowerCase();
                return s.includes('첨부') || s.includes('다운') ||
                       s.includes('.pdf') || s.includes('fncdownfile') ||
                       s.includes('정답');
            })"""
        )

        book_file_ids = set()
        for value in BOOK_FL_RE.findall(html):
            if value and value.lower() != "bookflid":
                book_file_ids.add(value)

        for item in candidates:
            onclick = item.get("onclick") or ""
            for value in BOOK_FL_RE.findall(onclick):
                if value and value.lower() != "bookflid":
                    book_file_ids.add(value)
            for key, value in (item.get("data") or {}).items():
                if "bookfl" in key.lower() and value:
                    book_file_ids.add(value)

        resolved = []
        for book_fl_id in sorted(book_file_ids):
            ajax = f"{BASE}/ebs/lms/lmsk/bkAnsMngFLdown.ajax?{urlencode({'bookFlId': book_fl_id})}"
            try:
                response = context.request.get(
                    ajax,
                    headers={
                        "Referer": page.url,
                        "X-Requested-With": "XMLHttpRequest",
                        "Accept": "application/json,text/javascript,*/*;q=0.1",
                    },
                    timeout=30000,
                )
                payload = response.json()
                direct = normalize_file_url(payload.get("flNm"))
                resolved.append({
                    "book_fl_id": book_fl_id,
                    "ajax_url": ajax,
                    "status": response.status,
                    "success": str(payload.get("success")) == "1",
                    "direct_url": direct,
                    "filename": payload.get("svNm"),
                    "is_pdf": bool(direct and PDF_RE.search(direct)),
                    "payload": payload,
                })
            except Exception as exc:
                resolved.append({
                    "book_fl_id": book_fl_id,
                    "ajax_url": ajax,
                    "status": None,
                    "success": False,
                    "direct_url": None,
                    "filename": None,
                    "is_pdf": False,
                    "error": f"{type(exc).__name__}: {exc}",
                })

        # 일부 페이지는 bookFlId를 정적 DOM에 두지 않고 클릭 시 요청을 만든다.
        # 이 경우 후보 첨부 링크를 한 번 클릭해 network 이벤트를 관찰한다.
        if not resolved:
            clickable = page.locator("a, button").filter(
                has_text=re.compile(r"첨부|다운|정답|\.pdf", re.IGNORECASE)
            )
            count = min(clickable.count(), 8)
            for i in range(count):
                node = clickable.nth(i)
                try:
                    with page.expect_download(timeout=4000) as download_info:
                        node.click(timeout=5000)
                    download = download_info.value
                    suggested = download.suggested_filename
                    resolved.append({
                        "book_fl_id": None,
                        "ajax_url": None,
                        "status": None,
                        "success": True,
                        "direct_url": download.url,
                        "filename": suggested,
                        "is_pdf": suggested.lower().endswith(".pdf"),
                        "source": "browser_download_event",
                    })
                    break
                except Exception:
                    try:
                        node.click(timeout=3000)
                        page.wait_for_timeout(1200)
                    except Exception:
                        continue

        # network에서 직접 PDF가 관찰되면 보조 후보로 기록한다.
        network_pdf = [
            item["url"] for item in network
            if PDF_RE.search(item["url"])
        ]

        result = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "book_id": book_id,
            "answer_no": answer_no,
            "requested_url": target,
            "final_url": page.url,
            "page_title": page.title(),
            "body_excerpt": body_text[:1800],
            "book_file_ids": sorted(book_file_ids),
            "attachment_candidates": candidates[:100],
            "resolved_files": resolved,
            "network_pdf_candidates": list(dict.fromkeys(network_pdf)),
            "network_events": network[-80:],
        }

        context.close()
        browser.close()
        return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="브라우저 렌더링 후 EBS 교재 정답지 첨부파일의 직접 URL 후보를 수집합니다."
    )
    parser.add_argument("--book-id", required=True)
    parser.add_argument("--answer-no", default="5")
    parser.add_argument("--url", default="")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = collect(
        args.book_id.strip().upper(),
        args.answer_no.strip(),
        args.url.strip() or None,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")

    found = any(item.get("direct_url") for item in result["resolved_files"])
    return 0 if found else 2


if __name__ == "__main__":
    raise SystemExit(main())
