"""산줄기(분수계) 만들기 — site/data/ridges.json

보유 자료만 쓴다 (새로 받지 않는다):
  - 표고: data/raw/terrain/srtm30plus_korea.csv (SRTM30+ 30초 격자)
  - 물줄기: site/data/world.json 의 rivers (화면에 그리는 396개 선) + 있으면 data/build/layers/rivers.geojson (WAMIS 유로선 전체, 물길 새기기에만)
  - 대한민국 육지 칸: site/data/world.json 의 owner

방법: 표고를 화면 단위 격자로 옮기고 → 물줄기를 새기고(stream burning) → 낮은 곳부터 채우며 흐름 방향을 정하고(priority-flood D8)
→ 흐름 누적으로 물길 나무를 만들고 → 이웃한 두 격자 칸의 물이 "어디서 만나는가"로 분수계의 크기를 재고
→ 낮고 밋밋한 곳을 걷어 내고 → 선으로 잇고 다듬은 뒤 → "산줄기는 물줄기를 건너지 않는다"를 검사한다 (0건이 아니면 실패).

계산한 선에는 고유 이름(산맥·대간·정맥 이름)을 붙이지 않는다.

실행: python pipeline/build_ridges.py [--debug 그림폴더]
"""
import argparse
import datetime
import heapq
import json
import math
import os
import sys

import numpy as np
from pyproj import Transformer
from scipy import ndimage
import shapely
from shapely.strtree import STRtree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEM_CSV = os.path.join(ROOT, "data", "raw", "terrain", "srtm30plus_korea.csv")
WORLD = os.path.join(ROOT, "site", "data", "world.json")
RAW_RIVERS = os.path.join(ROOT, "data", "build", "layers", "rivers.geojson")
OUT = os.path.join(ROOT, "site", "data", "ridges.json")

VERSION = "ridges-2"
RULE = "산줄기는 물줄기를 건너지 않는다."

# ---- 매개변수 ----
CS = 4.0                 # 계산 격자 한 칸 (화면 단위; 1 단위 = 112 m -> 448 m)
BURN_DRAWN = 60.0        # 그리는 물줄기 새김 깊이 (m)
BURN_RAW = 30.0          # WAMIS 나머지 유로선 새김 깊이 (m)
A0_KM2 = 8.0             # 물길로 치는 최소 유역 넓이
TIER_KM = [10.0, 30.0, 70.0, 160.0]   # 갈림 거리(km) 하한: tier 0,1,2,3
Z_MIN = [140.0, 110.0, 80.0, 60.0]    # tier 별 능선 표고 하한 (m)
HAND_MIN = [70.0, 55.0, 40.0, 30.0]   # tier 별 물길 위 높이 하한 (m)
MIN_LEN_KM = [5.0, 6.0, 8.0, 8.0]     # tier 별 가장 짧은 조각
RIVER_CLEAR = 1.0        # 그리는 물줄기에서 이만큼(화면 단위) 안쪽은 자른다
SMOOTH_ITERS = 12        # 1-2-1 고르기 횟수 (격자 계단·모서리를 편다)
GAP_KM = 10.0            # 큰 줄기(tier 2 이상) 사이의 낮은 고개 구간을 이어 그리는 최대 길이
RUN_MIN_KM = 6.0         # 한 획 안에서 크기가 바뀌는 구간의 최소 길이
JOIN_TOL = 8.0           # 선 끝이 다른 선에 닿았다고 보는 거리 (화면 단위)
SIMPLIFY_TOL = 0.5       # 화면 단위 (다듬은 곡선을 곧은 변으로 그려도 매끈하게)
MAX_BYTES = 190_000
TIER_NAMES = ["작은 줄기", "고을 줄기", "큰 줄기", "큰 분수계"]


DBG = {}


def log(*a):
    print("[ridges]", *a, flush=True)


def load_world():
    with open(WORLD, encoding="utf-8") as f:
        w = json.load(f)
    for k in ("grid", "width", "height", "meters_per_unit", "origin_5179", "owner", "rivers"):
        if k not in w:
            raise SystemExit(f"world.json 에 {k} 가 없다")
    return w


def hex_cell(x, y, cols, rows, R):
    """pointy-top odd-r (pipeline/lib/hexgrid.py 와 같은 계산)."""
    W = math.sqrt(3) * R
    px = np.asarray(x, float) - W / 2
    py = np.asarray(y, float) - R
    q = (math.sqrt(3) / 3 * px - py / 3) / R
    r = (2.0 / 3 * py) / R
    cx, cz = q, r
    cy = -cx - cz
    rx, ry, rz = np.round(cx), np.round(cy), np.round(cz)
    dx, dy, dz = np.abs(rx - cx), np.abs(ry - cy), np.abs(rz - cz)
    fx = (dx > dy) & (dx > dz)
    fy = ~fx & (dy > dz)
    rx = np.where(fx, -ry - rz, rx)
    ry = np.where(fy, -rx - rz, ry)
    rz = np.where(~fx & ~fy, -rx - ry, rz)
    row = rz.astype(np.int64)
    col = rx.astype(np.int64) + (row - (row & 1)) // 2
    ok = (col >= 0) & (col < cols) & (row >= 0) & (row < rows)
    return np.where(ok, row * cols + col, -1)


def densify(pts, step):
    """N×2 선 -> step 간격 점."""
    d = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
    s = np.concatenate([[0], np.cumsum(d)])
    if s[-1] <= 0:
        return pts[:1]
    t = np.arange(0, s[-1] + step, step)
    t[-1] = s[-1]
    return np.column_stack([np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", help="검토용 그림을 쓸 폴더")
    args = ap.parse_args()
    t_start = datetime.datetime.now()

    w = load_world()
    MPU = float(w["meters_per_unit"])
    ox, oy = w["origin_5179"]
    Wu, Hu = float(w["width"]), float(w["height"])
    g = w["grid"]
    owner = np.asarray(w["owner"], dtype=np.int32)
    cell_km = CS * MPU / 1000.0

    # ---------- 표고 ----------
    z = np.loadtxt(DEM_CSV, delimiter=",", skiprows=2)
    lats = np.unique(z[:, 0])
    lons = np.unique(z[:, 1])
    if len(lats) * len(lons) != len(z):
        raise SystemExit("표고 CSV 가 꽉 찬 격자가 아니다")
    dlat = float(np.median(np.diff(lats)))
    dlon = float(np.median(np.diff(lons)))
    order = np.lexsort((z[:, 1], z[:, 0]))
    dem = z[order, 2].reshape(len(lats), len(lons))
    dem_info = (f"SRTM30+ {len(lats)}×{len(lons)} 격자, 간격 {dlat * 3600:.0f}″×{dlon * 3600:.0f}″ "
                f"(남북 약 {dlat * 111.2:.2f} km, 동서 약 {dlon * 111.2 * math.cos(math.radians(36.5)):.2f} km), "
                f"범위 {lats[0]:.3f}–{lats[-1]:.3f}°N {lons[0]:.3f}–{lons[-1]:.3f}°E")
    log(dem_info)

    nx, ny = int(math.ceil(Wu / CS)), int(math.ceil(Hu / CS))
    gx = (np.arange(nx) + 0.5) * CS
    gy = (np.arange(ny) + 0.5) * CS
    GX, GY = np.meshgrid(gx, gy)
    inv = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    fwd = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    lon, lat = inv.transform(ox + GX * MPU, oy - GY * MPU)
    fi = (lat - lats[0]) / dlat
    fj = (lon - lons[0]) / dlon
    Z = ndimage.map_coordinates(dem, [fi, fj], order=3, mode="nearest").astype(np.float64)
    Zlin = ndimage.map_coordinates(dem, [fi, fj], order=1, mode="nearest")
    inside = (fi >= 0) & (fi <= len(lats) - 1) & (fj >= 0) & (fj <= len(lons) - 1)
    # 바다: 표고 0 이하이면서 격자 가장자리(또는 표고 범위 밖)와 이어진 곳
    low = (Zlin <= 0) | ~inside
    lab, _ = ndimage.label(low, structure=np.ones((3, 3)))
    edge_labels = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1], lab[~inside]]))
    sea = np.isin(lab, edge_labels[edge_labels > 0])
    land = ~sea
    Z = np.where(land, np.maximum(Z, 0.5), Z)
    log(f"계산 격자 {nx}×{ny} (한 칸 {CS * MPU:.0f} m), 육지 {int(land.sum()):,}칸")

    # ---------- 물줄기 새기기 ----------
    def to_idx(pts):
        i = np.clip((pts[:, 0] / CS).astype(int), 0, nx - 1)
        j = np.clip((pts[:, 1] / CS).astype(int), 0, ny - 1)
        return j, i

    Zb = Z.copy()
    drawn = []
    for r in w["rivers"]:
        p = np.asarray(r["pts"], float).reshape(-1, 2)
        if len(p) >= 2:
            drawn.append(p)
    raw_lines = []
    raw_note = "없음"
    if os.path.exists(RAW_RIVERS):
        try:
            with open(RAW_RIVERS, encoding="utf-8") as f:
                gj = json.load(f)
            for ft in gj["features"]:
                geom = ft.get("geometry") or {}
                parts = [geom["coordinates"]] if geom.get("type") == "LineString" else geom.get("coordinates", []) if geom.get("type") == "MultiLineString" else []
                for c in parts:
                    c = np.asarray(c, float)
                    if c.ndim != 2 or len(c) < 2:
                        continue
                    e, n = fwd.transform(c[:, 0], c[:, 1])
                    raw_lines.append(np.column_stack([(e - ox) / MPU, (oy - n) / MPU]))
            raw_note = f"{len(gj['features'])}건"
        except Exception as ex:  # 정리표가 없거나 깨졌으면 그리는 물줄기만으로 새긴다
            log("WAMIS 유로선 정리표를 읽지 못함:", ex)
            raw_lines = []
    log(f"물줄기: 그리는 선 {len(drawn)}개, WAMIS 유로선 {raw_note} (선 {len(raw_lines)}개)")

    def burn(lines, depth):
        for p in lines:
            q = densify(p, CS * 0.35)
            j, i = to_idx(q)
            zz = Z[j, i]
            k = max(2, len(zz) // 5)
            if zz[:k].mean() < zz[-k:].mean():   # 낮은 끝이 하류
                j, i, zz = j[::-1], i[::-1], zz[::-1]
            cond = np.minimum.accumulate(zz) - depth
            np.minimum.at(Zb, (j, i), cond)

    burn(raw_lines, BURN_RAW)
    burn(drawn, BURN_DRAWN)

    # ---------- 낮은 곳부터 채우며 흐름 방향 (priority-flood) ----------
    N = nx * ny
    zb = Zb.ravel().tolist()
    landf = land.ravel()
    landl = landf.tolist()
    parent = np.full(N, -1, dtype=np.int64)
    seen = bytearray(N)
    heap = []
    cnt = 0
    sea_nb = ndimage.binary_dilation(sea, structure=np.ones((3, 3))) & land
    border = np.zeros_like(land)
    border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
    seeds = np.flatnonzero((sea_nb | (border & land)).ravel())
    for c in seeds.tolist():
        heap.append((zb[c], cnt, c))
        cnt += 1
        seen[c] = 1
    heapq.heapify(heap)
    order_pop = []
    flen = [0.0] * N
    par = [-1] * N
    D8 = [(-1, -1, 1.4142), (0, -1, 1.0), (1, -1, 1.4142), (-1, 0, 1.0), (1, 0, 1.0), (-1, 1, 1.4142), (0, 1, 1.0), (1, 1, 1.4142)]
    pop, push = heapq.heappop, heapq.heappush
    while heap:
        lv, _, c = pop(heap)
        order_pop.append(c)
        cy, cx = divmod(c, nx)
        fl = flen[c]
        for dx, dy, dd in D8:
            x2, y2 = cx + dx, cy + dy
            if x2 < 0 or y2 < 0 or x2 >= nx or y2 >= ny:
                continue
            n = y2 * nx + x2
            if seen[n] or not landl[n]:
                continue
            seen[n] = 1
            par[n] = c
            flen[n] = fl + dd
            zn = zb[n]
            push(heap, (zn if zn > lv else lv, cnt, n))
            cnt += 1
    parent = np.asarray(par, dtype=np.int64)
    flen = np.asarray(flen) * cell_km
    acc = np.ones(N, dtype=np.int64)
    accl = [1] * N
    for c in reversed(order_pop):
        p = par[c]
        if p >= 0:
            accl[p] += accl[c]
    acc = np.asarray(accl, dtype=np.int64)
    log(f"흐름 방향: 육지 {len(order_pop):,}칸, 바다·가장자리 출구 {len(seeds):,}칸")

    # ---------- 물길 나무 ----------
    a0 = max(2, int(round(A0_KM2 / (cell_km * cell_km))))
    is_stream = (acc >= a0) & landf
    sid = np.full(N, -1, dtype=np.int64)
    scells = np.flatnonzero(is_stream)
    sid[scells] = np.arange(len(scells))
    sp = np.where(parent[scells] >= 0, sid[np.maximum(parent[scells], 0)], -1)   # 물길 나무의 부모 (하류)
    # 깊이 (출구에서부터), 뿌리
    depth = np.zeros(len(scells), dtype=np.int64)
    root = np.arange(len(scells))
    for c in order_pop:
        k = sid[c]
        if k >= 0 and sp[k] >= 0:
            depth[k] = depth[sp[k]] + 1
            root[k] = root[sp[k]]
    LOG = max(1, int(depth.max()).bit_length())
    up = np.empty((LOG, len(scells)), dtype=np.int64)
    up[0] = np.where(sp >= 0, sp, np.arange(len(scells)))
    for k in range(1, LOG):
        up[k] = up[k - 1][up[k - 1]]
    # 각 칸이 처음 닿는 물길 칸
    s_of = np.full(N, -1, dtype=np.int64)
    s_l = [-1] * N
    sidl = sid.tolist()
    for c in order_pop:
        k = sidl[c]
        if k >= 0:
            s_l[c] = k
        elif par[c] >= 0:
            s_l[c] = s_l[par[c]]
    s_of = np.asarray(s_l, dtype=np.int64)
    log(f"물길 칸 {len(scells):,} (유역 {A0_KM2:.0f} km² 이상), 나무 깊이 {int(depth.max())}")

    def lca(a, b):
        a = a.copy()
        b = b.copy()
        da, db = depth[a], depth[b]
        sw = da < db
        a[sw], b[sw] = b[sw], a[sw]
        diff = np.abs(da - db)
        for k in range(LOG):
            m = (diff >> k) & 1 == 1
            a[m] = up[k][a[m]]
        for k in range(LOG - 1, -1, -1):
            m = up[k][a] != up[k][b]
            a[m] = up[k][a[m]]
            b[m] = up[k][b[m]]
        return np.where(a == b, a, up[0][a])

    # ---------- 분수계 변: 이웃한 두 칸의 물이 만나는 곳까지의 거리 ----------
    idx = np.arange(N).reshape(ny, nx)
    Zs = ndimage.gaussian_filter(Z, 1.0)   # 능선 표고 (새기지 않은 표고)
    Zf = Zs.ravel()
    zstream = Z.ravel()[scells]            # 물길 칸의 표고
    scx = (scells % nx + 0.5) * CS
    scy = (scells // nx + 0.5) * CS

    def edge_measure(a, b):
        ok = landf[a] & landf[b]
        a, b = a[ok], b[ok]
        sa, sb = s_of[a], s_of[b]
        ok2 = (sa >= 0) & (sb >= 0) & (sa != sb)
        a, b, sa, sb = a[ok2], b[ok2], sa[ok2], sb[ok2]
        same = root[sa] == root[sb]
        Dkm = np.zeros(len(a))
        l = lca(sa[same], sb[same])
        comparable = np.zeros(len(a), dtype=bool)
        la = flen[a[same]] - flen[scells[l]]
        lb = flen[b[same]] - flen[scells[l]]
        Dkm[same] = np.maximum(la, lb)
        # 같은 물길의 위아래(한쪽이 본류 비탈)는 긴 쪽 물길 길이로 잰다 — 그대로 둔다
        ra, rb = root[sa[~same]], root[sb[~same]]
        sep = np.hypot(scx[ra] - scx[rb], scy[ra] - scy[rb]) * MPU / 1000.0
        Dkm[~same] = np.maximum(flen[a[~same]], flen[b[~same]]) + sep / 2
        ze = np.maximum(Zf[a], Zf[b])
        hand = 0.5 * ((Zf[a] - zstream[sa]) + (Zf[b] - zstream[sb]))
        return a, b, Dkm, ze, hand

    # 가로 이웃 (a | b): 경계는 세로 변, 꼭짓점 (i+1, j)–(i+1, j+1)
    a_h, b_h, D_h, z_h, h_h = edge_measure(idx[:, :-1].ravel(), idx[:, 1:].ravel())
    a_v, b_v, D_v, z_v, h_v = edge_measure(idx[:-1, :].ravel(), idx[1:, :].ravel())

    def tier_of(D, ze, hand):
        t = np.full(len(D), -1, dtype=np.int64)
        for k in range(4):
            t[(D >= TIER_KM[k])] = k
        keep = t >= 0
        tt = np.maximum(t, 0)
        keep &= (ze >= np.asarray(Z_MIN)[tt]) & (hand >= np.asarray(HAND_MIN)[tt])
        return t, keep

    t_h, k_h = tier_of(D_h, z_h, h_h)
    t_v, k_v = tier_of(D_v, z_v, h_v)
    # 꼭짓점 번호: (ny+1)×(nx+1)
    NXc = nx + 1

    def node(i, j):
        return j * NXc + i

    edges = {}   # (n1, n2) -> tier
    adj = {}
    low = {}     # 낮거나 밋밋해서 걷어 낸 변 가운데 큰 줄기(tier 2 이상)인 것
    m = t_h >= 0
    ai, aj = a_h[m] % nx, a_h[m] // nx
    for i, j, t, k in zip(ai.tolist(), aj.tolist(), t_h[m].tolist(), k_h[m].tolist()):
        n1, n2 = node(i + 1, j), node(i + 1, j + 1)
        if k:
            edges[(n1, n2)] = t
        elif t >= 2:
            low[(n1, n2)] = t
    m = t_v >= 0
    ai, aj = a_v[m] % nx, a_v[m] // nx
    for i, j, t, k in zip(ai.tolist(), aj.tolist(), t_v[m].tolist(), k_v[m].tolist()):
        n1, n2 = node(i, j + 1), node(i + 1, j + 1)
        if k:
            edges[(n1, n2)] = t
        elif t >= 2:
            low[(n1, n2)] = t
    # 낮은 고개 잇기: 걷어 낸 큰 줄기 변이 이어진 덩어리가 GAP_KM 이하이고, 남은 큰 줄기에 두 곳 이상 닿으면 되살린다
    big_nodes = set()
    for (n1, n2), t in edges.items():
        if t >= 2:
            big_nodes.add(n1); big_nodes.add(n2)
    uf = {}

    def find(x):
        while uf.setdefault(x, x) != x:
            uf[x] = uf[uf[x]]
            x = uf[x]
        return x

    for (n1, n2) in low:
        uf[find(n1)] = find(n2)
    comps = {}
    for e in sorted(low):
        comps.setdefault(find(e[0]), []).append(e)
    n_bridge, bridge_km = 0, 0.0
    for key in sorted(comps):
        es = comps[key]
        km = len(es) * cell_km
        touch = {n for e in es for n in e if n in big_nodes}
        if km <= GAP_KM and len(touch) >= 2:
            n_bridge += 1
            bridge_km += km
            for e in es:
                edges[e] = low[e]
    log(f"낮은 고개 구간 {n_bridge}곳 ({bridge_km:.0f} km) 을 이어 그림")
    for (n1, n2) in edges:
        adj.setdefault(n1, []).append(n2)
        adj.setdefault(n2, []).append(n1)
    log(f"분수계 변 {len(edges):,}개")
    DBG["edges"] = [((n1 % NXc) * CS, (n1 // NXc) * CS, (n2 % NXc) * CS, (n2 // NXc) * CS, t) for (n1, n2), t in edges.items()]

    def etier(n1, n2):
        return edges[(n1, n2) if n1 < n2 else (n2, n1)]

    # ---------- 사슬로 잇기 ----------
    used = set()
    chains = []
    for n0 in sorted(adj):
        if len(adj[n0]) == 2:
            continue
        for n1 in adj[n0]:
            if (n0, n1) in used:
                continue
            ch = [n0, n1]
            used.add((n0, n1)); used.add((n1, n0))
            while len(adj[ch[-1]]) == 2:
                a_, b_ = adj[ch[-1]]
                nxt = b_ if a_ == ch[-2] else a_
                if (ch[-1], nxt) in used:
                    break
                used.add((ch[-1], nxt)); used.add((nxt, ch[-1]))
                ch.append(nxt)
            chains.append(ch)
    for n0 in sorted(adj):   # 닫힌 고리
        for n1 in adj[n0]:
            if (n0, n1) in used:
                continue
            ch = [n0, n1]
            used.add((n0, n1)); used.add((n1, n0))
            while True:
                a_, b_ = adj[ch[-1]]
                nxt = b_ if a_ == ch[-2] else a_
                if (ch[-1], nxt) in used:
                    break
                used.add((ch[-1], nxt)); used.add((nxt, ch[-1]))
                ch.append(nxt)
            chains.append(ch)

    # 사슬마다 변의 tier 를 고르게 (중앙값 창) 해 둔다
    pieces = []   # (tiers per edge, [nodes])
    for ch in chains:
        ts = np.array([etier(ch[k], ch[k + 1]) for k in range(len(ch) - 1)])
        if len(ts) >= 5:
            ts = ndimage.median_filter(ts, size=min(15, len(ts) // 2 * 2 + 1), mode="nearest")
        pieces.append((ts, ch))

    # ---------- 획으로 묶기: 갈림점에서 가장 곧게 이어지는 둘을 잇는다 (같은 크기끼리 먼저) ----------
    def npos(n):
        return np.array([(n % NXc) * CS, (n // NXc) * CS], float)

    ends = {}
    for pi, (ts, ch) in enumerate(pieces):
        if ch[0] == ch[-1]:
            continue
        ends.setdefault(ch[0], []).append((pi, 0))
        ends.setdefault(ch[-1], []).append((pi, 1))

    def out_dir(pi, e):
        ch = pieces[pi][1]
        k = min(8, len(ch) - 1)
        p0 = npos(ch[0] if e == 0 else ch[-1])
        p1 = npos(ch[k] if e == 0 else ch[-1 - k])
        v = p1 - p0
        return v / (np.hypot(*v) + 1e-9)

    def end_tier(pi, e):
        ts = pieces[pi][0]
        return int(ts[0] if e == 0 else ts[-1])

    link = {}   # (pi, e) -> (pj, e2)
    for n in sorted(ends):
        lst = ends[n]
        if len(lst) < 2:
            continue
        cand = []
        for x in range(len(lst)):
            for y in range(x + 1, len(lst)):
                (pi, e1), (pj, e2) = lst[x], lst[y]
                if pi == pj:
                    continue
                t1, t2 = end_tier(pi, e1), end_tier(pj, e2)
                cosang = float(np.dot(out_dir(pi, e1), out_dir(pj, e2)))   # -1 이면 곧게 이어짐
                if len(lst) == 2 or cosang < 0.3:
                    cand.append((-min(t1, t2), abs(t1 - t2), cosang, x, y))
        cand.sort()
        taken = set()
        for _, _, _, x, y in cand:
            if x in taken or y in taken:
                continue
            taken.add(x); taken.add(y)
            link[lst[x]] = lst[y]
            link[lst[y]] = lst[x]
    strokes = []
    done = set()
    for pi in range(len(pieces)):
        if pi in done:
            continue
        cur, e = pi, 0
        guard = 0
        while (cur, e) in link and guard < 100000:
            pj, e2 = link[(cur, e)]
            if pj == pi:
                break
            cur, e = pj, 1 - e2
            guard += 1
        seq, tsq = [], []
        while True:
            done.add(cur)
            ts, ch = pieces[cur]
            if e == 1:
                ts, ch = ts[::-1], ch[::-1]
            seq.extend(ch if not seq else ch[1:])
            tsq.extend(ts.tolist())
            far = (cur, 1 - e)
            if far in link and link[far][0] not in done:
                cur, e = link[far]
            else:
                break
        strokes.append((np.array(tsq), seq))
    log(f"사슬 {len(chains):,} -> 획 {len(strokes):,}")

    # ---------- 다듬기 ----------
    def slen(p):
        return float(np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1])).sum())

    def chaikin(q):
        """모서리 깎기 한 번 (끝점은 그대로): 점 간격이 절반이 되어 곧은 변으로 그려도 매끈하다."""
        if len(q) < 3:
            return q
        a_, b_ = q[:-1], q[1:]
        out = np.empty((2 * (len(q) - 1), 2))
        out[0::2] = 0.75 * a_ + 0.25 * b_
        out[1::2] = 0.25 * a_ + 0.75 * b_
        return np.vstack([q[:1], out, q[-1:]])

    strokes.sort(key=lambda s: (-int(s[0].max()), -len(s[1]), s[1][0]))
    fixed = {}
    smooth = []
    run_min_edges = max(4, int(round(RUN_MIN_KM / cell_km)))
    for ts, seq in strokes:
        p = np.array([npos(n) for n in seq])
        closed = seq[0] == seq[-1]
        for k in (0, len(seq) - 1):
            if closed:
                break
            if seq[k] in fixed:
                p[k] = fixed[seq[k]]
        for _ in range(SMOOTH_ITERS):
            q = p.copy()
            q[1:-1] = 0.25 * p[:-2] + 0.5 * p[1:-1] + 0.25 * p[2:]
            if closed:
                q[0] = q[-1] = 0.25 * p[-2] + 0.5 * p[0] + 0.25 * p[1]
            p = q
        for k, n in enumerate(seq):
            fixed.setdefault(n, p[k].copy())
        # 획 안에서 크기가 바뀌는 곳으로 나눈다 (짧은 구간은 이웃에 붙인다)
        runs = []
        s0 = 0
        for k in range(1, len(ts) + 1):
            if k == len(ts) or ts[k] != ts[s0]:
                runs.append([s0, k, int(ts[s0])])
                s0 = k
        while len(runs) > 1:
            q = min(range(len(runs)), key=lambda i: runs[i][1] - runs[i][0])
            if runs[q][1] - runs[q][0] >= run_min_edges:
                break
            left = runs[q - 1] if q > 0 else None
            right = runs[q + 1] if q + 1 < len(runs) else None
            if right is None or (left is not None and left[2] >= right[2]):
                left[1] = runs[q][1]
            else:
                right[0] = runs[q][0]
            runs.pop(q)
            k = 0
            while k + 1 < len(runs):   # 같은 크기가 이웃하면 합친다
                if runs[k][2] == runs[k + 1][2]:
                    runs[k][1] = runs[k + 1][1]
                    runs.pop(k + 1)
                else:
                    k += 1
        for s0, s1, t in runs:
            smooth.append((t, chaikin(p[s0:s1 + 1])))

    # ---------- 자르기: 대한민국 육지 칸 밖, 물줄기 가까이, 호수 안 ----------
    river_lines = [shapely.LineString(p) for p in drawn]
    river_union_tree = STRtree(river_lines)
    lake_polys = []
    for lk in w.get("lakes", []):
        for ring in lk.get("rings", []):
            rr = np.asarray(ring, float).reshape(-1, 2)
            if len(rr) >= 4:
                poly = shapely.Polygon(rr)
                if poly.is_valid and poly.area > 0:
                    lake_polys.append(poly)
                    break   # 바깥 고리만
    lake_tree = STRtree(lake_polys) if lake_polys else None

    def cut_line(p):
        """선 -> 허용되는 구간들. 2 단위 간격으로 촘촘히 본 뒤 금지 점을 빼고 다시 묶는다."""
        q = densify(p, 2.0)
        cells = hex_cell(q[:, 0], q[:, 1], g["cols"], g["rows"], g["radius"])
        bad = (cells < 0) | (owner[np.maximum(cells, 0)] < 0)
        pts = shapely.points(q)
        near = river_union_tree.query(pts, predicate="dwithin", distance=RIVER_CLEAR)
        bad[np.unique(near[0])] = True
        if lake_tree is not None:
            inl = lake_tree.query(pts, predicate="within")
            bad[np.unique(inl[0])] = True
        out = []
        s = None
        for k in range(len(q) + 1):
            if k < len(q) and not bad[k]:
                if s is None:
                    s = k
            elif s is not None:
                if k - s >= 2:
                    out.append(q[s:k])
                s = None
        return out, int(bad.sum())

    lines = []
    n_cut_pts = 0
    for t, p in smooth:
        segs, nb = cut_line(p)
        n_cut_pts += nb
        for s in ([p] if nb == 0 else segs):
            ls = shapely.LineString(s).simplify(SIMPLIFY_TOL, preserve_topology=False)
            lines.append((t, np.asarray(ls.coords)))

    # 좌표를 소수 한 자리로 맞춘 뒤(파일에 쓰는 값 그대로) 교차 검사, 걸리는 선은 그 자리에서 끊는다
    water_tree = STRtree(river_lines + [poly.exterior for poly in lake_polys])

    def crossings(p):
        ls = shapely.LineString(p)
        hit = water_tree.query(ls, predicate="intersects")
        return [int(h) for h in hit]

    final = []
    n_fix = 0
    short_dropped = [0, 0, 0, 0]
    queue = [(t, np.round(p, 1)) for t, p in lines]
    while queue:
        t, p = queue.pop()
        keep = np.ones(len(p), dtype=bool)
        keep[1:] = np.any(np.diff(p, axis=0) != 0, axis=1)
        p = p[keep]
        if len(p) < 2 or slen(p) * MPU / 1000.0 < 1.2:
            continue
        hits = crossings(p)
        if not hits:
            final.append((t, p))
            continue
        n_fix += 1
        # 걸리는 변을 찾아 그 양쪽으로 나눈다
        for k in range(len(p) - 1):
            seg = shapely.LineString(p[k:k + 2])
            if len(water_tree.query(seg, predicate="intersects")):
                if k >= 1:
                    queue.append((t, p[:k + 1]))
                if k + 1 < len(p) - 1:
                    queue.append((t, p[k + 1:]))
                break
    # 짧은 곁가지 치기: 한쪽 끝이라도 다른 선에 닿지 않은 짧은 선을 되풀이해 뺀다 (양쪽이 이어진 짧은 이음매는 둔다)
    final.sort(key=lambda s: (-s[0], -slen(s[1]), float(s[1][0, 0]), float(s[1][0, 1])))
    while True:
        geoms = [shapely.LineString(p) for _, p in final]
        tree = STRtree(geoms)
        drop = set()
        for k, (t, p) in enumerate(final):
            km = slen(p) * MPU / 1000.0
            if km >= MIN_LEN_KM[t] * 1.5:
                continue
            free = 0
            for e in (p[0], p[-1]):
                near = [int(h) for h in tree.query(shapely.Point(e), predicate="dwithin", distance=JOIN_TOL) if int(h) != k]
                if not near:
                    free += 1
            # 큰 줄기(tier 2 이상)는 물줄기 머리에서 잘려 한쪽이 뜬 이음매를 살린다 (3 km 미만만 뺀다)
            lim = 3.0 if t >= 2 else MIN_LEN_KM[t]
            if (free >= 1 and km < lim) or (free == 2 and km < MIN_LEN_KM[t] * 1.5):
                drop.add(k)
        if not drop:
            break
        for k in drop:
            short_dropped[final[k][0]] += 1
        final = [x for k, x in enumerate(final) if k not in drop]

    # ---------- 검사 (독립 계산: 모든 산줄기 변 × 모든 물줄기 변) ----------
    rseg = []
    for p in drawn:
        rseg.append(np.column_stack([p[:-1], p[1:]]))
    rseg = np.vstack(rseg)
    rtree = STRtree(shapely.linestrings(rseg.reshape(-1, 2, 2)))
    n_cross = 0
    n_seg = 0
    for t, p in final:
        segs = shapely.linestrings(np.column_stack([p[:-1], p[1:]]).reshape(-1, 2, 2))
        n_seg += len(segs)
        n_cross += len(rtree.query(segs, predicate="intersects")[0])
    n_lake = 0
    if lake_tree is not None:
        for t, p in final:
            n_lake += len(lake_tree.query(shapely.LineString(p), predicate="intersects"))

    # 꼭짓점 표고
    def zat(p):
        return ndimage.map_coordinates(Zs, [p[:, 1] / CS - 0.5, p[:, 0] / CS - 0.5], order=1, mode="nearest")

    out_lines = []
    stats = {k: {"lines": 0, "km": 0.0} for k in range(4)}
    all_z, all_w = [], []
    low_km = 0.0
    for t, p in final:
        zz = zat(p)
        d = np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1])) * MPU / 1000.0
        zm = 0.5 * (zz[:-1] + zz[1:])
        low_km += float(d[zm < 100].sum())
        all_z.append(zm); all_w.append(d)
        stats[t]["lines"] += 1
        stats[t]["km"] += float(d.sum())
        out_lines.append({"t": int(t), "pts": [int(v) if float(v).is_integer() else round(float(v), 1) for v in p.ravel()], "z": [int(round(v)) for v in zz]})
    all_z = np.concatenate(all_z) if all_z else np.zeros(1)
    all_w = np.concatenate(all_w) if all_w else np.ones(1)
    total_km = float(all_w.sum())
    ridge_mean_z = float((all_z * all_w).sum() / max(total_km, 1e-9))
    # 대한민국 육지의 평균 표고 (계산 격자, 육지 칸 안)
    cells_g = hex_cell(GX.ravel(), GY.ravel(), g["cols"], g["rows"], g["radius"])
    kr = (cells_g >= 0) & (owner[np.maximum(cells_g, 0)] >= 0) & landf
    land_mean_z = float(Z.ravel()[kr].mean())
    n_vert = sum(len(l["z"]) for l in out_lines)

    checks = {
        "river_crossings": int(n_cross),
        "rivers_tested": len(drawn),
        "river_segments_tested": int(len(rseg)),
        "ridge_segments_tested": int(n_seg),
        "river_clearance_units": RIVER_CLEAR,
        "lake_crossings": int(n_lake),
        "lakes_tested": len(lake_polys),
        "lines": len(out_lines),
        "vertices": n_vert,
        "total_km": round(total_km, 1),
        "by_tier": {str(k): {"lines": stats[k]["lines"], "km": round(stats[k]["km"], 1)} for k in range(4)},
        "below_100m_share_pct": round(100 * low_km / max(total_km, 1e-9), 2),
        "short_pieces_dropped": {str(k): short_dropped[k] for k in range(4)},
        "shortest_kept_km": round(min((slen(p) * MPU / 1000.0 for _, p in final), default=0), 1),
        "ridge_mean_elev_m": round(ridge_mean_z, 1),
        "land_mean_elev_m": round(land_mean_z, 1),
        "lines_refit_after_rounding": n_fix,
        "low_pass_bridges": {"count": n_bridge, "km": round(bridge_km, 1), "max_km": GAP_KM},
        "smoothing": ("곡선 다듬기(1-2-1 고르기 %d회, 모서리 깎기 1회, 허용 오차 %.1f 단위로 줄이기)와 소수 한 자리 맞춤을 모두 끝낸 뒤의 좌표로 "
                      "교차를 검사했다. 그리는 쪽은 꼭짓점을 곧은 변으로 잇기만 하면 검사한 그대로다.") % (SMOOTH_ITERS, SIMPLIFY_TOL),
    }
    doc = {
        "version": VERSION,
        "generated": datetime.date.today().isoformat(),
        "rule": RULE,
        "method": ("가지고 있는 표고 자료(SRTM30+, 약 0.9 km 격자)와 물줄기(WAMIS 하천 유로선)로 계산한 분수계 산줄기다. "
                   "물줄기를 표고에 새긴 뒤 물이 흐르는 방향을 따져, 이웃한 두 곳의 물이 멀리 가서야 만나는(또는 서로 다른 바다로 가는) 경계일수록 큰 줄기로 쳤다. "
                   "계산한 선이므로 고유 이름을 붙이지 않았고, 산경표나 교과서의 산맥과 꼭 같지 않다. 표고 격자가 거칠어 낮은 구릉·평야·바닷가에서는 선을 그리지 않았으며, "
                   "휴전선 북쪽은 물줄기 자료가 없어 그리지 않았다."),
        "source": {
            "dem": {"file": "data/raw/terrain/srtm30plus_korea.csv", "name": "SRTM30+", "grid": dem_info},
            "rivers": {"drawn": f"site/data/world.json rivers {len(drawn)}개 (WAMIS 국가·지방하천, 검사 대상)",
                       "burn_only": f"data/build/layers/rivers.geojson WAMIS 유로선 {raw_note} (물길 새기기에만 씀)"},
            "world_version": w.get("version"),
        },
        "params": {"cell_units": CS, "cell_m": CS * MPU, "burn_m": [BURN_DRAWN, BURN_RAW], "stream_min_km2": A0_KM2,
                   "tier_split_km": TIER_KM, "elev_min_m": Z_MIN, "height_above_stream_min_m": HAND_MIN,
                   "min_len_km": MIN_LEN_KM, "smooth_iters": SMOOTH_ITERS, "low_pass_gap_km": GAP_KM, "simplify_units": SIMPLIFY_TOL},
        "encoding": ("lines[].pts = [x0,y0,x1,y1,…] world.json 과 같은 화면 단위(소수 한 자리까지, 1 단위 = %g m, 원점 왼쪽 위, y 는 남쪽으로 증가). "
                     "lines[].z = 꼭짓점마다의 표고(m, 정수). lines[].t = 줄기 크기 0–3 (3 이 가장 큼). 큰 것부터 적는다.") % MPU,
        "checks": checks,
        "tiers": [{"t": k, "name": TIER_NAMES[k],
                   "rule": f"두 쪽의 물이 만나기까지 흐르는 거리(다른 바다로 가면 긴 쪽 물길 + 하구 사이 거리의 절반)가 {TIER_KM[k]:.0f} km 이상, "
                           f"능선 표고 {Z_MIN[k]:.0f} m 이상, 물길 위 높이 {HAND_MIN[k]:.0f} m 이상, 길이 {MIN_LEN_KM[k]:.0f} km 이상"
                           + (f". 이보다 낮거나 밋밋한 고개라도 {GAP_KM:.0f} km 이하이고 양쪽이 큰 줄기에 닿으면 이어 그린다" if k >= 2 else "")}
                  for k in (3, 2, 1, 0)],
        "lines": out_lines,
    }
    txt = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    nbytes = len(txt.encode("utf-8"))

    log("---- 검사 ----")
    log(f"규칙: {RULE}")
    log(f"물줄기 교차: {n_cross}건 (산줄기 변 {n_seg:,} × 물줄기 {len(drawn)}개·변 {len(rseg):,}) / 호수 가로지름 {n_lake}건 (호수 {len(lake_polys)}개)")
    for k in (3, 2, 1, 0):
        log(f"tier {k} {TIER_NAMES[k]}: {stats[k]['lines']}선, {stats[k]['km']:.0f} km (짧아서 뺀 조각 {short_dropped[k]})")
    log(f"합계 {len(out_lines)}선, {total_km:.0f} km, 꼭짓점 {n_vert:,}, 가장 짧은 선 {checks['shortest_kept_km']} km")
    log(f"표고 100 m 아래 길이 몫 {checks['below_100m_share_pct']}%")
    log(f"산줄기 평균 표고 {ridge_mean_z:.0f} m / 대한민국 육지 평균 {land_mean_z:.0f} m")
    log(f"물줄기 가까이·나라 밖·호수 안이라 뺀 점 {n_cut_pts:,}, 정수 맞춤 뒤 다시 끊은 선 {n_fix}")
    log(f"낮은 고개 이음 {n_bridge}곳 {bridge_km:.0f} km (한 곳 {GAP_KM:.0f} km 이하)")
    log(f"파일 {nbytes:,} 바이트 (상한 {MAX_BYTES:,})")

    fail = []
    if n_cross != 0:
        fail.append(f"물줄기 교차 {n_cross}건")
    if n_lake != 0:
        fail.append(f"호수 가로지름 {n_lake}건")
    if nbytes > MAX_BYTES:
        fail.append(f"파일 {nbytes} 바이트 > {MAX_BYTES}")
    if not out_lines:
        fail.append("선이 없다")
    if ridge_mean_z <= land_mean_z:
        fail.append("산줄기가 평균보다 낮은 곳에 있다")
    if fail:
        log("실패:", "; ".join(fail))
        sys.exit(1)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)
    tot = sum(os.path.getsize(os.path.join(os.path.dirname(OUT), fn)) for fn in os.listdir(os.path.dirname(OUT)) if fn.endswith(".json"))
    log(f"씀: {OUT}  (site/data/*.json 합계 {tot:,} 바이트 = {tot / 1e6:.2f} MB)")
    log(f"걸린 시간 {(datetime.datetime.now() - t_start).total_seconds():.0f}초")

    if args.debug:
        debug_render(args.debug, w, doc, Zs, land, CS, drawn)


def debug_render(folder, w, doc, Zs, land, cs, drawn):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    os.makedirs(folder, exist_ok=True)
    Wu, Hu = w["width"], w["height"]
    views = {"nation": (900, 6000, 900, 6200, 14, (3, 2)), "nation_all": (900, 6000, 900, 6200, 14, (3, 2, 1, 0)),
             "gangwon": (3300, 5300, 1100, 2900, 14, (3, 2, 1, 0)), "jiri": (2600, 4400, 3300, 4900, 14, (3, 2, 1, 0)),
             "honam": (1500, 3300, 3000, 4700, 14, (3, 2, 1, 0)), "jeju": (1700, 2900, 5500, 6200, 12, (3, 2, 1, 0)),
             "yeongnam": (3800, 5400, 2800, 4600, 14, (3, 2, 1, 0))}
    shade = np.where(land, Zs, np.nan)
    for name, (x0, x1, y0, y1, size, tiers) in views.items():
        fig, ax = plt.subplots(figsize=(size, size * (y1 - y0) / (x1 - x0)), dpi=110)
        ax.imshow(shade, extent=(0, Zs.shape[1] * cs, Zs.shape[0] * cs, 0), cmap="Greys", vmin=-200, vmax=2600, interpolation="bilinear")
        ax.add_collection(LineCollection([p for p in drawn], colors="#3b78b5", linewidths=0.7))
        base = {3: 2.4, 2: 1.5, 1: 0.9, 0: 0.5}
        if DBG.get("edges") and name != "nation":
            col = {3: "#d22", 2: "#e80", 1: "#3a3", 0: "#99c"}
            for t in (0, 1, 2, 3):
                ax.add_collection(LineCollection([[(a, b), (c, d)] for a, b, c, d, tt in DBG["edges"] if tt == t], colors=col[t], linewidths=2.2, alpha=0.55))
        for ln in doc["lines"]:
            if ln["t"] not in tiers:
                continue
            p = np.asarray(ln["pts"], float).reshape(-1, 2)
            zz = np.asarray(ln["z"], float)
            segs = np.stack([p[:-1], p[1:]], axis=1)
            wv = base[ln["t"]] * (0.55 + 0.9 * np.clip(0.5 * (zz[:-1] + zz[1:]) / 1200.0, 0, 1))
            ax.add_collection(LineCollection(segs, colors="#111", linewidths=wv, capstyle="round"))
        ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_axis_off()
        fig.subplots_adjust(0, 0, 1, 1)
        fig.savefig(os.path.join(folder, f"ridge_{name}.png"))
        plt.close(fig)
    log("검토용 그림:", folder)


if __name__ == "__main__":
    main()
