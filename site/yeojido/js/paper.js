// 한지 결: 닥 섬유와 얼룩을 절차적으로 그려 이어 붙일 수 있는 무늬(data URL)로 만든다. 이미지 파일을 쓰지 않는다.

export function makePaper(size = 512) {
  const cv = document.createElement('canvas');
  cv.width = cv.height = size;
  const ctx = cv.getContext('2d');
  let seed = 20260927;
  const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const W9 = [];
  for (const a of [-size, 0, size]) for (const b of [-size, 0, size]) W9.push([a, b]);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, size, size);
  // 얼룩 (종이 두께의 고르지 않음)
  for (let k = 0; k < 90; k++) {
    const x = rnd() * size, y = rnd() * size, r = 24 + rnd() * 60;
    const dark = rnd() < 0.55;
    for (const [ox, oy] of W9) {
      const g = ctx.createRadialGradient(x + ox, y + oy, 0, x + ox, y + oy, r);
      g.addColorStop(0, dark ? 'rgba(150,128,84,0.028)' : 'rgba(255,255,255,0.3)');
      g.addColorStop(1, dark ? 'rgba(150,128,84,0)' : 'rgba(255,255,255,0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, size, size);
    }
  }
  // 섬유: 가늘고 긴 곡선
  ctx.lineCap = 'round';
  for (let k = 0; k < 1300; k++) {
    const x = rnd() * size, y = rnd() * size, a = rnd() * Math.PI, len = 6 + rnd() * rnd() * 46;
    const dx = Math.cos(a) * len, dy = Math.sin(a) * len, bend = (rnd() - 0.5) * len * 0.5;
    ctx.strokeStyle = rnd() < 0.7 ? `rgba(120,98,58,${0.04 + rnd() * 0.07})` : `rgba(255,255,255,${0.25 + rnd() * 0.3})`;
    ctx.lineWidth = 0.4 + rnd() * 0.7;
    for (const [ox, oy] of W9) {
      ctx.beginPath();
      ctx.moveTo(x + ox, y + oy);
      ctx.quadraticCurveTo(x + ox + dx / 2 - dy / len * bend, y + oy + dy / 2 + dx / len * bend, x + ox + dx, y + oy + dy);
      ctx.stroke();
    }
  }
  // 티끌
  const img = ctx.getImageData(0, 0, size, size), d = img.data;
  for (let p = 0; p < d.length; p += 4) {
    const n = (rnd() - 0.5) * 9;
    d[p] += n; d[p + 1] += n; d[p + 2] += n * 0.9;
  }
  ctx.putImageData(img, 0, 0);
  return cv.toDataURL('image/png');
}
