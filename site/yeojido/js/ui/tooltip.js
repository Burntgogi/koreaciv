// 풍선말(마우스)과 칸 띠(손가락). 칸: 시도·시군구, 표고·지형, 피복, 켜진 렌즈의 값.
// 자료에서 온 글은 모두 텍스트 노드로 넣는다. 값이 없으면 '자료 없음'.

import { h, clear } from '../dom.js';
import { lensValues, lensUnitOf } from '../adapter.js';
import { lensValueUnit, fmtInt, fmtMan, NA } from '../fmt.js';
import { KINDS } from '../config.js';
import { iconEl } from '../icons.js';

export const PREC_KO = { point: '좌표', area: '경계 대표점', county: '시군구 대표 위치', sido: '시도 대표 위치', list: '목록만' };
const SUB = { forest: ['broadleaf', 'conifer', 'mixed'], crop: ['paddy', 'field', 'orchard', 'greenhouse'] };
const dim = (...k) => h('span.dim', ...k);

// 층 항목의 값 글 (없으면 null)
export function itemValueText(it) {
  const x = it.x || {};
  if (x.valueLabel) return x.valueLabel;
  if (it.group) return it.value == null ? null : `연구비 합 ${fmtInt(it.value / 1e8)}억 원`;
  if (it.value == null) return null;
  return `${it.value.toLocaleString('ko-KR')}${it.unit ? ' ' + it.unit : ''}`;
}

export class Tooltip {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('tip');
    this.strip = document.getElementById('cellstrip');
  }

  place(lines, x, y) {
    const el = this.el;
    clear(el);
    for (const l of lines) if (l) el.append(l instanceof Node ? l : h('div', l));
    el.hidden = false;
    const w = el.offsetWidth, hh = el.offsetHeight, vx = window.innerWidth, vy = window.innerHeight;
    el.style.left = Math.max(8, Math.min(vx - w - 8, x + 16)) + 'px';
    el.style.top = Math.max(8, y + 18 + hh > vy - 8 ? y - hh - 12 : y + 18) + 'px';
  }

  hide() {
    this.el.hidden = true;
    // 칸 띠는 짚은 칸이 풀렸을 때만 걷는다 (지도를 끌어도 남는다)
    if (!this.strip.hidden && !(this.app.pinCell >= 0)) { this.strip.hidden = true; clear(this.strip); }
  }

  showCity(c, x, y) {
    const s = this.app.D.stateByCode.get(c.sido);
    this.place([
      h('div.t', h('b', c.name), ' ', dim(s ? s.name : '')),
      h('div', '인구 ', c.pop == null ? h('span.na', NA) : `${fmtInt(c.pop)}명`),
      h('div.hint', '누르면 고을 장'),
    ], x, y);
  }

  showState(s, x, y) {
    this.place([h('div.t', h('b', s.name)), h('div', '인구 ', s.pop == null ? h('span.na', NA) : `${fmtInt(s.pop)}명`), h('div.hint', '누르면 시도 장')], x, y);
  }

  showItem(it, others, x, y) {
    const K = KINDS[it.kind] || { label: it.kind }, xx = it.x || {};
    const lines = [h('div.t', h('b', it.name), ' ', dim(it.group ? '대학 묶음 · 같은 칸·이웃 칸' : K.label + (it.kind === 'station' && xx.hsr ? ' · 고속철도' : '')))];
    if (it.group) {
      for (const m of it.memberItems || []) lines.push(h('div', m.name, ' ', dim(m.x && m.x.fundingWon != null ? `${fmtInt(m.x.fundingWon / 1e8)}억 원` : NA)));
    } else {
      if (xx.component) lines.push(dim(xx.component));
      const v = itemValueText(it);
      lines.push(h('div', v == null ? h('span.na', NA) : v, it.year && v != null && !String(v).includes(String(it.year)) ? dim(` (${it.year})`) : null));
      if (it.kind === 'airport' && xx.cargoT != null) lines.push(h('div', `화물 ${fmtInt(xx.cargoT)}톤`));
      if (it.kind === 'trade_port' && xx.teu != null) lines.push(h('div', `컨테이너 ${fmtInt(xx.teu)} TEU `, dim(xx.teuNote ? `(${xx.teuNote})` : '')));
    }
    lines.push(dim(`${it.place}${it.place ? ' · ' : ''}위치 ${PREC_KO[it.precision] || '자료 없음'}`));
    if (others && others.length) lines.push(h('div', dim(`같은 칸에 ${others.length}개 더: `), others.slice(0, 5).map((o) => o.name).join(', ') + (others.length > 5 ? ' …' : '')));
    lines.push(h('div.hint', '누르면 자세히'));
    this.place(lines, x, y);
  }

  showRoute(r, x, y) {
    const D = this.app.D, A = D.stateByCode.get(r.a), B = D.stateByCode.get(r.b), T = D.layers && D.layers.trade;
    const an = A ? A.short : r.a, bn = B ? B.short : r.b;
    const t = (v) => (v == null ? NA : `${fmtInt(v / 1e4)}만 톤`);
    this.place([
      h('div.t', h('b', `${an} – ${bn}`), ' ', dim(`교역로 · ${T ? T.mode : ''} ${T ? T.year : ''}`)),
      h('div', `두 방향 합 ${t(r.total)} `, dim(`(시도 간 ${r.rank}위${r.share != null ? ` · ${r.share}%` : ''})`)),
      dim(`${an}→${bn} ${t(r.ab)} · ${bn}→${an} ${t(r.ba)}`),
      h('div.hint', '누르면 구간 장'),
    ], x, y);
  }

  // 칸의 내용을 줄 묶음으로 (풍선말·칸 띠 공용). 반환 {title, sub, lines[], lensLine, unitNote, city, state}
  cellInfo(i) {
    const D = this.app.D, W = D.world, lens = this.app.lens;
    if (i < 0) return null;
    const elev = W.elevKnown[i] ? W.elev[i] : null;
    const out = { lines: [], city: null, state: null };
    if (W.owner[i] >= 0) {
      const st = D.stateOfCell(i), ct = D.countyOfCell(i), city = D.cityOfCell(i);
      out.city = city; out.state = st;
      out.title = `${st ? st.name : ''} · ${ct ? ct.name : ''}`;
      if (city && ct && city.name !== ct.name && !ct.name.startsWith(city.name)) out.sub = `고을: ${city.name}`;
      out.terrain = `${elev != null ? `표고 ${fmtInt(elev)} m` : '표고 자료 없음'} · ${W.reliefName(i) || ''}`;
      out.lines.push(out.terrain);
      if (W.water[i] === 3) out.lines.push('호수·저수지 칸');
      // 피복: 대분류 상위 셋. 도엽 통계 칸은 숲·농경지를 세부까지
      if (W.cover[i]) {
        const me = W.coverSrc[i] === 1;
        const top = W.coverKeys.map((k) => [k, W.share[k] ? W.share[k][i] : NaN]).filter(([, v]) => v > 0.005).sort((a, b) => b[1] - a[1]).slice(0, 3);
        const txt = top.map(([k, v]) => {
          let t = `${W.coverNames[k] || k} ${Math.round(v * 100)}%`;
          if ((me || W.coverPublic) && SUB[k]) {
            const parts = SUB[k].map((q) => [q, W.share[q] ? W.share[q][i] : NaN]).filter(([, w]) => w >= 0.01).sort((a, b) => b[1] - a[1]);
            if (parts.length) t += ` (${parts.map(([q, w]) => `${W.coverNames[q] || q} ${Math.round(w * 100)}`).join('·')})`;
          }
          return t;
        });
        const un = me && W.share.unclassified ? W.share.unclassified[i] : 0;
        out.cover = `피복 ${txt.join(' · ')}${un >= 0.005 ? ` · 미분류 ${Math.round(un * 100)}%` : ''}`;
        out.lines.push(out.cover);
        const src = W.coverSrcNames[W.coverSrc[i] - 1];
        if (src) out.coverSrc = (me || W.coverPublic ? '' : '도엽 통계가 닿지 않는 칸 — ') + src;
      }
      if (W.tidal[i] > 0) out.lines.push(`칸 넓이 중 갯벌 ${Math.round(W.tidal[i] * 100)}%${W.tidalMeta && W.tidalMeta.year ? ` (${W.tidalMeta.year})` : ''}`);
      const pop = D.lenses.cellPop[i];
      if (pop != null) out.lines.push(`칸 인구 ${fmtInt(pop)}명`);
      if (lens) {
        const v = lensValues(lens, W)[i];
        out.lens = { name: lens.name, text: lensValueUnit(v, lens), missing: v == null };
        const u = v != null ? lensUnitOf(lens, W.county[i]) : null;
        if (u && u.label) out.unitNote = u.label;
      }
    } else if (W.foreign[i]) {
      out.title = '외국 땅';
      out.sub = '통계 없음';
      out.lines.push(`${elev != null ? `표고 ${fmtInt(elev)} m` : '표고 자료 없음'} · ${W.reliefName(i) || ''}`);
    } else {
      out.title = W.waterName(i) || '바다';
      out.lines.push(elev != null ? `평균 수심 ${fmtInt(Math.max(0, -elev))} m` : '수심 자료 없음');
      if (W.tidal[i] > 0) out.lines.push(`칸 넓이 중 갯벌 ${Math.round(W.tidal[i] * 100)}%`);
    }
    return out;
  }

  showCell(i, x, y) {
    const c = this.cellInfo(i);
    if (!c) return this.hide();
    const lines = [h('div.t', h('b', c.title), c.sub ? [' ', dim(c.sub)] : null)];
    for (const l of c.lines) lines.push(h('div', l));
    if (c.coverSrc) lines.push(dim(c.coverSrc));
    if (c.lens) lines.push(h('div.lensv', `${c.lens.name} `, c.lens.missing ? h('span.na', NA) : h('b', c.lens.text)));
    if (c.unitNote) lines.push(h('div.unitnote', `↳ ${c.unitNote}`));
    if (c.city) lines.push(h('div.hint', '누르면 고을 장'));
    this.place(lines, x, y);
  }

  // 손가락: 빈 땅을 한 번 짚으면 도판 아래에 한 줄 띠 (장이 바로 덮지 않는다)
  pinCell(i) {
    const c = this.cellInfo(i), app = this.app, el = this.strip;
    this.el.hidden = true;
    clear(el);
    if (!c) { el.hidden = true; return; }
    const close = () => { app.pinCell = -1; this.hide(); app.requestDraw(); };
    app.pinCell = i;
    const info = h('div.info',
      h('b', c.city ? c.city.name : c.title),
      h('span', c.lens ? [`${c.lens.name} `, c.lens.missing ? h('span.na', NA) : h('em', c.lens.text), c.unitNote ? ' *' : null] : (c.terrain || c.lines[0] || '')));
    if (c.unitNote) info.title = c.unitNote;
    el.append(info);
    if (c.city) el.append(h('button.btn', { type: 'button', onclick: () => { const id = c.city.id; close(); app.selectCity(id, { fly: false }); } }, '고을 장'));
    if (c.state) el.append(h('button.btn', { type: 'button', onclick: () => { const code = c.state.code; close(); app.selectState(code, { fly: false }); } }, '시도 장'));
    el.append(h('button.x', { type: 'button', 'aria-label': '칸 띠 닫기', onclick: close }, iconEl('close', 18)));
    el.hidden = false;
    app.say(`${c.title}. ${c.lens ? `${c.lens.name} ${c.lens.text}` : c.terrain || ''}`);
  }
}
