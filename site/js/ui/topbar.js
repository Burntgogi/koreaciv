// 상단 띠: 전국 인구 지표 + 다섯 산출(금은 조 원). 수치를 누르면 그 수치의 순위 보고서가 내려온다(report.js).
// '기준' 칸은 전국 보고서 패널. 오른쪽: 찾기 · 연감 · 공유 · 도움말.

import { fmtMan, fmtWon, partialNote, YIELD_ICONS } from '../render/banners.js';

const YNAME = { food: '식량', production: '생산', gold: '금', science: '과학', culture: '문화' };
// 보고서 id 허용 형식 (nation.reports 의 id 만 쓴다)
const REPORT_ID = /^[a-z][a-z0-9_]{0,40}$/;
// 작은 DOM 도우미: 글은 텍스트 노드로, 속성은 setAttribute 로만 넣는다
function el_(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v != null) e.setAttribute(k, String(v));
  for (const k of kids) if (k != null) e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return e;
}

export class Topbar {
  constructor(app) {
    this.app = app;
    const n = app.nation.nation;
    const el = document.getElementById('topbar');
    this.el = el;
    // 전국 산출은 공식값(지역소득, 광업 포함). 시군구 합은 툴팁에 함께 적는다
    // 감사 07: 자료 글(연도·이름·이모지·기준 시점)은 HTML 로 잇지 않고 노드·textContent·속성 대입으로 넣는다. 보고서 id 는 허용 목록(nation.reports)과 형식으로 거른다
    const OG = n.official && n.official.gdp;
    const num = (v, f) => (typeof v === 'number' && Number.isFinite(v) ? f(v) : '–');
    const stat = (report, title, label, value, extra) => {
      const b = el_('button', { class: 'st' + (report && YNAME[report] ? ' y' : '') + (extra && extra.cls ? ' ' + extra.cls : ''), title });
      if (report) b.dataset.report = report;
      b.append(el_('em', null, label), el_('b', null, value));
      if (extra && extra.small != null) b.append(el_('small', null, extra.small));
      return b;
    };
    el.replaceChildren();
    const brand = el_('div', { class: 'brand' });
    const altA = el_('a', { class: 'altfe', href: 'yeojido/index.html', title: '같은 위치·선택을 신여지도 화면으로 열기 (주소 해시를 그대로 넘김)' }, '⇄ 신여지도');
    altA.hidden = true;
    brand.append(el_('span', { class: 'logo' }, '⬢'), el_('div', null, el_('b', null, 'koreaciv'), el_('small', null, '대한민국 전략 지도'), altA));
    const stats = el_('div', { class: 'stats', role: 'group', 'aria-label': '전국 수치 (누르면 순위 보고서)' });
    stats.append(stat('population', '인구 순위 보고서', '인구', fmtMan(n.population)),
      stat('over65', '고령 비율 순위 보고서', '고령 비율', num(n.age && n.age.over65, (v) => v.toFixed(1) + '%')),
      stat('extinction', '소멸위험지수 순위 보고서', '소멸위험지수', num(n.extinction_index, (v) => v.toFixed(2))));
    if (OG) {
      for (const [k, ic] of YIELD_ICONS) {
        const pn = partialNote(n, k);
        const sg = n.yields ? n.yields[k] : null;
        const tip = `${YNAME[k]} · 공식 전국값 (지역소득 ${OG.year}) · 시군구 합 ${sg == null ? '자료 없음' : fmtWon(sg)}${pn ? ` (${pn})` : ''}${OG.latest ? ` · ${OG.latest.label} ${fmtWon(OG.latest.yields[k])}` : ''} — 누르면 순위 보고서`;
        stats.append(stat(k, tip, `${ic} ${YNAME[k]}`, OG.yields[k] == null ? '–' : fmtWon(OG.yields[k])));
      }
    }
    const more = el_('button', { class: 'st more', 'aria-haspopup': 'menu', 'aria-expanded': 'false', title: '순위 보고서 전체 (좁은 화면에서 숨긴 수치 포함)' }, el_('em', null, '순위 보고서'), el_('b', null, '전체 ▾'));
    more.dataset.reportsMenu = '';
    const vint = el_('button', { class: 'st vintage', title: '전국 보고서 패널 열기' }, el_('em', null, '기준'), el_('b', null, String(app.nation.vintage ?? '')), el_('small', null, `GRDP ${OG ? `공식 ${OG.year}` : n.gdp_year_label || ''}`));
    vint.dataset.nation = '';
    stats.append(more, vint);
    const tools = el_('div', { class: 'tools' },
      el_('button', { id: 'search-btn', title: '도시·시도 찾기 ( / )' }, '🔍 ', el_('span', null, '찾기'), el_('kbd', null, '/')),
      el_('button', { id: 'almanac-btn', title: '지형 규칙·렌즈 정의·산출·출처' }, '📖 ', el_('span', null, '연감')),
      el_('button', { id: 'share-btn', title: '공유: 링크 복사 · PNG 내려받기', 'aria-haspopup': 'menu' }, '📤 ', el_('span', null, '공유')),
      el_('button', { id: 'help-btn', title: '조작 안내 ( ? )', 'aria-label': '조작 안내' }, '?'));
    el.append(brand, stats, tools);
    // 좁은 화면(1250px 이하)에서 숨긴 수치까지 모든 순위 보고서를 고르는 메뉴 (감사 09)
    this.menu = document.createElement('div');
    this.menu.id = 'repmenu';
    this.menu.hidden = true;
    this.menu.setAttribute('role', 'menu');
    const reps = ((app.nation.reports || {}).items || []).filter((r) => r && typeof r.id === 'string' && REPORT_ID.test(r.id));
    for (const r of reps) {
      const b = el_('button', { type: 'button', role: 'menuitem' }, `${r.emoji ?? ''} ${r.name ?? r.id}`);
      b.dataset.pick = r.id;
      this.menu.append(b);
    }
    document.body.appendChild(this.menu);
    this.menu.addEventListener('click', (e) => {
      const b = e.target.closest('[data-pick]');
      if (!b || !REPORT_ID.test(b.dataset.pick)) return;
      this.closeMenu();
      app.report.open(b.dataset.pick);
      const first = app.report.el.querySelector('select, button');
      if (first) first.focus();
    });
    document.addEventListener('pointerdown', (e) => {
      if (!this.menu.hidden && !this.menu.contains(e.target) && !e.target.closest('[data-reports-menu]')) this.closeMenu();
    }, true);
    el.querySelector('.stats').addEventListener('click', (e) => {
      const mb = e.target.closest('[data-reports-menu]');
      if (mb) return this.menu.hidden ? this.openMenu(mb) : this.closeMenu();
      const b = e.target.closest('[data-report]');
      if (b) return app.report.toggle(b.dataset.report);
      if (e.target.closest('[data-nation]')) {
        app.report.close();
        app.showNation();
      }
    });
    // 다른 화면(신여지도, site/yeojido/)으로 같은 해시를 들고 가는 고리. 폴더가 없으면(HEAD 실패) 보이지 않는다
    const alt = el.querySelector('.altfe');
    const syncAlt = () => { alt.href = 'yeojido/index.html' + (app.lastHash || location.hash || ''); };
    for (const ev of ['pointerdown', 'focus', 'click']) alt.addEventListener(ev, syncAlt);
    fetch('yeojido/index.html', { method: 'HEAD', cache: 'no-cache' })
      .then((r) => { if (r.ok) { alt.hidden = false; el.querySelector('.brand').classList.add('has-alt'); } })
      .catch(() => {});
    el.querySelector('#search-btn').addEventListener('click', () => app.search.open());
    el.querySelector('#almanac-btn').addEventListener('click', () => app.almanac.open());
    el.querySelector('#share-btn').addEventListener('click', (e) => app.share.toggle(e.currentTarget));
    el.querySelector('#help-btn').addEventListener('click', () => app.help.toggle());
  }

  openMenu(btn) {
    const r = btn.getBoundingClientRect();
    this.menu.style.top = `${r.bottom + 6}px`;
    this.menu.style.left = `${Math.max(6, Math.min(window.innerWidth - 200, r.left))}px`;
    this.menu.hidden = false;
    btn.setAttribute('aria-expanded', 'true');
    this.menu.querySelector('button').focus();
  }

  closeMenu() {
    this.menu.hidden = true;
    const b = this.el.querySelector('[data-reports-menu]');
    if (b) b.setAttribute('aria-expanded', 'false');
  }

  mark(id) {
    for (const b of this.el.querySelectorAll('[data-report]')) b.classList.toggle('on', b.dataset.report === id);
  }
}
