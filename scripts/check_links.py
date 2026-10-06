from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "catalog.json"
REPORT = ROOT / "data" / "link-status.json"
USER_AGENT = "answer-link-index/1.0 (+GitHub Actions link checker)"

class TrackingRedirectHandler(HTTPRedirectHandler):
    def __init__(self):
        self.redirects = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirects.append({"code": code, "from": req.full_url, "to": newurl})
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def check_url(url: str) -> dict:
    handler = TrackingRedirectHandler()
    opener = build_opener(handler)
    req = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with opener.open(req, timeout=20) as response:
            status_code = getattr(response, "status", 200)
            final_url = response.geturl()
            status = "redirect" if handler.redirects or final_url != url else "ok"
            return {"url": url, "status": status, "http_status": status_code, "final_url": final_url, "redirects": handler.redirects, "error": None}
    except HTTPError as exc:
        if exc.code in (401, 403):
            status = "restricted"
        elif exc.code == 404:
            status = "broken"
        else:
            status = "http_error"
        return {"url": url, "status": status, "http_status": exc.code, "final_url": getattr(exc, "url", url), "redirects": handler.redirects, "error": str(exc)}
    except (URLError, TimeoutError) as exc:
        return {"url": url, "status": "network_error", "http_status": None, "final_url": None, "redirects": handler.redirects, "error": str(exc)}

def iter_targets(data: dict):
    for book in data.get("books", []):
        if book.get("official_page"):
            yield {"book_id": book["book_id"], "resource_id": None, "kind": "official_page", "url": book["official_page"]}
        if book.get("cover_image_url"):
            yield {"book_id": book["book_id"], "resource_id": None, "kind": "cover_image_url", "url": book["cover_image_url"]}
        for material in book.get("materials", []):
            if material.get("resource_page"):
                yield {"book_id": book["book_id"], "resource_id": material["resource_id"], "kind": "resource_page", "url": material["resource_page"]}
            if material.get("direct_url"):
                yield {"book_id": book["book_id"], "resource_id": material["resource_id"], "kind": "direct_url", "url": material["direct_url"]}
        for course in book.get("courses", []):
            if course.get("course_url"):
                yield {"book_id": book["book_id"], "resource_id": course["course_id"], "kind": "course_url", "url": course["course_url"]}

def main():
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    checks = []
    seen = set()
    for target in iter_targets(data):
        key = (target["kind"], target["url"])
        if key in seen:
            continue
        seen.add(key)
        result = check_url(target["url"])
        result.update({"book_id": target["book_id"], "resource_id": target["resource_id"], "kind": target["kind"], "checked_at": date.today().isoformat()})
        checks.append(result)
        print(f'{result["status"]:>13} {target["kind"]:<14} {target["url"]}')
        time.sleep(0.25)

    previous = {}
    if REPORT.exists():
        try:
            old = json.loads(REPORT.read_text(encoding="utf-8"))
            previous = {(x["kind"], x["url"]): x for x in old.get("checks", [])}
        except Exception:
            previous = {}

    changes = []
    for item in checks:
        old = previous.get((item["kind"], item["url"]))
        if not old:
            continue
        if old.get("status") != item.get("status") or old.get("final_url") != item.get("final_url") or old.get("http_status") != item.get("http_status"):
            changes.append({"kind": item["kind"], "url": item["url"], "book_id": item["book_id"], "before": {"status": old.get("status"), "http_status": old.get("http_status"), "final_url": old.get("final_url")}, "after": {"status": item.get("status"), "http_status": item.get("http_status"), "final_url": item.get("final_url")}})

    payload = {"checked_at": date.today().isoformat(), "total": len(checks), "changes": changes, "checks": checks}
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"checked={len(checks)} changes={len(changes)} report={REPORT}")

if __name__ == "__main__":
    main()
