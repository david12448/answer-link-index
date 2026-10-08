from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://www.ebsi.co.kr"
PAGES = {
    "mp3": f"{BASE}/ebs/pot/potg/retrieveMp3DownList.ebs",
    "additional": f"{BASE}/ebs/pot/potg/txbkAdtlDatList.ebs",
}
DIRECT_HINT_RE = re.compile(
    r"(?:\.mp3|\.zip|\.pdf|\.hwp|\.hwpx|download|fileDown|FlDown|mp3)",
    re.IGNORECASE,
)


def normalize(value: str) -> str:
    return re.sub(r"[\s._\-·/()\[\]]+", "", (value or "").lower())


def search_page(page, kind: str, title: str) -> dict:
    page.goto(PAGES[kind], wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    page.wait_for_timeout(700)

    search_info = {"field": None, "submitted": False}
    names = ["bookNm", "schWd"] if kind == "mp3" else ["schWd", "bookNm"]

    for name in names:
        locator = page.locator(f'input[name="{name}"]')
        if not locator.count():
            continue
        try:
            locator.first.fill(title, timeout=3000)
            search_info["field"] = name
            locator.first.press("Enter", timeout=3000)
            search_info["submitted"] = True
            page.wait_for_timeout(1800)
            break
        except Exception:
            continue

    # 엔터 검색이 막혀 있을 경우 가까운 '검색' 버튼을 한 번 시도한다.
    if search_info["field"] and not search_info["submitted"]:
        try:
            page.get_by_text("검색", exact=True).last.click(timeout=3000)
            search_info["submitted"] = True
            page.wait_for_timeout(1800)
        except Exception:
            pass

    return search_info


def collect_nodes(page) -> list[dict]:
    return page.locator("a, button, input").evaluate_all(
        r"""els => els.map(el => ({
          tag: el.tagName,
          text: (el.innerText || el.value || el.textContent || '').replace(/\s+/g, ' ').trim(),
          href: el.getAttribute('href'),
          onclick: el.getAttribute('onclick'),
          name: el.getAttribute('name'),
          value: el.getAttribute('value'),
          parent_text: (el.closest('tr,li,div')?.innerText || '')
            .replace(/\s+/g, ' ').trim().slice(0, 900)
        })).filter(x => {
          const s = JSON.stringify(x).toLowerCase();
          return s.includes('mp3') || s.includes('다운') || s.includes('첨부') ||
                 s.includes('file') || s.includes('.zip') || s.includes('.pdf') ||
                 s.includes('fldown') || s.includes('download');
        })"""
    )


def inspect_one(page, book: dict, kind: str) -> dict:
    title = book["title"]
    book_id = book["publisher_book_id"]
    events = []
    ajax_payloads = []

    def on_response(response):
        url = response.url
        content_type = response.headers.get("content-type") or ""
        if (
            "mp3" in url.lower()
            or "down" in url.lower()
            or "adtl" in url.lower()
            or book_id in url
            or "audio" in content_type.lower()
            or "octet-stream" in content_type.lower()
        ):
            events.append({
                "url": url,
                "status": response.status,
                "content_type": content_type,
                "content_disposition": response.headers.get("content-disposition"),
            })

        if "retrieveMp3Down.ajax" in url:
            try:
                payload = response.text()
                mp3_urls = re.findall(
                    r'https?://[^"\'<>\s]+\.mp3(?:\?[^"\'<>\s]*)?',
                    payload,
                    flags=re.IGNORECASE,
                )
                ajax_payloads.append({
                    "url": url,
                    "method": response.request.method,
                    "post_data": response.request.post_data,
                    "html_length": len(payload),
                    "mp3_occurrences": len(re.findall(r"\.mp3", payload, re.IGNORECASE)),
                    "mp3_urls": list(dict.fromkeys(mp3_urls))[:40],
                    "has_mp3url_attr": "mp3url" in payload.lower(),
                    "excerpt": re.sub(r"\s+", " ", payload[:5000]),
                })
            except Exception as exc:
                ajax_payloads.append({
                    "url": url,
                    "error": f"{type(exc).__name__}: {exc}",
                })

    page.on("response", on_response)
    search = search_page(page, kind, title)
    nodes = collect_nodes(page)

    title_norm = normalize(title)
    matching_rows = []
    for node in nodes:
        context = " ".join([
            node.get("text") or "",
            node.get("parent_text") or "",
            node.get("href") or "",
            node.get("onclick") or "",
        ])
        if title_norm and title_norm in normalize(context):
            matching_rows.append(node)

    detail_clicked = False
    detail_call = None
    if kind == "mp3":
        exact = next(
            (
                node for node in matching_rows
                if book_id in (node.get("onclick") or "")
                and "mp3Detail(" in (node.get("onclick") or "")
            ),
            None,
        )
        if exact:
            detail_call = exact.get("onclick")
            try:
                selector = f'a[onclick*="{book_id}"]'
                candidates = page.locator(selector)
                target = candidates.filter(has_text=title).first if candidates.count() else None
                if target and target.count():
                    target.click(timeout=5000)
                elif candidates.count():
                    candidates.first.click(timeout=5000)
                else:
                    page.evaluate(
                        "(args) => mp3Detail(args.bookId, args.iemDs, args.rowNum)",
                        {
                            "bookId": book_id,
                            "iemDs": re.search(r"mp3Detail\('[^']+','([^']+)','([^']+)'", detail_call).group(1),
                            "rowNum": re.search(r"mp3Detail\('[^']+','([^']+)','([^']+)'", detail_call).group(2),
                        },
                    )
                detail_clicked = True
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                try:
                    page.wait_for_function(
                        "() => document.querySelector('#ajaxArea') && "
                        "document.querySelector('#ajaxArea').innerHTML.trim().length > 0",
                        timeout=10000,
                    )
                except Exception:
                    pass
                page.wait_for_timeout(1800)
                nodes = collect_nodes(page)
            except Exception:
                detail_clicked = False

    body = page.locator("body").inner_text(timeout=10000)
    html = page.content()

    mp3_files = []
    if kind == "mp3":
        mp3_files = page.locator("input[mp3url]").evaluate_all(
            r"""els => els.map(el => ({
              url: el.getAttribute('mp3url'),
              value: el.getAttribute('value'),
              prtcd: el.getAttribute('prtcd'),
              info: el.getAttribute('mp3info'),
              name: el.getAttribute('name'),
              parent_text: (el.closest('li,dd,div')?.innerText || '')
                .replace(/\s+/g, ' ').trim().slice(0, 300)
            })).filter(x => x.url)"""
        )

    snippets = []
    for match in DIRECT_HINT_RE.finditer(html):
        start = max(0, match.start() - 300)
        end = min(len(html), match.end() + 700)
        snippet = re.sub(r"\s+", " ", html[start:end])
        if snippet not in snippets:
            snippets.append(snippet)
        if len(snippets) >= 40:
            break

    page.remove_listener("response", on_response)
    return {
        "book_id": book["book_id"],
        "publisher_book_id": book_id,
        "title": title,
        "kind": kind,
        "page_url": PAGES[kind],
        "final_url": page.url,
        "search": search,
        "title_visible": title in body,
        "detail_clicked": detail_clicked,
        "detail_call": detail_call,
        "body_excerpt": body[-4500:],
        "matching_rows": matching_rows[:80],
        "candidate_nodes": nodes[:150],
        "mp3_file_count": len(mp3_files),
        "mp3_files": mp3_files,
        "ajax_mp3_file_count": len({
            url
            for payload in ajax_payloads
            for url in payload.get("mp3_urls", [])
        }),
        "ajax_payloads": ajax_payloads[-10:],
        "whole_file_candidates": [
            item for item in mp3_files
            if "통파일" in ((item.get("info") or "") + " " + (item.get("parent_text") or ""))
        ],
        "network_events": events[-120:],
        "html_snippets": snippets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EBSi 영어 MP3/부가자료의 검색 및 다운로드 구조를 브라우저로 조사합니다."
    )
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.json"))
    parser.add_argument("--output", type=Path, default=Path("ebsi-optional-material-probe.json"))
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    targets = []
    for book in catalog.get("books", []):
        if book.get("publisher") != "EBS" or book.get("publisher_site") != "ebsi":
            continue
        for material in book.get("materials", []):
            if material.get("type") in {"mp3", "additional"}:
                targets.append((book, material["type"]))

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
        for book, kind in targets:
            try:
                results.append(inspect_one(page, book, kind))
            except Exception as exc:
                results.append({
                    "book_id": book.get("book_id"),
                    "publisher_book_id": book.get("publisher_book_id"),
                    "title": book.get("title"),
                    "kind": kind,
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
