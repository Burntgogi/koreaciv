// 시도 이름: 가장 큰 육지 덩어리의 중심에 계산해 둔 위치·각도·크기로, 지형·경계 위 · 아이콘·깃발 아래 층에 반투명 명조로 새긴다 (7b #2).
// 깃발·우선 아이콘과 겹치면 가까운 자리(위·아래·옆) 가운데 덜 겹치는 곳으로 옮기되, 시도 이름 때문에 깃발이나 아이콘을 숨기지 않는다. 누르면 시도 패널.

const SERIF = '"Batang","AppleMyungjo","Nanum Myeongjo","Noto Serif KR",serif';

function overlap(a, b) {
  return Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) * Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0));
}
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export class StateLabels {
  constructor(states, cities) {
    // 광역시처럼 같은 이름의 도시 깃발이 있는 시도는 이름표를 생략한다 (깃발이 이름을 대신)
    const dup = new Set(cities.filter((c) => states.some((s) => s.code === c.sido && s.short === c.name)).map((c) => c.sido));
    this.states = states.filter((s) => !dup.has(s.code));
    this.boxes = [];
  }

  spacing(s, px) { return px * (s.short.length >= 4 ? 0.12 : 0.22); }

  // avoid: 이미 놓인 깃발·우선 아이콘 사각형 [{x0,y0,x1,y1}] -> 이름표 위치를 정하고 그 사각형(축 정렬) 목록을 돌려준다
  layout(ctx, cam, selected, avoid, lensOn = false) {
    this.boxes = [];
    const z = cam.scale / cam.minScale;
    this.lensOn = lensOn;
    this.alpha = lensOn ? clamp(0.82 - (z - 1) * 0.08, 0.34, 0.82) : clamp(0.82 - (z - 1) * 0.08, 0.36, 0.82);
    const cap = cam.vw <= 700 ? 24 : 34;
    for (const s of this.states) {
      const L = s.label;
      const [sx0, sy0] = cam.toScreen(L.x, L.y);
      const raw = L.size * cam.scale;
      // 너무 작게 나올 시도는 그 확대 수준에서 숨긴다
      // (명세 site_r3 는 14px 이었으나, 전국 첫 화면의 시도 이름 수가 고치기 전보다 늘지 않게 15px 그대로 둔다)
      if (raw < 15 && s.code !== selected) continue;
      const px = Math.min(cap, raw);
      if (sx0 < -200 || sy0 < -60 || sx0 > cam.vw + 200 || sy0 > cam.vh + 60) continue;
      ctx.font = `700 ${px}px ${SERIF}`;
      if ('letterSpacing' in ctx) ctx.letterSpacing = `${this.spacing(s, px).toFixed(1)}px`;
      const w = ctx.measureText(s.short).width + 8, h = px + 6;
      const a = (L.angle * Math.PI) / 180;
      // 회전한 글자 상자를 덮는 축 정렬 사각형의 반폭·반높이
      const hw = (Math.abs(Math.cos(a)) * w + Math.abs(Math.sin(a)) * h) / 2;
      const hh = (Math.abs(Math.sin(a)) * w + Math.abs(Math.cos(a)) * h) / 2;
      const cands = [[0, 0], [0, -1.15 * h], [0, 1.15 * h], [-0.45 * w, 0], [0.45 * w, 0], [0, -1.9 * h], [0, 1.9 * h]];
      let best = null;
      for (const [dx, dy] of cands) {
        const r = { x0: sx0 + dx - hw, y0: sy0 + dy - hh, x1: sx0 + dx + hw, y1: sy0 + dy + hh };
        let ov = 0;
        for (const f of avoid) ov += overlap(r, f);
        for (const b of this.boxes) ov += 4 * overlap(r, b.r);
        const score = ov + Math.hypot(dx, dy) * 0.5; // 같은 겹침이면 원래 자리 가까이
        if (!best || score < best.score) best = { score, dx, dy, r, ov };
        if (ov === 0) break;
      }
      this.boxes.push({ s, sx: sx0 + best.dx, sy: sy0 + best.dy, w, h, a, px, r: best.r });
    }
    if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
    return this.boxes.map((b) => b.r);
  }

  draw(ctx, selected) {
    const alpha = this.alpha, lens = this.lensOn;
    for (const b of this.boxes) {
      const s = b.s;
      ctx.save();
      ctx.translate(b.sx, b.sy);
      ctx.rotate(b.a);
      ctx.font = `700 ${b.px}px ${SERIF}`;
      if ('letterSpacing' in ctx) ctx.letterSpacing = `${this.spacing(s, b.px).toFixed(1)}px`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const sel = s.code === selected;
      ctx.lineJoin = 'round';
      ctx.lineWidth = lens ? Math.max(2.0, b.px * 0.14) : Math.max(1.5, b.px * 0.10);
      ctx.strokeStyle = sel ? 'rgba(18,14,4,0.85)' : lens ? `rgba(12,14,18,${alpha * 0.78})` : `rgba(18,16,12,${alpha * 0.62})`;
      ctx.strokeText(s.short, 0, 0);
      ctx.fillStyle = sel ? 'rgba(255,214,90,0.92)' : `rgba(255,248,232,${alpha})`;
      ctx.fillText(s.short, 0, 0);
      ctx.restore();
    }
    if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
  }

  hit(x, y) {
    for (const b of this.boxes) {
      const dx = x - b.sx, dy = y - b.sy;
      const c = Math.cos(-b.a), s = Math.sin(-b.a);
      const rx = dx * c - dy * s, ry = dx * s + dy * c;
      if (Math.abs(rx) <= b.w / 2 && Math.abs(ry) <= b.h / 2) return b.s;
    }
    return null;
  }
}
