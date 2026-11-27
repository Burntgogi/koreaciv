"""6단계 다듬기(6b) 스크린샷 (docs/screenshots/6b_*.png). 실행: python tools/screens_phase6b.py
조작은 실제 입력(마우스·키보드)으로 하고, evaluate 는 좌표·상태를 읽는 데만 쓴다.
1. 전국 화면: 원전 5곳 (전체 + 남동부 2배 확대)
2. 중간 배율 서울: 대학 묶음 표지와 그 패널, 묶음 안 대학 하나의 항목 패널(위치 문구)
3. 도시 패널: 값 옆 ⓘ 와 하나를 눌러 연 문장
"""
import functools
import http.server
import json
import os
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
SHOT = os.path.join(ROOT, "docs", "screenshots")
VIEW = "#v=3302,3352,0.1350"   # 6단계 전국 첫 화면과 같은 위치·배율 (1600×900)


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=SITE))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/index.html"


def ready(pg, url):
    pg.goto("about:blank")
    pg.goto(url)
    pg.wait_for_function("window.app && window.app.layerR && window.app.layers", timeout=30000)
    pg.wait_for_timeout(1500)


def shot(pg, name, **kw):
    pg.screenshot(path=os.path.join(SHOT, name), **kw)
    print("찍음", name)


def placed(pg):
    return pg.evaluate("""(() => app.layerR.placed.map(q => ({kind: q.it.kind, name: q.it.name, x: Math.round(q.x), y: Math.round(q.y),
        moved: q.ox != null ? Math.round(Math.hypot(q.x - q.ox, q.y - q.oy)) : 0, group: !!q.it.group})))()""")


def main():
    srv, url = serve()
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1600, "height": 900}, device_scale_factor=1)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        # 1. 전국: 원전 5곳
        ready(pg, url + VIEW)
        pl = placed(pg)
        out["national"] = {"z": pg.evaluate("app.cam.scale / app.cam.minScale"), "nuclear": [q for q in pl if q["kind"] == "nuclear"],
                           "knowledge": [q for q in pl if q["kind"] == "knowledge"], "banners": pg.evaluate("app.banners.rects.map(r => r.c.name)")}
        shot(pg, "6b_nation_nuclear.png")
        ctx2 = b.new_context(viewport={"width": 1600, "height": 900}, device_scale_factor=2)
        p2 = ctx2.new_page()
        ready(p2, url + VIEW)
        shot(p2, "6b_nation_nuclear_se.png", clip={"x": 780, "y": 260, "width": 220, "height": 320})
        shot(p2, "6b_nation_nuclear_sw.png", clip={"x": 540, "y": 470, "width": 200, "height": 110})
        ctx2.close()
        # 2. 중간 배율 서울: 대학 묶음
        mn = pg.evaluate("app.cam.minScale")
        ready(pg, url + f"#v=2282,1660,{mn * 2.9:.4f}")
        pl = placed(pg)
        out["seoul_mid"] = {"z": pg.evaluate("app.cam.scale / app.cam.minScale"), "groups": [q for q in pl if q["group"]],
                            "knowledge": [q for q in pl if q["kind"] == "knowledge" and not q["group"]]}
        g = next((q for q in pl if q["group"] and q["name"] == "대학 3"), None) or next((q for q in pl if q["group"]), None)
        if g:
            pg.mouse.move(g["x"], g["y"])
            pg.wait_for_timeout(300)
            shot(pg, "6b_seoul_mid_groups_hover.png")
            pg.mouse.click(g["x"], g["y"])
            pg.wait_for_timeout(500)
            pg.mouse.move(5, 450)
            pg.wait_for_timeout(200)
            shot(pg, "6b_seoul_mid_groups.png")
            out["group_panel"] = pg.inner_text("#panel")[:600]
            # 묶음 안 첫 대학을 눌러 항목 패널 (위치 문구)
            pg.locator("#panel tr[data-item]").first.click()
            pg.wait_for_timeout(500)
            shot(pg, "6b_item_university.png")
            out["item_panel"] = pg.inner_text("#panel")[:500]
        else:
            print("!! 중간 배율 서울에 그려진 대학 묶음 표지가 없음")
        # 3. 도시 패널 값 옆 ⓘ (인천: 보훈 인원 옆 ⓘ 두 개, 수입 옆 ⓘ). 수입 옆 ⓘ 를 눌러 연다
        ready(pg, url + VIEW)
        pg.keyboard.press("/")
        pg.keyboard.type("인천")
        pg.wait_for_timeout(250)
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(1200)
        fn = pg.locator('#panel [data-k="trade-import"] .fn').last
        fn.scroll_into_view_if_needed()
        pg.wait_for_timeout(200)
        fn.click()
        pg.wait_for_timeout(300)
        shot(pg, "6b_panel_value_fn.png")
        out["fn_open"] = pg.evaluate("document.getElementById('fnpop').innerText")
        pg.keyboard.press("Escape")
        fv = pg.locator('#panel [data-k="vet-count"] .fn').first
        fv.scroll_into_view_if_needed()
        pg.wait_for_timeout(200)
        fv.hover()
        pg.wait_for_timeout(300)
        shot(pg, "6b_panel_value_fn_hover.png")
        out["fn_hover"] = pg.evaluate("document.getElementById('fnpop').innerText")
        out["errors"] = errs
        ctx.close()
        b.close()
    srv.shutdown()
    with open(os.path.join(SHOT, "6b_info.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
