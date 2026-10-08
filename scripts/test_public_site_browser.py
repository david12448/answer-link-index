"""Check the built public UI and its real network requests in Chromium."""
import functools
import json
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
from build_public_site import build


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def assert_no_horizontal_overflow(page):
    overflow = page.evaluate("""() => ({
      width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
      elements: [...document.querySelectorAll('body *')].filter(el => {
        const rect = el.getBoundingClientRect();
        return rect.width && (rect.right > innerWidth + 1 || rect.left < -1);
      }).map(el => ({tag: el.tagName, id: el.id, className: el.className,
                    width: el.getBoundingClientRect().width}))
    })""")
    assert overflow["scrollWidth"] <= overflow["width"], json.dumps(overflow, ensure_ascii=False)


def main():
    screenshots = Path("public-site-smoke")
    screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "site"
        build(output)
        catalog = json.loads((output / "data/catalog.json").read_text())
        book = next(b for b in catalog["books"] if b["book_id"] == "ebs-middle-neuron-math-1-upper-2022")
        handler = functools.partial(QuietHandler, directory=str(output))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 390, "height": 844})
                requests, errors = [], []
                page.on("request", lambda request: requests.append(request.url))
                page.on("pageerror", lambda error: errors.append(str(error)))
                base = f"http://127.0.0.1:{server.server_port}/index.html"
                page.goto(base + f"?book={book['book_id']}&embed=1", wait_until="domcontentloaded")
                page.wait_for_function("document.querySelectorAll('.book-card').length === 1")
                assert page.locator(".book-title").inner_text() == book["title"]
                assert not page.locator("#filters").is_visible()
                assert not any(url.endswith("/data/catalog.json") for url in requests)
                assert any(url.endswith(f"/data/books/{book['book_id']}.json") for url in requests)
                assert page.locator(".materials").get_by_text("로그인", exact=False).count() > 0
                page.screenshot(path=str(screenshots / "book-mobile.png"), full_page=True)
                assert_no_horizontal_overflow(page)
                requests.clear()
                page.goto(base + "?book=nonexistent-book&embed=1", wait_until="domcontentloaded")
                page.wait_for_selector("#results .empty")
                assert not any(url.endswith("/data/catalog.json") for url in requests)
                page.goto(base, wait_until="domcontentloaded")
                page.wait_for_function("document.querySelectorAll('.book-card').length === 20")
                assert page.locator("#resultCount").inner_text() == str(len(catalog["books"]))
                page.locator("#loadMoreButton").click()
                assert page.locator(".book-card").count() == 40
                page.locator("#searchInput").fill("기출로 영문법")
                page.wait_for_function("document.querySelectorAll('.book-card').length === 3")
                page.screenshot(path=str(screenshots / "search-mobile.png"), full_page=True)
                assert_no_horizontal_overflow(page)
                assert not errors, errors
                browser.close()
                print("Browser passed: mobile embed, one-book transfer, missing ID, 20/40 pagination, title search, no JS errors")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
