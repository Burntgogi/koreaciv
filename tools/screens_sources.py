"""출처 쪽(site/sources/) 갈무리와 점검: python tools/screens_sources.py
site/ 를 임시 서버로 띄워 1280·390 폭에서 출처 쪽을 찍고(docs/screenshots/9_*.png), 두 판의 링크로 오가고,
필드를 뺀 sources.json 으로도 오류 없이 그려지는지, 키보드 이동과 인쇄(PDF)를 본다. 결과는 표준 출력에 적는다.
"""
import copy, functools, http.server, json, os, socketserver, sys, tempfile, threading
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
OUT = os.path.join(ROOT, "docs", "screenshots")


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
    pg.on("requestfailed", lambda r: errs.append(f"REQFAIL {r.url} ({r.failure})"))


def shot(pg, name, sel=None):
    if sel:
        pg.locator(sel).first.scroll_into_view_if_needed()
        pg.evaluate(f"document.querySelector({json.dumps(sel)}).scrollIntoView({{block:'start'}})")
        pg.wait_for_timeout(250)
    p = os.path.join(OUT, name)
    pg.screenshot(path=p)
    print("갈무리", os.path.relpath(p, ROOT))


def main():
    os.makedirs(OUT, exist_ok=True)
    s, port = serve()
    base = f"http://127.0.0.1:{port}"
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        # ---- 1280 ----
        ctx = b.new_context(viewport={"width": 1280, "height": 900})
        pg = ctx.new_page(); errs = []; watch(pg, errs)
        pg.goto(base + "/sources/")
        pg.wait_for_function("document.body.classList.contains('is-ready')", timeout=15000)
        pg.wait_for_timeout(400)
        info = pg.evaluate("""() => ({
          items: document.querySelectorAll('li.item').length, pubs: document.querySelectorAll('section.pub').length,
          rcards: document.querySelectorAll('.rcard').length, unknown: document.querySelectorAll('ul.unknown li').length,
          derived: document.querySelectorAll('.dcard').length, fonts: document.querySelectorAll('.fcard').length, other: document.querySelectorAll('.ocard').length,
          count: document.querySelector('.count')?.textContent, cite: document.querySelector('pre.cite')?.textContent.length,
          font: getComputedStyle(document.querySelector('h1')).fontFamily, fontsLoaded: [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family),
          overflowX: document.documentElement.scrollWidth > innerWidth, h: document.documentElement.scrollHeight })""")
        print("1280 그린 것:", info)
        res["1280"] = info
        shot(pg, "9_sources_1280_top.png")
        shot(pg, "9_sources_1280_restricted.png", "#restricted")
        shot(pg, "9_sources_1280_derived.png", "#derived")
        shot(pg, "9_sources_1280_credits.png", "#credits")
        # 거르기: 이용허락 '공공누리 제4유형' + 글자 '세종'
        pg.select_option("#f-lic", label=[o for o in pg.eval_on_selector_all("#f-lic option", "os => os.map(o => o.textContent)") if o.startswith("공공누리 제4유형")][0])
        pg.wait_for_timeout(150)
        c1 = pg.text_content(".count")
        pg.select_option("#f-lic", "")
        pg.fill("#f-q", "토지피복")
        pg.wait_for_timeout(150)
        c2 = pg.text_content(".count")
        shot(pg, "9_sources_1280_list_filtered.png", "#list")
        pg.click(".filters .btn.ghost")
        c3 = pg.text_content(".count")
        print("거르기: 제4유형 →", c1, "| '토지피복' →", c2, "| 처음대로 →", c3)
        # 조건 카드의 제목 링크 → 목록 항목
        pg.fill("#f-q", "없는낱말zz"); pg.wait_for_timeout(100)
        pg.click(".rcard h3 a >> nth=0"); pg.wait_for_timeout(500)
        tgt = pg.evaluate("() => { const el = document.getElementById(decodeURIComponent(location.hash.slice(1))); return el ? {id: el.id, hidden: el.hidden, top: Math.round(el.getBoundingClientRect().top)} : null }")
        print("조건 카드 → 목록 항목 (가려져 있으면 거르기를 푼다):", tgt)
        # 키보드: 첫 Tab 은 건너뛰기 링크, Enter 로 본문
        pg.goto(base + "/sources/"); pg.wait_for_function("document.body.classList.contains('is-ready')")
        seq = []
        for _ in range(6):
            pg.keyboard.press("Tab")
            seq.append(pg.evaluate("() => { const a = document.activeElement; return (a.tagName + ' ' + (a.textContent || a.id || '').trim().slice(0, 24)) + ' outline=' + getComputedStyle(a).outlineStyle }"))
        print("키보드 Tab 순서:", seq)
        pg.goto(base + "/sources/"); pg.wait_for_function("document.body.classList.contains('is-ready')")
        pg.keyboard.press("Tab"); pg.keyboard.press("Enter"); pg.wait_for_timeout(100)
        print("건너뛰기 Enter 뒤 초점:", pg.evaluate("document.activeElement.id"))
        # 복사 단추 (http://127.0.0.1 은 보안 맥락 — 권한을 주고 누른다)
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
        pg.click(".citebar .btn"); pg.wait_for_timeout(200)
        print("복사 단추:", pg.text_content(".copymsg"), "| 클립보드 앞부분:", pg.evaluate("navigator.clipboard.readText()")[:40])
        # 인쇄
        pg.emulate_media(media="print")
        pdf = os.path.join(tempfile.gettempdir(), "koreaciv_sources_print.pdf")
        pg.pdf(path=pdf, format="A4", print_background=False)
        pg.screenshot(path=os.path.join(OUT, "9_sources_print_media.png"))
        print("인쇄 PDF:", os.path.getsize(pdf), "바이트", pdf, "| 인쇄에서 차례 보임:", pg.evaluate("getComputedStyle(document.querySelector('.toc')).display"))
        pg.emulate_media(media="screen")
        print("1280 오류:", errs or "없음")
        ctx.close()

        # ---- 390 ----
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = ctx.new_page(); errs = []; watch(pg, errs)
        pg.goto(base + "/sources/")
        pg.wait_for_function("document.body.classList.contains('is-ready')", timeout=15000)
        pg.wait_for_timeout(400)
        ov = pg.evaluate("() => ({sw: document.documentElement.scrollWidth, iw: innerWidth, wide: [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && getComputedStyle(e).position !== 'absolute').slice(0, 5).map(e => e.tagName + '.' + e.className)})")
        print("390 가로 넘침:", ov)
        shot(pg, "9_sources_390_top.png")
        shot(pg, "9_sources_390_restricted.png", "#restricted")
        shot(pg, "9_sources_390_list.png", "#list")
        pg.evaluate("document.querySelector('#list li.item details.files').open = true")
        shot(pg, "9_sources_390_item.png", "#list li.item")
        shot(pg, "9_sources_390_credits.png", "#credits")
        print("390 오류:", errs or "없음")
        ctx.close()

        # ---- 필드가 빠진 기록으로도 오류 없이 ----
        J = json.load(open(os.path.join(SITE, "data", "sources.json"), encoding="utf-8"))
        M = copy.deepcopy(J)
        for k in ("summary", "cite", "derived", "restriction_kinds", "notes"):
            M.pop(k, None)
        for i, s_ in enumerate(M["sources"]):
            for k in ("license_short", "url", "vintage", "publisher", "used_in", "files", "affects", "group") if i % 3 == 0 else ("license", "license_url", "sha256"):
                s_.pop(k, None)
        for c in M["credits"]:
            c.pop("files", None); c.pop("copyright", None); c.pop("license_file", None)
        ctx = b.new_context(viewport={"width": 1280, "height": 900})
        pg = ctx.new_page(); errs = []; watch(pg, errs)
        pg.route("**/data/sources.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(M, ensure_ascii=False)))
        pg.goto(base + "/sources/")
        pg.wait_for_function("document.body.classList.contains('is-ready')", timeout=15000)
        bad = pg.evaluate("[...document.querySelectorAll('[data-slot] .warn[role=alert]')].length")
        print("필드를 뺀 기록: 항목", pg.evaluate("document.querySelectorAll('li.item').length"), "· 그리지 못한 부분", bad, "· 오류", errs or "없음")
        # 기록을 못 읽을 때
        pg2 = ctx.new_page(); errs2 = []; watch(pg2, errs2)
        pg2.route("**/data/sources.json", lambda r: r.fulfill(status=404, body="no"))
        pg2.goto(base + "/sources/"); pg2.wait_for_timeout(800)
        print("기록 404:", pg2.text_content("[data-slot=summary]").strip()[:60], "| 오류(요청 실패 외):", [e for e in errs2 if "404" not in e and "REQFAIL" not in e] or "없음")
        ctx.close()

        # ---- 두 판에서 오가기 ----
        ctx = b.new_context(viewport={"width": 1280, "height": 900})
        pg = ctx.new_page(); errs = []; watch(pg, errs)
        pg.goto(base + "/index.html#")
        pg.wait_for_function("window.app && window.app.almanac", timeout=30000)
        pg.wait_for_timeout(1500)
        pg.evaluate("window.app.almanac.open('sources')")
        pg.wait_for_selector("#almanac .srcpage a", timeout=10000)
        shot(pg, "9_link_koreaciv_almanac.png")
        url0 = pg.url
        pg.click("#almanac .srcpage a")
        pg.wait_for_function("document.body.classList.contains('is-ready')", timeout=15000)
        cls = pg.evaluate("document.getElementById('back-koreaciv').className")
        print("koreaciv 연감 → 출처 쪽:", pg.url, "| 돌아가기 표시:", cls)
        pg.click("#back-koreaciv"); pg.wait_for_function("window.app && window.app.almanac", timeout=30000)
        print("출처 쪽 → koreaciv:", pg.url, "(처음", url0, ")")
        pg.goto(base + "/yeojido/index.html")
        pg.wait_for_function('document.body.classList.contains("is-ready")', timeout=30000)
        pg.wait_for_timeout(1200)
        pg.evaluate("window.app.almanac.open('sources')")
        pg.wait_for_selector(".alm-body .jump a[href='../sources/']", timeout=10000)
        pg.wait_for_timeout(400)
        shot(pg, "9_link_yeojido_almanac.png")
        foot = pg.evaluate("[...document.querySelectorAll('#foot .credit a')].map(a => a.getAttribute('href') + ' ' + a.textContent)")
        print("신여지도 꼬리 링크:", foot)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        pg.evaluate("window.app.leaveIntro && window.app.leaveIntro()")  # 표지를 걷어야 꼬리(#foot)가 보인다
        pg.wait_for_timeout(1500)
        pg.evaluate("window.app.almanac.close()")
        pg.wait_for_timeout(300)
        hash0 = pg.url
        pg.click("#foot .credit a[href='../sources/']")
        pg.wait_for_function("document.body.classList.contains('is-ready')", timeout=15000)
        print("신여지도 꼬리 → 출처 쪽:", pg.url, "| 돌아가기 표시:", pg.evaluate("document.getElementById('back-yeojido').className"))
        shot(pg, "9_sources_from_yeojido.png")
        pg.click("#back-yeojido")
        pg.wait_for_function('document.body.classList.contains("is-ready")', timeout=30000)
        print("출처 쪽 → 신여지도:", pg.url, "(떠날 때", hash0, ")")
        # 새 창에서 바로 연 출처 쪽의 링크는 그냥 링크
        pg.goto(base + "/sources/"); pg.wait_for_function("document.body.classList.contains('is-ready')")
        print("바로 연 쪽의 링크:", pg.evaluate("[...document.querySelectorAll('.editions a')].map(a => a.getAttribute('href'))"))
        pg.click("#back-yeojido"); pg.wait_for_function('document.body.classList.contains("is-ready")', timeout=30000)
        print("→", pg.url)
        print("오가기 오류:", [e for e in errs if "favicon" not in e] or "없음")
        ctx.close()
        b.close()
    s.shutdown()


if __name__ == "__main__":
    main()
