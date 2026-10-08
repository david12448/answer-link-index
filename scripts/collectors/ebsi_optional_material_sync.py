from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

from ebsi_optional_material_probe import inspect_one


def find_material(book: dict, kind: str) -> dict | None:
    return next(
        (item for item in book.get("materials", []) if item.get("type") == kind),
        None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EBSi MP3/부가자료 존재 여부를 점검하고 확인된 자료만 catalog에 노출합니다."
    )
    parser.add_argument("--catalog", type=Path, default=Path("data/catalog.json"))
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("ebsi-optional-material-sync-report.json"),
    )
    args = parser.parse_args()

    data = json.loads(args.catalog.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    targets = []
    for book in data.get("books", []):
        if book.get("publisher") != "EBS" or book.get("publisher_site") != "ebsi":
            continue
        for kind in ("mp3", "additional"):
            material = find_material(book, kind)
            if material:
                targets.append((book, kind, material))

    checks = []
    changes = []

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

        for book, kind, material in targets:
            before = {
                "availability": material.get("availability") or "unknown",
                "status": material.get("status"),
                "resource_page": material.get("resource_page"),
            }
            try:
                result = inspect_one(page, book, kind)
                book_id = book.get("publisher_book_id") or ""
                exact_detail = (
                    kind == "mp3"
                    and bool(result.get("detail_clicked"))
                    and book_id in (result.get("final_url") or "")
                    and book_id in (result.get("detail_call") or "")
                )
                dom_file_count = int(result.get("mp3_file_count") or 0)
                ajax_file_count = int(result.get("ajax_mp3_file_count") or 0)
                file_count = max(dom_file_count, ajax_file_count)

                desired = before.copy()
                if kind == "mp3" and exact_detail and file_count > 0:
                    desired = {
                        "availability": "available",
                        "status": "ok",
                        "resource_page": result.get("final_url"),
                    }
                elif kind == "additional":
                    # 부가자료는 게시물/첨부의 교재 일치 검증이 더 필요하므로
                    # 현재는 자동으로 available 승격하지 않는다.
                    desired = before
                elif before["availability"] != "available":
                    # 파일 0개를 곧바로 '없음'으로 단정하지 않는다.
                    desired = {
                        **before,
                        "availability": "unknown",
                    }

                changed = any(before.get(k) != desired.get(k) for k in desired)
                if changed:
                    material.update(desired)
                    material["last_checked"] = today
                    changes.append({
                        "book_id": book.get("book_id"),
                        "title": book.get("title"),
                        "kind": kind,
                        "before": before,
                        "after": desired,
                        "file_count": file_count,
                    })

                checks.append({
                    "book_id": book.get("book_id"),
                    "title": book.get("title"),
                    "kind": kind,
                    "exact_detail": exact_detail,
                    "file_count": file_count,
                    "dom_file_count": dom_file_count,
                    "ajax_file_count": ajax_file_count,
                    "availability": desired.get("availability"),
                    "changed": changed,
                    "error": None,
                })
            except Exception as exc:
                checks.append({
                    "book_id": book.get("book_id"),
                    "title": book.get("title"),
                    "kind": kind,
                    "availability": before.get("availability"),
                    "changed": False,
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
