// koreaciv — 초기화, 자료 불러오기, 그리기 반복, 입력, 상태(URL 해시)

import { Grid, EDGE_CORNERS } from './hex.js';
import { Camera } from './camera.js';
import { TerrainRenderer } from './render/terrain.js';
import { ensureValues, unitOf, valueWithUnit } from './render/lens.js';
import { Banners } from './render/banners.js';
import { StateLabels } from './render/labels.js';
import { GeoLabels } from './render/geolabels.js';
import { Topbar } from './ui/topbar.js';
import { Tooltip } from './ui/tooltip.js';
import { Panel, TAB_IDS } from './ui/panel.js';
import { LensBar } from './ui/lensbar.js';
import { Search } from './ui/search.js';
import { Minimap } from './ui/minimap.js';
import { Almanac } from './ui/almanac.js';
import { LayerRenderer, LAYER_GROUPS, BUDGET_DEFAULT } from './render/layers.js';
import { LayerControl } from './ui/layerctl.js';
import { Report } from './ui/report.js';
import { Help } from './ui/help.js';
import { Share } from './ui/share.js';

const FILES = ['world', 'cities', 'states', 'nation', 'lenses'];
// 첫 화면에 없어도 지도는 뜨는 자료 (연감 출처·공유 그림 출처 줄). 실패하면 그 부분만 '불러오지 못함'으로 둔다 (감사 08)
const OPTIONAL_FILES = ['sources'];
// 지도 층은 첫 화면을 그린 뒤 따로 불러온다 (첫 화면이 느려지지 않게)
const LAYER_FILES = ['wonders', 'resources', 'infrastructure', 'frontier', 'trade'];
// 층 기본값 (6단계 5묶음: 교역·접경은 꺼 둠). URL 해시에는 기본값과 다른 것만 적는다 (ly = 켠 묶음, hide = 끈 세부)
const LAYER_DEFAULT = Object.fromEntries(LAYER_GROUPS.map((g) => [g.id, g.def]));
// 5단계까지의 옛 층 키 (공유 링크의 off=/on=) -> 새 묶음·세부
const LEGACY_OFF = { wonders: { group: 'wonders' }, resources: { subs: ['dam', 'mine', 'industrial', 'fishport'] }, power: { subs: ['power'] },
  ports: { subs: ['trade_port', 'airport'] }, trade: { subs: ['export_hub'] }, industry: { subs: ['industry'] }, farm: { subs: ['farm'] },
  infra: { subs: ['station'] }, lines: { subs: ['lines'] } };
const LEGACY_ON = { frontier: 'frontier', routes: 'trade' };

async function fetchJSON(f) {
  const r = await fetch(`data/${f}.json`, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${f}.json (${r.status})`);
  return r.json();
}

// 파일마다 따로 받는다. -> {data: {이름: 값}, failed: {이름: 이유}}
async function fetchAll(names) {
  const res = await Promise.allSettled(names.map((f) => fetchJSON(f)));
  const data = {}, failed = {};
  res.forEach((r, k) => { if (r.status === 'fulfilled') data[names[k]] = r.value; else failed[names[k]] = r.reason ? r.reason.message : '알 수 없음'; });
  return { data, failed };
}

async function load() {
  const { data, failed } = await fetchAll([...FILES, ...OPTIONAL_FILES]);
  const need = FILES.filter((f) => failed[f]);
  if (need.length) throw new Error(`필수 자료를 불러오지 못했습니다: ${need.map((f) => failed[f]).join(', ')}`);
  for (const f of OPTIONAL_FILES) if (!(f in data)) data[f] = null;
  data.loadFailed = Object.fromEntries(OPTIONAL_FILES.filter((f) => failed[f]).map((f) => [f, failed[f]]));
  return data;
}

// 지도 층 파일이 빠졌을 때 쓰는 빈 자리 (다른 층·패널은 그대로 동작)
const LAYER_EMPTY = {
  wonders: () => ({ name: '불가사의', kinds: {}, items: [], parks: [], precision_counts: {}, failed: true }),
  resources: () => ({ name: '자원', kinds: {}, items: [], unplaced: [], precision_counts: {}, failed: true }),
  infrastructure: () => ({ name: '기반시설', kinds: {}, items: [], unplaced: [], lines: { roads: [], rails: [] }, precision_counts: {}, failed: true }),
  frontier: () => null,
  trade: () => null,
};

class App {
  constructor(data) {
    Object.assign(this, data);
    const w = this.world;
    this.grid = new Grid(w.grid.cols, w.grid.rows, w.grid.radius);
    this.cam = new Camera(this.grid.width, this.grid.height, w.grid.radius);
    this.terrain = new TerrainRenderer(w, this.grid);
    this.banners = new Banners(this.cities);
    this.labels = new StateLabels(this.states, this.cities);
    this.geoLabels = new GeoLabels(w);
    this.cityById = new Map(this.cities.map((c) => [c.id, c]));
    this.countyIndex = new Map(w.counties.map((c, k) => [c.code, k]));
    this.stateByCode = new Map(this.states.map((s) => [s.code, s]));
    this.countyCity = new Int16Array(w.counties.length).fill(-1);
    for (const c of this.cities) {
      for (const code of c.sgg) {
        const k = w.counties.findIndex((x) => x.code === code);
        this.countyCity[k] = c.id;
      }
    }
    this.lensById = new Map(this.lenses.lenses.map((l) => [l.id, l]));
    // 렌즈 막대에서 뺀 렌즈의 시군구 값 (패널·툴팁)
    this.retiredById = new Map(((this.lenses.retired_values || {}).items || []).map((x) => [x.id, x]));
    this.lens = null;
    this.selCity = null;
    // 도시 패널에서 고른 탭 (다른 도시로 옮겨도 남음, 해시 tab=)
    this.panelTab = 'overview';
    this.hoverCell = -1;
    this.hoverCity = null;
    this.outline = null;
    this.lastZoom = 0;
    // 지도 층: 5묶음 켜고 끄기 + 세부(subOff). 어느 배율에서 무엇을 그리는지는 빌드가 붙인 tier (wonders.json zoom)
    this.layerOn = { ...LAYER_DEFAULT };
    this.subOff = new Set();
    this.layers = null;
    this.layerR = null;
    this.selItem = null;
    this.selRoute = null;
    this.hoverItem = null;
    // 관심 범위: 대한민국 육지 칸 + 여백
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (let i = 0; i < this.grid.n; i++) {
      if (w.owner[i] < 0) continue;
      x0 = Math.min(x0, this.grid.cx[i]);
      x1 = Math.max(x1, this.grid.cx[i]);
      y0 = Math.min(y0, this.grid.cy[i]);
      y1 = Math.max(y1, this.grid.cy[i]);
    }
    const m = w.grid.radius * 3;
    this.focus = { x0: x0 - m, y0: y0 - m, x1: x1 + m, y1: y1 + m };

    this.canvas = document.getElementById('map');
    this.ctx = this.canvas.getContext('2d');
    this.topbar = new Topbar(this);
    this.tooltip = new Tooltip(this);
    this.panel = new Panel(this);
    this.lensbar = new LensBar(this);
    this.search = new Search(this);
    this.minimap = new Minimap(this);
    this.almanac = new Almanac(this);
    this.layerctl = new LayerControl(this);
    this.report = new Report(this);
    this.help = new Help(this);
    this.share = new Share(this);

    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.bindInput();
    this.readHash();
    window.addEventListener('hashchange', () => {
      if (location.hash !== this.lastHash) this.readHash();
    });
    this.requestDraw();
  }

  resize() {
    const r = this.canvas.getBoundingClientRect();
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(r.width * this.dpr);
    this.canvas.height = Math.round(r.height * this.dpr);
    const first = this.cam.vw === 1;
    // 상단 띠와 아래 렌즈 띠가 덮는 높이 (첫 화면에서 제주가 렌즈 띠에 걸리지 않게)
    const tb = document.getElementById('topbar').getBoundingClientRect();
    const lb = document.getElementById('lensbar').getBoundingClientRect();
    document.documentElement.style.setProperty('--tb-bottom', `${Math.round(tb.bottom + 6)}px`);
    // 좁은 화면에서는 층 조작 줄이 상단 막대 바로 아래에 있다 (그 아래부터 지도를 맞춘다)
    const narrow = r.width <= 700;
    const lc = narrow ? document.getElementById('layerctl').querySelector('.row') : null;
    const top = lc ? Math.max(tb.bottom, lc.getBoundingClientRect().bottom) : tb.bottom;
    const insets = { top: top + 6, bottom: Math.max(0, r.height - lb.top) + 6, left: 0, right: 0 };
    this.cam.resize(r.width, r.height, this.focus, insets);
    if (first) this.cam.fit();
    this.terrain.invalidate();
    this.minimap.draw();
    this.requestDraw();
  }

  requestDraw() {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => {
      this.raf = 0;
      this.render();
    });
  }

  render() {
    const { ctx, cam, dpr } = this;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = '#0c1826';
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    const settled = performance.now() - this.lastZoom > 180 && !this.anim;
    const missing = this.terrain.draw(ctx, cam, dpr, settled);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.drawScene(ctx, cam, false);
    this.minimap.drawView();
    if (!settled) {
      clearTimeout(this.settleTimer);
      this.settleTimer = setTimeout(() => this.requestDraw(), 200);
    } else if (missing) this.requestDraw();
    this.writeHash();
  }

  // 지형 위의 모든 것 (선·접경·공원·교역로, 선택 테두리, 이름표, 아이콘, 깃발, 시도 이름). 공유 그림(share.js)도 같은 함수로 그린다.
  drawScene(ctx, cam, exporting) {
    this.drawFrame(ctx, cam);
    if (this.layerR) {
      this.layerR.drawLines(ctx, cam);
      this.layerR.drawFrontier(ctx, cam);
      this.layerR.drawParks(ctx, cam);
      this.layerR.drawRoutes(ctx, cam);
    }
    this.drawOverlay(ctx, cam, exporting);
    // 한 가지 배치 규칙 (7b #1·#2, wonders.json zoom.draw_priority·budget): 배치는 원전 자리 → 깃발 → 층 아이콘(원전 → 공항·무역항 → 나머지, 예산 안) → 시도 이름 → 강·호수 이름표 순으로 정하고,
    // 그리기는 시도 이름 → 강·호수 이름표 → 아이콘 → 깃발 순으로 아래에서 위로 쌓는다. 시도 이름 때문에 깃발·아이콘을 숨기지 않는다.
    const selId = this.selItem ? this.selItem.id : null;
    const prio = this.layerR ? this.layerR.priorityBoxes(cam, selId) : [];
    const budget = this.layerR ? this.layerR.budget : BUDGET_DEFAULT;
    const flags = this.banners.layout(ctx, cam, this.selCity, prio, budget);
    if (this.layerR) this.layerR.layout(cam, selId, flags);
    const flagBoxes = flags.map((f) => f.r);
    const iconBoxes = this.layerR ? this.layerR.placedBoxes() : [];
    this.labels.layout(ctx, cam, this.selState, [...flagBoxes, ...(this.layerR ? this.layerR.placedBoxes(true) : [])], !!this.lens);
    this.labels.draw(ctx, this.selState);
    this.geoLabels.draw(ctx, cam, !!this.lens, [...flagBoxes, ...iconBoxes]);
    if (this.layerR) this.layerR.drawIcons(ctx);
    this.banners.draw(ctx, this.selCity, exporting ? null : this.hoverCity);
  }

  // 지도판 가장자리: 안쪽으로 옅어지는 그늘과 가는 금색 테
  drawFrame(ctx, cam) {
    const { grid } = this;
    const [x0, y0] = cam.toScreen(0, 0), [x1, y1] = cam.toScreen(grid.width, grid.height);
    const g = 46;
    const edges = [
      [x0, y0, x0 + g, y0, x0, y0, g, y1 - y0],
      [x1, y0, x1 - g, y0, x1 - g, y0, g, y1 - y0],
      [x0, y0, x0, y0 + g, x0, y0, x1 - x0, g],
      [x0, y1, x0, y1 - g, x0, y1 - g, x1 - x0, g],
    ];
    for (const [ax, ay, bx, by, rx, ry, rw, rh] of edges) {
      const lg = ctx.createLinearGradient(ax, ay, bx, by);
      lg.addColorStop(0, 'rgba(8,16,28,0.75)');
      lg.addColorStop(1, 'rgba(8,16,28,0)');
      ctx.fillStyle = lg;
      ctx.fillRect(rx, ry, rw, rh);
    }
    ctx.strokeStyle = 'rgba(216,178,90,0.55)';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(x0 + 0.5, y0 + 0.5, x1 - x0 - 1, y1 - y0 - 1);
  }

  // 선택한 도시 영토 테두리, 커서 칸
  drawOverlay(ctx, cam, exporting) {
    const { grid } = this;
    const s = cam.scale;
    const tx = (x) => (x - cam.x) * s + cam.vw / 2, ty = (y) => (y - cam.y) * s + cam.vh / 2;
    if (this.outline) {
      ctx.lineCap = 'round';
      ctx.beginPath();
      for (const [x0, y0, x1, y1] of this.outline) {
        ctx.moveTo(tx(x0), ty(y0));
        ctx.lineTo(tx(x1), ty(y1));
      }
      ctx.strokeStyle = 'rgba(20,14,0,0.75)';
      ctx.lineWidth = 5;
      ctx.stroke();
      ctx.strokeStyle = '#ffd34d';
      ctx.lineWidth = 2.5;
      ctx.stroke();
    }
    // 선택한 층 항목의 칸 (아이콘이 깃발에 가려져도 어디인지 보이게)
    if (this.selItem && this.selItem.cell != null && this.selItem.cell >= 0) {
      ctx.beginPath();
      grid.pathHex(ctx, this.selItem.cell, s, cam.x - cam.vw / 2 / s, cam.y - cam.vh / 2 / s);
      ctx.strokeStyle = 'rgba(20,14,0,0.8)';
      ctx.lineWidth = 4.5;
      ctx.stroke();
      ctx.strokeStyle = '#ffd34d';
      ctx.lineWidth = 2.2;
      ctx.stroke();
    }
    if (this.hoverCell >= 0 && !exporting) {
      ctx.beginPath();
      grid.pathHex(ctx, this.hoverCell, s, cam.x - cam.vw / 2 / s, cam.y - cam.vh / 2 / s);
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }

  footprintOutline(cells) {
    const set = new Set(cells);
    const segs = [];
    const G = this.grid;
    for (const i of cells) {
      const nb = G.neighborSlots(i);
      for (let d = 0; d < 6; d++) {
        if (set.has(nb[d])) continue;
        const [a, b] = EDGE_CORNERS[d];
        segs.push([G.cx[i] + G.corner[a][0], G.cy[i] + G.corner[a][1], G.cx[i] + G.corner[b][0], G.cy[i] + G.corner[b][1]]);
      }
    }
    return segs;
  }

  cityOfCell(i) {
    if (i < 0 || this.world.owner[i] < 0) return null;
    const id = this.countyCity[this.world.county[i]];
    return id >= 0 ? this.cityById.get(id) : null;
  }

  // ---------- 선택 ----------
  selectCity(id, fly = false) {
    const c = this.cityById.get(id);
    if (!c) return;
    this.selItem = null;
    this.selRoute = null;
    this.selCity = id;
    this.selState = null;
    this.outline = this.footprintOutline(c.footprint);
    this.panel.showCity(c);
    this.announce(`${c.name} 도시 패널. 인구 ${c.population.toLocaleString('ko-KR')}명.${this.lensSummary(c.sgg)}`);
    if (fly) {
      const xs = c.footprint.map((i) => this.grid.cx[i]), ys = c.footprint.map((i) => this.grid.cy[i]);
      const ext = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)) + this.grid.W * 4;
      const sc = Math.min(this.cam.maxScale * 0.8, Math.min(this.cam.vw, this.cam.vh) / ext);
      this.flyTo(c.x, c.y, Math.max(sc, this.cam.scale * 0.999));
    }
    this.requestDraw();
  }

  selectState(code, fly = false) {
    const s = this.stateByCode.get(code);
    if (!s) return;
    this.selItem = null;
    this.selRoute = null;
    this.selCity = null;
    this.selState = code;
    const idx = this.world.states.findIndex((x) => x.code === code);
    const cells = [];
    for (let i = 0; i < this.grid.n; i++) if (this.world.owner[i] === idx) cells.push(i);
    this.outline = this.footprintOutline(cells);
    this.panel.showState(s);
    this.announce(`${s.name} 시도 패널. 인구 ${s.population.toLocaleString('ko-KR')}명.${this.lensSummary(this.world.counties.filter((x) => x.sido === code).map((x) => x.code))}`);
    if (fly) {
      const xs = cells.map((i) => this.grid.cx[i]), ys = cells.map((i) => this.grid.cy[i]);
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
      const sc = Math.min(this.cam.maxScale * 0.6, Math.min(this.cam.vw / (x1 - x0 + 200), this.cam.vh / (y1 - y0 + 200)));
      this.flyTo((x0 + x1) / 2, (y0 + y1) / 2, sc);
    }
    this.requestDraw();
  }

  // 층 항목 (아이콘) 선택: 항목 패널. 위치가 없는 항목(댐)은 패널만 연다
  selectItem(it, fly = false) {
    if (!it) return;
    this.selItem = it;
    this.selRoute = null;
    this.selCity = null;
    this.selState = null;
    this.outline = null;
    if (it.kind === 'national_park') {
      const p = this.layers.wonders.parks.find((x) => x.id === it.ref);
      if (p) this.outline = this.footprintOutline(p.cells);
    }
    this.panel.showItem(it);
    this.announce(`${it.name} 항목 패널.`);
    if (fly && it.cell != null && it.cell >= 0) {
      const sc = Math.max(this.cam.scale, Math.min(this.cam.maxScale * 0.55, this.cam.minScale * 5));
      this.flyTo(this.grid.cx[it.cell], this.grid.cy[it.cell], sc);
    }
    this.requestDraw();
  }

  // 교역로 구간 선택: 구간 패널, 두 시도 영토 테두리
  selectRoute(rt, fly = false) {
    if (!rt) return;
    this.selRoute = rt;
    this.selItem = null;
    this.selCity = null;
    this.selState = null;
    if (!this.layerVisible('trade', 'routes')) { this.layerOn.trade = true; this.subOff.delete('routes'); this.layerctl.render(); }
    const cells = [];
    for (const code of [rt.a, rt.b]) {
      const idx = this.world.states.findIndex((x) => x.code === code);
      for (let i = 0; i < this.grid.n; i++) if (this.world.owner[i] === idx) cells.push(i);
    }
    this.outline = this.footprintOutline(cells);
    this.panel.showRoute(rt);
    if (fly) {
      const x0 = Math.min(rt.ax, rt.bx), x1 = Math.max(rt.ax, rt.bx), y0 = Math.min(rt.ay, rt.by), y1 = Math.max(rt.ay, rt.by);
      const sc = Math.min(this.cam.maxScale * 0.5, Math.min(this.cam.vw / (x1 - x0 + 500), this.cam.vh / (y1 - y0 + 500)));
      this.flyTo((x0 + x1) / 2, (y0 + y1) / 2, sc);
    }
    this.requestDraw();
  }

  // 데이터 기준 시점 (nation.json presets, 7b #20): 렌즈·층·대상·위치를 한 번에. 새 해시 키 없이 v·lens·ly·hide·city·route 로 남는다
  applyPreset(id) {
    const P = this.nation.presets, p = P && P.items.find((x) => x.id === id);
    if (!p) return;
    this.setLens(p.lens || null);
    for (const k of Object.keys(this.layerOn)) this.layerOn[k] = p.ly ? p.ly.includes(k) : LAYER_DEFAULT[k];
    this.subOff = new Set(p.hide || []);
    this.layerctl.render();
    const sc = Math.min(this.cam.maxScale, Math.max(this.cam.minScale, this.cam.minScale * p.z));
    const shift = this.cam.vw > 700 && (p.city != null || p.route) ? 180 / sc : 0;
    if (p.city != null) this.selectCity(p.city);
    else if (p.route) {
      const rt = this.layerR && this.layerR.routeById.get(p.route);
      if (rt) this.selectRoute(rt); else this.pendingRoute = p.route;
    }
    this.flyTo(p.x + shift, p.y, sc);
    this.panel.focus();
  }

  showNation() {
    this.selRoute = null;
    this.selCity = null;
    this.selState = null;
    this.outline = null;
    this.panel.showNation();
    this.requestDraw();
  }

  clearSelection() {
    this.selItem = null;
    this.selRoute = null;
    this.selCity = null;
    this.selState = null;
    this.outline = null;
    this.panel.hide();
    this.requestDraw();
  }

  // 화면 낭독기용 상태 문장 (감사 10): 선택한 지역·켜진 렌즈와 그 지역의 렌즈 값
  announce(text) {
    const el = document.getElementById('a11y-status');
    if (el) el.textContent = text;
  }

  lensSummary(sgg) {
    const L = this.lens;
    if (!L || !L.by_county) return L ? ` 렌즈 ${L.name}: 칸 값 렌즈라 지역 값은 지도에서 칸을 가리켜 본다.` : '';
    const ks = sgg.map((c) => this.countyIndex.get(c));
    const vals = ks.map((k) => L.by_county[k]).filter((v) => v != null);
    if (!vals.length) return ` 렌즈 ${L.name}: 자료 없음.`;
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const units = [...new Set(ks.map((k) => unitOf(L, k)).filter(Boolean).map((u) => u.label))];
    return ` 렌즈 ${L.name}: ${lo === hi ? valueWithUnit(lo, L) : `${valueWithUnit(lo, L)}–${valueWithUnit(hi, L)} (시군구별 범위)`}${units.length ? ` · ${units.join(', ')}` : ''}.`;
  }

  retiredNear(id) {
    return [...this.retiredById.values()].filter((x) => x.near === id);
  }

  layerVisible(group, sub) {
    return !!this.layerOn[group] && !this.subOff.has(sub);
  }

  toggleLayerGroup(id) {
    this.layerOn[id] = !this.layerOn[id];
    this.layerctl.render();
    this.requestDraw();
  }

  // 지형(null) + 렌즈 막대 순서 (L / Shift+L)
  stepLens(d) {
    const ids = [null, ...this.lenses.lenses.map((l) => l.id)];
    const k = ids.indexOf(this.lens ? this.lens.id : null);
    this.setLens(ids[(k + d + ids.length) % ids.length]);
  }

  toast(msg) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => { el.hidden = true; }, 3800);
  }

  setLens(id) {
    // 6단계에서 렌즈 막대에서 뺀 렌즈의 id (옛 공유 링크): 가장 가까운 남은 렌즈로, 모르는 id 는 지형으로
    const removed = this.lenses.removed || {};
    if (id && !this.lensById.has(id) && Object.prototype.hasOwnProperty.call(removed, id)) {
      // 이 판에서 뺀 렌즈(공개판의 아파트·침엽수림)의 옛 링크: 까닭을 알리고 가까운 렌즈(있으면)나 지형으로
      const g = removed[id], near = g.near && this.lensById.has(g.near) ? g.near : null;
      this.toast(`'${g.name || id}' 렌즈는 이 판에서는 제공하지 않습니다${near ? ` — '${this.lensById.get(near).name}' 렌즈로 보여 줍니다` : ' — 지형으로 보여 줍니다'}. 까닭은 연감 › 출처.`);
      id = near;
    } else if (id && !this.lensById.has(id)) {
      const near = this.lenses.retired && this.lenses.retired[id];
      const old = this.retiredById.get(id);
      if (near && this.lensById.has(near)) {
        this.toast(`'${old ? old.name : id}' 렌즈는 정리되어 '${this.lensById.get(near).name}' 렌즈로 보여 줍니다. 값은 도시 패널과 툴팁에 있습니다.`);
        id = near;
      } else {
        this.toast(`'${id}' 렌즈를 찾지 못해 지형으로 보여 줍니다.`);
        id = null;
      }
    }
    this.lens = id ? this.lensById.get(id) || null : null;
    if (this.lens) ensureValues(this.lens, this.world);
    this.terrain.setLens(this.lens);
    this.lensbar.update();
    this.announce(this.lens ? `렌즈 ${this.lens.name} (${this.lens.unit || '범주'}). ${this.lens.description}` : '지형 보기.');
    this.requestDraw();
  }

  flyTo(x, y, scale, ms = 650) {
    const c = this.cam;
    const from = { x: c.x, y: c.y, s: c.scale };
    const to = { x, y, s: Math.min(c.maxScale, Math.max(c.minScale, scale)) };
    // 동작 줄이기 설정이면 보간 없이 바로 옮긴다 (감사 19)
    if (ms <= 0 || (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches)) {
      if (this.anim) cancelAnimationFrame(this.anim);
      this.anim = 0;
      c.scale = to.s;
      c.x = x;
      c.y = y;
      c.clamp();
      this.lastZoom = 0;
      this.requestDraw();
      return;
    }
    const t0 = performance.now();
    const step = () => {
      const t = Math.min(1, (performance.now() - t0) / ms);
      const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      // 로그 공간에서 확대 비율 보간
      c.scale = Math.exp(Math.log(from.s) + (Math.log(to.s) - Math.log(from.s)) * e);
      c.x = from.x + (to.x - from.x) * e;
      c.y = from.y + (to.y - from.y) * e;
      c.clamp();
      this.lastZoom = performance.now();
      this.requestDraw();
      if (t < 1) this.anim = requestAnimationFrame(step);
      else {
        this.anim = 0;
        this.lastZoom = 0;
        this.requestDraw();
      }
    };
    if (this.anim) cancelAnimationFrame(this.anim);
    this.anim = requestAnimationFrame(step);
  }

  // ---------- 입력 ----------
  bindInput() {
    const cv = this.canvas;
    const pts = new Map();
    let drag = null, pinch = null, moved = 0;
    cv.addEventListener('pointerdown', (e) => {
      cv.setPointerCapture(e.pointerId);
      pts.set(e.pointerId, [e.offsetX, e.offsetY]);
      moved = 0;
      if (pts.size === 1) drag = [e.offsetX, e.offsetY];
      if (pts.size === 2) {
        const [a, b] = [...pts.values()];
        pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), m: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] };
        drag = null;
      }
    });
    cv.addEventListener('pointermove', (e) => {
      if (pts.has(e.pointerId)) pts.set(e.pointerId, [e.offsetX, e.offsetY]);
      if (pinch && pts.size === 2) {
        const [a, b] = [...pts.values()];
        const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        const m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        this.cam.pan(m[0] - pinch.m[0], m[1] - pinch.m[1]);
        this.cam.zoomAt(d / pinch.d, m[0], m[1]);
        pinch = { d, m };
        moved += 10;
        this.lastZoom = performance.now();
        this.requestDraw();
        return;
      }
      if (drag) {
        const dx = e.offsetX - drag[0], dy = e.offsetY - drag[1];
        moved += Math.abs(dx) + Math.abs(dy);
        if (moved > 4) {
          this.cam.pan(dx, dy);
          cv.classList.add('dragging');
          this.tooltip.hide();
          this.requestDraw();
        }
        drag = [e.offsetX, e.offsetY];
        return;
      }
      this.hover(e.offsetX, e.offsetY, e);
    });
    const end = (e) => {
      const wasClick = pts.size === 1 && moved <= 4 && e.type === 'pointerup';
      pts.delete(e.pointerId);
      if (pts.size < 2) pinch = null;
      if (pts.size === 0) drag = null;
      cv.classList.remove('dragging');
      if (wasClick) this.click(e.offsetX, e.offsetY, e.pointerType === 'touch');
    };
    cv.addEventListener('pointerup', end);
    cv.addEventListener('pointercancel', end);
    cv.addEventListener('pointerleave', () => {
      this.hoverCell = -1;
      this.hoverCity = null;
      this.tooltip.hide();
      this.requestDraw();
    });
    cv.addEventListener(
      'wheel',
      (e) => {
        e.preventDefault();
        const k = Math.exp(-Math.max(-120, Math.min(120, e.deltaY)) * 0.0022);
        this.cam.zoomAt(k, e.offsetX, e.offsetY);
        this.lastZoom = performance.now();
        this.tooltip.hide();
        this.requestDraw();
      },
      { passive: false },
    );
    cv.addEventListener('dblclick', (e) => {
      const [wx, wy] = this.cam.toWorld(e.offsetX, e.offsetY);
      this.flyTo(wx, wy, this.cam.scale * 2, 350);
    });
    window.addEventListener('keydown', (e) => {
      if (e.target.closest && e.target.closest('input, textarea, select, [contenteditable]')) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      // 도시 패널 탭 바의 화살표는 탭 이동 (지도를 옮기지 않음)
      if (e.key.startsWith('Arrow') && e.target.closest && e.target.closest('[role="tablist"], [role="tab"]')) return;
      const step = 90;
      const k = e.key, c = e.code;
      if (k === '/') {
        e.preventDefault();
        this.search.open();
      } else if (k === '?') {
        e.preventDefault();
        this.help.toggle();
      } else if (k === 'Escape') this.escape();
      else if (c === 'KeyL') this.stepLens(e.shiftKey ? -1 : 1);
      else if (c === 'KeyR' && !e.shiftKey) this.toggleLayerGroup('resources');
      else if (k === 'ArrowLeft' || c === 'KeyA') this.cam.pan(step, 0);
      else if (k === 'ArrowRight' || c === 'KeyD') this.cam.pan(-step, 0);
      else if (k === 'ArrowUp' || c === 'KeyW') this.cam.pan(0, step);
      else if (k === 'ArrowDown' || c === 'KeyS') this.cam.pan(0, -step);
      else if (k === '+' || k === '=') this.flyTo(this.cam.x, this.cam.y, this.cam.scale * 1.6, 250);
      else if (k === '-' || k === '_') this.flyTo(this.cam.x, this.cam.y, this.cam.scale / 1.6, 250);
      else return;
      if (k.startsWith('Arrow')) e.preventDefault();
      this.requestDraw();
    });
  }

  // Esc: 도움말 → 공유 메뉴 → 찾기 → 연감 → 보고서 → 패널 순으로 하나씩 닫는다
  escape() {
    if (this.panel.closeNote && this.panel.closeNote()) return;
    if (this.share.closePreview && this.share.closePreview()) return;
    if (this.topbar.menu && !this.topbar.menu.hidden) this.topbar.closeMenu();
    else if (this.help.isOpen()) this.help.close();
    else if (this.share.isOpen()) this.share.close(true);
    else if (!this.search.el.hidden) this.search.close();
    else if (this.almanac.isOpen()) this.almanac.close();
    else if (this.report.isOpen()) this.report.close();
    else this.clearSelection();
  }

  hover(sx, sy, e) {
    const b = this.banners.hit(sx, sy);
    const [wx, wy] = this.cam.toWorld(sx, sy);
    const cell = this.grid.pointToCell(wx, wy);
    const ic = b || !this.layerR ? null : this.layerR.hit(sx, sy, !!(e && e.pointerType === 'touch'));
    const rt = b || ic || !this.layerR ? null : this.layerR.hitRoute(sx, sy);
    const lab = b || ic || rt ? null : this.labels.hit(sx, sy);
    const changed = cell !== this.hoverCell || (b && b.id) !== this.hoverCity;
    this.hoverCell = cell;
    this.hoverCity = b ? b.id : null;
    this.canvas.style.cursor = b || ic || rt || lab || (cell >= 0 && this.world.owner[cell] >= 0) ? 'pointer' : 'grab';
    if (b) this.tooltip.showCity(b, e.clientX, e.clientY);
    else if (ic) this.tooltip.showItem(ic.it, ic.others, e.clientX, e.clientY, ic.ox != null);
    else if (rt) this.tooltip.showRoute(rt, e.clientX, e.clientY);
    else if (lab) this.tooltip.showState(lab, e.clientX, e.clientY);
    else this.tooltip.showCell(cell, e.clientX, e.clientY);
    if (changed) this.requestDraw();
  }

  click(sx, sy, touch = false) {
    const b = this.banners.hit(sx, sy);
    if (b) return this.selectCity(b.id);
    const ic = this.layerR ? this.layerR.hit(sx, sy, touch) : null;
    if (ic) return this.selectItem(ic.it);
    const rt = this.layerR ? this.layerR.hitRoute(sx, sy) : null;
    if (rt) return this.selectRoute(rt);
    const lab = this.labels.hit(sx, sy);
    if (lab) return this.selectState(lab.code);
    // 빈 땅(깃발·아이콘·선·이름표가 아닌 곳)을 누르면 그 칸의 시도 패널 (6단계 명세 A2). 도시는 깃발·검색·시도 패널 목록으로
    const [wx, wy] = this.cam.toWorld(sx, sy);
    const cell = this.grid.pointToCell(wx, wy);
    if (cell >= 0 && this.world.owner[cell] >= 0) this.selectState(this.world.states[this.world.owner[cell]].code);
    else this.clearSelection();
  }

  // ---------- URL 해시 ----------
  writeHash() {
    if (!this.hashReady) return;
    const c = this.cam;
    const p = new URLSearchParams();
    p.set('v', `${Math.round(c.x)},${Math.round(c.y)},${c.scale.toFixed(4)}`);
    if (this.lens) p.set('lens', this.lens.id);
    if (this.selItem) p.set('item', this.selItem.id);
    else if (this.selRoute) p.set('route', this.selRoute.id);
    else if (this.selCity != null) {
      p.set('city', String(this.selCity));
      if (this.panelTab && this.panelTab !== 'overview') p.set('tab', this.panelTab);
    }
    else if (this.selState) p.set('state', this.selState);
    else if (this.panel.mode === 'nation') p.set('report', '1');
    if (Object.entries(this.layerOn).some(([k, v]) => v !== LAYER_DEFAULT[k])) p.set('ly', Object.keys(this.layerOn).filter((k) => this.layerOn[k]).join(','));
    if (this.subOff.size) p.set('hide', [...this.subOff].sort().join(','));
    const h = '#' + p.toString();
    if (h !== this.lastHash) {
      this.lastHash = h;
      // 신여지도 고리는 늘 지금 해시를 단다 (topbar.js)
      const alt = document.querySelector('#topbar .altfe');
      if (alt) alt.setAttribute('href', 'yeojido/index.html' + h);
      clearTimeout(this.hashTimer);
      this.hashTimer = setTimeout(() => history.replaceState(null, '', h), 150);
    }
  }

  // 층 상태: 새 형식(ly=켠 묶음, hide=끈 세부). ly 가 없고 옛 off=/on= 이 있으면 옛 키를 새 묶음·세부로 옮긴다
  readLayers(p) {
    Object.assign(this.layerOn, LAYER_DEFAULT);
    this.subOff = new Set((p.get('hide') || '').split(',').filter(Boolean));
    if (p.has('ly')) {
      const on = p.get('ly').split(',');
      for (const k of Object.keys(this.layerOn)) this.layerOn[k] = on.includes(k);
      return;
    }
    for (const k of (p.get('off') || '').split(',').filter(Boolean)) {
      const m = LEGACY_OFF[k];
      if (!m) continue;
      if (m.group) this.layerOn[m.group] = false;
      for (const s_ of m.subs || []) this.subOff.add(s_);
    }
    for (const k of (p.get('on') || '').split(',').filter(Boolean)) if (LEGACY_ON[k]) this.layerOn[LEGACY_ON[k]] = true;
  }

  // 해시 전체를 한 상태로 읽어 한 번에 적용한다 (감사 11): 빈 값·없는 id 는 무시하고, 값이 유효한 대상 중 우선순위가 높은 것
  // (item > route > city > state > report=1)을 고른다. 대상 키가 하나도 유효하지 않으면 이전 선택을 비운다.
  readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    clearTimeout(this.hashTimer);
    const v = (p.get('v') || '').split(',').map((x) => (x.trim() === '' ? NaN : Number(x)));
    if (v.length === 3 && v.every(Number.isFinite) && v[2] > 0) {
      this.cam.x = v[0];
      this.cam.y = v[1];
      this.cam.scale = v[2];
      this.cam.clamp();
    }
    this.setLens(p.get('lens') || null);
    this.readLayers(p);
    if (this.layerctl) this.layerctl.render();
    const str = (k) => { const x = p.get(k); return x != null && x.trim() !== '' ? x.trim() : null; };
    const item = str('item'), route = str('route'), city = str('city'), state = str('state');
    const cityId = city != null && /^\d+$/.test(city) && this.cityById.has(Number(city)) ? Number(city) : null;
    const stateOk = state != null && this.stateByCode.has(state) ? state : null;
    // 층 자료가 아직 없으면 item·route 는 기다렸다가(setLayers) 유효할 때 고르고, 그동안은 다음 순위 대상을 연다
    this.pendingItem = item && !this.layers ? item : null;
    this.pendingRoute = route && !this.layers ? route : null;
    const it = item && this.layerR ? this.layerR.byId.get(item) : null;
    const rt = route && this.layerR ? this.layerR.routeById.get(route) : null;
    if (it) this.selectItem(it);
    else if (rt) this.selectRoute(rt);
    else if (cityId != null) {
      const tb = str('tab');
      this.panelTab = TAB_IDS.includes(tb) ? tb : 'overview';
      this.selectCity(cityId);
    }
    else if (stateOk) this.selectState(stateOk);
    else if (p.get('report') === '1') this.showNation();
    else if (this.selItem || this.selRoute || this.selCity != null || this.selState || (this.panel && this.panel.mode)) this.clearSelection();
    this.hashReady = true;
    this.lastHash = null;
    this.requestDraw();
  }
}

App.prototype.setLayers = function (L) {
  this.layers = L;
  this.layerR = new LayerRenderer(this, L);
  this.layerctl.render();
  this.search.addLayers(L, this.layerR);
  const pi = this.pendingItem, pr = this.pendingRoute;
  this.pendingItem = this.pendingRoute = null;
  if (pi && this.layerR.byId.has(pi)) this.selectItem(this.layerR.byId.get(pi));
  else if (pr && this.layerR.routeById.has(pr)) this.selectRoute(this.layerR.routeById.get(pr));
  else if (this.panel.mode === 'nation') this.panel.showNation();
  else if (this.panel.mode === 'city' && this.selCity != null) this.panel.showCity(this.cityById.get(this.selCity));
  else if (this.panel.mode === 'state' && this.selState) this.panel.showState(this.stateByCode.get(this.selState));
  this.requestDraw();
};

// 층 파일은 하나씩 따로 받는다. 빠진 파일은 빈 자리로 두고 화면 위에 실패 범위와 '다시 시도'를 보인다 (감사 08)
async function loadLayers(app, only = null) {
  const names = only || LAYER_FILES;
  const { data, failed } = await fetchAll(names);
  const prev = app.layers || {};
  const out = {};
  for (const f of LAYER_FILES) {
    if (f in data) out[f] = data[f];
    else if (names.includes(f)) out[f] = LAYER_EMPTY[f]();
    else out[f] = prev[f];
  }
  app.layerFailed = Object.fromEntries(Object.entries({ ...(app.layerFailed || {}), ...Object.fromEntries(names.map((f) => [f, null])), ...failed }).filter(([, v]) => v));
  app.setLayers(out);
  app.showLoadStatus();
}

// 화면 위 안내: 불러오지 못한 파일과 다시 시도
App.prototype.showLoadStatus = function () {
  const el = document.getElementById('loadwarn');
  const fail = { ...(this.loadFailed || {}), ...(this.layerFailed || {}) };
  const names = Object.keys(fail);
  if (!names.length) { el.hidden = true; return; }
  const what = { sources: '출처 목록(연감 › 출처·그림 출처 줄)', wonders: '불가사의 층', resources: '자원 층', infrastructure: '기반시설 층(공항·항만·역·도로)', frontier: '접경 층', trade: '교역 층(교역로·수출입 품목)' };
  el.innerHTML = `<span>일부 자료를 불러오지 못했습니다: ${names.map((f) => `${what[f] || f} <small>${String(fail[f]).replace(/[&<>"]/g, '')}</small>`).join(', ')}. 나머지는 그대로 볼 수 있습니다.</span> <button type="button" data-retry>다시 시도</button>`;
  el.hidden = false;
  el.querySelector('[data-retry]').onclick = () => this.retryLoad();
};

App.prototype.retryLoad = async function () {
  const lf = Object.keys(this.layerFailed || {}), of = Object.keys(this.loadFailed || {});
  if (of.length) {
    const { data, failed } = await fetchAll(of);
    for (const [f, v] of Object.entries(data)) this[f] = v;
    this.loadFailed = failed;
    if (this.share) this.share._by = null;
    this.lensbar.update();
    if (this.almanac.isOpen()) this.almanac.open();
  }
  if (lf.length) await loadLayers(this, lf);
  else this.showLoadStatus();
};

load()
  .then((d) => {
    window.app = new App(d);
    document.body.classList.add('ready');
    window.app.showLoadStatus();
    // 첫 화면을 그린 다음 프레임에 층을 불러온다
    requestAnimationFrame(() => setTimeout(() => loadLayers(window.app).catch((e) => console.error('층 불러오기 실패', e)), 0));
  })
  .catch((e) => {
    console.error(e);
    const el = document.getElementById('loading');
    el.textContent = '불러오기 실패: ' + e.message + ' ';
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = '다시 시도';
    b.onclick = () => location.reload();
    el.appendChild(b);
  });
