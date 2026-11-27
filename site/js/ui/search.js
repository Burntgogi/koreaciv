// 검색 (/): 도시·시도 이름, 그리고 국립공원·세계유산·발전소·국가산업단지·무역항·공항·지리적표시 이름으로 찾아 이동
import { KINDS } from '../render/layers.js';

const SEARCH_KINDS = ['national_park', 'world_heritage', 'knowledge', 'nuclear', 'industrial_national', 'dam', 'airport', 'trade_port', 'power_coal', 'power_gas', 'power_hydro', 'gi'];

export class Search {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('search');
    this.el.innerHTML = `<div class="box"><input type="search" placeholder="도시·시도 이름 (예: 수원, 강원, 울릉)" aria-label="도시·시도 찾기"><ul></ul></div>`;
    this.input = this.el.querySelector('input');
    this.list = this.el.querySelector('ul');
    this.items = [];
    this.layerItems = [];
    this.k = 0;
    this.input.addEventListener('input', () => this.update());
    this.input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { this.k = Math.min(this.items.length - 1, this.k + 1); this.paint(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { this.k = Math.max(0, this.k - 1); this.paint(); e.preventDefault(); }
      else if (e.key === 'Enter') this.go(this.items[this.k]);
      else if (e.key === 'Escape') this.close();
    });
    this.el.addEventListener('click', (e) => {
      if (e.target === this.el) return this.close();
      const li = e.target.closest('li[data-k]');
      if (li) this.go(this.items[Number(li.dataset.k)]);
    });
  }

  addLayers(L, R) {
    const seen = new Set();
    this.layerItems = []; // 층을 다시 불러오면 (감사 08 다시 시도) 처음부터
    const all = [...L.wonders.items, ...L.resources.items, ...L.infrastructure.items, ...L.resources.unplaced, ...L.infrastructure.unplaced];
    for (const it of all) {
      if (!SEARCH_KINDS.includes(it.kind)) continue;
      const key = it.kind + it.name; // 세계유산은 구성 유산마다 항목이 있어 이름으로 하나만
      if (seen.has(key)) continue;
      seen.add(key);
      this.layerItems.push({ type: 'item', it, name: it.name, alt: `${KINDS[it.kind].label}${it.place ? ' · ' + it.place : ' · 위치 없음'}`, pop: -1 });
    }
    this.input.placeholder = '도시·시도, 국립공원·세계유산·발전소·산업단지·항만·공항·특산 (예: 수원, 설악산, 당진, 광양항, 보성녹차)';
  }

  open() {
    this.el.hidden = false;
    this.input.value = '';
    this.update();
    this.input.focus();
  }

  close() { this.el.hidden = true; }

  update() {
    const q = this.input.value.trim().replace(/\s+/g, '');
    const a = this.app;
    const all = [
      ...a.states.map((s) => ({ type: 'state', s, name: s.name, alt: s.short, pop: s.population })),
      ...a.cities.map((c) => ({ type: 'city', c, name: c.name, alt: c.full, pop: c.population })),
      ...this.layerItems,
    ];
    let res;
    if (!q) {
      // 빈 입력: 인구 상위 도시 8곳 + 데이터 기준 시점 6선 (7b #20, 빌드가 극값 규칙으로 고름)
      const P = (a.nation.presets || {}).items || [];
      res = [...all.filter((x) => x.type === 'city').slice(0, 8),
        ...P.map((p, k) => ({ type: 'preset', p, name: p.title, alt: `${p.metric}${p.lens && a.lensById.get(p.lens) ? ' · ' + a.lensById.get(p.lens).name + ' 렌즈' : ''}`, rule: p.rule, first: k === 0 }))];
    }
    else {
      res = all
        .map((x) => {
          const n = x.name.replace(/\s+/g, ''), f = x.alt.replace(/\s+/g, '');
          const sc = n === q ? 0 : n.startsWith(q) ? 1 : f.startsWith(q) ? 2 : n.includes(q) ? 3 : f.includes(q) ? 4 : 9;
          return { ...x, sc };
        })
        .filter((x) => x.sc < 9)
        .sort((x, y) => x.sc - y.sc || y.pop - x.pop)
        .slice(0, 12);
    }
    this.items = res;
    this.k = 0;
    this.paint();
  }

  // 이름·보조 설명은 텍스트 노드로 넣는다 (자료 문자열을 HTML 로 해석하지 않음, 감사 07)
  paint() {
    this.list.replaceChildren();
    if (!this.items.length) {
      const li = document.createElement('li');
      li.className = 'none';
      li.textContent = '찾는 이름이 없습니다';
      this.list.appendChild(li);
      return;
    }
    this.items.forEach((x, k) => {
      if (x.type === 'preset' && x.first) {
        const h = document.createElement('li');
        h.className = 'sep';
        h.textContent = '데이터 기준 시점 6선 (자동 선정)';
        this.list.appendChild(h);
      }
      const li = document.createElement('li');
      li.dataset.k = String(k);
      if (k === this.k) li.className = 'on';
      if (x.type === 'preset') {
        li.classList.add('preset');
        li.setAttribute('aria-label', `${x.name}, ${x.alt}, 선정 규칙 ${x.rule}`);
        const b = document.createElement('b'), sp = document.createElement('span'), sm = document.createElement('small');
        b.textContent = x.name;
        sp.textContent = x.alt;
        sm.textContent = '규칙: ' + x.rule;
        li.append(b, sp, sm);
        this.list.appendChild(li);
        return;
      }
      const b = document.createElement('b'), sp = document.createElement('span'), sm = document.createElement('small');
      b.textContent = x.name;
      sp.textContent = x.type === 'state' ? '시도' : x.alt;
      sm.textContent = x.type === 'item' ? '' : x.pop.toLocaleString('ko-KR') + '명';
      li.append(b, sp, sm);
      this.list.appendChild(li);
    });
  }

  go(x) {
    if (!x) return;
    this.close();
    if (x.type === 'preset') return this.app.applyPreset(x.p.id);
    if (x.type === 'item') this.app.selectItem(x.it, true);
    else if (x.type === 'city') this.app.selectCity(x.c.id, true);
    else this.app.selectState(x.s.code, true);
    this.app.panel.focus();
  }
}
