// 장(패널) — 고을(읍지)·시도·전국·층 항목·교역로. 자료는 adapter 의 보기 모형(cityView …)만 읽는다.
// 넓은 화면: 오른쪽에서 넘어오는 접지 한 장. 좁은 화면(≤700px): 세 높이로 서는 아래 장.
// 자료에서 온 글은 모두 텍스트 노드(h)로 넣는다.

import { cityView, stateView, nationView, itemView, routeView } from '../adapter.js';
import { h, s, clear, add, numEl, na, reducedMotion } from '../dom.js';
import { iconEl, KIND_ICON } from '../icons.js';
import { KINDS, YIELDS } from '../config.js';
import { fmtInt, fmtFixed, fmtPct, fmtWon, fmtUsd, fmtMan, wonParts, usdParts, manParts, isNum } from '../fmt.js';
import { svgSpark, svgPyramid, svgDist, landStrip } from './panel_charts.js';

const SNAPS = ['low', 'mid', 'high'];
const SNAP_KO = { low: '낮게', mid: '가운데', high: '높게' };

// 값 모형 -> 노드
function val(v, big = false) {
  if (!v || v.t === 'na') { const e = na(); if (v && v.why) e.title = v.why; return e; }
  const cls = big ? 'big' : '';
  switch (v.t) {
    case 'won': { const p = wonParts(v.v); return numEl(p ? [p[0], p[1] + '원'] : null, cls); }
    case 'usd': { const p = usdParts(v.v); if (p && v.sign && v.v > 0) p[0] = '+' + p[0]; return numEl(p, cls); }
    case 'pct': return numEl([fmtPct(v.v, v.d ?? 1, !!v.sign).replace('%', ''), '%'], cls);
    case 'int': return numEl([fmtInt(v.v), v.unit || ''], cls);
    case 'fix': return numEl([fmtFixed(v.v, v.d ?? 1), v.unit || ''], cls);
    default: return h('span.txt', v.v);
  }
}

export class Panel {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('panel');
    this.mode = null; this.arg = null;
    this.snap = 'mid';
    this.sort = 'pop'; this.tab = {};
    this.el.classList.add('pn');
    app.on('resize', () => { if (!this.el.hidden) this.applySnap(false); });
  }

  // ---------- 열고 닫기 ----------
  open(mode, arg, view, label) {
    const same = this.mode === mode && this.key === (view ? view.id : null);
    this.mode = mode; this.arg = arg; this.key = view ? view.id : null;
    const el = this.el, D = this.app.D;
    el.setAttribute('aria-label', label);
    const keepScroll = same && this.body ? this.body.scrollTop : 0;
    const act = document.activeElement;
    const wantFocus = !this.noFocus && !!act && act !== this.app.canvas && act !== document.body && (!same || this.el.contains(act));
    clear(el);
    this.handle = h('button.pn-handle', { type: 'button', 'aria-label': `장 높이 바꾸기 (지금 ${SNAP_KO[this.snap]})`, onclick: () => { if (this.dragged) { this.dragged = false; return; } this.cycleSnap(); } }, h('i'));
    this.bindDrag(this.handle);
    this.body = h('div.pn-body', { tabindex: '-1' });
    el.append(this.handle,
      h('button.pn-close', { type: 'button', 'aria-label': '장 닫기', title: '닫기 (Esc)', onclick: () => this.app.clearSelection() }, iconEl('close', 18)),
      this.body);
    if (!view) this.body.append(h('div.pn-pad', h('h2.pn-h-plain', { tabindex: '-1' }, label), h('p.pn-na', '이 장을 그릴 자료가 없습니다.' + (D.failed.length ? ` (불러오지 못한 파일: ${D.failed.join(', ')})` : ''))));
    else this.body.append(mode === 'item' || mode === 'route' ? this.renderSmall(view) : this.renderPlace(view));
    el.hidden = false;
    el.dataset.mode = mode;
    this.applySnap(false);
    this.body.scrollTop = keepScroll;
    // 초점: 지도(캔버스)에서 눌러 연 것이 아니면 장의 제목으로 옮긴다
    if (wantFocus) {
      const hd = this.body.querySelector('h2');
      if (hd) hd.focus({ preventScroll: true });
    }
  }

  focusHeading() { if (this.el.hidden) return; const hd = this.body && this.body.querySelector('h2'); if (hd) hd.focus({ preventScroll: true }); }

  hide() { this.mode = null; this.arg = null; this.key = null; this.el.hidden = true; }

  refresh() {
    if (this.el.hidden || !this.mode) return;
    const a = this.arg;
    this.noFocus = !this.el.contains(document.activeElement);
    try { this.refreshNow(a); } finally { this.noFocus = false; }
  }

  refreshNow(a) {
    if (this.mode === 'city') this.showCity(a); else if (this.mode === 'state') this.showState(a); else if (this.mode === 'nation') this.showNation();
    else if (this.mode === 'item') this.showItem(a); else if (this.mode === 'route') this.showRoute(a);
  }

  showCity(c) { this.open('city', c, cityView(this.app.D, c.id), `${c.name} 고을 장`); }
  showState(st) { this.open('state', st, stateView(this.app.D, st.code), `${st.name} 시도 장`); }
  showNation() { this.open('nation', null, nationView(this.app.D), '대한민국 전국 장'); }
  showItem(it) { this.open('item', it, itemView(this.app.D, it), `${it.name} 항목`); }
  showRoute(rt) { this.open('route', rt, routeView(this.app.D, rt), '교역로 구간'); }

  // ---------- 아래 장 (좁은 화면) ----------
  applySnap(announce) {
    const el = this.el;
    for (const k of SNAPS) el.classList.toggle('is-' + k, this.snap === k);
    el.style.height = '';
    if (this.handle) this.handle.setAttribute('aria-label', `장 높이 바꾸기 (지금 ${SNAP_KO[this.snap]})`);
    if (announce) this.app.say(`장 높이 ${SNAP_KO[this.snap]}`);
  }
  setSnap(k) {
    this.snap = k; this.applySnap(true);
    const done = () => { this.app.updateInsets(); this.app.requestDraw(); };
    done(); setTimeout(done, reducedMotion() ? 0 : 280);
  }
  cycleSnap() { this.setSnap(SNAPS[(SNAPS.indexOf(this.snap) + 1) % SNAPS.length]); }
  bindDrag(grip) {
    let y0 = 0, h0 = 0, on = false;
    grip.addEventListener('pointerdown', (e) => {
      if (!this.app.narrow) return;
      on = true; this.dragged = false; y0 = e.clientY; h0 = this.el.getBoundingClientRect().height;
      grip.setPointerCapture(e.pointerId); this.el.classList.add('is-dragging');
    });
    grip.addEventListener('pointermove', (e) => {
      if (!on) return;
      const dy = e.clientY - y0;
      if (Math.abs(dy) > 5) this.dragged = true;
      if (this.dragged) this.el.style.height = Math.max(90, Math.min(window.innerHeight * 0.94, h0 - dy)) + 'px';
    });
    const end = () => {
      if (!on) return;
      on = false; this.el.classList.remove('is-dragging');
      if (!this.dragged) return;
      const f = this.el.getBoundingClientRect().height / window.innerHeight;
      this.setSnap(f < 0.4 ? 'low' : f < 0.74 ? 'mid' : 'high');
      setTimeout(() => { this.dragged = false; }, 0);
    };
    grip.addEventListener('pointerup', end);
    grip.addEventListener('pointercancel', end);
  }

  // ---------- 이동 ----------
  go(g) {
    const a = this.app;
    if (!g) return;
    if (g.city != null) a.selectCity(g.city, { fly: true });
    else if (g.state) a.selectState(g.state, { fly: true });
    else if (g.nation) a.showNation();
    else if (g.item && a.layerMap) a.selectItem(a.layerMap.byId.get(g.item) || a.D.layers.byId.get(g.item), { fly: true });
    else if (g.route && a.layerMap) a.selectRoute(a.layerMap.routeById.get(g.route), { fly: true });
  }
  goBtn(cls, g, ...kids) { return h('button.' + cls, { type: 'button', onclick: () => this.go(g) }, ...kids); }

  // ---------- 고을·시도·전국 ----------
  renderPlace(v) {
    const H = v.head, root = h('article.pn-place.pn-' + v.kind);
    const len = [...v.title].length;
    const title = h('h2.pn-title', { tabindex: '-1', dataset: { len: String(Math.min(len, 9)) } }, v.title);
    const meta = h('div.pn-meta');
    if (v.kicker) meta.append(this.goBtn('pn-kicker', v.kicker.go, v.kicker.text, iconEl('arrow', 12)));
    if (v.full && v.full !== v.title) meta.append(h('p.pn-full', v.full));
    if (v.badges && v.badges.length) meta.append(h('ul.pn-badges', v.badges.map((b) => h('li' + (b.tone ? '.is-' + b.tone : ''), b.title ? { title: b.title } : null, b.text))));
    if (v.sub) meta.append(h('p.pn-sub', v.sub));
    if (v.scope) meta.append(h('p.pn-scope', v.scope));
    // 인구
    const pop = h('div.pn-pop');
    pop.append(h('p.pn-popnum', isNum(H.pop) ? [h('span.num.huge', fmtInt(H.pop), h('small', '명'))] : na(), H.rank ? h('span.rank' + (H.rank <= 10 ? '.top' : ''), `${H.rank}위`) : null));
    const g = H.growth5;
    pop.append(h('div.pn-poprow', svgSpark(H.series), h('p.pn-popnote', h('span', H.when), h('span', `${H.growthLabel} `, isNum(g) ? h('b' + (g < 0 ? '.down' : '.up'), fmtPct(g, 2, true)) : na()))));
    meta.append(pop);
    root.append(h('header.pn-head', title, meta));
    if (v.portrait && v.portrait.length) root.append(h('p.pn-portrait', v.portrait.join(' ')));
    const folds = [];
    for (const sec of v.sections) { if (sec.fold) folds.push(sec); else root.append(this.section(sec)); }
    if (folds.length || (v.footNotes && v.footNotes.length)) {
      const tail = h('section.pn-sec.pn-tail', h('h3', '더 보기'));
      for (const sec of folds) tail.append(h('details.pn-fold', h('summary', sec.title, sec.caption ? h('small', sec.caption) : null), this.blocks(sec.blocks), this.notes(sec.notes)));
      if (v.footNotes && v.footNotes.length) tail.append(this.notes(v.footNotes, '이 장의 기준'));
      root.append(tail);
    }
    if (v.foot) root.append(h('p.pn-foot', v.foot));
    root.append(h('p.pn-foot', h('button.pn-link', { type: 'button', onclick: () => this.app.almanac.open('sources') }, '모든 출처와 기준 시점은 연감에')));
    return root;
  }

  section(sec) {
    return h('section.pn-sec', { dataset: { sec: sec.id } },
      h('div.pn-sechead', h('h3', sec.title), sec.caption ? h('p.pn-cap', sec.caption) : null),
      this.blocks(sec.blocks), this.notes(sec.notes));
  }

  notes(list, label = '기준과 주의') {
    const L = (list || []).filter(Boolean);
    if (!L.length) return null;
    return h('details.pn-notes', h('summary', label, h('small', `${L.length}건`)), h('ol', L.map((t) => h('li', t))));
  }

  blocks(list) { return (list || []).filter(Boolean).map((b) => this.block(b)); }

  block(b) {
    switch (b.type) {
      case 'yields': return this.bYields(b);
      case 'tabs': return this.bTabs(b);
      case 'bars': return this.bBars(b);
      case 'kv': return this.bKV(b);
      case 'pyramid': return h('figure.pn-pyr', svgPyramid(b.male, b.female), h('figcaption', b.caption || ''), this.pyramidTable(b));
      case 'ext': return this.bExt(b);
      case 'strip': return landStrip(b);
      case 'chips': return this.bChips(b.items);
      case 'kinds': return this.bKinds(b);
      case 'list': return this.bList(b);
      case 'table': return this.bTable(b);
      case 'sortlist': return this.bSort(b);
      case 'sub': return h('h4.pn-subh', b.title, b.small ? h('small', b.small) : null);
      case 'warn': return h('p.pn-warn', b.text);
      case 'note': return h('p.pn-note', b.text);
      case 'fold': return h('details.pn-fold', h('summary', b.summary, b.small ? h('small', b.small) : null), this.blocks(b.blocks));
      default: return h('p.pn-text' + (b.na ? '.pn-na' : ''), b.text || '');
    }
  }

  bYields(b) {
    const icon = Object.fromEntries(YIELDS.map(([k]) => [k, k]));
    return h('ul.pn-yields', b.items.map((y) => {
      const li = h('li' + (y.partial ? '.is-partial' : ''));
      li.append(h('span.yn', iconEl(icon[y.key] || 'gold', 18), y.name));
      const v = val(y.value);
      if (y.partial) { v.append(h('sup', { title: `제조업 + 건설업 + 공개된 광업의 합. ${y.partial} (비공개 몫을 추정해 더하지 않음)` }, '*')); }
      li.append(h('span.yv', v));
      if (y.rank) li.append(h('span.rank' + (y.rank <= 10 ? '.top' : ''), `${y.rank}위`));
      li.append(h('span.yr', y.partial ? `* ${y.partial} · ${y.rule}` : y.rule));
      for (const t of y.subs || []) li.append(h('span.ys', t));
      if (y.jobs) li.append(h('span.ys', { title: y.jobs.tip }, y.jobs.text));
      return li;
    }));
  }

  bTabs(b) {
    const key = b.tabs.map((t) => t.id).join(',');
    let cur = this.tab[key] && b.tabs.some((t) => t.id === this.tab[key]) ? this.tab[key] : b.tabs[0].id;
    const wrap = h('div.pn-tabs');
    const bar = h('div.pn-tabbar', { role: 'group', 'aria-label': '보기 바꾸기' });
    const pane = h('div.pn-tabpane');
    const draw = () => {
      clear(bar);
      for (const t of b.tabs) bar.append(h('button', { type: 'button', 'aria-pressed': String(t.id === cur), onclick: () => { cur = this.tab[key] = t.id; draw(); } }, t.label));
      clear(pane).append(this.block(b.tabs.find((t) => t.id === cur).block));
    };
    draw();
    wrap.append(bar, pane);
    return wrap;
  }

  bBars(b) {
    const mx = Math.max(1e-9, ...b.rows.map((r) => (isNum(r.v) ? Math.abs(r.v) : 0)));
    const f = (v) => (b.fmt === 'won' ? fmtWon(v, '') : b.fmt === 'usd' ? fmtUsd(v) : b.fmt === 'mw' ? fmtFixed(v, v < 10 ? 2 : 1) + ' MW' : fmtInt(v) + (b.fmt === 'people' ? '명' : ''));
    const row = (r) => h('li' + (r.dim ? '.dim' : '') + (b.clip ? '.clip' : ''),
      h('span.bl', { title: r.label }, r.label),
      h('span.bb', h('i', { style: { width: (isNum(r.v) ? Math.max(0.6, (100 * Math.abs(r.v)) / mx) : 0) + '%' } })),
      h('span.bv', isNum(r.v) ? [f(r.v), isNum(r.share) ? h('small', r.share.toFixed(1) + '%') : null] : h('span.na', b.naText || '자료 없음')));
    const top = b.top || b.rows.length;
    const wrap = h('div.pn-barswrap');
    if (b.caption) wrap.append(h('p.pn-cap', b.caption));
    wrap.append(h('ul.pn-bars', b.rows.slice(0, top).map(row)));
    if (b.rows.length > top) wrap.append(h('details.pn-rest', h('summary', `나머지 ${b.rows.length - top}개 펼치기`), h('ul.pn-bars', b.rows.slice(top).map(row))));
    return wrap;
  }

  bKV(b) {
    if (!b.leader) {
      return h('dl.pn-tiles', { style: { '--cols': String(b.cols || 3) } }, b.rows.map((r) => h('div', h('dt', r.label, r.sub ? h('small', r.sub) : null), h('dd', val(r.value), (r.subs || []).map((t) => h('small', t))))));
    }
    const row = (r) => {
      const dd = h('dd');
      if (r.range) dd.append(h('span.num', `${r.range.label} ${r.range.min.toFixed(1)}–${r.range.max.toFixed(1)}`, h('small', r.range.unit)));
      else { const v = val(r.value); if (r.mark) v.append(h('sup', r.mark)); dd.append(v); }
      if (r.rank) dd.append(h('span.rank' + (r.rank <= 10 ? '.top' : ''), { title: r.rankNote || (r.of ? `${r.of}곳 중` : '') }, `${r.rank}위`));
      const el = h('div', h('dt', h('span', r.label), r.sub ? h('small', r.sub) : null), r.dist && r.dist.all ? svgDist(r.dist.all, r.dist.v, r.label) : h('span.lead', { 'aria-hidden': 'true' }), dd);
      const subs = (r.subs || []).filter(Boolean);
      if (r.rankNote) subs.push(r.rankNote);
      if (subs.length) el.append(h('p.kvs', subs.join(' · ')));
      return el;
    };
    const top = b.top || b.rows.length;
    const dl = h('dl.pn-kv', b.rows.slice(0, top).map(row));
    if (b.rows.length <= top) return dl;
    return h('div', dl, h('details.pn-rest', h('summary', `${b.restLabel || '나머지'} ${b.rows.length - top}개 펼치기`), h('dl.pn-kv', b.rows.slice(top).map(row))));
  }

  bExt(b) {
    const hi = b.stage && /위험/.test(b.stage);
    return h('div.pn-ext', h('div', h('span.kicker', '소멸위험지수'), isNum(b.index) ? h('span.num.mid', b.index.toFixed(2)) : na()),
      h('span.stage' + (hi ? '.is-ju' : ''), b.stage || '자료 없음'), h('p', b.formula));
  }

  bChips(items) {
    return h('ul.pn-chips', items.map((it) => h('li', this.goBtn('chip', it.go, it.kind && KIND_ICON[it.kind] ? iconEl(KIND_ICON[it.kind], 14) : null, h('b', it.label), it.small ? h('small', it.small) : null))));
  }

  bKinds(b) {
    const one = (g) => {
      const K = KINDS[g.kind] || { label: g.kind };
      const cap = g.kind === 'station' ? 6 : 4;
      const box = h('div.pn-kind', h('h4', iconEl(KIND_ICON[g.kind] || 'gold', 16), h('span', K.label), h('small', String(g.n))));
      const body = h('div.pn-kindbody', this.bChips(g.items.slice(0, cap)));
      if (g.items.length > cap) body.append(h('details.pn-rest', h('summary', `외 ${g.items.length - cap}곳 더 보기`), this.bChips(g.items.slice(cap))));
      box.append(body);
      return box;
    };
    const top = 5;
    const wrap = h('div.pn-kinds', b.groups.slice(0, top).map(one));
    if (b.groups.length > top) wrap.append(h('details.pn-rest', h('summary', `다른 종류 ${b.groups.length - top}가지 더 보기`), b.groups.slice(top).map(one)));
    return wrap;
  }

  bList(b) {
    return h('ul.pn-list', b.items.map((it) => h('li' + (it.here ? '.here' : ''), it.tag ? h('span.tag', it.tag) : null, it.strong ? h('b', it.strong) : null, it.label ? h('span.ll', it.label) : null,
      it.text ? h('small', it.text) : null, it.go ? this.goBtn('pn-link', it.go, `${it.go.label} 장`) : null)));
  }

  bTable(b) {
    const nf = b.numFrom ?? 99;
    const t = h('table.pn-table', h('thead', h('tr', b.head.map((x, k) => h('th' + (k >= nf ? '.n' : ''), { scope: 'col' }, x)))),
      h('tbody', b.rows.map((r, i) => h('tr', r.map((c, k) => (k === 0
        ? h('th', { scope: 'row' }, b.go && b.go[i] ? this.goBtn('pn-rowbtn', b.go[i], String(c)) : String(c))
        : h('td' + (k >= nf ? '.n' : '') + (c === '자료 없음' ? '.na' : ''), String(c))))))));
    return b.scroll ? h('div.pn-scroll', { tabindex: '0', role: 'region', 'aria-label': '표 (가로로 넘김)' }, t) : t;
  }

  bSort(b) {
    const wrap = h('div.pn-sort');
    const bar = h('div.pn-tabbar', { role: 'group', 'aria-label': '정렬 기준' });
    const list = h('ol.pn-members'), rest = h('ol.pn-members.cont'), sum = h('summary', ''), more = h('details.pn-rest', sum, rest);
    const get = (r, key) => (key.startsWith('y:') ? r.yields[key.slice(2)] : r[key]);
    const draw = () => {
      const key = b.sorts.some(([k]) => k === this.sort) ? this.sort : 'pop';
      clear(bar);
      for (const [k, label] of b.sorts) bar.append(h('button', { type: 'button', 'aria-pressed': String(k === key), onclick: () => { this.sort = k; draw(); } }, label));
      const asc = key === 'ext'; // 소멸위험은 지수가 낮은(위험한) 곳부터
      const rows = b.rows.slice().sort((x, y) => { const a = get(x, key), c = get(y, key); if (a == null) return 1; if (c == null) return -1; return asc ? a - c : c - a; });
      clear(list); clear(rest);
      rows.forEach((r, idx) => {
        const v = get(r, key);
        let cell;
        if (v == null) cell = na();
        else if (key === 'pop') cell = h('span', fmtInt(v), h('small', '명'));
        else if (key === 'ext') cell = h('span', v.toFixed(2));
        else cell = h('span', fmtWon(v), key.startsWith('y:') && r.partial[key.slice(2)] ? h('sup', '*') : null);
        (idx < 10 ? list : rest).append(h('li', this.goBtn('pn-member', { city: r.id }, h('b', r.name), h('span.lead', { 'aria-hidden': 'true' }), cell)));
      });
      more.hidden = rows.length <= 10;
      sum.textContent = `나머지 ${Math.max(0, rows.length - 10)}곳 펼치기`;
    };
    draw();
    wrap.append(bar, list, more);
    return wrap;
  }

  pyramidTable(b) {
    const lab = (k) => (k === 20 ? '100세 이상' : `${k * 5}–${k * 5 + 4}세`);
    return h('table.sr-only', h('caption', '나이 계급별 남녀 인구'), h('thead', h('tr', h('th', { scope: 'col' }, '나이'), h('th', { scope: 'col' }, '남'), h('th', { scope: 'col' }, '여'))),
      h('tbody', b.male.map((m, k) => h('tr', h('th', { scope: 'row' }, lab(k)), h('td', isNum(m) ? fmtInt(m) : '자료 없음'), h('td', isNum(b.female[k]) ? fmtInt(b.female[k]) : '자료 없음')))));
  }

  // ---------- 층 항목·교역로 (가벼운 장) ----------
  renderSmall(v) {
    const root = h('article.pn-small.pn-' + v.kind);
    const K = v.itemKind ? KINDS[v.itemKind] : null;
    const grp = K ? K.layer : 'trade';
    const badge = h('p.pn-kindbadge.g-' + grp, iconEl(v.kind === 'route' ? 'export_hub' : KIND_ICON[v.itemKind] || 'gold', 16), v.kind === 'route' ? '교역로' : (K ? K.label : '항목') + (v.hsr ? ' · 고속철도 정차' : ''));
    const head = h('header.pn-shead', badge, h('h2.pn-stitle', { tabindex: '-1' }, v.title), h('p.pn-sub', v.sub || ''));
    if (v.states) head.append(h('p.pn-actions', v.states.map((x) => this.goBtn('btn', x.go, `${x.label} 장`))));
    root.append(head);
    // 핵심 수치
    const key = h('div.pn-key', h('span.kicker', v.key.label));
    if (v.key.value) key.append(val(v.key.value, true)); else if (v.key.text) key.append(h('span.num.mid', v.key.text)); else key.append(h('span.na', '값 없음'));
    if (v.key.small) key.append(h('small', v.key.small));
    root.append(key);
    if (v.dir && isNum(v.dir.ab) && isNum(v.dir.ba)) {
      const tot = v.dir.ab + v.dir.ba || 1;
      root.append(h('div.pn-dir', { role: 'img', 'aria-label': `${v.dir.a}에서 ${v.dir.b}로 ${fmtInt(v.dir.ab)}톤, 반대로 ${fmtInt(v.dir.ba)}톤` },
        h('i.a', { style: { width: (100 * v.dir.ab) / tot + '%' } }), h('i.b', { style: { width: (100 * v.dir.ba) / tot + '%' } })),
      h('p.pn-dirlab', h('span', `${v.dir.a} → ${v.dir.b}`), h('span', `${v.dir.b} → ${v.dir.a}`)));
    }
    for (const w of v.warns || []) root.append(h('p.pn-warn', w));
    if (v.meta && v.meta.length) root.append(this.bKV({ leader: true, rows: v.meta }));
    add(root, this.blocks(v.body));
    if (v.cityGo) root.append(h('p.pn-actions', this.goBtn('btn', { city: v.cityGo.city }, v.cityGo.label, iconEl('arrow', 14))));
    for (const sec of v.sections || []) root.append(this.section(sec));
    return root;
  }
}
