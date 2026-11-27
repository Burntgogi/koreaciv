// 층 조작(오른쪽 여백의 다섯 단추 + 세부 서랍)과 지도표 ↔ 색인도(도판 오른쪽 아래).
// 좁은 화면에서는 둥근 단추 하나가 같은 서랍을 연다.

import { h, clear } from '../dom.js';
import { LAYER_GROUPS, KINDS, NARROW } from '../config.js';
import { iconEl, KIND_ICON } from '../icons.js';
import { drawBadge } from '../map/layers.js';

// 세부 -> 견본으로 보일 종류
const SUB_KIND = { national_park: 'national_park', world_heritage: 'world_heritage', heritage_cluster: 'heritage_cluster', knowledge: 'knowledge',
  power: 'nuclear', dam: 'dam', mine: 'mine', industrial: 'industrial_national', industry: 'ind_c30', fishport: 'port', farm: 'rice',
  station: 'station', trade_port: 'trade_port', airport: 'airport', export_hub: 'export_hub' };
const GROUP_KIND = { wonders: 'world_heritage', resources: 'industrial_national', infra: 'trade_port', trade: 'export_hub' };

// 배지 견본 (캔버스 한 장)
function badge(kind, size = 20) {
  const k = Math.min(2, window.devicePixelRatio || 1), pad = 3;
  const cv = h('canvas.badge', { 'aria-hidden': 'true', width: Math.round((size + pad * 2) * k), height: Math.round((size + pad * 2) * k), style: { width: size + pad * 2 + 'px', height: size + pad * 2 + 'px' } });
  const ctx = cv.getContext('2d');
  ctx.scale(k, k);
  drawBadge(ctx, kind, size / 2 + pad, size / 2 + pad, size);
  return cv;
}

export class LayerCtl {
  constructor(app) {
    this.app = app;
    this.host = document.getElementById('layers');
    this.key = document.getElementById('key');
    this.open = false;
    this.mode = '';
    this.buildCtl();
    this.buildKey();
    app.on('layers', () => this.render());
    app.on('layersloaded', (L) => {
      // 층 자료에 항목이 있는 세부만 둔다 (그 판에 없는 층 — 공개판의 광산·한우 — 은 서랍에서 숨긴다)
      const kinds = new Set();
      const lists = L && Array.isArray(L.items) ? [L.items] : Object.values(L || {}).map((x) => (x && Array.isArray(x.items) ? x.items : []));
      for (const lst of lists) for (const it of lst) if (it && it.kind) kinds.add(it.kind);
      this.presentSubs = new Set([...kinds].map((k) => (KINDS[k] || {}).sub).filter(Boolean));
      this.render(); this.drawLocator();
    });
    app.on('view', () => this.onView());
    app.on('resize', () => { this.drawLocator(); this.onView(); });
    document.addEventListener('pointerdown', (e) => { if (this.open && !this.host.contains(e.target)) this.setOpen(false); });
  }

  // ---------- 층 조작 ----------
  buildCtl() {
    const app = this.app;
    this.groupBtns = new Map(); this.groupChecks = new Map(); this.subChecks = new Map();
    const col = h('div.lcol');
    for (const g of LAYER_GROUPS) {
      const b = h('button.lg', { type: 'button', 'aria-pressed': 'false', title: `${g.name} 층 켜고 끄기`, onclick: () => app.toggleLayerGroup(g.id) },
        g.id === 'frontier' ? h('span.fr', { 'aria-hidden': 'true' }) : badge(GROUP_KIND[g.id], 24), h('span', g.name));
      this.groupBtns.set(g.id, b);
      col.append(b);
    }
    this.more = h('button.lmore', { type: 'button', 'aria-expanded': 'false', 'aria-controls': 'layerdrawer', onclick: () => this.setOpen(!this.open) }, h('span', '세부'), iconEl('caret', 14));
    col.append(this.more);
    // 좁은 화면의 둥근 단추
    this.fab = h('button.lfab', { type: 'button', 'aria-label': '지도 층', 'aria-expanded': 'false', 'aria-controls': 'layerdrawer', onclick: () => this.setOpen(!this.open) }, iconEl('layers', 22));
    const dr = this.drawer = h('div#layerdrawer.ldrawer', { hidden: true, role: 'group', 'aria-label': '지도 층 세부' });
    dr.append(h('div.lhead', h('b', '지도 층'), h('button.x', { type: 'button', 'aria-label': '닫기', onclick: () => { this.setOpen(false); (this.fab.offsetParent ? this.fab : this.more).focus(); } }, iconEl('close', 18))));
    for (const g of LAYER_GROUPS) {
      const gc = h('input', { type: 'checkbox', id: `lg-${g.id}`, onchange: (e) => app.toggleLayerGroup(g.id, e.target.checked) });
      this.groupChecks.set(g.id, gc);
      const fs = h('fieldset', h('legend', h('label', { for: `lg-${g.id}` }, gc, h('b', g.name))));
      const ul = h('ul');
      for (const [sub, name] of g.subs) {
        if (g.subs.length === 1 && sub === g.id) continue;
        const c = h('input', { type: 'checkbox', id: `ls-${sub}`, onchange: (e) => app.toggleSub(sub, e.target.checked) });
        const li = h('li', h('label', { for: `ls-${sub}` }, c, SUB_KIND[sub] ? badge(SUB_KIND[sub], 16) : h('span.ln.ln-' + sub, { 'aria-hidden': 'true' }), h('span', name)));
        this.subChecks.set(sub, { c, group: g.id, li, item: !!SUB_KIND[sub] });
        ul.append(li);
      }
      if (ul.children.length) fs.append(ul);
      dr.append(fs);
    }
    this.note = h('p.lnote', '아이콘은 배율에 따라 늘어난다. 찾기와 장의 목록에서는 언제나 전부 닿는다.');
    dr.append(this.note);
    clear(this.host).append(col, this.fab, dr);
    this.render();
  }

  setOpen(on) {
    this.open = on;
    this.drawer.hidden = !on;
    this.more.setAttribute('aria-expanded', String(on));
    this.fab.setAttribute('aria-expanded', String(on));
    this.host.classList.toggle('is-open', on);
    if (on) { const f = this.drawer.querySelector('input'); if (f) f.focus({ preventScroll: true }); }
  }
  closeTransient() { if (!this.open) return false; this.setOpen(false); (this.fab.offsetParent ? this.fab : this.more).focus({ preventScroll: true }); return true; }

  render() {
    const app = this.app, loaded = !!app.layerMap;
    for (const g of LAYER_GROUPS) {
      const on = !!app.layerOn[g.id];
      const b = this.groupBtns.get(g.id);
      b.setAttribute('aria-pressed', String(on));
      this.groupChecks.get(g.id).checked = on;
    }
    for (const [sub, { c, group, li, item }] of this.subChecks) {
      c.checked = !app.subOff.has(sub); c.disabled = !app.layerOn[group];
      li.hidden = !!(this.presentSubs && item && !this.presentSubs.has(sub));
    }
    this.host.classList.toggle('is-loading', !loaded);
    const n = LAYER_GROUPS.filter((g) => app.layerOn[g.id]).length;
    this.fab.dataset.n = n;
    this.renderKeyLayers();
  }

  // ---------- 지도표 ↔ 색인도 ----------
  buildKey() {
    const sym = (cls) => h('i.sym.' + cls, { 'aria-hidden': 'true' });
    this.keyLayers = h('ul.klayers');
    this.legend = h('div.kkey',
      h('b.kt', '지도표'),
      h('ul',
        h('li', sym('cap'), '수도'),
        h('li', sym('seat'), '광역시 · 도청 소재지'),
        h('li', sym('town'), '시 · 군'),
        h('li', sym('ridge'), '산줄기 ', h('small', '계산한 분수계')),
        h('li', sym('river'), '물줄기'),
        h('li', sym('sido'), '시도 경계'),
        h('li', sym('dmz'), '휴전선')),
      this.keyLayers);
    this.locCv = h('canvas', { width: 116, height: 140 });
    this.locView = h('i.view');
    this.loc = h('div.kloc', { 'aria-hidden': 'true', title: '색인도 — 누르거나 끌어 옮긴다' }, this.locCv, this.locView);
    clear(this.key).append(this.legend, this.loc);
    this.key.setAttribute('aria-label', '지도표');
    const move = (e) => {
      const r = this.locCv.getBoundingClientRect(), L = this.locGeom;
      if (!L) return;
      const cam = this.app.cam;
      cam.anim = null;
      cam.x = L.x0 + (e.clientX - r.left) / L.k; cam.y = L.y0 + (e.clientY - r.top) / L.k;
      cam.clamp();
      this.app.requestDraw();
    };
    this.loc.addEventListener('pointerdown', (e) => { this.loc.setPointerCapture(e.pointerId); this.dragging = true; move(e); });
    this.loc.addEventListener('pointermove', (e) => { if (this.dragging) move(e); });
    const up = () => { this.dragging = false; };
    this.loc.addEventListener('pointerup', up);
    this.loc.addEventListener('pointercancel', up);
    this.drawLocator();
    this.renderKeyLayers();
  }

  renderKeyLayers() {
    if (!this.keyLayers) return;
    clear(this.keyLayers);
    for (const g of LAYER_GROUPS) {
      if (!this.app.layerOn[g.id]) continue;
      this.keyLayers.append(h('li', g.id === 'frontier' ? h('i.sym.front', { 'aria-hidden': 'true' }) : badge(GROUP_KIND[g.id], 14), g.name));
    }
  }

  // 색인도: 나라 뭍의 먹 실루엣을 한 번 그려 둔다
  drawLocator() {
    const app = this.app, G = app.grid, W = app.D.world, f = app.focus;
    const cw = 116, ch = 140, k = Math.min(cw / (f.x1 - f.x0), ch / (f.y1 - f.y0)), dpr = Math.min(2, window.devicePixelRatio || 1);
    const x0 = (f.x0 + f.x1) / 2 - cw / 2 / k, y0 = (f.y0 + f.y1) / 2 - ch / 2 / k;
    this.locGeom = { k, x0, y0 };
    const cv = this.locCv;
    cv.width = cw * dpr; cv.height = ch * dpr;
    const ctx = cv.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, cw, ch);
    const r = Math.max(0.9, G.R * k * 1.05);
    ctx.fillStyle = 'rgb(224,215,195)';
    for (let i = 0; i < G.n; i++) { if (W.foreign[i] !== 1) continue; const x = (G.cx[i] - x0) * k, y = (G.cy[i] - y0) * k; if (x < -2 || y < -2 || x > cw + 2 || y > ch + 2) continue; ctx.fillRect(x - r, y - r, 2 * r, 2 * r); }
    ctx.fillStyle = 'rgb(128,119,104)';
    for (let i = 0; i < G.n; i++) { if (W.owner[i] < 0) continue; const x = (G.cx[i] - x0) * k, y = (G.cy[i] - y0) * k; ctx.fillRect(x - r, y - r, 2 * r, 2 * r); }
    this._vk = '';
  }

  onView() {
    const cam = this.app.cam;
    const mode = cam.z >= 1.8 ? 'loc' : 'key';
    if (mode !== this.mode) { this.mode = mode; this.key.dataset.mode = mode; }
    if (mode !== 'loc' || !this.locGeom) return;
    const v = cam.view(), L = this.locGeom;
    const x = Math.max(0, (v.x0 - L.x0) * L.k), y = Math.max(0, (v.y0 - L.y0) * L.k);
    const w = Math.min(116, (v.x1 - L.x0) * L.k) - x, hh = Math.min(140, (v.y1 - L.y0) * L.k) - y;
    const key = `${x.toFixed(1)}|${y.toFixed(1)}|${w.toFixed(1)}|${hh.toFixed(1)}`;
    if (key === this._vk) return;
    this._vk = key;
    const s = this.locView.style;
    s.transform = `translate(${x.toFixed(1)}px,${y.toFixed(1)}px)`; s.width = Math.max(3, w).toFixed(1) + 'px'; s.height = Math.max(3, hh).toFixed(1) + 'px';
  }
}
