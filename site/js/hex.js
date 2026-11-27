// 헥스 격자 수학. pipeline/lib/hexgrid.py 와 같은 규칙.
// 뾰족한 쪽이 위, 열 간격 W=√3R, 행 간격 1.5R, 홀수 행은 W/2 오른쪽 (odd-r).
// 칸 (col,row) 중심: x = W(col + 0.5(row&1)) + W/2, y = 1.5R·row + R. 칸 번호 = row*cols + col.

const SQRT3 = Math.sqrt(3);

// 이웃 순서: 동, 북동, 북서, 서, 남서, 남동 (y 는 아래로)
const NB_EVEN = [[1, 0], [0, -1], [-1, -1], [-1, 0], [-1, 1], [0, 1]];
const NB_ODD = [[1, 0], [1, -1], [0, -1], [-1, 0], [0, 1], [1, 1]];
// 이웃 방향 d 쪽 변의 두 꼭짓점 번호. 꼭짓점 k 는 각도 60k-30° (y 아래): 0 오른위, 1 오른아래, 2 아래, 3 왼아래, 4 왼위, 5 위
export const EDGE_CORNERS = [[0, 1], [5, 0], [4, 5], [3, 4], [2, 3], [1, 2]];

export class Grid {
  constructor(cols, rows, radius) {
    this.cols = cols;
    this.rows = rows;
    this.R = radius;
    this.W = SQRT3 * radius;
    this.n = cols * rows;
    this.width = this.W * (cols + 0.5);
    this.height = 1.5 * radius * (rows - 1) + 2 * radius;
    this.cx = new Float32Array(this.n);
    this.cy = new Float32Array(this.n);
    for (let i = 0; i < this.n; i++) {
      const r = Math.floor(i / cols), c = i - r * cols;
      this.cx[i] = this.W * (c + 0.5 * (r & 1)) + this.W / 2;
      this.cy[i] = 1.5 * radius * r + radius;
    }
    // 꼭짓점 상대 좌표
    this.corner = [];
    for (let k = 0; k < 6; k++) {
      const a = (Math.PI / 180) * (60 * k - 30);
      this.corner.push([radius * Math.cos(a), radius * Math.sin(a)]);
    }
  }

  center(i) { return [this.cx[i], this.cy[i]]; }

  // 6방향 이웃 번호 (격자 밖이면 -1)
  neighborSlots(i) {
    const r = Math.floor(i / this.cols), c = i - r * this.cols;
    const t = r & 1 ? NB_ODD : NB_EVEN;
    const out = new Array(6);
    for (let d = 0; d < 6; d++) {
      const cc = c + t[d][0], rr = r + t[d][1];
      out[d] = cc >= 0 && cc < this.cols && rr >= 0 && rr < this.rows ? rr * this.cols + cc : -1;
    }
    return out;
  }

  neighbors(i) { return this.neighborSlots(i).filter((j) => j >= 0); }

  // 화면 단위 좌표 -> 칸 번호 (격자 밖이면 -1)
  pointToCell(x, y) {
    const px = x - this.W / 2, py = y - this.R;
    const q = ((SQRT3 / 3) * px - py / 3) / this.R;
    const r = ((2 / 3) * py) / this.R;
    let rx = Math.round(q), rz = Math.round(r), ry = Math.round(-q - r);
    const dx = Math.abs(rx - q), dy = Math.abs(ry - (-q - r)), dz = Math.abs(rz - r);
    if (dx > dy && dx > dz) rx = -ry - rz;
    else if (dy > dz) ry = -rx - rz;
    else rz = -rx - ry;
    const row = rz, col = rx + ((row - (row & 1)) >> 1);
    if (col < 0 || col >= this.cols || row < 0 || row >= this.rows) return -1;
    return row * this.cols + col;
  }

  // 사각형(화면 단위) 과 겹칠 수 있는 칸의 행·열 범위
  range(x0, y0, x1, y1) {
    const r0 = Math.max(0, Math.floor((y0 - 2 * this.R) / (1.5 * this.R)));
    const r1 = Math.min(this.rows - 1, Math.ceil(y1 / (1.5 * this.R)));
    const c0 = Math.max(0, Math.floor(x0 / this.W) - 1);
    const c1 = Math.min(this.cols - 1, Math.ceil(x1 / this.W));
    return [c0, c1, r0, r1];
  }

  // 칸 경로를 ctx 에 추가 (s: 축척, ox/oy: 화면 원점에서 뺄 값)
  pathHex(ctx, i, s, ox, oy, shrink = 1) {
    const x = (this.cx[i] - ox) * s, y = (this.cy[i] - oy) * s;
    const k = s * shrink;
    ctx.moveTo(x + this.corner[0][0] * k, y + this.corner[0][1] * k);
    for (let j = 1; j < 6; j++) ctx.lineTo(x + this.corner[j][0] * k, y + this.corner[j][1] * k);
    ctx.closePath();
  }
}
