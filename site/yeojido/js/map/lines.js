// 선 — 산줄기·물줄기·해안·경계·휴전선. 조각에 굽지 않고 매 프레임 벡터로 그어 어느 배율에서나 또렷하다.
// 산줄기는 ridges.json 의 꼭짓점을 그대로 잇는다(검사한 선 = 그리는 선). 굵기는 표고를 따라 변한다: 봉우리에서 굵고 고개에서 가늘다.

import { EDGE_CORNERS } from '../hex.js';
import { INK, JU, JJOK, BAEK, css, smooth } from './land.js';

const lerp = (a, b, t) => a + (b - a) * t;

export class Lines {
  constructor(D, grid, land) {
    this.D = D; this.grid = grid; this.land = land;
    const W = D.world, G = grid, nb = land.nb, own = W.owner;
    const seg = (p, i, d) => {
      const [a, b] = EDGE_CORNERS[d];
      p.moveTo(G.cx[i] + G.corner[a][0], G.cy[i] + G.corner[a][1]);
      p.lineTo(G.cx[i] + G.corner[b][0], G.cy[i] + G.corner[b][1]);
    };
    const P = this.p = { coast: new Path2D(), coastF: new Path2D(), sido: new Path2D(), county: new Path2D(), dmz: new Path2D(), lakes: new Path2D(), rMain: new Path2D(), rNat: new Path2D(), rLoc: new Path2D() };
    for (let i = 0; i < G.n; i++) {
      if (!land.isLand(i)) continue;
      const mine = own[i] >= 0;
      for (let d = 0; d < 6; d++) {
        const j = nb[i * 6 + d];
        if (j < 0) continue;
        if (!land.isLand(j)) { seg(mine ? P.coast : P.coastF, i, d); continue; }
        if (!mine) continue;
        if (W.foreign[j] === 1) { seg(P.dmz, i, d); continue; }
        if (d < 3 && own[j] >= 0) {
          if (own[j] !== own[i]) seg(P.sido, i, d);
          else if (W.county[j] !== W.county[i]) seg(P.county, i, d);
        }
      }
    }
    for (const l of W.lakes) for (const r of l.rings) {
      P.lakes.moveTo(r[0], r[1]);
      for (let q = 2; q < r.length; q += 2) P.lakes.lineTo(r[q], r[q + 1]);
      P.lakes.closePath();
    }
    for (const rv of W.rivers) {
      const p = rv.main ? P.rMain : rv.tier === 1 ? P.rNat : P.rLoc, a = rv.pts;
      if (a.length < 4) continue;
      p.moveTo(a[0], a[1]);
      for (let q = 2; q < a.length; q += 2) p.lineTo(a[q], a[q + 1]);
    }
    this.prepRidges();
  }

  // 산줄기: 꼭짓점마다 굵기 몫(0..1)과 끝 가늘어짐을 미리 셈한다
  prepRidges() {
    const R = this.D.ridges;
    this.ridges = [];
    if (!R) return;
    // 다른 선과 맞닿은 끝은 붓을 떼지 않는다 (가늘게 빼지 않음)
    const cell = 12, idx = new Map();
    const key = (x, y) => Math.floor(x / cell) + ':' + Math.floor(y / cell);
    R.lines.forEach((l, li) => { for (let q = 0; q < l.pts.length; q += 2) { const k = key(l.pts[q], l.pts[q + 1]); let a = idx.get(k); if (!a) idx.set(k, (a = [])); a.push(li, l.pts[q], l.pts[q + 1]); } });
    const touches = (li, x, y) => {
      const cx = Math.floor(x / cell), cy = Math.floor(y / cell);
      for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
        const a = idx.get((cx + dx) + ':' + (cy + dy));
        if (!a) continue;
        for (let q = 0; q < a.length; q += 3) if (a[q] !== li && Math.hypot(a[q + 1] - x, a[q + 2] - y) < 10) return true;
      }
      return false;
    };
    R.lines.forEach((l, li) => {
      const n = l.pts.length / 2;
      if (n < 2) return;
      let zmin = 1e9, zmax = -1e9;
      for (const z of l.z) { if (z < zmin) zmin = z; if (z > zmax) zmax = z; }
      const len = new Float32Array(n);
      for (let k = 1; k < n; k++) len[k] = len[k - 1] + Math.hypot(l.pts[2 * k] - l.pts[2 * k - 2], l.pts[2 * k + 1] - l.pts[2 * k - 1]);
      const total = len[n - 1] || 1;
      const j0 = touches(li, l.pts[0], l.pts[1]), j1 = touches(li, l.pts[2 * n - 2], l.pts[2 * n - 1]);
      const f = new Float32Array(n);
      const taper = Math.min(total * 0.45, 46);
      for (let k = 0; k < n; k++) {
        const z = l.z[k] ?? zmin;
        const rel = zmax > zmin ? (z - zmin) / (zmax - zmin) : 0.5;
        const abs = Math.min(1, Math.max(0, (z - 120) / 1100));
        let w = 0.5 + 0.5 * (0.45 * rel + 0.55 * abs);
        if (!j0) w *= 0.25 + 0.75 * Math.min(1, len[k] / taper);
        if (!j1) w *= 0.25 + 0.75 * Math.min(1, (total - len[k]) / taper);
        f[k] = w;
      }
      this.ridges.push({ t: l.t, pts: l.pts, n, f, bb: l.bb });
    });
  }

  // 붓 리본 한 벌을 ctx 경로에 더한다 (화면 좌표)
  ribbon(ctx, r, cam, wpx, dx, dy, grow) {
    const { pts, n, f } = r, s = cam.scale, ox = cam.vw / 2 - cam.x * s + dx, oy = cam.vh / 2 - cam.y * s + dy;
    const L = this._L || (this._L = new Float32Array(4096)), Rt = this._R || (this._R = new Float32Array(4096));
    const m = Math.min(n, 2048);
    for (let k = 0; k < m; k++) {
      const x = pts[2 * k] * s + ox, y = pts[2 * k + 1] * s + oy;
      const a = k > 0 ? k - 1 : k, b = k < m - 1 ? k + 1 : k;
      let tx = pts[2 * b] - pts[2 * a], ty = pts[2 * b + 1] - pts[2 * a + 1];
      const tl = Math.hypot(tx, ty) || 1;
      tx /= tl; ty /= tl;
      const hw = Math.max(0.2, wpx * f[k] * grow) / 2;
      L[2 * k] = x - ty * hw; L[2 * k + 1] = y + tx * hw;
      Rt[2 * k] = x + ty * hw; Rt[2 * k + 1] = y - tx * hw;
    }
    ctx.moveTo(L[0], L[1]);
    for (let k = 1; k < m; k++) ctx.lineTo(L[2 * k], L[2 * k + 1]);
    for (let k = m - 1; k >= 0; k--) ctx.lineTo(Rt[2 * k], Rt[2 * k + 1]);
    ctx.closePath();
  }

  drawRidges(ctx, cam, o) {
    if (!this.ridges.length || o.ridges === false) return;
    const rc = cam.rc, v = cam.view(), far = smooth(1.2, 3.4, rc), near = smooth(4, 15, rc);
    // tier 별 [보임 0..1, 굵기 px]
    const vis = [smooth(8.5, 11.5, rc), 0.55 * smooth(2.8, 3.6, rc) + 0.45 * smooth(4.6, 6.4, rc), 1, 1];
    const wid = [lerp(0.8, 1.2, near), lerp(0.75, 1.7, near), lerp(lerp(0.8, 1.5, far), 2.8, near), lerp(lerp(1.3, 2.6, far), 4.4, near)];
    const alpha = [0.55, 0.66, 0.84, 0.94];
    const dim = (o.lens ? 0.5 : 1) * lerp(1, 0.8, smooth(6, 13, rc));
    const m = 30;
    for (let t = 0; t <= 3; t++) {
      if (vis[t] <= 0.01) continue;
      const list = this.ridges.filter((r) => r.t === t && !(r.bb[2] < v.x0 - m || r.bb[0] > v.x1 + m || r.bb[3] < v.y0 - m || r.bb[1] > v.y1 + m));
      if (!list.length) continue;
      // 남동 사면의 엷은 먹 바림 (큰 줄기만, 렌즈를 켜면 뺀다)
      if (t >= 2 && !o.lens && rc >= 2.2) {
        const off = wid[t] * 0.9;
        ctx.beginPath();
        for (const r of list) this.ribbon(ctx, r, cam, wid[t], off, off, 2.6);
        ctx.fillStyle = css(INK, 0.085 * vis[t] * dim);
        ctx.fill();
      }
      ctx.beginPath();
      for (const r of list) this.ribbon(ctx, r, cam, wid[t], 0, 0, 1);
      ctx.fillStyle = css(INK, alpha[t] * vis[t] * dim);
      ctx.fill();
    }
  }

  // o: {lens: bool, cdpr}
  draw(ctx, cam, o) {
    const s = cam.scale, k = o.cdpr, rc = cam.rc, P = this.p;
    const far = smooth(1.2, 3.4, rc), near = smooth(4, 15, rc);
    const world = () => ctx.setTransform(k * s, 0, 0, k * s, k * (cam.vw / 2 - cam.x * s), k * (cam.vh / 2 - cam.y * s));
    const screen = () => ctx.setTransform(k, 0, 0, k, 0, 0);
    const stroke = (path, color, px, dash) => {
      ctx.strokeStyle = color; ctx.lineWidth = px / s;
      ctx.setLineDash(dash ? dash.map((d) => d / s) : []);
      ctx.stroke(path);
    };
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    world();
    // 호수 테두리
    if (rc >= 3) stroke(P.lakes, css(JJOK, 0.5), 0.7);
    // 물줄기
    const ra = o.lens ? 0.62 : 1;
    if (rc >= 5.6) stroke(P.rLoc, css(JJOK, 0.58 * ra * smooth(5.6, 7.6, rc)), lerp(0.7, 1.0, near));
    stroke(P.rNat, css(JJOK, 0.82 * ra), lerp(lerp(0.6, 0.85, far), 1.6, near));
    const mw = lerp(lerp(0.95, 1.4, far), 2.8, near);
    stroke(P.rMain, css(JJOK, ra), mw);
    if (rc >= 10 && !o.lens) stroke(P.rMain, css([196, 213, 213], smooth(10, 13, rc)), mw * 0.42); // 큰 강은 가까이에서 두 줄(강폭)
    // 산줄기
    screen();
    this.drawRidges(ctx, cam, o);
    world();
    // 시군구 경계
    if (rc >= 7) { ctx.lineCap = 'butt'; stroke(P.county, css(INK, 0.3 * smooth(7, 9, rc)), 0.8, [2, 3]); }
    // 시도 경계
    ctx.lineCap = 'butt';
    stroke(P.sido, css(INK, o.lens ? 0.6 : 0.46), lerp(lerp(0.7, 1.0, far), 1.4, near), rc >= 2.2 ? [4, 3] : null);
    ctx.lineCap = 'round';
    // 해안선
    stroke(P.coastF, css(INK, 0.3), lerp(0.6, 0.9, near));
    stroke(P.coast, css(INK, 0.8), lerp(lerp(0.8, 1.1, far), 1.5, near));
    // 휴전선
    const dw = lerp(lerp(1.2, 1.8, far), 2.2, near);
    stroke(P.dmz, css(BAEK, 0.9), dw * 1.8);
    ctx.lineCap = 'butt';
    stroke(P.dmz, css(JU), dw, [5, 4]);
    ctx.setLineDash([]);
    ctx.lineCap = 'round';
    screen();
  }
}
