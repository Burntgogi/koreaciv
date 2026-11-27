// 장의 작은 도표 — 먹·쪽·주홍만 쓰는 SVG. 숫자는 받은 값 그대로 그린다 (없는 값은 그리지 않는다).

import { h, s } from '../dom.js';
import { fmtInt, fmtMan, isNum } from '../fmt.js';

// 인구 일곱 시점 추이
export function svgSpark(series) {
  const pts = (series || []).filter((p) => isNum(p.v));
  if (pts.length < 2 || pts.length !== (series || []).length) return h('p.pn-na', '시계열 자료 없음');
  const W = 190, H = 54, L = 6, R = 8, T = 8, B = 16;
  let lo = Math.min(...pts.map((p) => p.v)), hi = Math.max(...pts.map((p) => p.v));
  if (hi === lo) { hi += 1; lo -= 1; }
  const x = (k) => L + ((W - L - R) * k) / (pts.length - 1), y = (v) => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
  const yr = (k) => (k.length > 4 ? k.slice(2).replace('-', '.') : "'" + k.slice(2));
  const svg = s('svg', { class: 'pn-spark', viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: 'img',
    'aria-label': `인구 추이: ${pts.map((p) => `${p.k} ${fmtInt(p.v)}명`).join(', ')}` });
  svg.append(s('polyline', { points: pts.map((p, k) => `${x(k).toFixed(1)},${y(p.v).toFixed(1)}`).join(' '), fill: 'none', stroke: 'var(--ink)', 'stroke-width': 1.4 }));
  pts.forEach((p, k) => {
    const last = k === pts.length - 1;
    const c = s('circle', { cx: x(k).toFixed(1), cy: y(p.v).toFixed(1), r: last ? 3.2 : 2.2, fill: last ? 'var(--ju)' : 'var(--paper-hi)', stroke: last ? 'var(--ju)' : 'var(--ink)', 'stroke-width': 1.2 });
    c.append(s('title', null, `${p.k}: ${fmtInt(p.v)}명`));
    svg.append(c);
  });
  svg.append(s('text', { x: L, y: H - 3, class: 'ax' }, yr(pts[0].k)), s('text', { x: W - R, y: H - 3, class: 'ax', 'text-anchor': 'end' }, yr(pts[pts.length - 1].k)));
  return svg;
}

// 나이 피라미드 (다섯 살 계급 21단)
export function svgPyramid(male, female) {
  const n = Math.min(male.length, female.length);
  const W = 520, rowH = 8, H = n * rowH + 22, mid = W / 2, gap = 16;
  const mx = Math.max(1, ...male.filter(isNum), ...female.filter(isNum));
  const sc = (v) => ((mid - gap - 4) * v) / mx;
  const tm = male.reduce((a, b) => a + (b || 0), 0), tf = female.reduce((a, b) => a + (b || 0), 0);
  const svg = s('svg', { class: 'pn-pyrsvg', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `나이 피라미드. 남 ${fmtInt(tm)}명, 여 ${fmtInt(tf)}명. 계급별 값은 이어지는 표에 있다.` });
  for (let k = 0; k < n; k++) {
    const y = H - 20 - (k + 1) * rowH;
    const lab = k === 20 ? '100세 이상' : `${k * 5}–${k * 5 + 4}세`;
    if (isNum(male[k])) { const r = s('rect', { x: (mid - gap - sc(male[k])).toFixed(1), y, width: sc(male[k]).toFixed(1), height: rowH - 1.6, fill: 'var(--jjok)' }); r.append(s('title', null, `남 ${lab}: ${fmtInt(male[k])}명`)); svg.append(r); }
    if (isNum(female[k])) { const r = s('rect', { x: mid + gap, y, width: sc(female[k]).toFixed(1), height: rowH - 1.6, fill: 'var(--ju)' }); r.append(s('title', null, `여 ${lab}: ${fmtInt(female[k])}명`)); svg.append(r); }
    if (k % 4 === 0) svg.append(s('text', { x: mid, y: y + rowH - 1.5, 'text-anchor': 'middle', class: 'ax' }, String(k * 5)));
  }
  svg.append(s('text', { x: mid - gap, y: H - 4, 'text-anchor': 'end', class: 'ax lab' }, `남 ${fmtMan(tm)}`), s('text', { x: mid + gap, y: H - 4, class: 'ax lab' }, `여 ${fmtMan(tf)}`), s('text', { x: mid, y: H - 4, 'text-anchor': 'middle', class: 'ax' }, '나이'));
  return svg;
}

// 전국 고을 분포선: 가는 눈금 + 이 고을의 주홍 점 (순위 자리로 놓는다 — 값의 크기가 아니라 몇 번째인지)
export function svgDist(all, v, label) {
  const W = 64, H = 14, n = all.length;
  let below = 0;
  for (const x of all) if (x < v) below++;
  const t = n > 1 ? below / (n - 1) : 0.5;
  const svg = s('svg', { class: 'pn-dist', viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: 'img', 'aria-label': `${label}: 값 있는 고을 ${n}곳 가운데 낮은 쪽에서 ${below + 1}번째` });
  svg.append(s('line', { x1: 2, x2: W - 2, y1: H / 2, y2: H / 2, stroke: 'var(--hair)', 'stroke-width': 1 }));
  for (const q of [0, 0.25, 0.5, 0.75, 1]) svg.append(s('line', { x1: 2 + (W - 4) * q, x2: 2 + (W - 4) * q, y1: H / 2 - (q === 0.5 ? 3.5 : 2), y2: H / 2 + (q === 0.5 ? 3.5 : 2), stroke: 'var(--ink-3)', 'stroke-width': 0.8 }));
  const c = s('circle', { cx: (2 + (W - 4) * t).toFixed(1), cy: H / 2, r: 3, fill: 'var(--ju)' });
  c.append(s('title', null, `값 있는 고을 ${n}곳 가운데 낮은 쪽에서 ${below + 1}번째 (가운데 눈금 = 중앙)`));
  svg.append(c);
  return svg;
}

// 땅의 쓰임 띠: 통계 항목의 넓이 비 (석채와 같은 빛). 나머지는 '그 밖'
const LAND_COLOR = { 논: '#CBCF8A', 밭: '#DDC996', 과수원: '#BCB574', 시설재배지: '#E5E2D5', 산림: '#89A37C', 시가화: '#D9BBAA' };
export function landStrip(b) {
  const parts = b.parts.filter((p) => isNum(p.pct));
  const rest = Math.max(0, 100 - parts.reduce((a, p) => a + p.pct, 0));
  const wrap = h('div.pn-land');
  wrap.append(h('div.pn-strip', { role: 'img', 'aria-label': '땅의 쓰임: ' + parts.map((p) => `${p.key} ${p.pct.toFixed(1)}%`).join(', ') + (rest > 0.05 ? `, 그 밖 ${rest.toFixed(1)}%` : '') },
    parts.map((p) => h('i', { style: { width: p.pct + '%', background: LAND_COLOR[p.key] || '#C0C992' }, title: `${p.key} ${p.pct.toFixed(1)}%` })),
    rest > 0.05 ? h('i.rest', { style: { width: rest + '%' }, title: `그 밖 ${rest.toFixed(1)}%` }) : null));
  wrap.append(h('ul.pn-landkey', b.parts.map((p) => h('li', h('i', { style: { background: LAND_COLOR[p.key] || '#C0C992' } }), h('span', p.key),
    h('b', isNum(p.pct) ? p.pct.toFixed(1) + '%' : h('span.na', '자료 없음')), h('small', isNum(p.ha) ? fmtInt(p.ha) + 'ha' : ''))),
    rest > 0.05 ? h('li', h('i.rest'), h('span', '그 밖'), h('b', rest.toFixed(1) + '%'), h('small', '')) : null));
  wrap.append(h('p.pn-cap', isNum(b.total) ? `전체 ${fmtInt(b.total)}ha · 띠는 전체 대비 %` : '전체 넓이 자료 없음'));
  return wrap;
}
