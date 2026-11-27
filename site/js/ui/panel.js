// 도시·시도·전국 패널: 인구, 시계열, 인구 피라미드, 연령 지표, 소멸위험지수, 순위, 닮은 도시

import { STATE_COLORS } from '../render/terrain.js';
import { fmtMan, fmtWon, partialNote, YIELD_ICONS } from '../render/banners.js';
import { KINDS, PLACE_FROM, PREC_KO, iconURL, precisionText } from '../render/layers.js';
import { itemValue } from './tooltip.js';
import { formatValue, unitOf } from '../render/lens.js';

const AGE_LABELS = Array.from({ length: 21 }, (_, k) => (k === 20 ? '100+' : `${k * 5}`));
const STAGE_COLOR = { '매우 낮음': '#3f8f6b', '보통': '#86b86f', '주의': '#e0a94e', '소멸위험': '#d4553a', '소멸 고위험': '#a3202f' };
// 배지 글자색: 흰색과 어두운 색 가운데 배경과의 대비(WCAG 상대휘도)가 큰 쪽 (감사 14 — 다섯 단계 모두 4.5:1 이상)
const DARK_TEXT = '#1a1208';
function lum(hex) {
  const n = parseInt(hex.slice(1), 16), ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
}
export function contrast(a, b) { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
export function badgeText(bg) { return contrast(bg, '#ffffff') >= contrast(bg, DARK_TEXT) ? '#ffffff' : DARK_TEXT; }
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const num = (v) => (v == null ? '자료 없음' : v.toLocaleString('ko-KR'));
const pct = (v, d = 1) => (v == null ? '자료 없음' : v.toFixed(d) + '%');
const sgn = (v) => (v == null ? '자료 없음' : (v > 0 ? '+' : '') + v.toFixed(1) + '%');

// compact: 도시 패널 '개요'의 두 칸 나란히 (7b #9) — 눈금은 처음·끝만
function seriesChart(series, compact = false) {
  const keys = Object.keys(series).sort();
  const vals = keys.map((k) => series[k]);
  if (vals.some((v) => v == null)) return '<p class="dim">시계열 자료 없음</p>';
  const [W, H, L, R, T, B] = compact ? [180, 104, 40, 10, 8, 18] : [300, 120, 50, 18, 12, 22];
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.15 || hi * 0.02 || 1;
  lo -= pad;
  hi += pad;
  const x = (k) => L + ((W - L - R) * k) / (keys.length - 1);
  const y = (v) => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
  const pts = vals.map((v, k) => `${x(k).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const up = vals[vals.length - 1] >= vals[0];
  const col = up ? '#6fc3a5' : '#e8836a';
  // 변화 폭이 작으면 만 단위 반올림이 같아지므로 명 단위로 적는다
  const tl = (v) => (hi - lo < 4e4 ? Math.round(v).toLocaleString('ko-KR') : fmtMan(v));
  const ticks = (compact ? [lo + pad, hi - pad] : [lo + pad, (lo + hi) / 2, hi - pad])
    .map((v) => `<text x="${L - 4}" y="${y(v) + 3}" text-anchor="end">${tl(v)}</text><line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="grid"/>`)
    .join('');
  const xl = keys.map((k, i) => (compact && i > 0 && i < keys.length - 1 ? '' : `<text x="${x(i)}" y="${H - 5}" text-anchor="${compact ? (i ? 'end' : 'start') : 'middle'}">${k.length > 4 ? k.slice(2).replace('-', '.') : "'" + k.slice(2)}</text>`)).join('');
  const dots = vals.map((v, k) => `<circle cx="${x(k)}" cy="${y(v)}" r="2.6" fill="${col}"><title>${esc(keys[k])}: ${v.toLocaleString('ko-KR')}명</title></circle>`).join('');
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="인구 시계열">${ticks}${xl}
    <polyline points="${pts}" fill="none" stroke="${col}" stroke-width="2"/>${dots}</svg>`;
}

function pyramid(p, compact = false) {
  const [W, rowH, gap] = compact ? [180, 4.4, 12] : [300, 7.2, 18], H = 21 * rowH + (compact ? 14 : 18), mid = W / 2;
  const mx = Math.max(...p.male, ...p.female) || 1;
  const sc = (v) => ((mid - gap - 4) * v) / mx;
  let s = '';
  for (let k = 0; k < 21; k++) {
    const y = H - (compact ? 12 : 16) - (k + 1) * rowH;
    const m = sc(p.male[k]), f = sc(p.female[k]);
    s += `<rect x="${mid - gap - m}" y="${y}" width="${m}" height="${rowH - 1}" fill="#6b9bd8"><title>남 ${esc(AGE_LABELS[k])}세: ${p.male[k].toLocaleString('ko-KR')}명</title></rect>`;
    s += `<rect x="${mid + gap}" y="${y}" width="${f}" height="${rowH - 1}" fill="#e07fa5"><title>여 ${esc(AGE_LABELS[k])}세: ${p.female[k].toLocaleString('ko-KR')}명</title></rect>`;
    if (k % 4 === 0) s += `<text x="${mid}" y="${y + rowH - (compact ? 0 : 1.5)}" text-anchor="middle">${esc(AGE_LABELS[k])}</text>`;
  }
  s += `<text x="${mid - gap - 2}" y="${H - 3}" text-anchor="end" class="lab">남</text><text x="${mid + gap + 2}" y="${H - 3}" class="lab">여</text>`;
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="인구 피라미드">${s}</svg>`;
}

function popBlock(o, vintage) {
  const st = o.extinction_stage;
  return `
    <div class="bignum"><b>${num(o.population)}</b>명 <span class="chg ${o.growth_5y >= 0 ? 'up' : 'down'}">${sgn(o.growth_5y)} <small>5년(2020→2025)</small></span></div>
    <h4>인구 변화 <small>주민등록, 각 12월 · ${esc(vintage)}</small></h4>${seriesChart(o.pop_series)}
    <h4>인구 피라미드 <small>5세 계급</small></h4>${pyramid(o.pyramid)}
    <div class="kv">
      <div><em>65세 이상</em><b>${pct(o.age.over65)}</b></div>
      <div><em>0–14세</em><b>${pct(o.age.under15)}</b></div>
      <div><em>15–64세</em><b>${pct(o.age.working)}</b></div>
      <div><em>평균연령(추정)</em><b>${esc(o.age.mean_est ?? '–')}세</b></div>
      <div><em>중위연령(추정)</em><b>${esc(o.age.median_est ?? '–')}세</b></div>
      <div><em>청년 성비</em><b>${esc(o.sex_ratio_20_39 ?? '–')}</b></div>
    </div>
    <div class="ext">
      <div><em>소멸위험지수</em><b>${o.extinction_index != null ? o.extinction_index.toFixed(2) : '자료 없음'}</b></div>
      <span class="stage" style="background:${esc(STAGE_COLOR[st] || '#5a5a5a')};color:${badgeText(STAGE_COLOR[st] || '#5a5a5a')};text-shadow:none">${esc(st || '자료 없음')}</span>
      <p class="dim">20–39세 여성 ${pct(o.age.women_20_39)} ÷ 65세 이상 ${pct(o.age.over65)}. 0.5 미만 소멸위험, 0.2 미만 고위험.</p>
    </div>`;
}

const YNAME = { food: '식량', production: '생산', gold: '금', science: '과학', culture: '문화' };
export const TAB_IDS = ['overview', 'econ', 'infra', 'land'];
const YRULE = { food: '농림어업', production: '제조+건설+광업', gold: '지역내총생산', science: '정보통신+사업서비스', culture: '문화·기타서비스' };
const NA = (why) => `<span class="na" title="${esc(why || '')}">자료 없음</span>`;
const won = (v) => (v == null ? NA() : fmtWon(v) + (Math.abs(v) < 1e12 && Math.abs(v) >= 1e4 ? '원' : ''));
const man = (v, unit = '만원') => (v == null ? NA() : Math.round(v).toLocaleString('ko-KR') + unit);

// 입지계수 칸: 비중 5% 이상·배수 1.5 이상(반올림 전)이면 강조 (7b #11)
function lqCell(lq, share) {
  if (lq == null) return '<span class="lq"></span>';
  const t = lq >= 10 ? String(Math.round(lq)) : lq < 0.1 ? lq.toFixed(2) : lq.toFixed(1);
  return `<span class="lq ${share >= 0.05 && lq >= 1.5 ? 'hi' : ''}" title="입지계수: 도시 비중 ÷ 전국 공식 비중">×${t}</span>`;
}

// 산업별 부가가치 가로 막대 (16분류 + 순생산물세). 비공개는 '비공개'. lq(k) 가 있으면 입지계수 열
function industryBars(b, ko, keys, lq = null) {
  if (!b) return `<p class="dim">GRDP 자료 없음</p>`;
  const rows = [...keys, 'net_taxes'];
  const mx = Math.max(...rows.map((k) => b[k] || 0)) || 1;
  const order = rows.slice().sort((x, y) => (b[y] ?? -1) - (b[x] ?? -1));
  return `<div class="ibars${lq ? ' lqs' : ''}">${order.map((k) => {
    const v = b[k];
    const w = v == null ? 0 : Math.max(0.5, (100 * v) / mx);
    const share = v == null || !b.grdp ? '' : ` <small>${((100 * v) / b.grdp).toFixed(1)}%</small>`;
    const lc = lq ? (k === 'net_taxes' || v == null ? '<span class="lq"></span>' : lqCell(lq(k), v / b.grdp)) : '';
    return `<div class="ib ${k === 'net_taxes' ? 'tax' : ''}"><span class="lab">${esc(ko[k])}</span><span class="bar"><i style="width:${w}%"></i></span><span class="val">${v == null ? '<span class="na">비공개</span>' : fmtWon(v) + share}</span>${lc}</div>`;
  }).join('')}</div>`;
}

// 산업 대분류별 종사자 가로 막대 (사업장 소재지). 비공개는 '비공개'
function jobBars(o, E, lq = null) {
  if (!o.jobs) return `<p class="dim">산업 대분류 종사자 자료 없음</p>`;
  const keys = Object.keys(E.ksic_ko);
  const mx = Math.max(...keys.map((k) => o.jobs[k] || 0)) || 1;
  const tot = o.jobs_total;
  const order = keys.slice().sort((x, y) => (o.jobs[y] ?? -1) - (o.jobs[x] ?? -1));
  return `<p class="dim sm">${esc(o.jobs_year_label || o.jobs_year)} · 사업장 소재지 기준 · 합계 ${tot == null ? '비공개' : tot.toLocaleString('ko-KR') + '명'}</p>
    <div class="ibars jobs${lq ? ' lqs' : ''}">${order.map((k) => {
      const v = o.jobs[k];
      const lc = lq ? (v == null || !tot ? '<span class="lq"></span>' : lqCell(lq(k), v / tot)) : '';
      const w = v == null ? 0 : Math.max(0.5, (100 * v) / mx);
      const share = v == null || !tot ? '' : ` <small>${((100 * v) / tot).toFixed(1)}%</small>`;
      return `<div class="ib"><span class="lab">${k} ${esc(E.ksic_ko[k])}</span><span class="bar"><i style="width:${w}%"></i></span><span class="val">${v == null ? '<span class="na">비공개</span>' : v.toLocaleString('ko-KR') + share}</span>${lc}</div>`;
    }).join('')}</div>`;
}

// 공식값 보조: 전남광주처럼 광주·전남 두 값을 나란히 (비율은 더하지 않는다)
const partsTxt = (parts, f) => (parts ? Object.entries(parts).map(([p, v]) => `${esc(p)} ${f(v)}`).join(' · ') : '');
const pctv = (v) => (v == null ? '자료 없음' : v.toFixed(1) + '%');

function officialKV(o, kind) {
  const O = o.official || {};
  const em = O.employment, fi = O.fiscal, fa = O.farm, g = O.gdp;
  const s = [];
  if (g) {
    const sg = o.gdp_growth;
    s.push(`<div><em>1인당 GRDP <small>공식 ${esc(g.year)}</small></em><b data-k="gdppc">${won(g.per_capita)}</b><small class="sub2">시군구 합 ${won(o.gdp_per_capita)}</small></div>`);
    s.push(`<div><em>명목 증가율 <small>공식 ${g.growth ? `${esc(g.growth.from)}→${esc(g.growth.to)}` : ''}</small></em><b>${g.growth ? (g.growth.rate > 0 ? '+' : '') + g.growth.rate.toFixed(1) + '%' : NA()}</b>${sg ? `<small class="sub2">시군구 합 ${esc(sg.from)}→${esc(sg.to)} ${(sg.rate > 0 ? '+' : '') + sg.rate.toFixed(1)}%</small>` : ''}</div>`);
  }
  if (em) {
    const t = em.rate != null ? `<b>${em.rate.toFixed(1)}%</b>` : `<b class="rng">${partsTxt(em.parts, (v) => pctv(v.rate))}</b>`;
    s.push(`<div><em>고용률 <small>${esc(em.label || (em.parts ? '경제활동인구조사' : ''))}</small></em>${t}${em.rate != null && em.parts ? `<small class="sub2">${partsTxt(em.parts, (v) => pctv(v.rate))}</small>` : ''}<small class="sub2" title="${esc(em.note)}">시군구 값(지역별고용조사, 반기)과 다른 조사</small></div>`);
    s.push(`<div><em>실업률 <small>${esc(em.label || '')}</small></em>${em.unemployment != null ? `<b>${em.unemployment.toFixed(1)}%</b>` : `<b class="rng">${partsTxt(em.parts, (v) => pctv(v.unemployment))}</b>`}${em.unemployment != null && em.parts ? `<small class="sub2">${partsTxt(em.parts, (v) => pctv(v.unemployment))}</small>` : ''}</div>`);
  }
  if (fi) {
    const main = fi.avg != null ? `<b>${fi.avg.toFixed(1)}%</b>${fi.hq != null ? `<small class="sub2">본청 ${fi.hq.toFixed(1)}%</small>` : ''}`
      : `<b class="rng">${partsTxt(fi.parts, (v) => pctv(v.avg))}</b><small class="sub2">본청 ${partsTxt(fi.parts, (v) => pctv(v.hq))} · 비율이라 더하지 않음</small>`;
    s.push(`<div><em>재정자립도 <small>지방재정365 ${esc(fi.year)} 당초 · ${kind === 'nation' ? '단체별 평균' : '시도 전체 평균'}</small></em>${main}</div>`);
  }
  if (fa) {
    const c = fa.combined ? ` · ${esc(fa.combined)}` : '';
    s.push(`<div><em>논 <small>농업면적조사 ${esc(fa.year)}${c}</small></em><b>${fa.paddy_ha == null ? NA() : Math.round(fa.paddy_ha).toLocaleString('ko-KR') + 'ha'}</b>${o.farm && o.farm.paddy_ha != null ? `<small class="sub2">시군구 합 ${o.farm.paddy_ha.toLocaleString('ko-KR')}ha</small>` : ''}</div>`);
    s.push(`<div><em>밭 <small>농업면적조사 ${esc(fa.year)}${c}</small></em><b>${fa.field_ha == null ? NA() : Math.round(fa.field_ha).toLocaleString('ko-KR') + 'ha'}</b>${o.farm && o.farm.field_ha != null ? `<small class="sub2">시군구 합 ${o.farm.field_ha.toLocaleString('ko-KR')}ha</small>` : ''}</div>`);
  }
  return s.join('');
}

// 공식 산업별 종사자 막대 (전국·시도)
function officialJobs(o, E) {
  const j = o.official && o.official.jobs;
  if (!j) return null;
  return jobBars({ jobs: j.by, jobs_total: j.total, jobs_year_label: `공식 ${j.year} 전국사업체조사${j.combined ? ' · ' + j.combined : ''}` }, E);
}

function econBlock(o, a, kind, P) {
  const E = a.nation.econ, n = a.cities.length;
  if (!E) return '';
  if (o.gdp == null) return `<h4>경제</h4><p class="pending">GRDP 자료 없음</p>`;
  const yr = esc(o.gdp_year_label || o.gdp_year);   // 감사 07: 화면에 그대로 잇는 값이라 미리 esc
  const r = o.ranks || {};
  const OG = kind !== 'city' && o.official && o.official.gdp ? o.official.gdp : null;
  // 7b #12: 다섯 산출은 한 줄(5칸). 도시는 패널 머리에 있고, 시도·전국은 이 구역 맨 위
  const tiles = kind === 'city' ? '' : yieldStrip(o, a, kind, P);
  // 입지계수 (도시만, 7b #11): 전국 공식 비중 대비 배수
  const NO = a.nation.nation.official;
  const lqG = kind === 'city' && o.gdp_by_industry ? (k) => { const b = o.gdp_by_industry, v = b[k]; return v == null || !b.grdp || NO.gdp.by[k] == null ? null : (v / b.grdp) / (NO.gdp.by[k] / NO.gdp.by.grdp); } : null;
  const lqJ = kind === 'city' && o.jobs && o.jobs_total ? (L) => { const v = o.jobs[L]; return v == null || NO.jobs.by[L] == null ? null : (v / o.jobs_total) / (NO.jobs.by[L] / NO.jobs.total); } : null;
  const pnP = partialNote(o, 'production');
  // 비공개 산업 주의가 걸린 산출: 값이 없거나(자료 없음) 부분 합(*)인 것
  const undKeys = YIELD_ICONS.map(([k]) => k).filter((k) => (o.yields ? o.yields[k] : null) == null || partialNote(o, k)).map((k) => `y-${k}`).join(' ');
  const und = o.gdp_undisclosed && o.gdp_undisclosed.length
    ? `<p class="note"${kind === 'city' ? '' : ` data-for="${undKeys}"`}>비공개 산업: ${o.gdp_undisclosed.map((x) => E.industry_ko[x]).join(', ')} — 이 산업이 든 산출은 '자료 없음'으로 둔다 (추정으로 메우지 않음).${pnP ? ` 단 생산은 비공개가 광업뿐이라 제조업 + 건설업 + 공개된 광업 몫의 합으로 냈다 (<b>* ${pnP}</b> — 비공개인 공표 단위의 광업 몫은 빼고 추정하지 않음).` : ''}</p>` : '';
  const g = o.gdp_growth;
  const h = o.housing || {}, em = o.employment || {}, wk = o.workers || {}, fm = o.farm || {};
  const hasH = 'housing' in o;   // 공개판(profile public)에는 아파트 매매·전세 값이 없다
  const multi = kind !== 'city' || (o.sgg && o.sgg.length > 1 && !o.name.endsWith('시'));
  // 특별·광역시: 도시 값이 없으면 자치구 값의 범위 (합치거나 평균하지 않는다)
  const MR = o.member_ranges || {};
  const rng = (r, period) => (r ? `<b class="rng">${esc(r.unit_label)} ${r.min.toFixed(1)}–${r.max.toFixed(1)}%</b><small title="${esc(a.nation.econ.range_note || '')}">${r.n === r.of ? `${esc(r.unit_label)} ${esc(r.n)}곳` : `${esc(r.of)}곳 중 ${esc(r.n)}곳 값 있음`} · ${esc(period || '')} · 범위(합치지 않음)</small>` : null);
  const rk = (k) => (kind === 'city' && r[k] ? `<small class="rk">${esc(r[k])}위/${n}</small>` : '');
  const ref = (k, v, opt) => (kind === 'city' ? refLine(a, o, k, v, opt) : '');
  const OF = kind !== 'city' && o.official ? o.official : null;
  // 특별·광역시 도시 패널: 자치구 범위 옆에 시도 공식값 (경제활동인구조사 월, 재정자립도 시도 전체·본청)
  const OS = kind === 'city' ? o.official_sido : null;
  const osE = (k) => (OS && OS.employment && OS.employment[k] != null ? `<small class="sub2">${esc(OS.scope)} ${OS.employment[k].toFixed(1)}% (${esc(OS.employment.label)}) · 다른 조사</small>` : '');
  const osF = OS && OS.fiscal && OS.fiscal.avg != null ? `<small class="sub2">${esc(OS.scope)} 평균 ${OS.fiscal.avg.toFixed(1)}% · 본청 ${OS.fiscal.hq != null ? OS.fiscal.hq.toFixed(1) + '%' : '–'} (지방재정365 ${esc(OS.fiscal.year)} 당초)</small>` : '';
  const ogTab = OF && OF.gdp ? `<div class="itab" data-pane="gva"><p class="dim sm">공식 ${esc(OF.gdp.year)} · 지역소득 33개 분류를 16 + 순생산물세로 묶음${OF.gdp.combined ? ' · ' + esc(OF.gdp.combined) : ''}</p>${industryBars(OF.gdp.by, E.industry_ko, E.industry_keys)}</div>
    <div class="itab" data-pane="gva_sgg" hidden><p class="dim sm">시군구 합 ${yr} · GRDP 19분류 중 산업 16 + 순생산물세 · 생산지</p>${industryBars(o.gdp_by_industry, E.industry_ko, E.industry_keys)}</div>` : '';
  const ojobs = OF ? officialJobs(o, E) : null;
  return `
    <h4>${kind === 'city' ? '경제 · 산업 구성' : '경제 · 다섯 산출'} <small>${OG ? `공식 GRDP ${esc(OG.year)} (지역소득) · 시군구 합 ${yr} 병기` : `GRDP ${yr}`} · 명목 · 생산지 기준${kind === 'city' ? ` · ×배수 = 입지계수(전국 공식 비중 대비)` : ''}</small></h4>
    ${tiles}${OG ? '' : und}
    ${OG ? `<p class="official-note">공식 GRDP ${fmtWon(OG.grdp)} · 시군구 합 ${fmtWon(o.gdp)} (${yr}) · 차이 ${fmtWon(OG.grdp - o.gdp)}${OG.latest ? ` · ${esc(OG.latest.label)} ${fmtWon(OG.latest.grdp)}` : ''}</p>` : ''}
    <h4 class="tabs"><button data-itab="gva" class="on">${OF && OF.gdp ? '부가가치 (공식)' : '산업별 부가가치'}</button>${OF && OF.gdp ? '<button data-itab="gva_sgg">부가가치 (시군구 합)</button>' : ''}<button data-itab="jobs">${ojobs ? '종사자 (공식)' : '산업별 종사자'}</button>${ojobs ? '<button data-itab="jobs_sgg">종사자 (시군구 합)</button>' : ''}</h4>
    ${ogTab || `<div class="itab" data-pane="gva"><p class="dim sm">${yr} · GRDP 19분류 중 산업 16 + 순생산물세 · 생산지</p>${industryBars(o.gdp_by_industry, E.industry_ko, E.industry_keys, lqG)}</div>`}
    <div class="itab" data-pane="jobs" hidden>${ojobs || jobBars(o, E, lqJ)}</div>
    ${ojobs ? `<div class="itab" data-pane="jobs_sgg" hidden>${jobBars(o, E)}</div>` : ''}
    <div class="kv econ">
      ${OF ? officialKV(o, kind) : `<div><em>1인당 GRDP <small>${yr}</small></em><b data-k="gdppc">${won(o.gdp_per_capita)}</b>${rk('gdp_per_capita')}${ref('gdp_per_capita', o.gdp_per_capita)}</div>
      <div><em>명목 증가율 <small>${g ? `${esc(g.from)}→${esc(g.to)}` : ''}</small></em><b>${g ? (g.rate > 0 ? '+' : '') + g.rate.toFixed(1) + '%' : NA('비교할 이전 연도 GRDP 가 정리표에 없음')}</b>${g && g.series && g.series !== '같은 표' ? `<small class="sub2" title="${esc(g.series)}">과거표 이어 붙임 (2020년 기준 개편)</small>` : ''}</div>`}
      <div><em>1인당 총급여 <small>${esc(o.wage.year)} 귀속 · 주소지</small></em><b>${won(o.wage.per_filer)}</b>${rk('wage')}${ref('wage', o.wage.per_filer)}</div>
      ${hasH ? `<div><em>아파트 매매 ㎡당 <small>${esc(h.months || '')}</small></em><b data-k="housing">${man(h.sale_per_m2, '만원')}</b>${rk('housing')}${h.trades != null ? `<small>매매 ${h.trades.toLocaleString('ko-KR')}건</small>` : ''}${ref('sale_per_m2', h.sale_per_m2, { trades: h.trades })}</div>
      <div><em>아파트 매매 중위 <small>${esc(h.months || '')}</small></em><b>${h.sale_median == null ? NA() : fmtWon(h.sale_median * 1e4)}</b>${ref('sale_median', h.sale_median, { trades: h.trades })}</div>
      <div><em>아파트 전세 중위 <small>${esc(h.months || '')}</small></em><b>${h.jeonse_median == null ? NA() : fmtWon(h.jeonse_median * 1e4)}</b>${h.jeonse_trades != null ? `<small>전세 ${h.jeonse_trades.toLocaleString('ko-KR')}건</small>` : ''}${ref('jeonse_median', h.jeonse_median, { trades: h.jeonse_trades })}</div>`
        : `<div class="gone"><em>아파트 매매·전세</em><b class="na">이 판에서는 제공하지 않음</b><small>공개판 — 연감 › 출처의 '이 판'</small></div>`}
      ${OF ? '' : `<div><em>고용률 <small>${esc(em.period || '')} · 지역별고용조사</small></em>${em.rate != null ? `<b>${em.rate.toFixed(1)}%</b>${ref('employment', em.rate)}` : rng(MR.employment, em.period) || `<b>${NA(multi ? '시군 단위로만 공표 (여러 구의 비율은 합칠 수 없음)' : '')}</b>`}${osE('rate')}</div>
      <div><em>실업률 <small>${esc(em.period || '')} · 지역별고용조사</small></em>${em.unemployment != null ? `<b>${em.unemployment.toFixed(1)}%</b>` : rng(MR.unemployment, em.period) || `<b>${NA()}</b>`}${osE('unemployment')}</div>
      <div><em>재정자립도 <small>${esc(o.fiscal_year || '')}</small></em>${o.fiscal_independence != null ? `<b>${o.fiscal_independence.toFixed(1)}%</b>${ref('fiscal', o.fiscal_independence)}` : rng(MR.fiscal, o.fiscal_year) || `<b>${NA(multi ? '자치구별로만 공표' : '')}</b>`}${osF}</div>`}
      <div><em>종사자 <small>${esc(wk.year || '')} · 사업장</small></em><b>${wk.total == null ? NA() : wk.total.toLocaleString('ko-KR') + '명'}</b></div>
      <div><em>제조업 종사자 <small>${esc(wk.manufacturing_year || '')}</small></em><b>${wk.manufacturing == null ? NA() : wk.manufacturing.toLocaleString('ko-KR') + '명'}</b></div>
      <div><em>농가 <small>${esc(fm.year || '')}</small></em><b>${fm.households == null ? NA() : fm.households.toLocaleString('ko-KR') + '가구'}</b><small>${fm.population == null ? '' : fm.population.toLocaleString('ko-KR') + '명'}</small></div>
      ${OF && OF.farm ? '' : `<div><em>논 <small>${esc(fm.land_year || '')}</small></em><b>${fm.paddy_ha == null ? NA('여러 구를 합친 항목으로만 공표됐거나 자료 없음') : fm.paddy_ha.toLocaleString('ko-KR') + 'ha'}</b></div>
      <div><em>밭 <small>${esc(fm.land_year || '')}</small></em><b>${fm.field_ha == null ? NA() : fm.field_ha.toLocaleString('ko-KR') + 'ha'}</b></div>`}
      <div><em>대졸 이상 <small>${o.degree ? esc(o.degree.year) : ''} · 15세 이상</small></em><b>${o.degree && o.degree.share_15 != null ? o.degree.share_15.toFixed(1) + '%' : NA()}</b>${ref('degree', o.degree && o.degree.share_15)}${o.degree && o.degree.share_25 != null ? `<small>25세 이상 ${o.degree.share_25.toFixed(1)}%</small>` : `<small title="15–24세 칸이 비공개라 25세 이상 비율을 계산할 수 없는 곳이 많다">25세 이상: 계산 불가</small>`}</div>
    </div>
    <p class="note" data-for="gdppc housing">1인당 GRDP 는 생산지 기준 총생산을 같은 해 12월 주민등록 인구로 나눈 값이라 통근 유입이 큰 도시가 높게 나온다.${hasH ? ` 아파트 가격은 ${esc(h.months || '')} 12개월 실거래 전체(해제 제외)의 중위값을 건별 원자료에서 직접 계산했다.` : ''}</p>`;
}

// 지도 층 목록 (도시·시도 패널)
function layerBlock(a, sggSet, cellSet, extra) {
  if (!a.layerR) return `<h4>불가사의·자원·기반시설</h4><p class="dim">지도 층을 불러오는 중…</p>`;
  const items = a.layerR.itemsFor(sggSet, cellSet);
  const groups = new Map();
  for (const it of items) {
    if (!groups.has(it.kind)) groups.set(it.kind, []);
    groups.get(it.kind).push(it);
  }
  let h = `<h4>불가사의·자원·기반시설 <small>소재 시군구 기준 · 국립공원은 칸이 걸치면</small></h4>`;
  if (!items.length && !extra) h += `<p class="dim">이 지역에 놓인 항목이 없다.</p>`;
  for (const [kind, lst] of groups) {
    const K = KINDS[kind];
    const show = kind === 'station' ? lst.slice(0, 12) : lst;
    h += `<div class="lyg"><p class="lyh"><img src="${iconURL(kind, kind === 'station')}" alt=""> ${esc(K.label)} <small>${esc(lst.length)}</small></p>
      <div class="lyl">${show.map((it) => `<button data-item="${esc(it.id)}">${esc(it.name)}${itemValue(it) ? ` <small>${esc(itemValue(it))}</small>` : ''}</button>`).join('')}${lst.length > show.length ? `<span class="dim">외 ${lst.length - show.length}곳</span>` : ''}</div></div>`;
  }
  return h + (extra || '');
}

// 땅: 국가토지피복통계(시군구 행의 합, ha·%), 영토 칸의 피복 비율 평균(칸 넓이 같음), 호수 칸, 갯벌이 닿은 칸
const LAND_KO = { forest: '숲', crop: '농경지', built: '시가지', grass: '초지', wetland: '습지', bare: '나지', water: '수면',
  broadleaf: '활엽수림', conifer: '침엽수림', mixed: '혼효림', paddy: '논', field: '밭', orchard: '과수원', greenhouse: '시설재배지', unclassified: '미분류' };
function landStatsBlock(a, ls) {
  if (!ls) return '';
  const M = a.nation.land_stats_meta || {};
  const head = `<h4>땅 · 국가토지피복통계 <small>${esc(ls.year)}년 기준 · 기후에너지환경부 (2025 작성) · 시군구 행의 합</small></h4>`;
  if (!ls.value) return `${head}<p class="dim sm">${NA(ls.reason)} — ${esc(ls.reason || '')}</p>`;
  const v = ls.value;
  const rows = Object.entries(v.by).map(([k, x]) => `<div class="ib"><span class="lab">${esc(k)}</span><span class="bar"><i style="width:${x.pct == null ? 0 : Math.max(0.5, x.pct)}%"></i></span><span class="val">${x.ha == null ? NA() : x.ha.toLocaleString('ko-KR') + 'ha'}${x.pct == null ? '' : ` <small>${x.pct.toFixed(1)}%</small>`}</span></div>`).join('');
  const old = ls.old_units ? `<p class="dim sm"><b>개편 전 구역 기준 합</b> <span class="note" data-for="land-total">${ls.old_units.map(esc).join(', ')}은 개편 전 단위로만 공표돼 통째로 더함 (자치구·일반구로는 나누지 않음). ${esc(ls.note || '')}</span></p>` : '';
  return `${head}<p class="dim sm"><span data-k="land-total">전체 ${v.total_ha.toLocaleString('ko-KR')}ha</span> · 막대는 전체 대비 %${M.rule ? ` <span class="note" data-for="land-total">${esc(M.rule)}</span>` : ''}</p>${old}<div class="ibars land">${rows}</div>`;
}

function terrainBlock(a, cells, sido, ls) {
  const T = a.terrain, W = a.world;
  if (!T || !T.coverKeys.length) return landStatsBlock(a, ls);
  const keys = T.shareKeys;
  const sum = {};
  for (const k of keys) sum[k] = 0;
  let n = 0, nMe = 0, nEsa = 0, lake = 0;
  const crop = {}, forest = {};
  for (const i of cells) {
    if (W.owner[i] < 0) continue;
    if (W.water[i] === 3) lake++;
    if (!T.cover[i]) continue;
    n++;
    if (T.coverSrc[i] === 1) nMe++; else if (T.coverSrc[i] === 2) nEsa++;
    for (const k of T.coverKeys) sum[k] += T.share[k][i] || 0;
    if (T.coverSrc[i] === 1 || T.coverPublic) for (const k of keys) if (!T.coverKeys.includes(k)) sum[k] += T.share[k][i] || 0;
    if (T.crop[i]) crop[T.crop[i]] = (crop[T.crop[i]] || 0) + 1;
    if (T.forest[i]) forest[T.forest[i]] = (forest[T.forest[i]] || 0) + 1;
  }
  let h = landStatsBlock(a, ls);
  if (!n) return h;
  const parts = T.coverKeys.map((k) => [k, sum[k] / n]).filter(([, v]) => v >= 0.005).sort((x, y) => y[1] - x[1]);
  // 세부 비율: 도엽 통계 칸만 (ESA 보완 칸에는 세부가 없다)
  const nSub = T.coverPublic ? n : nMe;
  const subs = nSub ? ['paddy', 'field', 'orchard', 'greenhouse', 'broadleaf', 'conifer', 'mixed', 'unclassified'].filter((k) => k in sum).map((k) => [k, sum[k] / nSub]).filter(([, v]) => v >= 0.005) : [];
  const cnt = (o) => Object.entries(o).sort((x, y) => y[1] - x[1]).map(([k, v]) => `${esc(LAND_KO[k])} ${v}`).join(', ');
  h += `<h4>땅 · 칸 피복 <small>칸 ${n}개의 비율 평균 · ${esc((W.cover_meta && W.cover_meta.label) || '')}${nEsa ? ` · 도엽 통계가 닿지 않는 ${nEsa}칸은 대체 자료 ESA` : ''}</small></h4>
    <p class="dim sm" data-k="cover-share">${parts.map(([k, v]) => `${esc(LAND_KO[k])} ${(v * 100).toFixed(0)}%`).join(' · ')}</p>
    ${subs.length ? `<p class="dim sm" data-k="cover-sub">${T.coverPublic ? '농경지 세부' : `도엽 통계 칸 ${nMe}개의 세부`}: ${subs.map(([k, v]) => `${esc(LAND_KO[k])} ${(v * 100).toFixed(1)}%`).join(' · ')}</p>` : ''}
    ${W.cover_meta && W.cover_meta.bias_note ? `<p class="note" data-for="cover-share cover-sub">칸 비율은 ${esc(W.cover_meta.bias_note)}</p>` : ''}
    <p class="dim sm">${Object.keys(crop).length ? `농경지가 대표인 칸 — ${cnt(crop)}` : ''}${Object.keys(crop).length && Object.keys(forest).length ? ' · ' : ''}${Object.keys(forest).length ? `숲이 대표인 칸 — ${cnt(forest)}` : ''}${lake ? ` · 호수 칸 ${lake}` : ''}</p>`;
  const td = sido && W.tidal && W.tidal.by_sido[sido];
  if (td) h += `<p class="dim sm tidal">갯벌: 갯벌 타일 ${esc(td.tile_cells)}칸 · 폴리곤 넓이 ${td.area_km2.toLocaleString('ko-KR')} km² <small>(해양수산부 1:25,000 연안정보도, ${esc(W.tidal.year)}년 제작 · 바다 칸은 가장 가까운 육지 칸의 시도)</small></p>`;
  return h;
}

// 청사: 시도청·통합특별시 청사(이 도시에 있는 것), 시군구청 주소
function officeBlock(a, c) {
  const cn = (codes) => (codes || []).map((x) => (a.world.counties.find((k) => k.code === x) || {}).name || x).join('·');
  const so = c.sido_offices || [], own = c.offices || [];
  if (!so.length && !own.length) return '';
  const st = a.stateByCode.get(c.sido);
  const sp = st && st.special_offices;
  let h = `<h4>청사 <small>행정안전부 공표본 주소 → 시군구 (시군구 대표 위치)</small></h4><ul class="names offices">`;
  for (const o of so) h += `<li><b>${esc(o.name)}</b> <small>${esc(o.role)}${o.law ? ' · ' + esc(o.law) : ''} · ${esc(o.address || '주소 없음')} (${esc(cn(o.sgg))})</small></li>`;
  for (const o of own.slice(0, 8)) h += `<li>${esc(o.name)} <small>${esc(o.kind)} · ${esc(o.address)}</small></li>`;
  if (own.length > 8) h += `<li class="dim">외 ${own.length - 8}곳</li>`;
  h += '</ul>';
  if (sp && so.some((o) => o.role === '통합특별시 청사')) {
    h += `<p class="note">${esc(sp[0].law)}: 청사 3곳(${sp.map((e) => esc(e.name)).join('·')})을 모두 적고 수도(주 청사) 표시를 하나로 정하지 않는다.</p>`;
  }
  return h;
}

function gicLine(g, label) {
  if (!g) return '';
  return `<div class="lyg"><p class="lyh">🏭 일반산업단지 <small>${label}</small></p><p class="dim sm">단지 ${esc(g.count)}곳 · 지정면적 ${g.area_km2.toLocaleString('ko-KR', { maximumFractionDigits: 2 })} km² · 가동업체 ${g.operating.toLocaleString('ko-KR')}곳 (입주 ${g.tenants.toLocaleString('ko-KR')})</p></div>`;
}

// 발전설비: 소재 시군구별 연료원 설비용량 합 (EPSIS 발전기 현황)
const FUEL_COLOR = { nuclear: '#d6b11f', coal: '#4a4440', coal_gasification: '#6d625a', gas: '#d0632a', oil: '#6b4a2a', hydro: '#2f7fc0', pumped: '#5c8fd0',
  solar: '#e3a21a', wind: '#5aa6a0', fuel_cell: '#9b6fc0', bio: '#6f9b3c', ocean: '#2a9db0', unspecified: '#8d8a84' };
function powerBlock(a, pw, label) {
  const P = a.layers && a.layers.resources.power;
  if (!P) return '';
  const head = `<p class="lyh">⚡ 발전설비 <small>${label} · 발전기 소재지 · EPSIS ${esc(P.date)}</small></p>`;
  if (!pw || !Object.keys(pw).length) return `<div class="lyg">${head}<p class="dim sm">이 지역 소재지로 적힌 발전기가 없다.</p></div>`;
  const ks = Object.keys(pw).sort((x, y) => pw[y] - pw[x]);
  const tot = ks.reduce((t, k) => t + pw[k], 0), mx = pw[ks[0]] || 1;
  const f = (v) => v.toLocaleString('ko-KR', { maximumFractionDigits: v < 10 ? 2 : 1 });
  return `<div class="lyg">${head}<p class="dim sm">합계 ${f(tot)} MW</p><div class="ibars pw">${ks.map((k) => `<div class="ib"><span class="lab">${esc(P.fuel_ko[k] || k)}</span><span class="bar"><i style="width:${Math.max(0.5, (100 * pw[k]) / mx)}%;background:${esc(FUEL_COLOR[k] || '#999')}"></i></span><span class="val">${f(pw[k])} MW</span></div>`).join('')}</div></div>`;
}

// 식량 구역: 쌀(논벼 2026)·한우(2026-10)·돼지(시군 2026 방역본부, 시도는 가축동향조사 2026년 3분기도 나란히) — 빈 값·없는 행은 '자료 없음'
function farmBlock(a, get, sido, cityId) {
  const F = a.layers && a.layers.resources.farm;
  if (!F) return '';
  const row = (k) => {
    if (!F[k]) return '';   // 그 판에 없는 항목 (공개판의 한우)
    let v = get(F[k]);
    if (k === 'pigs' && sido && v === undefined) v = null; // 원표에 시군 행이 하나도 없는 시도(서울)
    if (v === undefined) return '';
    let na = '소속 시군구 가운데 원표에 행이 없는 곳이 있어 합을 내지 않음 (0 이 아님)', sub = '';
    if (k === 'pigs') {
      const M = cityId != null && F.pigs.metro ? F.pigs.metro[cityId] : null;
      na = M ? `원표가 ${esc(M.scope)} 한 값만 공표해 이 도시 몫을 나눌 수 없음` : '원표에 이 시군 행이 없음 (0 이 아님)';
      if (v == null && M) sub = `<small>${esc(M.scope)} ${M.value.toLocaleString('ko-KR')}마리에 포함</small>`;
    }
    return `<div><em>${esc(F[k].label)} <small>${esc(F[k].year)}</small></em><b data-k="farm-${k}">${v == null ? NA(na) : v.toLocaleString('ko-KR') + F[k].unit}</b>${sub}</div>`;
  };
  let h = ['rice', 'cattle', 'pigs'].map(row).join('');
  const P = F.pigs_sido_2026;
  if (sido && P) {
    const v = P.by_sido[sido];
    h += `<div><em>돼지 <small>${esc(P.period)} · 시도</small></em><b data-k="farm-pigs-sido">${v == null ? NA('원표에 이 시도 행이 없음') : v.toLocaleString('ko-KR') + '마리'}</b><small>가축동향조사 (전체 돼지)</small></div>`;
  }
  const pyr = F.pigs ? F.pigs.year : '';
  const hw = !!F.cattle;   // 공개판에는 한우가 없다
  return h ? `<div class="lyg"><p class="lyh">🌾 식량 <small>쌀 2026${hw ? ' · 한우 2026-10' : ''} · 돼지 ${esc(pyr)} <span class="note"${sido ? ' data-for="farm-pigs farm-pigs-sido"' : ''}>논벼 생산량 (2026)${hw ? ' · 한우 (2026-10, 농장 소재지)' : ''} · 돼지 (${esc(pyr)} 가축위생방역지원본부, 일반돼지만 · 방역 시스템 등록 농가${sido ? '; 시도는 가축동향조사 2026년 3분기도 — 조사가 달라 값이 다름' : ''})</span></small></p><div class="kv econ">${h}</div></div>` : '';
}

// 보훈대상자: 국가보훈부 시군구 인원 (대상구분 합계의 합 — 대상 사이 중복이 있어 실제 인원보다 많을 수 있음) ÷ 주민등록 인구
function veteransBlock(V, kind) {
  if (!V) return '';
  const n = (x) => x.toLocaleString('ko-KR');
  const p = (x) => x.toLocaleString('ko-KR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  let h = '';
  if (V.count == null) {
    h = `<div><em>인원</em><b data-k="vet-count">${NA('소속 시군구 가운데 값이 없는 곳이 있음')}</b><small>${esc((V.missing || []).join(', '))} — 최신 분기 원표에 행이 없음</small></div>`;
  } else {
    const partial = kind === 'state' && !V.complete;
    h = `<div><em>인원 <small>${kind === 'state' ? '시군구 합' : kind === 'metro' ? '자치구 합' : '시군구 합'}</small></em><b data-k="vet-count">${n(V.count)}명${partial ? '<sup title="부분 합">*</sup>' : ''}</b>${partial ? `<small>* ${esc(V.missing.join(', '))} 자료 없음 — 부분 합</small>` : ''}</div>
      <div><em>인구 천 명당</em><b>${V.per_1000 == null ? NA(partial ? '부분 합이라 계산하지 않음' : '인구 자료 없음') : p(V.per_1000) + '명'}</b><small>주민등록 ${esc(V.pop_ym || '')}</small></div>`;
    if (kind === 'state' && V.sido_row != null) h += `<div><em>원표 시도 합계 행 <small>대조용</small></em><b>${n(V.sido_row)}명</b>${V.sido_row_per_1000 != null ? `<small>천 명당 ${p(V.sido_row_per_1000)}명</small>` : ''}</div>`;
  }
  const res = (V.residual || []).length ? `<p class="note" data-for="vet-count">현재 구 하나로 나눌 수 없는 옛 구역 행 ${V.residual.map((r) => `${esc(r.name)} ${n(r.value)}명`).join(', ')}을 합에 넣었다(시군구 렌즈 값에는 없음).</p>` : '';
  return `<div class="lyg"><p class="lyh">🎖️ 보훈대상자 <small>국가보훈부 ${esc(V.period || '')}</small></p><div class="kv econ">${h}</div><p class="note" data-for="vet-count">대상구분별 인원의 합이라 대상 사이 중복이 있어 실제 인원보다 많을 수 있다.</p>${res}</div>`;
}

// 주력 업종: 2020 경제총조사(전국 한 기준)와, 있으면 최신 값(시도별 사업체조사 2024 / 인천 2022)을 연도와 함께 나란히
function keyIndBlock(a, id) {
  const K = a.layers && a.layers.resources.key_industries;
  const r = K && K.by_city[id];
  if (!r) return '';
  const f = (v, p) => (v == null ? '<span class="na">비공개</span>' : v.toLocaleString('ko-KR') + '명' + (p ? '<sup title="소속 시군구 가운데 비공개(빈 값)가 있어 공개값만 더함">*</sup>' : ''));
  const rows = K.codes.filter((c) => r[c]).map((c) => {
    const [v20, p20, vl, pl, yl] = r[c];
    return `<tr><th>${c} ${esc(K.short[c])}</th><td class="num">${f(v20, p20)}</td><td class="num">${v20 != null && K.national_2020[c] ? ((100 * v20) / K.national_2020[c]).toFixed(1) + '%' : '–'}</td>
      <td class="num">${yl ? f(vl, pl) + ` <small>${esc(yl)}</small>` : '<span class="dim">자료 없음</span>'}</td></tr>`;
  }).join('');
  return `<div class="lyg"><p class="lyh">🏭 주력 업종 종사자 <small>2020 경제총조사(전국) · 최신: 시도별 사업체조사 2024, 인천 2022</small></p>
    <table class="tbl ki"><thead><tr><th></th><th class="num">2020</th><th class="num">전국 중</th><th class="num">최신</th></tr></thead><tbody>${rows}</tbody></table>
    <p class="note">비공개(빈 값)는 0 이 아니다. * 표시는 공개값만 더한 부분 합. '전국 중'의 분모는 2020 전국 공개값 합. 최신 값은 부산·광주·대전·울산·강원에 없다.</p></div>`;
}

// 교역 (관세청 수출입 2025): 도시 = 소속 시군구 공표 단위의 합, 품목은 공표 단위별 상위 5 그대로
const usdT = (v) => {
  if (v == null) return '자료 없음';
  const x = Math.abs(v), sg = v < 0 ? '−' : '';
  if (x >= 1e8) return sg + (x / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 1 }) + '억 달러';
  if (x >= 1e4) return sg + Math.round(x / 1e4).toLocaleString('ko-KR') + '만 달러';
  return sg + Math.round(x).toLocaleString('ko-KR') + ' 달러';
};
const usd = (v) => (v == null ? NA() : usdT(v));
const hsCode = (c) => String(c).padStart(2, '0');
function hsBars(TJ, lst) {
  if (!lst || !lst.length) return '<p class="dim sm">품목 자료 없음</p>';
  const mx = lst[0][1] || 1;
  return `<div class="ibars hs">${lst.map(([c, v]) => {
    const nm = TJ.hs_names[hsCode(c)] || '';
    return `<div class="ib" title="HS${hsCode(c)} ${esc(nm)}"><span class="lab">HS${hsCode(c)} ${esc(nm)}</span><span class="bar"><i style="width:${Math.max(0.5, (100 * v) / mx)}%"></i></span><span class="val">${usdT(v * 1000)}</span></div>`;
  }).join('')}</div>`;
}
function unitName(a, key) {
  const codes = key.split('+');
  const c = a.cityById.get(a.countyCity[a.world.counties.findIndex((x) => x.code === codes[0])]);
  if (c && codes.length > 1 && c.sgg.length === codes.length) return c.name;
  return codes.map((x) => (a.world.counties.find((k) => k.code === x) || {}).name || x).join('·');
}
function tradeBlock(a, o, kind) {
  const T = o.trade, TJ = a.layers && a.layers.trade;
  let h = `<h4>교역 · 수출입 <small>관세청 2025 · 신고 수리일 기준 · 달러${kind !== 'city' ? ' · 시군구 공표값의 합' : ''}</small></h4>`;
  if (!T || T.export == null) {
    return h + `<p class="dim sm">${NA()} — ${TJ ? esc(TJ.trade.unmatched_note) : '이 도시의 공표 단위를 현재 시군구 코드에 대응하지 못함'}</p>`;
  }
  const nr = a.cities.filter((c) => c.ranks && c.ranks.export).length;
  const rk = kind === 'city' && o.ranks && o.ranks.export ? `<small class="rk">수출 ${esc(o.ranks.export)}위/${nr}</small>` : '';
  h += `<div class="kv econ"><div><em>수출 <small>제조장소</small></em><b data-k="trade-export">${usd(T.export)}</b>${rk}</div><div><em>수입 <small>납세의무자 주소지</small></em><b data-k="trade-import">${usd(T.import)}</b></div>
    <div><em>무역수지 <small>원표</small></em><b class="${T.balance >= 0 ? 'up' : 'down'}">${T.balance > 0 ? '+' : ''}${usd(T.balance)}</b></div>${kind !== 'city' ? `<div><em>공표 단위</em><b>${esc(T.units)}곳</b></div>` : ''}</div>`;
  if (!TJ) return h + (a.layerFailed && a.layerFailed.trade ? '<p class="na sm">품목 자료(trade.json)를 불러오지 못했습니다. 화면 위의 ‘다시 시도’를 누르십시오.</p>' : '<p class="dim sm">품목 자료를 불러오는 중…</p>');
  h += `<p class="note" data-for="trade-export trade-import">${esc(TJ.trade.basis)}</p>`;
  if (kind === 'city') {
    const units = (T.units || []).map((k) => [k, TJ.units[k]]).filter(([, u]) => u);
    if (units.length === 1) {
      const u = units[0][1];
      h += `<p class="lyh">수출 상위 품목 <small>HS 2단위</small></p>${hsBars(TJ, u.e)}<p class="lyh">수입 상위 품목</p>${hsBars(TJ, u.i)}`;
    } else if (units.length > 1) {
      units.sort((x, y) => (y[1].v ? y[1].v[0] : 0) - (x[1].v ? x[1].v[0] : 0));
      h += `<p class="dim sm">품목은 공표 단위(구)별 상위 5개만 있어 도시로 합쳐 다시 매기지 않는다 — 구별 목록 ${esc(units.length)}개:</p>`
        + units.map(([k, u]) => `<details class="hsu"><summary>${esc(unitName(a, k))} <small>수출 ${usdT(u.v ? u.v[0] : null)} · 수입 ${usdT(u.v ? u.v[1] : null)}</small></summary>
          <p class="lyh">수출 상위</p>${hsBars(TJ, u.e)}<p class="lyh">수입 상위</p>${hsBars(TJ, u.i)}</details>`).join('');
    }
    h += `<p class="note" data-for="trade-import">${esc(TJ.trade.hq_note)}</p>`;
  } else {
    const pool = kind === 'state' ? o.cities.map((id) => a.cityById.get(id)) : a.cities;
    const cs = pool.filter((c) => c.trade && c.trade.export != null).sort((x, y) => y.trade.export - x.trade.export).slice(0, kind === 'state' ? 6 : 10);
    h += `<p class="lyh">수출 상위 도시</p><div class="lyl">${cs.map((c) => `<button data-city="${esc(c.id)}">${esc(c.name)} <small>${usdT(c.trade.export)}</small></button>`).join('')}</div>`;
    if (T.unmatched && T.unmatched.length) h += `<p class="note" data-for="trade-export trade-import">현재 시군구 코드에 대응하지 못한 공표 단위 (도시에는 붙이지 않고 이 합에는 넣음): ${T.unmatched.map((u) => esc(u.name)).join(', ')}</p>`;
    if (kind === 'nation') h += `<p class="note" data-for="trade-import">${esc(T.note)} ${esc(TJ.trade.hq_note)}</p>`;
  }
  return h;
}

// 시도 패널: 도로 화물 상대 시도 상위 5, 시도 안 흐름 비중
function freightBlock(a, s) {
  const F = s.freight;
  if (!F) return '';
  const R = a.layers && a.layers.trade && a.layers.trade.routes;
  const t = (v) => (v / 1e4).toLocaleString('ko-KR', { maximumFractionDigits: 0 }) + '만 톤';
  return `<h4>교역로 · 도로 화물 <small>${esc(F.year)} · 시도 간 O/D · 국가물류통합정보센터</small></h4>
    <p class="dim sm">시도 안 흐름 ${t(F.intra_t)} — 이 시도에서 출발한 도로 화물 ${t(F.out_t)} 가운데 ${esc(F.intra_share_out)}% 가 시도 안에 도착${F.note ? ' · ' + esc(F.note) : ''}</p>
    <p class="lyh">상대 시도 상위 5 <small>두 방향 합</small></p><div class="lyl">${F.partners.map((p) => {
      const S = a.stateByCode.get(p.sido), inTop = R && p.rank <= R.top_n;
      return `<button ${inTop ? `data-route="${[s.code, p.sido].sort().join('-')}"` : `data-state="${esc(p.sido)}"`}>${esc(S.short)} <small>${t(p.total)} (보냄 ${t(p.out)} · 받음 ${t(p.in)}) · 구간 ${esc(p.rank)}위${inTop ? '' : ' · 지도에 그리지 않음'}</small></button>`;
    }).join('')}</div>`;
}

function minesBlock(a, m, label) {
  if (!m || !a.layers || !a.layers.resources.mines_5d) return '';
  return `<div class="lyg"><p class="lyh"><img src="${iconURL('mine')}" alt=""> 가행 광산 (광종별) <small>${label} <span class="note">한국광해광업공단 국내광산검색 (수집 2026-11, 소재지 → 시군구)</span></small></p>
    <p class="dim sm">${Object.entries(m).map(([k, v]) => `${esc(k)} ${v}곳`).join(' · ')}</p></div>`;
}

// 대학 연구비: 소재지가 시도까지만이라 지도에 놓지 않고 시도 패널에 순위로
function fundingBlock(a, s) {
  const K = a.layers && a.layers.resources.knowledge;
  if (!K || !K.funding_by_sido) return '';
  const d = K.funding_by_sido[s.code];
  const top = K.funding_top.filter((x) => x.sido === s.code);
  const eok = (v) => (v / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 0 }) + '억원';
  return `<div class="lyg"><p class="lyh"><img src="${iconURL('knowledge')}" alt=""> 대학 연구비 <small>대학알리미 ${esc(K.funding_year)} <span class="note">${esc(a.layers.wonders.universities && a.layers.wonders.universities.status === 'ok' ? '연구비 상위 대학은 6단계부터 주소로 지도에 지식 불가사의로 놓는다(아래 층 목록). 이 시도 합은 대학알리미 공시 행의 시도 합이다.' : '대학알리미 연구비 공시의 소재지가 시도까지만 있어 이 순위만으로는 지도에 놓지 않는다.')}</span></small></p>
    ${d ? `<p class="dim sm">이 시도 공표 학교·캠퍼스 ${esc(d.count)}곳 합 ${eok(d.won)}</p>` : '<p class="dim sm">이 시도 공표 행 없음</p>'}
    ${top.length ? `<ul class="names">${top.map((x) => `<li>전국 ${esc(x.rank)}위 ${esc(x.name)} <small>${eok(x.won)}</small></li>`).join('')}</ul>`
    : `<p class="dim sm">전국 상위 ${esc(K.funding_top.length)}곳 가운데 이 시도 학교 없음${d ? ` · 이 시도 1위 ${esc(d.top[0].name)} (전국 ${esc(d.top[0].rank)}위, ${eok(d.top[0].won)})` : ''}</p>`}</div>`;
}

// 6단계: 렌즈 막대에서 뺀 지표와 건강 지수 (시군구 값). 도시가 시군구 여럿이면 값이 같을 때만 하나로, 다르면 범위
function retiredBlock(a, c) {
  const items = [...a.retiredById.values()].filter((x) => !['under15', 'age', 'sex_ratio'].includes(x.id));
  const H = a.lensById.get('health');
  if (!items.length && !H) return '';
  const ks = c.sgg.map((code) => a.countyIndex.get(code));
  const cell = (vals, L) => {
    const have = vals.filter((v) => v != null);
    if (!have.length) return `<b>${NA('이 도시의 시군구에 값이 없음')}</b>`;
    const lo = Math.min(...have), hi = Math.max(...have);
    if (lo === hi && have.length === vals.length) return `<b>${formatValue(lo, L)}</b>`;
    if (lo === hi) return `<b>${formatValue(lo, L)}</b><small>${esc(vals.length)}곳 중 ${esc(have.length)}곳 값</small>`;
    return `<b class="rng">${formatValue(lo, L)}–${formatValue(hi, L)}</b><small>구별 범위 · ${esc(vals.length)}곳 중 ${esc(have.length)}곳 값 (합치지 않음)</small>`;
  };
  const kv = (L, vals) => `<div><em>${esc(L.emoji)} ${esc(L.name)} <small>${esc(L.vintage || '')}</small></em>${cell(vals, L).replace(/^<b/, `<b data-k="ret-${esc(L.id)}"`)}</div>`;
  const hv = H ? ks.map((k) => H.by_county[k]) : null;
  const comp = H ? items.filter((x) => x.near === 'health') : [];
  const rest = items.filter((x) => x.near !== 'health');
  // 감사 01: 이 도시의 시군구 값 가운데 시 전체·개편 전 구 단위로 공표된 값 (빌드가 적은 units)
  const ul = new Map();
  for (const L of [...(H ? [H] : []), ...comp, ...rest]) {
    const vals = L.by_county || L.values;
    for (const k of ks) {
      const u = vals[k] != null ? unitOf(L, k) : null;
      if (!u) continue;
      const key = u.label.replace(/으로 계산$/, '');
      if (!ul.has(key)) ul.set(key, { u, names: new Set() });
      ul.get(key).names.add(L.name);
    }
  }
  const unote = ul.size ? `<p class="note unitnote">구 칸에 같은 값을 칠한 공표 단위: ${[...ul.entries()].map(([lab, { u, names }]) => `${esc(lab)} — ${u.counties.map((k) => esc(a.world.counties[k].name.split(' ').pop())).join('·')} (${[...names].map(esc).join('·')})`).join('; ')}</p>` : '';
  return `<h4>건강 · 더 많은 지표 <small>시군구 값 · 렌즈 막대에서 뺀 지표 포함</small></h4>
    <div class="kv econ">${H ? kv(H, hv) : ''}${comp.map((x) => kv(x, ks.map((k) => x.values[k]))).join('')}${rest.map((x) => kv(x, ks.map((k) => x.values[k]))).join('')}</div>${unote}
    ${H ? `<p class="note" data-for="ret-health">${esc(H.definition)}</p>` : ''}<p class="note">${esc(a.lenses.retired_values.rule)} ${a.lenses.retired_values.items.some((x) => x.id === 'conifer') ? '밭·침엽수림' : '밭'}은 칸 값의 시군구 평균, 논 비율(시군구 통계)·순이동률·농림어업 비중·건강 네 지표는 원래 시군구 값이다.</p>`;
}

// ---------- 7b: 전국 기준 대비 · 순위 막대 · 산출 띠 · 특성 표시 · 닮은 도시 근거 ----------
// 말풍선 내용 등록기: 패널을 열 때마다 새로 만든다. 단추의 data-pop 열쇠로 #fnpop 에 띄운다 (기준과 주의 서랍에 넣지 않는 설명)
function popReg() {
  const m = new Map();
  const reg = (html) => { const k = 'p' + m.size; m.set(k, html); return k; };
  reg.map = m;
  return reg;
}

// 전국 기준 대비 한 줄 (nation.benchmarks). 값이 없거나 범위·연도 차이로 비교하지 않을 때는 빈 문자열
function refLine(a, c, key, val, opt = {}) {
  const BM = a.nation.nation.benchmarks, M = BM && BM.metrics[key];
  if (!M || val == null || M.v == null) return '';
  const refName = M.ref === 'city_median' ? '도시 중앙' : '전국';
  const yr = key === 'gdp_per_capita' && c.gdp_year && M.year && c.gdp_year !== M.year ? `('${String(M.year).slice(2)})` : '';
  const lab = refName + yr;
  const fmtRef = M.fmt === 'won' ? fmtWon(M.v) + '원' : M.fmt === 'won1e4' ? fmtWon(M.v * 1e4) + '원' : M.fmt === 'man' ? Math.round(M.v).toLocaleString('ko-KR') + '만원'
    : M.fmt === 'f2' ? M.v.toFixed(2) : M.v.toFixed(1) + (M.unit === '%' ? '%' : M.unit);
  let txt, arrow = '';
  if (M.mode === 'ratio') {
    const p = (val / M.v - 1) * 100;
    if (Math.abs(p) < BM.eq.ratio_pct) txt = `= ${lab} 수준`;
    else { arrow = p > 0 ? '▲' : '▼'; txt = `${arrow} ${lab} ${p > 0 ? '+' : '−'}${Math.abs(p).toFixed(0)}%`; }
  } else {
    const d = val - M.v, f2 = M.fmt === 'f2';
    if (Math.abs(d) < (f2 ? BM.eq.diff_f2 : BM.eq.diff)) txt = `= ${lab} 수준`;
    else {
      arrow = d > 0 ? '▲' : '▼';
      const u = M.unit === '%' ? '%p' : M.unit;
      txt = `${arrow} ${lab} ${d > 0 ? '+' : '−'}${Math.abs(d).toFixed(f2 ? 2 : 1)}${u}`;
    }
  }
  if (opt.trades != null && opt.trades < 10) txt += ` (거래 ${esc(opt.trades)}건)`;
  const tip = `${esc(M.label)}: 기준 ${lab} ${fmtRef}${M.ref === 'city_median' ? ` (값이 있는 도시 ${esc(M.n)}곳의 중앙값 — 같은 산식의 전국값이 없음)` : ''}. 화살표는 크고 작음만 뜻한다.`;
  return `<small class="ref" title="${esc(tip)}">${txt}</small>`;
}

// 순위 막대 (도시 패널 '개요'): 9개 지표, 1열. 행을 누르면 바로 위·아래 순위 도시와 도내 1위
const RK = [
  ['population', '인구', (c) => c.population, (v) => fmtMan(v) + '명'],
  ['growth', '5년 인구 증감', (c) => c.growth_5y, (v) => (v > 0 ? '+' : '') + v.toFixed(1) + '%'],
  ['over65', '고령 비율', (c) => c.age.over65, (v) => v.toFixed(1) + '%'],
  ['extinction', '소멸위험', (c) => c.extinction_index, (v) => '지수 ' + v.toFixed(2)],
  ['gdp', 'GRDP', (c) => c.gdp, (v) => fmtWon(v) + '원'],
  ['gdp_per_capita', '1인당 GRDP', (c) => c.gdp_per_capita, (v) => fmtWon(v) + '원'],
  ['wage', '1인당 총급여', (c) => c.wage && c.wage.per_filer, (v) => fmtWon(v) + '원'],
  ['housing', '아파트 ㎡당', (c) => c.housing && c.housing.sale_per_m2, (v) => Math.round(v).toLocaleString('ko-KR') + '만원'],
  ['export', '수출', (c) => c.trade && c.trade.export, (v) => usdT(v)],
];
function rankRows(a, c) {
  const den = (a.nation.nation.benchmarks || {}).rank_denominators || {};
  // 그 판에 없는 순위(공개판의 아파트 ㎡당)는 줄을 만들지 않는다 — 분모가 없는 지표
  return RK.filter(([k]) => k in den).map(([k, name, get]) => {
    const r = c.ranks[k], N = den[k] || a.cities.length;
    if (r == null) return `<div class="rk-item"><div class="rk-row disabled" aria-label="${name} 자료 없음, 순위 제외"><span class="rk-l">${name}</span><span class="rk-na">자료 없음 · 순위 제외</span></div></div>`;
    const pos = N > 1 ? ((N - r) / (N - 1)) * 100 : 100;
    const risk = k === 'extinction';
    const top = risk ? '1위 = 가장 위험(지수가 가장 낮음)' : '1위 = 가장 큼';
    return `<div class="rk-item"><button type="button" class="rk-row" data-rk="${k}" aria-expanded="false" aria-label="${name} ${N}개 도시 중 ${r}위, 상위 ${Math.max(1, Math.round((r / N) * 100))}% — 인접 순위 보기" title="${top} · 오른쪽 끝이 1위">
      <span class="rk-l">${name}</span><span class="rk-t"><i class="${risk ? 'risk' : ''}" style="left:${pos.toFixed(1)}%"></i></span><span class="rk-v">${r}위<small>/${N}</small></span></button><div class="rk-adj" hidden></div></div>`;
  }).join('');
}
function rankAdj(a, c, k) {
  const [, , get, f] = RK.find((x) => x[0] === k);
  const r = c.ranks[k];
  const at = (rr) => a.cities.find((x) => x.ranks[k] === rr && x.id !== c.id);
  const chip = (x, lab) => (x ? `<button type="button" data-city="${esc(x.id)}">${lab} ${esc(x.name)} <small>${get(x) == null ? '자료 없음' : f(get(x))}</small></button>` : '');
  const inSido = a.cities.filter((x) => x.sido === c.sido && x.ranks[k] != null).sort((p, q) => p.ranks[k] - q.ranks[k]);
  const best = inSido[0];
  return chip(at(r - 1), `▲ ${r - 1}위`) + chip(at(r + 1), `▼ ${r + 1}위`) + (best && best.id !== c.id && inSido.length > 1 ? chip(best, `도내 1위 (${esc(best.ranks[k])}위)`) : '');
}

// 다섯 산출 한 줄 (7b #12): 도시는 시군구 합 값과 순위, 시도·전국은 공식값. 칸을 누르면 구성 산업·종사자·기준
function yieldStrip(o, a, kind, P) {
  const E = a.nation.econ;
  const OG = kind !== 'city' && o.official && o.official.gdp ? o.official.gdp : null;
  const yr = esc(o.gdp_year_label || o.gdp_year);   // 감사 07: 화면에 그대로 잇는 값이라 미리 esc
  const r = o.ranks || {};
  return `<div class="yields" role="group" aria-label="다섯 산출">${YIELD_ICONS.map(([k, ic]) => {
    const pn = partialNote(o, k);
    const rk = kind === 'city' ? r[k === 'gold' ? 'gdp' : k] : null;
    const v = OG ? OG.yields[k] : o.yields ? o.yields[k] : null;
    let tip = `<b>${ic} ${esc(YNAME[k])}</b> — ${esc(YRULE[k])} 부가가치 (명목, 생산지)`;
    if (OG) {
      const sv = o.yields ? o.yields[k] : null, lv = OG.latest ? OG.latest.yields[k] : null;
      tip += `<br>공식 ${esc(OG.year)} (지역소득)${OG.combined ? ' · ' + esc(OG.combined) : ''}: ${v == null ? '자료 없음' : fmtWon(v) + '원'}<br>시군구 합 ${esc(String(yr || ''))}: ${sv == null ? '자료 없음' : fmtWon(sv) + '원'}${pn ? ` * (${pn})` : ''}`;
      if (OG.latest) tip += `<br>${esc(OG.latest.label)}: ${lv == null ? '자료 없음' : fmtWon(lv) + '원'}`;
    } else {
      tip += `<br>시군구 합 GRDP ${esc(String(yr || ''))}: ${v == null ? '자료 없음' : fmtWon(v) + '원'}${rk ? ` · 도시 ${esc(a.cities.length)}곳 중 ${rk}위` : ''}`;
      if (v == null && o.gdp_undisclosed && o.gdp_undisclosed.length) tip += `<br>구성 산업 비공개: ${o.gdp_undisclosed.map((x) => esc(E.industry_ko[x])).join(', ')} — 추정으로 메우지 않음`;
      const jl = E.jobs_map && E.jobs_map[k];
      if (o.jobs && (jl || k === 'gold')) {
        const vals = k === 'gold' ? [o.jobs_total] : jl.map((L) => o.jobs[L]);
        const lab = k === 'gold' ? '전산업 종사자' : jl.map((L) => `${esc(L)} ${esc(E.ksic_ko[L])}`).join(' + ');
        tip += `<br>👷 ${lab}: ${vals.some((x) => x == null) ? '비공개 포함' : vals.reduce((s_, x) => s_ + x, 0).toLocaleString('ko-KR') + '명'} (${esc(String(o.jobs_year_label || o.jobs_year))}, 사업장 소재지)`;
      }
    }
    if (pn) tip += `<br><span class="pmn">* 제조업 + 건설업 + 공개된 광업의 합 (${pn}, 비공개 몫은 추정해 더하지 않음)</span>`;
    const key = P(tip);
    const vt = v == null ? '<span class="na">자료 없음</span>' : fmtWon(v);
    const sm = OG ? `공식 '${String(OG.year).slice(2)}` : rk ? `${rk}위` : '';
    const al = `${esc(YNAME[k])} ${v == null ? '자료 없음' : fmtWon(v) + '원'}${pn ? ', 부분 합계' : ''}${rk ? `, 전국 ${rk}위` : ''} — 세부 기준 보기`;
    return `<button type="button" class="yt ${pn && !OG ? 'partial' : ''}" data-pop="${key}" aria-expanded="false" aria-label="${esc(al)}"><em>${ic} ${esc(YNAME[k])}</em><b>${vt}${pn && !OG ? '<sup class="pm">*</sup>' : ''}</b><small>${sm}</small></button>`;
  }).join('')}</div>`;
}

const RK_KO = { gdp_per_capita: '1인당 GRDP', export: '수출', wage: '1인당 총급여' };
function tagsBlock(a, c, P) {
  if (!c.tags || !c.tags.length) return '';
  const E = a.nation.econ, N = a.nation.nation, OG = N.official.gdp, den = (N.benchmarks || {}).rank_denominators || {};
  const lt = (v) => (v >= 10 ? String(Math.round(v)) : v.toFixed(1));
  return `<div class="tags" role="group" aria-label="데이터 기반 도시 특성">${c.tags.map((t) => {
    let tip;
    if (t.t === 'ind') {
      tip = `${esc(c.name)} ${esc(E.industry_ko[t.k])} 비중 ${t.sh.toFixed(1)}% ÷ 전국 공식 ${t.nat.toFixed(1)}% = ×${lt(t.lq)} (입지계수 LQ · 도시는 시군구 합 GRDP ${esc(c.gdp_year)}, 전국은 지역소득 ${esc(OG.year)} · 반올림 전 값으로 계산)`;
      if (t.small) tip += ' — 인구 5만 미만 지역은 단일 발전소·광산·농업 비중이 커 배수가 높게 나올 수 있다.';
      if (t.yr_diff) tip += ` — ${esc(c.name)}은 ${esc(c.gdp_year)}년, 전국 공식 분모는 ${esc(OG.year)}년 GRDP 기준.`;
    } else if (t.t === 'rk') tip = `${esc(RK_KO[t.k])}: 값이 있는 도시 ${den[t.k] || a.cities.length}곳 중 ${esc(t.r)}위 (10위 이내일 때 표시)`;
    else if (t.k === 'extinction') tip = `소멸위험지수 = 20–39세 여성 ${c.age.women_20_39.toFixed(1)}% ÷ 65세 이상 ${c.age.over65.toFixed(1)}% = ${c.extinction_index.toFixed(3)} (0.2 미만은 소멸 고위험 구간, 주민등록)`;
    else tip = `주민등록 인구 5년(2020→2025) ${t.v > 0 ? '+' : ''}${t.v.toFixed(1)}% (10% 이상일 때 표시)`;
    tip += `<br><span class="dim">${esc(N.tag_rule || '')}</span>`;
    return `<button type="button" class="ctag" data-pop="${P(tip)}" aria-expanded="false" aria-label="${esc(t.txt)} — 산식 보기">${esc(t.txt)}</button>`;
  }).join('')}</div>`;
}

// 닮은 도시 (7b #13): 가까운 두 축과 뚜렷한 차이 하나 (cities[i].peer_reasons, 빌드 계산)
const AX = { pop: '인구', age: '고령 비율', gdp: '1인당 GRDP', ind: '산업 구성' };
function peerWhy(a, c, p, R) {
  if (!R) return '';
  const E = a.nation.econ;
  const same = R.same.map((x) => (x === 'ind' && R.ind ? `${esc(E.industry_ko[R.ind])} 비중(${R.ind_a.toFixed(1)}%·${R.ind_b.toFixed(1)}%)` : x === 'gdp' && R.gdp_years ? `${esc(AX.gdp)}('${String(R.gdp_years[0]).slice(2)}/'${String(R.gdp_years[1]).slice(2)})` : AX[x])).join('·');
  let d = '';
  if (R.diff) {
    const [k, v] = R.diff;
    const hi = k === 'growth' ? v > 0 : v >= 1;
    const ord = hi ? `${esc(c.name)} > ${esc(p.name)}` : `${esc(p.name)} > ${esc(c.name)}`;
    const q = (x) => (x >= 1 ? x : 1 / x).toFixed(1);
    d = k === 'home' ? `아파트 ㎡당 ${q(v)}배 차` : k === 'growth' ? `5년 인구 증감 ${Math.abs(v).toFixed(1)}%p 차` : `1인당 총급여 ${q(v)}배 차`;
    d += ` (${ord})`;
  }
  return `<span class="peer-why">${same} 가까움${d ? ` · ${d}` : ''}</span>`;
}

function frontierOf(a, sgg) {
  if (!a.layerR) return null;
  for (const c of sgg) { const ar = a.layerR.frontierBy.get(c); if (ar) return ar; }
  return null;
}

export class Panel {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('panel');
    this.mode = null;
    this.el.addEventListener('pointerover', (e) => {
      const f = e.target.closest('.fn, [data-pop]');
      if (f && e.pointerType === 'mouse' && !this.notePinned) this.showNote(f, false);
    });
    this.el.addEventListener('pointerout', (e) => {
      const f = e.target.closest('.fn, [data-pop]');
      if (f && e.pointerType === 'mouse' && !this.notePinned) this.closeNote();
    });
    // 키보드로 ⓘ 에 초점이 오면 문장을 보이고, 초점이 떠나면 닫는다 (누르면 고정은 그대로)
    this.el.addEventListener('focusin', (e) => {
      const f = e.target.closest('.fn, [data-pop]');
      if (f && !this.notePinned) this.showNote(f, false);
    });
    this.el.addEventListener('focusout', (e) => {
      const f = e.target.closest('.fn, [data-pop]');
      if (f && !this.notePinned) this.closeNote();
    });
    // 스크롤하면 고정한 말풍선은 ⓘ 를 따라가고, 가리키기만 한 말풍선은 닫힌다
    this.el.addEventListener('scroll', () => { if (this.notePinned && this.noteBtn) this.showNote(this.noteBtn, true); else this.closeNote(); }, { passive: true });
    document.addEventListener('pointerdown', (e) => {
      if (this.notePinned && !e.target.closest('#fnpop') && !e.target.closest('.fn, [data-pop]')) this.closeNote();
    }, true);
    // 탭 바: ←/→ · Home/End 로 탭 이동 (지도 이동 단축키와 겹치지 않게 여기서 멈춘다)
    this.el.addEventListener('keydown', (e) => {
      const t = e.target.closest && e.target.closest('[role="tab"]');
      if (!t) return;
      const tabs = [...this.el.querySelectorAll('[role="tab"]')], k = tabs.indexOf(t);
      let j = null;
      if (e.key === 'ArrowRight') j = (k + 1) % tabs.length;
      else if (e.key === 'ArrowLeft') j = (k - 1 + tabs.length) % tabs.length;
      else if (e.key === 'Home') j = 0;
      else if (e.key === 'End') j = tabs.length - 1;
      if (j == null) return;
      e.preventDefault();
      e.stopPropagation();
      this.setTab(tabs[j].dataset.ptab, true);
    });
    this.el.addEventListener('click', (e) => {
      const tb = e.target.closest('[data-ptab]');
      if (tb) return this.setTab(tb.dataset.ptab, false);
      const rr = e.target.closest('.rk-row[data-rk]');
      if (rr) return this.toggleRank(rr);
      const fb = e.target.closest('.fn, [data-pop]');
      if (fb) {
        e.preventDefault();
        if (this.notePinned && this.noteBtn === fb) this.closeNote();
        else this.showNote(fb, true);
        return;
      }
      const it = e.target.closest('[data-itab]');
      if (it) {
        for (const b of this.el.querySelectorAll('[data-itab]')) b.classList.toggle('on', b === it);
        for (const p of this.el.querySelectorAll('.itab')) p.hidden = p.dataset.pane !== it.dataset.itab;
        return;
      }
      const so = e.target.closest('[data-sort]');
      if (so && this.state) {
        this.el.querySelector('.citylist').innerHTML = this.cityList(this.state, so.dataset.sort);
        for (const b of this.el.querySelectorAll('[data-sort]')) b.classList.toggle('on', b === so);
        return;
      }
      const di = e.target.closest('[data-item]');
      if (di && app.layerR) return app.selectItem(app.layerR.byId.get(di.dataset.item), true);
      const dr = e.target.closest('[data-route]');
      if (dr && app.layerR) return app.selectRoute(app.layerR.routeById.get(dr.dataset.route), true);
      const t = e.target.closest('[data-city],[data-state],[data-close],[data-nation]');
      if (!t) return;
      if (t.dataset.close !== undefined) return app.clearSelection();
      if (t.dataset.nation !== undefined) return app.showNation();
      if (t.dataset.city) return app.selectCity(Number(t.dataset.city), true);
      if (t.dataset.state) return app.selectState(t.dataset.state, true);
    });
  }

  open(html, mode) {
    this.closeNote();
    this.mode = mode;
    this.el.innerHTML = `<button class="close" data-close title="닫기 (Esc)">×</button><div class="grip"></div>${html}`;
    this.footnotes();
    this.el.hidden = false;
    this.el.scrollTop = 0;
    document.body.classList.add('panel-open');
  }

  // 6단계 B4 + 7b #12: 본문의 기준·주의 문장(.note)을 값·제목 옆 ⓘ 로 줄이고, 접힌 '기준과 주의' 한 곳에 모은다 (문장은 지우지 않는다).
  // 도시 패널은 탭(.ptab)마다 맨 아래 하나, 다른 패널은 패널 맨 아래(.foot 위) 하나. 번호는 탭마다 1부터.
  footnotes() {
    const root = this.el;
    const tabs = [...root.querySelectorAll('.ptab')];
    const scopes = tabs.length ? tabs : [root];
    const per = new Map(scopes.map((sc) => [sc, []]));
    for (const el of root.querySelectorAll('.note')) per.get(el.closest('.ptab') || scopes[0]).push(el);
    scopes.forEach((sc, si) => {
      const notes = per.get(sc);
      if (!notes.length) return;
      const list = [];
      notes.forEach((el, j) => {
        const n = j + 1, key = `${si}-${n}`;
        list.push([n, key, el.innerHTML]);
        const mk = document.createElement('button');
        mk.type = 'button';
        mk.className = 'fn';
        mk.textContent = 'ⓘ';
        mk.dataset.fn = key;
        mk.setAttribute('aria-label', `기준과 주의 ${n}`);
        // 값에 딸린 주의(data-for="값 열쇠…"): 그 값(data-k) 바로 옆에 ⓘ. 값이 여럿이면 같은 문장을 가리키는 ⓘ 를 값마다. 값이 화면에 없으면 아래의 제목 자리로
        const targets = (el.dataset.for || '').split(/\s+/).filter(Boolean).map((k) => sc.querySelector(`[data-k="${k}"]`)).filter(Boolean);
        if (targets.length) {
          targets.forEach((t, q) => t.appendChild(q ? mk.cloneNode(true) : mk));
          el.remove();
          return;
        }
        if (el.tagName === 'P' || el.tagName === 'DIV') {
          // 문단: 앞의 제목(h4·묶음 제목) 끝에 ⓘ, 제목이 없으면 그 자리에
          let p = el.previousElementSibling;
          while (p && !(p.matches('h4, .lyh'))) p = p.previousElementSibling;
          const lyg = el.closest('.lyg');
          if (!p && lyg) p = lyg.querySelector('.lyh');
          if (p) p.appendChild(mk); else el.before(mk);
          el.remove();
        } else el.replaceWith(mk);
      });
      const d = document.createElement('details');
      d.className = 'caveats';
      d.innerHTML = `<summary>기준과 주의 <small>${esc(list.length)}건</small></summary><ol>${list.map(([n, k, h]) => `<li value="${n}" data-fnote="${k}">${h}</li>`).join('')}</ol>`;
      const foot = [...sc.children].find((x) => x.classList.contains('foot'));
      if (foot) sc.insertBefore(d, foot); else sc.appendChild(d);
    });
  }

  noteText(btn) {
    if (btn.dataset.pop) return (this.pops && this.pops.map.get(btn.dataset.pop)) || '';
    const li = this.el.querySelector(`[data-fnote="${esc(btn.dataset.fn)}"]`);
    return li ? li.innerHTML : '';
  }

  // ⓘ·산출 칸·특성 표시 말풍선: 가리키면 보이고, 누르면 고정(다시 누르거나 Esc·바깥을 누르면 닫힘)
  showNote(btn, pin) {
    const pop = document.getElementById('fnpop');
    if (this.noteBtn && this.noteBtn !== btn && this.noteBtn.hasAttribute('aria-expanded')) this.noteBtn.setAttribute('aria-expanded', 'false');
    pop.innerHTML = this.noteText(btn);
    pop.hidden = false;
    pop.classList.toggle('pinned', !!pin);
    this.noteBtn = btn;
    this.notePinned = !!pin;
    if (btn.hasAttribute('aria-expanded')) btn.setAttribute('aria-expanded', pin ? 'true' : 'false');
    const r = btn.getBoundingClientRect();
    const w = pop.offsetWidth, h = pop.offsetHeight;
    pop.style.left = `${Math.max(6, Math.min(window.innerWidth - w - 6, r.left + r.width / 2 - w / 2))}px`;
    pop.style.top = `${r.bottom + 6 + h > window.innerHeight ? Math.max(6, r.top - h - 6) : r.bottom + 6}px`;
  }

  closeNote() {
    const pop = document.getElementById('fnpop');
    if (this.noteBtn && this.noteBtn.hasAttribute('aria-expanded')) this.noteBtn.setAttribute('aria-expanded', 'false');
    if (pop.hidden) return false;
    pop.hidden = true;
    this.notePinned = false;
    this.noteBtn = null;
    return true;
  }

  // 도시 패널 탭 (개요·경제·시설·교역·땅·행정). 고른 탭은 다른 도시로 옮겨도 남는다 (app.panelTab, 해시 tab=)
  setTab(id, focus) {
    if (!TAB_IDS.includes(id)) id = 'overview';
    this.app.panelTab = id;
    for (const b of this.el.querySelectorAll('[data-ptab]')) {
      const on = b.dataset.ptab === id;
      b.setAttribute('aria-selected', on ? 'true' : 'false');
      b.tabIndex = on ? 0 : -1;
      b.classList.toggle('on', on);
      if (on && focus) b.focus();
    }
    for (const p of this.el.querySelectorAll('.ptab')) p.hidden = p.id !== `ptab-${id}`;
    this.closeNote();
    const tb = this.el.querySelector('.ptabs');
    if (tb && this.el.scrollTop > tb.offsetTop) this.el.scrollTop = tb.offsetTop;
    this.app.requestDraw();
  }

  // 순위 행: 누르면 바로 위·아래 순위 도시와 도내 1위 (한 번에 한 행만 펼침)
  toggleRank(btn) {
    const box = btn.nextElementSibling, open = btn.getAttribute('aria-expanded') === 'true';
    for (const b of this.el.querySelectorAll('.rk-row[aria-expanded="true"]')) { b.setAttribute('aria-expanded', 'false'); b.nextElementSibling.hidden = true; }
    if (open) return;
    const c = this.app.cityById.get(this.app.selCity);
    if (!c) return;
    box.innerHTML = rankAdj(this.app, c, btn.dataset.rk) || '<span class="dim">인접 순위 도시 없음</span>';
    box.hidden = false;
    btn.setAttribute('aria-expanded', 'true');
  }

  // 패널 제목으로 초점을 옮긴다 (키보드로 보고서 행·검색에서 이동했을 때, 감사 10)
  focus() {
    const h = this.el.querySelector('h2, h3');
    if (!h || this.el.hidden) return;
    h.tabIndex = -1;
    h.focus({ preventScroll: true });
  }

  hide() {
    this.closeNote();
    this.mode = null;
    this.el.hidden = true;
    document.body.classList.remove('panel-open');
  }

  // 도시 패널 (7b #9): 머리(배지·특성 표시·이름·부제) + 인구 한 줄 + 다섯 산출 한 줄 + 탭 4개 (개요·경제·시설·교역·땅·행정)
  showCity(c) {
    const a = this.app, s = a.stateByCode.get(c.sido);
    const P = popReg();
    this.pops = P;
    const fr = frontierOf(a, c.sgg);
    const badges = [c.kind, c.capital !== '없음' ? (c.capital === '수도' ? '★ 수도' : c.capital === '통합청사' ? '◇ 통합특별시 청사' : '◆ 도청 소재지') : null].filter(Boolean);
    const tab = TAB_IDS.includes(a.panelTab) ? a.panelTab : 'overview';
    const nInfra = a.layerR ? a.layerR.itemsFor(new Set(c.sgg), new Set(c.footprint)).length : null;
    const TABS = [['overview', '개요'], ['econ', '경제'], ['infra', `시설·교역${nInfra ? ` <small>${nInfra}</small>` : ''}`], ['land', '땅·행정']];
    const st = c.extinction_stage;
    const extTip = P(`소멸위험지수 = 20–39세 여성 ${pct(c.age.women_20_39)} ÷ 65세 이상 ${pct(c.age.over65)}. 0.5 미만 소멸위험, 0.2 미만 고위험 (주민등록 ${esc(a.nation.vintage)}).`);
    const kv = (lab, val, key, raw) => `<div><em>${lab}</em><b>${val}</b>${refLine(a, c, key, raw)}</div>`;
    const refTitle = (key, raw) => { const t = refLine(a, c, key, raw).replace(/<[^>]+>/g, ''); return t ? ` · ${t}` : ''; };
    const peers = c.peers.map((id, k) => {
      const p = a.cityById.get(id), R = (c.peer_reasons || [])[k];
      return `<button type="button" data-city="${esc(p.id)}" class="peer-go"><span class="pn"><b>${esc(p.name)}</b> <small>${fmtMan(p.population)} · 고령 ${p.age.over65.toFixed(0)}%</small></span>${peerWhy(a, c, p, R && R.id === p.id ? R : null)}</button>`;
    }).join('');
    const pane = (id, html) => `<section class="ptab" role="tabpanel" id="ptab-${id}" aria-labelledby="tab-${id}"${id === tab ? '' : ' hidden'}>${html}</section>`;
    const scopeTxt = c.scope_label || c.scope;
    this.open(`
      <header style="--c:${esc(STATE_COLORS[c.sido])}">
        <div class="badges brow"><span>${badges.join(' · ')}</span>${fr ? `<span class="frontier" title="${esc(a.layers.frontier.rule)}">접경지역(시행령 ${esc(fr.article.replace('시행령 ', ''))})</span>` : ''}${tagsBlock(a, c, P)}</div>
        <h2>${esc(c.name)}</h2>
        <p class="sub">${scopeTxt ? `<span class="scope" title="${esc(c.scope || '')}">${esc(scopeTxt)}</span>` : esc(c.full)} · <a data-state="${esc(c.sido)}">${esc(s.name)}</a></p>
      </header>
      <div class="bignum"><b>${num(c.population)}</b>명 <span class="chg ${c.growth_5y >= 0 ? 'up' : 'down'}">${sgn(c.growth_5y)} <small>5년(2020→2025)</small></span></div>
      ${yieldStrip(c, a, 'city', P)}
      <div class="ptabs" role="tablist" aria-label="도시 정보 분류">${TABS.map(([id, t]) => `<button type="button" role="tab" id="tab-${id}" data-ptab="${id}" aria-controls="ptab-${id}" aria-selected="${id === tab}" tabindex="${id === tab ? 0 : -1}" class="${id === tab ? 'on' : ''}">${t}</button>`).join('')}</div>
      ${pane('overview', `
        <div class="pop-charts"><figure><figcaption>인구 변화 <small>주민등록 12월</small></figcaption>${seriesChart(c.pop_series, true)}</figure><figure><figcaption>인구 피라미드 <small>5세</small></figcaption>${pyramid(c.pyramid, true)}</figure></div>
        <div class="kv kv3">
          <div class="agebar"><em>연령 구성</em><span class="abar" role="img" aria-label="0–14세 ${pct(c.age.under15)}, 15–64세 ${pct(c.age.working)}, 65세 이상 ${pct(c.age.over65)}"><i class="a0" style="width:${esc(c.age.under15 || 0)}%"></i><i class="a1" style="width:${esc(c.age.working || 0)}%"></i><i class="a2" style="width:${esc(c.age.over65 || 0)}%"></i></span>
            <span class="alab"><span title="0–14세${esc(refTitle('under15', c.age.under15))}">${c.age.under15 != null ? c.age.under15.toFixed(1) : '–'}</span><span title="15–64세${esc(refTitle('working', c.age.working))}">${c.age.working != null ? c.age.working.toFixed(1) : '–'}</span><b>65+ ${pct(c.age.over65)}</b></span>${refLine(a, c, 'over65', c.age.over65)}</div>
          ${kv('<span title="평균연령·중위연령 (5세 계급에서 추정)">평균·중위 나이</span>', `${esc(c.age.mean_est ?? '–')}·${esc(c.age.median_est ?? '–')}<small>세</small>`, 'median_est', c.age.median_est)}
          ${kv('<span title="20–39세 여성 100명당 남성">청년 성비</span>', `${esc(c.sex_ratio_20_39 ?? '–')}`, 'sex_ratio_20_39', c.sex_ratio_20_39)}
        </div>
        <div class="ext ext1"><em>소멸위험지수</em><b>${c.extinction_index != null ? c.extinction_index.toFixed(2) : '자료 없음'}</b><button type="button" class="ipop" data-pop="${extTip}" aria-label="소멸위험지수 산식 보기">ⓘ</button>${refLine(a, c, 'extinction_index', c.extinction_index)}
          <span class="stage" style="background:${esc(STAGE_COLOR[st] || '#5a5a5a')};color:${badgeText(STAGE_COLOR[st] || '#5a5a5a')};text-shadow:none">${esc(st || '자료 없음')}</span></div>
        <h4>순위 <small>값이 있는 도시 중 · 오른쪽 끝 = 1위 · 누르면 인접 순위</small></h4>
        <div class="rk-list">${rankRows(a, c)}</div>
        <h4>닮은 도시 <small>${esc(c.peer_rule || '인구 규모·고령 비율')}이 가까운 곳</small>${a.nation.nation.peer_rule ? `<button type="button" class="ipop" data-pop="${P(esc(a.nation.nation.peer_rule))}" aria-label="닮은 도시 고르는 규칙 보기">ⓘ</button>` : ''}</h4><div class="peers">${peers}</div>`)}
      ${pane('econ', econBlock(c, a, 'city', P) + keyIndBlock(a, c.id))}
      ${pane('infra', tradeBlock(a, c, 'city') + layerBlock(a, new Set(c.sgg), new Set(c.footprint), gicLine(a.layers && a.layers.resources.general_complexes.by_city[c.id], '시군구 합계')
        + (a.layers ? powerBlock(a, a.layers.resources.power.by_city[c.id], '시군구 합계') + farmBlock(a, (F) => F.by_city[c.id], null, String(c.id))
          + minesBlock(a, a.layers.resources.mines_5d && a.layers.resources.mines_5d.by_city[c.id], '시군구 합계') : '')))}
      ${pane('land', terrainBlock(a, c.footprint, null, c.land_stats) + retiredBlock(a, c)
        + veteransBlock(c.veterans, c.sgg.length > 1 && (c.kind === '광역시' || c.kind === '특별시') ? 'metro' : 'city') + officeBlock(a, c)
        + `<p class="foot">시군구 ${esc(c.sgg.length)}개 · 칸 ${esc(c.footprint.length)}개 · 깃발 위치: ${esc(c.center_rule)}</p>`)}`, 'city');
    this.pops = P;
  }

  cityList(s, key) {
    const a = this.app;
    const val = (c) => (key === 'population' ? c.population : c.yields ? c.yields[key] : null);
    const cs = s.cities.map((id) => a.cityById.get(id)).sort((x, y) => (val(y) ?? -1) - (val(x) ?? -1));
    return cs.map((c, k) => `<button data-city="${esc(c.id)}"><span class="no">${k + 1}</span>${esc(c.name)}<small>${key === 'population' ? num(c.population) + '명' : val(c) == null ? '자료 없음' : fmtWon(val(c)) + (partialNote(c, key) ? '*' : '')}</small></button>`).join('');
  }

  showState(s) {
    const a = this.app;
    const list = this.cityList(s, 'population');
    const sorters = [['population', '👥 인구'], ...YIELD_ICONS.map(([k, ic]) => [k, `${ic} ${esc(YNAME[k])}`])]
      .map(([k, t]) => `<button data-sort="${k}" class="${k === 'population' ? 'on' : ''}">${t}</button>`).join('');
    this.open(`
      <header style="--c:${esc(STATE_COLORS[s.code])}">
        <div class="badges"><span>시도</span></div>
        <h2>${esc(s.name)}</h2><p class="sub">도시 ${esc(s.cities.length)}곳 · 칸 ${esc(s.cells)}개 · <a data-nation>전국 보고서</a></p>
      </header>
      ${popBlock(s, a.nation.vintage)}
      ${veteransBlock(s.veterans, 'state')}
      ${econBlock(s, a, 'state', this.pops = popReg())}
      ${tradeBlock(a, s, 'state')}
      ${freightBlock(a, s)}
      ${this.stateOffices(s)}
      ${terrainBlock(a, this.stateCells(s), s.code, s.land_stats)}
      ${this.stateLayers(s)}
      <h4>소속 도시 <small>정렬 기준을 고른다</small></h4><div class="sorters">${sorters}</div><div class="citylist">${list}</div>`, 'state');
    this.state = s;
  }

  stateCells(s) {
    const a = this.app, idx = a.world.states.findIndex((x) => x.code === s.code), out = [];
    for (let i = 0; i < a.grid.n; i++) if (a.world.owner[i] === idx) out.push(i);
    return out;
  }

  // 시도청 (원표 표기대로 여럿), 전남광주통합특별시는 특별법의 청사 3곳
  stateOffices(s) {
    const a = this.app;
    const cn = (codes) => (codes || []).map((x) => (a.world.counties.find((k) => k.code === x) || {}).name || x).join('·');
    const link = (id) => (id != null ? ` · <a data-city="${id}">${esc(a.cityById.get(id).name)}</a>` : '');
    if (s.special_offices) {
      return `<h4>청사 <small>${esc(s.special_offices[0].law)}</small></h4><ul class="names offices">${s.special_offices.map((e) => `<li><b>${esc(e.name)}</b> <small>${e.sgg ? esc(cn(e.sgg)) + ' (시군구 대표 위치)' : '지도에 놓지 않음'}${link(e.city)} — ${esc(e.located_by)}</small></li>`).join('')}</ul>
        <p class="note">특별법이 종전 청사 3곳을 균형 있게 활용·운영하도록 정해 수도(주 청사) 별표를 하나로 정하지 않는다.</p>`;
    }
    if (!s.offices || !s.offices.length) return '';
    return `<h4>청사 <small>행정안전부 공표본 (2025-12-31 기준) 주소 → 시군구</small></h4><ul class="names offices">${s.offices.map((o) => `<li><b>${esc(o.name)}</b> <small>${esc(o.role)} · ${esc(o.address)} (${esc(cn(o.sgg))})${link(o.city)}</small></li>`).join('')}</ul>`;
  }

  stateLayers(s) {
    const a = this.app;
    const sgg = new Set(a.world.counties.filter((c) => c.sido === s.code).map((c) => c.code));
    const idx = a.world.states.findIndex((x) => x.code === s.code);
    const cells = new Set();
    for (let i = 0; i < a.grid.n; i++) if (a.world.owner[i] === idx) cells.add(i);
    let extra = '';
    if (a.layers) {
      extra += gicLine(a.layers.resources.general_complexes.by_sido[s.code], '시도 합계');
      const M = a.layers.resources.minerals, m = M.by_sido[s.code];
      extra += `<div class="lyg"><p class="lyh">⛏️ 가행 광산 <small>시도 집계 <span class="note">전국광산 통계(연말 기준)의 시도 집계다. 아래 광종별 수(수집 시점 가행 목록)와 기준 시점이 다르다.</span></small></p><p class="dim sm">${m
        ? `금속 ${esc(m.metal ?? '자료 없음')}곳 (${esc(M.metal_date)}) · 비금속 ${esc(m.nonmetal ?? '자료 없음')}곳 (${esc(M.nonmetal_date)})`
        : '원자료에 이 시도 칸이 없음'} · 한국광해광업공단</p></div>`;
      const R = a.layers.resources;
      extra += powerBlock(a, R.power.by_sido[s.code], '시도 합계');
      extra += farmBlock(a, (F) => (F.by_sido && F.by_sido[s.code] && F.by_sido[s.code].units ? F.by_sido[s.code].sum : undefined), s.code);
      extra += minesBlock(a, R.mines_5d && R.mines_5d.by_sido[s.code], '시도 합계');
      extra += fundingBlock(a, s);
      const gs = R.gi.sido_level.filter((g) => g.sido === s.code);
      if (gs.length) extra += `<div class="lyg"><p class="lyh"><img src="${iconURL('gi')}" alt=""> 시도 전체가 등록지역인 지리적표시 <small>지도에 놓지 않음</small></p><p class="dim sm">${gs.map((g) => `${esc(g.name)} (${esc(g.gi_kind)} ${esc(g.no)})`).join(' · ')}</p></div>`;
    }
    return layerBlock(a, sgg, cells, extra);
  }

  // 층 항목 패널: 이름, 종류, 값과 단위, 기준 연도, 위치 정밀도, 출처, 같은 칸의 다른 항목
  showItem(it) {
    if (it.group) return this.showGroup(it);
    const a = this.app, L = a.layerR, K = KINDS[it.kind];
    const rule = L.rule(it.kind) || {};
    const v = itemValue(it);
    const src = (rule.source || []).map((x) => `${esc(x.publisher || '')} · ${esc(x.title || x.key)}${x.retrieved ? ` (수집 ${esc(x.retrieved)})` : ''}`).join('<br>');
    const others = it.cell != null ? (L.byCell.get(it.cell) || []).filter((x) => x !== it) : [];
    let body = '';
    if (it.kind === 'heritage_cluster' && it.list) {
      body += `<h4>이 칸의 국보·사적 <small>${esc(it.list.length)}건</small></h4><ul class="names">${it.list.map(([k, n]) => `<li><span class="tag ${k === '국보' ? 'nt' : 'hs'}">${esc(k)}</span>${esc(n)}</li>`).join('')}</ul>`;
    }
    if (it.kind === 'national_park') {
      const p = a.layers.wonders.parks.find((x) => x.id === it.ref);
      if (p) body += `<h4>공원이 덮는 곳</h4><p class="dim">육지 칸 ${esc(p.cells.length)}개 (경계 파일 '공원경계버퍼'의 표본점 과반 칸 — 넓이로 쓰지 않음) · ${p.marine ? '해상·해안 공원 (폴리곤의 대부분이 바다)' : '내륙 공원'}<br>걸친 시군구: ${p.spans.map((c) => esc(a.world.counties.find((x) => x.code === c).name)).join(', ')}</p>`;
    }
    if (it.kind === 'world_heritage') {
      const e = a.layers.wonders.world_heritage.find((x) => x.id === it.ref);
      if (e) {
        const PK = { point: '● ' + PREC_KO.point, county: '◐ ' + PREC_KO.county };
        const cnt = e.counts || {};
        body += `<h4>구성 유산 ${esc(e.components.length)}건 <small>${esc(PREC_KO.point)} ${esc(cnt.point || 0)} · ${esc(PREC_KO.county)} ${esc(cnt.county || 0)} · 목록만 ${esc(cnt.list || 0)}</small></h4><ul class="names wh">${e.components.map((c) => `<li class="${c.cell === it.cell ? 'here' : ''}"><span class="tag ${c.precision ? 'hs' : ''}">${c.precision ? PK[c.precision] : '○ 목록만'}</span>${esc(c.name)} <small>${esc(c.matched || '')}</small></li>`).join('')}</ul>
          <p class="note">● 이름이 같은 국가유산의 좌표 · ◐ 소재지 문자열의 시군구 (인구 가중 중심 칸) · ○ 소재지가 시도까지만이거나 이름이 여러 곳이라 지도에 놓지 않음. 굵게 = 이 아이콘에 든 구성 유산.</p>`;
        if (e.visitor_series) body += `<h4>관람객 <small>국가유산청 세계유산 관람객 현황</small></h4><p class="dim">${Object.entries(e.visitor_series).map(([y, n]) => `${y}: ${n == null ? '자료 없음' : n.toLocaleString('ko-KR') + '명'}`).join(' · ')}</p>`;
      }
    }
    if (it.kind === 'nuclear' && it.operating) {
      const u = (lst) => lst.map((x) => `${esc(x.name)} ${esc(x.mw ?? '?')} MW`).join(', ') || '없음';
      body += `<h4>호기</h4><p class="dim">가동 ${esc(it.units_operating)}기: ${u(it.operating)}<br>영구정지 ${esc(it.stopped.length)}기: ${u(it.stopped)}<br>건설 중 ${esc(it.construction.length)}기: ${u(it.construction)}</p>`;
    }
    if (it.kind === 'nuclear' && it.nssc && a.layers.resources.nuclear_nssc) {
      const n = a.layers.resources.nuclear_nssc.find((x) => x.site === it.nssc);
      if (n) {
        const u = (lst) => lst.map((x) => `${esc(x.name)} ${esc(x.mw ?? '?')} MW`).join(', ') || '없음';
        body += `<h4>원자력안전위원회 본부 '${esc(n.site)}' <small>${it.nssc_match ? '용량 일치' : '용량 다름'}</small></h4><p class="dim">가동 ${esc(n.units_operating)}기: ${u(n.operating)}<br>영구정지 ${esc(n.stopped.length)}기: ${u(n.stopped)}<br>건설 중 ${esc(n.construction.length)}기: ${u(n.construction)}</p>`;
      }
    }
    if (it.kind === 'airport' && it.cargo_t != null) body += `<p class="dim">2025년 화물 ${it.cargo_t.toLocaleString('ko-KR')}톤</p>`;
    if (it.kind === 'trade_port' && it.teu != null) body += `<p class="dim">컨테이너 ${it.teu.toLocaleString('ko-KR')} TEU (${esc(it.teu_note)})</p>`;
    if (it.place_from) body += `<p class="dim">위치를 정한 근거: ${esc(PLACE_FROM[it.place_from])}</p>`;
    const city = it.city != null ? a.cityById.get(it.city) : null;
    this.open(`
      <header style="--c:${esc(K.color)}">
        <div class="badges"><span><img class="bi" src="${iconURL(it.kind, !!it.hsr)}" alt=""> ${esc(K.label)}${it.kind === 'station' && it.hsr ? ' · 고속철도 정차' : ''}</span></div>
        <h2>${esc(it.name)}</h2>
        <p class="sub">${it.place ? esc(it.place) : '위치 없음'}${city ? ` · <a data-city="${esc(city.id)}">${esc(city.name)} 패널</a>` : ''}</p>
      </header>
      <div class="kv econ">
        <div><em>값</em><b>${v ? esc(v) : '<span class="na">값 없음</span>'}</b></div>
        <div><em>기준</em><b>${esc(it.year ?? rule.year ?? '–')}</b></div>
        <div><em>위치 정밀도</em><b class="sm2">${esc(precisionText(it))}</b></div>
        <div><em>지도 칸</em><b class="sm2">${it.cell != null ? it.cell : '–'}</b></div>
      </div>
      ${it.kind === 'knowledge' && it.precision === 'county' ? `<p class="warn">지도 아이콘은 ${esc(it.place || '')}의 중심 칸에 있다. 캠퍼스·기관의 실제 자리가 아니다 — 좌표가 없어 주소의 자치구·시군구까지만 읽어 그 인구 가중 중심 칸에 놓았다.</p>` : ''}
      ${it.reason ? `<p class="warn">${esc(it.reason)}</p>` : ''}
      ${(it.detail || []).length ? `<ul class="names">${it.detail.map((d) => `<li>${esc(d)}</li>`).join('')}</ul>` : ''}
      ${body}
      ${others.length ? `<h4>같은 칸의 다른 항목 <small>${esc(others.length)}</small></h4><div class="lyl">${others.map((o) => `<button data-item="${esc(o.id)}"><img src="${iconURL(o.kind, !!o.hsr)}" alt=""> ${esc(o.name)} <small>${esc(KINDS[o.kind].label)}</small></button>`).join('')}</div>` : ''}
      <h4>선정 규칙</h4><p class="dim">${esc(rule.rule || '')}</p>
      <h4>출처</h4><p class="dim">${src}</p>`, 'item');
  }

  // 대학 묶음 패널: 묶인 대학과 연구비 (누르면 그 대학 패널)
  showGroup(g) {
    const a = this.app, Z = a.layerR.zoom, K = KINDS.knowledge;
    const ms = (g.memberItems || []).slice().sort((x, y) => (y.funding_won || 0) - (x.funding_won || 0));
    const eok = (v) => (v == null ? '<span class="na">자료 없음</span>' : Math.round(v / 1e8).toLocaleString('ko-KR') + '억원');
    const city = g.city != null ? a.cityById.get(g.city) : null;
    const vt = g.view_tiers.map((t) => (Z.levels.find((l) => l.tier === t) || {}).name).filter(Boolean).join('·');
    this.open(`
      <header style="--c:${esc(K.color)}">
        <div class="badges"><span><img class="bi" src="${iconURL('knowledge')}" alt=""> 대학 묶음 · ${esc(vt)} 배율</span></div>
        <h2>${esc(g.name)}</h2>
        <p class="sub">${city ? `<a data-city="${esc(city.id)}">${esc(city.name)} 패널</a> · ` : ''}같은 칸·이웃 칸에 놓인 대학</p>
      </header>
      <p class="warn">대학 아이콘은 캠퍼스 자리가 아니라 주소의 자치구·시군구 중심 칸에 있다(좌표 없음). 가까운 구의 대학이 겹쳐 보이지 않게 한 표지로 묶었다.</p>
      <h4>묶인 대학 <small>${esc(ms.length)}곳 · 연구비 대학알리미 ${esc(g.funding_year || '')} · 합 ${eok(g.funding_won_sum)}</small></h4>
      <table class="tbl"><thead><tr><th>순위</th><th>대학</th><th>자치구·시군구</th><th class="num">연구비</th></tr></thead><tbody>${ms.map((m) => `<tr data-item="${esc(m.id)}" style="cursor:pointer"><td>${esc(m.funding_rank ?? '–')}</td><td>${esc(m.name)}</td><td>${esc(String(m.place || '').split(' ').pop())}</td><td class="num">${eok(m.funding_won)}</td></tr>`).join('')}</tbody></table>
      <div class="kv econ">
        <div><em>위치 정밀도</em><b class="sm2">${esc(precisionText(g))}</b></div>
        <div><em>표지 칸</em><b class="sm2">${esc(g.cell)} <small>연구비가 가장 큰 대학의 칸</small></b></div>
      </div>
      <h4>묶는 규칙</h4><p class="dim">${esc((Z.knowledge_groups || {}).rule || '')}</p>`, 'item');
  }

  // 교역로 구간 패널
  showRoute(rt) {
    const a = this.app, A = a.stateByCode.get(rt.a), B = a.stateByCode.get(rt.b), R = a.layers.trade.routes;
    const t = (v) => v.toLocaleString('ko-KR') + '톤';
    const anc = (c) => R.anchors[c];
    this.open(`
      <header style="--c:#e0a94e"><div class="badges"><span><i class="trk"></i> 교역로 · 도로 화물 ${esc(R.year)}</span></div>
        <h2>${esc(A.short)} – ${esc(B.short)}</h2><p class="sub"><a data-state="${esc(A.code)}">${esc(A.name)}</a> · <a data-state="${esc(B.code)}">${esc(B.name)}</a></p></header>
      <div class="kv econ">
        <div><em>두 방향 합 <small>톤/년</small></em><b>${t(rt.total)}</b><small>시도 간 ${esc(R.pairs_total)}쌍 중 ${esc(rt.rank)}위</small></div>
        <div><em>시도 간 도로 화물 중</em><b>${esc(rt.share)}%</b><small>전체 ${t(R.totals.inter_t)}</small></div>
        <div><em>${esc(A.short)} → ${esc(B.short)}</em><b>${t(rt.ab)}</b></div>
        <div><em>${esc(B.short)} → ${esc(A.short)}</em><b>${t(rt.ba)}</b></div>
      </div>
      <h4>선의 끝점 <small>청사 소재 칸 (시군구 대표 위치)</small></h4><ul class="names">${[rt.a, rt.b].map((c) => `<li>${esc(anc(c).office)} <small>${esc(anc(c).rule)}</small></li>`).join('')}</ul>
      <h4>규칙</h4><p class="dim">${esc(R.rule)}</p>
      <h4>출처</h4><p class="dim">${R.source.map((x) => `${esc(x.publisher)} · ${esc(x.title)} (수집 ${esc(x.retrieved)}${x.license ? ', 이용허락 ' + esc(x.license) : ''})`).join('<br>')}</p>`, 'route');
  }

  // 전국 보고서: 공식 전국값 / 시군구 합 / 차이
  compareTable(n) {
    const C = n.official_compare;
    if (!C) return '';
    const E = this.app.nation.econ;
    const row = (name, o, s, k) => `<tr><th>${name}</th><td class="num">${o == null ? '–' : fmtWon(o)}</td><td class="num"${k ? ` data-k="${k}"` : ''}>${s == null ? '<span class="na">자료 없음</span>' : fmtWon(s)}</td><td class="num">${o == null || s == null ? '–' : (o - s >= 0 ? '+' : '') + fmtWon(o - s)} <small>${o == null || s == null ? '' : (((o / s) - 1) * 100).toFixed(1) + '%'}</small></td></tr>`;
    const yl = YIELD_ICONS.map(([k, ic]) => row(`${ic} ${esc(YNAME[k])}`, C.yields[k].official, C.yields[k].sgg_sum, `cmp-${k}`)).join('');
    const jb = Object.keys(E.ksic_ko).filter((L) => C.jobs[L].sgg_sum == null).map((L) => `${L} ${esc(E.ksic_ko[L])} ${C.jobs[L].official.toLocaleString('ko-KR')}명`).join(', ');
    return `<h4>공식 전국값 / 시군구 합 / 차이 <small>지역소득 ${esc(C.year)} · 시군구 합 ${esc(C.sgg_sum_label)}</small></h4>
      <table class="tbl cmp"><thead><tr><th></th><th class="num">공식 전국값</th><th class="num">시군구 합</th><th class="num">차이</th></tr></thead><tbody>
      ${row('💰 GRDP', C.grdp.official, C.grdp.sgg_sum)}${yl}</tbody></table>
      <p class="note" data-for="cmp-production">시군구 합의 생산은 광업이 비공개인 공표 단위의 광업 몫이 빠진 부분 합계다. 시도 공식 GRDP 17행 합 ÷ 전국 행 = ${esc(C.sido_sum_check.ratio)}.${jb ? ` 종사자: 시군구 합에서 비공개였던 ${jb}(공식 전국사업체조사 2024).` : ''}</p>`;
  }

  showNation() {
    const a = this.app, n = a.nation.nation;
    const states = a.states.slice().sort((x, y) => y.population - x.population);
    const rows = states.map((s) => `<tr data-state="${esc(s.code)}"><td><i style="background:${esc(STATE_COLORS[s.code])}"></i>${esc(s.name)}</td><td>${fmtMan(s.population)}</td><td class="${s.growth_5y >= 0 ? 'up' : 'down'}">${sgn(s.growth_5y)}</td><td>${pct(s.age.over65)}</td><td>${s.extinction_index.toFixed(2)}</td></tr>`).join('');
    const risk = a.cities.filter((c) => c.extinction_index != null && c.extinction_index < 0.2).length;
    const riskAll = a.cities.filter((c) => c.extinction_index != null && c.extinction_index < 0.5).length;
    this.open(`
      <header style="--c:#d8b25a"><div class="badges"><span>전국 보고서</span></div><h2>대한민국</h2>
        <p class="sub">시도 ${esc(n.states)} · 시군구 ${esc(n.sgg)} · 도시 ${esc(n.cities)} · 기준 ${esc(a.nation.vintage)}</p></header>
      ${popBlock(n, a.nation.vintage)}
      <p class="dim">도시 ${esc(n.cities)}곳 중 소멸위험(0.5 미만) ${riskAll}곳, 그중 고위험(0.2 미만) ${risk}곳.</p>
      <h4>시도 <small>누르면 이동</small></h4>
      <table class="tbl"><thead><tr><th>시도</th><th>인구</th><th>5년</th><th>고령</th><th>소멸</th></tr></thead><tbody>${rows}</tbody></table>
      ${econBlock(n, a, 'nation', this.pops = popReg())}
      ${this.compareTable(n)}
      ${tradeBlock(a, n, 'nation')}
      ${landStatsBlock(a, n.land_stats)}
      <h4>시도별 경제 순위 <small>공식 GRDP 순 · 누르면 이동</small></h4>
      <table class="tbl"><thead><tr><th>시도</th><th>공식 GRDP</th><th>시군구 합</th><th>1인당 (공식)</th><th>생산 (공식)</th><th>과학 (공식)</th></tr></thead><tbody>${
        a.states.filter((x) => x.official && x.official.gdp).sort((x, y) => y.official.gdp.grdp - x.official.gdp.grdp).map((x, k) => { const G = x.official.gdp; return `<tr data-state="${esc(x.code)}"><td><i style="background:${esc(STATE_COLORS[x.code])}"></i>${k + 1}. ${esc(x.short)}${G.combined ? '<sup title="광주 + 전남 합">합</sup>' : ''}</td><td>${fmtWon(G.grdp)}</td><td class="dim">${x.gdp == null ? '–' : fmtWon(x.gdp) + (x.gdp_year !== G.year ? ` (${esc(x.gdp_year)})` : '')}</td><td>${G.per_capita == null ? '–' : fmtWon(G.per_capita)}</td><td>${fmtWon(G.yields.production)}</td><td>${fmtWon(G.yields.science)}</td></tr>`; }).join('')
      }</tbody></table>
      <p class="note" data-for="y-production">공식값은 지역소득 ${esc(a.nation.nation.official.gdp.year)} (광업 포함, 부분 합계 없음). 시군구 합의 * 생산 부분 합계: 제조업 + 건설업 + 공개된 광업의 합이며, 광업이 비공개인 공표 단위의 광업 몫만 뺐다 (전국 ${esc(n.production_mining_excluded || 0)}곳 제외, 시도 ${a.states.filter((x) => partialNote(x, 'production')).length}곳·도시 ${a.cities.filter((x) => partialNote(x, 'production')).length}곳). 도시 순위는 시군구 합 값으로 매긴다.</p>
      <p class="note">${esc(a.nation.econ.national_note)}</p><p class="note">${esc(a.nation.econ.combined_note || '')}</p>`, 'nation');
  }
}
