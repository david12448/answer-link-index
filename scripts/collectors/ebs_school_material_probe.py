from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

FILE_RE = re.compile(r"\.(?:pdf|hwp|hwpx|zip|xlsx?|mp3)(?:$|[?#])", re.IGNORECASE)
GO_DETAIL_RE = re.compile(r"goDetail\s*\(\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
DOWNLOAD_HINT_RE = re.compile(r"download|file|down|첨부|정답|해설|자료", re.IGNORECASE)


def normalize_title(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\(\s*20\d{2}\s*\)", "", value)
    value = re.sub(r"20\d{2}", "", value)
    value = value.replace("ebs", "")
    value = re.sub(r"[\s()\[\]{}._\-/·]+", "", value)
    return value


def extract_go_detail_rows(page) -> list[dict]:
    return page.locator("a").evaluate_all(
        r"""els => els.map((a, i) => ({
          index: i,
          text: (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim(),
          href: a.getAttribute('href') || '',
          onclick: a.getAttribute('onclick') || ''
        })).filter(x => (x.href + ' ' + x.onclick).includes('goDetail('))"""
    )


def choose_matching_row(rows: list[dict], title: str) -> dict | None:
    target = normalize_title(title)
    target_level = re.findall(r"\d+[-학년]\d*|\d+-\d+", title)
    best = None
    best_score = -1

    for row in rows:
        text = row.get("text") or ""
        norm = normalize_title(text)
        if not norm:
            continue

        # 3-1을 찾는데 6-2를 고르는 식의 오매칭을 막는다.
        row_level = re.findall(r"\d+[-학년]\d*|\d+-\d+", text)
        if target_level and row_level and not any(token in row_level for token in target_level):
            continue

        if target == norm:
            score = 100
        elif target in norm:
            score = 90
        elif norm in target and len(norm) >= max(6, int(len(target) * 0.75)):
            score = 75
        else:
            tokens = [token for token in re.split(r"\s+", title) if len(token) >= 2]
            matched = sum(1 for token in tokens if token in text)
            score = matched * 5

        if score > best_score:
            best = row
            best_score = score

    return best if best_score >= 15 else None


def try_search_board(page, title: str) -> dict:
    info = {"attempted": False, "input": None, "submitted": False}
    candidates = page.locator('input[type="text"], input[type="search"]')
    ranked = []

    for i in range(candidates.count()):
        node = candidates.nth(i)
        try:
            attrs = node.evaluate(
                """el => ({
                  name: el.getAttribute('name'),
                  id: el.id || null,
                  placeholder: el.getAttribute('placeholder'),
                  value: el.value || '',
                  form_text: (el.closest('form')?.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 500)
                })"""
            )
        except Exception:
            continue

        name = str(attrs.get("name") or "").lower()
        node_id = str(attrs.get("id") or "").lower()
        placeholder = str(attrs.get("placeholder") or "")
        form_text = str(attrs.get("form_text") or "")

        score = 0
        if "교재" in placeholder:
            score += 100
        if "교재" in form_text and "검색" in form_text:
            score += 60
        if "book" in name or "book" in node_id or "textbook" in name or "textbook" in node_id:
            score += 50
        if name == "q" or node_id in {"search", "search1", "search2"}:
            score -= 80

        if score > 0:
            ranked.append((score, i, attrs))

    for _, index, attrs in sorted(ranked, reverse=True):
        node = candidates.nth(index)
        try:
            node.fill(title, timeout=3000)
            info["attempted"] = True
            info["input"] = attrs
            node.press("Enter", timeout=3000)
            info["submitted"] = True
            page.wait_for_timeout(2500)
            return info
        except Exception:
            continue

    return info


def collect_attachments(page) -> list[dict]:
    items = page.locator("a, button, input").evaluate_all(
        r"""els => els.map(el => ({
          tag: el.tagName,
          text: (el.innerText || el.value || el.textContent || '').replace(/\s+/g, ' ').trim(),
          href: el.getAttribute('href'),
          onclick: el.getAttribute('onclick'),
          id: el.id || null,
          name: el.getAttribute('name'),
          value: el.getAttribute('value'),
          parent_text: (el.parentElement?.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 500)
        })).filter(x => {
          const s = JSON.stringify(x).toLowerCase();
          return s.includes('/file/download') || s.includes('download?') ||
                 s.includes('.pdf') || s.includes('.hwp') || s.includes('.hwpx') ||
                 s.includes('.zip') || s.includes('첨부');
        })"""
    )
    out = []
    for item in items:
        href = item.get("href") or ""
        onclick = item.get("onclick") or ""
        urls = []
        if href and not href.lower().startswith("javascript:"):
            urls.append(urljoin(page.url, href))
        for value in re.findall(r"https?://[^'\"\s)]+|/[^'\"\s)]+(?:download|file)[^'\"\s)]*", onclick, re.IGNORECASE):
            urls.append(urljoin(page.url, value))
        out.append({**item, "urls": list(dict.fromkeys(urls))})
    return out


def collect_one(page, book: dict) -> dict:
    title = book["title"]
    official = book["official_page"]
    textbook_id = book["publisher_book_id"]
    site = book.get("publisher_site")
    events = []

    def on_response(response):
        url = response.url
        content_type = response.headers.get("content-type") or ""
        if (
            textbook_id in url
            or "/file/download" in url
            or "answer" in url.lower()
            or "correct" in url.lower()
            or "octet-stream" in content_type.lower()
            or "pdf" in content_type.lower()
        ):
            events.append({
                "url": url,
                "status": response.status,
                "content_type": content_type,
                "content_disposition": response.headers.get("content-disposition"),
            })

    page.on("response", on_response)
    page.goto(official, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    page.wait_for_timeout(1000)

    # 상세 페이지에 교재별 자료 hash가 있으면 그것을 최우선으로 사용한다.
    hash_links = page.locator("a").evaluate_all(
        r"""els => els.map(a => ({
          text: (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim(),
          href: a.getAttribute('href') || ''
        })).filter(x => x.href.startsWith('#') && /answer|정답|자료/i.test(x.href + ' ' + x.text))"""
    )
    per_book_hash = next((item for item in reversed(hash_links) if textbook_id in item["href"]), None)

    if per_book_hash:
        page.evaluate("(h) => { location.hash = h; }", per_book_hash["href"])
        page.wait_for_timeout(2200)
    else:
        base = "https://primary.ebs.co.kr" if site == "ebs_primary" else "https://mid.ebs.co.kr"
        answer_path = "/book/answer/index" if site == "ebs_primary" else "/book/main/correctAnswerList"
        page.goto(base + answer_path, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(900)

    rows = extract_go_detail_rows(page)
    matched = choose_matching_row(rows, title)
    search_info = {"attempted": False, "input": None, "submitted": False}

    if matched is None:
        search_info = try_search_board(page, title)
        rows = extract_go_detail_rows(page)
        matched = choose_matching_row(rows, title)

    detail_clicked = False
    post_id = None
    if matched:
        source = (matched.get("href") or "") + " " + (matched.get("onclick") or "")
        match = GO_DETAIL_RE.search(source)
        if match:
            post_id = match.group(1)
        try:
            target_text = matched.get("text") or ""
            locator = page.locator("a").filter(has_text=target_text).first
            locator.click(timeout=5000)
            detail_clicked = True
            page.wait_for_timeout(2200)
        except Exception:
            if post_id:
                try:
                    page.evaluate("(id) => { if (typeof goDetail === 'function') goDetail(id, '-1'); }", post_id)
                    detail_clicked = True
                    page.wait_for_timeout(2200)
                except Exception:
                    pass

    attachments = collect_attachments(page)
    body_text = page.locator("body").inner_text(timeout=10000)

    # viewer installer처럼 모든 교재에 공통으로 보이는 파일은 자동 direct 후보에서 제외한다.
    direct_candidates = []
    for item in attachments:
        parent = item.get("parent_text") or ""
        text = item.get("text") or ""
        for url in item.get("urls") or []:
            if "view=Y" in url and not any(token in parent + text for token in ["정답", "해설", title]):
                continue
            direct_candidates.append({
                "text": text,
                "context": parent,
                "url": url,
            })

    page.remove_listener("response", on_response)
    return {
        "book_id": book["book_id"],
        "publisher_site": site,
        "publisher_book_id": textbook_id,
        "title": title,
        "official_page": official,
        "resource_page": (
            official + per_book_hash["href"] if per_book_hash else page.url
        ),
        "per_book_hash": per_book_hash,
        "search": search_info,
        "row_count": len(rows),
        "matched_row": matched,
        "post_id": post_id,
        "detail_clicked": detail_clicked,
        "final_url": page.url,
        "attachments": attachments[:80],
        "direct_candidates": direct_candidates[:30],
        "network_events": events[-100:],
        "body_excerpt": body_text[-4500:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EBS 초등/중학 대표 교재의 자료 게시물과 첨부 다운로드 구조를 점검합니다."
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
                results.append(collect_one(page, book))
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
