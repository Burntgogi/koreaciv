"""출처 페이지·NOTICE.md 공용: 이용조건 분류, 계산한 층의 규칙 문장 찾기, 글꼴 이용허락 파일 읽기, NOTICE.md 만들기.

build_sources.py(기록을 만든다)·build_notice.py(NOTICE.md 를 쓴다)·validate.py(다시 만들어 대조한다)가 같은 함수를 쓴다.
NOTICE.md 는 site/data/sources.json 하나만 읽어 만든다 — 원자료(data/raw)·이용허락 표(data/build)가 없는 저장소에서도 같은 결과가 나온다.
"""
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(ROOT, "site")
FONT_DIR = os.path.join(SITE, "yeojido", "fonts")
NOTICE = os.path.join(ROOT, "NOTICE.md")
# 사이트에 실리는 글꼴 파일(과 글꼴 윤곽에서 뽑은 그림). 이 확장자는 site/ 아래 어디에 있든 이용허락 기록이 있어야 한다.
FONT_EXT = (".woff2", ".woff", ".ttf", ".otf")
# fonts/ 안에서 글꼴 윤곽을 뽑아 만든 그림 (README.md 표: title-hanja.svg, seal.svg, seal-mask.svg)
FONT_DERIVED_EXT = (".svg",)

# ---- 이용조건 분류 ----
# 이용허락 원문(license)·이용허락 표의 메모(license_note)에서 고른다. 사람 손으로 자료마다 분류하지 않는다.
RESTRICTION_KINDS = [
    ("noncommercial", "비상업 조건", "상업적 이용을 금지하거나, 교육·연구·비영리 목적으로만 허용한다.",
     [r"상업적\s*이용\s*금지", r"상업적이용금지", r"non-?profit", r"비상업적\s*(사용|목적|이용)", r"영리\s*목적.{0,40}(안\s*됩|안됩|금지)",
      r"명시적\s*승인\s*없이\s*상업적", r"상업\s*(제품|목적)[^.]{0,30}협의"]),
    ("noderivs", "변경 금지", "원 저작물의 변경(가공)을 금지하거나 제한한다.",
     [r"변경\s*금지", r"무단\s*변경"]),
    ("consent", "사전 허락·협의", "(영리) 이용·제3자 제공 전에 제공기관의 승인·허락·협의가 필요하다.",
     [r"사전\s*(에\s*)?(별도의\s*)?(승낙|허락|협의|허가|승인)", r"prior\s+permission", r"명시적\s*승인", r"승인\s*필요", r"상업[^.]{0,30}협의"]),
    ("api_terms", "API 이용약관", "Open API 약관이 저장·복제·전송과 비상업 이용을 제한한다 (기록의 restriction).", []),
    ("publication", "외부 공개 조건", "외부에 공개할 때 지켜야 할 조건이 원문에 있다.",
     [r"외부\s*공개\s*시"]),
]
KIND_NAME = {k: n for k, n, _, _ in RESTRICTION_KINDS}


def restriction_kinds(s):
    """출처 기록 하나 -> 이용조건 분류 코드 목록 (원문·메모·restriction 필드에서)."""
    t = " ".join(str(s.get(k) or "") for k in ("license", "license_note"))
    unknown = (s.get("license") or "미확인") == "미확인"
    out = []
    for code, _, _, pats in RESTRICTION_KINDS:
        if code == "api_terms":
            if s.get("restriction"):
                out.append(code)
            continue
        if not unknown and any(re.search(p, t, re.I) for p in pats):
            out.append(code)
    return out


def restriction_rule():
    return ("이용조건 분류는 이용허락 원문(license)과 이용허락 표의 메모(license_note)에 그 갈래의 문구가 있는지로 정한다(자료마다 손으로 고르지 않는다; "
            "API 이용약관은 기록의 restriction 필드): " + " / ".join(f"{n}: {d.rstrip('.')}" for _, n, d, _ in RESTRICTION_KINDS) + ". "
            "이용허락을 확인하지 못한 자료('미확인')는 메모에 다른 자료의 조건이 적혀 있어도 분류하지 않고 따로 적는다. "
            "분류에 들지 않았다고 조건이 없다는 뜻은 아니다 — 출처 표시 등 원문의 조건은 모두 지켜야 한다.")


# ---- 계산한 층: 규칙 문장이 든 자리 ----
def jpath(doc, path):
    """'a.b[id=x].c' 꼴 경로 -> 값. [*] 는 목록 그대로. 없으면 KeyError."""
    cur = doc
    for part in re.findall(r"[^.\[\]]+|\[[^\]]*\]", path):
        if part.startswith("["):
            sel = part[1:-1]
            if sel == "*":
                continue
            k, v = sel.split("=", 1)
            cur = next(x for x in cur if str(x.get(k)) == v)
        else:
            cur = cur[part]
    return cur


def rule_text(val):
    """규칙 자리의 값 -> (문장, 조각 목록). 문자열은 그대로, {name|t, rule} 목록은 조각으로."""
    if isinstance(val, str):
        return val, None
    if isinstance(val, list):
        parts = []
        for x in val:
            if isinstance(x, dict) and x.get("rule"):
                nm = x.get("name") if x.get("name") is not None else x.get("t")
                parts.append({"name": str(nm if nm is not None else ""), "rule": x["rule"]})
        return " / ".join(f"{p['name']}: {p['rule']}" for p in parts), parts
    raise ValueError(f"규칙 자리의 값이 문자열·목록이 아님: {type(val).__name__}")


def resolve_rule(spec, loader):
    """spec 'ridges.json:rule' -> (문장, 조각). loader(파일 이름) -> JSON."""
    fn, path = spec.split(":", 1)
    return rule_text(jpath(loader(fn), path))


# ---- 글꼴 이용허락 파일 ----
def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest(), os.path.getsize(p)


def parse_ofl(path):
    """이용허락 파일 -> {license, license_url, copyright, reserved_font_name}. OFL 1.1 문구가 없으면 license=None."""
    with open(path, encoding="utf-8") as fh:
        txt = fh.read()
    flat = re.sub(r"\s+", " ", txt)
    lic = "SIL Open Font License 1.1" if re.search(r"SIL Open Font License,? Version 1\.1", flat, re.I) and "PERMISSION & CONDITIONS" in txt else None
    url = re.search(r"available with a FAQ at:\s*(https?://\S+)", txt)
    head = txt.split("This Font Software")[0]
    cps = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", head) if p.strip().startswith("Copyright")]
    rfn = re.findall(r"Reserved Font Name '([^']+)'", flat)
    return {"license": lic, "license_url": url.group(1) if url else None, "copyright": cps, "reserved_font_name": rfn or None}


def shipped_font_files():
    """site/ 아래 글꼴 파일 + fonts/ 안 글꼴 윤곽 그림 (상대 경로 site/...)."""
    out = []
    for dp, _, fs in os.walk(SITE):
        for f in fs:
            p = os.path.join(dp, f)
            low = f.lower()
            if low.endswith(FONT_EXT) or (os.path.normcase(dp) == os.path.normcase(FONT_DIR) and low.endswith(FONT_DERIVED_EXT)):
                out.append(os.path.relpath(p, ROOT).replace("\\", "/"))
    return sorted(out)


# ---- NOTICE.md ----
def _cell(v):
    return str(v if v is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def license_counts(sources):
    c = {}
    for s in sources:
        k = s.get("license_short") or ("이용허락 미확인" if (s.get("license") or "미확인") == "미확인" else str(s.get("license"))[:28])
        c[k] = c.get(k, 0) + 1
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))


def restricted_groups(S):
    """제한 자료를 (기관, 이용허락, 메모, 분류, 쓴 곳의 앞부분) 이 같은 것끼리 묶는다 (월별 파일 24개 같은 묶음)."""
    groups = {}
    for s in S:
        if not s.get("restriction_kinds"):
            continue
        k = (s.get("publisher"), s.get("license"), s.get("license_note"), tuple(s["restriction_kinds"]), s.get("restriction"),
             re.sub(r"\d{4}-\d{2}", "", s.get("title") or ""))
        groups.setdefault(k, []).append(s)
    return list(groups.values())


def shipped_text(s):
    return "; ".join(f"{r.get('label')} (`{r.get('file')}` `{r.get('path')}`)" for r in s.get("shipped") or [])


def render_profile(P):
    if not P:
        return []
    out = [f"## 이 판: {_cell(P.get('name'))} (`{_cell(P.get('profile'))}`)", "", _cell(P.get("statement")), ""]
    pub = P.get("profile") == "public"
    out += ["| 묶음 | 무엇 | 까닭 | 대신 | 출처 key |" if pub else "| 묶음 (공개판에서 빼는 것) | 무엇 | 까닭 | 공개판에서 대신 | 출처 key |", "|---|---|---|---|---|"]
    for e in P.get("excluded") or []:
        out.append(f"| `{_cell(e.get('id'))}` | {_cell(e.get('what'))} | {_cell(e.get('why'))} | {_cell(e.get('instead') or '대신하지 않음 (빈 자리로 둔다)')} | "
                   + _cell(", ".join(f"`{x.get('key')}`" for x in e.get("sources") or [])) + " |")
    out.append("")
    if P.get("check_needed"):
        out += ["### 변경금지 통계 — 원 통계를 바꾸지 않고 모아 보이기만 한다", "", _cell(P.get("check_rule")), ""]
        out += [f"- {_cell(x.get('publisher'))} 「{_cell(x.get('title'))}」 (`{_cell(x.get('key'))}`, {_cell(x.get('license_short'))}) — 실린 곳: {_cell('; '.join(x.get('where') or []))}"
                for x in P["check_needed"]] + [""]
    if P.get("consent_kept"):
        out += ["### 허락 조건이 상업 이용에만 걸려 남긴 자료", ""]
        out += [f"- 「{_cell(x.get('title'))}」 (`{_cell(x.get('key'))}`) — {_cell(x.get('why'))}" for x in P["consent_kept"]] + [""]
    out += [_cell(P.get("rule")), ""]
    return out


def render_notice(SJ):
    S = SJ.get("sources") or []
    sm = SJ.get("summary") or {}
    out = ["# NOTICE — 출처와 이용조건", "",
           "> 이 파일은 `pipeline/build_notice.py` 가 `site/data/sources.json` 에서 만든다. 손으로 고치지 않는다.",
           "> 사이트의 출처 페이지(`site/sources/`)가 같은 기록을 더 자세히 보인다.", ""]
    out += ["## 요약", ""] + [f"- {t}" for t in sm.get("text") or []] + [""]
    out += render_profile(SJ.get("profile"))
    out += ["## 코드", "", "- 이 저장소의 코드: Apache License 2.0 (`LICENSE`). 이 이용허락은 우리가 만든 코드·디자인·문서에만 미친다. 아래 자료·글꼴에는 각자의 조건이 따로 있다.", ""]
    for s in S:
        rn = s.get("required_notice")
        if rn:
            out += [f"## 표고 자료 고지 — {_cell(s.get('title'))} (`{_cell(s.get('key'))}`)", "", _cell(rn.get("rule")), "",
                    f"원문: {_cell(rn.get('from_url'))} (보관본 `{_cell(rn.get('from'))}`, sha256 `{_cell(rn.get('from_sha256'))}`)", "", "```text"]
            for k, para in enumerate(rn.get("paragraphs") or []):
                out += ([""] if k else []) + str(para).splitlines()
            out += ["```", ""]
            if s.get("commercial_use"):
                out += [_cell(s["commercial_use"]), ""]
    for s in S:
        if s.get("odbl"):
            out += [f"## OpenStreetMap 파생 자료 (ODbL) — `{_cell(s.get('key'))}`", "", _cell(s["odbl"]), ""]
    out += ["## 이용허락 유형별 건수", "", f"자료 출처 {len(S)}건.", "", "| 이용허락 (짧은 표기) | 건수 |", "|---|---:|"]
    out += [f"| {_cell(k)} | {n} |" for k, n in license_counts(S)] + [""]
    out += ["## 이용조건에 제한이 있는 자료", "", _cell(SJ.get("restricted_rule")), ""]
    out += ["| 자료 | 기관 | 분류 | 이용허락 원문 | 사이트에서 쓰는 곳 |", "|---|---|---|---|---|"]
    for g in restricted_groups(S):
        s = g[0]
        aff = s.get("affects") or {}
        lens = []
        for x in g:
            lens += [n for n in (x.get("affects") or {}).get("lenses") or [] if n not in lens]
        where = (s.get("used_in") or "") + (f" · 렌즈: {', '.join(lens)}" if lens else "") + (" · 지도 바탕" if aff.get("base") else "")
        sh = []
        for x in g:
            sh += [t for t in shipped_text(x).split("; ") if t and t not in sh]
        if sh:
            where += " · 실린 필드: " + "; ".join(sh)
        lic = (s.get("license") or "") + (f" — {s['license_note']}" if s.get("license_note") else "") + (f" — {s['restriction']}" if s.get("restriction") else "")
        name = f"{_cell(s.get('title'))} (`{_cell(s.get('key'))}`)" if len(g) == 1 else f"{_cell(s.get('title'))} 외 {len(g) - 1}건 (`{_cell(s.get('key'))}` … `{_cell(g[-1].get('key'))}`)"
        out.append(f"| {name} | {_cell(s.get('publisher'))} | {_cell(' · '.join(KIND_NAME.get(k, k) for k in s['restriction_kinds']))} | {_cell(lic)} | {_cell(where)} |")
    out.append("")
    U = [s for s in S if (s.get("license") or "미확인") == "미확인"]
    out += ["## 이용허락 미확인", "", f"{len(U)}건. 이용허락 문구를 확인하지 못했다. 쓰기 전에 제공기관에 확인해야 한다.", ""]
    out += [f"- {_cell(s.get('publisher'))} 「{_cell(s.get('title'))}」 (`{_cell(s.get('key'))}`)" + (f" — {_cell(s.get('license_note'))}" if s.get("license_note") else "")
            + (f" — 수집 기록의 값: {_cell(s.get('license_collected'))}" if s.get("license_collected") else "")
            + (f" — 실린 필드: {_cell(shipped_text(s))}" if s.get("shipped") else "") for s in U] + [""]
    cite = SJ.get("cite") or {}
    out += ["## 출처 표기", "", "그대로 옮겨 쓸 수 있는 표기:", "", "```text", *(cite.get("text") or "").splitlines(), "```", "",
            "이용허락별 기관 (출처 표기 줄):", ""] + [f"- {_cell(x)}" for x in cite.get("lines") or []] + [""]
    D = SJ.get("derived") or []
    out += ["## 계산한 층", "", "원자료에서 이 프로젝트가 계산한 것. 규칙 문장 전문은 출처 페이지에 있다.", ""]
    def ins(d):
        k = d.get("inputs") or []
        if not k:
            return d.get("inputs_note") or "–"
        return f"출처 {len(k)}건 — " + ", ".join(f"`{x}`" for x in k[:5]) + (f" 외 {len(k) - 5}건" if len(k) > 5 else "")
    out += [f"- **{_cell(d.get('title'))}** (`{_cell(d.get('file'))}`) — 입력: {_cell(ins(d))}" for d in D] + [""]
    C = SJ.get("credits") or []
    F = [c for c in C if c.get("kind") == "font"]
    out += ["## 글꼴", "", "| 글꼴 | 쓰임 | 만든 이 | 이용허락 | 이용허락 파일 | 실린 파일 |", "|---|---|---|---|---|---|"]
    out += [f"| {_cell(c.get('title'))} | {_cell(c.get('role'))} | {_cell(c.get('publisher'))} | {_cell(c.get('license'))}"
            + (f" (예약 글꼴 이름: {_cell(', '.join(c['reserved_font_name']))})" if c.get("reserved_font_name") else "")
            + f" | `{_cell(c.get('license_file'))}` | {_cell(', '.join('`' + f['file'] + '`' for f in c.get('files') or []))} |" for c in F] + [""]
    O = [c for c in C if c.get("kind") != "font"]
    out += ["## 그 밖의 표기", ""]
    for c in O:
        out.append(f"- **{_cell(c.get('title'))}** — {_cell(c.get('publisher'))}" + (f" <{c['url']}>" if c.get("url") else "")
                   + f". {_cell(c.get('used_in'))}. 이용허락: {_cell(c.get('license'))}" + (f" — {_cell(c.get('license_note'))}" if c.get("license_note") else "")
                   + (f" ({_cell(', '.join(c['names']))})" if c.get("names") else ""))
    out.append("")
    out += ["## 관계 없음", "", "이 사이트는 정부·공공기관과 관계가 없다. 통계의 가공·표현에 대한 책임은 제작자에게 있다.", ""]
    return "\n".join(out)


def read_notice():
    with open(NOTICE, encoding="utf-8", newline="") as fh:
        return fh.read()


def load_sources_json():
    with open(os.path.join(SITE, "data", "sources.json"), encoding="utf-8") as fh:
        return json.load(fh)
