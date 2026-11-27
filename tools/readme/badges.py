"""README 배지: site/data 의 실제 값으로 assets/badges/*.svg 를 만든다. 실행: python tools/readme/badges.py"""
import json, pathlib, unicodedata
ROOT = pathlib.Path(__file__).resolve().parents[2]
D, OUT = ROOT / "site/data", ROOT / "assets/badges"
OUT.mkdir(parents=True, exist_ok=True)
J = lambda n: json.load(open(D / f"{n}.json", encoding="utf-8"))

def tw(s):  # 대략의 글자 폭(px, 11px Verdana 기준)
    return sum(11 if unicodedata.east_asian_width(ch) in "WF" else (4 if ch in " .,·" else 7) for ch in s)

def badge(name, label, value, color):
    a, b = tw(label) + 12, tw(value) + 12
    w = a + b
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" viewBox="0 0 {w} 20" role="img" aria-label="{label}: {value}">\n'
           f'<title>{label}: {value}</title><clipPath id="r"><rect width="{w}" height="20" rx="3"/></clipPath>'
           f'<g clip-path="url(#r)"><path fill="#555" d="M0 0h{a}v20H0z"/><path fill="{color}" d="M{a} 0h{b}v20H{a}z"/></g>'
           f'<g fill="#fff" text-anchor="middle" font-family="Verdana,Arial,sans-serif" font-size="11">'
           f'<text x="{a/2}" y="14">{label}</text><text x="{a + b/2}" y="14">{value}</text></g></svg>\n')
    (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")

world, cities, lenses, src = J("world"), J("cities"), J("lenses"), J("sources")
land = sum(1 for o in world["owner"] if o is not None and o >= 0)
badge("editions", "판", "2 · koreaciv / 신여지도", "#8a5a2b")
badge("map", "지도", f"육각 칸 {land:,} · 도시 {len(cities)}", "#3b6e8f")
badge("lenses", "렌즈", f"{len(lenses['lenses'])}종", "#6b5b95")
badge("sources", "출처", f"{len(src['sources'])}건", "#7a6a3a")
badge("stack", "빌드 단계", "없음 · 정적 HTML", "#3a8566")
badge("license", "license", "Apache-2.0", "#3a8566")
print("land", land, "cities", len(cities), "lenses", len(lenses["lenses"]), "sources", len(src["sources"]), "profile", src.get("profile"))
