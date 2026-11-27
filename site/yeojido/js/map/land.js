// 땅 — 칸마다의 빛깔 두 벌(먹판·채색판)과 조각 그리기.
// 먹판: 한지 위 호분 뭍, 네 단 수묵 음영, 연안 쪽빛 바림, 물결. 채색판: 토지피복 석채, 무늬, 칸 금.
// 선(산줄기·물줄기·해안·경계)은 조각에 굽지 않고 매 프레임 벡터로 긋는다 (lines.js).

import { EDGE_CORNERS } from '../hex.js';

export const INK = [29, 26, 22], JU = [184, 50, 31], JJOK = [38, 70, 95], PAPER = [239, 230, 210], BAEK = [251, 246, 232];
const FOREIGN = [226, 217, 196];
const TONE = [[0, [251, 246, 232]], [100, [247, 240, 222]], [400, [236, 227, 204]], [900, [222, 212, 188]], [1500, [206, 196, 173]]];
const LAKE_INK = [205, 216, 212], LAKE_PIG = [170, 198, 204];
const SEA_PIG = [[196, 215, 211], [168, 196, 201]];
const TIDAL = [216, 207, 181];
// 석채 (채도를 낮춘 안료 빛)
export const PIG = {
  broadleaf: [160, 180, 128], conifer: [112, 147, 124], mixed: [137, 163, 124], forest: [140, 166, 124],
  paddy: [203, 207, 138], field: [221, 201, 150], orchard: [188, 181, 116], greenhouse: [229, 226, 213], crop: [210, 198, 146],
  built: [217, 187, 170], grass: [192, 201, 146], wetland: [160, 187, 170], bare: [224, 211, 184], water: [170, 198, 204],
};
const LEAF = ['broadleaf', 'conifer', 'mixed', 'paddy', 'field', 'orchard', 'greenhouse', 'built', 'grass', 'wetland', 'bare', 'water'];

export function hash(i) {
  let h = (i * 2654435761) >>> 0;
  h ^= h >>> 15; h = Math.imul(h, 2246822519) >>> 0; h ^= h >>> 13;
  return (h >>> 0) / 4294967296;
}
export const css = (c, a = 1) => (a >= 1 ? `rgb(${c[0] | 0},${c[1] | 0},${c[2] | 0})` : `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${+a.toFixed(3)})`);
export const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const mul = (c, k) => [Math.min(255, c[0] * k), Math.min(255, c[1] * k), Math.min(255, c[2] * k)];
export const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
function tone(e) {
  for (let k = 1; k < TONE.length; k++) if (e < TONE[k][0]) return mix(TONE[k - 1][1], TONE[k][1], (e - TONE[k - 1][0]) / (TONE[k][0] - TONE[k - 1][0]));
  return TONE[TONE.length - 1][1];
}

export class Land {
  constructor(W, grid) {
    this.W = W; this.grid = grid;
    const n = grid.n;
    const { owner, foreign, water } = W;
    this.nb = new Int32Array(n * 6);
    for (let i = 0; i < n; i++) { const s = grid.neighborSlots(i); for (let d = 0; d < 6; d++) this.nb[i * 6 + d] = s[d]; }
    const nb = this.nb;
    const rawLand = (i) => owner[i] >= 0 || foreign[i] === 1;
    // 그림용 표고: 값이 없는 칸은 둘레 값으로 메운다 (자료는 그대로 둔다)
    const elev = this.elev = W.elev.slice();
    for (let pass = 0; pass < 6; pass++) {
      let left = 0;
      for (let i = 0; i < n; i++) {
        if (!Number.isNaN(elev[i])) continue;
        let s = 0, k = 0;
        for (let d = 0; d < 6; d++) { const j = nb[i * 6 + d]; if (j >= 0 && !Number.isNaN(elev[j]) && rawLand(j) === rawLand(i)) { s += elev[j]; k++; } }
        if (k) elev[i] = s / k; else left++;
      }
      if (!left) break;
    }
    for (let i = 0; i < n; i++) if (Number.isNaN(elev[i])) elev[i] = rawLand(i) ? 0 : -80;

    // 외딴 섬 칸 (이웃이 모두 바다이고 땅 비율이 낮음): 칸 전체가 아니라 작은 섬으로 그린다
    this.islet = new Uint8Array(n);
    for (let i = 0; i < n; i++) {
      if (owner[i] < 0 || W.landFrac[i] >= 0.7) continue;
      let alone = true;
      for (let d = 0; d < 6; d++) { const j = nb[i * 6 + d]; if (j >= 0 && rawLand(j)) { alone = false; break; } }
      if (alone) this.islet[i] = 1;
    }
    const isLand = this.isLand = (i) => i >= 0 && !this.islet[i] && (owner[i] >= 0 || foreign[i] === 1);
    const bfs = (seed, max) => {
      const dist = new Uint8Array(n).fill(255);
      let fr = [];
      for (let i = 0; i < n; i++) if (seed(i)) { dist[i] = 0; fr.push(i); }
      for (let dd = 1; dd <= max && fr.length; dd++) {
        const nx = [];
        for (const i of fr) for (let d = 0; d < 6; d++) { const j = nb[i * 6 + d]; if (j >= 0 && dist[j] > dd) { dist[j] = dd; nx.push(j); } }
        fr = nx;
      }
      return dist;
    };
    this.coastDist = bfs((i) => isLand(i), 6);                 // 뭍(나라 안팎)에서의 칸 거리
    this.ownDist = bfs((i) => owner[i] >= 0 && !this.islet[i], 30); // 대한민국 뭍에서의 칸 거리
    // 자료 가장자리로 갈수록 빈 종이로 (네모난 자료 끝이 보이지 않게)
    this.edge = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const r = Math.floor(i / grid.cols), c = i - r * grid.cols;
      const e = Math.min(1, Math.min(c, grid.cols - 1 - c, r, grid.rows - 1 - r) / 9);
      this.edge[i] = e * e * (3 - 2 * e);
    }
    // 칸 빛깔
    const dirs = [[1, 0], [0.5, -0.866], [-0.5, -0.866], [-1, 0], [-0.5, 0.866], [0.5, 0.866]];
    const spacing = grid.W * W.metersPerUnit;
    this.shade = new Float32Array(n);
    this.cInk = new Array(n); this.cPig = new Array(n);
    this.seaA = new Float32Array(n); // 먹판 바다 쪽빛 바림의 세기
    for (let i = 0; i < n; i++) {
      const own = owner[i] >= 0;
      if (own || foreign[i]) {
        let gx = 0, gy = 0;
        const e0 = Math.max(0, elev[i]);
        for (let d = 0; d < 6; d++) {
          const j = nb[i * 6 + d];
          const ej = j >= 0 ? Math.max(0, elev[j]) : e0;
          gx += (ej - e0) * dirs[d][0]; gy += (ej - e0) * dirs[d][1];
        }
        // 북서에서 드는 빛
        this.shade[i] = Math.max(-0.16, Math.min(0.14, ((gx * -0.6 + gy * -0.8) / (3 * spacing)) * -2.8));
      }
      if (own && water[i] === 3) { this.cInk[i] = LAKE_INK; this.cPig[i] = LAKE_PIG; continue; }
      if (own) {
        const sh = this.shade[i];
        let p = this.coverMix(i) || PIG.grass;
        const rl = W.relief[i];
        if (rl === 3) p = mix(p, [196, 184, 160], 0.4);
        else if (rl === 2) p = mix(p, [176, 170, 140], 0.14);
        this.cPig[i] = mul(p, (1 + sh) * (1 + (hash(i) - 0.5) * 0.035));
        this.cInk[i] = mul(tone(Math.max(0, elev[i])), 1 + sh * 0.62);
      } else if (foreign[i]) {
        const f = mix(PAPER, mul(FOREIGN, 1 + this.shade[i] * 0.12), this.edge[i]);
        this.cInk[i] = f; this.cPig[i] = f;
      } else {
        const cd = this.coastDist[i], od = this.ownDist[i];
        const band = [0, 0.23, 0.15, 0.1, 0.06, 0.03][cd] || 0;
        const near = od <= 6 ? 1 : Math.max(0.35, 1 - (od - 6) / 16);
        this.seaA[i] = band * near * this.edge[i];
        const t = Math.min(0.8, W.tidal[i] * 1.6);
        this.cInk[i] = mix(mix(PAPER, JJOK, this.seaA[i]), TIDAL, t * 0.5 * this.edge[i]);
        const deep = water[i] === 1 ? Math.min(1, Math.max(0.35, (-elev[i] - 150) / 1800)) : Math.min(0.3, Math.max(0, -elev[i] / 400));
        const far = Math.max(0, Math.min(1, 1 - (od - 3) / 22));
        this.cPig[i] = mix(PAPER, mix(mix(SEA_PIG[0], SEA_PIG[1], deep), TIDAL, t), (0.3 + 0.7 * far * far) * this.edge[i]);
      }
    }
  }

  coverMix(i) {
    const W = this.W, sh = W.share;
    let r = 0, g = 0, b = 0, t = 0;
    const addc = (c, w) => { if (w > 0) { r += c[0] * w; g += c[1] * w; b += c[2] * w; t += w; } };
    if (W.coverSrc[i] === 1 && sh.paddy) {
      for (const k of LEAF) if (sh[k]) addc(PIG[k], sh[k][i]);
      if (sh.crop) addc(PIG.crop, sh.crop[i] - sh.paddy[i] - sh.field[i] - sh.orchard[i] - sh.greenhouse[i]);
    } else {
      for (const k of W.coverKeys) addc(k === 'crop' && W.crop[i] ? PIG[W.crop[i]] : PIG[k] || PIG.grass, sh[k] ? sh[k][i] : NaN);
    }
    return t > 0 ? [r / t, g / t, b / t] : null;
  }

  cellsIn(t) {
    const G = this.grid;
    const [c0, c1, r0, r1] = G.range(t.ox - G.W * 2, t.oy - G.R * 3, t.ox + t.tw + G.W * 2, t.oy + t.tw + G.R * 3);
    const cells = [];
    for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) cells.push(r * G.cols + c);
    return cells;
  }

  lakesPath(t) {
    const p = new Path2D();
    let any = false;
    for (const l of this.W.lakes) {
      if (l.bb[2] < t.ox - 2 || l.bb[0] > t.ox + t.tw + 2 || l.bb[3] < t.oy - 2 || l.bb[1] > t.oy + t.tw + 2) continue;
      for (const r of l.rings) {
        p.moveTo((r[0] - t.ox) * t.s, (r[1] - t.oy) * t.s);
        for (let q = 2; q < r.length; q += 2) p.lineTo((r[q] - t.ox) * t.s, (r[q + 1] - t.oy) * t.s);
        p.closePath();
      }
      any = true;
    }
    return any ? p : null;
  }

  // ---------- 먹판 ----------
  paintInk(ctx, t) {
    const G = this.grid, { ox, oy, s, rc, pdpr } = t, rpx = G.R * s;
    const cells = this.cellsIn(t);
    const X = (i) => (G.cx[i] - ox) * s, Y = (i) => (G.cy[i] - oy) * s;
    ctx.fillStyle = css(PAPER);
    ctx.fillRect(0, 0, 512, 512);
    // 바다: 뭍 가까이만 쪽빛 바림 (먼 바다는 빈 종이)
    for (const i of cells) {
      if (this.isLand(i)) continue;
      if (this.seaA[i] < 0.004 && this.W.tidal[i] < 0.02) continue;
      ctx.beginPath(); G.pathHex(ctx, i, s, ox, oy, 1.035);
      ctx.fillStyle = css(this.cInk[i]); ctx.fill();
    }
    // 물결: 뭍 가까운 바다 칸의 짧은 가로 획
    if (rc >= 2.4) {
      ctx.strokeStyle = css(JJOK, 0.3); ctx.lineCap = 'round';
      ctx.lineWidth = Math.max(0.6 * pdpr, rpx * 0.035);
      ctx.beginPath();
      for (const i of cells) {
        const cd = this.coastDist[i];
        if (cd === 0 || cd > 3 || this.edge[i] < 0.5 || this.ownDist[i] > 14) continue;
        const nw = cd === 1 ? 2 : hash(i + 5) < (cd === 2 ? 0.5 : 0.2) ? 1 : 0;
        for (let q = 0; q < nw; q++) {
          const x = X(i) + (hash(i * 3 + q) - 0.5) * rpx * 0.9, y = Y(i) + (q ? 0.42 : -0.3) * rpx + (hash(i * 5 + q) - 0.5) * rpx * 0.3;
          const w = rpx * (0.4 + hash(i + q) * 0.3);
          ctx.moveTo(x - w, y);
          if (rc > 7) { ctx.bezierCurveTo(x - w * 0.5, y - w * 0.28, x - w * 0.1, y - w * 0.28, x, y); ctx.bezierCurveTo(x + w * 0.1, y - w * 0.28, x + w * 0.5, y - w * 0.28, x + w, y); }
          else ctx.lineTo(x + w, y);
        }
      }
      ctx.stroke();
    }
    // 뭍
    for (const i of cells) {
      if (!this.isLand(i)) continue;
      ctx.beginPath(); G.pathHex(ctx, i, s, ox, oy, 1.035);
      ctx.fillStyle = css(this.cInk[i]); ctx.fill();
    }
    this.paintIslets(ctx, t, cells, false);
    const lp = this.lakesPath(t);
    if (lp) { ctx.fillStyle = css(LAKE_INK); ctx.fill(lp, 'evenodd'); }
  }

  paintIslets(ctx, t, cells, pig) {
    const G = this.grid, { ox, oy, s, pdpr } = t, rpx = G.R * s;
    for (const i of cells) {
      if (!this.islet[i]) continue;
      const r = Math.max(1.0 * pdpr, rpx * 0.78 * Math.sqrt(Math.max(0.04, this.W.landFrac[i])));
      ctx.beginPath();
      ctx.arc((G.cx[i] - ox) * s + (hash(i + 3) - 0.5) * rpx * 0.3, (G.cy[i] - oy) * s + (hash(i + 9) - 0.5) * rpx * 0.3, r, 0, 6.3);
      ctx.fillStyle = css(pig ? this.cPig[i] : BAEK); ctx.fill();
      ctx.strokeStyle = css(INK, 0.72); ctx.lineWidth = Math.max(0.7 * pdpr, rpx * 0.05); ctx.stroke();
    }
  }

  // ---------- 채색판 ----------
  paintPigment(ctx, t) {
    const G = this.grid, W = this.W, { ox, oy, s, rc, pdpr } = t, rpx = G.R * s;
    const cells = this.cellsIn(t);
    ctx.fillStyle = css(PAPER);
    ctx.fillRect(0, 0, 512, 512);
    for (const i of cells) {
      if (this.islet[i]) continue;
      ctx.beginPath(); G.pathHex(ctx, i, s, ox, oy, 1.035);
      ctx.fillStyle = css(this.cPig[i]); ctx.fill();
    }
    // 갯벌 점묘
    if (rc >= 7) {
      ctx.fillStyle = css([110, 96, 70], 0.4);
      for (const i of cells) {
        if (W.water[i] !== 4 || this.isLand(i)) continue;
        for (let q = 0; q < 9; q++) {
          ctx.beginPath();
          ctx.arc((G.cx[i] - ox) * s + (hash(i * 7 + q) - 0.5) * rpx * 1.4, (G.cy[i] - oy) * s + (hash(i * 11 + q) - 0.5) * rpx * 1.2, Math.max(0.6, rpx * 0.035), 0, 6.3);
          ctx.fill();
        }
      }
    }
    // 물결
    if (rc >= 5) {
      ctx.strokeStyle = css(JJOK, 0.22); ctx.lineCap = 'round'; ctx.lineWidth = Math.max(0.6 * pdpr, rpx * 0.035);
      ctx.beginPath();
      for (const i of cells) {
        const cd = this.coastDist[i];
        if (cd === 0 || cd > 3 || this.edge[i] < 0.5) continue;
        const nw = cd === 1 ? 2 : hash(i + 5) < (cd === 2 ? 0.5 : 0.2) ? 1 : 0;
        for (let q = 0; q < nw; q++) {
          const x = (G.cx[i] - ox) * s + (hash(i * 3 + q) - 0.5) * rpx * 0.9, y = (G.cy[i] - oy) * s + (q ? 0.42 : -0.3) * rpx + (hash(i * 5 + q) - 0.5) * rpx * 0.3;
          const w = rpx * (0.4 + hash(i + q) * 0.3);
          ctx.moveTo(x - w, y);
          if (rc > 7) { ctx.bezierCurveTo(x - w * 0.5, y - w * 0.28, x - w * 0.1, y - w * 0.28, x, y); ctx.bezierCurveTo(x + w * 0.1, y - w * 0.28, x + w * 0.5, y - w * 0.28, x + w, y); }
          else ctx.lineTo(x + w, y);
        }
      }
      ctx.stroke();
    }
    this.paintIslets(ctx, t, cells, true);
    const lp = this.lakesPath(t);
    if (lp) { ctx.fillStyle = css(LAKE_PIG); ctx.fill(lp, 'evenodd'); }
    // 칸 금
    if (rc > 5) {
      ctx.strokeStyle = css(INK, 0.13); ctx.lineWidth = Math.max(0.6, 0.7 * pdpr);
      ctx.beginPath();
      for (const i of cells) if (W.owner[i] >= 0 && !this.islet[i]) G.pathHex(ctx, i, s, ox, oy);
      ctx.stroke();
    }
    if (rc >= 8) this.paintCover(ctx, t, cells, smooth(8, 13, rc));
  }

  // 피복 무늬: 칸의 으뜸 피복을 먹선 기호로
  paintCover(ctx, t, cells, a) {
    const G = this.grid, W = this.W, { ox, oy, s } = t, rpx = G.R * s, u = rpx / 10;
    const ink = (al) => css(INK, al * a);
    ctx.lineWidth = Math.max(0.8, u * 0.42); ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    for (const i of cells) {
      if (W.owner[i] < 0 || W.water[i] === 3 || this.islet[i]) continue;
      const x = (G.cx[i] - ox) * s, y = (G.cy[i] - oy) * s;
      if (x < -rpx || y < -rpx || x > 512 + rpx || y > 512 + rpx) continue;
      const kd = W.coverKind(i), rl = W.relief[i];
      const jx = (hash(i + 21) - 0.5) * 2 * u, jy = (hash(i + 23) - 0.5) * 2 * u;
      if (kd === 'forest' || kd === 'broadleaf' || kd === 'conifer' || kd === 'mixed') {
        const spots = [[-4.2, 3.2], [4, 3.8], [0, -3.6]];
        ctx.strokeStyle = ink(0.4);
        spots.forEach(([dx, dy], q) => {
          const px = x + dx * u + jx * 0.6, py = y + dy * u + jy * 0.6;
          const kind = kd === 'mixed' ? (q % 2 ? 'conifer' : 'broadleaf') : kd;
          ctx.beginPath();
          if (kind === 'conifer') {
            ctx.moveTo(px, py - 2.6 * u); ctx.lineTo(px, py + 1.8 * u);
            ctx.moveTo(px - 1.5 * u, py - 0.5 * u); ctx.lineTo(px, py - 2 * u); ctx.lineTo(px + 1.5 * u, py - 0.5 * u);
            ctx.moveTo(px - 1.9 * u, py + 1.1 * u); ctx.lineTo(px, py - 0.5 * u); ctx.lineTo(px + 1.9 * u, py + 1.1 * u);
          } else {
            ctx.arc(px, py - 0.6 * u, 1.55 * u, Math.PI * 0.75, Math.PI * 2.25);
            ctx.moveTo(px, py + 0.9 * u); ctx.lineTo(px, py + 2 * u);
          }
          ctx.stroke();
        });
        if (rl >= 2) { ctx.strokeStyle = ink(0.42); ctx.beginPath(); ctx.moveTo(x - 3 * u, y + 0.6 * u); ctx.quadraticCurveTo(x - 0.4 * u, y - 2.2 * u, x + 3.2 * u, y + 0.6 * u); ctx.stroke(); }
      } else if (kd === 'paddy' || kd === 'crop') {
        ctx.strokeStyle = css([64, 92, 44], (kd === 'paddy' ? 0.5 : 0.34) * a);
        ctx.beginPath();
        for (const dy of [-3.6, 0, 3.6]) {
          const off = dy === 0 ? 1.4 : 0;
          ctx.moveTo(x - 5 * u + jx, y + dy * u + jy); ctx.lineTo(x - 0.8 * u + jx + off * u, y + dy * u + jy);
          ctx.moveTo(x + 0.8 * u + jx + off * u, y + dy * u + jy); ctx.lineTo(x + 5 * u + jx, y + dy * u + jy);
        }
        ctx.stroke();
      } else if (kd === 'field') {
        ctx.strokeStyle = css([122, 86, 44], 0.46 * a);
        ctx.beginPath();
        for (const d of [-4, -1.3, 1.4, 4.1]) { ctx.moveTo(x + (d - 1.6) * u + jx, y + 2.8 * u + jy); ctx.lineTo(x + (d + 1.6) * u + jx, y - 2.8 * u + jy); }
        ctx.stroke();
      } else if (kd === 'orchard') {
        ctx.strokeStyle = ink(0.42);
        for (const dx of [-3.6, 0, 3.6]) for (const dy of [-2.4, 2.4]) { ctx.beginPath(); ctx.arc(x + dx * u + jx, y + dy * u + jy, 0.9 * u, 0, 6.3); ctx.stroke(); }
      } else if (kd === 'greenhouse') {
        ctx.strokeStyle = ink(0.4);
        ctx.beginPath();
        for (const dy of [-1.6, 2.6]) for (const dx of [-4.4, 0.4]) { ctx.moveTo(x + dx * u + jx, y + dy * u + jy); ctx.quadraticCurveTo(x + (dx + 2) * u + jx, y + (dy - 2.6) * u + jy, x + (dx + 4) * u + jx, y + dy * u + jy); }
        ctx.stroke();
      } else if (kd === 'built') {
        ctx.fillStyle = css([150, 62, 40], 0.5 * a);
        for (const [dx, dy] of [[-4.2, -1.4], [-1, -3.4], [2, -0.6], [-2.2, 1.9], [1, 2.8]]) ctx.fillRect(x + dx * u + jx, y + dy * u + jy, 2.4 * u, 2.4 * u);
      }
    }
  }

  // ---------- 렌즈판 (투명 바탕. 먹판 위에 곱하기로 찍는다) ----------
  // colorOf(i) -> [r,g,b] | null(자료 없음) | undefined(가림: 고른 범위 밖)
  paintLens(ctx, t, colorOf) {
    const G = this.grid, W = this.W, { ox, oy, s, rc, pdpr } = t, rpx = G.R * s;
    const cells = this.cellsIn(t);
    ctx.clearRect(0, 0, 512, 512);
    const hatch = [];
    for (const i of cells) {
      if (W.owner[i] < 0) continue;
      const c = colorOf(i);
      if (c === undefined) continue;
      ctx.beginPath();
      if (this.islet[i]) ctx.arc((G.cx[i] - ox) * s + (hash(i + 3) - 0.5) * rpx * 0.3, (G.cy[i] - oy) * s + (hash(i + 9) - 0.5) * rpx * 0.3, Math.max(1.0 * pdpr, rpx * 0.78 * Math.sqrt(Math.max(0.04, W.landFrac[i]))), 0, 6.3);
      else G.pathHex(ctx, i, s, ox, oy, 1.035);
      if (c) { ctx.fillStyle = css(c); ctx.fill(); }
      else { ctx.fillStyle = 'rgb(226,217,196)'; ctx.fill(); if (!this.islet[i]) hatch.push(i); }
    }
    // 자료 없음: 빗금
    if (hatch.length && rc > 3) {
      ctx.strokeStyle = css(INK, 0.3); ctx.lineWidth = Math.max(0.7 * pdpr, rpx * 0.04);
      const step = Math.max(3 * pdpr, rpx / 2.4);
      for (const i of hatch) {
        const x = (G.cx[i] - ox) * s, y = (G.cy[i] - oy) * s;
        ctx.save(); ctx.beginPath(); G.pathHex(ctx, i, s, ox, oy); ctx.clip();
        ctx.beginPath();
        for (let d = -rpx * 2; d <= rpx * 2; d += step) { ctx.moveTo(x + d - rpx, y + rpx); ctx.lineTo(x + d + rpx, y - rpx); }
        ctx.stroke(); ctx.restore();
      }
    }
    if (rc > 5) {
      ctx.strokeStyle = css(INK, 0.12); ctx.lineWidth = Math.max(0.6, 0.7 * pdpr);
      ctx.beginPath();
      for (const i of cells) if (W.owner[i] >= 0 && !this.islet[i]) G.pathHex(ctx, i, s, ox, oy);
      ctx.stroke();
    }
  }

  // 칸 집합의 바깥 테두리 선분 [x0,y0,x1,y1][] (세계 좌표)
  outline(cells) {
    const set = cells instanceof Set ? cells : new Set(cells), G = this.grid, segs = [];
    for (const i of set) for (let d = 0; d < 6; d++) {
      if (set.has(this.nb[i * 6 + d])) continue;
      const [a, b] = EDGE_CORNERS[d];
      segs.push([G.cx[i] + G.corner[a][0], G.cy[i] + G.corner[a][1], G.cx[i] + G.corner[b][0], G.cy[i] + G.corner[b][1]]);
    }
    return segs;
  }
}
