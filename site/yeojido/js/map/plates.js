// 판(版) — 512 px 조각 피라미드. 먹판·채색판·렌즈판이 저마다 하나씩 갖는다.
// 단계 j 의 축척 s_j = S0·2^(j/2). 지금 축척보다 같거나 큰 가장 가까운 단계를 골라 줄여 그리므로(0.71–1배) 확대하는 동안에도 흐려지지 않는다.
// 조각이 아직 없으면 바닥 단계(전도)와 바로 전 단계 조각을 늘려 깔고, 프레임마다 시간 예산 안에서 새 조각을 굽는다.

export const TILE = 512;
const S0 = 0.04;

export class Plate {
  // paint(ctx, t): t = {ox, oy, s, tw, rc, pdpr} — 조각 왼쪽 위 세계 좌표, 기기 축척, 조각의 세계 크기, 칸 반지름(CSS px)
  constructor(paint, opts = {}) {
    this.paint = paint;
    this.alpha = !!opts.alpha;        // 투명 바탕 조각인가 (렌즈판)
    this.tiles = new Map();           // 'j:tx:ty' -> {cv, j, tx, ty, ver}
    this.ver = 0;
    this.baseJ = null;
    this.prevJ = null;
    this.curJ = null;
    this.cap = 48;
  }

  invalidate() { this.ver++; }        // 낡은 조각은 새로 구울 때까지 그대로 쓴다
  drop() { this.tiles.clear(); this.ver++; }

  static levelFor(scale) { return Math.max(0, Math.ceil(2 * Math.log2(scale / S0) - 1e-6)); }
  static scaleOf(j) { return S0 * Math.pow(2, j / 2); }

  bake(j, tx, ty, pdpr, hexR) {
    const s = Plate.scaleOf(j), tw = TILE / s;
    const cv = document.createElement('canvas');
    cv.width = TILE; cv.height = TILE;
    const ctx = cv.getContext('2d', { alpha: this.alpha });
    this.paint(ctx, { ox: tx * tw, oy: ty * tw, s, tw, rc: (hexR * s) / pdpr, pdpr });
    return { cv, j, tx, ty, ver: this.ver };
  }

  // 그린다. 반환: 아직 굽지 못한(또는 낡은) 조각 수
  draw(ctx, cam, pdpr, cdpr, budgetMs, world) {
    const want = cam.scale * pdpr;
    const j = Plate.levelFor(want);
    if (this.curJ !== j) { this.prevJ = this.curJ; this.curJ = j; }
    if (this.baseJ == null) this.baseJ = Plate.levelFor(cam.fitScale * Math.min(1, pdpr) * 0.9);
    const v = cam.view();
    const vx0 = Math.max(0, v.x0), vy0 = Math.max(0, v.y0), vx1 = Math.min(world.w, v.x1), vy1 = Math.min(world.h, v.y1);
    if (vx1 <= vx0 || vy1 <= vy0) return 0;
    const k = cdpr; // 캔버스 기기 px / CSS px
    const blit = (t) => {
      const s = Plate.scaleOf(t.j), tw = TILE / s;
      const x0 = ((t.tx * tw - cam.x) * cam.scale + cam.vw / 2) * k, y0 = ((t.ty * tw - cam.y) * cam.scale + cam.vh / 2) * k;
      const x1 = (((t.tx + 1) * tw - cam.x) * cam.scale + cam.vw / 2) * k, y1 = (((t.ty + 1) * tw - cam.y) * cam.scale + cam.vh / 2) * k;
      const rx0 = Math.round(x0), ry0 = Math.round(y0);
      ctx.drawImage(t.cv, rx0, ry0, Math.round(x1) - rx0, Math.round(y1) - ry0);
    };
    const need = [];
    const s = Plate.scaleOf(j), tw = TILE / s;
    const tx0 = Math.floor(vx0 / tw), tx1 = Math.floor((vx1 - 1e-6) / tw), ty0 = Math.floor(vy0 / tw), ty1 = Math.floor((vy1 - 1e-6) / tw);
    const cur = [];
    let missing = 0;
    for (let ty = ty0; ty <= ty1; ty++) for (let tx = tx0; tx <= tx1; tx++) {
      const id = `${j}:${tx}:${ty}`;
      const t = this.tiles.get(id);
      if (t) { this.tiles.delete(id); this.tiles.set(id, t); cur.push(t); }
      if (!t || t.ver !== this.ver) {
        const cx = (tx + 0.5) * tw - cam.x, cy = (ty + 0.5) * tw - cam.y;
        need.push({ id, tx, ty, d: cx * cx + cy * cy, stale: !!t });
      }
      if (!t) missing++;
    }
    this.cap = Math.max(8, Math.ceil((tx1 - tx0 + 1) * (ty1 - ty0 + 1) * 1.6) + 4);
    // 굽기 (가운데 가까운 것부터, 예산 안에서. 적어도 하나)
    if (need.length) {
      need.sort((a, b) => (a.stale - b.stale) || a.d - b.d);
      const t0 = performance.now();
      let n = 0;
      for (const q of need) {
        if (n > 0 && performance.now() - t0 > budgetMs) break;
        const t = this.bake(j, q.tx, q.ty, pdpr, world.hexR);
        if (!q.stale) { cur.push(t); missing--; }
        else { const k2 = cur.findIndex((c) => c.tx === q.tx && c.ty === q.ty); if (k2 >= 0) cur[k2] = t; }
        this.tiles.set(q.id, t);
        n++;
      }
      need.splice(0, n);
    }
    // 빈 자리를 가릴 밑그림: 바닥 단계, 그리고 바로 전 단계
    if (missing > 0) {
      let clipped = false;
      if (this.alpha) { // 투명 판은 겹쳐 찍히면 두 번 곱해지므로, 빈 조각 자리에만 밑그림을 깐다
        const have = new Set(cur.map((c) => c.tx + ':' + c.ty));
        ctx.save(); ctx.beginPath(); clipped = true;
        for (let ty = ty0; ty <= ty1; ty++) for (let tx = tx0; tx <= tx1; tx++) {
          if (have.has(tx + ':' + ty)) continue;
          const x0 = Math.round(((tx * tw - cam.x) * cam.scale + cam.vw / 2) * k), y0 = Math.round(((ty * tw - cam.y) * cam.scale + cam.vh / 2) * k);
          const x1 = Math.round((((tx + 1) * tw - cam.x) * cam.scale + cam.vw / 2) * k), y1 = Math.round((((ty + 1) * tw - cam.y) * cam.scale + cam.vh / 2) * k);
          ctx.rect(x0, y0, x1 - x0, y1 - y0);
        }
        ctx.clip();
      }
      const under = (jj, make) => {
        if (jj == null || jj === j) return;
        const s2 = Plate.scaleOf(jj), tw2 = TILE / s2;
        const ax0 = Math.floor(vx0 / tw2), ax1 = Math.floor((vx1 - 1e-6) / tw2), ay0 = Math.floor(vy0 / tw2), ay1 = Math.floor((vy1 - 1e-6) / tw2);
        if ((ax1 - ax0 + 1) * (ay1 - ay0 + 1) > 64) return;
        for (let ty = ay0; ty <= ay1; ty++) for (let tx = ax0; tx <= ax1; tx++) {
          const id = `${jj}:${tx}:${ty}`;
          let t = this.tiles.get(id);
          if (!t && make) { t = this.bake(jj, tx, ty, pdpr, world.hexR); this.tiles.set(id, t); }
          if (t) blit(t);
        }
      };
      if (j > this.baseJ) under(this.baseJ, true);
      if (this.prevJ != null && this.prevJ !== this.baseJ && !(this.alpha && j > this.baseJ)) under(this.prevJ, false);
      if (clipped) ctx.restore();
    }
    for (const t of cur) blit(t);
    // 오래 안 쓴 조각 버리기 (바닥 단계는 남김)
    if (this.tiles.size > this.cap) {
      for (const [id, t] of this.tiles) {
        if (this.tiles.size <= this.cap) break;
        if (t.j === this.baseJ || t.j === j) continue;
        this.tiles.delete(id);
      }
      if (this.tiles.size > this.cap * 2) for (const [id, t] of this.tiles) { if (this.tiles.size <= this.cap) break; if (t.j !== this.baseJ) this.tiles.delete(id); }
    }
    return need.length;
  }

  get bytes() { return this.tiles.size * TILE * TILE * 4; }
}
