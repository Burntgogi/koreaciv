// 이동·확대. 세계 좌표의 한 점(x,y)이 화면(캔버스) 가운데에 오고, scale = CSS px / 세계 단위.
// 기존판(site/js/camera.js)과 같은 좌표·배율 뜻이라 해시 v=x,y,scale 을 그대로 주고받는다.

export class Camera {
  constructor(worldW, worldH, hexR) {
    this.worldW = worldW; this.worldH = worldH; this.hexR = hexR;
    this.x = worldW / 2; this.y = worldH / 2; this.scale = 0.1;
    this.vw = 1; this.vh = 1;
    this.minScale = 0.05; this.maxScale = 1.2; this.fitScale = 0.1;
    this.insets = { top: 0, bottom: 0, left: 0, right: 0 };
    this.anim = null;
  }

  resize(vw, vh, focus, insets) {
    this.vw = vw; this.vh = vh;
    if (insets) this.insets = insets;
    if (focus) this.focus = focus;
    this.fitScale = this.fitTarget().scale;
    this.minScale = this.fitScale * 0.9;
    this.maxScale = 72 / (2 * this.hexR);
    this.clamp();
  }

  // 여백(insets)을 뺀 영역에 관심 범위를 맞춘 자리
  fitTarget(insets = this.insets) {
    const f = this.fitFocus || this.focus, I = insets;
    const aw = Math.max(80, this.vw - I.left - I.right), ah = Math.max(80, this.vh - I.top - I.bottom);
    const scale = Math.min(aw / (f.x1 - f.x0), ah / (f.y1 - f.y0));
    return { scale, x: (f.x0 + f.x1) / 2 - (I.left - I.right) / 2 / scale, y: (f.y0 + f.y1) / 2 - (I.top - I.bottom) / 2 / scale };
  }
  fit() { Object.assign(this, this.fitTarget()); }

  // 세계 점이 여백을 뺀 영역 가운데에 오는 자리
  centerTarget(wx, wy, scale, insets = this.insets) {
    scale = Math.min(this.maxScale, Math.max(this.minScale, scale));
    return { scale, x: wx - (insets.left - insets.right) / 2 / scale, y: wy - (insets.top - insets.bottom) / 2 / scale };
  }

  flyTo(t, ms = 520) {
    if (ms <= 0) { this.x = t.x; this.y = t.y; this.scale = t.scale; this.anim = null; this.clamp(); return; }
    this.anim = { t0: performance.now(), ms, from: { x: this.x, y: this.y, scale: this.scale }, to: t };
  }

  // 한 프레임 진행. 움직이는 중이면 true
  step(now) {
    const a = this.anim;
    if (!a) return false;
    const u = Math.min(1, (now - a.t0) / a.ms);
    const e = 1 - Math.pow(1 - u, 4);
    this.scale = Math.exp(Math.log(a.from.scale) + (Math.log(a.to.scale) - Math.log(a.from.scale)) * e);
    // 확대 비율에 맞춰 중심을 옮겨야 목표점이 곧게 다가온다
    const ks = a.to.scale === a.from.scale ? e : (1 / a.from.scale - 1 / this.scale) / (1 / a.from.scale - 1 / a.to.scale);
    this.x = a.from.x + (a.to.x - a.from.x) * ks;
    this.y = a.from.y + (a.to.y - a.from.y) * ks;
    if (u >= 1) { this.anim = null; this.clamp(); }
    return true;
  }

  clamp() {
    this.scale = Math.min(this.maxScale, Math.max(this.minScale, this.scale));
    const f = this.focus || { x0: 0, y0: 0, x1: this.worldW, y1: this.worldH };
    const I = this.insets;
    const mx = (Math.abs(I.left - I.right) / 2 + 1) / this.scale, my = (Math.abs(I.top - I.bottom) / 2 + 1) / this.scale;
    this.x = Math.min(f.x1 + mx, Math.max(f.x0 - mx, this.x));
    this.y = Math.min(f.y1 + my, Math.max(f.y0 - my, this.y));
  }

  toScreen(wx, wy) { return [(wx - this.x) * this.scale + this.vw / 2, (wy - this.y) * this.scale + this.vh / 2]; }
  toWorld(sx, sy) { return [(sx - this.vw / 2) / this.scale + this.x, (sy - this.vh / 2) / this.scale + this.y]; }

  zoomAt(factor, sx, sy) {
    this.anim = null;
    const [wx, wy] = this.toWorld(sx, sy);
    this.scale = Math.min(this.maxScale, Math.max(this.minScale, this.scale * factor));
    this.x = wx - (sx - this.vw / 2) / this.scale;
    this.y = wy - (sy - this.vh / 2) / this.scale;
    this.clamp();
  }
  pan(dx, dy) { this.anim = null; this.x -= dx / this.scale; this.y -= dy / this.scale; this.clamp(); }

  view() { const hw = this.vw / 2 / this.scale, hh = this.vh / 2 / this.scale; return { x0: this.x - hw, y0: this.y - hh, x1: this.x + hw, y1: this.y + hh }; }
  get z() { return this.scale / this.fitScale; }      // 전도(1) 대비 확대 배율
  get rc() { return this.hexR * this.scale; }         // 칸 반지름 (CSS px)
}
