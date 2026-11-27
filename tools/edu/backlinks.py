"""두 판과 출처 쪽에서 교육 쪽으로 가는 고리 점검: python tools/edu/backlinks.py
기존판·신여지도의 연감 '출처' 갈피와 출처 쪽 머리에 edu/ 로 가는 고리가 있고, 눌러서 교육 쪽이 열리는지 본다. docs/screenshots/11_edu_from_*.png 를 찍는다.
"""
import functools, http.server, json, os, socketserver, sys, threading
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(ROOT, "site")
OUT = os.path.join(ROOT, "docs", "screenshots")


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    s = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(Q, directory=SITE)); s.daemon_threads = True
    threading.Thread(target=s.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{s.server_address[1]}"
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 800})
        for ed, path, ready, opener in (("classic", "/", "window.app && window.app.layers", "app.almanac.open('sources')"),
                                         ("yeojido", "/yeojido/#v=3250,3150,0.12", "window.app && window.app.layerMap", "app.almanac.open('sources')")):
            pg = ctx.new_page(); errs = []
            pg.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
            pg.on("console", lambda m, errs=errs: errs.append(m.text) if m.type == "error" else None)
            pg.goto(base + path)
            try:
                pg.wait_for_function(ready, timeout=30000)
                try:
                    pg.evaluate(opener)
                except Exception:
                    pg.click("text=연감"); pg.wait_for_timeout(400); pg.click("role=tab[name='출처']")
                pg.wait_for_selector("a[href$='edu/']", timeout=15000)
                pg.locator("a[href$='edu/']").first.scroll_into_view_if_needed()
                pg.screenshot(path=os.path.join(OUT, f"11_edu_from_{ed}.png"))
                pg.click("a[href$='edu/']")
                pg.wait_for_function("document.body.classList.contains('is-ready')", timeout=15000)
                res[ed] = {"arrived": pg.url.replace(base, ""), "h1": pg.inner_text("h1"), "errors": errs}
            except Exception as e:
                res[ed] = {"failed": str(e)[:300], "errors": errs}
            pg.close()
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(base + "/sources/"); pg.wait_for_function("document.body.classList.contains('is-ready')", timeout=15000)
        pg.screenshot(path=os.path.join(OUT, "11_edu_from_sources.png"))
        pg.click("#to-edu"); pg.wait_for_function("document.body.classList.contains('is-ready')", timeout=15000)
        res["sources"] = {"arrived": pg.url.replace(base, ""), "h1": pg.inner_text("h1"), "errors": errs}
        for sel in ("#back-koreaciv", "#back-yeojido", "#to-sources"):
            pg.goto(base + "/edu/"); pg.wait_for_function("document.body.classList.contains('is-ready')", timeout=15000)
            pg.click(sel); pg.wait_for_load_state("domcontentloaded")
            res["edu " + sel] = pg.url.replace(base, "")
        b.close()
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
