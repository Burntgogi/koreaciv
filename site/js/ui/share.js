// 공유: (1) 지금 화면 링크 복사, (2) 정사각 1:1 그림 1200×1200, (3) 와이드 16:9 그림 1600×900 (7b #32).
// 그림은 지도 캔버스를 그 크기로 다시 그리고(패널·조작부 없이), 아래 띠에 제목(도시·시도·렌즈 이름)·범례·기준 시점·사이트 표기·출처를 넣는다.
// 아래 띠의 출처 줄(감사 03)은 sources.json 의 attribution(지도 바탕·렌즈별 key)과 각 출처의 기관·이용허락으로 만든다. 글을 손으로 적지 않는다.
// 범주 범례(감사 12)는 화면 범례와 같은 범주를 모두 그린다 (띠 높이를 범주 수와 출처 줄 수에 맞춰 늘린다).
// 내려받기: 글꼴을 기다리고 → toBlob(3초 안에 답이 없거나 실패하면 toDataURL 로) → 터치 기기는 공유 시트, 그 밖은 <a download>.
// iOS Safari·앱 안 브라우저는 내려받기가 막히는 일이 많아 미리보기 시트(#pngpreview)를 함께 연다.

import { Camera } from '../camera.js';
import { LensScale, formatValue } from '../render/lens.js';
import { TERRAIN_KEY } from './lensbar.js';
import { KINDS } from '../render/layers.js';
import { SITE_NAME, SITE_URL } from '../config.js';

export const PRESETS = { square: { W: 1200, H: 1200, label: '정사각 1:1' }, wide: { W: 1600, H: 900, label: '와이드 16:9' } };
const CREDIT_FONT = 11.5, CREDIT_LH = 15, PAD = 28;
const FONT = '"Pretendard","Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif';

// 사이트 표기: config.js 의 SITE_URL, 비어 있으면 지금 주소(호스트+경로, 48자까지). 내 컴퓨터 주소면 연감 안내
export function siteLabel() {
  if (SITE_URL) return `${SITE_NAME} · ${SITE_URL}`;
  const h = location.hostname;
  if (!h || h === 'localhost' || h === '127.0.0.1' || location.protocol === 'file:') return `${SITE_NAME} · 연감(📖)에 전체 출처·이용허락 수록`;
  let u = (location.host + location.pathname).replace(/index\.html$/, '');
  if (u.length > 48) u = u.slice(0, 47) + '…';
  return `${SITE_NAME} · ${u}`;
}

function ellipsize(ctx, t, maxw) {
  if (ctx.measureText(t).width <= maxw) return t;
  while (t.length > 1 && ctx.measureText(t + '…').width > maxw) t = t.slice(0, -1);
  return t + '…';
}

// canvas → PNG Blob. toBlob 이 null 을 주거나 3초 안에 답이 없거나 예외면 toDataURL 을 풀어서
export function canvasToPngBlob(cv, ms = 3000) {
  const viaDataURL = () => {
    const u = cv.toDataURL('image/png');
    const bin = atob(u.slice(u.indexOf(',') + 1));
    const buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    return new Blob([buf], { type: 'image/png' });
  };
  return new Promise((resolve, reject) => {
    let done = false;
    const fin = (b) => { if (done) return; done = true; clearTimeout(t); try { resolve(b && b.size ? b : viaDataURL()); } catch (e) { reject(e); } };
    const t = setTimeout(() => fin(null), ms);
    try { cv.toBlob((b) => fin(b), 'image/png'); } catch (e) { fin(null); }
  });
}

export class Share {
  constructor(app) {
    this.app = app;
    this.el = document.getElementById('sharemenu');
    this.el.setAttribute('role', 'menu');
    this.el.setAttribute('aria-label', '공유');
    this.el.addEventListener('click', (e) => {
      const b = e.target.closest('[data-act]');
      if (!b) return;
      this.close(false);
      if (b.dataset.act === 'link') this.copyLink();
      else if (b.dataset.act === 'png') this.downloadPNG('wide');
      else if (b.dataset.act === 'png-square') this.downloadPNG('square');
    });
    // 메뉴 안 키보드: ↑/↓ 이동, Esc 닫고 공유 단추로 초점
    this.el.addEventListener('keydown', (e) => {
      const items = [...this.el.querySelectorAll('[role="menuitem"]')], k = items.indexOf(document.activeElement);
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        e.stopPropagation();
        items[(k + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length].focus();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        this.close(true);
      }
    });
    document.addEventListener('pointerdown', (e) => {
      if (this.isOpen() && !this.el.contains(e.target) && !e.target.closest('#share-btn')) this.close(false);
    }, true);
    this.pv = document.getElementById('pngpreview');
    if (this.pv) this.pv.addEventListener('click', (e) => { if (e.target === this.pv || e.target.closest('[data-pvclose]')) this.closePreview(); });
  }

  isOpen() { return !this.el.hidden; }
  close(focusBtn = false) {
    const was = this.isOpen();
    this.el.hidden = true;
    const b = document.getElementById('share-btn');
    if (b) b.setAttribute('aria-expanded', 'false');
    if (was && focusBtn && b) b.focus();
  }

  toggle(btn) {
    if (this.isOpen()) return this.close(false);
    this.app.help.close();
    this.el.innerHTML = `<button type="button" role="menuitem" data-act="link">🔗 지금 화면 링크 복사</button>
      <button type="button" role="menuitem" data-act="png-square">🖼️ 그림 내려받기 — 정사각 1:1 <small>1200×1200 · 전국 화면에 알맞음</small></button>
      <button type="button" role="menuitem" data-act="png">🖼️ 그림 내려받기 — 와이드 16:9 <small>1600×900 · 확대·가로 구간에 알맞음</small></button>`;
    const r = btn.getBoundingClientRect();
    this.el.style.top = `${r.bottom + 6}px`;
    this.el.style.right = `${Math.max(6, window.innerWidth - r.right)}px`;
    this.el.hidden = false;
    btn.setAttribute('aria-expanded', 'true');
    this.el.querySelector('[role="menuitem"]').focus();
  }

  url() {
    const a = this.app;
    a.writeHash();
    return location.origin + location.pathname + (a.lastHash || location.hash);
  }

  async copyLink() {
    const u = this.url();
    let ok = false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(u);
        ok = true;
      }
    } catch (e) { ok = false; }
    if (!ok) {
      const ta = document.createElement('textarea');
      ta.value = u;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      ta.remove();
    }
    this.app.toast(ok ? '지금 화면 링크를 복사했습니다.' : `복사하지 못했습니다. 주소창의 링크를 쓰세요: ${u}`);
    return ok;
  }

  title() {
    const a = this.app;
    let place = '대한민국';
    if (a.selCity != null) place = a.cityById.get(a.selCity).name;
    else if (a.selState) place = a.stateByCode.get(a.selState).name;
    else if (a.selItem) place = a.selItem.name;
    else if (a.selRoute) place = `${a.stateByCode.get(a.selRoute.a).short}–${a.stateByCode.get(a.selRoute.b).short} 교역로`;
    return `${place} · ${a.lens ? a.lens.name : '지형'}`;
  }

  // 출처 키 -> sources.json 기록 (끝이 '-' 인 층 종류 출처 key 는 접두어로 찾는다)
  srcRecords(keys) {
    const S = this.app.sources, out = [];
    if (!S) return out;
    if (!this._by) this._by = new Map(S.sources.map((x) => [x.key, x]));
    for (const k of keys) {
      const hit = this._by.has(k) ? [this._by.get(k)] : S.sources.filter((x) => x.key.startsWith(k));
      for (const x of hit) if (!out.includes(x)) out.push(x);
    }
    return out;
  }

  // 같은 이용허락끼리 기관을 묶은 문구들
  creditParts(keys) {
    const g = new Map();
    for (const x of this.srcRecords(keys)) {
      const lic = x.license_short || x.license || '이용허락 미확인';
      if (!g.has(lic)) g.set(lic, []);
      const nm = x.attribution_name || x.publisher;
      if (!g.get(lic).includes(nm)) g.get(lic).push(nm);
    }
    return [...g.entries()].map(([lic, names]) => `${names.join(', ')} (${lic})`);
  }

  // 지금 그림에 켜진 지도 층 종류의 출처 key (층 자료의 kinds[].source, 교역로·접경의 source)
  layerKeys() {
    const a = this.app, L = a.layers, keys = [];
    if (!L || !a.layerR) return keys;
    const add = (src) => { for (const x of src || []) if (x && x.key && !keys.includes(x.key)) keys.push(x.key); };
    const kindsOn = new Set(a.layerR.items.map((it) => it.kind).filter((k) => KINDS[k] && a.layerR.kindOn(k)));
    for (const obj of [L.wonders, L.resources, L.infrastructure]) {
      if (!obj) continue;
      for (const [kind, k] of Object.entries(obj.kinds || {})) {
        const K = KINDS[kind];
        const on = K ? kindsOn.has(kind) : (kind === 'roads' || kind === 'rails') ? a.layerVisible('infra', 'lines') : false;
        if (on) add(k.source);
      }
    }
    if (L.trade && L.trade.routes && a.layerVisible('trade', 'routes')) add(L.trade.routes.source);
    if (L.frontier && a.layerVisible('frontier', 'frontier')) add(L.frontier.source);
    return keys;
  }

  // 출처 줄: [{text, warn}] (wrap 전)
  credits() {
    const a = this.app, S = a.sources, lens = a.lens;
    const site = siteLabel();
    if (!S || !S.attribution) return [{ text: `출처 목록(sources.json)을 불러오지 못해 출처를 적지 못했습니다. 전체 출처는 ${site} 의 연감 › 출처에 있습니다.`, warn: true }];
    const A = S.attribution, out = [];
    const used = [...A.base];
    out.push({ text: `지도 바탕: ${this.creditParts(A.base).join(' · ')}` });
    if (lens) {
      const lk = A.lenses[lens.id];
      if (lk) { out.push({ text: `렌즈 ‘${lens.name}’: ${this.creditParts(lk).join(' · ')}` }); used.push(...lk); }
      else out.push({ text: `렌즈 ‘${lens.name}’: ${lens.source}` });
    }
    const lyk = this.layerKeys();
    if (lyk.length) { out.push({ text: `지도 층: ${this.creditParts(lyk).join(' · ')}` }); used.push(...lyk); }
    for (const x of this.srcRecords(used)) if (x.restriction_short) out.push({ text: `⚠ ${x.restriction_short}`, warn: true });
    out.push({ text: `전체 출처·이용허락 목록: ${SITE_URL ? site : SITE_NAME} › ${A.full_list}` });
    return out;
  }

  // 줄 바꿈: ' · ' 와 ', ' 에서 끊는다 (넘치면 글자 단위)
  wrap(ctx, text, maxw) {
    const toks = text.split(/(?<=· |, )/);
    const lines = [];
    let cur = '';
    for (const t of toks) {
      if (ctx.measureText(cur + t).width <= maxw) { cur += t; continue; }
      if (cur) lines.push(cur.trimEnd());
      cur = t;
      while (ctx.measureText(cur).width > maxw) {
        let n = cur.length;
        while (n > 1 && ctx.measureText(cur.slice(0, n)).width > maxw) n--;
        lines.push(cur.slice(0, n));
        cur = cur.slice(n);
      }
    }
    if (cur) lines.push(cur.trimEnd());
    return lines;
  }

  // 띠 배치. 와이드: 1행에 제목(왼쪽)·범례(가운데)·기준(오른쪽), 그 아래 출처. 정사각: 1행 제목·기준, 2행 범례(전체 폭), 3행 출처
  layout(ctx, P) {
    const a = this.app, lens = a.lens, W = P.W, sq = P === PRESETS.square;
    let steps = null, cols = 4, rows = 2, cat = false;
    if (lens) {
      steps = new LensScale(lens).legend(formatValue);
      cat = lens.scale === 'bins' || lens.scale === 'category';
      if (cat) { cols = steps.length <= 8 ? 4 : 5; rows = Math.ceil(steps.length / cols); }
    }
    const legH = lens ? (cat ? rows * 22 + 24 : 62) : 2 * 28 + 10;
    const legW = sq ? W - 2 * PAD : 680;
    const headH = sq ? 92 : Math.max(112, 24 + legH + 6);
    const top = sq ? headH + legH + 6 : headH;
    ctx.font = `400 ${CREDIT_FONT}px ${FONT}`;
    const lines = [];
    for (const c of this.credits()) for (const t of this.wrap(ctx, c.text, W - 2 * PAD)) lines.push({ text: t, warn: c.warn });
    const band = top + 8 + lines.length * CREDIT_LH + 10;
    return { steps, cat, cols, rows, legH, legW, headH, top, lines, band, maph: P.H - band, sq };
  }

  // 지도를 W×(H - 띠) 로 다시 그린 캔버스
  render(preset = 'wide') {
    const a = this.app, P = PRESETS[preset] || PRESETS.wide;
    const cv = document.createElement('canvas');
    cv.width = P.W;
    cv.height = P.H;
    const ctx = cv.getContext('2d');
    const lay = this.layout(ctx, P);
    const MAPH = lay.maph;
    const cam = new Camera(a.grid.width, a.grid.height, a.world.grid.radius);
    cam.resize(P.W, MAPH, a.focus, { top: 0, bottom: 0, left: 0, right: 0 });
    if (a.cam.scale <= a.cam.minScale * 1.03) cam.fit();
    else {
      cam.x = a.cam.x;
      cam.y = a.cam.y;
      cam.scale = a.cam.scale * Math.min(P.W / a.cam.vw, MAPH / a.cam.vh);
      cam.clamp();
    }
    ctx.fillStyle = '#0c1826';
    ctx.fillRect(0, 0, P.W, P.H);
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, P.W, MAPH);
    ctx.clip();
    a.terrain.drawAll(ctx, cam, 1);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    a.drawScene(ctx, cam, true);
    ctx.restore();
    this.band(ctx, lay, P);
    a.requestDraw(); // 화면의 깃발·아이콘 배치를 화면 카메라로 되돌린다
    return cv;
  }

  band(ctx, lay, P) {
    const a = this.app, lens = a.lens, y0 = lay.maph, W = P.W, sq = lay.sq;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = '#141822';
    ctx.fillRect(0, y0, W, lay.band);
    ctx.fillStyle = '#d8b25a';
    ctx.fillRect(0, y0, W, 2);
    ctx.textBaseline = 'alphabetic';
    ctx.textAlign = 'left';
    // 오른쪽: 기준 시점 · 사이트 표기 (먼저 재서 제목이 겹치지 않게)
    const vint = `기준 ${lens ? lens.vintage ?? a.lenses.vintage : `행정구역 2026-10-01 · 주민등록 ${a.nation.vintage}`}`;
    const site = siteLabel();
    ctx.font = `600 16px ${FONT}`;
    const vw = ctx.measureText(vint).width;
    ctx.font = `700 ${sq ? 15 : 18}px ${FONT}`;
    const sw = ctx.measureText(site).width;
    const rightW = Math.max(vw, sw);
    // 제목 (오른쪽 글과 24px 띄움, 넘치면 말줄임)
    const titleMax = sq ? Math.min(760, W - 2 * PAD - rightW - 24) : 540;
    ctx.fillStyle = '#f6e7b8';
    ctx.font = `700 30px ${FONT}`;
    const title = ellipsize(ctx, this.title(), titleMax);
    ctx.fillText(title, PAD, y0 + 46);
    ctx.fillStyle = '#a69f8e';
    ctx.font = `400 15px ${FONT}`;
    const sub = lens ? `${lens.emoji} ${lens.unit} · 어디서 센 값: ${lens.basis ?? '–'}` : '기복·피복·물';
    ctx.fillText(ellipsize(ctx, sub, titleMax), PAD + 2, y0 + 72);
    const sel = a.selItem ? `${KINDS[a.selItem.kind] ? KINDS[a.selItem.kind].label : ''}` : '';
    if (sel && !sq) ctx.fillText(sel, PAD + 2, y0 + 96);
    ctx.textAlign = 'right';
    ctx.fillStyle = '#e6dfcf';
    ctx.font = `600 16px ${FONT}`;
    ctx.fillText(vint, W - PAD, y0 + 42);
    ctx.fillStyle = '#d8b25a';
    ctx.font = `700 ${sq ? 15 : 18}px ${FONT}`;
    ctx.fillText(site, W - PAD, y0 + 70);
    ctx.textAlign = 'left';
    // 범례: 와이드는 가운데(600px부터 680px 폭), 정사각은 둘째 줄 전체 폭. 범주·구간은 화면 범례와 같은 항목 전부
    const lx = sq ? PAD : 600, lw = lay.legW, ly = sq ? y0 + lay.headH : y0;
    ctx.font = `400 13px ${FONT}`;
    const drawn = [];
    if (lens) {
      const steps = lay.steps;
      if (lay.cat) {
        const cw = lw / lay.cols;
        steps.forEach((s, k) => {
          const x = lx + (k % lay.cols) * cw, y = ly + 14 + Math.floor(k / lay.cols) * 22;
          ctx.fillStyle = s.color;
          ctx.fillRect(x, y, 16, 14);
          ctx.fillStyle = '#e6dfcf';
          ctx.fillText(ellipsize(ctx, String(s.label), cw - 26), x + 22, y + 12);
          drawn.push(String(s.label));
        });
      } else {
        const g = ctx.createLinearGradient(lx, 0, lx + lw, 0);
        steps.forEach((s, k) => g.addColorStop(k / (steps.length - 1), s.color));
        ctx.fillStyle = g;
        ctx.fillRect(lx, ly + 18, lw, 16);
        ctx.strokeStyle = 'rgba(0,0,0,0.5)';
        ctx.strokeRect(lx + 0.5, ly + 18.5, lw - 1, 15);
        ctx.fillStyle = '#e6dfcf';
        steps.forEach((s, k) => {
          const x = lx + (lw * k) / (steps.length - 1);
          ctx.textAlign = k === 0 ? 'left' : k === steps.length - 1 ? 'right' : 'center';
          ctx.fillText(s.label, x, ly + 52);
          drawn.push(String(s.label));
        });
        ctx.textAlign = 'left';
      }
      const ny = ly + lay.legH;
      ctx.fillStyle = 'rgba(150,150,150,0.8)';
      ctx.fillRect(lx, ny - 11, 14, 12);
      ctx.fillStyle = '#a69f8e';
      ctx.fillText(`자료 없음 · ${({ good: '높을수록 좋음', bad: '낮을수록 좋음' })[lens.higher_is] || '방향 없음'}`, lx + 20, ny);
    } else {
      const keys = TERRAIN_KEY.filter(([, t]) => ['평지', '산', '활엽수림', '침엽수림', '논', '밭', '시가지', '갯벌'].includes(t));
      const cw = sq ? lw / 8 : 130;
      keys.forEach(([c, t], k) => {
        const x = sq ? lx + k * cw : lx + (k % 4) * 130, y = sq ? ly + 14 : ly + 30 + Math.floor(k / 4) * 28;
        ctx.fillStyle = c;
        ctx.fillRect(x, y, 16, 14);
        ctx.fillStyle = '#e6dfcf';
        ctx.fillText(t, x + 22, y + 12);
        drawn.push(t);
      });
    }
    // 출처 줄
    const cy = y0 + lay.top + 8;
    ctx.fillStyle = 'rgba(255,255,255,0.08)';
    ctx.fillRect(PAD, cy - 4, W - 2 * PAD, 1);
    ctx.font = `400 ${CREDIT_FONT}px ${FONT}`;
    lay.lines.forEach((l, k) => {
      ctx.fillStyle = l.warn ? '#f0b46a' : '#b3ab98';
      ctx.fillText(l.text, PAD, cy + 12 + k * CREDIT_LH);
    });
    // 검사용: 그린 범례 항목과 출처 줄, 제목이 차지한 오른쪽 끝 (QA 가 화면 범례·출처와 대조)
    ctx.font = `700 30px ${FONT}`;
    this.last = { preset: sq ? 'square' : 'wide', W, H: P.H, legend: drawn, credits: lay.lines.map((l) => l.text), band: lay.band, title,
      titleRight: PAD + ctx.measureText(title).width, rightLeft: W - PAD - rightW };
  }

  // 그림 만들기 → PNG → 내려받기(또는 공유 시트·미리보기). 결과를 돌려준다 (시험용)
  async downloadPNG(preset = 'wide') {
    const a = this.app;
    try { if (document.fonts && document.fonts.ready) await document.fonts.ready; } catch (e) { /* 글꼴 없이도 그린다 */ }
    let cv;
    try { cv = this.render(preset); } catch (e) {
      console.error(e);
      a.toast('그림을 만들지 못했습니다. 화면을 축소하거나 다시 시도해 주세요.');
      return null;
    }
    let blob;
    try { blob = await canvasToPngBlob(cv); } catch (e) {
      console.error(e);
      a.toast('그림을 만들지 못했습니다. 화면을 축소하거나 다시 시도해 주세요.');
      return null;
    }
    const name = `koreaciv-${this.title().replace(/[\s·/\\:*?"<>|]+/g, '_')}-${preset === 'square' ? '1x1' : '16x9'}.png`;
    this.lastBlob = { size: blob.size, type: blob.type, name };
    const touch = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
    const ua = navigator.userAgent || '';
    const iosLike = /iP(hone|ad|od)/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
    const inApp = /KAKAOTALK|NAVER|Instagram|FBAN|FBAV|Line\//i.test(ua);
    if (touch && typeof File === 'function' && navigator.canShare) {
      const file = new File([blob], name, { type: 'image/png' });
      try {
        if (navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file], title: this.title() });
          cv.width = cv.height = 0;
          return this.lastBlob;
        }
      } catch (e) {
        if (e && e.name === 'AbortError') { cv.width = cv.height = 0; return this.lastBlob; }
      }
    }
    const u = URL.createObjectURL(blob);
    const lnk = document.createElement('a');
    lnk.href = u;
    lnk.download = name;
    document.body.appendChild(lnk);
    lnk.click();
    lnk.remove();
    if ((iosLike || inApp) && this.pv) this.openPreview(u, name, cv);
    else { setTimeout(() => URL.revokeObjectURL(u), 15000); cv.width = cv.height = 0; }
    a.toast(`그림을 내려받습니다: ${name}`);
    return this.lastBlob;
  }

  openPreview(u, name, cv) {
    this.pvState = { u, cv };
    this.pv.innerHTML = `<div class="sheet" role="dialog" aria-modal="true" aria-label="공유 그림 미리보기"><img src="${u}" alt="${name.replace(/"/g, '')}">
      <p>이미지를 길게 눌러 저장하거나 아래 단추로 내려받으세요.</p><div class="btns"><a class="btn" href="${u}" download="${name.replace(/"/g, '')}">내려받기</a><button type="button" data-pvclose>닫기</button></div></div>`;
    this.pv.hidden = false;
    this.pv.querySelector('[data-pvclose]').focus();
  }

  previewOpen() { return !!this.pv && !this.pv.hidden; }

  closePreview() {
    if (!this.previewOpen()) return false;
    this.pv.hidden = true;
    this.pv.innerHTML = '';
    if (this.pvState) {
      URL.revokeObjectURL(this.pvState.u);
      this.pvState.cv.width = this.pvState.cv.height = 0;
      this.pvState = null;
    }
    return true;
  }
}
