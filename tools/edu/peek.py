"""수업안 사실 확인용: site/data 에서 도시·시도·렌즈 값을 뽑아 본다. (읽기만 한다)
실행: python tools/edu/peek.py city 9 42 ...  |  python tools/edu/peek.py name 화성 안동  |  python tools/edu/peek.py top <lens> [n]
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def ld(n):
    return json.load(open(os.path.join(ROOT, 'site', 'data', n + '.json'), encoding='utf-8'))
W = ld('world'); C = ld('cities'); S = ld('states'); L = ld('lenses')
CI = {c['code']: i for i, c in enumerate(W['counties'])}
LENS = {l['id']: l for l in L['lenses']}
def lens_city(lid, c):
    l = LENS.get(lid)
    if not l or 'by_county' not in l: return None
    v = [l['by_county'][CI[k]] for k in c['sgg'] if k in CI]
    v = [x for x in v if x is not None]
    return (min(v), max(v)) if v else None
def city_line(c):
    out = [f"#{c['id']} {c['full']} pop={c['population']:,} g5={c['growth_5y']} o65={c['age']['over65']} ext={c['extinction_index']}({c['extinction_stage']})"]
    out.append(f"   gdp_pc={c.get('gdp_per_capita')} wage={(c.get('wage') or {}).get('per_filer')} fiscal={c.get('fiscal_independence')} emp={(c.get('employment') or {}).get('rate')} ranks={c.get('ranks')}")
    g = c.get('gdp_by_industry') or {}
    if g.get('gva'):
        sh = sorted(((k, v / g['gva'] * 100) for k, v in g.items() if v and k not in ('gva', 'grdp', 'net_taxes')), key=lambda x: -x[1])[:4]
        out.append('   industry ' + ', '.join(f'{k} {v:.1f}%' for k, v in sh) + f" undisclosed={c.get('gdp_undisclosed')}")
    out.append('   lens ' + ' '.join(f"{lid}={lens_city(lid, c)}" for lid in LENS if 'by_county' in LENS[lid] and LENS[lid]['scale'] != 'category'))
    out.append(f"   peers={[next(x['name'] for x in C if x['id']==p) for p in c.get('peers', [])]} tags={[t.get('txt') for t in c.get('tags', [])]}")
    return '\n'.join(out)
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'city':
        for i in a[1:]:
            print(city_line(next(c for c in C if c['id'] == int(i))))
    elif a[0] == 'name':
        for n in a[1:]:
            for c in C:
                if n in c['full']: print(city_line(c))
    elif a[0] == 'top':
        lid = a[1]; n = int(a[2]) if len(a) > 2 else 5
        rows = [(lens_city(lid, c), c['full'], c['id']) for c in C]
        rows = [r for r in rows if r[0]]
        rows.sort(key=lambda r: r[0][1])
        print('lowest', rows[:n]); print('highest', rows[-n:][::-1])
    elif a[0] == 'rank':
        key = a[1]; n = int(a[2]) if len(a) > 2 else 5
        rows = sorted(C, key=lambda c: c['ranks'].get(key, 999))[:n]
        print([(c['ranks'].get(key), c['full'], c['id']) for c in rows])
