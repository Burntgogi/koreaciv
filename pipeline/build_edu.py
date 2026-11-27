"""교육의 활용 쪽(site/edu/) 내용 점검: python pipeline/build_edu.py [--data DIR] [--strict] [--quiet]

site/edu/content.json 을 읽어 다음을 본다. 파일을 고치거나 새로 쓰지 않는다 (읽기만 한다).
  1. 짜임: 수업안·짧은 활동·과제·안내의 필드와 형, id 중복, 서로 가리키는 id.
  2. 성취기준: 수업안이 쓴 코드가 standards 표에 있고, 표의 항목마다 문장·학교급·단원·근거 문서·쪽이 있는지.
     (문장이 고시 원문과 같은지는 tools/edu/verify_standards.py 가 내려받은 원문으로 따로 견준다.)
  3. 링크: 모든 해시(#…)가 두 판이 읽는 키로만 되어 있고, 렌즈·층 묶음·세부·도시·시도·교역로·아이템 id 가 지금 site/data 에 있는지.
  4. 값: '지금 자료의 값'(facts)의 경로가 풀리는지, 수업의 전제(checks)가 지금 자료에서도 참인지.
  5. 글: 수업안에 굳은 통계 수치나 공개판에서 빠지는 자료(아파트 값·광산·한우·숲 종류)를 적지 않았는지 (경고).

빌드 판(full/public) 어느 쪽에서 돌려도 된다. 공개판에서만 빠지는 렌즈(PROFILE_ONLY_LENSES)를 가리키는 링크는 오류가 아니라
경고로 적는다 — 쪽(edu.js)이 그 링크를 '이 판에 없음'으로 표시한다. 그 밖에 없는 id 는 오류다.
끝나면 요약을 찍고, 오류가 있으면 1 로 끝난다. --strict 는 경고도 오류로 친다.
"""
import json
import os
import re
import sys
from urllib.parse import parse_qsl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONTENT = os.path.join(ROOT, "site", "edu", "content.json")

# 두 판이 함께 지키는 표 (site/js/render/layers.js, site/yeojido/js/config.js 의 LAYER_GROUPS 와 같아야 한다)
LAYER_GROUPS = {
    "wonders": ["national_park", "world_heritage", "heritage_cluster", "knowledge"],
    "resources": ["power", "dam", "mine", "industrial", "industry", "fishport", "farm"],
    "infra": ["lines", "station", "trade_port", "airport"],
    "trade": ["routes", "export_hub"],
    "frontier": ["frontier"],
}
SUBS = {s for v in LAYER_GROUPS.values() for s in v}
TAB_IDS = ["overview", "econ", "infra", "land"]
HASH_KEYS = {"v", "lens", "city", "state", "item", "route", "report", "ly", "hide", "tab", "intro"}
# 전체판에만 있는 렌즈 (pipeline/lib/profile.py 의 EXCLUDE 'housing'). 공개판에서 이 렌즈를 가리키는 링크는 경고.
PROFILE_ONLY_LENSES = {"home", "jeonse"}
# 수업안 글에 나오면 안 되는 낱말: 공개판에서 빠지는 자료에 기대는 표현 (숲 종류 활엽·침엽은 두 판 공용 토지피복에 있어 뺐다)
PROFILE_WORDS = ["매매가", "전세가", "한우", "광산"]
STAGES = ["observe", "interpret", "limit"]
LAYER_FILES = ["wonders", "resources", "infrastructure", "trade", "ridges", "frontier", "nation"]


class Data:
    """site/data 를 읽어 경로(path)를 값으로 푼다. edu.js 의 resolve() 와 같은 문법."""

    def __init__(self, d):
        self.dir = d
        self._c = {}
        self.cities = {c["id"]: c for c in self.load("cities")}
        self.states = {s["code"]: s for s in self.load("states")}
        L = self.load("lenses")
        self.lenses = {l["id"]: l for l in L["lenses"]}
        W = self.load("world")
        self.profile = W.get("build_profile", "full")
        self.county_index = {c["code"]: i for i, c in enumerate(W["counties"])}
        self.routes = {f"{s['a']}-{s['b']}": s for s in self.load("trade")["routes"]["segments"]}
        self.items = {}
        for f in ("wonders", "resources", "infrastructure"):
            for it in self.load(f).get("items", []):
                self.items[it["id"]] = it

    def load(self, name):
        if name not in self._c:
            with open(os.path.join(self.dir, name + ".json"), encoding="utf-8") as f:
                self._c[name] = json.load(f)
        return self._c[name]

    @staticmethod
    def dig(o, dotted):
        for k in dotted.split(".") if dotted else []:
            if isinstance(o, dict):
                if k not in o:
                    raise KeyError(k)
                o = o[k]
            elif isinstance(o, list) and re.fullmatch(r"\d+", k):
                o = o[int(k)]
            else:
                raise KeyError(k)
        return o

    def lens_range(self, lid, codes):
        l = self.lenses.get(lid)
        if l is None:
            raise KeyError(f"렌즈 {lid} 없음")
        if "by_county" not in l:
            raise KeyError(f"렌즈 {lid} 는 칸 값 렌즈라 지역 값을 낼 수 없음")
        v = [l["by_county"][self.county_index[c]] for c in codes if c in self.county_index]
        v = [x for x in v if isinstance(x, (int, float))]
        return [min(v), max(v)] if v else None

    def resolve(self, path):
        p = path.split(":")
        kind = p[0]
        if kind == "city":
            return self.dig(self.cities[int(p[1])], p[2])
        if kind == "state":
            return self.dig(self.states[p[1]], p[2])
        if kind == "nation":
            return self.dig(self.load("nation")["nation"], p[1])
        if kind == "route":
            return self.dig(self.routes[p[1]], p[2])
        if kind == "layer":
            if p[1] not in LAYER_FILES:
                raise KeyError(f"layer 파일 {p[1]}")
            return self.dig(self.load(p[1]), p[2])
        if kind == "lens":
            lid = p[1]
            if len(p) >= 4 and p[2] in ("city", "state"):
                if p[2] == "city":
                    codes = self.cities[int(p[3])]["sgg"]
                else:
                    if p[3] not in self.states:
                        raise KeyError(p[3])
                    codes = [c for c in self.county_index if c.startswith(p[3])]
                r = self.lens_range(lid, codes)
                if len(p) == 5:
                    if p[4] not in ("lo", "hi"):
                        raise KeyError(p[4])
                    return None if r is None else r[0 if p[4] == "lo" else 1]
                return r
            if lid not in self.lenses:
                raise KeyError(f"렌즈 {lid} 없음")
            return self.dig(self.lenses[lid], p[2])
        raise KeyError(f"모르는 경로 종류 {kind}")


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


def check_hash(h, where, D, R):
    """해시 하나를 두 판의 readHash 가 읽는 방식대로 뜯어 본다. 돌려주는 것: 이 판에 없는 렌즈 id 또는 None."""
    if not isinstance(h, str) or not h.startswith("#"):
        R.err(where, f"해시가 # 로 시작하지 않음: {h!r}")
        return None
    pairs = parse_qsl(h[1:], keep_blank_values=True)
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        R.err(where, f"같은 키가 두 번: {h}")
    p = dict(pairs)
    for k in p:
        if k not in HASH_KEYS:
            R.err(where, f"두 판이 읽지 않는 키 {k!r}: {h}")
    absent = None
    if "v" in p:
        try:
            v = [float(x) for x in p["v"].split(",")]
            assert len(v) == 3 and v[2] > 0
        except Exception:
            R.err(where, f"v 는 x,y,축척 세 숫자여야 함: {p['v']!r}")
    # 신여지도는 v·lens·city·state·item·route·report 가 하나도 없으면 표지를 먼저 보인다
    if not any(p.get(k) for k in ("v", "lens", "city", "state", "item", "route", "report")) and p.get("intro") != "0":
        R.err(where, f"신여지도에서 표지가 먼저 뜨는 해시 (v 나 intro=0 을 넣는다): {h}")
    if p.get("lens"):
        if p["lens"] not in D.lenses:
            if p["lens"] in PROFILE_ONLY_LENSES:
                absent = p["lens"]
                R.warn(where, f"렌즈 {p['lens']} 는 이 판({D.profile})에 없음 — 쪽이 '이 판에 없음'으로 표시한다")
            else:
                R.err(where, f"없는 렌즈 {p['lens']!r}")
    if p.get("city"):
        if not re.fullmatch(r"\d+", p["city"]) or int(p["city"]) not in D.cities:
            R.err(where, f"없는 도시 id {p['city']!r}")
    if p.get("state") and p["state"] not in D.states:
        R.err(where, f"없는 시도 코드 {p['state']!r}")
    if p.get("route") and p["route"] not in D.routes:
        R.err(where, f"없는 교역로 {p['route']!r}")
    if p.get("item") and p["item"] not in D.items:
        R.err(where, f"없는 아이템 {p['item']!r}")
    if "ly" in p:
        for g in filter(None, p["ly"].split(",")):
            if g not in LAYER_GROUPS:
                R.err(where, f"없는 층 묶음 {g!r}")
    for s in filter(None, (p.get("hide") or "").split(",")):
        if s not in SUBS:
            R.err(where, f"없는 층 세부 {s!r}")
    if p.get("tab") and p["tab"] not in TAB_IDS:
        R.err(where, f"없는 패널 탭 {p['tab']!r}")
    if p.get("report") not in (None, "1"):
        R.warn(where, f"report={p['report']} 는 신여지도만 읽는다 (기존판은 report=1 만)")
    targets = [k for k in ("item", "route", "city", "state") if p.get(k)]
    if len(targets) > 1:
        R.err(where, f"선택 대상이 둘 이상 {targets} — 판마다 우선순위가 달라질 수 있음")
    return absent


def cmp_check(c, where, D, R):
    try:
        a = D.resolve(c["path"])
    except Exception as e:
        R.err(where, f"전제 경로를 못 풂 {c['path']!r}: {e}")
        return
    op = c.get("op")
    if "path2" in c:
        try:
            b = D.resolve(c["path2"])
        except Exception as e:
            R.err(where, f"전제 경로를 못 풂 {c['path2']!r}: {e}")
            return
        if isinstance(b, (int, float)) and "times" in c:
            b = b * c["times"]
    else:
        b = c.get("value")
    ok = None
    try:
        if op == "==":
            ok = a == b
        elif op == "has":
            ok = b in a
        elif op == "len>":
            ok = len(a) > b
        elif op == "~":
            ok = abs(a - b) <= c["tol"]
        elif op in ("<", ">", "<=", ">="):
            if a is None or b is None:
                ok = False
            else:
                ok = {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
        else:
            R.err(where, f"모르는 비교 {op!r}")
            return
    except Exception as e:
        R.err(where, f"전제를 견주지 못함 {c}: {e}")
        return
    if not ok:
        R.err(where, f"수업의 전제가 지금 자료와 다름 — {c.get('why', '')} ({c['path']} = {a!r} {op} {b!r} 가 거짓)")


def text_of(o):
    """수업안 하나에서 사람에게 보이는 글만 모은다."""
    out = []
    def walk(x, key=None):
        if isinstance(x, str):
            if key not in ("hash", "harder_hash", "path", "path2", "id", "code", "fmt", "op", "level", "stage", "doc"):
                out.append(x)
        elif isinstance(x, list):
            for y in x:
                walk(y, key)
        elif isinstance(x, dict):
            for k, y in x.items():
                if k in ("facts", "checks", "next", "themes", "subjects", "editions", "levels"):
                    continue
                walk(y, k)
    walk(o)
    return out


NUM_STAT = re.compile(r"(?<![\d.])\d[\d,]*(?:\.\d+)?\s*(?:%|만\s*원|억\s*원|만\s*명|만\s*톤|명/)")


def need(o, keys, where, R):
    ok = True
    for k, t in keys.items():
        if k not in o:
            R.err(where, f"필드 {k} 없음")
            ok = False
        elif not isinstance(o[k], t):
            R.err(where, f"필드 {k} 의 형이 {t} 가 아님")
            ok = False
    return ok


def validate(content, D):
    R = Report()
    stats = {"links": 0, "facts": 0, "checks": 0, "absent_lens_links": []}
    for k, t in {"meta": dict, "curriculum": dict, "standards": dict, "levels": list, "themes": list, "editions": dict, "start": dict,
                 "lessons": list, "quick": list, "projects": list, "guide": dict, "cannot": dict, "glossary": list, "references": list}.items():
        if not isinstance(content.get(k), t):
            R.err("content", f"맨 위 필드 {k} 없음 또는 형이 다름")
    if R.errors:
        return R, stats
    levels = {l["id"] for l in content["levels"]}
    themes = {t["id"] for t in content["themes"]}
    docs = {d["id"] for d in content["curriculum"].get("documents", [])}
    for d in content["curriculum"].get("documents", []):
        need(d, {"id": str, "title": str, "publisher": str, "url": str, "retrieved": str}, f"curriculum.documents[{d.get('id')}]", R)
    # 성취기준 표
    used = set()
    for code, s in content["standards"].items():
        w = f"standards{code}"
        if not re.fullmatch(r"\[\d{1,2}[가-힣]+(?:\([가-힣]+\))?(?:\d-)?\d{2}-\d{2}\]", code):
            R.err(w, "코드 꼴이 성취기준 코드가 아님")
        if need(s, {"text": str, "band": str, "course": str, "unit": str, "doc": str, "page": int}, w, R):
            if s["doc"] not in docs:
                R.err(w, f"근거 문서 {s['doc']!r} 가 curriculum.documents 에 없음")
            if not s["text"].endswith("다."):
                R.warn(w, "성취기준 문장이 '…다.'로 끝나지 않음")

    def link(h, where):
        stats["links"] += 1
        a = check_hash(h, where, D, R)
        if a:
            stats["absent_lens_links"].append(where)

    ids = set()
    for i, st in enumerate(content["start"].get("steps", [])):
        need(st, {"title": str, "text": str}, f"start.steps[{i}]", R)
        if st.get("hash"):
            link(st["hash"], f"start.steps[{i}]")
    lesson_ids = {l.get("id") for l in content["lessons"]}
    for l in content["lessons"]:
        w = f"lesson {l.get('id')}"
        if not need(l, {"id": str, "level": str, "subjects": list, "themes": list, "minutes": int, "periods": str, "title": str, "question": str,
                        "target": str, "standards": list, "devices": str, "summary": list, "open": dict, "steps": list, "worksheet": list,
                        "closing": str, "rubric": dict, "cautions": list, "donts": list, "easier": str, "harder": str, "next": list}, w, R):
            continue
        if l["id"] in ids:
            R.err(w, "id 중복")
        ids.add(l["id"])
        if not re.fullmatch(r"[a-z0-9]+-\d{2}", l["id"]):
            R.err(w, "id 는 닻으로 쓰므로 영문 소문자·숫자·붙임표만")
        if l["level"] not in levels:
            R.err(w, f"없는 학교급 {l['level']!r}")
        for t in l["themes"]:
            if t not in themes:
                R.err(w, f"없는 주제 {t!r}")
        if len(l["summary"]) != 3:
            R.err(w, "요약은 세 줄")
        if len(l["steps"]) != 3:
            R.err(w, "지도 단계는 셋")
        if not l["standards"] and not l.get("related_units"):
            R.err(w, "성취기준도 관련 단원도 없음")
        for s in l["standards"]:
            if s.get("code") not in content["standards"]:
                R.err(w, f"standards 표에 없는 코드 {s.get('code')!r} — 확인하지 못한 코드는 쓰지 않는다")
            used.add(s.get("code"))
            if s.get("fit") not in ("direct", "partial"):
                R.err(w, f"{s.get('code')} 의 fit 은 direct 또는 partial")
            if not s.get("note"):
                R.err(w, f"{s.get('code')} 에 맞는 정도를 적은 note 가 없음")
        for e in l.get("editions", []):
            if e not in content["editions"]:
                R.err(w, f"없는 판 {e!r}")
        if not l["open"].get("hash"):
            R.err(w, "여는 링크(open.hash)가 없음")
        else:
            link(l["open"]["hash"], w + " open")
        for i, st in enumerate(l["steps"]):
            if not isinstance(st, dict) or not st.get("text"):
                R.err(w, f"단계 {i + 1} 글 없음")
            elif st.get("hash"):
                link(st["hash"], f"{w} step{i + 1}")
        if l.get("harder_hash"):
            link(l["harder_hash"], w + " harder")
        # 활동지: 관찰 → 해석 → 한계 순서, 셋 다 있어야 한다
        seq = [q.get("stage") for q in l["worksheet"]]
        if any(s not in STAGES for s in seq):
            R.err(w, f"활동지 단계는 {STAGES} 가운데 하나")
        else:
            order = [STAGES.index(s) for s in seq]
            if order != sorted(order):
                R.err(w, "활동지 질문이 관찰 → 해석 → 한계 순서가 아님")
            if set(seq) != set(STAGES):
                R.err(w, "활동지에 관찰·해석·한계 질문이 모두 있어야 함")
        if not 4 <= len(l["worksheet"]) <= 6:
            R.err(w, "활동지 질문은 4~6개")
        for q in l["worksheet"]:
            if not q.get("q"):
                R.err(w, "활동지 질문 글 없음")
        if set(l["rubric"]) != {"high", "mid", "low"}:
            R.err(w, "평가 기준은 high·mid·low 세 단계")
        if not l["cautions"] or not l["donts"]:
            R.err(w, "주의할 점과 하지 말 것이 있어야 함")
        for n in l["next"]:
            if n not in lesson_ids:
                R.err(w, f"다음 수업안 {n!r} 없음")
        for f in l.get("facts", []):
            stats["facts"] += 1
            if not need(f, {"label": str, "path": str, "fmt": str}, w + " facts", R):
                continue
            try:
                v = D.resolve(f["path"])
                if v is None and not f.get("nullable"):
                    R.err(w, f"값이 비어 있음: {f['label']} ({f['path']})")
                if f.get("nullable") and v is not None:
                    R.warn(w, f"비어 있어야 할 값에 값이 있음: {f['label']} = {v!r}")
            except Exception as e:
                lid = f["path"].split(":")[1] if f["path"].startswith("lens:") else None
                if lid in PROFILE_ONLY_LENSES and lid not in D.lenses:
                    R.warn(w, f"이 판에 없는 렌즈의 값: {f['path']}")
                else:
                    R.err(w, f"값 경로를 못 풂 {f['path']!r}: {e}")
        for c in l.get("checks", []):
            stats["checks"] += 1
            cmp_check(c, w + " checks", D, R)
        for s in text_of(l):
            for wd in PROFILE_WORDS:
                if wd in s:
                    R.err(w, f"공개판에서 빠지는 자료에 기대는 낱말 {wd!r}: {s[:40]}…")
            m = NUM_STAT.search(s)
            if m:
                R.warn(w, f"굳은 수치로 보이는 표현 {m.group(0)!r}: {s[:50]}…")
    for code in content["standards"]:
        if code not in used:
            R.warn(f"standards{code}", "어느 수업안도 쓰지 않는 성취기준")
    for kind, keys in (("quick", {"id": str, "title": str, "when": str, "minutes": int, "levels": list, "question": str, "how": str, "hash": str}),
                       ("projects", {"id": str, "title": str, "levels": list, "question": str, "screen": str, "deliverable": str, "limit": str, "hash": str})):
        for q in content[kind]:
            w = f"{kind} {q.get('id')}"
            if not need(q, keys, w, R):
                continue
            if q["id"] in ids:
                R.err(w, "id 중복")
            ids.add(q["id"])
            for lv in q["levels"]:
                if lv not in levels:
                    R.err(w, f"없는 학교급 {lv!r}")
            link(q["hash"], w)
            for s in text_of(q):
                for wd in PROFILE_WORDS:
                    if wd in s:
                        R.err(w, f"공개판에서 빠지는 자료에 기대는 낱말 {wd!r}")
                m = NUM_STAT.search(s)
                if m:
                    R.warn(w, f"굳은 수치로 보이는 표현 {m.group(0)!r}")
    for g in content["glossary"]:
        need(g, {"term": str, "plain": str}, f"glossary {g.get('term')}", R)
    for r in content["references"]:
        need(r, {"title": str, "url": str}, f"references {r.get('title')}", R)
    g = content["guide"]
    for k in ("rules", "sensitive", "game", "faq", "devices"):
        if k not in g:
            R.err("guide", f"{k} 없음")
    if len(g.get("rules", {}).get("items", [])) != 5:
        R.err("guide.rules", "숫자를 읽는 약속은 다섯")
    if not content["meta"].get("caveats"):
        R.err("meta", "caveats 없음")
    return R, stats


def main(argv):
    data_dir = os.path.join(ROOT, "site", "data")
    strict = "--strict" in argv
    quiet = "--quiet" in argv
    for i, a in enumerate(argv):
        if a == "--data" and i + 1 < len(argv):
            data_dir = argv[i + 1]
        elif a.startswith("--data="):
            data_dir = a.split("=", 1)[1]
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        with open(CONTENT, encoding="utf-8") as f:
            content = json.load(f)
    except Exception as e:
        print(f"!!! site/edu/content.json 을 읽지 못함: {e}")
        return 1
    try:
        D = Data(data_dir)
    except Exception as e:
        print(f"!!! {data_dir} 의 자료를 읽지 못함: {type(e).__name__}: {e}")
        return 1
    R, stats = validate(content, D)
    if not quiet:
        for w in R.warnings:
            print("경고", w)
    for e in R.errors:
        print("오류", e)
    by_level = {}
    for l in content.get("lessons", []):
        by_level[l["level"]] = by_level.get(l["level"], 0) + 1
    print(f"교육 쪽 점검 — 자료 판 {D.profile} · 수업안 {len(content.get('lessons', []))}({', '.join(f'{k} {v}' for k, v in by_level.items())}) · "
          f"짧은 활동 {len(content.get('quick', []))} · 과제 {len(content.get('projects', []))} · 성취기준 {len(content.get('standards', {}))} · "
          f"링크 {stats['links']} · 값 {stats['facts']} · 전제 {stats['checks']} · 이 판에 없는 렌즈를 가리키는 링크 {len(stats['absent_lens_links'])} · "
          f"오류 {len(R.errors)} · 경고 {len(R.warnings)}")
    return 1 if R.errors or (strict and R.warnings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
