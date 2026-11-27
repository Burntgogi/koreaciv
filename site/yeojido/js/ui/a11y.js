// 글로 읽는 지도 — 캔버스에 닿지 못하는 화면 낭독기·글쇠 사용자를 위한 목록 (#places).
// 지도 한 줄 설명, 켠 렌즈의 높은·낮은 고을 다섯씩, 시도 16 → 고을 167 단추. 고른 것이 바뀌면 #live 로 알린다.

import { h, clear } from '../dom.js';
import { fmtInt, lensValueUnit, fmtWhen } from '../fmt.js';
import { lensValues, lensIsContinuous } from '../adapter.js';

export class Places {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('places');
    this.lensBox = h('section', { 'aria-live': 'polite' });
    this.build();
    // 건너뛰기 링크: 주소(#places)를 바꾸지 않고 목록의 제목으로 초점만 옮긴다 (해시는 지도 상태가 쓴다)
    const skip = document.querySelector('a.skip');
    if (skip) skip.addEventListener('click', (e) => { e.preventDefault(); const t = document.getElementById('places-title'); if (t) t.focus(); });
    this.el.addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.stopPropagation(); app.canvas.focus(); } });
    app.on('lens', () => this.update());
    app.on('select', (sel) => this.announce(sel));
  }

  focusPanel() {
    requestAnimationFrame(() => {
      const p = document.getElementById('panel');
      if (p.hidden) return;
      const t = p.querySelector('h2') || p;
      if (!t.hasAttribute('tabindex')) t.setAttribute('tabindex', '-1');
      t.focus({ preventScroll: true });
    });
  }

  build() {
    const a = this.app, D = a.D;
    const cityBtn = (c) => h('button', { type: 'button', onclick: () => { a.selectCity(c.id, { fly: true }); this.focusPanel(); } }, c.name, c.pop != null ? h('small', ` ${fmtInt(c.pop)}명`) : h('small', ' 인구 자료 없음'));
    const states = D.states.map((s) => {
      const cities = s.cityIds.map((id) => D.cityById.get(id)).filter(Boolean).sort((x, y) => (y.pop || 0) - (x.pop || 0));
      return h('li', h('h3', h('button', { type: 'button', onclick: () => { a.selectState(s.code, { fly: true }); this.focusPanel(); } }, s.name), s.pop != null ? h('small', ` ${fmtInt(s.pop)}명 · 고을 ${cities.length}곳`) : null),
        h('ul.cities', cities.map((c) => h('li', cityBtn(c)))));
    });
    clear(this.el).append(
      h('h2', { tabindex: '-1', id: 'places-title' }, '고을 목록 — 지도를 글로 읽기'),
      h('p', `대한민국을 넓이 ${D.world.hexKm2 ?? '–'} km² 육각 칸 ${fmtInt(D.world.landCells.length)}개로 나눈 지도입니다. 시도 ${D.states.length}곳, 고을 ${D.cities.length}곳이 있고, 렌즈 ${D.lenses.list.length}개로 통계를 칸에 찍어 볼 수 있습니다. 기준 시점은 ${fmtWhen(D.vintage) || '자료 없음'}입니다. 아래 단추를 누르면 그 고을이나 시도의 장이 열립니다.`),
      h('p', h('button', { type: 'button', onclick: () => { a.showNation(); this.focusPanel(); } }, '전국 장 열기'), ' ', h('button', { type: 'button', onclick: () => a.search.open() }, '이름으로 찾기'), ' ', h('button', { type: 'button', onclick: () => a.almanac.open() }, '연감(규칙·출처) 열기'), ' ', h('button', { type: 'button', onclick: () => a.canvas.focus() }, '지도로 돌아가기')),
      this.lensBox,
      h('h2', '시도와 고을'),
      h('ul.states', states));
    this.update();
  }

  update() {
    const a = this.app, D = a.D, lens = a.lens, box = clear(this.lensBox);
    box.append(h('h2', '렌즈'));
    if (!lens) { box.append(h('p', '지금은 렌즈를 켜지 않았습니다 (지형). 렌즈는 화면 왼쪽 갈피에서 고르거나 L 글쇠로 넘깁니다.')); return; }
    box.append(h('p', `켠 렌즈: ${lens.name}${lens.unit ? ' (' + lens.unit + ')' : ''}. ${lens.description || ''} 기준 ${lens.vintage || '자료 없음'}. 출처 ${lens.source || '자료 없음'}.`));
    const vals = lensValues(lens, D.world);
    const rows = D.cities.map((c) => ({ c, v: vals[c.cell] })).filter((r) => r.v != null);
    const none = D.cities.length - rows.length;
    const tbl = (cap, list) => h('table', h('caption', cap), h('thead', h('tr', h('th', { scope: 'col' }, '고을'), h('th', { scope: 'col' }, '값'))),
      h('tbody', list.map((r) => h('tr', h('th', { scope: 'row' }, h('button', { type: 'button', onclick: () => { a.selectCity(r.c.id, { fly: true }); this.focusPanel(); } }, r.c.name)), h('td', lensValueUnit(r.v, lens))))));
    if (lensIsContinuous(lens) && rows.length) {
      rows.sort((x, y) => y.v - x.v);
      box.append(tbl('값이 높은 고을 다섯 (고을 중심 칸의 값)', rows.slice(0, 5)), tbl('값이 낮은 고을 다섯', rows.slice(-5).reverse()));
    } else if (rows.length) {
      const cnt = new Map();
      for (const r of rows) { const t = lensValueUnit(r.v, lens); cnt.set(t, (cnt.get(t) || 0) + 1); }
      box.append(h('table', h('caption', '고을 중심 칸의 값으로 센 고을 수'), h('tbody', [...cnt.entries()].sort((x, y) => y[1] - x[1]).map(([t, n]) => h('tr', h('th', { scope: 'row' }, t), h('td', `${n}곳`))))));
    }
    box.append(h('p', none ? `중심 칸에 값이 없는 고을 ${none}곳은 자료 없음입니다.` : '모든 고을의 중심 칸에 값이 있습니다.'));
  }

  announce(sel) {
    const a = this.app, D = a.D;
    let msg = '';
    if (!sel || !sel.type) msg = this._had ? '장을 닫았습니다.' : '';
    else if (sel.type === 'city') { const c = D.cityById.get(sel.id); msg = c ? `${c.name} 고을 장을 열었습니다.` : ''; }
    else if (sel.type === 'state') { const s = D.stateByCode.get(sel.id); msg = s ? `${s.name} 시도 장을 열었습니다.` : ''; }
    else if (sel.type === 'item') msg = a.selItem ? `${a.selItem.name} 항목 장을 열었습니다.` : '';
    else if (sel.type === 'route') { const r = a.selRoute; const n = (c) => (D.stateByCode.get(c) || {}).short || c; msg = r ? `${n(r.a)}–${n(r.b)} 교역로 장을 열었습니다.` : ''; }
    else if (sel.type === 'nation') msg = '전국 장을 열었습니다.';
    this._had = !!(sel && sel.type);
    if (msg && msg !== this._last) a.say(msg);
    this._last = msg;
  }
}
