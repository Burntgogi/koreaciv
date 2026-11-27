// 자료 어댑터 (출처·규칙 문장) — sources.json 과, 연감이 보여 주는 규칙·주석 글의 모양을 읽는 곳.
// 연감(ui/almanac.js)은 여기서 만든 '구역(section)' 목록을 그대로 그리기만 한다.
// 구역: {h, sub, p:[글], dim:[글], ul:[글], warn:[글], table:{head:[], rows:[[...]], num:[열 번호]}, details:{summary, ...구역}}
// 공유 그림의 출처 줄(attributionFor)도 여기서 sources.json 의 attribution 으로 만든다. 글을 손으로 적지 않는다.

import { loadSourcesRaw, SCALE_KO } from './core.js';
import { KINDS, LAYER_GROUPS } from '../config.js';

const arr = (v) => (Array.isArray(v) ? v : []);
const obj = (v) => (v && typeof v === 'object' ? v : {});
const n0 = (v) => (typeof v === 'number' && Number.isFinite(v) ? v.toLocaleString('ko-KR') : '자료 없음');
const pct1 = (v) => (typeof v === 'number' && Number.isFinite(v) ? (v * 100).toFixed(1) : '–');
const BASIS_KO = { site_policy: '사이트 이용정책', dataset_page: '자료 상세 페이지', license_doc: '이용허락 문서' };
export const SRC_PRECISION_KO = { point: '좌표', area: '경계 폴리곤 대표점', county: '시군구 대표 위치', sido: '시도 기준', list: '목록만' };
const YIELD_KO = { food: '식량', production: '생산', gold: '금', science: '과학', culture: '문화' };
const kindName = (k) => (KINDS[k] ? KINDS[k].label : k);
// 구역 하나가 실패해도 나머지는 보이게
const safe = (out, fn, title) => { try { const r = fn(); for (const x of [].concat(r || [])) if (x) out.push(x); } catch (e) { console.warn('연감 구역 실패:', title, e); out.push({ h: title, warn: ['이 구역의 자료 모양을 읽지 못했습니다. 자료 파일을 직접 보십시오.'] }); } };

// ---------- sources.json ----------
function buildSources(raw) {
  if (!raw || !Array.isArray(raw.sources)) return null;
  const list = raw.sources.map((x) => ({
    key: String(x.key), title: x.title || String(x.key), publisher: x.publisher || '', attributionName: x.attribution_name || '',
    vintage: x.vintage || '', retrieved: x.retrieved ? String(x.retrieved).slice(0, 10) : '', url: x.url || '', group: x.group || '기타', usedIn: x.used_in || '',
    license: x.license || '미확인', licenseShort: x.license_short || x.license || '이용허락 미확인', licenseUrl: x.license_url || '', licenseNote: x.license_note || '',
    licenseBasis: BASIS_KO[x.license_basis] || '', licenseChecked: x.license_checked || '', licenseCollected: x.license_collected || '', licenseFrom: x.license_from === '수집 기록' ? '수집 기록' : '',
    unknown: x.license === '미확인' || /미확인/.test(x.license_short || ''), useScope: x.use_scope || '',
    restriction: x.restriction || '', restrictionShort: x.restriction_short || '',
    sha: x.sha256 ? String(x.sha256).slice(0, 16) : '', files: arr(x.files).length, manual: !!x.manual, file: x.file || '', basis: x.basis || '', derivedTable: x.derived_table || '',
  }));
  const A = obj(raw.attribution);
  // 이 판 (공개판·전체판): 판 이름, 뺀 것과 까닭, 변경금지 통계 — 글은 그대로 텍스트로만 쓴다
  const P = obj(raw.profile);
  const profile = P.profile ? {
    id: String(P.profile), name: String(P.name || P.profile), statement: String(P.statement || ''), rule: String(P.rule || ''), checkRule: String(P.check_rule || ''),
    excluded: arr(P.excluded).map((e) => ({ what: String(obj(e).what || ''), why: String(obj(e).why || ''), instead: obj(e).instead ? String(e.instead) : '' })),
    checkNeeded: arr(P.check_needed).map((x) => ({ title: String(obj(x).title || ''), publisher: String(obj(x).publisher || ''), license: String(obj(x).license_short || ''), where: arr(obj(x).where).map(String) })),
  } : null;
  return { profile,
    list, byKey: new Map(list.map((x) => [x.key, x])),
    groups: [...new Set(list.map((x) => x.group))],
    unknownCount: list.filter((x) => x.unknown).length,
    restrictions: arr(raw.restrictions).map((r) => ({ key: r.key, title: r.title || '', text: r.text || '', short: r.short || '' })),
    licenseRule: raw.license_rule || '', notes: arr(raw.notes),
    attribution: { base: arr(A.base), lenses: obj(A.lenses), fullList: A.full_list || '연감 › 출처', rule: A.rule || '' },
  };
}

// 출처 목록 (처음 필요할 때 불러온다). 실패하면 null — D.sources 에도 남긴다
export async function loadSources(D) {
  if (D.sources) return D.sources;
  const raw = await loadSourcesRaw(D);
  D.sources = buildSources(raw);
  return D.sources;
}

// 출처 key -> 기록 (끝이 '-' 인 층 종류 key 는 접두어로 찾는다)
export function sourceRecords(S, keys) {
  const out = [];
  if (!S) return out;
  for (const k of keys) {
    const hit = S.byKey.has(k) ? [S.byKey.get(k)] : S.list.filter((x) => x.key.startsWith(k));
    for (const x of hit) if (!out.includes(x)) out.push(x);
  }
  return out;
}
// 같은 이용허락끼리 기관을 묶은 문구들
export function creditParts(S, keys) {
  const g = new Map();
  for (const x of sourceRecords(S, keys)) {
    const lic = x.licenseShort;
    if (!g.has(lic)) g.set(lic, []);
    const nm = x.attributionName || x.publisher;
    if (nm && !g.get(lic).includes(nm)) g.get(lic).push(nm);
  }
  return [...g.entries()].map(([lic, names]) => `${names.join(', ')} (${lic})`);
}
// 지금 켜진 지도 층 종류의 출처 key. visible(group, sub) -> bool
export function layerSourceKeys(D, visible) {
  const L = D.layers, keys = [];
  if (!L || !visible) return keys;
  const add = (src) => { for (const x of arr(src)) if (x && x.key && !keys.includes(x.key)) keys.push(x.key); };
  const present = new Set(L.items.map((it) => it.kind));
  for (const [kind, k] of Object.entries(L.kinds)) {
    const K = KINDS[kind];
    const on = K ? present.has(kind) && visible(K.layer, K.sub) : (kind === 'roads' || kind === 'rails') ? visible('infra', 'lines') : false;
    if (on) add(k.source);
  }
  if (L.trade && visible('trade', 'routes')) add(L.trade.source);
  if (L.frontier && visible('frontier', 'frontier')) add(L.frontier.source);
  return keys;
}
// 공유 그림의 출처 줄: [{text, warn}] — 그린 것에 맞춘다 (바탕은 늘, 렌즈를 켜면 그 렌즈, 켜진 층)
export function attributionFor(D, { lens, layerVisible } = {}) {
  const S = D.sources;
  if (!S) return [{ text: '출처 목록을 불러오지 못함 — 연감 참조. (sources.json 을 읽지 못해 이 그림에 출처를 적지 못했습니다)', warn: true }];
  const A = S.attribution, out = [], used = [...A.base];
  out.push({ text: `지도 바탕: ${creditParts(S, A.base).join(' · ')}` });
  if (D.ridges) out.push({ text: '산줄기: 위 표고·하천 자료로 계산한 분수계 (고유 이름 없음)' });
  if (lens) {
    const lk = arr(A.lenses[lens.id]);
    if (lk.length) { out.push({ text: `렌즈 ‘${lens.name}’: ${creditParts(S, lk).join(' · ')}` }); used.push(...lk); }
    else out.push({ text: `렌즈 ‘${lens.name}’: ${lens.source || '출처 기록 없음'}` });
  }
  const lyk = layerSourceKeys(D, layerVisible);
  if (lyk.length) {
    const parts = creditParts(S, lyk);
    // 층 자료 안에 적힌 출처가 sources.json 에 없으면 층 자료의 기관 이름을 그대로 쓴다
    out.push({ text: `지도 층: ${parts.length ? parts.join(' · ') : '출처 기록은 연감 › 지도 층'}` });
    used.push(...lyk);
  }
  for (const x of sourceRecords(S, used)) if (x.restrictionShort) out.push({ text: `주의 — ${x.restrictionShort}`, warn: true });
  out.push({ text: `전체 출처·이용허락 목록: 신여지도 › ${A.fullList}` });
  return out;
}

// ---------- 연감: 지형·산줄기 ----------
export function ridgeInfo(D) {
  const R = D.ridges;
  if (!R) return null;
  const c = obj(R.checks);
  return { rule: R.rule, method: R.method, generated: R.generated, version: R.version, tiers: arr(R.tiers).map((t) => ({ t: t.t, name: t.name || '', rule: t.rule || '' })),
    checks: c, lines: R.lines.length, source: obj(R.source) };
}

export function almanacTerrain(D) {
  const out = [], W = D.world, rw = obj(D.raw && D.raw.world), t = obj(W.tables);
  safe(out, () => {
    const R = ridgeInfo(D);
    if (!R) return { h: '산줄기', warn: ['산줄기 자료(ridges.json)를 불러오지 못해 지도에 산줄기를 그리지 않았습니다.'] };
    const c = R.checks, bt = obj(c.by_tier);
    const dem = obj(R.source.dem), rv = obj(R.source.rivers);
    return [{
      h: '산줄기', sub: `계산한 분수계 · ${n0(R.lines)}줄 · ${R.generated || ''}`,
      p: [R.rule, R.method,
        '이 선들은 누가 그어 둔 산맥 지도가 아니라, 이 사이트가 가진 표고 자료와 하천 자료에서 물이 갈리는 자리(분수계)를 셈해 이은 것이다. 그래서 고유한 산맥·산줄기 이름을 붙이지 않는다. 교과서의 산맥이나 옛 지리서의 줄기와 꼭 같지 않다.'],
      table: { head: ['검사', '결과'], rows: [
        ['물줄기와 엇갈린 곳', `${n0(c.river_crossings)}건 (산줄기 변 ${n0(c.ridge_segments_tested)} × 물줄기 ${n0(c.rivers_tested)}개·변 ${n0(c.river_segments_tested)})`],
        ['호수를 가로지른 곳', `${n0(c.lake_crossings)}건 (호수 ${n0(c.lakes_tested)}개)`],
        ['선·꼭짓점·길이', `${n0(c.lines)}줄 · 꼭짓점 ${n0(c.vertices)} · ${n0(c.total_km)} km`],
        ['산줄기 평균 표고 / 육지 평균 표고', `${n0(c.ridge_mean_elev_m)} m / ${n0(c.land_mean_elev_m)} m`],
        ['표고 100 m 아래를 지나는 길이', c.below_100m_share_pct != null ? `${c.below_100m_share_pct}%` : '자료 없음'],
        ...(c.low_pass_bridges ? [['낮은 고개를 이은 곳', `${n0(c.low_pass_bridges.count)}곳 · ${n0(c.low_pass_bridges.km)} km (한 곳 ${n0(c.low_pass_bridges.max_km)} km 이하)`]] : []),
      ] },
      dim: [c.smoothing || '', `표고: ${dem.name || dem.file || '–'}${dem.grid ? ' · ' + dem.grid : ''}. 물줄기: ${rv.drawn || '–'}${rv.burn_only ? ' / ' + rv.burn_only : ''}.`,
        '한계: 약 0.9 km 간격 표고로 셈해 좁은 골짜기에서는 선이 물줄기에 바짝 붙는다. 들과 바닷가, 제주(물줄기가 한라산에서 사방으로 흘러 분수계가 모두 끊긴다)에는 선이 거의 없다. 북쪽은 하천 자료가 없어 그리지 않았다. 선의 굵기(봉우리에서 굵고 고개에서 가늚)와 남동쪽 엷은 바림은 그림 처리다.'].filter(Boolean),
    }, { h: '산줄기 단계', table: { head: ['단계', '규칙'], rows: R.tiers.map((x) => [x.name, x.rule]) }, dim: ['큰 줄기부터 배율에 따라 차례로 나타난다.'] }];
  }, '산줄기');
  const tbl = (rows, title) => ({ h: title, table: { rows: arr(rows).map((r) => [r.name, r.rule || '']) } });
  const cmeta = obj(rw.cover_meta);
  safe(out, () => [tbl(t.relief, '기복'), tbl(t.water, '물'), tbl(t.cover, cmeta.table_title || '피복')], '지형 규칙');
  safe(out, () => {
    // 토지피복: 두 판 공용 (기후에너지환경부 세분류 토지피복지도 도엽 통계). 글은 world.cover_meta 에서
    const cm = cmeta;
    if (!cm.weighted_share) return null;
    return { h: '토지피복', warn: D.sources ? D.sources.restrictions.map((r) => r.text) : [],
      p: [`${cm.legend || cm.source || ''}`, cm.bias_note ? `알려진 치우침: 칸 비율은 ${cm.bias_note}` : ''].filter(Boolean),
      dim: [cm.summary || '', W.coverRule].filter(Boolean) };
  }, '토지피복');
  safe(out, () => { const LM = obj(D.nationRaw && D.nationRaw.land_stats_meta); return LM.rule ? { h: '국가토지피복통계', sub: `${LM.year}년 기준 · 고을·시도·전국 장의 '땅' 구역`, p: [LM.rule], dim: [LM.source || ''] } : null; }, '국가토지피복통계');
  safe(out, () => {
    const lm = obj(rw.lake_meta);
    if (!lm.polygons) return null;
    return { h: '호수·저수지', sub: '대체 자료: © OpenStreetMap 기여자 (ODbL 1.0)',
      p: [`수면 ${n0(lm.polygons)}면 가운데 호수 칸이 된 것 ${n0(lm.lake_cells)}칸 (${Object.entries(obj(lm.lake_cells_by_name)).map(([k, v]) => `${k} ${v}칸`).join(', ') || '없음'}). 칸(${W.hexKm2} km²)의 과반을 덮는 수면이 드물어 대부분의 호수는 칸 위 폴리곤(${lm.draw_min_km2} km² 이상 ${W.lakes.length}면)으로만 그린다. 이름표: ${W.lakeLabels.map((l) => `${l.name}(${l.areaKm2} km²)`).join(', ')}.`] };
  }, '호수');
  safe(out, () => {
    const td = rw.tidal;
    if (!td) return null;
    const sname = (c) => (W.states[W.stateIndex.get(String(c))] || {}).name || c;
    return { h: '갯벌', sub: `해양수산부 1:25,000 연안정보도, ${td.year}년 제작 · 폴리곤 ${n0(td.polygons)}면 · 넓이 합 ${n0(td.polygon_area_km2)} km²`,
      table: { head: ['시도', '갯벌 칸', '폴리곤 넓이 (km²)', '갯벌이 닿은 해안 육지 칸'], num: [1, 2, 3], rows: Object.entries(obj(td.by_sido)).sort((x, y) => y[1].area_km2 - x[1].area_km2).map(([c, v]) => [sname(c), n0(v.tile_cells), n0(v.area_km2), n0(v.land_cells_touched)]) },
      dim: [`칸에 든 넓이 합 ${n0(td.area_in_cells_km2)} km² (나머지는 외국 땅 칸·격자 밖). 바다 칸의 시도는 칸 거리로 가장 가까운 육지 칸의 시도.`] };
  }, '갯벌');
  safe(out, () => ({ h: '격자와 판정', ul: W.notes, dim: [`격자 ${W.cols}×${W.rows} · 칸 넓이 ${W.hexKm2} km² · 1 화면 단위 = ${W.metersPerUnit} m · 원점(EPSG:5179) ${arr(rw.origin_5179).join(', ')} · 자료 판 ${W.version}`] }), '격자');
  return out;
}

// ---------- 연감: 렌즈 ----------
const dirKo = (hi) => (hi === 'good' ? '높을수록 좋음' : hi === 'bad' ? '낮을수록 좋음' : '방향 없음');
function vetAudit(D, A) {
  const W = D.world, cn = (c) => (W.counties[W.countyIndex.get(String(c))] || {}).name || c;
  const dim = [];
  if (A.detail) dim.push(A.detail);
  if (arr(A.categories_upper).length) dim.push(`대상구분 상위 ${A.categories_upper.length}개: ${A.categories_upper.join(', ')}`);
  const dropped = arr(A.dropped_files);
  dim.push(`시군구 값 합 ${n0(A.unit_total)}명 + 나눌 수 없는 옛 구역 행 ${n0(arr(A.residual).reduce((s, r) => s + r.value, 0))}명 + 대응 실패 ${n0(arr(A.unmatched).filter((u) => !dropped.includes(u.file)).reduce((s, u) => s + u.value, 0))}명 = 원자료 시군구 행 합 ${n0(A.raw_county_rows)}명 (겹친 파일 제외). 인구 ${A.pop_ym || '–'}.`);
  if (arr(A.duplicates).length) dim.push(`두 파일에 나온 시군구 ${A.duplicates.length}곳 (값이 다른 곳 ${A.duplicates.filter((d) => !d.same).length}): ${A.duplicates.map((d) => `${d.name} ${Object.entries(obj(d.values)).map(([k, v]) => `${k} ${obj(d.periods)[k] || ''} ${n0(v)}`).join(' / ')}`).join('; ')} → 소재 시도 파일 값.`);
  if (arr(A.residual).length) dim.push(`옛 구역 행: ${A.residual.map((r) => `${r.name} ${n0(r.value)}명 (${arr(r.codes).map(cn).join('·')}) — ${r.reason}`).join('; ')}`);
  dim.push(arr(A.unmatched).length ? `대응 실패: ${A.unmatched.map((u) => `${u.sido} '${u.name}' ${n0(u.value)}명 — ${u.reason}`).join('; ')}` : '대응 실패 없음');
  if (arr(A.no_value).length) dim.push(`값이 없는 시군구: ${A.no_value.map(cn).join(', ')}`);
  return { summary: `원자료 대조 (파일 ${arr(A.sido_check).length}개)`, dim,
    table: { head: ['파일 시도', '최신 분기', '시군구 행 합', '시도 합계 행', '차', ''], num: [2, 3, 4], rows: arr(A.sido_check).map((r) => [r.sido_txt, r.period, n0(r.county_rows), n0(r.total_row), (r.diff > 0 ? '+' : '') + n0(r.diff), r.used ? '씀' : '안 씀 (겹친 파일)']) } };
}
// 렌즈 정의: {intro:[구역], groups:[{id,name,lenses:[{id,name,unit,scaleKo,domain,direction,description,unitsNote,basis,vintage,source,level,details}]}], outro:[구역]}
export function almanacLenses(D) {
  const LS = D.lenses, intro = [], outro = [];
  const fmtDom = (l) => (l.scale === 'category' ? `범주 ${l.categories.length}개` : l.scale === 'bins' ? l.binLabels.join(' / ') : l.domain.map((v) => n0(v)).join(' – '));
  const groups = LS.groups.map((g) => ({ id: g.id, name: g.name, lenses: g.lenses.map((l) => {
    let details = null;
    try { if (l.raw.audit) details = vetAudit(D, l.raw.audit); } catch (e) { details = null; }
    return { id: l.id, name: l.name, unit: l.unit, scaleKo: SCALE_KO[l.scale] || l.scale, domain: fmtDom(l), direction: dirKo(l.higherIs), description: l.description,
      unitsNote: l.raw.units_note || '', basis: l.basis, vintage: l.vintage, source: l.source, level: l.level, definition: typeof l.raw.definition === 'string' ? l.raw.definition : '', details };
  }) }));
  safe(intro, () => {
    if (!LS.retiredItems.length) return null;
    return { h: '렌즈에서 뺀 지표', sub: `${LS.retiredItems.length}개 · 값은 시군구 값으로 남음`, p: [LS.retiredRule],
      table: { head: ['지표', '남은 자리', '옛 링크가 가는 렌즈'], rows: LS.retiredItems.map((x) => [x.name, `${x.level || ''} · 값 있는 시군구 ${x.counties_with_value ?? '–'}${x.units_note ? ' — ' + x.units_note : ''}`, (LS.byId.get(x.near) || {}).name || x.near || '']) } };
  }, '뺀 지표');
  safe(outro, () => ({ h: '렌즈 일러두기', ul: LS.notes, dim: ['지도에 찍는 빛깔은 자료에 실린 색이 아니라 이 판의 안료 띠다. 값에서 빛깔로 가는 척도(로그·선형·발산·구간·범주)와 범위는 자료 그대로다.'] }), '렌즈 일러두기');
  return { intro, groups, outro, count: LS.list.length };
}

// ---------- 연감: 지도 층 ----------
export function almanacLayers(D) {
  const L = D.layers, out = [];
  if (!L) return null;
  const raw = obj(L.raw), Wd = obj(raw.wonders), Rs = obj(raw.resources), If = obj(raw.infrastructure);
  const sn = (c) => (D.stateByCode.get(String(c)) || {}).short || c;
  const failed = D.failed.filter((f) => ['wonders', 'resources', 'infrastructure', 'frontier', 'trade'].includes(f));
  if (failed.length) out.push({ h: '불러오지 못한 층', warn: [`${failed.map((f) => f + '.json').join(', ')} — 그 층의 항목은 이 목록과 지도에 없습니다.`] });
  safe(out, () => ({ h: '층 묶음', sub: `${LAYER_GROUPS.length}묶음`, table: { head: ['묶음', '처음 상태', '세부'], rows: LAYER_GROUPS.map((g) => [g.name, g.def ? '켜짐' : '꺼짐', g.subs.map((s) => s[1]).join(' · ')]) } }), '층 묶음');
  safe(out, () => {
    const Z = L.zoom;
    if (!Z) return null;
    const C = obj(Z.counts);
    return { h: '배율에 따른 표시', sub: Z.national_total != null ? `전국 배율 아이콘 ${Z.national_total}개 (겹침·이름표 피하기 전)` : '', ul: arr(Z.rules),
      dim: ['이 판은 같은 단계(tier)를 쓰되, 이름표·아이콘이 겹칠 때 비켜 놓는 자리는 이 판의 배치 규칙을 따른다. 찾기와 장의 목록은 배율과 관계없이 전부 찾는다.'],
      table: { head: ['단계', '시작 배율 z', '그리는 아이콘 (누적, 종류별)'], rows: arr(Z.levels).map((lv) => { const c = obj(C[String(lv.tier)]); return [lv.name, String(lv.z_min), `${Object.values(c).reduce((a, v) => a + v, 0)}개 — ${Object.entries(c).sort((x, y) => y[1] - x[1]).map(([k, v]) => `${kindName(k)} ${v}`).join(' · ')}`]; }) } };
  }, '배율에 따른 표시');
  safe(out, () => (L.universities ? { h: '연구대학', sub: L.universities.status === 'ok' ? '지식 불가사의에 더함' : '자료 없음', p: [L.universities.note || ''] } : null), '연구대학');
  for (const [file, o] of [['wonders', Wd], ['resources', Rs], ['infrastructure', If]]) {
    if (!o.kinds) continue;
    safe(out, () => {
      const secs = [{ h: o.name || file, sub: `위치 정밀도: ${Object.entries(obj(o.precision_counts)).map(([k, v]) => `${SRC_PRECISION_KO[k] || k} ${v}`).join(' · ') || '–'}`, major: true }];
      for (const [kind, k] of Object.entries(o.kinds)) {
        const miss = arr(k.missing);
        const dim = [`기준: ${k.year || '–'} · 출처: ${arr(k.source).map((x) => `${x.publisher || ''} 「${x.title || x.key || ''}」`).join(', ') || '–'}`];
        if (k.excluded && Object.keys(k.excluded).length) dim.push(`뺀 것: ${Object.entries(k.excluded).map(([r, v]) => `${r} ${v}`).join(' · ')}`);
        if (arr(k.fallback).length) dim.push(`좌표 대신 주소로 놓은 것 ${k.fallback.length}곳: ${k.fallback.map((x) => x.name).join(', ')}`);
        if (k.precision_note) dim.push(`위치: ${String(k.precision_note).replace(/\b(point|county|area|sido|list)\b/g, (m) => SRC_PRECISION_KO[m] || m)}`);
        if (!miss.length) dim.push('빠진 항목 없음');
        secs.push({ h: k.name || kindName(kind), kind, sub: `${k.count != null ? n0(k.count) + '건' : ''}${k.placed != null ? ' · 지도에 놓음 ' + n0(k.placed) : ''}${k.draft ? ' · 초안' : ''}`, p: [k.rule || ''], dim,
          details: miss.length ? { summary: `빠진 항목 ${miss.length}건`, ul: miss.map((m) => `${m.name} — ${m.reason}`) } : null });
      }
      return secs;
    }, o.name || file);
  }
  safe(out, () => { const un = [...arr(Rs.unplaced), ...arr(If.unplaced)]; return { h: '위치가 없어 지도에 놓지 못한 항목', sub: `${un.length}건 · 값은 그대로 싣는다`, table: un.length ? { rows: un.map((u) => [kindName(u.kind), u.name, (u.value == null ? '자료 없음' : n0(u.value) + ' ' + (u.unit || '')) + (u.year ? ` (${u.year})` : '')]) } : null, dim: un.length ? [] : ['없음'] }; }, '놓지 못한 항목');
  safe(out, () => (L.lineNotes.length ? { h: '도로·철도 선', ul: L.lineNotes } : null), '선');
  safe(out, () => { const F = L.frontier; return F ? { h: '접경지역', sub: `${F.areas.length}곳 · ${F.year}`, p: [F.rule], table: { rows: F.areas.map((x) => [x.name, x.article]) } } : null; }, '접경지역');
  safe(out, () => { const G = Rs.gi; return G ? { h: '지리적표시: 지도에 놓지 않은 것', sub: `시도 전체 ${arr(G.sido_level).length} · 목록만 ${arr(G.list_only).length}`, ul: [...arr(G.sido_level).map((g) => `${g.name} — ${g.gi_kind}, 등록지역 '${g.area}' (시도 장에 실음)`), ...arr(G.list_only).map((g) => `${g.name} — ${g.gi_kind}: ${g.reason}`)] } : null; }, '지리적표시');
  safe(out, () => {
    const P = Rs.power;
    if (!P) return null;
    return { h: '발전설비 검산', sub: `EPSIS 발전기 현황 ${P.date || ''}`, dim: [
      `발전기 ${n0(P.generators)}기 · ${n0(Math.round(P.total_mw))} MW = 시군구 합 ${n0(Math.round(P.unit_sum_mw))} + 소재지 대응 실패 ${obj(P.failed).count}기 ${Number(obj(P.failed).mw).toFixed(1)} MW.`,
      `연료원별: ${Object.entries(obj(P.by_fuel_mw)).map(([k, v]) => `${obj(P.fuel_ko)[k] || k} ${n0(Math.round(v))}`).join(' · ')} MW.`,
      `원전 대조: ${arr(P.nuclear_compare).map((x) => `${x.sgg} ${n0(x.mw)} MW ↔ 원안위 ${x.nssc_site} ${n0(x.nssc_mw)} MW (${x.match ? '일치' : '다름'})`).join('; ')}.`] };
  }, '발전설비');
  safe(out, () => {
    const K = Rs.knowledge;
    if (!K) return null;
    const eok = (v) => (v == null ? '자료 없음' : Math.round(v / 1e8).toLocaleString('ko-KR') + '억원');
    const secs = [{ h: '지식 불가사의', p: [K.note || ''], dim: arr(K.research_institutes).length ? [`국가과학기술연구회 소관 출연연 (이름만, 지도에 놓지 않음): ${K.research_institutes.join(' · ')}`] : [] }];
    if (arr(K.funding_top).length) secs.push({ h: `대학 연구비 상위 ${K.funding_top.length}`, sub: `대학알리미 ${K.funding_year || ''} · ${K.funding_rows ?? '–'}개 학교·캠퍼스 · ${K.funding_unit || ''}`,
      table: { head: ['순위', '학교', '시도', '연구비'], num: [3], rows: K.funding_top.map((x) => [String(x.rank), x.name, sn(x.sido), eok(x.won)]) } });
    return secs;
  }, '지식');
  safe(out, () => {
    const T = L.trade;
    if (!T) return null;
    const TT = obj(T.raw.trade), nt = obj(obj(D.nationRaw && D.nationRaw.nation).trade), tot = obj(T.totals), R = obj(T.raw.routes);
    const usd = (v) => (v / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 1 }) + '억 달러';
    const top = D.cities.filter((c) => c.raw.trade && c.raw.trade.export != null).sort((x, y) => y.raw.trade.export - x.raw.trade.export).slice(0, 15);
    return [{ h: '수출입', sub: `관세청 ${TT.year || ''}${nt.units != null ? ` · 시군구 공표 단위 ${nt.units}곳` : ''}`, p: [TT.basis, TT.hq_note, TT.hs_rule].filter(Boolean), dim: [[TT.unmatched_note, nt.note].filter(Boolean).join(' ')].filter(Boolean),
      table: { head: ['수출 순위', '고을', '수출', '수입'], num: [2, 3], rows: top.map((c, k) => [String(k + 1), c.name, usd(c.raw.trade.export), c.raw.trade.import != null ? usd(c.raw.trade.import) : '자료 없음']) } },
    { h: '교역로', sub: `${T.mode} ${T.year} · 시도 간 ${R.pairs_total ?? '–'}쌍 중 상위 ${R.top_n ?? T.segments.length}구간${tot.inter_t ? ` (${(100 * tot.shown_t / tot.inter_t).toFixed(0)}%)` : ''}`, p: [T.rule],
      dim: [`원자료 ${n0(tot.raw_t)}톤 = 시도 간 ${n0(tot.inter_t)} + 시도 안 ${n0(tot.intra_t)} (17개 시도 대각 ${n0(tot.intra_17_diag_t)} + 광주↔전남 ${n0(tot.gwangju_jeonnam_t)}, 전남광주 안 흐름으로 봄)`],
      details: { summary: `구간 ${T.segments.length}개`, table: { head: ['순위', '구간', '물동량', '몫'], num: [2, 3], rows: T.segments.map((g) => [String(g.rank), `${sn(g.a)}–${sn(g.b)}`, n0(g.total) + '톤', g.share != null ? g.share + '%' : '–']) } } }];
  }, '교역');
  safe(out, () => {
    const P = obj(obj(Rs.farm).pigs);
    if (!P.sido_compare) return null;
    return { h: '돼지 시도 합 대조', sub: `방역본부 ${P.year || ''} 시군 값의 시도 합 / 가축동향조사 · 판정하지 않음`, dim: [`${P.sido_compare_note || ''} ${P.note || ''}. 원표 ${P.raw_rows ?? '–'}행 합 ${n0(P.raw_total)}마리, 대응 실패 ${arr(P.unmatched).length}행.`],
      table: { head: ['시도', '시군 값 합', '가축동향조사', '차이 비율'], num: [1, 2, 3], rows: P.sido_compare.map((r) => [sn(r.sido), r.county_sum == null ? '자료 없음' : n0(r.county_sum), r.survey == null ? '자료 없음' : n0(r.survey), r.diff_ratio == null ? '–' : (r.diff_ratio > 0 ? '+' : '') + (100 * r.diff_ratio).toFixed(1) + '%']) } };
  }, '돼지');
  safe(out, () => (arr(Rs.unavailable).length ? { h: '받지 못한 자료', ul: Rs.unavailable.map((u) => `${u.name} — ${u.reason}`) } : null), '받지 못한 자료');
  safe(out, () => { const H = Wd.heritage; return H ? { h: '국가유산 좌표', dim: [`원자료 ${Object.entries(obj(H.raw)).map(([k, v]) => `${k} ${v}`).join(' · ')} · 좌표 유효 ${n0(H.valid)}건 · 뺀 것 ${Object.entries(obj(H.excluded)).map(([k, v]) => `${k} ${v}`).join(' · ')}`] } : null; }, '국가유산');
  return out;
}

// ---------- 연감: 산출·고을 ----------
export function yieldDefs(D) {
  const E = obj(D.nationRaw && D.nationRaw.econ);
  return arr(E.yields).map((y) => ({ id: y.id, name: y.name || YIELD_KO[y.id] || y.id, rule: y.rule || '' }));
}
export function almanacYields(D) {
  const out = [], N = obj(D.nationRaw), E = obj(N.econ), nn = obj(N.nation), LS = D.lenses;
  if (!D.nationRaw) return [{ h: '산출', warn: ['nation.json 을 불러오지 못해 산출 정의를 보여 주지 못합니다.'] }];
  safe(out, () => ({ h: '다섯 산출', sub: '모두 GRDP 경제활동별 부가가치 (명목, 생산지 기준, 원)', yields: yieldDefs(D) }), '다섯 산출');
  safe(out, () => ({ h: '알고 쓰는 한계', ul: arr(E.limits) }), '한계');
  safe(out, () => ({ h: '계산 규칙', ul: [
    '고을 = 소속 시군구의 합. 일반구가 있는 시는 시 전체로만 공표된 값을 그대로 쓰고 구에 나누지 않는다.',
    `고을마다 GRDP 가 있는 가장 최근 연도를 쓴다. 시도·전국은 고을 합이 아니라 소속 시군구 합이다. 전국 기준: ${nn.gdp_year_label || '–'}.`,
    E.undisclosed_note, E.per_capita_note, E.housing_note, E.range_note, E.national_note, E.growth_note, E.official_note, E.combined_note, E.jobs_note, E.jobs_vs_grdp_note,
    '산출의 종사자 보조 값: 식량 = A, 생산 = B + C + F, 과학 = J + M, 문화 = R, 금 = 전산업 종사자.',
    '닮은 고을은 인구(로그)·고령 비율·1인당 GRDP(로그)·산업 16분류 비중의 표준화 거리로 고른다.'].filter(Boolean) }), '계산 규칙');
  safe(out, () => {
    const cov = obj(E.coverage);
    const partial = D.cities.filter((c) => c.raw.yields_partial && c.raw.yields_partial.production);
    const noY = D.cities.filter((c) => c.raw.yields && Object.values(c.raw.yields).some((v) => v == null));
    const lensName = (k) => (LS.byId.get(k) ? LS.byId.get(k).name : ((LS.retiredItems.find((x) => x.id === k) || {}).name || k) + '(뺀 렌즈)');
    return { h: '덮은 범위', ul: [
      `GRDP 가 있는 고을 ${cov.cities_with_gdp ?? '–'}/${D.cities.length}곳, 다섯 산출이 모두 있는 고을 ${cov.cities_all_yields ?? '–'}곳.`,
      `생산이 부분 합계(광업 비공개 몫 제외, 값 옆 * 표식)인 곳: 고을 ${cov.cities_production_partial ?? '–'}곳 · 시도 ${cov.states_production_partial ?? '–'}곳 · 전국 합계에서 빠진 공표 단위 ${cov.nation_production_mining_excluded ?? '–'}곳. 고을: ${partial.map((c) => `${c.name}(광업 비공개 ${c.raw.production_mining_excluded}곳 제외)`).join(', ') || '없음'}`,
      `산출이 빈 고을: ${noY.map((c) => `${c.name}(${Object.entries(c.raw.yields).filter(([, v]) => v == null).map(([k]) => YIELD_KO[k] || k).join('·')})`).join(', ') || '없음'}`,
      `렌즈별 값이 있는 육지 칸: ${Object.entries(obj(cov.lens_land_coverage_pct)).map(([k, v]) => `${lensName(k)} ${v}%`).join(' · ')}`] };
  }, '덮은 범위');
  safe(out, () => { const R = obj(N.reports); return R.rule ? { h: '순위 보고서', ul: [R.rule, ...arr(R.items).map((r) => `${r.name}: ${r.definition || ''}${r.source ? ' — ' + r.source : ''}`)] } : null; }, '순위 보고서');
  safe(out, () => {
    const n = obj(N.notes);
    return { h: '고을의 정의', ul: [
      '특별·광역시의 자치구는 한 고을로 묶고, 그 안의 군(기장·달성·군위·강화·옹진·울주)은 따로 둔다.',
      "'…시 …구' 꼴의 일반구는 앞의 시로 묶는다. 세종은 한 고을, 제주시·서귀포시는 각각 고을.",
      n.gwangju, `나머지 시·군은 각각 한 고을. 결과 ${D.cities.length}곳.`].filter(Boolean) };
  }, '고을의 정의');
  safe(out, () => ({ h: '인구·고을 주석', ul: Object.values(obj(N.notes)).filter((x) => typeof x === 'string'), dim: [`주민등록 인구 기준 시점 ${N.vintage || '–'} · 시계열 ${arr(N.series_years).join(', ')}. 지도와 장은 가장 최근 시점 하나만 보여 주고, 지난 시점은 고을 장의 인구 추이에 있다.`] }), '주석');
  safe(out, () => {
    const O = N.offices, W = D.world;
    if (!O) return null;
    const cname = (codes) => arr(codes).map((c) => (W.counties[W.countyIndex.get(String(c))] || {}).name || c).join('·');
    const rows = D.states.flatMap((s) => arr(s.raw.offices).map((o) => [s.short, `${o.name || ''}${o.role ? ' (' + o.role + ')' : ''}`, o.address || '', cname(o.sgg)]));
    return [{ h: '청사', sub: `행정안전부 공표본 사무소 소재지 표 ${O.count ?? '–'}건, 주소 → 시군구 ${O.resolved ?? '–'}건`, table: { head: ['시도', '청사', '주소 (원표)', '시군구'], rows },
      dim: [arr(O.failed).length ? `주소 처리 예외: ${O.failed.map((f) => `${f.name} '${f.address}' — ${f.reason}`).join('; ')}` : '', arr(O.name_mismatch).length ? `청사 주소의 시군구가 기관 이름의 시군구와 다른 곳(원표 그대로): ${O.name_mismatch.join(', ')}` : '',
        '특례시 표(수원·고양·용인·화성·창원)는 출처를 확인할 공표 자료를 받지 못한 수작업 표다.'].filter(Boolean) },
    { h: '전남광주통합특별시 청사', sub: O.law || '', dim: ['특별법이 종전 청사 3곳을 균형 있게 활용·운영하도록 정해 3곳을 모두 적고 주 청사를 하나로 정하지 않는다.'],
      ul: arr(O.special).map((e) => `${e.name} — ${e.sgg ? cname(e.sgg) + ' (시군구 대표 위치)' : '지도에 놓지 않음'} · ${e.located_by || ''}`) }];
  }, '청사');
  return out;
}

// 화면이 쓰는 한 줄 사실들 (도움말·글 목록)
export function mapFacts(D) {
  return { landCells: D.world.landCells.length, cities: D.cities.length, states: D.states.length, lenses: D.lenses.list.length, hexKm2: D.world.hexKm2, vintage: D.vintage };
}

// 공유 카드에 찍는 고을의 사실 몇 가지 (인구, 다섯 산출, 기준 연도). 없으면 null 로 둔다
export function cardFacts(D, city) {
  const r = obj(city && city.raw), y = obj(r.yields), part = obj(r.yields_partial);
  return { name: city.name, full: city.full, pop: city.pop, vintage: D.vintage, gdpYear: r.gdp_year ?? null,
    yields: yieldDefs(D).map((d) => ({ id: d.id, name: d.name, value: typeof y[d.id] === 'number' ? y[d.id] : null, partial: !!part[d.id] })) };
}
// 렌즈에서 실제로 지도에 나온 범주·구간 번호 (대한민국 육지 칸)
export function lensObservedSteps(D, lens, values, tOf) {
  const seen = new Set(), own = D.world.owner;
  for (let i = 0; i < values.length; i++) if (own[i] >= 0 && values[i] != null) seen.add(tOf(values[i]));
  return seen;
}

// 글꼴 목록 (fonts/fonts.json — 쪽 기준 상대 주소). 실패하면 거절한다.
export async function loadFontCredits() {
  const r = await fetch('fonts/fonts.json');
  if (!r.ok) throw new Error(String(r.status));
  const F = await r.json();
  const fonts = (Array.isArray(F.fonts) ? F.fonts : []).map((f) => ({ role: f.role || '', family: f.family_shown || '', note: f.note || '', author: f.author || '', licence: f.licence || '', licenceFile: f.licence_file || '', sourceUrl: f.source_url || '', sourceRef: f.source_ref || '' }));
  const s0 = Array.isArray(F.seal) ? F.seal[0] : F.seal;
  return { fonts, seal: s0 ? (s0.note || s0.source || '') : '' };
}
