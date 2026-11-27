"""갈피·범례·장부·순위 보고서 점검 (실제 포인터·키보드 입력). python tools/yeojido/qa_lens.py [outdir]"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shot import serve
from playwright.sync_api import sync_playwright

OUT = sys.argv[1] if len(sys.argv) > 1 else None
SIZES = [(1920, 1080), (1280, 800), (768, 1024), (390, 844)]
fails = []
def check(name, ok, info=''):
    print(('ok  ' if ok else 'FAIL'), name, info)
    if not ok: fails.append(name)

def run():
    s, port = serve()
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w, hgt in SIZES:
            tag = f'{w}x{hgt}'
            ctx = b.new_context(viewport={'width': w, 'height': hgt}, has_touch=w < 700, is_mobile=w < 700)
            pg = ctx.new_page()
            errs = []
            pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
            pg.on('pageerror', lambda e: errs.append('PAGEERROR ' + str(e)))
            def go(h):
                pg.goto(f'http://127.0.0.1:{port}/yeojido/index.html{h}')
                pg.wait_for_function('document.body.classList.contains("is-ready")', timeout=20000)
                pg.wait_for_timeout(700)
            def shot(n):
                if OUT: pg.screenshot(path=os.path.join(OUT, f'{n}_{w}.png'))
            noscroll = lambda: pg.evaluate('document.documentElement.scrollWidth <= innerWidth')
            go('#intro=0')
            check(f'{tag} 가로 넘침 없음', noscroll())
            # 장부: 한 줄, 넘침 없음, 여덟 보고서 모두 닿음
            led = pg.evaluate('''(() => { const el = document.getElementById('ledger'); const f = [...el.querySelectorAll('.fig:not([hidden])')];
              const tops = new Set(f.map(x => Math.round(x.getBoundingClientRect().top / 24))); const r = el.getBoundingClientRect();
              return {n: f.length, rows: tops.size, over: f.some(x => x.getBoundingClientRect().right > r.right + 1), tools: document.getElementById('tools').getBoundingClientRect().left, right: r.right}; })()''')
            check(f'{tag} 장부 한 줄·넘침 없음', led['rows'] <= 1 and not led['over'] and led['right'] <= led['tools'] + 1, json.dumps(led))
            pg.locator('#ledger .fig:not([hidden])').first.click()
            pg.wait_for_timeout(350)
            check(f'{tag} 보고서 열림', pg.evaluate('!document.getElementById("drawer").hidden && document.querySelectorAll("#drawer .rtab").length') == 8)
            check(f'{tag} 보고서 안 초점', pg.evaluate('document.getElementById("drawer").contains(document.activeElement)'))
            # 키보드로 여덟 갈래 돌기
            seen = set()
            for _ in range(8):
                seen.add(pg.evaluate('app.masthead.reportId()'))
                pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(60)
            check(f'{tag} 여덟 보고서 키보드 전환', len(seen) == 8, str(sorted(seen)))
            check(f'{tag} 보고서 가로 넘침 없음', noscroll() and pg.evaluate('(() => { const d = document.getElementById("drawer"); return d.scrollWidth <= d.clientWidth + 1; })()'))
            shot('report')
            check(f'{tag} 해시에 report', 'report=' in pg.evaluate('(app.writeHash(true), location.hash)'))
            # 행 Enter -> 장 열림, 보고서 닫힘
            pg.locator('#drawer .rrow.city').first.focus()
            pg.keyboard.press('Enter'); pg.wait_for_timeout(500)
            check(f'{tag} 행 Enter -> 고을 선택', pg.evaluate('app.sel.type === "city" && document.getElementById("drawer").hidden'))
            pg.evaluate('app.clearSelection()')
            pg.locator('#ledger .fig:not([hidden])').first.click(); pg.wait_for_timeout(250)
            pg.keyboard.press('Escape'); pg.wait_for_timeout(250)
            check(f'{tag} Esc 로 보고서 닫힘', pg.evaluate('document.getElementById("drawer").hidden && app.masthead.reportId() === null'))
            # 갈피 -> 메뉴 -> 렌즈 (키보드)
            pg.locator('#rail .tab').nth(1).focus()
            pg.keyboard.press('Enter'); pg.wait_for_timeout(250)
            check(f'{tag} 메뉴 열림·초점', pg.evaluate('!document.getElementById("flyout").hidden && document.getElementById("flyout").contains(document.activeElement)'))
            shot('flyout')
            pg.keyboard.press('ArrowDown'); pg.keyboard.press('ArrowDown'); pg.keyboard.press('ArrowUp'); pg.keyboard.press('Enter'); pg.wait_for_timeout(700)
            check(f'{tag} 키보드로 렌즈 켬', pg.evaluate('app.lens && app.lens.id') == pg.evaluate('app.D.lenses.groups[0].lenses[1].id'))
            check(f'{tag} 초점이 갈피로 돌아옴', pg.evaluate('document.activeElement.classList.contains("tab")'))
            check(f'{tag} 범례 보임', pg.evaluate('!document.getElementById("legend").hidden'))
            pg.locator('#rail .tab').nth(1).click(); pg.wait_for_timeout(200)
            pg.keyboard.press('Escape'); pg.wait_for_timeout(200)
            check(f'{tag} Esc 로 메뉴 닫힘', pg.evaluate('document.getElementById("flyout").hidden'))
            # 연속 렌즈: 끌어서 범위
            go('#lens=density&intro=0')
            if w <= 700:
                check(f'{tag} 범례 한 줄 리본', pg.evaluate('document.getElementById("legend").getBoundingClientRect().height') <= 46)
                shot('ribbon')
                pg.locator('#legend .lg-exp').tap(); pg.wait_for_timeout(300)
            box = pg.locator('#legend .hist').bounding_box()
            y = box['y'] + box['height'] / 2
            pg.mouse.move(box['x'] + box['width'] * 0.55, y); pg.mouse.down()
            pg.mouse.move(box['x'] + box['width'] * 0.7, y, steps=4); pg.mouse.move(box['x'] + box['width'] * 0.9, y, steps=4); pg.mouse.up()
            pg.wait_for_timeout(500)
            r = pg.evaluate('app.lensRange && [app.lensRange.lo, app.lensRange.hi]')
            check(f'{tag} 끌어서 범위 고름', r is not None and r[0] in (19, 20) and r[1] in (32, 33), str(r))
            check(f'{tag} 선택 칸 수 표시', '칸' in (pg.evaluate('document.querySelector("#legend .lg-sel").textContent') or ''))
            shot('range')
            # 키보드 손잡이
            pg.locator('#legend .thumb[data-which="lo"]').focus()
            pg.keyboard.press('ArrowRight'); pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(200)
            r2 = pg.evaluate('[app.lensRange.lo, app.lensRange.hi]')
            check(f'{tag} 화살표 키로 범위', r2[0] == r[0] + 2, str(r2))
            pg.locator('#legend .lg-sel .clear').click(); pg.wait_for_timeout(200)
            check(f'{tag} 풀기', pg.evaluate('app.lensRange === null'))
            # 범주 렌즈: 단계 단추, 관측 범주 전부
            go('#lens=top_industry&intro=0')
            if w <= 700: pg.locator('#legend .lg-exp').tap(); pg.wait_for_timeout(300)
            n = pg.evaluate('''(() => { const l = app.lens, v = app.lensui.statsOf(l); return [document.querySelectorAll('#legend .chip').length, [...v.steps].filter(x => x > 0).length]; })()''')
            check(f'{tag} 관측 범주 전부 범례에', n[0] == n[1] and n[0] > 0, str(n))
            pg.locator('#legend .chip').nth(0).click(); pg.locator('#legend .chip').nth(2).click(); pg.wait_for_timeout(400)
            check(f'{tag} 단계 두 개 고름', pg.evaluate('app.lensRange && app.lensRange.set.size') == 2)
            shot('category')
            check(f'{tag} 범례가 도판 안', pg.evaluate('''(() => { const a = document.getElementById('legend').getBoundingClientRect(), b = document.getElementById('plate').getBoundingClientRect(); return a.left >= b.left && a.right <= b.right + 1 && a.top >= b.top - 1 && a.bottom <= b.bottom + 1; })()'''))
            pg.locator('#legend .x').click(); pg.wait_for_timeout(300)
            check(f'{tag} 범례 닫기 -> 지형', pg.evaluate('app.lens === null && document.getElementById("legend").hidden'))
            go('#lens=extinction&intro=0'); shot('extinction')
            check(f'{tag} 끝까지 가로 넘침 없음', noscroll())
            check(f'{tag} 콘솔 오류 없음', not errs, ' | '.join(errs[:3]))
            ctx.close()
        b.close()
    s.shutdown()
    print('\n실패', len(fails), fails)

run()
