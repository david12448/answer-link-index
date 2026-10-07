from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

from ebs_school_material_probe import collect_one, normalize_title

DOWNLOAD_PATH = "/board/common/download"
PDF_RE = re.compile(r"\.pdf$", re.IGNORECASE)


def answer_material(book: dict) -> dict | None:
    return next(
        (item for item in book.get("materials", []) if item.get("type") == "answer"),
        None,
    )


def rotating_batch(items: list[dict], limit: int) -> list[dict]:
    if not limit or len(items) <= limit:
        return items

    # 주 2회 실행을 기준으로 매 실행마다 다음 묶음으로 이동한다.
    today = date.today()
    monday_epoch = date(2020, 1, 6)
    week_index = (today.toordinal() - monday_epoch.toordinal()) // 7
    slot_index = week_index * 2 + (1 if today.weekday() >= 3 else 0)
    start = (slot_index * limit) % len(items)

    return [
        items[(start + index) % len(items)]
        for index in range(min(limit, len(items)))
    ]


def safe_candidate(book: dict, result: dict) -> dict | None:
    matched = result.get("matched_row") or {}
    matched_text = matched.get("text") or ""
    target = normalize_title(book.get("title") or "")
    matched_norm = normalize_title(matched_text)

    # 교재 제목이 자료 게시물 제목 안에 충분히 포함되는 경우만 자동 채택한다.
    if not target or target not in matched_norm:
        return None

    candidates = []
    seen = set()
    for item in result.get("direct_candidates", []):
        url = item.get("url") or ""
        filename = (item.get("text") or "").strip()
        if DOWNLOAD_PATH not in url or not PDF_RE.search(filename):
            continue
        key = (url, filename)
        if key not in seen:
            seen.add(key)
            candidates.append({
                "url": url,
                "filename": filename,
                "context": item.get("context") or "",
            })

    # 정답책/실전책 등 여러 PDF가 같이 있으면 사람이 확인하기 전에는 하나를 추측하지 않는다.
    if len(candidates) != 1:
        return None

    candidate = candidates[0]
    query = parse_qs(urlparse(candidate["url"]).query)
    file_id = (query.get("id") or [None])[0]
    if not file_id:
        return None

    final_url = result.get("final_url") or result.get("resource_page")
    if not final_url or "#answer/view/" not in final_url:
        return None

    return {
        **candidate,
        "publisher_file_id": file_id,
        "resource_page": final_url,
        "post_id": result.get("post_id"),
        "matched_row": matched_text,
    }


def verify_download(context, candidate: dict) -> dict:
    try:
        response = context.request.get(
            candidate["url"],
            headers={
                "Referer": candidate["resource_page"],
                "Accept": "application/pdf,application/octet-stream,*/*",
            },
            timeout=30000,
        )
        body = response.body()
        content_type = (response.headers.get("content-type") or "").lower()
        disposition = (response.headers.get("content-disposition") or "").lower()
        ok = (
            response.ok
            and len(body) > 500
            and (
                body.startswith(b"%PDF")
                or "application/pdf" in content_type
                or "attachment" in disposition
                or "octet-stream" in content_type
            )
        )
        return {
            "ok": ok,
            "status": response.status,
            "content_type": content_type,
            "content_disposition": disposition,
            "bytes": len(body),
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "content_type": None,
            "content_disposition": None,
            "bytes": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EBS 초등/중학 미확인 정답 PDF를 보수적으로 확인하고 catalog 후보를 갱신합니다."
    )
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.json"))
    parser.add_argument("--report", type=Path, default=Path("ebs-school-answer-sync-report.json"))
    parser.add_argument("--limit-per-site", type=int, default=6)
    args = parser.parse_args()

    data = json.loads(args.catalog.read_text(encoding="utf-8"))
    pending = [
        book for book in data.get("books", [])
        if book.get("publisher") == "EBS"
        and book.get("publisher_site") in {"ebs_primary", "ebs_middle"}
        and book.get("publisher_book_id")
        and answer_material(book)
        and not answer_material(book).get("direct_url")
    ]
    pending.sort(key=lambda book: (
        book.get("publisher_site") or "",
        book.get("grade") or 99,
        book.get("subject") or "",
        book.get("title") or "",
    ))

    if args.limit_per_site:
        selected = []
        for site in ("ebs_primary", "ebs_middle"):
            site_books = [
                book for book in pending
                if book.get("publisher_site") == site
            ]
            selected.extend(rotating_batch(site_books, args.limit_per_site))
        pending = selected

    checks = []
    changes = []
    today = date.today().isoformat()

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

        for book in pending:
            material = answer_material(book)
            try:
                result = collect_one(page, book)
                candidate = safe_candidate(book, result)
                verification = (
                    verify_download(context, candidate) if candidate else None
                )
                accepted = bool(candidate and verification and verification["ok"])
                check = {
                    "book_id": book.get("book_id"),
                    "publisher_book_id": book.get("publisher_book_id"),
                    "title": book.get("title"),
                    "matched_row": (result.get("matched_row") or {}).get("text"),
                    "candidate_count": len(result.get("direct_candidates", [])),
                    "accepted": accepted,
                    "candidate": candidate,
                    "verification": verification,
                    "error": None,
                }
                checks.append(check)

                if not accepted:
                    continue

                before = {
                    "direct_url": material.get("direct_url"),
                    "resource_page": material.get("resource_page"),
                    "publisher_file_id": material.get("publisher_file_id"),
                    "status": material.get("status"),
                    "access": material.get("access"),
                }
                after = {
                    "direct_url": candidate["url"],
                    "resource_page": candidate["resource_page"],
                    "publisher_file_id": candidate["publisher_file_id"],
                    "status": "ok",
                    "access": "public",
                }
                if before != after:
                    material.update(after)
                    material["last_checked"] = today
                    changes.append({
                        "book_id": book.get("book_id"),
                        "title": book.get("title"),
                        "before": before,
                        "after": after,
                        "filename": candidate["filename"],
                        "post_id": candidate.get("post_id"),
                    })
            except Exception as exc:
                checks.append({
                    "book_id": book.get("book_id"),
                    "publisher_book_id": book.get("publisher_book_id"),
                    "title": book.get("title"),
                    "accepted": False,
                    "candidate": None,
                    "error": f"{type(exc).__name__}: {exc}",
                })

        context.close()
        browser.close()

    if changes:
        data.setdefault("meta", {})["generated_at"] = today
        args.catalog.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    report = {
        "checked_at": today,
        "pending_total_before_run": len([
            book for book in data.get("books", [])
            if book.get("publisher") == "EBS"
            and book.get("publisher_site") in {"ebs_primary", "ebs_middle"}
            and answer_material(book)
            and not answer_material(book).get("direct_url")
        ]) + len(changes),
        "checked_count": len(checks),
        "accepted_count": sum(1 for item in checks if item.get("accepted")),
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
