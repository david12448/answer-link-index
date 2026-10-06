from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import quote, urlencode, urljoin
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
ANCHOR_RE = re.compile(r"<a\\b([^>]*)>(.*?)</a>", re.IGNORECASE | re.DOTALL)
ATTR_RE = re.compile(r"([\\w:-]+)\\s*=\\s*[\\\"']([^\\\"']*)[\\\"']", re.IGNORECASE)
FILE_TOKEN_RE = re.compile(r"[^\\s\\\"\'<>]+\\.(?:pdf|hwp|hwpx|zip|mp3|wav)(?:\\?[^\\s\\\"\'<>]*)?", re.IGNORECASE)
QUOTED_URL_RE = re.compile(r"[\\\"']((?:https?://|/)[^\\\"']+)[\\\"']", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
BOOK_FL_CALL_RE = re.compile(r"fncDownFile\\s*\\(\\s*[\\\"']?([^\\\"')\\s]+)[\\\"']?\\s*\\)", re.IGNORECASE)
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


def clean_text(value: str) -> str:
    value = TAG_RE.sub(" ", value)
    return re.sub(r"\\s+", " ", unescape(value)).strip()


def extract_attachment_candidates(html: str, final_url: str) -> list[dict]:
    candidates = []
    seen = set()

    def add(kind: str, raw_value: str, text: str = "", context: str = ""):
        value = unescape(raw_value).strip()
        if not value:
            return
        resolved = urljoin(final_url, value) if value.startswith(("/", "./", "../")) else value
        key = (kind, resolved, text)
        if key in seen:
            return
        seen.add(key)
        candidates.append({
            "kind": kind,
            "value": resolved,
            "text": clean_text(text)[:240],
            "context": clean_text(context)[:500],
        })

    for attrs_raw, inner in ANCHOR_RE.findall(html):
        attrs = {name.lower(): unescape(value) for name, value in ATTR_RE.findall(attrs_raw)}
        href = attrs.get("href", "")
        onclick = attrs.get("onclick", "")
        text = clean_text(inner)
        combined = " ".join([href, onclick, text]).lower()
        if (
            FILE_TOKEN_RE.search(combined)
            or "download" in combined
            or "filedown" in combined
            or "첨부파일" in combined
            or "정답과해설" in combined
        ):
            if href and href not in ("#", "javascript:;", "javascript:void(0);"):
                add("href", href, text, attrs_raw)
            if onclick:
                add("onclick", onclick, text, attrs_raw)
                for quoted in QUOTED_URL_RE.findall(onclick):
                    add("onclick_url", quoted, text, onclick)

    for token in FILE_TOKEN_RE.findall(html):
        add("file_token", token)

    for match in re.finditer(r".{0,180}(?:download|fileDown|첨부파일|정답과해설|\\.pdf).{0,260}", html, re.IGNORECASE | re.DOTALL):
        snippet = clean_text(match.group(0))
        if snippet:
            add("html_snippet", snippet)

    return candidates[:100]


def summarize_html(html: str, final_url: str) -> dict:
    book_ids = sorted(set(value.upper() for value in BOOK_ID_RE.findall(html)))
    book_file_ids = sorted({
        value for value in BOOK_FL_CALL_RE.findall(html)
        if value and value.lower() != "bookflid"
    })
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
        "book_file_ids": book_file_ids[:50],
        "book_urls": sorted(set(book_urls))[:100],
        "form_actions": sorted(set(unescape(x) for x in FORM_ACTION_RE.findall(html))),
        "input_names": sorted(set(INPUT_NAME_RE.findall(html))),
        "select_names": sorted(set(SELECT_NAME_RE.findall(html))),
        "attachment_candidates": extract_attachment_candidates(html, final_url),
        "markers": {
            "contains_book_id": bool(book_ids),
            "contains_detail_answer": "detailBkAnsInfo.ebs" in html,
            "contains_detail_errata": "DetailBkErrInfo.ebs" in html,
            "contains_download_word": "download" in html.lower() or "다운로드" in html,
        },
    }


def resolve_book_file(book_fl_id: str, referer: str) -> dict:
    ajax_url = build_url(
        "/ebs/lms/lmsk/bkAnsMngFLdown.ajax",
        {"bookFlId": book_fl_id},
    )
    req = Request(
        ajax_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/javascript,*/*;q=0.1",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": referer,
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=30) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type")
            text, charset = decode_body(raw, content_type)
            payload = json.loads(text)
            fl_nm = payload.get("flNm")
            if fl_nm and fl_nm.startswith("//"):
                direct_url = "https:" + fl_nm
            elif fl_nm:
                direct_url = urljoin(BASE, fl_nm)
            else:
                direct_url = None
            return {
                "book_fl_id": book_fl_id,
                "ajax_url": ajax_url,
                "http_status": getattr(response, "status", 200),
                "content_type": content_type,
                "charset": charset,
                "success": str(payload.get("success")) == "1",
                "direct_url": direct_url,
                "server_filename": payload.get("svNm"),
                "raw_file_url": fl_nm,
                "error": None,
            }
    except Exception as exc:
        return {
            "book_fl_id": book_fl_id,
            "ajax_url": ajax_url,
            "http_status": None,
            "content_type": None,
            "charset": None,
            "success": False,
            "direct_url": None,
            "server_filename": None,
            "raw_file_url": None,
            "error": f"{type(exc).__name__}: {exc}",
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
            if "detailBkAnsInfo.ebs" in response.geturl():
                result["resolved_files"] = [
                    resolve_book_file(book_fl_id, response.geturl())
                    for book_fl_id in result.get("book_file_ids", [])[:20]
                ]
            else:
                result["resolved_files"] = []
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
            "book_file_ids": [],
            "book_urls": [],
            "form_actions": [],
            "input_names": [],
            "select_names": [],
            "attachment_candidates": [],
            "resolved_files": [],
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
        "--answer-no",
        default="",
        help="선택: 정답지 상세 게시물 no 값. bookId와 함께 주면 정확한 첨부파일 상세 페이지를 점검",
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
            params = {"bookId": book_id}
            if name == "answer" and args.answer_no.strip():
                params.update({
                    "year_n": "",
                    "no": args.answer_no.strip(),
                    "devonTargetRow": "1",
                    "catGbn": "",
                    "connectionBookYn": "",
                    "bookNm": "",
                    "currentPage": "",
                })
            targets.append(
                {
                    "name": name,
                    "role": "detail",
                    "url": build_url(path, params),
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
        "answer_no": args.answer_no.strip() or None,
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
