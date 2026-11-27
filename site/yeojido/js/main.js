// 신여지도 — 초기화, 상태, 그리기 반복, 입력, URL 해시.
// 해시 열쇠는 기존판(site/js/main.js)과 같다: v=x,y,scale · lens · city|state|item|route|report · ly · hide (+ 옛 off/on 읽기).

import { loadCore, loadLayers, lensValues } from './adapter.js';
import { Grid } from './hex.js';
import { Camera } from './camera.js';
import { Plate } from './map/plates.js';
import { Land, smooth, css, INK, JU, BAEK, PAPER } from './map/land.js';
import { Lines } from './map/lines.js';
import { Labels } from './map/labels.js';
import { LensColor } from './map/lenscolor.js';
import { LayerMap } from './map/layers.js';
import { LAYER_GROUPS, LAYER_DEFAULT, LEGACY_OFF, LEGACY_ON, OTHER_EDITION, NARROW } from './config.js';
import { makePaper } from './paper.js';
import { h, clear, reducedMotion } from './dom.js';
import { iconEl } from './icons.js';
import { fmtWhen, fmtInt } from './fmt.js';
import { closeTop, modalOpen } from './ui/modal.js';
import { Masthead } from './ui/masthead.js';
import { LensUI } from './ui/lensui.js';
import { Panel } from './ui/panel.js';
import { LayerCtl } from './ui/layerctl.js';
import { Tooltip } from './ui/tooltip.js';
import { Search } from './ui/search.js';
import { Almanac } from './ui/almanac.js';
import { Help } from './ui/help.js';
import { Share } from './ui/share.js';
import { Places } from './ui/a11y.js';

const $ = (id) => document.getElementById(id);

class App {
  constructor(D) {
    this.D = D;
    const W = D.world;
    this.grid = new Grid(W.cols, W.rows, W.radius);
    this.cam = new Camera(this.grid.width, this.grid.height, W.radius);
    this.land = new Land(W, this.grid);
    this.lines = new Lines(D, this.grid, this.land);
    this.labels = new Labels(D);
    this.world = { w: this.grid.width, h: this.grid.height, hexR: W.radius };
    this.inkPlate = new Plate((ctx, t) => this.land.paintInk(ctx, t));
    this.pigPlate = new Plate((ctx, t) => this.land.paintPigment(ctx, t));
    this.lensPlate = null; this.lensOld = null; this.lensFade = null;

    // 상태
    this.lens = null; this.lensColor = null; this.lensRange = null;
    this.sel = { type: null, id: null };
    this.outline = null;
    this.layerOn = { ...LAYER_DEFAULT };
    this.subOff = new Set();
    this.layerMap = null;
    this.hoverCell = -1; this.hoverCity = null;
    this.listeners = new Map();
    this.narrow = window.innerWidth <= NARROW;
    this.touch = false;

    // 관심 범위: 대한민국 육지 칸 + 여백
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (let i = 0; i < this.grid.n; i++) {
      if (W.owner[i] < 0) continue;
      x0 = Math.min(x0, this.grid.cx[i]); x1 = Math.max(x1, this.grid.cx[i]);
      y0 = Math.min(y0, this.grid.cy[i]); y1 = Math.max(y1, this.grid.cy[i]);
    }
    const m = W.radius * 3;
    this.focus = { x0: x0 - m, y0: y0 - m, x1: x1 + m, y1: y1 + m };
    // 전도 맞춤은 본토와 큰 섬(이어진 칸 20개 이상)에 맞춘다. 울릉도·독도와 먼 섬은 끌어서 본다.
    {
      const seen = new Uint8Array(this.grid.n), nb = this.land.nb;
      let fx0 = 1e9, fy0 = 1e9, fx1 = -1e9, fy1 = -1e9;
      for (let i = 0; i < this.grid.n; i++) {
        if (W.owner[i] < 0 || seen[i]) continue;
        const comp = [i]; seen[i] = 1;
        for (let q = 0; q < comp.length; q++) for (let d = 0; d < 6; d++) { const j = nb[comp[q] * 6 + d]; if (j >= 0 && !seen[j] && W.owner[j] >= 0) { seen[j] = 1; comp.push(j); } }
        if (comp.length < 20) continue;
        for (const c of comp) { fx0 = Math.min(fx0, this.grid.cx[c]); fx1 = Math.max(fx1, this.grid.cx[c]); fy0 = Math.min(fy0, this.grid.cy[c]); fy1 = Math.max(fy1, this.grid.cy[c]); }
      }
      this.fitFocus = fx1 > fx0 ? { x0: fx0 - m, y0: fy0 - m, x1: fx1 + m, y1: fy1 + m } : this.focus;
      this.cam.fitFocus = this.fitFocus;
    }

    this.canvas = $('map');
    this.ctx = this.canvas.getContext('2d', { alpha: false });
    this.buildChrome();
    this.masthead = new Masthead(this);
    this.lensui = new LensUI(this);
    this.panel = new Panel(this);
    this.layerctl = new LayerCtl(this);
    this.tooltip = new Tooltip(this);
    this.search = new Search(this);
    this.almanac = new Almanac(this);
    this.help = new Help(this);
    this.share = new Share(this);
    this.places = new Places(this);

    this.resize(true);
    new ResizeObserver(() => this.resize()).observe($('plate'));
    window.addEventListener('resize', () => this.resize());
    this.bindInput();
    this.readHash(true);
    window.addEventListener('hashchange', () => { if (location.hash !== this.lastHash) this.readHash(false); });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { this.labels.wcache.clear(); this.requestDraw(); });
    this.requestDraw();
  }

  // ---------- 알림 ----------
  on(evt, fn) { (this.listeners.get(evt) || this.listeners.set(evt, []).get(evt)).push(fn); return this; }
  emit(evt, a) { for (const fn of this.listeners.get(evt) || []) { try { fn(a); } catch (e) { console.error(e); } } }

  // ---------- 여백의 고정 부품: 제첨, 도구, 아래 여백 ----------
  buildChrome() {
    document.documentElement.style.setProperty('--grain', `url(${makePaper(512)})`);
    const slip = $('slip');
    clear(slip).append(h('a', { href: '#', title: '표지로', 'aria-label': '신여지도 — 표지 보기', onclick: (e) => { e.preventDefault(); this.showIntro(); } },
      h('span.title-hanja', { 'aria-hidden': 'true' }), h('b', '신여지도'), h('span.seal', { 'aria-hidden': 'true' })));
    const tool = (ic, label, fn, extra) => h('button.tool', { type: 'button', onclick: fn, ...(extra || {}) }, iconEl(ic, 16), h('span', label));
    const tools = $('tools');
    clear(tools).append(
      tool('search', '찾기', () => this.search.open(), { 'aria-keyshortcuts': '/', class: 't-search' }),
      tool('almanac', '연감', () => this.almanac.open(), { class: 't-almanac' }),
      tool('share', '공유', (e) => this.share.toggle(e.currentTarget), { class: 't-share', 'aria-haspopup': 'menu' }),
      tool('help', '도움말', () => this.help.open(), { 'aria-keyshortcuts': '?', class: 't-help' }),
      h('a.tool.switch', { href: OTHER_EDITION, id: 'edition', title: '같은 자리·같은 렌즈를 원래 판(koreaciv)으로 봅니다', 'aria-label': 'koreaciv 판으로 돌아가기', onclick: (e) => { e.preventDefault(); this.goOtherEdition(); } }, iconEl('swap', 16), h('span', 'koreaciv 판으로')),
    );
    const foot = $('foot');
    this.zname = h('span.zname', '전도');
    this.scaleBar = h('i'); this.scaleText = h('span', '');
    clear(foot).append(
      this.zname,
      h('div.scale', { 'aria-hidden': 'true' }, this.scaleBar, this.scaleText),
      h('div.zoom', { role: 'group', 'aria-label': '확대·축소' },
        h('button', { type: 'button', 'aria-label': '확대', title: '확대 (+)', onclick: () => this.zoomBy(1.6) }, iconEl('plus', 16)),
        h('button', { type: 'button', 'aria-label': '축소', title: '축소 (−)', onclick: () => this.zoomBy(1 / 1.6) }, iconEl('minus', 16)),
        h('button', { type: 'button', 'aria-label': '전도로', title: '전도 (0)', onclick: () => this.fitAll() }, iconEl('home', 16))),
      h('p.credit', `칸 하나 ${this.D.world.hexKm2 ?? '—'} km² · 모든 숫자는 공공 통계 · `, h('button', { type: 'button', onclick: () => this.almanac.open('sources') }, '출처와 기준 시점'), ' · ', h('a', { href: '../sources/' }, '이용조건')),
    );
  }

  goOtherEdition() {
    this.writeHash(true);
    location.href = OTHER_EDITION + (this.lastHash || location.hash || '');
  }

  // ---------- 크기 ----------
  insets() {
    const pad = this.narrow ? 6 : 12;
    const I = { top: pad, bottom: pad, left: pad, right: pad };
    const pr = $('plate').getBoundingClientRect();
    if (this.introOn) {
      if (this.narrow) { I.top = pr.height * 0.24; I.bottom = pr.height * 0.13; }
      else I.right = pr.width * 0.46;
      return I;
    }
    const p = $('panel');
    if (!p.hidden) {
      const r = p.getBoundingClientRect();
      if (this.narrow) I.bottom = Math.max(pad, Math.min(pr.height * 0.6, pr.bottom - r.top) + pad);
      else I.right = Math.max(pad, pr.right - r.left + pad);
    }
    return I;
  }

  resize(first = false) {
    const r = $('plate').getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    this.narrow = window.innerWidth <= NARROW;
    const dpr = window.devicePixelRatio || 1;
    this.cdpr = Math.min(dpr, 2);
    this.pdpr = Math.min(dpr, 1.5);
    const w = Math.round(r.width * this.cdpr), hgt = Math.round(r.height * this.cdpr);
    if (this.canvas.width !== w || this.canvas.height !== hgt) { this.canvas.width = w; this.canvas.height = hgt; }
    const wasFit = !first && Math.abs(this.cam.scale - this.cam.fitScale) / this.cam.fitScale < 0.01;
    this.cam.resize(r.width, r.height, this.focus, this.insets());
    if (first || wasFit) this.cam.fit();
    for (const p of [this.inkPlate, this.pigPlate, this.lensPlate]) if (p) p.baseJ = null;
    this.emit('resize');
    this.requestDraw();
  }

  // 패널이 열리고 닫힐 때 여백만 다시 셈한다 (자리 맞추기는 flyTo 가 한다)
  updateInsets() { this.cam.insets = this.insets(); this.cam.fitScale = this.cam.fitTarget().scale; this.cam.minScale = this.cam.fitScale * 0.9; }

  requestDraw() {
    if (this.raf) return;
    this.raf = requestAnimationFrame((now) => { this.raf = 0; this.render(now); });
  }

  // ---------- 그리기 ----------
  render(now) {
    const { ctx, cam } = this, k = this.cdpr;
    let more = cam.step(now);
    if (this.inertia) more = this.stepInertia() || more;
    const moving = more || now - (this.lastMove || 0) < 140;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = css(PAPER);
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    const budget = moving ? 5 : 14;
    const rc = cam.rc;
    // 먹판 위로 채색판이 배어 나온다. 렌즈를 켜면 먹판 위에 통계를 한 판 더 찍는다.
    const kPig = this.lens ? 0 : smooth(5.5, 12, rc);
    let pending = 0;
    if (kPig < 1) pending += this.inkPlate.draw(ctx, cam, this.pdpr, k, budget, this.world);
    if (kPig > 0) { ctx.globalAlpha = kPig; pending += this.pigPlate.draw(ctx, cam, this.pdpr, k, budget, this.world); ctx.globalAlpha = 1; }
    if (this.lensPlate || this.lensOld) {
      let a = 1;
      if (this.lensFade) {
        a = Math.min(1, (now - this.lensFade) / 380);
        a = 1 - Math.pow(1 - a, 3);
        if (a >= 1) { this.lensFade = null; this.lensOld = null; } else more = true;
      }
      ctx.globalCompositeOperation = 'multiply';
      if (this.lensOld) { ctx.globalAlpha = 0.84 * (1 - a); this.lensOld.draw(ctx, cam, this.pdpr, k, 0, this.world); }
      if (this.lensPlate) { ctx.globalAlpha = 0.84 * a; pending += this.lensPlate.draw(ctx, cam, this.pdpr, k, budget, this.world); }
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    }
    this.drawScene(ctx, cam, { cdpr: k, lens: !!this.lens, exporting: false });
    this.updateFoot();
    this.emit('view');
    if (more || pending > 0) this.requestDraw();
    else if (moving) { clearTimeout(this.settleT); this.settleT = setTimeout(() => this.requestDraw(), 150); }
    this.writeHash();
  }

  // 다른 캔버스에 지금 상태를 한 번에 그린다 (그림 내보내기용). cam: 그 캔버스 크기에 맞춘 Camera, k: 기기 px / CSS px.
  // 조각을 모두 구울 때까지 기다리지 않고 이 호출 안에서 다 굽는다. 끝난 뒤 화면은 requestDraw 로 되돌린다.
  renderTo(ctx, cam, k) {
    const world = this.world, pd = Math.min(k, 2);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = css(PAPER);
    ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    const kPig = this.lens ? 0 : smooth(5.5, 12, cam.rc);
    const once = (paint, alpha) => { const p = new Plate(paint, { alpha }); p.baseJ = -1; p.draw(ctx, cam, pd, k, 1e9, world); };
    if (kPig < 1) once((c, t) => this.land.paintInk(c, t), false);
    if (kPig > 0) { ctx.globalAlpha = kPig; once((c, t) => this.land.paintPigment(c, t), false); ctx.globalAlpha = 1; }
    if (this.lensPaint) { ctx.globalCompositeOperation = 'multiply'; ctx.globalAlpha = 0.84; once(this.lensPaint, true); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over'; }
    this.drawScene(ctx, cam, { cdpr: k, lens: !!this.lens, exporting: true });
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.requestDraw();
  }

  // 판 위의 모든 것 (선·층·테두리·이름). 내보내는 그림(share.js)도 이 함수로 그린다.
  drawScene(ctx, cam, o) {
    const k = o.cdpr;
    ctx.setTransform(k, 0, 0, k, 0, 0);
    this.lines.draw(ctx, cam, o);
    ctx.setTransform(k, 0, 0, k, 0, 0);
    const L = this.layerMap;
    if (L) L.drawUnder(ctx, cam, o);
    this.drawSelection(ctx, cam, o);
    this.labels.drawGeo(ctx, cam, { lens: o.lens, compact: this.narrow });
    const reserved = L ? L.priorityBoxes(cam) : [];
    const rects = this.labels.layout(ctx, cam, { sel: this.sel.type === 'city' ? this.sel.id : null, hover: o.exporting ? null : this.hoverCity, selState: this.sel.type === 'state' ? this.sel.id : null, reserved, compact: this.narrow });
    if (L) { L.layout(cam, rects, o); L.drawIcons(ctx, cam, o); }
    this.labels.draw(ctx, cam, { lens: o.lens });
  }

  drawSelection(ctx, cam, o) {
    const s = cam.scale, ox = cam.vw / 2 - cam.x * s, oy = cam.vh / 2 - cam.y * s;
    if (this.outline && this.outline.length) {
      ctx.lineCap = 'round';
      ctx.beginPath();
      for (const [x0, y0, x1, y1] of this.outline) { ctx.moveTo(x0 * s + ox, y0 * s + oy); ctx.lineTo(x1 * s + ox, y1 * s + oy); }
      const w = Math.max(2.2, Math.min(4, cam.rc * 0.14));
      ctx.strokeStyle = 'rgba(251,246,232,0.92)'; ctx.lineWidth = w + 2.4; ctx.stroke();
      ctx.strokeStyle = css(JU); ctx.lineWidth = w; ctx.stroke();
    }
    const hex = (i, color, w, under) => {
      ctx.beginPath();
      this.grid.pathHex(ctx, i, s, cam.x - cam.vw / 2 / s, cam.y - cam.vh / 2 / s);
      if (under) { ctx.strokeStyle = 'rgba(251,246,232,0.9)'; ctx.lineWidth = w + 2.2; ctx.stroke(); }
      ctx.strokeStyle = color; ctx.lineWidth = w; ctx.stroke();
    };
    if (this.sel.type === 'item' && this.selItem && this.selItem.cell >= 0) hex(this.selItem.cell, css(JU), 2.2, true);
    if (this.pinCell >= 0) hex(this.pinCell, css(JU), 2, true);
    if (this.hoverCell >= 0 && !o.exporting && cam.rc > 3) hex(this.hoverCell, css(INK, 0.85), 1.5, false);
  }

  updateFoot() {
    const cam = this.cam, rc = cam.rc;
    const name = rc < 5 ? '전도' : rc < 6.8 ? '권역도' : rc < 11 ? '도별도' : rc < 17 ? '군현도' : '칸';
    if (this.zname.textContent !== name) this.zname.textContent = name;
    // 축척 막대: 보기 좋은 거리로
    const kmPerPx = this.D.world.metersPerUnit / 1000 / cam.scale;
    const nice = [1, 2, 5, 10, 20, 50, 100, 200];
    const km = nice.find((v) => v / kmPerPx >= 52) || 200;
    const px = Math.round(km / kmPerPx);
    if (this._sb !== px + ':' + km) { this._sb = px + ':' + km; this.scaleBar.style.width = px + 'px'; this.scaleText.textContent = km + ' km'; }
  }

  // ---------- 렌즈 ----------
  setLens(id, silent = false) {
    const LS = this.D.lenses;
    const gone = id && !LS.byId.has(id) && Object.prototype.hasOwnProperty.call(LS.removed, id) ? LS.removed[id] : null;
    if (gone) {
      // 이 판에서 뺀 렌즈의 옛 링크: 까닭을 알리고 가까운 렌즈(있으면)나 지형으로
      const near = gone.near && LS.byId.has(gone.near) ? gone.near : null;
      this.toast(`'${gone.name || id}' 렌즈는 이 판에서는 제공하지 않습니다${near ? ` — '${LS.byId.get(near).name}' 렌즈로 보여 줍니다` : ' — 지형으로 보여 줍니다'}. 까닭은 연감 › 출처.`);
      id = near;
    } else if (id && !LS.byId.has(id)) {
      const near = LS.retired[id], old = LS.retiredItems.find((x) => x.id === id);
      if (near && LS.byId.has(near)) { this.toast(`'${old ? old.name : id}' 렌즈는 정리되어 '${LS.byId.get(near).name}' 렌즈로 보여 줍니다.`); id = near; }
      else { this.toast(`'${id}' 렌즈를 찾지 못해 지형으로 보여 줍니다.`); id = null; }
    }
    const lens = id ? LS.byId.get(id) : null;
    if (lens === this.lens) return;
    this.lensOld = this.lensPlate;
    this.lens = lens;
    this.lensRange = null;
    this.lensColor = lens ? new LensColor(lens) : null;
    if (lens) {
      const vals = lensValues(lens, this.D.world), col = this.lensColor, own = this.D.world.owner;
      this.lensPaint = (ctx, t) => this.land.paintLens(ctx, t, (i) => {
        const v = vals[i], R = this.lensRange;
        if (R && !R.test(v)) return undefined;
        return col.rgb(v);
      });
      this.lensPlate = new Plate(this.lensPaint, { alpha: true });
    } else { this.lensPlate = null; this.lensPaint = null; }
    this.lensFade = reducedMotion() || silent ? null : performance.now();
    if (!this.lensFade) this.lensOld = null;
    this.emit('lens', lens);
    this.requestDraw();
  }

  // 범례에서 고른 범위만 남긴다. range: null | {test(v) -> bool, ...}
  setLensRange(range) {
    this.lensRange = range || null;
    if (this.lensPlate) this.lensPlate.invalidate();
    this.emit('range', this.lensRange);
    this.requestDraw();
  }

  stepLens(d) {
    const ids = [null, ...this.D.lenses.list.map((l) => l.id)];
    const k = ids.indexOf(this.lens ? this.lens.id : null);
    this.setLens(ids[(k + d + ids.length) % ids.length]);
  }

  // ---------- 층 ----------
  layerVisible(group, sub) { return !!this.layerOn[group] && !this.subOff.has(sub); }
  toggleLayerGroup(id, on) { this.layerOn[id] = on == null ? !this.layerOn[id] : !!on; this.emit('layers'); this.requestDraw(); }
  toggleSub(sub, on) { const off = on == null ? !this.subOff.has(sub) : !on; if (off) this.subOff.add(sub); else this.subOff.delete(sub); this.emit('layers'); this.requestDraw(); }

  // ---------- 고르기 ----------
  cellsOfState(code) {
    const idx = this.D.world.stateIndex.get(code), own = this.D.world.owner, out = [];
    if (idx == null) return out;
    for (let i = 0; i < this.grid.n; i++) if (own[i] === idx) out.push(i);
    return out;
  }
  flyCells(cells, maxFrac = 0.8, pad = 4) {
    if (!cells.length) return;
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (const i of cells) { x0 = Math.min(x0, this.grid.cx[i]); x1 = Math.max(x1, this.grid.cx[i]); y0 = Math.min(y0, this.grid.cy[i]); y1 = Math.max(y1, this.grid.cy[i]); }
    const I = this.cam.insets, aw = Math.max(120, this.cam.vw - I.left - I.right), ah = Math.max(120, this.cam.vh - I.top - I.bottom);
    const m = this.grid.W * pad;
    const sc = Math.min(this.cam.maxScale * maxFrac, aw / (x1 - x0 + m), ah / (y1 - y0 + m));
    this.flyTo((x0 + x1) / 2, (y0 + y1) / 2, sc);
  }
  flyTo(x, y, scale, ms = 520) {
    this.inertia = null;
    this.cam.flyTo(this.cam.centerTarget(x, y, scale), reducedMotion() ? 0 : ms);
    this.requestDraw();
  }
  zoomBy(f) { const c = this.cam, I = c.insets; const [wx, wy] = c.toWorld((c.vw + I.left - I.right) / 2, (c.vh + I.top - I.bottom) / 2); this.flyTo(wx, wy, c.scale * f, 240); }
  fitAll() { this.updateInsets(); this.cam.flyTo(this.cam.fitTarget(), reducedMotion() ? 0 : 520); this.requestDraw(); }

  _select(type, id, outline) {
    this.sel = { type, id };
    this.selItem = null; this.selRoute = null; this.pinCell = -1;
    this.outline = outline || null;
    this.tooltip.hide();
  }
  // 장이 열리면(넓은 화면) 종이 전체가 장 왼쪽으로 물러난다: 도구·층·여백이 가려지지 않는다
  syncPanel() {
    const open = !$('panel').hidden;
    const w = open ? Math.round($('panel').getBoundingClientRect().width) : 0;
    if (this._pw !== w) {
      this._pw = w;
      document.body.classList.toggle('has-panel', open);
      document.body.style.setProperty('--panel-cur', w + 'px');
      this.resize();
    } else this.updateInsets();
  }
  _after(fly) { this.syncPanel(); if (fly) fly(); this.emit('select', this.sel); this.requestDraw(); }

  selectCity(id, o = {}) {
    const c = this.D.cityById.get(id);
    if (!c) return false;
    this._select('city', id, this.land.outline(c.footprint));
    this.panel.showCity(c);
    this._after(o.fly ? () => this.flyCells(c.footprint, 0.75, 5) : null);
    if (o.fly) this.focusPanel();
    return true;
  }
  selectState(code, o = {}) {
    const s = this.D.stateByCode.get(String(code));
    if (!s) return false;
    const cells = this.cellsOfState(s.code);
    this._select('state', s.code, this.land.outline(cells));
    this.panel.showState(s);
    this._after(o.fly ? () => this.flyCells(cells, 0.6, 3) : null);
    if (o.fly) this.focusPanel();
    return true;
  }
  selectItem(it, o = {}) {
    if (!it) return false;
    let outline = null;
    const L = this.D.layers;
    if (it.kind === 'national_park' && L) { const p = L.parks.find((x) => x.id === it.ref); if (p) outline = this.land.outline(p.cells); }
    this._select('item', it.id, outline);
    this.selItem = it;
    this.panel.showItem(it);
    this._after(o.fly && it.cell >= 0 ? () => this.flyTo(this.grid.cx[it.cell], this.grid.cy[it.cell], Math.max(this.cam.scale, Math.min(this.cam.maxScale * 0.5, this.cam.fitScale * 4))) : null);
    if (o.fly) this.focusPanel();
    return true;
  }
  selectRoute(rt, o = {}) {
    if (!rt) return false;
    if (!this.layerVisible('trade', 'routes')) { this.layerOn.trade = true; this.subOff.delete('routes'); this.emit('layers'); }
    const cells = [...this.cellsOfState(rt.a), ...this.cellsOfState(rt.b)];
    this._select('route', rt.id, this.land.outline(cells));
    this.selRoute = rt;
    this.panel.showRoute(rt);
    this._after(o.fly ? () => this.flyCells(cells, 0.5, 3) : null);
    if (o.fly) this.focusPanel();
    return true;
  }
  // 지도 밖(찾기·순위·목록)에서 연 장은 초점을 장 제목으로 옮긴다 (모달이 초점을 되돌린 뒤에)
  focusPanel() { setTimeout(() => { if (this.panel.focusHeading) this.panel.focusHeading(); }, 40); }

  showNation() {
    this._select('nation', '1', null);
    this.panel.showNation();
    this._after(null);
  }
  clearSelection() {
    if (!this.sel.type && $('panel').hidden) return;
    this._select(null, null, null);
    this.panel.hide();
    this._after(null);
  }

  toast(msg) {
    const el = $('toast');
    el.textContent = msg; el.hidden = false;
    clearTimeout(this.toastT);
    this.toastT = setTimeout(() => { el.hidden = true; }, 3800);
  }
  say(msg) { $('live').textContent = msg; }

  // ---------- 표지 ----------
  showIntro() {
    const el = $('intro'), D = this.D;
    this.clearSelection();
    this.introOn = true;
    document.body.classList.add('is-intro');
    const fact = (k, v) => h('div', h('span.kicker', k), h('b', v));
    const landCells = D.world.landCells.length;
    clear(el).append(h('div.side',
      h('div.title', h('h1', '신여지도'), h('span.title-hanja', { role: 'img', 'aria-label': '新輿地圖' }), h('span.seal', { 'aria-hidden': 'true' })),
      h('p.lead', '멀리서는 먹으로 찍은 지도.', h('br'), '다가가면 칸마다 빛깔과 숫자가 배어 나온다.'),
      h('div.facts', fact('칸', fmtInt(landCells)), fact('고을', fmtInt(D.cities.length)), fact('렌즈', fmtInt(D.lenses.list.length)), fact('산줄기', D.ridges ? fmtInt(D.ridges.lines.length) + '줄' : '자료 없음')),
      h('div.go', h('button.btn-ink', { type: 'button', id: 'enter' }, '지도를 펼치다', iconEl('arrow', 18)), h('p.when', `${fmtWhen(D.vintage)} 판 · 공공 통계로 다시 새긴 나라 지도`)),
    ));
    el.hidden = false; el.classList.remove('is-leaving');
    el.onclick = () => this.leaveIntro();
    this.resize(); this.cam.fit(); this.requestDraw();
    requestAnimationFrame(() => { this.resize(); this.cam.fit(); this.requestDraw(); const b = $('enter'); if (b) b.focus({ preventScroll: true }); });
  }
  leaveIntro() {
    if (!this.introOn) return;
    this.introOn = false;
    try { sessionStorage.setItem('yeojido.seen', '1'); } catch (e) { /* 저장 못 해도 된다 */ }
    const el = $('intro');
    el.classList.add('is-leaving');
    document.body.classList.remove('is-intro');
    setTimeout(() => { el.hidden = true; }, reducedMotion() ? 0 : 320);
    const from = { x: this.cam.x, y: this.cam.y, scale: this.cam.scale };
    this.resize();
    // 도판이 여백 자리로 줄어든 만큼 보정한 뒤 전도 자리로 옮겨 간다
    Object.assign(this.cam, from); this.cam.clamp();
    this.cam.flyTo(this.cam.fitTarget(), reducedMotion() ? 0 : 780);
    this.requestDraw();
    this.canvas.focus({ preventScroll: true });
  }

  // ---------- 입력 ----------
  bindInput() {
    const cv = this.canvas, cam = this.cam;
    const pts = new Map();
    let drag = null, pinch = null, moved = 0, vel = [0, 0], lastT = 0;
    const pos = (e) => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    cv.addEventListener('pointerdown', (e) => {
      if (e.button > 0) return;
      cv.setPointerCapture(e.pointerId);
      this.touch = e.pointerType === 'touch';
      const p = pos(e);
      pts.set(e.pointerId, p);
      moved = 0; this.inertia = null; cam.anim = null;
      if (pts.size === 1) { drag = p; vel = [0, 0]; lastT = performance.now(); }
      if (pts.size === 2) { const [a, b] = [...pts.values()]; pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), m: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] }; drag = null; }
    });
    cv.addEventListener('pointermove', (e) => {
      const p = pos(e);
      if (pts.has(e.pointerId)) pts.set(e.pointerId, p);
      if (pinch && pts.size === 2) {
        const [a, b] = [...pts.values()];
        const d = Math.hypot(a[0] - b[0], a[1] - b[1]), m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        cam.pan(m[0] - pinch.m[0], m[1] - pinch.m[1]);
        if (pinch.d > 0) cam.zoomAt(d / pinch.d, m[0], m[1]);
        pinch = { d, m }; moved += 10; this.lastMove = performance.now();
        this.requestDraw();
        return;
      }
      if (drag) {
        const dx = p[0] - drag[0], dy = p[1] - drag[1];
        moved += Math.abs(dx) + Math.abs(dy);
        if (moved > 4) {
          cam.pan(dx, dy);
          const now = performance.now(), dt = Math.max(1, now - lastT);
          vel = [vel[0] * 0.6 + (dx / dt) * 0.4, vel[1] * 0.6 + (dy / dt) * 0.4]; lastT = now;
          cv.classList.add('is-drag');
          this.tooltip.hide(); this.lastMove = now;
          this.requestDraw();
        }
        drag = p;
        return;
      }
      if (e.pointerType !== 'touch') this.hover(p[0], p[1], e);
    });
    const end = (e) => {
      const p = pos(e);
      const wasClick = pts.size === 1 && moved <= 4 && e.type === 'pointerup';
      const wasDrag = pts.size === 1 && moved > 4 && e.type === 'pointerup';
      pts.delete(e.pointerId);
      if (pts.size < 2) pinch = null;
      if (pts.size === 0) drag = null;
      else if (pts.size === 1) { drag = [...pts.values()][0]; moved = 99; }
      cv.classList.remove('is-drag');
      if (wasClick) this.click(p[0], p[1], e.pointerType === 'touch');
      else if (wasDrag && !reducedMotion() && performance.now() - lastT < 60 && Math.hypot(vel[0], vel[1]) > 0.25) { this.inertia = { vx: vel[0] * 16, vy: vel[1] * 16 }; this.requestDraw(); }
    };
    cv.addEventListener('pointerup', end);
    cv.addEventListener('pointercancel', end);
    cv.addEventListener('pointerleave', () => { if (this.hoverCell >= 0 || this.hoverCity != null) { this.hoverCell = -1; this.hoverCity = null; this.requestDraw(); } this.tooltip.hide(); });
    cv.addEventListener('wheel', (e) => {
      e.preventDefault();
      const p = pos(e);
      const dy = e.deltaMode === 1 ? e.deltaY * 33 : e.deltaY;
      cam.zoomAt(Math.exp(-Math.max(-160, Math.min(160, dy)) * (e.ctrlKey ? 0.01 : 0.0022)), p[0], p[1]);
      this.inertia = null; this.lastMove = performance.now();
      this.tooltip.hide();
      this.requestDraw();
    }, { passive: false });
    cv.addEventListener('dblclick', (e) => { const p = pos(e); const [wx, wy] = cam.toWorld(p[0], p[1]); this.flyTo(wx, wy, cam.scale * 2, 320); });

    window.addEventListener('keydown', (e) => {
      if (this.introOn) { if (e.key === 'Enter' || e.key === ' ' || e.key === 'Escape') { e.preventDefault(); this.leaveIntro(); } return; }
      if (e.key === 'Escape') { if (this.escape()) e.preventDefault(); return; }
      if (e.target.closest && e.target.closest('input, textarea, select, [contenteditable]')) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (modalOpen()) return;
      const k = e.key, c = e.code, step = 90;
      const onMap = e.target === cv || e.target === document.body;
      if (k === '?' || (k === '/' && e.shiftKey)) { e.preventDefault(); this.help.open(); }
      else if (k === '/') { e.preventDefault(); this.search.open(); }
      else if (c === 'KeyL') this.stepLens(e.shiftKey ? -1 : 1);
      else if (c === 'KeyR' && !e.shiftKey) this.toggleLayerGroup('resources');
      else if (k === '+' || k === '=') this.zoomBy(1.6);
      else if (k === '-' || k === '_') this.zoomBy(1 / 1.6);
      else if (k === '0') this.fitAll();
      else if (!onMap && k.startsWith('Arrow')) return;
      else if (k === 'ArrowLeft' || c === 'KeyA') cam.pan(step, 0);
      else if (k === 'ArrowRight' || c === 'KeyD') cam.pan(-step, 0);
      else if (k === 'ArrowUp' || c === 'KeyW') cam.pan(0, step);
      else if (k === 'ArrowDown' || c === 'KeyS') cam.pan(0, -step);
      else return;
      if (k.startsWith('Arrow')) e.preventDefault();
      this.requestDraw();
    });
  }

  stepInertia() {
    const v = this.inertia;
    this.cam.pan(v.vx, v.vy);
    v.vx *= 0.88; v.vy *= 0.88;
    this.lastMove = performance.now();
    if (Math.hypot(v.vx, v.vy) < 0.4) { this.inertia = null; return false; }
    return true;
  }

  // Esc: 맨 위에 뜬 것부터 하나씩 (모달 → 공유 메뉴·렌즈 메뉴·층 메뉴 → 보고서 → 범례 범위 → 장)
  escape() {
    if (closeTop()) return true;
    for (const u of [this.share, this.lensui, this.layerctl, this.masthead]) if (u.closeTransient && u.closeTransient()) return true;
    if (this.pinCell >= 0) { this.pinCell = -1; this.tooltip.hide(); this.requestDraw(); return true; }
    if (this.lensRange) { this.setLensRange(null); return true; }
    if (this.sel.type) { this.clearSelection(); this.canvas.focus({ preventScroll: true }); return true; }
    return false;
  }

  pick(sx, sy) {
    const city = this.labels.hitCity(sx, sy);
    if (city) return { city };
    const L = this.layerMap;
    const ic = L ? L.hit(sx, sy) : null;
    if (ic) return { icon: ic };
    const route = L ? L.hitRoute(sx, sy) : null;
    if (route) return { route };
    const state = this.labels.hitState(sx, sy);
    if (state) return { state };
    const [wx, wy] = this.cam.toWorld(sx, sy);
    return { cell: this.grid.pointToCell(wx, wy) };
  }

  hover(sx, sy, e) {
    const p = this.pick(sx, sy);
    const [wx, wy] = this.cam.toWorld(sx, sy);
    const cell = this.grid.pointToCell(wx, wy);
    const hc = p.city ? p.city.id : null;
    const changed = cell !== this.hoverCell || hc !== this.hoverCity;
    this.hoverCell = cell; this.hoverCity = hc;
    this.canvas.classList.toggle('is-hot', !!(p.city || p.icon || p.route || p.state));
    if (p.city) this.tooltip.showCity(p.city, e.clientX, e.clientY);
    else if (p.icon) this.tooltip.showItem(p.icon.it, p.icon.others || [], e.clientX, e.clientY);
    else if (p.route) this.tooltip.showRoute(p.route, e.clientX, e.clientY);
    else if (p.state) this.tooltip.showState(p.state, e.clientX, e.clientY);
    else this.tooltip.showCell(cell, e.clientX, e.clientY);
    if (changed) this.requestDraw();
  }

  click(sx, sy, touch) {
    const p = this.pick(sx, sy);
    if (p.city) return this.selectCity(p.city.id);
    if (p.icon) return this.selectItem(p.icon.it);
    if (p.route) return this.selectRoute(p.route);
    if (p.state) return this.selectState(p.state.code);
    const cell = p.cell, W = this.D.world;
    if (cell < 0 || W.owner[cell] < 0) { this.pinCell = -1; this.tooltip.hide(); return this.clearSelection(); }
    // 빈 땅: 손가락이면 먼저 칸 띠(고을 장·시도 장 단추), 마우스면 그 칸의 고을 장
    if (touch) { this.pinCell = cell; this.tooltip.pinCell(cell); this.requestDraw(); return null; }
    const c = this.D.cityOfCell(cell);
    if (c) return this.selectCity(c.id);
    const s = this.D.stateOfCell(cell);
    return s ? this.selectState(s.code) : null;
  }

  // ---------- URL 해시 ----------
  hashString() {
    const c = this.cam, p = new URLSearchParams();
    p.set('v', `${Math.round(c.x)},${Math.round(c.y)},${c.scale.toFixed(4)}`);
    if (this.lens) p.set('lens', this.lens.id);
    const s = this.sel;
    if (s.type === 'item') p.set('item', s.id);
    else if (s.type === 'route') p.set('route', s.id);
    else if (s.type === 'city') p.set('city', String(s.id));
    else if (s.type === 'state') p.set('state', s.id);
    else if (s.type === 'nation') p.set('report', '1');
    else if (this.masthead.reportId && this.masthead.reportId()) p.set('report', this.masthead.reportId());
    if (Object.entries(this.layerOn).some(([k, v]) => v !== LAYER_DEFAULT[k])) p.set('ly', Object.keys(this.layerOn).filter((k) => this.layerOn[k]).join(','));
    if (this.subOff.size) p.set('hide', [...this.subOff].sort().join(','));
    return '#' + p.toString().replace(/%2C/g, ',');
  }
  writeHash(now = false) {
    if (!this.hashReady || this.introOn) return;
    const hs = this.hashString();
    if (hs === this.lastHash) return;
    this.lastHash = hs;
    clearTimeout(this.hashT);
    if (now) history.replaceState(null, '', hs);
    else this.hashT = setTimeout(() => history.replaceState(null, '', hs), 150);
  }

  readLayers(p) {
    Object.assign(this.layerOn, LAYER_DEFAULT);
    const known = new Set(LAYER_GROUPS.flatMap((g) => g.subs.map((s) => s[0])));
    this.subOff = new Set((p.get('hide') || '').split(',').filter((k) => known.has(k)));
    if (p.has('ly')) { const on = p.get('ly').split(','); for (const k of Object.keys(this.layerOn)) this.layerOn[k] = on.includes(k); return; }
    for (const k of (p.get('off') || '').split(',').filter(Boolean)) {
      const m = LEGACY_OFF[k];
      if (!m) continue;
      if (m.group) this.layerOn[m.group] = false;
      for (const s of m.subs || []) this.subOff.add(s);
    }
    for (const k of (p.get('on') || '').split(',').filter(Boolean)) if (LEGACY_ON[k]) this.layerOn[LEGACY_ON[k]] = true;
  }

  // 해시 전체를 한 번에 적용한다: 먼저 지난 선택을 모두 지우고, 검증을 통과한 값만 넣는다.
  readHash(first) {
    if (!first && /^#[a-z-]+$/.test(location.hash)) return; // 건너뛰기 링크 같은 쪽 안 닻
    const p = new URLSearchParams(location.hash.slice(1));
    const keys = ['v', 'lens', 'city', 'state', 'item', 'route', 'report'];
    const meaningful = keys.some((k) => p.get(k));
    // 지난 상태 지우기
    this._select(null, null, null);
    this.panel.hide();
    if (this.masthead.closeReport) this.masthead.closeReport(true);
    this.pendingItem = null; this.pendingRoute = null;
    this.syncPanel();
    const v = (p.get('v') || '').split(',').map(Number);
    if (v.length === 3 && v.every(Number.isFinite) && v[2] > 0) { this.cam.anim = null; this.cam.x = v[0]; this.cam.y = v[1]; this.cam.scale = v[2]; this.cam.clamp(); }
    else if (!first) this.cam.fit();
    this.setLens(p.get('lens') || null, true);
    this.readLayers(p);
    this.emit('layers');
    const item = p.get('item'), route = p.get('route'), city = p.get('city'), state = p.get('state'), report = p.get('report');
    const cmp = p.get('cmp');
    if (item) { this.pendingItem = item; if (this.layerMap) this.selectItem(this.layerMap.byId.get(item)); }
    else if (route) { this.pendingRoute = route; if (this.layerMap) this.selectRoute(this.layerMap.routeById.get(route)); }
    else if (city && /^\d+$/.test(city)) this.selectCity(Number(city));
    else if (cmp && /^\d+/.test(cmp)) this.selectCity(Number(cmp.split(',')[0]));
    else if (state) this.selectState(state);
    else if (report === '1') this.showNation();
    else if (report && report !== '0' && this.masthead.openReport) this.masthead.openReport(report, true);
    this.hashReady = true;
    if (first) {
      let seen = false;
      try { seen = sessionStorage.getItem('yeojido.seen') === '1'; } catch (e) { /* */ }
      if (!meaningful && p.get('intro') !== '0' && !seen) this.showIntro();
    }
    this.emit('select', this.sel);
    this.requestDraw();
  }

  setLayers(L) {
    this.layerMap = new LayerMap(this, L);
    this.emit('layersloaded', L);
    if (this.pendingItem && this.layerMap.byId.has(this.pendingItem)) this.selectItem(this.layerMap.byId.get(this.pendingItem));
    else if (this.pendingRoute && this.layerMap.routeById.has(this.pendingRoute)) this.selectRoute(this.layerMap.routeById.get(this.pendingRoute));
    else this.panel.refresh && this.panel.refresh();
    this.pendingItem = this.pendingRoute = null;
    this.requestDraw();
  }
}

const bar = document.querySelector('#loader .bar i');
loadCore((f) => { if (bar) bar.style.width = Math.round(f * 100) + '%'; })
  .then(async (D) => {
    try { await Promise.race([document.fonts.load('700 14px Hahmlet', '가'), new Promise((r) => setTimeout(r, 1200))]); } catch (e) { /* 글꼴 없이도 그린다 */ }
    const app = (window.app = new App(D));
    document.body.classList.remove('is-loading');
    document.body.classList.add('is-ready');
    if (D.failed.length) app.toast(`일부 자료를 불러오지 못했습니다: ${D.failed.join(', ')}.json — 그 자료가 드는 곳은 '자료 없음'으로 보입니다.`);
    requestAnimationFrame(() => setTimeout(() => loadLayers(D).then((L) => { app.setLayers(L); const f = D.failed.filter((n) => ['wonders', 'resources', 'infrastructure', 'frontier', 'trade'].includes(n)); if (f.length) app.toast(`지도 층 자료 일부를 불러오지 못했습니다: ${f.join(', ')}.json`); }).catch((e) => console.error('층 불러오기 실패', e)), 0));
  })
  .catch((e) => {
    console.error(e);
    const el = document.getElementById('loader');
    el.classList.add('is-error');
    el.querySelector('p').textContent = '지도를 열지 못했습니다: ' + e.message;
  });
