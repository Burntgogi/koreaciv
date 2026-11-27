// 지도 층: 불가사의·자원·발전소·항만·공항·특산·기반시설 아이콘, 국립공원 칸 테두리, 접경 띠, 도로 선(표준노드링크)·철도 선(Natural Earth 초안).
// 아이콘은 캔버스에 도형으로 직접 그린다 (외부 그림·글꼴 없음). 종류마다 바탕 모양과 색이 다르다.
// 같은 칸에 여러 항목이 있으면 우선순위·값이 큰 것 하나를 그리고 나머지는 툴팁·패널 목록에 둔다.

import { EDGE_CORNERS } from '../hex.js';

// 종류: 이름, 층 묶음(layer), 세부 켜고 끄기(sub), 바탕 모양, 색, 우선순위(작을수록 먼저).
// 어느 배율부터 그리는지는 항목마다 빌드가 붙인 tier(0 전국, 1 중간, 2 가까이)와 wonders.json 의 zoom 규칙이 정한다.
// 층 조작 5묶음(6단계): 불가사의 · 자원 · 기반시설 · 교역 · 접경. 펼치면 종류별 세부 켜고 끄기.
export const LAYER_GROUPS = [
  { id: 'wonders', name: '불가사의', icon: 'world_heritage', def: true,
    subs: [['national_park', '국립공원'], ['world_heritage', '세계유산'], ['heritage_cluster', '국가유산 밀집지'], ['knowledge', '지식']] },
  { id: 'resources', name: '자원', icon: 'industrial_national', def: true,
    subs: [['power', '발전소'], ['dam', '댐'], ['mine', '광산'], ['industrial', '국가산단'], ['industry', '주력 업종'], ['fishport', '어항'], ['farm', '특산·농축산']] },
  { id: 'infra', name: '기반시설', icon: 'trade_port', def: true, subs: [['lines', '도로·철도 선'], ['station', '역'], ['trade_port', '항만'], ['airport', '공항']] },
  { id: 'trade', name: '교역', icon: 'export_hub', def: false, subs: [['routes', '교역로'], ['export_hub', '수출 거점']] },
  { id: 'frontier', name: '접경', icon: null, def: false, subs: [['frontier', '접경지역']] },
];
// 세부 항목의 아이콘 (조작부 그림)
export const SUB_ICONS = { national_park: ['national_park'], world_heritage: ['world_heritage'], heritage_cluster: ['heritage_cluster'], knowledge: ['knowledge'],
  power: ['nuclear', 'power_coal', 'power_solar'], dam: ['dam'], mine: ['mine'], industrial: ['industrial_national'], industry: ['ind_c26', 'ind_c30'], fishport: ['port'],
  farm: ['rice', 'cattle', 'gi'], station: ['station'], trade_port: ['trade_port'], airport: ['airport'], export_hub: ['export_hub'], lines: [], routes: [], frontier: [] };
export const KINDS = {
  world_heritage: { label: '세계유산', layer: 'wonders', sub: 'world_heritage', shape: 'diamond', color: '#c99a1e', pri: 0 },
  knowledge: { label: '지식 (과학기술원·연구기관·대학)', layer: 'wonders', sub: 'knowledge', shape: 'diamond', color: '#3f63b8', pri: 1 },
  national_park: { label: '국립공원', layer: 'wonders', sub: 'national_park', shape: 'circle', color: '#2f8a4e', pri: 1 },
  heritage_cluster: { label: '국가유산 밀집지', layer: 'wonders', sub: 'heritage_cluster', shape: 'square', color: '#9a4a2c', pri: 2 },
  industrial_national: { label: '국가산업단지', layer: 'resources', sub: 'industrial', shape: 'hex', color: '#59677a', pri: 3 },
  port: { label: '국가어항', layer: 'resources', sub: 'fishport', shape: 'circle', color: '#2a6db5', pri: 4 },
  dam: { label: '댐', layer: 'resources', sub: 'dam', shape: 'circle', color: '#3c8fb0', pri: 4 },
  mine: { label: '가행 광산 (광종별)', layer: 'resources', sub: 'mine', shape: 'square', color: '#7b6650', pri: 5 },
  nuclear: { label: '원전', layer: 'resources', sub: 'power', shape: 'hex', color: '#d6b11f', pri: 2 },
  power_coal: { label: '석탄 발전소', layer: 'resources', sub: 'power', shape: 'hex', color: '#4a4440', pri: 3 },
  power_gas: { label: '가스(LNG) 발전소', layer: 'resources', sub: 'power', shape: 'hex', color: '#d0632a', pri: 3 },
  power_oil: { label: '유류 발전소', layer: 'resources', sub: 'power', shape: 'hex', color: '#6b4a2a', pri: 3 },
  power_hydro: { label: '수력·양수', layer: 'resources', sub: 'power', shape: 'hex', color: '#2f7fc0', pri: 3 },
  power_solar: { label: '태양광 (시군구 합계)', layer: 'resources', sub: 'power', shape: 'hex', color: '#e3a21a', pri: 4 },
  power_wind: { label: '풍력 (시군구 합계)', layer: 'resources', sub: 'power', shape: 'hex', color: '#5aa6a0', pri: 4 },
  trade_port: { label: '무역항', layer: 'infra', sub: 'trade_port', shape: 'square', color: '#1f5d8f', pri: 2 },
  airport: { label: '공항', layer: 'infra', sub: 'airport', shape: 'circle', color: '#6a5acd', pri: 2 },
  station: { label: '철도역', layer: 'infra', sub: 'station', shape: 'dot', color: '#c23b30', pri: 6 },
  gi: { label: '특산 (지리적표시)', layer: 'resources', sub: 'farm', shape: 'circle', color: '#8a5a9e', pri: 5 },
  rice: { label: '쌀 (생산 상위)', layer: 'resources', sub: 'farm', shape: 'circle', color: '#a89a2e', pri: 4 },
  cattle: { label: '한우 (사육 상위, 2026-10)', layer: 'resources', sub: 'farm', shape: 'circle', color: '#8c5a3c', pri: 4 },
  pigs: { label: '돼지 (사육 상위, 2026)', layer: 'resources', sub: 'farm', shape: 'circle', color: '#c97c86', pri: 4 },
  // 5d: 주력 업종 (2020 경제총조사, 전국 종사자의 3% 이상인 도시), 수출 거점 (수출 상위 도시)
  ind_c19: { label: '석유정제 (C19)', layer: 'resources', sub: 'industry', shape: 'square', color: '#3b3a36', pri: 3 },
  ind_c20: { label: '화학 (C20)', layer: 'resources', sub: 'industry', shape: 'square', color: '#6d4c9a', pri: 3 },
  ind_c24: { label: '1차 금속 (C24)', layer: 'resources', sub: 'industry', shape: 'square', color: '#8a4b2a', pri: 3 },
  ind_c26: { label: '전자부품 (C26)', layer: 'resources', sub: 'industry', shape: 'square', color: '#1f7a6b', pri: 3 },
  ind_c30: { label: '자동차 (C30)', layer: 'resources', sub: 'industry', shape: 'square', color: '#a8322e', pri: 3 },
  ind_c31: { label: '기타 운송장비·조선 (C31)', layer: 'resources', sub: 'industry', shape: 'square', color: '#2a5d9a', pri: 3 },
  export_hub: { label: '수출 거점 (수출 상위 도시)', layer: 'trade', sub: 'export_hub', shape: 'circle', color: '#0e7f8a', pri: 2 },
};
// 배치 예산 기본값 (층 파일을 받기 전 첫 화면 깃발용). 빌드 값은 wonders.json zoom.budget
export const BUDGET_DEFAULT = { z_max: 2.0, flags_desktop: 24, flags_mobile: 12, icons_desktop: 52, icons_mobile: 24, mobile_vw: 700,
  second_ring: 2.4, second_px: 22, second_ring_mobile: 2.0, second_px_mobile: 18 };
export const PRECISION = {
  point: '원자료 좌표',
  area: '경계 폴리곤 대표점',
  county: '시군구 대표 위치 (주소의 시군구, 인구 가중 중심 칸)',
  sido: '시도 대표 위치 (위치 문자열에 시도뿐: 시도의 해안 칸 중 인구 중심에 가까운 칸)',
};
// 저장 키(point·area·county·sido) -> 화면 이름 (감사 22: 내부 분류명을 그대로 보이지 않는다)
export const PREC_KO = { point: '좌표', area: '경계 대표점', county: '시군구 대표 위치', sido: '시도 대표 위치', list: '목록만' };
// 항목 패널·툴팁의 위치 정밀도 문구. 지식 불가사의(대학·기관)를 주소의 시군구로 놓았으면 캠퍼스 자리가 아님을 문구에 드러낸다
export function precisionText(it) {
  if (!it.precision) return '지도에 놓지 못함';
  if (it.kind === 'knowledge' && it.precision === 'county') {
    const unit = it.group ? '자치구·시군구' : (String(it.place || '').split(' ').pop() || '시군구');
    return `${unit} 중심 칸 — 캠퍼스·기관 자리가 아님 (좌표 없음, 주소의 시군구 인구 가중 중심 = 시군구 대표 위치)`;
  }
  return PRECISION[it.precision] || it.precision;
}
export const PLACE_FROM = {
  area: '등록지역 문자열의 시군구', name: '품목 이름이 시·군 이름으로 시작 (place_from: name)',
  heritage_name: '이름이 같은 국가유산의 좌표 (place_from: heritage_name)', address: '소재지·주소 문자열의 시군구 (place_from: address)',
  observation: '이름이 같은 WAMIS 댐 관측소 좌표 (place_from: observation)', city: '도시 합계 — 도시 시군구의 인구 가중 중심 칸 (place_from: city)',
};

// ---------- 글리프 (반지름 r 의 바탕 안에 흰 선으로) ----------
function glyph(ctx, kind, x, y, r) {
  ctx.save();
  ctx.translate(x, y);
  ctx.fillStyle = '#fffdf4';
  ctx.strokeStyle = '#fffdf4';
  ctx.lineWidth = Math.max(1, r * 0.14);
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  const u = r / 10;
  ctx.beginPath();
  switch (kind) {
    case 'national_park': // 소나무 두 층 + 줄기
      ctx.moveTo(0, -7 * u); ctx.lineTo(5 * u, -1 * u); ctx.lineTo(-5 * u, -1 * u); ctx.closePath();
      ctx.moveTo(0, -3 * u); ctx.lineTo(6.5 * u, 4 * u); ctx.lineTo(-6.5 * u, 4 * u); ctx.closePath();
      ctx.fill();
      ctx.fillRect(-1.2 * u, 4 * u, 2.4 * u, 3 * u);
      break;
    case 'world_heritage': // 지붕 + 기둥 셋 + 기단
      ctx.moveTo(-6 * u, -2.5 * u); ctx.lineTo(0, -6.5 * u); ctx.lineTo(6 * u, -2.5 * u); ctx.closePath();
      ctx.fill();
      for (const dx of [-4, 0, 4]) ctx.fillRect((dx - 0.9) * u, -1.5 * u, 1.8 * u, 6 * u);
      ctx.fillRect(-6.5 * u, 4.5 * u, 13 * u, 1.8 * u);
      break;
    case 'heritage_cluster': // 탑 (지붕 세 겹)
      for (let k = 0; k < 3; k++) {
        const yy = -5.5 * u + k * 3.6 * u, ww = (3 + k * 1.6) * u;
        ctx.moveTo(-ww, yy + 1.4 * u); ctx.quadraticCurveTo(0, yy - 1.2 * u, ww, yy + 1.4 * u);
      }
      ctx.stroke();
      ctx.fillRect(-0.9 * u, -7 * u, 1.8 * u, 13 * u);
      ctx.fillRect(-4.5 * u, 5.5 * u, 9 * u, 1.6 * u);
      break;
    case 'industrial_national': // 톱니 지붕 공장 + 굴뚝
      ctx.moveTo(-6.5 * u, 5.5 * u); ctx.lineTo(-6.5 * u, -0.5 * u); ctx.lineTo(-3 * u, -3 * u); ctx.lineTo(-3 * u, -0.5 * u);
      ctx.lineTo(0.5 * u, -3 * u); ctx.lineTo(0.5 * u, -0.5 * u); ctx.lineTo(3.5 * u, -3 * u); ctx.lineTo(3.5 * u, -7 * u);
      ctx.lineTo(6 * u, -7 * u); ctx.lineTo(6.5 * u, 5.5 * u); ctx.closePath();
      ctx.fill();
      break;
    case 'port': // 닻
      ctx.arc(0, -5 * u, 1.7 * u, 0, Math.PI * 2);
      ctx.moveTo(0, -3.3 * u); ctx.lineTo(0, 6 * u);
      ctx.moveTo(-3.5 * u, -1 * u); ctx.lineTo(3.5 * u, -1 * u);
      ctx.moveTo(-6 * u, 1.5 * u); ctx.quadraticCurveTo(-5 * u, 6.5 * u, 0, 6 * u); ctx.quadraticCurveTo(5 * u, 6.5 * u, 6 * u, 1.5 * u);
      ctx.stroke();
      break;
    case 'nuclear': // 원자 (궤도 셋)
      for (let k = 0; k < 3; k++) {
        ctx.save(); ctx.rotate((k * Math.PI) / 3); ctx.beginPath(); ctx.ellipse(0, 0, 6.5 * u, 2.4 * u, 0, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
      }
      ctx.beginPath(); ctx.arc(0, 0, 1.6 * u, 0, Math.PI * 2); ctx.fill();
      break;
    case 'dam': // 물결
      for (const yy of [-2.5, 2.5]) { ctx.moveTo(-6 * u, yy * u); ctx.quadraticCurveTo(-3 * u, (yy - 2.5) * u, 0, yy * u); ctx.quadraticCurveTo(3 * u, (yy + 2.5) * u, 6 * u, yy * u); }
      ctx.stroke();
      break;
    case 'airport': // 비행기
      ctx.moveTo(0, -7 * u); ctx.lineTo(1.3 * u, -2 * u); ctx.lineTo(7 * u, 1 * u); ctx.lineTo(7 * u, 2.5 * u); ctx.lineTo(1.3 * u, 1 * u);
      ctx.lineTo(1 * u, 5 * u); ctx.lineTo(3 * u, 6.5 * u); ctx.lineTo(-3 * u, 6.5 * u); ctx.lineTo(-1 * u, 5 * u); ctx.lineTo(-1.3 * u, 1 * u);
      ctx.lineTo(-7 * u, 2.5 * u); ctx.lineTo(-7 * u, 1 * u); ctx.lineTo(-1.3 * u, -2 * u); ctx.closePath();
      ctx.fill();
      break;
    case 'power_coal': // 굴뚝 둘 + 연기
      ctx.fillRect(-5 * u, -1 * u, 3 * u, 7 * u); ctx.fillRect(1 * u, -3 * u, 3 * u, 9 * u);
      ctx.fill();
      ctx.beginPath(); ctx.arc(-1.5 * u, -4.5 * u, 2 * u, 0, Math.PI * 2); ctx.arc(3 * u, -6.5 * u, 1.6 * u, 0, Math.PI * 2); ctx.fill();
      break;
    case 'power_gas': case 'power_oil': // 불꽃
      ctx.moveTo(0, -7 * u); ctx.quadraticCurveTo(6 * u, -1 * u, 4 * u, 3.5 * u); ctx.quadraticCurveTo(2.5 * u, 7 * u, 0, 7 * u);
      ctx.quadraticCurveTo(-2.5 * u, 7 * u, -4 * u, 3.5 * u); ctx.quadraticCurveTo(-5 * u, -0.5 * u, -1 * u, -3 * u);
      ctx.quadraticCurveTo(0.5 * u, -1 * u, 0, -7 * u); ctx.closePath(); ctx.fill();
      break;
    case 'power_hydro': // 물방울
      ctx.moveTo(0, -7 * u); ctx.quadraticCurveTo(6 * u, 0, 5 * u, 2.5 * u); ctx.arc(0, 2.5 * u, 5 * u, 0, Math.PI); ctx.quadraticCurveTo(-6 * u, 0, 0, -7 * u);
      ctx.fill();
      break;
    case 'power_solar': // 해
      ctx.arc(0, 0, 3 * u, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath();
      for (let k = 0; k < 8; k++) { const a = (Math.PI / 4) * k; ctx.moveTo(Math.cos(a) * 4.6 * u, Math.sin(a) * 4.6 * u); ctx.lineTo(Math.cos(a) * 7 * u, Math.sin(a) * 7 * u); }
      ctx.stroke();
      break;
    case 'power_wind': // 풍차 날개 셋 + 기둥
      ctx.moveTo(0, -1 * u); ctx.lineTo(0, 7 * u);
      for (let k = 0; k < 3; k++) { const a = -Math.PI / 2 + (2 * Math.PI / 3) * k; ctx.moveTo(0, -1 * u); ctx.lineTo(Math.cos(a) * 6.5 * u, -1 * u + Math.sin(a) * 6.5 * u); }
      ctx.stroke();
      break;
    case 'trade_port': // 배
      ctx.moveTo(-7 * u, 1 * u); ctx.lineTo(7 * u, 1 * u); ctx.lineTo(4.5 * u, 5.5 * u); ctx.lineTo(-4.5 * u, 5.5 * u); ctx.closePath(); ctx.fill();
      ctx.fillRect(-4 * u, -3 * u, 3.4 * u, 3.4 * u); ctx.fillRect(0.4 * u, -3 * u, 3.4 * u, 3.4 * u); ctx.fillRect(-1.8 * u, -6.6 * u, 3.4 * u, 3.4 * u);
      break;
    case 'gi': // 별
      for (let k = 0; k < 10; k++) { const a = -Math.PI / 2 + (Math.PI / 5) * k, rr = (k % 2 ? 3 : 7) * u; if (k) ctx.lineTo(Math.cos(a) * rr, Math.sin(a) * rr); else ctx.moveTo(Math.cos(a) * rr, Math.sin(a) * rr); }
      ctx.closePath(); ctx.fill();
      break;
    case 'rice': // 벼 이삭
      ctx.moveTo(0, 7 * u); ctx.quadraticCurveTo(0.5 * u, -1 * u, 4 * u, -6 * u); ctx.stroke();
      for (const [x0, y0] of [[1.2, 1], [2.2, -2], [3.4, -4.8]]) {
        ctx.beginPath(); ctx.ellipse((x0 - 2.2) * u, y0 * u, 1.3 * u, 2.4 * u, -0.6, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.ellipse((x0 + 1.6) * u, (y0 + 1.2) * u, 1.3 * u, 2.4 * u, 0.6, 0, Math.PI * 2); ctx.fill();
      }
      break;
    case 'cattle': // 소 머리 (뿔)
      ctx.arc(0, 1 * u, 4 * u, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.moveTo(-3.5 * u, -2 * u); ctx.quadraticCurveTo(-7 * u, -3 * u, -6.5 * u, -6.5 * u); ctx.moveTo(3.5 * u, -2 * u); ctx.quadraticCurveTo(7 * u, -3 * u, 6.5 * u, -6.5 * u); ctx.stroke();
      break;
    case 'pigs': // 돼지 코
      ctx.arc(0, 0, 5.5 * u, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.ellipse(0, 1 * u, 3.2 * u, 2.3 * u, 0, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#c97c86'; ctx.beginPath(); ctx.arc(-1.2 * u, 1 * u, 0.8 * u, 0, Math.PI * 2); ctx.arc(1.2 * u, 1 * u, 0.8 * u, 0, Math.PI * 2); ctx.fill();
      break;
    case 'knowledge': // 펼친 책
      ctx.moveTo(0, -3.5 * u); ctx.quadraticCurveTo(-3.5 * u, -6 * u, -7 * u, -4.5 * u); ctx.lineTo(-7 * u, 4.5 * u); ctx.quadraticCurveTo(-3.5 * u, 3 * u, 0, 5.5 * u);
      ctx.quadraticCurveTo(3.5 * u, 3 * u, 7 * u, 4.5 * u); ctx.lineTo(7 * u, -4.5 * u); ctx.quadraticCurveTo(3.5 * u, -6 * u, 0, -3.5 * u); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = '#3f63b8'; ctx.beginPath(); ctx.moveTo(0, -3.5 * u); ctx.lineTo(0, 5.5 * u); ctx.stroke();
      break;
    case 'mine': // 곡괭이
      ctx.moveTo(-6 * u, -3 * u); ctx.quadraticCurveTo(0, -8 * u, 6 * u, -3 * u); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, -5.3 * u); ctx.lineTo(0, 7 * u); ctx.lineWidth = Math.max(1.4, r * 0.2); ctx.stroke();
      break;
    case 'ind_c19': // 기름통
      ctx.roundRect(-4.5 * u, -6 * u, 9 * u, 12 * u, 2 * u); ctx.fill();
      ctx.fillStyle = '#3b3a36'; ctx.fillRect(-4.5 * u, -2.2 * u, 9 * u, 1.2 * u); ctx.fillRect(-4.5 * u, 1.8 * u, 9 * u, 1.2 * u);
      break;
    case 'ind_c20': // 플라스크
      ctx.moveTo(-1.6 * u, -6.5 * u); ctx.lineTo(1.6 * u, -6.5 * u); ctx.lineTo(1.6 * u, -1.5 * u); ctx.lineTo(6 * u, 6 * u); ctx.lineTo(-6 * u, 6 * u); ctx.lineTo(-1.6 * u, -1.5 * u);
      ctx.closePath(); ctx.fill();
      break;
    case 'ind_c24': // 쇳덩이 (사다리꼴 둘)
      ctx.moveTo(-6.5 * u, 6 * u); ctx.lineTo(-4.5 * u, 1 * u); ctx.lineTo(-0.5 * u, 1 * u); ctx.lineTo(1.5 * u, 6 * u); ctx.closePath();
      ctx.moveTo(-0.5 * u, 6 * u); ctx.lineTo(1.5 * u, 1 * u); ctx.lineTo(5 * u, 1 * u); ctx.lineTo(7 * u, 6 * u); ctx.closePath();
      ctx.moveTo(-3.5 * u, 0 * u); ctx.lineTo(-1.5 * u, -5 * u); ctx.lineTo(2.5 * u, -5 * u); ctx.lineTo(4.5 * u, 0 * u); ctx.closePath(); ctx.fill();
      break;
    case 'ind_c26': // 반도체 칩
      ctx.fillRect(-4 * u, -4 * u, 8 * u, 8 * u);
      for (const t of [-2.5, 0, 2.5]) { ctx.fillRect(-7 * u, (t - 0.6) * u, 2.4 * u, 1.2 * u); ctx.fillRect(4.6 * u, (t - 0.6) * u, 2.4 * u, 1.2 * u); ctx.fillRect((t - 0.6) * u, -7 * u, 1.2 * u, 2.4 * u); ctx.fillRect((t - 0.6) * u, 4.6 * u, 1.2 * u, 2.4 * u); }
      break;
    case 'ind_c30': // 자동차
      ctx.moveTo(-7 * u, 3 * u); ctx.lineTo(-7 * u, 0); ctx.lineTo(-4 * u, -1 * u); ctx.lineTo(-2 * u, -4.5 * u); ctx.lineTo(3 * u, -4.5 * u); ctx.lineTo(5 * u, -1 * u); ctx.lineTo(7 * u, 0); ctx.lineTo(7 * u, 3 * u); ctx.closePath(); ctx.fill();
      ctx.beginPath(); ctx.arc(-3.8 * u, 3.6 * u, 2 * u, 0, Math.PI * 2); ctx.arc(3.8 * u, 3.6 * u, 2 * u, 0, Math.PI * 2); ctx.fill();
      break;
    case 'ind_c31': // 배와 크레인
      ctx.moveTo(-7 * u, 2 * u); ctx.lineTo(7 * u, 2 * u); ctx.lineTo(4.5 * u, 6.5 * u); ctx.lineTo(-4.5 * u, 6.5 * u); ctx.closePath(); ctx.fill();
      ctx.beginPath(); ctx.moveTo(-3 * u, 1.5 * u); ctx.lineTo(-3 * u, -6.5 * u); ctx.lineTo(5 * u, -6.5 * u); ctx.moveTo(4 * u, -6.5 * u); ctx.lineTo(4 * u, -2 * u); ctx.stroke();
      break;
    case 'export_hub': // 컨테이너 + 오른쪽 위 화살표
      ctx.fillRect(-6.5 * u, -0.5 * u, 9 * u, 6.5 * u);
      ctx.moveTo(0, -1.5 * u); ctx.lineTo(6 * u, -6.5 * u); ctx.moveTo(1.5 * u, -6.5 * u); ctx.lineTo(6 * u, -6.5 * u); ctx.lineTo(6 * u, -2 * u); ctx.stroke();
      ctx.strokeStyle = '#0e7f8a'; ctx.lineWidth = Math.max(0.8, r * 0.08); ctx.beginPath();
      for (const x of [-4, -1.5, 0.5]) { ctx.moveTo(x * u, 0.8 * u); ctx.lineTo(x * u, 4.8 * u); }
      ctx.stroke();
      break;
    default:
  }
  ctx.restore();
}

function badgePath(ctx, shape, x, y, r) {
  ctx.beginPath();
  if (shape === 'diamond') {
    const k = r * 1.22;
    ctx.moveTo(x, y - k); ctx.lineTo(x + k, y); ctx.lineTo(x, y + k); ctx.lineTo(x - k, y); ctx.closePath();
  } else if (shape === 'square') {
    ctx.roundRect(x - r * 0.95, y - r * 0.95, r * 1.9, r * 1.9, r * 0.3);
  } else if (shape === 'hex') {
    for (let k = 0; k < 6; k++) {
      const a = (Math.PI / 3) * k;
      const px = x + r * 1.08 * Math.cos(a), py = y + r * 1.08 * Math.sin(a);
      if (k) ctx.lineTo(px, py); else ctx.moveTo(px, py);
    }
    ctx.closePath();
  } else ctx.arc(x, y, r, 0, Math.PI * 2);
}

// 범례·패널용 작은 아이콘 (캔버스 -> data URL, 종류마다 한 번)
const iconCache = new Map();
export function iconURL(kind, hsr = false) {
  const key = kind + (hsr ? 'h' : '');
  if (iconCache.has(key)) return iconCache.get(key);
  const cv = document.createElement('canvas');
  cv.width = cv.height = 36;
  const ctx = cv.getContext('2d');
  drawBadge(ctx, kind, 18, 18, kind === 'station' ? (hsr ? 7 : 5) : 13, hsr);
  const url = cv.toDataURL();
  iconCache.set(key, url);
  return url;
}

export function drawBadge(ctx, kind, x, y, r, hsr = false, sel = false) {
  const K = KINDS[kind];
  if (K.shape === 'dot') {
    ctx.beginPath();
    ctx.arc(x, y, r + 1.2, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(20,16,12,0.85)';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = hsr ? '#fff6e6' : K.color;
    ctx.fill();
    if (hsr) {
      ctx.beginPath();
      ctx.arc(x, y, r * 0.55, 0, Math.PI * 2);
      ctx.fillStyle = K.color;
      ctx.fill();
    }
    if (sel) { ctx.strokeStyle = '#ffd34d'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x, y, r + 3, 0, Math.PI * 2); ctx.stroke(); }
    return;
  }
  badgePath(ctx, K.shape, x, y + 1.2, r + 1.4);
  ctx.fillStyle = 'rgba(12,10,8,0.55)';
  ctx.fill();
  badgePath(ctx, K.shape, x, y, r);
  ctx.fillStyle = K.color;
  ctx.fill();
  ctx.lineWidth = sel ? 2.4 : 1.4;
  ctx.strokeStyle = sel ? '#ffd34d' : 'rgba(255,250,235,0.92)';
  ctx.stroke();
  glyph(ctx, kind, x, y, r * 0.86);
}

export class LayerRenderer {
  constructor(app, data) {
    this.app = app;
    this.data = data;
    const G = app.grid;
    this.items = [...data.wonders.items, ...data.resources.items, ...data.infrastructure.items];
    this.zoom = data.wonders.zoom || { levels: [{ tier: 0, z_min: 0 }, { tier: 1, z_min: 2 }, { tier: 2, z_min: 3.2 }], rules: [] };
    // 그리기 우선순위 (wonders.json zoom.draw_priority): 이 종류는 먼저 놓고 숨기지 않는다 (깃발이 비켜 서거나 아이콘을 가까운 빈 칸으로 옮김)
    FIRST = new Set((this.zoom.draw_priority && this.zoom.draw_priority.first) || []);
    // 7b #1: 다음 우선군 (전국 단계 공항·무역항) — 깃발은 밀지 않고 아이콘만 가까운 빈 칸으로 옮긴다. 배치 예산(전국 배율 아이콘 수)
    SECOND = new Set((this.zoom.draw_priority && this.zoom.draw_priority.second) || ['airport', 'trade_port']);
    this.budget = this.zoom.budget || BUDGET_DEFAULT;
    this.byId = new Map(this.items.map((i) => [i.id, i]));
    // 대학 묶음 표지 (같은 도시의 같은·이웃 칸 대학): 보기 단계(view_tiers)에서 묶인 대학 대신 그린다
    this.groups = ((this.zoom.knowledge_groups && this.zoom.knowledge_groups.groups) || []).map((g) => ({ ...g, memberItems: g.members.map((m) => this.byId.get(m)).filter(Boolean) }));
    for (const g of this.groups) this.byId.set(g.id, g);
    for (const u of [...data.resources.unplaced, ...data.infrastructure.unplaced]) this.byId.set(u.id, u);
    this.byCell = new Map();
    for (const it of this.items) {
      if (!this.byCell.has(it.cell)) this.byCell.set(it.cell, []);
      this.byCell.get(it.cell).push(it);
    }
    for (const lst of this.byCell.values()) lst.sort(cmp);
    // 국립공원 칸 테두리 (칸 집합의 바깥 변)
    this.parkSegs = data.wonders.parks.map((p) => {
      const set = new Set(p.cells), segs = [];
      for (const i of p.cells) {
        const nb = G.neighborSlots(i);
        for (let d = 0; d < 6; d++) {
          if (set.has(nb[d])) continue;
          const [a, b] = EDGE_CORNERS[d];
          segs.push(G.cx[i] + G.corner[a][0], G.cy[i] + G.corner[a][1], G.cx[i] + G.corner[b][0], G.cy[i] + G.corner[b][1]);
        }
      }
      return { park: p, segs };
    });
    this.lines = data.infrastructure.lines;
    // 교역로 (5d): 시도 청사 칸 두 곳을 잇는 완만한 곡선. 굵기는 두 방향 합 톤에 비례
    this.routes = [];
    this.routeById = new Map();
    const R = data.trade && data.trade.routes;
    if (R) {
      const tmax = Math.max(...R.segments.map((g) => g.total)) || 1;
      for (const g of R.segments) {
        const A = R.anchors[g.a], B = R.anchors[g.b];
        const ax = G.cx[A.cell], ay = G.cy[A.cell], bx = G.cx[B.cell], by = G.cy[B.cell];
        const dx = bx - ax, dy = by - ay, len = Math.hypot(dx, dy) || 1;
        // 제어점: 가운데에서 선에 수직으로 길이의 18% (코드가 작은 시도에서 큰 시도로 갈 때 왼쪽)
        const qx = (ax + bx) / 2 - (dy / len) * len * 0.18, qy = (ay + by) / 2 + (dx / len) * len * 0.18;
        const rt = { ...g, id: `${g.a}-${g.b}`, ax, ay, bx, by, qx, qy, w: Math.max(1.2, (13 * g.total) / tmax) };
        this.routes.push(rt);
        this.routeById.set(rt.id, rt);
      }
      // 굵은 선을 먼저 그리고 가는 선을 위에 (가는 선이 묻히지 않게)
      this.routes.sort((p, q) => q.total - p.total);
    }
    this.routeScreen = [];
    this.placed = [];
    // 접경: 시군 영토 테두리와 휴전선 변
    const W = app.world;
    this.frontierSegs = [];
    this.dmzSegs = [];
    this.frontierBy = new Map();
    if (data.frontier) {
      const kIdx = new Map(W.counties.map((c, k) => [c.code, k]));
      for (const ar of data.frontier.areas) {
        const ks = new Set(ar.sgg.map((c) => kIdx.get(c)));
        const cells = [];
        for (let i = 0; i < G.n; i++) if (W.owner[i] >= 0 && ks.has(W.county[i])) cells.push(i);
        const set = new Set(cells), segs = [];
        for (const i of cells) {
          const nb = G.neighborSlots(i);
          for (let d = 0; d < 6; d++) {
            if (set.has(nb[d])) continue;
            const [a, b] = EDGE_CORNERS[d];
            segs.push(G.cx[i] + G.corner[a][0], G.cy[i] + G.corner[a][1], G.cx[i] + G.corner[b][0], G.cy[i] + G.corner[b][1]);
          }
        }
        this.frontierSegs.push({ area: ar, segs, cells });
        for (const c of ar.sgg) this.frontierBy.set(c, ar);
      }
      for (let i = 0; i < G.n; i++) {
        if (W.owner[i] < 0) continue;
        const nb = G.neighborSlots(i);
        for (let d = 0; d < 6; d++) {
          if (nb[d] < 0 || W.foreign[nb[d]] !== 1) continue;
          const [a, b] = EDGE_CORNERS[d];
          this.dmzSegs.push(G.cx[i] + G.corner[a][0], G.cy[i] + G.corner[a][1], G.cx[i] + G.corner[b][0], G.cy[i] + G.corner[b][1]);
        }
      }
    }
  }

  // 교역로 층: 깃발·아이콘보다 먼저 그리고 반투명으로 (다른 층을 가리지 않게)
  drawRoutes(ctx, cam) {
    this.routeScreen = [];
    if (!this.app.layerVisible('trade', 'routes') || !this.routes.length) return;
    const sel = this.app.selRoute;
    const lens = !!this.app.lens;
    ctx.save();
    ctx.lineCap = 'round';
    for (const r of this.routes) {
      const [ax, ay] = cam.toScreen(r.ax, r.ay), [bx, by] = cam.toScreen(r.bx, r.by), [qx, qy] = cam.toScreen(r.qx, r.qy);
      const on = sel && sel.id === r.id;
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.quadraticCurveTo(qx, qy, bx, by);
      ctx.strokeStyle = on ? 'rgba(30,14,0,0.75)' : 'rgba(30,14,0,0.28)';
      ctx.lineWidth = r.w + 2.2;
      ctx.stroke();
      ctx.strokeStyle = on ? 'rgba(255,214,90,0.98)' : lens ? 'rgba(255,170,40,0.7)' : 'rgba(255,196,96,0.66)';
      ctx.lineWidth = r.w;
      ctx.stroke();
      // 화면 좌표 표본 (누르기·툴팁 판정)
      const pts = [];
      for (let k = 0; k <= 24; k++) {
        const t = k / 24, u = 1 - t;
        pts.push([u * u * ax + 2 * u * t * qx + t * t * bx, u * u * ay + 2 * u * t * qy + t * t * by]);
      }
      this.routeScreen.push({ r, pts });
    }
    // 끝점: 청사 칸에 작은 점
    const seen = new Set();
    for (const r of this.routes) {
      for (const [x, y, c] of [[r.ax, r.ay, r.a], [r.bx, r.by, r.b]]) {
        if (seen.has(c)) continue;
        seen.add(c);
        const [sx, sy] = cam.toScreen(x, y);
        ctx.beginPath();
        ctx.arc(sx, sy, 3.2, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,214,120,0.95)';
        ctx.strokeStyle = 'rgba(40,20,0,0.7)';
        ctx.lineWidth = 1.2;
        ctx.fill();
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  hitRoute(sx, sy) {
    let best = null, bd = 1e9;
    for (const { r, pts } of this.routeScreen) {
      for (let k = 1; k < pts.length; k++) {
        const [x0, y0] = pts[k - 1], [x1, y1] = pts[k];
        const dx = x1 - x0, dy = y1 - y0, L2 = dx * dx + dy * dy || 1;
        const t = Math.max(0, Math.min(1, ((sx - x0) * dx + (sy - y0) * dy) / L2));
        const d = Math.hypot(sx - (x0 + t * dx), sy - (y0 + t * dy));
        if (d <= r.w / 2 + 4 && d < bd) { bd = d; best = r; }
      }
    }
    return best;
  }

  // 접경 층: 접경지역 시군 테두리를 안쪽 띠로, 휴전선을 굵게
  drawFrontier(ctx, cam) {
    if (!this.app.layerVisible('frontier', 'frontier') || !this.frontierSegs.length) return;
    const s = cam.scale, ox = cam.x - cam.vw / 2 / s, oy = cam.y - cam.vh / 2 / s;
    const G = this.app.grid;
    const seg = (arr) => {
      ctx.beginPath();
      for (let k = 0; k < arr.length; k += 4) {
        ctx.moveTo((arr[k] - ox) * s, (arr[k + 1] - oy) * s);
        ctx.lineTo((arr[k + 2] - ox) * s, (arr[k + 3] - oy) * s);
      }
    };
    ctx.save();
    ctx.lineCap = 'round';
    for (const { area, segs, cells } of this.frontierSegs) {
      ctx.beginPath();
      for (const i of cells) G.pathHex(ctx, i, s, ox, oy);
      ctx.fillStyle = area.clause === 1 ? 'rgba(230,120,40,0.16)' : 'rgba(230,170,40,0.12)';
      ctx.fill();
      seg(segs);
      ctx.strokeStyle = area.clause === 1 ? 'rgba(235,110,30,0.55)' : 'rgba(235,170,40,0.5)';
      ctx.lineWidth = Math.max(4, s * 9);
      ctx.stroke();
      ctx.strokeStyle = area.clause === 1 ? '#ffb070' : '#ffd88a';
      ctx.lineWidth = 1.3;
      ctx.stroke();
    }
    seg(this.dmzSegs);
    ctx.strokeStyle = 'rgba(170,20,20,0.9)';
    ctx.lineWidth = Math.max(4, s * 7);
    ctx.stroke();
    ctx.setLineDash([6, 4]);
    ctx.strokeStyle = '#fff2e0';
    ctx.lineWidth = Math.max(1.5, s * 2.4);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();
  }

  kindOn(kind) {
    const K = KINDS[kind];
    return this.app.layerVisible(K.layer, K.sub);
  }

  // 배율 단계: wonders.json 의 zoom.levels[tier].z_min 이상이면 그린다 (선택한 항목은 늘)
  tierOn(it, z) {
    const lv = this.zoom.levels[it.tier ?? 2];
    return z >= (lv ? lv.z_min : 0);
  }

  zoomTier(z) {
    let t = 0;
    for (const lv of this.zoom.levels) if (z >= lv.z_min) t = lv.tier;
    return t;
  }

  iconR(z) { return Math.max(8, Math.min(13, 8 + (z - 1) * 0.9)); }

  // 대표 아이콘 후보: 칸마다 대표 하나(우선순위, 값) + 우선순위 종류(원전)는 같은 칸과 따로 하나씩 + 대학 묶음 표지.
  // 묶인 대학은 그 보기 단계에서 따로 그리지 않는다(선택했으면 그린다).
  reps(cam, selId) {
    const z = cam.scale / cam.minScale;
    const vt = String(this.zoomTier(z));
    const v = cam.view();
    const G = this.app.grid;
    const inView = (cell) => !(G.cx[cell] < v.x0 - 60 || G.cx[cell] > v.x1 + 60 || G.cy[cell] < v.y0 - 60 || G.cy[cell] > v.y1 + 60);
    const out = [];
    for (const [cell, lst] of this.byCell) {
      if (!inView(cell)) continue;
      const vis = lst.filter((it) => it.id === selId || (this.kindOn(it.kind) && this.tierOn(it, z) && !(it.grouped && it.grouped[vt])));
      if (!vis.length) continue;
      const first = vis.filter((it) => FIRST.has(it.kind));
      const second = vis.filter((it) => isSecond(it));
      const rest = vis.filter((it) => !FIRST.has(it.kind) && !isSecond(it));
      for (const it of first) out.push({ it, others: [], cell, prio: true });
      for (const it of second) out.push({ it, others: [], cell, second: true });
      if (rest.length) {
        rest.sort((p, q) => (p.id === selId ? -1 : q.id === selId ? 1 : 0));
        out.push({ it: rest[0], others: lst.filter((x) => x !== rest[0] && !first.includes(x) && !second.includes(x)), cell });
      }
    }
    if (this.kindOn('knowledge')) {
      for (const g of this.groups) {
        // 중간 배율부터는 묶음 표지도 깃발에 가리면 숨기지 않고 가까운 빈 칸으로 옮긴다 (깃발을 밀지는 않음)
        if ((g.id === selId || g.view_tiers.includes(Number(vt))) && inView(g.cell)) out.push({ it: g, others: [], cell: g.cell, nudge: vt !== '0' });
      }
    }
    out.sort((p, q) => (p.it.id === selId ? -1 : q.it.id === selId ? 1 : drawCmp(p.it, q.it)));
    return out;
  }

  // 우선순위 아이콘의 제자리 상자 (깃발 배치가 먼저 피하도록 main.js 가 Banners.layout 에 넘긴다)
  priorityBoxes(cam, selId) {
    const z = cam.scale / cam.minScale, r = this.iconR(z) + 2, G = this.app.grid;
    return this.reps(cam, selId).filter((rp) => rp.prio).map((rp) => {
      const [x, y] = cam.toScreen(G.cx[rp.cell], G.cy[rp.cell]);
      return { x0: x - r, y0: y - r, x1: x + r, y1: y + r };
    });
  }

  // 보이는 항목 배치. flags: 놓인 도시 깃발 상자 — 전국·중간 배율에서는 깃발과 겹치는 아이콘을 그리지 않는다.
  // 우선순위 종류(원전)는 숨기지 않고, 깃발·먼저 놓인 아이콘·같은 칸의 대표 아이콘과 겹치면 가까운 빈 칸(이웃 몇 겹 안)으로 옮긴다(원래 칸에 선).
  // 반환 [{it, others, x, y, r, ox?, oy?}]
  layout(cam, selId, flags = []) {
    const z = cam.scale / cam.minScale;
    const G = this.app.grid;
    const near = this.zoomTier(z) >= 2;
    const reps = this.reps(cam, selId);
    const out = [];
    const r0 = this.iconR(z);
    const flagHit = (x, y, r, strict) => flags.some((f) => (near && !strict
      ? x > f.r.x0 && x < f.r.x1 && y > f.r.y0 && y < f.r.y1
      : x + r > f.r.x0 && x - r < f.r.x1 && y + r > f.r.y0 && y - r < f.r.y1));
    const iconHit = (x, y, r, pad, lst = out) => lst.some((o) => Math.abs(o.x - x) < (o.r + r) * pad && Math.abs(o.y - y) < (o.r + r) * pad);
    // 우선순위 아이콘이 피할 자리: 같은 칸의 보통 대표 아이콘 (그 아이콘을 밀어내지 않게)
    const reserved = [];
    const prioCells = new Set(reps.filter((rp) => rp.prio).map((rp) => rp.cell));
    for (const rp of reps) {
      if (!rp.prio && prioCells.has(rp.cell)) {
        const [x, y] = cam.toScreen(G.cx[rp.cell], G.cy[rp.cell]);
        reserved.push({ x, y, r: r0 });
      }
    }
    // 깃발 글씨 상자와 도시 점 (옮길 아이콘이 피하는 것)
    const labels = [];
    for (const f of flags) {
      labels.push({ id: f.c.id, x0: f.x - 2, y0: f.y - 2, x1: f.x + f.w + 2, y1: f.y + f.h + 2 });
      labels.push({ id: f.c.id, x0: f.sx - 4, y0: f.sy - 4, x1: f.sx + 4, y1: f.sy + 4 });
    }
    const cellPx = G.W * cam.scale;
    const maxRing = Math.max(2, Math.min(14, Math.ceil(Math.max(4.5 * r0, 56) / cellPx)));
    const B = this.budget, mobile = cam.vw <= B.mobile_vw;
    const iconCap = z < B.z_max ? (mobile ? B.icons_mobile : B.icons_desktop) : Infinity;
    const secondDist = mobile ? Math.max(B.second_ring_mobile * r0, B.second_px_mobile) : Math.max(B.second_ring * r0, B.second_px);
    const W = this.app.world;
    for (const rp of reps) {
      const [sx, sy] = cam.toScreen(G.cx[rp.cell], G.cy[rp.cell]);
      const st = rp.it.kind === 'station';
      // 국립공원은 탐방객이 많을수록 크게 (size = √(탐방객 ÷ 최다))
      const r = st ? (rp.it.hsr ? Math.max(4, r0 * 0.5) : Math.max(3, r0 * 0.36)) : rp.it.kind === 'national_park' && rp.it.size != null ? r0 * (0.8 + 0.45 * rp.it.size) : r0;
      const sel = rp.it.id === selId;
      if (rp.second && !sel) {
        // 우선군 ②(공항·무역항): 깃발은 밀지 않는다. 제자리가 깃발 글씨·도시 점·먼저 놓인 아이콘과 겹치면 가까운 빈 칸(무역항은 바다 칸 먼저)으로 옮기고 선을 잇는다
        const free = (x, y) => {
          const b = boxesOf(x, y, r, false, 1)[0];
          return !labels.some((l) => over(b, l)) && !out.some((o) => boxesOf(o.x, o.y, o.r, !!o.it.group, 0.9).some((q) => over(b, q)));
        };
        if (free(sx, sy)) { out.push({ ...rp, x: sx, y: sy, r, sel }); continue; }
        const sea = rp.it.kind === 'trade_port';
        const cand = this.rings(rp.cell, maxRing).map((c) => {
          const [x, y] = cam.toScreen(G.cx[c], G.cy[c]);
          const d = Math.hypot(x - sx, y - sy);
          return { x, y, d, cost: d + (sea && W.owner[c] < 0 && W.foreign[c] !== 1 ? -4 : 0) };
        }).sort((p, q) => p.cost - q.cost);
        const spot = cand.find((p) => p.d <= secondDist && free(p.x, p.y)) || cand.find((p) => free(p.x, p.y));
        out.push({ ...rp, x: spot ? spot.x : sx, y: spot ? spot.y : sy, r, sel, ...(spot ? { ox: sx, oy: sy } : {}) });
        continue;
      }
      // 배치 예산: 전국 배율에서는 화면 아이콘 수 상한 (우선군 ①②는 상한 밖에서도 그린다)
      if (!sel && !rp.prio && out.length >= iconCap) continue;
      if ((rp.prio || rp.nudge) && !sel) {
        // 옮길 아이콘은 깃발의 글씨 상자와 도시 점만 피한다(깃대 아래 빈 곳은 써도 됨). 묶음 표지는 '대학 N' 표까지 상자로 본다
        const grp = !!rp.it.group;
        const free = (x, y) => {
          const B = boxesOf(x, y, r, grp, 1);
          return !B.some((b) => labels.some((l) => over(b, l))) && !B.some((b) => out.some((o) => boxesOf(o.x, o.y, o.r, !!o.it.group, 0.9).some((q) => over(b, q))))
            && !B.some((b) => reserved.some((o) => over(b, boxesOf(o.x, o.y, o.r, false, 0.9)[0])));
        };
        if (free(sx, sy)) { out.push({ ...rp, x: sx, y: sy, r, sel }); continue; }
        // 이웃 칸을 겹겹이 넓혀 가며 비용이 가장 작은 빈 칸. 비용 = 옮긴 거리 + 다른 깃발(원래 칸을 덮은 깃발 말고)에 12px 안으로 붙으면 15
        // + 원래 칸에서 가는 선이 다른 깃발 글씨를 가로지르면 40 — 빈 쪽(바다 등)으로, 선이 글씨를 지나지 않게
        const own = new Set(flags.filter((f) => sx > f.r.x0 && sx < f.r.x1 && sy > f.r.y0 && sy < f.r.y1).map((f) => f.c.id));
        const others = labels.filter((l) => !own.has(l.id));
        const crowd = (x, y) => others.filter((l) => x + r + 12 > l.x0 && x - r - 12 < l.x1 && y + r + 12 > l.y0 && y - r - 12 < l.y1).length;
        const cross = (x, y) => others.some((l) => { for (let t = 0.1; t < 1; t += 0.1) { const px = sx + (x - sx) * t, py = sy + (y - sy) * t; if (px > l.x0 && px < l.x1 && py > l.y0 && py < l.y1) return true; } return false; });
        const ring = this.rings(rp.cell, maxRing).map((c) => { const [x, y] = cam.toScreen(G.cx[c], G.cy[c]); return { x, y, d: Math.hypot(x - sx, y - sy) + 15 * crowd(x, y) + (cross(x, y) ? 40 : 0) }; }).sort((p, q) => p.d - q.d);
        let spot = ring.find((p) => free(p.x, p.y));
        if (!spot && !rp.prio) continue; // 대학 묶음은 빈 칸이 없으면 이 배율에서 숨긴다 (원전만 반드시 그림)
        spot = spot || ring.find((p) => !flagHit(p.x, p.y, r + 1, true)) || { x: sx, y: sy };
        out.push({ ...rp, x: spot.x, y: spot.y, r, sel, ...(spot.x !== sx || spot.y !== sy ? { ox: sx, oy: sy } : {}) });
        continue;
      }
      if (!sel) {
        // 깃발: 전국·중간 배율은 아이콘 상자가 깃발 상자와 겹치면, 가까운 배율은 아이콘 중심이 깃발 안이면 숨긴다
        if (flagHit(sx, sy, r, false)) continue;
        // 겹침: 이미 놓인 아이콘과 많이 겹치면 숨긴다 (대학 묶음의 '대학 N' 표와 겹쳐도)
        if (iconHit(sx, sy, r, st ? 0.6 : 0.8)) continue;
        if (out.some((o) => o.it.group && over(boxesOf(sx, sy, r, false, 0.8)[0], boxesOf(o.x, o.y, o.r, true, 1)[1]))) continue;
      }
      out.push({ ...rp, x: sx, y: sy, r, sel });
    }
    this.placed = out;
    return out;
  }

  // 놓인 아이콘 상자 (시도 이름·강 이름표가 피한다). onlyPrio 면 우선군 ①②만
  placedBoxes(onlyPrio = false) {
    return this.placed.filter((p) => !onlyPrio || p.prio || p.second).map((p) => ({ x0: p.x - p.r, y0: p.y - p.r, x1: p.x + p.r, y1: p.y + p.r }));
  }

  // 칸 i 둘레의 이웃 칸 (1겹부터 k겹까지)
  rings(i, k) {
    const G = this.app.grid, seen = new Set([i]);
    let front = [i];
    const out = [];
    for (let d = 0; d < k; d++) {
      const nx = [];
      for (const c of front) for (const j of G.neighbors(c)) if (!seen.has(j)) { seen.add(j); nx.push(j); out.push(j); }
      front = nx;
    }
    return out;
  }

  drawLines(ctx, cam) {
    if (!this.app.layerVisible('infra', 'lines')) return;
    const s = cam.scale, ox = cam.x - cam.vw / 2 / s, oy = cam.y - cam.vh / 2 / s;
    const z = s / cam.minScale;
    const path = (lst, pred) => {
      ctx.beginPath();
      for (const ln of lst) {
        if (pred && !pred(ln)) continue;
        const p = ln.pts;
        ctx.moveTo((p[0] - ox) * s, (p[1] - oy) * s);
        for (let k = 2; k < p.length; k += 2) ctx.lineTo((p[k] - ox) * s, (p[k + 1] - oy) * s);
      }
    };
    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    const lens = !!this.app.lens;
    // 6단계: 기반시설 선은 옅게 — 전국 배율에서는 더 옅게 (아이콘·깃발이 먼저 읽히게)
    const soft = z < 2 ? 0.62 : 0.85;
    // 주요 도로 (옅게)
    // 일반국도는 확대했을 때만
    path(this.lines.roads, (l) => l.tier === 2 && z >= 1.8);
    ctx.strokeStyle = lens ? `rgba(60,50,40,${0.35 * soft})` : `rgba(250,240,215,${0.45 * soft})`;
    ctx.lineWidth = Math.max(0.8, Math.min(2, 0.7 + z * 0.12));
    ctx.stroke();
    // 고속도로 급
    path(this.lines.roads, (l) => l.tier === 1);
    ctx.strokeStyle = `rgba(70,50,20,${0.35 * soft})`;
    ctx.lineWidth = Math.max(2.2, Math.min(4.5, 1.8 + z * 0.3));
    ctx.stroke();
    ctx.strokeStyle = `rgba(255,214,120,${(lens ? 0.8 : 0.72) * soft})`;
    ctx.lineWidth = Math.max(1.2, Math.min(2.6, 1 + z * 0.18));
    ctx.stroke();
    // 철도: 어두운 선 위에 흰 점선 (옅게)
    path(this.lines.rails);
    ctx.strokeStyle = `rgba(40,30,30,${0.55 * soft})`;
    ctx.lineWidth = Math.max(1.6, Math.min(3.2, 1.4 + z * 0.2));
    ctx.stroke();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = `rgba(255,255,255,${0.65 * soft})`;
    ctx.lineWidth = Math.max(0.8, Math.min(1.6, 0.7 + z * 0.1));
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();
  }

  drawParks(ctx, cam) {
    if (!this.app.layerVisible('wonders', 'national_park')) return;
    const s = cam.scale, ox = cam.x - cam.vw / 2 / s, oy = cam.y - cam.vh / 2 / s;
    const G = this.app.grid;
    const v = cam.view();
    const sel = this.app.selItem && this.app.selItem.kind === 'national_park' ? this.app.selItem.ref : null;
    ctx.save();
    for (const { park, segs } of this.parkSegs) {
      // 옅은 채움 (칸 단위)
      const on = park.id === sel;
      ctx.beginPath();
      for (const i of park.cells) {
        if (G.cx[i] < v.x0 - 50 || G.cx[i] > v.x1 + 50 || G.cy[i] < v.y0 - 50 || G.cy[i] > v.y1 + 50) continue;
        G.pathHex(ctx, i, s, ox, oy);
      }
      ctx.fillStyle = this.hatch(ctx, on);
      ctx.fill(); // 빗금 (시군구 경계의 점선과 헷갈리지 않게 테두리는 실선)
      ctx.beginPath();
      for (let k = 0; k < segs.length; k += 4) {
        ctx.moveTo((segs[k] - ox) * s, (segs[k + 1] - oy) * s);
        ctx.lineTo((segs[k + 2] - ox) * s, (segs[k + 3] - oy) * s);
      }
      ctx.strokeStyle = 'rgba(8,40,16,0.7)';
      ctx.lineWidth = on ? 4.4 : 3.2;
      ctx.stroke();
      ctx.strokeStyle = on ? '#c8ffb8' : '#6fd87e';
      ctx.lineWidth = on ? 2.2 : 1.6;
      ctx.stroke();
    }
    ctx.restore();
  }

  hatch(ctx, on) {
    const key = on ? 'h1' : 'h0';
    this._hatch = this._hatch || {};
    if (!this._hatch[key]) {
      const c = document.createElement('canvas');
      c.width = c.height = 9;
      const g = c.getContext('2d');
      g.strokeStyle = on ? 'rgba(190,255,170,0.75)' : 'rgba(40,150,60,0.55)';
      g.lineWidth = 1.6;
      g.beginPath();
      g.moveTo(-1, 10); g.lineTo(10, -1);
      g.moveTo(-1, 1); g.lineTo(1, -1);
      g.moveTo(8, 10); g.lineTo(10, 8);
      g.stroke();
      this._hatch[key] = ctx.createPattern(c, 'repeat');
    }
    return this._hatch[key];
  }

  drawIcons(ctx) {
    // 옮긴 우선순위 아이콘: 원래 칸까지 가는 선과 점 (아이콘보다 먼저)
    for (const p of this.placed) {
      if (p.ox == null) continue;
      const d = Math.hypot(p.x - p.ox, p.y - p.oy) || 1;
      const ex = p.x - ((p.x - p.ox) / d) * p.r, ey = p.y - ((p.y - p.oy) / d) * p.r;
      ctx.save();
      ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(p.ox, p.oy); ctx.lineTo(ex, ey);
      ctx.strokeStyle = 'rgba(12,10,8,0.75)'; ctx.lineWidth = 3; ctx.stroke();
      ctx.strokeStyle = KINDS[p.it.kind].color; ctx.lineWidth = 1.4; ctx.stroke();
      ctx.beginPath(); ctx.arc(p.ox, p.oy, 2.4, 0, Math.PI * 2);
      ctx.fillStyle = KINDS[p.it.kind].color; ctx.fill();
      ctx.strokeStyle = 'rgba(12,10,8,0.85)'; ctx.lineWidth = 1; ctx.stroke();
      ctx.restore();
    }
    for (let k = this.placed.length - 1; k >= 0; k--) {
      const p = this.placed[k];
      drawBadge(ctx, p.it.kind, p.x, p.y, p.r, !!p.it.hsr, p.sel);
      if (p.it.group) { // 대학 묶음: '대학 N'
        ctx.font = '700 10px sans-serif';
        const t = p.it.name;
        const w = ctx.measureText(t).width + 8;
        const bx = p.x + p.r * 0.7, by = p.y - p.r - 4;
        ctx.beginPath();
        ctx.roundRect(bx, by, w, 13, 6);
        ctx.fillStyle = p.sel ? '#6a4c0c' : '#22336b';
        ctx.fill();
        ctx.lineWidth = 1;
        ctx.strokeStyle = p.sel ? '#ffd34d' : 'rgba(255,250,235,0.9)';
        ctx.stroke();
        ctx.fillStyle = '#fff';
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'left';
        ctx.fillText(t, bx + 4, by + 7);
        continue;
      }
      if (p.others.length && p.r >= 9.5) { // 같은 칸에 더 있는 항목 수
        ctx.font = '700 9px sans-serif';
        const t = '+' + p.others.length;
        const w = ctx.measureText(t).width + 5;
        ctx.beginPath();
        ctx.roundRect(p.x + p.r * 0.55, p.y - p.r - 5, w, 11, 5);
        ctx.fillStyle = 'rgba(20,20,28,0.9)';
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'left';
        ctx.fillText(t, p.x + p.r * 0.55 + 2.5, p.y - p.r + 0.5);
      }
    }
  }

  // 누르기 판정: 배지 중심 기준 (옮긴 아이콘은 선 끝이 아니라 배지). 터치는 더 넓게
  hit(sx, sy, touch = false) {
    for (const p of this.placed) {
      const rr = touch ? Math.max(p.r + 4, 14) : Math.max(p.r + 2, 10);
      if (Math.abs(sx - p.x) <= rr && Math.abs(sy - p.y) <= rr) return p;
      // 대학 묶음의 '대학 N' 표도 누를 수 있게
      if (p.it.group && sx >= p.x + p.r * 0.7 && sx <= p.x + p.r * 0.7 + PILL_W && sy >= p.y - p.r - 4 && sy <= p.y - p.r + 9) return p;
    }
    return null;
  }

  // 도시(시도)에 든 항목: 소재 시군구가 그 도시에 속하거나, 공원 칸이 영토에 걸침
  itemsFor(sggSet, cellSet) {
    const out = [];
    for (const it of this.items) {
      if (it.kind === 'national_park') {
        const p = this.data.wonders.parks.find((x) => x.id === it.ref);
        if (p && p.cells.some((c) => cellSet.has(c))) out.push(it);
      } else if (it.sgg.some((c) => sggSet.has(c)) || (it.spans || []).some((c) => sggSet.has(c))) out.push(it);
    }
    return out.sort(cmp);
  }

  rule(kind) {
    const d = this.data;
    return d.wonders.kinds[kind] || d.resources.kinds[kind] || d.infrastructure.kinds[kind];
  }
}

// 아이콘 상자: [바탕(반지름 × k), 대학 묶음이면 '대학 N' 표]
const PILL_W = 44;
function boxesOf(x, y, r, group, k) {
  const b = [{ x0: x - r * k, y0: y - r * k, x1: x + r * k, y1: y + r * k }];
  if (group) b.push({ x0: x + r * 0.7, y0: y - r - 4, x1: x + r * 0.7 + PILL_W, y1: y - r + 9 });
  return b;
}
const over = (a, b) => a.x0 < b.x1 && a.x1 > b.x0 && a.y0 < b.y1 && a.y1 > b.y0;

let FIRST = new Set(['nuclear']);
let SECOND = new Set(['airport', 'trade_port']);
// 우선군 ②: 전국 단계(tier 0)의 공항·무역항
const isSecond = (it) => SECOND.has(it.kind) && (it.tier ?? 2) === 0;
// 그리는 순서: 우선군 ①(원전) → ②(전국 단계 공항·무역항) → 나머지는 cmp (목록 순서는 cmp 그대로)
function drawCmp(a, b) {
  const ra = FIRST.has(a.kind) ? 0 : isSecond(a) ? 1 : 2, rb = FIRST.has(b.kind) ? 0 : isSecond(b) ? 1 : 2;
  if (ra !== rb) return ra - rb;
  return cmp(a, b);
}

function cmp(a, b) {
  const pa = KINDS[a.kind].pri, pb = KINDS[b.kind].pri;
  if (pa !== pb) return pa - pb;
  if (a.kind === 'station' && !!a.hsr !== !!b.hsr) return a.hsr ? -1 : 1;
  return (b.value ?? -1) - (a.value ?? -1);
}
