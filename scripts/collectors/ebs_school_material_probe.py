from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

FILE_RE = re.compile(r"\.(?:pdf|hwp|hwpx|zip|xlsx?|mp3)(?:$|[?#])", re.IGNORECASE)
DOWNLOAD_HINT_RE = re.compile(r"download|file|down|첨부|정답|해설|자료", re.IGNORECASE)


def collect_one(page, context, book: dict) -> dict:
    title = book["title"]
    official = book["official_page"]
    textbook_id = book["publisher_book_id"]
    events = []

    def on_response(response):
        u = response.url
        ct = response.headers.get("content-type") or ""
        if (
            textbook_id in u
            or DOWNLOAD_HINT_RE.search(u)
            or "json" in ct.lower()
            or "octet-stream" in ct.lower()
            or "pdf" in ct.lower()
        ):
            events.append({
                "url": u,
                "status": response.status,
                "content_type": ct,
            })

    page.on("response", on_response)
    page.goto(official, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    page.wait_for_timeout(1200)

    answer_links = page.locator("a").evaluate_all(
        r"""els => els.map((a, i) => ({
          index: i,
          text: (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim(),
          href: a.getAttribute('href'),
          onclick: a.getAttribute('onclick')
        })).filter(x => /정답지|정답.*자료|자료실/.test(x.text))"""
    )

    clicked = None
    # 교재 상세 내부의 정답지/자료 링크를 우선 선택한다.
    for item in reversed(answer_links):
        href = item.get("href") or ""
        onclick = item.get("onclick") or ""
        combined = " ".join([href, onclick])
        if textbook_id in combined or href.startswith("#") or "answer" in combined.lower():
            clicked = item
            break
    if clicked is None and answer_links:
        clicked = answer_links[-1]

    if clicked:
        href = clicked.get("href") or ""
        try:
            if href.startswith("#"):
                page.evaluate("(h) => { location.hash = h; }", href)
            else:
                locator = page.locator("a").filter(has_text=re.compile(r"정답지|정답.*자료|자료실")).last
                locator.click(timeout=5000)
        except Exception:
            pass
        page.wait_for_timeout(2200)

    candidates = page.locator("a, button, input").evaluate_all(
        r"""els => els.map(el => ({
          tag: el.tagName,
          text: (el.innerText || el.value || el.textContent || '').replace(/\s+/g, ' ').trim(),
          href: el.getAttribute('href'),
          onclick: el.getAttribute('onclick'),
          id: el.id || null,
          name: el.getAttribute('name'),
          value: el.getAttribute('value'),
          data: Object.fromEntries([...el.attributes]
            .filter(a => a.name.startsWith('data-'))
            .map(a => [a.name, a.value]))
        })).filter(x => {
          const s = JSON.stringify(x).toLowerCase();
          return s.includes('.pdf') || s.includes('.hwp') || s.includes('.zip') ||
                 s.includes('download') || s.includes('filedown') ||
                 s.includes('첨부') || s.includes('정답') || s.includes('해설');
        })"""
    )

    direct_candidates = []
    for item in candidates:
        href = item.get("href") or ""
        if href and not href.lower().startswith("javascript:") and (
            FILE_RE.search(href) or DOWNLOAD_HINT_RE.search(href)
        ):
            direct_candidates.append({
                "source": "href",
                "text": item.get("text"),
                "url": urljoin(page.url, href),
            })

    # 다운로드로 보이는 후보를 클릭해 실제 browser download URL도 관찰한다.
    download_events = []
    clickable = page.locator("a, button").filter(
        has_text=re.compile(r"다운|정답|해설|첨부|파일", re.IGNORECASE)
    )
    for i in range(min(clickable.count(), 12)):
        node = clickable.nth(i)
        try:
            text = (node.inner_text(timeout=1000) or "").strip()
        except Exception:
            text = ""
        if not text:
            continue
        try:
            with page.expect_download(timeout=2500) as info:
                node.click(timeout=3000)
            download = info.value
            download_events.append({
                "text": text,
                "url": download.url,
                "filename": download.suggested_filename,
            })
            if download.url:
                break
        except Exception:
            continue

    body_text = page.locator("body").inner_text(timeout=10000)
    page.remove_listener("response", on_response)

    return {
        "book_id": book["book_id"],
        "publisher_site": book.get("publisher_site"),
        "publisher_book_id": textbook_id,
        "title": title,
        "official_page": official,
        "final_url": page.url,
        "answer_links": answer_links,
        "candidate_count": len(candidates),
        "candidates": candidates[:120],
        "direct_candidates": direct_candidates[:50],
        "download_events": download_events[:20],
        "network_events": events[-120:],
        "body_excerpt": body_text[-3500:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EBS 초등/중학 대표 교재의 정답지/자료 direct 링크 구조를 브라우저로 점검합니다."
    )
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.json"))
    parser.add_argument("--output", type=Path, default=Path("ebs-school-material-probe.json"))
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    books = [
        b for b in catalog.get("books", [])
        if b.get("publisher") == "EBS"
        and b.get("publisher_site") in {"ebs_primary", "ebs_middle"}
        and b.get("publisher_book_id")
    ]

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
                results.append(collect_one(page, context, book))
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
