"""교육의 활용 쪽(site/edu/) 갈무리와 점검: python tools/edu/screens.py [--no-maps]
site/ 를 임시 서버로 띄워 1280·390 폭에서 쪽을 찍고(docs/screenshots/11_*.png), 거르기·닻·키보드·값 읽기·인쇄 꼴·
내용을 못 읽었을 때·렌즈가 없는 판을 흉내 냈을 때를 본다. 결과는 표준 출력과 tools/edu/screens_result.json 에 적는다.
"""
import functools, http.server, json, os, socketserver, sys, threading
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(ROOT, "site")
OUT = os.path.join(ROOT, "docs", "screenshots")
ONE = {"e34": "e34-01", "e56": "e56-03", "m": "m-03", "h": "h-02"}


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    s = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(Q, directory=SITE))
    s.daemon_threads = True
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, s.server_address[1]


def watch(pg, errs):
    pg.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
    pg.on("requestfailed", lambda r: errs.append(f"REQFAIL {r.url}"))


def shot(pg, name, sel=None, full=False):
    if sel:
        pg.evaluate(f"document.querySelector({json.dumps(sel)}).scrollIntoView({{block:'start'}})")
        pg.wait_for_timeout(250)
    p = os.path.join(OUT, name)
    pg.screenshot(path=p, full_page=full)
    print("갈무리", os.path.relpath(p, ROOT))


def ready(pg, url):
    pg.goto(url)
    pg.wait_for_function("document.body.classList.contains('is-ready')", timeout=15000)
    pg.wait_for_function("document.body.classList.contains('lenses-known') || document.body.classList.contains('lenses-unknown')", timeout=20000)
    pg.wait_for_timeout(400)


def main():
    maps = "--no-maps" not in sys.argv
    os.makedirs(OUT, exist_ok=True)
    s, port = serve()
    base = f"http://127.0.0.1:{port}"
    res = {"profile": json.load(open(os.path.join(SITE, "data", "world.json"), encoding="utf-8")).get("build_profile", "full")}
    content = json.load(open(os.path.join(SITE, "edu", "content.json"), encoding="utf-8"))
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w, hgt in ((1280, 900), (390, 844)):
            ctx = b.new_context(viewport={"width": w, "height": hgt}, device_scale_factor=1 if w == 1280 else 2)
            pg = ctx.new_page(); errs = []; watch(pg, errs)
            ready(pg, base + "/edu/")
            info = pg.evaluate("""() => ({
              lessons: document.querySelectorAll('details.lesson').length, quick: document.querySelectorAll('#quick .card').length,
              projects: document.querySelectorAll('#projects .card').length, stds: document.querySelectorAll('table.std tbody tr').length,
              glossary: document.querySelectorAll('#glossary dl > div').length, opens: document.querySelectorAll('a.btn[data-edition]').length,
              absent: document.querySelectorAll('.btn.absent').length, overflow: document.documentElement.scrollWidth - window.innerWidth,
              font: getComputedStyle(document.querySelector('h1')).fontFamily, loaded: [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family),
              h1: document.querySelector('h1').textContent, caveat0: document.querySelector('ul.caveats li').textContent.slice(0, 60) })""")
            res[f"info_{w}"] = info
            shot(pg, f"11_edu_top_{w}.png")
            shot(pg, f"11_edu_start_{w}.png", "#start")
            shot(pg, f"11_edu_index_{w}.png", "#lessons")
            for lv, lid in ONE.items():
                pg.evaluate(f"location.hash = '#{lid}'")
                pg.wait_for_timeout(350)
                assert pg.evaluate(f"document.getElementById('{lid}').open"), lid
                shot(pg, f"11_edu_lesson_{lv}_{w}.png")
                if w == 1280 and lv == "m":
                    pg.screenshot(path=os.path.join(OUT, "11_edu_lesson_m_full_1280.png"), clip=pg.evaluate(
                        f"(() => {{ const r = document.getElementById('{lid}').getBoundingClientRect(); return {{x: 0, y: r.top + scrollY, width: innerWidth, height: Math.min(r.height + 20, 5000)}}; }})()"), full_page=True)
                    print("갈무리 docs/screenshots/11_edu_lesson_m_full_1280.png")
                pg.evaluate(f"document.getElementById('{lid}').open = false")
            shot(pg, f"11_edu_quick_{w}.png", "#quick")
            shot(pg, f"11_edu_guide_{w}.png", "#guide")
            shot(pg, f"11_edu_sensitive_{w}.png", "#sensitive")
            shot(pg, f"11_edu_glossary_{w}.png", "#glossary")
            shot(pg, f"11_edu_curriculum_{w}.png", "#curriculum")
            res[f"overflow_after_{w}"] = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            res[f"console_{w}"] = errs[:]
            if w == 1280:
                # 거르기
                pg.select_option("#f-level", "h"); pg.wait_for_timeout(100)
                res["filter_h"] = pg.evaluate("[...document.querySelectorAll('details.lesson')].filter(d => !d.hidden).map(d => d.id)")
                res["filter_count"] = pg.inner_text(".count")
                pg.select_option("#f-theme", "data"); pg.wait_for_timeout(100)
                res["filter_h_data"] = pg.evaluate("[...document.querySelectorAll('details.lesson')].filter(d => !d.hidden).map(d => d.id)")
                # 걸러진 수업안의 닻으로 가면 거르기를 풀고 편다
                pg.evaluate("location.hash = '#e34-02'"); pg.wait_for_timeout(300)
                res["anchor_unfilters"] = pg.evaluate("(() => { const d = document.getElementById('e34-02'); return !d.hidden && d.open; })()")
                pg.evaluate("document.getElementById('e34-02').open = false")
                # 키보드: 수업안 제목에 초점을 두고 Enter 로 편다
                pg.focus("#e56-01 > summary"); pg.keyboard.press("Enter"); pg.wait_for_timeout(150)
                res["keyboard_open"] = pg.evaluate("document.getElementById('e56-01').open")
                res["focus_outline"] = pg.evaluate("getComputedStyle(document.querySelector('#e56-01 > summary')).outlineStyle")
                res["e56_01_classic_disabled"] = pg.evaluate("document.querySelectorAll('#e56-01 [aria-disabled=true]').length")
                # Tab 으로 닿는 순서의 처음 몇 개
                pg.evaluate("document.activeElement.blur(); window.scrollTo(0,0)")
                order = []
                for _ in range(8):
                    pg.keyboard.press("Tab")
                    order.append(pg.evaluate("(document.activeElement.textContent || '').trim().slice(0, 18)"))
                res["tab_order"] = order
                # 값 읽기
                pg.evaluate("location.hash = '#h-02'"); pg.wait_for_timeout(300)
                pg.click("#h-02 .loadbtn"); pg.wait_for_selector("#h-02 table.facts", timeout=30000)
                res["facts_h02"] = pg.evaluate("[...document.querySelectorAll('#h-02 table.facts tr')].map(r => r.innerText.replace(/\\s+/g, ' '))")
                res["facts_note"] = pg.inner_text("#h-02 .factbox .out p")
                shot(pg, "11_edu_facts_1280.png", "#h-02 .factbox")
                pg.evaluate("location.hash = '#e56-04'"); pg.wait_for_timeout(300)
                pg.click("#e56-04 .loadbtn"); pg.wait_for_selector("#e56-04 table.facts", timeout=30000)
                res["facts_e5604"] = pg.evaluate("[...document.querySelectorAll('#e56-04 table.facts tr')].map(r => r.innerText.replace(/\\s+/g, ' '))")
                res["console_after_facts"] = errs[:]
                # 인쇄: 수업안 하나
                pg.evaluate("window.print = () => {}")
                for lid in ("e34-02", "h-02"):
                    pg.evaluate(f"location.hash = '#{lid}'"); pg.wait_for_timeout(200)
                    pg.click(f"#{lid} .bar button")
                    pg.emulate_media(media="print")
                    pg.set_viewport_size({"width": 794, "height": 1123})
                    pg.wait_for_timeout(200)
                    res[f"print_{lid}"] = pg.evaluate("({sheets: document.querySelectorAll('#printsheet .sheet').length, visibleMain: getComputedStyle(document.querySelector('main')).display, lines: document.querySelectorAll('#printsheet .lines i').length})")
                    pg.screenshot(path=os.path.join(OUT, f"11_edu_print_{lid}.png"), full_page=True)
                    print(f"갈무리 docs/screenshots/11_edu_print_{lid}.png")
                    pdf = os.path.join(ROOT, "tools", "edu", f"print_{lid}.pdf")
                    pg.pdf(path=pdf, format="A4", margin={"top": "15mm", "bottom": "15mm", "left": "14mm", "right": "14mm"})
                    res[f"print_pdf_bytes_{lid}"] = os.path.getsize(pdf)
                    try:
                        import pymupdf
                        d = pymupdf.open(pdf); res[f"print_pages_{lid}"] = d.page_count
                        for i in range(d.page_count):
                            d[i].get_pixmap(dpi=60).save(os.path.join(OUT, f"11_edu_print_{lid}_p{i + 1}.png"))
                        d.close()
                    except Exception as e:
                        res[f"print_pages_{lid}"] = "pymupdf 없음: " + str(e)[:40]
                    os.remove(pdf)
                    pg.emulate_media(media="screen")
                    pg.set_viewport_size({"width": w, "height": hgt})
                    pg.evaluate("window.dispatchEvent(new Event('afterprint'))")
                    res[f"print_cleanup_{lid}"] = pg.evaluate("!document.body.classList.contains('print-one') && document.querySelectorAll('#printsheet .sheet').length === 0")
            ctx.close()

        # ---- 내용을 못 읽었을 때 ----
        ctx = b.new_context(viewport={"width": 1280, "height": 900})
        pg = ctx.new_page(); errs = []; watch(pg, errs)
        pg.route("**/edu/content.json", lambda r: r.fulfill(status=404, body="no"))
        pg.goto(base + "/edu/"); pg.wait_for_function("document.body.classList.contains('is-failed')", timeout=10000)
        res["fail_message"] = pg.inner_text("[data-slot=about]")
        res["fail_errors"] = [e for e in errs if "404" not in e]
        shot(pg, "11_edu_failed_1280.png")
        ctx.close()
        # ---- 깨진 JSON ----
        ctx = b.new_context(viewport={"width": 1280, "height": 900})
        pg = ctx.new_page(); errs = []; watch(pg, errs)
        pg.route("**/edu/content.json", lambda r: r.fulfill(status=200, content_type="application/json", body="{ broken"))
        pg.goto(base + "/edu/"); pg.wait_for_function("document.body.classList.contains('is-failed')", timeout=10000)
        res["broken_json_errors"] = errs[:]
        ctx.close()
        # ---- 렌즈가 빠진 판 흉내: lenses.json 에서 렌즈 둘을 뺀다 ----
        ctx = b.new_context(viewport={"width": 1280, "height": 900})
        pg = ctx.new_page(); errs = []; watch(pg, errs)
        L = json.load(open(os.path.join(SITE, "data", "lenses.json"), encoding="utf-8"))
        L["lenses"] = [l for l in L["lenses"] if l["id"] not in ("doctors", "growth")]
        pg.route("**/data/lenses.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(L, ensure_ascii=False)))
        ready(pg, base + "/edu/#h-02")
        res["absent_sim"] = pg.evaluate("({absent: document.querySelectorAll('.btn.absent').length, live: document.querySelectorAll('a.btn[data-lens=doctors], a.btn[data-lens=growth]').length, h02: [...document.querySelectorAll('#h-02 .bar .opens .btn')].map(x => x.innerText.replace(/\\s+/g,' '))})")
        pg.click("#h-02 .loadbtn"); pg.wait_for_selector("#h-02 table.facts", timeout=30000)
        res["absent_sim_facts"] = pg.evaluate("[...document.querySelectorAll('#h-02 table.facts tr')].map(r => r.innerText.replace(/\\s+/g, ' ')).slice(0, 3)")
        res["absent_sim_errors"] = errs[:]
        shot(pg, "11_edu_absent_lens_1280.png")
        ctx.close()
        # ---- 렌즈 목록을 못 받았을 때 ----
        ctx = b.new_context(viewport={"width": 1280, "height": 900})
        pg = ctx.new_page(); errs = []; watch(pg, errs)
        pg.route("**/data/lenses.json", lambda r: r.abort())
        pg.goto(base + "/edu/"); pg.wait_for_function("document.body.classList.contains('lenses-unknown')", timeout=10000)
        res["no_lens_list"] = pg.evaluate("({links: document.querySelectorAll('a.btn[data-edition]').length, lessons: document.querySelectorAll('details.lesson').length})")
        ctx.close()

        # ---- 두 판에서 이 쪽으로, 이 쪽에서 두 판·출처로 ----
        ctx = b.new_context(viewport={"width": 1280, "height": 800})
        pg = ctx.new_page(); errs = []; watch(pg, errs)
        ready(pg, base + "/edu/")
        res["back_links"] = pg.evaluate("[...document.querySelectorAll('.editions a, .colophon a')].map(a => a.getAttribute('href'))")
        codes = {}
        for href in ("../", "../yeojido/", "../sources/", "content.json"):
            r = pg.request.get(base + "/edu/" + href); codes[href] = r.status
        res["back_status"] = codes
        if maps:
            lid = "m-03"
            pg.evaluate(f"location.hash = '#{lid}'"); pg.wait_for_timeout(300)
            for ed, ready_js in (("classic", "window.app && window.app.layers"), ("yeojido", "window.app && window.app.layerMap")):
                try:
                    with ctx.expect_page() as np:
                        pg.click(f"#{lid} .bar a.btn[data-edition={ed}]")
                    mp = np.value; merr = []; watch(mp, merr)
                    mp.wait_for_function(ready_js, timeout=30000); mp.wait_for_timeout(1200)
                    res[f"open_{ed}"] = {"url": mp.url.replace(base, ""), "errors": merr}
                    mp.screenshot(path=os.path.join(OUT, f"11_edu_open_{ed}.png"))
                    print(f"갈무리 docs/screenshots/11_edu_open_{ed}.png")
                    mp.close()
                except Exception as e:
                    res[f"open_{ed}"] = {"failed": str(e)[:200]}
        ctx.close()
        b.close()
    s.shutdown()
    json.dump(res, open(os.path.join(ROOT, "tools", "edu", "screens_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
