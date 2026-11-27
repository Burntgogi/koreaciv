#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""신여지도 글꼴 짓기 (다시 돌릴 수 있다).

    python tools/yeojido/build_fonts.py

하는 일
  1. 글자 범위 = KS X 1001 한글 2,350 + ASCII + 기호 + site/data/*.json 의 모든 글자
     + site/yeojido/**/*.{html,js,css} + docs/YEOJIDO.md 의 모든 글자  -> fonts/charset.txt
  2. Hahmlet(제목) · Pretendard(본문; 내부 이름을 'Yeojido Sans' 로 바꾼 수정본) 를 줄여 WOFF2 로
  3. Yuji Syuku 에서 新輿地圖 4자만 -> title-hanja.woff2 + title-hanja.svg (윤곽 그대로)
  4. 한글 낙관 seal.svg / seal-mask.svg (Hahmlet 900 윤곽 + 기하 인변)
  5. fonts.json (연감이 읽는 글꼴 목록), 이용허락 원문 복사
원본은 tools/yeojido/fonts_src/ 에 있다 (없으면 README 의 주소에서 받는다).
글꼴마다 '범위에 있으나 원본에 없는 글자'를 찍는다.
"""
import io
import json
import math
import os
import shutil
import sys

from fontTools import subset
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'tools', 'yeojido', 'fonts_src')
OUT = os.path.join(ROOT, 'site', 'yeojido', 'fonts')
FETCHED = '2026-11-27'

HANJA = '新輿地圖'
SEAL_TEXT = '신여지도'  # 오른쪽 줄 위→아래 신·여, 왼쪽 줄 지·도
CINNABAR = '#B8321F'

SYMBOLS = (
    ' ·…‥—–−‐×÷±≤≥≈≠∼~→←↑↓↔↗↘▲▼◀▶△▽▴▾◂▸○●◎◯□■◆◇◦•※☆★✓✕'
    '℃°′″‰％㎢㎡㎞㎏㏊㎝㎜㎥ℓ№‘’“”「」『』〈〉《》【】〔〕（）［］｛｝、。，．：；？！／～'
    '¹²³⁰⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉½¼¾©®™§¶†‡₩€$£¥µ'
    '①②③④⑤⑥⑦⑧⑨⑩ⅠⅡⅢⅣⅤ⌘⇧⏎␣'
)


def ks_hangul():
    out = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            try:
                out.append(bytes([hi, lo]).decode('euc_kr'))
            except UnicodeDecodeError:
                pass
    return out


def walk_strings(v, acc):
    if isinstance(v, str):
        acc.update(v)
    elif isinstance(v, dict):
        for k, x in v.items():
            acc.update(k)
            walk_strings(x, acc)
    elif isinstance(v, list):
        for x in v:
            walk_strings(x, acc)


def collect_charset():
    cs = set(chr(c) for c in range(0x20, 0x7F))
    cs.update(chr(c) for c in range(0xA0, 0x100))
    cs.update(ks_hangul())
    cs.update(chr(c) for c in range(0x3131, 0x3164))  # 호환 자모 (찾기 입력 중)
    cs.update(SYMBOLS)
    used = set()
    ddir = os.path.join(ROOT, 'site', 'data')
    for fn in sorted(os.listdir(ddir)):
        if not fn.endswith('.json'):
            continue
        try:
            with open(os.path.join(ddir, fn), encoding='utf-8') as f:
                walk_strings(json.load(f), used)
        except Exception as e:  # 다른 작업자가 다시 쓰는 중일 수 있다
            print(f'  ! {fn} 을 읽지 못함: {e}')
    ydir = os.path.join(ROOT, 'site', 'yeojido')
    for base, _dirs, files in os.walk(ydir):
        for fn in files:
            if fn.endswith(('.html', '.js', '.css')) or fn == 'fonts.json':
                with open(os.path.join(base, fn), encoding='utf-8', errors='ignore') as f:
                    used.update(f.read())
    doc = os.path.join(ROOT, 'docs', 'YEOJIDO.md')
    if os.path.exists(doc):
        with open(doc, encoding='utf-8') as f:
            used.update(f.read())
    cs.update(c for c in used if ord(c) >= 0x20 and not (0x7F <= ord(c) < 0xA0))
    cs.discard('﻿')
    return cs, used


def classify(c):
    o = ord(c)
    if 0xAC00 <= o <= 0xD7A3:
        return '한글'
    if 0x3400 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF or o >= 0x20000:
        return '한자'
    if o >= 0x1F000 or 0x2600 <= o <= 0x27BF or o in (0xFE0F, 0x200D):
        return '그림문자'
    return '기호'


def report_missing(label, cmap, charset, used):
    miss = sorted(c for c in charset if ord(c) not in cmap and not c.isspace())
    by = {}
    for c in miss:
        by.setdefault(classify(c), []).append(c)
    print(f'  [{label}] 범위 {len(charset)}자 중 원본에 없는 글자 {len(miss)}자')
    for k, v in by.items():
        mark = ''.join(v)
        print(f'    {k} {len(v)}: {mark[:300]}')
    return {k: ''.join(v) for k, v in by.items()}, [c for c in miss if c in used]


def do_subset(src, dst, charset, features, rename=None):
    font = TTFont(src)
    opts = subset.Options()
    opts.flavor = 'woff2'
    opts.layout_features = features
    opts.name_IDs = ['*']
    opts.name_languages = ['*']
    opts.notdef_outline = True
    opts.glyph_names = False
    opts.drop_tables += ['DSIG']
    opts.hinting = False
    opts.desubroutinize = True
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=[ord(c) for c in charset])
    sub.subset(font)
    if rename:
        rename(font)
    font.flavor = 'woff2'
    font.save(dst)
    return os.path.getsize(dst)


def rename_sans(font):
    """OFL 1.1 제3조: 수정본은 예약 글꼴 이름(Pretendard)을 쓸 수 없다.
    줄인 파일은 수정본이므로 글꼴 이름 레코드를 모두 'Yeojido Sans' 로 바꾼다.
    저작권(0)·상표(7)·디자이너(8,9)·이용허락(13,14) 레코드는 OFL 제2조에 따라 그대로 둔다."""
    fam, ps = 'Yeojido Sans', 'YeojidoSans'
    name = font['name']
    repl = {1: fam, 4: fam, 6: ps + '-Regular', 16: fam, 25: ps,
            3: '1.309;YJD;' + ps + ';subset-' + FETCHED,
            10: 'Modified Version (character subset, renamed) of an OFL-1.1 font by Kil Hyung-jin. '
                'Renamed because the Original Version declares a Reserved Font Name.'}
    for rec in list(name.names):
        if rec.nameID in repl:
            name.removeNames(nameID=rec.nameID, platformID=rec.platformID, platEncID=rec.platEncID, langID=rec.langID)
    for nid, s in repl.items():
        name.setName(s, nid, 3, 1, 0x409)
        name.setName(s, nid, 1, 0, 0)
    for rec in list(name.names):  # fvar 인스턴스의 PostScript 이름 (PretendardVariable-Bold …)
        u = rec.toUnicode()
        if rec.nameID >= 256 and 'pretendard' in u.lower():
            name.setName(u.replace('PretendardVariable', ps).replace('Pretendard', ps), rec.nameID, rec.platformID, rec.platEncID, rec.langID)
    name.names.sort(key=lambda r: (r.platformID, r.platEncID, r.langID, r.nameID))  # 이름 레코드는 정렬돼 있어야 한다 (Firefox 경고)
    bad = [(r.nameID, r.toUnicode()) for r in name.names
           if 'pretendard' in r.toUnicode().lower() and r.nameID not in (0, 7, 8, 9, 11, 12, 13, 14)]
    if bad:
        raise SystemExit(f'이름 레코드에 예약 이름이 남아 있다: {bad}')


def glyph_path(font, gs, ch, dx, dy, sx, sy):
    """글리프 윤곽을 SVG 좌표(y 아래로)로. (x*sx+dx, -y*sy+dy)"""
    gname = font.getBestCmap()[ord(ch)]
    pen = SVGPathPen(gs, ntos=lambda v: str(int(round(v))))
    gs[gname].draw(TransformPen(pen, (sx, 0, 0, -sy, dx, dy)))
    return pen.getCommands()


def glyph_bounds(font, gs, ch):
    gname = font.getBestCmap()[ord(ch)]
    bp = BoundsPen(gs)
    gs[gname].draw(bp)
    return bp.bounds


def build_title_hanja():
    src = os.path.join(SRC, 'cand_yujisyuku', 'YujiSyuku-Regular.ttf')
    font = TTFont(src)
    cmap = font.getBestCmap()
    for ch in HANJA:
        if ord(ch) not in cmap:
            raise SystemExit(f'Yuji Syuku 에 {ch} 가 없다')
    gs = font.getGlyphSet()
    upm = font['head'].unitsPerEm
    gap = round(upm * 0.06)
    paths, y = [], 0
    x0, x1 = 1e9, -1e9
    for ch in HANJA:
        bx0, by0, bx1, by1 = glyph_bounds(font, gs, ch)
        # 글자마다 윗변을 y 에 맞춰 쌓는다 (세로 한 줄)
        paths.append((ch, bx0, bx1, by0, by1, y))
        y += (by1 - by0) + gap
        x0, x1 = min(x0, bx0), max(x1, bx1)
    h = y - gap
    cx = (x0 + x1) / 2
    w = x1 - x0
    ds = []
    for ch, bx0, bx1, by0, by1, top in paths:
        # 가로는 글자 중심을 줄 중심에 맞춘다
        dx = cx - (bx0 + bx1) / 2 - x0
        ds.append(glyph_path(font, gs, ch, dx, top + by1, 1, 1))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w/10:.0f}" height="{h/10:.0f}" role="img" aria-label="新輿地圖">'
           f'<title>新輿地圖</title>'
           f'<!-- 윤곽: Yuji Syuku Regular (The Yuji Project Authors, SIL OFL 1.1) 의 U+65B0 U+8F3F U+5730 U+5716. tools/yeojido/build_fonts.py 가 만든다. -->'
           + ''.join(f'<path d="{d}"/>' for d in ds) + '</svg>\n')
    with open(os.path.join(OUT, 'title-hanja.svg'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(svg)
    size = do_subset(src, os.path.join(OUT, 'title-hanja.woff2'), set(HANJA), ['vert', 'vrt2'])
    return size, (w, h)


def build_seal():
    """한글 낙관 (백문: 인주 바탕에 흰 글자). Hahmlet 900 윤곽, 칸을 채우게 늘리고,
    글자 가장자리를 둥근 획으로 살짝 불려 칼맛을 낸다. 인변은 정해진 수열로 흔든 다각형 (난수 없음)."""
    vf = TTFont(os.path.join(SRC, 'hahmlet', 'Hahmlet-wght.ttf'))
    font = instancer.instantiateVariableFont(vf, {'wght': 900})
    gs = font.getGlyphSet()
    S = 1000
    pad, gut = 70, 30          # 인변 두께, 글자 사이
    cell = (S - 2 * pad - gut) / 2
    # 칸 자리: 오른쪽 줄 위·아래 = 신·여, 왼쪽 줄 위·아래 = 지·도
    pos = [(1, 0), (1, 1), (0, 0), (0, 1)]
    glyphs = []
    for ch, (cxi, cyi) in zip(SEAL_TEXT, pos):
        bx0, by0, bx1, by1 = glyph_bounds(font, gs, ch)
        gw, gh = bx1 - bx0, by1 - by0
        # 새긴 글자처럼 칸을 가득 채운다 (가로·세로를 따로 늘린다. 한쪽이 다른 쪽의 1.45배를 넘지 않게)
        sx, sy = cell / gw, cell / gh
        lim = 1.45
        if sx > sy * lim:
            sx = sy * lim
        if sy > sx * lim:
            sy = sx * lim
        ox = pad + cxi * (cell + gut) + (cell - gw * sx) / 2
        oy = pad + cyi * (cell + gut) + (cell - gh * sy) / 2
        glyphs.append(glyph_path(font, gs, ch, ox - bx0 * sx, oy + by1 * sy, sx, sy))

    # 인변: 변마다 9점, 사인 두 겹으로 ±7 흔들고 모서리는 둥글린다
    def wob(i, k):
        return 3.5 * math.sin(i * 1.7 + k * 2.3) + 2.5 * math.sin(i * 0.9 + k * 5.1 + 1.3)

    pts, n, r = [], 9, 26
    m = 14  # 바깥 여백
    for k in range(4):
        for i in range(n):
            t = i / (n - 1)
            a = m + r + (S - 2 * m - 2 * r) * t
            d = m + wob(i, k)
            pts.append([(a, d), (S - d, a), (S - a, S - d), (d, S - a)][k])
    # 닫힌 Catmull-Rom -> 3차 베지에
    d = []
    L = len(pts)
    for i in range(L):
        p0, p1, p2, p3 = pts[(i - 1) % L], pts[i], pts[(i + 1) % L], pts[(i + 2) % L]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        if i == 0:
            d.append(f'M{p1[0]:.1f} {p1[1]:.1f}')
        d.append(f'C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}')
    border = ''.join(d) + 'Z'
    # 떨어져 나간 자국 (인변의 이, 정해진 자리 다섯 곳)
    chips = [(4, 318, 11, 18), (S - 5, 644, 10, 15), (724, 5, 19, 9), (238, S - 6, 21, 9), (S - 20, 28, 13, 12)]
    chip_svg = ''.join(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}"/>' for x, y, rx, ry in chips)
    gl = ''.join(f'<path d="{g}"/>' for g in glyphs)

    def make(fill, note):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="200" height="200" role="img" aria-label="신여지도 낙관">'
                f'<title>신여지도</title><!-- {note} -->'
                f'<defs><mask id="m" maskUnits="userSpaceOnUse" x="0" y="0" width="{S}" height="{S}">'
                f'<rect width="{S}" height="{S}" fill="#fff"/>'
                f'<g fill="#000" stroke="#000" stroke-width="5" stroke-linejoin="round">{gl}</g>'
                f'<g fill="#000">{chip_svg}</g></mask></defs>'
                f'<path d="{border}" fill="{fill}" mask="url(#m)"/></svg>\n')

    note = '한글 낙관(백문). 글자 윤곽: Hahmlet 900 (The Hahmlet Project Authors, SIL OFL 1.1). 인변은 기하 계산. tools/yeojido/build_fonts.py 가 만든다.'
    with open(os.path.join(OUT, 'seal.svg'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(make(CINNABAR, note))
    with open(os.path.join(OUT, 'seal-mask.svg'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(make('#000', note + ' (마스크용 검정판)'))


def main():
    os.makedirs(OUT, exist_ok=True)
    charset, used = collect_charset()
    with open(os.path.join(OUT, 'charset.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(''.join(sorted(charset)))
    print(f'글자 범위 {len(charset)}자 (자료·화면에 실제로 나온 글자 {len(used)}자)')

    hah = os.path.join(SRC, 'hahmlet', 'Hahmlet-wght.ttf')
    pre = os.path.join(SRC, 'pretendard', 'PretendardVariable.ttf')
    for p in (hah, pre):
        if not os.path.exists(p):
            raise SystemExit(f'원본이 없다: {p} (site/yeojido/fonts/README.md 의 주소에서 받는다)')

    miss = {}
    m, used_miss_serif = report_missing('Hahmlet', TTFont(hah, lazy=True).getBestCmap(), charset, used)
    miss['Hahmlet'] = m
    m, used_miss_sans = report_missing('Pretendard(Yeojido Sans)', TTFont(pre, lazy=True).getBestCmap(), charset, used)
    miss['Yeojido Sans'] = m
    both = sorted(set(used_miss_serif) & set(used_miss_sans))
    print(f'  두 글꼴 모두에 없고 실제로 쓰인 글자 {len(both)}자: {"".join(both)[:300]}')

    s1 = do_subset(hah, os.path.join(OUT, 'Hahmlet-VF.subset.woff2'), charset,
                   ['kern', 'mark', 'mkmk', 'ccmp', 'locl', 'liga', 'calt', 'case', 'tnum', 'lnum', 'pnum', 'rvrn'])
    s2 = do_subset(pre, os.path.join(OUT, 'YeojidoSans-VF.subset.woff2'), charset,
                   ['kern', 'mark', 'mkmk', 'ccmp', 'locl', 'calt', 'case', 'tnum', 'pnum', 'ss06', 'zero', 'rlig', 'cpsp'],
                   rename=rename_sans)
    # 자료에 나오는 한자(왕릉 이름 등)는 두 글꼴에 없다 -> Noto Serif KR 에서 그 글자만
    noto = os.path.join(SRC, 'notoserifkr', 'NotoSerifKR-wght.ttf')
    hanja = set(c for c in charset if classify(c) == '한자') | set(HANJA) | set('年鑑')
    ncm = TTFont(noto, lazy=True).getBestCmap()
    nmiss = ''.join(sorted(c for c in hanja if ord(c) not in ncm))
    print(f'  [Noto Serif KR] 한자 {len(hanja)}자 중 없는 글자: {nmiss or "없음"}')
    do_subset(noto, os.path.join(OUT, 'NotoSerifKR-VF.hanja.woff2'), hanja, ['kern', 'ccmp', 'locl'])
    s3, dim = build_title_hanja()
    build_seal()

    # 확인: 가변 축·tnum·이름
    for fn, need in (('Hahmlet-VF.subset.woff2', 'Hahmlet'), ('YeojidoSans-VF.subset.woff2', 'Yeojido Sans')):
        f = TTFont(os.path.join(OUT, fn))
        ax = [(a.axisTag, a.minValue, a.maxValue) for a in f['fvar'].axes]
        feats = sorted({r.FeatureTag for r in f['GSUB'].table.FeatureList.FeatureRecord})
        fam = f['name'].getDebugName(1)
        assert 'tnum' in feats, fn
        assert fam == need, (fn, fam)
        print(f'  {fn}: {os.path.getsize(os.path.join(OUT, fn)):,} B · 축 {ax} · 이름 "{fam}" · GSUB {feats} · 글리프 {f["maxp"].numGlyphs}')
    f = TTFont(os.path.join(OUT, 'title-hanja.woff2'))
    print(f'  title-hanja.woff2: {s3:,} B · {"".join(chr(c) for c in sorted(f.getBestCmap()))} · svg {dim[0]:.0f}×{dim[1]:.0f}')

    for a, b in ((os.path.join(SRC, 'hahmlet', 'OFL.txt'), 'Hahmlet-OFL.txt'),
                 (os.path.join(SRC, 'pretendard', 'LICENSE'), 'YeojidoSans-Pretendard-OFL.txt'),
                 (os.path.join(SRC, 'notoserifkr', 'OFL.txt'), 'NotoSerifKR-OFL.txt'),
                 (os.path.join(SRC, 'cand_yujisyuku', 'OFL.txt'), 'YujiSyuku-OFL.txt')):
        shutil.copyfile(a, os.path.join(OUT, b))

    def size(fn):
        return os.path.getsize(os.path.join(OUT, fn))

    fonts = [
        {'role': '제목 · 고을 이름 · 큰 숫자', 'css_family': 'Hahmlet', 'family_shown': 'Hahmlet (함렛)',
         'author': 'The Hahmlet Project Authors — 함민주(한글), Mark Frömberg(라틴) / Hypertype',
         'licence': 'SIL Open Font License 1.1', 'reserved_font_name': None, 'licence_file': 'Hahmlet-OFL.txt',
         'source_url': 'https://github.com/google/fonts/tree/main/ofl/hahmlet', 'source_ref': 'google/fonts c1eda92 (2026-03-03), Version 1.002',
         'fetched': FETCHED, 'file': 'Hahmlet-VF.subset.woff2', 'bytes': size('Hahmlet-VF.subset.woff2'),
         'note': '가변 글꼴(굵기 100–900)을 쓰는 글자만 남겨 줄였다. 예약 글꼴 이름이 없어 이름을 그대로 둔다.'},
        {'role': '본문 · 표 · 단추', 'css_family': 'Yeojido Sans', 'family_shown': 'Pretendard Variable 1.309 의 수정본 (내부 이름 Yeojido Sans)',
         'author': '길형진 (Kil Hyung-jin). 바탕: Inter (The Inter Project Authors), Source Han Sans (Adobe), M PLUS 1 (The M+ FONTS Project Authors)',
         'licence': 'SIL Open Font License 1.1', 'reserved_font_name': "Pretendard, Source, Inter, M PLUS 1",
         'licence_file': 'YeojidoSans-Pretendard-OFL.txt',
         'source_url': 'https://github.com/orioncactus/pretendard', 'source_ref': 'orioncactus/pretendard 7aeb069 (2025-06-28), packages/pretendard/dist/public/variable/PretendardVariable.ttf, Version 1.309',
         'fetched': FETCHED, 'file': 'YeojidoSans-VF.subset.woff2', 'bytes': size('YeojidoSans-VF.subset.woff2'),
         'note': '글자를 줄인 파일은 OFL 의 수정본이고 원본에 예약 글꼴 이름이 있어, 글꼴 안의 이름을 Yeojido Sans 로 바꿨다 (OFL 제3조). 저작권·이용허락 표시는 그대로 두었다.'},
        {'role': '자료 속 한자 (문화유산 이름 등)', 'css_family': 'Yeojido Hanja', 'family_shown': 'Noto Serif KR',
         'author': 'Adobe · Google (Source Han Serif 의 Noto 판)', 'licence': 'SIL Open Font License 1.1', 'reserved_font_name': None,
         'licence_file': 'NotoSerifKR-OFL.txt', 'source_url': 'https://github.com/google/fonts/tree/main/ofl/notoserifkr',
         'source_ref': 'google/fonts main (2026-11-27 받음), NotoSerifKR[wght].ttf, Version 2.003',
         'fetched': FETCHED, 'file': 'NotoSerifKR-VF.hanja.woff2', 'bytes': size('NotoSerifKR-VF.hanja.woff2'),
         'note': '자료와 화면에 나오는 한자만 남겼다. CSS 에서는 unicode-range 로 한자에만 쓰인다 (@font-face 이름 Yeojido Hanja 는 CSS 별칭이고 글꼴 안 이름은 그대로다).'},
        {'role': '제호 곁글 한자 新輿地圖', 'css_family': None, 'family_shown': 'Yuji Syuku Regular',
         'author': 'The Yuji Project Authors — 글씨 片岡佑之(Kataoka Yuji), Kinuta Font Factory',
         'licence': 'SIL Open Font License 1.1', 'reserved_font_name': None, 'licence_file': 'YujiSyuku-OFL.txt',
         'source_url': 'https://github.com/google/fonts/tree/main/ofl/yujisyuku', 'source_ref': 'google/fonts main (2026-11-27 받음), YujiSyuku-Regular.ttf',
         'fetched': FETCHED, 'file': 'title-hanja.svg', 'bytes': size('title-hanja.svg'),
         'note': '붓글씨 해서 글꼴에서 네 글자의 윤곽만 뽑았다 (title-hanja.woff2 는 같은 네 글자의 기록용 서브셋). 특정 서예가의 글씨를 본뜬 것이 아니다.'},
        {'role': '낙관 (한글 「신여지도」)', 'css_family': None, 'family_shown': 'Hahmlet 900 윤곽 + 계산한 인변',
         'author': 'The Hahmlet Project Authors (글자 윤곽)', 'licence': 'SIL Open Font License 1.1', 'reserved_font_name': None,
         'licence_file': 'Hahmlet-OFL.txt', 'source_url': 'https://github.com/google/fonts/tree/main/ofl/hahmlet', 'source_ref': '위와 같음',
         'fetched': FETCHED, 'file': 'seal.svg', 'bytes': size('seal.svg'),
         'note': '한자 전서 낙관은 쓰지 않았다: 열린 이용허락의 소전 글꼴에서 네 글자를 모두 확인하지 못했다 (README 참고).'},
    ]
    with open(os.path.join(OUT, 'fonts.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'built': FETCHED, 'fonts': fonts, 'missing': miss,
                   'missing_used_in_both': ''.join(both)}, f, ensure_ascii=False, indent=1)
    total = sum(size(x) for x in ('Hahmlet-VF.subset.woff2', 'YeojidoSans-VF.subset.woff2', 'NotoSerifKR-VF.hanja.woff2', 'title-hanja.svg', 'seal.svg'))
    print(f'화면이 받는 글꼴·제호·낙관 합계 {total:,} B')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
