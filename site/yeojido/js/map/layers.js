// 지도 층 — 아이콘(불가사의·자원·기반시설·교역), 국립공원 영역, 도로·철도 선, 접경 띠, 교역로.
// 어느 배율에서 무엇이 나오는지는 자료가 정한다(item.tier 와 zoom.levels). 여기서는 놓는 차례와 겹침만 다룬다:
//   1) 원전은 늘 그린다(현판이 먼저 비켜 서고, 그래도 겹치면 가까운 빈 칸으로 옮겨 지시선을 긋는다).
//   2) 전국 배율의 공항·무역항(tier 0)도 숨기지 않고 필요하면 옮긴다.
//   3) 나머지는 종류마다 값이 큰 것부터 돌아가며 놓고, 현판이나 먼저 놓인 아이콘과 겹치면 그 배율에서는 그리지 않는다.
// 전국·중간 배율에는 놓는 수의 상한이 있다 (종이가 조용해야 한다). 찾기와 장의 목록은 배율과 관계없이 전부 닿는다.

import { KINDS, NARROW } from '../config.js';
import { itemExtra, zoomRules, unplacedItems } from '../adapter.js';
import { KIND_ICON, glyphPath } from '../icons.js';
import { smooth } from './land.js';

const INK = '#1D1A16', BAEK = '#FBF6E8', HI = '#F8F3E6', JU = '#B8321F', JJOK = '#26465F', NOK = '#3F6B52';
const STYLE = { // 묶음 -> 배지 꼴·빛
  wonders: { shape: 'square', fill: JU, glyph: BAEK, ring: BAEK },
  infra: { shape: 'circle', fill: JJOK, glyph: BAEK, ring: BAEK },
  trade: { shape: 'diamond', fill: NOK, glyph: BAEK, ring: BAEK },
  resources: { shape: 'circle', fill: HI, glyph: INK, ring: INK },
};
export { itemExtra };
export const groupStyle = (kind) => STYLE[(KINDS[kind] || {}).layer] || STYLE.resources;


const cmp = (a, b) => ((KINDS[a.kind] || { pri: 9 }).pri - (KINDS[b.kind] || { pri: 9 }).pri) || ((b.value ?? -1) - (a.value ?? -1));

export class LayerMap {
  constructor(app, L) {
    this.app = app; this.L = L;
    const G = app.grid, W = app.D.world;
    const Z = this.zoom = zoomRules(L);
    this.items = L.items.filter((it) => KINDS[it.kind]);
    this.byId = new Map(L.items.map((i) => [i.id, i]));
    this.groups = Z.groups.map((g) => ({ ...g, memberItems: g.members.map((m) => this.byId.get(m)).filter(Boolean) }));
    for (const g of this.groups) this.byId.set(g.id, g);
    for (const u of unplacedItems(L)) if (!this.byId.has(u.id)) this.byId.set(u.id, u);
    // 항목마다: 덧붙은 값, 종류 안 값 순위
    const byKind = new Map();
    for (const it of this.items) {
      it.x = itemExtra(it);
      (byKind.get(it.kind) || byKind.set(it.kind, []).get(it.kind)).push(it);
    }
    for (const lst of byKind.values()) { lst.sort((a, b) => (b.value ?? -1) - (a.value ?? -1)); lst.forEach((it, k) => { it._rk = k; }); }
    this.byCell = new Map();
    for (const it of this.items) { if (it.cell < 0) continue; (this.byCell.get(it.cell) || this.byCell.set(it.cell, []).get(it.cell)).push(it); }
    for (const lst of this.byCell.values()) lst.sort(cmp);

    // 선: 세계 좌표 경로로 한 번만 만든다
    // 선은 세계 좌표 경로로 한 번만 만들되, 바둑판 조각으로 나눠 두고 보이는 조각만 긋는다
    const CH = this.CH = 640;
    const chunked = (list) => {
      const m = new Map();
      for (const r of list) {
        const a = r.pts;
        if (a.length < 4) continue;
        const key = Math.floor((r.bb[0] + r.bb[2]) / 2 / CH) + ':' + Math.floor((r.bb[1] + r.bb[3]) / 2 / CH);
        let p = m.get(key);
        if (!p) m.set(key, (p = new Path2D()));
        p.moveTo(a[0], a[1]);
        for (let q = 2; q < a.length; q += 2) p.lineTo(a[q], a[q + 1]);
      }
      return m;
    };
    this.pRoad1 = chunked(L.roads.filter((r) => r.tier === 1));
    this.pRoad2 = chunked(L.roads.filter((r) => r.tier !== 1));
    this.pRail = chunked(L.rails);
    const segPath = (segs) => { const p = new Path2D(); for (const [x0, y0, x1, y1] of segs) { p.moveTo(x0, y0); p.lineTo(x1, y1); } return p; };
    const hexPath = (cells) => { const p = new Path2D(); for (const i of cells) { p.moveTo(G.cx[i] + G.corner[0][0], G.cy[i] + G.corner[0][1]); for (let k = 1; k < 6; k++) p.lineTo(G.cx[i] + G.corner[k][0], G.cy[i] + G.corner[k][1]); p.closePath(); } return p; };
    // 국립공원 영역
    this.parkShapes = L.parks.map((p) => {
      let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
      for (const c of p.cells) { x0 = Math.min(x0, G.cx[c]); x1 = Math.max(x1, G.cx[c]); y0 = Math.min(y0, G.cy[c]); y1 = Math.max(y1, G.cy[c]); }
      return { edge: segPath(app.land.outline(p.cells)), fill: hexPath(p.cells), bb: [x0 - G.W, y0 - G.W, x1 + G.W, y1 + G.W] };
    });
    // 접경
    this.pFrontEdge = null;
    if (L.frontier) {
      const ks = new Set();
      for (const a of L.frontier.areas) for (const c of a.sgg) { const k = W.countyIndex.get(c); if (k != null) ks.add(k); }
      const cells = [];
      for (let i = 0; i < G.n; i++) if (W.owner[i] >= 0 && ks.has(W.county[i])) cells.push(i);
      this.pFrontEdge = segPath(app.land.outline(cells));
      this.pFrontFill = hexPath(cells);
    }
    // 교역로: 시도 청사 칸 두 곳을 잇는 완만한 곡선. 굵기는 두 방향 합 톤에 비례
    this.routes = [];
    this.routeById = new Map();
    if (L.trade) {
      const tmax = Math.max(1, ...L.trade.segments.map((g) => g.total || 0));
      for (const g of L.trade.segments) {
        const A = L.trade.anchors[g.a], B = L.trade.anchors[g.b];
        this.routeById.set(g.id, g);
        if (!A || !B || A.cell == null || B.cell == null) continue;
        const ax = G.cx[A.cell], ay = G.cy[A.cell], bx = G.cx[B.cell], by = G.cy[B.cell];
        const dx = bx - ax, dy = by - ay, len = Math.hypot(dx, dy) || 1;
        Object.assign(g, { ax, ay, bx, by, qx: (ax + bx) / 2 - dy * 0.18, qy: (ay + by) / 2 + dx * 0.18, w: Math.max(1.2, (11 * (g.total || 0)) / tmax), len });
        this.routes.push(g);
      }
      this.routes.sort((p, q) => (q.total || 0) - (p.total || 0));
    }
    this.routeScreen = [];
    this.placed = [];
    this.sprites = new Map();
    this._hatch = null;
  }

  kindOn(kind) { const K = KINDS[kind]; return !!K && this.app.layerVisible(K.layer, K.sub); }
  zoomTier(z) { let t = 0; for (const lv of this.zoom.levels) if (z >= lv.zMin) t = lv.tier; return t; }
  badgeSize(cam) { const rc = cam.rc; return rc < 2.4 ? 14 : rc < 5 ? 16 : rc < 6.8 ? 18 : rc < 11 ? 20 : rc < 17 ? 22 : 24; }
  selId() { return this.app.selItem ? this.app.selItem.id : null; }

  // 이번 화면의 후보: 칸마다 대표 하나 + 원전은 따로 + 대학 묶음 표지
  reps(cam) {
    const key = `${cam.x.toFixed(1)}|${cam.y.toFixed(1)}|${cam.scale.toFixed(5)}|${cam.vw}|${cam.vh}|${this.selId()}|${this.stateKey()}`;
    if (this._repKey === key) return this._reps;
    const G = this.app.grid, v = cam.view(), z = cam.z, vt = this.zoomTier(z), selId = this.selId();
    const m = 40 / cam.scale;
    const inView = (c) => c >= 0 && !(G.cx[c] < v.x0 - m || G.cx[c] > v.x1 + m || G.cy[c] < v.y0 - m || G.cy[c] > v.y1 + m);
    const out = [];
    for (const [cell, lst] of this.byCell) {
      if (!inView(cell)) continue;
      const on = lst.filter((it) => it.id === selId || this.kindOn(it.kind));
      if (!on.length) continue;
      const vis = on.filter((it) => it.id === selId || (it.tier <= vt && !(it.x.grouped && it.x.grouped[vt])));
      if (!vis.length) continue;
      const first = vis.filter((it) => this.zoom.first.has(it.kind));
      const rest = vis.filter((it) => !this.zoom.first.has(it.kind));
      for (const it of first) out.push({ it, others: [], cell, prio: true });
      if (rest.length) {
        const rep = rest.find((it) => it.id === selId) || rest[0];
        out.push({ it: rep, others: on.filter((x) => x !== rep && !first.includes(x)), cell, keep: vt === 0 && rep.tier === 0 && (rep.kind === 'airport' || rep.kind === 'trade_port') });
      }
    }
    if (this.kindOn('knowledge')) for (const g of this.groups) if ((g.id === selId || g.viewTiers.includes(vt)) && inView(g.cell)) out.push({ it: g, others: [], cell: g.cell, nudge: vt > 0 });
    // 놓는 차례: 고른 것 → 원전 → 지켜야 할 공항·항만 → 종류마다 돌아가며(값 순위) → 종류 우선순위
    const rank = (r) => (r.it.id === selId ? 0 : r.prio ? 1 : r.keep ? 2 : 3);
    // 불가사의(인주 낙관)는 앞당기고, 여섯 갈래인 발전소는 한 갈래처럼 늦춘다
    const wgt = (K) => (K.layer === 'wonders' ? 0.5 : K.sub === 'power' ? 2.5 : 1);
    const score = (r) => { const K = KINDS[r.it.kind] || { pri: 9 }; return (r.it._rk ?? 0) * wgt(K) + K.pri * 0.6; };
    out.sort((a, b) => rank(a) - rank(b) || score(a) - score(b) || cmp(a.it, b.it));
    this._repKey = key; this._reps = out; this._vt = vt;
    return out;
  }
  stateKey() { const a = this.app; return Object.keys(a.layerOn).map((k) => (a.layerOn[k] ? 1 : 0)).join('') + [...a.subOff].join(','); }

  // 현판이 먼저 비켜 설 자리 (원전의 제자리)
  priorityBoxes(cam) {
    const G = this.app.grid, r = this.badgeSize(cam) / 2 + 2;
    return this.reps(cam).filter((rp) => rp.prio).map((rp) => { const [x, y] = cam.toScreen(G.cx[rp.cell], G.cy[rp.cell]); return { x: x - r, y: y - r, w: 2 * r, h: 2 * r }; });
  }

  rings(i, k) {
    const G = this.app.grid, seen = new Set([i]);
    let front = [i];
    const out = [];
    for (let d = 0; d < k; d++) { const nx = []; for (const c of front) for (const j of G.neighbors(c)) if (!seen.has(j)) { seen.add(j); nx.push(j); out.push(j); } front = nx; }
    return out;
  }

  layout(cam, labelRects = [], o = {}) {
    const app = this.app, G = app.grid, reps = this.reps(cam), vt = this._vt, selId = this.selId();
    const narrow = window.innerWidth <= NARROW;
    const size = this.badgeSize(cam), r0 = size / 2;
    const budget = vt === 0 ? (narrow ? 0 : 17) : vt === 1 ? (narrow ? 26 : 60) : 1e9; // 지켜야 할 것(원전·공항·항만) 말고 더 놓는 수
    const near = vt >= 2;
    const boxes = labelRects.map((b) => ({ x0: b.x - 1, y0: b.y - 1, x1: b.x + b.w + 1, y1: b.y + b.h + 1 }));
    for (const p of app.labels.placed || []) boxes.push({ x0: p.ax - 5, y0: p.ay - 5, x1: p.ax + 5, y1: p.ay + 5 });
    const out = [];
    const boxHit = (x, y, r) => boxes.some((b) => x + r > b.x0 && x - r < b.x1 && y + r > b.y0 && y - r < b.y1);
    const inBox = (x, y) => boxes.some((b) => x > b.x0 && x < b.x1 && y > b.y0 && y < b.y1);
    const iconHit = (x, y, r, pad) => out.some((q) => Math.abs(q.x - x) < (q.r + r) * pad && Math.abs(q.y - y) < (q.r + r) * pad);
    const inside = (x, y, r) => x > r + 2 && y > r + 2 && x < cam.vw - r - 2 && y < cam.vh - r - 2;
    const cellPx = G.W * cam.scale;
    const maxRing = Math.max(2, Math.min(12, Math.ceil(Math.max(4.5 * r0, 52) / cellPx)));
    let extra = 0;
    // 원전이 피할 자리: 같은 칸의 보통 대표 아이콘 (그 아이콘을 밀어내지 않게 원전 쪽이 옮긴다)
    const prioCells = new Set(reps.filter((rp) => rp.prio).map((rp) => rp.cell));
    const reserved = reps.filter((rp) => !rp.prio && prioCells.has(rp.cell) && rp.it.tier <= vt).map((rp) => cam.toScreen(G.cx[rp.cell], G.cy[rp.cell]));
    for (const rp of reps) {
      const [sx, sy] = cam.toScreen(G.cx[rp.cell], G.cy[rp.cell]);
      const st = rp.it.kind === 'station';
      const r = st ? (rp.it.x.hsr ? Math.max(3.6, r0 * 0.42) : Math.max(2.8, r0 * 0.32)) : r0;
      const sel = rp.it.id === selId;
      if (sel) { out.push({ ...rp, x: sx, y: sy, r, sel }); continue; }
      if (rp.prio || rp.keep || rp.nudge) {
        const free = (x, y) => !boxHit(x, y, r + 1) && !iconHit(x, y, r, 0.92) && !(rp.prio && reserved.some(([qx, qy]) => Math.abs(qx - x) < 2 * r * 0.92 && Math.abs(qy - y) < 2 * r * 0.92));
        if (free(sx, sy)) { out.push({ ...rp, x: sx, y: sy, r }); continue; }
        // 이웃 칸을 겹겹이 넓혀 가며 가장 가까운 빈 칸 (항만은 바다 쪽을 조금 더 고른다)
        const sea = rp.it.kind === 'trade_port';
        const W = app.D.world;
        const ring = this.rings(rp.cell, maxRing).map((c) => { const [x, y] = cam.toScreen(G.cx[c], G.cy[c]); return { x, y, d: Math.hypot(x - sx, y - sy) - (sea && W.owner[c] < 0 && !W.foreign[c] ? r0 : 0) }; }).sort((a, b) => a.d - b.d);
        let spot = ring.find((p) => free(p.x, p.y) && inside(p.x, p.y, r));
        if (!spot && rp.nudge) continue;
        spot = spot || { x: sx, y: sy };
        out.push({ ...rp, x: spot.x, y: spot.y, r, ...(spot.x !== sx || spot.y !== sy ? { ox: sx, oy: sy } : {}) });
        continue;
      }
      if (!st && extra >= budget) continue;
      if (near ? (inBox(sx, sy) || boxHit(sx, sy, r * 0.55)) : boxHit(sx, sy, r)) continue;
      if (iconHit(sx, sy, r, st ? 0.6 : 0.82)) continue;
      out.push({ ...rp, x: sx, y: sy, r });
      if (!st) extra++;
    }
    this.placed = out;
    this.size = size;
    return out;
  }

  // 배지 한 장 (종류·크기·기기 배율마다 한 번만 그려 둔다)
  sprite(kind, size, k, opt = '') {
    const key = `${kind}|${size}|${k}|${opt}`;
    let cv = this.sprites.get(key);
    if (cv) return cv;
    const pad = 3, px = Math.round((size + pad * 2) * k);
    cv = document.createElement('canvas');
    cv.width = cv.height = px;
    const ctx = cv.getContext('2d');
    ctx.scale(k, k);
    drawBadge(ctx, kind, size / 2 + pad, size / 2 + pad, size, opt);
    this.sprites.set(key, cv);
    if (this.sprites.size > 400) this.sprites.clear();
    return cv;
  }

  drawIcons(ctx, cam, o = {}) {
    const k = o.cdpr || 1, selId = this.selId(), size = this.size || 16;
    const dim = o.lens ? 0.9 : 1;
    // 옮긴 아이콘의 지시선과 제자리 점
    ctx.lineWidth = 1; ctx.strokeStyle = INK; ctx.fillStyle = INK;
    for (const p of this.placed) {
      if (p.ox == null) continue;
      ctx.beginPath(); ctx.moveTo(p.ox, p.oy); ctx.lineTo(p.x, p.y); ctx.stroke();
      ctx.beginPath(); ctx.arc(p.ox, p.oy, 2, 0, 6.3); ctx.fill();
    }
    ctx.globalAlpha = dim;
    for (let q = this.placed.length - 1; q >= 0; q--) {
      const p = this.placed[q], it = p.it;
      const x = Math.round(p.x), y = Math.round(p.y);
      if (it.kind === 'station') {
        ctx.beginPath(); ctx.arc(x, y, p.r, 0, 6.3);
        ctx.fillStyle = it.x.hsr ? JJOK : BAEK; ctx.fill();
        ctx.strokeStyle = it.x.hsr ? BAEK : JJOK; ctx.lineWidth = it.x.hsr ? 1 : 1.3; ctx.stroke();
      } else {
        const sp = this.sprite(it.kind, size, k);
        const w = sp.width / k;
        ctx.drawImage(sp, x - w / 2, y - w / 2, w, w);
        if (it.group) { // 대학 묶음: 묶인 수
          const n = String(it.members.length);
          ctx.font = '700 10px "Yeojido Sans", sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
          const bx = x + size / 2 + 1, by = y - size / 2 + 1;
          ctx.beginPath(); ctx.arc(bx, by, 6.5, 0, 6.3); ctx.fillStyle = BAEK; ctx.fill(); ctx.strokeStyle = INK; ctx.lineWidth = 1; ctx.stroke();
          ctx.fillStyle = INK; ctx.fillText(n, bx, by + 0.5);
        }
      }
      if (it.id === selId) {
        const rr = (it.kind === 'station' ? p.r : size / 2) + 4;
        ctx.beginPath(); ctx.arc(x, y, rr, 0, 6.3);
        ctx.strokeStyle = BAEK; ctx.lineWidth = 4; ctx.stroke();
        ctx.strokeStyle = JU; ctx.lineWidth = 2; ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
  }

  hit(sx, sy) {
    const pad = this.app.touch ? 8 : 3;
    let best = null, bd = 1e9;
    for (const p of this.placed) {
      const d = Math.hypot(sx - p.x, sy - p.y);
      if (d <= p.r + pad && d < bd) { bd = d; best = p; }
    }
    return best ? { it: best.it, others: best.others || [] } : null;
  }

  // ---------- 아이콘 아래에 깔리는 것 ----------
  hatch(ctx) {
    if (!this._hatch) {
      const c = document.createElement('canvas');
      c.width = c.height = 8;
      const x = c.getContext('2d');
      x.strokeStyle = 'rgba(63,107,82,0.34)'; x.lineWidth = 1;
      x.beginPath(); x.moveTo(-1, 9); x.lineTo(9, -1); x.moveTo(-5, 5); x.lineTo(5, -5); x.moveTo(3, 13); x.lineTo(13, 3); x.stroke();
      this._hatch = ctx.createPattern(c, 'repeat');
    }
    return this._hatch;
  }

  drawUnder(ctx, cam, o = {}) {
    const app = this.app, s = cam.scale, rc = cam.rc, lens = !!o.lens, near = smooth(6, 15, rc);
    const tx = cam.vw / 2 - cam.x * s, ty = cam.vh / 2 - cam.y * s;
    ctx.save();
    ctx.transform(s, 0, 0, s, tx, ty);
    ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    const v = cam.view(), CH = this.CH, cx0 = Math.floor(v.x0 / CH) - 1, cx1 = Math.floor(v.x1 / CH) + 1, cy0 = Math.floor(v.y0 / CH) - 1, cy1 = Math.floor(v.y1 / CH) + 1;
    const stroke = (path, color, px, dash) => {
      ctx.strokeStyle = color; ctx.lineWidth = px / s; ctx.setLineDash(dash ? dash.map((d) => d / s) : []);
      if (path instanceof Map) { for (let cy = cy0; cy <= cy1; cy++) for (let cx = cx0; cx <= cx1; cx++) { const p = path.get(cx + ':' + cy); if (p) ctx.stroke(p); } }
      else ctx.stroke(path);
    };
    // 접경: 엷은 먹 바탕 + 먹 점선 띠
    if (this.pFrontEdge && app.layerVisible('frontier', 'frontier')) {
      ctx.fillStyle = lens ? 'rgba(29,26,22,0.05)' : 'rgba(29,26,22,0.09)'; ctx.fill(this.pFrontFill);
      stroke(this.pFrontEdge, 'rgba(251,246,232,0.8)', 3.4);
      ctx.lineCap = 'butt';
      stroke(this.pFrontEdge, 'rgba(29,26,22,0.82)', 1.6, [1.6, 3.2]);
      ctx.lineCap = 'round';
    }
    // 국립공원 영역 (다가갔을 때)
    if (rc >= 5.2 && app.layerVisible('wonders', 'national_park')) {
      const a = smooth(5.2, 6.8, rc) * (lens ? 0.6 : 1);
      ctx.globalAlpha = a;
      const pat = this.hatch(ctx);
      const shapes = this.parkShapes.filter((q) => !(q.bb[2] < v.x0 || q.bb[0] > v.x1 || q.bb[3] < v.y0 || q.bb[1] > v.y1));
      if (pat && pat.setTransform) { pat.setTransform(new DOMMatrix().scale(1 / s)); ctx.fillStyle = pat; for (const q of shapes) ctx.fill(q.fill); }
      ctx.lineCap = 'butt';
      for (const q of shapes) stroke(q.edge, NOK, 1.1 + 0.4 * near, [4, 3]);
      ctx.lineCap = 'round';
      ctx.globalAlpha = 1;
    }
    // 길과 철길
    if (app.layerVisible('infra', 'lines')) {
      const la = lens ? 0.5 : 1;
      if (rc >= 10.5) stroke(this.pRoad2, `rgba(184,50,31,${(0.34 * la * smooth(10.5, 12.5, rc)).toFixed(3)})`, 1.0);
      if (rc >= 6.4) stroke(this.pRoad1, `rgba(184,50,31,${(0.58 * la * smooth(6.4, 8, rc)).toFixed(3)})`, 1.1 + 0.5 * near);
      if (rc >= 7.2) {
        const a = la * smooth(7.2, 8.6, rc), w = 1.6 + 0.5 * near;
        ctx.lineCap = 'butt';
        stroke(this.pRail, `rgba(29,26,22,${(0.8 * a).toFixed(3)})`, w);
        stroke(this.pRail, `rgba(251,246,232,${(0.95 * a).toFixed(3)})`, w * 0.5, [4, 4]);
        ctx.lineCap = 'round';
      }
    }
    ctx.setLineDash([]);
    ctx.restore();
    this.drawRoutes(ctx, cam, o);
  }

  drawRoutes(ctx, cam, o) {
    this.routeScreen = [];
    const app = this.app;
    if (!app.layerVisible('trade', 'routes') || !this.routes.length) return;
    const sel = app.selRoute, narrow = window.innerWidth <= NARROW, wk = narrow ? 0.6 : 1;
    ctx.save();
    ctx.lineCap = 'round';
    const curve = (r) => {
      const [ax, ay] = cam.toScreen(r.ax, r.ay), [bx, by] = cam.toScreen(r.bx, r.by), [qx, qy] = cam.toScreen(r.qx, r.qy);
      ctx.beginPath(); ctx.moveTo(ax, ay); ctx.quadraticCurveTo(qx, qy, bx, by);
      return [ax, ay, qx, qy, bx, by];
    };
    for (const r of this.routes) {
      const on = sel && sel.id === r.id;
      if (on) continue;
      const [ax, ay, qx, qy, bx, by] = curve(r);
      const w = Math.max(1.2, r.w * wk);
      ctx.strokeStyle = `rgba(63,107,82,${o.lens ? 0.42 : sel ? 0.3 : 0.56})`; ctx.lineWidth = w; ctx.stroke();
      const pts = [];
      for (let k = 0; k <= 20; k++) { const t = k / 20, u = 1 - t; pts.push(u * u * ax + 2 * u * t * qx + t * t * bx, u * u * ay + 2 * u * t * qy + t * t * by); }
      this.routeScreen.push({ r, pts, w });
    }
    if (sel && sel.ax != null) {
      const [ax, ay, qx, qy, bx, by] = curve(sel);
      const w = Math.max(2.4, sel.w * wk);
      ctx.strokeStyle = 'rgba(251,246,232,0.95)'; ctx.lineWidth = w + 3.5; ctx.stroke();
      ctx.strokeStyle = JU; ctx.lineWidth = w; ctx.stroke();
      const pts = [];
      for (let k = 0; k <= 20; k++) { const t = k / 20, u = 1 - t; pts.push(u * u * ax + 2 * u * t * qx + t * t * bx, u * u * ay + 2 * u * t * qy + t * t * by); }
      this.routeScreen.push({ r: sel, pts, w });
    }
    // 끝점: 시도 청사 칸에 작은 마름모
    const seen = new Set();
    for (const r of this.routes) for (const [x, y, c] of [[r.ax, r.ay, r.a], [r.bx, r.by, r.b]]) {
      if (seen.has(c)) continue;
      seen.add(c);
      const [sx, sy] = cam.toScreen(x, y);
      ctx.beginPath(); ctx.moveTo(sx, sy - 4.5); ctx.lineTo(sx + 4.5, sy); ctx.lineTo(sx, sy + 4.5); ctx.lineTo(sx - 4.5, sy); ctx.closePath();
      ctx.fillStyle = NOK; ctx.fill(); ctx.strokeStyle = BAEK; ctx.lineWidth = 1; ctx.stroke();
    }
    ctx.restore();
  }

  hitRoute(sx, sy) {
    const pad = this.app.touch ? 9 : 4;
    let best = null, bd = 1e9;
    for (const { r, pts, w } of this.routeScreen) {
      for (let k = 2; k < pts.length; k += 2) {
        const x0 = pts[k - 2], y0 = pts[k - 1], dx = pts[k] - x0, dy = pts[k + 1] - y0, L2 = dx * dx + dy * dy || 1;
        const t = Math.max(0, Math.min(1, ((sx - x0) * dx + (sy - y0) * dy) / L2));
        const d = Math.hypot(sx - (x0 + t * dx), sy - (y0 + t * dy));
        if (d <= w / 2 + pad && d < bd) { bd = d; best = r; }
      }
    }
    return best;
  }

  // 어떤 시군구·칸에 걸친 항목 (장의 '이곳의 것' 목록용)
  itemsFor(sggSet, cellSet) {
    return this.items.filter((it) => (cellSet && cellSet.has(it.cell)) || (sggSet && it.x.sgg.some((c) => sggSet.has(c)))).sort(cmp);
  }
}

// 배지 그리기 (DOM 견본·캔버스 공용). size = 배지 한 변(지름) px
export function drawBadge(ctx, kind, cx, cy, size, opt = '') {
  const S = groupStyle(kind), r = size / 2;
  ctx.save();
  ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  ctx.beginPath();
  if (S.shape === 'square') { const q = r - 0.5; ctx.rect(cx - q, cy - q, 2 * q, 2 * q); }
  else if (S.shape === 'diamond') { const q = r + 1; ctx.moveTo(cx, cy - q); ctx.lineTo(cx + q, cy); ctx.lineTo(cx, cy + q); ctx.lineTo(cx - q, cy); ctx.closePath(); }
  else ctx.arc(cx, cy, r - 0.5, 0, 6.3);
  if (S.ring !== INK) { ctx.strokeStyle = S.ring; ctx.lineWidth = 2.2; ctx.stroke(); }
  ctx.fillStyle = S.fill; ctx.fill();
  if (S.ring === INK) { ctx.strokeStyle = INK; ctx.lineWidth = 1.3; ctx.stroke(); }
  // 글리프
  const g = size * (S.shape === 'diamond' ? 0.66 : 0.76), k = g / 24;
  ctx.translate(cx - g / 2, cy - g / 2);
  ctx.scale(k, k);
  ctx.strokeStyle = S.glyph;
  ctx.lineWidth = (size <= 18 ? 1.25 : size <= 22 ? 1.4 : 1.55) / k;
  ctx.stroke(glyphPath(KIND_ICON[kind] || 'gold', size <= 20));
  ctx.restore();
}
