// 자료 어댑터 (지도 층) — 층 항목의 덧붙은 값, 배율 규칙, 대학 묶음, 위치 없는 항목.
// map/layers.js 가 그리는 데 쓰는 모양은 여기서만 읽는다.

const rawOf = (it) => it.raw || {};
export const itemExtra = (it) => { // 항목의 덧붙은 값들
  const r = rawOf(it);
  return { hsr: !!r.hsr, valueLabel: r.value_label || null, component: r.component || null, cargoT: r.cargo_t ?? null, teu: r.teu ?? null, teuNote: r.teu_note || '',
    fundingWon: r.funding_won ?? null, grouped: r.grouped || null, sgg: (r.sgg || []).map(String), placeFrom: r.place_from || '' };
};
export function zoomRules(L) {
  const z = L.zoom || {};
  const levels = Array.isArray(z.levels) && z.levels.length ? z.levels.map((l) => ({ tier: l.tier, zMin: l.z_min, name: l.name || '' })) : [{ tier: 0, zMin: 0 }, { tier: 1, zMin: 2 }, { tier: 2, zMin: 3.2 }];
  const first = new Set((z.draw_priority && z.draw_priority.first) || ['nuclear']);
  const groups = ((z.knowledge_groups && z.knowledge_groups.groups) || []).map((g) => ({
    id: g.id, kind: g.kind || 'knowledge', name: g.name, cell: g.cell ?? -1, tier: g.tier ?? 1, value: g.funding_won_sum ?? null, unit: '원', year: g.funding_year || '',
    sido: g.sido != null ? String(g.sido) : '', city: g.city ?? null, place: g.place || '', precision: g.precision || '', ref: null, detail: [], file: 'wonders',
    group: true, viewTiers: g.view_tiers || [], members: g.members || [], raw: g,
  }));
  return { levels, first, groups, rules: z.rules || [] };
}
export function unplacedItems(L) { // 위치가 없는 항목 (댐 몇 곳): 지도에는 없지만 id 로는 찾을 수 있게
  const out = [];
  for (const f of ['resources', 'infrastructure', 'wonders']) for (const u of ((L.raw && L.raw[f] && L.raw[f].unplaced) || []))
    out.push({ id: u.id, kind: u.kind, name: u.name, cell: -1, tier: 2, value: u.value ?? null, unit: u.unit || '', year: u.year || '', sido: '', city: null, place: '', precision: '', ref: null, detail: [], file: f, unplaced: true, raw: u });
  return out;
}
