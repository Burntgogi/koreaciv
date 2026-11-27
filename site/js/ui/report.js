// 순위 보고서: 상단 막대의 수치를 누르면 내려온다. 자료는 빌드가 만든 nation.json 의 reports (정의·구성·시도 순위·도시 순위).
// 한 번에 하나만 열린다. Esc 또는 바깥을 누르면 닫힌다. 행을 누르면 그 도시·시도로 이동해 패널을 연다.

import { fmtWon } from '../render/banners.js';
import { STATE_COLORS } from '../render/terrain.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
// 감사 07: 자료에서 온 글·id·숫자는 모두 esc 를 거쳐 잇는다. id 는 허용 형식만 (보고서·렌즈 id, 시도 코드, 도시 번호)
const ID_RE = /^[a-z][a-z0-9_]{0,40}$/;
const CODE_RE = /^\d{2}$/;
const pctW = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : 0);

export function fmtReport(v, f) {
  if (v == null) return '자료 없음';
  if (typeof v !== 'number') return String(v);   // 숫자가 아닌 값은 형식을 입히지 않고 글로 (호출하는 쪽이 esc 한다)
  if (f === 'won') return fmtWon(v) + (Math.abs(v) >= 1e4 && Math.abs(v) < 1e12 ? '원' : Math.abs(v) >= 1e12 ? ' 원' : '');
  if (f === 'pct1') return v.toFixed(1) + '%';
  if (f === 'f2') return v.toFixed(2);
  if (f === 'int') return Math.round(v).toLocaleString('ko-KR');
  return String(v);
}
const signed = (v, f) => (f === 'pct1' && v > 0 ? '+' : '') + fmtReport(v, f);
// 값과 단위를 한 번만 (감사 20): 형식이 이미 단위를 붙였으면(%, 원) 다시 붙이지 않는다
export function reportValueHTML(v, f, unit) {
  const t = fmtReport(v, f);
  const need = v != null && unit && f !== 'won' && !t.endsWith(unit);
  return `<b>${esc(t)}</b>${need ? ` <small>${esc(unit)}</small>` : ''}`;
}

export class Report {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('report');
    this.id = null;
    this.mode = 0;
    this.byId = new Map(((app.nation.reports || {}).items || []).filter((r) => r && ID_RE.test(String(r.id))).map((r) => [r.id, r]));
    this.el.addEventListener('click', (e) => {
      if (e.target.closest('[data-close]')) return this.close();
      const m = e.target.closest('[data-mode]');
      if (m) {
        this.mode = Number(m.dataset.mode);
        return this.render();
      }
      const lz = e.target.closest('[data-lens]');
      if (lz && ID_RE.test(lz.dataset.lens)) {
        app.setLens(lz.dataset.lens);
        return this.close();
      }
      const c = e.target.closest('[data-city]');
      if (c) {
        this.close();
        app.selectCity(Number(c.dataset.city), true);
        return app.panel.focus();
      }
      const s = e.target.closest('[data-state]');
      if (s && CODE_RE.test(s.dataset.state)) {
        this.close();
        app.selectState(s.dataset.state, true);
        return app.panel.focus();
      }
      if (e.target.closest('[data-nation]')) {
        this.close();
        app.showNation();
        app.panel.focus();
      }
    });
    // 보고서 안에서 다른 수치로 바꾸기 (좁은 화면에서 상단에 숨은 수치도, 감사 09)
    this.el.addEventListener('change', (e) => {
      const sel = e.target.closest('[data-report-pick]');
      if (sel) {
        this.open(sel.value);
        const s2 = this.el.querySelector('[data-report-pick]');
        if (s2) s2.focus();
      }
    });
    // 키보드: 행에 초점을 두고 Enter·Space 를 누르면 클릭과 같다 (감사 10)
    this.el.addEventListener('keydown', (e) => {
      if ((e.key === 'Enter' || e.key === ' ') && e.target.matches && e.target.matches('tr[data-city], tr[data-state]')) {
        e.preventDefault();
        e.target.click();
      }
    });
    // 바깥을 누르면 닫힌다 (상단 막대의 수치 단추는 그 단추가 처리)
    document.addEventListener('pointerdown', (e) => {
      if (!this.isOpen()) return;
      if (this.el.contains(e.target) || e.target.closest('#topbar .stats')) return;
      this.close();
    }, true);
  }

  isOpen() { return !this.el.hidden; }

  toggle(id) {
    if (this.isOpen() && this.id === id) return this.close();
    this.open(id);
  }

  open(id) {
    if (!this.byId.has(id)) return;
    if (this.id !== id) this.mode = 0;
    this.id = id;
    this.app.help.close();
    this.app.share.close();
    this.el.hidden = false;
    this.render();
    this.app.topbar.mark(id);
  }

  close() {
    if (this.el.hidden) return;
    this.el.hidden = true;
    this.app.topbar.mark(null);
  }

  render() {
    const a = this.app, r = this.byId.get(this.id);
    const m = r.modes[Math.min(this.mode, r.modes.length - 1)];
    const C = r.composition;
    const cmax = Math.max(...C.rows.map((x) => pctW(x.value))) || 1;
    // 구성비는 행들이 한 전체의 부분일 때만 (감사 23: 소멸위험지수의 분자·분모에는 붙이지 않음)
    const ctot = C.parts_of_whole === false ? 0 : C.rows.reduce((t, x) => t + (x.value || 0), 0);
    const comp = `<div class="rbars">${C.rows.map((x) => `<div class="rb"><span class="lab">${esc(x.label)}</span><span class="bar"><i style="width:${x.value == null ? 0 : Math.max(0.5, (100 * pctW(x.value)) / cmax)}%"></i></span>
      <span class="val">${x.value == null ? '<span class="na">비공개</span>' : esc(fmtReport(x.value, C.unit === '원' ? 'won' : 'int'))}${x.value != null && ctot ? ` <small>${((100 * pctW(x.value)) / ctot).toFixed(1)}%</small>` : ''}</span></div>`).join('')}</div>`;
    const smax = Math.max(...m.sido.map((x) => Math.abs(pctW(x.value)))) || 1;
    const sname = (code) => (a.stateByCode.get(code) || {}).short || code;
    const sido = m.sido.filter((x) => CODE_RE.test(String(x.code))).map((x) => `<tr data-state="${esc(x.code)}" tabindex="0" role="button" aria-label="${esc(sname(x.code))} ${x.value == null ? '자료 없음' : esc(signed(x.value, m.format))} — 시도 패널 열기"><td class="no">${esc(x.rank ?? '–')}</td><td><i style="background:${STATE_COLORS[x.code] || '#999'}"></i>${esc(sname(x.code))}${x.note ? ` <sup title="${esc(x.note)}">합</sup>` : ''}</td>
      <td class="barc"><span class="bar"><i style="width:${x.value == null ? 0 : Math.max(0.5, (100 * Math.abs(pctW(x.value))) / smax)}%"></i></span></td><td class="num">${x.value == null ? '<span class="na">자료 없음</span>' : esc(signed(x.value, m.format))}</td></tr>`).join('');
    const cn = (id) => (a.cityById.get(id) || {}).name || id;
    const crow = (x) => (Number.isInteger(x.id) ? `<tr data-city="${x.id}" tabindex="0" role="button" aria-label="${esc(cn(x.id))} ${esc(signed(x.value, m.format))} — 도시 패널 열기"><td class="no">${esc(x.rank)}</td><td>${esc(cn(x.id))} <small>${esc((a.stateByCode.get((a.cityById.get(x.id) || {}).sido) || {}).short || '')}</small></td>
      <td class="num">${esc(signed(x.value, m.format))}${x.partial ? '<sup class="pm" title="부분 합: 광업이 비공개인 공표 단위의 광업 몫을 뺌">*</sup>' : ''}</td></tr>` : '');
    const CR = m.cities;
    const gap = CR.bottom.length && CR.bottom[0].rank > (CR.top[CR.top.length - 1] || { rank: 0 }).rank + 1;
    const notes = [];
    if (CR.excluded) notes.push(`값이 없는 도시 ${esc(CR.excluded)}곳은 순위에서 뺐다${CR.excluded_names && CR.excluded_names.length <= 12 ? ` (${CR.excluded_names.map(esc).join(', ')})` : ''}.`);
    if (CR.filtered_small) notes.push(`인구 ${esc(Number(a.nation.reports.per_capita_min_pop).toLocaleString('ko-KR'))}명 미만 도시 ${esc(CR.filtered_small)}곳은 이 순위에 넣지 않았다.`);
    if (CR.top.concat(CR.bottom).some((x) => x.partial)) notes.push('* 부분 합 (비공개 몫 제외).');
    const lens = r.lens && a.lensById.has(r.lens) ? a.lensById.get(r.lens) : null;
    this.el.innerHTML = `<div class="rhead"><h3>${esc(r.emoji)} ${esc(r.name)} <small>${esc(r.year)} · ${esc(r.source)}</small></h3>
        <div class="rtools"><select data-report-pick aria-label="다른 순위 보고서">${[...this.byId.values()].map((x) => `<option value="${esc(x.id)}"${x.id === r.id ? ' selected' : ''}>${esc(x.emoji)} ${esc(x.name)}</option>`).join('')}</select>${lens && ID_RE.test(lens.id) ? `<button data-lens="${esc(lens.id)}" class="lensbtn">${esc(lens.emoji)} 지도에서 보기 <small>${esc(lens.name)} 렌즈</small></button>` : ''}<button data-close title="닫기 (Esc)" class="x">×</button></div></div>
      <div class="rbody">
        <p class="def">${esc(r.definition)}</p>
        <div class="rnat"><em>전국</em>${reportValueHTML(r.national, r.format, r.unit)}<button type="button" class="linkbtn" data-nation>전국 보고서 패널 ›</button></div>
        <h4>${esc(C.title)}</h4>${comp}${C.formula ? `<p class="def">지수 = ${esc(C.formula)}</p>` : ''}
        ${r.modes.length > 1 ? `<div class="modes" role="tablist">${r.modes.map((x, k) => `<button data-mode="${k}" role="tab" aria-selected="${k === this.mode}" class="${k === this.mode ? 'on' : ''}">${esc(x.label)}</button>`).join('')}</div>` : ''}
        <div class="rcols">
          <div><h4>시도 <small>${esc(m.sido.length)}곳 · ${esc(m.label)}</small></h4><table class="rt"><tbody>${sido}</tbody></table></div>
          <div><h4>도시 <small>상위 8 · 하위 3 / ${esc(CR.n)}곳</small></h4><table class="rt"><tbody>${CR.top.map(crow).join('')}${gap ? '<tr class="gap"><td></td><td>…</td><td></td></tr>' : ''}${CR.bottom.map(crow).join('')}</tbody></table></div>
        </div>
        <p class="rule">${esc(m.rule)}${notes.length ? ' ' + notes.join(' ') : ''}</p>
        <p class="rule">행을 누르면 그 시도·도시로 이동해 패널을 연다.</p>
      </div>`;
  }
}
