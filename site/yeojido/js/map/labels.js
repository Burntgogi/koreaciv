// 이름 — 고을 현판과 묵서, 시도 이름, 바다·강·호수 이름.
// 위계(수도 > 특별·광역시 > 도청 소재지 > 특례시 > 인구 순)로 먼저 놓고, 여덟 방향 가운데 비는 자리를 고른다.
// 큰 고을만 얇은 현판을 갖고, 나머지는 테 없는 묵서 + 작은 고리다. 다섯 산출 같은 숫자는 지도에 깔지 않는다(고을 장에 있다).

import { fmtMan } from '../fmt.js';
import { smooth } from './land.js';

const SERIF = 'Hahmlet, "Yeojido Hanja", "Yeojido Sans", serif', SANS = '"Yeojido Sans", system-ui, sans-serif';
const INK = '#1D1A16', INK2 = '#5B5347', JU = '#B8321F', BAEK = '#FBF6E8', HI = '#F8F3E6', JJOK = '#26465F';
// 바다 이름 셋은 자료가 아니라 손으로 놓은 것이다 (연감 일러두기에 적음)
const SEAS = [{ name: '동해', x: 5250, y: 2350 }, { name: '서해', x: 760, y: 2700 }, { name: '남해', x: 3250, y: 5080 }];

const hit = (r, x, y) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h;
const overlap = (a, b, pad = 0) => a.x < b.x + b.w + pad && a.x + a.w + pad > b.x && a.y < b.y + b.h + pad && a.y + a.h + pad > b.y;

export class Labels {
  constructor(D) {
    this.D = D;
    const score = (c) => (c.capital === '수도' ? 5 : /특별시|광역시|특별자치시/.test(c.kind) ? 4 : c.capital ? 3 : c.kind === '특례시' ? 2 : 0);
    this.cities = D.cities.map((c) => ({ c, cls: score(c) })).sort((a, b) => b.cls - a.cls || (b.c.pop || 0) - (a.c.pop || 0));
    const cityNames = new Set(D.cities.map((c) => c.name));
    this.states = D.states.filter((s) => s.label).map((s) => ({ s, twin: cityNames.has(s.short) }));
    this.pos = new Map();   // 고을 id -> 지난번 자리 번호
    this.placed = [];       // 이번 프레임에 놓인 고을 이름 [{c, x,y,w,h, ...}]
    this.stateBoxes = [];
    this.rects = [];
    this.wcache = new Map();
  }

  tw(ctx, font, text) {
    const k = font + '|' + text;
    let w = this.wcache.get(k);
    if (w == null) { ctx.font = font; w = ctx.measureText(text).width; this.wcache.set(k, w); if (this.wcache.size > 4000) this.wcache.clear(); }
    return w;
  }

  // 자리 잡기. o: {sel: 고른 고을 id, hover: id, reserved: [rect], compact: 좁은 화면}
  layout(ctx, cam, o = {}) {
    const rc = cam.rc, vw = cam.vw, vh = cam.vh;
    const A = Math.max(5, Math.min(18, Math.round((vw * vh) / 100000)));
    const budget = rc < 5 ? A : rc < 6.8 ? Math.round(A * 1.5) : rc < 11 ? Math.round(A * 2.5) : 999;
    const placed = [], boxes = [...(o.reserved || [])];
    const showPop = rc >= 5.2;
    const tryPlace = (it, force) => {
      const c = it.c, [ax, ay] = cam.toScreen(c.x, c.y);
      if (ax < -80 || ay < -40 || ax > vw + 80 || ay > vh + 40) return null;
      const big = it.cls >= 2 || force;
      const fs = big ? (it.cls >= 4 ? 14 : 13) : 12;
      const font = `${big ? 700 : 500} ${fs}px ${SERIF}`;
      const pop = (big ? showPop : rc >= 11) && c.pop != null ? fmtMan(c.pop) : '';
      const pfont = `500 11px ${SANS}`;
      const nw = this.tw(ctx, font, c.name), pw = pop ? this.tw(ctx, pfont, pop) + 7 : 0;
      const padX = big ? 8 : 2, bandW = big ? 3 : 0;
      const w = Math.ceil(nw + pw + padX * 2 + bandW), hgt = big ? fs + 10 : fs + 4;
      const g = big ? 7 : 6; // 고을 점에서 떨어진 거리
      // 여덟 방향: 동, 서, 북동, 북서, 남동, 남서, 북, 남
      const cand = [[g, -hgt / 2], [-g - w, -hgt / 2], [g - 2, -hgt - 3], [-g - w + 2, -hgt - 3], [g - 2, 3], [-g - w + 2, 3], [-w / 2, -hgt - g], [-w / 2, g]];
      const order = [...cand.keys()];
      const prev = this.pos.get(c.id);
      if (prev != null) { order.splice(order.indexOf(prev), 1); order.unshift(prev); }
      const dot = { x: ax - 4, y: ay - 4, w: 8, h: 8 };
      for (const k of order) {
        const r = { x: Math.round(ax + cand[k][0]), y: Math.round(ay + cand[k][1]), w, h: hgt };
        if (!force) {
          if (r.x < 2 || r.y < 2 || r.x + r.w > vw - 2 || r.y + r.h > vh - 2) continue;
          let bad = false;
          for (const b of boxes) if (overlap(r, b, big ? 3 : 2)) { bad = true; break; }
          if (bad) continue;
          for (const b of boxes) if (b.dot && overlap(dot, b, 0)) { bad = true; break; }
          if (bad) continue;
        }
        this.pos.set(c.id, k);
        const p = { c, cls: it.cls, big, font, pfont, pop, nw, padX, bandW, ax, ay, ...r };
        placed.push(p); boxes.push(r); boxes.push({ ...dot, dot: true });
        return p;
      }
      return null;
    };
    // 고른 고을·가리킨 고을은 늘 놓는다
    const first = [];
    for (const id of [o.sel, o.hover]) { if (id == null) continue; const it = this.cities.find((x) => x.c.id === id); if (it && !first.includes(it)) first.push(it); }
    for (const it of first) { const p = tryPlace(it, true); if (p) p.state = it.c.id === o.sel ? 'sel' : 'hover'; }
    let n = 0;
    for (const it of this.cities) {
      if (n >= budget) break;
      if (first.includes(it)) continue;
      if (rc < 4.4 && it.cls < 2 && n >= A) break;
      if (tryPlace(it, false)) n++;
    }
    this.placed = placed;
    // 시도 이름
    this.stateBoxes = [];
    const sa = 1 - smooth(8, 11, rc);
    if (sa > 0.02) {
      for (const { s, twin } of this.states) {
        if (twin) continue; // 같은 이름의 고을 현판이 있는 특별·광역시는 적지 않는다 (고을 장의 머리에서 시도 장으로 간다)
        const [x, y] = cam.toScreen(s.label.x, s.label.y);
        if (x < -100 || y < -40 || x > vw + 100 || y > vh + 40) continue;
        const fs = Math.max(o.compact ? 11 : 13, Math.min(o.compact ? 19 : 30, (s.label.size || 120) * cam.scale * 0.55));
        const text = s.short, gap = fs * 0.55;
        const font = `500 ${fs.toFixed(1)}px ${SERIF}`;
        const w = this.tw(ctx, font, text) + gap * (text.length - 1);
        let r = { x: x - w / 2, y: y - fs * 0.62, w, h: fs * 1.24 };
        // 현판과 겹치면 위아래로 비켜 본다
        const clash = (q) => placed.some((p) => overlap(q, p, 2)) || this.stateBoxes.some((p) => overlap(q, p, 4));
        if (clash(r)) { const alt = [fs * 1.3, -fs * 1.3, fs * 2.4, -fs * 2.4].map((dy) => ({ ...r, y: r.y + dy })).find((q) => !clash(q)); if (!alt) continue; r = alt; }
        this.stateBoxes.push({ s, font, fs, gap, text, alpha: sa, sel: o.selState === s.code, ...r });
      }
    }
    this.rects = placed.map((p) => ({ x: p.x, y: p.y, w: p.w, h: p.h }));
    return this.rects;
  }

  drawGeo(ctx, cam, o = {}) {
    const rc = cam.rc, vw = cam.vw, vh = cam.vh, W = this.D.world;
    ctx.textBaseline = 'middle'; ctx.textAlign = 'center';
    // 바다 이름 (멀리서)
    const seaA = (1 - smooth(6, 9, rc)) * (o.compact ? 0.8 : 1);
    if (seaA > 0.02) {
      const fs = Math.max(13, Math.min(24, 16 + rc * 1.6));
      ctx.font = `400 ${fs}px ${SERIF}`;
      ctx.fillStyle = `rgba(38,70,95,${(0.62 * seaA).toFixed(3)})`;
      for (const sea of SEAS) {
        const [x, y] = cam.toScreen(sea.x, sea.y);
        if (x < 10 || y < 20 || x > vw - 10 || y > vh - 20) continue;
        const gap = fs * 3.2;
        [...sea.name].forEach((ch, k) => ctx.fillText(ch, x, y + (k - (sea.name.length - 1) / 2) * gap));
      }
    }
    // 강·호수 이름 (다가갔을 때)
    const ga = smooth(6.4, 8, rc);
    if (ga > 0.02) {
      ctx.lineJoin = 'round';
      const put = (text, x, y, ang, fs) => {
        ctx.save(); ctx.translate(x, y);
        let a = (ang * Math.PI) / 180;
        if (a > Math.PI / 2) a -= Math.PI; if (a < -Math.PI / 2) a += Math.PI;
        ctx.rotate(a);
        ctx.font = `500 ${fs}px ${SERIF}`;
        ctx.strokeStyle = `rgba(251,246,232,${(0.85 * ga).toFixed(3)})`; ctx.lineWidth = 3.2;
        const gap = fs * 0.5, w = ctx.measureText(text).width + gap * (text.length - 1);
        let px = -w / 2;
        for (const ch of text) { const cw = ctx.measureText(ch).width; ctx.strokeText(ch, px + cw / 2, 0); px += cw + gap; }
        ctx.fillStyle = `rgba(38,70,95,${(0.95 * ga * (o.lens ? 0.8 : 1)).toFixed(3)})`;
        px = -w / 2;
        for (const ch of text) { const cw = ctx.measureText(ch).width; ctx.fillText(ch, px + cw / 2, 0); px += cw + gap; }
        ctx.restore();
      };
      for (const l of W.riverLabels) { const [x, y] = cam.toScreen(l.x, l.y); if (x > -60 && y > -20 && x < vw + 60 && y < vh + 20) put(l.name, x, y, l.angle, 12.5); }
      for (const l of W.lakeLabels) { const [x, y] = cam.toScreen(l.x, l.y); if (x > -60 && y > -20 && x < vw + 60 && y < vh + 20) put(l.name, x, y, 0, 11.5); }
    }
  }

  draw(ctx, cam, o = {}) {
    ctx.textBaseline = 'middle'; ctx.textAlign = 'left'; ctx.lineJoin = 'round';
    // 시도 이름: 넓게 띄운 먹 글자
    for (const b of this.stateBoxes) {
      ctx.font = b.font;
      ctx.fillStyle = b.sel ? `rgba(184,50,31,${(0.9 * b.alpha).toFixed(3)})` : `rgba(29,26,22,${((o.lens ? 0.62 : 0.44) * b.alpha).toFixed(3)})`;
      ctx.strokeStyle = `rgba(251,246,232,${(0.55 * b.alpha).toFixed(3)})`; ctx.lineWidth = 3;
      let x = b.x;
      for (const ch of b.text) { const w = this.tw(ctx, b.font, ch); ctx.font = b.font; ctx.strokeText(ch, x, b.y + b.h / 2); ctx.fillText(ch, x, b.y + b.h / 2); x += w + b.gap; }
    }
    // 고을
    for (let k = this.placed.length - 1; k >= 0; k--) {
      const p = this.placed[k], st = p.state, c = p.c;
      // 고을 점
      ctx.beginPath();
      if (c.capital === '수도') {
        ctx.arc(p.ax, p.ay, 4.2, 0, 6.3); ctx.fillStyle = BAEK; ctx.fill(); ctx.strokeStyle = JU; ctx.lineWidth = 1.6; ctx.stroke();
        ctx.beginPath(); ctx.arc(p.ax, p.ay, 1.7, 0, 6.3); ctx.fillStyle = JU; ctx.fill();
      } else if (p.cls >= 2) {
        ctx.rect(p.ax - 3, p.ay - 3, 6, 6); ctx.fillStyle = INK; ctx.fill(); ctx.strokeStyle = BAEK; ctx.lineWidth = 1; ctx.stroke();
      } else {
        ctx.arc(p.ax, p.ay, 2.4, 0, 6.3); ctx.fillStyle = BAEK; ctx.fill(); ctx.strokeStyle = INK; ctx.lineWidth = 1.2; ctx.stroke();
      }
      const cy = p.y + p.h / 2 + 0.5;
      if (p.big || st) {
        ctx.fillStyle = st === 'sel' ? JU : HI;
        ctx.fillRect(p.x, p.y, p.w, p.h);
        ctx.strokeStyle = st === 'sel' ? JU : INK; ctx.lineWidth = 1;
        ctx.strokeRect(p.x + 0.5, p.y + 0.5, p.w - 1, p.h - 1);
        if (p.bandW && st !== 'sel') { ctx.fillStyle = c.capital === '수도' ? JU : INK; ctx.fillRect(p.x, p.y, p.bandW, p.h); }
        ctx.font = p.font; ctx.fillStyle = st === 'sel' ? BAEK : INK;
        ctx.fillText(c.name, p.x + p.bandW + p.padX, cy);
        if (p.pop) { ctx.font = p.pfont; ctx.fillStyle = st === 'sel' ? BAEK : INK2; ctx.fillText(p.pop, p.x + p.bandW + p.padX + p.nw + 7, cy + 0.5); }
      } else {
        ctx.font = p.font;
        ctx.strokeStyle = 'rgba(251,246,232,0.9)'; ctx.lineWidth = 3.2;
        ctx.strokeText(c.name, p.x + p.padX, cy);
        ctx.fillStyle = INK; ctx.fillText(c.name, p.x + p.padX, cy);
        if (p.pop) { ctx.font = p.pfont; ctx.strokeText(p.pop, p.x + p.padX + p.nw + 7, cy + 0.5); ctx.fillStyle = INK2; ctx.fillText(p.pop, p.x + p.padX + p.nw + 7, cy + 0.5); }
      }
    }
  }

  hitCity(x, y) {
    for (const p of this.placed) if (hit(p, x, y) || Math.hypot(x - p.ax, y - p.ay) < 7) return p.c;
    return null;
  }
  hitState(x, y) {
    for (const b of this.stateBoxes) if (hit(b, x, y)) return b.s;
    return null;
  }
}
