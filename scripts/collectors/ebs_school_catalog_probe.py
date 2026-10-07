from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.sync_api import sync_playwright

SITES = {
    "elementary": {
        "base": "https://primary.ebs.co.kr",
        "list_url": "https://primary.ebs.co.kr/book/main/list",
        "answer_url": "https://primary.ebs.co.kr/book/main/correctAnswerList",
        "errata_url": "https://primary.ebs.co.kr/book/main/errataList",
    },
    "middle": {
        "base": "https://mid.ebs.co.kr",
        "list_url": "https://mid.ebs.co.kr/book/main/list",
        "answer_url": "https://mid.ebs.co.kr/book/main/correctAnswerList",
        "errata_url": "https://mid.ebs.co.kr/book/main/errataList",
    },
}

TEXTBOOK_RE = re.compile(r"TB\d+")
GRADE_PATTERNS = [
    re.compile(r"(?:초등|초|만점왕\s*)?(\d)[-학년]"),
    re.compile(r"중학\s*뉴런.*?(\d)"),
    re.compile(r"중(\d)"),
]
SUBJECTS = ["국어", "수학", "영어", "사회", "역사", "과학", "한문"]


def infer_grade(title: str) -> int | None:
    for pattern in GRADE_PATTERNS:
        match = pattern.search(title)
        if match:
            try:
                value = int(match.group(1))
                if 1 <= value <= 6:
                    return value
            except ValueError:
                pass
    return None


def infer_subject(title: str) -> str | None:
    for subject in SUBJECTS:
        if subject in title:
            return subject
    return None


def extract_title_from_context(context: str, anchor_text: str) -> str | None:
    noise = (
        "교재 미리보기", "종이책 구입", "eBook 구입", "eBook 보기",
        "정답지/자료", "정오표", "MP3", "종이책 정가", "종이책 판매가",
        "출판사 :", "원", "% 할인", "교재 Q&A"
    )
    lines = [re.sub(r"\\s+", " ", line).strip() for line in context.splitlines()]
    candidates = []
    for line in lines:
        if not line or line == anchor_text:
            continue
        if any(token in line for token in noise):
            continue
        if len(line) < 3 or len(line) > 120:
            continue
        if re.fullmatch(r"[0-9,().%\\s-]+", line):
            continue
        candidates.append(line)
    return candidates[0] if candidates else None


def collect(site_key: str) -> dict:
    cfg = SITES[site_key]

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
        page.goto(cfg["list_url"], wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(1800)

        anchors = page.locator("a").evaluate_all(
            """els => els.map(a => {
              let node = a;
              let context = '';
              for (let i = 0; i < 6 && node; i += 1, node = node.parentElement) {
                const raw = (node.innerText || node.textContent || '').trim();
                if (raw && raw.length <= 1200) context = raw;
                if (node.tagName === 'LI' || node.tagName === 'TR') break;
              }
              return {
                text: (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim(),
                href: a.getAttribute('href'),
                onclick: a.getAttribute('onclick'),
                context: context.replace(/\r/g, '')
              };
            }).filter(x => x.text || x.href || x.onclick)"""
        )

        books = {}
        for item in anchors:
            title = (item.get("text") or "").strip()
            combined = " ".join([
                item.get("href") or "",
                item.get("onclick") or "",
            ])
            ids = TEXTBOOK_RE.findall(combined)
            for textbook_id in ids:
                if not title or len(title) > 160:
                    continue
                href = item.get("href") or ""
                official = (
                    urljoin(cfg["base"], href)
                    if href and not href.lower().startswith("javascript:")
                    else f'{cfg["base"]}/book/main/view?textbookId={textbook_id}'
                )
                context_title = extract_title_from_context(item.get("context") or "", title)
                resolved_title = context_title or (title if title not in {"교재 미리보기", "정답지/자료", "정오표", "MP3"} else None)
                candidate = {
                    "textbook_id": textbook_id,
                    "title": resolved_title,
                    "official_page": official,
                    "grade_guess": infer_grade(resolved_title or ""),
                    "subject_guess": infer_subject(resolved_title or ""),
                    "source": "anchor_context" if context_title else "anchor",
                }
                current = books.get(textbook_id)
                if current is None or (not current.get("title") and candidate.get("title")):
                    books[textbook_id] = candidate

        # 링크 텍스트와 textbookId가 서로 다른 DOM 노드에 있는 경우를 보완.
        html = page.content()
        for textbook_id in set(TEXTBOOK_RE.findall(html)):
            books.setdefault(textbook_id, {
                "textbook_id": textbook_id,
                "title": None,
                "official_page": f'{cfg["base"]}/book/main/view?textbookId={textbook_id}',
                "grade_guess": None,
                "subject_guess": None,
                "source": "html",
            })

        results = {
            "site": site_key,
            "list_url": cfg["list_url"],
            "answer_url": cfg["answer_url"],
            "errata_url": cfg["errata_url"],
            "book_count": len(books),
            "books": sorted(books.values(), key=lambda x: (x["title"] or "", x["textbook_id"])),
        }

        context.close()
        browser.close()
        return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EBS 초등/중학 교재 목록에서 textbookId와 교재 제목 후보를 수집합니다."
    )
    parser.add_argument(
        "--site",
        choices=["elementary", "middle", "all"],
        default="all",
    )
    parser.add_argument("--output", type=Path, default=Path("ebs-school-catalog-probe.json"))
    args = parser.parse_args()

    sites = ["elementary", "middle"] if args.site == "all" else [args.site]
    payload = {"results": [collect(site) for site in sites]}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
