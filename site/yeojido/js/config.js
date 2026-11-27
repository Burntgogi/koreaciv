// 화면 쪽 상수. 층 묶음·세부의 id 는 기존판(site/js/render/layers.js)과 같아야 해시(ly, hide)를 주고받을 수 있다.
// 종류(kind) -> 묶음·세부 대응은 자료가 아니라 두 판이 함께 지키는 표다 (기존판 KINDS 와 같은 뜻).

export const LAYER_GROUPS = [
  { id: 'wonders', name: '불가사의', icon: 'world_heritage', def: true, shape: 'square', color: 'ju',
    subs: [['national_park', '국립공원'], ['world_heritage', '세계유산'], ['heritage_cluster', '국가유산 밀집지'], ['knowledge', '지식']] },
  { id: 'resources', name: '자원', icon: 'industrial', def: true, shape: 'circle', color: 'paper',
    subs: [['power', '발전소'], ['dam', '댐'], ['mine', '광산'], ['industrial', '국가산단'], ['industry', '주력 업종'], ['fishport', '어항'], ['farm', '특산·농축산']] },
  { id: 'infra', name: '기반시설', icon: 'station', def: true, shape: 'circle', color: 'jjok',
    subs: [['lines', '도로·철도 선'], ['station', '역'], ['trade_port', '항만'], ['airport', '공항']] },
  { id: 'trade', name: '교역', icon: 'export_hub', def: false, shape: 'diamond', color: 'nok', subs: [['routes', '교역로'], ['export_hub', '수출 거점']] },
  { id: 'frontier', name: '접경', icon: 'frontier', def: false, shape: null, color: 'ink', subs: [['frontier', '접경지역']] },
];
export const LAYER_DEFAULT = Object.fromEntries(LAYER_GROUPS.map((g) => [g.id, g.def]));

// 종류: 이름표, 묶음(layer), 세부(sub), 우선순위(작을수록 먼저)
export const KINDS = {
  world_heritage: { label: '세계유산', layer: 'wonders', sub: 'world_heritage', pri: 0 },
  knowledge: { label: '지식 (과학기술원·연구기관·대학)', layer: 'wonders', sub: 'knowledge', pri: 1 },
  national_park: { label: '국립공원', layer: 'wonders', sub: 'national_park', pri: 1 },
  heritage_cluster: { label: '국가유산 밀집지', layer: 'wonders', sub: 'heritage_cluster', pri: 2 },
  industrial_national: { label: '국가산업단지', layer: 'resources', sub: 'industrial', pri: 3 },
  port: { label: '국가어항', layer: 'resources', sub: 'fishport', pri: 4 },
  dam: { label: '댐', layer: 'resources', sub: 'dam', pri: 4 },
  mine: { label: '가행 광산', layer: 'resources', sub: 'mine', pri: 5 },
  nuclear: { label: '원전', layer: 'resources', sub: 'power', pri: -1 },
  power_coal: { label: '석탄 발전소', layer: 'resources', sub: 'power', pri: 3 },
  power_gas: { label: '가스(LNG) 발전소', layer: 'resources', sub: 'power', pri: 3 },
  power_oil: { label: '유류 발전소', layer: 'resources', sub: 'power', pri: 3 },
  power_hydro: { label: '수력·양수', layer: 'resources', sub: 'power', pri: 3 },
  power_solar: { label: '태양광 (시군구 합계)', layer: 'resources', sub: 'power', pri: 4 },
  power_wind: { label: '풍력 (시군구 합계)', layer: 'resources', sub: 'power', pri: 4 },
  trade_port: { label: '무역항', layer: 'infra', sub: 'trade_port', pri: 2 },
  airport: { label: '공항', layer: 'infra', sub: 'airport', pri: 2 },
  station: { label: '철도역', layer: 'infra', sub: 'station', pri: 6 },
  gi: { label: '특산 (지리적표시)', layer: 'resources', sub: 'farm', pri: 5 },
  rice: { label: '쌀 (생산 상위)', layer: 'resources', sub: 'farm', pri: 4 },
  cattle: { label: '한우 (사육 상위)', layer: 'resources', sub: 'farm', pri: 4 },
  pigs: { label: '돼지 (사육 상위)', layer: 'resources', sub: 'farm', pri: 4 },
  ind_c19: { label: '석유정제 (C19)', layer: 'resources', sub: 'industry', pri: 3 },
  ind_c20: { label: '화학 (C20)', layer: 'resources', sub: 'industry', pri: 3 },
  ind_c24: { label: '1차 금속 (C24)', layer: 'resources', sub: 'industry', pri: 3 },
  ind_c26: { label: '전자부품 (C26)', layer: 'resources', sub: 'industry', pri: 3 },
  ind_c30: { label: '자동차 (C30)', layer: 'resources', sub: 'industry', pri: 3 },
  ind_c31: { label: '기타 운송장비·조선 (C31)', layer: 'resources', sub: 'industry', pri: 3 },
  export_hub: { label: '수출 거점 (수출 상위 도시)', layer: 'trade', sub: 'export_hub', pri: 2 },
};
// 옛 공유 링크의 층 열쇠 (off=/on=) -> 새 묶음·세부
export const LEGACY_OFF = { wonders: { group: 'wonders' }, resources: { subs: ['dam', 'mine', 'industrial', 'fishport'] }, power: { subs: ['power'] },
  ports: { subs: ['trade_port', 'airport'] }, trade: { subs: ['export_hub'] }, industry: { subs: ['industry'] }, farm: { subs: ['farm'] },
  infra: { subs: ['station'] }, lines: { subs: ['lines'] } };
export const LEGACY_ON = { frontier: 'frontier', routes: 'trade' };

// 다섯 산출 (아이콘 이름은 icons.js)
export const YIELDS = [['food', '식량'], ['production', '생산'], ['gold', '금'], ['science', '과학'], ['culture', '문화']];
// 다른 판(기존판)의 주소: 같은 해시를 들고 간다
export const OTHER_EDITION = '../index.html';
export const NARROW = 700;
