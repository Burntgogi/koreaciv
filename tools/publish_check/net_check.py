import http.server, functools, threading, pathlib
from playwright.sync_api import sync_playwright
SITE = pathlib.Path(__file__).resolve().parents[2] / "site"
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(SITE)))
port = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{port}/"
with sync_playwright() as p:
    b = p.chromium.launch()
    for path in ["", "#city=12&lens=density", "yeojido/", "yeojido/#city=12", "sources/", "edu/"]:
        ctx = b.new_context(); pg = ctx.new_page(); ext, n, errs = [], 0, []
        def onreq(r):
            global n
            if not r.url.startswith(base) and not r.url.startswith("data:") and not r.url.startswith("blob:"): ext.append(r.url)
        pg.on("request", onreq); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(base + path); pg.wait_for_timeout(3500)
        print(f"{path or '/':24} 외부 요청 {len(ext)} {ext[:3]} · 쿠키 {len(ctx.cookies())} · 페이지 오류 {len(errs)}")
        ctx.close()
    b.close()
srv.shutdown()
