// 강·호수 이름표: 확대했을 때만. 강은 대권역 본류 5개(하천코드 규칙)를 선 방향으로, 호수는 넓이 15 km² 이상 이름 있는 수면.
// 도시 깃발·층 아이콘보다 먼저(아래에) 그리고, 서로 겹치거나 깃발·아이콘 상자(avoid)와 겹치면 그 이름표는 그리지 않는다 (7b #1).
// 강은 한 강에 세 지점이 있어 겹치지 않는 지점에 그려진다.

const FONT = '"Pretendard","Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif';

export class GeoLabels {
  constructor(world) {
    this.rivers = world.river_labels || [];
    this.lakes = (world.lake_labels || []).slice().sort((a, b) => b.area_km2 - a.area_km2);
  }

  draw(ctx, cam, lensOn, avoid = []) {
    const z = cam.scale / cam.minScale;
    this.drawn = [];
    if (z < 2.4) return;
    const placed = [];
    const ov = (r, p) => r.x0 < p.x1 && r.x1 > p.x0 && r.y0 < p.y1 && r.y1 > p.y0;
    const hit = (r) => placed.some((p) => ov(r, p)) || avoid.some((p) => ov(r, p));
    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    if ('letterSpacing' in ctx) ctx.letterSpacing = '1px';
    const fs = Math.min(14, 10 + (z - 2.4) * 0.9);
    // 강: 한 강의 세 지점 가운데 화면 안이고 겹치지 않는 곳
    for (const l of this.rivers) {
      const [sx, sy] = cam.toScreen(l.x, l.y);
      if (sx < -40 || sy < -20 || sx > cam.vw + 40 || sy > cam.vh + 20) continue;
      ctx.font = `italic 600 ${fs}px ${FONT}`;
      const w = ctx.measureText(l.name).width + 6, hgt = fs + 6;
      // 돌린 글자를 덮는 축 정렬 상자
      const an = (l.angle * Math.PI) / 180, hw = (Math.abs(Math.cos(an)) * w + Math.abs(Math.sin(an)) * hgt) / 2, hh = (Math.abs(Math.sin(an)) * w + Math.abs(Math.cos(an)) * hgt) / 2;
      const r = { x0: sx - hw, y0: sy - hh, x1: sx + hw, y1: sy + hh };
      if (hit(r)) continue;
      placed.push(r);
      this.drawn.push({ name: l.name, ...r });
      ctx.save();
      ctx.translate(sx, sy);
      ctx.rotate((l.angle * Math.PI) / 180);
      ctx.lineWidth = 3;
      ctx.strokeStyle = lensOn ? 'rgba(255,255,255,0.85)' : 'rgba(232,244,252,0.85)';
      ctx.strokeText(l.name, 0, 0);
      ctx.fillStyle = '#1d5a92';
      ctx.fillText(l.name, 0, 0);
      ctx.restore();
    }
    if (z >= 2.8) {
      for (const l of this.lakes) {
        const [sx, sy] = cam.toScreen(l.x, l.y);
        if (sx < -40 || sy < -20 || sx > cam.vw + 40 || sy > cam.vh + 20) continue;
        ctx.font = `italic 600 ${fs - 1}px ${FONT}`;
        const w = ctx.measureText(l.name).width + 6;
        const r = { x0: sx - w / 2, y0: sy - fs / 2 - 2, x1: sx + w / 2, y1: sy + fs / 2 + 2 };
        if (hit(r)) continue;
        placed.push(r);
        this.drawn.push({ name: l.name, ...r });
        ctx.lineWidth = 3;
        ctx.strokeStyle = 'rgba(232,244,252,0.85)';
        ctx.strokeText(l.name, sx, sy);
        ctx.fillStyle = '#1a4f80';
        ctx.fillText(l.name, sx, sy);
      }
    }
    ctx.restore();
  }
}
