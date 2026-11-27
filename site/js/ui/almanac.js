// 연감: 지형 규칙(world.tables), 렌즈 정의, 인구 주석, 출처 목록(sources.json)

import { iconURL, KINDS, PREC_KO } from '../render/layers.js';
// 저장 키 -> 화면 이름 (감사 22)
const SCALE_KO = { log: '로그', linear: '선형', diverging: '발산(중심값 양쪽)', bins: '구간', category: '범주' };
const BASIS_KO = { site_policy: '사이트 이용정책', dataset_page: '자료 상세 페이지', license_doc: '이용허락 문서' };

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
// 자료 링크는 http(s) 주소만 링크로 만든다 (감사 07). 그 밖의 값은 글자로만
const safeURL = (u) => { try { const x = new URL(String(u)); return x.protocol === 'https:' || x.protocol === 'http:' ? x.href : null; } catch (e) { return null; } };

export class Almanac {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('almanac');
    this.el.addEventListener('click', (e) => {
      if (e.target === this.el || e.target.closest('[data-close]')) return this.close();
      const t = e.target.closest('[data-tab]');
      if (t) this.tab(t.dataset.tab);
    });
  }

  isOpen() { return !this.el.hidden; }

  open(tab = 'terrain') {
    this.el.hidden = false;
    this.tab(tab);
  }

  close() { this.el.hidden = true; }

  // 층마다 선정 규칙 문장, 건수, 출처, 기준 연도, 빠진 항목 수와 이유
  layersBody() {
    const L = this.app.layers;
    if (!L) return '<p class="dim">지도 층을 불러오는 중…</p>';
    const fmt = (n) => (n == null ? '–' : Number(n).toLocaleString('ko-KR'));
    let h = '';
    const Z = L.wonders.zoom;
    if (Z) {
      const C = Z.counts || {};
      const kn = (k) => (KINDS[k] ? KINDS[k].label : k);
      h += `<h3>배율에 따른 표시 <small>전국 배율 아이콘 ${esc(Z.national_total)}개 (겹침·깃발 피하기 전)</small></h3><ul>${Z.rules.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>
        <table class="tbl"><thead><tr><th>단계</th><th>시작 배율 z</th><th>그리는 아이콘 (누적, 종류별)</th></tr></thead><tbody>${Z.levels.map((lv) => {
          const c = C[String(lv.tier)] || {};
          return `<tr><th>${esc(lv.name)}</th><td>${esc(lv.z_min)}</td><td>${Object.values(c).reduce((t, v) => t + v, 0)}개 — ${Object.entries(c).sort((x, y) => y[1] - x[1]).map(([k, v]) => `${esc(kn(k))} ${v}`).join(' · ')}</td></tr>`;
        }).join('')}</tbody></table>`;
    }
    if (L.wonders.universities) h += `<h3>연구대학 <small>${L.wonders.universities.status === 'ok' ? '지식 불가사의에 더함' : '자료 없음'}</small></h3><p>${esc(L.wonders.universities.note)}</p>`;
    for (const obj of [L.wonders, L.resources, L.infrastructure]) {
      h += `<h3>${esc(obj.name)} <small>위치 정밀도: ${Object.entries(obj.precision_counts).map(([k, v]) => `${esc(PREC_KO[k] || k)} ${v}`).join(' · ') || '–'}</small></h3>`;
      for (const [kind, k] of Object.entries(obj.kinds)) {
        const ic = KINDS[kind] ? `<img class="ai" src="${iconURL(kind, kind === 'station')}" alt="">` : '';
        const miss = k.missing || [];
        const placed = k.placed != null ? ` · 지도에 놓음 ${fmt(k.placed)}` : '';
        h += `<div class="lensdef"><h3>${ic}${esc(k.name)} <small>${k.count != null ? `${fmt(k.count)}건` : ''}${placed}${k.draft ? ' · 초안' : ''}</small></h3>
          <p>${esc(k.rule)}</p>
          <p class="dim">기준: ${esc(k.year || '–')} · 출처: ${(k.source || []).map((x) => `${esc(x.publisher)} 「${esc(x.title)}」`).join(', ')}</p>
          ${k.excluded && Object.keys(k.excluded).length ? `<p class="dim">뺀 것: ${Object.entries(k.excluded).map(([r, v]) => `${esc(r)} ${v}`).join(' · ')}</p>` : ''}
          ${k.fallback && k.fallback.length ? `<p class="dim">좌표 대신 주소로 놓은 것 ${esc(k.fallback.length)}곳: ${k.fallback.map((x) => esc(x.name)).join(', ')}</p>` : ''}
          ${miss.length ? `<details><summary>빠진 항목 ${esc(miss.length)}건</summary><ul>${miss.map((m) => `<li>${esc(m.name)} — ${esc(m.reason)}</li>`).join('')}</ul></details>` : '<p class="dim">빠진 항목 없음</p>'}</div>`;
      }
    }
    const un = [...L.resources.unplaced, ...L.infrastructure.unplaced];
    h += `<h3>위치가 없어 지도에 놓지 못한 항목 <small>${esc(un.length)}건 · 값은 그대로 싣는다</small></h3>
      <table class="tbl"><tbody>${un.map((u) => `<tr><th>${esc((KINDS[u.kind] || {}).label || u.kind)}</th><td>${esc(u.name)}</td><td>${u.value == null ? '자료 없음' : fmt(u.value) + ' ' + esc(u.unit || '')}${u.year ? ` (${esc(u.year)})` : ''}</td></tr>`).join('')}</tbody></table>`;
    const R = L.resources;
    if (L.frontier) {
      const F = L.frontier;
      h += `<h3>접경지역 <small>${esc(F.areas.length)}곳 · ${esc(F.year)}</small></h3><p>${esc(F.rule)}</p>
        <table class="tbl"><tbody>${F.areas.map((x) => `<tr><th>${esc(x.name)}</th><td>${esc(x.article)}</td></tr>`).join('')}</tbody></table>`;
    }
    if (R.gi) {
      h += `<h3>지리적표시: 지도에 놓지 않은 것 <small>시도 전체 ${esc(R.gi.sido_level.length)} · 목록만 ${esc(R.gi.list_only.length)}</small></h3>
        <ul>${R.gi.sido_level.map((g) => `<li>${esc(g.name)} — ${esc(g.gi_kind)}, 등록지역 '${esc(g.area)}' (시도 패널에 실음)</li>`).join('')}${R.gi.list_only.map((g) => `<li>${esc(g.name)} — ${esc(g.gi_kind)}: ${esc(g.reason)}</li>`).join('')}</ul>`;
    }
    if (R.power) {
      const P = R.power;
      h += `<h3>발전설비 검산 <small>EPSIS 발전기 현황 ${esc(P.date)}</small></h3><p class="dim">발전기 ${fmt(P.generators)}기 · ${fmt(Math.round(P.total_mw))} MW = 시군구 합 ${fmt(Math.round(P.unit_sum_mw))} + 소재지 대응 실패 ${esc(P.failed.count)}기 ${P.failed.mw.toFixed(1)} MW.
        연료원별: ${Object.entries(P.by_fuel_mw).map(([k, v]) => `${esc(P.fuel_ko[k])} ${fmt(Math.round(v))}`).join(' · ')} MW.
        원전 대조: ${P.nuclear_compare.map((n) => `${esc(n.sgg)} ${fmt(n.mw)} MW ↔ 원안위 ${esc(n.nssc_site)} ${fmt(n.nssc_mw)} MW (${n.match ? '일치' : '다름'})`).join('; ')}.</p>`;
    }
    if (R.knowledge) {
      const K = R.knowledge, eok = (v) => (v == null ? '자료 없음' : (v / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 0 }) + '억원');
      const sn = (c) => (this.app.stateByCode.get(c) || {}).short || '–';
      const U = L.wonders.universities;
      h += `<h3>지식 불가사의 <small>${U && U.status === 'ok' ? `기관 주소 8곳 + 연구비 상위 대학 (6단계)` : '주소 8곳은 지도(시군구 대표 위치) · 대학 연구비는 시도까지만이라 순위로만'}</small></h3><p>${esc(K.note)}</p>${U && U.status === 'ok' ? `<p>${esc(U.note)}</p>` : ''}`;
      if (K.funding_top) h += `<h3>대학 연구비 상위 ${esc(K.funding_top.length)} <small>대학알리미 ${esc(K.funding_year)} · ${esc(K.funding_rows)}개 학교·캠퍼스 · ${esc(K.funding_unit)}</small></h3>
        <table class="tbl"><thead><tr><th>순위</th><th>학교</th><th>시도</th><th class="num">연구비</th></tr></thead><tbody>${K.funding_top.map((x) => `<tr><td>${esc(x.rank)}</td><td>${esc(x.name)}</td><td>${esc(sn(x.sido))}</td><td class="num">${eok(x.won)}</td></tr>`).join('')}</tbody></table>`;
      if (K.research_institutes && K.research_institutes.length) h += `<p class="dim">국가과학기술연구회 소관 출연연 (이름만, 지도에 놓지 않음): ${K.research_institutes.map(esc).join(' · ')}</p>`;
    }
    const TJ = L.trade;
    if (TJ) {
      const T = TJ.trade, RT = TJ.routes, a = this.app;
      const usd = (v) => (v / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 1 }) + '억 달러';
      const top = a.cities.filter((c) => c.trade && c.trade.export != null).sort((x, y) => y.trade.export - x.trade.export).slice(0, 15);
      h += `<h3>수출입 <small>관세청 ${esc(T.year)} · 시군구 공표 단위 ${esc(a.nation.nation.trade.units)}곳</small></h3><p>${esc(T.basis)}</p><p>${esc(T.hq_note)}</p><p>${esc(T.hs_rule)}</p><p class="dim">${esc(T.unmatched_note)} ${esc(a.nation.nation.trade.note)}</p>
        <table class="tbl"><thead><tr><th>수출 순위</th><th>도시</th><th class="num">수출</th><th class="num">수입</th></tr></thead><tbody>${top.map((c, k) => `<tr><td>${k + 1}</td><td>${esc(c.name)}</td><td class="num">${usd(c.trade.export)}</td><td class="num">${usd(c.trade.import)}</td></tr>`).join('')}</tbody></table>`;
      const sn = (c) => (a.stateByCode.get(c) || {}).short || c;
      h += `<h3>교역로 <small>도로 화물 ${esc(RT.year)} · 시도 간 ${esc(RT.pairs_total)}쌍 중 상위 ${esc(RT.top_n)}구간 (${(100 * RT.totals.shown_t / RT.totals.inter_t).toFixed(0)}%)</small></h3><p>${esc(RT.rule)}</p>
        <p class="dim">원자료 ${fmt(RT.totals.raw_t)}톤 = 시도 간 ${fmt(RT.totals.inter_t)} + 시도 안 ${fmt(RT.totals.intra_t)} (17개 시도 대각 ${fmt(RT.totals.intra_17_diag_t)} + 광주↔전남 ${fmt(RT.totals.gwangju_jeonnam_t)}, 전남광주 안 흐름으로 봄)</p>
        <details><summary>구간 ${esc(RT.segments.length)}개</summary><table class="tbl"><tbody>${RT.segments.map((g) => `<tr><td>${esc(g.rank)}</td><td>${esc(sn(g.a))}–${esc(sn(g.b))}</td><td class="num">${fmt(g.total)}톤</td><td class="num">${esc(g.share)}%</td></tr>`).join('')}</tbody></table></details>`;
    }
    if (R.farm && R.farm.pigs && R.farm.pigs.sido_compare) {
      const P = R.farm.pigs, sn = (c) => (this.app.stateByCode.get(c) || {}).short || c;
      h += `<h3>돼지 시도 합 대조 <small>방역본부 ${esc(P.year)} 시군 값의 시도 합 / 가축동향조사 2026년 3분기 · 판정하지 않음</small></h3><p class="dim">${esc(P.sido_compare_note)} ${esc(P.note)}. 원표 ${esc(P.raw_rows)}행 합 ${fmt(P.raw_total)}마리, 대응 실패 ${esc(P.unmatched.length)}행.</p>
        <table class="tbl"><thead><tr><th>시도</th><th class="num">시군 값 합</th><th class="num">가축동향조사</th><th class="num">차이 비율</th></tr></thead><tbody>${P.sido_compare.map((r) => `<tr><th>${esc(sn(r.sido))}</th><td class="num">${r.county_sum == null ? '자료 없음' : fmt(r.county_sum)}</td><td class="num">${r.survey == null ? '자료 없음' : fmt(r.survey)}</td><td class="num">${r.diff_ratio == null ? '–' : (r.diff_ratio > 0 ? '+' : '') + (100 * r.diff_ratio).toFixed(1) + '%'}</td></tr>`).join('')}</tbody></table>`;
    }
    if (R.unavailable) h += `<h3>받지 못한 자료</h3><ul>${R.unavailable.map((u) => `<li><b>${esc(u.name)}</b> — ${esc(u.reason)}</li>`).join('')}</ul>`;
    const H = L.wonders.heritage;
    const fl = Object.keys(this.app.layerFailed || {});
    if (fl.length) h = `<p class="na">불러오지 못한 층 파일: ${fl.map((f) => esc(f + '.json')).join(', ')} — 그 층의 항목은 이 목록과 지도에 없습니다.</p>` + h;
    if (H) h += `<h3>국가유산 좌표</h3><p class="dim">원자료 ${Object.entries(H.raw).map(([k, v]) => `${esc(k)} ${esc(v)}`).join(' · ')} · 좌표 유효 ${fmt(H.valid)}건 · 뺀 것 ${Object.entries(H.excluded).map(([k, v]) => `${esc(k)} ${v}`).join(' · ')}</p>`;
    return h;
  }

  // 보훈대상자 렌즈: 파일별 기준 시점, 시도 합계 행 대조, 겹친 파일, 옛 구역 행, 대응 실패
  // 이 판 (sources.json profile): 판 이름, 뺀 것과 까닭, 변경금지 통계 — 출처 목록을 아직 못 받았으면 그 사실만
  profileBody() {
    const P = this.app.sources && this.app.sources.profile;
    if (!P) return this.app.sources ? '' : '<p class="dim">판 안내는 출처 목록(data/sources.json)을 불러오면 보인다.</p>';
    const pub = P.profile === 'public';
    const ex = (P.excluded || []).map((e) => `<li><b>${esc(e.what)}</b> — ${esc(e.why)}${e.instead ? ` <span class="dim">대신: ${esc(e.instead)}</span>` : ''}</li>`).join('');
    const ck = (P.check_needed || []).map((x) => `<li>${esc(x.title)} <small class="dim">${esc(x.publisher || '')} · ${esc(x.license_short || '')} · ${esc((x.where || []).join('; '))}</small></li>`).join('');
    return `<div class="profile ${pub ? 'pub' : 'full'}" role="note"><h3>이 판: ${esc(P.name)} <small>profile ${esc(P.profile)}</small></h3><p>${esc(P.statement)}</p>
      <details><summary>${pub ? '이 판에서 뺀 것' : '공개판에서 빼는 것'} ${(P.excluded || []).length}묶음</summary><ul>${ex}</ul>${ck ? `<p><b>변경금지 통계 — 원 통계를 바꾸지 않음</b> <small class="dim">${esc(P.check_rule || '')}</small></p><ul>${ck}</ul>` : ''}<p class="dim">${esc(P.rule || '')}</p></details></div>`;
  }

  vetAudit(l) {
    const A = l.audit, n = (x) => Number(x).toLocaleString('ko-KR');
    const cn = (c) => esc((this.app.world.counties.find((x) => x.code === c) || {}).name || c);
    const rows = A.sido_check.map((r) => `<tr${r.used ? '' : ' class="dim"'}><th>${esc(r.sido_txt)}</th><td>${esc(r.period)}</td><td class="num">${n(r.county_rows)}</td><td class="num">${n(r.total_row)}</td><td class="num">${r.diff > 0 ? '+' : ''}${n(r.diff)}</td><td>${r.used ? '씀' : '안 씀 (겹친 파일)'}</td></tr>`).join('');
    return `<details><summary>원자료 대조 (파일 ${esc(A.sido_check.length)}개)</summary>
      <table class="tbl"><thead><tr><th>파일 시도</th><th>최신 분기</th><th class="num">시군구 행 합</th><th class="num">시도 합계 행</th><th class="num">차</th><th></th></tr></thead><tbody>${rows}</tbody></table>
      ${A.detail ? `<p>${esc(A.detail)}</p>` : ''}
      ${A.categories_upper ? `<p class="dim">대상구분 상위 ${esc(A.categories_upper.length)}개: ${A.categories_upper.map(esc).join(', ')}</p>` : ''}
      <p class="dim">시군구 값 합 ${n(A.unit_total)}명 + 나눌 수 없는 옛 구역 행 ${n(A.residual.reduce((t, r) => t + r.value, 0))}명 + 대응 실패 ${n(A.unmatched.filter((u) => !A.dropped_files.includes(u.file)).reduce((t, u) => t + u.value, 0))}명 = 원자료 시군구 행 합 ${n(A.raw_county_rows)}명 (겹친 파일 제외). 인구 ${esc(A.pop_ym)}.</p>
      ${A.duplicates.length ? `<p class="dim">두 파일에 나온 시군구 ${esc(A.duplicates.length)}곳 (값이 다른 곳 ${A.duplicates.filter((d) => !d.same).length}): ${A.duplicates.map((d) => `${esc(d.name)} ${Object.entries(d.values).map(([k, v]) => `${k} ${esc(d.periods[k])} ${n(v)}`).join(' / ')}`).join('; ')} → 소재 시도 파일 값.</p>` : ''}
      ${A.residual.length ? `<p class="dim">옛 구역 행: ${A.residual.map((r) => `${esc(r.name)} ${n(r.value)}명 (${r.codes.map(cn).join('·')}) — ${esc(r.reason)}`).join('; ')}</p>` : ''}
      ${A.unmatched.length ? `<p class="dim">대응 실패: ${A.unmatched.map((u) => `${esc(u.sido)} '${esc(u.name)}' ${n(u.value)}명 — ${esc(u.reason)}`).join('; ')}</p>` : '<p class="dim">대응 실패 없음</p>'}
      ${A.no_value.length ? `<p class="dim">값이 없는 시군구: ${A.no_value.map(cn).join(', ')}</p>` : ''}</details>`;
  }

  // 청사: 시도청 소재지(행정안전부 공표본 주소), 전남광주통합특별시 청사 3곳(특별법 제7조제3항)
  officesBody() {
    const a = this.app, O = a.nation.offices;
    if (!O) return '';
    const cname = (codes) => (codes || []).map((c) => (a.world.counties.find((x) => x.code === c) || {}).name || c).join('·');
    const rows = a.states.flatMap((s) => (s.offices || []).map((o) => `<tr><th>${esc(s.short)}</th><td>${esc(o.name)} <small>${esc(o.role)}</small></td><td>${esc(o.address)}</td><td>${esc(cname(o.sgg))}</td></tr>`)).join('');
    const sp = (O.special || []).map((e) => `<li><b>${esc(e.name)}</b> — ${e.sgg ? esc(cname(e.sgg)) + ' (시군구 대표 위치)' : '지도에 놓지 않음'} · ${esc(e.located_by)}</li>`).join('');
    return `<h3>청사 <small>행정안전부 공표본 사무소 소재지 표 ${esc(O.count)}건, 주소 → 시군구 ${esc(O.resolved)}건</small></h3>
      <table class="tbl"><thead><tr><th>시도</th><th>청사</th><th>주소 (원표)</th><th>시군구</th></tr></thead><tbody>${rows}</tbody></table>
      <h3>전남광주통합특별시 청사 <small>${esc(O.law)}</small></h3><p class="dim">특별법이 종전 청사 3곳을 균형 있게 활용·운영하도록 정해 3곳을 모두 적고 수도(주 청사) 별표를 하나로 정하지 않는다. 종전 광주광역시청·전라남도청 행(2025-12-31 기준 공표본)은 청사 위치를 찾는 데만 썼다.</p><ul>${sp}</ul>
      ${O.failed && O.failed.length ? `<p class="dim">주소 처리 예외: ${O.failed.map((f) => `${esc(f.name)} '${esc(f.address)}' — ${esc(f.reason)}`).join('; ')}</p>` : ''}
      ${O.name_mismatch && O.name_mismatch.length ? `<p class="dim">청사 주소의 시군구가 기관 이름의 시군구와 다른 곳(원표 그대로): ${O.name_mismatch.map(esc).join(', ')}</p>` : ''}
      <p class="dim">특례시 표(수원·고양·용인·화성·창원)는 출처를 확인할 공표 자료를 받지 못한 <b>수작업 표</b>다.</p>`;
  }

  tab(id) {
    const a = this.app, t = a.world.tables;
    const tabs = [['terrain', '지형 규칙'], ['lenses', '렌즈 정의'], ['people', '인구·도시'], ['econ', '산출'], ['layers', '지도 층'], ['sources', '출처']];
    let body = '';
    if (id === 'terrain') {
      const tbl = (rows, title) => `<h3>${esc(title)}</h3><table class="tbl"><tbody>${rows.map((r) => `<tr><th>${esc(r.name)}</th><td>${esc(r.rule || '')}</td></tr>`).join('')}</tbody></table>`;
      const W = a.world, td = W.tidal;
      const sname = (c) => (W.states.find((x) => x.code === c) || {}).name || c;
      const tidalTbl = td ? `<h3>갯벌 <small>해양수산부 1:25,000 연안정보도, ${esc(td.year)}년 제작 · 폴리곤 ${td.polygons.toLocaleString('ko-KR')}면 · 넓이 합 ${td.polygon_area_km2.toLocaleString('ko-KR')} km²</small></h3>
        <table class="tbl"><thead><tr><th>시도</th><th>갯벌 칸</th><th>폴리곤 넓이 (km²)</th><th>갯벌이 닿은 해안 육지 칸</th></tr></thead><tbody>${Object.entries(td.by_sido).sort((x, y) => y[1].area_km2 - x[1].area_km2).map(([c, v]) => `<tr><th>${esc(sname(c))}</th><td>${esc(v.tile_cells)}</td><td>${v.area_km2.toLocaleString('ko-KR')}</td><td>${esc(v.land_cells_touched)}</td></tr>`).join('')}</tbody></table>
        <p class="dim">칸에 든 넓이 합 ${td.area_in_cells_km2.toLocaleString('ko-KR')} km² (나머지는 외국 땅 칸·격자 밖). 바다 칸의 시도는 칸 거리로 가장 가까운 육지 칸의 시도.</p>` : '';
      const lm = W.lake_meta;
      const lakeTxt = lm ? `<h3>호수·저수지 <small>대체 자료: © OpenStreetMap 기여자 (ODbL 1.0)</small></h3><p>수면 ${lm.polygons.toLocaleString('ko-KR')}면 가운데 호수 칸이 된 것 ${esc(lm.lake_cells)}칸 (${Object.entries(lm.lake_cells_by_name).map(([k, v]) => `${esc(k)} ${v}칸`).join(', ') || '없음'}). 칸(20.4 km²)의 과반을 덮는 수면이 드물어 대부분의 호수는 칸 위 폴리곤(${esc(lm.draw_min_km2)} km² 이상 ${esc(W.lakes.length)}면)으로만 그린다. 이름표: ${W.lake_labels.map((l) => `${esc(l.name)}(${esc(l.area_km2)} km²)`).join(', ')}.</p>` : '';
      const cm = W.cover_meta;
      const LM = a.nation.land_stats_meta;
      const rs = ((a.sources && a.sources.restrictions) || []).map((r) => `<div class="restrict" role="note"><b>⚠ 이용조건 경고</b><br>${esc(r.text)}</div>`).join('');
      // 토지피복: 두 판 공용 (기후에너지환경부 세분류 토지피복지도 도엽 통계). 글은 모두 world.cover_meta 에서
      const covTxt = cm ? `${rs}<p class="dim">${esc(cm.legend || '')} ${esc(cm.summary || '')}</p>${cm.bias_note ? `<p><b>알려진 치우침:</b> 칸 비율은 ${esc(cm.bias_note)}</p>` : ''}` : '';
      const lsTxt = LM ? `<h3>국가토지피복통계 <small>${esc(LM.year)}년 기준 · 도시·시도·전국 패널의 '땅' 구역</small></h3><p>${esc(LM.rule)}</p>` : '';
      body = this.profileBody() + tbl(t.relief, '기복') + tbl(t.water, '물') + tbl(t.cover, (cm && cm.table_title) || '피복') + covTxt + lsTxt + lakeTxt + tidalTbl +
        `<h3>격자와 판정</h3><ul>${t.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul>` +
        `<p class="dim">격자 ${esc(a.world.grid.cols)}×${esc(a.world.grid.rows)} · 칸 넓이 ${esc(a.world.hex_km2)} km² · 1 화면 단위 = ${esc(a.world.meters_per_unit)} m · 원점(EPSG:5179) ${esc(a.world.origin_5179.join(', '))}</p>`;
    } else if (id === 'lenses') {
      const grp = new Map(a.lenses.groups.map((g) => [g.id, g.name]));
      const RV = a.lenses.retired_values;
      body = `<h3>렌즈 막대 <small>${esc(a.lenses.groups.length)}묶음 ${esc(a.lenses.lenses.length)}종</small></h3><p>${a.lenses.groups.map((g) => `<b>${esc(g.name)}</b> ${a.lenses.lenses.filter((l) => l.group === g.id).map((l) => esc(l.name)).join(' · ')}`).join('<br>')}</p>` +
        (RV ? `<h3>렌즈 막대에서 뺀 지표 <small>${esc(RV.items.length)}개 · 값은 시군구 값으로 남음</small></h3><p>${esc(RV.rule)}</p><table class="tbl"><thead><tr><th>지표</th><th>남은 자리</th><th>옛 링크가 가는 렌즈</th></tr></thead><tbody>${RV.items.map((x) => `<tr><th>${esc(x.emoji)} ${esc(x.name)}</th><td>${esc(x.level)} · 값 있는 시군구 ${esc(x.counties_with_value)}${x.units_note ? `<br><small class="unitnote">${esc(x.units_note)}</small>` : ''}</td><td>${esc((a.lensById.get(x.near) || {}).name || x.near)}</td></tr>`).join('')}</tbody></table>` : '') +
        a.lenses.lenses.map((l) => `<div class="lensdef"><h3>${esc(l.emoji)} ${esc(l.name)} <small>${esc(l.unit)} · ${esc(grp.get(l.group) || '')}</small></h3><p>${esc(l.description)}</p>${l.units_note ? `<p class="unitnote">${esc(l.units_note)}</p>` : ''}
        <p class="dim">척도 ${esc(SCALE_KO[l.scale] || l.scale)} · 색 범위 ${esc(l.domain.join(' – '))} · ${l.higher_is === 'good' ? '높을수록 좋음' : l.higher_is === 'bad' ? '낮을수록 좋음' : '방향 없음'} · ${esc(l.source)}</p>${l.audit ? this.vetAudit(l) : ''}</div>`).join('') +
        `<ul>${a.lenses.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul>`;
    } else if (id === 'people') {
      const n = a.nation.notes;
      body = `<h3>도시 정의</h3><ul>
        <li>특별·광역시의 자치구는 한 도시로 묶고, 그 안의 군(기장·달성·군위·강화·옹진·울주)은 따로 둔다.</li>
        <li>'…시 …구' 꼴의 일반구는 앞의 시로 묶는다. 세종은 한 도시, 제주시·서귀포시는 각각 도시.</li>
        <li>${esc(n.gwangju)}</li><li>나머지 시·군은 각각 한 도시. 결과 ${esc(a.cities.length)}곳.</li></ul>
        <h3>주석</h3><ul>${Object.values(n).map((x) => `<li>${esc(x)}</li>`).join('')}</ul>${this.officesBody()}`;
    } else if (id === 'econ') {
      const E = a.nation.econ;
      const cov = E.coverage;
      const noY = a.cities.filter((c) => c.yields && Object.values(c.yields).some((v) => v == null));
      body = `<h3>다섯 산출 <small>모두 GRDP 경제활동별 부가가치 (명목, 생산지 기준, 원)</small></h3>
        <table class="tbl"><tbody>${E.yields.map((y) => `<tr><th>${esc(y.emoji)} ${esc(y.name)}</th><td>${esc(y.rule)}</td></tr>`).join('')}</tbody></table>
        <h3>알고 쓰는 한계</h3><ul>${E.limits.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>
        <h3>계산 규칙</h3><ul>
          <li>도시 = 소속 시군구의 합. 일반구가 있는 시는 시 전체로만 공표된 값을 그대로 쓰고 구에 나누지 않는다.</li>
          <li>도시마다 GRDP 가 있는 가장 최근 연도를 쓴다 (gdp_year). 시도·전국은 도시 합이 아니라 소속 시군구 합이다. 전국 기준: ${esc(a.nation.nation.gdp_year_label || '')}.</li>
          <li>${esc(E.undisclosed_note)}</li><li>${esc(E.per_capita_note)}</li><li>${E.housing_note ? esc(E.housing_note) : '아파트 매매·전세: 이 판(공개판)에서는 제공하지 않음 — 연감 › 출처의 판 안내'}</li><li>${esc(E.national_note)}</li>
          <li>${esc(E.growth_note || '')}</li>
          <li>${esc(E.official_note || '')}</li><li>${esc(E.combined_note || '')}</li>
          <li>${esc(E.jobs_note)}</li><li>${esc(E.jobs_vs_grdp_note)}</li>
          <li>패널 위 다섯 산출 칸은 도시의 경우 시군구 합 명목 부가가치와 도시 ${esc(a.cities.length)}곳 중 순위를, 시도·전국은 공식 지역소득 값을 한 줄로 요약한다. 점선 테두리와 * 표시는 광업 비공개 몫을 뺀 부분 합계(제조업 + 건설업 + 공개된 광업)다. 칸을 누르면 구성 산업과 사업장 기준 종사자 수(식량 = A, 생산 = B + C + F, 과학 = J + M, 문화 = R, 금 = 전산업)가 나온다.</li>
          <li>${esc(a.nation.nation.peer_rule || '닮은 도시는 인구(로그)·고령 비율·1인당 GRDP(로그)·산업 16분류 비중의 표준화 거리로 고른다.')}</li></ul>
        ${a.nation.nation.lq_rule ? `<h3>입지계수와 도시 특성 표시</h3><ul><li>${esc(a.nation.nation.lq_rule)}</li><li>${esc(a.nation.nation.tag_rule || '')}</li></ul>` : ''}
        ${a.nation.nation.benchmarks ? `<h3>전국 기준 대비와 순위 막대</h3><p>${esc(a.nation.nation.benchmarks.rule)}</p><table class="tbl"><tbody>${Object.values(a.nation.nation.benchmarks.metrics).map((m) => `<tr><th>${esc(m.label)}</th><td>${m.ref === 'city_median' ? `도시 중앙값 (${esc(m.n)}곳)` : '전국'} ${esc(String(m.v))}${esc(m.unit === '%' ? '%' : m.unit === '원' ? '원' : m.unit === '만원' ? '만원' : m.unit)} · ${m.mode === 'ratio' ? '배수' : '차이'}</td></tr>`).join('')}</tbody></table>` : ''}
        <h3>덮은 범위</h3><ul>
          <li>GRDP 가 있는 도시 ${esc(cov.cities_with_gdp)}/${esc(a.cities.length)}곳, 다섯 산출이 모두 있는 도시 ${esc(cov.cities_all_yields)}곳.</li>
          <li>생산이 부분 합계(광업 비공개 몫 제외, 값 옆 * 표식)인 곳: 도시 ${esc(cov.cities_production_partial)}곳 · 시도 ${esc(cov.states_production_partial)}곳 · 전국 합계에서 빠진 공표 단위 ${esc(cov.nation_production_mining_excluded)}곳.
            도시: ${a.cities.filter((c) => c.yields_partial && c.yields_partial.production).map((c) => `${esc(c.name)}(광업 비공개 ${esc(c.production_mining_excluded)}곳 제외)`).join(', ')}</li>
          <li>산출이 빈 도시: ${noY.map((c) => `${esc(c.name)}(${Object.entries(c.yields).filter(([, v]) => v == null).map(([k]) => ({ food: '식량', production: '생산', gold: '금', science: '과학', culture: '문화' })[k]).join('·')})`).join(', ') || '없음'}</li>
          <li>렌즈별 값이 있는 육지 칸: ${Object.entries(cov.lens_land_coverage_pct).map(([k, v]) => `${esc(a.lensById.get(k)?.name || a.retiredById.get(k)?.name || k)}${a.lensById.has(k) ? '' : '(뺀 렌즈)'} ${v}%`).join(' · ')}</li></ul>`;
    } else if (id === 'layers') {
      body = this.layersBody();
    } else if (!a.sources) {
      body = `<p class="na">출처 목록(data/sources.json)을 불러오지 못했습니다. 새로 고침하거나 화면 위 안내의 '다시 시도'를 누르십시오.</p><p class="srcpage"><a href="sources/">출처와 이용조건 쪽</a>에서도 볼 수 있습니다.</p>`;
    } else {
      const s = a.sources.sources;
      const unk = s.filter((x) => x.license === '미확인').length;
      const lic = (x) => {
        const t = esc(x.license || '미확인');
        const v = safeURL(x.license_url) ? `<a href="${esc(safeURL(x.license_url))}" target="_blank" rel="noopener">${t}</a>` : t;
        const sub = [x.license_from === '수집 기록' ? '수집 기록' : '', BASIS_KO[x.license_basis] || x.license_basis || '', x.license_checked ? `확인 ${esc(x.license_checked)}` : ''].filter(Boolean).join(' · ');
        return `${x.restriction ? `<div class="restrict" role="note"><b>⚠ 공개 배포 금지 — 내부 열람용</b><br>${esc(x.restriction)}</div>` : ''}<span class="${x.license === '미확인' ? 'na' : ''}">${v}</span>${sub ? `<br><small class="dim">${esc(sub)}</small>` : ''}${x.license_note ? `<br><small class="dim">${esc(x.license_note)}</small>` : ''}${x.license_collected ? `<br><small class="dim">수집 기록의 값(확인 표에서는 미확인): ${esc(x.license_collected)}</small>` : ''}${x.use_scope ? `<br><small class="unitnote">사용 범위: ${esc(x.use_scope)}</small>` : ''}`;
      };
      body = `<p class="srcpage">📑 <a href="sources/">출처와 이용조건 쪽</a> — 기관별 목록·출처 표기·조건이 있는 자료·글꼴 (두 판 공용)</p><p class="srcpage">🎒 <a href="edu/">교육의 활용 쪽</a> — 수업안·짧은 활동·교사용 안내 (두 판 공용)</p>${this.profileBody()}
        ${(a.sources.restrictions || []).map((r) => `<div class="restrict" role="note"><b>⚠ 이용조건 경고: ${esc(r.title)}</b><br>${esc(r.text)}</div>`).join('')}
        <p>${esc(a.sources.license_rule || '')} 출처 ${esc(s.length)}건 가운데 이용허락 미확인 ${unk}건.</p>
        <table class="tbl src"><thead><tr><th>자료</th><th>기관</th><th>기준</th><th>이용허락</th><th>쓴 곳</th></tr></thead><tbody>${s.map((x) => `<tr${x.restriction ? ' class="restricted"' : ''}>
        <td>${safeURL(x.url) ? `<a href="${esc(safeURL(x.url))}" target="_blank" rel="noopener">${esc(x.title)}</a>` : esc(x.title)}${x.sha256 ? `<br><code title="sha256">${esc(x.sha256.slice(0, 16))}…</code>` : ''}${x.files && x.files.length ? `<br><small class="dim">파일 ${esc(x.files.length)}개 (파일별 sha256)</small>` : ''}${x.manual ? `<br><small class="dim">수작업 표: ${esc(x.file)}${x.basis ? ' — ' + esc(x.basis) : ''}</small>` : ''}${x.derived_table ? `<br><small class="dim">원자료 data/raw/${esc(x.file)} → 정리표 ${esc(x.derived_table)}</small>` : ''}</td>
        <td>${esc(x.publisher)}</td><td>${esc(x.vintage)}</td><td class="lic">${lic(x)}</td><td>${esc(x.used_in)}</td></tr>`).join('')}</tbody></table>
        <ul>${a.sources.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul>`;
    }
    this.el.innerHTML = `<div class="sheet"><button class="close" data-close title="닫기">×</button><h2>📖 연감</h2>
      <nav>${tabs.map(([k, v]) => `<button data-tab="${k}" class="${k === id ? 'on' : ''}">${v}</button>`).join('')}</nav>
      <div class="body">${body}</div></div>`;
  }
}
