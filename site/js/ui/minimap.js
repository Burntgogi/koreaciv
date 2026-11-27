// 미니맵: 시도 색으로 칠한 작은 지도 + 지금 보이는 범위. 누르거나 끌면 그곳으로 이동.

import { STATE_COLORS } from '../render/terrain.js';

export class Minimap {
  constructor(app) {
    this.app = app;
    this.wrap = document.getElementById('minimap');
    this.cv = this.wrap.querySelector('canvas');
    this.ctx = this.cv.getContext('2d');
    this.base = null;
    const go = (e) => {
      const r = this.cv.getBoundingClientRect();
      const f = app.focus;
      const x = f.x0 + ((e.clientX - r.left) / r.width) * (f.x1 - f.x0);
      const y = f.y0 + ((e.clientY - r.top) / r.height) * (f.y1 - f.y0);
      app.cam.x = x;
      app.cam.y = y;
      app.cam.clamp();
      app.requestDraw();
    };
    let down = false;
    this.cv.addEventListener('pointerdown', (e) => { down = true; this.cv.setPointerCapture(e.pointerId); go(e); });
    this.cv.addEventListener('pointermove', (e) => down && go(e));
    this.cv.addEventListener('pointerup', () => { down = false; });
  }

  draw() {
    const a = this.app, f = a.focus, G = a.grid, w = a.world;
    const W = 168, H = Math.round((W * (f.y1 - f.y0)) / (f.x1 - f.x0));
    const dpr = a.dpr || 1;
    this.cv.width = W * dpr;
    this.cv.height = H * dpr;
    this.cv.style.width = W + 'px';
    this.cv.style.height = H + 'px';
    this.W = W;
    this.H = H;
    const b = document.createElement('canvas');
    b.width = W * dpr;
    b.height = H * dpr;
    const c = b.getContext('2d');
    c.fillStyle = '#1b3e63';
    c.fillRect(0, 0, b.width, b.height);
    const s = (W * dpr) / (f.x1 - f.x0);
    for (let i = 0; i < G.n; i++) {
      const o = w.owner[i];
      if (o < 0 && !w.foreign[i]) continue;
      c.beginPath();
      G.pathHex(c, i, s, f.x0, f.y0, 1.1);
      c.fillStyle = o >= 0 ? STATE_COLORS[w.states[o].code] : '#7d786b';
      c.fill();
    }
    this.base = b;
    this.drawView();
  }

  drawView() {
    if (!this.base) return;
    const a = this.app, f = a.focus, c = this.ctx, dpr = a.dpr || 1;
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.drawImage(this.base, 0, 0);
    const v = a.cam.view();
    const sx = (this.W * dpr) / (f.x1 - f.x0);
    c.strokeStyle = '#fff3c4';
    c.lineWidth = 1.5 * dpr;
    c.strokeRect((v.x0 - f.x0) * sx, (v.y0 - f.y0) * sx, (v.x1 - v.x0) * sx, (v.y1 - v.y0) * sx);
    c.fillStyle = 'rgba(255,243,196,0.12)';
    c.fillRect((v.x0 - f.x0) * sx, (v.y0 - f.y0) * sx, (v.x1 - v.x0) * sx, (v.y1 - v.y0) * sx);
  }
}
