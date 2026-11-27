"""README 그림: site/ 를 임시 서버로 띄워 두 판·출처·교육 쪽을 찍고 assets/ 에 JPEG 로 저장한다.
실행: python tools/readme/shots.py  (Playwright·Pillow 필요)"""
import http.server, io, socketserver, threading, functools, pathlib
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
SITE, OUT = ROOT / "site", ROOT / "assets"
OUT.mkdir(exist_ok=True)

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

http.server.ThreadingHTTPServer.request_queue_size = 128
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(SITE)))
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
B = f"http://127.0.0.1:{port}/"

SHOTS = [  # 이름, 주소, 폭, 높이, 기다림(ms)
    ("classic-nation", "index.html#intro=0", 1600, 900, 3500),
    ("yeojido-nation", "yeojido/index.html#intro=0&v=0", 1600, 900, 4500),
    ("yeojido-title", "yeojido/index.html", 1600, 900, 4500),
    ("classic-city", "index.html#city=12", 1600, 900, 3500),
    ("yeojido-city", "yeojido/index.html#city=12", 1600, 900, 5000),
    ("classic-lens", "index.html#lens=extinction", 1600, 900, 3500),
    ("sources", "sources/index.html", 1280, 800, 2000),
    ("edu", "edu/index.html#lessons", 1280, 800, 2500),
]
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, url, w, h, wait in SHOTS:
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
        if name != "yeojido-title":
            ctx.add_init_script("try{sessionStorage.setItem('yeojido.seen','1')}catch(e){}")
        pg = ctx.new_page()
        pg.on("console", lambda m, n=name: errs.append((n, m.text)) if m.type == "error" else None)
        pg.on("pageerror", lambda e, n=name: errs.append((n, str(e))))
        pg.goto(B + url); pg.wait_for_timeout(wait)
        Image.open(io.BytesIO(pg.screenshot())).convert("RGB").save(OUT / f"{name}.jpg", quality=84, optimize=True, progressive=True)
        ctx.close()
    b.close()
srv.shutdown()

a, c = Image.open(OUT / "classic-nation.jpg"), Image.open(OUT / "yeojido-nation.jpg")
W = 1600; half = W // 2
ban = Image.new("RGB", (W, 450), (20, 24, 32))
ban.paste(a.resize((half, 450)), (0, 0)); ban.paste(c.resize((half, 450)), (half, 0))
ban.save(OUT / "banner.jpg", quality=84, optimize=True, progressive=True)
for f in sorted(OUT.glob("*.jpg")):
    print(f.name, f.stat().st_size // 1024, "KB")
print("console errors:", errs or "없음")
