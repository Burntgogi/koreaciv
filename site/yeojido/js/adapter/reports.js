// 자료 어댑터 (장부·순위 보고서) — nation.json 의 reports 를 화면 모형으로 바꾼다.
// 자료 속 emoji 필드는 쓰지 않는다. 값이 없으면 null (0 으로 바꾸지 않는다).

const arr = (v) => (Array.isArray(v) ? v : []);
const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);

// 보고서 id -> 아이콘 이름 (icons.js). 모르는 id 는 almanac
const REPORT_ICON = { population: 'people', over65: 'people', extinction: 'people', food: 'food', production: 'production', gold: 'gold', science: 'science', culture: 'culture' };

function rankRows(list, kind) {
  return arr(list).map((x) => ({ key: kind === 'sido' ? String(x.code) : x.id, value: num(x.value), rank: x.rank ?? null, partial: !!x.partial, note: x.note || '' }));
}

function buildReport(r) {
  const C = r.composition || {};
  return {
    id: String(r.id), name: r.name || String(r.id), icon: REPORT_ICON[r.id] || 'almanac',
    unit: r.unit || '', format: r.format || '', national: num(r.national),
    definition: r.definition || '', year: r.year != null ? String(r.year) : '', source: r.source || '',
    lens: r.lens || null, additive: !!r.additive,
    composition: {
      title: C.title || '', unit: C.unit || '', formula: C.formula || '',
      partsOfWhole: C.parts_of_whole !== false,
      rows: arr(C.rows).map((x) => ({ label: x.label || '', value: num(x.value) })),
    },
    modes: arr(r.modes).map((m) => {
      const cs = m.cities || {};
      return {
        id: m.id || '', label: m.label || '', unit: m.unit || '', format: m.format || r.format || '', rule: m.rule || '',
        sido: rankRows(m.sido, 'sido'),
        cities: { n: cs.n ?? null, top: rankRows(cs.top, 'city'), bottom: rankRows(cs.bottom, 'city'), excluded: cs.excluded || 0, excludedNames: arr(cs.excluded_names), filteredSmall: cs.filtered_small || 0 },
      };
    }),
  };
}

// 순위 보고서 모형. D.nationRaw 가 없으면(파일 실패) 빈 목록
export function reportsModel(D) {
  if (D._reports) return D._reports;
  const R = (D.nationRaw && D.nationRaw.reports) || {};
  const list = arr(R.items).map(buildReport);
  D._reports = { list, byId: new Map(list.map((r) => [r.id, r])), rule: R.rule || '', perCapitaMinPop: num(R.per_capita_min_pop) };
  return D._reports;
}

// 나라 단추: 이름과 기준 시점
export function nationHead(D) {
  const n = (D.nationRaw && D.nationRaw.nation) || {};
  return { name: n.name || '대한민국', vintage: D.vintage || '' };
}

// 값 -> [숫자, 단위] (큰 글자 + 작은 단위로 짜기 위해 나눈다). 없으면 null
export function reportParts(v, format, unit) {
  if (v == null || !Number.isFinite(v)) return null;
  const c = (n) => n.toLocaleString('ko-KR');
  const sign = v < 0 ? '−' : '';
  const a = Math.abs(v);
  if (format === 'won') {
    if (a >= 1e12) return [sign + c(+(a / 1e12).toFixed(a >= 1e14 ? 0 : 1)), '조 원'];
    if (a >= 1e10) return [sign + c(Math.round(a / 1e8)), '억 원'];
    if (a >= 1e8) return [sign + (a / 1e8).toFixed(1), '억 원'];
    if (a >= 1e4) return [sign + c(Math.round(a / 1e4)), '만 원'];
    return [sign + c(Math.round(a)), '원'];
  }
  if (format === 'pct1') return [sign + a.toFixed(1), '%'];
  if (format === 'pct2') return [sign + a.toFixed(2), '%'];
  if (format === 'f2') return [sign + a.toFixed(2), unit === '지수' ? '' : unit];
  if (format === 'f1') return [sign + a.toFixed(1), unit];
  if (format === 'int') return [sign + c(Math.round(a)), unit];
  return [sign + String(a), unit];
}
// 장부용 짧은 꼴: 사람 수는 만 단위로 (5,108만), 금액은 조
export function ledgerParts(r) {
  const v = r.national;
  if (v == null) return null;
  if (r.format === 'int' && r.unit === '명') {
    if (v >= 1e6) return [Math.round(v / 1e4).toLocaleString('ko-KR'), '만'];
    if (v >= 1e4) return [(v / 1e4).toFixed(1), '만'];
  }
  const p = reportParts(v, r.format, r.unit);
  if (p && r.format === 'won') p[1] = p[1].replace(' 원', '');
  return p;
}

// 렌즈의 덧붙임 글 (범례의 '기준' 서랍): 개편 전 공표 단위 주, 셈법, 값이 있는 범위
export function lensMeta(lens) {
  const r = (lens && lens.raw) || {};
  const cv = r.coverage;
  let coverage = '';
  if (typeof cv === 'number') coverage = `대한민국 육지 칸의 ${(cv <= 1 ? cv * 100 : cv).toFixed(1)}% 에 값이 있다.`;
  else if (cv && typeof cv === 'object') {
    if (cv.counties_with_value != null && cv.counties != null) coverage = `시군구 ${cv.counties}곳 가운데 ${cv.counties_with_value}곳에 값이 있다.`;
    else if (cv.land_pct != null) coverage = `대한민국 육지 칸의 ${cv.land_pct}% 에 값이 있다.`;
  }
  return { unitsNote: typeof r.units_note === 'string' ? r.units_note : '', definition: typeof r.definition === 'string' ? r.definition : '', coverage };
}
