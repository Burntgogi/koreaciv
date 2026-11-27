"""6단계 보고용 스크린샷 (docs/screenshots/6_*.png). 실행: python tools/screens_phase6.py
조작은 실제 입력(마우스·키보드·탭)으로 하고, evaluate 는 좌표·상태를 읽는 데만 쓴다. 정리 전 화면(6_nation_before.png)은 작업 전에 따로 찍어 두었다.
"""
import functools
import http.server
import json
import os
import shutil
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
SHOT = os.path.join(ROOT, "docs", "screenshots")
VIEW = "#v=3302,3352,0.1350"   # 정리 전 화면과 같은 위치·배율 (1600×900 첫 화면)


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=SITE))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/index.html"


def ready(pg, url):
    pg.goto(url)
    pg.wait_for_function("window.app && window.app.layerR && window.app.layers", timeout=30000)
    pg.wait_for_timeout(1500)


def flag(pg, name):
    return pg.evaluate("(n) => { const b = app.banners.rects.find(r => r.c.name === n); return b ? [b.x + b.w / 2, b.y + 9] : null; }", name)


def shot(pg, name, **kw):
    p = os.path.join(SHOT, name)
    pg.screenshot(path=p, **kw)
    print("찍음", name)


def main():
    srv, url = serve()
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1600, "height": 900}, accept_downloads=True)
        pg = ctx.new_page()
        ready(pg, url + VIEW)
        shot(pg, "6_nation_after.png")
        # 배율별로 실제로 그린 아이콘 수 (겹침·깃발 피하기 뒤, 이 화면에서) — 읽기만
        out["drawn_national"] = pg.evaluate("(() => { const c = {}; for (const q of app.layerR.placed) c[q.it.kind] = (c[q.it.kind] || 0) + 1; return {z: app.cam.scale / app.cam.minScale, n: app.layerR.placed.length, by: c, flags: app.banners.rects.length}; })()")
        # 수도권 깃발이 아이콘에 가리지 않는지: 깃발 상자와 겹치는 아이콘 수 (읽기만)
        out["flag_icon_overlap"] = pg.evaluate("""(() => { let n = 0; const names = []; for (const f of app.banners.rects) for (const q of app.layerR.placed) {
            if (q.x + q.r > f.r.x0 && q.x - q.r < f.r.x1 && q.y + q.r > f.r.y0 && q.y - q.r < f.r.y1) { n++; names.push(f.c.name + '/' + q.it.name); } } return {n, names}; })()""")
        shot(pg, "6_capital_region.png", clip={"x": 520, "y": 120, "width": 360, "height": 260})
        # 중간·가까운 배율 (서울 중심, 휠로 확대)
        for target, nm in ((2.4, "mid"), (3.6, "near")):
            ready(pg, url + VIEW)
            sx, sy = flag(pg, "서울")
            pg.mouse.move(sx, sy + 30)
            for _ in range(40):
                z = pg.evaluate("app.cam.scale / app.cam.minScale")
                if z >= target:
                    break
                pg.mouse.wheel(0, -60)
                pg.wait_for_timeout(40)
            pg.wait_for_timeout(700)
            out[f"drawn_{nm}"] = pg.evaluate("(() => { const c = {}; for (const q of app.layerR.placed) c[q.it.kind] = (c[q.it.kind] || 0) + 1; return {z: app.cam.scale / app.cam.minScale, n: app.layerR.placed.length, by: c, flags: app.banners.rects.length}; })()")
            shot(pg, f"6_zoom_{nm}.png")
        # 보고서
        ready(pg, url + VIEW)
        pg.click('[data-report="gold"]')
        pg.wait_for_timeout(400)
        shot(pg, "6_report_gold.png")
        pg.click('[data-report="population"]')
        pg.wait_for_timeout(400)
        shot(pg, "6_report_population.png")
        pg.keyboard.press("Escape")
        # 도움말
        pg.keyboard.press("?")
        pg.wait_for_timeout(300)
        shot(pg, "6_help.png")
        pg.keyboard.press("Escape")
        # 범례 구간 (고령 비율 렌즈, 마우스로 끄는 중)
        pg.click('#lensbar [data-group="people"]')
        pg.click('#lensbar [data-lens="over65"]')
        pg.wait_for_timeout(600)
        bb = pg.locator("#legend .fbar").bounding_box()
        pg.mouse.move(bb["x"] + bb["width"] * 0.62, bb["y"] + bb["height"] / 2, steps=3)
        pg.mouse.down()
        pg.mouse.move(bb["x"] + bb["width"] * 0.98, bb["y"] + bb["height"] / 2, steps=6)
        pg.wait_for_timeout(900)
        shot(pg, "6_legend_range.png")
        pg.mouse.up()
        # 공유 PNG (내려받은 파일 그대로)
        pg.mouse.move(800, 450)
        pg.click('#lensbar [data-lens=""]')
        sx, sy = flag(pg, "서울")
        pg.mouse.click(sx, sy)
        pg.wait_for_timeout(300)
        pg.click('#lensbar [data-group="living"]')
        pg.click('#lensbar [data-lens="gdp_pc"]')
        pg.wait_for_timeout(600)
        pg.click("#share-btn")
        with pg.expect_download() as dl:
            pg.click('#sharemenu [data-act="png"]')
        shutil.copyfile(dl.value.path(), os.path.join(SHOT, "6_share_png.png"))
        print("찍음 6_share_png.png (내려받은 PNG)", dl.value.suggested_filename)
        # 층 조작부: 접힘·펼침
        ready(pg, url + VIEW)
        shot(pg, "6_layers_collapsed.png", clip={"x": 0, "y": 60, "width": 420, "height": 120})
        pg.click("#layerctl .more")
        pg.wait_for_timeout(300)
        shot(pg, "6_layers_expanded.png", clip={"x": 0, "y": 60, "width": 420, "height": 700})
        pg.click("#layerctl .more")
        # 패널 ⓘ 주석 (울산: 경제 구역의 ⓘ 를 눌러 고정, 그 구역의 '기준과 주의' 펼침)
        pg.keyboard.press("/")
        pg.keyboard.type("울산")
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(1200)
        fn = pg.locator("#panel h4 .fn").nth(1)
        fn.scroll_into_view_if_needed()
        pg.wait_for_timeout(200)
        det = pg.locator("#panel details.caveats").nth(1)
        det.locator("summary").click()
        pg.wait_for_timeout(200)
        fn.click()
        pg.wait_for_timeout(250)
        shot(pg, "6_panel_notes.png")
        ctx.close()
        # 모바일 390
        m = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
        mp = m.new_page()
        ready(mp, url)
        shot(mp, "6_mobile_first.png")
        fx = flag(mp, "서울")
        mp.touchscreen.tap(*fx)
        mp.wait_for_timeout(700)
        shot(mp, "6_mobile_panel.png")
        mp.locator("#panel .close").tap()
        mp.wait_for_timeout(200)
        mp.locator('#lensbar [data-group="people"]').tap()
        mp.locator('#lensbar [data-lens="extinction"]').tap()
        mp.wait_for_timeout(400)
        mp.locator("#legend h5").tap()
        mp.wait_for_timeout(600)
        shot(mp, "6_mobile_lens.png")
        m.close()
        b.close()
    srv.shutdown()
    # 정리 전·후 나란히 (같은 1600×900, 같은 위치·배율)
    from PIL import Image
    bf, af = Image.open(os.path.join(SHOT, "6_nation_before.png")), Image.open(os.path.join(SHOT, "6_nation_after.png"))
    cmp_ = Image.new("RGB", (bf.width + af.width + 12, max(bf.height, af.height)), (12, 24, 38))
    cmp_.paste(bf.convert("RGB"), (0, 0))
    cmp_.paste(af.convert("RGB"), (bf.width + 12, 0))
    cmp_.save(os.path.join(SHOT, "6_nation_compare.png"))
    print("만듦 6_nation_compare.png (왼쪽 정리 전, 오른쪽 정리 뒤)")
    with open(os.path.join(SHOT, "6_icon_counts.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
