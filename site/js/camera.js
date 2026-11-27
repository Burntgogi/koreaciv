// 이동·확대. 세계 좌표(화면 단위)의 한 점(x,y)이 화면 가운데에 오고, scale = 화면 px / 세계 단위.

export class Camera {
  constructor(worldW, worldH, hexR) {
    this.worldW = worldW;
    this.worldH = worldH;
    this.hexR = hexR;
    this.x = worldW / 2;
    this.y = worldH / 2;
    this.scale = 0.1;
    this.vw = 1;
    this.vh = 1;
    this.minScale = 0.05;
    this.maxScale = 1.2;
  }

  // insets: 화면 가장자리를 덮는 띠(상단 띠, 렌즈 띠)의 두께. 전국 화면은 그 사이에 맞춘다.
  resize(vw, vh, focus, insets) {
    this.vw = vw;
    this.vh = vh;
    this.insets = insets || { top: 0, bottom: 0, left: 0, right: 0 };
    const I = this.insets;
    // 전국(관심 범위)이 띠 사이에 드는 수준이 최소, 칸 하나(꼭짓점 사이 2R)가 약 60 px 인 수준이 최대
    const f = focus || { x0: 0, y0: 0, x1: this.worldW, y1: this.worldH };
    this.focus = f;
    const aw = Math.max(100, vw - I.left - I.right), ah = Math.max(100, vh - I.top - I.bottom);
    this.minScale = Math.min(aw / (f.x1 - f.x0), ah / (f.y1 - f.y0)) * 0.98;
    this.maxScale = 60 / (2 * this.hexR);
    this.clamp();
  }

  fit() {
    const f = this.focus, I = this.insets;
    this.scale = this.minScale;
    // 띠를 뺀 영역의 가운데에 관심 범위의 가운데가 오게
    this.x = (f.x0 + f.x1) / 2 - (I.left - I.right) / 2 / this.scale;
    this.y = (f.y0 + f.y1) / 2 - (I.top - I.bottom) / 2 / this.scale;
  }

  clamp() {
    this.scale = Math.min(this.maxScale, Math.max(this.minScale, this.scale));
    const f = this.focus || { x0: 0, y0: 0, x1: this.worldW, y1: this.worldH };
    // 화면 가운데가 관심 범위 안에 머물게 한다
    const I = this.insets || { top: 0, bottom: 0, left: 0, right: 0 };
    const mx = (Math.abs(I.left - I.right) / 2 + 1) / this.scale, my = (Math.abs(I.top - I.bottom) / 2 + 1) / this.scale;
    this.x = Math.min(f.x1 + mx, Math.max(f.x0 - mx, this.x));
    this.y = Math.min(f.y1 + my, Math.max(f.y0 - my, this.y));
  }

  toScreen(wx, wy) { return [(wx - this.x) * this.scale + this.vw / 2, (wy - this.y) * this.scale + this.vh / 2]; }
  toWorld(sx, sy) { return [(sx - this.vw / 2) / this.scale + this.x, (sy - this.vh / 2) / this.scale + this.y]; }

  // 화면 점 (sx,sy) 을 고정한 채 확대
  zoomAt(factor, sx, sy) {
    const [wx, wy] = this.toWorld(sx, sy);
    this.scale *= factor;
    this.scale = Math.min(this.maxScale, Math.max(this.minScale, this.scale));
    this.x = wx - (sx - this.vw / 2) / this.scale;
    this.y = wy - (sy - this.vh / 2) / this.scale;
    this.clamp();
  }

  pan(dx, dy) {
    this.x -= dx / this.scale;
    this.y -= dy / this.scale;
    this.clamp();
  }

  // 보이는 세계 범위
  view() {
    const hw = this.vw / 2 / this.scale, hh = this.vh / 2 / this.scale;
    return { x0: this.x - hw, y0: this.y - hh, x1: this.x + hw, y1: this.y + hh };
  }
}
