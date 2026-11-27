"""7b 단계 (docs/ideas/site_r3.md) 스크린샷과 화면 요소 수. 실행: python tools/screens_7b.py before | after

- before: 고치기 전 전국 첫 화면(1280×800·390×844)과 울산 도시 패널 첫 화면을 찍고 요소 수를 docs/screenshots/7b_counts_before.json 에 남긴다.
- after : 같은 것과 명세 합격 기준을 볼 화면들을 찍고 요소 수를 7b_counts_after.json 에 남긴다.
요소 수는 before·after 가 같은 함수(COUNT_JS)로 센다. 조작은 실제 입력(마우스·키보드)으로 하고 evaluate 는 상태·좌표를 읽는 데만 쓴다.
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

# 화면에 보이는 요소 수: 조작부 크롬(상단 띠·층 조작·범례·렌즈 막대·미니맵 안의 보이는 단추·수치)과 캔버스(깃발·아이콘·시도 이름·강 이름표)
NATIONAL_JS = """() => {
  const vis = (e) => { if (!e) return false; const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0 && b.right > 0 && b.bottom > 0 && b.left < innerWidth && b.top < innerHeight; };
  const n = (sel) => [...document.querySelectorAll(sel)].filter(vis).length;
  const a = app;
  return {
    topbar: n('#topbar button') + n('#topbar .brand'),
    layerctl: n('#layerctl button'),
    legend: vis(document.getElementById('legend')) ? 1 : 0,
    lensbar: n('#lensbar > button, #lensbar .grp, #lensbar .lb'),
    minimap: vis(document.getElementById('minimap')) ? 1 : 0,
    chrome_total: 0,
    flags: a.banners.rects.length,
    icons: a.layerR ? a.layerR.placed.length : 0,
    icons_by_kind: a.layerR ? a.layerR.placed.reduce((o, p) => (o[p.it.kind] = (o[p.it.kind] || 0) + 1, o), {}) : {},
    state_labels: a.labels.boxes.length,
    z: a.cam.scale / a.cam.minScale,
  };
}"""

# 도시 패널 첫 화면(스크롤 전 패널 뷰포트 안)에 보이는 내용 단위 수
PANEL_JS = """() => {
  const P = document.getElementById('panel'); const pr = P.getBoundingClientRect();
  const vis = (e) => { for (let x = e; x && x !== P; x = x.parentElement) { if (x.hidden) return false; const cs = getComputedStyle(x); if (cs.display === 'none' || cs.visibility === 'hidden') return false; }
    const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0 && b.bottom > pr.top && b.top < pr.bottom; };
  const SEL = 'h2, h4, .badges > span, .tags > button, .sub, .bignum, .yt, .ptabs [role=tab], svg.chart, .kv > div, .ext, .ranks > div, .rk-row, .peers > *, .ib, details.caveats, .lyg, ul.names li, p.dim, p.note, .fn';
  const els = [...P.querySelectorAll(SEL)].filter(vis);
  const by = {}; for (const e of els) { const k = e.matches('.fn') ? 'ⓘ' : e.matches('.kv > div') ? 'kv칸' : e.matches('.ib') ? '막대행' : e.matches('.yt') ? '산출칸' : e.matches('.ranks > div, .rk-row') ? '순위행' : e.matches('details.caveats') ? '주의서랍' : e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : ''); by[k] = (by[k] || 0) + 1; }
  const rk = [...P.querySelectorAll('h4')].find(h => h.textContent.trim().startsWith('순위'));
  return { visible_units: els.length, by, scrollHeight: P.scrollHeight, clientHeight: P.clientHeight,
    caveats_total: P.querySelectorAll('details.caveats').length, fn_total: P.querySelectorAll('.fn').length,
    ranks_visible: !!(rk && vis(rk)), ranks_top: rk ? Math.round(rk.getBoundingClientRect().top - pr.top) : null };
}"""


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
    pg.wait_for_timeout(1200)


def shot(pg, name, **kw):
    pg.screenshot(path=os.path.join(SHOT, name), **kw)
    print("찍음", name, flush=True)


def national(pg):
    d = pg.evaluate(NATIONAL_JS)
    d["chrome_total"] = d["topbar"] + d["layerctl"] + d["legend"] + d["lensbar"] + d["minimap"]
    return d


def flag_click(pg, name):
    xy = pg.evaluate("""(n) => { const b = app.banners.rects.find(r => r.c.name === n); return b ? [b.x + b.w / 2, b.y + 9] : null; }""", name)
    if xy:
        pg.mouse.click(*xy)
    else:  # 깃발이 화면에 없으면 찾기로
        pg.keyboard.press("/")
        pg.keyboard.type(name)
        pg.wait_for_timeout(200)
        pg.keyboard.press("Enter")
    pg.wait_for_timeout(700)


def before():
    srv, url = serve()
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for (w, h) in ((1280, 800), (390, 844)):
            ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
            pg = ctx.new_page()
            ready(pg, url)
            out[f"national_{w}"] = national(pg)
            shot(pg, f"7b_before_national_{w}.png")
            if w == 1280:
                flag_click(pg, "울산")
                out["city_ulsan_1280"] = pg.evaluate(PANEL_JS)
                shot(pg, "7b_before_city_ulsan_1280.png")
            ctx.close()
        b.close()
    srv.shutdown()
    json.dump(out, open(os.path.join(SHOT, "7b_counts_before.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


def open_city(pg, name):
    pg.keyboard.press("Escape")
    pg.keyboard.press("/")
    pg.wait_for_timeout(150)
    pg.keyboard.type(name)
    pg.wait_for_timeout(250)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(800)


def panel_clip(pg):
    b = pg.locator("#panel").bounding_box()
    return {"x": b["x"] - 4, "y": b["y"] - 4, "width": b["width"] + 8, "height": b["height"] + 8}


def after():
    srv, url = serve()
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for (w, h) in ((1280, 800), (390, 844)):
            ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, accept_downloads=True)
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            ready(pg, url)
            out[f"national_{w}"] = national(pg)
            shot(pg, f"7b_after_national_{w}.png")
            if w == 1280:
                flag_click(pg, "울산")
                out["city_ulsan_1280"] = pg.evaluate(PANEL_JS)
                shot(pg, "7b_ulsan_overview_1280.png")
                for t in ("econ", "infra", "land"):
                    pg.click(f'#panel [data-ptab="{t}"]')
                    pg.wait_for_timeout(250)
                    shot(pg, f"7b_ulsan_{t}_1280.png")
                pg.click('#panel [data-ptab="overview"]')
                # 작은 군, 값 없는 칸: 옹진군 (아파트 매매 자료 없음) 경제 탭, 군위군 땅·행정 탭 (보훈 자료 없음)
                open_city(pg, "옹진군")
                pg.click('#panel [data-ptab="econ"]')
                pg.wait_for_timeout(200)
                kv = pg.locator("#panel .kv.econ").first
                kv.scroll_into_view_if_needed()
                pg.wait_for_timeout(200)
                shot(pg, "7b_gun_ongjin_missing_econ.png", clip=panel_clip(pg))
                pg.click('#panel [data-ptab="overview"]')
                pg.wait_for_timeout(200)
                pg.locator('#panel .rk-row.disabled, #panel .rk-row[data-rk="export"]').first.scroll_into_view_if_needed()
                shot(pg, "7b_gun_ongjin_overview.png", clip=panel_clip(pg))
                # 전국 기준 대비와 순위 막대: 화성시, 인구 행 펼침
                open_city(pg, "화성시")
                pg.click('#panel .rk-row[data-rk="gdp_per_capita"]')
                pg.wait_for_timeout(200)
                pg.locator('#panel .rk-list').scroll_into_view_if_needed()
                shot(pg, "7b_hwaseong_gauges_refs.png", clip=panel_clip(pg))
                pg.locator('#panel .peers').scroll_into_view_if_needed()
                pg.wait_for_timeout(150)
                shot(pg, "7b_hwaseong_peers.png", clip=panel_clip(pg))
                pg.click('#panel [data-ptab="econ"]')
                pg.wait_for_timeout(200)
                shot(pg, "7b_hwaseong_econ_lq.png", clip=panel_clip(pg))
                pg.click('#panel [data-ptab="overview"]')
                # 특성 표시 말풍선: 울진군 (소규모 주석), 세종 (연도 주석)
                for nm, fn in (("울진군", "7b_tag_uljin_popup.png"), ("세종", "7b_tag_sejong_popup.png")):
                    open_city(pg, nm)
                    pg.locator("#panel .ctag").first.click()
                    pg.wait_for_timeout(200)
                    shot(pg, fn)
                    pg.keyboard.press("Escape")
                # 서울 생산 칸 말풍선 (부분 합 문구)
                open_city(pg, "서울")
                pg.locator("#panel .yields .yt").nth(1).click()
                pg.wait_for_timeout(200)
                shot(pg, "7b_seoul_production_tile.png")
                pg.keyboard.press("Escape")
                # 공유 그림: 전국 지형 정사각, 최대 산업 정사각·와이드, 전남광주 정사각 (제목·기준 겹침 확인)
                for hs, fn, act in (("#", "7b_png_square_terrain.png", "png-square"), ("#lens=top_industry", "7b_png_square_top_industry.png", "png-square"),
                                    ("#lens=top_industry", "7b_png_wide_top_industry.png", "png"), ("#state=12&lens=extinction", "7b_png_square_jeonnam.png", "png-square")):
                    pg.goto("about:blank")
                    ready(pg, url + hs)
                    pg.click("#share-btn")
                    with pg.expect_download() as dl:
                        pg.click(f'#sharemenu [data-act="{act}"]')
                    dl.value.save_as(os.path.join(SHOT, fn))
                    out[fn] = pg.evaluate("({legend: app.share.last.legend.length, screen: document.querySelectorAll('#legend .steps li').length, titleRight: app.share.last.titleRight, rightLeft: app.share.last.rightLeft, credits: app.share.last.credits.length})")
                    print("저장", fn, out[fn], flush=True)
                # 찾기 빈 입력: 데이터 기준 시점 6선
                pg.goto("about:blank")
                ready(pg, url)
                pg.keyboard.press("/")
                pg.wait_for_timeout(300)
                shot(pg, "7b_search_presets.png")
                pg.keyboard.press("Escape")
                # 도움말 (시점 6선 포함)
                pg.click("#help-btn")
                pg.wait_for_timeout(200)
                shot(pg, "7b_help.png")
            else:
                open_city(pg, "울산")
                out["city_ulsan_390"] = pg.evaluate(PANEL_JS)
                shot(pg, "7b_mobile_panel_ulsan_390.png")
                pg.click('#panel [data-ptab="econ"]')
                pg.wait_for_timeout(200)
                shot(pg, "7b_mobile_panel_ulsan_econ_390.png")
            out[f"errors_{w}"] = errs
            ctx.close()
        b.close()
    srv.shutdown()
    json.dump(out, open(os.path.join(SHOT, "7b_counts_after.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k.startswith(("national", "city", "errors"))}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if sys.argv[1:] == ["before"]:
        before()
    else:
        after()
