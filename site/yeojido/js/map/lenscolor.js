// 렌즈 빛깔 — 자료의 색 대신 안료 띠를 쓴다. 척도 규칙과 정의역은 자료 그대로(adapter 의 lensT).
// 띠는 종이색에서 시작해 명도가 한쪽으로만 내려가므로, 먹판 위에 곱해 찍어도 결과가 단조롭게 짙어진다.

import { lensT, lensSteps, lensIsContinuous } from '../adapter.js';

const hex = (h) => { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const R = (...a) => a.map(hex);
const RAMPS = {
  ju: R('#FAF4E6', '#F3D8BA', '#E8AE82', '#D87D52', '#BE4D32', '#942F22'),
  jjok: R('#F7F3E7', '#D6E2DF', '#A1C1C6', '#6A99AC', '#3E708A', '#264B66'),
  nok: R('#F7F3E5', '#DCE4C3', '#B4CB9B', '#83AC7F', '#558768', '#33614D'),
  hwang: R('#FAF4E4', '#F1DEAC', '#E3C070', '#CC993B', '#A67324', '#7C511A'),
  div: R('#9A3424', '#D67A52', '#ECC39E', '#F9F4E6', '#BDD6D3', '#6A99AC', '#264B66'),
  divg: R('#9A3424', '#D67A52', '#ECC39E', '#F9F4E6', '#C6DEC2', '#7BA87A', '#33614D'),
  heritage: R('#F7F2E4', '#EFE0AE', '#E1BC6A', '#CE8E3E', '#B35D2E', '#8C3522'),
};
// 렌즈 id -> 띠. 여기 없는 새 렌즈는 묶음의 띠를 쓴다.
const BY_ID = {
  density: 'ju', over65: 'ju', veterans: 'ju', home: 'ju', assistance: 'ju', long_commute: 'ju', pm25: 'ju', built: 'ju', disaster: 'ju',
  foreign: 'jjok', fiscal: 'jjok', export_pc: 'jjok', single: 'jjok', doctors: 'jjok', degree: 'jjok', religion: 'jjok',
  fertility: 'nok', employment: 'nok', owner: 'nok', forest: 'nok', paddy_share: 'nok',
  gdp_pc: 'hwang', wage: 'hwang', jeonse: 'hwang', manufacturing_share: 'hwang', academies: 'hwang', cropland: 'hwang',
  growth: 'div', health: 'divg', heritage: 'heritage',
};
const BY_GROUP = { people: 'ju', living: 'hwang', industry: 'hwang', daily: 'jjok', learn: 'jjok', land: 'nok' };
const EXTINCTION = R('#CE6549', '#E9AC8A', '#F5E9CE', '#B3CEAA', '#538669');
// 범주 빛깔: 이름으로 찾는다 (번호가 바뀌어도 같은 빛)
const CAT = [
  ['제조', '#C86446'], ['공공', '#8D9AA3'], ['도소매', '#D8A648'], ['농림', '#78A372'], ['부동산', '#9B749C'], ['보건', '#D4929E'], ['전기', '#E4C86A'], ['운수', '#4C7D9B'],
  ['사업', '#5D9A94'], ['정보', '#3A5F85'], ['교육', '#7894B5'], ['건설', '#B58E6D'], ['금융', '#6E5882'], ['문화', '#B4BC7A'], ['광업', '#A39A8E'], ['숙박', '#E09670'],
  ['개신교', '#4A7C9B'], ['천주교', '#8FB3C4'], ['불교', '#D8A444'], ['원불교', '#B9C27A'], ['유교', '#9B749C'], ['천도교', '#C86446'], ['대순', '#78A372'], ['대종교', '#B58E6D'], ['기타', '#A39A8E'],
];
const CAT_SPARE = R('#C86446', '#4C7D9B', '#D8A648', '#78A372', '#9B749C', '#5D9A94', '#D4929E', '#3A5F85', '#B58E6D', '#B4BC7A', '#6E5882', '#E09670', '#8D9AA3', '#E4C86A', '#7894B5', '#A39A8E');

function rampAt(r, t) {
  t = Math.min(1, Math.max(0, t));
  const f = t * (r.length - 1), k = Math.min(r.length - 2, Math.floor(f)), u = f - k, a = r[k], b = r[k + 1];
  return [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u];
}

export class LensColor {
  constructor(lens) {
    this.lens = lens;
    const name = BY_ID[lens.id] || (lens.scale === 'diverging' ? (lens.higherIs === 'good' ? 'divg' : 'div') : BY_GROUP[lens.group] || 'ju');
    this.rampName = name;
    this.ramp = RAMPS[name];
    this.steps = lensSteps(lens);
    if (lens.scale === 'bins') {
      this.stepColors = lens.id === 'extinction' && this.steps === EXTINCTION.length ? EXTINCTION
        : Array.from({ length: this.steps }, (_, k) => rampAt(this.ramp, this.steps > 1 ? k / (this.steps - 1) : 0));
    } else if (lens.scale === 'category') {
      let spare = 0;
      this.stepColors = lens.categories.map((nm) => { const m = CAT.find(([key]) => String(nm).includes(key)); return m ? hex(m[1]) : CAT_SPARE[spare++ % CAT_SPARE.length]; });
    }
  }
  // 값 -> [r,g,b] | null(자료 없음)
  rgb(v) {
    const t = lensT(this.lens, v);
    if (t == null) return null;
    if (this.stepColors) return this.stepColors[Math.min(this.stepColors.length - 1, Math.max(0, t))] || null;
    return rampAt(this.ramp, t);
  }
  // 0..1 자리 -> 빛깔 (연속 척도의 색띠)
  at(t) { return rampAt(this.ramp, t); }
  // 단계 k 의 빛깔 (구간·범주)
  step(k) { return this.stepColors ? this.stepColors[k] : null; }
  get continuous() { return lensIsContinuous(this.lens); }
}
export const rgbCss = (c) => `rgb(${c[0] | 0},${c[1] | 0},${c[2] | 0})`;
// 먹판(호분) 위에 곱해 찍힌 뒤의 빛 (범례 견본용): 0.82 로 곱하기
export function printed(c, base = [251, 246, 232], a = 0.82) {
  return [0, 1, 2].map((k) => base[k] * (1 - a) + (base[k] * c[k] / 255) * a);
}
