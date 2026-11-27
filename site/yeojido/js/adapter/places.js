// 자료 어댑터 (장) — 고을·시도·전국·층 항목·교역로 장이 읽는 보기 모형을 만든다.
// cities/states/nation/trade/층 항목의 원자료 모양은 여기서만 읽는다. 장(ui/panel.js)은 아래 모형만 그린다.
//
// 보기 모형: { kind, title, kicker, badges, sub, scope, head, sections: [{id, title, caption, open, blocks, notes}] }
// 블록(type): yields · tabs(bars 여럿) · bars · kv · pyramid · ext · strip · chips · list · table · text · warn · sortlist
// 값: {t:'won'|'usd'|'pct'|'int'|'fix'|'text', v, unit, d, sign} — 없으면 {t:'na', why}. 0 으로 바꾸지 않는다.

import { fmtWon, fmtInt, fmtFixed, fmtPct, fmtUsd, fmtMan, fmtWhen, isNum, lensValueText } from '../fmt.js';
import { lensValues } from './core.js';

const arr = (v) => (Array.isArray(v) ? v : []);
const obj = (v) => (v && typeof v === 'object' ? v : {});
const NAV = (why) => ({ t: 'na', why: why || '' });
const won = (v, why) => (isNum(v) ? { t: 'won', v } : NAV(why));
const usd = (v, why) => (isNum(v) ? { t: 'usd', v } : NAV(why));
const pct = (v, d = 1, why) => (isNum(v) ? { t: 'pct', v, d } : NAV(why));
const int = (v, unit = '', why) => (isNum(v) ? { t: 'int', v, unit } : NAV(why));
const fix = (v, d = 1, unit = '', why) => (isNum(v) ? { t: 'fix', v, d, unit } : NAV(why));
const txt = (s) => ({ t: 'text', v: String(s) });
const ton = (v) => (isNum(v) ? fmtInt(v / 1e4) + '만 톤' : '자료 없음');
const eok = (v) => (isNum(v) ? fmtInt(v / 1e8) + '억원' : '자료 없음');

export const YIELD_KEYS = ['food', 'production', 'gold', 'science', 'culture'];
const YNAME = { food: '식량', production: '생산', gold: '금', science: '과학', culture: '문화' };
const YRULE = { food: '농림어업', production: '제조+건설+광업', gold: '지역내총생산', science: '정보통신+사업서비스', culture: '문화·기타서비스' };
const PREC_KO = { point: '좌표', area: '경계 대표점', county: '시군구 대표 위치', sido: '시도 대표 위치', list: '목록만' };
const PREC_LONG = {
  point: '원자료 좌표',
  area: '경계 폴리곤 대표점',
  county: '주소의 시군구, 인구 가중 중심 칸 (시군구 대표 위치)',
  sido: '위치 문자열에 시도뿐: 시도의 해안 칸 중 인구 중심에 가까운 칸 (시도 대표 위치)',
};
const PLACE_FROM = {
  area: '등록지역 문자열의 시군구', name: '품목 이름이 시·군 이름으로 시작',
  heritage_name: '이름이 같은 국가유산의 좌표', address: '소재지·주소 문자열의 시군구',
  observation: '이름이 같은 WAMIS 댐 관측소 좌표', city: '도시 합계 — 도시 시군구의 인구 가중 중심 칸',
};

const econOf = (D) => obj(obj(D.nationRaw).econ);
const countyName = (D, code) => { const k = D.world.countyIndex.get(String(code)); return k != null ? D.world.counties[k].name : String(code); };
const countyNames = (D, codes) => arr(codes).map((c) => countyName(D, c)).join('·');

// 부분 합(생산: 광업 일부 비공개) 문구. 없으면 null
function partialNote(o, k) {
  const p = obj(o.yields_partial)[k];
  if (!p || !p.length) return null;
  return `광업 비공개 ${o.production_mining_excluded || 0}곳 제외`;
}
export function cityPartial(c, k) { return partialNote(c.raw, k); }

function seriesOf(o) {
  const s = obj(o.pop_series);
  return Object.keys(s).sort().map((k) => ({ k, v: isNum(s[k]) ? s[k] : null }));
}

// ---------- 머리 (인구) ----------
function headOf(o, vintage, rank, n) {
  return {
    pop: isNum(o.population) ? o.population : null,
    rank: rank || null, of: n || null,
    growth5: isNum(o.growth_5y) ? o.growth_5y : null,
    growthLabel: '다섯 해(2020→2025)',
    series: seriesOf(o),
    vintage, when: `${fmtWhen(vintage)} 주민등록`,
  };
}

// ---------- 나이 ----------
function ageSection(o, vintage) {
  const a = obj(o.age), p = obj(o.pyramid);
  const blocks = [];
  if (arr(p.male).length && arr(p.female).length) blocks.push({ type: 'pyramid', male: p.male, female: p.female, caption: `${fmtWhen(vintage)} · 다섯 살 계급` });
  else blocks.push({ type: 'text', na: true, text: '나이 계급 자료 없음' });
  blocks.push({ type: 'kv', cols: 3, rows: [
    { label: '65세 이상', value: pct(a.over65) },
    { label: '0–14세', value: pct(a.under15) },
    { label: '15–64세', value: pct(a.working) },
    { label: '평균 나이(추정)', value: fix(a.mean_est, 1, '세') },
    { label: '중위 나이(추정)', value: fix(a.median_est, 1, '세') },
    { label: '청년 성비', sub: '20–39세 여 100명당 남', value: fix(o.sex_ratio_20_39, 1) },
  ] });
  blocks.push({ type: 'ext', index: isNum(o.extinction_index) ? o.extinction_index : null, stage: o.extinction_stage || null,
    formula: `20–39세 여성 ${fmtPct(a.women_20_39)} ÷ 65세 이상 ${fmtPct(a.over65)}. 0.5 미만 소멸위험, 0.2 미만 고위험.` });
  return { id: 'age', title: '나이', caption: `${fmtWhen(vintage)} 주민등록`, blocks, notes: [] };
}

// ---------- 산업 막대 ----------
function gvaBars(b, E, caption) {
  if (!b) return { type: 'text', na: true, text: 'GRDP 자료 없음' };
  const ko = obj(E.industry_ko), keys = [...arr(E.industry_keys), 'net_taxes'];
  const rows = keys.map((k) => ({ label: ko[k] || k, v: isNum(b[k]) ? b[k] : null, share: isNum(b[k]) && isNum(b.grdp) && b.grdp ? (100 * b[k]) / b.grdp : null, dim: k === 'net_taxes' }))
    .sort((x, y) => (y.v ?? -1) - (x.v ?? -1));
  return { type: 'bars', caption, fmt: 'won', naText: '비공개', rows, top: 6 };
}
function jobBars(jobs, total, E, caption) {
  if (!jobs) return { type: 'text', na: true, text: '산업 대분류 종사자 자료 없음' };
  const ko = obj(E.ksic_ko);
  const rows = Object.keys(ko).map((k) => ({ label: `${k} ${ko[k]}`, v: isNum(jobs[k]) ? jobs[k] : null, share: isNum(jobs[k]) && total ? (100 * jobs[k]) / total : null }))
    .sort((x, y) => (y.v ?? -1) - (x.v ?? -1));
  return { type: 'bars', caption: `${caption} · 합계 ${isNum(total) ? fmtInt(total) + '명' : '비공개'}`, fmt: 'people', naText: '비공개', rows, top: 6 };
}

// ---------- 산출 + 산업 + 살림 (고을·시도·전국 공통) ----------
function econSections(D, o, kind, nCities) {
  const E = econOf(D);
  if (!Object.keys(E).length) return [];
  if (!isNum(o.gdp)) return [{ id: 'yields', title: '산출', caption: '', blocks: [{ type: 'text', na: true, text: 'GRDP 자료 없음' }], notes: [] }];
  const yr = o.gdp_year_label || o.gdp_year || '';
  const r = obj(o.ranks);
  const OF = kind !== 'city' && o.official ? o.official : null;
  const OG = OF && OF.gdp ? OF.gdp : null;
  const und = arr(Array.isArray(o.gdp_undisclosed) ? o.gdp_undisclosed : []);
  const undNames = und.map((x) => obj(E.industry_ko)[x] || x);
  const pnP = partialNote(o, 'production');
  const jm = obj(E.jobs_map), ksic = obj(E.ksic_ko);

  const items = YIELD_KEYS.map((k) => {
    const pn = partialNote(o, k);
    const sv = obj(o.yields)[k];
    if (OG) {
      const lv = OG.latest ? obj(OG.latest.yields)[k] : null;
      const subs = [`시군구 합 ${isNum(sv) ? fmtWon(sv) + (pn ? `* (${pn})` : '') : '자료 없음'}`];
      if (OG.latest && isNum(lv)) subs.push(`${OG.latest.label} ${fmtWon(lv)}`);
      return { key: k, name: YNAME[k], rule: `${YRULE[k]} · 공식 ${OG.year}${OG.combined ? ' · ' + OG.combined : ''}`, value: won(obj(OG.yields)[k]), subs };
    }
    const why = !isNum(sv) ? `구성 산업 비공개: ${undNames.join(', ')}` : '';
    const rank = kind === 'city' ? r[k === 'gold' ? 'gdp' : k] : null;
    let jobs = null;
    if (o.jobs && (jm[k] || k === 'gold')) {
      const vals = k === 'gold' ? [o.jobs_total] : jm[k].map((L) => o.jobs[L]);
      jobs = { text: vals.some((v) => !isNum(v)) ? '종사자 비공개 포함' : `종사자 ${fmtInt(vals.reduce((s, v) => s + v, 0))}명`,
        tip: `${k === 'gold' ? '전산업 종사자' : jm[k].map((L) => `${L} ${ksic[L] || ''}`).join(' + ')} · ${o.jobs_year_label || o.jobs_year || ''} · 사업장 소재지` };
    }
    return { key: k, name: YNAME[k], rule: YRULE[k], value: won(sv, why), partial: pn, rank: rank || null, jobs };
  });
  const yNotes = [];
  if (!OG && und.length) yNotes.push(`비공개 산업: ${undNames.join(', ')} — 이 산업이 든 산출은 '자료 없음'으로 둔다 (추정으로 메우지 않음).${pnP ? ` 단 생산은 광업 일부만 비공개라 제조업 + 건설업 + 공개된 광업의 합으로 냈다 (* ${pnP}, 비공개 몫은 추정하지 않음).` : ''}`);
  else if (!OG && pnP) yNotes.push(`* 생산은 제조업 + 건설업 + 공개된 광업의 합이다. ${pnP} (비공개 몫을 추정해 더하지 않음).`);
  if (E.undisclosed_note && (und.length || pnP)) yNotes.push(E.undisclosed_note);
  const yBlocks = [{ type: 'yields', items, of: kind === 'city' ? nCities : null }];
  if (OG) yBlocks.push({ type: 'text', text: `공식 GRDP ${fmtWon(OG.grdp)} · 시군구 합 ${fmtWon(o.gdp)} (${yr}) · 차이 ${fmtWon(OG.grdp - o.gdp)}${OG.latest ? ` · ${OG.latest.label} ${fmtWon(OG.latest.grdp)}` : ''}` });
  const out = [{ id: 'yields', title: '산출', caption: `${OG ? `공식 GRDP ${OG.year} (지역소득) · 시군구 합 ${yr} 병기` : `지역내총생산 ${yr}`} · 명목 · 생산지 기준${kind === 'city' ? ` · 순위는 고을 ${nCities}곳 중` : ''}`, blocks: yBlocks, notes: yNotes }];

  // 산업과 일터
  const tabs = [];
  if (OG) {
    tabs.push({ id: 'gva', label: '부가가치 (공식)', block: gvaBars(OG.by, E, `공식 ${OG.year} · 지역소득 33개 분류를 16 + 순생산물세로 묶음${OG.combined ? ' · ' + OG.combined : ''}`) });
    tabs.push({ id: 'gva_sgg', label: '부가가치 (시군구 합)', block: gvaBars(o.gdp_by_industry, E, `시군구 합 ${yr} · GRDP 19분류 중 산업 16 + 순생산물세 · 생산지`) });
  } else tabs.push({ id: 'gva', label: '부가가치', block: gvaBars(o.gdp_by_industry, E, `${yr} · GRDP 19분류 중 산업 16 + 순생산물세 · 생산지`) });
  const oj = OF && OF.jobs ? OF.jobs : null;
  if (oj) tabs.push({ id: 'jobs', label: '종사자 (공식)', block: jobBars(oj.by, oj.total, E, `공식 ${oj.year} 전국사업체조사${oj.combined ? ' · ' + oj.combined : ''} · 사업장 소재지`) });
  tabs.push({ id: oj ? 'jobs_sgg' : 'jobs', label: oj ? '종사자 (시군구 합)' : '종사자', block: jobBars(o.jobs, o.jobs_total, E, `${o.jobs_year_label || o.jobs_year || ''} · 사업장 소재지 기준`) });
  const iNotes = [E.jobs_note, E.jobs_vs_grdp_note, ...arr(E.limits)].filter(Boolean);
  out.push({ id: 'industry', title: '산업과 일터', caption: '', blocks: [{ type: 'tabs', tabs }], notes: iNotes });

  // 살림
  const h = obj(o.housing), em = obj(o.employment), wk = obj(o.workers), fm = obj(o.farm), g = o.gdp_growth, MR = obj(o.member_ranges);
  const multi = kind !== 'city' || (arr(o.sgg).length > 1 && !String(o.name || '').endsWith('시'));
  const rk = (k) => (kind === 'city' && r[k] ? { rank: r[k], of: nCities } : {});
  const rng = (R, period) => (R && isNum(R.min) ? { range: { label: R.unit_label, min: R.min, max: R.max, unit: '%' }, subs: [`${R.n === R.of ? `${R.unit_label} ${R.n}곳` : `${R.of}곳 중 ${R.n}곳 값 있음`} · ${period || ''} · 범위(합치지 않음)`] } : null);
  const OS = kind === 'city' ? o.official_sido : null;
  const osE = (k) => (OS && OS.employment && isNum(OS.employment[k]) ? [`${OS.scope} ${OS.employment[k].toFixed(1)}% (${OS.employment.label}) · 다른 조사`] : []);
  const rows = [];
  const pctSign = (v) => (isNum(v) ? { t: 'pct', v, d: 1, sign: true } : null);
  const partsTxt = (parts, f) => (parts ? Object.entries(parts).map(([p, v]) => `${p} ${f(v)}`).join(' · ') : '');
  const p1 = (v) => (isNum(v) ? v.toFixed(1) + '%' : '자료 없음');
  if (OF) {
    const og = OF.gdp, oe = OF.employment, fi = OF.fiscal, fa = OF.farm;
    if (og) {
      rows.push({ label: '1인당 GRDP', sub: `공식 ${og.year}`, value: won(og.per_capita), subs: [`시군구 합 ${isNum(o.gdp_per_capita) ? fmtWon(o.gdp_per_capita) : '자료 없음'}`] });
      rows.push({ label: '명목 증가율', sub: `공식 ${og.growth ? `${og.growth.from}→${og.growth.to}` : ''}`, value: (og.growth && pctSign(og.growth.rate)) || NAV(), subs: g ? [`시군구 합 ${g.from}→${g.to} ${fmtPct(g.rate, 1, true)}`] : [] });
    }
    if (oe) {
      const lab = oe.label || (oe.parts ? '경제활동인구조사' : '');
      rows.push({ label: '고용률', sub: lab, value: isNum(oe.rate) ? pct(oe.rate) : txt(partsTxt(oe.parts, (v) => p1(v.rate)) || '자료 없음'),
        subs: [...(isNum(oe.rate) && oe.parts ? [partsTxt(oe.parts, (v) => p1(v.rate))] : []), '시군구 값(지역별고용조사, 반기)과 다른 조사'], note: oe.note });
      rows.push({ label: '실업률', sub: lab, value: isNum(oe.unemployment) ? pct(oe.unemployment) : txt(partsTxt(oe.parts, (v) => p1(v.unemployment)) || '자료 없음'),
        subs: isNum(oe.unemployment) && oe.parts ? [partsTxt(oe.parts, (v) => p1(v.unemployment))] : [] });
    }
    if (fi) rows.push({ label: '재정자립도', sub: `지방재정365 ${fi.year} 당초 · ${kind === 'nation' ? '단체별 평균' : '시도 전체 평균'}`,
      value: isNum(fi.avg) ? pct(fi.avg) : txt(partsTxt(fi.parts, (v) => p1(v.avg)) || '자료 없음'),
      subs: isNum(fi.avg) ? (isNum(fi.hq) ? [`본청 ${fi.hq.toFixed(1)}%`] : []) : [`본청 ${partsTxt(fi.parts, (v) => p1(v.hq))} · 비율이라 더하지 않음`], note: fi.note });
    if (fa) {
      const c = fa.combined ? ` · ${fa.combined}` : '';
      rows.push({ label: '논', sub: `농업면적조사 ${fa.year}${c}`, value: int(fa.paddy_ha, 'ha'), subs: isNum(fm.paddy_ha) ? [`시군구 합 ${fmtInt(fm.paddy_ha)}ha`] : [] });
      rows.push({ label: '밭', sub: `농업면적조사 ${fa.year}${c}`, value: int(fa.field_ha, 'ha'), subs: isNum(fm.field_ha) ? [`시군구 합 ${fmtInt(fm.field_ha)}ha`] : [] });
    }
  } else {
    rows.push({ label: '1인당 GRDP', sub: String(yr), value: won(o.gdp_per_capita), ...rk('gdp_per_capita'), dist: 'gdp_per_capita' });
    rows.push({ label: '명목 증가율', sub: g ? `${g.from}→${g.to}` : '', value: (g && pctSign(g.rate)) || NAV('비교할 이전 연도 GRDP 가 정리표에 없음'),
      subs: g && g.series && g.series !== '같은 표' ? ['과거표 이어 붙임 (2020년 기준 개편)'] : [], note: g && g.series && g.series !== '같은 표' ? g.series : null });
  }
  rows.push({ label: '1인당 총급여', sub: `${obj(o.wage).year || ''} 귀속 · 주소지`, value: won(obj(o.wage).per_filer), ...rk('wage'), dist: 'wage' });
  // 공개판(profile public)에는 아파트 매매·전세 값이 없다 — 한 줄로 '이 판에서는 제공하지 않음'
  const hasH = 'housing' in o;
  if (hasH) {
    rows.push({ label: '아파트 매매 ㎡당', sub: h.months || '', value: isNum(h.sale_per_m2) ? won(h.sale_per_m2 * 1e4) : NAV(), ...rk('housing'), subs: isNum(h.trades) ? [`매매 ${fmtInt(h.trades)}건`] : [], dist: 'housing' });
    rows.push({ label: '아파트 매매 중위', sub: h.months || '', value: isNum(h.sale_median) ? won(h.sale_median * 1e4) : NAV() });
    rows.push({ label: '아파트 전세 중위', sub: h.months || '', value: isNum(h.jeonse_median) ? won(h.jeonse_median * 1e4) : NAV(), subs: isNum(h.jeonse_trades) ? [`전세 ${fmtInt(h.jeonse_trades)}건`] : [] });
  } else rows.push({ label: '아파트 매매·전세', sub: '공개판', value: txt('이 판에서는 제공하지 않음'), subs: ['연감 › 출처의 「이 판」'] });
  if (!OF) {
    const e1 = isNum(em.rate) ? { value: pct(em.rate) } : rng(MR.employment, em.period) || { value: NAV(multi ? '시군 단위로만 공표 (여러 구의 비율은 합칠 수 없음)' : '') };
    rows.push({ label: '고용률', sub: `${em.period || ''} · 지역별고용조사`, ...e1, subs: [...(e1.subs || []), ...osE('rate')], dist: 'employment' });
    const e2 = isNum(em.unemployment) ? { value: pct(em.unemployment) } : rng(MR.unemployment, em.period) || { value: NAV() };
    rows.push({ label: '실업률', sub: `${em.period || ''} · 지역별고용조사`, ...e2, subs: [...(e2.subs || []), ...osE('unemployment')] });
    const f1 = isNum(o.fiscal_independence) ? { value: pct(o.fiscal_independence) } : rng(MR.fiscal, o.fiscal_year) || { value: NAV(multi ? '자치구별로만 공표' : '') };
    const osF = OS && OS.fiscal && isNum(OS.fiscal.avg) ? [`${OS.scope} 평균 ${OS.fiscal.avg.toFixed(1)}% · 본청 ${isNum(OS.fiscal.hq) ? OS.fiscal.hq.toFixed(1) + '%' : '자료 없음'} (지방재정365 ${OS.fiscal.year} 당초)`] : [];
    rows.push({ label: '재정자립도', sub: String(o.fiscal_year || ''), ...f1, subs: [...(f1.subs || []), ...osF], dist: 'fiscal' });
  }
  rows.push({ label: '소멸위험지수', sub: '20–39세 여성 ÷ 65세 이상', value: fix(o.extinction_index, 2), ...(kind === 'city' && r.extinction ? { rank: r.extinction, of: nCities, rankNote: '1위 = 가장 위험' } : {}), dist: 'extinction' });
  const topN = rows.length;
  rows.push({ label: '종사자', sub: `${wk.year || ''} · 사업장`, value: int(wk.total, '명') });
  rows.push({ label: '제조업 종사자', sub: String(wk.manufacturing_year || ''), value: int(wk.manufacturing, '명') });
  rows.push({ label: '농가', sub: String(fm.year || ''), value: int(fm.households, '가구'), subs: isNum(fm.population) ? [`${fmtInt(fm.population)}명`] : [] });
  if (!(OF && OF.farm)) {
    rows.push({ label: '논', sub: String(fm.land_year || ''), value: int(fm.paddy_ha, 'ha', '여러 구를 합친 항목으로만 공표됐거나 자료 없음') });
    rows.push({ label: '밭', sub: String(fm.land_year || ''), value: int(fm.field_ha, 'ha') });
  }
  const dg = obj(o.degree);
  rows.push({ label: '대졸 이상', sub: `${dg.year || ''} · 15세 이상`, value: pct(dg.share_15), subs: [isNum(dg.share_25) ? `25세 이상 ${dg.share_25.toFixed(1)}%` : '25세 이상: 계산 불가 (15–24세 칸 비공개)'] });
  const lNotes = [`1인당 GRDP 는 생산지 기준 총생산을 같은 해 12월 주민등록 인구로 나눈 값이라 통근 유입이 큰 도시가 높게 나온다.${hasH ? ` 아파트 가격은 ${h.months || ''} 12개월 실거래 전체(해제 제외)의 중위값을 건별 원자료에서 직접 계산했다.` : ''}`,
    E.per_capita_note, E.housing_note, (MR.employment || MR.fiscal) ? E.range_note : null, ...rows.map((x) => x.note)].filter(Boolean);
  out.push({ id: 'living', title: '살림', caption: kind === 'city' ? `순위는 고을 ${nCities}곳 중` : '', blocks: [{ type: 'kv', leader: true, rows, top: topN, restLabel: '일터·농가·학력' }], notes: [...new Set(lNotes)] });
  return out;
}

// 살림 표의 전국 분포선: 고을 167곳의 값 (없는 곳은 뺀다)
function distOf(D, key) {
  const get = { gdp_per_capita: (c) => c.gdp_per_capita, wage: (c) => obj(c.wage).per_filer, housing: (c) => obj(c.housing).sale_per_m2,
    employment: (c) => obj(c.employment).rate, fiscal: (c) => c.fiscal_independence, extinction: (c) => c.extinction_index }[key];
  if (!get) return null;
  if (!D._dist) D._dist = {};
  if (!D._dist[key]) D._dist[key] = D.cities.map((c) => get(c.raw)).filter(isNum).sort((a, b) => a - b);
  return { get, all: D._dist[key] };
}

// ---------- 교역 ----------
function hsBars(TJ, lst) {
  const rows = arr(lst).map(([c, v]) => { const code = String(c).padStart(2, '0'); return { label: `HS${code} ${obj(TJ.hs_names)[code] || ''}`, v: isNum(v) ? v * 1000 : null }; });
  return rows.length ? { type: 'bars', fmt: 'usd', rows, top: 5, clip: true } : { type: 'text', na: true, text: '품목 자료 없음' };
}
function unitName(D, key) {
  const codes = key.split('+');
  const k = D.world.countyIndex.get(codes[0]);
  const c = k != null ? D.cityById.get(D.countyCity[k]) : null;
  if (c && codes.length > 1 && c.sgg.length === codes.length) return c.name;
  return countyNames(D, codes);
}
function tradeSection(D, o, kind, state) {
  const T = o.trade, TJ = D.layers && D.layers.trade ? D.layers.trade.raw : null;
  const TT = TJ ? obj(TJ.trade) : null;
  const sec = { id: 'trade', title: '교역', caption: `수출입 · 관세청 ${obj(T).year || ''} · 신고 수리일 기준 · 달러${kind !== 'city' ? ' · 시군구 공표값의 합' : ''}`, blocks: [], notes: [] };
  if (!T || !isNum(T.export)) {
    sec.blocks.push({ type: 'text', na: true, text: `자료 없음 — ${TT && TT.unmatched_note ? TT.unmatched_note : '이 도시의 공표 단위를 현재 시군구 코드에 대응하지 못함'}` });
    return sec;
  }
  const nr = D.cities.filter((c) => obj(c.raw.ranks).export).length;
  const rows = [
    { label: '수출', sub: '제조 장소 기준', value: usd(T.export), ...(kind === 'city' && obj(o.ranks).export ? { rank: o.ranks.export, of: nr } : {}) },
    { label: '수입', sub: '납세의무자 주소지 기준', value: usd(T.import) },
    { label: '무역수지', sub: '원표', value: isNum(T.balance) ? { t: 'usd', v: T.balance, sign: true } : NAV() },
  ];
  if (kind !== 'city') rows.push({ label: '공표 단위', value: int(T.units, '곳') });
  sec.blocks.push({ type: 'kv', leader: true, rows });
  if (!TJ) { sec.blocks.push({ type: 'text', na: true, text: D.failed.includes('trade') ? '품목 자료(trade.json)를 불러오지 못했습니다.' : '품목 자료를 불러오는 중…' }); return sec; }
  if (TT.basis) sec.notes.push(TT.basis);
  if (kind === 'city') {
    const units = arr(T.units).map((k) => [k, obj(TJ.units)[k]]).filter(([, u]) => u);
    if (units.length === 1) {
      sec.blocks.push({ type: 'sub', title: '수출 상위 품목', small: 'HS 2단위' }, hsBars(TJ, units[0][1].e), { type: 'sub', title: '수입 상위 품목' }, hsBars(TJ, units[0][1].i));
    } else if (units.length > 1) {
      units.sort((x, y) => (y[1].v ? y[1].v[0] : 0) - (x[1].v ? x[1].v[0] : 0));
      sec.blocks.push({ type: 'text', text: `품목은 공표 단위(구)별 상위 5개만 있어 도시로 합쳐 다시 매기지 않는다 — 구별 목록 ${units.length}개:` });
      for (const [k, u] of units) sec.blocks.push({ type: 'fold', summary: unitName(D, k), small: `수출 ${fmtUsd(u.v ? u.v[0] : null)} · 수입 ${fmtUsd(u.v ? u.v[1] : null)}`,
        blocks: [{ type: 'sub', title: '수출 상위' }, hsBars(TJ, u.e), { type: 'sub', title: '수입 상위' }, hsBars(TJ, u.i)] });
    }
    if (TT.hs_rule) sec.notes.push(TT.hs_rule);
    if (TT.hq_note) sec.notes.push(TT.hq_note);
  } else {
    const pool = kind === 'state' ? state.cityIds.map((id) => D.cityById.get(id)).filter(Boolean) : D.cities;
    const cs = pool.filter((c) => isNum(obj(c.raw.trade).export)).sort((x, y) => y.raw.trade.export - x.raw.trade.export).slice(0, kind === 'state' ? 6 : 10);
    sec.blocks.push({ type: 'sub', title: '수출 상위 고을' }, { type: 'chips', items: cs.map((c) => ({ label: c.name, small: fmtUsd(c.raw.trade.export), go: { city: c.id } })) });
    if (arr(T.unmatched).length) sec.notes.push(`현재 시군구 코드에 대응하지 못한 공표 단위 (도시에는 붙이지 않고 이 합에는 넣음): ${T.unmatched.map((u) => u.name).join(', ')}`);
    if (kind === 'nation') sec.notes.push([T.note, TT.hq_note].filter(Boolean).join(' '));
  }
  return sec;
}

// ---------- 땅 ----------
const LAND_KO = { forest: '숲', crop: '농경지', built: '시가지', grass: '초지', wetland: '습지', bare: '나지', water: '수면',
  broadleaf: '활엽수림', conifer: '침엽수림', mixed: '혼효림', paddy: '논', field: '밭', orchard: '과수원', greenhouse: '시설재배지', unclassified: '미분류' };
function landSection(D, ls, cells, sido) {
  const W = D.world, M = obj(obj(D.nationRaw).land_stats_meta);
  const sec = { id: 'land', title: '땅', caption: '', blocks: [], notes: [] };
  if (ls) {
    sec.caption = `국가토지피복통계 ${ls.year}년 기준 · 기후에너지환경부 (2025 작성) · 시군구 행의 합`;
    if (!ls.value) sec.blocks.push({ type: 'text', na: true, text: `자료 없음 — ${ls.reason || ''}` });
    else {
      const v = ls.value;
      sec.blocks.push({ type: 'strip', total: isNum(v.total_ha) ? v.total_ha : null, parts: Object.entries(obj(v.by)).map(([k, x]) => ({ key: k, ha: isNum(x.ha) ? x.ha : null, pct: isNum(x.pct) ? x.pct : null })) });
      if (M.rule) sec.notes.push(M.rule);
      if (ls.old_units) sec.blocks.push({ type: 'warn', text: `개편 전 구역 기준 합 — ${arr(ls.old_units).join(', ')}은 개편 전 단위로만 공표돼 통째로 더함 (자치구·일반구로는 나누지 않음). ${ls.note || ''}` });
    }
  }
  if (cells && cells.length && W.coverKeys.length) {
    const keys = Object.keys(W.share), sum = {};
    for (const k of keys) sum[k] = 0;
    let n = 0, nMe = 0, nEsa = 0, lake = 0;
    const crop = {}, forest = {};
    for (const i of cells) {
      if (W.owner[i] < 0) continue;
      if (W.water[i] === 3) lake++;
      if (!W.cover[i]) continue;
      n++;
      if (W.coverSrc[i] === 1) nMe++; else if (W.coverSrc[i] === 2) nEsa++;
      for (const k of W.coverKeys) if (W.share[k]) sum[k] += W.share[k][i] || 0;
      if (W.coverSrc[i] === 1 || W.coverPublic) for (const k of keys) if (!W.coverKeys.includes(k)) sum[k] += W.share[k][i] || 0;
      if (W.crop[i]) crop[W.crop[i]] = (crop[W.crop[i]] || 0) + 1;
      if (W.forest[i]) forest[W.forest[i]] = (forest[W.forest[i]] || 0) + 1;
    }
    if (n) {
      const nm = (k) => W.coverNames[k] || LAND_KO[k] || k;
      const parts = W.coverKeys.map((k) => [k, sum[k] / n]).filter(([, v]) => v >= 0.005).sort((x, y) => y[1] - x[1]);
      // 세부 비율: 도엽 통계 칸만 (ESA 보완 칸에는 세부가 없다)
      const nSub = W.coverPublic ? n : nMe;
      const subs = nSub ? ['paddy', 'field', 'orchard', 'greenhouse', 'broadleaf', 'conifer', 'mixed', 'unclassified'].filter((k) => k in sum).map((k) => [k, sum[k] / nSub]).filter(([, v]) => v >= 0.005) : [];
      const cnt = (o) => Object.entries(o).sort((x, y) => y[1] - x[1]).map(([k, v]) => `${nm(k)} ${v}`).join(', ');
      sec.blocks.push({ type: 'sub', title: '칸 피복', small: `칸 ${n}개의 비율 평균 · ${W.coverMeta.label || ''}${nEsa ? ` · 도엽 통계가 닿지 않는 ${nEsa}칸은 대체 자료 ESA` : ''}` });
      sec.blocks.push({ type: 'text', text: parts.map(([k, v]) => `${nm(k)} ${(v * 100).toFixed(0)}%`).join(' · ') });
      if (subs.length) sec.blocks.push({ type: 'text', text: `${W.coverPublic ? '농경지 세부' : `도엽 통계 칸 ${nMe}개의 세부`}: ${subs.map(([k, v]) => `${nm(k)} ${(v * 100).toFixed(1)}%`).join(' · ')}` });
      const tail = [Object.keys(crop).length ? `농경지가 대표인 칸 — ${cnt(crop)}` : '', Object.keys(forest).length ? `숲이 대표인 칸 — ${cnt(forest)}` : '', lake ? `호수 칸 ${lake}` : ''].filter(Boolean).join(' · ');
      if (tail) sec.blocks.push({ type: 'text', text: tail });
      if (W.coverMeta.bias_note) sec.notes.push(`칸 비율은 ${W.coverMeta.bias_note}`);
    }
    const td = sido && D.raw.world && D.raw.world.tidal ? obj(D.raw.world.tidal.by_sido)[sido] : null;
    if (td) sec.blocks.push({ type: 'text', text: `갯벌: 갯벌 타일 ${td.tile_cells}칸 · 폴리곤 넓이 ${fmtFixed(td.area_km2, 1)} km² (해양수산부 1:25,000 연안정보도, ${D.raw.world.tidal.year}년 제작 · 바다 칸은 가장 가까운 육지 칸의 시도)` });
  }
  return sec.blocks.length ? sec : null;
}

// ---------- 보훈 ----------
function veteransBlocks(V, kind) {
  if (!V) return null;
  const rows = [], notes = ['대상구분별 인원의 합이라 대상 사이 중복이 있어 실제 인원보다 많을 수 있다.'];
  if (!isNum(V.count)) rows.push({ label: '인원', value: NAV('소속 시군구 가운데 값이 없는 곳이 있음'), subs: [`${arr(V.missing).join(', ')} — 최신 분기 원표에 행이 없음`] });
  else {
    const partial = kind === 'state' && V.complete === false;
    rows.push({ label: '인원', sub: kind === 'metro' ? '자치구 합' : '시군구 합', value: int(V.count, '명'), mark: partial ? '*' : null, subs: partial ? [`* ${arr(V.missing).join(', ')} 자료 없음 — 부분 합`] : [] });
    rows.push({ label: '인구 천 명당', sub: `주민등록 ${V.pop_ym || ''}`, value: fix(V.per_1000, 1, '명', partial ? '부분 합이라 계산하지 않음' : '인구 자료 없음') });
    if (kind === 'state' && isNum(V.sido_row)) rows.push({ label: '원표 시도 합계 행', sub: '대조용', value: int(V.sido_row, '명'), subs: isNum(V.sido_row_per_1000) ? [`천 명당 ${V.sido_row_per_1000.toFixed(1)}명`] : [] });
  }
  if (arr(V.residual).length) notes.push(`현재 구 하나로 나눌 수 없는 옛 구역 행 ${V.residual.map((r) => `${r.name} ${fmtInt(r.value)}명`).join(', ')}을 합에 넣었다(시군구 렌즈 값에는 없음).`);
  return { id: 'veterans', title: '보훈대상자', caption: `국가보훈부 ${V.period || ''}`, fold: true, blocks: [{ type: 'kv', leader: true, rows }], notes };
}

// ---------- 층 항목 (이곳의 것) ----------
export function itemValueText(it) {
  const r = it.raw || it;
  if (r.value_label) return r.value_label;
  if (r.value == null) return null;
  const v = typeof r.value === 'number' ? r.value.toLocaleString('ko-KR') : r.value;
  return `${v}${r.unit ? ' ' + r.unit : ''}`;
}
function itemsFor(D, sggSet, cellSet) {
  const L = D.layers, out = [];
  if (!L) return out;
  for (const it of L.items) {
    if (it.kind === 'national_park') { const p = L.parks.find((x) => x.id === it.ref); if (p && p.cells.some((c) => cellSet.has(c))) out.push(it); }
    else if (arr(it.raw.sgg).some((c) => sggSet.has(String(c))) || arr(it.raw.spans).some((c) => sggSet.has(String(c)))) out.push(it);
  }
  return out;
}
function hereSection(D, sggSet, cellSet, extra) {
  const sec = { id: 'here', title: '이곳의 것', caption: '불가사의·자원·기반시설 · 소재 시군구 기준 (국립공원은 칸이 걸치면)', blocks: [], notes: [] };
  if (!D.layers) { sec.blocks.push({ type: 'text', na: true, text: D.failed.some((f) => ['wonders', 'resources', 'infrastructure'].includes(f)) ? '지도 층 자료를 불러오지 못했습니다.' : '지도 층을 불러오는 중…' }); return sec; }
  const items = itemsFor(D, sggSet, cellSet);
  const groups = new Map();
  for (const it of items) { if (!groups.has(it.kind)) groups.set(it.kind, []); groups.get(it.kind).push(it); }
  for (const lst of groups.values()) lst.sort((a, b) => (b.value ?? -1) - (a.value ?? -1));
  sec.blocks.push({ type: 'kinds', groups: [...groups.entries()].map(([kind, lst]) => ({ kind, n: lst.length, items: lst.map((it) => ({ label: it.name, small: itemValueText(it), go: { item: it.id } })) })) });
  if (!items.length && !(extra && extra.length)) sec.blocks.push({ type: 'text', text: '이 지역에 놓인 항목이 없다.' });
  for (const e of extra || []) if (e) sec.blocks.push(e);
  return sec;
}
const resOf = (D) => (D.layers && D.layers.raw.resources ? D.layers.raw.resources : null);
function gicFold(g, label) {
  if (!g) return null;
  return { type: 'fold', summary: '일반산업단지', small: label, blocks: [{ type: 'text', text: `단지 ${g.count}곳 · 지정면적 ${fmtFixed(g.area_km2, 2)} km² · 가동업체 ${fmtInt(g.operating)}곳 (입주 ${fmtInt(g.tenants)})` }] };
}
function powerFold(D, pw, label) {
  const P = resOf(D) && resOf(D).power;
  if (!P) return null;
  const head = { type: 'fold', summary: '발전설비', small: `${label} · 발전기 소재지 · EPSIS ${P.date || ''}` };
  if (!pw || !Object.keys(pw).length) return { ...head, blocks: [{ type: 'text', text: '이 지역 소재지로 적힌 발전기가 없다.' }] };
  const ks = Object.keys(pw).sort((x, y) => pw[y] - pw[x]);
  return { ...head, blocks: [{ type: 'text', text: `합계 ${fmtFixed(ks.reduce((t, k) => t + pw[k], 0), 1)} MW` }, { type: 'bars', fmt: 'mw', rows: ks.map((k) => ({ label: obj(P.fuel_ko)[k] || k, v: pw[k] })), top: 8 }] };
}
function farmFold(D, get, sido, cityId) {
  const F = resOf(D) && resOf(D).farm;
  if (!F) return null;
  const rows = [];
  for (const k of ['rice', 'cattle', 'pigs']) {
    if (!F[k]) continue;
    let v = get(F[k]);
    if (k === 'pigs' && sido && v === undefined) v = null;
    if (v === undefined) continue;
    let why = '소속 시군구 가운데 원표에 행이 없는 곳이 있어 합을 내지 않음 (0 이 아님)', subs = [];
    if (k === 'pigs') {
      const M = cityId != null && F.pigs.metro ? F.pigs.metro[cityId] : null;
      why = M ? `원표가 ${M.scope} 한 값만 공표해 이 도시 몫을 나눌 수 없음` : '원표에 이 시군 행이 없음 (0 이 아님)';
      if (v == null && M) subs = [`${M.scope} ${fmtInt(M.value)}마리에 포함`];
    }
    rows.push({ label: F[k].label, sub: String(F[k].year || ''), value: int(v, F[k].unit, why), subs: v == null ? [why, ...subs] : subs });
  }
  const P = F.pigs_sido_2026;
  if (sido && P) rows.push({ label: '돼지', sub: `${P.period} · 시도 · 가축동향조사 (전체 돼지)`, value: int(obj(P.by_sido)[sido], '마리', '원표에 이 시도 행이 없음') });
  if (!rows.length) return null;
  const pyr = F.pigs ? F.pigs.year : '';
  // 그 판에 없는 항목(공개판의 한우)은 머리글·주석에도 적지 않는다
  return { type: 'fold', summary: '식량', small: [`쌀 ${obj(F.rice).year || ''}`, F.cattle ? `한우 ${obj(F.cattle).year || ''}` : null, `돼지 ${pyr}`].filter(Boolean).join(' · '), blocks: [{ type: 'kv', leader: true, rows },
    { type: 'note', text: [`논벼 생산량 (${obj(F.rice).year || ''})`, F.cattle ? `한우 (${obj(F.cattle).year || ''}, 농장 소재지)` : null, `돼지 (${pyr} 가축위생방역지원본부, 일반돼지만 · 방역 시스템 등록 농가${sido ? '; 시도는 가축동향조사 2026년 3분기도 — 조사가 달라 값이 다름' : ''})`].filter(Boolean).join(' · ') }] };
}
function keyIndFold(D, id) {
  const K = resOf(D) && resOf(D).key_industries;
  const r = K && obj(K.by_city)[id];
  if (!r) return null;
  const f = (v, p) => (isNum(v) ? fmtInt(v) + '명' + (p ? '*' : '') : '비공개');
  const rows = arr(K.codes).filter((c) => r[c]).map((c) => {
    const [v20, p20, vl, pl, yl] = r[c];
    return [`${c} ${obj(K.short)[c] || ''}`, f(v20, p20), isNum(v20) && obj(K.national_2020)[c] ? ((100 * v20) / K.national_2020[c]).toFixed(1) + '%' : '–', yl ? `${f(vl, pl)} (${yl})` : '자료 없음'];
  });
  if (!rows.length) return null;
  return { type: 'fold', summary: '주력 업종 종사자', small: '2020 경제총조사(전국) · 최신: 시도별 사업체조사', blocks: [
    { type: 'table', head: ['업종', '2020', '전국 중', '최신'], rows, numFrom: 1 },
    { type: 'note', text: "비공개(빈 값)는 0 이 아니다. * 표시는 공개값만 더한 부분 합. '전국 중'의 분모는 2020 전국 공개값 합. 최신 값은 부산·광주·대전·울산·강원에 없다." },
    K.rule ? { type: 'note', text: K.rule } : null].filter(Boolean) };
}
function minesFold(D, m, label) {
  if (!m || !resOf(D) || !resOf(D).mines_5d) return null;
  return { type: 'fold', summary: '가행 광산 (광종별)', small: label, blocks: [{ type: 'text', text: Object.entries(m).map(([k, v]) => `${k} ${v}곳`).join(' · ') }, { type: 'note', text: '한국광해광업공단 국내광산검색 (수집 2026-11, 소재지 → 시군구)' }] };
}

// ---------- 뺀 렌즈·건강 지표 (시군구 값) ----------
function moreSection(D, c) {
  const LS = D.lenses, W = D.world;
  const items = LS.retiredItems.filter((x) => !['under15', 'age', 'sex_ratio'].includes(x.id));
  const H = LS.byId.get('health');
  if (!items.length && !H) return null;
  const ks = c.sgg.map((code) => W.countyIndex.get(code)).filter((k) => k != null);
  const fmtL = (v, L) => lensValueText(v, { format: L.format, scale: L.scale, categories: arr(L.categories) }) + (L.unit && L.format !== 'cat' && !String(L.format).startsWith('pct') ? ' ' + L.unit : '');
  const row = (L, vals) => {
    const have = vals.filter((v) => v != null);
    const base = { label: L.name, sub: String(L.vintage || '') };
    if (!have.length) return { ...base, value: NAV('이 도시의 시군구에 값이 없음') };
    const lo = Math.min(...have), hi = Math.max(...have);
    if (lo === hi) return { ...base, value: txt(fmtL(lo, L)), subs: have.length === vals.length ? [] : [`${vals.length}곳 중 ${have.length}곳 값`] };
    return { ...base, value: txt(`${fmtL(lo, L)}–${fmtL(hi, L)}`), subs: [`구별 범위 · ${vals.length}곳 중 ${have.length}곳 값 (합치지 않음)`] };
  };
  const hRaw = H ? arr(H.raw.by_county) : null;
  const comp = H ? items.filter((x) => x.near === 'health') : [], rest = items.filter((x) => x.near !== 'health');
  const rows = [];
  if (H) rows.push(row(H, ks.map((k) => hRaw[k] ?? null)));
  for (const x of [...comp, ...rest]) rows.push(row(x, ks.map((k) => arr(x.values)[k] ?? null)));
  // 구 칸에 같은 값을 칠한 공표 단위 (시 전체·개편 전 구)
  const ul = new Map();
  for (const L of [...(H ? [{ name: H.name, vals: hRaw, units: H.units }] : []), ...items.map((x) => ({ name: x.name, vals: arr(x.values), units: arr(x.units) }))]) {
    for (const u of arr(L.units)) for (const k of ks) if (arr(u.counties).includes(k) && L.vals[k] != null) {
      const key = String(u.label || '').replace(/으로 계산$/, '');
      if (!ul.has(key)) ul.set(key, { u, names: new Set() });
      ul.get(key).names.add(L.name);
    }
  }
  const notes = [];
  if (ul.size) notes.push(`구 칸에 같은 값을 칠한 공표 단위: ${[...ul.entries()].map(([lab, { u, names }]) => `${lab} — ${arr(u.counties).map((k) => String(W.counties[k].name).split(' ').pop()).join('·')} (${[...names].join('·')})`).join('; ')}`);
  if (H && H.raw.definition) notes.push(H.raw.definition);
  const hasCon = arr(LS.retiredItems).some((x) => x.id === 'conifer');
  notes.push(`${LS.retiredRule} ${hasCon ? '밭·침엽수림' : '밭'}은 칸 값의 시군구 평균, 논 비율(시군구 통계)·순이동률·농림어업 비중·건강 네 지표는 원래 시군구 값이다.`);
  return { id: 'more', title: '건강 · 더 많은 지표', caption: '시군구 값 · 렌즈에서 뺀 지표 포함', fold: true, blocks: [{ type: 'kv', leader: true, rows }], notes };
}

// ---------- 청사 ----------
function officeSectionCity(D, c) {
  const o = c.raw, so = arr(o.sido_offices), own = arr(o.offices);
  if (!so.length && !own.length) return null;
  const st = D.stateByCode.get(c.sido), sp = st && st.raw.special_offices;
  const items = [];
  for (const x of so) items.push({ strong: x.name, text: `${x.role || ''}${x.law ? ' · ' + x.law : ''} · ${x.address || '주소 없음'} (${countyNames(D, x.sgg)})` });
  for (const x of own.slice(0, 8)) items.push({ label: x.name, text: `${x.kind || ''} · ${x.address || ''}` });
  if (own.length > 8) items.push({ text: `외 ${own.length - 8}곳` });
  const notes = [];
  if (sp && so.some((x) => x.role === '통합특별시 청사')) notes.push(`${sp[0].law}: 청사 3곳(${sp.map((e) => e.name).join('·')})을 모두 적고 수도(주 청사) 표시를 하나로 정하지 않는다.`);
  return { id: 'offices', title: '청사', caption: '행정안전부 공표본 주소 → 시군구 (시군구 대표 위치)', fold: true, blocks: [{ type: 'list', items }], notes };
}
function officeSectionState(D, s) {
  const o = s.raw;
  const link = (id) => (id != null && D.cityById.get(id) ? { city: id, label: D.cityById.get(id).name } : null);
  if (o.special_offices) return { id: 'offices', title: '청사', caption: o.special_offices[0].law || '', fold: true,
    blocks: [{ type: 'list', items: o.special_offices.map((e) => ({ strong: e.name, text: `${e.sgg ? countyNames(D, e.sgg) + ' (시군구 대표 위치)' : '지도에 놓지 않음'} — ${e.located_by || ''}`, go: link(e.city) })) }],
    notes: ['특별법이 종전 청사 3곳을 균형 있게 활용·운영하도록 정해 수도(주 청사) 별표를 하나로 정하지 않는다.'] };
  if (!arr(o.offices).length) return null;
  return { id: 'offices', title: '청사', caption: '행정안전부 공표본 (2025-12-31 기준) 주소 → 시군구', fold: true,
    blocks: [{ type: 'list', items: o.offices.map((x) => ({ strong: x.name, text: `${x.role || ''} · ${x.address || ''} (${countyNames(D, x.sgg)})`, go: link(x.city) })) }], notes: [] };
}

const stageBadge = (st) => ({ text: /^소멸/.test(st) ? st : `소멸위험 ${st}`, tone: /위험/.test(st) ? 'ju' : '' });
const BADGE_CAP = { '수도': '수도', '통합청사': '통합특별시 청사', '도청소재지': '도청 소재지' };

// ================= 고을 =================
export function cityView(D, id) {
  const c = D.cityById.get(id);
  if (!c) return null;
  const o = c.raw, n = D.cities.length, r = obj(o.ranks), st = D.stateByCode.get(c.sido);
  const badges = [];
  if (c.capital) badges.push({ text: BADGE_CAP[c.capital] || c.capital, tone: 'ink' });
  if (c.kind) badges.push({ text: c.kind });
  if (o.extinction_stage) badges.push(stageBadge(o.extinction_stage));
  const fr = D.layers && D.layers.frontier ? D.layers.frontier.areas.find((a) => a.sgg.some((x) => c.sgg.includes(x))) : null;
  if (fr) badges.push({ text: `접경지역 (${String(fr.article).replace('시행령 ', '시행령 ')})`, title: D.layers.frontier.rule });
  const sections = [];
  const econ = econSections(D, o, 'city', n);
  // 살림 분포선
  for (const s of econ) if (s.id === 'living') for (const row of s.blocks[0].rows) {
    if (!row.dist) continue;
    const d = distOf(D, row.dist);
    const v = d ? d.get(o) : null;
    row.dist = d && isNum(v) && d.all.length > 1 ? { all: d.all, v } : null;
  }
  const bySec = (k) => econ.find((s) => s.id === k);
  if (bySec('yields')) sections.push(bySec('yields'));
  if (bySec('industry')) sections.push(bySec('industry'));
  sections.push(ageSection(o, D.vintage));
  if (bySec('living')) sections.push(bySec('living'));
  sections.push(tradeSection(D, o, 'city'));
  const land = landSection(D, o.land_stats, c.footprint, null);
  if (land) sections.push(land);
  const R = resOf(D);
  sections.push(hereSection(D, new Set(c.sgg), new Set(c.footprint), R ? [
    gicFold(obj(obj(R.general_complexes).by_city)[c.id], '시군구 합계'),
    powerFold(D, obj(obj(R.power).by_city)[c.id], '시군구 합계'),
    farmFold(D, (F) => obj(F.by_city)[c.id], null, String(c.id)),
    keyIndFold(D, c.id),
    minesFold(D, R.mines_5d && obj(R.mines_5d.by_city)[c.id], '시군구 합계'),
  ] : []));
  const peers = arr(o.peers).map((pid) => D.cityById.get(pid)).filter(Boolean);
  if (peers.length) sections.push({ id: 'peers', title: '닮은 고을', caption: `${o.peer_rule || '인구 규모·고령 비율'}이 가까운 곳`, blocks: [{ type: 'chips', items: peers.map((p) => ({ label: p.name, small: `${fmtMan(p.pop)} · 고령 ${isNum(obj(p.raw.age).over65) ? p.raw.age.over65.toFixed(0) + '%' : '자료 없음'}`, go: { city: p.id } })) }], notes: [] });
  const rk = (label, k, note) => ({ label, value: isNum(r[k]) ? { t: 'int', v: r[k], unit: '위' } : NAV(), subs: note ? [note] : [] });
  sections.push({ id: 'ranks', title: '순위', caption: `고을 ${n}곳 중`, fold: true, blocks: [{ type: 'kv', cols: 3, rows: [rk('인구', 'population'), rk('5년 증가율', 'growth'), rk('고령 비율', 'over65'), rk('소멸위험', 'extinction', '1위 = 가장 위험'),
    rk('GRDP', 'gdp'), rk('1인당 GRDP', 'gdp_per_capita'), rk('1인당 총급여', 'wage'), ...('housing' in o ? [rk('아파트 ㎡당', 'housing')] : []), rk('수출', 'export')] }], notes: [obj(obj(D.nationRaw).notes).ranks].filter(Boolean) });
  const more = moreSection(D, c);
  if (more) sections.push(more);
  const vet = veteransBlocks(o.veterans, c.sgg.length > 1 && (c.kind === '광역시' || c.kind === '특별시') ? 'metro' : 'city');
  if (vet) sections.push(vet);
  const off = officeSectionCity(D, c);
  if (off) sections.push(off);
  const gn = obj(obj(D.nationRaw).notes);
  return {
    kind: 'city', id: c.id, title: c.name, full: st && c.full === st.name ? null : c.full, kicker: st ? { text: st.name, go: { state: st.code } } : null, badges,
    scope: o.scope ? `범위: ${o.scope}` : null,
    portrait: portrait(D, c),
    head: headOf(o, D.vintage, r.population, n), sections,
    foot: `시군구 ${c.sgg.length}개 · 칸 ${c.footprint.length}개 · 고을 자리: ${o.center_rule || ''}`,
    footNotes: [gn.growth, gn.age, c.capital ? gn.capital : null, c.kind === '특례시' ? gn.special_city : null, c.sido === '12' ? gn.gwangju : null].filter(Boolean),
  };
}

// 자료 초상 두 문장: 실린 값으로만 짓는다 (판단하는 말은 넣지 않는다)
const iga = (w) => { const c = w.charCodeAt(w.length - 1); return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? '이' : '가'; };
function portrait(D, c) {
  const o = c.raw, r = obj(o.ranks), n = D.cities.length, out = [];
  const a1 = isNum(r.population) ? `인구는 고을 ${n}곳 가운데 ${r.population}번째` : null;
  const b1 = isNum(o.growth_5y) ? `다섯 해 동안 ${fmtPct(Math.abs(o.growth_5y))} ${o.growth_5y >= 0 ? '늘었다' : '줄었다'}` : null;
  if (a1 && b1) out.push(`${a1}이고, ${b1}.`); else if (a1) out.push(`${a1}다.`); else if (b1) out.push(`${b1}.`);
  const best = YIELD_KEYS.filter((k) => k !== 'gold').map((k) => [k, r[k]]).filter(([, v]) => isNum(v)).sort((x, y) => x[1] - y[1])[0];
  const b = o.gdp_by_industry, E = econOf(D);
  let top = null;
  if (b && isNum(b.grdp) && b.grdp > 0) { const ks = arr(E.industry_keys).filter((k) => isNum(b[k])).sort((x, y) => b[y] - b[x]); if (ks.length) top = [obj(E.industry_ko)[ks[0]] || ks[0], (100 * b[ks[0]]) / b.grdp]; }
  const a2 = top ? `지역내총생산의 ${top[1].toFixed(0)}%가 ${top[0]}에서 나오` : null;
  const b2 = best ? `다섯 산출 가운데 ${YNAME[best[0]]}${iga(YNAME[best[0]])} ${best[1]}위로 가장 높다` : null;
  if (a2 && b2) out.push(`${a2}고, ${b2}.`); else if (a2) out.push(`${a2}ㄴ다.`.replace('나오ㄴ다', '나온다')); else if (b2) out.push(`${b2}.`);
  return out;
}

// ================= 시도 =================
export function stateView(D, code) {
  const s = D.stateByCode.get(String(code));
  if (!s) return null;
  const o = s.raw;
  const cells = [];
  const idx = D.world.stateIndex.get(s.code);
  for (let i = 0; i < D.world.n; i++) if (D.world.owner[i] === idx) cells.push(i);
  const sections = [];
  const econ = econSections(D, o, 'state', D.cities.length);
  const bySec = (k) => econ.find((x) => x.id === k);
  if (bySec('yields')) sections.push(bySec('yields'));
  // 소속 고을 (정렬 바꿈)
  const members = s.cityIds.map((id) => D.cityById.get(id)).filter(Boolean).map((c) => ({ id: c.id, name: c.name, pop: c.pop, ext: isNum(c.raw.extinction_index) ? c.raw.extinction_index : null, gdppc: isNum(c.raw.gdp_per_capita) ? c.raw.gdp_per_capita : null,
    yields: Object.fromEntries(YIELD_KEYS.map((k) => [k, isNum(obj(c.raw.yields)[k]) ? c.raw.yields[k] : null])), partial: Object.fromEntries(YIELD_KEYS.map((k) => [k, !!partialNote(c.raw, k)])) }));
  sections.push({ id: 'members', title: '소속 고을', caption: `${members.length}곳 · 누르면 그 고을 장`, blocks: [{ type: 'sortlist', rows: members, sorts: [['pop', '인구'], ['ext', '소멸위험'], ['gdppc', '1인당 GRDP'], ...YIELD_KEYS.map((k) => ['y:' + k, YNAME[k]])] }], notes: ['* 생산 부분 합: 제조업 + 건설업 + 공개된 광업의 합 (광업 비공개 단위 제외).'] });
  if (bySec('industry')) sections.push(bySec('industry'));
  sections.push(ageSection(o, D.vintage));
  if (bySec('living')) sections.push(bySec('living'));
  sections.push(tradeSection(D, o, 'state', s));
  // 도로 화물
  const F = o.freight;
  if (F) {
    const top = D.layers && D.layers.trade ? D.layers.trade.raw.routes.top_n : null;
    sections.push({ id: 'freight', title: '교역로', caption: `도로 화물 ${F.year} · 시도 간 O/D · 국가물류통합정보센터`, blocks: [
      { type: 'text', text: `시도 안 흐름 ${ton(F.intra_t)} — 이 시도에서 출발한 도로 화물 ${ton(F.out_t)} 가운데 ${F.intra_share_out}% 가 시도 안에 도착${F.note ? ' · ' + F.note : ''}` },
      { type: 'sub', title: '상대 시도 상위 5', small: '두 방향 합' },
      { type: 'chips', items: arr(F.partners).map((p) => { const S = D.stateByCode.get(String(p.sido)); const inTop = top != null && p.rank <= top;
        return { label: S ? S.short : String(p.sido), small: `${ton(p.total)} (보냄 ${ton(p.out)} · 받음 ${ton(p.in)}) · 구간 ${p.rank}위${inTop ? '' : top != null ? ' · 지도에 그리지 않음' : ''}`, go: inTop ? { route: [s.code, String(p.sido)].sort().join('-') } : { state: String(p.sido) } }; }) },
    ], notes: [] });
  }
  const land = landSection(D, o.land_stats, cells, s.code);
  if (land) sections.push(land);
  const R = resOf(D);
  const extra = [];
  if (R) {
    extra.push(gicFold(obj(obj(R.general_complexes).by_sido)[s.code], '시도 합계'));
    const M = obj(R.minerals), m = obj(M.by_sido)[s.code];
    extra.push({ type: 'fold', summary: '가행 광산', small: '시도 집계 · 한국광해광업공단', blocks: [{ type: 'text', text: m ? `금속 ${m.metal ?? '자료 없음'}곳 (${M.metal_date}) · 비금속 ${m.nonmetal ?? '자료 없음'}곳 (${M.nonmetal_date})` : '원자료에 이 시도 칸이 없음' },
      { type: 'note', text: '전국광산 통계(연말 기준)의 시도 집계다. 광종별 수(수집 시점 가행 목록)와 기준 시점이 다르다.' }] });
    extra.push(powerFold(D, obj(obj(R.power).by_sido)[s.code], '시도 합계'));
    extra.push(farmFold(D, (Fm) => { const x = obj(Fm.by_sido)[s.code]; return x && x.units ? x.sum : undefined; }, s.code));
    extra.push(minesFold(D, R.mines_5d && obj(R.mines_5d.by_sido)[s.code], '시도 합계'));
    const K = R.knowledge;
    if (K && K.funding_by_sido) {
      const d = K.funding_by_sido[s.code], top = arr(K.funding_top).filter((x) => String(x.sido) === s.code);
      const U = obj(D.layers.raw.wonders).universities;
      extra.push({ type: 'fold', summary: '대학 연구비', small: `대학알리미 ${K.funding_year || ''}`, blocks: [
        { type: 'text', text: d ? `이 시도 공표 학교·캠퍼스 ${d.count}곳 합 ${eok(d.won)}` : '이 시도 공표 행 없음' },
        top.length ? { type: 'list', items: top.map((x) => ({ label: `전국 ${x.rank}위 ${x.name}`, text: eok(x.won) })) }
          : { type: 'text', text: `전국 상위 ${arr(K.funding_top).length}곳 가운데 이 시도 학교 없음${d && arr(d.top).length ? ` · 이 시도 1위 ${d.top[0].name} (전국 ${d.top[0].rank}위, ${eok(d.top[0].won)})` : ''}` },
        { type: 'note', text: U && U.status === 'ok' ? '연구비 상위 대학은 주소로 지도에 지식 불가사의로 놓는다(위 목록). 이 시도 합은 대학알리미 공시 행의 시도 합이다.' : '대학알리미 연구비 공시의 소재지가 시도까지만 있어 이 순위만으로는 지도에 놓지 않는다.' }] });
    }
    const gs = arr(obj(R.gi).sido_level).filter((g) => String(g.sido) === s.code);
    if (gs.length) extra.push({ type: 'fold', summary: '시도 전체가 등록지역인 지리적표시', small: '지도에 놓지 않음', blocks: [{ type: 'text', text: gs.map((g) => `${g.name} (${g.gi_kind} ${g.no})`).join(' · ') }] });
  }
  const sgg = new Set(D.world.counties.filter((c) => c.sido === s.code).map((c) => c.code));
  sections.push(hereSection(D, sgg, new Set(cells), extra));
  const vet = veteransBlocks(o.veterans, 'state');
  if (vet) sections.push(vet);
  const off = officeSectionState(D, s);
  if (off) sections.push(off);
  const E = econOf(D);
  return {
    kind: 'state', id: s.code, title: s.name, kicker: { text: '대한민국', go: { nation: true } }, badges: [{ text: '시도', tone: 'ink' }, ...(o.extinction_stage ? [stageBadge(o.extinction_stage)] : [])],
    sub: `고을 ${s.cityIds.length}곳 · 칸 ${o.cells ?? cells.length}개${D.world.hexKm2 ? ` (칸 넓이 합 약 ${fmtInt((o.cells ?? cells.length) * D.world.hexKm2)} km²)` : ''}`,
    head: headOf(o, D.vintage, null, null), sections,
    footNotes: [E.official_note, obj(o.official).gdp && o.official.gdp.combined ? E.combined_note : null, E.national_note].filter(Boolean),
  };
}

// ================= 전국 =================
export function nationView(D) {
  const NR = obj(D.nationRaw), n = NR.nation;
  if (!n) return null;
  const E = econOf(D);
  const sections = [];
  const risk = D.cities.filter((c) => isNum(c.raw.extinction_index) && c.raw.extinction_index < 0.2).length;
  const riskAll = D.cities.filter((c) => isNum(c.raw.extinction_index) && c.raw.extinction_index < 0.5).length;
  const econ = econSections(D, n, 'nation', D.cities.length);
  const bySec = (k) => econ.find((x) => x.id === k);
  if (bySec('yields')) sections.push(bySec('yields'));
  // 공식 / 시군구 합 대조
  const C = n.official_compare;
  if (C) {
    const row = (name, a, b, mark) => [name, isNum(a) ? fmtWon(a) : '–', isNum(b) ? fmtWon(b) + (mark || '') : '자료 없음', isNum(a) && isNum(b) ? `${a - b >= 0 ? '+' : ''}${fmtWon(a - b)} (${(((a / b) - 1) * 100).toFixed(1)}%)` : '–'];
    const jb = Object.keys(obj(E.ksic_ko)).filter((L) => obj(C.jobs)[L] && C.jobs[L].sgg_sum == null).map((L) => `${L} ${E.ksic_ko[L]} ${fmtInt(C.jobs[L].official)}명`).join(', ');
    sections.push({ id: 'compare', title: '공식값과 시군구 합', caption: `지역소득 ${C.year} · 시군구 합 ${C.sgg_sum_label || ''}`, blocks: [
      { type: 'table', head: ['', '공식 전국값', '시군구 합', '차이'], numFrom: 1, rows: [row('GRDP', obj(C.grdp).official, obj(C.grdp).sgg_sum), ...YIELD_KEYS.map((k) => row(YNAME[k], obj(obj(C.yields)[k]).official, obj(obj(C.yields)[k]).sgg_sum, k === 'production' ? '*' : ''))] }],
      notes: [`* 시군구 합의 생산은 광업이 비공개인 공표 단위의 광업 몫이 빠진 부분 합계다. 시도 공식 GRDP 17행 합 ÷ 전국 행 = ${obj(C.sido_sum_check).ratio ?? '자료 없음'}.${jb ? ` 종사자: 시군구 합에서 비공개였던 ${jb}(공식 전국사업체조사 2024).` : ''}`] });
  }
  // 시도 표
  const states = D.states.slice().sort((x, y) => (y.pop || 0) - (x.pop || 0));
  sections.push({ id: 'states', title: '시도', caption: '인구 순 · 누르면 그 시도 장', blocks: [{ type: 'table', head: ['시도', '인구', '다섯 해', '고령', '소멸'], numFrom: 1,
    rows: states.map((s) => [s.name, fmtMan(s.pop), fmtPct(s.raw.growth_5y, 1, true), fmtPct(obj(s.raw.age).over65), fmtFixed(s.raw.extinction_index, 2)]), go: states.map((s) => ({ state: s.code })) },
    { type: 'text', text: `고을 ${n.cities}곳 중 소멸위험(0.5 미만) ${riskAll}곳, 그중 고위험(0.2 미만) ${risk}곳.` }], notes: [] });
  if (bySec('industry')) sections.push(bySec('industry'));
  sections.push(ageSection(n, D.vintage));
  if (bySec('living')) sections.push(bySec('living'));
  sections.push(tradeSection(D, n, 'nation'));
  const land = landSection(D, n.land_stats, null, null);
  if (land) sections.push(land);
  const og = D.states.filter((x) => obj(x.raw.official).gdp).sort((x, y) => y.raw.official.gdp.grdp - x.raw.official.gdp.grdp);
  if (og.length) sections.push({ id: 'econrank', title: '시도별 경제 순위', caption: '공식 GRDP 순 · 누르면 이동', blocks: [{ type: 'table', head: ['시도', '공식 GRDP', '시군구 합', '1인당 (공식)', '생산 (공식)', '과학 (공식)'], numFrom: 1, scroll: true,
    rows: og.map((x, k) => { const G = x.raw.official.gdp; return [`${k + 1}. ${x.short}${G.combined ? ' (합)' : ''}`, fmtWon(G.grdp, ''), isNum(x.raw.gdp) ? fmtWon(x.raw.gdp, '') + (x.raw.gdp_year !== G.year ? ` (${x.raw.gdp_year})` : '') : '자료 없음', fmtWon(G.per_capita, ''), fmtWon(obj(G.yields).production, ''), fmtWon(obj(G.yields).science, '')]; }),
    go: og.map((x) => ({ state: x.code })) }],
    notes: [`공식값은 지역소득 ${obj(obj(n.official).gdp).year || ''} (광업 포함, 부분 합계 없음). 시군구 합의 * 생산 부분 합계: 제조업 + 건설업 + 공개된 광업의 합이며, 광업이 비공개인 공표 단위의 광업 몫만 뺐다 (전국 ${n.production_mining_excluded || 0}곳 제외, 시도 ${D.states.filter((x) => partialNote(x.raw, 'production')).length}곳·도시 ${D.cities.filter((x) => partialNote(x.raw, 'production')).length}곳). 도시 순위는 시군구 합 값으로 매긴다.`, '(합) = 광주 + 전남 합.'] });
  const V = n.veterans;
  if (V && isNum(V.count)) sections.push({ id: 'veterans', title: '보훈대상자', caption: `국가보훈부 ${V.period || ''}`, fold: true, blocks: [{ type: 'kv', leader: true, rows: [{ label: '인원', sub: '시군구 합', value: int(V.count, '명') }] }], notes: ['대상구분별 인원의 합이라 대상 사이 중복이 있어 실제 인원보다 많을 수 있다.'] });
  return {
    kind: 'nation', id: '1', title: n.name || '대한민국', kicker: null, badges: [{ text: '전국 장', tone: 'ink' }],
    sub: `시도 ${n.states} · 시군구 ${n.sgg} · 고을 ${n.cities} · 기준 ${fmtWhen(D.vintage)}`,
    head: headOf(n, D.vintage, null, null), sections,
    footNotes: [E.national_note, E.combined_note, E.official_note, E.growth_note].filter(Boolean),
  };
}

// ================= 층 항목 =================
function precisionText(it) {
  const r = it.raw || it;
  if (!r.precision) return '지도에 놓지 못함';
  if (r.kind === 'knowledge' && r.precision === 'county') {
    const unit = r.group ? '자치구·시군구' : (String(r.place || '').split(' ').pop() || '시군구');
    return `${unit} 중심 칸 — 캠퍼스·기관 자리가 아님 (좌표 없음, 주소의 시군구 인구 가중 중심 = 시군구 대표 위치)`;
  }
  return PREC_LONG[r.precision] || PREC_KO[r.precision] || '위치 근거 미상';
}
const srcLine = (x) => `${x.publisher || ''} · ${x.title || x.key || ''}${x.retrieved ? ` (수집 ${x.retrieved}${x.license ? ', 이용허락 ' + x.license : ''})` : ''}`;

export function itemView(D, it) {
  if (!it) return null;
  const L = D.layers, r = it.raw || it;
  if (r.group || it.group) return groupView(D, it);
  const K = L ? L.kinds[it.kind] : null;
  const city = r.city != null ? D.cityById.get(r.city) : null;
  const v = itemValueText(it);
  const sections = [], warns = [];
  const meta = [
    { label: '기준', value: txt(r.year ?? (K && K.year) ?? '자료 없음') },
    { label: '위치 정밀도', value: txt(precisionText(it)) },
  ];
  if (r.place_from && PLACE_FROM[r.place_from]) meta.push({ label: '위치를 정한 근거', value: txt(PLACE_FROM[r.place_from]) });
  if (r.rank != null) meta.push({ label: '같은 종류 안 순위', value: { t: 'int', v: r.rank, unit: '위' } });
  if (it.kind === 'airport' && isNum(r.cargo_t)) meta.push({ label: '화물', sub: String(r.year || ''), value: int(r.cargo_t, '톤') });
  if (it.kind === 'trade_port' && isNum(r.teu)) meta.push({ label: '컨테이너', sub: r.teu_note || '', value: int(r.teu, 'TEU') });
  if (isNum(r.area_km2) && it.kind !== 'national_park') meta.push({ label: '지정면적', value: fix(r.area_km2, 2, 'km²') });
  if (it.kind === 'knowledge' && r.precision === 'county') warns.push(`지도 아이콘은 ${r.place || ''}의 중심 칸에 있다. 캠퍼스·기관의 실제 자리가 아니다 — 좌표가 없어 주소의 자치구·시군구까지만 읽어 그 인구 가중 중심 칸에 놓았다.`);
  if (r.reason) warns.push(r.reason);
  if (it.kind === 'station' && r.hsr) meta.push({ label: '고속철도', value: txt('정차') });
  const body = [];
  if (arr(r.detail).length) body.push({ type: 'list', items: r.detail.map((d) => ({ text: d })) });
  if (it.kind === 'heritage_cluster' && arr(r.list).length) sections.push({ id: 'list', title: '이 칸의 국보·사적', caption: `${r.list.length}건`, blocks: [{ type: 'list', items: r.list.map(([k, nm]) => ({ tag: k, label: nm })) }], notes: [] });
  if (it.kind === 'national_park' && L) {
    const p = L.parks.find((x) => x.id === it.ref);
    if (p) {
      const pr = p.raw;
      meta.unshift({ label: '지정면적', sub: pr.area_basis || '', value: fix(p.areaKm2, 1, 'km²') });
      if (pr.designated) meta.push({ label: '지정일', value: txt(pr.designated) });
      sections.push({ id: 'park', title: '공원이 덮는 곳', caption: '', blocks: [{ type: 'text', text: `육지 칸 ${p.cells.length}개 (경계 파일 '공원경계버퍼'의 표본점 과반 칸 — 넓이로 쓰지 않음) · ${p.marine ? '해상·해안 공원 (폴리곤의 대부분이 바다)' : '내륙 공원'}` },
        { type: 'text', text: `걸친 시군구: ${arr(pr.spans).map((c) => countyName(D, c)).join(', ')}` }], notes: [] });
    }
  }
  if (it.kind === 'world_heritage' && L) {
    const e = arr(L.worldHeritage).find((x) => x.id === it.ref);
    if (e) {
      const cnt = obj(e.counts);
      sections.push({ id: 'wh', title: `구성 유산 ${arr(e.components).length}건`, caption: `${PREC_KO.point} ${cnt.point || 0} · ${PREC_KO.county} ${cnt.county || 0} · 목록만 ${cnt.list || 0}`,
        blocks: [{ type: 'list', items: arr(e.components).map((c) => ({ tag: c.precision ? PREC_KO[c.precision] : '목록만', label: c.name, text: c.matched || '', here: c.cell === it.cell })) }],
        notes: ['좌표 = 이름이 같은 국가유산의 좌표 · 시군구 대표 위치 = 소재지 문자열의 시군구 (인구 가중 중심 칸) · 목록만 = 소재지가 시도까지만이거나 이름이 여러 곳이라 지도에 놓지 않음. 굵게 = 이 아이콘에 든 구성 유산.'] });
      if (e.visitor_series) sections.push({ id: 'visitors', title: '관람객', caption: '국가유산청 세계유산 관람객 현황', blocks: [{ type: 'kv', cols: 3, rows: Object.entries(e.visitor_series).map(([y, nn]) => ({ label: y, value: int(nn, '명') })) }], notes: [] });
    }
  }
  if (it.kind === 'nuclear') {
    const u = (lst) => arr(lst).map((x) => `${x.name} ${x.mw ?? '?'} MW`).join(', ') || '없음';
    if (r.operating) sections.push({ id: 'units', title: '호기', caption: '', blocks: [{ type: 'list', items: [{ label: `가동 ${r.units_operating}기`, text: u(r.operating) }, { label: `영구정지 ${arr(r.stopped).length}기`, text: u(r.stopped) }, { label: `건설 중 ${arr(r.construction).length}기`, text: u(r.construction) }] }], notes: [] });
    const nn = r.nssc && resOf(D) ? arr(resOf(D).nuclear_nssc).find((x) => x.site === r.nssc) : null;
    if (nn) sections.push({ id: 'nssc', title: `원자력안전위원회 본부 '${nn.site}'`, caption: r.nssc_match ? '용량 일치' : '용량 다름', blocks: [{ type: 'list', items: [{ label: `가동 ${nn.units_operating}기`, text: u(nn.operating) }, { label: `영구정지 ${arr(nn.stopped).length}기`, text: u(nn.stopped) }, { label: `건설 중 ${arr(nn.construction).length}기`, text: u(nn.construction) }] }], notes: [] });
  }
  const others = L && it.cell >= 0 ? L.items.filter((x) => x.cell === it.cell && x !== it) : [];
  if (others.length) sections.push({ id: 'others', title: '같은 칸의 다른 항목', caption: `${others.length}`, blocks: [{ type: 'chips', items: others.map((o) => ({ label: o.name, kind: o.kind, go: { item: o.id } })) }], notes: [] });
  sections.push({ id: 'rule', title: '선정 규칙과 출처', caption: '', blocks: [{ type: 'text', text: (K && K.rule) || '규칙 자료 없음' }, { type: 'list', items: (K ? K.source : []).map((x) => ({ text: srcLine(x) })) }], notes: [] });
  return { kind: 'item', id: it.id, itemKind: it.kind, hsr: !!r.hsr, title: it.name, sub: r.place || '위치 없음', cityGo: city ? { city: city.id, label: `${city.name} 장 보기` } : null,
    key: { label: '값', text: v, unit: null }, meta, warns, body, sections };
}

// 대학 묶음 (층 모듈이 만든 묶음 항목: {group, memberItems|members, ...})
function groupView(D, g) {
  const r = g.raw || g, L = D.layers;
  const ids = arr(r.members || g.members);
  const ms = (arr(g.memberItems).length ? g.memberItems : ids.map((id) => L && L.byId.get(id)).filter(Boolean)).slice().sort((x, y) => ((y.raw || y).funding_won || 0) - ((x.raw || x).funding_won || 0));
  const city = r.city != null ? D.cityById.get(r.city) : null;
  const Z = L && L.zoom ? obj(L.zoom.knowledge_groups) : {};
  const sum = isNum(r.funding_won_sum) ? r.funding_won_sum : ms.reduce((t, m) => t + ((m.raw || m).funding_won || 0), 0);
  return { kind: 'item', id: g.id, itemKind: 'knowledge', title: g.name || r.name, sub: '같은 칸·이웃 칸에 놓인 대학', cityGo: city ? { city: city.id, label: `${city.name} 장 보기` } : null,
    key: { label: '연구비 합', text: eok(sum) }, meta: [{ label: '위치 정밀도', value: txt(precisionText({ raw: { ...r, group: true, kind: 'knowledge' } })) }],
    warns: ['대학 아이콘은 캠퍼스 자리가 아니라 주소의 자치구·시군구 중심 칸에 있다(좌표 없음). 가까운 구의 대학이 겹쳐 보이지 않게 한 표지로 묶었다.'], body: [],
    sections: [{ id: 'members', title: '묶인 대학', caption: `${ms.length}곳 · 연구비 대학알리미 ${(ms[0] && (ms[0].raw || ms[0]).funding_year) || ''}`,
      blocks: [{ type: 'table', head: ['순위', '대학', '자치구·시군구', '연구비'], numFrom: 3, rows: ms.map((m) => { const x = m.raw || m; return [x.funding_rank ?? '–', x.name, String(x.place || '').split(' ').pop(), eok(x.funding_won)]; }), go: ms.map((m) => ({ item: m.id })) }], notes: [] },
    { id: 'rule', title: '묶는 규칙', caption: '', blocks: [{ type: 'text', text: Z.rule || '규칙 자료 없음' }], notes: [] }] };
}

// ================= 교역로 =================
export function routeView(D, rt) {
  const L = D.layers;
  if (!rt || !L || !L.trade) return null;
  const T = L.trade, R = T.raw.routes || {};
  const A = D.stateByCode.get(rt.a), B = D.stateByCode.get(rt.b);
  const an = (c) => obj(T.anchors)[c] || {};
  const t = (v) => int(v, '톤');
  return { kind: 'route', id: rt.id, title: `${A ? A.short : rt.a} – ${B ? B.short : rt.b}`, sub: `도로 화물 ${T.year}`,
    states: [A, B].filter(Boolean).map((s) => ({ label: s.name, go: { state: s.code } })),
    key: { label: '두 방향 합', value: t(rt.total), small: `시도 간 ${R.pairs_total ?? '–'}쌍 중 ${rt.rank}위` },
    meta: [
      { label: `${A ? A.short : rt.a} → ${B ? B.short : rt.b}`, value: t(rt.ab) },
      { label: `${B ? B.short : rt.b} → ${A ? A.short : rt.a}`, value: t(rt.ba) },
      { label: '시도 간 도로 화물 중', sub: `전체 ${isNum(obj(T.totals).inter_t) ? fmtInt(T.totals.inter_t) + '톤' : '자료 없음'}`, value: pct(rt.share) },
    ],
    dir: { ab: rt.ab, ba: rt.ba, a: A ? A.short : rt.a, b: B ? B.short : rt.b },
    sections: [
      { id: 'ends', title: '선의 끝점', caption: '청사 소재 칸 (시군구 대표 위치)', blocks: [{ type: 'list', items: [rt.a, rt.b].map((c) => ({ label: an(c).office || '자료 없음', text: an(c).rule || '' })) }], notes: [] },
      { id: 'rule', title: '규칙과 출처', caption: '', blocks: [{ type: 'text', text: T.rule || '' }, { type: 'list', items: T.source.map((x) => ({ text: srcLine(x) })) }], notes: [] },
    ] };
}
