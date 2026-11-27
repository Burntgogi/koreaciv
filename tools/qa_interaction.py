"""6단계 A2: 실제 입력 이벤트(page.mouse · touchscreen · keyboard · CDP 터치)로 조작을 확인하고 docs/QA_INTERACTION.md 에 표를 남긴다.

실행: python tools/qa_interaction.py            (Chromium·Firefox·WebKit 모두)
      python tools/qa_interaction.py chromium   (하나만)

- 사이트(site/)를 이 스크립트가 빈 포트에 직접 띄운다.
- 조작은 모두 실제 입력 이벤트로 한다. evaluate 는 상태를 읽는 데만 쓴다(좌표 찾기, 패널 종류·카메라 값 확인).
- 결과: 통과 / 실패 / 확인 못 함 (이유를 비고에 적는다).
"""
import functools
import http.server
import io
import json
import os
import sys
import threading
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
# 빌드 판 (site/data/sources.json profile): 공개판에는 아파트 매매·전세가 없다 — 그 자리를 보는 검사는 '없음'을 확인한다
PROFILE = (json.load(open(os.path.join(SITE, "data", "sources.json"), encoding="utf-8")).get("profile") or {}).get("profile", "full")
PUBLIC = PROFILE == "public"
OUT = os.path.join(ROOT, "docs", "QA_INTERACTION.md")
WIDTHS = [(390, 844), (768, 1024), (1280, 800), (1920, 1080)]

results = []


def rec(item, browser, width, ok, note=""):
    st = "통과" if ok is True else "실패" if ok is False else "확인 못 함"
    results.append((item, browser, width, st, note))
    print(f"[{st}] {browser} {width} — {item}" + (f" — {note}" if note else ""), flush=True)


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
    pg.wait_for_timeout(900)


def S(pg, js, arg=None):
    """상태 읽기 (조작이 아님)"""
    return pg.evaluate(js, arg)


def cam(pg):
    return S(pg, "({x: app.cam.x, y: app.cam.y, s: app.cam.scale, min: app.cam.minScale})")


def mode(pg):
    return S(pg, "app.panel.mode")


def flag_pos(pg, name):
    return S(pg, """(n) => { const b = app.banners.rects.find(r => r.c.name === n); if (!b) return null;
      const x = b.x + b.w / 2, y = b.y + 9; const el = document.elementFromPoint(x, y); return el && el.id === 'map' ? [x, y] : null; }""", name)


def free_land(pg, avoid_panel=True):
    """깃발·아이콘·선·이름표가 없고 화면 조작부에 덮이지 않은 육지 칸의 화면 좌표와 시도 코드"""
    return S(pg, """() => { const a = app, G = a.grid, W = a.world, v = a.cam.view(); const out = [];
      for (let i = 0; i < G.n; i += 7) { if (W.owner[i] < 0) continue; const cx = G.cx[i], cy = G.cy[i];
        if (cx < v.x0 || cx > v.x1 || cy < v.y0 || cy > v.y1) continue; const [x, y] = a.cam.toScreen(cx, cy);
        if (x < 30 || y < 30 || x > a.cam.vw - 30 || y > a.cam.vh - 30) continue;
        if (a.banners.hit(x, y) || a.layerR.hit(x, y) || a.layerR.hit(x, y, true) || a.layerR.hitRoute(x, y) || a.labels.hit(x, y)) continue;
        let clear = true; for (const [dx, dy] of [[0,0],[8,0],[-8,0],[0,8],[0,-8]]) { const el = document.elementFromPoint(x + dx, y + dy); if (!el || el.id !== 'map') clear = false; }
        if (!clear) continue; if (a.layerR.hit(x + 6, y) || a.layerR.hit(x - 6, y) || a.banners.hit(x, y - 8)) continue;
        if (G.pointToCell(...a.cam.toWorld(x, y)) !== i) continue;
        out.push([x, y, W.states[W.owner[i]].code, i]); }
      return out.length ? out[Math.floor(out.length / 2)] : null; }""")


def icon_pos(pg, kinds=None):
    return S(pg, """(ks) => { const a = app; for (const p of a.layerR.placed) { if (ks && !ks.includes(p.it.kind)) continue;
        if (p.it.kind === 'station') continue; const el = document.elementFromPoint(p.x, p.y); if (!el || el.id !== 'map') continue;
        if (a.banners.hit(p.x, p.y)) continue; const h = a.layerR.hit(p.x, p.y); if (!h || h.it.id !== p.it.id) continue;
        return [p.x, p.y, p.it.id, p.it.name]; } return null; }""", kinds)


def rects(pg):
    return S(pg, """() => { const r = (sel) => { const el = document.querySelector(sel); if (!el) return null; const cs = getComputedStyle(el);
        if (el.hidden || cs.display === 'none' || cs.visibility === 'hidden') return null; const b = el.getBoundingClientRect();
        if (b.width === 0 || b.height === 0) return null; return {x0: b.left, y0: b.top, x1: b.right, y1: b.bottom}; };
      return {topbar: r('#topbar'), lensbar: r('#lensbar'), layerctl: r('#layerctl'), legend: r('#legend'), panel: r('#panel'), minimap: r('#minimap'),
              vw: innerWidth, vh: innerHeight}; }""")


def overlap(a, b):
    if not a or not b:
        return False
    return a["x0"] < b["x1"] - 1 and a["x1"] > b["x0"] + 1 and a["y0"] < b["y1"] - 1 and a["y1"] > b["y0"] + 1


def reachable(pg, sel):
    """조작부 가운데 점의 맨 위 요소가 그 조작부 안인지 (가려지지 않았는지)"""
    return S(pg, """(s) => { const el = document.querySelector(s); if (!el) return false; const b = el.getBoundingClientRect();
      if (b.right <= 0 || b.bottom <= 0 || b.left >= innerWidth || b.top >= innerHeight) return false;
      const x = Math.min(innerWidth - 1, Math.max(0, b.left + b.width / 2)), y = Math.min(innerHeight - 1, Math.max(0, b.top + b.height / 2));
      const t = document.elementFromPoint(x, y); return !!t && el.contains(t); }""", sel)


def pick_lens(pg, group, lens, tap=False):
    """렌즈 막대에서 묶음을 (닫혀 있으면) 눌러 펼치고 렌즈를 누른다"""
    if S(pg, "app.lensbar.openGroup") != group:
        (pg.locator(f'#lensbar [data-group="{group}"]').tap() if tap else pg.click(f'#lensbar [data-group="{group}"]'))
    (pg.locator(f'#lensbar [data-lens="{lens}"]').tap() if tap else pg.click(f'#lensbar [data-lens="{lens}"]'))
    pg.wait_for_timeout(300)


def center(pg, sel):
    b = pg.locator(sel).first.bounding_box()
    return (b["x"] + b["width"] / 2, b["y"] + b["height"] / 2) if b else None


# ---------------------------------------------------------------- 마우스
def mouse_suite(pg, url, br, wlabel):
    ready(pg, url)
    # 깃발 클릭 -> 도시 패널
    p = flag_pos(pg, "서울")
    if p:
        pg.mouse.click(*p)
        pg.wait_for_timeout(300)
        ok = mode(pg) == "city" and "서울" in pg.inner_text("#panel h2")
        rec("마우스: 도시 깃발 클릭 → 도시 패널", br, wlabel, ok, f"서울 깃발 ({p[0]:.0f},{p[1]:.0f}), 패널 {mode(pg)}")
    else:
        rec("마우스: 도시 깃발 클릭 → 도시 패널", br, wlabel, None, "서울 깃발이 가려지지 않은 자리를 찾지 못함")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    # 빈 땅 클릭 -> 시도 패널
    q = free_land(pg)
    if q:
        pg.mouse.click(q[0], q[1])
        pg.wait_for_timeout(300)
        sel = S(pg, "app.selState")
        rec("마우스: 빈 땅 클릭 → 시도 패널", br, wlabel, mode(pg) == "state" and sel == q[2], f"칸 {q[3]} ({q[0]:.0f},{q[1]:.0f}) 시도 {q[2]} → 패널 {mode(pg)} {sel}")
    else:
        rec("마우스: 빈 땅 클릭 → 시도 패널", br, wlabel, None, "빈 땅 자리를 찾지 못함")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    # 아이콘 클릭 -> 항목 패널
    ic = icon_pos(pg)
    if ic:
        pg.mouse.click(ic[0], ic[1])
        pg.wait_for_timeout(300)
        rec("마우스: 아이콘 클릭 → 항목 패널", br, wlabel, mode(pg) == "item" and S(pg, "app.selItem && app.selItem.id") == ic[2], f"{ic[3]} → 패널 {mode(pg)}")
    else:
        rec("마우스: 아이콘 클릭 → 항목 패널", br, wlabel, None, "가려지지 않은 아이콘을 찾지 못함")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    # 호버 툴팁: 땅·아이콘·깃발
    def tip():
        return S(pg, "(() => { const t = document.getElementById('tooltip'); return t.hidden ? null : t.innerText; })()")
    pg.mouse.move(5, pg.viewport_size["height"] / 2)
    q = free_land(pg)
    if q:
        pg.mouse.move(q[0] - 3, q[1] - 3)
        pg.mouse.move(q[0], q[1], steps=3)
        pg.wait_for_timeout(120)
        t = tip()
        sname = S(pg, "(c) => app.stateByCode.get(c).name", q[2])
        rec("마우스: 땅 위 호버 → 툴팁", br, wlabel, bool(t) and sname in t, (t or "툴팁 없음").split("\n")[0])
    ic = icon_pos(pg)
    if ic:
        pg.mouse.move(ic[0] - 2, ic[1] - 2)
        pg.mouse.move(ic[0], ic[1], steps=2)
        pg.wait_for_timeout(120)
        t = tip()
        rec("마우스: 아이콘 호버 → 툴팁", br, wlabel, bool(t) and ic[3] in t, (t or "툴팁 없음").split("\n")[0])
    p = flag_pos(pg, "부산") or flag_pos(pg, "서울")
    if p:
        pg.mouse.move(p[0] - 2, p[1])
        pg.mouse.move(p[0], p[1], steps=2)
        pg.wait_for_timeout(120)
        t = tip()
        rec("마우스: 깃발 호버 → 툴팁", br, wlabel, bool(t) and ("부산" in t or "서울" in t), (t or "툴팁 없음").split("\n")[0])
    # 끌어서 이동
    c0 = cam(pg)
    q = free_land(pg)
    x0, y0 = (q[0], q[1]) if q else (pg.viewport_size["width"] / 2, pg.viewport_size["height"] / 2)
    pg.mouse.move(x0, y0)
    pg.mouse.down()
    pg.mouse.move(x0 + 140, y0 + 70, steps=8)
    pg.mouse.up()
    pg.wait_for_timeout(250)
    c1 = cam(pg)
    dxs, dys = (c0["x"] - c1["x"]) * c1["s"], (c0["y"] - c1["y"]) * c1["s"]
    rec("마우스: 끌어서 이동", br, wlabel, abs(dxs - 140) < 12 and abs(dys - 70) < 12 and mode(pg) is None,
        f"화면 이동 ({dxs:.0f},{dys:.0f}) px (기대 140,70), 끈 뒤 패널 {mode(pg)}")
    # 휠 확대
    c0 = cam(pg)
    pg.mouse.move(pg.viewport_size["width"] / 2, pg.viewport_size["height"] / 2)
    pg.mouse.wheel(0, -300)
    pg.wait_for_timeout(400)
    c1 = cam(pg)
    rec("마우스: 휠 확대", br, wlabel, c1["s"] > c0["s"] * 1.15, f"배율 {c0['s']:.4f} → {c1['s']:.4f}")
    # 더블클릭 확대
    c0 = cam(pg)
    q = free_land(pg)
    if q:
        pg.mouse.dblclick(q[0], q[1])
        pg.wait_for_timeout(700)
        c1 = cam(pg)
        rec("마우스: 더블클릭 확대", br, wlabel, c1["s"] > c0["s"] * 1.6 or abs(c1["s"] - S(pg, "app.cam.maxScale")) < 1e-6, f"배율 {c0['s']:.4f} → {c1['s']:.4f}")
    else:
        rec("마우스: 더블클릭 확대", br, wlabel, None, "빈 땅 자리를 찾지 못함")
    pg.keyboard.press("Escape")
    # 미니맵 클릭·끌기
    vis = S(pg, "getComputedStyle(document.getElementById('minimap')).display !== 'none'")
    if vis:
        bb = pg.locator("#minimap canvas").bounding_box()
        f = S(pg, "app.focus")
        tx, ty = bb["x"] + bb["width"] * 0.35, bb["y"] + bb["height"] * 0.4
        pg.mouse.click(tx, ty)
        pg.wait_for_timeout(200)
        c1 = cam(pg)
        ex, ey = f["x0"] + 0.35 * (f["x1"] - f["x0"]), f["y0"] + 0.4 * (f["y1"] - f["y0"])
        rec("마우스: 미니맵 클릭 → 그곳으로", br, wlabel, abs(c1["x"] - ex) < 40 and abs(c1["y"] - ey) < 40, f"카메라 ({c1['x']:.0f},{c1['y']:.0f}) / 기대 ({ex:.0f},{ey:.0f})")
        pg.mouse.move(tx, ty)
        pg.mouse.down()
        pg.mouse.move(bb["x"] + bb["width"] * 0.6, bb["y"] + bb["height"] * 0.7, steps=6)
        pg.mouse.up()
        pg.wait_for_timeout(200)
        c2 = cam(pg)
        ex, ey = f["x0"] + 0.6 * (f["x1"] - f["x0"]), f["y0"] + 0.7 * (f["y1"] - f["y0"])
        rec("마우스: 미니맵 끌기", br, wlabel, abs(c2["x"] - ex) < 40 and abs(c2["y"] - ey) < 40, f"카메라 ({c2['x']:.0f},{c2['y']:.0f}) / 기대 ({ex:.0f},{ey:.0f})")
    else:
        rec("마우스: 미니맵 클릭·끌기", br, wlabel, None, "이 폭에서는 미니맵을 숨김")
    # 교역로 선 클릭 (교역 층을 층 조작부에서 켬)
    ready(pg, url)
    pg.click('#layerctl [data-grp="trade"]')
    pg.wait_for_timeout(300)
    pt = S(pg, """() => { const a = app; for (const {r, pts} of a.layerR.routeScreen) { for (const k of [12, 9, 15, 6, 18]) { const [x, y] = pts[k];
        const el = document.elementFromPoint(x, y); if (!el || el.id !== 'map') continue; if (a.banners.hit(x, y) || a.layerR.hit(x, y)) continue;
        const h = a.layerR.hitRoute(x, y); if (h && h.id === r.id) return [x, y, r.id]; } } return null; }""")
    if pt:
        pg.mouse.click(pt[0], pt[1])
        pg.wait_for_timeout(300)
        rec("마우스: 교역로 선 클릭 → 구간 패널", br, wlabel, mode(pg) == "route" and S(pg, "app.selRoute && app.selRoute.id") == pt[2], f"구간 {pt[2]} → 패널 {mode(pg)}")
    else:
        rec("마우스: 교역로 선 클릭 → 구간 패널", br, wlabel, None, "가려지지 않은 선 위 점을 찾지 못함")


# ---------------------------------------------------------------- 단축키·보고서·범례·공유·주석·층 (Chromium 데스크톱)
def open_city_by_search(pg, name):
    pg.keyboard.press("Escape")
    pg.keyboard.press("/")
    pg.wait_for_timeout(150)
    pg.keyboard.type(name)
    pg.wait_for_timeout(250)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(700)


def caveat_checks(pg, br, wlabel):
    """ⓘ 가 값 옆에 붙었는지, 도시 패널의 '기준과 주의' 문장 수가 옮기기 전(tools/qa_caveats_baseline.json)과 같은지"""
    base = json.load(open(os.path.join(ROOT, "tools", "qa_caveats_baseline.json"), encoding="utf-8"))["cities"]
    # 기준 문장(옛 전체판에서 만든 것)을 지금 자료로 옮긴다: 칸 비율 치우침 문장은 두 판 모두 도엽 통계 문장으로 바뀌었다.
    # 공개판은 여기에 더해 아파트 가격 구절·한우 구절이 빠지고 광산 문장이 없어진다
    bias = S(pg, "app.world.cover_meta.bias_note")
    n_ret = S(pg, "app.lenses.retired_values.items.length")

    def tr(t):
        if t.startswith("칸 비율은 "):
            return "칸 비율은 " + bias
        if not PUBLIC:
            return t
        if t.startswith("1인당 GRDP 는 생산지") and " 아파트 가격은" in t:
            return t.split(" 아파트 가격은")[0]
        if t.startswith("한국광해광업공단 국내광산검색"):
            return None
        t = t.replace(" · 한우 (2026-10, 농장 소재지)", "")
        if t.startswith("렌즈 막대를 6묶음으로 줄이며"):
            t = t.replace("뺀 렌즈 12개", f"뺀 렌즈 {n_ret}개")
        return t
    base = {k: {"sentences": sorted({tr(t) for t in v["sentences"]} - {None}), "distinct": len({tr(t) for t in v["sentences"]} - {None})} for k, v in base.items()}
    rows, ok = [], True
    for name, b in base.items():
        open_city_by_search(pg, name)
        d = S(pg, """() => { const lis = [...document.querySelectorAll('#panel details.caveats li')].map(l => l.textContent.replace(/\\s+/g, ' ').trim());
          const fns = [...document.querySelectorAll('#panel .fn')];
          return {h2: document.querySelector('#panel h2') ? document.querySelector('#panel h2').innerText : '', mode: app.panel.mode, sent: [...new Set(lis)].sort(),
            fn: fns.length, val: fns.filter(f => f.closest('[data-k]')).length,
            orphan: fns.filter(f => !document.querySelector(`#panel [data-fnote="${f.dataset.fn}"]`)).length}; }""")
        same = d["sent"] == b["sentences"]
        good = d["mode"] == "city" and name in d["h2"] and len(d["sent"]) == b["distinct"] and d["orphan"] == 0 and d["val"] > 0
        ok = ok and good
        rows.append(f"{name} 문장 {b['distinct']}→{len(d['sent'])}{'' if same else ' (문장 바뀜)'} · ⓘ {d['fn']}개 중 값 옆 {d['val']}" + ("" if d["orphan"] == 0 else f" · 문장 없는 ⓘ {d['orphan']}"))
    rec("패널 ⓘ: 값 옆 표시, 도시 패널 '기준과 주의' 문장 수가 옮기기 전과 같음 (서울·울산·인천·세종·울릉군, 찾기로 열기)", br, wlabel, ok, "; ".join(rows))
    # 값 옆 ⓘ 를 마우스로 누르면 그 값의 문장이 고정되어 나온다
    open_city_by_search(pg, "서울")
    pg.click('#panel [data-ptab="infra"]')  # 7b: 수출입은 '시설·교역' 탭
    fn = pg.locator('#panel [data-k="trade-import"] .fn').last
    fn.scroll_into_view_if_needed()
    fn.click()
    pg.wait_for_timeout(150)
    t = S(pg, "document.getElementById('fnpop').hidden ? '' : document.getElementById('fnpop').innerText")
    pinned = S(pg, "document.getElementById('fnpop').classList.contains('pinned')")
    rec("패널 ⓘ: 수입 값 옆 ⓘ 를 누르면 본사 주소 영향 문장이 고정되어 나옴", br, wlabel, pinned and "본사" in t, t[:60])
    pg.keyboard.press("Escape")
    pg.click('#panel [data-ptab="overview"]')


def marker_checks(pg, url, br, wlabel):
    """전국 배율 원전 5곳이 모두 그려지는지, 중간 배율 서울의 대학 묶음 표지를 누르면 묶음 패널이 열리는지"""
    ready(pg, url)
    n = S(pg, "app.layerR.placed.filter(q => q.it.kind === 'nuclear').length")
    tot = S(pg, "app.layerR.items.filter(i => i.kind === 'nuclear').length")
    z = S(pg, "app.cam.scale / app.cam.minScale")
    rec("층: 전국 배율에서 원전이 모두 그려짐 (깃발에 가려 숨지 않음)", br, wlabel, n == tot == 5, f"z {z:.2f}, 원전 {n}/{tot}")
    mn = S(pg, "app.cam.minScale")
    pg.goto("about:blank")
    ready(pg, url + f"#v=2282,1660,{mn * 2.9:.4f}")
    g = S(pg, """() => { for (const p of app.layerR.placed) { if (!p.it.group) continue; const el = document.elementFromPoint(p.x, p.y);
        if (!el || el.id !== 'map' || app.banners.hit(p.x, p.y)) continue; return [p.x, p.y, p.it.name, p.it.members.length]; } return null; }""")
    if not g:
        rec("층: 중간 배율 서울의 대학 묶음 표지를 누르면 묶음 패널(대학별 연구비)", br, wlabel, False, "누를 수 있는 묶음 표지 없음")
        return
    pg.mouse.click(g[0], g[1])
    pg.wait_for_timeout(300)
    rows = pg.locator("#panel tr[data-item]").count()
    txt = pg.inner_text("#panel") if mode(pg) == "item" else ""
    rec("층: 중간 배율 서울의 대학 묶음 표지를 누르면 묶음 패널(대학별 연구비)", br, wlabel, rows == g[3] and "억원" in txt and "캠퍼스 자리가 아니라" in txt,
        f"z {S(pg, 'app.cam.scale / app.cam.minScale'):.2f}, {g[2]} → 행 {rows}")


def ui_suite(pg, ctx, url, br, wlabel):
    ready(pg, url)
    # 순위 보고서
    pg.click('[data-report="gold"]')
    pg.wait_for_timeout(250)
    op = S(pg, "!document.getElementById('report').hidden")
    rows = pg.locator("#report tr[data-city]").count()
    rec("보고서: 상단 '금' 누르면 보고서가 내려옴", br, wlabel, op and rows == 11, f"열림 {op}, 도시 행 {rows} (상위 8 + 하위 3)")
    pg.click('#report [data-mode="1"]')
    pg.wait_for_timeout(150)
    rec("보고서: 총량 / 1인당 전환", br, wlabel, "1인당" in pg.inner_text("#report .modes .on") and "100,000명 이상" in pg.inner_text("#report .rule"), pg.inner_text("#report .rule").split("\n")[0][:80])
    pg.click('[data-report="population"]')
    pg.wait_for_timeout(200)
    one = S(pg, "document.querySelectorAll('#report').length === 1 && document.querySelector('#report h3').innerText.includes('인구')")
    rec("보고서: 한 번에 하나만 (다른 수치를 누르면 바뀜)", br, wlabel, one)
    name = pg.locator("#report tr[data-city] td").nth(1).inner_text().split(" ")[0]
    pg.locator("#report tr[data-city]").first.click()
    pg.wait_for_timeout(900)
    rec("보고서: 도시 행 클릭 → 이동하고 도시 패널", br, wlabel, mode(pg) == "city" and name in pg.inner_text("#panel h2") and S(pg, "document.getElementById('report').hidden"), f"{name} → {mode(pg)}")
    pg.click('[data-report="over65"]')
    pg.wait_for_timeout(200)
    pg.locator("#report tr[data-state]").first.click()
    pg.wait_for_timeout(900)
    rec("보고서: 시도 행 클릭 → 시도 패널", br, wlabel, mode(pg) == "state")
    pg.click('[data-report="gold"]')
    pg.wait_for_timeout(150)
    pg.click("#report .lensbtn")
    pg.wait_for_timeout(300)
    rec("보고서: '지도에서 보기' → 관련 렌즈", br, wlabel, S(pg, "app.lens && app.lens.id") == "gdp_pc", f"렌즈 {S(pg, 'app.lens && app.lens.id')}")
    pg.click('[data-report="culture"]')
    pg.wait_for_timeout(150)
    q = free_land(pg)
    pg.mouse.click(q[0], q[1]) if q else None
    pg.wait_for_timeout(200)
    rec("보고서: 바깥을 누르면 닫힘", br, wlabel, S(pg, "document.getElementById('report').hidden"))
    # Esc 순서: 도움말 → 찾기 → 연감 → 보고서 → 패널 (실제 입력으로 함께 열 수 있는 짝마다 확인)
    ready(pg, url)
    st = lambda: S(pg, "({help: !document.getElementById('help').hidden, search: !document.getElementById('search').hidden, alm: app.almanac.isOpen(), rep: app.report.isOpen(), panel: app.panel.mode})")  # noqa: E731
    seq = []
    p = flag_pos(pg, "서울")
    pg.mouse.click(*p)
    pg.click('[data-report="population"]')
    pg.wait_for_timeout(100)
    pg.keyboard.press("?")
    seq.append(st())
    for _ in range(3):
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(60)
        seq.append(st())
    exp1 = [dict(help=True, search=False, alm=False, rep=True, panel="city"), dict(help=False, search=False, alm=False, rep=True, panel="city"),
            dict(help=False, search=False, alm=False, rep=False, panel="city"), dict(help=False, search=False, alm=False, rep=False, panel=None)]
    p = flag_pos(pg, "서울")
    pg.mouse.click(*p)
    pg.click("#almanac-btn")
    pg.wait_for_timeout(100)
    a0 = st()
    pg.keyboard.press("Escape")
    a1 = st()
    pg.keyboard.press("/")
    pg.wait_for_timeout(100)
    a2 = st()
    pg.keyboard.press("Escape")
    a3 = st()
    exp2 = [dict(help=False, search=False, alm=True, rep=False, panel="city"), dict(help=False, search=False, alm=False, rep=False, panel="city"),
            dict(help=False, search=True, alm=False, rep=False, panel="city"), dict(help=False, search=False, alm=False, rep=False, panel="city")]
    short = lambda o: ",".join(k if v is True else str(v) for k, v in o.items() if v) or "없음"  # noqa: E731
    rec("단축키: Esc 가 도움말 → 찾기 → 연감 → 보고서 → 패널 순으로 하나씩 닫음", br, wlabel, seq == exp1 and [a0, a1, a2, a3] == exp2,
        "패널+보고서+도움말: " + " / ".join(short(o) for o in seq) + " · 패널+연감, 패널+찾기: " + " / ".join(short(o) for o in [a0, a1, a2, a3])
        + " (연감·찾기는 화면을 덮어 보고서와 함께 열 수 없어 짝으로 확인)")
    pg.keyboard.press("Escape")
    # ? 와 도움말 단추
    pg.keyboard.press("?")
    pg.wait_for_timeout(100)
    a1 = S(pg, "!document.getElementById('help').hidden")
    pg.keyboard.press("Escape")
    pg.click("#help-btn")
    pg.wait_for_timeout(100)
    a2 = S(pg, "!document.getElementById('help').hidden")
    pg.click("#help [data-close]")
    rec("도움말: ? 키와 상단 ? 단추로 열림", br, wlabel, a1 and a2)
    # L / Shift+L, R
    l0 = S(pg, "app.lens && app.lens.id")
    pg.keyboard.press("l")
    l1 = S(pg, "app.lens && app.lens.id")
    pg.keyboard.press("l")
    l2 = S(pg, "app.lens && app.lens.id")
    pg.keyboard.press("Shift+L")
    l3 = S(pg, "app.lens && app.lens.id")
    pg.keyboard.press("Shift+L")
    l4 = S(pg, "app.lens && app.lens.id")
    rec("단축키: L 다음 렌즈, Shift+L 이전 렌즈", br, wlabel, l0 is None and l1 == "density" and l2 == "growth" and l3 == "density" and l4 is None, f"{l0} → {l1} → {l2} → {l3} → {l4}")
    r0 = S(pg, "app.layerOn.resources")
    pg.keyboard.press("r")
    r1 = S(pg, "app.layerOn.resources")
    pg.keyboard.press("r")
    rec("단축키: R 자원 켜고 끄기", br, wlabel, r0 is True and r1 is False and S(pg, "app.layerOn.resources") is True, f"{r0} → {r1} → {S(pg, 'app.layerOn.resources')}")
    # 방향키·WASD, +/-
    moves = []
    for key, dx, dy in (("ArrowLeft", 90, 0), ("d", -90, 0), ("w", 0, 90), ("ArrowDown", 0, -90)):
        c0 = cam(pg)
        pg.keyboard.press(key)
        c1 = cam(pg)
        moves.append(abs((c0["x"] - c1["x"]) * c1["s"] - dx) < 2 and abs((c0["y"] - c1["y"]) * c1["s"] - dy) < 2)
    rec("단축키: 방향키·WASD 이동", br, wlabel, all(moves), str(moves))
    c0 = cam(pg)
    pg.keyboard.press("+")
    pg.wait_for_timeout(400)
    c1 = cam(pg)
    pg.keyboard.press("-")
    pg.wait_for_timeout(400)
    c2 = cam(pg)
    rec("단축키: + / − 확대·축소", br, wlabel, c1["s"] > c0["s"] * 1.4 and c2["s"] < c1["s"] / 1.4, f"{c0['s']:.4f} → {c1['s']:.4f} → {c2['s']:.4f}")
    # / 찾기, 입력란에서는 단축키가 동작하지 않음
    pg.keyboard.press("/")
    pg.wait_for_timeout(100)
    foc = S(pg, "document.activeElement && document.activeElement.closest('#search') !== null")
    lz = S(pg, "app.lens && app.lens.id")
    pg.keyboard.type("lrwasd+")
    pg.wait_for_timeout(100)
    same = S(pg, "app.lens && app.lens.id") == lz and S(pg, "app.layerOn.resources") is True
    rec("단축키: / 로 찾기 열림, 입력란에 초점이 있으면 L·R·WASD·+ 가 동작하지 않음", br, wlabel, foc and same, f"초점 {foc}, 렌즈·층 그대로 {same}")
    pg.keyboard.press("Escape")
    # 범례 구간 (렌즈 막대에서 실제로 렌즈를 고른 뒤)
    pick_lens(pg, "people", "over65")
    bb = pg.locator("#legend .fbar").bounding_box()
    pg.mouse.move(bb["x"] + bb["width"] * 0.5, bb["y"] + bb["height"] / 2, steps=3)
    pg.wait_for_timeout(150)
    f1 = S(pg, "!!app.terrain.filter")
    pg.mouse.down()
    pg.mouse.move(bb["x"] + bb["width"] * 0.9, bb["y"] + bb["height"] / 2, steps=5)
    w = S(pg, "parseFloat(document.querySelector('#legend .selr').style.width)")
    pg.mouse.up()
    pg.wait_for_timeout(100)
    f2 = S(pg, "!!app.terrain.filter")
    pg.mouse.move(bb["x"] + bb["width"] * 0.5, bb["y"] + bb["height"] / 2)
    pg.mouse.move(bb["x"] + bb["width"] * 0.5, bb["y"] - 80, steps=3)
    f3 = S(pg, "!!app.terrain.filter")
    rec("범례: 눈금 위를 가리키면 구간만 색이 남고, 끌면 범위가 넓어지고, 놓거나 벗어나면 풀림", br, wlabel, f1 and w > 30 and not f2 and not f3,
        f"가리킴 {f1}, 끈 범위 폭 {w:.0f}%, 놓은 뒤 {f2}, 벗어난 뒤 {f3}")
    pick_lens(pg, "people", "extinction")
    li = pg.locator("#legend .fsteps li").nth(1)
    li.hover()
    pg.wait_for_timeout(100)
    d1 = S(pg, "!!app.terrain.filter && document.querySelectorAll('#legend .fsteps li.dimmed').length")
    pg.mouse.move(5, 300, steps=3)
    d2 = S(pg, "!!app.terrain.filter")
    rec("범례: 구간 렌즈(소멸위험지수) 단계 위를 가리키면 그 단계만", br, wlabel, bool(d1) and not d2, f"흐린 단계 {d1}, 벗어난 뒤 {d2}")
    # ⓘ 주석
    pg.click('#lensbar [data-lens=""]')
    p = flag_pos(pg, "서울")
    pg.mouse.click(*p)
    pg.wait_for_timeout(300)
    pg.click('#panel [data-ptab="econ"]')  # 7b: 도시 패널 탭 — ⓘ 가 있는 '경제' 탭
    n_fn = pg.locator("#panel .fn").count()
    n_det = pg.locator("#panel details.caveats").count()
    fn = pg.locator("#panel .ptab:not([hidden]) .fn").first
    fn.scroll_into_view_if_needed()
    fn.hover()
    pg.wait_for_timeout(100)
    h1 = S(pg, "!document.getElementById('fnpop').hidden && document.getElementById('fnpop').innerText.length")
    fn.click()
    pg.wait_for_timeout(100)
    h2 = S(pg, "document.getElementById('fnpop').classList.contains('pinned')")
    pg.keyboard.press("Escape")
    h3 = S(pg, "document.getElementById('fnpop').hidden") and mode(pg) == "city"
    det = pg.locator("#panel .ptab:not([hidden]) details.caveats summary").first
    det.click()
    h4 = S(pg, "document.querySelector('#panel .ptab:not([hidden]) details.caveats').open")
    pg.click('#panel [data-ptab="overview"]')
    rec("패널 ⓘ: 가리키면 문장, 누르면 고정, Esc 로 닫힘(패널은 남음), '기준과 주의' 펼침", br, wlabel, bool(h1) and h2 and h3 and h4,
        f"ⓘ {n_fn}개, 기준과 주의 {n_det}곳, 가리킴 {h1}자, 고정 {h2}, Esc {h3}, 펼침 {h4}")
    caveat_checks(pg, br, wlabel)
    marker_checks(pg, url, br, wlabel)
    # 층 조작
    ready(pg, url)
    pg.click('#layerctl [data-grp="wonders"]')
    a1 = S(pg, "app.layerOn.wonders")
    pg.click('#layerctl [data-grp="wonders"]')
    a2 = S(pg, "app.layerOn.wonders")
    pg.click("#layerctl .more")
    pg.wait_for_timeout(100)
    subs = pg.locator("#layerctl .subs input").count()
    pg.click('#layerctl input[data-sub="power"]')
    a3 = S(pg, "app.subOff.has('power')")
    pg.wait_for_timeout(200)
    hsh = S(pg, "location.hash")
    # 세부 수: 공개판은 광산 층이 없어 그 세부를 조작부에 두지 않는다 (18 → 17)
    want_subs = 17 if PUBLIC else 18
    rec(f"층 조작: 접힌 줄의 아이콘으로 묶음 켜고 끄기, 펼쳐서 세부({want_subs}개) 끄기, 링크에 남음", br, wlabel, a1 is False and a2 is True and subs == want_subs and a3 and "hide=power" in hsh,
        f"불가사의 {a1}→{a2}, 세부 {subs}개, 발전소 끔 {a3}, 해시 {hsh[-40:]}")
    # 공유: 링크 복사, PNG
    pg.click("#share-btn")
    pg.click('#sharemenu [data-act="link"]')
    pg.wait_for_timeout(300)
    try:
        clip = S(pg, "navigator.clipboard.readText()")
    except Exception as e:  # noqa: BLE001
        clip = f"읽기 실패 {e}"
    rec("공유: 지금 화면 링크 복사", br, wlabel, isinstance(clip, str) and clip.startswith("http") and "v=" in clip and "hide=power" in clip, clip[:90])
    pg.click("#share-btn")
    with pg.expect_download() as dl:
        pg.click('#sharemenu [data-act="png"]')
    d = dl.value
    path = d.path()
    try:
        from PIL import Image
        im = Image.open(path)
        size = im.size
    except Exception as e:  # noqa: BLE001
        size = str(e)
    rec("공유: PNG 내려받기 1600×900", br, wlabel, size == (1600, 900), f"{d.suggested_filename} {size}")
    # 옛 링크
    pg.goto(url.replace("index.html", "index.html#lens=smoking&off=power,lines&on=routes"))
    pg.wait_for_function("window.app && window.app.layerR", timeout=30000)
    pg.wait_for_timeout(500)
    st = S(pg, "({lens: app.lens && app.lens.id, toast: !document.getElementById('toast').hidden, power: app.subOff.has('power'), lines: app.subOff.has('lines'), trade: app.layerOn.trade})")
    rec("옛 공유 링크: 뺀 렌즈 id → 가까운 렌즈, 옛 층 키 → 새 묶음", br, wlabel, st == {"lens": "health", "toast": True, "power": True, "lines": True, "trade": True}, json.dumps(st, ensure_ascii=False))


# ---------------------------------------------------------------- 터치
def touch_suite(br_obj, url, br):
    ctx = br_obj.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
    pg = ctx.new_page()
    cdp = ctx.new_cdp_session(pg)
    ready(pg, url)
    wl = "390×844 터치"

    def touch(kind, pts):
        cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [{"x": x, "y": y, "id": i} for i, (x, y) in enumerate(pts)]})

    q = free_land(pg)
    c0 = cam(pg)
    x0, y0 = q[0], q[1]
    touch("touchStart", [(x0, y0)])
    for k in range(1, 9):
        touch("touchMove", [(x0 + 10 * k, y0 + 6 * k)])
    touch("touchEnd", [])
    pg.wait_for_timeout(200)
    c1 = cam(pg)
    dxs, dys = (c0["x"] - c1["x"]) * c1["s"], (c0["y"] - c1["y"]) * c1["s"]
    rec("터치: 한 손가락 끌기 → 이동", br, wl, abs(dxs - 80) < 10 and abs(dys - 48) < 10 and mode(pg) is None, f"화면 이동 ({dxs:.0f},{dys:.0f}) px (기대 80,48), 패널 {mode(pg)}")
    c0 = cam(pg)
    cx, cy = 195, 430
    touch("touchStart", [(cx - 30, cy), (cx + 30, cy)])
    for k in range(1, 11):
        touch("touchMove", [(cx - 30 - 8 * k, cy), (cx + 30 + 8 * k, cy)])
    touch("touchEnd", [])
    pg.wait_for_timeout(300)
    c1 = cam(pg)
    rec("터치: 두 손가락 벌리기 → 확대 (CDP 터치)", br, wl, c1["s"] > c0["s"] * 1.8 and mode(pg) is None, f"배율 {c0['s']:.4f} → {c1['s']:.4f} (손가락 간격 60 → 220 px)")
    ready(pg, url)
    p = flag_pos(pg, "서울")
    if p:
        pg.touchscreen.tap(*p)
        pg.wait_for_timeout(400)
        rec("터치: 깃발 탭 → 도시 패널", br, wl, mode(pg) == "city", f"패널 {mode(pg)}")
    else:
        rec("터치: 깃발 탭 → 도시 패널", br, wl, None, "서울 깃발 자리를 찾지 못함")
    pg.locator("#panel .close").tap()
    pg.wait_for_timeout(200)
    q = free_land(pg)
    if q:
        pg.touchscreen.tap(q[0], q[1])
        pg.wait_for_timeout(400)
        rec("터치: 빈 땅 탭 → 시도 패널", br, wl, mode(pg) == "state" and S(pg, "app.selState") == q[2], f"패널 {mode(pg)}")
    pg.locator("#panel .close").tap()
    pg.wait_for_timeout(200)
    ic = icon_pos(pg)
    if ic:
        pg.touchscreen.tap(ic[0], ic[1])
        pg.wait_for_timeout(400)
        rec("터치: 아이콘 탭 → 항목 패널", br, wl, mode(pg) == "item", f"{ic[3]} → {mode(pg)}")
        pg.locator("#panel .close").tap()
    # 범례(접힘) 탭 → 펼침, 구간 탭 → 남음, 두 번 탭 → 풀림
    pick_lens(pg, "people", "over65", tap=True)
    pg.locator("#legend h5").tap()
    pg.wait_for_timeout(150)
    op = S(pg, "document.getElementById('legend').classList.contains('open')")
    bb = pg.locator("#legend .fbar").bounding_box()
    if op and bb:
        pg.touchscreen.tap(bb["x"] + bb["width"] * 0.3, bb["y"] + bb["height"] / 2)
        pg.wait_for_timeout(500)
        f1 = S(pg, "!!app.terrain.filter")
        pg.touchscreen.tap(bb["x"] + bb["width"] * 0.3, bb["y"] + bb["height"] / 2)
        pg.wait_for_timeout(60)
        pg.touchscreen.tap(bb["x"] + bb["width"] * 0.3, bb["y"] + bb["height"] / 2)
        pg.wait_for_timeout(200)
        f2 = S(pg, "!!app.terrain.filter")
        rec("터치: 범례 탭 → 구간이 남고, 두 번 탭 → 풀림", br, wl, f1 and not f2, f"탭 뒤 {f1}, 두 번 탭 뒤 {f2}")
    else:
        rec("터치: 범례 탭 → 구간이 남고, 두 번 탭 → 풀림", br, wl, False, f"범례 펼침 {op}")
    ctx.close()


# ---------------------------------------------------------------- 폭별 배치
def layout_suite(br_obj, url, br):
    for w, h in WIDTHS:
        wl = f"{w}×{h}"
        ctx = br_obj.new_context(viewport={"width": w, "height": h})
        pg = ctx.new_page()
        ready(pg, url)
        R = rects(pg)
        names = ["topbar", "lensbar", "layerctl", "legend", "minimap"]
        bad = [f"{a}×{b}" for i, a in enumerate(names) for b in names[i + 1:] if overlap(R[a], R[b])]
        inside = [n for n in names if R[n] and (R[n]["x0"] < -1 or R[n]["y0"] < -1 or R[n]["x1"] > R["vw"] + 1 or R[n]["y1"] > R["vh"] + 1)]
        reach = {s: reachable(pg, s) for s in ("#topbar .brand", '#topbar [data-report="population"]', "#search-btn", "#help-btn", "#share-btn",
                                                '#layerctl [data-grp="wonders"]', "#layerctl .more", '#lensbar [data-lens=""]', "#legend h5")}
        rec("폭: 상단 막대·렌즈 막대·층 조작부·범례·미니맵이 겹치지 않고 화면 안", br, wl, not bad and not inside, (f"겹침 {bad}" if bad else "겹침 없음") + (f", 화면 밖 {inside}" if inside else ""))
        rec("폭: 조작부 단추가 가려지지 않음 (가운데 점의 맨 위 요소)", br, wl, all(reach.values()), ", ".join(k for k, v in reach.items() if not v) or "모두 닿음")
        # 렌즈 막대의 마지막 묶음까지 닿는지 (넘치면 가로 휠로 밀어서)
        last = '#lensbar [data-group="land"]'
        wheeled = not reachable(pg, last)
        if wheeled:
            bb = pg.locator("#lensbar").bounding_box()
            pg.mouse.move(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2)
            pg.mouse.wheel(600, 0)
            pg.wait_for_timeout(200)
        ok = reachable(pg, last)
        if ok:
            pg.click(last)
            pg.wait_for_timeout(100)
        rec("폭: 렌즈 막대 마지막 묶음(땅)까지 닿고 누르면 펼쳐짐", br, wl, ok and S(pg, "app.lensbar.openGroup") == "land", ("가로 휠로 밀어 닿음" if wheeled else "밀지 않아도 보임") if ok else "닿지 못함")
        # 패널을 열었을 때
        pg.click('#lensbar [data-group="land"]') if ok else None
        p = flag_pos(pg, "서울") or flag_pos(pg, "부산")
        if p:
            pg.mouse.click(*p)
            pg.wait_for_timeout(400)
            R2 = rects(pg)
            bad2 = [n for n in ("topbar", "lensbar", "layerctl", "legend", "minimap") if overlap(R2["panel"], R2[n])]
            close_ok = reachable(pg, "#panel .close")
            top_ok = reachable(pg, '#topbar [data-report="population"]')
            rec("폭: 패널을 열면 다른 조작부와 겹치지 않고 닫기·상단 막대에 닿음", br, wl, not bad2 and close_ok and top_ok,
                (f"겹침 {bad2}" if bad2 else "겹침 없음") + f", 닫기 {close_ok}, 상단 {top_ok}")
            pg.click("#panel .close")
        # 보고서·층 세부를 열었을 때
        pg.click('#topbar [data-report="population"]')
        pg.wait_for_timeout(200)
        rb = S(pg, "(() => { const b = document.getElementById('report').getBoundingClientRect(); return {x0: b.left, y0: b.top, x1: b.right, y1: b.bottom}; })()")
        rec("폭: 보고서가 상단 막대 아래로 화면 안에 열림", br, wl, rb["y0"] >= R["topbar"]["y1"] - 1 and rb["x0"] >= 0 and rb["x1"] <= w and rb["y1"] <= h and reachable(pg, "#report .x"),
            f"보고서 {rb['x0']:.0f},{rb['y0']:.0f}–{rb['x1']:.0f},{rb['y1']:.0f}")
        pg.keyboard.press("Escape")
        ctx.close()


# ---------------------------------------------------------------- 감사 대응 회귀 (docs/AUDIT_RESPONSE.md)
def audit_suite(br_obj, url, br):
    """독립 감사(docs/AUDIT_CODEX.md)가 권한 회귀 사례: 개편 구 툴팁, PNG 범례·출처, 부분 로드, 보고서 행 Enter, 같은 탭 해시, 동작 줄이기, 좁은 폭 보고서 메뉴."""
    wl = "1280×800"
    ctx = br_obj.new_context(viewport={"width": 1280, "height": 800}, accept_downloads=True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    ready(pg, url)
    # 01: 합계출산율 렌즈에서 화성시 만세구 칸을 가리키면 '개편 전 화성시 전체 값'
    i = S(pg, "(() => { const w = app.world, k = w.counties.findIndex(c => c.name.endsWith('만세구')); const cs = []; for (let i = 0; i < w.owner.length; i++) if (w.county[i] === k) cs.push(i); return cs[Math.floor(cs.length / 2)]; })()")
    cx, cy, ms = S(pg, f"[app.grid.cx[{i}], app.grid.cy[{i}], app.cam.minScale]")
    pg.goto(url + f"#v={round(cx)},{round(cy)},{ms * 4:.4f}&lens=fertility")
    pg.wait_for_timeout(700)
    xy = S(pg, f"(() => {{ const r = app.canvas.getBoundingClientRect(); const [x, y] = app.cam.toScreen(app.grid.cx[{i}], app.grid.cy[{i}]); return [x + r.left, y + r.top]; }})()")
    pg.mouse.move(xy[0] + 3, xy[1] + 3)
    pg.mouse.move(xy[0], xy[1])
    pg.wait_for_timeout(300)
    tip = S(pg, "document.getElementById('tooltip').innerText")
    rec("감사 01: 개편 구(화성시 만세구)의 합계출산율 툴팁에 '개편 전 화성시 전체 값'", br, wl, "개편 전 화성시 전체 값" in tip and "만세구" in tip, tip.replace("\n", " / ")[-120:])
    # 03·12: 최대 산업 렌즈 PNG — 범례 항목이 화면 범례와 같고, 출처 줄에 행정경계·OSM·토지피복·렌즈 출처와 이용조건 경고, 그림 안에 글자 픽셀
    pg.goto(url + "#lens=top_industry")
    pg.wait_for_timeout(600)
    pg.click("#share-btn")
    with pg.expect_download() as dl:
        pg.click('#sharemenu [data-act="png"]')
    path = dl.value.path()
    last = S(pg, "app.share.last")
    screen = S(pg, "[...document.querySelectorAll('#legend .steps li')].map(e => e.textContent.trim())")
    cr = " ".join(last["credits"])
    # 두 판 공용: 토지피복은 기후에너지환경부 세분류 토지피복지도 도엽 통계(공공누리 제1유형)이고 WMS 이용조건 경고가 없다
    need = ["OpenStreetMap", "ODbL", "admdongkor", "기후에너지환경부", "렌즈 ‘최대 산업’"]
    miss = [n for n in need if n not in cr]
    miss += [f"(없어야 함) {n}" for n in ("⚠", "WMS") if n in cr]
    px = 0
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        size = im.size
        y0 = 900 - last["band"]
        for y in range(y0 + 100, 900, 2):
            for x in range(28, 1572, 3):
                r, g, b = im.getpixel((x, y))
                if (abs(r - 179) < 40 and abs(g - 171) < 40 and abs(b - 152) < 40) or (r > 200 and 150 < g < 210 and b < 140):
                    px += 1
    except Exception as e:  # noqa: BLE001
        size = str(e)
    rec("감사 03·12: PNG 범례 = 화면 범례(범주 전부), 출처 줄에 OSM·행정경계·토지피복·렌즈 출처·이용조건, 그림의 출처 띠에 글자", br, wl,
        size == (1600, 900) and last["legend"] == screen and not miss and px > 500,
        f"범례 {len(last['legend'])}/{len(screen)}, 출처 줄 {len(last['credits'])}줄, 빠진 표기 {miss}, 출처 띠 글자 픽셀 {px}, {size}")
    # 10: 보고서 행에 Tab 으로 초점을 두고 Enter → 시도 패널, 초점이 패널로
    pg.goto(url + "#")
    pg.wait_for_timeout(400)
    pg.click('#topbar [data-report="population"]')
    pg.wait_for_timeout(200)
    hit = False
    for _ in range(40):
        pg.keyboard.press("Tab")
        if S(pg, "!!(document.activeElement && document.activeElement.matches && document.activeElement.matches('#report tr[data-state]'))"):
            hit = True
            break
    code = S(pg, "document.activeElement.dataset ? document.activeElement.dataset.state : null") if hit else None
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(500)
    st = S(pg, "({mode: app.panel.mode, sel: app.selState, rep: document.getElementById('report').hidden, inPanel: document.getElementById('panel').contains(document.activeElement)})")
    rec("감사 10: 보고서 시도 행에 Tab 초점 → Enter 로 시도 패널, 초점이 패널로", br, wl, hit and st["mode"] == "state" and st["sel"] == code and st["rep"] and st["inPanel"], json.dumps(st, ensure_ascii=False))
    # 11: 같은 탭에서 #city=0 → #lens=health 로 바꾸면 도시 선택이 남지 않음, 빈 city·없는 item·report=0
    pg.goto(url + "#city=0")
    pg.wait_for_timeout(400)
    a1 = S(pg, "app.selCity")
    pg.goto(url + "#lens=health")
    pg.wait_for_timeout(500)
    a2 = S(pg, "({city: app.selCity, mode: app.panel.mode, lens: app.lens && app.lens.id, hash: location.hash})")
    res = {}
    for h in ("#city=", "#item=unknown&city=9", "#report=0"):
        pg.goto(url.replace("index.html", "index.html?x=" + str(len(res))) + h)
        pg.wait_for_function("window.app && window.app.layerR", timeout=30000)
        pg.wait_for_timeout(300)
        res[h] = S(pg, "({city: app.selCity, mode: app.panel.mode})")
    ok11 = (a1 == 0 and a2["city"] is None and a2["mode"] is None and a2["lens"] == "health" and "city=" not in a2["hash"]
            and res["#city="]["city"] is None and res["#item=unknown&city=9"]["city"] == 9 and res["#report=0"]["mode"] != "nation")
    rec("감사 11: 같은 탭 해시 교체 시 이전 도시 선택이 남지 않음, 빈 city 무시, 없는 item 이면 유효한 city, report=0 은 전국 패널 아님", br, wl, ok11,
        json.dumps({"same_tab": a2, **res}, ensure_ascii=False)[:300])
    rec("감사 회귀 시험 동안 페이지 오류 없음", br, wl, not errs, "; ".join(errs[:3]))
    ctx.close()
    # 08: trade.json 이 404 여도 공항·국립공원 층은 있고, 패널은 '불러오지 못했습니다', 다시 시도하면 채워짐
    ctx = br_obj.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    block = {"on": True}

    def handler(route):
        if block["on"]:
            route.fulfill(status=404, body="not found")
        else:
            route.continue_()
    pg.route("**/data/trade.json", handler)
    ready(pg, url)
    s1 = S(pg, "({air: app.layerR.items.some(i => i.kind === 'airport'), park: app.layerR.items.some(i => i.kind === 'national_park'), trade: !!app.layers.trade, warn: !document.getElementById('loadwarn').hidden && document.getElementById('loadwarn').innerText})")
    open_city_by_search(pg, "서울")
    pg.click('#panel [data-ptab="infra"]')  # 7b: 수출입은 '시설·교역' 탭 (다시 불러와도 탭이 남는지도 아래에서 본다)
    p1 = S(pg, "document.getElementById('panel').innerText.includes('품목 자료(trade.json)를 불러오지 못했습니다') && app.layerR.items.some(i => i.kind === 'airport') && document.querySelector('#ptab-infra').innerText.includes('공항')")
    block["on"] = False
    pg.click("#loadwarn [data-retry]")
    pg.wait_for_function("window.app.layers && window.app.layers.trade", timeout=15000)
    pg.wait_for_timeout(300)
    s2 = S(pg, "({trade: !!app.layers.trade, warn: document.getElementById('loadwarn').hidden, tab: app.panelTab, panel: app.panelTab === 'infra' && !document.querySelector('#ptab-infra').hidden && !document.getElementById('panel').innerText.includes('불러오지 못했습니다') && !document.getElementById('panel').innerText.includes('불러오는 중')})")
    rec("감사 08: trade.json 404 → 공항·국립공원 층은 있고 실패 안내·패널 문구, 다시 시도 뒤 교역 자료와 패널이 채워짐", br, wl,
        s1["air"] and s1["park"] and not s1["trade"] and bool(s1["warn"]) and p1 and s2["trade"] and s2["warn"] and s2["panel"], json.dumps({"before": s1, "panel": p1, "after": s2}, ensure_ascii=False)[:260])
    ctx.close()
    ctx = br_obj.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    pg.route("**/data/sources.json", lambda r: r.fulfill(status=404, body="x"))
    ready(pg, url)
    pg.click("#almanac-btn")
    pg.click('#almanac [data-tab="sources"]')
    s3 = S(pg, "({map: !!app.layerR, src: app.sources, alm: document.getElementById('almanac').innerText.includes('불러오지 못했습니다')})")
    rec("감사 08: sources.json 404 → 지도는 뜨고 연감 출처 탭에 실패 안내", br, wl, s3["map"] and s3["src"] is None and s3["alm"], json.dumps(s3, ensure_ascii=False))
    ctx.close()
    # 19: 동작 줄이기 — 검색 이동이 즉시 (보간 없음)
    ctx = br_obj.new_context(viewport={"width": 1280, "height": 800}, reduced_motion="reduce")
    pg = ctx.new_page()
    ready(pg, url)
    pg.keyboard.press("/")
    pg.wait_for_timeout(150)
    pg.keyboard.type("김포공항")
    pg.wait_for_timeout(250)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(30)
    s4 = S(pg, "({anim: app.anim, item: app.selItem && app.selItem.name, dx: app.selItem ? Math.abs(app.cam.x - app.grid.cx[app.selItem.cell]) : null})")
    rec("감사 19: 동작 줄이기 설정에서 검색 이동이 즉시 (애니메이션 없음)", br, wl, s4["anim"] in (0, None) and s4["item"] and s4["dx"] is not None and s4["dx"] < 1, json.dumps(s4, ensure_ascii=False))
    ctx.close()
    # 09·17: 390·768 폭 — '순위 보고서 전체' 메뉴로 숨은 수치(식량)의 보고서를 열 수 있고, 상단 띠의 값이 한 줄이며 띠 안
    for w, h in ((390, 844), (768, 1024)):
        ctx = br_obj.new_context(viewport={"width": w, "height": h})
        pg = ctx.new_page()
        ready(pg, url)
        okm = reachable(pg, "#topbar [data-reports-menu]")
        if okm:
            pg.click("#topbar [data-reports-menu]")
            pg.wait_for_timeout(150)
            n_items = S(pg, "document.querySelectorAll('#repmenu [data-pick]').length")
            pg.click('#repmenu [data-pick="food"]')
            pg.wait_for_timeout(250)
            rep = S(pg, "({open: !document.getElementById('report').hidden, id: app.report.id, sel: document.querySelector('#report [data-report-pick]') ? document.querySelector('#report [data-report-pick]').options.length : 0})")
        else:
            n_items, rep = 0, {}
        lay = S(pg, """(() => { const tb = document.getElementById('topbar').getBoundingClientRect(); const out = [];
          for (const b of document.querySelectorAll('#topbar .st')) { if (getComputedStyle(b).display === 'none') continue;
            for (const e of b.querySelectorAll('em, b')) { const r = e.getBoundingClientRect(), lh = parseFloat(getComputedStyle(e).fontSize) * 1.6;
              if (r.top < tb.top - 1 || r.bottom > tb.bottom + 1 || r.height > lh) out.push(e.textContent + ' ' + Math.round(r.top) + '–' + Math.round(r.bottom) + '/' + Math.round(tb.top) + '–' + Math.round(tb.bottom)); } }
          return out; })()""")
        rec("감사 09·17: 좁은 폭에서 '순위 보고서 전체' 메뉴로 숨은 수치(식량) 보고서를 열고, 보고서 안 선택기, 상단 띠 값이 한 줄로 띠 안", br, f"{w}×{h}",
            okm and n_items == 8 and rep.get("open") and rep.get("id") == "food" and rep.get("sel") == 8 and not lay,
            f"메뉴 {okm} 항목 {n_items}, 보고서 {rep}, 띠 밖·두 줄 {lay[:4]}")
        ctx.close()
    # 14: 소멸위험 단계 배지 글자 대비 4.5:1 이상 (서울 '주의')
    ctx = br_obj.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    ready(pg, url)
    open_city_by_search(pg, "서울")
    cr_ = S(pg, """(() => { const e = document.querySelector('#panel .stage'); if (!e) return null; const cs = getComputedStyle(e);
      const p = (c) => c.match(/\\d+(\\.\\d+)?/g).slice(0, 3).map(Number).map(v => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
      const L = (c) => { const [r, g, b] = p(c); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
      const a = L(cs.color), b = L(cs.backgroundColor); return {text: e.textContent, ratio: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)}; })()""")
    rec("감사 14: 소멸위험 단계 배지(서울)의 글자·배경 대비 4.5:1 이상", br, wl, cr_ is not None and cr_["ratio"] >= 4.5, json.dumps(cr_, ensure_ascii=False))
    ctx.close()


# ---------------------------------------------------------------- 7b (docs/ideas/site_r3.md)
def png_info(path):
    try:
        from PIL import Image
        im = Image.open(path)
        return im.format, im.size, os.path.getsize(path)
    except Exception as e:  # noqa: BLE001
        return str(e), None, 0


def r3_png(br_obj, url, br):
    """#32: 정사각 1:1·와이드 16:9 그림을 메뉴(키보드·마우스)로 내려받아 PNG·크기·50 KB 이상인지 본다 (세 엔진)"""
    wl = "1280×800"
    ctx = br_obj.new_context(viewport={"width": 1280, "height": 800}, accept_downloads=True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    ready(pg, url)
    out = {}
    # 키보드: 공유 단추를 누르면 첫 항목에 초점, ↓ 로 정사각, Enter
    pg.click("#share-btn")
    pg.wait_for_timeout(150)
    f0 = S(pg, "document.activeElement && document.activeElement.dataset.act")
    pg.keyboard.press("ArrowDown")
    f1 = S(pg, "document.activeElement && document.activeElement.dataset.act")
    with pg.expect_download(timeout=30000) as dl:
        pg.keyboard.press("Enter")
    out["square"] = png_info(dl.value.path()) + (dl.value.suggested_filename,)
    last_sq = S(pg, "app.share.last")
    pg.click("#share-btn")
    with pg.expect_download(timeout=30000) as dl:
        pg.click('#sharemenu [data-act="png"]')
    out["wide"] = png_info(dl.value.path()) + (dl.value.suggested_filename,)
    ok = (f0 == "link" and f1 == "png-square" and out["square"][0] == "PNG" and out["square"][1] == (1200, 1200) and out["square"][2] > 50000
          and out["wide"][0] == "PNG" and out["wide"][1] == (1600, 900) and out["wide"][2] > 50000 and last_sq["titleRight"] < last_sq["rightLeft"])
    rec("7b #32: 공유 메뉴 키보드(첫 항목 초점·↓·Enter)로 정사각 1200×1200, 마우스로 와이드 1600×900 — 둘 다 50 KB 넘는 PNG, 제목이 오른쪽 기준 글과 안 겹침", br, wl, ok,
        f"초점 {f0}→{f1}, 정사각 {out['square'][:3]}, 와이드 {out['wide'][:3]}, 제목 끝 {last_sq['titleRight']:.0f} < 오른쪽 글 {last_sq['rightLeft']:.0f}")
    # Esc 로 메뉴 닫고 공유 단추로 초점
    pg.click("#share-btn")
    pg.keyboard.press("Escape")
    st = S(pg, "({open: !document.getElementById('sharemenu').hidden, focus: document.activeElement && document.activeElement.id})")
    rec("7b #32: 공유 메뉴 Esc → 닫히고 초점이 공유 단추로", br, wl, not st["open"] and st["focus"] == "share-btn", json.dumps(st))
    rec("7b 그림 시험 동안 페이지 오류 없음", br, wl, not errs, "; ".join(errs[:3]))
    ctx.close()


def r3_suite(br_obj, url, br):
    """7b 실제 입력 시험 (Chromium, 1280×800 · 390×844)"""
    for (w, h) in ((1280, 800), (390, 844)):
        wl = f"{w}×{h}"
        ctx = br_obj.new_context(viewport={"width": w, "height": h}, accept_downloads=True, **({"has_touch": True, "is_mobile": True} if w < 700 else {}))
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        ready(pg, url)
        # #1 · #2: 전국 배율 배치
        d = S(pg, """() => { const a = app, P = a.layerR.placed, B = a.layerR.budget, mob = a.cam.vw <= B.mobile_vw;
          const t0 = (k) => a.layerR.items.filter(i => i.kind === k && i.tier === 0).length;
          const pl = (k) => P.filter(p => p.it.kind === k).length;
          const src = a.drawScene.toString(), ix = (t) => src.indexOf(t);
          return {z: a.cam.scale / a.cam.minScale, nuc: [pl('nuclear'), t0('nuclear')], air: [pl('airport'), t0('airport')], port: [pl('trade_port'), t0('trade_port')],
            icons: P.length, flags: a.banners.rects.length, iconCap: mob ? B.icons_mobile : B.icons_desktop, flagCap: mob ? B.flags_mobile : B.flags_desktop,
            avoid: typeof a.banners.avoid, order: ix('labels.draw') < ix('geoLabels.draw') && ix('geoLabels.draw') < ix('drawIcons') && ix('drawIcons') < ix('banners.draw('),
            pxMax: Math.max(...a.labels.boxes.map(b => b.px)), moved: P.filter(p => p.ox != null).map(p => p.it.kind) }; }""")
        ok = (d["z"] < 1.05 and d["nuc"] == [5, 5] and d["air"][0] == d["air"][1] == 6 and d["port"][0] == d["port"][1] == 8
              and d["icons"] <= d["iconCap"] and d["flags"] <= d["flagCap"] and d["avoid"] == "undefined" and d["order"] and d["pxMax"] <= (24 if w < 700 else 34))
        rec("7b #1·#2: 전국 배율 원전 5/5·공항 6/6·무역항 8/8, 아이콘·깃발 예산 안, 시도 이름은 아이콘·깃발 아래 층(그리기 순서)·avoid 없음·글자 크기 상한", br, wl, ok, json.dumps(d, ensure_ascii=False)[:300])
        if w >= 700:
            # 옮겨 그린 아이콘을 마우스로 가리키면 '깃발과 겹쳐 옆 칸에 표시', 정밀도는 한국어
            xy = S(pg, """() => { for (const p of app.layerR.placed) { if (p.ox == null) continue; const el = document.elementFromPoint(p.x, p.y);
                if (!el || el.id !== 'map' || app.banners.hit(p.x, p.y)) continue; const h = app.layerR.hit(p.x, p.y); if (h && h.it.id === p.it.id) return [p.x, p.y, p.it.name]; } return null; }""")
            if xy:
                pg.mouse.move(xy[0] + 4, xy[1] + 4)
                pg.mouse.move(xy[0], xy[1])
                pg.wait_for_timeout(200)
                tip = S(pg, "document.getElementById('tooltip').hidden ? '' : document.getElementById('tooltip').innerText")
                rec("7b #1: 옮겨 그린 아이콘 툴팁에 '깃발과 겹쳐 옆 칸에 표시', 정밀도 영문 키 없음", br, wl,
                    "깃발과 겹쳐 옆 칸에 표시" in tip and not any(k in tip for k in ("point", "county", "area", "sido")), f"{xy[2]}: " + tip.replace("\n", " / ")[:150])
            else:
                rec("7b #1: 옮겨 그린 아이콘 툴팁에 '깃발과 겹쳐 옆 칸에 표시', 정밀도 영문 키 없음", br, wl, None, "가리킬 수 있는 옮긴 아이콘 없음")
            # z = 2.6 에서 강·호수 이름표가 깃발·아이콘 상자와 겹치지 않음
            mn = S(pg, "app.cam.minScale")
            pg.goto(url.replace("index.html", "index.html?z26") + f"#v=2600,2200,{mn * 2.6:.4f}")
            pg.wait_for_function("window.app && window.app.layerR", timeout=30000)
            pg.wait_for_timeout(700)
            g = S(pg, """() => { const ov = (r, p) => r.x0 < p.x1 && r.x1 > p.x0 && r.y0 < p.y1 && r.y1 > p.y0; const L = app.geoLabels.drawn || [];
              const F = app.banners.rects.map(f => f.r), I = app.layerR.placedBoxes(); let n = 0; for (const l of L) if (F.some(f => ov(l, f)) || I.some(b => ov(l, b))) n++;
              return {labels: L.length, hit: n, z: app.cam.scale / app.cam.minScale}; }""")
            rec("7b #1: z 2.6 에서 강·호수 이름표가 깃발·아이콘 상자와 겹치는 수 0", br, wl, g["labels"] > 0 and g["hit"] == 0, json.dumps(g))
        # #12 · #9: 울산 깃발을 눌러 도시 패널 — 산출 5칸 한 줄, 1280 에서 스크롤 없이 순위
        pg.goto(url.replace("index.html", "index.html?p") + "#")
        pg.wait_for_function("window.app && window.app.layerR", timeout=30000)
        pg.wait_for_timeout(500)
        fp = flag_pos(pg, "울산")
        if fp:
            (pg.touchscreen.tap(*fp) if w < 700 else pg.mouse.click(*fp))
        else:
            open_city_by_search(pg, "울산")
        pg.wait_for_timeout(600)
        y = S(pg, """() => { const P = document.getElementById('panel'), pr = P.getBoundingClientRect(); const ys = [...P.querySelectorAll('.yields .yt')];
          const rk = [...P.querySelectorAll('#ptab-overview h4')].find(h => h.textContent.startsWith('순위')); const row = P.querySelector('.rk-row');
          const inV = (e) => { const b = e.getBoundingClientRect(); return b.top >= pr.top && b.bottom <= pr.bottom; };
          return {mode: app.panel.mode, city: app.selCity, n: ys.length, tops: [...new Set(ys.map(e => e.offsetTop))].length, over: Math.max(0, P.scrollWidth - P.clientWidth),
            yover: P.querySelector('.yields').scrollWidth - P.querySelector('.yields').clientWidth, scrollTop: P.scrollTop, rank: !!rk && inV(rk), row: !!row && inV(row),
            tabs: [...P.querySelectorAll('.ptab')].map(t => t.querySelectorAll('details.caveats').length), sub: P.querySelector('.sub').innerText}; }""")
        okp = (y["mode"] == "city" and y["city"] == 12 and y["n"] == 5 and y["tops"] == 1 and y["over"] == 0 and y["yover"] <= 0 and max(y["tabs"]) <= 1
               and "자치구 4곳 합 · 울주군 별도" in y["sub"] and (w < 700 or (y["scrollTop"] == 0 and y["rank"] and y["row"])))
        rec("7b #12·#9: 울산 깃발 → 다섯 산출 5칸 한 줄·가로 넘침 0, 탭마다 '기준과 주의' 1개 이하, 부제 '자치구 4곳 합 · 울주군 별도'" + (", 스크롤 없이 순위 제목·첫 행" if w >= 700 else ""), br, wl, okp, json.dumps(y, ensure_ascii=False)[:300])
        # 서울·울릉군도 산출 한 줄 (찾기로)
        rows = []
        okr = True
        for nm in ("서울", "울릉군"):
            open_city_by_search(pg, nm)
            q = S(pg, "(() => { const ys = [...document.querySelectorAll('#panel .yields .yt')]; const Y = document.querySelector('#panel .yields'); return {n: ys.length, tops: new Set(ys.map(e => e.offsetTop)).size, over: Y.scrollWidth - Y.clientWidth}; })()")
            okr = okr and q["n"] == 5 and q["tops"] == 1 and q["over"] <= 0
            rows.append(f"{nm} {q}")
        rec("7b #12: 서울·울릉군 패널도 다섯 산출 5칸 한 줄(가로 넘침 0)", br, wl, okr, "; ".join(rows))
        # 서울 생산 칸: 점선·*, 눌러서(또는 Enter) 감사 16 문구, Esc 는 말풍선만 닫음
        open_city_by_search(pg, "서울")
        tile = pg.locator('#panel .yields .yt').nth(1)
        part = S(pg, "(() => { const t = document.querySelectorAll('#panel .yields .yt')[1]; return t.classList.contains('partial') && t.querySelector('sup.pm') && getComputedStyle(t).borderTopStyle; })()")
        (tile.tap() if w < 700 else tile.click())
        pg.wait_for_timeout(150)
        t1 = S(pg, "document.getElementById('fnpop').hidden ? '' : document.getElementById('fnpop').innerText")
        exp = S(pg, "app.cityById.get(0).production_mining_excluded")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(100)
        st = S(pg, "({pop: document.getElementById('fnpop').hidden, mode: app.panel.mode})")
        tile.focus()
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(100)
        t2 = S(pg, "document.getElementById('fnpop').hidden ? '' : document.getElementById('fnpop').innerText")
        pg.keyboard.press("Escape")
        rec("7b #12: 서울 생산 칸 점선·*, 누르기·Enter 로 '제조업 + 건설업 + 공개된 광업의 합 (광업 비공개 N곳 제외', Esc 는 말풍선만 닫음", br, wl,
            part == "dashed" and f"제조업 + 건설업 + 공개된 광업의 합 (광업 비공개 {exp}곳 제외" in t1 and t1 == t2 and st["pop"] and st["mode"] == "city",
            f"테두리 {part}, 문구 {t1.replace(chr(10), ' / ')[-90:]}, Esc 뒤 {st}")
        # #9 탭 기억: 울산 경제 탭 → 서울 깃발 → 경제 탭, 해시 tab=econ
        open_city_by_search(pg, "울산")
        tb = pg.locator('#panel [data-ptab="econ"]')
        (tb.tap() if w < 700 else tb.click())
        pg.keyboard.press("Escape") if False else None
        pg.goto(url.replace("index.html", "index.html?t") + "#city=12&tab=econ")
        pg.wait_for_function("window.app && window.app.layerR", timeout=30000)
        pg.wait_for_timeout(500)
        r1 = S(pg, "({tab: app.panelTab, vis: !document.getElementById('ptab-econ').hidden})")
        fp = flag_pos(pg, "서울")
        if fp and w >= 700:
            pg.mouse.click(*fp)
        else:
            open_city_by_search(pg, "서울")
        pg.wait_for_timeout(500)
        pg.wait_for_timeout(300)
        r2 = S(pg, "({city: app.selCity, tab: app.panelTab, vis: !document.getElementById('ptab-econ').hidden, sel: document.querySelector('#tab-econ').getAttribute('aria-selected'), hash: location.hash})")
        pg.goto(url.replace("index.html", "index.html?e") + "#city=")
        pg.wait_for_function("window.app && window.app.layerR", timeout=30000)
        pg.wait_for_timeout(300)
        r3 = S(pg, "app.selCity")
        pg.goto(url.replace("index.html", "index.html?b") + "#city=12&tab=bogus&zz=1")
        pg.wait_for_function("window.app && window.app.layerR", timeout=30000)
        pg.wait_for_timeout(300)
        r4 = S(pg, "({city: app.selCity, tab: app.panelTab})")
        rec("7b #9: 새로 고침 #city=12&tab=econ → 경제 탭, 서울로 옮겨도 경제 탭(해시 tab=econ), #city= 는 아무것도 안 엶, 모르는 tab·키는 무시(개요)", br, wl,
            r1 == {"tab": "econ", "vis": True} and r2["city"] == 0 and r2["tab"] == "econ" and r2["vis"] and r2["sel"] == "true" and "tab=econ" in r2["hash"] and r3 is None
            and r4 == {"city": 12, "tab": "overview"}, json.dumps({"reload": r1, "seoul": r2, "empty": r3, "bogus": r4}, ensure_ascii=False)[:300])
        if w >= 700:
            # 탭 바 ←/→ 로 탭 이동, 지도는 안 움직임
            pg.focus('#panel #tab-overview') if S(pg, "!!document.getElementById('tab-overview')") else None
            pg.click('#panel [data-ptab="overview"]')
            c0 = cam(pg)
            pg.keyboard.press("ArrowRight")
            pg.wait_for_timeout(100)
            k1 = S(pg, "({tab: app.panelTab, focus: document.activeElement && document.activeElement.dataset.ptab})")
            pg.keyboard.press("End")
            k2 = S(pg, "app.panelTab")
            pg.keyboard.press("ArrowLeft")
            k3 = S(pg, "app.panelTab")
            c1 = cam(pg)
            rec("7b #9: 탭 바에서 → · End · ← 로 탭 이동, 지도 카메라는 그대로", br, wl, k1 == {"tab": "econ", "focus": "econ"} and k2 == "land" and k3 == "infra" and c0 == c1,
                f"{k1} {k2} {k3}, 카메라 같음 {c0 == c1}")
            # #10: 순위 행 누르기 → 인접 순위 칩 → 칩 누르면 그 도시
            pg.click('#panel [data-ptab="overview"]')
            row = pg.locator('#panel .rk-row[data-rk="population"]')
            row.click()
            pg.wait_for_timeout(100)
            chips = S(pg, "[...document.querySelectorAll('#panel .rk-adj:not([hidden]) button')].map(b => [b.dataset.city, b.innerText])")
            tgt = int(chips[0][0]) if chips else None
            if chips:
                pg.locator('#panel .rk-adj:not([hidden]) button').first.click()
                pg.wait_for_timeout(400)
            moved = S(pg, "app.selCity")
            row2 = pg.locator('#panel .rk-row[data-rk="gdp"]')
            row2.focus()
            pg.keyboard.press("Enter")
            ex = S(pg, "document.querySelector('#panel .rk-row[data-rk=\"gdp\"]').getAttribute('aria-expanded')")
            rec("7b #10: 순위 행을 누르면 바로 위·아래 순위 칩, 칩을 누르면 그 도시, Enter 로도 펼침", br, wl, bool(chips) and moved == tgt and ex == "true",
                f"칩 {chips[:3]}, 이동 {moved}, Enter {ex}")
            # #10 · #11 · #13: 자료 대조 (찾기로 열고 상태를 읽음)
            res = {}
            for cid, nm in ((9, "화성시"), (12, "울산"), (30, "세종"), (166, "울릉군"), (63, "포천시"), (0, "서울"), (1, "부산"), (40, "익산시"), (115, "울진군")):
                open_city_by_search(pg, nm)
                res[nm] = S(pg, """() => { const P = document.getElementById('panel'); const T = (s) => [...P.querySelectorAll(s)].map(e => e.innerText.trim());
                  const card = (lab) => { const d = [...P.querySelectorAll('.kv > div')].find(x => x.querySelector('em') && x.querySelector('em').innerText.startsWith(lab)); return d ? (d.querySelector('.ref') ? d.querySelector('.ref').innerText : '') : null; };
                  return {tags: T('#panel .ctag'), over65: P.querySelector('.agebar .ref') ? P.querySelector('.agebar .ref').innerText : '', gdppc: card('1인당 GRDP'), home: card('아파트 매매 ㎡당'), emp: card('고용률'), fis: card('재정자립도'),
                    exp: (P.querySelector('.rk-row[data-rk="export"]') || {}).innerText, expDis: !!P.querySelector('.rk-item .rk-row.disabled') && [...P.querySelectorAll('.rk-row.disabled')].map(e => e.innerText).join('|'),
                    house: (P.querySelector('.rk-row[data-rk="housing"]') || {}).innerText, peer: (P.querySelector('.peers .peer-go .peer-why') || {}).innerText, peers: T('#panel .peer-why'),
                    dup: /% %|%%/.test(P.innerText)}; }""")
            B = S(pg, "app.nation.nation.benchmarks.metrics")
            hw, ul = res["화성시"], res["울산"]
            def dexp(cid):
                v = S(pg, f"app.cityById.get({cid}).age.over65")
                dd = v - B["over65"]["v"]
                return f"{'▲' if dd > 0 else '▼'} 전국 {'+' if dd > 0 else '−'}{abs(dd):.1f}%p"
            ok10 = (hw["over65"] == dexp(9) and ul["over65"] == dexp(12) and not any(r["dup"] for r in res.values()) and res["서울"]["emp"] == "" and res["부산"]["emp"] == ""
                    and "전국('23)" in res["세종"]["gdppc"] and "/165" in (ul["exp"] or "")
                    and ((res["울릉군"]["home"] is None and ul["house"] is None) if PUBLIC else ("(거래 3건)" in res["울릉군"]["home"] and "/166" in (ul["house"] or "")))
                    and "자료 없음 · 순위 제외" in (res["포천시"]["expDis"] or "") and (hw["fis"] or "").find("도시 중앙") >= 0)
            rec("7b #10: 화성시·울산 고령 대비 = nation.json 으로 계산한 값, '% %' 없음, 서울·부산 고용률 화살표 없음, 세종 전국('23), 울릉군 (거래 3건), 분모 수출 165·아파트 166, 포천시 수출 '자료 없음 · 순위 제외', 재정자립도는 도시 중앙", br, wl, ok10,
                json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("over65", "gdppc", "home", "emp", "fis", "exp", "expDis")} for k, v in res.items() if k in ("화성시", "울산", "세종", "울릉군", "포천시", "서울")}, ensure_ascii=False)[:300])
            ok11 = (hw["tags"] == ["제조업 비중 ×2.6", "1인당 GRDP 8위"] and res["익산시"]["tags"] == [] and res["울진군"]["tags"][:1] == ["전기·가스·증기 비중 ×33"]
                    and res["세종"]["tags"][:1] == ["공공행정·국방 비중 ×4.4"])
            # 태그 누르면 산식 (울진 소규모 주석, 세종 연도 주석)
            pops = {}
            for nm in ("울진군", "세종", "화성시"):
                open_city_by_search(pg, nm)
                pg.locator('#panel .ctag').first.click()
                pg.wait_for_timeout(120)
                pops[nm] = S(pg, "document.getElementById('fnpop').hidden ? '' : document.getElementById('fnpop').innerText")
                pg.keyboard.press("Escape")
            ok11 = ok11 and all("÷ 전국 공식" in t and "= ×" in t for t in pops.values()) and "인구 5만 미만" in pops["울진군"] and "2024년" in pops["세종"] and "66.6% ÷ 전국 공식 25.4% = ×2.6" in pops["화성시"]
            rec("7b #11: 화성시 '제조업 비중 ×2.6'·'1인당 GRDP 8위', 익산시 표시 없음, 울진군 ×33(+인구 5만 미만 주석), 세종 ×4.4(+2024 주석), 누르면 '도시 비중 ÷ 전국 공식 = ×배수'", br, wl, ok11,
                json.dumps({"tags": {k: res[k]["tags"] for k in ("화성시", "익산시", "울진군", "세종")}, "pop": {k: v[:80] for k, v in pops.items()}}, ensure_ascii=False)[:300])
            ok13 = (hw["peer"] or "").startswith("1인당 GRDP·제조업 비중(70.6%·74.3%) 가까움") and (("아파트" not in (hw["peer"] or "")) if PUBLIC else ("아파트 ㎡당 2.8배 차" in (hw["peer"] or ""))) and not any("아파트" in t for t in res["울릉군"]["peers"])
            rec("7b #13: 화성시 첫 닮은 도시(아산시) 근거 '1인당 GRDP·제조업 비중(70.6%·74.3%) 가까움 · 아파트 ㎡당 2.8배 차', 울릉군(거래 3건)은 매매가 차이 없음", br, wl, ok13,
                json.dumps({"화성시": hw["peer"], "울릉군": res["울릉군"]["peers"]}, ensure_ascii=False)[:260])
            # #20: 찾기 빈 입력 → 시점 6선, ↓ 로 첫 시점, Enter → 렌즈·도시, 새 해시 키 없음
            pg.goto(url.replace("index.html", "index.html?s") + "#")
            pg.wait_for_function("window.app && window.app.layerR", timeout=30000)
            pg.wait_for_timeout(300)
            pg.keyboard.press("/")
            pg.wait_for_timeout(150)
            n_p = S(pg, "document.querySelectorAll('#search li.preset').length")
            for _ in range(8):
                pg.keyboard.press("ArrowDown")
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(900)
            ps = S(pg, "({lens: app.lens && app.lens.id, city: app.selCity, keys: [...new URLSearchParams(location.hash.slice(1)).keys()]})")
            first = S(pg, "app.nation.presets.items[0]")
            rec("7b #20: 찾기 빈 입력에 시점 6선, ↓ 로 첫 시점을 골라 Enter → 그 렌즈·도시, 해시 키는 기존 것만", br, wl,
                n_p == 6 and ps["lens"] == first["lens"] and ps["city"] == first["city"] and set(ps["keys"]) <= {"v", "lens", "city", "ly", "hide", "route", "tab"}, json.dumps(ps, ensure_ascii=False))
            # 신여지도 고리: 폴더가 있으면 보이고, 지금 해시를 그대로 단다
            pg.goto(url.replace("index.html", "index.html?y") + "#city=9&lens=over65")
            pg.wait_for_function("window.app && window.app.layerR", timeout=30000)
            pg.wait_for_timeout(500)
            pg.hover(".brand .altfe")
            al = S(pg, "({vis: !document.querySelector('.brand .altfe').hidden, href: document.querySelector('.brand .altfe').getAttribute('href'), hash: location.hash})")
            rec("7b 신여지도 고리: 폴더가 있으면 상표 아래 보이고, 가리키면 지금 해시를 그대로 단 주소", br, wl, al["vis"] and al["href"] == "yeojido/index.html" + al["hash"] and "city=9" in al["hash"], json.dumps(al, ensure_ascii=False))
        else:
            # 390: 패널(아래 시트) 탭 4개가 한 줄, 가로 넘침 없음
            open_city_by_search(pg, "울산")
            m = S(pg, "(() => { const P = document.getElementById('panel'); const t = [...P.querySelectorAll('[role=tab]')]; return {tabs: t.length, rows: new Set(t.map(e => e.offsetTop)).size, over: P.scrollWidth - P.clientWidth, w: P.clientWidth}; })()")
            rec("7b #9: 390 아래 시트에서 탭 4개 한 줄, 패널 가로 넘침 0", br, wl, m["tabs"] == 4 and m["rows"] == 1 and m["over"] <= 0, json.dumps(m))
        rec("7b 시험 동안 페이지 오류 없음", br, wl, not errs, "; ".join(errs[:3]))
        ctx.close()
    # 신여지도 폴더가 없으면 고리가 보이지 않음 (HEAD 404)
    ctx = br_obj.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    pg.route("**/yeojido/index.html", lambda route: route.fulfill(status=404, body="no"))
    ready(pg, url)
    hid = S(pg, "document.querySelector('.brand .altfe').hidden && getComputedStyle(document.querySelector('.brand small')).display !== 'none'")
    rec("7b 신여지도 고리: 폴더가 없으면(HEAD 404) 숨고 원래 부제가 남음", br, "1280×800", hid, str(hid))
    # 동작 줄이기: 시점 적용이 보간 없이 바로
    ctx.close()
    ctx = br_obj.new_context(viewport={"width": 1280, "height": 800}, reduced_motion="reduce")
    pg = ctx.new_page()
    ready(pg, url)
    pg.click("#help-btn")
    pg.click('#help [data-preset="top_gdppc"]')
    pg.wait_for_timeout(50)
    rm = S(pg, "({anim: app.anim, city: app.selCity, lens: app.lens && app.lens.id})")
    rec("7b #20: 도움말의 시점 단추(동작 줄이기) → 보간 없이 바로 이동, 그 도시·렌즈", br, "1280×800", rm["anim"] == 0 and rm["lens"] == "gdp_pc" and rm["city"] == S(pg, "app.nation.presets.items[1].city"), json.dumps(rm))
    ctx.close()


def write_md(started):
    by = {}
    for r in results:
        by.setdefault(r[3], 0)
        by[r[3]] += 1
    lines = ["# 6단계 실제 조작 확인 (A2)", "",
             f"`python tools/qa_interaction.py` 가 만든 표다 ({started}). 조작은 모두 Playwright 의 실제 입력 이벤트(page.mouse · page.touchscreen · page.keyboard, "
             "두 손가락 확대는 CDP Input.dispatchTouchEvent)로 했고, evaluate 는 좌표를 찾고 결과 상태(패널 종류, 카메라 값, 필터)를 읽는 데만 썼다.", "",
             f"합계: {len(results)}개 — " + ", ".join(f"{k} {v}" for k, v in by.items()), "",
             "| 항목 | 브라우저 | 폭 | 결과 | 비고 |", "|---|---|---|---|---|"]
    for item, br, wl, st, note in results:
        lines.append(f"| {item} | {br} | {wl} | {st} | {note.replace('|', '/')} |")
    lines += ["", "## 앞선 실행에서 실패해 고친 것", "",
              "- 768×1024 Chromium: 패널을 열면 패널(오른쪽 360 px)과 가운데 렌즈 막대가 겹쳤다 → 넓은 화면에서 패널이 열려 있으면 렌즈 막대를 패널 왼쪽 빈 곳의 가운데로 옮기고 폭을 줄였다(style.css `body.panel-open #lensbar`). 다시 돌려 통과.",
              "- 390×844: 첫 시험 전 화면 점검에서 범례(지형 열쇠)가 층 조작부·지도와 겹치고 상단 수치가 두 줄로 꺾였다 → 좁은 화면에서는 층 조작 줄을 상단 막대 바로 아래에 두고(지도 맞춤도 그 아래부터), 범례는 제목 한 줄로 접어 누르면 펼치게, 상단 수치는 인구·고령·소멸·금 넷만 한 줄로.",
              "- 빈 땅을 누르면 도시 패널이 열렸다(명세는 시도 패널) → 깃발·아이콘·선·이름표가 아닌 땅을 누르면 그 칸의 시도 패널을 연다. 도시는 깃발·검색·시도 패널 목록으로 연다.",
              "- 시험 스크립트 쪽 잘못 두 가지(1인당 규칙 문장의 표기, 이미 펼쳐진 렌즈 묶음을 다시 눌러 닫은 것)를 고쳤다 — 사이트 문제는 아니었다.",
              "", "범위: Chromium 은 마우스·단축키·보고서·범례·공유·주석·층 조작·터치·네 폭 배치 전부, Firefox·WebKit 은 마우스 항목만(명세대로).",
              "실패한 항목은 사이트를 고친 뒤 다시 돌린 결과가 이 표다. '확인 못 함'은 자리를 찾지 못했거나 그 폭에서 숨긴 조작부라 시험하지 않은 것이다."]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    which = sys.argv[1:] or ["chromium", "firefox", "webkit"]
    srv, url = serve()
    started = time.strftime("%Y-%m-%d %H:%M")
    with sync_playwright() as p:
        for br in which:
            b = getattr(p, br).launch()
            ctx = b.new_context(viewport={"width": 1280, "height": 800}, accept_downloads=True,
                                **({"permissions": ["clipboard-read", "clipboard-write"]} if br == "chromium" else {}))
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            mouse_suite(pg, url, br, "1280×800")
            if br == "chromium":
                ui_suite(pg, ctx, url, br, "1280×800")
            rec("페이지 오류 없음 (위 시험 동안)", br, "1280×800", not errs, "; ".join(errs[:3]))
            ctx.close()
            if br == "chromium":
                touch_suite(b, url, br)
                layout_suite(b, url, br)
                audit_suite(b, url, br)
                r3_suite(b, url, br)
            r3_png(b, url, br)
            b.close()
    srv.shutdown()
    write_md(started)
    bad = [r for r in results if r[3] != "통과"]
    print(f"\n{len(results)}개 중 통과 {len(results) - len(bad)}, 실패 {sum(1 for r in bad if r[3] == '실패')}, 확인 못 함 {sum(1 for r in bad if r[3] == '확인 못 함')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
