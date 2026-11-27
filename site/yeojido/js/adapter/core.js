// 자료 어댑터 (핵심부) — ../data/*.json 의 모양을 읽는 곳은 js/adapter/ 뿐이다.
// 화면 모듈은 여기서 만든 모형(D)만 읽는다. 자료 모양이 바뀌면 이 폴더만 고친다.
// 파일 하나가 실패해도 나머지로 지도를 띄우고, 실패한 파일 이름을 D.failed 에 남긴다.

const BASE = new URL('../../../data/', import.meta.url);

async function getJSON(name) {
  const r = await fetch(new URL(`${name}.json`, BASE));
  if (!r.ok) throw new Error(`${name}.json (${r.status})`);
  return r.json();
}

const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const arr = (v) => (Array.isArray(v) ? v : []);

function bbox(pts) {
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (let k = 0; k + 1 < pts.length; k += 2) {
    if (pts[k] < x0) x0 = pts[k]; if (pts[k] > x1) x1 = pts[k];
    if (pts[k + 1] < y0) y0 = pts[k + 1]; if (pts[k + 1] > y1) y1 = pts[k + 1];
  }
  return [x0, y0, x1, y1];
}

// ---------- 세계(칸) ----------
function buildWorld(w) {
  const g = w.grid || {};
  const n = arr(w.owner).length;
  const W = {
    version: w.version || '',
    cols: g.cols, rows: g.rows, radius: g.radius, n,
    metersPerUnit: num(w.meters_per_unit) ?? 112,
    hexKm2: num(w.hex_km2),
    owner: Int16Array.from(arr(w.owner)),
    county: Int16Array.from(arr(w.county)),
    foreign: Uint8Array.from(arr(w.foreign)),
    water: Uint8Array.from(arr(w.water)),
    relief: Uint8Array.from(arr(w.relief)),
    landFrac: Float32Array.from(arr(w.land_frac).map((v) => v ?? 0)),
    elev: Float32Array.from(arr(w.elev).map((v) => (v == null ? NaN : v))),
    elevKnown: Uint8Array.from(arr(w.elev).map((v) => (v == null ? 0 : 1))),
    cover: Uint8Array.from(arr(w.cover)),
    coverKeys: arr(w.cover_keys),
    states: arr(w.states).map((s) => ({ code: String(s.code), name: s.name, short: s.short || s.name })),
    counties: arr(w.counties).map((c) => ({ code: String(c.code), name: c.name, sido: String(c.sido) })),
    rivers: arr(w.rivers).map((r) => ({ name: r.name || '', tier: r.tier ?? 2, main: !!r.main, grade: r.grade || '', lenKm: num(r.len_km), pts: arr(r.pts), bb: bbox(arr(r.pts)) })),
    riverLabels: arr(w.river_labels).map((l) => ({ name: l.name, x: l.x, y: l.y, angle: l.angle || 0 })),
    lakes: arr(w.lakes).map((l) => ({ name: l.name || '', areaKm2: num(l.area_km2), rings: arr(l.rings), bb: arr(l.rings).map(bbox).reduce((a, b) => [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])], [1e9, 1e9, -1e9, -1e9]) })),
    lakeLabels: arr(w.lake_labels).map((l) => ({ name: l.name, x: l.x, y: l.y, areaKm2: num(l.area_km2), kind: l.kind || '' })),
    tables: w.tables || {},
    notes: arr((w.tables || {}).notes),
    coverMeta: w.cover_meta || {},
    tidalMeta: w.tidal ? { year: w.tidal.year, areaKm2: num(w.tidal.polygon_area_km2) } : null,
    riverMeta: w.river_meta || {},
    lakeMeta: w.lake_meta || {},
  };
  // 피복 비율 (육지 칸만 실려 온다 -> 칸 배열로 펼침). 값은 0..1, 없으면 NaN
  const cs = w.cover_share || {};
  const lc = arr(cs.land_cells);
  W.landCells = Int32Array.from(lc);
  W.coverNames = cs.names || {};
  W.coverRule = cs.rule || '';
  W.share = {};
  for (const k of arr(cs.keys)) {
    const a = new Float32Array(n).fill(NaN), src = arr(cs[k]);
    for (let t = 0; t < lc.length; t++) if (src[t] != null) a[lc[t]] = src[t] / 100;
    W.share[k] = a;
  }
  W.coverSrc = new Uint8Array(n); // 0 없음, 1 도엽 통계(기후에너지환경부), 2 ESA …
  // 번호가 아니라 kinds 이름으로 읽는다: 1 = 도엽 통계(me), 2 = ESA. (옛 공개판 빌드는 kinds = ['esa'] 뿐)
  const srcKinds = w.cover_src ? arr(w.cover_src.kinds) : [];
  if (w.cover_src) arr(w.cover_src.src).forEach((v, t) => { if (v != null) W.coverSrc[lc[t]] = srcKinds[v] === 'me' ? 1 : 2; });
  W.coverSrcNames = w.cover_src ? (srcKinds[0] === 'me' ? arr(w.cover_src.names) : [null].concat(arr(w.cover_src.names))) : [];
  W.coverPublic = !!(w.cover_meta && w.cover_meta.profile === 'public');
  W.crop = new Array(n).fill(null);
  if (w.crop_kind) arr(w.crop_kind.cells).forEach((c, t) => { const k = w.crop_kind.kind[t]; W.crop[c] = k == null ? null : w.crop_kind.keys[k]; });
  W.forest = new Array(n).fill(null);
  if (w.forest_kind) arr(w.forest_kind.cells).forEach((c, t) => { W.forest[c] = w.forest_kind.keys[w.forest_kind.kind[t]]; });
  W.tidal = new Float32Array(n);
  if (w.tidal) arr(w.tidal.cells).forEach((c, t) => { W.tidal[c] = w.tidal.share[t]; });
  W.stateIndex = new Map(W.states.map((s, k) => [s.code, k]));
  W.countyIndex = new Map(W.counties.map((c, k) => [c.code, k]));
  // 칸의 으뜸 피복 열쇠 (논·밭·활엽 … 까지 내려감). 없으면 null
  W.coverKind = (i) => {
    const c = W.cover[i];
    if (!c) return null;
    const k = W.coverKeys[c - 1];
    if (k === 'crop') return W.crop[i] || 'crop';
    if (k === 'forest') return W.forest[i] || 'forest';
    return k;
  };
  const tname = (tbl, id) => { const r = arr(W.tables[tbl]).find((x) => x.id === id); return r ? r.name : null; };
  W.waterName = (i) => tname('water', W.water[i]);
  W.reliefName = (i) => tname('relief', W.relief[i]);
  W.coverName = (i) => { const k = W.coverKind(i); return k ? W.coverNames[k] || k : null; };
  return W;
}

// ---------- 고을·시도 (지도에 필요한 것만. 장(패널)용 자세한 값은 places.js) ----------
function buildCities(list, W) {
  return arr(list).map((c) => ({
    id: c.id, name: c.name, full: c.full || c.name, sido: String(c.sido), kind: c.kind || '', capital: c.capital && c.capital !== '없음' ? c.capital : '',
    x: c.x, y: c.y, cell: c.cell, footprint: arr(c.footprint), sgg: arr(c.sgg).map(String),
    pop: num(c.population), raw: c,
  }));
}
function buildStates(list) {
  return arr(list).map((s) => ({ code: String(s.code), name: s.name, short: s.short || s.name, label: s.label || null, pop: num(s.population), cityIds: arr(s.cities), raw: s }));
}

// ---------- 렌즈 ----------
function buildLenses(L, W) {
  const groups = arr(L.groups).map((g) => ({ id: g.id, name: g.name, lenses: [] }));
  const gById = new Map(groups.map((g) => [g.id, g]));
  const list = arr(L.lenses).map((l) => {
    const lens = {
      id: l.id, group: l.group, name: l.name, unit: l.unit || '', format: l.format || '', scale: l.scale || 'linear',
      domain: arr(l.domain), center: num(l.center), breaks: arr(l.breaks), binLabels: arr(l.bin_labels), categories: arr(l.categories),
      higherIs: l.higher_is || 'neutral', source: l.source || '', description: l.description || '', basis: l.basis || '', vintage: l.vintage || '',
      level: l.level || '', units: arr(l.units), dataRamp: arr(l.ramp), raw: l, _values: null,
    };
    (gById.get(l.group) || (groups.push({ id: l.group, name: l.group, lenses: [] }), gById.set(l.group, groups[groups.length - 1]), groups[groups.length - 1])).lenses.push(lens);
    return lens;
  });
  const retired = L.retired || {};
  const retiredItems = arr((L.retired_values || {}).items);
  // 그 판에서 뺀 렌즈 (공개판의 아파트 매매가·전세가): id -> { name, near, reason }
  const removed = L.removed && typeof L.removed === 'object' ? L.removed : {};
  return { groups, list, byId: new Map(list.map((l) => [l.id, l])), retired, retiredItems, removed, retiredRule: (L.retired_values || {}).rule || '', notes: arr(L.notes), vintage: L.vintage || '', level: L.level || '',
    cellPop: arr(L.cell_pop) };
}

// 렌즈의 칸 값 배열 (없으면 null). 세 가지 실림 꼴(values / land_values / by_county)을 한 꼴로 편다.
export function lensValues(lens, W) {
  if (lens._values) return lens._values;
  const r = lens.raw, n = W.n;
  let v;
  if (Array.isArray(r.values)) v = r.values;
  else if (Array.isArray(r.land_values)) { v = new Array(n).fill(null); for (let t = 0; t < W.landCells.length; t++) v[W.landCells[t]] = r.land_values[t]; }
  else if (Array.isArray(r.by_county)) { v = new Array(n).fill(null); for (let i = 0; i < n; i++) if (W.owner[i] >= 0) v[i] = r.by_county[W.county[i]] ?? null; }
  else v = new Array(n).fill(null);
  lens._values = v;
  return v;
}
// 시군구 값이 더 큰 공표 단위(개편 전 구 등)의 값이면 그 단위 기록, 아니면 null
export function lensUnitOf(lens, countyIdx) {
  if (!lens || !lens.units.length || countyIdx == null || countyIdx < 0) return null;
  if (!lens._unitBy) { lens._unitBy = new Map(); for (const u of lens.units) for (const c of arr(u.counties)) lens._unitBy.set(c, u); }
  return lens._unitBy.get(countyIdx) || null;
}
// 값 -> 0..1 자리 (범주는 번호 그대로, 구간은 구간 번호/구간 수). 없으면 null
export function lensT(lens, v) {
  if (v == null) return null;
  const [lo, hi] = lens.domain;
  switch (lens.scale) {
    case 'log': { const a = Math.log10(Math.max(lo, 0.1)), b = Math.log10(hi); return Math.min(1, Math.max(0, (Math.log10(Math.max(v, 0.1)) - a) / (b - a))); }
    case 'diverging': { const c = lens.center ?? 0; return v >= c ? 0.5 + 0.5 * Math.min(1, (v - c) / (hi - c)) : 0.5 - 0.5 * Math.min(1, (c - v) / (c - lo)); }
    case 'category': return v;
    case 'bins': { let k = 0; while (k < lens.breaks.length && v >= lens.breaks[k]) k++; return k; }
    default: return Math.min(1, Math.max(0, (v - lo) / (hi - lo)));
  }
}
// 0..1 자리 -> 값 (연속 척도의 범례 눈금용)
export function lensInv(lens, t) {
  const [lo, hi] = lens.domain;
  if (lens.scale === 'log') { const a = Math.log10(Math.max(lo, 0.1)), b = Math.log10(hi); return Math.pow(10, a + (b - a) * t); }
  if (lens.scale === 'diverging') { const c = lens.center ?? 0; return t < 0.5 ? c - (c - lo) * (1 - 2 * t) : c + (hi - c) * (2 * t - 1); }
  return lo + (hi - lo) * t;
}
export const lensIsContinuous = (lens) => lens.scale !== 'category' && lens.scale !== 'bins';
// 단계 수 (구간·범주), 연속이면 0
export function lensSteps(lens) {
  if (lens.scale === 'bins') return lens.breaks.length + 1;
  if (lens.scale === 'category') return lens.categories.length;
  return 0;
}
export const SCALE_KO = { log: '로그', linear: '선형', diverging: '발산', bins: '구간', category: '범주' };

// ---------- 층 (첫 화면 뒤에 따로 불러옴) ----------
function buildLayers(raw) {
  const out = { items: [], kinds: {}, parks: [], roads: [], rails: [], zoom: null, frontier: null, trade: null, raw, lineNotes: [] };
  for (const f of ['wonders', 'resources', 'infrastructure']) {
    const d = raw[f];
    if (!d) continue;
    for (const [k, v] of Object.entries(d.kinds || {})) out.kinds[k] = { key: k, file: f, name: v.name || k, group: v.group || '', rule: v.rule || '', year: v.year || '', source: arr(v.source), count: v.count, placed: v.placed, raw: v };
    for (const it of arr(d.items)) out.items.push({ id: it.id, kind: it.kind, name: it.name, cell: it.cell ?? -1, tier: it.tier ?? 2, value: num(it.value), unit: it.unit || '', year: it.year || '', sido: it.sido != null ? String(it.sido) : '', city: it.city ?? null, place: it.place || '', precision: it.precision || '', ref: it.ref || null, detail: arr(it.detail), file: f, raw: it });
  }
  const w = raw.wonders;
  if (w) {
    out.parks = arr(w.parks).map((p) => ({ id: p.id, name: p.name, short: p.short || p.name, cells: arr(p.cells), iconCell: p.icon_cell, areaKm2: num(p.area_km2), marine: !!p.marine, raw: p }));
    out.zoom = w.zoom || null;
    out.worldHeritage = arr(w.world_heritage);
    out.universities = w.universities || null;
  }
  const inf = raw.infrastructure;
  if (inf && inf.lines) {
    out.roads = arr(inf.lines.roads).map((r) => ({ tier: r.tier, route: r.route, pts: arr(r.pts), bb: bbox(arr(r.pts)) }));
    out.rails = arr(inf.lines.rails).map((r) => ({ tier: r.tier, pts: arr(r.pts), bb: bbox(arr(r.pts)) }));
    out.lineNotes = [inf.lines.road_note, inf.lines.note].filter(Boolean);
  }
  if (raw.frontier) out.frontier = { name: raw.frontier.name, rule: raw.frontier.rule || '', year: raw.frontier.year || '', source: arr(raw.frontier.source), areas: arr(raw.frontier.areas).map((a) => ({ name: a.name, sido: String(a.sido), sgg: arr(a.sgg).map(String), city: a.city ?? null, article: a.article || '', clause: a.clause })) };
  if (raw.trade) {
    const R = raw.trade.routes || {};
    out.trade = { raw: raw.trade, year: R.year || '', unit: R.unit || '', mode: R.mode || '', rule: R.rule || '', source: arr(R.source), totals: R.totals || {}, anchors: R.anchors || {},
      segments: arr(R.segments).map((s) => ({ id: `${s.a}-${s.b}`, a: String(s.a), b: String(s.b), ab: num(s.ab), ba: num(s.ba), total: num(s.total), rank: s.rank, share: num(s.share) })) };
  }
  out.byId = new Map(out.items.map((i) => [i.id, i]));
  return out;
}

// ---------- 불러오기 ----------
export async function loadCore(onStep) {
  const names = ['world', 'cities', 'states', 'nation', 'lenses', 'ridges'];
  const raw = {}, failed = [];
  let done = 0;
  await Promise.all(names.map(async (n) => {
    try { raw[n] = await getJSON(n); } catch (e) { failed.push(n); console.warn('자료 불러오기 실패:', e.message); }
    if (onStep) onStep(++done / names.length);
  }));
  if (!raw.world) throw new Error('world.json 을 불러오지 못해 지도를 그릴 수 없습니다.');
  const W = buildWorld(raw.world);
  const D = { world: W, failed, raw };
  D.cities = buildCities(raw.cities, W);
  D.cityById = new Map(D.cities.map((c) => [c.id, c]));
  D.states = buildStates(raw.states);
  D.stateByCode = new Map(D.states.map((s) => [s.code, s]));
  // 시군구(번호) -> 고을 id
  D.countyCity = new Int16Array(W.counties.length).fill(-1);
  for (const c of D.cities) for (const code of c.sgg) { const k = W.countyIndex.get(code); if (k != null) D.countyCity[k] = c.id; }
  D.cityOfCell = (i) => { if (i < 0 || W.owner[i] < 0) return null; const id = D.countyCity[W.county[i]]; return id >= 0 ? D.cityById.get(id) || null : null; };
  D.stateOfCell = (i) => (i >= 0 && W.owner[i] >= 0 ? D.stateByCode.get(W.states[W.owner[i]].code) || null : null);
  D.countyOfCell = (i) => (i >= 0 && W.owner[i] >= 0 ? W.counties[W.county[i]] || null : null);
  D.nationRaw = raw.nation || null;
  D.vintage = raw.nation ? raw.nation.vintage || '' : '';
  D.lenses = buildLenses(raw.lenses || {}, W);
  const rg = raw.ridges;
  D.ridges = rg ? { rule: rg.rule || '', method: rg.method || '', checks: rg.checks || {}, tiers: arr(rg.tiers), source: rg.source || {}, generated: rg.generated || '', version: rg.version || '',
    lines: arr(rg.lines).map((l) => ({ t: l.t, pts: arr(l.pts), z: arr(l.z), bb: bbox(arr(l.pts)) })) } : null;
  D.layers = null;
  D.sources = null;
  return D;
}

export async function loadLayers(D) {
  const names = ['wonders', 'resources', 'infrastructure', 'frontier', 'trade'];
  const raw = {};
  await Promise.all(names.map(async (n) => { try { raw[n] = await getJSON(n); } catch (e) { D.failed.push(n); console.warn('자료 불러오기 실패:', e.message); } }));
  D.layers = buildLayers(raw);
  return D.layers;
}

// 출처 (연감·공유 그림이 처음 필요할 때 불러온다). 실패하면 null
let srcPromise = null;
export function loadSourcesRaw(D) {
  if (!srcPromise) srcPromise = getJSON('sources').catch((e) => { D.failed.push('sources'); console.warn('자료 불러오기 실패:', e.message); return null; });
  return srcPromise;
}
