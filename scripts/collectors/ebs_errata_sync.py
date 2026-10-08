from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

BASE = "https://www.ebsi.co.kr"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/154.0.0.0 Safari/537.36"
)


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


def probe_download(book_id: str) -> dict:
    url = download_url(book_id)
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/octet-stream,application/pdf,*/*",
            "Referer": detail_url(book_id),
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=30) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type") or ""
            disposition = response.headers.get("Content-Disposition") or ""
            looks_like_file = (
                getattr(response, "status", 200) == 200
                and len(body) > 500
                and (
                    "attachment" in disposition.lower()
                    or "octet-stream" in content_type.lower()
                    or body.startswith(b"%PDF")
                    or body.startswith(b"PK\x03\x04")
                )
            )
            return {
                "url": url,
                "status": getattr(response, "status", 200),
                "content_type": content_type,
                "content_disposition": disposition,
                "bytes": len(body),
                "looks_like_file": looks_like_file,
                "definite_no_file": not looks_like_file,
                "error": None,
            }
    except HTTPError as exc:
        return {
            "url": url,
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "content_disposition": exc.headers.get("Content-Disposition") if exc.headers else None,
            "bytes": 0,
            "looks_like_file": False,
            "definite_no_file": exc.code in {400, 404, 500},
            "error": f"HTTPError: {exc.code}",
        }
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "url": url,
            "status": None,
            "content_type": None,
            "content_disposition": None,
            "bytes": 0,
            "looks_like_file": False,
            "definite_no_file": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EBS catalog의 정오표를 점검하고 새 정오표가 확인되면 direct_url을 반영합니다."
    )
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.json"))
    parser.add_argument("--report", type=Path, default=Path("ebs-errata-sync-report.json"))
    args = parser.parse_args()

    data = json.loads(args.catalog.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    changes = []
    checks = []

    for book in data.get("books", []):
        if book.get("publisher") != "EBS":
            continue
        book_id = (book.get("publisher_book_id") or "").strip()
        if not book_id:
            continue
        if book.get("publisher_site") not in {None, "ebsi"} or not book_id.startswith("LB"):
            continue
        material = next(
            (item for item in book.get("materials", []) if item.get("type") == "errata"),
            None,
        )
        if material is None:
            continue

        probe = probe_download(book_id)
        detail = detail_url(book_id)
        search = search_url(book.get("title") or "")
        before = {
            "direct_url": material.get("direct_url"),
            "resource_page": material.get("resource_page"),
            "status": material.get("status"),
            "availability": material.get("availability") or "unknown",
        }

        if probe["looks_like_file"]:
            desired = {
                "direct_url": probe["url"],
                "resource_page": detail,
                "status": "ok",
                "availability": "available",
            }
        elif material.get("direct_url"):
            # 네트워크 오류나 EBS 일시 오류 때문에 기존 확인 링크를 자동 삭제하지 않는다.
            desired = before
        elif probe.get("definite_no_file"):
            desired = {
                "direct_url": None,
                "resource_page": search,
                "status": "needs_review",
                "availability": "unavailable",
            }
        else:
            # 일시적인 네트워크 오류에서는 있음/없음 상태를 뒤집지 않는다.
            desired = before

        changed = any(before.get(key) != desired.get(key) for key in desired)
        if changed:
            material.update(desired)
            material["last_checked"] = today
            changes.append({
                "book_id": book.get("book_id"),
                "publisher_book_id": book_id,
                "title": book.get("title"),
                "before": before,
                "after": desired,
                "probe": probe,
            })

        checks.append({
            "book_id": book.get("book_id"),
            "publisher_book_id": book_id,
            "title": book.get("title"),
            "has_direct_errata": bool(desired.get("direct_url")),
            "fallback_url": desired.get("resource_page"),
            "changed": changed,
            "probe": probe,
        })

    if changes:
        data.setdefault("meta", {})["generated_at"] = today
        args.catalog.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    report = {
        "checked_at": today,
        "checked_count": len(checks),
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
