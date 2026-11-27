"""헥스 격자 수학. site/js/hex.js 와 같은 규칙을 쓴다.

- 뾰족한 쪽이 위(pointy-top). 외접원 반지름 R.
- 열 간격 W = √3·R, 행 간격 1.5·R. 홀수 행은 W/2 만큼 오른쪽으로 민다 (odd-r offset).
- 칸 (col, row) 의 중심: x = W·(col + 0.5·(row & 1)) + W/2,  y = 1.5·R·row + R   (화면 단위, y 는 아래로)
- 칸 번호 = row * cols + col
"""
import math

SQRT3 = math.sqrt(3.0)

# odd-r 이웃: (dcol, drow). 동, 북동, 북서, 서, 남서, 남동 순서 (y 가 아래로 증가하므로 북 = drow -1)
NEIGHBORS_EVEN = [(1, 0), (0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1)]
NEIGHBORS_ODD = [(1, 0), (1, -1), (0, -1), (-1, 0), (0, 1), (1, 1)]


class Grid:
    def __init__(self, cols, rows, radius):
        self.cols, self.rows, self.R = cols, rows, float(radius)
        self.W = SQRT3 * self.R
        self.n = cols * rows

    @property
    def width(self):
        return self.W * (self.cols + 0.5)

    @property
    def height(self):
        return 1.5 * self.R * (self.rows - 1) + 2 * self.R

    def center(self, idx):
        r, c = divmod(idx, self.cols)
        return self.W * (c + 0.5 * (r & 1)) + self.W / 2, 1.5 * self.R * r + self.R

    def neighbors(self, idx):
        r, c = divmod(idx, self.cols)
        out = []
        for dc, dr in (NEIGHBORS_ODD if r & 1 else NEIGHBORS_EVEN):
            cc, rr = c + dc, r + dr
            if 0 <= cc < self.cols and 0 <= rr < self.rows:
                out.append(rr * self.cols + cc)
        return out

    def neighbor_slots(self, idx):
        """6방향 각각의 이웃 번호 (격자 밖이면 -1). 변 그리기용."""
        r, c = divmod(idx, self.cols)
        out = []
        for dc, dr in (NEIGHBORS_ODD if r & 1 else NEIGHBORS_EVEN):
            cc, rr = c + dc, r + dr
            out.append(rr * self.cols + cc if 0 <= cc < self.cols and 0 <= rr < self.rows else -1)
        return out

    def point_to_cell_np(self, x, y):
        """numpy 배열 x, y (화면 단위) -> 칸 번호 배열 (격자 밖이면 -1)."""
        import numpy as np
        px = np.asarray(x, dtype=float) - self.W / 2
        py = np.asarray(y, dtype=float) - self.R
        q = (SQRT3 / 3 * px - py / 3) / self.R
        r = (2.0 / 3 * py) / self.R
        # 큐브 좌표 반올림
        cx, cz = q, r
        cy = -cx - cz
        rx, ry, rz = np.round(cx), np.round(cy), np.round(cz)
        dx, dy, dz = np.abs(rx - cx), np.abs(ry - cy), np.abs(rz - cz)
        fix_x = (dx > dy) & (dx > dz)
        fix_y = ~fix_x & (dy > dz)
        rx = np.where(fix_x, -ry - rz, rx)
        ry = np.where(fix_y, -rx - rz, ry)
        rz = np.where(~fix_x & ~fix_y, -rx - ry, rz)
        row = rz.astype(np.int64)
        col = rx.astype(np.int64) + (row - (row & 1)) // 2
        ok = (col >= 0) & (col < self.cols) & (row >= 0) & (row < self.rows)
        return np.where(ok, row * self.cols + col, -1)

    def point_to_cell(self, x, y):
        return int(self.point_to_cell_np([x], [y])[0])

    def sample_offsets(self):
        """칸을 고르게 덮는 표본점 37개 (중심 + 육각 고리 3겹)의 중심 기준 상대 좌표.

        간격 s = R·√(3/37) 의 삼각 격자에서 육각 거리 3 이내 점 37개를 고른다. 이 '반지름 3 육각형'은
        지수 37 부분격자로 평면을 빈틈없이 채우므로, 격자를 25.28° 돌려 칸 중심 격자와 맞추면
        이웃 칸의 표본점과 겹치거나 비는 곳 없이 전국을 같은 밀도로 덮는다.
        """
        s = self.R * math.sqrt(3.0 / 37.0)
        theta = -math.atan2(3 * SQRT3 / 2, 4 + 1.5)  # (4,3) 부분격자 벡터를 x 축에 맞춘다
        e1 = (s * math.cos(theta), s * math.sin(theta))
        e2 = (s * math.cos(theta + math.pi / 3), s * math.sin(theta + math.pi / 3))
        pts = []
        for i in range(-3, 4):
            for j in range(-3, 4):
                if max(abs(i), abs(j), abs(i + j)) <= 3:
                    pts.append((i * e1[0] + j * e2[0], i * e1[1] + j * e2[1]))
        pts.sort(key=lambda p: (round(p[0] ** 2 + p[1] ** 2, 6), p))
        assert len(pts) == 37
        return pts
