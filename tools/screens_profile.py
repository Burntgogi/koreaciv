"""두 빌드 판(전체판·공개판) 나란히 찍기 → docs/screenshots/10_*.png

전체판 자료는 data/build/site_data_full/ (python pipeline/build_all.py --profile full 이 남긴 사본), 공개판은 site/data.
판마다 site/ 를 임시 폴더에 복사하고 data/ 만 그 판의 것으로 바꿔 띄운다 (site/ 는 건드리지 않는다). 콘솔 오류도 센다.
실행: python tools/screens_profile.py
"""
import functools
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
SHOT = os.path.join(ROOT, "docs", "screenshots")
DATA = {"full": os.path.join(ROOT, "data", "build", "site_data_full"), "public": os.path.join(SITE, "data")}


def serve(root):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def shoot(br, base, prof, log):
    errs = []
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
    pg.on("console", lambda m: errs.append(m.text[:160]) if m.type == "error" else None)
    # 1. 전국 화면 (기존판)
    pg.goto(base + "index.html")
    pg.wait_for_function("window.app && window.app.layerR && window.app.layers", timeout=40000)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=os.path.join(SHOT, f"10_{prof}_national.png"))
    # 2. 논 지대 확대 (호남평야: 김제시 깃발 자리, 전국 화면의 5배) — 피복 빛깔과 논 무늬
    c = pg.evaluate("() => { const c = app.cities.find((x) => x.name === '김제시'); return { x: c.x, y: c.y, s: app.cam.minScale * 5 }; }")
    pg.goto(base + f"index.html#v={c['x']:.1f},{c['y']:.1f},{c['s']:.4f}")
    pg.wait_for_function("window.app && window.app.layerR && window.app.layers", timeout=40000)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(2500)
    pg.screenshot(path=os.path.join(SHOT, f"10_{prof}_paddy_closeup.png"))
    # 3. 도시 패널 (수원시, 경제 탭: 공개판은 아파트 칸이 '이 판에서는 제공하지 않음')
    cid = pg.evaluate("() => app.cities.find((x) => x.name === '수원시').id")
    pg.goto(base + f"index.html#city={cid}&tab=econ")
    pg.wait_for_function("window.app && window.app.layerR && window.app.layers && app.panel.mode === 'city'", timeout=40000)
    pg.wait_for_timeout(1500)
    pg.evaluate("() => { const d = [...document.querySelectorAll('#panel .kv.econ > div')].find((x) => /아파트/.test(x.innerText)); if (d) d.scrollIntoView({ block: 'center' }); }")
    pg.wait_for_timeout(400)
    pg.screenshot(path=os.path.join(SHOT, f"10_{prof}_city_panel.png"))
    housing = pg.evaluate("() => [...document.querySelectorAll('#panel .kv.econ > div')].filter((x) => /아파트/.test(x.innerText)).map((x) => x.innerText.replace(/\\s+/g, ' ')).slice(0, 3)")
    # 4. 신여지도 전국 화면
    pg.goto(base + "yeojido/index.html#intro=0")
    pg.wait_for_function("window.app && window.app.layerMap", timeout=40000)
    pg.wait_for_timeout(2500)
    pg.screenshot(path=os.path.join(SHOT, f"10_{prof}_yeojido_national.png"))
    # 5. 출처 쪽의 '이 판' 안내
    pg.goto(base + "sources/index.html#profile")
    pg.wait_for_selector("body.is-ready", timeout=20000)
    pg.wait_for_timeout(600)
    pg.evaluate("() => document.getElementById('profile').scrollIntoView()")
    pg.wait_for_timeout(300)
    pg.screenshot(path=os.path.join(SHOT, f"10_{prof}_sources_profile.png"))
    pg.evaluate("() => document.getElementById('notices').scrollIntoView()")
    pg.wait_for_timeout(300)
    pg.screenshot(path=os.path.join(SHOT, f"10_{prof}_sources_notices.png"))
    ctx.close()
    log[prof] = {"console_errors": errs, "housing_rows": housing}


def main():
    os.makedirs(SHOT, exist_ok=True)
    log = {}
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome")
        for prof, data in DATA.items():
            tmp = tempfile.mkdtemp(prefix=f"koreaciv-{prof}-")
            try:
                dst = os.path.join(tmp, "site")
                shutil.copytree(SITE, dst, ignore=shutil.ignore_patterns("data", "edu"))
                shutil.copytree(data, os.path.join(dst, "data"), ignore=shutil.ignore_patterns("NOTICE.md"))
                got = (json.load(open(os.path.join(dst, "data", "sources.json"), encoding="utf-8")).get("profile") or {}).get("profile", "full")
                if got != prof:
                    raise SystemExit(f"{data} 는 {got} 판이다 ({prof} 판을 기대)")
                srv, base = serve(dst)
                shoot(br, base, prof, log)
                srv.shutdown()
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        br.close()
    print(json.dumps(log, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
