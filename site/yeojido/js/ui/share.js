// 공유 — (1) 지금 화면 링크 복사 (2) 지도 그림 1600×900 PNG (3) 고을을 골랐으면 고을 카드 1200×630 PNG.
// 그림 아래 띠에는 제목·범례·기준 시점과, sources.json 에서 그린 것에 맞춰 만든 출처·이용허락 줄을 자르지 않고 찍는다.

import { h, clear } from '../dom.js';
import { iconEl } from '../icons.js';
import { Camera } from '../camera.js';
import { makePaper } from '../paper.js';
import { openModal, closeModal } from './modal.js';
import { lensValues, lensT, lensInv, lensIsContinuous } from '../adapter.js';
import { loadSources, attributionFor, cardFacts, lensObservedSteps } from '../adapter/sources.js';
import { printed, rgbCss } from '../map/lenscolor.js';
import { lensValueText, fmtWhen, wonParts, fmtInt } from '../fmt.js';

const SERIF = 'Hahmlet, "Yeojido Hanja", "Yeojido Sans", serif', SANS = '"Yeojido Sans", system-ui, sans-serif';
const INK = '#1d1a16', INK2 = '#5b5347', INK3 = '#685f50', JU = '#b8321f', JUD = '#8e2a1b', HI = '#f8f3e6', JJOK = '#26465f';
const PAD = 30, CREDIT_FS = 11, CREDIT_LH = 14.5;

const loadImg = (src) => new Promise((res) => { const im = new Image(); im.onload = () => res(im); im.onerror = () => res(null); im.src = src; });

export class Share {
  constructor(app) {
    this.app = app;
    this.menu = h('div#sharemenu.popmenu', { role: 'menu', 'aria-label': '공유', hidden: true });
    document.getElementById('modal-root').append(this.menu);
    document.addEventListener('pointerdown', (e) => { if (!this.menu.hidden && !this.menu.contains(e.target) && !(this.anchor && this.anchor.contains(e.target))) this.close(); }, true);
    this.menu.addEventListener('keydown', (e) => {
      const items = [...this.menu.querySelectorAll('button')], k = items.indexOf(document.activeElement);
      if (e.key === 'ArrowDown') { e.preventDefault(); items[(k + 1) % items.length].focus(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); items[(k + items.length - 1) % items.length].focus(); }
      else if (e.key === 'Tab') this.close();
    });
    window.addEventListener('resize', () => this.close());
    this.assets = null;
    this.last = null;
  }

  isOpen() { return !this.menu.hidden; }
  close(restore = false) {
    if (this.menu.hidden) return;
    this.menu.hidden = true;
    if (this.anchor) { this.anchor.setAttribute('aria-expanded', 'false'); if (restore) this.anchor.focus(); }
  }
  closeTransient() { if (this.menu.hidden) return false; this.close(true); return true; }

  toggle(anchor) {
    if (!this.menu.hidden) return this.close();
    this.anchor = anchor || this.anchor;
    const a = this.app, city = a.sel.type === 'city' ? a.D.cityById.get(a.sel.id) : null;
    const item = (ic, label, sub, fn) => h('button', { type: 'button', role: 'menuitem', onclick: () => { this.close(); fn(); } }, iconEl(ic, 18), h('span', label, sub ? h('small', sub) : null));
    clear(this.menu).append(
      item('link', '지금 화면 링크 복사', '자리 · 렌즈 · 고른 것 · 층', () => this.copyLink()),
      item('image', '지도 그림 저장', 'PNG 1600×900 · 범례와 출처 포함', () => this.save('map')));
    if (city) this.menu.append(item('image', `${city.name} 카드 저장`, 'PNG 1200×630 · 인구와 다섯 산출', () => this.save('card')));
    this.menu.hidden = false;
    if (this.anchor) {
      const r = this.anchor.getBoundingClientRect();
      this.menu.style.top = `${Math.round(r.bottom + 8)}px`;
      this.menu.style.right = `${Math.max(8, Math.round(window.innerWidth - r.right))}px`;
      this.anchor.setAttribute('aria-expanded', 'true');
    }
    this.menu.querySelector('button').focus({ preventScroll: true });
  }

  url() { return location.origin + location.pathname + this.app.hashString(); }

  async copyLink() {
    const u = this.url();
    let ok = false;
    try { if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(u); ok = true; } } catch (e) { ok = false; }
    if (!ok) {
      const ta = h('textarea', { readonly: true, style: { position: 'fixed', opacity: '0', left: '0', top: '0' } });
      ta.value = u;
      document.body.append(ta); ta.select();
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      ta.remove();
    }
    this.app.toast(ok ? '지금 화면의 링크를 복사했습니다.' : `복사하지 못했습니다. 주소창의 주소를 쓰십시오: ${u}`);
    return ok;
  }

  title() {
    const a = this.app, D = a.D, s = a.sel, sn = (c) => (D.stateByCode.get(c) || {}).short || c;
    let place = '대한민국';
    if (s.type === 'city') place = (D.cityById.get(s.id) || {}).name || place;
    else if (s.type === 'state') place = (D.stateByCode.get(s.id) || {}).name || place;
    else if (s.type === 'item' && a.selItem) place = a.selItem.name;
    else if (s.type === 'route' && a.selRoute) place = `${sn(a.selRoute.a)}–${sn(a.selRoute.b)} 교역로`;
    return { place, lens: a.lens ? a.lens.name : '지형' };
  }

  async prepare() {
    try { if (document.fonts && document.fonts.ready) await document.fonts.ready; } catch (e) { /* */ }
    try { await Promise.all([document.fonts.load('800 30px Hahmlet', '신여지도'), document.fonts.load('500 12px "Yeojido Sans"', '가')]); } catch (e) { /* */ }
    if (!this.assets) {
      const [seal, hanja, grain] = await Promise.all([loadImg('fonts/seal.svg'), loadImg('fonts/title-hanja.svg'), loadImg(makePaper(512))]);
      this.assets = { seal, hanja, grain };
    }
    await loadSources(this.app.D);
  }

  // 줄 바꿈: ' · ' 와 ', ' 에서 끊는다 (넘치면 글자 단위)
  wrap(ctx, text, maxw) {
    const toks = text.split(/(?<=· |, |\) )/), lines = [];
    let cur = '';
    for (const t of toks) {
      if (ctx.measureText(cur + t).width <= maxw) { cur += t; continue; }
      if (cur) lines.push(cur.trimEnd());
      cur = t;
      while (ctx.measureText(cur).width > maxw) {
        let n = cur.length;
        while (n > 1 && ctx.measureText(cur.slice(0, n)).width > maxw) n--;
        lines.push(cur.slice(0, n)); cur = cur.slice(n);
      }
    }
    if (cur) lines.push(cur.trimEnd());
    return lines;
  }

  // 화면 카메라와 같은 가운데·같은 범위를 w×hgt 에 담는 카메라 (fitCells 가 있으면 그 칸들에 맞춘다)
  camFor(w, hgt, fitCells) {
    const a = this.app, sc = a.cam, W = a.D.world, zero = { top: 0, bottom: 0, left: 0, right: 0 };
    const cam = new Camera(a.grid.width, a.grid.height, W.radius);
    cam.resize(w, hgt, a.focus, { top: 10, bottom: 10, left: 10, right: 10 });
    if (fitCells && fitCells.length) {
      let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
      for (const i of fitCells) { x0 = Math.min(x0, a.grid.cx[i]); x1 = Math.max(x1, a.grid.cx[i]); y0 = Math.min(y0, a.grid.cy[i]); y1 = Math.max(y1, a.grid.cy[i]); }
      const m = a.grid.W * 9;
      Object.assign(cam, cam.centerTarget((x0 + x1) / 2, (y0 + y1) / 2, Math.min(cam.maxScale * 0.6, w / (x1 - x0 + m), hgt / (y1 - y0 + m)), zero));
    } else if (sc.scale <= sc.fitScale * 1.03) cam.fit();
    else {
      const I = sc.insets, aw = Math.max(80, sc.vw - I.left - I.right), ah = Math.max(80, sc.vh - I.top - I.bottom);
      const [wx, wy] = sc.toWorld(I.left + aw / 2, I.top + ah / 2);
      Object.assign(cam, cam.centerTarget(wx, wy, sc.scale * Math.min(w / aw, hgt / ah), zero));
    }
    cam.insets = zero;
    cam.clamp();
    return cam;
  }

  mapCanvas(w, hgt, fitCells) {
    const cv = document.createElement('canvas');
    cv.width = w; cv.height = hgt;
    this.app.renderTo(cv.getContext('2d'), this.camFor(w, hgt, fitCells), 1);
    return cv;
  }

  grain(ctx, w, hgt) {
    const g = this.assets && this.assets.grain;
    if (!g) return;
    ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalCompositeOperation = 'multiply'; ctx.globalAlpha = 0.55;
    ctx.fillStyle = ctx.createPattern(g, 'repeat');
    ctx.fillRect(0, 0, w, hgt);
    ctx.restore();
  }

  // 범례: {kind:'steps', items:[{color,label}]} | {kind:'ramp', stops:[color], ticks:[label]} | {kind:'terrain'}
  legendModel() {
    const a = this.app, lens = a.lens, col = a.lensColor;
    if (!lens || !col) return { kind: 'terrain' };
    if (lensIsContinuous(lens)) {
      return { kind: 'ramp', stops: Array.from({ length: 24 }, (_, k) => rgbCss(printed(col.at(k / 23)))), ticks: [0, 0.25, 0.5, 0.75, 1].map((t) => lensValueText(lensInv(lens, t), lens)) };
    }
    const seen = lensObservedSteps(a.D, lens, lensValues(lens, a.D.world), (v) => lensT(lens, v));
    const names = lens.scale === 'bins' ? lens.binLabels : lens.categories;
    const items = [];
    names.forEach((nm, k) => { if (lens.scale === 'bins' || seen.has(k)) { const c = col.step(k); if (c) items.push({ color: rgbCss(printed(c)), label: String(nm) }); } });
    return { kind: 'steps', items };
  }

  layout(ctx, W) {
    const a = this.app, leg = this.legendModel();
    const cols = 5, legendRows = leg.kind === 'steps' ? Math.ceil(leg.items.length / cols) : 2;
    const top = Math.max(104, 24 + legendRows * 22 + 30);
    ctx.font = `400 ${CREDIT_FS}px ${SANS}`;
    const credits = attributionFor(a.D, { lens: a.lens, layerVisible: (g, s) => a.layerVisible(g, s) });
    const lines = [];
    for (const c of credits) for (const t of this.wrap(ctx, c.text, W - 2 * PAD)) lines.push({ text: t, warn: c.warn });
    return { leg, cols, legendRows, top, lines, band: top + 8 + lines.length * CREDIT_LH + 12 };
  }

  band(ctx, W, y0, lay) {
    const a = this.app, lens = a.lens, T = this.title(), A = this.assets || {};
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = HI; ctx.fillRect(0, y0, W, lay.band);
    ctx.fillStyle = INK; ctx.fillRect(0, y0, W, 1.5);
    ctx.fillStyle = 'rgba(29,26,22,0.24)'; ctx.fillRect(0, y0 + 5, W, 1);
    ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left';
    // 낙관 · 제목 · 곁글 한자
    let x = PAD;
    if (A.seal) { ctx.drawImage(A.seal, x, y0 + 22, 46, 46); x += 58; }
    ctx.fillStyle = INK; ctx.font = `800 30px ${SERIF}`;
    ctx.fillText('신여지도', x, y0 + 57);
    const tw = ctx.measureText('신여지도').width;
    if (A.hanja && A.hanja.width) { // 세로로 긴 그림 그대로, 작고 엷게
      const hh = 56, hw = hh * (A.hanja.width / A.hanja.height);
      ctx.globalAlpha = 0.32; ctx.drawImage(A.hanja, x + tw + 12, y0 + 16, hw, hh); ctx.globalAlpha = 1;
    }
    ctx.font = `600 16px ${SERIF}`; ctx.fillStyle = INK;
    ctx.fillText(`${T.place} · ${T.lens}`, PAD, y0 + 92);
    // 범례 (가운데)
    const lx = 400, lw = 800, drawn = [], leg = lay.leg;
    ctx.font = `400 13px ${SANS}`;
    if (leg.kind === 'steps') {
      const cw = lw / lay.cols;
      leg.items.forEach((s, k) => {
        const px = lx + (k % lay.cols) * cw, py = y0 + 24 + Math.floor(k / lay.cols) * 22;
        ctx.fillStyle = s.color; ctx.fillRect(px, py, 18, 14);
        ctx.strokeStyle = 'rgba(29,26,22,0.4)'; ctx.lineWidth = 1; ctx.strokeRect(px + 0.5, py + 0.5, 17, 13);
        ctx.fillStyle = INK;
        let fs = 13;
        while (fs > 9 && ctx.measureText(s.label).width > cw - 30) { fs -= 0.5; ctx.font = `400 ${fs}px ${SANS}`; }
        ctx.fillText(s.label, px + 25, py + 12);
        ctx.font = `400 13px ${SANS}`;
        drawn.push(s.label);
      });
    } else if (leg.kind === 'ramp') {
      const g = ctx.createLinearGradient(lx, 0, lx + lw, 0);
      leg.stops.forEach((c, k) => g.addColorStop(k / (leg.stops.length - 1), c));
      ctx.fillStyle = g; ctx.fillRect(lx, y0 + 30, lw, 16);
      ctx.strokeStyle = 'rgba(29,26,22,0.5)'; ctx.lineWidth = 1; ctx.strokeRect(lx + 0.5, y0 + 30.5, lw - 1, 15);
      ctx.fillStyle = INK;
      leg.ticks.forEach((t, k) => {
        ctx.textAlign = k === 0 ? 'left' : k === leg.ticks.length - 1 ? 'right' : 'center';
        ctx.fillText(t, lx + (lw * k) / (leg.ticks.length - 1), y0 + 64);
        drawn.push(t);
      });
      ctx.textAlign = 'left';
    } else {
      const key = [['산줄기 (계산한 분수계)', INK, 3, null], ['물줄기', JJOK, 2, null], ['시도 경계', 'rgba(29,26,22,0.55)', 1.2, [4, 3]], ['휴전선', JU, 2, [5, 4]]];
      key.forEach(([label, color, w, dash], k) => {
        const px = lx + (k % 2) * 350, py = y0 + 36 + Math.floor(k / 2) * 28;
        ctx.strokeStyle = color; ctx.lineWidth = w; ctx.setLineDash(dash || []);
        ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px + 40, py); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle = INK; ctx.fillText(label, px + 50, py + 4.5);
        drawn.push(label);
      });
    }
    if (lens) {
      const ny = Math.max(y0 + 24 + lay.legendRows * 22 + 16, y0 + 88);
      ctx.fillStyle = 'rgb(226,217,196)'; ctx.fillRect(lx, ny - 12, 18, 14);
      ctx.save(); ctx.beginPath(); ctx.rect(lx, ny - 12, 18, 14); ctx.clip();
      ctx.strokeStyle = 'rgba(29,26,22,0.4)'; ctx.lineWidth = 1; ctx.beginPath();
      for (let d = -14; d < 22; d += 5) { ctx.moveTo(lx + d, ny + 2); ctx.lineTo(lx + d + 14, ny - 12); }
      ctx.stroke(); ctx.restore();
      ctx.strokeStyle = 'rgba(29,26,22,0.4)'; ctx.strokeRect(lx + 0.5, ny - 11.5, 17, 13);
      ctx.fillStyle = INK2; ctx.font = `400 12.5px ${SANS}`;
      const dir = ({ good: '높을수록 좋음', bad: '낮을수록 좋음' })[lens.higherIs] || '';
      ctx.fillText(['자료 없음', lens.unit ? `단위 ${lens.unit}` : '', dir, a.lensRange ? '범례에서 고른 범위만 찍음' : ''].filter(Boolean).join(' · '), lx + 25, ny);
    }
    // 기준 시점 (오른쪽)
    ctx.textAlign = 'right';
    ctx.fillStyle = INK; ctx.font = `600 15px ${SERIF}`;
    ctx.fillText(lens ? `기준 ${lens.vintage || a.D.lenses.vintage || '자료 없음'}` : `주민등록 ${fmtWhen(a.D.vintage) || '자료 없음'} 판`, W - PAD, y0 + 46);
    ctx.fillStyle = INK2;
    const basis = lens && lens.basis ? `어디서 센 값: ${lens.basis}` : `칸 하나 ${a.D.world.hexKm2 ?? '–'} km²`;
    let bfs = 12.5;
    ctx.font = `400 ${bfs}px ${SANS}`;
    while (bfs > 9 && ctx.measureText(basis).width > W - PAD - (lx + lw) - 24) { bfs -= 0.5; ctx.font = `400 ${bfs}px ${SANS}`; }
    ctx.fillText(basis, W - PAD, y0 + 68);
    ctx.font = `400 12.5px ${SANS}`;
    ctx.fillText('공공 통계로 그린 대한민국 육각 칸 지도', W - PAD, y0 + 90);
    ctx.textAlign = 'left';
    // 출처 줄
    const cy = y0 + lay.top + 8;
    ctx.fillStyle = 'rgba(29,26,22,0.24)'; ctx.fillRect(PAD, cy - 6, W - 2 * PAD, 1);
    ctx.font = `400 ${CREDIT_FS}px ${SANS}`;
    lay.lines.forEach((l, k) => { ctx.fillStyle = l.warn ? JUD : INK3; ctx.fillText(l.text, PAD, cy + 11 + k * CREDIT_LH); });
    // 검사용: 그린 범례 항목과 출처 줄
    this.last = { legend: drawn, credits: lay.lines.map((l) => l.text), band: lay.band, title: `${T.place} · ${T.lens}` };
  }

  frame(ctx, w, hgt) {
    ctx.strokeStyle = INK; ctx.lineWidth = 1.5; ctx.strokeRect(0.75, 0.75, w - 1.5, hgt - 1.5);
    ctx.strokeStyle = 'rgba(29,26,22,0.24)'; ctx.lineWidth = 1; ctx.strokeRect(5.5, 5.5, w - 11, hgt - 11);
  }

  renderMap() {
    const W = 1600, H = 900;
    const cv = document.createElement('canvas');
    cv.width = W; cv.height = H;
    const ctx = cv.getContext('2d');
    const lay = this.layout(ctx, W);
    const maph = H - lay.band;
    ctx.drawImage(this.mapCanvas(W, maph), 0, 0);
    this.band(ctx, W, maph, lay);
    this.grain(ctx, W, H);
    this.frame(ctx, W, H);
    return cv;
  }

  // 고을 카드: 왼쪽 지도, 오른쪽 세로 이름 · 인구 · 다섯 산출 · 낙관
  renderCard() {
    const a = this.app, D = a.D, city = a.sel.type === 'city' ? D.cityById.get(a.sel.id) : null;
    if (!city) return null;
    const W = 1200, H = 630, MW = 690, A = this.assets || {};
    const F = cardFacts(D, city);
    const cv = document.createElement('canvas');
    cv.width = W; cv.height = H;
    const ctx = cv.getContext('2d');
    // 아래 온폭 띠: 출처 (그린 것에 맞춰 모두, 줄 수에 따라 띠 높이가 정해진다)
    const credit = attributionFor(D, { lens: a.lens, layerVisible: (g, s) => a.layerVisible(g, s) });
    const cfs = 9.5, clh = 12.5, lines = [];
    ctx.font = `400 ${cfs}px ${SANS}`;
    for (const c of credit) for (const t of this.wrap(ctx, c.text, W - 2 * PAD)) lines.push({ text: t, warn: c.warn });
    const strip = lines.length * clh + 20, MH = H - strip;
    ctx.fillStyle = HI; ctx.fillRect(0, 0, W, H);
    ctx.drawImage(this.mapCanvas(MW, MH, city.footprint), 0, 0);
    ctx.fillStyle = INK; ctx.fillRect(MW, 0, 1.5, MH); ctx.fillRect(0, MH, W, 1.5);
    const x0 = MW + 44, x1 = W - 44;
    // 세로 이름
    const nm = [...city.name], fs = Math.min(88, Math.floor((MH - 150) / nm.length));
    ctx.font = `800 ${fs}px ${SERIF}`; ctx.fillStyle = INK; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    nm.forEach((ch, k) => ctx.fillText(ch, x1 - fs / 2, 36 + k * fs * 1.04));
    if (A.seal) ctx.drawImage(A.seal, x1 - fs / 2 - 24, 48 + nm.length * fs * 1.04, 48, 48);
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    ctx.font = `800 15px ${SERIF}`; ctx.fillStyle = INK; ctx.fillText('신여지도', x0, 40);
    ctx.font = `600 12px ${SANS}`; ctx.fillStyle = INK2;
    ctx.fillText(city.full !== city.name ? city.full : (D.stateByCode.get(city.sido) || {}).name || '', x0, 64);
    ctx.fillText(`주민등록 인구 · ${fmtWhen(F.vintage) || '기준 자료 없음'}`, x0, 100);
    const big = (parts, x, y, size) => {
      if (!parts) { ctx.font = `400 ${Math.max(13, Math.round(size * 0.5))}px ${SANS}`; ctx.fillStyle = INK3; ctx.fillText('자료 없음', x, y); return; }
      ctx.font = `700 ${size}px ${SERIF}`; ctx.fillStyle = INK; ctx.fillText(parts[0], x, y);
      const w = ctx.measureText(parts[0]).width;
      ctx.font = `500 ${Math.round(size * 0.48)}px ${SANS}`; ctx.fillStyle = INK2; ctx.fillText(parts[1] || '', x + w + 4, y);
    };
    big(F.pop != null ? [fmtInt(F.pop), '명'] : null, x0, 146, 42);
    ctx.fillStyle = INK; ctx.fillRect(x0, 168, 290, 1);
    ctx.font = `600 12px ${SANS}`; ctx.fillStyle = INK2;
    ctx.fillText(`다섯 산출 (부가가치, 원)${F.gdpYear ? ' · ' + F.gdpYear + '년' : ''}`, x0, 190);
    const gap = Math.min(42, (MH - 236) / 5);
    let anyPartial = false;
    F.yields.forEach((yv, k) => {
      const y = 224 + k * gap;
      ctx.font = `500 14px ${SANS}`; ctx.fillStyle = INK2; ctx.fillText(yv.name, x0, y);
      big(yv.value != null ? wonParts(yv.value) : null, x0 + 70, y + 2, 26);
      if (yv.partial && yv.value != null) { anyPartial = true; ctx.font = `700 16px ${SANS}`; ctx.fillStyle = JU; ctx.fillText('*', x0 + 52, y - 4); }
      ctx.fillStyle = 'rgba(29,26,22,0.12)'; ctx.fillRect(x0, y + 12, 290, 1);
    });
    if (anyPartial) { ctx.font = `400 11px ${SANS}`; ctx.fillStyle = INK3; ctx.fillText('* 부분 합계: 비공개 몫이 빠진 합 (연감 › 산출·고을)', x0, MH - 12); }
    ctx.font = `400 ${cfs}px ${SANS}`;
    lines.forEach((l, k) => { ctx.fillStyle = l.warn ? JUD : INK3; ctx.fillText(l.text, PAD, MH + 10 + cfs + k * clh); });
    this.grain(ctx, W, H);
    this.frame(ctx, W, H);
    this.last = { legend: [], credits: lines.map((l) => l.text), title: city.name, card: true, creditFont: cfs, strip };
    return cv;
  }

  // 검사·저장 공용: 그림을 만들어 Blob 으로
  async exportPNG(kind = 'map') {
    await this.prepare();
    const cv = kind === 'card' ? this.renderCard() : this.renderMap();
    if (!cv) return null;
    return new Promise((res) => { try { cv.toBlob((b) => res(b), 'image/png'); } catch (e) { console.error(e); res(null); } });
  }

  async save(kind) {
    const a = this.app;
    a.toast('그림을 만드는 중…');
    let blob = null;
    try { blob = await this.exportPNG(kind); } catch (e) { console.error(e); }
    if (!blob) { a.toast('그림을 만들지 못했습니다.'); return; }
    const T = this.last ? this.last.title : '지도';
    const name = `신여지도-${T.replace(/[\s·/\\:*?"<>|]+/g, '_')}.png`;
    const url = URL.createObjectURL(blob);
    if (a.touch || a.narrow || !('download' in HTMLAnchorElement.prototype)) return this.preview(blob, url, name);
    const lnk = h('a', { href: url, download: name, style: { display: 'none' } });
    document.body.append(lnk); lnk.click(); lnk.remove();
    setTimeout(() => URL.revokeObjectURL(url), 8000);
    a.toast(`그림을 저장합니다: ${name}`);
  }

  // 손가락 화면: 미리 보기 (길게 눌러 저장하거나 단추로)
  preview(blob, url, name) {
    const file = typeof File === 'function' ? new File([blob], name, { type: 'image/png' }) : null;
    let canShare = false;
    try { canShare = !!(file && navigator.canShare && navigator.canShare({ files: [file] })); } catch (e) { canShare = false; }
    const el = h('div.modal.preview', { 'aria-label': '그림 미리 보기' });
    el.append(h('div.sheet',
      h('img', { src: url, alt: `${this.last ? this.last.title : '지도'} 그림. 아래 띠에 범례와 출처가 찍혀 있습니다.` }),
      h('p.dim', '그림을 길게 눌러 저장하거나 아래 단추를 누르십시오.'),
      h('div.acts',
        h('a.btn', { href: url, download: name }, iconEl('down', 16), '저장'),
        canShare ? h('button.btn', { type: 'button', onclick: () => navigator.share({ files: [file], title: '신여지도' }).catch(() => {}) }, iconEl('share', 16), '보내기') : null,
        h('button.btn', { type: 'button', onclick: () => closeModal(el) }, '닫기'))));
    el.addEventListener('pointerdown', (e) => { if (e.target === el) closeModal(el); });
    document.getElementById('modal-root').append(el);
    openModal(el, { onClose: () => { el.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); } });
    this.app.toast('그림을 만들었습니다.');
  }
}
