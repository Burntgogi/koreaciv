// 연감 — 지도에 보이는 모든 것의 규칙·정의·출처가 닿는 책. 여섯 갈피: 지형·산줄기 / 렌즈 / 지도 층 / 산출·고을 / 출처 / 일러두기·글꼴.
// 글은 adapter/sources.js 가 만든 '구역'을 그대로 그린다 (자료 글은 모두 텍스트 노드).

import { h, clear, safeLink } from '../dom.js';
import { iconEl } from '../icons.js';
import { openModal, closeModal, isOpen } from './modal.js';
import { loadSources, loadFontCredits, almanacTerrain, almanacLenses, almanacLayers, almanacYields } from '../adapter/sources.js';

const TABS = [['terrain', '지형·산줄기'], ['lenses', '렌즈'], ['layers', '지도 층'], ['yields', '산출·고을'], ['sources', '출처'], ['notes', '일러두기·글꼴']];

// 구역 하나 -> 노드들
function section(s, lv = 3) {
  const out = [];
  if (s.h) out.push(h(`h${lv}${s.major ? '.major' : ''}`, s.h, s.sub ? h('small', s.sub) : null));
  for (const w of s.warn || []) out.push(h('p.warn', { role: 'note' }, h('b', '주의'), w));
  for (const p of s.p || []) if (p) out.push(h('p', p));
  if (s.yields) out.push(h('table.tbl', h('tbody', s.yields.map((y) => h('tr', h('th', { scope: 'row' }, h('span.yi', iconEl(y.id, 16)), y.name), h('td', y.rule))))));
  if (s.table && s.table.rows && s.table.rows.length) out.push(table(s.table));
  if (s.ul && s.ul.length) out.push(h('ul.notes', s.ul.map((x) => h('li', x))));
  for (const d of s.dim || []) if (d) out.push(h('p.dim', d));
  if (s.details) out.push(h('details', h('summary', s.details.summary), section(s.details, lv + 1)));
  return out;
}
function table(t) {
  const num = new Set(t.num || []);
  return h('div.tblwrap', h('table.tbl',
    t.head ? h('thead', h('tr', t.head.map((x, k) => h('th', { scope: 'col', class: num.has(k) ? 'r' : null }, x)))) : null,
    h('tbody', t.rows.map((r) => h('tr', r.map((c, k) => (k === 0 ? h('th', { scope: 'row' }, c ?? '') : h('td', { class: num.has(k) ? 'r' : null }, c === '자료 없음' ? h('span.na', c) : c ?? ''))))))));
}

// 이 판 (sources.json profile): 판 이름·뺀 것·까닭·변경금지 통계. 모두 텍스트 노드
function profileNote(P) {
  const pub = P.id === 'public';
  return h('div.profile', { class: pub ? 'pub' : 'full', role: 'note' },
    h('h3', `이 판: ${P.name}`, h('small', ` profile ${P.id}`)),
    h('p', P.statement),
    h('details', h('summary', `${pub ? '이 판에서 뺀 것' : '공개판에서 빼는 것'} ${P.excluded.length}묶음`),
      h('ul', P.excluded.map((e) => h('li', h('b', e.what), ` — ${e.why}`, e.instead ? h('small', ` 대신: ${e.instead}`) : null))),
      P.checkNeeded.length ? [h('p', h('b', '변경금지 통계 — 원 통계를 바꾸지 않음 '), h('small', P.checkRule)), h('ul', P.checkNeeded.map((x) => h('li', x.title, h('small', ` ${x.publisher} · ${x.license} · ${x.where.join('; ')}`))))] : null,
      h('p.dim', P.rule)));
}

export class Almanac {
  constructor(app) {
    this.app = app;
    this.tabId = 'terrain';
    this.built = {};
    const root = document.getElementById('modal-root');
    this.tabs = h('div.tabs', { role: 'tablist', 'aria-label': '연감 갈피' });
    this.body = h('div.alm-body', { role: 'tabpanel', id: 'alm-panel', tabindex: '0' });
    this.el = h('div.modal.alm', { hidden: true, 'aria-labelledby': 'alm-title' },
      h('div.sheet',
        h('header.mhead', h('h2#alm-title', '연감', h('small', '규칙 · 정의 · 출처')), h('button.x', { type: 'button', 'aria-label': '연감 닫기', onclick: () => this.close() }, iconEl('close', 18))),
        this.tabs, this.body));
    this.el.addEventListener('pointerdown', (e) => { if (e.target === this.el) this.close(); });
    TABS.forEach(([id, name], k) => this.tabs.append(h('button', { type: 'button', role: 'tab', id: 'alm-tab-' + id, 'aria-controls': 'alm-panel', dataset: { tab: id }, onclick: () => this.show(id) }, name)));
    this.tabs.addEventListener('keydown', (e) => {
      const k = TABS.findIndex((t) => t[0] === this.tabId);
      let n = -1;
      if (e.key === 'ArrowRight') n = (k + 1) % TABS.length; else if (e.key === 'ArrowLeft') n = (k + TABS.length - 1) % TABS.length;
      else if (e.key === 'Home') n = 0; else if (e.key === 'End') n = TABS.length - 1;
      if (n < 0) return;
      e.preventDefault(); this.show(TABS[n][0]); this.tabs.children[n].focus();
    });
    root.append(this.el);
    app.on('layersloaded', () => { delete this.built.layers; delete this.built.terrain; if (isOpen(this.el) && this.tabId === 'layers') this.show('layers'); });
  }

  open(tab) {
    const id = TABS.some((t) => t[0] === tab) ? tab : this.tabId;
    this.show(id);
    openModal(this.el, { initial: this.tabs.querySelector('[aria-selected="true"]') });
  }
  close() { closeModal(this.el); }

  show(id) {
    this.tabId = id;
    for (const b of this.tabs.children) { const on = b.dataset.tab === id; b.setAttribute('aria-selected', on ? 'true' : 'false'); b.tabIndex = on ? 0 : -1; }
    this.body.setAttribute('aria-labelledby', 'alm-tab-' + id);
    if (!this.built[id]) this.built[id] = h('div.pane.pane-' + id, this['build_' + id]());
    clear(this.body).append(this.built[id]);
    this.body.scrollTop = 0;
  }

  build_terrain() {
    const D = this.app.D;
    // 이용조건 경고는 출처가 와야 채워진다: 오면 다시 짓는다
    if (!D.sources && !this._srcAsked) { this._srcAsked = true; loadSources(D).then((S) => { if (S) { delete this.built.terrain; if (this.tabId === 'terrain' && isOpen(this.el)) this.show('terrain'); } }); }
    return almanacTerrain(D).flatMap((s) => section(s));
  }

  build_lenses() {
    const A = almanacLenses(this.app.D), out = [];
    out.push(h('p.lead', `렌즈 ${A.count}개를 ${A.groups.length}묶음으로 나눴다. 이름을 누르면 그 렌즈를 지도에 찍는다.`));
    out.push(h('nav.jump', { 'aria-label': '묶음으로 건너뛰기' }, A.groups.map((g) => h('a', { href: '#alm-g-' + g.id, onclick: (e) => { e.preventDefault(); const t = this.body.querySelector('#alm-g-' + g.id); if (t) t.scrollIntoView({ block: 'start' }); } }, g.name, h('small', String(g.lenses.length))))));
    for (const g of A.groups) {
      out.push(h('h3.major', { id: 'alm-g-' + g.id }, g.name, h('small', `${g.lenses.length}개`)));
      for (const l of g.lenses) {
        out.push(h('article.def',
          h('h4', h('button.lensgo', { type: 'button', title: '이 렌즈를 지도에 찍기', onclick: () => { this.close(); this.app.setLens(l.id); } }, l.name), l.unit ? h('small', l.unit) : null),
          h('p', l.description || h('span.na', '자료 없음')),
          l.definition ? h('p', l.definition) : null,
          l.unitsNote ? h('p.unitnote', l.unitsNote) : null,
          h('dl.meta',
            h('div', h('dt', '척도'), h('dd', `${l.scaleKo} · ${l.domain} · ${l.direction}`)),
            h('div', h('dt', '어디서 센 값'), h('dd', l.basis || h('span.na', '자료 없음'))),
            h('div', h('dt', '기준 시점'), h('dd', l.vintage || h('span.na', '자료 없음'))),
            h('div', h('dt', '출처'), h('dd', l.source || h('span.na', '자료 없음')))),
          l.details ? h('details', h('summary', l.details.summary), section(l.details, 5)) : null));
      }
    }
    for (const s of [...A.intro, ...A.outro]) out.push(...section(s));
    return out;
  }

  build_layers() {
    const secs = almanacLayers(this.app.D);
    if (!secs) return [h('p.dim', { role: 'status' }, '지도 층 자료를 불러오는 중입니다. 잠시 뒤 이 갈피가 채워집니다.')];
    return secs.flatMap((s) => section(s, s.major ? 3 : s.kind ? 4 : 3));
  }

  build_yields() { return almanacYields(this.app.D).flatMap((s) => section(s)); }

  build_sources() {
    const host = h('div', h('p.dim', { role: 'status' }, '출처 목록을 불러오는 중…'));
    loadSources(this.app.D).then((S) => {
      clear(host);
      host.append(h('p.jump', h('a', { href: '../sources/' }, '출처와 이용조건 쪽 — 두 판 공용')));
      host.append(h('p.jump', h('a', { href: '../edu/' }, '교육의 활용 쪽 — 수업안과 교사용 안내 · 두 판 공용')));
      host.append(h('p.dim', '우리가 만든 코드·화면 디자인·문서·수업안은 Apache License 2.0 (저장소의 LICENSE). 자료와 글꼴에는 출처마다 각자의 조건이 있다. 착안한 원작 karpathy.ai/usaciv 는 공개된 이용허락 문서를 찾지 못했고, 원작의 코드·그림·자료는 가져오지 않았다.'));
      if (S && S.profile) host.append(profileNote(S.profile));
      if (!S) { host.append(h('p.warn', { role: 'alert' }, h('b', '불러오지 못함'), '출처 목록(data/sources.json)을 불러오지 못했습니다. 지도와 다른 갈피는 그대로 쓸 수 있습니다. 새로 고친 뒤 다시 열어 보십시오.')); return; }
      for (const r of S.restrictions) host.append(h('p.warn', { role: 'note' }, h('b', `이용조건 경고: ${r.title}`), r.text));
      const count = h('span.count', { role: 'status' });
      const input = h('input', { type: 'search', placeholder: '자료 · 기관 · 쓴 곳으로 거르기', 'aria-label': '출처 거르기' });
      const chips = h('div.chips', { role: 'group', 'aria-label': '갈래' });
      let group = '';
      const rows = S.list.map((x) => {
        const lic = h('td.lic',
          x.restriction ? h('p.warn', { role: 'note' }, h('b', '공개 배포 금지 — 내부 열람용'), x.restriction) : null,
          h('span', { class: x.unknown ? 'na' : 'licname' }, /^https?:/i.test(x.licenseUrl) ? safeLink(x.licenseUrl, x.license) : x.license),
          h('small', [x.licenseFrom, x.licenseBasis, x.licenseChecked ? `확인 ${x.licenseChecked}` : ''].filter(Boolean).join(' · ')),
          x.licenseNote ? h('small', x.licenseNote) : null,
          x.licenseCollected ? h('small', `수집 기록의 값(확인 표에서는 미확인): ${x.licenseCollected}`) : null,
          x.useScope ? h('small.unitnote', `사용 범위: ${x.useScope}`) : null);
        const tr = h('tr', { class: x.restriction ? 'restricted' : null },
          h('th', { scope: 'row' }, safeLink(x.url, x.title),
            h('small', [x.group, x.sha ? `sha256 ${x.sha}…` : '', x.files ? `파일 ${x.files}개` : '', x.manual ? `수작업 표: ${x.file}${x.basis ? ' — ' + x.basis : ''}` : '', x.derivedTable ? `정리표 ${x.derivedTable}` : ''].filter(Boolean).join(' · '))),
          h('td', x.publisher), h('td.when', x.vintage || h('span.na', '자료 없음'), x.retrieved ? h('small', `받은 날 ${x.retrieved}`) : null), lic, h('td', x.usedIn));
        return { tr, x, text: `${x.title} ${x.publisher} ${x.usedIn} ${x.license} ${x.licenseShort} ${x.key}`.toLowerCase() };
      });
      const apply = () => {
        const q = input.value.trim().toLowerCase();
        let n = 0;
        for (const r of rows) { const on = (!group || r.x.group === group) && (!q || r.text.includes(q)); r.tr.hidden = !on; if (on) n++; }
        count.textContent = `${n}건 / ${S.list.length}건 · 이용허락 미확인 ${S.unknownCount}건`;
      };
      const chip = (g, label) => h('button.btn', { type: 'button', 'aria-pressed': g === group ? 'true' : 'false', onclick: (e) => { group = g; for (const b of chips.children) b.setAttribute('aria-pressed', b === e.currentTarget ? 'true' : 'false'); apply(); } }, label);
      chips.append(chip('', '모두'), ...S.groups.map((g) => chip(g, g)));
      input.addEventListener('input', apply);
      host.append(h('p', S.licenseRule), h('div.filter', input, chips, count),
        h('div.tblwrap', h('table.tbl.src', h('thead', h('tr', ['자료', '기관', '기준', '이용허락', '쓴 곳'].map((t) => h('th', { scope: 'col' }, t)))), h('tbody', rows.map((r) => r.tr)))),
        h('ul.notes', S.notes.map((n) => h('li', n))),
        h('p.dim', S.attribution.rule));
      apply();
    });
    return [host];
  }

  build_notes() {
    const D = this.app.D, out = [];
    // 이 판 안내 (출처 목록을 받은 뒤 채운다)
    const ph = h('div.profilehost');
    out.push(ph);
    loadSources(D).then((S) => { if (S && S.profile) ph.append(profileNote(S.profile)); }).catch(() => {});
    out.push(...section({ h: '읽는 법', ul: [
      '모든 숫자는 자료에서 온다. 값이 없으면 어디서나 "자료 없음"이라고 적고 0 으로 적지 않는다.',
      '부분 합계(비공개 몫이 빠진 합)와 개편 전 행정구역 값에는 표식과 주석이 붙는다. 표식을 누르면 까닭이 나온다.',
      '멀리서는 먹판(땅의 높낮이·산줄기·물줄기)만 보이고, 다가가면 칸마다 토지피복 빛깔이 배어 나온다. 렌즈를 켜면 그 통계를 먹판 위에 한 판 더 찍는다(빛깔은 이 판의 안료 띠, 척도와 범위는 자료 그대로).',
      '지도 층의 아이콘은 배율에 따라 늘어난다. 규칙은 "지도 층" 갈피에 있다.',
    ] }));
    out.push(...section({ h: '자료가 아니라 그림인 것', ul: [
      '산줄기의 굵기 변화와 남동쪽 바림, 땅의 수묵 음영(칸 표고에서 셈한 빛 방향), 바닷가의 쪽빛 바림과 물결.',
      '이웃이 모두 바다인 작은 섬 칸은 칸 전체가 아니라 땅 비율만큼의 작은 섬으로 그린다. 값은 칸 값 그대로다.',
      '바다 이름 셋(동해·서해·남해)은 자료가 아니라 손으로 놓은 글자다.',
      '고을 이름표의 자리(여덟 방향 가운데 비는 곳)와 겹칠 때 숨는 순서는 배치 규칙이다. 숨은 고을도 찾기와 고을 목록에는 모두 있다.',
      '종이 결은 절차적으로 그린 무늬다. 그림 파일을 쓰지 않았다.',
    ] }));
    out.push(...section({ h: '두 판', p: ['신여지도는 같은 자료(site/data/*.json)를 읽는 두 번째 화면이다. 위 오른쪽 "koreaciv 판으로"를 누르면 같은 자리·같은 렌즈·같은 선택을 든 채 기존판으로 건너간다. 두 판의 숫자는 같은 파일에서 온다.'] }));
    if (D.failed.length) out.push(...section({ h: '이번에 불러오지 못한 자료', warn: [`${D.failed.map((f) => f + '.json').join(', ')} — 이 자료가 드는 곳은 비어 있거나 "자료 없음"으로 보인다.`] }));
    const host = h('div', h('h3', '글꼴', h('small', '모두 자체 호스팅')), h('p.dim', { role: 'status' }, '글꼴 목록을 불러오는 중…'));
    out.push(host);
    loadFontCredits().then(({ fonts, seal }) => {
      host.lastChild.remove();
      host.append(h('div.tblwrap', h('table.tbl', h('thead', h('tr', ['쓰임', '글꼴', '만든 이', '이용허락', '원본'].map((t) => h('th', { scope: 'col' }, t)))),
        h('tbody', fonts.map((f) => h('tr', h('th', { scope: 'row' }, f.role), h('td', f.family, f.note ? h('small', f.note) : null), h('td', f.author),
          h('td', f.licence, f.licenceFile ? h('small', /^[\w.-]+$/.test(f.licenceFile) ? h('a', { href: 'fonts/' + f.licenceFile, target: '_blank', rel: 'noopener' }, '전문 보기') : f.licenceFile) : null),
          h('td', safeLink(f.sourceUrl, '저장소'), f.sourceRef ? h('small', f.sourceRef) : null)))))));
      const han = fonts.find((f) => /新輿地圖/.test(f.role));
      host.append(h('p', `제호 곁의 한자 新輿地圖 는 ${han ? han.family : '목록의 붓글씨 글꼴'}에서 네 글자의 윤곽만 뽑아 엷게 놓은 것이다. 특정 서예가의 글씨나 서체를 본뜬 것이 아니며, 글씨를 바꿔 끼우는 법은 fonts/README.md 에 있다.`));
      if (seal) host.append(h('p.dim', `낙관: ${seal}`));
    }).catch(() => { host.lastChild.textContent = '글꼴 목록(fonts/fonts.json)을 불러오지 못했습니다. 글꼴 파일과 이용허락 전문은 fonts/ 폴더에 있습니다.'; host.lastChild.className = 'warn'; });
    return out;
  }
}
