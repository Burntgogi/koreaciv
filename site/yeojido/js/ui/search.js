// 찾기 (/) — 시도 16 · 고을 167(온 이름·소속 시군구 이름으로도) · 지도 층 항목 · 국립공원. 고르면 그 장을 열고 날아간다.

import { h, clear } from '../dom.js';
import { iconEl } from '../icons.js';
import { fmtInt } from '../fmt.js';
import { openModal, closeModal } from './modal.js';
import { KINDS } from '../config.js';

const SEARCH_KINDS = ['national_park', 'world_heritage', 'knowledge', 'nuclear', 'industrial_national', 'dam', 'airport', 'trade_port', 'station', 'power_coal', 'power_gas', 'power_hydro', 'gi', 'port', 'mine'];
const BADGE = { world_heritage: '세계유산', national_park: '국립공원', knowledge: '지식', nuclear: '원전', industrial_national: '산단', dam: '댐', airport: '공항', trade_port: '무역항', station: '역', power_coal: '발전소', power_gas: '발전소', power_hydro: '발전소', gi: '특산', port: '어항', mine: '광산' };
const FIRST = ['서울', '부산', '전주시', '울산', '강릉시', '제주시', '울릉군', '철원군'];
const norm = (s) => String(s || '').replace(/\s+/g, '').toLowerCase();

export class Search {
  constructor(app) {
    this.app = app;
    this.items = []; this.k = 0; this.layerItems = [];
    this.input = h('input', { type: 'search', id: 'search-input', role: 'combobox', 'aria-expanded': 'true', 'aria-controls': 'search-list', 'aria-autocomplete': 'list', autocomplete: 'off', spellcheck: 'false', placeholder: '고을 · 시도 · 국립공원 · 세계유산 · 항만 …', 'aria-label': '찾기' });
    this.list = h('ul#search-list', { role: 'listbox', 'aria-label': '찾은 것' });
    this.status = h('p.sr-only', { role: 'status' });
    this.el = h('div.modal.search', { hidden: true, 'aria-label': '찾기' },
      h('div.sheet', h('div.field', iconEl('search', 20), this.input, h('button.x', { type: 'button', 'aria-label': '찾기 닫기', onclick: () => this.close() }, iconEl('close', 18))),
        this.list, this.status,
        h('p.hint', h('kbd', '↑'), h('kbd', '↓'), ' 고르기 ', h('kbd', 'Enter'), ' 열기 ', h('kbd', 'Esc'), ' 닫기')));
    this.el.addEventListener('pointerdown', (e) => { if (e.target === this.el) this.close(); });
    this.input.addEventListener('input', () => this.update());
    this.input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { this.k = Math.min(this.items.length - 1, this.k + 1); this.paint(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { this.k = Math.max(0, this.k - 1); this.paint(); e.preventDefault(); }
      else if (e.key === 'Enter') { e.preventDefault(); this.go(this.items[this.k]); }
    });
    document.getElementById('modal-root').append(this.el);
    const D = app.D, W = D.world;
    // 고을: 이름, 온 이름, 소속 시군구 이름
    this.base = [
      ...D.states.map((s) => ({ type: 'state', id: s.code, name: s.name, badge: '시도', where: `고을 ${s.cityIds.length}곳`, keys: [norm(s.name), norm(s.short)], pop: s.pop ?? 0 })),
      ...D.cities.map((c) => {
        const st = D.stateByCode.get(c.sido), subs = c.sgg.map((code) => (W.counties[W.countyIndex.get(code)] || {}).name).filter(Boolean);
        return { type: 'city', id: c.id, name: c.name, badge: '고을', where: c.full !== c.name ? c.full : st ? st.name : '', keys: [norm(c.name), norm(c.full), ...subs.map(norm)], subs, pop: c.pop ?? 0 };
      }),
    ];
    app.on('layersloaded', (L) => this.addLayers(L));
    if (D.layers) this.addLayers(D.layers);
  }

  addLayers(L) {
    const seen = new Set();
    this.layerItems = [];
    for (const it of L.items) {
      if (!SEARCH_KINDS.includes(it.kind) || !KINDS[it.kind]) continue;
      const key = it.kind + it.name; // 세계유산은 구성 유산마다 항목이 있어 이름으로 하나만
      if (seen.has(key)) continue;
      seen.add(key);
      this.layerItems.push({ type: 'item', it, name: it.name, badge: BADGE[it.kind] || KINDS[it.kind].label, where: it.place || '위치 없음', keys: [norm(it.name)], pop: -1 });
    }
    if (!this.el.hidden) this.update();
  }

  open() {
    this.input.value = '';
    this.update();
    openModal(this.el, { initial: this.input });
  }
  close() { closeModal(this.el); }

  update() {
    const q = norm(this.input.value);
    const all = [...this.base, ...this.layerItems];
    let res;
    if (!q) res = FIRST.map((n) => this.base.find((x) => x.type === 'city' && x.name === n)).filter(Boolean);
    else {
      res = [];
      for (const x of all) {
        let sc = 9, via = '';
        x.keys.forEach((k, i) => {
          const s = k === q ? 0 : k.startsWith(q) ? 1 : k.includes(q) ? 3 : 9;
          const adj = s + (i > 1 ? 1.5 : i ? 0.5 : 0);
          if (s < 9 && adj < sc) { sc = adj; via = i > 1 && x.subs ? x.subs[i - 2] : ''; }
        });
        if (sc < 9) res.push({ ...x, sc, via });
      }
      res.sort((a, b) => a.sc - b.sc || b.pop - a.pop).splice(12);
    }
    this.items = res; this.k = 0;
    this.status.textContent = q ? (res.length ? `${res.length}건` : '찾는 이름이 없습니다') : '';
    this.paint();
  }

  paint() {
    clear(this.list);
    if (!this.items.length) { this.list.append(h('li.none', { role: 'presentation' }, '찾는 이름이 없습니다')); this.input.removeAttribute('aria-activedescendant'); return; }
    if (!norm(this.input.value)) this.list.append(h('li.cap', { role: 'presentation' }, '먼저 가 볼 곳'));
    this.items.forEach((x, k) => {
      const li = h('li', { role: 'option', id: 'search-opt-' + k, 'aria-selected': k === this.k ? 'true' : 'false', onclick: () => this.go(x), onpointermove: () => { if (this.k !== k) { this.k = k; this.mark(); } } },
        h('span.badge.b-' + x.type, x.badge), h('b', x.name), h('span.where', x.via ? `${x.via} · ${x.where}` : x.where),
        x.type !== 'item' && x.pop ? h('span.pop', fmtInt(x.pop), h('small', '명')) : null);
      this.list.append(li);
    });
    this.input.setAttribute('aria-activedescendant', 'search-opt-' + this.k);
  }
  mark() {
    [...this.list.querySelectorAll('[role=option]')].forEach((li, k) => li.setAttribute('aria-selected', k === this.k ? 'true' : 'false'));
    this.input.setAttribute('aria-activedescendant', 'search-opt-' + this.k);
  }

  go(x) {
    if (!x) return;
    closeModal(this.el, false);
    const a = this.app;
    if (x.type === 'item') a.selectItem(x.it, { fly: true });
    else if (x.type === 'city') a.selectCity(x.id, { fly: true });
    else a.selectState(x.id, { fly: true });
    const p = document.getElementById('panel');
    requestAnimationFrame(() => { const t = (!p.hidden && (p.querySelector('h2, [tabindex], button') || p)) || a.canvas; if (t === p && !p.hasAttribute('tabindex')) p.setAttribute('tabindex', '-1'); t.focus({ preventScroll: true }); });
  }
}
