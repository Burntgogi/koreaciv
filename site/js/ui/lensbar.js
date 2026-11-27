// 렌즈 선택(아래쪽 띠)과 범례. 렌즈가 많아 묶음별로 접고 편다: 묶음 단추를 누르면 그 묶음의 렌즈만 펼쳐진다.

import { LensScale, formatValue } from '../render/lens.js';

export const TERRAIN_KEY = [
  ['#8cbc5c', '평지'], ['#86ad57', '구릉', 'hill'], ['#a3916a', '산', 'mtn'], ['#d9d6cf', '고봉', 'peak'],
  ['#64904a', '활엽수림', 'cv-forest'], ['#2c5a46', '침엽수림', 'cv-conifer'], ['#4b7546', '혼효림', 'cv-mixed'],
  ['#b8d05c', '논', 'cv-paddy'], ['#d0b46e', '밭', 'cv-field'], ['#9b9440', '과수원', 'cv-orchard'], ['#d8d8ce', '시설재배지', 'cv-greenhouse'],
  ['#b0a098', '시가지', 'cv-built'],
  ['#569ac2', '호수·저수지'], ['#94886c', '갯벌', 'cv-tidal'],
  ['#4f98b6', '연안'], ['#244f7e', '먼바다'], ['#9a9482', '외국 땅'],
];
const esc = (t) => String(t ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const GROUP_ICON = { people: '👥', living: '💰', industry: '🏭', daily: '🏡', learn: '🎓', land: '🌾' };

export class LensBar {
  constructor(app) {
    this.app = app;
    this.bar = document.getElementById('lensbar');
    this.legend = document.getElementById('legend');
    this.openGroup = null;
    this.render();
    // 좁은 화면: 범례는 제목 한 줄로 접혀 있고 누르면 펼친다
    this.legend.addEventListener('click', (e) => {
      if (e.target.closest('h5')) this.legend.classList.toggle('open');
    });
    this.bar.addEventListener('click', (e) => {
      const g = e.target.closest('[data-group]');
      if (g) {
        this.openGroup = this.openGroup === g.dataset.group ? null : g.dataset.group;
        this.render();
        return;
      }
      const b = e.target.closest('[data-lens]');
      if (b) app.setLens(b.dataset.lens || null);
    });
  }

  render() {
    const L = this.app.lenses, cur = this.app.lens ? this.app.lens.id : null;
    let html = `<button data-lens="" class="lb ${cur ? '' : 'on'}"><span class="em">🗺️</span><span>지형</span></button>`;
    for (const g of L.groups) {
      const items = L.lenses.filter((x) => x.group === g.id);
      if (!items.length) continue;
      const open = this.openGroup === g.id;
      const has = items.some((x) => x.id === cur);
      html += `<button data-group="${esc(g.id)}" class="grp ${open ? 'open' : ''} ${has ? 'has' : ''}" aria-expanded="${open}" title="${esc(items.map((x) => x.name).join(', '))}">
        <span class="em">${esc(GROUP_ICON[g.id] || '•')}</span><span>${esc(g.name)} <small>${esc(items.length)}</small></span></button>`;
      if (open) {
        html += `<span class="items">${items.map((l) => `<button data-lens="${esc(l.id)}" class="lb ${l.id === cur ? 'on' : ''}" title="${esc(l.description)}"><span class="em">${esc(l.emoji)}</span><span>${esc(l.name)}</span></button>`).join('')}</span>`;
      }
    }
    this.bar.innerHTML = html;
  }

  update() {
    const a = this.app, lens = a.lens;
    if (lens && this.openGroup !== lens.group) this.openGroup = lens.group;
    this.render();
    if (!lens) {
      const w = a.world.tables.relief;
      const W = a.world;
      // 숲 종류(활엽·침엽·혼효)가 없는 자료(옛 빌드)는 숲 한 칸으로 적는다
      const key = W.forest_kind ? TERRAIN_KEY : TERRAIN_KEY.filter(([, , k]) => !['cv-conifer', 'cv-mixed'].includes(k)).map((x) => (x[2] === 'cv-forest' ? ['#567f4a', '숲', 'cv-forest'] : x));
      // 피복 출처 글은 world.cover_meta.legend (두 판 공용, 빌드가 숫자를 넣어 만든다)
      const cover = W.cover_meta && W.cover_meta.legend ? `<p class="src">${esc(W.cover_meta.legend)}</p>` : '';
      this.legend.innerHTML = `<h5>🗺️ 지형</h5>
        <ul class="steps key">${key.map(([c, t, k]) => `<li><i class="${k || ''}" style="background:${c}"></i>${t}</li>`).join('')}
        <li><i class="dmz"></i>휴전선</li><li><i class="river"></i>국가하천</li>
        <li><i class="road"></i>고속국도</li><li><i class="road2"></i>일반국도 (확대 시)</li><li><i class="rail"></i>철도</li></ul>
        <details class="lsrc"><summary>기준·출처</summary><p class="src">도로: 국가교통정보센터 전국표준노드링크 (2026-11-11) · 철도 선 — 초안: Natural Earth 1:10m, 공식 철도망으로 교체 예정</p>
        <p>기복: 칸 안 표고 표준편차 ${w[1].rule.match(/\d+/)[0]} m↑ 구릉, ${w[2].rule.match(/\d+/)[0]} m↑ 산, 평균 1,000 m↑ 고봉. 바탕색은 피복 비율을 섞은 색, 무늬는 칸의 대표 피복(확대 시, 산 칸의 숲 종류는 아래 귀퉁이에 작게).</p>
        ${this.restrictNote()}${cover}
        <p class="src">호수·저수지: <b>대체 자료</b> © OpenStreetMap 기여자 (ODbL) · 강: WAMIS 하천 유로선 (지방하천은 확대 시) · 갯벌: 해양수산부 ${a.world.tidal ? esc(a.world.tidal.year) : ''}년 제작</p>
        <p class="src">SRTM30+ · 행정동 경계 2026-10-01 · Natural Earth (국경·철도)</p></details>`;
      return;
    }
    const sc = new LensScale(lens);
    const steps = sc.legend(formatValue);
    const discrete = lens.scale === 'bins' || lens.scale === 'category';
    const scaleName = { log: '로그', linear: '선형', diverging: `발산(${esc(lens.center)} 중심)`, bins: `구간 ${esc(lens.ramp.length)}단계`, category: '범주' }[lens.scale];
    const dir = { good: ' · 높을수록 좋음', bad: ' · 낮을수록 좋음' }[lens.higher_is] || '';
    this.legend.innerHTML = `<h5>${esc(lens.emoji)} ${esc(lens.name)} <small>${esc(lens.unit)}</small></h5>
      ${discrete ? `<ul class="steps fsteps ${lens.scale === 'category' ? 'cat' : ''}" aria-label="범례 구간 고르기">${steps.map((s, k) => `<li data-k="${s.k ?? k}" tabindex="0" role="button" aria-pressed="false"><i style="background:${esc(s.color)}"></i>${esc(s.label)}</li>`).join('')}</ul>`
        : `<div class="fbar" tabindex="0" role="group" aria-label="범례 구간 고르기: 왼쪽·오른쪽 화살표로 구간, Esc 로 풀기"><div class="bar" style="background:linear-gradient(90deg,${steps.map((s) => esc(s.color)).join(',')})"></div><div class="selr" hidden></div></div>
           <div class="ticks">${steps.map((s) => `<span>${esc(s.label)}</span>`).join('')}</div>`}
      <p class="fhint">눈금을 가리키거나 끌면 그 구간의 칸만 색이 남는다${discrete ? ' (키보드: 항목에서 Enter)' : ' (놓으면 풀림 · 키보드: 화살표, Esc)'}</p>
      <p><i class="na"></i> 자료 없음 · 척도 ${scaleName}${dir}</p>
      <p class="basis">기준 <b>${esc(lens.vintage ?? a.lenses.vintage)}</b> · 어디서 센 값: <b>${esc(lens.basis ?? '–')}</b></p>
      <p>${esc(lens.description)}</p>
      ${lens.units_note ? `<p class="unitnote">${esc(lens.units_note)}</p>` : ''}
      <p class="src">${esc(lens.source)}</p>${this.restrictNote(lens.id)}`;
    this.bindFilter(lens, sc);
  }

  // 이용조건 경고 (sources.json restrictions, 감사 02): 지형은 늘, 렌즈는 그 렌즈의 출처에 제한 자료가 있을 때
  restrictNote(lensId) {
    const S = this.app.sources;
    if (!S || !S.restrictions) return '';
    const keys = lensId ? ((S.attribution && S.attribution.lenses[lensId]) || []) : null;
    const rs = S.restrictions.filter((r) => !keys || keys.includes(r.key));
    return rs.map((r) => `<p class="restrict sm" role="note">⚠ ${esc(r.short)} <small>(연감 › 출처)</small></p>`).join('');
  }

  // 범례 구간 고르기: 마우스는 가리키거나 끄는 동안만, 터치는 누르면 남고 두 번 누르면 풀린다
  bindFilter(lens, sc) {
    const a = this.app;
    const set = (fn) => { a.terrain.setFilter(fn); a.requestDraw(); };
    let lastTouchUp = 0;
    const dbl = (e) => e.pointerType !== 'mouse' && performance.now() - lastTouchUp < 380;
    const bar = this.legend.querySelector('.fbar');
    if (bar) {
      const selr = bar.querySelector('.selr');
      const tAt = (e) => { const r = bar.getBoundingClientRect(); return Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)); };
      const seg = (t) => { const k = Math.min(4, Math.floor(t * 5)); return [k / 5, (k + 1) / 5]; };
      const apply = (t0, t1) => {
        selr.hidden = false;
        selr.style.left = `${t0 * 100}%`;
        selr.style.width = `${Math.max(1, (t1 - t0) * 100)}%`;
        set((v) => { const t = sc.t(v); if (t == null) return false; const u = Math.min(1, Math.max(0, t)); return u >= t0 - 1e-9 && u <= t1 + 1e-9; });
      };
      const clear = () => { selr.hidden = true; set(null); };
      let drag = null;
      bar.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        if (dbl(e)) { lastTouchUp = 0; drag = null; return clear(); }
        bar.setPointerCapture(e.pointerId);
        drag = tAt(e);
        apply(...seg(drag));
      });
      bar.addEventListener('pointermove', (e) => {
        const t = tAt(e);
        if (drag != null) {
          const [p0, p1] = seg(drag), [q0, q1] = seg(t);
          apply(Math.min(p0, q0), Math.max(p1, q1));
        } else if (e.pointerType === 'mouse') apply(...seg(t));
      });
      bar.addEventListener('pointerup', (e) => {
        drag = null;
        if (e.pointerType === 'mouse') clear();
        else lastTouchUp = performance.now();
      });
      bar.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse' && drag == null) clear(); });
      bar.addEventListener('dblclick', clear);
      // 키보드 (감사 10): 화살표로 다섯 구간 가운데 하나, Esc 로 풀기
      let kk = -1;
      bar.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
          e.preventDefault();
          e.stopPropagation();
          kk = Math.max(0, Math.min(4, kk + (e.key === 'ArrowRight' ? 1 : -1)));
          apply(kk / 5, (kk + 1) / 5);
          const lo = sc.lo + (sc.hi - sc.lo) * (kk / 5), hi = sc.lo + (sc.hi - sc.lo) * ((kk + 1) / 5);
          a.announce(lens.scale === 'linear' ? `${kk + 1}번째 구간 (${formatValue(lo, lens)}–${formatValue(hi, lens)})의 칸만 색을 남김` : `${kk + 1}번째 구간의 칸만 색을 남김`);
        } else if (e.key === 'Escape') {
          e.stopPropagation();
          kk = -1;
          clear();
        }
      });
      return;
    }
    const ul = this.legend.querySelector('.fsteps');
    if (!ul) return;
    const test = (k) => (lens.scale === 'category' ? (v) => v === k : (v) => { const t = sc.t(v); return t != null && Math.round(t * lens.breaks.length) === k; });
    const mark = (k) => { for (const li of ul.children) { li.classList.toggle('sel', k != null && Number(li.dataset.k) === k); li.classList.toggle('dimmed', k != null && Number(li.dataset.k) !== k); } };
    const pick = (k) => { mark(k); set(k == null ? null : test(k)); };
    let pinned = null;
    ul.addEventListener('pointerover', (e) => { const li = e.target.closest('li[data-k]'); if (li && e.pointerType === 'mouse') pick(Number(li.dataset.k)); });
    ul.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse') pick(pinned); });
    ul.addEventListener('pointerdown', (e) => {
      const li = e.target.closest('li[data-k]');
      if (!li) return;
      if (e.pointerType === 'mouse') return;
      if (dbl(e)) { lastTouchUp = 0; pinned = null; return pick(null); }
      pinned = Number(li.dataset.k);
      pick(pinned);
    });
    ul.addEventListener('pointerup', (e) => { if (e.pointerType !== 'mouse') lastTouchUp = performance.now(); });
    ul.addEventListener('dblclick', () => { pinned = null; pick(null); });
    // 키보드 (감사 10): 항목에서 Enter·Space 로 고정·풀기
    ul.addEventListener('keydown', (e) => {
      const li = e.target.closest('li[data-k]');
      if (!li || (e.key !== 'Enter' && e.key !== ' ')) return;
      e.preventDefault();
      const k = Number(li.dataset.k);
      pinned = pinned === k ? null : k;
      pick(pinned);
      for (const x of ul.children) x.setAttribute('aria-pressed', String(pinned != null && Number(x.dataset.k) === pinned));
      a.announce(pinned == null ? '범례 고르기 풀림' : `${esc(li.textContent)} 칸만 색을 남김`);
    });
  }
}
