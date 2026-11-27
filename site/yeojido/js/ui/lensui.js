// 렌즈 갈피(왼쪽 여백의 세로 단추) · 렌즈 고르는 메뉴 · 범례.
// 범례의 빛깔은 자료의 색이 아니라 안료 띠가 먹판 위에 찍힌 뒤의 빛이다(printed). 분포는 대한민국 육지 칸만 센다.
// 범위 고르기: 연속 척도는 분포 막대를 끌거나 두 손잡이(화살표 키)로, 구간·범주는 단계 단추로. 고른 범위 밖 칸은 종이로 물러난다.

import { lensValues, lensT, lensInv, lensIsContinuous, lensSteps, SCALE_KO, lensMeta } from '../adapter.js';
import { LensColor, printed, rgbCss } from '../map/lenscolor.js';
import { h, clear } from '../dom.js';
import { iconEl } from '../icons.js';
import { lensValueText, lensValueUnit, fmtInt, fmtWhen } from '../fmt.js';

const BINS = 36;
const pcss = (c) => rgbCss(printed(c));

export class LensUI {
  constructor(app) {
    this.app = app;
    this.rail = document.getElementById('rail');
    this.legend = document.getElementById('legend');
    this.legend.setAttribute('role', 'region');
    this.legend.setAttribute('aria-label', '범례');
    this.flyout = h('div#flyout', { role: 'menu', hidden: true });
    document.body.append(this.flyout);
    this.openGroup = null;
    this.expanded = false; // 좁은 화면의 범례 펼침
    this.stats = new WeakMap();
    this.buildRail();
    app.on('lens', () => { this.closeFlyout(false); this.expanded = false; this.update(); });
    app.on('range', () => this.syncRange());
    app.on('resize', () => { if (this.openGroup) this.place(); });
    document.addEventListener('pointerdown', (e) => {
      if (this.openGroup && !this.flyout.contains(e.target) && !e.target.closest('#rail')) this.closeFlyout(false);
    }, true);
    this.flyout.addEventListener('keydown', (e) => this.menuKey(e));
    this.update();
  }

  // ---------- 갈피 ----------
  buildRail() {
    const { app } = this, G = app.D.lenses.groups;
    clear(this.rail);
    const tab = (id, name, n) => h('button.tab', { type: 'button', dataset: { group: id }, 'aria-haspopup': id ? 'menu' : null, 'aria-expanded': id ? 'false' : null,
      title: id ? `${name} 렌즈 ${n}개` : '지형 (렌즈 끄기)', onclick: (e) => (id ? this.toggleFlyout(id, e.currentTarget) : (this.closeFlyout(false), app.setLens(null))) },
      h('span.nm', name), n ? h('span.n', { 'aria-hidden': 'true' }, String(n)) : null);
    this.tabs = [tab('', '지형', 0), ...G.filter((g) => g.lenses.length).map((g) => tab(g.id, g.name, g.lenses.length))];
    this.rail.append(h('div.tabs', this.tabs));
    this.rail.addEventListener('keydown', (e) => {
      const narrow = window.innerWidth <= 700;
      const next = narrow ? 'ArrowRight' : 'ArrowDown', prev = narrow ? 'ArrowLeft' : 'ArrowUp';
      const k = this.tabs.indexOf(document.activeElement);
      if (k < 0) return;
      if (e.key === next || e.key === prev) { e.preventDefault(); e.stopPropagation(); this.tabs[(k + (e.key === next ? 1 : -1) + this.tabs.length) % this.tabs.length].focus(); }
      else if ((e.key === 'ArrowRight' && !narrow) || (e.key === 'ArrowUp' && narrow)) { const g = this.tabs[k].dataset.group; if (g) { e.preventDefault(); e.stopPropagation(); this.openFlyout(g, this.tabs[k]); } }
    });
  }

  markRail() {
    const cur = this.app.lens;
    for (const t of this.tabs) {
      const g = t.dataset.group;
      const on = cur ? g === cur.group : g === '';
      t.classList.toggle('is-on', on);
      if (!g) t.setAttribute('aria-pressed', String(!cur));
      else t.setAttribute('aria-expanded', String(this.openGroup === g));
      t.classList.toggle('is-open', !!g && this.openGroup === g);
    }
  }

  // ---------- 메뉴 ----------
  toggleFlyout(id, btn) { if (this.openGroup === id) this.closeFlyout(true); else this.openFlyout(id, btn); }

  openFlyout(id, btn) {
    const { app } = this, g = app.D.lenses.groups.find((x) => x.id === id);
    if (!g) return;
    this.openGroup = id; this.anchor = btn;
    const items = g.lenses.map((l) => {
      const col = new LensColor(l);
      const sw = h('span.sw', { 'aria-hidden': 'true' });
      if (col.continuous) for (let k = 0; k < 5; k++) sw.append(h('i', { style: { background: pcss(col.at(k / 4)) } }));
      else { const n = Math.min(6, col.steps); for (let k = 0; k < n; k++) sw.append(h('i', { style: { background: pcss(col.step(Math.round((k * (col.steps - 1)) / Math.max(1, n - 1)))) } })); }
      const on = app.lens === l;
      return h('button.item', { type: 'button', role: 'menuitemradio', 'aria-checked': String(on), tabindex: '-1', onclick: () => { const a = this.anchor; this.closeFlyout(false); app.setLens(l.id); app.say(`${l.name} 렌즈`); if (a) a.focus({ preventScroll: true }); } },
        sw, h('b', l.name), h('small', l.unit || SCALE_KO[l.scale] || ''));
    });
    clear(this.flyout).append(h('p.kicker', `${g.name} · 렌즈 ${g.lenses.length}`), h('div.items', items));
    this.flyout.setAttribute('aria-label', `${g.name} 렌즈 고르기`);
    this.flyout.hidden = false;
    this.place();
    this.markRail();
    (items.find((b) => b.getAttribute('aria-checked') === 'true') || items[0]).focus({ preventScroll: true });
  }

  place() {
    const f = this.flyout, a = this.anchor;
    if (!a) return;
    if (window.innerWidth <= 700) { f.style.left = f.style.top = ''; f.classList.add('is-sheet'); return; }
    f.classList.remove('is-sheet');
    const r = a.getBoundingClientRect(), rr = this.rail.getBoundingClientRect();
    f.style.left = Math.round(rr.right + 10) + 'px';
    const top = Math.max(8, Math.min(r.top, window.innerHeight - f.offsetHeight - 12));
    f.style.top = Math.round(top) + 'px';
  }

  closeFlyout(refocus) {
    if (!this.openGroup) return false;
    const a = this.anchor;
    this.openGroup = null;
    this.flyout.hidden = true;
    this.markRail();
    if (refocus && a) a.focus({ preventScroll: true });
    return true;
  }
  closeTransient() {
    if (this.closeFlyout(true)) return true;
    if (this.expanded && window.innerWidth <= 700) { this.expanded = false; this.legend.classList.remove('is-open'); const b = this.legend.querySelector('.lg-exp'); if (b) b.setAttribute('aria-expanded', 'false'); return true; }
    return false;
  }

  menuKey(e) {
    const items = [...this.flyout.querySelectorAll('.item')], k = items.indexOf(document.activeElement);
    const go = (n) => { e.preventDefault(); e.stopPropagation(); items[(n + items.length) % items.length].focus(); };
    if (e.key === 'ArrowDown') go(k + 1);
    else if (e.key === 'ArrowUp') go(k - 1);
    else if (e.key === 'Home') go(0);
    else if (e.key === 'End') go(items.length - 1);
    else if (e.key === 'ArrowLeft' || e.key === 'Tab') { e.preventDefault(); e.stopPropagation(); this.closeFlyout(true); }
  }

  // ---------- 분포 (대한민국 육지 칸) ----------
  statsOf(lens) {
    let s = this.stats.get(lens);
    if (s) return s;
    const { D } = this.app, W = D.world, vals = lensValues(lens, W), cont = lensIsContinuous(lens);
    const steps = lensSteps(lens);
    s = { land: 0, na: 0, bins: new Int32Array(BINS), steps: new Int32Array(Math.max(1, steps)), nums: [], hi: null, lo: null };
    let hiV = -Infinity, loV = Infinity;
    for (let i = 0; i < W.n; i++) {
      if (W.owner[i] < 0) continue;
      s.land++;
      const v = vals[i];
      if (v == null || !Number.isFinite(v)) { s.na++; continue; }
      const t = lensT(lens, v);
      if (cont) s.bins[Math.min(BINS - 1, Math.floor(t * BINS))]++;
      else if (t >= 0 && t < s.steps.length) s.steps[t]++;
      if (lens.scale !== 'category') {
        s.nums.push(v);
        if (v > hiV) { hiV = v; s.hi = i; }
        if (v < loV) { loV = v; s.lo = i; }
      }
    }
    s.nums.sort((a, b) => a - b);
    s.median = s.nums.length ? s.nums[Math.floor((s.nums.length - 1) / 2)] : null;
    s.vals = vals;
    this.stats.set(lens, s);
    return s;
  }

  placeName(i) {
    const D = this.app.D, st = D.stateOfCell(i), co = D.countyOfCell(i), c = D.cityOfCell(i);
    const nm = c && co && c.name !== co.name && !co.name.startsWith(c.name) && !c.name.startsWith(co.name) ? `${c.name} ${co.name}` : co ? co.name : c ? c.name : '';
    return [st && (!c || st.short !== c.name) ? st.short : '', nm].filter(Boolean).join(' ');
  }

  // 자료에서만 낸 두 문장. 정직하게 낼 수 없으면 빈 배열
  summary(lens, s) {
    const out = [];
    const valued = s.land - s.na;
    if (!valued) return out;
    if (lens.scale === 'category') {
      const order = [...s.steps.keys()].filter((k) => s.steps[k] > 0).sort((a, b) => s.steps[b] - s.steps[a]);
      const part = (k) => `${lens.categories[k]} ${fmtInt(s.steps[k])}칸(${((100 * s.steps[k]) / valued).toFixed(1)}%)`;
      if (order.length) out.push(`값이 있는 육지 ${fmtInt(valued)}칸 가운데 가장 많은 것은 ${part(order[0])}${order[1] != null ? `, 다음은 ${part(order[1])}` : ''}이다.`);
      if (order.length > 2) out.push(`지도에 나온 범주는 모두 ${order.length}가지다.`);
      return out;
    }
    if (s.median != null) out.push(`값이 있는 육지 ${fmtInt(valued)}칸의 가운데 값(칸 기준 중앙값)은 ${lens.unit === '지수' ? lensValueText(s.median, lens) : lensValueUnit(s.median, lens)}.`);
    if (s.hi != null && s.lo != null && s.vals[s.hi] !== s.vals[s.lo]) {
      out.push(`가장 높은 칸은 ${this.placeName(s.hi)}(${lensValueText(s.vals[s.hi], lens)}), 가장 낮은 칸은 ${this.placeName(s.lo)}(${lensValueText(s.vals[s.lo], lens)})에 있다.`);
    }
    return out;
  }

  // ---------- 범례 ----------
  update() {
    this.markRail();
    const { app } = this, lens = app.lens, el = this.legend;
    if (!lens) { el.hidden = true; clear(el); this.lens = null; return; }
    const col = app.lensColor || new LensColor(lens), s = this.statsOf(lens), cont = lensIsContinuous(lens);
    this.lens = lens; this.col = col; this.s = s;
    const narrow = window.innerWidth <= 700;
    el.classList.toggle('is-open', this.expanded);

    const head = h('header.lg-head',
      h('h2', lens.name, lens.unit ? h('small', lens.unit) : null),
      h('span.lg-mini', { 'aria-hidden': 'true' }, this.miniRamp(col, cont)),
      h('button.lg-exp', { type: 'button', 'aria-expanded': String(this.expanded), 'aria-label': '범례 펼치기·접기', onclick: (e) => { this.expanded = !this.expanded; el.classList.toggle('is-open', this.expanded); e.currentTarget.setAttribute('aria-expanded', String(this.expanded)); } }, iconEl('up', 18)),
      h('button.x', { type: 'button', 'aria-label': '렌즈 끄고 지형으로', title: '지형으로', onclick: () => { app.setLens(null); const t = this.tabs[0]; if (t && !narrow) t.focus({ preventScroll: true }); } }, iconEl('close', 18)));

    this.selLine = h('p.lg-sel', { 'aria-live': 'polite' });
    const scale = cont ? this.buildHist(lens, col, s) : this.buildSteps(lens, col, s);
    const naChip = h('p.lg-na', h('i.hatch', { 'aria-hidden': 'true' }), s.na ? `자료 없음 ${fmtInt(s.na)}칸` : '자료 없는 칸 없음', h('span.sc', `${SCALE_KO[lens.scale] || lens.scale} 척도 · 육지 ${fmtInt(s.land)}칸`));
    const sum = this.summary(lens, s);
    const M = lensMeta(lens);
    const row = (k, v) => (v ? h('div', h('dt', k), h('dd', v)) : null);
    const det = h('details.lg-det', h('summary', '기준 · 출처 · 정의'),
      h('dl', row('출처', lens.source), row('기준 시점', lens.vintage ? fmtWhen(lens.vintage) : ''), row('집계 기준', lens.basis), row('단위 수준', lens.level), row('정의', lens.description), row('셈법', M.definition),
        row('범위', cont ? `색띠는 ${lensValueText(lens.domain[0], lens)} – ${lensValueText(lens.domain[1], lens)} (육지 칸 값의 2–98 백분위 등 자료가 정한 정의역). 양 끝 막대에는 그 밖의 값이 함께 들어 있다.` : ''),
        M.unitsNote ? h('div.mark', h('dt', '공표 단위 *'), h('dd', M.unitsNote)) : null, row('자료 범위', M.coverage)),
      h('button.btn', { type: 'button', onclick: () => app.almanac.open('lenses') }, '연감에서 렌즈 정의 보기', iconEl('arrow', 14)));
    clear(el).append(head, h('div.lg-body', scale, this.selLine, naChip, sum.length ? h('p.lg-sum', sum.join(' ')) : null, M.unitsNote ? h('p.lg-mark', h('b', '*'), ' 일부 칸은 개편 전 공표 단위의 값이다 (아래 기준 참조).') : null, det));
    el.hidden = false;
    this.syncRange();
  }

  miniRamp(col, cont) {
    const out = [];
    if (cont) for (let k = 0; k < 8; k++) out.push(h('i', { style: { background: pcss(col.at(k / 7)) } }));
    else { const seen = [...this.s.steps.keys()].filter((k) => this.s.steps[k] > 0).slice(0, 8); for (const k of seen) out.push(h('i', { style: { background: pcss(col.step(k)) } })); }
    return out;
  }

  // 연속 척도: 분포 막대 + 색띠 + 두 손잡이
  buildHist(lens, col, s) {
    const max = Math.max(1, ...s.bins);
    this.bars = [];
    const bars = h('div.hist', { 'aria-hidden': 'true' });
    for (let k = 0; k < BINS; k++) {
      const b = h('i', { style: { height: (s.bins[k] ? Math.max(4, (100 * Math.sqrt(s.bins[k] / max))) : 0) + '%', background: pcss(col.at((k + 0.5) / BINS)) }, title: `${fmtInt(s.bins[k])}칸` });
      this.bars.push(b); bars.append(b);
    }
    const ramp = h('div.ramp', { 'aria-hidden': 'true', style: { background: `linear-gradient(90deg, ${Array.from({ length: 13 }, (_, k) => pcss(col.at(k / 12))).join(',')})` } });
    const tv = (t) => lensValueText(lensInv(lens, t), lens);
    const ticks = h('div.ticks', { 'aria-hidden': 'true' }, h('span', '≤ ' + tv(0)), lens.scale === 'diverging' ? h('span.mid', tv(0.5)) : h('span.mid', tv(0.5)), h('span', '≥ ' + tv(1)));
    this.lo = 0; this.hi = BINS;
    const thumb = (which) => h('button.thumb', { type: 'button', role: 'slider', 'aria-label': which === 'lo' ? '범위 아래 끝' : '범위 위 끝', 'aria-valuemin': '0', 'aria-valuemax': String(BINS), dataset: { which },
      onkeydown: (e) => {
        const d = e.key === 'ArrowRight' || e.key === 'ArrowUp' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowDown' ? -1 : e.key === 'PageUp' ? 4 : e.key === 'PageDown' ? -4 : 0;
        if (e.key === 'Home' || e.key === 'End') { e.preventDefault(); e.stopPropagation(); if (which === 'lo') this.setBins(e.key === 'Home' ? 0 : this.hi - 1, this.hi); else this.setBins(this.lo, e.key === 'End' ? BINS : this.lo + 1); return; }
        if (!d) return;
        e.preventDefault(); e.stopPropagation();
        if (which === 'lo') this.setBins(Math.max(0, Math.min(this.hi - 1, this.lo + d)), this.hi);
        else this.setBins(this.lo, Math.max(this.lo + 1, Math.min(BINS, this.hi + d)));
      } });
    this.tLo = thumb('lo'); this.tHi = thumb('hi');
    this.band = h('div.band', { 'aria-hidden': 'true' });
    const track = h('div.track', bars, ramp, this.band, this.tLo, this.tHi);
    // 끌어서 고르기 (막대 위 어디서나). 손잡이를 잡으면 그 끝만 옮긴다
    let drag = null;
    const binAt = (e) => { const r = bars.getBoundingClientRect(); return Math.max(0, Math.min(BINS, ((e.clientX - r.left) / r.width) * BINS)); };
    track.addEventListener('pointerdown', (e) => {
      if (e.button > 0) return;
      const th = e.target.closest('.thumb');
      const b = binAt(e);
      drag = th ? { fixed: th.dataset.which === 'lo' ? this.hi : this.lo, moved: true } : { fixed: Math.floor(Math.min(BINS - 1, b)), start: b, moved: false, bin: true };
      track.setPointerCapture(e.pointerId);
      e.preventDefault();
      if (th) th.focus({ preventScroll: true });
    });
    track.addEventListener('pointermove', (e) => {
      if (!drag) return;
      const b = binAt(e);
      if (drag.bin) {
        if (Math.abs(b - drag.start) > 0.2) drag.moved = true;
        const a = Math.floor(Math.min(BINS - 1, Math.min(drag.start, b))), z = Math.ceil(Math.max(drag.start, b));
        this.setBins(a, Math.max(a + 1, Math.min(BINS, z)));
      } else {
        const p = Math.round(b);
        const a = Math.min(drag.fixed, p), z = Math.max(drag.fixed, p);
        this.setBins(a, Math.max(a + 1, z));
      }
    });
    const end = (e) => {
      if (!drag) return;
      if (drag.bin && !drag.moved) { // 한 번 누르면 그 막대 하나 (이미 그 하나면 풀기)
        const k = drag.fixed;
        if (this.lo === k && this.hi === k + 1) this.setBins(0, BINS); else this.setBins(k, k + 1);
      }
      drag = null;
      try { track.releasePointerCapture(e.pointerId); } catch (x) { /* */ }
    };
    track.addEventListener('pointerup', end);
    track.addEventListener('pointercancel', end);
    return h('div.lg-scale.cont', { role: 'group', 'aria-label': '값의 분포와 범위 고르기 — 막대를 끌거나 손잡이에서 화살표 키' }, track, ticks);
  }

  setBins(lo, hi) {
    const { app } = this, lens = this.lens;
    lo = Math.max(0, Math.min(BINS - 1, lo)); hi = Math.max(lo + 1, Math.min(BINS, hi));
    if (lo === 0 && hi === BINS) { if (app.lensRange) app.setLensRange(null); else this.syncRange(); return; }
    const cur = app.lensRange;
    if (cur && cur.kind === 'bins' && cur.lo === lo && cur.hi === hi) return;
    app.setLensRange({ kind: 'bins', lo, hi, test: (v) => { if (v == null || !Number.isFinite(v)) return false; const k = Math.min(BINS - 1, Math.floor(lensT(lens, v) * BINS)); return k >= lo && k < hi; } });
  }

  // 구간·범주: 단계 단추
  buildSteps(lens, col, s) {
    const cat = lens.scale === 'category';
    const ids = [...s.steps.keys()].filter((k) => (cat ? s.steps[k] > 0 : true));
    if (cat) ids.sort((a, b) => s.steps[b] - s.steps[a]);
    this.chips = new Map();
    const list = h('div.chips' + (ids.length > 6 ? '.two' : ''), { role: 'group', 'aria-label': '단계 고르기 — 누른 단계의 칸만 남긴다' });
    for (const k of ids) {
      const label = cat ? lens.categories[k] : lens.binLabels[k] || String(k);
      const b = h('button.chip', { type: 'button', 'aria-pressed': 'false', title: label, onclick: () => this.toggleStep(k) }, h('i', { style: { background: pcss(col.step(k)) } }), h('span.lb', label), h('span.ct', fmtInt(s.steps[k])));
      this.chips.set(k, b); list.append(b);
    }
    return h('div.lg-scale.step', list);
  }

  toggleStep(k) {
    const { app } = this, lens = this.lens, cur = app.lensRange;
    const set = new Set(cur && cur.kind === 'steps' ? cur.set : []);
    if (set.has(k)) set.delete(k); else set.add(k);
    if (!set.size) return app.setLensRange(null);
    app.setLensRange({ kind: 'steps', set, test: (v) => v != null && set.has(lensT(lens, v)) });
  }

  // 고른 범위를 범례에 비춘다
  syncRange() {
    const { app } = this, lens = this.lens, R = app.lensRange, s = this.s;
    if (!lens || !this.selLine) return;
    clear(this.selLine);
    let n = 0, text = '';
    if (this.bars) {
      const lo = R && R.kind === 'bins' ? R.lo : 0, hi = R && R.kind === 'bins' ? R.hi : BINS;
      this.lo = lo; this.hi = hi;
      this.bars.forEach((b, k) => b.classList.toggle('off', k < lo || k >= hi));
      const pct = (x) => (100 * x) / BINS + '%';
      this.band.style.left = pct(lo); this.band.style.width = pct(hi - lo);
      this.tLo.style.left = pct(lo); this.tHi.style.left = pct(hi);
      const a = lensValueText(lensInv(lens, lo / BINS), lens), z = lensValueText(lensInv(lens, hi / BINS), lens);
      this.tLo.setAttribute('aria-valuenow', String(lo)); this.tLo.setAttribute('aria-valuetext', (lo === 0 ? '처음부터' : a));
      this.tHi.setAttribute('aria-valuenow', String(hi)); this.tHi.setAttribute('aria-valuetext', (hi === BINS ? '끝까지' : z));
      if (R && R.kind === 'bins') { for (let k = lo; k < hi; k++) n += s.bins[k]; text = `${lo === 0 ? '≤ ' : ''}${lo === 0 ? z : a}${lo === 0 ? '' : hi === BINS ? ' 이상' : ' – ' + z}`; }
    }
    if (this.chips) {
      const set = R && R.kind === 'steps' ? R.set : null;
      for (const [k, b] of this.chips) { b.setAttribute('aria-pressed', String(!!set && set.has(k))); b.classList.toggle('off', !!set && !set.has(k)); if (set && set.has(k)) n += s.steps[k]; }
      if (set) text = `${set.size}단계`;
    }
    if (R) {
      this.selLine.append(h('span', `선택 ${text} · `, h('b', `${fmtInt(n)}칸`), ` (${((100 * n) / Math.max(1, s.land)).toFixed(1)}%)`),
        h('button.clear', { type: 'button', onclick: () => app.setLensRange(null) }, '풀기'));
    }
    this.legend.classList.toggle('has-range', !!R);
  }
}
