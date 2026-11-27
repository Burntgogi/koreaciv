// 칸 위 툴팁: 시도·시군구, 표고, 지형, 켜진 렌즈의 값

import { unitOf, valueWithUnit } from '../render/lens.js';
import { fmtMan, fmtWon, partialNote } from '../render/banners.js';
import { KINDS, PLACE_FROM, precisionText } from '../render/layers.js';

const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
export function itemValue(it) {
  if (it.value_label) return it.value_label;
  if (it.value == null) return null;
  const v = typeof it.value === 'number' ? it.value.toLocaleString('ko-KR') : it.value;
  return `${v}${it.unit ? ' ' + it.unit : ''}`;
}

const RELIEF = ['평지', '구릉', '산', '고봉'];
export const COVER_KO = { forest: '숲', crop: '농경지', built: '시가지', grass: '초지', wetland: '습지', bare: '나지', water: '수면',
  broadleaf: '활엽수림', conifer: '침엽수림', mixed: '혼효림', paddy: '논', field: '밭', orchard: '과수원', greenhouse: '시설재배지', unclassified: '미분류' };

export class Tooltip {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('tooltip');
  }

  place(html, x, y) {
    const el = this.el;
    el.innerHTML = html;
    el.hidden = false;
    const w = el.offsetWidth, h = el.offsetHeight;
    const vx = window.innerWidth, vy = window.innerHeight;
    el.style.left = Math.min(vx - w - 8, x + 16) + 'px';
    el.style.top = Math.min(vy - h - 8, y + 16) + 'px';
  }

  hide() { this.el.hidden = true; }

  showCity(c, x, y) {
    const s = this.app.stateByCode.get(c.sido);
    const pv = c.yields ? c.yields.production : null, pn = partialNote(c, 'production');
    const prod = c.yields ? `<br>⚙️ 생산 ${pv == null ? '자료 없음' : fmtWon(pv)}${pn ? ` <span class="dim">* ${esc(pn)}</span>` : ''} · 💰 ${fmtWon(c.gdp)}` : '';
    this.place(`<b>${esc(c.name)}</b> <span class="dim">${esc(s ? s.name : '')}</span><br>인구 ${esc(c.population.toLocaleString('ko-KR'))}명 (${esc(fmtMan(c.population))})${prod}
      <br><span class="dim">누르면 도시 패널</span>`, x, y);
  }

  showItem(it, others, x, y, ox = false) {
    const K = KINDS[it.kind];
    if (it.group) {
      const eok = (v) => (v == null ? '자료 없음' : Math.round(v / 1e8).toLocaleString('ko-KR') + '억원');
      const ms = it.memberItems || [];
      this.place(`<b>${esc(it.name)}</b> <span class="dim">대학 묶음 · 같은 칸·이웃 칸</span><br>${ms.map((m) => `${esc(m.name)} <span class="dim">${eok(m.funding_won)}</span>`).join('<br>')}
        <br><span class="dim">위치 ${esc(precisionText(it))}</span><br><span class="dim">누르면 목록</span>`, x, y);
      return;
    }
    const v = itemValue(it);
    const lines = [`<b>${esc(it.name)}</b> <span class="dim">${esc(K ? K.label : it.kind)}${it.kind === 'station' && it.hsr ? ' · 고속철도' : ''}</span>`];
    if (it.component) lines.push(`<span class="dim">${esc(it.component)}</span>`);
    if (v) lines.push(`${esc(v)}${it.year ? ` <span class="dim">(${esc(it.year)})</span>` : ''}`);
    if (it.kind === 'airport' && it.cargo_t != null) lines.push(`화물 ${it.cargo_t.toLocaleString('ko-KR')}톤`);
    if (it.kind === 'trade_port' && it.teu != null) lines.push(`컨테이너 ${it.teu.toLocaleString('ko-KR')} TEU <span class="dim">(${esc(it.teu_note)})</span>`);
    lines.push(`<span class="dim">${esc(it.place)} · 위치 ${esc(precisionText(it))}${it.place_from ? ' · ' + esc(PLACE_FROM[it.place_from]) : ''}</span>`);
    if (ox) lines.push('<span class="unitnote">깃발과 겹쳐 옆 칸에 표시 (원래 위치는 선 끝 점)</span>');
    if (others && others.length) {
      lines.push(`<span class="dim">같은 칸에 ${others.length}개 더:</span> ${others.slice(0, 5).map((o) => esc(o.name)).join(', ')}${others.length > 5 ? ' …' : ''}`);
    }
    lines.push('<span class="dim">누르면 자세히</span>');
    this.place(lines.join('<br>'), x, y);
  }

  // 교역로 구간: 두 시도, 두 방향 톤, 순위
  showRoute(r, x, y) {
    const a = this.app, A = a.stateByCode.get(r.a), B = a.stateByCode.get(r.b);
    const t = (v) => `${(v / 1e4).toLocaleString('ko-KR', { maximumFractionDigits: 0 })}만 톤`;
    this.place(`<b>${esc(A.short)} – ${esc(B.short)}</b> <span class="dim">교역로 · 도로 화물 2024</span><br>두 방향 합 ${t(r.total)} <span class="dim">(시도 간 ${r.rank}위 · ${r.share}%)</span>
      <br><span class="dim">${esc(A.short)}→${esc(B.short)} ${t(r.ab)} · ${esc(B.short)}→${esc(A.short)} ${t(r.ba)}</span><br><span class="dim">누르면 구간 패널</span>`, x, y);
  }

  showState(s, x, y) {
    this.place(`<b>${esc(s.name)}</b><br>인구 ${esc(s.population.toLocaleString('ko-KR'))}명<br><span class="dim">누르면 시도 패널</span>`, x, y);
  }

  showCell(i, x, y) {
    const a = this.app, w = a.world;
    if (i < 0) return this.hide();
    const lines = [];
    const elev = w.elev[i];
    if (w.owner[i] >= 0) {
      const st = w.states[w.owner[i]], ct = w.counties[w.county[i]];
      const city = a.cityOfCell(i);
      lines.push(`<b>${esc(st.name)}</b> · ${esc(ct.name)}`);
      if (city && city.name !== ct.name && !ct.name.startsWith(city.name)) lines.push(`<span class="dim">도시: ${esc(city.name)}</span>`);
      lines.push(`${elev != null ? `표고 ${elev} m` : '표고 자료 없음'} · ${RELIEF[w.relief[i]]}${w.elev_sd[i] != null ? ` <span class="dim">(기복 ±${w.elev_sd[i]} m)</span>` : ''}`);
      const T = a.terrain;
      if (w.water[i] === 3) lines.push('호수·저수지 칸 <span class="dim">(수면 표본점 과반, OSM 대체 자료)</span>');
      if (T && T.cover[i]) {
        // 대분류 상위 3개. 도엽 통계 칸은 숲·농경지를 세부(활엽·침엽·혼효, 논·밭·과수원·시설재배지)로 풀어 적는다
        const me = T.coverSrc[i] === 1, pub = T.coverPublic;
        const top = T.coverKeys.map((k) => [k, T.share[k][i]]).filter(([, v]) => v > 0.005).sort((x, y) => y[1] - x[1]).slice(0, 3);
        const sub = { forest: ['broadleaf', 'conifer', 'mixed'], crop: ['paddy', 'field', 'orchard', 'greenhouse'] };
        const txt = top.map(([k, v]) => {
          let t = `${COVER_KO[k]} ${Math.round(v * 100)}%`;
          if ((me || pub) && sub[k]) {
            const parts = sub[k].filter((q) => T.share[q]).map((q) => [q, T.share[q][i]]).filter(([, w]) => w >= 0.01).sort((x, y) => y[1] - x[1]);
            if (parts.length) t += ` <span class="dim">(${parts.map(([q, w]) => `${COVER_KO[q]} ${Math.round(w * 100)}`).join('·')})</span>`;
          }
          return t;
        });
        const un = me && T.share.unclassified ? T.share.unclassified[i] : 0;
        lines.push(`피복 ${txt.join(' · ')}${un >= 0.005 ? ` <span class="dim">· 미분류 ${Math.round(un * 100)}%</span>` : ''}`);
        const CS = { stats: ' (시군구 통계로 구분)' };
        const kind = T.crop[i] ? `${COVER_KO[T.crop[i]]}${CS[T.cropSrc[i]] || ''}` : T.forest[i] ? COVER_KO[T.forest[i]] : null;
        lines.push(`<span class="dim">${kind ? '대표 ' + esc(kind) + ' · ' : ''}${me ? esc((w.cover_meta && w.cover_meta.label) || '') : '도엽 통계가 닿지 않는 칸 — 대체 자료 ESA WorldCover'}</span>`);
      }
      if (T && T.tidal[i] > 0) lines.push(`<span class="dim">칸 넓이 중 갯벌 ${Math.round(T.tidal[i] * 100)}% (${esc(w.tidal.year)})</span>`);
      const pop = a.lenses.cell_pop[i];
      if (pop != null) lines.push(`칸 인구 ${pop.toLocaleString('ko-KR')}명`);
      lines.push('<span class="dim">누르면 시도 패널 · 도시는 깃발을 누른다</span>');
      if (a.lens) {
        const v = a.lens.values[i], k = w.county[i];
        lines.push(`<span class="lensv">${esc(a.lens.emoji)} ${esc(a.lens.name)}: <b>${esc(valueWithUnit(v, a.lens))}</b></span>`);
        // 값이 시 전체·개편 전 구 단위로 공표된 값이면 그 단위 (빌드가 적은 lens.units)
        const u = v != null ? unitOf(a.lens, k) : null;
        if (u) lines.push(`<span class="unitnote">↳ ${esc(u.label)}</span>`);
        // 6단계에서 렌즈 막대에서 뺀 관련 지표의 시군구 값 (건강 지수 → 구성 값 네 개 등)
        const rel = a.retiredNear(a.lens.id);
        if (rel.length) {
          lines.push(`<span class="dim">${a.lens.id === 'health' ? '구성 값 (시군구)' : '관련 지표 (시군구)'}: ${rel.map((it) => `${esc(it.name)} ${esc(valueWithUnit(it.values[k], it))}`).join(' · ')}</span>`);
          const ul = [...new Set(rel.filter((it) => it.values[k] != null).map((it) => unitOf(it, k)).filter(Boolean).map((x) => x.label))];
          if (ul.length && !(u && ul.length === 1 && u.label.startsWith(ul[0]))) lines.push(`<span class="unitnote">↳ 관련 지표: ${ul.map(esc).join(' · ')}</span>`);
        }
      }
    } else if (w.foreign[i]) {
      lines.push(`<b>외국 땅</b> <span class="dim">(통계 없음)</span>`);
      lines.push(`${elev != null ? `표고 ${elev} m` : '표고 자료 없음'} · ${RELIEF[w.relief[i]]}`);
    } else {
      const kind = w.water[i] === 1 ? '먼바다' : w.water[i] === 3 ? '호수' : w.water[i] === 4 ? '갯벌' : '연안';
      lines.push(`<b>${kind}</b>`);
      lines.push(elev != null ? `평균 수심 ${Math.max(0, -elev).toLocaleString('ko-KR')} m` : '수심 자료 없음 (SRTM30+ 범위 밖)');
      const td = a.terrain ? a.terrain.tidal[i] : 0;
      if (td > 0) lines.push(`칸 넓이 중 갯벌 ${Math.round(td * 100)}% <span class="dim">(해양수산부 ${esc(w.tidal.year)}년 제작)</span>`);
    }
    this.place(lines.join('<br>'), x, y);
  }
}
