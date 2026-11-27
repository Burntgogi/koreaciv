// 렌즈 색칠: 값 -> 색. 척도: log, linear, diverging(중심값), bins(구간), category(범주 번호).

// 시군구 단위 렌즈(by_county)와 육지 칸 값만 실은 렌즈(land_values, world.cover_share.land_cells 순서)는
// 칸 배열로 펼친다. 한 번만 계산해 lens.values 에 붙인다.
export function ensureValues(lens, world) {
  if (lens.values) return lens.values;
  const n = world.owner.length;
  if (lens.land_values) {
    const v = new Array(n).fill(null), lc = world.cover_share.land_cells;
    for (let t = 0; t < lc.length; t++) v[lc[t]] = lens.land_values[t];
    lens.values = v;
    return v;
  }
  if (!lens.by_county) return lens.values;
  const v = new Array(n).fill(null);
  for (let i = 0; i < n; i++) if (world.owner[i] >= 0) v[i] = lens.by_county[world.county[i]];
  lens.values = v;
  return v;
}

// 시군구 값이 더 큰 공표 단위(시 전체·개편 전 구)의 값이면 그 단위 기록 (빌드가 lens.units 에 적음, 감사 01). 없으면 null
export function unitOf(lens, k) {
  if (!lens || !lens.units || k == null || k < 0) return null;
  if (!lens._unitBy) {
    lens._unitBy = new Map();
    for (const u of lens.units) for (const c of u.counties) lens._unitBy.set(c, u);
  }
  return lens._unitBy.get(k) || null;
}

function hexToRgb(h) {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rampAt(rgbs, t) {
  t = Math.min(1, Math.max(0, t));
  const f = t * (rgbs.length - 1);
  const k = Math.min(rgbs.length - 2, Math.floor(f));
  const u = f - k;
  const a = rgbs[k], b = rgbs[k + 1];
  return [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u];
}

export class LensScale {
  constructor(lens) {
    this.lens = lens;
    this.rgbs = lens.ramp.map(hexToRgb);
    const [lo, hi] = lens.domain;
    this.lo = lo;
    this.hi = hi;
  }

  // 값 -> 0..1 (bins 는 구간 번호)
  t(v) {
    const L = this.lens;
    if (v === null || v === undefined) return null;
    if (L.scale === 'log') {
      const a = Math.log10(Math.max(this.lo, 0.1)), b = Math.log10(this.hi);
      return (Math.log10(Math.max(v, 0.1)) - a) / (b - a);
    }
    if (L.scale === 'diverging') {
      const c = L.center;
      if (v >= c) return 0.5 + 0.5 * Math.min(1, (v - c) / (this.hi - c));
      return 0.5 - 0.5 * Math.min(1, (c - v) / (c - this.lo));
    }
    if (L.scale === 'category') return v;
    if (L.scale === 'bins') {
      let k = 0;
      while (k < L.breaks.length && v >= L.breaks[k]) k++;
      return k / L.breaks.length;
    }
    return (v - this.lo) / (this.hi - this.lo);
  }

  rgb(v) {
    const t = this.t(v);
    if (t === null) return null;
    if (this.lens.scale === 'category') return this.rgbs[v] || [150, 150, 150];
    if (this.lens.scale === 'bins') {
      const k = Math.round(t * this.lens.breaks.length);
      return this.rgbs[Math.min(this.rgbs.length - 1, k)];
    }
    return rampAt(this.rgbs, t);
  }

  css(v) {
    const c = this.rgb(v);
    return c ? `rgb(${c[0] | 0},${c[1] | 0},${c[2] | 0})` : null;
  }

  // 범례 단계: [{color, label}]
  legend(fmt) {
    const L = this.lens;
    if (L.scale === 'bins') return L.ramp.map((c, k) => ({ color: c, label: L.bin_labels[k] }));
    if (L.scale === 'category') {
      // 지도에 실제로 나온 범주만
      const seen = new Set((L.values || L.by_county || []).filter((x) => x !== null));
      return L.categories.map((name, k) => ({ color: L.ramp[k], label: name, k })).filter((x) => seen.has(x.k));
    }
    const n = 6, out = [];
    for (let k = 0; k < n; k++) {
      const t = k / (n - 1);
      let v;
      if (L.scale === 'log') {
        const a = Math.log10(Math.max(this.lo, 0.1)), b = Math.log10(this.hi);
        v = Math.pow(10, a + (b - a) * t);
      } else if (L.scale === 'diverging') {
        v = t < 0.5 ? L.center - (L.center - this.lo) * (1 - 2 * t) : L.center + (this.hi - L.center) * (2 * t - 1);
      } else v = this.lo + (this.hi - this.lo) * t;
      out.push({ color: this.css(v), label: fmt(v, L) });
    }
    return out;
  }
}

// 값과 단위를 한 번만 잇는다 (감사 20): 백분율 형식은 formatValue 가 이미 '%' 를 붙이므로 다시 붙이지 않고, 자료 없음에는 단위를 붙이지 않는다
export function valueWithUnit(v, lens) {
  const t = formatValue(v, lens);
  if (v === null || v === undefined || !lens.unit || lens.format === 'cat' || t.endsWith(lens.unit)) return t;
  return `${t} ${lens.unit}`;
}

export function formatValue(v, lens) {
  if (v === null || v === undefined) return '자료 없음';
  switch (lens.format) {
    case 'int':
      return Math.round(v).toLocaleString('ko-KR');
    case 'pct1':
      return (lens.scale === 'diverging' && v > 0 ? '+' : '') + v.toFixed(1) + '%';
    case 'f2':
      return v.toFixed(2);
    case 'pct2':
      return v.toFixed(2) + '%';
    case 'cat':
      return lens.categories[v] ?? '자료 없음';
    default:
      return v.toFixed(1);
  }
}
