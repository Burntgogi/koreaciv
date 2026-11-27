// 숫자 적기 — 값과 단위는 여기서 한 번만 잇는다. 값이 없으면 언제나 '자료 없음' (0 으로 적지 않는다).

export const NA = '자료 없음';
const comma = (n) => n.toLocaleString('ko-KR');
const minus = (s) => String(s).replace(/^-/, '−');
export const isNum = (v) => typeof v === 'number' && Number.isFinite(v);

export function fmtInt(v) { return isNum(v) ? minus(comma(Math.round(v))) : NA; }
export function fmtFixed(v, d = 1) { return isNum(v) ? minus(v.toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d })) : NA; }

// 사람 수: [숫자, 단위] 5,108 만 / 86.8 만 / 9,279 명
export function manParts(p) {
  if (!isNum(p)) return null;
  if (p >= 1e6) return [comma(Math.round(p / 1e4)), '만'];
  if (p >= 1e4) return [(p / 1e4).toFixed(1), '만'];
  return [comma(p), ''];
}
export function fmtMan(p) { const a = manParts(p); return a ? a[0] + a[1] : NA; }

// 금액(원): [숫자, 단위]
export function wonParts(v) {
  if (!isNum(v)) return null;
  const a = Math.abs(v);
  if (a >= 1e12) return [minus(comma(+(v / 1e12).toFixed(a >= 1e14 ? 0 : 1))), '조'];
  if (a >= 1e10) return [minus(comma(Math.round(v / 1e8))), '억'];
  if (a >= 1e8) return [minus((v / 1e8).toFixed(1)), '억'];
  if (a >= 1e4) return [minus(comma(Math.round(v / 1e4))), '만'];
  return [minus(comma(Math.round(v))), ''];
}
export function fmtWon(v, suffix = '원') { const p = wonParts(v); return p ? p[0] + p[1] + suffix : NA; }

// 달러
export function usdParts(v) {
  if (!isNum(v)) return null;
  const a = Math.abs(v);
  if (a >= 1e8) return [minus(comma(+(v / 1e8).toFixed(a >= 1e11 ? 0 : 1))), '억 달러'];
  if (a >= 1e4) return [minus(comma(Math.round(v / 1e4))), '만 달러'];
  return [minus(comma(Math.round(v))), '달러'];
}
export function fmtUsd(v) { const p = usdParts(v); return p ? p[0] + p[1] : NA; }

export function fmtPct(v, d = 1, sign = false) {
  if (!isNum(v)) return NA;
  return (v < 0 ? '−' : sign && v > 0 ? '+' : '') + Math.abs(v).toFixed(d) + '%';
}
export function fmtSigned(v, d = 2) {
  if (!isNum(v)) return NA;
  return (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d);
}
// '2026-09' -> '2026년 9월', '2023' -> '2023년'
export function fmtWhen(k) {
  if (k == null || k === '') return '';
  const [y, m] = String(k).split('-');
  return m ? `${y}년 ${+m}월` : `${y}년`;
}

// 렌즈 값 (단위 없이)
export function lensValueText(v, lens) {
  if (v == null || !isNum(v)) return NA;
  switch (lens.format) {
    case 'int': return minus(comma(Math.round(v)));
    case 'pct1': return (v < 0 ? '−' : lens.scale === 'diverging' && v > 0 ? '+' : '') + Math.abs(v).toFixed(1) + '%';
    case 'pct2': return minus(v.toFixed(2)) + '%';
    case 'f2': return minus(v.toFixed(2));
    case 'cat': return lens.categories[v] ?? NA;
    default: return minus(v.toFixed(1));
  }
}
// 렌즈 값 + 단위 (단위는 한 번만. 자료 없음에는 붙이지 않는다)
export function lensValueUnit(v, lens) {
  const t = lensValueText(v, lens);
  if (v == null || !lens.unit || lens.format === 'cat' || t.endsWith(lens.unit)) return t;
  return `${t} ${lens.unit}`;
}
