# koreaciv 프런트엔드 브레인스토밍 3회차 최종 구현 명세 (`site_r3`)

작성일: 2026-11-27  
대상: `C:\work\korea\site` (`koreaciv`, 바닐라 ES 모듈 + Canvas, 외부 라이브러리·CDN·서버 없음)  
연동 대상: `C:\work\korea\design2` (신여지도 — 동일 `site/data/*.json` 및 공유 URL 해시 사용), `C:\work\korea\pipeline` (정적 JSON 빌드 파이프라인)  
근거 문서: `docs/ideas/site_r1.md`, `docs/ideas/site_r2.md`, `docs/AUDIT_CODEX.md` (독립 감사 23건), `docs/screenshots/6_*.png`

전제 원칙:
1. **데이터 추가 제외**: 현행 `site/data/*.json` 11종과 기존 `data/build/*`에 이미 있는 원표·필드만 쓴다. 결측은 `"자료 없음"`, 비공개는 `"비공개"`로 두고 추정·보간·과장 수치를 만들지 않는다.
2. **감사 결함 수정 선행·통합**: `AUDIT_CODEX.md` 23건의 수정이 먼저이며, 감사 결함과 같은 영역(패널 주석·광역시 범위·개편 구역·PNG 출처/범례·해시·접근성·대비)을 건드리는 안은 감사 권장 수정과 **한 번의 변경으로 맞물리게** 설계한다.
3. **빌드 단계 공용 계산**: 새로 넣는 계산(전국 대비 기준값, 산업 입지계수 LQ·특성 태그, 닮은 도시 근거, 추천 시점)은 빌드 단계(`pipeline/build_phase6.py` 또는 후속 `pipeline/build_insights.py`)에서 `site/data/*.json`에 직렬화해 `site/`와 `design2/`가 동일한 숫자와 규칙을 공유한다.
4. **JSON 총량 제약 준수**: `pipeline/validate.py` F6 한도(`5,000,000`바이트)를 지킨다. 현재 `site/data/*.json` 합계는 `4,625,778`바이트(여유 `374,222`바이트)이며, 감사 18(`lenses.json` 5개 렌즈 `land_values` 전환, 약 `−450 KB`)과 결합하면 전체 JSON은 오히려 현재보다 작아진다.

---

## 1. 최종 채택안 분류

2회차 후보 11개 안을 **"반드시(이번에)" 7개**, **"하면 좋음(여유 있으면)" 3개**, **"이번엔 안 함" 1개**(+ 1회차에서 이미 제외한 21개 유지)로 확정한다.

### 1.1 반드시 (이번에) — 7개

| 순번 | 안 번호·제목 | 영역 | 핵심 선정 이유 및 감사 연동 |
|---|---|---|---|
| 1 | **#2 시도 이름 각인화와 층위 하향** | 지도 | 최소 비용으로 전국·모바일 첫 화면의 시도 글자-깃발 정면충돌 제거(`banners.avoid()` 폐지). #1의 선행 작업. |
| 2 | **#1 아이콘·깃발 통합 배치 예산과 전략 인프라 우선권** | 지도 | 전국 배율에서 공항(6)·무역항(8)이 대도시 깃발에 밀려 증발하는 왜곡 해소 + `GeoLabels` 겹침 방지 + 감사 22(정밀도 한국어화) 연동. |
| 3 | **#12 다섯 산출 5열 1행 스트립 + 단일 '기준과 주의' 서랍** | 패널 | 3+2 비대칭 산출과 구역마다 산재된 주석 서랍을 정리. **감사 16**(생산 부분합 설명 오류)과 한 번에 수정. |
| 4 | **#9 도시 패널 4탭 구조화(개요·경제·시설·교역·땅·행정)** | 패널 | 세로 스크롤 60% 단축, 1280×800에서 스크롤 없이 순위까지 노출. **감사 05·08·11·14·21**과 한 번에 통합. |
| 5 | **#10 핵심 지표 전국 기준 대비(▲/▼) 및 순위 미니 게이지** | 패널·빌드 | `nation.json`에 공용 벤치마크 직렬화(신여지도 공유). **감사 01·14·20**과 연동해 단위 중복·개편 구역·배지 대비 일괄 해결. |
| 6 | **#11 산업 입지계수(LQ) 및 엄격한 특성 태그(상한 2개)** | 패널·빌드 | `cities.json`에 LQ·태그 직렬화(신여지도 공유). 과잉 해석을 막기 위해 **상한 2개**·사실 수치 문구·소규모 지역 자동 주석 고정. |
| 7 | **#32 PNG 크로스브라우저 안정화 및 1:1 정사각 카드** | 공유 | **감사 03**(PNG 출처·ODbL·고정 주소 누락)·**감사 12**(범례 8개 절단 — 최대 산업 14개 중 6개 누락)와 정면 통합 수정. |

### 1.2 하면 좋음 (여유 있으면) — 3개

| 순번 | 안 번호·제목 | 영역 | 보류 조건 및 가치 |
|---|---|---|---|
| 8 | **#13 '닮은 도시' 유사 근거 1줄 요약** | 패널·빌드 | `build_econ.py`의 실제 4축 거리 그대로 `cities.json`에 근거 직렬화. #14 없이도 단독 가치 있으며 #14 추가 시 우측 `비교` 버튼 직결. |
| 9 | **#14 도시 대 도시(A vs B) 최소 비교 모드** | 비교·지도 | 패널 폭 전환(`460px`), 지도 아크, `#cmp=a,b`까지 변경 폭·위험이 가장 큼. **#9 탭과 중첩되지 않는 '탭 없는 단일 1면 핵심 대조표'** 최소 형태로 명세. |
| 10 | **#20 데이터 규칙 기반 추천 시점 6선** | 온보딩·빌드 | 수동 편집 목록을 배제하고, `nation.json` 빌드 시점 극값 규칙으로 6장면을 자동 생성(신여지도 공유). 신규 해시 키 없음. |

### 1.3 이번엔 안 함 — 1개 (+ 2회차 제외 21개 유지)

- **#18 렌즈 직전 대비(`B`) · 지형 엿보기(`Space` 홀드) · 짝 렌즈 제안** — 제외 사유 3가지:
  1. `Space` 키 홀드는 **감사 10(키보드 접근성)**에서 반드시 살려야 하는 `<button>`·`<summary>`·`role="tab"` 활성화 및 스크롤과 충돌 위험이 가장 크다.
  2. `#legend` 제목 줄에 `⇄`·`👁` 버튼 2개와 하단 수동 짝 렌즈 1줄을 추가하면 390px 모바일의 접힘 토글 `<h5>`와 터치 충돌이 생기고, 수동 짝 테이블은 유지보수·편향 부담이 남는다.
  3. `terrain.js`에 `peekCache`를 추가하면 LRU 상한 없이 512px 오프스크린 캔버스 메모리가 2배로 늘어 모바일 Safari 메모리 위험을 키운다.
- *(유지)* 1회차에서 이미 제외한 21개(#3, #4, #5, #6, #7, #8, #15, #16, #17, #19, #21, #22, #23, #24, #26, #27, #28, #29, #30, #31 — #25는 #32에 흡수)는 그대로 제외한다. 단 #29(타일 LRU)·#31(키보드 접근성)의 결함 성격 요소는 감사 10 및 성능 보수 작업으로 별도 처리한다.

---

## 2. 빌드 단계 공용 데이터 변경 총괄 (`site/` · `design2/` 공유)

새 계산을 모두 빌드 파이프라인(`pipeline/build_phase6.py` 끝부분 또는 `pipeline/build_all.py`의 `build_phase6.py` 직후 신설 `pipeline/build_insights.py` — `build_sources.py` 및 `validate.py` 앞)에 배치한다. 두 프런트엔드(`site/`, `design2/`)는 빌드된 JSON만 읽어 동일한 숫자를 표시한다.

| 대상 JSON | 추가 필드 | 관련 안 | 예상 추가 바이트 (실측) |
|---|---|---|---:|
| `site/data/wonders.json` | `zoom.draw_priority.second`, `zoom.budget`, 갱신된 `zoom.draw_priority.rule` | #1 | `+520 B` |
| `site/data/cities.json` | `cities[i].scope_label` (5개 광역시만), `cities[i].lq_gdp`, `cities[i].lq_jobs`, `cities[i].tags` | 감사 05, #9, #11 | `+72,300 B` |
| `site/data/cities.json` | `cities[i].peer_reasons` (`하면 좋음` #13 채택 시) | #13 | `+39,940 B` |
| `site/data/nation.json` | `nation.benchmarks` (전국값·도시 중앙값 16항목 + 규칙), `nation.lq_rule` | #10, #11 | `+1,350 B` |
| `site/data/nation.json` | `presets` (`하면 좋음` #20 채택 시 — 데이터 규칙 6선) | #20 | `+1,690 B` |
| **합계 ("반드시" 7개)** | | | **`+74,170 B` (+74.2 KB)** |
| **합계 ("반드시" + "하면 좋음" 10개)** | | | **`+115,800 B` (+115.8 KB)** |

- **F6(5 MB) 검증 여유**:
  - 현행 JSON 총합: `4,625,778 B` (`4.626 MB`)
  - 감사 18 선행 전 + 전체 10안 적용 시: `4,741,578 B` (`4.742 MB`, 여유 `258 KB`)
  - 감사 18(`density`·`over65`·`extinction`·`pm25`·`heritage` 5종 `land_values` 전환, 약 `−450 KB`) 선행 후 + 전체 10안 적용 시: 약 **`4.29 MB`** (현재보다 약 `334 KB` 감소).

---

## 3. "반드시" 7개 구현 명세

---

### [반드시 1] #2. 시도 이름 각인화와 층위 하향

#### 3.1.1 빌드 단계 변경
- **JSON 변경 없음** (`0 B`). 기존 `states.json`의 `states[i].{code, short, label.{x, y, angle, size}}`와 `cities.json`의 `cities[i].{sido, name}` 그대로 사용.
- 연감 `인구·도시` 탭(`site/js/ui/almanac.js`) 규칙 문구만 추가:
  > "시도 이름은 지형·경계 위, 아이콘·도시 깃발 아래에 반투명 명조체로 새긴다. 광역시·특별시·세종처럼 같은 이름의 도시 깃발이 있는 시도는 이름표를 중복 표시하지 않으며, 시도 이름 때문에 도시 깃발을 숨기지 않는다."

#### 3.1.2 화면 변경
- **수정 파일**: `site/js/render/labels.js`, `site/js/render/banners.js`, `site/js/main.js`.
- **그리기 순서 변경 (`main.js` `drawScene()`)**:
  - 기존: `geoLabels` → `banners.layout` → `labels.layout` → `banners.avoid` → `layerR.layout/drawIcons` → `banners.draw` → `labels.draw`.
  - 변경: `banners.avoid()` 호출 및 메서드 삭제. 배치(layout)는 `banners.layout` → `layerR.layout` → `labels.layout` 순으로 계산하고, 그리기(draw)는 **`labels.draw` → `geoLabels.draw` → `layerR.drawIcons` → `banners.draw`** 순으로 내린다.
- **타이포그래피·시각 상태 (`labels.js`)**:
  - 글꼴: `700 ${px}px "Batang","AppleMyungjo","Nanum Myeongjo","Noto Serif KR",serif`.
  - 크기: `raw = s.label.size * cam.scale`; `raw < 14 && s.code !== selected`이면 생략; `px = Math.min(34, raw)`.
  - 자간: `s.short.length >= 4` (`전남광주`)이면 `px * 0.12`, 그 외는 `px * 0.22` (`'letterSpacing' in ctx` 가드 유지).
  - 불투명도 및 외곽선:
    - 지형 모드(`!lensOn`): `alpha = clamp(0.64 - (z - 1) * 0.08, 0.22, 0.64)`, `lineWidth = Math.max(1.5, px * 0.10)`, `strokeStyle = rgba(18,16,12, alpha * 0.45)`, `fillStyle = rgba(255,248,232, alpha)`.
    - 렌즈 모드(`lensOn`): `alpha = clamp(0.74 - (z - 1) * 0.08, 0.26, 0.74)`, `lineWidth = Math.max(2.0, px * 0.14)`, `strokeStyle = rgba(12,14,18, alpha * 0.78)`.
    - 선택 시도(`s.code === selected`): `fillStyle = rgba(255,214,90, 0.92)`, `strokeStyle = rgba(18,14,4, 0.85)`.
- **데스크톱·390px 모바일 배치**:
  - 390px(`cam.vw <= 700`)에서는 `px = Math.min(24, raw)`로 상한을 낮춰 `6_mobile_first.png`처럼 `경북·충남·전북`이 국토 절반을 덮지 않게 한다.
  - 7개 후보 위치 탐색 시 `flags` + `P1 아이콘 상자`와 겹침 면적이 최소인 자리를 고르되, 겹침이 남아도 깃발·아이콘을 제거하지 않는다.

#### 3.1.3 상호작용 · 해시 · 결측/개편 · 접근성
- **마우스·키보드·터치**: `main.js` `click()`/`hover()` 판정 순서 `깃발 → 아이콘 → 교역로 → 시도 이름표 → 빈 육지(시도)` 유지.
- **Esc · 단축키**: 변경 없음. 충돌 없음.
- **해시 키**: 없음.
- **자료 없음 · 부분 합 · 개편 구역**: 16개 시도 모두 `label` 보유. `전남광주통합특별시(code: '12')`는 동명 도시가 없으므로 표시되며 4글자 자간 축소(`0.12em`)로 경계 일탈 방지.
- **접근성**: 캔버스 장식 라벨이므로 별도 초점 없음(시도 선택은 검색 `/` 또는 빈 육지 클릭·순위 보고서로 동일 접근).

---

### [반드시 2] #1. 아이콘·깃발 통합 배치 예산과 전략 인프라 우선권

#### 3.2.1 빌드 단계 변경
- **대상 파일**: `pipeline/build_phase6.py` → `site/data/wonders.json` (`+520 B`).
- **추가·수정 필드 (`wonders.json` `zoom`)**:
  ```json
  "draw_priority": {
    "first": ["nuclear"],
    "second": ["airport", "trade_port"],
    "rule": "전국 배율(z < 2.0)에서는 원전 5곳을 최우선(깃발 좌우 회피 허용)으로, 전국 배율 공항 6곳과 무역항 8곳을 전략 인프라 우선군(깃발은 제자리에 두고 아이콘만 2.4r 이내 가장 가까운 빈 칸으로 옮겨 원래 칸 중심에 선을 이음)으로 먼저 놓는다. 그 밖의 전국 배율 아이콘은 깃발과 겹치지 않는 범위에서 데스크톱 최대 52개, 모바일 최대 24개까지 종류 우선순위·값 순으로 그린다."
  },
  "budget": {
    "z_max": 2.0,
    "flags_desktop": 24,
    "flags_mobile": 12,
    "icons_desktop": 52,
    "icons_mobile": 24,
    "mobile_vw": 700
  }
  ```
- `design2/`도 `wonders.json`의 `zoom.draw_priority.second`와 `zoom.budget`을 그대로 참조할 수 있다.

#### 3.2.2 화면 변경
- **수정 파일**: `site/js/render/banners.js`, `site/js/render/layers.js`, `site/js/render/geolabels.js`, `site/js/ui/tooltip.js`, `site/js/main.js`.
- **단일 배치 파이프라인 (`main.js` `drawScene()`)**:
  1. **P1a 예약 (`layerR.priorityBoxes`)**: `first` (`nuclear` 5곳) 제자리 상자 수집.
  2. **도시 깃발 (`banners.layout`)**: 우선순위 `selCity(·cmpCity)` → `capital !== '없음'`(18곳, 인구 내림차순) → `population >= 500000` → 나머지 `population >= 150000 / (z*z)`.
     - 전국 배율(`z < budget.z_max`): 화면 상한 `flags_desktop = 24`, `flags_mobile = 12` (`cam.vw <= 700`). `selCity`는 상한과 무관하게 항상 표시. `z >= 2.0`이면 상한 해제.
  3. **지도 층 아이콘 (`layerR.layout`)**:
     - `SECOND = new Set(this.zoom.draw_priority?.second || ['airport', 'trade_port'])`.
     - 정렬: `selId` → `P1a(first)` → `P1b(second && tier === 0)` → `P2(나머지, cmp 순)`.
     - **P1a (`nuclear`)**: 현행 유지(깃발 회피 후 불가피 시 이웃 칸 오프셋 + 지시선).
     - **P1b (`airport` 6, `trade_port` 8)**: 깃발을 밀지 않음. 제자리가 깃발 글씨 상자·도시 점·기존 아이콘과 겹치면 `rings(rp.cell, maxRing)`에서 화면 거리 `<= maxDist` (`max(2.4 * r0, 22)`, 모바일 `max(2.0 * r0, 18)`) 내 가장 가까운 빈 칸(바다 칸 포함)으로 이동하고 원래 칸 중심(`ox, oy`)에 기준점과 가는 지시선 연결. `kind === 'trade_port'`는 바다 칸(`world.water[c] > 0`) 비용에 `-4` 가중.
     - **P2 (나머지)**: 전국 배율(`z < 2.0`)에서 `out.length >= iconBudget` (`52` / 모바일 `24`)이면 중단. 깃발 상자 겹침 시 숨김.
  4. **시도 이름표 (`labels.layout`)**: `flags` + `P1a/P1b` 상자 회피(#2).
  5. **강·호수 이름표 (`geolabels.draw(ctx, cam, lensOn, avoidRects)`)**: `flags` + `layerR.placed` 상자를 `avoidRects`로 받아 겹치는 강·호수 이름표 후보를 건너뛴다(강은 3개 후보 지점 중 빈 곳 자동 선택).
- **문구 초안 (툴팁 · 감사 22 연동)**:
  - `layers.js` `PRECISION`: 영문 키 괄호 제거 → `point: '원자료 좌표'`, `area: '경계 폴리곤 대표점'`, `county: '시군구 대표 위치 (인구 가중 중심)'`, `sido: '시도 해안 대표 위치'`.
  - 오프셋된 아이콘(`p.ox != null`) 툴팁 끝 1줄: `"깃발과 겹쳐 옆 칸에 표시 (원래 위치는 선 끝 점)"`.

#### 3.2.3 상호작용 · 해시 · 결측/개편 · 접근성
- **마우스·터치**: 아이콘 히트 반경은 마우스 `Math.max(p.r + 2, 10)`, 터치(`pointerType === 'touch'`) 시 `Math.max(p.r + 4, 14)`. 지시선 끝 점이 아닌 배지 중심 `(p.x, p.y)`로 판정. `hover()`·`click()`에서 `layerR.hit(sx, sy, isTouch)` 전달.
- **키보드 · Esc · 단축키**: 기존 `R`(자원 토글) 유지. 충돌 없음.
- **해시 키**: 없음.
- **자료 없음 · 부분 합 · 개편 구역**: `cell == null`인 `unplaced` 항목(댐 등)은 배치 제외(검색·패널·연감 유지). 부산항·울산항(`city: null, precision: 'sido'`)은 바다 쪽 오프셋 우대로 부산·울산 깃발 옆 해안에 안정 배치.
- **접근성**: 툴팁에 오프셋 안내·정밀도 한국어 문구를 텍스트 노드(`esc()` 처리, 감사 07)로 제공.

---

### [반드시 3] #12. 다섯 산출 5열 1행 스트립 + 단일 '기준과 주의' 서랍

#### 3.3.1 빌드 단계 변경
- **JSON 변경 없음** (`0 B`). 기존 `cities[i].{yields, yields_partial, production_mining_excluded, ranks, jobs, jobs_total, gdp_undisclosed}`, `states[i].official.gdp`, `nation.nation.official.gdp`, `nation.econ.{jobs_map, ksic_ko, industry_ko}` 사용.
- **감사 16 정정 반영**: `cities.json`의 서울·부산 등 생산 부분 합은 실제로 `제조업 + 건설업 + 공개된 광업` 합계(비공개 광업 행만 제외)이므로, `banners.js` `partialNote` 및 `panel.js` 주석 문구에서 `"제조업 + 건설업으로 냈다"`를 **전면 수정**한다.
- 규칙 문장 (연감 `산출` 탭):
  > "패널 상단 다섯 산출 칸은 도시의 경우 시군구 합 명목 부가가치와 167개 도시 중 순위를, 시도·전국은 공식 지역소득 값을 5열 한 줄로 요약한다. 점선 테두리와 * 표시는 광업 비공개 몫을 뺀 부분 합계(제조업 + 건설업 + 공개된 광업)이며, 각 칸을 누르면 구성 산업과 사업장 기준 종사자 수를 확인할 수 있다."

#### 3.3.2 화면 변경
- **수정 파일**: `site/js/ui/panel.js`, `site/js/render/banners.js`, `site/css/style.css`.
- **다섯 산출 스트립 (`.yields`)**:
  - 레이아웃: `grid-template-columns: repeat(5, minmax(0, 1fr))`, `gap: 4px`.
  - 각 칸을 `<button type="button" class="yt [partial]" data-ytip="...">`로 구현(3줄 고정):
    1. `<em>` `🌾 식량` / `⚙️ 생산` / `💰 금` / `🔬 과학` / `🎭 문화` (`font-size: 10px`)
    2. `<b>` `fmtWon(v)` + 부분 합 시 `<sup class="pm">*</sup>` (`font-size: clamp(11px, 3vw, 13px); font-variant-numeric: tabular-nums;`)
    3. `<small>` 도시는 `${rank}위`, 시도·전국은 `공식 '${yy}`
  - 제거된 4번째 줄(`👷 종사자 수`, 구성 산업 규칙, 시군구 합·잠정치)은 타일 클릭/호버 시 `#fnpop` 말풍선과 `경제` 탭 본문으로 이동.
  - **데스크톱 (`> 700px`)**: `360px` 패널 폭(내부 `328px`)에서 칸당 `62.4px`, 5칸 모두 1행 표시(줄바꿈 없음).
  - **390px 모바일**: 패널 내부 `358px`에서 칸당 `68.4px`, 5열 1행 유지. `350px` 미만 초소형 폭에서만 `overflow-x: auto; grid-auto-columns: minmax(62px, 1fr);`.
- **단일 '기준과 주의' 서랍 (`Panel.prototype.footnotes()`)**:
  - 기존: 구역(`.lyg` / `h4`)마다 `<details class="caveats">`를 개별 생성(도시 패널당 최대 8~9개 산재).
  - 변경: `footnotes(scopeEl)`가 **도시 패널은 각 탭(`.ptab`) 최하단에 단 1개**, 시도·전국·항목 패널은 **패널 최하단(`.foot` 바로 위)에 단 1개**의 `<details class="caveats"><summary>기준과 주의 <small>N건</small></summary><ol>...</ol></details>`만 생성한다.
  - 각 값 옆 `ⓘ` 버튼(`data-fn="k"`)은 기존과 동일하게 호버·클릭·포커스 시 `#fnpop` 말풍선을 연다. 주석 번호 `1..K`는 탭(스코프)마다 독립 부여해 숨은 탭 번호가 건너뛰지 않게 한다.
- **감사 16 정확한 부분 합 문구 초안**:
  - 생산 부분 합 말풍선·주석: `"제조업 + 건설업 + 공개된 광업의 합 (광업 비공개 ${n}곳 제외, 비공개 몫은 추정해 더하지 않음)"`.

#### 3.3.3 상호작용 · 해시 · 결측/개편 · 접근성
- **마우스·키보드·터치**:
  - 각 산출 타일(`.yt`)은 `<button type="button">` — 마우스 호버 시 `#fnpop` 임시 표시, 클릭·`Enter`·`Space`·터치 탭 시 `#fnpop` 고정 토글, 다시 누르거나 바깥 클릭·`Esc`로 닫힘.
- **Esc 순서**: `#fnpop`(산출 말풍선·ⓘ 주석)이 **최우선 1순위**로 닫힌다(`main.js` `escape()`).
- **해시 키**: 없음.
- **자료 없음 · 부분 합 · 개편 구역**:
  - `yields[k] == null` → `<b><span class="na">자료 없음</span></b>`, 말풍선에 `gdp_undisclosed` 산업명 나열.
  - `yields_partial.production` 18개 도시(서울·부산·대전·부천 등) → `.yt.partial` 점선 테두리 + 주황 `*` + 감사 16 정정 문구.
  - `전남광주통합특별시(12)` 시도 패널 말풍선에 `"광주 + 전남 공식값 합"` 병기.
- **접근성**: 각 산출 버튼에 `aria-label="${YNAME[k]} ${v == null ? '자료 없음' : fmtWon(v)}${pn ? ', 부분 합계' : ''}${rk ? ', 전국 ' + rk + '위' : ''} — 세부 기준 보기"` 및 `aria-expanded` 동기화.

---

### [반드시 4] #9. 도시 패널 4탭 구조화 (개요 · 경제 · 시설·교역 · 땅·행정)

#### 3.4.1 빌드 단계 변경
- **대상 파일**: `pipeline/build_regions.py` (또는 `build_phase6.py`) → `site/data/cities.json` (`+250 B`).
- **추가 필드 (감사 05 통합)**:
  - 광역시·특별시 중 같은 시도 안에 별도 군이 존재하는 5개 도시에 `cities[i].scope_label`을 직렬화:
    - 부산(`1`): `"자치구 15곳 합 · 기장군 별도"`
    - 인천(`2`): `"자치구 9곳 합 · 강화군·옹진군 별도"`
    - 대구(`3`): `"자치구 7곳 합 · 달성군·군위군 별도"`
    - 울산(`12`): `"자치구 4곳 합 · 울주군 별도"`
    - 광주(`5`): `"옛 광주 자치구 5곳 합"`
  - `design2/`도 `c.scope_label`을 도시 헤더 부제에 그대로 표시한다.
- **규칙 문장**: 도움말(`help.js`, **감사 21 수정 포함**)에 `"깃발을 누르면 도시 패널(개요·경제·시설·교역·땅·행정 4탭), 시도 이름이나 빈 육지를 누르면 시도 패널"` 명시.

#### 3.4.2 화면 변경
- **수정 파일**: `site/js/ui/panel.js`, `site/js/main.js`, `site/js/ui/help.js`, `site/css/style.css`.
- **상단 고정 영역 (`.phead-sticky`)** — 도시 패널에만 적용(시도·전국·항목·교역로 패널은 기존 단일 스크롤 유지):
  1. `<header>`: 행정 배지(`.badges`) + 특성 태그 최대 2개(`.tags`, #11) + `<h2>도시명</h2>` + `<p class="sub">${scope_label ? scope_label + ' · ' : c.full + ' · '}<a data-state>...</a></p>` (+ 여유 시 #14 `비교` 버튼 1개)
  2. 핵심 인구 1줄(`.bignum`): `868,367명 -2.1% 5년(2020→2025)`
  3. 5열 1행 산출 스트립(`.yields`, #12)
  4. **4탭 바 (`<div class="ptabs" role="tablist">`)**:
     - `개요` (`overview`)
     - `경제` (`econ`)
     - `시설·교역` (`infra`, 층 로드 완료 시 보유 건수 `시설·교역 14`)
     - `땅·행정` (`land`)
- **4개 탭 내부 구성 및 1280×800 첫 화면 압축 설계**:
  - **`개요` (`overview`)**:
    - **`.pop-charts` 2열 병렬 (`grid-template-columns: 1fr 1fr; gap: 8px`)**: 좌측 5년 인구 변화 SVG(`viewBox="0 0 180 96"`), 우측 5세 피라미드 SVG(`viewBox="0 0 180 108"`). 기존 세로 적층(364px)에서 **132px**로 `232px` 절감 → **`1280×800`(패널 가용 높이 `722px`)에서 헤더+인구+5산출+4탭(`220px`) + 차트(`132px`) + 연령 `.kv`(`112px`) + 소멸위험 `.ext`(`52px`) = `516px`로 끝나 `순위` 제목과 상위 6개 순위 게이지가 스크롤 없이 첫 화면에 진입한다.**
    - 연령 `.kv` 6칸 (#10 전국 대비 포함)
    - 소멸위험지수 `.ext` 1줄 압축(설명 공식은 `ⓘ`로 이동, **감사 14 대비 수정**: `STAGE_COLOR` 5단계별 글자색 명시 — `매우 낮음 #3f8f6b / #fff (4.6:1)`, `보통 #86b86f / #11151d (8.2:1)`, `주의 #e0a94e / #11151d (8.7:1)`, `소멸위험 #d4553a / #fff (4.6:1)`, `소멸 고위험 #a3202f / #fff (7.3:1)`)
    - 순위 9행 미니 게이지 (#10)
    - 닮은 도시 5곳 (#13 연결 지점)
  - **`경제` (`econ`)**: 부가가치/종사자 전환 막대(#11 LQ 포함), 경제 `.kv.econ` 14칸(#10 대비 포함), 주력 업종(`keyIndBlock`).
  - **`시설·교역` (`infra`)**: 수출입·HS 상위 품목(`tradeBlock`), 지도 층 목록(`layerBlock`), 일반산단(`gicLine`), 발전설비(`powerBlock`), 식량(`farmBlock`), 가행 광산(`minesBlock`).
  - **`땅·행정` (`land`)**: 국가토지피복통계 + 칸 피복(`terrainBlock`), 건강·정리한 지표(`retiredBlock`), 보훈대상자(`veteransBlock`), 청사(`officeBlock`), 하단 `.foot`.
- **데스크톱 vs 390px 모바일 배치**:
  - 데스크톱(`> 700px`): `<header>` + `.bignum` + `.yields` + `.ptabs`를 상단 고정(`.phead-sticky`)으로 두고 본문(`.ptab`)만 스크롤하거나, 패널 전체 스크롤 시 `.ptabs`만 `position: sticky; top: 0;` 고정해 탭 전환 접근성 유지(권장: `.ptabs`만 `sticky`로 두면 `1280×800` 가독 높이가 더 넓고 스크롤바도 단일 유지).
  - 390px 모바일(`<= 700px`): `.ptabs` 4개 균등 1행(`grid-template-columns: repeat(4, 1fr); font-size: 11px;`), `.ptabs`만 `sticky` 고정, `.pop-charts`는 `340px` 이상에서 2열 유지(`340px` 미만 1열).
- **탭 기억**: `app.panelTab` (`'overview' | 'econ' | 'infra' | 'land'`, 기본 `'overview'`). 도시 A의 `경제` 탭을 보다가 지도에서 도시 B 깃발을 누르면 도시 B도 `경제` 탭으로 열린다.

#### 3.4.3 상호작용 · 해시 · 결측/개편 · 접근성
- **키보드**: `role="tablist"` 포커스 시 `←`/`→` 탭 이동(`e.stopPropagation()`으로 지도 팬 화살표와 충돌 차단!), `Home`/`End` 첫·끝 탭 이동, `Enter`/`Space` 선택.
- **Esc 순서**: 기존과 동일(말풍선 → 도움말 → 공유 → 찾기 → 연감 → 보고서 → 패널 닫기).
- **단축키 충돌 방지**: `main.js` 전역 `keydown`의 `ArrowLeft`/`ArrowRight` 가드에 `e.target.closest('[role="tablist"], [role="tab"]')` 예외 추가.
- **해시 키 (감사 11 통합)**:
  - `tab=econ|infra|land` (`overview`일 때는 생략, `city=`와 함께 있을 때만 유효, 미등록 값은 `overview` 폴백).
  - `design2/` 호환: `design2`는 미지원 키 `tab`을 무시하므로 링크 공유가 깨지지 않는다.
  - **감사 11 동시 수정 (`readHash()`)**: 해시 파싱을 "① 불변 상태 객체로 전체 해석(빈 `city=`는 무효 처리, 유효 대상 우선순위 `item > route > cmp > city > state > report`) → ② 기존 선택·비교·타이머·패널 일괄 초기화 → ③ 새 상태 1회 적용"으로 개편.
- **자료 없음 · 부분 합 · 개편 구역 (감사 08 통합)**:
  - `loadLayers()`를 `Promise.allSettled`로 분리(감사 08). 예를 들어 `trade.json`만 404여도 나머지 층은 정상 표시하고, `시설·교역` 탭의 수출입 구역만 `"교역 자료를 불러오지 못했습니다"` + `[다시 시도]` 버튼을 표시하며 `setLayers()` 재시도 성공 시 활성 탭을 유지한 채 재렌더한다.
  - `포천시`·`여주시`(`trade: null`), `군위군`(`veterans.count: null`), `옹진군`(`housing.sale_per_m2: null`)도 탭을 비활성화하지 않고 해당 구역에 `"자료 없음"` 사유 표시.
- **접근성**: `role="tablist" aria-label="도시 정보 분류"`, 각 탭 `role="tab" aria-selected aria-controls="ptab-{id}" tabindex="0|-1"`, 각 패널 `role="tabpanel" id="ptab-{id}" aria-labelledby="tab-{id}"`. 도시 선택 시 패널 `<header>` `<h2>`에 `tabindex="-1"`로 초점 이동 옵션(키보드/검색/보고서 진입 시 초점 이동, 지도 마우스 클릭 시에는 지도 탐색 방해 안 하게 `aria-live="polite"` 안내만 출력).

---

### [반드시 5] #10. 핵심 지표 전국 기준 대비(▲/▼) 및 순위 미니 게이지

#### 3.5.1 빌드 단계 변경
- **대상 파일**: `pipeline/build_phase6.py` (또는 `build_insights.py`) → `site/data/nation.json` (`+920 B`).
- **추가 필드 (`nation.json` `nation.benchmarks`)**:
  ```json
  "benchmarks": {
    "rule": "같은 조사·같은 산식의 지표는 전국값(nation)과 비교한다. 고용률(시군구 지역별고용조사 반기)과 재정자립도(기초 시·군 기준)는 전국 공식값과 조사·범위가 달라 값이 있는 도시의 중앙값(city_median)과 비교한다. 순위 막대의 분모는 값이 있는 도시 수다.",
    "metrics": {
      "growth_5y":       { "v": -1.4,      "ref": "nation",      "unit": "%",   "fmt": "pct1", "dir": "neutral", "mode": "diff" },
      "over65":          { "v": 22.1,      "ref": "nation",      "unit": "%",   "fmt": "pct1", "dir": "neutral", "mode": "diff" },
      "under15":         { "v": 10.0,      "ref": "nation",      "unit": "%",   "fmt": "pct1", "dir": "neutral", "mode": "diff" },
      "working":         { "v": 67.8,      "ref": "nation",      "unit": "%",   "fmt": "pct1", "dir": "neutral", "mode": "diff" },
      "mean_est":        { "v": 45.9,      "ref": "nation",      "unit": "세",  "fmt": "f1",   "dir": "neutral", "mode": "diff" },
      "median_est":      { "v": 46.8,      "ref": "nation",      "unit": "세",  "fmt": "f1",   "dir": "neutral", "mode": "diff" },
      "sex_ratio_20_39": { "v": 107.7,     "ref": "nation",      "unit": "",    "fmt": "f1",   "dir": "neutral", "mode": "diff" },
      "extinction_index":{ "v": 0.52,      "ref": "nation",      "unit": "",    "fmt": "f2",   "dir": "good",    "mode": "diff" },
      "gdp_per_capita":  { "v": 47000000,  "ref": "nation",      "unit": "원",  "fmt": "won",  "dir": "good",    "mode": "ratio", "year": 2023 },
      "wage":            { "v": 43320000,  "ref": "nation",      "unit": "원",  "fmt": "won",  "dir": "good",    "mode": "ratio" },
      "sale_per_m2":     { "v": 674.0,     "ref": "nation",      "unit": "만원","fmt": "man",  "dir": "neutral", "mode": "ratio" },
      "sale_median":     { "v": 48000,     "ref": "nation",      "unit": "만원","fmt": "won1e4","dir":"neutral", "mode": "ratio" },
      "jeonse_median":   { "v": 29500,     "ref": "nation",      "unit": "만원","fmt": "won1e4","dir":"neutral", "mode": "ratio" },
      "degree":          { "v": 46.9,      "ref": "nation",      "unit": "%",   "fmt": "pct1", "dir": "good",    "mode": "diff" },
      "employment":      { "v": 66.5,      "ref": "city_median", "n": 159, "unit": "%", "fmt": "pct1", "dir": "good", "mode": "diff" },
      "fiscal":          { "v": 13.3,      "ref": "city_median", "n": 158, "unit": "%", "fmt": "pct1", "dir": "good", "mode": "diff" }
    },
    "rank_denominators": {
      "population": 167, "growth": 167, "over65": 167, "extinction": 167,
      "gdp": 167, "gdp_per_capita": 167, "wage": 167, "housing": 166, "export": 165,
      "food": 167, "production": 167, "science": 167, "culture": 167
    }
  }
  ```
  *(실제 수치는 빌드 시 `nation.json`·`cities.json`에서 자동 산출하며, `validate.py`에서 `rank_denominators`와 `city_median`을 교차 검증한다.)*

#### 3.5.2 화면 변경
- **수정 파일**: `site/js/ui/panel.js`, `site/js/ui/format.js` (신규 경량 공용 포매터 — 감사 20 통합), `site/css/style.css`.
- **전국 기준 대비 1줄 (`.ref`)**:
  - `개요`·`경제` 탭의 `.kv > div` 카드 하단에 1줄 추가(`font-size: 10px`, `tabular-nums`):
    - `mode === 'diff'`: `diff = cityVal - refVal`. `|diff| < 0.05` (소멸지수는 `< 0.005`)이면 `= 전국 수준` / `= 도시 중앙`. 그 외 `▲ 전국 +3.2%p` 또는 `▼ 도시 중앙 -1.8%p`.
    - `mode === 'ratio'`: `pct = (cityVal / refVal - 1) * 100`. `|pct| < 0.5`이면 `= 전국 수준`. 그 외 `▲ 전국 +42%` (`title`에 기준값 `전국 4,700만원` 병기).
  - 색상 규칙(`dir`):
    - `good`: `diff > 0` `.up` (`#78cfa9`), `diff < 0` `.down` (`#f08b72`).
    - `neutral`: 가치 판단 색 없이 `.neu` (`#b8b09e`).
- **순위 미니 게이지 (`.rk-list`, 1열 9행)**:
  - 기존 4열 텍스트 박스 `.ranks`를 **1열 9행 콤팩트 버튼 리스트**로 교체(행 높이 `26px`, 총 높이 약 `240px`):
    - 좌: 지표명(`74px`, 예: `1인당 GRDP`)
    - 중: 가로 트랙(`height: 6px`, `border-radius: 3px`) + 위치 점(`8px` 원, `left: pctPos%`, `pctPos = ((N - rank) / (N - 1)) * 100`, 우측=1위). `extinction` 행은 1위=가장 위험이므로 점 색 `#d4553a` + 우측 끝 작은 `위험` 표기.
    - 우: `${rank}위/${N}` (`54px`, 우측 정렬).
  - 행을 클릭하면 그 행 바로 아래에 **인접 순위 점프 칩 1줄(`.rk-adj`)**이 펼쳐짐(기본 접힘):
    - `▲ {rank-1}위 {도시명} ({값})` · `▼ {rank+1}위 {도시명} ({값})` · `도내 1위 {도시명}` (이미 도내 1위거나 단일 도시 시도이면 생략).
- **데스크톱·390px 모바일 배치**: 1열 가로 리스트라 360px 데스크톱과 390px 모바일에서 동일한 구조로 깨짐 없이 동작.
- **감사 20 통합 (공통 포매터)**: `site/js/ui/format.js`에 `fmtUnit(v, fmt, unit)`을 두고, `%`가 이미 포함된 `pct1`·`pct2`에는 `unit`을 중복 부착하지 않으며 `int`에는 `명` 등 단위를 정확히 1회 부착(`report.js`·`tooltip.js`·`panel.js` 공용).

#### 3.5.3 상호작용 · 해시 · 결측/개편 · 접근성
- **마우스·키보드·터치**: 각 순위 행은 `<button type="button" class="rk-row" aria-expanded="false">`. `Enter`/`Space`/탭으로 인접 도시 칩 토글, 칩 클릭 시 `app.selectCity(id, true)`. 한 번에 1개 행만 펼쳐 세로 팽창 방지.
- **Esc · 단축키**: 충돌 없음.
- **해시 키**: 없음.
- **자료 없음 · 부분 합 · 개편 구역 (감사 01 연동)**:
  - 값이 `null`인 카드(예: `옹진군` 매매가, `포천시`·`여주시` 수출)는 대비 줄 생략, 순위 행은 `<div class="rk-row disabled">`로 트랙 대신 `"자료 없음 · 순위 제외"` 표시(클릭 비활성).
  - 광역시 `member_ranges`(서울·부산·대구·인천·광주·대전·울산의 고용률·재정자립도)는 범위 텍스트만 유지하고 대비 화살표 미생성(평균 추정 금지).
  - `세종(gdp_year: 2024)`의 1인당 GRDP 대비 줄은 `▲ 전국('23) +XX%`로 연도 차이를 명시.
  - `housing.trades < 10`(신안 7·영양 8·울릉 3건)이면 대비 줄 뒤에 `(거래 N건)` 자동 병기.
  - **감사 01 연동**: `땅·행정` 탭의 `retiredBlock` 등 시군구별 값 카드와 렌즈 툴팁에서 개편 전 공표 구역(`pub_unit` 메타가 있는 화성시 4개 구·인천 서해구/검단구)은 `"화성시 전체, 2025"` / `"개편 전 인천 서구"` 라벨을 그대로 표시하고 전국 대비 화살표를 붙이지 않는다.
- **접근성**: 각 순위 행 `aria-label="${지표명} ${N}개 도시 중 ${rank}위, 상위 ${Math.round(rank/N*100)}% — 인접 순위 보기"`.

---

### [반드시 6] #11. 산업 입지계수(LQ) 및 엄격한 특성 태그 (상한 2개)

#### 3.6.1 빌드 단계 변경
- **대상 파일**: `pipeline/build_phase6.py` (또는 `build_insights.py`) → `site/data/cities.json` (`+72,050 B`), `site/data/nation.json` (`+430 B`).
- **계산식 (전국 분모 = 반드시 공식 전국값)**:
  - `nation.nation.gdp_by_industry`는 `mining`·`utilities`가 `null`이고 `nation.nation.jobs`는 `A`·`B`가 `null`이므로, 분모는 반드시 `nation.nation.official.gdp.by`와 `nation.nation.official.jobs.by`를 쓴다.
  - 부가가치 LQ: $\text{LQ}_{c,k} = \frac{\text{gdp\_by\_industry}[k] / \text{gdp\_by\_industry.grdp}}{\text{official.gdp.by}[k] / \text{official.gdp.by.grdp}}$ (`k ∈ industry_keys` 16개, `net_taxes` 제외)
  - 종사자 LQ: $\text{LQ}^{\text{job}}_{c,L} = \frac{\text{jobs}[L] / \text{jobs\_total}}{\text{official.jobs.by}[L] / \text{official.jobs.total}}$ (`L ∈ ksic_ko` 19개)
  - **반올림 전 임계 판정**: 반올림 오차 방지(예: `익산시` 보건업 `1.49xx`가 `1.5`로 반올림되어 태그가 오발동하는 현상 차단)를 위해 모든 임계 조건(`share >= 0.05 && lq >= 1.5`)은 **반올림 전 실수값**으로 판정한 뒤 JSON에는 소수 1자리로 저장한다.
- **JSON 저장 스키마**:
  - `cities[i].lq_gdp`: 도시 내 비중 `>= 1.0%`이고 비공개가 아닌 업종만 `{ "manufacturing": 2.6, ... }` 저장(`+42.2 KB`).
  - `cities[i].lq_jobs`: 도시 내 비중 `>= 1.0%`이고 비공개가 아닌 대분류만 `{ "C": 2.4, ... }` 저장(`+20.4 KB`).
  - `cities[i].tags`: **최대 2개** 배열(`+9.5 KB`).
    - **슬롯 1 — 특화 산업 (0~1개)**: 16개 부가가치 산업 중 `비공개 제외 ∧ share >= 0.05 ∧ lq >= 1.5`인 업종 중 `lq` 최댓값 1개 → `{ "t": "ind", "k": "manufacturing", "lq": 2.6, "sh": 66.6, "nat": 25.4, "small": false, "yr_diff": false }` (`small = population < 50000 && lq >= 10`, `yr_diff = gdp_year != official_gdp_year`).
    - **슬롯 2 — 객관 극단 지표 (0~1개, 아래 우선순위 순 첫 일치 1개만)**:
      1. `ranks.gdp_per_capita <= 10` → `{ "t": "rk", "k": "gdp_per_capita", "r": 8 }`
      2. else `ranks.export != null && ranks.export <= 10` → `{ "t": "rk", "k": "export", "r": 3 }`
      3. else `ranks.wage <= 10` → `{ "t": "rk", "k": "wage", "r": 4 }`
      4. else `extinction_index != null && extinction_index < 0.2` → `{ "t": "pop", "k": "extinction", "v": 0.16 }`
      5. else `growth_5y != null && growth_5y >= 10.0` → `{ "t": "pop", "k": "growth_5y", "v": 15.8 }`
  - `nation.json` `nation.lq_rule`:
    > "입지계수(LQ)는 도시의 업종별 비중을 전국 공식 비중(부가가치는 지역소득 공식 전국값, 종사자는 전국사업체조사 공식 전국값)으로 나눈 배수다. 1.0이면 전국 평균과 같으며, 도시 내 비중 5% 이상·배수 1.5 이상(반올림 전 기준)을 강조한다. 도시 헤더의 특성 표시는 최대 2개(특화 산업 1개 + 객관 지표 조건 1개)로 제한하고, 평가형 수식어 없이 지표명과 수치만 적는다. 비공개 업종은 계산과 태그 선정에서 제외한다."

#### 3.6.2 화면 변경
- **수정 파일**: `site/js/ui/panel.js`, `site/js/ui/almanac.js`, `site/css/style.css`.
- **과잉 해석 방지 문구 규칙 (필수 준수)**:
  - 금지 표현: `"부자 도시"`, `"성장 거점"`, `"쇠퇴 지역"`, `"경제 중심"`, `"강세"`, `"특화 도시"` 같은 주관적·가치판단형 문구 일절 금지.
  - 허용 문구(정확히 지표명 + 수치):
    - 슬롯 1: `{산업명} 비중 ×{LQ}` (예: `제조업 비중 ×2.6`, `정보통신업 비중 ×2.4`, `LQ >= 10`이면 정수 `전기·가스·증기 비중 ×33`)
    - 슬롯 2: `1인당 GRDP {r}위` / `수출 {r}위` / `총급여 {r}위` / `소멸지수 {v} (<0.2)` / `5년 인구 +{v}%`
- **배치**:
  - 도시 패널 `<header>`의 행정 배지(`.badges`) 바로 아래 `.tags` 1줄(`flex-wrap: wrap; gap: 4px;`, 최대 2개라 360px 데스크톱·390px 모바일 모두 1줄 유지).
  - `경제` 탭의 `industryBars`·`jobBars` 각 행 우측 `.val` 끝에 `<span class="lq [hi]">×2.6</span>` (`share >= 5% && lq >= 1.5`일 때 `.hi` 금색 강조).
- **말풍선(`#fnpop`) 산식 투명화**:
  - 태그 클릭/호버/포커스 시 산식과 분자·분모 실측값을 즉시 표시:
    - 일반 예: `"화성시 제조업 비중 66.6% ÷ 전국 공식 25.4% = ×2.6 (입지계수 LQ)"`
    - `small === true` (`울진군`, `영월군` 등 29개 군): 뒤에 `" — 인구 5만 미만 지역은 단일 발전소·광산·농업 비중이 커 배수가 높게 나올 수 있다."` 자동 추가.
    - `yr_diff === true` (`세종`): 뒤에 `" — 세종은 2024년, 전국 공식 분모는 2023년 GRDP 기준."` 자동 추가.

#### 3.6.3 상호작용 · 해시 · 결측/개편 · 접근성
- **마우스·키보드·터치**: 각 태그는 `<button type="button" class="ctag">`, 클릭·호버·포커스 시 `#fnpop` 표시, `Esc`로 닫힘.
- **해시 키**: 없음.
- **자료 없음 · 부분 합 · 비공개**:
  - 비공개 업종(`gdp_undisclosed` 25곳, `jobs` 비공개 47곳): LQ 칸 생략(`비공개`만 유지), 태그 후보 제외.
  - 조건 미충족 도시(`익산시(40)`): 슬롯 1 강제 생성 금지 → 0개(슬롯 2도 미충족이면 `.tags` 자체 미렌더).
- **접근성**: `<div class="tags" role="group" aria-label="데이터 기반 도시 특성">`, 각 버튼 `aria-label="{라벨} — 산식 보기"`.

---

### [반드시 7] #32. PNG 크로스브라우저 안정화 및 1:1 정사각 카드 (감사 03·12 통합)

#### 3.7.1 빌드 단계 변경
- **JSON 변경 없음** (`0 B`, 감사 02의 토지피복 이용조건 해결 시 `world.json` 또는 `sources.json`에 기록되는 단일 진실원 문자열을 `share.js`가 런타임에 읽어 출처 줄에 반영하도록 하드코딩 제거).
- **고정 출처 주소 (`site/js/config.js`)**: `SITE_URL`이 비어 있으면 런타임 `location.origin + location.pathname`에서 호스트+경로(최대 48자, `localhost`/`127.0.0.1`일 때는 `연감(📖)에 전체 출처·이용허락 수록`)를 출처 안내 문구로 생성. 배포 시 `config.js`의 `SITE_URL`을 채우면 고정 주소가 그대로 인쇄된다.

#### 3.7.2 화면 변경
- **수정 파일**: `site/js/ui/share.js`, `site/js/ui/help.js`, `site/index.html`, `site/css/style.css`.
- **공유 메뉴 (`#sharemenu`) 3항목**:
  1. `🔗 지금 화면 링크 복사`
  2. `🖼️ 그림 내려받기 — 정사각 1:1` (`1200×1200`, 한반도 전국 화면 권장)
  3. `🖼️ 그림 내려받기 — 와이드 16:9` (`1600×900`, 확대·가로 구간용)
- **감사 12 통합 — 동적 범례 레이아웃 (8개 절단 완전 폐지)**:
  - 기존 `steps.slice(0, 8)` 제거! `lens.scale === 'bins' || lens.scale === 'category'`일 때 실제 관측 범주 수 `n = steps.length` (예: `최대 산업` 14개)에 따라:
    - 1:1 (`W = 1200`): 열 수 `cols = n <= 8 ? 4 : 5`, 행 수 `rows = Math.ceil(n / cols)`, 범례 높이 `legH = rows * 22 + 24`.
    - 16:9 (`W = 1600`): 범례 폭 `lw = 620`, 열 수 `cols = n <= 8 ? 4 : 5`, 행 수 `rows = Math.ceil(n / cols)`, `legH = rows * 22 + 24`.
    - 하단 띠 높이 `BAND = Math.max(baseBand, topRowH + legH + attrH + 16)`로 동적 확장(최대 `260px` 이내), `MAPH = H - BAND`. 모든 관측 범주가 단 하나도 누락되지 않는다.
- **감사 03 통합 — 레이어 연동 저작자·라이선스·출처 줄 (46자 절단 폐지)**:
  - 하단 띠 맨 아래 전용 출처 행(`attrH = 38px`, 2줄 줄바꿈, `font: 11.5px`)에 **실제 그려진 레이어 기준**으로 필수 표기를 빠짐없이 조합한다:
    - **기본 지도 필수 표기(항상)**: `경계: 행정안전부 행정동(2026-10-01) · 수면: © OpenStreetMap 기여자(ODbL) · 지형: SRTM30+ · Natural Earth`
    - **지형 모드(`!lens`) 추가**: `피복: 기후에너지환경부 토지피복지도 2025(공개제한 구역 ESA WorldCover) · 갯벌: 해양수산부 · 하천: WAMIS` (감사 02 이용조건 문자열 연동)
    - **렌즈 모드(`lens`) 추가**: `통계: ${lens.source} (기준 ${lens.vintage ?? a.lenses.vintage})` (절단 없이 2줄 줄바꿈)
    - **활성 층 추가(해당 묶음 켜짐 시)**: 도로(`국가교통정보센터`)·교역로(`국가물류통합정보센터`)·세계유산/국립공원 등 켜진 묶음 출처 요약 + 우측 끝 `전체 출처·이용허락: ${SITE_URL || 'koreaciv 연감'}`.
- **1:1 정사각 카드 (`1200×1200`) 2단 하단 띠**:
  - 1행: 좌=제목(`최대 폭 760px` `measureText` 말줄임) + 부제 / 우=기준 시점 + `SITE_NAME`
  - 2행: 범례 전체 폭 (`1144px`)
  - 3행: 출처·저작자·라이선스 2줄 (`1144px`, 감사 03)
- **크로스브라우저 안정화 + 모바일 폴백 (`downloadPNG(preset)`)**:
  1. `await document.fonts?.ready`.
  2. `cv = this.render(preset)` (실패 시 토스트 `"그림을 만들지 못했습니다. 화면을 축소하거나 다시 시도해 주세요."`).
  3. `blob = await canvasToPngBlob(cv)`: `cv.toBlob`이 `null`이거나 3초 내 미응답/예외 시 `cv.toDataURL('image/png')` 디코드 폴백.
  4. 터치 기기 + `navigator.canShare?.({ files: [file] })`: `await navigator.share({ files: [file], title })` (`AbortError`는 정상 취소 처리).
  5. 그 외 데스크톱·Firefox·Safari: `<a download>` 클릭 + `setTimeout(() => URL.revokeObjectURL(url), 15000)`. iOS Safari·인앱 브라우저 감지 시 경량 미리보기 모달 `#pngpreview`를 함께 열어 `<img>` + `"이미지를 길게 눌러 저장하거나 아래 버튼으로 내려받으세요"` + `[내려받기]` `[닫기]` 제공.
  6. `#pngpreview` 닫힘 시 즉시 `URL.revokeObjectURL` + `cv.width = cv.height = 0` 메모리 해제.
- **데스크톱·390px 모바일 배치**: `#sharemenu`는 우측 상단 버튼 아래 드롭다운(390px에서 `right: 6px; max-width: calc(100vw - 12px)`). `#pngpreview`는 화면 중앙 시트(`max-width: min(520px, calc(100vw - 24px))`).

#### 3.7.3 상호작용 · 해시 · 결측/개편 · 접근성
- **마우스·키보드·터치**: `#sharemenu` 열릴 때 첫 버튼 포커스, `↑`/`↓` 이동, `Esc`로 닫고 `#share-btn`으로 초점 복귀. `#pngpreview`도 `Esc` 최상위 모달로 닫힘(`help`와 동급 우선순위).
- **해시 키**: 없음.
- **자료 없음 · 부분 합**: 범례의 `"자료 없음"` 빗금 칩과 `higher_is` 방향 문구 유지. 비교 모드(#14 활성 시) 제목 `${A.name} vs ${B.name} · ${lens ? lens.name : '지형'}` 및 두 도시 테두리+아크 포함.
- **접근성**: `#sharemenu` `role="menu"`, 항목 `role="menuitem"`. `#pngpreview` `role="dialog" aria-modal="true" aria-label="공유 그림 미리보기"`. 생성된 PNG 자체의 하단 띠 텍스트 대비 ≥ 7:1(`#e6dfcf` on `#141822`).

---

## 4. "하면 좋음" 3개 구현 명세

---

### [하면 좋음 1] #13. '닮은 도시' 유사 근거 1줄 요약

#### 4.1.1 빌드 단계 변경
- **대상 파일**: `pipeline/build_econ.py` (578행 `c["peers"]` 산출 직후) → `site/data/cities.json` (`+39,940 B`).
- **산식 (`build_econ.py` 실제 `peers` 거리와 100% 일치)**:
  - `build_econ.py`가 이미 계산한 `feats[i]` (`lp`, `o65`, `lg`, `s_k = v / gva`), `sd[k]`를 그대로 사용해 두 도시 `(i, j)`의 4축 정규화 제곱거리 산출:
    - `d_pop = ((fi.lp - fj.lp) / sd.lp)^2`
    - `d_age = ((fi.o65 - fj.o65) / sd.o65)^2`
    - `d_gdp = ((fi.lg - fj.lg) / sd.lg)^2` (둘 다 `lg` 있을 때)
    - `d_ind = mean(((fi['s_'+k] - fj['s_'+k]) / sd['s_'+k])^2 for k in common_s)`
  - 4축 중 거리가 가장 작은 2축 → `same: [axis1, axis2]`. `'ind'`가 포함되면 공통 공개 업종 중 `min(fi['s_'+k], fj['s_'+k])` 최댓값 업종 `ind`, `ind_a`, `ind_b`(GVA 대비 %) 기록.
  - **결정적 차이 1개 (`diff`, 임계값 초과 시만 기록 — 억지 차이 금지)**:
    1. 둘 다 `housing.sale_per_m2 != null && housing.trades >= 10`이고 `max(a/b, b/a) >= 1.35` → `["home", round(ratio, 1)]`
    2. else 둘 다 `growth_5y != null`이고 `|a - b| >= 5.0` → `["growth", round(a - b, 1)]`
    3. else 둘 다 `wage.per_filer != null`이고 `max(a/b, b/a) >= 1.15` → `["wage", round(ratio, 1)]`
- **JSON 저장 스키마 (`cities[i].peer_reasons`)**:
  ```json
  [
    { "id": 31, "same": ["gdp", "ind"], "ind": "manufacturing", "ind_a": 70.6, "ind_b": 74.3, "diff": ["home", 2.8] }
  ]
  ```
- **규칙 문장 (연감 `산출` 탭)**:
  > "닮은 도시는 인구(로그)·고령 비율·1인당 GRDP(로그)·산업 16분류(GVA 대비 비중)의 표준화 거리로 5곳을 고른다. 카드 아래 요약은 이 네 축 중 거리가 가장 작은 두 항목과, 아파트 매매가(1.35배↑, 거래 10건 이상)·5년 인구 증감(5%p↑)·1인당 총급여(1.15배↑) 중 차이가 뚜렷한 한 항목을 표시한다."

#### 4.1.2 화면 변경
- **수정 파일**: `site/js/ui/panel.js`, `site/css/style.css`.
- **배치 (`개요` 탭 `.peers` 5행)**:
  - 각 행을 `.peer-row` flex 컨테이너로 구성:
    - 좌측 `<button type="button" class="peer-go" data-city="{id}">`: 1줄 `<b>아산시</b> <small>35.9만 · 고령 15%</small>`, 2줄 `<span class="peer-why">1인당 GRDP·제조업 비중(70.6%·74.3%) 비슷 · 매매가 2.8배 차</span>`.
    - 우측(#14 구현 시에만 노출): `<button type="button" class="peer-cmp" data-cmp="{id}">비교</button>` (최소 터치 영역 `44×44px`).
- **390px 모바일**: 2줄 요약에 `white-space: normal; line-height: 1.3;` 적용, 좌·우 버튼 간 `gap: 4px` 분리로 오탭 방지.

#### 4.1.3 상호작용 · 해시 · 결측/개편 · 접근성
- **중첩 버튼 금지**: `.peer-go`와 `.peer-cmp`는 반드시 형제 `<button>`으로 분리.
- **자료 없음 · 부분 합 · 개편 구역**:
  - 비공개 산업은 `common_s`에서 제외.
  - `울릉군(trades: 3)`·`옹진군(sale_per_m2: null)`·`신안군(7)`·`영양군(8)`은 매매가 배수 차이 자동 제외.
  - `세종(2024)`과 타 도시(2023) 쌍은 `1인당 GRDP` 라벨에 `('24/'23)` 자동 부기.
- **해시 키**: 없음(`비교` 버튼 클릭 시 #14의 `#cmp=a,b` 진입).
- **접근성**: `.peer-cmp`에 `aria-label="${c.name}과 ${p.name} 비교하기"`.

---

### [하면 좋음 2] #14. 도시 대 도시(A vs B) 최소 비교 모드

> **#9 4탭과 공존하기 위한 최소 형태 원칙**: 비교 모드 안에 4탭을 또 넣지 않는다. 단일 도시는 `#9` 4탭, 비교 모드는 **탭 없는 단일 1면 핵심 16지표 대조표**로 완전히 분리해 상태 복잡도를 1단계로 제한한다.

#### 4.2.1 빌드 단계 변경
- **JSON 변경 없음** (`0 B`). 기존 `cities.json` + #10 `nation.json.benchmarks` + `cities[i].scope_label` + `cities[i].tags` 재사용.
- **규칙 문장 (연감 `인구·도시` 탭)**:
  > "도시 비교는 두 도시의 인구 피라미드를 각 도시 총인구 대비 5세 계급 비중(%)으로 정규화해 겹쳐 그린다. GRDP 기준 연도가 다르거나(세종 2024, 그 외 2023) 한쪽이 자치구 범위·자료 없음인 지표는 차이를 계산하지 않고 각 값과 기준을 나란히 적는다. 승패나 종합 점수는 매기지 않는다."

#### 4.2.2 화면 변경
- **수정 파일**: `site/js/ui/panel.js`, `site/js/main.js`, `site/js/ui/search.js`, `site/js/ui/share.js`, `site/css/style.css`.
- **진입·이탈 상태 기계 (`app.cmpMode`, `app.cmpCity`)**:
  1. `idle` (일반 단일 도시 패널 — #9 4탭). 헤더 우측에 작은 `[비교]` 버튼 1개.
  2. `picking` (비교 대상 고르기 대기): `[비교]` 클릭 시 지도 상단에 작은 안내 바(`#cmp-banner`: `"비교할 도시를 지도에서 누르거나 / 검색으로 고르세요 [취소 Esc]"`) 표시. A 패널은 유지.
  3. `active` (`app.selCity = A`, `app.cmpCity = B`): `#panel.compare`가 **단일 1면 핵심 대조표**로 전환.
  4. 종료(`[단일 보기]` 또는 `Esc`): `app.cmpCity = null`, A의 단일 패널(#9 **마지막으로 보던 `app.panelTab`** 복원) 또는 패널 닫기.
- **최소 1면 대조표 구성 (총 4블록, 탭 없음)**:
  1. **고정 상단 헤더**: 좌 `A(금색 #ffd34d)` `<h2>` + `scope_label` + `[A 자세히]` | 중 `[⇄ 바꾸기]` | 우 `B(하늘색 #63c7ff)` `<h2>` + `scope_label` + `[B 변경]` + `[닫기]`
  2. **인구·피라미드**: 인구·5년 증감·고령 비율·소멸위험지수(4행 대조) + **비중(%) 정규화 겹침 피라미드 SVG** (A=반투명 채움, B=굵은 윤곽선, 툴팁에 `%`와 실제 `명` 동시 표기)
  3. **다섯 산출 (5행)** + **핵심 경제·교역 (7행: 1인당 GRDP·1인당 총급여·매매 ㎡당·전세 중위·고용률·재정자립도·수출)**:
     - 각 행 구조: `[A 값 + 우측 정렬 막대] | [지표명 + Δ] | [좌측 정렬 막대 + B 값]`.
     - 양수 두 값 모두 존재 시 `max(vA, vB)`를 100%로 정규화(최소 폭 `2px`). 부호가 다를 수 있는 `5년 증감`·`무역수지`는 막대 없이 수치·차이만 표기.
     - 우세 색 강조는 `nation.benchmarks.metrics[k].dir === 'good'`인 지표만 미세 강조, `neutral`은 중립. 승패·점수 UI 금지.
  4. **특성 태그 & 보유 층 건수 1줄 요약**: 각 도시의 태그(#11) + 세계유산·국립공원·발전소·공항·무역항 건수 나열.
- **지도 오버레이 (`main.js` `drawOverlay`)**:
  - A 영토 외곽선 `#ffd34d`(금색), B 영토 외곽선 `#63c7ff`(하늘색), `(A.x, A.y)`↔`(B.x, B.y)` 금색 점선 이차 베지어 아크(제어점 = 중점 수직 15%).
  - 진입 시 두 도시 영토 합집합 바운딩 박스로 `flyTo` (감사 19: `prefers-reduced-motion` 시 즉시 이동).
- **데스크톱 vs 390px 모바일 배치**:
  - 데스크톱(`> 700px`): `#panel.compare { width: 460px; }`, `body.compare-open #minimap { right: 480px; }`, `body.compare-open #lensbar { left: calc((100vw - 480px) / 2); max-width: calc(100vw - 500px); }`.
  - 390px 모바일(`<= 700px`): 바텀시트 `width: 100%; max-height: 70vh;`, 행 구조를 2줄(윗줄 중앙 지표명+Δ, 아랫줄 좌 A 막대·값 / 우 B 값·막대)로 접어 390px 가로 넘침 0건.

#### 4.2.3 상호작용 · 해시 · 결측/개편 · 접근성
- **마우스·키보드·터치**:
  - `picking` 중 지도 깃발 클릭 → B 확정, `/` 검색에서 도시 선택 → `selectCity` 대신 `setCompare(selCity, chosenId)`.
  - **Esc 순서**: `#fnpop` → `#help` → `#sharemenu` → `#search` → `#almanac` → `#report` → **`picking` 취소(A 패널 유지)** → **`active` 비교 패널 닫기(단일 A 복귀 또는 닫기)**.
- **해시 키 (`#cmp=a,b`)**:
  - `city`/`state`/`item`/`route`와 상호 배타적.
  - 파싱 검증(감사 11 연동): `a`, `b` 모두 유효한 `cityById` 정수이고 `a !== b`일 때만 비교 진입. `a === b`이거나 한쪽만 유효하면 유효한 단일 도시로 폴백 + 토스트 안내. 둘 다 무효면 선택 없음.
  - `design2/` 호환: `cities[i].id`가 동일하므로 `design2`도 향후 `cmp=`를 그대로 해석 가능하며, 미구현 상태에서는 무해하게 무시.
- **자료 없음 · 부분 합 · 개편 구역**:
  - 한쪽 `null` (예: `옹진군` 매매가, `포천시`·`여주시` 수출) → 해당 칸 `"자료 없음"`, 막대 폭 `0` (DOM에 막대 미생성), Δ 칸 `"–"`.
  - `A.gdp_year !== B.gdp_year` (`세종 2024` vs 타 도시 `2023`) → 경제 블록 상단 주황 경고 배지 `"GRDP 기준 연도 다름 (세종 2024 · 상대 2023) — 차이 미계산"` 표시, GRDP·5산출 Δ 칸 `"연도 다름"`.
  - 광역시 `member_ranges` vs 시군 단일값 (예: `서울` vs `수원시` 고용률·재정자립도) → 광역시 칸에 `자치구 min–max%`만 표시, 막대 미생성, Δ 칸 `"비교 불가(범위)"`.
  - 생산 부분 합(`yields_partial.production`) → 해당 값 `*` + 점선 + 감사 16 정정 주석.
- **접근성**: 비교 진입·바꾸기 시 `#sr-live` (`aria-live="polite"`)에 `"${A.name}과 ${B.name} 비교 열림"` 낭독. 각 대조 행은 시맨틱 `<table class="cmp-tbl"><caption>...</caption>` 또는 `role="table"` 사용.

---

### [하면 좋음 3] #20. 데이터 규칙 기반 추천 시점 6선

> **검토 의견 반영(수동 목록 금지)**: 어떤 도시 ID나 좌표도 손으로 적지 않는다. 빌드 스크립트가 매 빌드마다 실제 JSON 극값 규칙으로 6개 장면을 자동 추출해 `nation.json`에 기록하고, UI에 규칙과 실측 수치를 그대로 표시한다. 향후 편집자가 수동 장면을 추가해야 한다면 스키마에 `"kind": "editorial"`과 `"편집 선정"` 배지를 강제하는 규칙을 함께 둔다.

#### 4.3.1 빌드 단계 변경
- **대상 파일**: `pipeline/build_phase6.py` (또는 `build_insights.py`) → `site/data/nation.json` (`+1,690 B`).
- **6개 자동 추출 규칙 및 현행 데이터 실측 결과**:

| ID | 데이터 추출 규칙 (`rule`) | 현행 자동 추출 대상 | 실측 수치 (`metric`) | 적용 렌즈·층 |
|---|---|---|---|---|
| `top_pop` | 도시 167곳 중 주민등록 인구 최대 | 서울 (`id: 0`) | `928만명` | `density` · `wonders,resources,infra` |
| `top_gdppc` | 인구 10만 이상 도시 중 1인당 GRDP 최대 | 여수시 (`id: 42`) | `1.13억원` | `gdp_pc` · `resources,infra,trade` |
| `top_mfg` | GRDP 대비 제조업 비중 최대 | 아산시 (`id: 31`) | `70.4%` | `manufacturing_share` · `resources,infra,trade` |
| `min_ext` | 소멸위험지수 최솟값 (가장 위험) | 군위군 (`id: 161`) | `지수 0.07` | `extinction` · `wonders` |
| `top_paddy` | 농업면적조사 논 면적 최대 | 해남군 (`id: 96`) | `22,275ha` | `paddy_share` · `resources` |
| `top_route` | 시도 간 도로 화물 O/D 양방향 합 최대 | 경기–충남 (`41-44`) | `6,367만 톤` | 지형(`null`) · `trade,infra` |

- **JSON 저장 스키마 (`nation.json` `presets`)**:
  ```json
  "presets": {
    "rule": "여섯 시점은 편집자가 임의로 고르지 않고, 빌드 시점의 실제 JSON 수치 극값 규칙으로 자동 선정한다.",
    "items": [
      {
        "id": "top_pop", "kind": "auto",
        "title": "인구 1위 · 서울",
        "rule": "도시 167곳 중 주민등록 인구 최대",
        "metric": "928만명",
        "lens": "density", "ly": ["wonders", "resources", "infra"], "hide": [],
        "city": 0, "route": null, "x": 2282, "y": 1652, "z": 2.6
      }
    ]
  }
  ```
- `design2/` 공유: `nation.json` `presets`를 그대로 읽어 동일한 6개 자동 시점을 제공할 수 있다.

#### 4.3.2 화면 변경
- **수정 파일**: `site/js/ui/search.js`, `site/js/ui/help.js`, `site/js/main.js`, `site/css/style.css`.
- **노출 위치 (첫 화면 무침해 — 모달/상단 배너 없음)**:
  1. `#search` 빈 입력 상태: 기존 인구 상위 도시 8곳 아래에 구분선 + 소제목 `데이터 기준 시점 6선 (자동 선정)` + 6개 항목 리스트.
  2. `#help` 하단: 같은 6개 버튼 2열(모바일 1열) 그리드 + `"모든 시점은 빌드 시점의 데이터 극값 규칙으로 자동 선정됩니다"` 문구.
- 각 카드 표시: `<b>인구 1위 · 서울</b> <span>928만명 · 인구밀도 렌즈</span> <small>규칙: 도시 167곳 중 주민등록 인구 최대</small>`.
- **카메라 이동**: `scale = clamp(cam.minScale * p.z, cam.minScale, cam.maxScale)`. 데스크톱(`vw > 700`)에서 `p.city != null`이면 우측 패널(360px)에 가리지 않도록 `tx = p.x + 180 / scale` 보정. 감사 19(`prefers-reduced-motion`) 준수.

#### 4.3.3 상호작용 · 해시 · 결측/개편 · 접근성
- **키보드**: `#search` 빈 상태에서 `↑`/`↓`로 도시 8곳 → 추천 시점 6선 연속 이동, `Enter`로 적용(모든 문자열 `esc()` 처리, 감사 07).
- **해시 키**: **신규 해시 키 없음**. 프리셋 실행 결과는 기존 `v`, `lens`, `ly`, `hide`, `city`, `route`로 직렬화되어 `design2/`와 100% 호환.
- **자료 없음 · 부분 합 · 개편 구역**: 층 비동기 로딩 완료 전 `top_route` 선택 시 `pendingRoute`로 예약해 `setLayers()` 완료 즉시 구간 패널 열기.
- **접근성**: 각 항목 `<button type="button">` 또는 `role="option"`, `aria-label="${title}, ${metric}, 선정 규칙 ${rule}"`.

---

## 5. 안별 합격 기준 (Pass Criteria)

모든 검사는 `site/` 로컬 서버(`python -I -B -m http.server 18972 --bind 127.0.0.1 --directory site`)에서 콘솔 오류 `0건`, 네트워크 404 `0건` 상태로 수행한다.

| 안 | 검사 가능한 합격 기준 (Pass Criteria) |
|---|---|
| **#2** (반드시) | ① `1280×800` 및 `390×844` 전국 화면에서 `StateLabels`가 `LayerRenderer` 아이콘·`Banners` 깃발 아래에 그려진다(`drawScene` 호출 순서 및 스크린샷 육안 확인). ② `banners.avoid` 메서드가 존재하지 않으며, 전국 배율에서 충주시·안동시 등 비청사 중소 도시 깃발이 시도 이름 때문에 탈락하지 않는다. ③ `전남광주` 4글자 자간이 `0.12em`으로 제한돼 도 경계 밖으로 튀지 않고, `390×844`에서 시도 글자 크기가 `24px` 이하다. ④ `over65`·`extinction` 렌즈 활성 시에도 시도 이름 판독이 유지된다. |
| **#1** (반드시) | ① `1280×800` 및 `390×844` 전국 배율(`z = 1.0`)에서 `app.layerR.placed` 집계: `nuclear` **`5/5`**, `tier 0` `airport` **`6/6`**, `tier 0` `trade_port` **`8/8`** 전부 표시된다. ② 전국 배율 총 아이콘 수가 데스크톱 `<= 52`, 모바일 `<= 24`이고 총 도시 깃발 수가 데스크톱 `<= 24`, 모바일 `<= 12`다. ③ 오프셋된 아이콘(`p.ox != null`)마다 지시선 끝 점이 원래 칸 중심에 있고, 호버 툴팁에 `"깃발과 겹쳐 옆 칸에 표시"` 문구와 한국어 정밀도(`point`/`county` 영문 미노출)가 뜬다. ④ `z = 2.6`에서 강·호수 이름표가 깃발·아이콘 상자와 겹치는 건수가 `0건`이다. |
| **#12** (반드시) | ① 울산(`id=12`), 서울(`id=0`), 울릉군(`id=166`) 패널에서 `360px` 데스크톱과 `390px` 모바일 모두 `.yields .yt` 5개 버튼의 `offsetTop`이 동일하다(정확히 1행 5열, 가로 넘침 `0px`). ② 열린 도시 패널의 각 탭(`.ptab`)마다 `details.caveats`가 최대 `1개`만 DOM에 존재한다. ③ 서울(`id=0`) 생산 타일에 `.partial` 점선 테두리·`*`가 있고, 클릭·`Enter` 시 `#fnpop`에 `"제조업 + 건설업 + 공개된 광업의 합 (광업 비공개 14곳 제외"` 문구가 뜬다(감사 16 통과). ④ `Esc` 1회로 `#fnpop`만 닫히고 패널은 유지된다. |
| **#9** (반드시) | ① **울산(`id=12`) 패널에서 다섯 산출이 한 줄에 보이고, `1280×800`에서 스크롤 없이(`scrollTop === 0`) `순위` 제목과 상위 순위 행이 `#panel` 뷰포트 안에 보인다.** ② 부산(`id=1`)·울산(`id=12`)·대구(`id=3`)·인천(`id=2`) 패널 부제에 각각 `"자치구 15곳 합 · 기장군 별도"`, `"자치구 4곳 합 · 울주군 별도"` 등 `scope_label`이 표시된다(감사 05 통과). ③ 서울(`id=0`) 소멸위험 `주의` 배지 글자·배경 대비가 `4.5:1` 이상이다(감사 14 통과). ④ 울산 `경제` 탭 선택 후 서울 깃발 클릭 시 `경제` 탭이 유지되고, `#city=12&tab=econ` 새로고침 시 `경제` 탭이 복원되며, `#city=` 빈 해시 진입 시 서울이 열리지 않는다(감사 11 통과). ⑤ `trade.json`을 404로 차단해도 `시설·교역` 탭의 공항·원전 목록은 정상 표시되고 수출입 구역만 오류+재시도를 보인다(감사 08 통과). ⑥ 탭 바에서 `←`/`→` 키로 탭이 이동하며 지도가 패닝되지 않는다. |
| **#10** (반드시) | ① `nation.json.nation.benchmarks`가 존재하며, 화성시(`id=9`)·울산(`id=12`)의 전국 대비 수치가 `nation.json`과 소수 첫째 자리까지 일치하고 `% %` 중복이나 `명` 누락이 `0건`이다(감사 20 통과). ② 고용률·재정자립도는 `"도시 중앙"` 기준으로 표시되고, 서울(`id=0`)·부산(`id=1`)처럼 `member_ranges`인 광역시에는 대비 화살표가 생성되지 않는다. ③ 세종(`id=30`) 1인당 GRDP 대비 줄에 `전국('23)` 연도가 명시되고, 울릉군(`id=166`, 매매 3건) 매매가 대비 줄에 `(거래 3건)`이 붙는다. ④ 순위 게이지 분모가 수출 `165`, 아파트 `166`, 나머지 `167`이고, 포천시(`id=63`) 수출 행은 `"자료 없음 · 순위 제외"`로 클릭 비활성이다. ⑤ 순위 행 클릭·`Enter` 시 `rank-1`/`rank+1` 점프 칩이 펼쳐지고, 칩 클릭 시 해당 도시로 이동한다. |
| **#11** (반드시) | ① 167개 도시 전체 검사: `cities[i].lq_gdp`, `lq_jobs`, `tags`에 `NaN`/`Infinity` `0건`, `tags.length <= 2` 100% 준수, 비공개 산업(`gdp_undisclosed` 25곳·`jobs` 47곳)에 LQ 미생성. ② 화성시(`id=9`)=`제조업 비중 ×2.6` + `1인당 GRDP 8위` (2개), 익산시(`id=40`)=산업 태그 미생성(`0개`), 울진군(`id=115`)=`전기·가스·증기 비중 ×33`(+소규모 주석), 세종(`id=30`)=`공공행정·국방 비중 ×4.4`(+2024/2023 주석). ③ 태그 텍스트에 주관적 수식어가 없으며, 태그 클릭 시 `#fnpop`에 `도시 비중 ÷ 전국 공식 비중 = ×배수` 산식이 표시된다. |
| **#32** (반드시) | ① Chromium·Firefox·WebKit 3엔진에서 1:1(`1200×1200`) 및 16:9(`1600×900`) PNG가 모두 `> 50 KB` 유효 PNG로 생성되고 다운로드 또는 미리보기 시트가 동작한다. ② `최대 산업`(`top_industry`, 14개 범주) 화면에서 내보낸 1:1·16:9 PNG 모두 **14개 범주가 하나도 빠짐없이** 범례에 그려진다(감사 12 통과). ③ 지형·렌즈 PNG 모두 하단 출처 줄에 OSM 기여자(ODbL)·행정안전부 경계·활성 렌즈 전체 출처·고정 안내 문구가 46자 절단 없이 식별 가능하게 인쇄된다(감사 03 통과). ④ 1:1 카드에서 제목이 우측 기준 시점과 겹치지 않는다(`전남광주통합특별시`·`화성시 vs 무안군` 기준). |
| **#13** (하면 좋음) | ① 167개 도시 × 5닮은 도시 = 835건 전체에서 `peer_reasons` 생성 예외 `0건`. ② 화성시(`id=9`) 1번 닮은 도시 아산시(`id=31`) 아래에 `1인당 GRDP·제조업 비중(70.6%·74.3%) 비슷 · 매매가 2.8배 차`가 표시된다. ③ 울릉군(`id=166`, `trades: 3`)·옹진군(`id=164`, `null`)에서는 매매가 배수 차이가 미노출된다. ④ 좌측 이동 버튼과 우측 `비교` 버튼(44×44px)이 중첩 DOM 없이 독립 동작한다. |
| **#14** (하면 좋음) | ① `#cmp=9,12`(화성시 vs 울산) 진입·새로고침·`⇄ 바꾸기`·`B 변경`·`Esc` 취소/복귀가 정상 동작한다. ② **비교 모드(`#cmp=9,164` 화성시 vs 옹진군, `#cmp=9,63` 화성시 vs 포천시)에서 값이 없는 칸은 `"자료 없음"`이고 막대가 그려지지 않으며(`0px`/DOM 없음) Δ 칸은 `"–"`이다.** ③ `#cmp=30,9`(세종 vs 화성시)에서 `"GRDP 기준 연도 다름"` 경고가 뜨고 GRDP·산출 Δ가 미계산된다. ④ `#cmp=0,6`(서울 vs 수원시)에서 고용률·재정자립도가 `"비교 불가(범위)"`로 처리된다. ⑤ `#cmp=0,166`(서울 vs 울릉군) 피라미드가 비중(%) 정규화로 양쪽 모두 판독 가능하다. ⑥ `1280×800`에서 비교 패널(`460px`)이 `#minimap`·`#lensbar`와 겹치지 않고, `390×844`에서 가로 넘침이 `0px`이다. ⑦ `#cmp=9,9`·`#cmp=9,999`는 단일 도시 폴백+토스트로 처리된다. |
| **#20** (하면 좋음) | ① `nation.json.presets.items` 6개 모두 `kind === "auto"`이며 `rule`·`metric` 문자열을 보유하고, 빌드 재실행 시 수동 좌표 없이 원자료에서 결정적으로 재현된다. ② `#search` 빈 상태와 `#help`에서 6개 시점 클릭 시 의도한 렌즈·층·위치로 이동하고, 생성된 해시를 새 탭에 열었을 때 동일 화면이 복원되며 신규 해시 키가 추가되지 않는다. ③ `prefers-reduced-motion: reduce`에서 `flyTo` 보간 없이 즉시 이동한다(감사 19 통과). |

---

## 6. 독립 감사 23건 ↔ 채택안 맞물림 표

감사 결함 수정이 선행이며, 아래 19건은 본 설계안과 같은 파일·데이터·DOM을 공유하므로 **한 번에 통합 구현**해 이중 수정을 없앤다. 나머지 4건(04·06·15·23)은 데이터·원표·보고서 단독 결함이므로 0단계 선행 감사 수정에서 독립 처리한다.

| 감사 # | 심각도 | 결함 요약 | 맞물리는 안 | 함께 고칠 때의 통합 설계 |
|---|---|---|---|---|
| **01** | 높음 | 개편 구역(화성 4구·인천 서해/검단)에 구별 공표 전 값 복사 표시 | #10, #14 | `lenses.json`에 `pub_unit` 메타 직렬화 → 툴팁 및 #9/#10 `retiredBlock`에서 `"화성시 전체, 2025"` / `"개편 전 인천 서구"` 표시, 구 단위 대비 화살표 미생성 |
| **02** | 높음 | 토지피복 WMS 저장 제한과 제1유형 단독 표기 | #32 | `world.json`/`sources.json`에 정정된 이용조건 문자열을 두고, #32 PNG 하단 지형 출처가 하드코딩 대신 그 문자열을 동적 인쇄 |
| **03** | 높음 | 공유 PNG 출처·OSM ODbL·경계 저작자 누락 및 46자 절단 | **#32** | #32 하단 띠에 전용 출처 2줄 행을 설계해 실제 활성 레이어 출처 + OSM ODbL + 경계 + 고정 안내 주소를 절단 없이 인쇄 |
| **05** | 중간 | 부산·울산·대구·인천 도시 패널 부제에 자치구 합/별도 군 미표기 | **#9**, #10, #14 | 빌드 단계에 `cities[i].scope_label` 추가 → #9 도시 패널 헤더 부제와 #14 비교 헤더에 한 번에 표시(`design2` 공유) |
| **07** | 중간 | `search.js`·`tooltip.js`·`lensbar.js`·`almanac.js` 데이터 문자열 HTML 삽입 | #1, #9, #10, #11, #13, #14, #20 | 신규 UI 및 수정 파일에서 모든 데이터 문자열 `esc()`/`textContent` 통일, 출처 URL `https?://` 스킴 검증 동시 반영 |
| **08** | 중간 | JSON 하나(예: `trade.json`, `sources.json`) 실패 시 전체 전파 | **#9**, #14 | `loadLayers()`를 `Promise.allSettled`로 분리, #9 `시설·교역` 탭과 #14 비교에서 실패한 모듈만 국소 오류+재시도 표시 |
| **09** | 중간 | 좁은 화면(390/768px)에서 순위 보고서 4개 진입 불가 | #12 | 상단 띠 보고서 메뉴는 0단계 감사 수정으로 해결, #12 5산출 스트립이 모바일에서도 도시 5산출 순위를 빠짐없이 노출 |
| **10** | 중간 | 키보드(`Enter` 미동작, 범례 포인터 전용) 및 화면 낭독기 부재 | **#9, #10, #12, #13, #14, #20, #32** | 모든 신규 UI를 네이티브 `<button>` + ARIA(`tablist`/`menu`/`dialog`) + 공용 `#sr-live` (`aria-live="polite"`)로 구축 |
| **11** | 중간 | 공유 해시가 이전 선택 잔존, 빈 `#city=` 서울 열림, 무효 ID 처리 오류 | **#9, #14, #20** | `readHash()`를 불변 파싱 → 상태/비교/타이머 일괄 초기화 → 단일 유효 대상 적용으로 재작성하면서 `tab=`·`cmp=` 통합 |
| **12** | 중간 | PNG 범례 8개 절단 (`최대 산업` 14개 중 6개 누락) | **#32** | #32 PNG 범례의 `slice(0, 8)` 폐지, 관측 범주 수에 따른 동적 열·행 및 `BAND` 높이 계산으로 14개 전량 표시 |
| **13** | 중간 | `validate.py` 검증 통과 수와 진단 출력 혼재·감도 부족 | 빌드 공통 (#10, #11, #13, #20) | 새 빌드 필드(`benchmarks`, `lq_gdp`, `tags`, `peer_reasons`, `presets`) 검증 항목을 `validate.py`에 실제 원표 재계산 단언으로 추가 |
| **14** | 중간 | 소멸위험 `주의` 배지 명도 대비 2.11:1 | **#9, #10**, #14 | #9 `개요` 탭 및 #14 비교 모드에서 `STAGE_COLOR` 5단계의 글자색을 4.5:1 이상(`보통`·`주의` 어두운 글씨 `#11151d`)으로 전면 교체 |
| **16** | 중간 | 생산 부분 합 주석이 공개된 광업 포함 사실을 누락 | **#12**, #14 | #12 산출 스트립 말풍선·단일 주의 서랍 및 #14 비교 주석을 `"제조업 + 건설업 + 공개된 광업의 합 (광업 비공개 N곳 제외)"`로 통일 |
| **17** | 낮음 | 768px 상단 띠 수치 2줄 줄바꿈 | (상단 띠) | 0단계 감사 수정으로 해결; 본 10안은 `#topbar`에 요소를 일절 추가하지 않아 768px 폭 부담 증가 `0px` |
| **18** | 낮음 | 첫 화면 `lenses.json` null 417 KB 낭비 | 빌드 공통 (#10, #11, #13, #20) | 감사 18로 약 `450 KB` 절감하면 신규 빌드 JSON(`+116 KB`)을 모두 합쳐도 전체가 `4.29 MB`로 현행보다 감소 |
| **19** | 낮음 | `prefers-reduced-motion` 무시 `flyTo` 보간 | #10, #14, #20 | `main.js` `flyTo()`에서 `reducedMotion`이면 즉시 이동하도록 수정해 #10·#14·#20 이동 전체에 자동 적용 |
| **20** | 낮음 | 백분율 `% %` 중복 및 인구 `명` 누락 | **#10**, #13, #14 | 공용 `site/js/ui/format.js` 도입으로 `report.js`·`tooltip.js`·#10 대비·#14 비교의 단위 조립 일원화 |
| **21** | 낮음 | 도움말 `"땅 누르면 도시"` 오기 | **#9, #20, #32** | `help.js`에 4탭·추천 시점·1:1 PNG 안내를 추가하면서 `"깃발=도시, 시도 이름·빈 땅=시도"`로 동시 정정 |
| **22** | 낮음 | 한국어 UI에 `point`·`county`·`linear` 등 내부 키 노출 | **#1**, #9 | `layers.js` `PRECISION`·`panel.js` 청사·#1 오프셋 툴팁에서 영문 키를 `"원자료 좌표"`·`"시군구 대표 위치"`로 한국어화 |

*(독립 선행 감사 항목 4건: **04** 변경금지 자료 이용범위, **06** 의사 수 렌즈 basis 문구 정정, **15** 출처 원본/정리표 경로 분리, **23** 소멸위험지수 보고서 구성도 비율 분모 수정 → 0단계에서 별도 완료.)*

---

## 7. 화면 복잡도(지저분함) 자체 점검

전체를 다 넣었을 때 화면이 다시 무거워지거나 복잡해지지 않는지 **전국 첫 화면**과 **도시 패널 첫 화면(울산 `id=12`, `1280×800` 스크롤 전 뷰포트 `722px`)**의 가시 요소 수를 정량 비교한다.

### 7.1 전국 첫 화면 (`1280×800` · `390×844`) 요소 수 비교

| 구역 | 현재 (6단계) | "반드시" 7개 적용 후 | "하면 좋음" 포함 (10개) | 증감 및 정리 근거 |
|---|---:|---:|---:|---|
| 상단 `#topbar` 버튼·수치 | 데스크톱 13 / 모바일 8 | 데스크톱 13 / 모바일 8 | 데스크톱 13 / 모바일 8 | **증가 0건** (#19·#21 제외, #20은 `#search`/`#help` 내부 배치) |
| 좌상 `#layerctl` | 6버튼 (1줄) | 6버튼 (1줄) | 6버튼 (1줄) | **증가 0건** |
| 좌하 `#legend` | 지형 범례 1박스 | 지형 범례 1박스 | 지형 범례 1박스 | **증가 0건** (#18 불채택으로 버튼 2개·짝 렌즈 줄 추가 차단) |
| 하단 `#lensbar` | 7버튼 (지형+6묶음) | 7버튼 | 7버튼 | **증가 0건** |
| 캔버스 도시 깃발 (`z=1`) | 데스크톱 ~22 / 모바일 ~8 | 상한 24 / 모바일 12 | 상한 24 / 모바일 12 | `banners.avoid()` 제거로 부당 탈락만 회복, 예산 상한으로 과밀 차단 |
| 캔버스 지도 층 아이콘 (`z=1`) | 데스크톱 ~35~45 / 모바일 ~15 | 상한 52 (원전5·공항6·항만8 보장) / 모바일 24 | 동일 | 전략 인프라 19곳 보장 후 나머지 P2를 예산 안에서 절제 |
| 캔버스 시도 이름표 (`z=1`) | 9개 (최상단 굵은 고딕) | 9개 (배경층 반투명 명조, 모바일 ≤24px) | 동일 | 요소 수는 같으나 **시각 무게 대폭 감소** (전경 경쟁 제거) |
| **전국 첫 화면 UI 크롬 합계** | **27개** (모바일 21개) | **27개** (모바일 21개) | **27개** (모바일 21개) | **크롬 증가 0건** |

### 7.2 도시 패널 첫 화면 (`울산 id=12`, `1280×800`, 스크롤 전 `722px` 이내) 비교

| 요소 | 현재 (6단계) | 적용 후 (`개요` 탭) | 변화 및 덜어 낸 요소 |
|---|---:|---:|---|
| 헤더 배지·태그 | 배지 1개 | 배지 1 + 특성 태그 2 (`제조업 비중 ×2.2`, `수출 3위`) + `비교` 버튼 1 (#14 시) | **+2~3개** (상한 2개로 1줄 고정; 주관 수식어 배제) |
| 핵심 인구 + 5산출 | 인구 1줄만 (5산출은 스크롤 아래 2,000px 뒤에 숨음) | 인구 1줄 + 5열 1행 산출 스트립 | **+5칸** (대신 타일 4번째 줄 종사자·규칙 문구를 말풍선으로 **덜어 냄**) |
| 4탭 바 | 없음 | 4개 탭 버튼 (1줄) | **+4개** (대신 패널 전체 `scrollHeight` 약 **60% 단축**) |
| 인구 차트 | 시계열 1 + 피라미드 1 (세로 `364px`) | 시계열 + 피라미드 2열 병렬 (`132px`) | 개수 동일, **세로 높이 `232px` 절감** |
| 연령·소멸 카드 | `.kv` 6칸 + `.ext` 1칸 | `.kv` 6칸(+대비 1줄) + `.ext` 1칸(공식 문장 제거→`ⓘ`) | `.ext` 설명 문단 **덜어 냄** (`22px` 절감) |
| 건강·더 많은 지표 (`retiredBlock`) | 첫 화면 하단에 바로 노출 (11칸, `6_panel_notes.png`) | **`땅·행정` 탭으로 이동 (첫 화면에서 제거)** | **−11칸 덜어 냄** (첫 화면 밀도 대폭 감소) |
| 순위 구역 | 스크롤해야 보임 (4열 9박스) | **첫 화면 하단에 1열 미니 게이지 6~7행 즉시 노출** | 스크롤 없이 핵심 순위 판독 가능 |
| `기준과 주의` 서랍 (패널 전체) | 구역마다 **7~9개** 산재 | 활성 탭 최하단 **단 1개** | **−6~8개 서랍 덜어 냄** |

**자체 점검 결론**:
- 전국 첫 화면의 UI 크롬 요소 수는 **완전 동결(+0개)**이다.
- 도시 패널 첫 화면에 새로 추가되는 요소(특성 태그 2개, 5산출 1줄, 4탭 바 1줄, 비교 버튼 1개)는, **`retiredBlock` 11칸의 탭 분리 + 산출 타일 4번째 줄 제거 + `details.caveats` 7~9개→1개 통합 + 차트 2열 병렬 + `.ext` 설명 문단 제거**로 상쇄되어 실제 첫 화면의 인지 밀도는 오히려 낮아지고 핵심 정보(5산출·전국 대비·순위) 도달 거리는 1/3로 줄어든다.
- 만약 구현 후 실측 화면(`1280×800`)에서 울산 `개요` 탭의 `순위`가 잘린다면, **1순위 절감 대상**은 `.kv` 6칸 중 `평균연령`·`중위연령`의 전국 대비 1줄을 생략(행 높이 `12px` 추가 절감)하고, **2순위 절감 대상**은 `.pop-charts` 높이를 `108px → 92px`로 줄인다.

---

## 8. 구현 순서 · 예상 작업량 · 위험이 큰 순서

### 8.1 구현 순서 (의존 관계)

```text
[0단계: 독립 감사 선행 수정]
  감사 04·06·15·23 (데이터·원표·보고서) + 감사 01·02·07·08·09·10·11·14·17·18·19·20·22 기반 정리
   │
   ▼
[1단계: 빌드 파이프라인 공용 스키마 확장]  (site/ · design2/ 공용)
  - wonders.json: zoom.draw_priority.second, zoom.budget (#1)
  - cities.json: scope_label (감사 05), lq_gdp, lq_jobs, tags (#11), [하면 좋음] peer_reasons (#13)
  - nation.json: benchmarks, lq_rule (#10·#11), [하면 좋음] presets (#20)
  - validate.py: 신규 필드 교차 검증 + F6 (< 5 MB) 통과 확인
   │
   ├──▶ [2단계: 지도 첫 화면 정리]
   │      #2 (시도 이름 각인화·층위 하향) ──▶ #1 (통합 배치 예산 + GeoLabels 회피)
   │
   ├──▶ [3단계: 공용 포매터 + 도시 패널 개편]
   │      format.js (감사 20)
   │      ──▶ #12 (5열 산출 스트립 + 단일 주의 서랍 + 감사 16)
   │      ──▶ #9  (도시 패널 4탭 + 감사 05·08·11·14·21)
   │      ──▶ #10 (전국 대비 + 순위 미니 게이지 + 감사 01)
   │      ──▶ #11 (LQ 막대 병기 + 특성 태그 최대 2개)
   │
   ├──▶ [4단계: 공유 PNG 통합 수정]
   │      #32 (감사 03 출처 + 감사 12 전체 범주 + 크로스브라우저 + 1:1 정사각)  [의존: #1, #2]
   │
   └──▶ [5단계: 하면 좋음 — 여유 시 순차 투입]
          #13 (닮은 도시 근거 1줄) ──▶ #14 (도시 A vs B 최소 비교 + #cmp= + PNG 연동)
          #20 (데이터 규칙 추천 시점 6선 — #13/#14와 독립, 병렬 가능)
```

### 8.2 안별 예상 작업량 및 수정 파일

| 분류 | 안 | 예상 작업량 | 주요 수정·신규 파일 |
|---|---|---|---|
| 반드시 | **#2 시도 이름 각인화** | **하** | `site/js/render/labels.js`, `banners.js`, `main.js` |
| 반드시 | **#1 통합 배치 예산** | **중** | `pipeline/build_phase6.py`, `site/js/render/layers.js`, `banners.js`, `geolabels.js`, `ui/tooltip.js`, `main.js` |
| 반드시 | **#12 산출 스트립 + 단일 서랍** | **하** | `site/js/ui/panel.js`, `render/banners.js`, `css/style.css` |
| 반드시 | **#9 도시 패널 4탭** | **중** | `pipeline/build_regions.py`(또는 `build_phase6.py`), `site/js/ui/panel.js`, `main.js`, `ui/help.js`, `css/style.css` |
| 반드시 | **#10 전국 대비 + 순위 게이지** | **중** | `pipeline/build_phase6.py`, `site/js/ui/format.js`(신규), `ui/panel.js`, `ui/report.js`, `ui/tooltip.js`, `css/style.css` |
| 반드시 | **#11 입지계수 LQ + 특성 태그** | **중** | `pipeline/build_phase6.py`, `site/js/ui/panel.js`, `ui/almanac.js`, `css/style.css` |
| 반드시 | **#32 PNG 안정화 + 1:1 카드** | **중** | `site/js/ui/share.js`, `index.html`, `ui/help.js`, `css/style.css` |
| 하면 좋음 | **#13 닮은 도시 근거** | **하** | `pipeline/build_econ.py`, `site/js/ui/panel.js`, `css/style.css` |
| 하면 좋음 | **#14 도시 A vs B 비교** | **상** | `site/js/ui/panel.js`, `main.js`, `ui/search.js`, `ui/share.js`, `css/style.css` |
| 하면 좋음 | **#20 데이터 규칙 추천 시점** | **하** | `pipeline/build_phase6.py`, `site/js/ui/search.js`, `ui/help.js`, `main.js`, `css/style.css` |

### 8.3 위험이 큰 순서와 완화 방안

| 위험 순위 | 대상 안 | 핵심 위험 | 완화 및 검증 방안 |
|---|---|---|---|
| **1 (최고)** | **#14 도시 A vs B 비교** | 패널 폭 전환(`360→460px`) 시 `#minimap`·`#lensbar` 겹침, `readHash()` 상태 꼬임(감사 11), `picking` 중 클릭·검색·`Esc` 상태 누수, 연도/범위 혼합 비교 오해 | "하면 좋음"으로 분리해 1차 안정화 후 투입. 탭 없는 1면 최소 형태 고정. `tools/qa_interaction.py`에 `#cmp=` 유효/무효/동일ID/`Esc` 회귀 테스트 추가. |
| **2** | **#32 PNG + 감사 03·12** | Safari/WebKit·iOS 인앱 `toBlob` 실패, 14개 범주+2줄 출처로 하단 띠가 좁아져 텍스트 겹침, 토지피복 이용조건(감사 02) 문구 불일치 | 동적 `BAND` 높이 계산과 `measureText` 말줄임 강제, Playwright 3엔진(Chromium·Firefox·WebKit) PNG 픽셀/크기 자동 검증, 감사 02 문자열 단일 진실원 참조. |
| **3** | **#9 도시 패널 4탭 + #12 서랍** | 기존 `tools/qa_interaction.py`·`tools/audit/samples.py`가 단일 스크롤 DOM을 가정해 탭 내부 요소 조회가 깨질 수 있음. `1280×800`에서 `순위`가 스크롤 아래로 밀릴 위험 | 숨겨진 탭은 `hidden` 속성만 써 DOM에 유지(또는 탭 전환 시 스코프별 `footnotes()` 실행)하고 QA 스크립트 업데이트. `.pop-charts` 2열 병렬 후 `1280×800` 울산 실측 캡처로 무스크롤 합격 검증. |
| **4** | **#1 통합 배치 예산** | 공항(6)·무역항(8) 오프셋이 과도해 실제 위치 오인, 수도권·부산 해안에서 지시선이 서로 교차하거나 깃발 글씨를 가로지름 | 최대 이동 거리 `2.4r`(모바일 `2.0r`) 엄격 제한, 기존 `cross()` 페널티 유지, 툴팁에 오프셋 사유+원래 정밀도 명시. 전국 화면 스크린샷 육안 대조. |
| **5** | **#11 입지계수 LQ·특성 태그** | 소규모 군(`울진군 ×33`, `영월군 ×59`) 과잉 해석, 반올림 경계(`익산시 1.49→1.5`) 오발동, `cities.json` 비대화(`F6 < 5 MB` 압박) | 반올림 전 임계 판정, 상한 2개·사실 수치 문구 강제, `population < 50,000 && lq >= 10` 자동 주석, `share >= 1%`만 저장해 용량 통제(`+72 KB`). |
| **6** | **#10 전국 대비 + 순위 게이지** | 고용률·재정자립도(조사 상이), 광역시 `member_ranges`, 세종 2024년 GRDP, 개편 구역(감사 01)에서 부당한 비교 화살표 발생 | `nation.benchmarks`에 `ref: 'city_median'`·`year` 명시, 범위·결측·개편 구역은 화살표 생성 금지, 공용 `format.js`로 `% %` 중복 원천 차단. |
| **7 (최저)** | **#2, #13, #20** | #2: 진한 렌즈 위 명조 대비 저하 / #13: 소표본 매매가 배수 왜곡 / #20: 지연 로딩 전 `top_route` 클릭 | #2: 렌즈 활성 시 외곽선 불투명도 자동 상향 / #13: `trades >= 10` 필터 / #20: `pendingRoute` 예약 및 `validate.py` 자동 추출 재현 검사. |
