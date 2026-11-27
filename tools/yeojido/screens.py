"""신여지도 최종 갈무리 — docs/screenshots/y_*.png (Chromium). python tools/yeojido/screens.py [이름 일부]"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from shot import serve
from playwright.sync_api import sync_playwright
OUT = os.path.abspath(os.path.join(HERE, '..', '..', 'docs', 'screenshots'))
FILT = sys.argv[1] if len(sys.argv) > 1 else ''
CITY = "app.D.cities.find(c => c.name === '%s').id"
# (이름, 해시, (w, h, dpr), 연 뒤 실행할 JS 또는 None, 키 입력 등 함수 이름)
D, M = (1920, 1080, 1), (390, 844, 2)
SHOTS = [
    ('y_01_title', '', D, None),
    ('y_02_nation', '#intro=0', D, None),
    ('y_03_mid', '#v=3700,2500,0.33&intro=0', D, None),
    ('y_04_near', '#v=3950,3550,0.85&intro=0', D, None),
    ('y_05_ridge_closeup', '#v=3150,3620,0.62&intro=0&ly=', D, None),
    ('y_06_city_ulsan', '#intro=0', D, f"app.selectCity({CITY % '울산'}, {{fly: true}})"),
    ('y_07_city_jeonju', '#intro=0', D, f"app.selectCity({CITY % '전주시'}, {{fly: true}})"),
    ('y_08_state', '#intro=0', D, "app.selectState('47', {fly: true})"),
    ('y_09_lens_extinction', '#lens=extinction&intro=0', D, None),
    ('y_10_lens_top_industry', '#lens=top_industry&intro=0', D, None),
    ('y_11_report', '#report=gold&intro=0', D, None),
    ('y_12_almanac', '#intro=0', D, "app.almanac.open('terrain')"),
    ('y_12b_almanac_sources', '#intro=0', D, "app.almanac.open('sources')"),
    ('y_13_help', '#intro=0', D, "app.help.open()"),
    ('y_14_search', '#intro=0', D, 'SEARCH'),
    ('y_15_layers', '#v=3300,3300,0.2&ly=wonders,resources,infra,trade,frontier&intro=0', D, "document.querySelector('#layers .lmore').click()"),
    ('y_16_nation_item', '#intro=0', D, "app.selectItem(app.layerMap.items.find(i => i.kind === 'airport' && i.tier === 0), {fly: false})"),
    ('y_17_route', '#route=41-44&intro=0', D, None),
    ('y_20_nation_1280', '#intro=0', (1280, 800, 1), None),
    ('y_21_nation_768', '#intro=0', (768, 1024, 1), None),
    ('y_m1_title', '', M, None),
    ('y_m2_nation', '#intro=0', M, None),
    ('y_m3_city', '#intro=0', M, f"app.selectCity({CITY % '울산'}, {{fly: true}})"),
    ('y_m4_lens', '#lens=extinction&intro=0', M, None),
    ('y_m5_lens_open', '#lens=density&intro=0', M, "document.querySelector('#legend .lg-exp').click()"),
]

def main():
    s, port = serve()
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, hsh, (w, h, dpr), js in SHOTS:
            if FILT and FILT not in name: continue
            ctx = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=dpr, has_touch=w < 700, is_mobile=w < 700)
            pg = ctx.new_page()
            errs = []
            pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
            pg.on('pageerror', lambda e: errs.append('PAGEERROR ' + str(e)))
            pg.goto(f'http://127.0.0.1:{port}/yeojido/index.html{hsh}')
            pg.wait_for_function('document.body.classList.contains("is-ready")', timeout=30000)
            pg.wait_for_function('window.app && app.layerMap', timeout=20000)
            pg.wait_for_timeout(1200)
            if js == 'SEARCH':
                pg.locator('#map').focus(); pg.keyboard.press('/'); pg.wait_for_timeout(300); pg.keyboard.insert_text('경주'); pg.wait_for_timeout(500)
            elif js:
                pg.evaluate(js)
            pg.wait_for_timeout(1700)
            pg.mouse.move(2, 2)
            pg.screenshot(path=os.path.join(OUT, name + '.png'))
            print(name, 'ERR ' + ' | '.join(errs[:2]) if errs else 'ok')
            ctx.close()
        b.close()
    s.shutdown()

if __name__ == '__main__':
    main()
