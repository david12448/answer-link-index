from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

BASE = "https://www.ebsi.co.kr"
USER_AGENT = "answer-link-index/1.0 (+public EBS collector probe)"

ENDPOINTS = {
    "answer": "/ebs/pot/potg/bkAnsList.ebs",
    "errata": "/ebs/pot/potg/bkErrChrgMngList.ebs",
    "mp3": "/ebs/pot/potg/retrieveMp3DownList.ebs",
    "additional": "/ebs/pot/potg/txbkAdtlDatList.ebs",
}

DETAIL_ENDPOINTS = {
    "book": "/ebs/pot/potg/retrieveCourseDetailNw.ebs",
    "answer": "/ebs/pot/potg/detailBkAnsInfo.ebs",
    "errata": "/ebs/pot/potg/DetailBkErrInfo.ebs",
}

BOOK_ID_RE = re.compile(r"LB\d{8,14}", re.IGNORECASE)
INPUT_NAME_RE = re.compile(r"<input\b[^>]*\bname=[\"']([^\"']+)[\"']", re.IGNORECASE)
SELECT_NAME_RE = re.compile(r"<select\b[^>]*\bname=[\"']([^\"']+)[\"']", re.IGNORECASE)
FORM_ACTION_RE = re.compile(r"<form\b[^>]*\baction=[\"']([^\"']*)[\"']", re.IGNORECASE)
HREF_RE = re.compile(r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"']", re.IGNORECASE)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def decode_body(raw: bytes, content_type: str | None) -> tuple[str, str]:
    candidates = []
    if content_type:
        match = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
        if match:
            candidates.append(match.group(1))
    candidates.extend(["utf-8", "euc-kr", "cp949"])

    for charset in candidates:
        try:
            return raw.decode(charset), charset
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def summarize_html(html: str, final_url: str) -> dict:
    book_ids = sorted(set(value.upper() for value in BOOK_ID_RE.findall(html)))
    hrefs = [unescape(value) for value in HREF_RE.findall(html)]
    book_urls = []
    for href in hrefs:
        if "bookId=" in href or BOOK_ID_RE.search(href):
            book_urls.append(urljoin(final_url, href))

    title_match = TITLE_RE.search(html)
    title = re.sub(r"\s+", " ", unescape(title_match.group(1))).strip() if title_match else None

    return {
        "title": title,
        "book_ids": book_ids,
        "book_urls": sorted(set(book_urls))[:100],
        "form_actions": sorted(set(unescape(x) for x in FORM_ACTION_RE.findall(html))),
        "input_names": sorted(set(INPUT_NAME_RE.findall(html))),
        "select_names": sorted(set(SELECT_NAME_RE.findall(html))),
        "markers": {
            "contains_book_id": bool(book_ids),
            "contains_detail_answer": "detailBkAnsInfo.ebs" in html,
            "contains_detail_errata": "DetailBkErrInfo.ebs" in html,
            "contains_download_word": "download" in html.lower() or "다운로드" in html,
        },
    }


def fetch(url: str) -> dict:
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=30) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type")
            html, charset = decode_body(raw, content_type)
            result = {
                "requested_url": url,
                "final_url": response.geturl(),
                "http_status": getattr(response, "status", 200),
                "content_type": content_type,
                "charset": charset,
                "bytes": len(raw),
                "ok": True,
                "error": None,
            }
            result.update(summarize_html(html, response.geturl()))
            return result
    except Exception as exc:
        return {
            "requested_url": url,
            "final_url": None,
            "http_status": None,
            "content_type": None,
            "charset": None,
            "bytes": 0,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "title": None,
            "book_ids": [],
            "book_urls": [],
            "form_actions": [],
            "input_names": [],
            "select_names": [],
            "markers": {},
        }


def build_url(path: str, params: dict[str, str] | None = None) -> str:
    url = urljoin(BASE, path)
    if params:
        return f"{url}?{urlencode(params)}"
    return url


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EBS 공개 자료실의 폼/링크 구조를 읽기 전용으로 점검합니다."
    )
    parser.add_argument(
        "--kind",
        choices=["all", *ENDPOINTS.keys()],
        default="all",
        help="점검할 자료실 종류",
    )
    parser.add_argument(
        "--book-id",
        default="",
        help="선택: LB... 교재 ID를 주면 공식 교재/정답/정오표 상세 주소도 점검",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="선택: JSON 결과 저장 경로. 생략하면 stdout만 사용",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="하나라도 네트워크 점검 실패 시 종료 코드 1",
    )
    args = parser.parse_args()

    kinds = list(ENDPOINTS) if args.kind == "all" else [args.kind]
    targets = [
        {
            "name": kind,
            "role": "list",
            "url": build_url(ENDPOINTS[kind], {"devonTargetRow": "1"}),
        }
        for kind in kinds
    ]

    book_id = args.book_id.strip().upper()
    if book_id:
        if not BOOK_ID_RE.fullmatch(book_id):
            parser.error("--book-id는 LB로 시작하는 EBS 교재 ID 형식이어야 합니다.")
        for name, path in DETAIL_ENDPOINTS.items():
            targets.append(
                {
                    "name": name,
                    "role": "detail",
                    "url": build_url(path, {"bookId": book_id}),
                }
            )

    results = []
    for target in targets:
        item = dict(target)
        item["probe"] = fetch(target["url"])
        results.append(item)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "read-only discovery of EBS public material page structure",
        "book_id": book_id or None,
        "results": results,
    }

    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")

    failed = [item for item in results if not item["probe"]["ok"]]
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
