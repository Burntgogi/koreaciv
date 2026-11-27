"""신여지도 갈무리 도우미: python tools/yeojido/shot.py <out.png> <hash> [w h] [--wait ms] [--js "..."] [--dpr n]
site/ 를 임시 서버로 띄워 yeojido/ 를 연다."""
import sys, os, threading, http.server, socketserver, functools, time
from playwright.sync_api import sync_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'site')

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

def serve():
    h = functools.partial(Q, directory=os.path.abspath(ROOT))
    socketserver.ThreadingTCPServer.request_queue_size = 128  # 기본 5 는 요청이 몰리면 연결을 거부한다
    s = socketserver.ThreadingTCPServer(('127.0.0.1', 0), h)
    s.daemon_threads = True
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, s.server_address[1]

def main():
    a = sys.argv[1:]
    out, hsh = a[0], a[1]
    w, hgt = (int(a[2]), int(a[3])) if len(a) > 3 and a[2].isdigit() else (1920, 1080)
    wait = int(a[a.index('--wait') + 1]) if '--wait' in a else 900
    js = a[a.index('--js') + 1] if '--js' in a else None
    dpr = float(a[a.index('--dpr') + 1]) if '--dpr' in a else 1
    s, port = serve()
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': w, 'height': hgt}, device_scale_factor=dpr, has_touch=w < 700, is_mobile=w < 700)
        pg = ctx.new_page()
        errs = []
        pg.on('console', lambda m: errs.append(m.text) if m.type in ('error', 'warning') else None)
        pg.on('pageerror', lambda e: errs.append('PAGEERROR ' + str(e)))
        pg.on('requestfailed', lambda r: errs.append('REQFAIL ' + r.url))
        pg.goto(f'http://127.0.0.1:{port}/yeojido/index.html{hsh}')
        pg.wait_for_function('document.body.classList.contains("is-ready") || document.querySelector("#loader.is-error")', timeout=20000)
        pg.wait_for_timeout(wait)
        if js:
            r = pg.evaluate(js)
            if r is not None: print('JS:', r)
            pg.wait_for_timeout(wait)
        pg.screenshot(path=out)
        for e in errs[:20]: print('ERR', e)
        b.close()
    s.shutdown()

if __name__ == '__main__':
    main()
