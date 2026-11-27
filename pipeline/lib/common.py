"""경로·입출력 공통 함수."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "data", "raw")
BUILD = os.path.join(ROOT, "data", "build")
SITE_DATA = os.path.join(ROOT, "site", "data")

for _d in (BUILD, SITE_DATA):
    os.makedirs(_d, exist_ok=True)


def raw(*p):
    return os.path.join(RAW, *p)


def build(*p):
    return os.path.join(BUILD, *p)


def site(*p):
    return os.path.join(SITE_DATA, *p)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj, compact=True):
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1, allow_nan=False)
    return os.path.getsize(path)


def rnd(v, nd):
    """반올림. None·NaN 은 None (JSON null = 자료 없음)."""
    if v is None or v != v:
        return None
    r = round(float(v), nd)
    return int(r) if nd == 0 else r
