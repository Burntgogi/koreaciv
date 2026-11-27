"""신여지도 통합 점검 — 실제 입력(마우스·휠·끌기·키보드·터치)으로 본다.
python tools/yeojido/qa.py [--only chromium|firefox|webkit] [--quick]
끝 코드 = 실패 수. 기록: tools/yeojido/qa_result.txt. 갈피·범례·장부·순위는 qa_lens.py 를 함께 돌린다(Chromium).
"""
import sys, os, json, re, base64, subprocess, statistics, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from shot import serve
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
DATA = os.path.join(ROOT, 'site', 'data')
SHOTS = os.path.join(ROOT, 'docs', 'screenshots')
ONLY = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
LOG, FAILS, PERF = [], [], []
EMOJI = r'[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B50}\u{2B55}\u{FE0F}]'

def out(s):
    print(s, flush=True); LOG.append(s)
def check(tag, name, ok, info=''):
    out(f"{'PASS' if ok else 'FAIL'} [{tag}] {name}{(' — ' + str(info)) if info and (not ok or len(str(info)) < 90) else ''}")
    if not ok: FAILS.append(f'[{tag}] {name} — {info}')
def J(name):
    with open(os.path.join(DATA, name + '.json'), encoding='utf-8') as f: return json.load(f)
def comma(n): return f'{int(round(n)):,}'
def won(v):
    a = abs(v)
    if a >= 1e12:
        x = round(v / 1e12, 0 if a >= 1e14 else 1)
        return (comma(x) if x == int(x) else f'{x:,.1f}') + '조'
    if a >= 1e10: return comma(v / 1e8) + '억'
    if a >= 1e8: return f'{v / 1e8:.1f}억'
    return comma(v / 1e4) + '만'

class Page:
    def __init__(self, browser, port, w, h, tag, **kw):
        self.port, self.tag, self.w, self.h = port, tag, w, h
        self.ctx = browser.new_context(viewport={'width': w, 'height': h}, **kw)
        self.pg = self.ctx.new_page()
        self.errs, self.foreign = [], []
        self.pg.on('console', lambda m: self.errs.append(m.text) if m.type == 'error' else None)
        self.pg.on('pageerror', lambda e: self.errs.append('PAGEERROR ' + str(e)))
        self.pg.on('requestfailed', lambda r: self.errs.append('REQFAIL ' + r.url))
        self.pg.on('request', lambda r: self.foreign.append(r.url) if not r.url.startswith(f'http://127.0.0.1:{port}/') and not r.url.startswith(('data:', 'blob:')) else None)
    def go(self, hsh='', wait=700, layers=True):
        self.pg.goto('about:blank')  # 해시만 다른 주소는 같은 문서라 다시 불러오지 않는다 -> 늘 새로 연다
        self.pg.goto(f'http://127.0.0.1:{self.port}/yeojido/index.html{hsh}')
        self.pg.wait_for_function('document.body.classList.contains("is-ready") || document.querySelector("#loader.is-error")', timeout=30000)
        if layers:
            try: self.pg.wait_for_function('window.app && app.layerMap', timeout=15000)
            except Exception: pass
        self.pg.wait_for_timeout(wait)
    def ev(self, js): return self.pg.evaluate(js)
    def wait(self, ms): self.pg.wait_for_timeout(ms)
    def ck(self, name, ok, info=''): check(self.tag, name, bool(ok), info)
    def pt(self, x, y):  # 세계 좌표 -> 쪽 좌표
        return self.ev(f'(() => {{ const r = app.canvas.getBoundingClientRect(), p = app.cam.toScreen({x}, {y}); return [r.left + p[0], r.top + p[1]]; }})()')
    def close(self): self.ctx.close()

def safe(P, name, fn):
    try: fn()
    except Exception as e:
        P.ck(name + ' (점검 중 예외)', False, str(e).split('\n')[0][:200])

PIX = '''(() => { const c = app.canvas, k = app.cdpr, x = Math.round(c.width / 2 - 20 * k), y = Math.round(c.height / 2 - 20 * k);
  const d = c.getContext('2d').getImageData(x, y, Math.round(40 * k), Math.round(40 * k)).data; let r = 0, g = 0, b = 0, n = d.length / 4;
  for (let i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; } return [r / n, g / n, b / n, app.cam.rc]; })()'''
SIG = '''(() => { const c = app.canvas, d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; const o = new Uint8Array(d.length / 16);
  for (let i = 0, k = 0; i < d.length; i += 16, k++) o[k] = (d[i] + d[i + 1] + d[i + 2]) / 3; window.__sig = window.__sig || []; window.__sig.push(o); return window.__sig.length; })()'''
DIFF = '''(() => { const a = window.__sig[window.__sig.length - 2], b = window.__sig[window.__sig.length - 1]; let n = 0; for (let i = 0; i < a.length; i++) if (Math.abs(a[i] - b[i]) > 10) n++; return n; })()'''

# ---------------------------------------------------------------- 불러오기
def t_load(P):
    P.go('', layers=False)
    P.ck('첫 방문에 표지', P.ev('!document.getElementById("intro").hidden && document.body.classList.contains("is-intro")'))
    P.ck('표지 가로 넘침 없음', P.ev('document.documentElement.scrollWidth <= innerWidth'))
    P.pg.keyboard.press('Enter'); P.wait(1100)
    P.ck('Enter 로 표지 나감', P.ev('document.getElementById("intro").hidden && !document.body.classList.contains("is-intro")'))
    P.ck('글꼴 불러옴', P.ev('document.fonts.check(\'700 14px Hahmlet\', "가") && document.fonts.check(\'14px "Yeojido Sans"\', "가")'))
    P.ck('가로 넘침 없음', P.ev('document.documentElement.scrollWidth <= innerWidth'))
    P.go('#intro=0'); P.ck('intro=0 이면 표지 없음', P.ev('document.getElementById("intro").hidden'))
    P.go('#lens=density'); P.ck('상태 해시면 표지 없음', P.ev('document.getElementById("intro").hidden && app.lens.id === "density"'))
    P.ck('콘솔 오류·실패 요청 없음', not P.errs, ' | '.join(P.errs[:3]))
    P.ck('다른 출처로 가는 요청 없음', not P.foreign, ' | '.join(P.foreign[:3]))

# ---------------------------------------------------------------- 지도 조작 (마우스·키보드)
def t_map(P):
    P.go('#v=3900,3000,0.17&intro=0&ly=')
    box = P.pg.locator('#map').bounding_box()
    cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    P.pg.mouse.move(cx, cy)
    s0 = P.ev('app.cam.scale')
    samples = [P.ev(PIX)]
    for k in range(14):
        P.pg.mouse.wheel(0, -100); P.wait(45)
        samples.append(P.ev(PIX))   # 멈추기를 기다리지 않고 바로 읽는다
    rcs = [s[3] for s in samples]
    green = [s[1] - s[0] for s in samples]  # 종이(g<r) -> 석채(g>r)
    P.ck('휠 확대가 이어짐', all(b >= a for a, b in zip(rcs, rcs[1:])) and all(b > a for a, b in zip(rcs[:6], rcs[1:7])) and P.ev('app.cam.scale') > s0 * 2, f'rc {rcs[0]:.1f}->{rcs[-1]:.1f}')
    mid = [(r, g) for r, g in zip(rcs, green) if 5.0 <= r <= 13]
    mono = all(b[1] >= a[1] - 4 for a, b in zip(mid, mid[1:]))  # 4: rc 8–13 에서 피복 무늬(먹선)가 함께 올라와 표본 평균이 조금 흔들린다
    P.ck('확대하는 동안 먹->빛깔이 이어서 배어 나옴', len(mid) >= 3 and mono and green[-1] - green[0] > 12 and len({round(g) for _, g in mid}) >= 3,
         ' '.join(f'{r:.1f}:{g:+.0f}' for r, g in zip(rcs, green)))
    x0 = P.ev('app.cam.x')
    P.pg.mouse.move(cx, cy); P.pg.mouse.down(); P.pg.mouse.move(cx - 150, cy + 40, steps=6); P.pg.mouse.up(); P.wait(600)
    P.ck('끌어서 옮김', P.ev('app.cam.x') > x0 + 20)
    s1 = P.ev('app.cam.scale'); P.pg.mouse.dblclick(cx, cy); P.wait(700)
    P.ck('두 번 눌러 확대', P.ev('app.cam.scale') > s1 * 1.3 or P.ev('app.cam.scale >= app.cam.maxScale * 0.99'))
    P.go('#intro=0'); P.pg.locator('#map').focus()
    x0 = P.ev('app.cam.x'); s0 = P.ev('app.cam.scale')
    P.pg.keyboard.press('+'); P.wait(500)
    s1 = P.ev('app.cam.scale'); P.ck('+ 로 확대', s1 > s0 * 1.3)
    P.pg.keyboard.press('ArrowRight'); P.wait(200); P.ck('화살표로 옮김', P.ev('app.cam.x') > x0 + 10)
    P.pg.keyboard.press('-'); P.wait(500); P.ck('- 로 축소', P.ev('app.cam.scale') < s1)
    P.pg.keyboard.press('+'); P.wait(400); P.pg.keyboard.press('0'); P.wait(900)
    P.ck('0 으로 전도', P.ev('Math.abs(app.cam.scale - app.cam.fitScale) / app.cam.fitScale < 0.02'))

def t_reduced(browser, port, tag):
    P = Page(browser, port, 1280, 800, tag + ' reduced-motion', reduced_motion='reduce')
    P.go('#intro=0')
    r = P.ev('(() => { app.selectCity(12, {fly: true}); const a = app.cam.anim === null; app.setLens("density"); return [a, app.lensFade === null, app.lensOld === null]; })()')
    P.ck('움직임 줄이기: 날아가기 즉시·렌즈 겹침 없음', all(r), r)
    box = P.pg.locator('#map').bounding_box(); cx, cy = box['x'] + 200, box['y'] + 300
    P.pg.mouse.move(cx, cy); P.pg.mouse.down(); P.pg.mouse.move(cx + 200, cy, steps=3); P.pg.mouse.up(); P.wait(60)
    P.ck('움직임 줄이기: 관성 없음', P.ev('!app.inertia'))
    P.ck('움직임 줄이기: CSS 전환 0ms', P.ev('getComputedStyle(document.documentElement).getPropertyValue("--d2").trim()') in ('0ms', '0s'))
    P.close()

# ---------------------------------------------------------------- 산줄기
def t_ridges(P):
    P.go('#intro=0&ly=')
    P.ev(SIG)
    P.ev('(() => { window.__r = app.lines.ridges; app.lines.ridges = []; app.requestDraw(); })()'); P.wait(300)
    P.ev(SIG); n = P.ev(DIFF)
    P.ev('(() => { app.lines.ridges = window.__r; app.requestDraw(); })()')
    P.ck('전도에 산줄기가 그려짐 (끄면 달라지는 표본 픽셀 수)', n > 1500, n)
    rg = J('ridges')
    P.ck('ridges.json 물줄기 교차 0건', rg['checks']['river_crossings'] == 0, rg['checks'].get('river_crossings'))
    P.ck('ridges.json 에 고유 산맥 이름 없음', not re.search('백두대간|정맥|태백산맥|소백산맥', json.dumps(rg, ensure_ascii=False)))
    P.ev('app.almanac.open("terrain")'); P.wait(500)
    txt = P.ev('document.querySelector("#modal-root .alm").innerText')
    P.ck('연감 지형 갈피에 규칙 문장', rg['rule'] in txt, rg['rule'])
    P.ck('연감에 교차 검사 수치', str(rg['checks']['rivers_tested']) in txt.replace(',', ''))
    P.pg.keyboard.press('Escape')

# ---------------------------------------------------------------- 고르기 (마우스)
def t_select(P):
    P.go('#intro=0&ly=')
    p = P.ev('(() => { const r = app.canvas.getBoundingClientRect(), p = app.labels.placed.find(p => p.c.name === "대전") || app.labels.placed[2]; return [r.left + p.x + p.w / 2, r.top + p.y + p.h / 2, p.c.name, p.c.id]; })()')
    P.pg.mouse.move(p[0], p[1]); P.wait(80); P.pg.mouse.click(p[0], p[1]); P.wait(700)
    P.ck('현판 누르면 그 고을 장', P.ev('app.sel.type === "city" && app.sel.id') == p[3] and p[2] in P.ev('document.getElementById("panel").innerText'))
    P.wait(300); hsh = P.ev('location.hash')
    P.ck('해시에 city', f'city={p[3]}' in hsh, hsh)
    P.go(hsh); P.ck('해시로 다시 열면 같은 상태', P.ev('app.sel.type === "city" && app.sel.id') == p[3] and P.ev('!document.getElementById("panel").hidden'))
    P.ev('app.almanac.open("notes")'); P.wait(300)
    P.pg.keyboard.press('Escape'); P.wait(250)
    a = P.ev('[document.querySelector("#modal-root .alm").hidden, app.sel.type]')
    P.pg.keyboard.press('Escape'); P.wait(250)
    P.ck('Esc 차례: 연감 먼저, 그다음 장', a == [True, 'city'] and P.ev('app.sel.type === null && document.getElementById("panel").hidden'), a)
    P.go(hsh); P.pg.locator('#panel .pn-close').click(); P.wait(300)
    P.ck('닫기 단추', P.ev('app.sel.type === null && document.getElementById("panel").hidden'))
    # 시도 이름
    P.go('#intro=0&ly=')
    b = P.ev('(() => { const r = app.canvas.getBoundingClientRect(), b = app.labels.stateBoxes[0]; return b ? [r.left + b.x + b.w / 2, r.top + b.y + b.h / 2, b.s.code] : null; })()')
    if b:
        P.pg.mouse.click(b[0], b[1]); P.wait(700)
        P.ck('시도 이름 누르면 시도 장', P.ev('app.sel.type === "state" && app.sel.id') == b[2])
    else: P.ck('시도 이름 누르면 시도 장', False, '시도 이름이 놓이지 않음')
    # 빈 땅
    P.go('#v=3900,3000,0.8&intro=0&ly=')
    q = P.ev('''(() => { const r = app.canvas.getBoundingClientRect(); for (let y = 120; y < app.cam.vh - 80; y += 37) for (let x = 120; x < app.cam.vw - 120; x += 41) {
      const p = app.pick(x, y); if (p.cell >= 0 && app.D.world.owner[p.cell] >= 0 && app.D.cityOfCell(p.cell)) return [r.left + x, r.top + y, app.D.cityOfCell(p.cell).id]; } return null; })()''')
    P.pg.mouse.move(q[0], q[1]); P.wait(120)
    P.ck('칸 풍선말', P.ev('!document.getElementById("tip").hidden && document.getElementById("tip").innerText.length > 4'))
    P.pg.mouse.click(q[0], q[1]); P.wait(600)
    P.ck('빈 땅 누르면 그 칸의 고을 장', P.ev('app.sel.type === "city" && app.sel.id') == q[2])
    # 아이콘
    P.go('#intro=0')
    ic = P.ev('(() => { const r = app.canvas.getBoundingClientRect(); const p = app.layerMap.placed.find(p => p.it && p.it.kind === "airport") || app.layerMap.placed[0]; return p ? [r.left + p.x, r.top + p.y, p.it.id] : null; })()')
    if ic:
        P.pg.mouse.move(ic[0], ic[1]); P.wait(120); P.pg.mouse.click(ic[0], ic[1]); P.wait(700)
        got = P.ev('[app.sel.type, app.sel.id]')
        P.ck('아이콘 누르면 항목 장', got[0] == 'item', f'{got} (바란 것 {ic[2]})')
    else: P.ck('아이콘 누르면 항목 장', False, '놓인 아이콘 없음')
    # 교역로
    P.go('#intro=0&ly=trade')
    rt = P.ev('''(() => { const r = app.canvas.getBoundingClientRect(); for (const s of app.D.layers.trade.segments) { if (s.qx == null) continue;
      const x = 0.25 * s.ax + 0.5 * s.qx + 0.25 * s.bx, y = 0.25 * s.ay + 0.5 * s.qy + 0.25 * s.by, p = app.cam.toScreen(x, y);
      const h = app.pick(p[0], p[1]); if (h.route && h.route.id === s.id) return [r.left + p[0], r.top + p[1], s.id]; } return null; })()''')
    if rt:
        P.pg.mouse.click(rt[0], rt[1]); P.wait(700)
        got = P.ev('[app.sel.type, app.sel.id, !document.getElementById("panel").hidden]')
        P.ck('교역로 누르면 교역로 장', got[0] == 'route' and got[2], f'{got} (짚은 선 {rt[2]})')
    else: P.ck('교역로 누르면 교역로 장', False, '누를 수 있는 교역로 점을 찾지 못함')
    # 잘못된 해시
    n0 = len(P.errs)
    for hs in ['#city=', '#city=9999', '#report=0', '#lens=nope', '#v=a,b,c', '#state=zz', '#item=nope', '#route=1-2']:
        P.go(hs + '&intro=0', wait=350)
        P.ck(f'잘못된 해시 {hs}: 선택·렌즈 없음', P.ev('app.sel.type === null && app.lens === null && document.getElementById("panel").hidden'), P.ev('JSON.stringify(app.sel)'))
    P.ck('잘못된 해시에서 오류 없음', len(P.errs) == n0, ' | '.join(P.errs[n0:n0 + 3]))
    P.go('#city=12&intro=0'); P.ev('location.hash = "#lens=density"'); P.wait(600)
    P.ck('해시 바뀜(고을 -> 렌즈만): 장 닫힘', P.ev('app.sel.type === null && document.getElementById("panel").hidden && app.lens && app.lens.id === "density"'))

# ---------------------------------------------------------------- 터치 (390)
def t_touch(P):
    P.go('#intro=0')
    q = P.ev('''(() => { const r = app.canvas.getBoundingClientRect(); for (let y = 200; y < app.cam.vh - 120; y += 23) for (let x = 60; x < app.cam.vw - 60; x += 19) {
      const p = app.pick(x, y); if (p.cell >= 0 && app.D.world.owner[p.cell] >= 0 && app.D.cityOfCell(p.cell)) return [r.left + x, r.top + y, app.D.cityOfCell(p.cell).id]; } return null; })()''')
    P.pg.touchscreen.tap(q[0], q[1]); P.wait(500)
    P.ck('빈 땅 한 번 짚기: 칸 띠 (장은 아직 안 뜸)', P.ev('!document.getElementById("cellstrip").hidden && document.getElementById("panel").hidden'))
    P.pg.locator('#cellstrip button', has_text='고을 장').tap(); P.wait(700)
    P.ck('[고을 장] 짚으면 고을 장', P.ev('app.sel.type === "city" && app.sel.id') == q[2])
    P.ck('아래 장이 화면 폭 안', P.ev('document.documentElement.scrollWidth <= innerWidth'))
    P.go('#intro=0')
    p = P.ev('(() => { const r = app.canvas.getBoundingClientRect(), p = app.labels.placed[0]; return [r.left + p.x + p.w / 2, r.top + p.y + p.h / 2, p.c.id]; })()')
    P.pg.touchscreen.tap(p[0], p[1]); P.wait(700)
    P.ck('현판 짚으면 고을 장', P.ev('app.sel.type === "city" && app.sel.id') == p[2])
    P.go('#intro=0'); P.pg.locator('#layers .lfab').tap(); P.wait(400)
    P.ck('층 단추 -> 층 서랍', P.ev('!document.getElementById("layerdrawer").hidden'))
    P.pg.locator('label[for="lg-trade"]').tap(); P.wait(300)
    P.ck('층 서랍에서 교역 켬', P.ev('app.layerOn.trade === true'))

# ---------------------------------------------------------------- 층
def t_layers(P, mouse=True):
    P.go('#intro=0')
    lay = P.ev('''(() => { const L = app.layerMap, pl = L.placed.map(p => p.it), t0 = (k) => L.items.filter(i => i.kind === k && i.tier === 0).length, n = (k) => pl.filter(i => i.kind === k).length;
      return {total: pl.length, nuclear: n('nuclear'), nuclearAll: L.items.filter(i => i.kind === 'nuclear').length, airport: n('airport'), airport0: t0('airport'), port: n('trade_port'), port0: t0('trade_port')}; })()''')
    P.ck('전도: 원전 전부·tier 0 공항·무역항 전부 놓임', lay['nuclear'] == lay['nuclearAll'] == 5 and lay['airport'] >= lay['airport0'] > 0 and lay['port'] >= lay['port0'] > 0, json.dumps(lay))
    if not mouse: return
    for k in range(5):
        b = P.pg.locator('#layers .lg').nth(k)
        before = b.get_attribute('aria-pressed'); b.click(); P.wait(150)
        P.ck(f'층 묶음 {k + 1} 마우스로 켜고 끔', b.get_attribute('aria-pressed') != before)
    P.wait(300); hs = P.ev('(app.writeHash(true), location.hash)')
    P.ck('해시에 ly', 'ly=' in hs, hs)
    P.go('#intro=0')
    P.pg.locator('#layers .lmore').focus(); P.pg.keyboard.press('Enter'); P.wait(300)
    P.ck('키보드로 세부 서랍', P.ev('!document.getElementById("layerdrawer").hidden'))
    P.pg.locator('#ls-national_park').focus(); P.pg.keyboard.press('Space'); P.wait(200)
    hs = P.ev('(app.writeHash(true), location.hash)')
    P.ck('키보드로 세부 끔 + 해시 hide', P.ev('app.subOff.has("national_park")') and 'hide=national_park' in hs, hs)
    P.pg.locator('#layers .lg').first.focus(); before = P.ev('app.layerOn.wonders'); P.pg.keyboard.press('Enter'); P.wait(150)
    P.ck('키보드로 묶음 켜고 끔', P.ev('app.layerOn.wonders') != before)

# ---------------------------------------------------------------- 찾기·연감·도움말·공유
def t_modals(P, bname, save=False):
    narrow = P.w <= 700
    P.go('#intro=0'); P.pg.locator('#map').focus()
    P.pg.keyboard.press('/'); P.wait(300)
    P.ck('/ 로 찾기 열림·입력란 초점', P.ev('document.activeElement && document.activeElement.id === "search-input"'))
    P.pg.keyboard.insert_text('전주'); P.wait(400)
    P.ck('찾기 결과', P.ev('document.querySelectorAll("#search-list [role=option]").length') > 0)
    P.pg.keyboard.press('Enter'); P.wait(900)
    P.ck('찾기 Enter -> 전주시 고을 장', P.ev('app.sel.type === "city" && app.D.cityById.get(app.sel.id).name') == '전주시')
    P.ck('찾기 뒤 초점이 장 제목으로', P.ev('document.getElementById("panel").contains(document.activeElement) && /^H\\d$/.test(document.activeElement.tagName)'), P.ev('document.activeElement.tagName + "." + document.activeElement.className'))
    P.go('#intro=0')
    P.pg.locator('#tools .t-almanac').click(); P.wait(600)
    tabs = P.pg.locator('#modal-root .alm .tabs button'); n = tabs.count()
    P.ck('연감 여섯 갈피', n == 6, n)
    short = []
    for k in range(n):
        tabs.nth(k).click(); P.wait(900 if k == 4 else 350)
        ln = P.ev('document.querySelector("#modal-root .alm .alm-body").innerText.length')
        if ln < 300: short.append((k, ln))
        if P.ev(f'/{EMOJI}/u.test(document.querySelector("#modal-root .alm").innerText)'): short.append((k, 'emoji'))
    P.ck('연감 갈피마다 내용 있음·이모지 없음', not short, short)
    P.ev('app.almanac.open("sources")'); P.wait(900)
    src = P.ev('''(() => { const p = document.querySelector('#modal-root .alm .pane-sources'); const a = [...p.querySelectorAll('a[href]')];
      return {rows: p.querySelectorAll('table.src tbody tr').length, links: a.length, bad: a.filter(x => !/^https?:\\/\\//.test(x.getAttribute('href')) && !/^\\.\\.\\/[a-z]+\\/$/.test(x.getAttribute('href'))).length}; })()''')
    P.ck('출처 200건 이상·링크는 http(s) 또는 같은 사이트의 쪽(../sources/ 등)만', src['rows'] >= 200 and src['bad'] == 0, json.dumps(src))
    P.ev('app.almanac.open("notes")'); P.wait(900)
    t = P.ev('document.querySelector("#modal-root .alm").innerText')
    P.ck('글꼴 실명 표기 (Hahmlet · Pretendard · Yuji Syuku · Noto Serif KR)', all(x in t for x in ['Hahmlet', 'Pretendard', 'Yuji Syuku', 'Noto Serif KR']))
    P.ck("화면에 '추사' 없음", '추사' not in P.ev('document.body.innerText'))
    if not narrow:
        inside = True
        for _ in range(30):
            P.pg.keyboard.press('Tab')
            inside = inside and P.ev('document.querySelector("#modal-root .alm").contains(document.activeElement)')
        P.ck('연감: Tab 이 모달 안에 머묾', inside)
    P.pg.keyboard.press('Escape'); P.wait(300)
    P.ck('연감 닫으면 초점이 연 단추로', P.ev('document.activeElement && document.activeElement.classList.contains("t-almanac")') or narrow, P.ev('document.activeElement.className'))
    P.pg.locator('#map').focus(); P.pg.keyboard.press('?'); P.wait(300)
    P.ck('? 로 도움말', P.ev('!document.querySelector("#modal-root .help").hidden && document.querySelector("#modal-root .help").innerText.length > 200'))
    P.pg.keyboard.press('Escape'); P.wait(250)
    P.ck('Esc 로 도움말 닫힘', P.ev('document.querySelector("#modal-root .help").hidden'))
    # 공유
    P.go('#lens=density&city=12&intro=0')
    if bname == 'chromium':
        try: P.ctx.grant_permissions(['clipboard-read', 'clipboard-write'])
        except Exception: pass
    P.pg.locator('#tools .t-share').click(); P.wait(300)
    P.ck('공유 메뉴 열림 (장이 열려 있어도 닿음)', P.ev('!document.getElementById("sharemenu").hidden'))
    P.pg.locator('#sharemenu [role=menuitem]').first.click(); P.wait(500)
    want = P.ev('location.origin + location.pathname + app.hashString()')
    P.ck('링크 주소 = 지금 해시', P.ev('app.share.url()') == want and 'lens=density' in want and 'city=12' in want)
    if bname == 'chromium' and not narrow:
        clip = None
        try: clip = P.ev('navigator.clipboard.readText()')
        except Exception as e: clip = 'ERR ' + str(e)[:80]
        P.ck('클립보드에 복사된 주소', clip == want, clip)
    for hs, fn in [('#intro=0', 'y_export.png'), ('#lens=top_industry&intro=0', 'y_export_lens.png')]:
        P.go(hs)
        r = P.ev('''(async () => { const b = await app.share.exportPNG('map'); const a = new Uint8Array(await b.arrayBuffer()); let s = ''; for (let i = 0; i < a.length; i += 8192) s += String.fromCharCode.apply(null, a.subarray(i, i + 8192)); return {size: b.size, type: b.type, b64: btoa(s)}; })()''')
        P.ck(f'PNG 내보내기 {hs} > 50 KB', r['size'] > 50000 and r['type'] == 'image/png', f"{r['size']} bytes")
        if save:
            with open(os.path.join(SHOTS, fn), 'wb') as f: f.write(base64.b64decode(r['b64']))

# ---------------------------------------------------------------- 판 바꾸기
def t_edition(P):
    hs = '#v=3000,3000,0.3000&lens=density&city=12&ly=wonders,trade&hide=station'
    P.go(hs)
    P.pg.locator('#edition').click()
    try:
        P.pg.wait_for_url(re.compile(r'/index\.html#'), timeout=10000)
        P.pg.wait_for_function('!location.pathname.includes("/yeojido/") && window.app && document.body.classList.contains("ready")', timeout=20000)
        P.wait(900)
        st = P.ev('({path: location.pathname, lens: app.lens && app.lens.id, city: app.selCity, x: Math.round(app.cam.x), y: Math.round(app.cam.y), s: +app.cam.scale.toFixed(3), trade: app.layerOn && app.layerOn.trade, res: app.layerOn && app.layerOn.resources, st: app.subOff && app.subOff.has("station")})')
        P.ck('다른 판으로: 기존판이 같은 렌즈·고을·자리·층', st['lens'] == 'density' and st['city'] == 12 and abs(st['x'] - 3000) < 3 and abs(st['y'] - 3000) < 3 and st['trade'] is True and st['res'] is False and st['st'] is True, json.dumps(st))
        back = P.ev('location.hash')
    except Exception as e:
        P.ck('다른 판으로: 기존판이 같은 상태', False, str(e).split('\n')[0][:160]); back = hs
    P.go(back)
    st = P.ev('({lens: app.lens && app.lens.id, sel: app.sel, x: Math.round(app.cam.x), trade: app.layerOn.trade, res: app.layerOn.resources, st: app.subOff.has("station")})')
    P.ck('기존판 해시를 신여지도가 그대로 되살림', st['lens'] == 'density' and st['sel'] == {'type': 'city', 'id': 12} and abs(st['x'] - 3000) < 3 and st['trade'] and not st['res'] and st['st'], json.dumps(st))

# ---------------------------------------------------------------- 실패 격리
def t_isolation(browser, port, tag):
    for name in ['trade', 'sources', 'ridges', 'nation']:
        P = Page(browser, port, 1280, 800, f'{tag} {name}.json 막음')
        P.ctx.route(f'**/data/{name}.json', lambda r: r.abort())
        try:
            P.go('#intro=0')
            P.ck('지도는 뜸', P.ev('document.body.classList.contains("is-ready") && !!window.app'))
            perr = [e for e in P.errs if e.startswith('PAGEERROR')]
            P.ck('쪽 오류 없음', not perr, ' | '.join(perr[:2]))
            if name == 'trade':
                P.ck('알림에 trade.json', 'trade' in P.ev('document.getElementById("toast").textContent'))
                P.ev('app.selectCity(12)'); P.wait(400)
                P.ck('고을 장 정상', P.ev('!document.getElementById("panel").hidden && !/NaN|undefined/.test(document.getElementById("panel").innerText)'))
            if name == 'sources':
                P.ev('app.almanac.open("sources")'); P.wait(900)
                P.ck('연감 출처 갈피가 실패를 알림', '불러오지 못' in P.ev('document.querySelector("#modal-root .alm").innerText'))
                P.pg.keyboard.press('Escape')
                r = P.ev('(async () => (await app.share.exportPNG("map")).size)()')
                P.ck('PNG 는 그래도 나옴', r > 50000, r)
            if name == 'ridges':
                P.ck('산줄기 없이 그림', P.ev('app.D.ridges === null && app.lines.ridges.length === 0'))
                P.ck('알림에 ridges.json', 'ridges' in P.ev('document.getElementById("toast").textContent'))
            if name == 'nation':
                P.ev('app.selectCity(12)'); P.wait(400)
                P.ck('nation 없이도 고을 장', P.ev('!document.getElementById("panel").hidden'))
        except Exception as e:
            P.ck('점검 중 예외', False, str(e).split('\n')[0][:200])
        P.close()

# ---------------------------------------------------------------- 접근성
NAMELESS = '''(() => { const bad = []; for (const el of document.querySelectorAll('#sheet button, #sheet a[href], #sheet input, #panel button, #panel a[href], #panel summary, #drawer button, #modal-root button, #modal-root input, #modal-root a[href], .skip')) {
  if (el.offsetParent === null) continue;
  let n = el.getAttribute('aria-label') || el.textContent.trim() || el.getAttribute('title') || '';
  if (!n && el.getAttribute('aria-labelledby')) n = (document.getElementById(el.getAttribute('aria-labelledby')) || {}).innerText || '';
  if (!n && el.id) { const l = document.querySelector('label[for="' + el.id + '"]'); if (l) n = l.innerText.trim(); }
  if (!n && el.closest('label')) n = el.closest('label').innerText.trim();
  if (!n) bad.push(el.tagName + '#' + el.id + '.' + el.className); } return bad; })()'''
BADTEXT = '''(() => { const t = document.getElementById('panel').innerText; const m = t.match(/(^|[^A-Za-z])(NaN|undefined|null|Infinity|\\[object Object\\])([^A-Za-z]|$)/); return [m ? t.slice(Math.max(0, m.index - 30), m.index + 40) : null, t.includes('자료 없음'), t.length, /%EMOJI%/u.test(t)]; })()'''.replace('%EMOJI%', EMOJI)

def t_a11y(P):
    narrow = P.w <= 700
    P.go('#intro=0')
    bad = P.ev(NAMELESS); P.ck('여백의 조작 요소에 이름 있음', not bad, bad[:6])
    if not narrow:
        P.ev('document.body.focus()')
        regions, widths, first = [], [], None
        for k in range(70):
            P.pg.keyboard.press('Tab')
            r = P.ev('''(() => { const a = document.activeElement; if (!a || a === document.body) return null; const c = a.closest('#masthead, #rail, #layers, #foot, #slip, #places, #legend, #key'); const cs = getComputedStyle(a);
              return [a.id === 'map' ? 'map' : a.classList.contains('skip') ? 'skip' : c ? c.id : a.tagName, parseFloat(cs.outlineWidth) || 0, cs.outlineStyle]; })()''')
            if not r: continue
            if first is None: first = r[0]
            regions.append(r[0]); widths.append(r[1] if r[2] != 'none' else 0)
        need = {'masthead', 'rail', 'layers', 'map'}
        P.ck('Tab 으로 장부·갈피·층·지도에 닿음', need <= set(regions), sorted(set(regions)))
        webkit = P.tag.startswith('webkit')  # WebKit 은 기본값으로 Tab 이 링크를 건너뛴다(사파리의 '키보드 탐색' 설정). 그 경우 링크에 직접 초점을 둔다
        if webkit and first != 'skip': out(f'NOTE [{P.tag}] 첫 Tab 이 건너뛰기 링크가 아님({first}) — WebKit 기본 동작(링크는 Option+Tab)')
        else: P.ck('첫 Tab 은 건너뛰기 링크', first == 'skip', first)
        P.ck('초점 테가 보임 (outline > 0)', widths and min(widths) > 0, f'min {min(widths) if widths else None} of {len(widths)}')
        P.go('#intro=0'); P.ev('document.body.focus()')
        if webkit: P.pg.locator('.skip').focus()
        else: P.pg.keyboard.press('Tab')
        P.pg.keyboard.press('Enter'); P.wait(300)
        P.ck('건너뛰기 -> 고을 목록 안으로 초점', P.ev('document.getElementById("places").contains(document.activeElement)'), P.ev('document.activeElement.tagName'))
        P.ev('(() => { const b = [...document.querySelectorAll("#places ul.cities button")].find(b => b.innerText.includes("울산")); b.focus(); })()')
        P.pg.keyboard.press('Enter'); P.wait(800)
        P.ck('목록에서 고을 열기 -> 장 + 초점', P.ev('app.sel.type === "city" && app.sel.id === 12 && document.getElementById("panel").contains(document.activeElement)'), P.ev('document.activeElement.tagName'))
        P.ck('선택 알림(aria-live)', '울산' in P.ev('document.getElementById("live").textContent'))
    else:
        small = P.ev('''(() => { const o = []; for (const el of document.querySelectorAll('#masthead button, #masthead a, #slip a, #rail button, #layers button')) { if (el.offsetParent === null) continue; const r = el.getBoundingClientRect();
          if (r.width < 43.5 || r.height < 43.5) o.push((el.getAttribute('aria-label') || el.innerText.trim() || el.className).slice(0, 14) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height)); } return o; })()''')
        P.ck('390: 여백 조작 요소 44x44 이상', not small, small)
        P.ev('app.selectCity(12)'); P.wait(500)
        small = P.ev('''(() => { const o = []; for (const el of document.querySelectorAll('#panel .pn-close, #panel .pn-handle')) { const r = el.getBoundingClientRect(); if (r.width < 43.5 || r.height < 43.5) o.push(el.className + ' ' + Math.round(r.width) + 'x' + Math.round(r.height)); } return o; })()''')
        P.ck('390: 장 닫기·손잡이 44x44 이상', not small, small)
    # 장마다: 이름 없는 단추·NaN·이모지
    C = J('cities'); ids = {c['name']: c['id'] for c in C}
    small_gun = min((c for c in C if c['kind'] == '군'), key=lambda c: c['population'])
    # 세종: 지역별고용조사에 시군 값이 없어 고용률이 '자료 없음' (공개판은 한우가 빠져 서울의 '자료 없음' 칸이 없다)
    states = [('city', ids[n], n) for n in ['서울', '울산', '전주시', '화성시', '세종', small_gun['name']]]
    kinds = ['airport', 'nuclear', 'world_heritage', 'national_park', 'station', 'gi', 'dam']
    its = P.ev(f'(() => {json.dumps(kinds)}.map(k => (app.layerMap.items.find(i => i.kind === k) || {{}}).id))()')
    seen_na = False
    todo = [(f'#city={i}&intro=0', n) for _, i, n in states] + [('#state=47&intro=0', '경북'), ('#state=12&intro=0', '전남광주'), ('#report=1&intro=0', '전국')] + [(f'#item={i}&intro=0', k) for i, k in zip(its, kinds) if i] + [('#route=41-44&intro=0', '교역로')]
    for hs, nm in todo:
        P.go(hs, wait=450)
        r = P.ev(BADTEXT); nl = P.ev(NAMELESS)
        seen_na = seen_na or r[1]
        P.ck(f'장 {nm}: NaN·undefined·이모지 없음, 단추 이름 있음', r[0] is None and r[2] > 40 and not r[3] and not nl, f'{r[0]!r} len={r[2]} emoji={r[3]} nameless={nl[:3]}')
        P.ck(f'장 {nm}: 가로 넘침 없음', P.ev('document.documentElement.scrollWidth <= innerWidth && document.querySelector("#panel .pn-body").scrollWidth <= document.querySelector("#panel .pn-body").clientWidth + 1'))
    P.ck("빠진 값은 '자료 없음' 으로 적힘 (서울 재정자립도 등)", seen_na)
    for hs in ['#intro=0', '#lens=extinction&intro=0', '#report=population&intro=0']:
        P.go(hs, wait=400); P.ck(f'{hs}: 이모지 없음', not P.ev(f'/{EMOJI}/u.test(document.body.innerText)'))

# ---------------------------------------------------------------- 자료와 맞는가
def t_honesty(P):
    N, C = J('nation'), J('cities')
    pop = next(r for r in N['reports']['items'] if r['id'] == 'population')['national']
    P.go('#intro=0')
    led = P.ev('document.getElementById("ledger").innerText')
    if comma(pop / 1e4) in led:
        P.ck('장부 인구 = nation.json', True)
    else:  # 장부가 접힌 폭: 접힌 단추로 보고서를 열어 본다
        b = P.pg.locator('#ledger button:not([hidden])').first
        (b.tap() if P.w <= 700 else b.click()); P.wait(500)
        t = P.ev('document.getElementById("drawer").innerText')
        P.ck('보고서 인구 = nation.json', comma(pop) in t or comma(pop / 1e4) in t, comma(pop))
    u = next(c for c in C if c['name'] == '울산')
    P.go(f"#city={u['id']}&intro=0")
    t = P.ev('document.getElementById("panel").innerText').replace('\n', ' ')
    miss = []
    if comma(u['population']) not in t: miss.append('인구 ' + comma(u['population']))
    for k in ['food', 'production', 'gold', 'science', 'culture']:
        w = won(u['yields'][k]); num = w[:-1]
        if num not in t: miss.append(f'{k} {w}')
        rk = u['ranks'].get('gdp' if k == 'gold' else k)
        if rk and f'{rk}위' not in t: miss.append(f'{k} {rk}위')
    P.ck('울산 인구·다섯 산출·순위 = cities.json', not miss, miss)
    I = J('infrastructure'); ap = next(i for i in I['items'] if i['kind'] == 'airport')
    P.go(f"#item={ap['id']}&intro=0")
    t = P.ev('document.getElementById("panel").innerText')
    P.ck(f"{ap['name']} 여객 = infrastructure.json", comma(ap['value']) in t or comma(ap['value'] / 1e4) + '만' in t, comma(ap['value']))
    T = J('trade'); sg = T['routes']['segments'][0]
    P.go(f"#route={sg['a']}-{sg['b']}&intro=0")
    t = P.ev('document.getElementById("panel").innerText')
    ok = any(x in t for x in [comma(sg['total']), comma(sg['total'] / 1e4) + '만', comma(sg['ab']), comma(sg['ab'] / 1e4) + '만'])
    P.ck('교역로 톤수 = trade.json', ok, f"{comma(sg['total'])} / {comma(sg['total'] / 1e4)}만")
    if P.w > 700:
        L = J('lenses'); dens = next(l for l in L['lenses'] if l['id'] == 'density')
        P.go('#v=3900,3000,0.8&lens=density&intro=0&ly=')
        q = P.ev('''(() => { const r = app.canvas.getBoundingClientRect(); for (let y = 150; y < app.cam.vh - 100; y += 37) for (let x = 150; x < app.cam.vw - 150; x += 41) {
          const p = app.pick(x, y); if (p.cell >= 0 && app.D.world.owner[p.cell] >= 0) return [r.left + x, r.top + y, p.cell]; } return null; })()''')
        P.pg.mouse.move(q[0] - 3, q[1]); P.pg.mouse.move(q[0], q[1]); P.wait(200)
        if 'values' in dens: v = dens['values'][q[2]]
        else:
            lc = J('world')['cover_share']['land_cells']; v = dens['land_values'][lc.index(q[2])] if q[2] in lc else None
        tip = P.ev('document.getElementById("tip").innerText')
        P.ck('칸 풍선말의 렌즈 값 = lenses.json', (comma(v) in tip) if v is not None else ('자료 없음' in tip), f'{v} / {tip[:80]!r}')

# ---------------------------------------------------------------- 성능
def t_perf(browser, port, w, h, dpr, tag, **kw):
    P = Page(browser, port, w, h, tag, device_scale_factor=dpr, **kw)
    t0 = time.time(); P.go('#intro=0', wait=0, layers=False)
    ready = P.ev('performance.now()'); nav = time.time() - t0
    P.wait(800)
    rec = 'window.__f = []; (function loop(t) { window.__f.push(t); window.__raf = requestAnimationFrame(loop); })(performance.now());'
    stop = '(() => { cancelAnimationFrame(window.__raf); const f = window.__f, d = []; for (let i = 1; i < f.length; i++) d.push(f[i] - f[i - 1]); return d; })()'
    box = P.pg.locator('#map').bounding_box(); cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    P.pg.mouse.move(cx, cy)
    P.ev(rec)
    for k in range(75): P.pg.mouse.wheel(0, -60 if k < 50 else 90); P.wait(40)
    dz = P.ev(stop)
    P.ev(rec)
    P.pg.mouse.down()
    for k in range(60): P.pg.mouse.move(cx + (k % 30 - 15) * 12, cy + (k % 20 - 10) * 9); P.wait(33)
    P.pg.mouse.up()
    dd = P.ev(stop); P.wait(500)
    st = P.ev('''({ink: app.inkPlate.tiles.size, pig: app.pigPlate.tiles.size, lens: app.lensPlate ? app.lensPlate.tiles.size : 0, mb: +((app.inkPlate.bytes + app.pigPlate.bytes) / 1048576).toFixed(1),
      heap: performance.memory ? +(performance.memory.usedJSHeapSize / 1048576).toFixed(1) : null, canvas: [app.canvas.width, app.canvas.height]})''')
    pct = lambda a, q: sorted(a)[min(len(a) - 1, int(len(a) * q))] if a else None
    line = f'PERF [{tag}] 첫 지도까지 {ready:.0f} ms (goto 포함 {nav * 1000:.0f} ms) · 휠 확대 프레임 간격 중앙 {statistics.median(dz):.1f} / p95 {pct(dz, 0.95):.1f} ms ({len(dz)}프레임) · 끌기 중앙 {statistics.median(dd):.1f} / p95 {pct(dd, 0.95):.1f} ms · 조각 먹 {st["ink"]} 채색 {st["pig"]} = {st["mb"]} MB · JS 힙 {st["heap"]} MB · 캔버스 {st["canvas"]}'
    out(line); PERF.append(line)
    P.ck('성능: 휠 확대 중앙 프레임 간격 <= 34 ms (헤드리스 소프트웨어 렌더링)', statistics.median(dz) <= 34, f'{statistics.median(dz):.1f}')
    P.ck('성능: 조각 메모리 <= 96 MB', st['mb'] <= 96, st['mb'])
    P.close()

def t_files():
    hits = []
    for base, _, files in os.walk(os.path.join(ROOT, 'site', 'yeojido')):
        for fn in files:
            if not fn.endswith(('.js', '.css', '.html', '.json', '.svg', '.md', '.txt')): continue
            p = os.path.join(base, fn)
            txt = open(p, encoding='utf-8', errors='ignore').read()
            if '추사' in txt and not fn.endswith('.md'): hits.append(os.path.relpath(p, ROOT))
            if fn.endswith(('.js', '.css', '.html')) and re.search(r'https?://(?!www\.w3\.org)[a-z0-9.-]+\.[a-z]{2,}/[^\s"\']*\.(js|css|woff2?)|cdn\.|googleapis|unpkg|jsdelivr', txt): hits.append('CDN? ' + os.path.relpath(p, ROOT))
            if fn.endswith(('.js', '.css', '.html')) and re.search(r'[Cc]ivilization|시빌라이제이션|문명 ?[0-9VI]', txt): hits.append('wording ' + os.path.relpath(p, ROOT))
    check('files', "코드에 '추사'·CDN·게임 이름 없음", not hits, hits)
    tot = sum(os.path.getsize(os.path.join(DATA, f)) for f in os.listdir(DATA) if f.endswith('.json'))
    check('files', 'site/data/*.json 합계 < 5 MB', tot < 5_000_000, f'{tot:,} bytes')
    check('files', 'ridges.json <= 200 KB', os.path.getsize(os.path.join(DATA, 'ridges.json')) <= 200_000, os.path.getsize(os.path.join(DATA, 'ridges.json')))

def main():
    s, port = serve()
    t_files()
    with sync_playwright() as pw:
        for bname in ['chromium', 'firefox', 'webkit']:
            if ONLY and bname != ONLY: continue
            try: b = getattr(pw, bname).launch()
            except Exception as e:
                check(bname, '브라우저 띄우기', False, str(e)[:120]); continue
            sizes = [(1920, 1080), (1280, 800), (768, 1024), (390, 844)] if bname == 'chromium' else [(1280, 800)]
            for w, h in sizes:
                tag = f'{bname} {w}x{h}'
                mobile = w <= 700
                kw = dict(has_touch=True, is_mobile=True, device_scale_factor=2) if mobile and bname == 'chromium' else {}
                P = Page(b, port, w, h, tag, **kw)
                safe(P, '불러오기', lambda: t_load(P))
                if not mobile:
                    safe(P, '지도 조작', lambda: t_map(P))
                    safe(P, '고르기', lambda: t_select(P))
                else:
                    safe(P, '터치', lambda: t_touch(P))
                safe(P, '산줄기', lambda: t_ridges(P))
                safe(P, '층', lambda: t_layers(P, mouse=not mobile))
                safe(P, '찾기·연감·도움말·공유', lambda: t_modals(P, bname, save=(bname == 'chromium' and w == 1920)))
                safe(P, '접근성', lambda: t_a11y(P))
                safe(P, '자료 대조', lambda: t_honesty(P))
                if not mobile and (w == 1280): safe(P, '판 바꾸기', lambda: t_edition(P))
                real = [e for e in P.errs if 'REQFAIL' not in e or '/data/' in e or '/yeojido/' in e]
                P.ck('전체 과정에서 콘솔 오류 없음', not real, ' | '.join(real[:4]))
                P.close()
            try: t_reduced(b, port, bname)
            except Exception as e: check(bname, '움직임 줄이기 (예외)', False, str(e)[:160])
            if bname == 'chromium':
                t_isolation(b, port, bname)
                try:
                    t_perf(b, port, 1920, 1080, 1, 'chromium 1920x1080 dpr1')
                    t_perf(b, port, 390, 844, 2, 'chromium 390x844 dpr2', has_touch=True, is_mobile=True)
                except Exception as e: check(bname, '성능 (예외)', False, str(e)[:160])
            b.close()
    s.shutdown()
    if not ONLY or ONLY == 'chromium':
        r = subprocess.run([sys.executable, os.path.join(HERE, 'qa_lens.py')], capture_output=True, text=True, encoding='utf-8', errors='replace')
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        fl = [l for l in lines if l.startswith('FAIL')]
        out(f'--- qa_lens.py (갈피·범례·장부·순위, Chromium 네 화면): {len([l for l in lines if l.startswith("ok")])} 통과, {len(fl)} 실패')
        for l in fl: check('qa_lens', l[4:].strip(), False, '')
    out(f'\n=== 실패 {len(FAILS)} / 점검 {len([l for l in LOG if l.startswith(("PASS", "FAIL"))])}')
    for f in FAILS: out('  ' + f)
    for p in PERF: out('  ' + p)
    with open(os.path.join(HERE, 'qa_result.txt'), 'w', encoding='utf-8') as f: f.write('\n'.join(LOG) + '\n')
    sys.exit(min(len(FAILS), 250))

if __name__ == '__main__':
    main()
