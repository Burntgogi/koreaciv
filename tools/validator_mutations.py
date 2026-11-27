"""감사 13 대응 증거 (docs/AUDIT_RESPONSE.md): 메모리에서만 자료를 바꿔 검증 함수가 실패하는지 본다. 파일은 바꾸지 않는다.

site/data 의 빌드 판(sources.json profile: full 전체판 / public 공개판)에 따라, 그 판에 없는 자리를 바꾸는 변이는 까닭을 적고 건너뛴다.
공개판이 빼야 할 것을 되살리는 변이(X3–X8)는 공개판에서만, 전체판 기록 변이(X2)는 전체판에서만 돈다.

실행: python tools/validator_mutations.py [옛 validate.py 경로]
옛 검증기 경로를 주면 같은 변이로 옛 판정도 함께 적는다 (감사 대응 전 사본으로 한 번 돌린 결과가 AUDIT_RESPONSE.md 에 있다).
"""
import contextlib, copy, io, json, os, runpy, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
NEW = runpy.run_path(os.path.join(ROOT, "pipeline", "validate.py"))
OLD = runpy.run_path(sys.argv[1]) if len(sys.argv) > 1 else None
D = {n: json.load(open(os.path.join(ROOT, "site", "data", n + ".json"), encoding="utf-8")) for n in
     ("world", "cities", "states", "nation", "lenses", "sources", "wonders", "resources", "infrastructure")}
PROFILE = (D["sources"].get("profile") or {}).get("profile", "full")
FULL, PUB = {"full"}, {"public"}

def to_values(lenses, world):
    """옛 검증기는 칸 렌즈를 values 로 읽는다 — land_values 를 펼친 사본"""
    L = copy.deepcopy(lenses)
    lc = world["cover_share"]["land_cells"]
    for l_ in L["lenses"]:
        if "land_values" in l_ and l_["id"] in ("density", "over65", "extinction", "pm25", "heritage"):
            v = [None] * len(world["owner"])
            for t, i in enumerate(lc):
                v[i] = l_["land_values"][t]
            l_["values"] = v
            del l_["land_values"]
    return L

def run(mod, fn, prefix, data, old=False):
    files = {os.path.normcase(os.path.join(ROOT, "site", "data", n + ".json")): data[n] for n in data}
    G = mod[fn].__globals__  # run_path 가 돌려준 사전은 사본이라 함수의 실제 전역에 바꿔 끼운다
    orig = G["load_json"]
    def lj(p):
        k = os.path.normcase(os.path.abspath(p))
        if k in files:
            return copy.deepcopy(files[k])
        return orig(p)
    G["load_json"] = lj
    del G["results"][:]
    args = {"validate_6": ("world", "cities", "states", "nation", "lenses"), "validate_econ": ("world", "cities", "lenses"),
            "validate_layers": ("world", "cities", "lenses"), "validate_5b_terrain": ("world", "states", "nation"),
            "validate_7b": ("world", "cities", "states", "nation", "lenses"), "validate_sources_page": (),
            "validate_profile": ("world", "cities", "states", "nation", "lenses"), "validate_landcover": ("world", "lenses"),
            "validate_5b_layers": ("world", "lenses")}[fn]
    a = [data[x] for x in args]
    if old and "lenses" in args:
        a[args.index("lenses")] = to_values(data["lenses"], data["world"])
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            mod[fn](*a)
        r = [x for x in G["results"] if x[0].startswith(prefix)]
        res = ("통과" if r[-1][1] else "실패") if r else "검사 없음"
        det = r[-1][2] if r else ""
    except Exception as e:
        res, det = f"오류 {type(e).__name__}: {e}"[:120], ""
    finally:
        G["load_json"] = orig
    return res, det

def mut(f):
    d = copy.deepcopy(D)
    f(d)
    return d

def find(lst, **kw):
    return next(x for x in lst if all(x.get(k) == v for k, v in kw.items()))

def rep(d, rid):
    return find(d["nation"]["reports"]["items"], id=rid)

cases = [
 ("F4", "validate_6", "F4.", "인구 보고서 도시 1위(서울) 행 9,279,861 → 0", lambda d: rep(d, "population")["modes"][0]["cities"]["top"][0].__setitem__("value", 0)),
 ("F4", "validate_6", "F4.", "고령 보고서 전국값 22.15 → 0", lambda d: rep(d, "over65").__setitem__("national", 0)),
 ("F4", "validate_6", "F4.", "생산 1인당 모드 시도 1위 값 × 2 (첫 모드가 아닌 모드)", lambda d: rep(d, "production")["modes"][1]["sido"][0].__setitem__("value", rep(d, "production")["modes"][1]["sido"][0]["value"] * 2)),
 ("E4", "validate_econ", "E4.", "칸 렌즈 '인구밀도'의 육지 칸 값을 모두 null", lambda d: find(d["lenses"]["lenses"], id="density").__setitem__("land_values", [None] * len(find(d["lenses"]["lenses"], id="density")["land_values"]))),
 ("L6", "validate_layers", "L6.", "resources.json precision_counts county 570 → 999", lambda d: d["resources"]["precision_counts"].__setitem__("county", 999)),
 ("T3", "validate_5b_terrain", "T3.", "world.cover_share 의 숲 비율을 모두 0", lambda d: d["world"]["cover_share"].__setitem__("forest", [0 if v is not None else None for v in d["world"]["cover_share"]["forest"]])),
 ("T6", "validate_5b_terrain", "T6.", "nation official_compare 공식 GRDP 를 절반으로 (적어 둔 ratio 는 그대로)", lambda d: d["nation"]["nation"]["official_compare"]["grdp"].__setitem__("official", d["nation"]["nation"]["official_compare"]["grdp"]["official"] / 2)),
 ("T9", "validate_5b_terrain", "T9.", "수원시 GRDP 증가율 21.46 → 26.46", lambda d: find(d["cities"], name="수원시")["gdp_growth"].__setitem__("rate", 26.46)),
 ("T10", "validate_5b_terrain", "T10.", "전국 공식 식량 산출을 0 으로 (원표에는 0 행이 없음)", lambda d: d["nation"]["nation"]["official"]["gdp"]["yields"].__setitem__("food", 0)),
 ("F5", "validate_6", "F5.", "osm-water 출처의 sha256 한 글자 바꿈", lambda d: find(d["sources"]["sources"], key="osm-water").__setitem__("sha256", "0" + find(d["sources"]["sources"], key="osm-water")["sha256"][1:])),
 ("F5", "validate_6", "F5.", "대학 주소 출처 file 을 감사 전 경로(layers/universities.csv)로", lambda d: find(d["sources"]["sources"], key="data-15107736-univ-address").__setitem__("file", "layers/universities.csv")),
 ("F5", "validate_6", "F5.", "관세 묶음 출처의 파일별 기록(files) 삭제", lambda d: find(d["sources"]["sources"], key="customs-trade-sgg-2025").pop("files")),
 ("F7", "validate_6", "F7.", "합계출산율 렌즈의 공표 단위 기록(units) 삭제", lambda d: find(d["lenses"]["lenses"], id="fertility").pop("units")),
 ("F8", "validate_6", "F8.", "출처 줄 규칙에서 합계출산율 렌즈 삭제", lambda d: d["sources"]["attribution"]["lenses"].pop("fertility")),
 ("F8", "validate_6", "F8.", "지도 바탕 출처 줄에서 토지피복 도엽 통계(data-15150509) 삭제", lambda d: d["sources"]["attribution"]["base"].remove("data-15150509")),
 ("F9", "validate_6", "F9.", "부산 도시의 범위 문구 삭제", lambda d: find(d["cities"], name="부산").pop("scope")),
 # 7b (docs/ideas/site_r3.md): 새 공용 계산
 ("G1", "validate_7b", "G1.", "화성시 제조업 입지계수 2.6 → 2.7", lambda d: find(d["cities"], name="화성시")["lq_gdp"].__setitem__("manufacturing", 2.7)),
 ("G1", "validate_7b", "G1.", "광업이 비공개인 도시(울릉군)에 광업 입지계수 1.0 을 넣음", lambda d: find(d["cities"], name="울릉군")["lq_gdp"].__setitem__("mining", 1.0)),
 ("G2", "validate_7b", "G2.", "화성시 특성 표시를 3개로 (5년 인구 +15.8% 더함)", lambda d: find(d["cities"], name="화성시")["tags"].append({"t": "pop", "k": "growth_5y", "v": 15.75, "txt": "5년 인구 +15.8%"})),
 ("G2", "validate_7b", "G2.", "익산시에 반올림하면 1.5 가 되는 보건업(×1.46) 표시를 넣음 (반올림 뒤 판정 흉내)", lambda d: find(d["cities"], name="익산시")["tags"].insert(0, {"t": "ind", "k": "health", "lq": 1.46, "sh": 7.9, "nat": 5.4, "small": False, "yr_diff": False, "txt": "보건·사회복지 비중 ×1.5"})),
 ("G2", "validate_7b", "G2.", "화성시 표시 문구를 '제조업 특화 도시 ×2.6' 으로 (평가하는 말)", lambda d: find(d["cities"], name="화성시")["tags"][0].__setitem__("txt", "제조업 특화 도시 ×2.6")),
 ("G3", "validate_7b", "G3.", "전국 기준 고령 비율 22.15 → 22.1 (반올림한 값)", lambda d: d["nation"]["nation"]["benchmarks"]["metrics"]["over65"].__setitem__("v", 22.1)),
 ("G3", "validate_7b", "G3.", "순위 분모 수출 165 → 167", lambda d: d["nation"]["nation"]["benchmarks"]["rank_denominators"].__setitem__("export", 167)),
 ("G3", "validate_7b", "G3.", "고용률 도시 중앙값 66.5 → 66.0", lambda d: d["nation"]["nation"]["benchmarks"]["metrics"]["employment"].__setitem__("v", 66.0)),
 ("G4", "validate_7b", "G4.", "화성시 첫 닮은 도시 근거의 가까운 두 축을 [인구, 고령]으로", lambda d: find(d["cities"], name="화성시")["peer_reasons"][0].__setitem__("same", ["pop", "age"])),
 ("G4", "validate_7b", "G4.", "울릉군(거래 3건) 첫 근거에 매매가 2배 차이를 넣음", lambda d: find(d["cities"], name="울릉군")["peer_reasons"][0].__setitem__("diff", ["home", 2.0])),
 ("G5", "validate_7b", "G5.", "추천 시점 '인구 1위' 대상을 부산으로", lambda d: find(d["nation"]["presets"]["items"], id="top_pop").__setitem__("city", 1)),
 ("G5", "validate_7b", "G5.", "추천 시점 하나를 손으로 고른 것(kind=editorial)으로", lambda d: d["nation"]["presets"]["items"][2].__setitem__("kind", "editorial")),
 ("G6", "validate_7b", "G6.", "배치 우선군 ②(공항·무역항) 삭제", lambda d: d["wonders"]["zoom"]["draw_priority"].pop("second")),
 ("G6", "validate_7b", "G6.", "데스크톱 아이콘 예산 24 → 52 (규칙 문장은 그대로)", lambda d: d["wonders"]["zoom"]["budget"].__setitem__("icons_desktop", 52)),
 ("G7", "validate_7b", "G7.", "부산 짧은 범위 문구에서 기장군 삭제", lambda d: find(d["cities"], name="부산").__setitem__("scope_label", "자치구 15곳 합")),
 # 출처 쪽·NOTICE.md (site/sources/, pipeline/build_notice.py)
 ("S1", "validate_sources_page", "S1.", "관세 출처의 기관(publisher)을 빈 값으로", lambda d: find(d["sources"]["sources"], key="customs-trade-sgg-2025").__setitem__("publisher", "")),
 ("S1", "validate_sources_page", "S1.", "착안(usaciv) 표기의 이용허락 필드 삭제", lambda d: find(d["sources"]["credits"], key="inspiration-usaciv").pop("license")),
 ("S2", "validate_sources_page", "S2.", "Hahmlet 글꼴 기록 삭제 (실린 woff2 의 이용허락 기록이 없어짐)", lambda d: d["sources"]["credits"].remove(find(d["sources"]["credits"], key="font-hahmlet-vf"))),
 ("S2", "validate_sources_page", "S2.", "Yeojido Sans 의 예약 글꼴 이름 기록을 비움", lambda d: find(d["sources"]["credits"], key="font-yeojidosans-vf").__setitem__("reserved_font_name", None)),
 ("S3", "validate_sources_page", "S3.", "건강 지수 규칙 문장을 '네 지표의 평균' 으로 바꿈", lambda d: find(d["sources"]["derived"], key="derived-health-index").__setitem__("rule", "네 지표의 평균")),
 ("S3", "validate_sources_page", "S3.", "산줄기 입력에서 SRTM30+ 표고 삭제", lambda d: find(d["sources"]["derived"], key="derived-ridges")["inputs"].remove("terrain_srtm30plus")),
 ("S4", "validate_sources_page", "S4.", "보건복지부 기초생활 수급(공공누리 제4유형)의 제한 분류 삭제", lambda d: find(d["sources"]["sources"], key="mohw-welfare-2025").pop("restriction_kinds")),
 ("S4", "validate_sources_page", "S4.", "토지피복 도엽 통계에 API 약관 분류(api_terms)를 붙임", lambda d: find(d["sources"]["sources"], key="data-15150509").__setitem__("restriction_kinds", ["api_terms"])),
 ("S5", "validate_sources_page", "S5.", "미확인 출처 하나를 'CC BY 4.0' 으로 바꿈 (NOTICE.md 는 그대로)", lambda d: find(d["sources"]["sources"], key="airkorea-stations").update(license="CC BY 4.0", license_short="CC BY 4.0")),
 ("S6", "validate_sources_page", "S6.", "출처 쪽이 읽는 'derived' 묶음 삭제", lambda d: d["sources"].pop("derived")),
 ("S6", "validate_sources_page", "S6.", "출처 하나에서 license_short 필드 삭제", lambda d: find(d["sources"]["sources"], key="osm-water").pop("license_short")),
 # 빌드 판 (공개판이 빼는 것 — pipeline/lib/profile.py EXCLUDE), 감사 04·05
 ("X1", "validate_profile", "X1.", "sources.json 의 판 이름만 다른 판으로 바꿈 (world.json·렌즈 기록은 그대로)", lambda d: d["sources"]["profile"].__setitem__("profile", "full" if PROFILE == "public" else "public")),
 ("X1", "validate_profile", "X1.", "뺀 묶음 기록에서 한우 묶음 삭제", lambda d: d["sources"]["profile"]["excluded"].pop(2)),
 ("X2", "validate_profile", "X2.", "전체판 기록에서 '내부 열람용' 문구를 지움", lambda d: d["sources"]["profile"].__setitem__("statement", "공개 배포해도 된다"), FULL),
 ("X3", "validate_profile", "X3.", "피복 출처 이름을 옛 WMS 이름으로 바꿈", lambda d: d["world"]["cover_src"]["names"].__setitem__(0, "기후에너지환경부 토지피복지도 중분류 2025")),
 ("X3", "validate_profile", "X3.", "숲 종류(forest_kind) 기록을 지움", lambda d: d["world"].pop("forest_kind")),
 ("X3", "validate_profile", "X3.", "WMS 토지피복 출처 기록을 sources.json 에 되살림", lambda d: d["sources"]["sources"].append({"key": "landcover-me-wms-lv2-2025y", "title": "토지피복 WMS", "publisher": "x"})),
 ("X3", "validate_profile", "X3.", "공항 종류 출처에 인천공항 AIP 를 넣음", lambda d: d["infrastructure"]["kinds"]["airport"]["source"].append({"key": "incheon-aip"})),
 # 칸 토지피복 (두 판 공용, 세분류 토지피복지도 도엽 통계 — validate_landcover)
 ("C1s", "validate_landcover", "C1s.", "피복 기록의 도엽 행 규칙 문장(cover_meta.sheets.rule)을 '2023년 행을 쓴다'로", lambda d: d["world"]["cover_meta"]["sheets"].__setitem__("rule", "도엽마다 2023년 기준 행을 쓴다.")),
 ("C2s", "validate_landcover", "C2s.", "육지 칸 하나의 숲 비율(정수 %)을 +7", lambda d: d["world"]["cover_share"]["forest"].__setitem__(1000, (d["world"]["cover_share"]["forest"][1000] or 0) + 7)),
 ("C2s", "validate_landcover", "C2s.", "침엽수림 비율 열을 모두 0 으로", lambda d: d["world"]["cover_share"].__setitem__("conifer", [0 if v is not None else None for v in d["world"]["cover_share"]["conifer"]])),
 ("C3s", "validate_landcover", "C3s.", "숲 종류가 붙은 첫 칸의 종류를 다른 것으로", lambda d: d["world"]["forest_kind"]["kind"].__setitem__(0, (d["world"]["forest_kind"]["kind"][0] + 1) % 3)),
 ("C3s", "validate_landcover", "C3s.", "도엽 통계 칸 하나의 출처를 ESA 로", lambda d: d["world"]["cover_src"]["src"].__setitem__(1000, 1)),
 ("C4s", "validate_landcover", "C4s.", "숲 렌즈의 육지 칸 값 하나를 100 으로", lambda d: find(d["lenses"]["lenses"], id="forest")["land_values"].__setitem__(1000, 100.0)),
 ("C5s", "validate_landcover", "C5s.", "치우침 문장의 전국 산림 숫자를 71.3% 로 (옛 공개판 값)", lambda d: d["world"]["cover_meta"].__setitem__("bias_note", d["world"]["cover_meta"]["bias_note"].replace("산림 57.1%", "산림 71.3%"))),
 ("C5s", "validate_landcover", "C5s.", "저장한 전국 대조 값에서 논 차이를 +5%p 로", lambda d: d["world"]["cover_meta"]["compare"]["nation"]["paddy"].__setitem__("diff_pp", 5.0)),
 ("C7s", "validate_landcover", "C7s.", "칸 비율 열에 미분류(unclassified, WMS 투명 픽셀) 열 이름을 되살림", lambda d: d["world"]["cover_share"]["keys"].append("unclassified")),
 ("C7s", "validate_landcover", "C7s.", "출처 줄 지도 바탕에 WMS key 를 넣음", lambda d: d["sources"]["attribution"]["base"].append("landcover-me-wms-lv2-2025y")),
 ("C7s", "validate_landcover", "C7s.", "피복 '근거' 규칙 문장에 'WMS 50 m 그림에서 센 값' 을 넣음", lambda d: d["world"]["tables"]["cover"][8].__setitem__("rule", d["world"]["tables"]["cover"][8]["rule"] + " WMS 50 m 그림에서 센 값.")),
 # 인천공항 (두 판 공용, 공항철도 두 터미널 역의 중점 — validate_5b_layers P1)
 ("P1", "validate_5b_layers", "P1.", "인천공항 경도를 0.01° 옮김", lambda d: find(d["infrastructure"]["items"], name="인천공항").__setitem__("lon", find(d["infrastructure"]["items"], name="인천공항")["lon"] + 0.01)),
 ("P1", "validate_5b_layers", "P1.", "인천공항 위치 문구(position_note)를 '공항 기준점'으로", lambda d: find(d["infrastructure"]["items"], name="인천공항").__setitem__("position_note", "공항 기준점")),
 ("X4", "validate_profile", "X4.", "도시 하나에 아파트 값(housing)을 넣음", lambda d: d["cities"][0].__setitem__("housing", {"sale_per_m2": 1000}), PUB),
 ("X4", "validate_profile", "X4.", "렌즈 막대에 아파트 매매가(home)를 되살림", lambda d: d["lenses"]["lenses"].append(dict(d["lenses"]["lenses"][0], id="home")), PUB),
 ("X4", "validate_profile", "X4.", "순위 분모에 아파트(housing)를 넣음", lambda d: d["nation"]["nation"]["benchmarks"]["rank_denominators"].__setitem__("housing", 166), PUB),
 ("X5", "validate_profile", "X5.", "가행 광산 아이콘 하나를 넣음", lambda d: d["resources"]["items"].append(dict(d["resources"]["items"][0], kind="mine", id="r-mut")), PUB),
 ("X5", "validate_profile", "X5.", "도시 패널 한우 값(farm.cattle)을 되살림", lambda d: d["resources"]["farm"].__setitem__("cattle", {"by_city": {}, "by_sido": {}}), PUB),
 ("X6", "validate_profile", "X6.", "층 항목 하나의 출처 key 를 한우 이력제 key 로", lambda d: d["resources"]["items"][0].__setitem__("source", "mtrace-hanwoo-202610"), PUB),
 ("X6", "validate_profile", "X6.", "출처 기록 글(license_rule)에 뺀 출처 key(mtrace-hanwoo-202610)를 글로 넣음", lambda d: d["sources"].__setitem__("license_rule", d["sources"]["license_rule"] + " 참고: mtrace-hanwoo-202610."), PUB),
 ("X3", "validate_profile", "X3.", "출처 기록 글(license_rule)에 쓰지 않는 출처 key(incheon-aip)를 글로 넣음", lambda d: d["sources"].__setitem__("license_rule", d["sources"]["license_rule"] + " 참고: incheon-aip.")),
 ("X7", "validate_profile", "X7.", "변경금지 통계 목록에서 보건복지부 수급자 자료를 뺌", lambda d: d["sources"]["profile"]["check_needed"].pop(0)),
 ("X7", "validate_profile", "X7.", "변경금지 통계 문장을 옛 '조건 확인 필요' 문장으로", lambda d: d["sources"]["profile"].__setitem__("check_rule", "조건 확인 필요: 제공기관에 확인해야 한다.")),
 ("X8", "validate_profile", "X8.", "뺀 렌즈 기록(removed)에서 아파트 전세가를 지움", lambda d: d["lenses"]["removed"].pop("jeonse"), PUB),
 ("S7", "validate_profile", "S7.", "변경금지 자료(경북 사업체조사)의 실린 곳(shipped) 삭제", lambda d: find(d["sources"]["sources"], key="gyeongbuk-business-2024").pop("shipped")),
 ("S7", "validate_profile", "S7.", "미확인 자료의 실린 곳을 없는 필드로", lambda d: find(d["sources"]["sources"], key="tidal-flat-shp").__setitem__("shipped", [{"file": "world.json", "path": "no_such_field", "label": "x"}])),
 ("S8", "validate_profile", "S8.", "SRTM30+ 고지 문단 하나의 글자를 바꿈", lambda d: find(d["sources"]["sources"], key="terrain_srtm30plus")["required_notice"]["paragraphs"].__setitem__(1, "Permission is granted.")),
 ("S8", "validate_profile", "S8.", "OSM 호수의 ODbL 안내 삭제", lambda d: find(d["sources"]["sources"], key="osm-water").pop("odbl")),
]
print("| 검사 | 메모리에서 바꾼 것 | 옛 검증기 | 새 검증기 | 새 검증기 상세 (앞부분) |")
print("|---|---|---|---|---|")
base_new = {}
caught = skipped = 0
for c in cases:
    cid, fn, pre, desc, f = c[:5]
    profs = c[5] if len(c) > 5 else None
    if profs and PROFILE not in profs:
        skipped += 1
        print(f"| {cid} | {desc} | – | 건너뜀 | 이 판({PROFILE})에는 없는 자리라 변이가 뜻이 없다 ({'·'.join(sorted(profs))} 판에서만) |")
        continue
    d = mut(f)
    o = run(OLD, fn, pre, d, old=True)[0] if OLD else "–"
    n, det = run(NEW, fn, pre, d)
    base = run(NEW, fn, pre, D)[0]
    caught += n == "실패" and base == "통과"
    print(f"| {cid} | {desc} | {o} | {n} | 원자료 그대로면 {base}. {det[-170:].replace('|', '/')} |")
ran = len(cases) - skipped
print(f"\n변이 {len(cases)}개 (판 {PROFILE}): 돌린 것 {ran}개 가운데 검증기가 잡은 것 {caught}개(원자료 그대로면 통과, 바꾸면 실패), 이 판에서 건너뛴 것 {skipped}개")
