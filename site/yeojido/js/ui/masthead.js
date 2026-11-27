// 나라 장부(위 여백의 여덟 수치)와 순위 보고서 서랍.
// 수치를 누르면 그 수치의 순위 보고서가 장부 아래로 내려온다. 한 줄에 들어가지 않는 수치는 '순위' 단추 뒤로 접히고,
// 서랍 안의 여덟 갈래 전환으로 어느 폭에서나 모두 닿는다. 자료 모양은 adapter/reports.js 가 읽는다.

import { reportsModel, nationHead, reportParts, ledgerParts } from '../adapter.js';
import { h, clear, numEl, na } from '../dom.js';
import { iconEl } from '../icons.js';
import { fmtWhen, fmtInt } from '../fmt.js';
import { openModal, closeModal, isOpen } from './modal.js';

const COMP_TOP = 6; // 구성 막대를 처음에 몇 줄 보일지

export class Masthead {
  constructor(app) {
    this.app = app;
    this.R = reportsModel(app.D);
    this.id = null;
    this.mode = 0;
    this.drawer = document.getElementById('drawer');
    this.drawer.setAttribute('aria-label', '순위 보고서');
    this.buildNation();
    this.buildLedger();
    app.on('resize', () => this.fit());
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => this.fit());
    // 바깥을 누르면 닫힌다 (장부 단추는 그 단추가 처리)
    document.addEventListener('pointerdown', (e) => {
      if (!this.id || this.drawer.contains(e.target) || e.target.closest('#ledger')) return;
      this.closeReport();
    }, true);
  }

  buildNation() {
    const nh = nationHead(this.app.D), b = document.getElementById('nationbtn');
    clear(b).append(h('b', nh.name), h('span', nh.vintage ? `${fmtWhen(nh.vintage)} 판` : '기준 시점 자료 없음'));
    b.title = '전국 장 열기';
    b.setAttribute('aria-label', `${nh.name} — 전국 장 열기`);
    b.addEventListener('click', () => { this.closeReport(true); this.app.showNation(); });
  }

  buildLedger() {
    const el = document.getElementById('ledger');
    clear(el);
    this.figs = this.R.list.map((r) => {
      const p = ledgerParts(r);
      const b = h('button.fig', { type: 'button', 'aria-haspopup': 'dialog', title: `${r.name} 순위 보고서`, dataset: { report: r.id }, onclick: () => this.toggleReport(r.id) },
        h('span.kicker', iconEl(r.icon, 13), r.name), p ? numEl(p) : na());
      el.append(b);
      return b;
    });
    this.more = h('button.fig.more', { type: 'button', 'aria-haspopup': 'dialog', title: '순위 보고서 여덟 가지', onclick: () => this.toggleReport(this.id || (this.R.list[0] && this.R.list[0].id)) },
      h('span.kicker', '장부'), h('span.num', h('span.lbl', '순위'), iconEl('down', 12)));
    if (this.R.list.length) el.append(this.more);
    else el.append(h('span.na', '나라 장부 자료 없음'));
    this.fit();
  }

  // 한 줄에 들어가는 만큼만 보이고 나머지는 '순위' 단추 뒤로
  fit() {
    const el = document.getElementById('ledger');
    if (!this.figs || !this.figs.length) return;
    const narrow = window.innerWidth <= 700;
    for (const f of this.figs) f.hidden = false;
    this.more.hidden = false;
    const avail = el.clientWidth;
    const mw = this.more.offsetWidth + 4;
    let used = 0, n = 0;
    if (!narrow) {
      const ws = this.figs.map((f) => f.offsetWidth + 4);
      const total = ws.reduce((a, b) => a + b, 0);
      if (total <= avail) n = ws.length;
      else for (const w of ws) { if (used + w + mw > avail) break; used += w; n++; }
    }
    this.figs.forEach((f, k) => { f.hidden = k >= n; });
    this.more.hidden = n === this.figs.length;
    this.more.classList.toggle('only', n === 0);
    this.more.querySelector('.lbl').textContent = narrow ? '장부' : '순위';
    this.more.setAttribute('aria-label', n === 0 ? '나라 장부와 순위 보고서 여덟 가지' : '나머지 순위 보고서');
  }

  update() { this.fit(); this.mark(); }
  mark() {
    for (const f of this.figs || []) f.classList.toggle('is-on', f.dataset.report === this.id);
    if (this.more) this.more.classList.toggle('is-on', !!this.id && (this.figs.find((f) => f.dataset.report === this.id) || {}).hidden !== false);
  }

  reportId() { return this.id; }
  closeTransient() { if (!this.id) return false; this.closeReport(); return true; }

  toggleReport(id) { if (this.id === id) this.closeReport(); else this.openReport(id); }

  openReport(id, silent) {
    if (!this.R.byId.has(id)) return false;
    const app = this.app;
    if (this.id !== id) this.mode = 0;
    const was = this.id;
    this.id = id;
    if (!silent && app.sel.type) app.clearSelection(); // 보고서를 여는 동안 장은 닫는다
    this.render();
    if (!was || !isOpen(this.drawer)) {
      const prev = document.activeElement;
      openModal(this.drawer, { trap: !silent, initial: silent ? this.drawer : this.drawer.querySelector('.rtab[aria-selected="true"]'), onClose: () => { this.id = null; this.mark(); app.requestDraw(); } });
      if (silent && prev && prev.focus && prev !== document.body) prev.focus({ preventScroll: true });
    }
    this.mark();
    app.requestDraw(); // 해시 갱신
    return true;
  }

  closeReport(silent) {
    if (!this.id && this.drawer.hidden) return;
    closeModal(this.drawer, !silent);
    this.id = null;
    this.mark();
  }

  go(fn) { this.closeReport(true); fn(); const p = document.getElementById('panel'); if (p && !p.hidden) { const f = p.querySelector('button, a[href], [tabindex]'); (f || p).focus && (f || p).focus({ preventScroll: true }); } }

  render() {
    const app = this.app, D = app.D, r = this.R.byId.get(this.id), el = this.drawer;
    const mode = r.modes[Math.min(this.mode, r.modes.length - 1)] || null;
    const val = (v, f, u) => { const p = reportParts(v, f, u); return p ? h('span.v', p[0], p[1] ? h('small', p[1]) : null) : na(); };
    const signed = (v, f, u) => { const p = reportParts(v, f, u); if (!p) return na(); return h('span.v', (f === 'pct1' && v > 0 && /증|감/.test((mode && mode.label) || '') ? '+' : '') + p[0], p[1] ? h('small', p[1]) : null); };

    // 여덟 갈래 전환
    const tabs = h('div.rtabs', { role: 'tablist', 'aria-label': '순위 보고서 고르기' }, this.R.list.map((x) => h('button.rtab', { type: 'button', role: 'tab', 'aria-selected': String(x.id === r.id), tabindex: x.id === r.id ? '0' : '-1', dataset: { id: x.id },
      onclick: () => { this.openReport(x.id); const t = el.querySelector('.rtab[aria-selected="true"]'); if (t) t.focus(); } }, iconEl(x.icon, 14), x.name)));
    tabs.addEventListener('keydown', (e) => {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft' && e.key !== 'Home' && e.key !== 'End') return;
      e.preventDefault();
      const L = this.R.list, k = L.findIndex((x) => x.id === this.id);
      const n = e.key === 'Home' ? 0 : e.key === 'End' ? L.length - 1 : (k + (e.key === 'ArrowRight' ? 1 : -1) + L.length) % L.length;
      this.openReport(L[n].id);
      const t = el.querySelector('.rtab[aria-selected="true"]'); if (t) { t.focus(); t.scrollIntoView({ block: 'nearest', inline: 'nearest' }); }
    });
    const lens = r.lens && D.lenses.byId.get(r.lens);
    const head = h('header.rhead',
      h('div.rname', h('h2', r.name), h('p.rsrc', [r.year ? fmtWhen(r.year) : '', r.source].filter(Boolean).join(' · '))),
      h('div.rnat', h('span.kicker', '전국'), numEl(reportParts(r.national, r.format, r.unit))),
      h('button.x', { type: 'button', 'aria-label': '순위 보고서 닫기', title: '닫기 (Esc)', onclick: () => this.closeReport() }, iconEl('close', 18)));

    // 구성
    const C = r.composition, rows = C.rows;
    const cmax = Math.max(0, ...rows.map((x) => x.value || 0)) || 1;
    const ctot = C.partsOfWhole ? rows.reduce((t, x) => t + (x.value || 0), 0) : 0;
    const cfmt = C.unit === '원' ? 'won' : 'int';
    const crow = (x) => h('li', h('span.lab', x.label), h('span.bar', h('i', { style: { width: (x.value == null ? 0 : Math.max(0.5, (100 * x.value) / cmax)) + '%' } })),
      x.value == null ? h('span.na', '비공개') : h('span.cv', val(x.value, cfmt, C.unit)), h('span.pc', x.value != null && ctot ? ((100 * x.value) / ctot).toFixed(1) + '%' : ''));
    const comp = h('section.rcomp', h('h3', C.title || '구성'), h('ul.rbars', rows.slice(0, COMP_TOP).map(crow)),
      rows.length > COMP_TOP ? h('details', h('summary', `나머지 ${rows.length - COMP_TOP}줄 펼치기`), h('ul.rbars', rows.slice(COMP_TOP).map(crow))) : null,
      C.formula ? h('p.rnote', '지수 = ', C.formula) : null);

    // 방식 전환 (총량 / 1인당 …)
    const modes = r.modes.length > 1 ? h('div.rmodes', { role: 'group', 'aria-label': '순위 방식' }, r.modes.map((m, k) => h('button.btn', { type: 'button', 'aria-pressed': String(k === this.mode), onclick: () => { this.mode = k; this.render(); const b = el.querySelectorAll('.rmodes .btn')[k]; if (b) b.focus(); } }, m.label))) : null;

    let cols = null, notes = [];
    if (mode) {
      const smax = Math.max(0, ...mode.sido.map((x) => Math.abs(x.value || 0))) || 1;
      const sname = (code) => (D.stateByCode.get(code) || {}).short || code;
      const srow = (x) => h('li', h('button.rrow', { type: 'button', title: x.note || null, 'aria-label': `${x.rank ?? '순위 없음'}위 ${sname(x.key)} — 시도 장 열기`, onclick: () => this.go(() => app.selectState(x.key, { fly: true })) },
        h('span.no', x.rank ?? '–'), h('span.nm', sname(x.key), x.note ? h('sup', { title: x.note }, '합') : null),
        h('span.bar', h('i', { style: { width: (x.value == null ? 0 : Math.max(0.5, (100 * Math.abs(x.value)) / smax)) + '%' } })), signed(x.value, mode.format, mode.unit)));
      const cityRow = (x) => {
        const c = D.cityById.get(x.key), st = c ? D.stateByCode.get(c.sido) : null;
        return h('li', h('button.rrow.city', { type: 'button', 'aria-label': `${x.rank}위 ${c ? c.name : x.key} — 고을 장 열기`, onclick: () => this.go(() => app.selectCity(x.key, { fly: true })) },
          h('span.no' + (x.rank <= 3 ? '.top' : ''), x.rank ?? '–'), h('span.nm', c ? c.name : String(x.key), st && st.short !== c.name ? h('small', st.short) : null),
          h('span.vv', signed(x.value, mode.format, mode.unit), x.partial ? h('sup.pm', { title: '부분 합: 광업이 비공개인 공표 단위의 광업 몫을 뺌' }, '*') : null)));
      };
      const CR = mode.cities;
      const lastTop = CR.top.length ? CR.top[CR.top.length - 1].rank : 0;
      const gap = CR.bottom.length && CR.bottom[0].rank > lastTop + 1;
      cols = h('div.rcols',
        h('section', h('h3', '시도', h('small', `${mode.sido.length}곳 · ${mode.label}`)), h('ol.rlist', mode.sido.map(srow))),
        h('section', h('h3', '고을', h('small', `위 ${CR.top.length} · 아래 ${CR.bottom.length}${CR.n != null ? ` / ${CR.n}곳` : ''}`)),
          h('ol.rlist', CR.top.map(cityRow), gap ? h('li.gap', { 'aria-hidden': 'true' }, '· · ·') : null, CR.bottom.map(cityRow))));
      if (mode.rule) notes.push(mode.rule);
      if (CR.excluded) notes.push(`값이 없는 고을 ${CR.excluded}곳은 순위에서 뺐다${CR.excludedNames.length && CR.excludedNames.length <= 12 ? ` (${CR.excludedNames.join(', ')})` : ''}.`);
      if (CR.filteredSmall) notes.push(`인구 ${this.R.perCapitaMinPop != null ? fmtInt(this.R.perCapitaMinPop) : '기준'}명 미만 고을 ${CR.filteredSmall}곳은 이 순위에 넣지 않았다.`);
      if (CR.top.concat(CR.bottom).some((x) => x.partial)) notes.push('* 부분 합 (비공개 몫 제외).');
      if (mode.sido.some((x) => x.note)) notes.push("'합' 표시는 따로 공표된 값을 더한 시도다 (단추에 마우스를 올리면 설명).");
    }
    const acts = h('div.racts',
      lens ? h('button.btn.lensbtn', { type: 'button', onclick: () => { this.closeReport(); app.setLens(lens.id); } }, iconEl('layers', 14), `지도에서 보기 — ${lens.name} 렌즈`) : null,
      h('button.btn', { type: 'button', onclick: () => this.go(() => app.showNation()) }, '전국 장', iconEl('arrow', 14)));

    clear(el).append(tabs, h('div.rbody', head, h('p.rdef', r.definition), comp, modes, cols,
      notes.length ? h('p.rnote', notes.join(' ')) : null, this.R.rule && r.modes.length > 1 ? h('p.rnote', this.R.rule) : null, acts));
    el.scrollTop = 0;
  }
}
