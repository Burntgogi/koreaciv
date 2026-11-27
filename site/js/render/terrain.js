// 지형 그리기: 바다 · 갯벌 · 외국 땅 · 대한민국 땅(표고 + 피복 바탕, 피복 무늬, 기복 무늬) · 호수 · 강 · 해안 · 시군구/시도 경계 · 휴전선 · 렌즈 색.
// 화면 밖 캔버스에 512 px 조각(tile)으로 그려 두고, 이동할 때는 복사만 한다. 확대 비율이나 렌즈가 바뀌면 다시 그린다.
// 피복(기후에너지환경부 세분류 토지피복지도 도엽 통계를 칸에 나눈 값, 두 판 공용): 바탕색은 표고색과 칸의 세부 피복 비율(활엽·침엽·혼효림, 논·밭·과수원·시설재배지 …)을
// 섞은 색(전국 화면에서는 색만). 확대하면 대표 피복의 작은 무늬: 숲은 활엽(둥근 나무)·침엽(뾰족한 나무)·혼효(둘 다), 농경지는 논·밭·과수원·시설재배지.
// 도엽 통계가 닿지 않는 칸(cover_src 'esa')은 대분류 비율만 있어 숲·농경지 기본 색과 무늬로 그린다.
// 렌즈를 켜면 피복 무늬와 수면 폴리곤은 그리지 않는다 (렌즈 색을 가리지 않게). 북한·일본·중국 칸에는 피복을 칠하지 않는다.

import { EDGE_CORNERS } from '../hex.js';
import { LensScale } from './lens.js';

export const STATE_COLORS = {
  '11': '#e0473c', '12': '#9a5cc4', '26': '#2f7fd6', '27': '#ff9a1f', '28': '#17a78f', '30': '#d8458f',
  '31': '#46b2e0', '36': '#f2c51a', '41': '#f4b244', '43': '#b7c43a', '44': '#4a6fcf', '47': '#c0503a',
  '48': '#3fae9f', '50': '#f2879e', '51': '#2f9a58', '52': '#d79a33',
};

const TILE = 512;

// 표고(m) -> 바탕색. 낮은 들은 밝은 초록, 산지는 올리브·황토, 높은 곳은 회갈색
const LAND_STOPS = [
  [0, [150, 196, 98]], [40, [140, 188, 92]], [120, [124, 172, 84]], [250, [128, 160, 80]],
  [420, [150, 154, 86]], [650, [166, 145, 94]], [900, [160, 130, 98]], [1200, [150, 132, 116]], [1700, [196, 190, 182]],
];
const FOREIGN_STOPS = [[0, [164, 158, 142]], [300, [150, 144, 130]], [800, [134, 127, 116]], [1500, [158, 154, 148]]];

// 피복 색. 대분류(cover_keys)와 세부(숲 종류·농경지 종류). 세부 비율이 있는 칸(공식 자료)은 세부 색을 섞는다.
export const COVER_RGB = {
  forest: [70, 118, 62], crop: [188, 186, 104], built: [176, 160, 152], grass: [150, 182, 104],
  wetland: [112, 156, 136], bare: [196, 184, 156], water: [96, 156, 190],
  broadleaf: [96, 144, 60], conifer: [34, 86, 66], mixed: [64, 114, 60],
  paddy: [184, 208, 92], field: [208, 180, 110], orchard: [150, 146, 58], greenhouse: [216, 216, 206], crop_other: [186, 164, 96],
};
export const CROP_RGB = { paddy: COVER_RGB.paddy, field: COVER_RGB.field, orchard: COVER_RGB.orchard, greenhouse: COVER_RGB.greenhouse };
// 세부 비율로 색을 섞을 때 쓰는 열 (forest·crop 은 세부로 나눠 섞고, crop 의 나머지는 기타재배지)
const LEAF_KEYS = ['broadleaf', 'conifer', 'mixed', 'paddy', 'field', 'orchard', 'greenhouse', 'built', 'grass', 'wetland', 'bare', 'water'];
export const LAKE_RGB = [86, 154, 194];
export const TIDAL_RGB = [148, 136, 108];

function ramp(stops, v) {
  if (v <= stops[0][0]) return stops[0][1].slice();
  for (let k = 1; k < stops.length; k++) {
    if (v <= stops[k][0]) {
      const [a, ca] = stops[k - 1], [b, cb] = stops[k];
      const u = (v - a) / (b - a);
      return [ca[0] + (cb[0] - ca[0]) * u, ca[1] + (cb[1] - ca[1]) * u, ca[2] + (cb[2] - ca[2]) * u];
    }
  }
  return stops[stops.length - 1][1].slice();
}

function hash(i) {
  let h = (i * 2654435761) >>> 0;
  h ^= h >>> 15;
  h = Math.imul(h, 2246822519) >>> 0;
  h ^= h >>> 13;
  return (h >>> 0) / 4294967296;
}

const css = (c, a = 1) => (a === 1 ? `rgb(${c[0] | 0},${c[1] | 0},${c[2] | 0})` : `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`);
const mul = (c, k) => [c[0] * k, c[1] * k, c[2] * k];
const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const gray = (c) => {
  const g = 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2];
  return [g, g, g];
};

export class TerrainRenderer {
  constructor(world, grid) {
    this.world = world;
    this.grid = grid;
    const n = grid.n;
    this.owner = Int16Array.from(world.owner);
    this.county = Int16Array.from(world.county);
    this.foreign = Uint8Array.from(world.foreign);
    this.water = Uint8Array.from(world.water);
    this.relief = Uint8Array.from(world.relief);
    this.elev = Float32Array.from(world.elev.map((v) => (v === null ? NaN : v)));
    // 수심 자료가 없는 칸(SRTM30+ 범위 밖 바다, 아주 작은 섬)은 그리기용으로만 주변 자료 칸의 거리 가중 평균을 쓴다
    // (자료에는 null 그대로). 예전에는 이웃 평균을 한 칸씩 번져 나가게 채워, 범위 경계(동경 132°)의 값이 행마다 그대로
    // 동쪽으로 끌려가 독도 동쪽에 가로 줄무늬가 생겼다. 반지름 8칸 창의 역거리 제곱 가중 평균은 행 방향 편향이 없다.
    {
      const known = this.elev.slice();
      const W = grid.W, R8 = 8;
      let gs = 0, gk = 0;
      for (let i = 0; i < n; i++) if (!Number.isNaN(known[i]) && world.owner[i] < 0 && !world.foreign[i]) { gs += known[i]; gk++; }
      const fallback = gk ? gs / gk : 0;
      for (let i = 0; i < n; i++) {
        if (!Number.isNaN(known[i])) continue;
        const r = Math.floor(i / grid.cols), c = i - r * grid.cols;
        const isSea = world.owner[i] < 0 && !world.foreign[i];
        let s = 0, k = 0;
        for (let rr = Math.max(0, r - R8); rr <= Math.min(grid.rows - 1, r + R8); rr++) {
          for (let cc = Math.max(0, c - R8); cc <= Math.min(grid.cols - 1, c + R8); cc++) {
            const j = rr * grid.cols + cc;
            const v = known[j];
            if (Number.isNaN(v)) continue;
            // 바다 칸은 바다 칸 값만 (육지 표고가 수심에 섞이지 않게)
            if (isSea && (world.owner[j] >= 0 || world.foreign[j])) continue;
            const dx = (grid.cx[j] - grid.cx[i]) / W, dy = (grid.cy[j] - grid.cy[i]) / W;
            const wgt = 1 / (1 + dx * dx + dy * dy);
            s += v * wgt;
            k += wgt;
          }
        }
        this.elev[i] = k ? s / k : isSea ? fallback : 0;
      }
    }
    this.stateCode = world.states.map((s) => s.code);
    this.stateRGB = this.stateCode.map((c) => {
      const h = parseInt(STATE_COLORS[c].slice(1), 16);
      return [(h >> 16) & 255, (h >> 8) & 255, h & 255];
    });
    // 피복: 칸별 비율(정수 %), 대표 피복, 출처(me/esa), 농경지·숲 세분, 갯벌 비율
    const keys = world.cover_keys || [];
    this.coverKeys = keys;
    this.cover = Uint8Array.from(world.cover || []);
    const cs = world.cover_share;
    this.shareKeys = cs ? cs.keys || keys : [];
    this.share = {};
    for (const k of this.shareKeys) this.share[k] = new Float32Array(n).fill(NaN);
    if (cs) {
      const lc = cs.land_cells;
      for (const k of this.shareKeys) { const a = cs[k]; for (let t = 0; t < lc.length; t++) if (a[t] != null) this.share[k][lc[t]] = a[t] / 100; }
    }
    this.coverSrc = new Uint8Array(n);   // 0 없음, 1 도엽 통계(me), 2 ESA — 번호가 아니라 kinds 이름으로 읽는다
    const srcKinds = world.cover_src ? world.cover_src.kinds || [] : [];
    if (world.cover_src && cs) world.cover_src.src.forEach((v, t) => { if (v != null) this.coverSrc[cs.land_cells[t]] = srcKinds[v] === 'me' ? 1 : 2; });
    // 옛 공개판 빌드(world.cover_meta.profile 'public', ESA 만)를 읽을 때만 참. 지금 빌드는 두 판 모두 도엽 통계
    this.coverPublic = !!(world.cover_meta && world.cover_meta.profile === 'public');
    this.coverSrcName = world.cover_src ? world.cover_src.kinds : [];
    this.crop = new Array(n).fill(null);     // 'paddy' | 'field' | 'orchard' | 'greenhouse'
    this.cropSrc = new Array(n).fill(null);  // 'me' | 'stats'
    const CK = world.crop_kind;
    if (CK) CK.cells.forEach((c, t) => {
      const k = CK.kind[t], s_ = CK.src[t];
      this.crop[c] = k == null ? null : (CK.keys ? CK.keys[k] : k);
      this.cropSrc[c] = s_ == null ? null : (CK.srcs ? CK.srcs[s_] : s_);
    });
    this.forest = new Array(n).fill(null);   // 'broadleaf' | 'conifer' | 'mixed'
    const FK = world.forest_kind;
    if (FK) FK.cells.forEach((c, t) => { this.forest[c] = FK.keys[FK.kind[t]]; });
    this.tidal = new Float32Array(n);
    if (world.tidal) world.tidal.cells.forEach((c, t) => { this.tidal[c] = world.tidal.share[t]; });
    // 수면 폴리곤(1 km² 이상)과 강의 범위 상자 (조각마다 겹치는 것만 그린다)
    const bbox = (pts) => {
      let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
      for (let k = 0; k < pts.length; k += 2) { x0 = Math.min(x0, pts[k]); x1 = Math.max(x1, pts[k]); y0 = Math.min(y0, pts[k + 1]); y1 = Math.max(y1, pts[k + 1]); }
      return [x0, y0, x1, y1];
    };
    this.lakes = (world.lakes || []).map((l) => ({ ...l, bb: l.rings.map(bbox).reduce((a, b) => [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])]) }));
    this.rivers = (world.rivers || []).map((r) => ({ ...r, bb: bbox(r.pts) }));
    // 칸 바탕색
    this.base = new Array(n);
    for (let i = 0; i < n; i++) {
      const j = 1 + (hash(i) - 0.5) * 0.05;
      if (this.owner[i] >= 0 && this.water[i] === 3) this.base[i] = LAKE_RGB.slice();
      else if (this.owner[i] >= 0) this.base[i] = mul(mix(ramp(LAND_STOPS, this.elev[i]), this.coverMix(i) || ramp(LAND_STOPS, this.elev[i]), 0.62), j);
      else if (this.foreign[i]) this.base[i] = mul(ramp(FOREIGN_STOPS, this.elev[i]), j);
      else if (this.water[i] === 4) this.base[i] = mul(mix(TIDAL_RGB, [86, 160, 186], Math.max(0, 1 - this.tidal[i]) * 0.5), j);
      else if (this.water[i] === 1) {
        const d = Math.min(1, (-this.elev[i] - 200) / 2200);
        this.base[i] = mix([44, 98, 140], [22, 58, 99], Math.max(0, d));
      } else if (this.water[i] === 3) this.base[i] = LAKE_RGB.slice();
      else {
        const d = Math.min(1, Math.max(0, -this.elev[i] / 200));
        this.base[i] = mix(mix([86, 160, 186], [58, 122, 162], d), TIDAL_RGB, Math.min(0.45, this.tidal[i] * 1.2));
      }
    }
    this.nb = new Int32Array(n * 6);
    for (let i = 0; i < n; i++) {
      const s = grid.neighborSlots(i);
      for (let d = 0; d < 6; d++) this.nb[i * 6 + d] = s[d];
    }
    // 음영 기복: 이웃 칸 표고로 기울기를 구해 북서쪽 빛을 받는 쪽은 밝게, 반대쪽은 어둡게
    const dirs = [[1, 0], [0.5, -0.866], [-0.5, -0.866], [-1, 0], [-0.5, 0.866], [0.5, 0.866]];
    const light = [-0.6, -0.8];
    const spacing = grid.W * world.meters_per_unit; // 이웃 중심 사이 거리 (m)
    for (let i = 0; i < n; i++) {
      const landish = this.owner[i] >= 0 || this.foreign[i];
      if (!landish) continue;
      let gx = 0, gy = 0;
      const e0 = Math.max(0, this.elev[i]);
      for (let d = 0; d < 6; d++) {
        const j = this.nb[i * 6 + d];
        const ej = j >= 0 ? Math.max(0, this.elev[j]) : e0;
        gx += (ej - e0) * dirs[d][0];
        gy += (ej - e0) * dirs[d][1];
      }
      gx /= 3 * spacing;
      gy /= 3 * spacing;
      // 빛 쪽으로 오르막이면(기울기가 빛 방향과 같으면) 그늘
      const shade = Math.max(-0.22, Math.min(0.22, -(gx * light[0] + gy * light[1]) * 3.2));
      const relief = this.relief[i];
      let c = this.base[i];
      // 산은 바위빛을 조금만 섞어 피복(숲 초록)이 남게 한다. 고봉은 더 섞는다.
      const lakeCell = this.owner[i] >= 0 && this.water[i] === 3;
      if (!lakeCell && relief >= 2 && this.owner[i] >= 0) c = mix(c, [132, 114, 88], relief === 3 ? 0.45 : 0.16);
      else if (!lakeCell && relief === 1 && this.owner[i] >= 0) c = mix(c, [150, 160, 92], 0.08);
      this.base[i] = mul(c, 1 + shade);
    }
    this.isLand = (i) => i >= 0 && (this.owner[i] >= 0 || this.foreign[i] === 1);
    this.cache = new Map();
    this.old = null;
    this.key = '';
    this.lens = null;
    this.lensScale = null;
  }

  // 피복 비율로 섞은 색. 공식 칸은 세부 비율(숲 종류·농경지 종류)로, ESA 보완 칸은 대분류 비율로 (농경지는 crop_kind 색). 비율이 없으면 null
  coverMix(i) {
    let r = 0, g = 0, b = 0, t = 0;
    const add = (c, w) => { if (w > 0) { r += c[0] * w; g += c[1] * w; b += c[2] * w; t += w; } };
    const sh = this.share;
    if (this.coverSrc[i] === 1 && sh.paddy) {
      for (const k of LEAF_KEYS) add(COVER_RGB[k], sh[k][i]);
      add(COVER_RGB.crop_other, sh.crop[i] - sh.paddy[i] - sh.field[i] - sh.orchard[i] - sh.greenhouse[i]);
    } else {
      for (const k of this.coverKeys) {
        const s_ = sh[k] ? sh[k][i] : NaN;
        add(k === 'crop' && this.crop[i] ? CROP_RGB[this.crop[i]] : COVER_RGB[k], s_);
      }
    }
    return t > 0 ? [r / t, g / t, b / t] : null;
  }

  // 대표 피복의 무늬 이름: broadleaf·conifer·mixed·forest(종류 없음), paddy·field·orchard·greenhouse·crop(종류 없음), built, …
  coverKind(i) {
    const c = this.cover[i];
    if (!c) return null;
    const k = this.coverKeys[c - 1];
    if (k === 'crop') return this.crop[i] || 'crop';
    if (k === 'forest') return this.forest[i] || 'forest';
    return k;
  }

  // 범례 구간 고르기 (6단계 A4): filter(v) 가 false 인 칸은 렌즈 색을 흐리게. null 이면 모두
  setFilter(fn) {
    if (fn === this.filter) return;
    this.filter = fn;
    this.invalidate();
  }

  // 공유 그림: 캐시를 쓰지 않고 보이는 조각을 모두 그린다
  drawAll(ctx, cam, dpr) {
    this.blit(ctx, cam, dpr, cam.scale * dpr, new Map(), cam.view(), true, Infinity);
  }

  setLens(lens) {
    this.lens = lens;
    this.filter = null;
    this.lensScale = lens ? new LensScale(lens) : null;
    this.invalidate();
  }

  invalidate() {
    this.old = null;
    this.cache = new Map();
    this.key = '';
  }

  // 매 프레임: 보이는 조각을 그린다. 없는 조각은 시간 예산 안에서 새로 그리고, 나머지는 예전 축척 조각을 늘려 보여 준다.
  // 반환값: 아직 못 그린 조각 수 (0보다 크면 다음 프레임을 다시 요청)
  draw(ctx, cam, dpr, settled) {
    const want = cam.scale * dpr;
    if (!this.cache.size) this.s = want;
    else if (want !== this.s && settled) {
      this.old = { s: this.s, tiles: this.cache };
      this.cache = new Map();
      this.s = want;
    }
    const v = cam.view();
    const t0 = performance.now();
    if (this.old) this.blit(ctx, cam, dpr, this.old.s, this.old.tiles, v, false);
    const missing = this.blit(ctx, cam, dpr, this.s, this.cache, v, true, t0);
    if (!missing && this.old) this.old = null;
    return missing + (want !== this.s ? 1 : 0);
  }

  blit(ctx, cam, dpr, s, tiles, v, create, t0) {
    const tw = TILE / s;
    const tx0 = Math.floor(v.x0 / tw), tx1 = Math.floor(v.x1 / tw);
    const ty0 = Math.floor(v.y0 / tw), ty1 = Math.floor(v.y1 / tw);
    const k = (cam.scale * dpr) / s;
    let missing = 0;
    ctx.imageSmoothingEnabled = true;
    for (let ty = ty0; ty <= ty1; ty++) {
      for (let tx = tx0; tx <= tx1; tx++) {
        const id = tx + ',' + ty;
        let c = tiles.get(id);
        if (!c && create) {
          if (performance.now() - t0 > 30 && tiles.size > 0) {
            missing++;
            continue;
          }
          c = this.renderTile(tx, ty, s);
          tiles.set(id, c);
        }
        if (!c) continue;
        const wx = tx * tw, wy = ty * tw;
        const sx = ((wx - cam.x) * cam.scale + cam.vw / 2) * dpr;
        const sy = ((wy - cam.y) * cam.scale + cam.vh / 2) * dpr;
        ctx.drawImage(c, Math.round(sx), Math.round(sy), Math.ceil(TILE * k) + 1, Math.ceil(TILE * k) + 1);
      }
    }
    return missing;
  }

  renderTile(tx, ty, s) {
    const cv = document.createElement('canvas');
    cv.width = TILE;
    cv.height = TILE;
    const ctx = cv.getContext('2d');
    const tw = TILE / s;
    const ox = tx * tw, oy = ty * tw;
    const G = this.grid;
    const [c0, c1, r0, r1] = G.range(ox - G.W, oy - G.R * 2, ox + tw + G.W, oy + tw + G.R * 2);
    const cells = [];
    for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) cells.push(r * G.cols + c);
    const rpx = G.R * s; // 칸 반지름 (px)
    const lens = this.lensScale;
    const lensVals = this.lens ? this.lens.values : null;

    // 1. 바탕
    for (const i of cells) {
      let col = this.base[i];
      const land = this.owner[i] >= 0;
      if (lens && land) col = mix(gray(col), [236, 232, 222], 0.35);
      ctx.beginPath();
      G.pathHex(ctx, i, s, ox, oy, 1.02);
      ctx.fillStyle = css(col);
      ctx.fill();
    }
    // 수면 폴리곤 (1 km² 이상, OpenStreetMap 대체 자료). 렌즈를 켜면 그리지 않는다
    if (!lens) this.drawLakes(ctx, s, ox, oy, tw, rpx);
    // 바다 물결 무늬 (먼바다에 드문드문)
    if (rpx > 6 && !lens) {
      ctx.strokeStyle = 'rgba(190,220,240,0.22)';
      ctx.lineWidth = Math.max(0.8, rpx * 0.06);
      for (const i of cells) {
        if (this.isLand(i) || hash(i + 7) > 0.18) continue;
        const x = (G.cx[i] - ox) * s + (hash(i + 1) - 0.5) * rpx, y = (G.cy[i] - oy) * s + (hash(i + 2) - 0.5) * rpx;
        const w = rpx * 0.35;
        ctx.beginPath();
        ctx.moveTo(x - w, y);
        ctx.quadraticCurveTo(x - w / 2, y - w * 0.45, x, y);
        ctx.quadraticCurveTo(x + w / 2, y + w * 0.45, x + w, y);
        ctx.stroke();
      }
    }
    // 2. 렌즈 색
    if (lens) {
      for (const i of cells) {
        if (this.owner[i] < 0) continue;
        const v = lensVals[i];
        const c = lens.rgb(v);
        ctx.beginPath();
        G.pathHex(ctx, i, s, ox, oy, 1.02);
        const out = this.filter && !(c && this.filter(v));
        ctx.fillStyle = out ? 'rgba(70,72,78,0.82)' : c ? css(c, 0.9) : 'rgba(150,150,150,0.55)';
        ctx.fill();
        if (!c && !out && rpx > 6) { // 자료 없음: 빗금
          ctx.save();
          ctx.clip();
          ctx.strokeStyle = 'rgba(90,90,90,0.5)';
          ctx.lineWidth = 1;
          const x = (G.cx[i] - ox) * s, y = (G.cy[i] - oy) * s;
          for (let d = -rpx; d <= rpx; d += Math.max(3, rpx / 3)) {
            ctx.beginPath();
            ctx.moveTo(x + d - rpx, y + rpx);
            ctx.lineTo(x + d + rpx, y - rpx);
            ctx.stroke();
          }
          ctx.restore();
        }
      }
    }
    // 칸 테두리 (아주 옅게)
    if (rpx > 5) {
      ctx.strokeStyle = lens ? 'rgba(40,30,20,0.10)' : 'rgba(30,40,20,0.10)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (const i of cells) if (this.isLand(i)) G.pathHex(ctx, i, s, ox, oy);
      ctx.stroke();
    }
    // 3. 피복·갯벌 무늬 (렌즈를 켜면 그리지 않는다), 기복 무늬
    if (!lens && rpx >= 7) this.drawCover(ctx, cells, s, ox, oy, rpx);
    this.drawRelief(ctx, cells, s, ox, oy, rpx, !!lens);
    // 4. 강
    this.drawRivers(ctx, s, ox, oy, rpx, !!lens, tw);
    // 5. 해안선·경계
    this.drawEdges(ctx, cells, s, ox, oy, rpx, !!lens);
    return cv;
  }

  drawRelief(ctx, cells, s, ox, oy, rpx, lensOn) {
    const G = this.grid;
    if (rpx < 5.5) {
      // 작게 보일 때: 산·고봉 칸에 작은 봉우리 하나씩 (산줄기가 읽히게), 구릉은 살짝 어둡게
      for (const i of cells) {
        const rl = this.relief[i];
        if (!this.isLand(i) || rl === 0 || this.isLakeCell(i)) continue;
        const x = (G.cx[i] - ox) * s + (hash(i + 11) - 0.5) * rpx * 0.3;
        const y = (G.cy[i] - oy) * s + (hash(i + 13) - 0.5) * rpx * 0.3;
        const base = this.base[i];
        if (rl === 1) {
          if (lensOn) continue;
          ctx.beginPath();
          G.pathHex(ctx, i, s, ox, oy, 0.85);
          ctx.fillStyle = 'rgba(60,70,30,0.10)';
          ctx.fill();
          continue;
        }
        const h = rpx * (rl === 3 ? 1.9 : 1.45), w = rpx * (rl === 3 ? 1.1 : 0.9);
        const dark = lensOn ? [40, 32, 24] : this.foreign[i] ? [104, 98, 90] : [96, 82, 64];
        const a = lensOn ? 0.4 : 1;
        ctx.beginPath();
        ctx.moveTo(x - w, y + h * 0.45);
        ctx.lineTo(x, y - h * 0.55);
        ctx.lineTo(x + w, y + h * 0.45);
        ctx.closePath();
        ctx.fillStyle = css(dark, a);
        ctx.fill();
        ctx.beginPath();
        ctx.moveTo(x - w, y + h * 0.45);
        ctx.lineTo(x, y - h * 0.55);
        ctx.lineTo(x, y + h * 0.45);
        ctx.closePath();
        ctx.fillStyle = rl === 3 ? `rgba(250,250,255,${a})` : css(this.foreign[i] ? [176, 170, 160] : [188, 172, 140], a);
        ctx.fill();
      }
      return;
    }
    for (const i of cells) {
      if (!this.isLand(i) || this.isLakeCell(i)) continue;
      const rl = this.relief[i];
      if (rl === 0) continue;
      const x = (G.cx[i] - ox) * s + (hash(i + 11) - 0.5) * rpx * 0.25;
      const y = (G.cy[i] - oy) * s + (hash(i + 13) - 0.5) * rpx * 0.2;
      const fg = this.foreign[i] === 1;
      const base = this.base[i];
      const alpha = lensOn ? 0.38 : 1;
      if (rl === 1) {
        const dark = lensOn ? [40, 32, 24] : mul(base, fg ? 0.78 : 0.72);
        const light = lensOn ? [255, 255, 255] : mix(base, [255, 252, 225], 0.3);
        this.hills(ctx, x, y, rpx, dark, light, alpha, i);
      } else {
        // 산은 바탕과 다른 바위빛으로: 산줄기가 띠처럼 읽히게
        const dark = lensOn ? [40, 32, 24] : fg ? [104, 98, 90] : [98, 84, 66];
        const light = lensOn ? [255, 255, 255] : fg ? [176, 170, 160] : [186, 170, 140];
        this.mountains(ctx, x, y, rpx, dark, light, alpha, i, rl === 3, fg);
      }
    }
  }

  hills(ctx, x, y, r, dark, light, a, i) {
    const n = hash(i + 3) > 0.5 ? 2 : 3;
    const w = r * 0.28;
    ctx.lineCap = 'round';
    for (let k = 0; k < n; k++) {
      const hx = x + (k - (n - 1) / 2) * w * 1.15 + (hash(i * 3 + k) - 0.5) * w * 0.3;
      const hy = y + (k % 2 ? -w * 0.35 : w * 0.25);
      ctx.beginPath();
      ctx.moveTo(hx - w * 0.75, hy + w * 0.25);
      ctx.quadraticCurveTo(hx, hy - w * 0.95, hx + w * 0.75, hy + w * 0.25);
      ctx.fillStyle = css(light, a * 0.7);
      ctx.fill();
      ctx.strokeStyle = css(dark, a * 0.85);
      ctx.lineWidth = Math.max(1, r * 0.07);
      ctx.stroke();
    }
  }

  mountains(ctx, x, y, r, dark, light, a, i, peak, fg) {
    const peaks = peak ? [[0, 0, 1.15]] : hash(i + 5) > 0.45 ? [[-0.28, 0.12, 0.72], [0.22, 0, 0.95]] : [[0, 0.02, 0.95]];
    if (peak) peaks.push([-0.42, 0.2, 0.6], [0.4, 0.18, 0.55]);
    peaks.sort((p, q) => p[2] - q[2]);
    for (const [dx, dy, k] of peaks) {
      const h = r * 0.92 * k, w = r * 0.6 * k;
      const px = x + dx * r, py = y + dy * r + h * 0.42;
      // 그늘 쪽 (오른쪽)
      ctx.beginPath();
      ctx.moveTo(px - w, py);
      ctx.lineTo(px, py - h);
      ctx.lineTo(px + w, py);
      ctx.closePath();
      ctx.fillStyle = css(dark, a);
      ctx.fill();
      // 볕 드는 쪽 (왼쪽)
      ctx.beginPath();
      ctx.moveTo(px - w, py);
      ctx.lineTo(px, py - h);
      ctx.lineTo(px + w * 0.05, py);
      ctx.closePath();
      ctx.fillStyle = css(light, a);
      ctx.fill();
      if (peak && k > 0.9) { // 눈 덮인 꼭대기
        ctx.beginPath();
        ctx.moveTo(px - w * 0.38, py - h * 0.62);
        ctx.lineTo(px, py - h);
        ctx.lineTo(px + w * 0.38, py - h * 0.62);
        ctx.lineTo(px + w * 0.12, py - h * 0.7);
        ctx.lineTo(px - w * 0.05, py - h * 0.58);
        ctx.lineTo(px - w * 0.2, py - h * 0.68);
        ctx.closePath();
        ctx.fillStyle = `rgba(250,250,255,${a})`;
        ctx.fill();
      }
      ctx.beginPath();
      ctx.moveTo(px - w, py);
      ctx.lineTo(px, py - h);
      ctx.lineTo(px + w, py);
      ctx.strokeStyle = css(mul(dark, 0.7), a * 0.8);
      ctx.lineWidth = Math.max(0.8, r * 0.05);
      ctx.lineJoin = 'round';
      ctx.stroke();
    }
  }

  isLakeCell(i) { return this.owner[i] >= 0 && this.water[i] === 3; }

  // 강: 국가하천은 전국 화면부터 (대권역 본류는 굵게), 지방하천(20 km 이상)은 확대했을 때만
  drawRivers(ctx, s, ox, oy, rpx, lensOn, tw) {
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    const showLocal = rpx >= 8;
    const m = 4;
    const vis = this.rivers.filter((rv) => (rv.tier === 1 || showLocal) && rv.bb[2] >= ox - m && rv.bb[0] <= ox + tw + m && rv.bb[3] >= oy - m && rv.bb[1] <= oy + tw + m);
    const width = (rv) => (rv.main ? Math.max(1.7, rpx * 0.16) : rv.tier === 1 ? Math.max(1.1, rpx * 0.12) : Math.max(0.7, rpx * 0.07));
    for (const pass of [0, 1]) {
      for (const rv of vis) {
        if (pass === 0 && rv.tier === 2) continue; // 지방하천은 밝은 테두리 없이 가늘게
        const p = rv.pts;
        ctx.beginPath();
        ctx.moveTo((p[0] - ox) * s, (p[1] - oy) * s);
        for (let k = 2; k < p.length; k += 2) ctx.lineTo((p[k] - ox) * s, (p[k + 1] - oy) * s);
        const ww = width(rv);
        if (pass === 0) {
          ctx.strokeStyle = lensOn ? 'rgba(255,255,255,0.45)' : 'rgba(225,240,250,0.5)';
          ctx.lineWidth = ww + Math.max(0.8, rpx * 0.06);
        } else {
          ctx.strokeStyle = lensOn ? 'rgba(40,110,170,0.8)' : rv.tier === 2 ? 'rgba(52,122,184,0.85)' : '#3d85c2';
          ctx.lineWidth = ww;
        }
        ctx.stroke();
      }
    }
  }

  // 수면 폴리곤: 짝홀 규칙으로 섬(구멍)을 남긴다
  drawLakes(ctx, s, ox, oy, tw, rpx) {
    const m = 2;
    ctx.save();
    ctx.lineJoin = 'round';
    for (const l of this.lakes) {
      if (l.bb[2] < ox - m || l.bb[0] > ox + tw + m || l.bb[3] < oy - m || l.bb[1] > oy + tw + m) continue;
      const path = new Path2D();
      for (const r of l.rings) {
        path.moveTo((r[0] - ox) * s, (r[1] - oy) * s);
        for (let k = 2; k < r.length; k += 2) path.lineTo((r[k] - ox) * s, (r[k + 1] - oy) * s);
        path.closePath();
      }
      ctx.fillStyle = css(LAKE_RGB);
      ctx.fill(path, 'evenodd');
      if (rpx > 4) {
        ctx.strokeStyle = 'rgba(40,90,130,0.55)';
        ctx.lineWidth = Math.max(0.6, rpx * 0.03);
        ctx.stroke(path);
      }
    }
    ctx.restore();
  }

  // 피복 무늬: 칸의 가장 많은 피복에 작은 기호. 산(기복 2 이상) 칸의 숲은 봉우리 무늬가 대신한다.
  drawCover(ctx, cells, s, ox, oy, rpx) {
    const G = this.grid;
    const u = rpx / 10;
    ctx.save();
    ctx.lineCap = 'round';
    for (const i of cells) {
      const x = (G.cx[i] - ox) * s, y = (G.cy[i] - oy) * s;
      if (this.owner[i] < 0) {
        if (this.water[i] === 4) { // 갯벌: 진흙 점과 물골
          ctx.fillStyle = 'rgba(92,78,56,0.45)';
          for (let k = 0; k < 7; k++) {
            const px = x + (hash(i * 7 + k) - 0.5) * rpx * 1.3, py = y + (hash(i * 11 + k) - 0.5) * rpx * 1.1;
            ctx.beginPath(); ctx.arc(px, py, Math.max(0.6, u * 0.45), 0, Math.PI * 2); ctx.fill();
          }
          ctx.strokeStyle = 'rgba(120,170,200,0.55)';
          ctx.lineWidth = Math.max(0.7, u * 0.35);
          ctx.beginPath();
          ctx.moveTo(x - 5 * u, y + 2 * u); ctx.quadraticCurveTo(x - 1 * u, y - 1 * u, x + 1 * u, y + 2.5 * u); ctx.quadraticCurveTo(x + 3 * u, y + 5 * u, x + 6 * u, y + 3 * u);
          ctx.stroke();
        }
        continue;
      }
      if (this.isLakeCell(i)) continue;
      const k = this.coverKind(i);
      const rl = this.relief[i];
      const jx = (hash(i + 21) - 0.5) * 2 * u, jy = (hash(i + 23) - 0.5) * 2 * u;
      if (k === 'forest' || k === 'broadleaf' || k === 'conifer' || k === 'mixed') {
        // 숲: 활엽 = 둥근 나무, 침엽 = 뾰족한 나무, 혼효 = 둘 다, 종류 없음(ESA 보완) = 둥근 나무를 옅게.
        // 산(기복 2 이상) 칸은 봉우리 무늬가 가운데를 차지하므로 아래 두 귀퉁이에 작게 둔다.
        const spots = rl >= 2 ? [[-6.2, 5.4, 0.62], [6.2, 5.4, 0.62]] : rl === 1 ? [[-4.5, 4.5, 1], [4.8, 4.2, 1]] : [[-4, 3.5, 1], [3.8, 4, 1], [0, -3.5, 1]];
        spots.forEach(([dx, dy, sc], q) => {
          const px = x + dx * u + jx * 0.5, py = y + dy * u + jy * 0.5;
          const kind = k === 'mixed' ? (q % 2 ? 'conifer' : 'broadleaf') : k;
          if (kind === 'conifer') this.conifer(ctx, px, py, u * sc);
          else this.broadleaf(ctx, px, py, u * sc, kind === 'forest' ? 0.75 : 1);
        });
      } else if (k === 'paddy' || k === 'crop') { // 논: 물 댄 칸 줄 (가로선 + 두렁). 종류 없는 농경지는 가로선만 옅게
        ctx.strokeStyle = k === 'paddy' ? 'rgba(60,104,44,0.46)' : 'rgba(90,100,50,0.32)';
        ctx.lineWidth = Math.max(0.7, u * 0.38);
        ctx.beginPath();
        for (const dy of [-3.5, 0, 3.5]) { ctx.moveTo(x - 5.5 * u + jx, y + dy * u + jy); ctx.lineTo(x + 5.5 * u + jx, y + dy * u + jy); }
        if (k === 'paddy') for (const dx of [-2, 2.5]) { ctx.moveTo(x + dx * u + jx, y - 3.5 * u + jy); ctx.lineTo(x + dx * u + jx, y + 3.5 * u + jy); }
        ctx.stroke();
      } else if (k === 'field') { // 밭: 비스듬한 이랑
        ctx.strokeStyle = 'rgba(118,84,44,0.5)';
        ctx.lineWidth = Math.max(0.7, u * 0.38);
        ctx.beginPath();
        for (const d of [-4, -1.3, 1.4, 4.1]) { ctx.moveTo(x + (d - 2.5) * u + jx, y + 3.5 * u + jy); ctx.lineTo(x + (d + 2.5) * u + jx, y - 3.5 * u + jy); }
        ctx.stroke();
      } else if (k === 'orchard') { // 과수원: 줄 맞춘 작은 나무 (줄기 + 둥근 잎)
        for (const dx of [-3.8, 0, 3.8]) for (const dy of [-2.6, 2.2]) {
          const px = x + dx * u + jx, py = y + dy * u + jy;
          ctx.strokeStyle = 'rgba(92,64,36,0.6)';
          ctx.lineWidth = Math.max(0.6, u * 0.3);
          ctx.beginPath(); ctx.moveTo(px, py + 0.4 * u); ctx.lineTo(px, py + 1.6 * u); ctx.stroke();
          ctx.fillStyle = 'rgba(70,96,30,0.7)';
          ctx.beginPath(); ctx.arc(px, py - 0.2 * u, 1.05 * u, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = 'rgba(214,92,64,0.75)';
          ctx.beginPath(); ctx.arc(px + 0.4 * u, py - 0.5 * u, 0.32 * u, 0, Math.PI * 2); ctx.fill();
        }
      } else if (k === 'greenhouse') { // 시설재배지: 둥근 지붕 비닐하우스 줄
        for (const dy of [-2.2, 2.4]) for (const dx of [-4.6, -0.6]) {
          const px = x + dx * u + jx, py = y + dy * u + jy, w = 3.6 * u, h = 1.6 * u;
          ctx.fillStyle = 'rgba(246,246,240,0.85)';
          ctx.beginPath(); ctx.moveTo(px, py + h); ctx.lineTo(px, py + h * 0.35); ctx.quadraticCurveTo(px + w / 2, py - h * 0.6, px + w, py + h * 0.35); ctx.lineTo(px + w, py + h); ctx.closePath(); ctx.fill();
          ctx.strokeStyle = 'rgba(120,128,120,0.6)';
          ctx.lineWidth = Math.max(0.5, u * 0.18);
          ctx.stroke();
        }
      } else if (k === 'built') { // 시가지: 작은 건물 덩어리
        const blocks = [[-4, -1, 2.6, 3.2], [-1, -3, 2.4, 5.2], [1.8, 0, 2.8, 2.6], [-2.5, 2.6, 3, 2]];
        for (const [dx, dy, w, h] of blocks) {
          ctx.fillStyle = 'rgba(78,70,72,0.5)';
          ctx.fillRect(x + dx * u + jx, y + dy * u + jy, w * u, h * u);
          ctx.fillStyle = 'rgba(235,228,220,0.45)';
          ctx.fillRect(x + dx * u + jx, y + dy * u + jy, w * u, Math.max(0.6, 0.5 * u));
        }
      }
    }
    ctx.restore();
  }

  // 활엽수: 둥근 잎 (짙은 둘레 + 밝은 볕)
  broadleaf(ctx, px, py, u, a = 1) {
    ctx.fillStyle = `rgba(38,74,36,${0.66 * a})`;
    ctx.beginPath(); ctx.arc(px, py - 0.6 * u, 1.75 * u, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = `rgba(132,184,96,${0.6 * a})`;
    ctx.beginPath(); ctx.arc(px - 0.5 * u, py - 1.1 * u, 0.8 * u, 0, Math.PI * 2); ctx.fill();
  }

  // 침엽수: 두 층 뾰족한 나무 (짙은 청록)
  conifer(ctx, px, py, u) {
    ctx.fillStyle = 'rgba(18,52,40,0.78)';
    ctx.beginPath();
    ctx.moveTo(px, py - 3.1 * u); ctx.lineTo(px + 1.45 * u, py - 0.6 * u); ctx.lineTo(px + 0.7 * u, py - 0.6 * u);
    ctx.lineTo(px + 1.8 * u, py + 1.3 * u); ctx.lineTo(px - 1.8 * u, py + 1.3 * u); ctx.lineTo(px - 0.7 * u, py - 0.6 * u);
    ctx.lineTo(px - 1.45 * u, py - 0.6 * u); ctx.closePath(); ctx.fill();
    ctx.fillStyle = 'rgba(70,40,24,0.7)';
    ctx.fillRect(px - 0.25 * u, py + 1.3 * u, 0.5 * u, 0.8 * u);
  }

  drawEdges(ctx, cells, s, ox, oy, rpx, lensOn) {
    const G = this.grid;
    const own = this.owner, cnty = this.county;
    const corner = G.corner;
    const seg = (i, d, inset) => {
      const [a, b] = EDGE_CORNERS[d];
      const cx = (G.cx[i] - ox) * s, cy = (G.cy[i] - oy) * s;
      const k = s * (1 - inset);
      return [cx + corner[a][0] * k, cy + corner[a][1] * k, cx + corner[b][0] * k, cy + corner[b][1] * k];
    };
    ctx.lineCap = 'round';
    // 해안선: 육지 칸과 바다 칸 사이 (모래빛)
    ctx.beginPath();
    for (const i of cells) {
      if (!this.isLand(i)) continue;
      for (let d = 0; d < 6; d++) {
        const j = this.nb[i * 6 + d];
        if (j >= 0 && !this.isLand(j)) {
          const [x0, y0, x1, y1] = seg(i, d, 0);
          ctx.moveTo(x0, y0);
          ctx.lineTo(x1, y1);
        }
      }
    }
    ctx.strokeStyle = lensOn ? 'rgba(255,255,255,0.7)' : 'rgba(236,224,180,0.85)';
    ctx.lineWidth = Math.max(1, rpx * 0.09);
    ctx.stroke();
    // 시군구 경계 (확대했을 때만)
    if (rpx >= 11) {
      ctx.beginPath();
      for (const i of cells) {
        if (own[i] < 0) continue;
        for (let d = 0; d < 3; d++) { // 한 변을 한 번만
          const j = this.nb[i * 6 + d];
          if (j >= 0 && own[j] === own[i] && cnty[j] !== cnty[i]) {
            const [x0, y0, x1, y1] = seg(i, d, 0);
            ctx.moveTo(x0, y0);
            ctx.lineTo(x1, y1);
          }
        }
      }
      // 짙은 밑선 위에 밝은 점선: 초록·산 무늬 위에서도 읽히게
      ctx.strokeStyle = lensOn ? 'rgba(20,20,20,0.35)' : 'rgba(40,34,20,0.35)';
      ctx.lineWidth = Math.max(1.5, rpx * 0.09);
      ctx.stroke();
      ctx.setLineDash([Math.max(3, rpx * 0.3), Math.max(2, rpx * 0.16)]);
      ctx.strokeStyle = lensOn ? 'rgba(255,255,255,0.75)' : 'rgba(255,246,214,0.8)';
      ctx.lineWidth = Math.max(1, rpx * 0.05);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    // 시도 경계: 칸마다 자기 쪽 안으로 들인 띠를 시도 색으로 (양쪽 색이 나란히 보인다)
    const band = Math.max(1.2, rpx * 0.15);
    const inset = Math.min(0.2, (band / 2 + 0.5) / rpx);
    for (const i of cells) {
      const o = own[i];
      if (o < 0) continue;
      let path = null;
      for (let d = 0; d < 6; d++) {
        const j = this.nb[i * 6 + d];
        if (j >= 0 && own[j] === o) continue;
        if (!path) path = new Path2D();
        const [x0, y0, x1, y1] = seg(i, d, inset);
        path.moveTo(x0, y0);
        path.lineTo(x1, y1);
      }
      if (path) {
        ctx.strokeStyle = css(this.stateRGB[o], lensOn ? 0.75 : 0.9);
        ctx.lineWidth = band;
        ctx.stroke(path);
      }
    }
    // 시도 사이의 경계선 (가운데 짙은 선)
    ctx.beginPath();
    for (const i of cells) {
      if (own[i] < 0) continue;
      for (let d = 0; d < 3; d++) {
        const j = this.nb[i * 6 + d];
        if (j >= 0 && own[j] >= 0 && own[j] !== own[i]) {
          const [x0, y0, x1, y1] = seg(i, d, 0);
          ctx.moveTo(x0, y0);
          ctx.lineTo(x1, y1);
        }
      }
    }
    ctx.strokeStyle = 'rgba(30,24,18,0.8)';
    ctx.lineWidth = Math.max(1, rpx * 0.05);
    ctx.stroke();
    // 휴전선: 대한민국 칸과 외국 땅(북한) 칸이 맞닿은 변
    ctx.beginPath();
    for (const i of cells) {
      if (own[i] < 0) continue;
      for (let d = 0; d < 6; d++) {
        const j = this.nb[i * 6 + d];
        if (j >= 0 && this.foreign[j] === 1) {
          const [x0, y0, x1, y1] = seg(i, d, 0);
          ctx.moveTo(x0, y0);
          ctx.lineTo(x1, y1);
        }
      }
    }
    const lw = Math.max(1.5, rpx * 0.12);
    ctx.strokeStyle = 'rgba(120,20,20,0.9)';
    ctx.lineWidth = lw + 1.5;
    ctx.stroke();
    ctx.setLineDash([lw * 1.6, lw * 1.2]);
    ctx.strokeStyle = '#f6efe0';
    ctx.lineWidth = lw;
    ctx.stroke();
    ctx.setLineDash([]);
  }
}
