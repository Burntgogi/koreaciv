// 도시 깃발: 이름 + 인구(만 단위) 띠. 확대하면 그 아래에 다섯 산출(식량·생산·금·과학·문화)을 작게 보인다.
// 인구가 큰 도시부터 놓고, 이미 놓인 깃발과 겹치면 그 확대 수준에서는 숨긴다.

import { STATE_COLORS } from './terrain.js';

export function fmtMan(p) {
  if (p >= 1e6) return Math.round(p / 1e4).toLocaleString('ko-KR') + '만';
  return (p / 1e4).toFixed(1) + '만';
}

// 금액(원): 34.3조, 8,120억, 12.4억, 2.3억, 8,500만
export function fmtWon(v, compact = false) {
  if (v === null || v === undefined) return '자료 없음';
  const a = Math.abs(v);
  if (a >= 1e12) return (v / 1e12).toFixed(a >= 1e14 ? 0 : 1).replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '조';
  if (a >= 1e10) return Math.round(v / 1e8).toLocaleString('ko-KR') + '억';
  if (a >= 1e8) return (v / 1e8).toFixed(1) + '억';
  if (a >= 1e4) return Math.round(v / 1e4).toLocaleString('ko-KR') + '만';
  return compact ? Math.round(v).toString() : Math.round(v).toLocaleString('ko-KR') + '원';
}

// 생산이 부분 합계(광업 비공개 몫 제외)인지와 설명
export function partialNote(o, k) {
  const p = o && o.yields_partial && o.yields_partial[k];
  if (!p || !p.length) return null;
  const n = o.production_mining_excluded || 0;
  return `광업 비공개 ${n}곳 제외`;
}

export const YIELD_ICONS = [['food', '🌾'], ['production', '⚙️'], ['gold', '💰'], ['science', '🔬'], ['culture', '🎭']];

const FONT = '"Pretendard","Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif';
const H1 = 19, H2 = 15;

function star(ctx, x, y, r) {
  ctx.beginPath();
  for (let k = 0; k < 10; k++) {
    const a = -Math.PI / 2 + (k * Math.PI) / 5;
    const rr = k % 2 ? r * 0.45 : r;
    ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
  }
  ctx.closePath();
}

export class Banners {
  constructor(cities) {
    this.cities = cities.slice().sort((a, b) => b.population - a.population);
    this.rects = [];
    this.widths = new Map();
  }

  measure(ctx, c, withYields) {
    const key = c.id + (withYields ? 'y' : '');
    if (this.widths.has(key)) return this.widths.get(key);
    ctx.font = `700 12px ${FONT}`;
    const a = ctx.measureText(c.name).width;
    ctx.font = `500 11px ${FONT}`;
    const b = ctx.measureText(fmtMan(c.population)).width;
    let y = 0;
    const ytxt = [];
    if (withYields) {
      ctx.font = `500 10px ${FONT}`;
      for (const [k, icon] of YIELD_ICONS) {
        const v = c.yields ? c.yields[k] : null;
        const t = v == null ? '–' : fmtWon(v, true) + (partialNote(c, k) ? '*' : '');
        const tw = ctx.measureText(t).width;
        ytxt.push([icon, t, tw]);
        y += 13 + tw + 5;
      }
    }
    const w = { name: a, pop: b, y, ytxt };
    this.widths.set(key, w);
    return w;
  }

  // 화면 좌표 배치. selected 는 항상 보인다. 반환: 놓인 깃발 목록
  // 놓는 순서 (7b #1, wonders.json zoom.draw_priority.rule): 선택한 도시 → 수도·도청 소재지(인구 순) → 인구 50만 이상 → 그 밖(배율에 따른 최소 인구 이상).
  // 앞선 깃발과 겹치면 그 배율에서 숨긴다. 전국 배율(z < budget.z_max)에서는 화면에 budget 개수까지만 (선택한 도시는 늘).
  // avoid: 먼저 놓을 우선순위 아이콘 상자(원전). 기본 자리가 그 상자와 겹치면 깃발을 좌우로 밀어 비켜 세운다.
  // 비켜 설 자리가 없으면 큰 도시(수도·도청·인구 50만 이상·선택)는 제자리에 두고(아이콘이 옮겨 감), 나머지는 이 배율에서 숨긴다.
  // 시도 이름은 깃발을 숨기지 않는다 (7b #2: 시도 이름은 깃발 아래 층).
  layout(ctx, cam, selected, avoid = [], budget = null) {
    if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
    const placed = [];
    const out = [];
    const pad = 3;
    const z = cam.scale / cam.minScale;
    this.withYields = z >= 3.2;
    // 확대 수준에 따른 최소 인구: 전국 화면 15만, 2배 확대 3.75만, 4배 약 0.9만 … (수도·도청 소재지는 늘 후보)
    const minPop = 150000 / (z * z);
    const cap = budget && z < budget.z_max ? (cam.vw <= budget.mobile_vw ? budget.flags_mobile : budget.flags_desktop) : Infinity;
    const tier = (c) => (c.id === selected ? 0 : c.capital !== '없음' ? 1 : c.population >= 500000 ? 2 : 3);
    const order = this.cities.slice().sort((a, b) => tier(a) - tier(b) || b.population - a.population);
    let n = 0;
    for (const c of order) {
      if (c.id !== selected && c.capital === '없음' && c.population < minPop) continue;
      if (c.id !== selected && n >= cap) continue;
      const [sx, sy] = cam.toScreen(c.x, c.y);
      if (sx < -120 || sy < -60 || sx > cam.vw + 120 || sy > cam.vh + 60) continue;
      const m = this.measure(ctx, c, this.withYields);
      const icon = c.capital !== '없음' ? 14 : 8;
      const w = Math.max(6 + icon + m.name + 5 + m.pop + 7, this.withYields ? m.y + 8 : 0);
      const h = this.withYields ? H1 + H2 : H1;
      const hits = (r, lst) => lst.some((p) => r.x0 < p.x1 && r.x1 > p.x0 && r.y0 < p.y1 && r.y1 > p.y0);
      const at = (dx) => {
        const x = Math.round(sx - w / 2 + dx), y = Math.round(sy - h - 7);
        return { x, y, r: { x0: x - pad, y0: y - pad, x1: x + w + pad, y1: sy + 3 + pad } };
      };
      let pos = at(0);
      if (c.id !== selected && hits(pos.r, placed)) continue;
      if (avoid.length && hits(pos.r, avoid)) {
        // 좌우로 밀기 (깃대가 깃발 안에 남는 만큼, 덜 움직인 쪽부터). 위아래로는 옮기지 않는다(다른 깃발·시도 이름 자리를 흔들지 않게)
        const lim = Math.max(0, w / 2 - 8), cand = [];
        for (let d = 4; d <= lim; d += 4) cand.push(-d, d);
        const ok = cand.map(at).find((q) => !hits(q.r, avoid) && (c.id === selected || !hits(q.r, placed)));
        const big = c.id === selected || c.capital !== '없음' || c.population >= 500000;
        if (ok) pos = ok;
        else if (!big) continue; // 작은 도시 깃발은 이 배율에서 비켜 줌
      }
      const { x, y, r } = pos;
      placed.push(r);
      out.push({ c, x, y, w, h, sx, sy, icon, m, r });
      n += 1;
    }
    // 그리기·누르기 순서는 인구가 큰 것이 위 (draw 는 뒤에서부터 그린다)
    out.sort((a, b) => (a.c.id === selected ? -1 : b.c.id === selected ? 1 : b.c.population - a.c.population));
    this.rects = out;
    return out;
  }

  draw(ctx, selected, hover) {
    const items = this.rects;
    if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
    ctx.textBaseline = 'middle';
    for (let k = items.length - 1; k >= 0; k--) {
      const { c, x, y, w, h, sx, sy, icon, m } = items[k];
      const col = STATE_COLORS[c.sido];
      const sel = c.id === selected, hov = c.id === hover;
      ctx.strokeStyle = 'rgba(20,20,28,0.8)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(sx, y + h);
      ctx.lineTo(sx, sy);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(sx, sy, 3, 0, Math.PI * 2);
      ctx.fillStyle = col;
      ctx.fill();
      ctx.strokeStyle = '#141820';
      ctx.stroke();
      ctx.beginPath();
      ctx.roundRect(x, y, w, h, 4);
      ctx.fillStyle = sel ? 'rgba(48,38,14,0.96)' : hov ? 'rgba(38,44,60,0.96)' : 'rgba(20,24,34,0.88)';
      ctx.fill();
      ctx.lineWidth = sel ? 2 : 1;
      ctx.strokeStyle = sel ? '#f3c74b' : col;
      ctx.stroke();
      ctx.beginPath();
      ctx.roundRect(x + 3, y + 3, icon, H1 - 6, 2);
      ctx.fillStyle = col;
      ctx.fill();
      if (c.capital === '수도') {
        star(ctx, x + 3 + icon / 2, y + H1 / 2, 5.2);
        ctx.fillStyle = '#fff6c8';
        ctx.fill();
      } else if (c.capital === '도청소재지' || c.capital === '통합청사') {
        // 통합청사(전남광주통합특별시 청사 3곳, 특별법 제7조제3항)는 속이 빈 마름모: 주 청사를 하나로 정하지 않는다
        ctx.beginPath();
        const cx = x + 3 + icon / 2, cy = y + H1 / 2;
        ctx.moveTo(cx, cy - 4);
        ctx.lineTo(cx + 3.4, cy);
        ctx.lineTo(cx, cy + 4);
        ctx.lineTo(cx - 3.4, cy);
        ctx.closePath();
        if (c.capital === '통합청사') {
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1.4;
          ctx.stroke();
        } else {
          ctx.fillStyle = '#ffffff';
          ctx.fill();
        }
      }
      ctx.font = `700 12px ${FONT}`;
      ctx.fillStyle = '#f4f1ea';
      ctx.fillText(c.name, x + 6 + icon, y + H1 / 2 + 0.5);
      ctx.font = `500 11px ${FONT}`;
      ctx.fillStyle = '#c9c2ae';
      ctx.fillText(fmtMan(c.population), x + 6 + icon + m.name + 5, y + H1 / 2 + 0.5);
      if (this.withYields && m.ytxt.length) {
        ctx.strokeStyle = 'rgba(255,255,255,0.1)';
        ctx.beginPath();
        ctx.moveTo(x + 3, y + H1);
        ctx.lineTo(x + w - 3, y + H1);
        ctx.stroke();
        let xx = x + 5;
        const yy = y + H1 + H2 / 2;
        for (const [ic, t, tw] of m.ytxt) {
          ctx.font = `10px ${FONT}`;
          ctx.fillText(ic, xx, yy);
          ctx.font = `500 10px ${FONT}`;
          ctx.fillStyle = t === '–' ? '#7d776a' : '#e8dcb5';
          ctx.fillText(t, xx + 13, yy);
          ctx.fillStyle = '#c9c2ae';
          xx += 13 + tw + 5;
        }
      }
    }
  }

  hit(sx, sy) {
    for (const b of this.rects) {
      if (sx >= b.x && sx <= b.x + b.w && sy >= b.y && sy <= b.y + b.h) return b.c;
    }
    return null;
  }
}
