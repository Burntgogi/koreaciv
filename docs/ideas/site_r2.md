# koreaciv 프런트엔드 브레인스토밍 2회차 (`site_r2`)

작성일: 2026-11-27  
대상: `C:\work\korea\site` 정적 앱 (바닐라 ES 모듈 + Canvas, 외부 라이브러리·CDN·서버 없음)  
전제 조건:
- **데이터 추가 제외**: `site/data/*.json` 11종에 이미 들어 있는 필드만 사용한다. 숫자를 꾸미거나 결측을 추정하지 않는다.
- **성격 유지**: 별도 디자인(신여지도)과 **같은 데이터·같은 URL 해시**를 공유한다. 기존판은 "원본(`usaciv`)에 충실한 전략 게임 판" 성격을 지키며, 구조를 갈아엎기보다 완성도를 높인다.
- **우선순위**: 별도 감사에서 나오는 결함 수정이 먼저다. 채택 가짓수는 **11개**(10개 안팎, 1회차 #25는 #32에 흡수)로 제한한다.

---

## 1. 1회차 32안 선별 결과

### 채택 목록 (11개)

| # | 제목 | 분류 | 2회차 반영 방향 |
|---|---|---|---|
| **#1** | 아이콘·깃발 통합 배치 예산과 전략 인프라 우선권 | 지도 | 현행 `wonders.json` `zoom.draw_priority` (`nuclear` 단독)를 P1a/P1b·화면 예산 규칙으로 확장 |
| **#2** | 시도 이름표의 지도판 각인화(명조·반투명)와 층위 하향 | 지도 | 깃발·아이콘 아래로 내리고 `banners.avoid()` 삭제 |
| **#12** | 다섯 산출 5열 1행 스트립 + '기준과 주의' 통합 서랍 | 패널 | 3+2 비대칭을 5열 1행 HUD로 압축, 산재된 서랍을 1개로 통합 |
| **#10** | 핵심 지표 '전국 기준 대비(▲/▼)' 및 '전국 순위 미니 게이지' 인라인 병기 | 패널 | `nation.json` 동일 기준만 대조(고용률·재정자립도는 도시 중앙값), 순위 인접 도시 점프 포함 |
| **#11** | 산업 특화도(입지계수 LQ) 계산과 객관적 '도시 특성 태그' | 패널 | 조건부 채택 해소: 공식 전국값 분모, `비중 ≥ 5% ∧ LQ ≥ 1.5` 임계값, 비공개·결측 규칙 고정 |
| **#9** | 도시 패널 4탭 구조화(개요 · 경제 · 시설·교역 · 땅·행정)와 탭 기억 | 패널 | 세로 스크롤 60% 단축, 마지막 탭 유지, `tab=` 선택 해시 |
| **#13** | '닮은 도시' 유사 근거 1줄 요약과 원클릭 비교 연결 | 탐색 | `peers` 5곳마다 가장 비슷한 2개 축 + 결정적 차이 1개 요약, 우측 `비교` 버튼으로 #14 직결 |
| **#14** | '도시 대 도시(A vs B)' 나란히 비교 모드 & 지도 연결 아크 | 비교 | 460px 2열 대조표, 비중 정규화 피라미드 겹치기, 지도 아크, `#cmp=a,b` 공유 |
| **#18** | 렌즈 '직전 대비 토글(`B`)'과 '지형 엿보기(`Space` 홀드)' | 렌즈 | 25줄 내외 경량 조작으로 렌즈 교차 판독과 지형 대조 강화(연관 렌즈 1줄 제안 연계) |
| **#20** | '추천 시점(관전 포인트)' 프리셋 6선 | 온보딩 | 신규 해시 키 없이 기존 해시 조합 재활용, 검색 빈 상태·도움말 노출 |
| **#32** | PNG 내보내기 크로스브라우저 안정화 및 1:1 정사각 카드 (#25 흡수) | 공유 | `fonts.ready`, `toBlob` 폴백, Web Share·미리보기 시트, 1200×1200 정사각 추가 |

### 제외 목록 (21개 — 각 한 줄 이유)

- **#3 도시 깃발 산업 문장**: 6단계에서 줄인 화면 밀도가 다시 지저분해지고 수도권·영남 깃발 탈락이 늘어남(산업 정체성은 패널 #11로 대체).
- **#4 절차적 시가지 스카이라인·논두렁·등수심선**: 타일 렌더 비용과 시각적 노이즈 위험이 커 완성도 개선 범위를 넘음.
- **#5 국정 자문관 6인 드로어**: 기존 `report.js`와 역할이 겹치고 기존판 UI 구조를 크게 바꿈.
- **#6 도시 집중 보기(City View)**: 별도 모달/암막 모드 추가는 구조 변경 폭이 크고 대면적 시군에서 라벨이 과밀해짐.
- **#7 '1분 발견' 탐색 질문 칩**: 퀴즈식 카피가 공공데이터 지도에서 장난감 인상을 줄 수 있으며, 입문 동선은 #20 프리셋으로 충분함.
- **#8 '전국 탐험 도감' (`localStorage`)**: 수집 진행률 표시가 정보 도구를 게이미피케이션 장난감처럼 보이게 할 위험이 큼.
- **#15 이변량(Bivariate) 2축 조합 렌즈**: 9색 매트릭스는 해석·색각 장벽이 높고 신여지도와 공유할 새 해시 규격 합의가 필요함.
- **#16 렌즈 막대 전면 개편(고정 4 + 팝오버)**: 하단 크롬 구조 변경 폭이 크며 6단계 6묶음 막대와 기본 성격이 달라짐.
- **#17 범례 분포 히스토그램 + 선택 지역 핀**: 면적(칸) vs 인구 가중 해석 분기 관리가 필요해 10개 예산 밖으로 보류.
- **#19 3단계 '첫걸음' 가이드 칩**: 첫 화면 상단에 추가 줄이 생기고 공유 링크·스크린샷 예외 처리 부담 대비 효용이 작음(#20으로 대체).
- **#21 상단 검색창 상시 노출 + 초성 검색**: 1024~1250px에서 상단 8개 전국 수치 버튼과 가로 폭을 두고 충돌함.
- **#22 모바일 3단 드래그 바텀시트**: iOS Safari 내부 스크롤과의 제스처 충돌 검증 비용이 커 #9 탭으로 세로 길이를 먼저 줄임.
- **#23 모바일 터치 근접 선택기**: 새 팝오버 상태 기계를 추가하므로 감사 결함 정리 후 모바일 후속 과제로 보류.
- **#24 모바일 1줄 상단바 + 하단 통합 독**: 모바일 크롬 전면 재설계라 기존판 안정화 범위를 초과함.
- **#25 모바일 PNG 공유·저장 폴백**: 단독 안으로 두지 않고 **#32 PNG 안정화의 모바일 경로로 흡수 통합**.
- **#26 카메라 이동 도착 파문과 선택 영토 암전**: 애니메이션 효과는 정적 판독성에 필수적이지 않고 모션 설정 분기만 늘림.
- **#27 교역로 우세 방향 흐름 맥동**: 교역로는 기본 꺼짐 층이며 상시/준상시 rAF 루프 관리 대비 체감 효용이 작음.
- **#28 렌즈 전환 크로스페이드**: `L` 연타 시 화면 반응이 둔하게 느껴질 수 있어 우선순위에서 제외.
- **#29 오프스크린 타일 캐시 LRU 상한**: 기능 개선안이 아니라 감사에서 메모리 결함이 확인될 때 결함 수정으로 처리함.
- **#30 색각이상 안전 팔레트 토글**: 33종 렌즈 램프 치환과 범례 대조 검증 범위가 넓어 감사 이후 접근성 일괄 작업으로 보류.
- **#31 키보드 깃발 순환·모달 포커스 트랩·`aria-live`**: 감사 접근성 지적 항목과 묶어 일괄 수정하는 편이 중복 작업을 막음.

---

## 2. 채택 11안 구현 명세

### #1. 아이콘·깃발 통합 배치 예산과 전략 인프라 우선권

> 현행 코드 확인: `site/js/render/layers.js`는 이미 `wonders.json`의 `zoom.draw_priority.first = ["nuclear"]`에 한해 `priorityBoxes()`와 `rings()` 이웃 칸 오프셋을 수행한다. 그러나 `airport`(6곳)·`trade_port`(8곳)는 일반 아이콘과 같아 `6_nation_after.png`에서 김포·김해·제주·대구·청주 공항과 부산·인천·울산항이 대도시 깃발에 밀려 증발한다. 이를 **P1a(깃발 회피)**와 **P1b(아이콘 자체 오프셋 보장)** 2단 전략 인프라 규칙과 화면 예산으로 확장한다.

- **화면 위치와 동작**:
  - 데스크톱/모바일 공통: `main.js` `drawScene()`의 배치 단계(`banners.layout` ↔ `layerR.layout`).
  - 전국 배율(`z < 2.0`, `tier === 0`):
    - **P1a(`nuclear`, 5곳)**: 현행과 동일. 제자리 상자를 `banners.layout(..., prio)`에 넘겨 깃발이 먼저 좌우/아래로 비켜 서고, 대도시 깃발과 불가피하게 겹칠 때만 아이콘이 이웃 칸으로 이동해 지시선 연결.
    - **P1b(`airport` 6곳, `trade_port` 8곳 — 모두 `tier === 0` 항목)**: 대도시 깃발(`서울`, `부산`, `인천`, `대구`, `제주시`, `청주시` 등)을 밀어내지 않는다. 대신 깃발이 놓인 뒤 P1b 아이콘이 깃발·먼저 놓인 아이콘과 겹치면 `rings(rp.cell, maxRing)`에서 **원래 칸 중심으로부터 화면 거리 `<= 2.4 * r0` 이내의 가장 가까운 빈 칸(바다 칸 포함)**으로 이동하고 원래 칸 중심(`ox, oy`)에 기준점과 가는 지시선을 그린다.
    - **P2(나머지 `tier === 0` 아이콘)**: `world_heritage`, `knowledge`, `national_park`, 기타 발전소, `industrial_national`은 깃발과 겹치면 숨기며, 전국 배율 총 아이콘 예산(데스크톱 **52개**, 모바일 `vw <= 700` **24개**) 안에서 `drawCmp` 순으로 채운다.
  - 중간·가까이(`z >= 2.0`): 총 아이콘 예산 상한을 풀고 기존 `tier`/`iconHit` 규칙 적용(P1a/P1b 오프셋은 유지).
- **실제 데이터 필드 경로**:
  - `wonders.json`: `wonders.zoom.levels` (`tier` 0/1/2, `z_min` 0/2.0/3.2), `wonders.zoom.draw_priority.first` (`["nuclear"]`), `wonders.zoom.knowledge_groups.groups`, `wonders.items[k].{id, kind, cell, tier, value, precision}`
  - `resources.json`: `resources.items[k].{id, kind, cell, tier, value, precision}` (`nuclear` 5건)
  - `infrastructure.json`: `infrastructure.items[k].{id, kind, cell, tier, value, precision}` (`airport` `tier:0` 6건, `trade_port` `tier:0` 8건)
  - `cities.json`: `cities[i].{id, x, y, capital, population}`
- **계산식**:
  - 배율 `z = cam.scale / cam.minScale`.
  - 아이콘 반지름 `r0 = Math.max(8, Math.min(13, 8 + (z - 1) * 0.9))`.
  - P1b 오프셋 허용 최대 화면 거리: `maxDist = Math.max(2.4 * r0, 22)` (모바일 `vw <= 700`은 `2.0 * r0`).
  - 탐색 링 깊이: `maxRing = Math.max(2, Math.min(10, Math.ceil(maxDist / (grid.W * cam.scale))))`.
  - 오프셋 후보 점수: `score = hypot(x - sx, y - sy) + (water[c] > 0 && kind === 'trade_port' ? -4 : 0)` (무역항은 바다 쪽 빈 칸을 미세 우대).
- **"자료 없음" · 부분 합 · 비공개일 때 표시**:
  - 위치가 없어 `cell == null`인 항목(`resources.unplaced` 4건 등)은 지도 배치 대상에서 제외하고 기존처럼 검색·패널·연감에만 표시한다.
  - 오프셋된 아이콘의 툴팁(`tooltip.js`)·항목 패널(`panel.js`)에는 원래 칸 정밀도(`precisionText(it)`)를 그대로 두고, `p.ox != null`일 때 툴팁 끝에 `"깃발을 피해 옆 칸에 표시 (원래 위치는 선 끝 점)"` 1줄을 덧붙인다.
- **규칙 문장 (연감 `지도 층` 탭 초안)**:
  > "전국 배율(z < 2.0)에서는 원전 5곳을 최우선(깃발 회피 허용)으로, 주요 공항 6곳과 무역항 8곳을 전략 인프라 우선군(깃발은 제자리에 두고 아이콘만 2.4r 이내 가까운 빈 칸으로 옮겨 원래 칸 중심에 선을 이음)으로 먼저 놓는다. 그 밖의 전국 배율 아이콘은 깃발과 겹치지 않는 범위에서 데스크톱 최대 52개, 모바일 최대 24개까지 종류 우선순위·값 순으로 그린다."
- **키보드 · 터치 동작**:
  - 기존 클릭·호버·`R`(자원 토글) 동일. 지시선 끝 기준점이 아니라 아이콘 배지(`p.x, p.y`, 히트 반경 `Math.max(p.r + 2, 10)` 터치 시 `14`)로 선택한다.
- **공유 링크 해시 키**: 없음.
- **예상 엣지 케이스**:
  - **광역시와 자치구**: 부산항(`i5-15`, `city: null`, `precision: 'sido'`)·울산항(`i5-25`, `city: null`, `precision: 'sido'`)은 `city`가 비어 있고 `부산`/`울산` 대도시 깃발 바로 옆 해안 칸에 놓여 있다. P1b 바다 쪽 빈 칸 오프셋으로 부산·울산 깃발을 가리지 않고 모두 표시된다.
  - **전남광주통합특별시**: `광주(5)`·`무안군(80)`은 `capital: '통합청사'`로 `big` 깃발 취급이므로 P1b(`광양항` 등)가 깃발을 밀어내지 않는다.
  - **인구 10만 미만 군**: 원전 5곳 중 울진군(4.6만)·영광군(5.1만) 등 소규모 군은 전국 배율에서 도시 깃발이 없으므로 원전이 오프셋 없이 제자리에 놓인다. 기장군(17.6만)·울주군(21.8만)은 `z < 2.0`에서 `부산`/`울산` 깃발에 밀려 깃발이 비켜 서므로 고리·새울 원전이 모두 보인다.

---

### #2. 시도 이름표의 지도판 각인화(명조·반투명)와 층위 하향

- **화면 위치와 동작**:
  - 데스크톱/모바일 공통: `site/js/render/labels.js`와 `site/js/main.js` `drawScene()`.
  - `labels.draw()` 호출을 `banners.draw()` 뒤에서 **지형·선·경계·선택 테두리 바로 위, `geoLabels`·`layerR.drawIcons`·`banners.draw` 아래**로 내린다.
  - `main.js:184`의 `this.banners.avoid(boxes, this.selCity)` 호출과 `banners.js`의 `avoid()`를 제거해 시도 이름표 때문에 인구 50만 미만 비청사 도시 깃발이 사라지는 현상을 없앤다.
  - 서체를 굵은 고딕(`800`)에서 명조/세리프(`700`, `"Batang","AppleMyungjo","Nanum Myeongjo","Noto Serif KR",serif`), 넓은 자간(`0.22em`), 낮은 불투명도(`0.52~0.66`)의 판화 각인 스타일로 변경한다.
- **실제 데이터 필드 경로**:
  - `states.json`: `states[i].{code, short, label.{x, y, angle, size}}`
  - `cities.json`: `cities[i].{sido, name}` (광역시 동명 시도 이름 생략 판정 — 기존 `StateLabels` 생성자 유지)
- **계산식**:
  - 글자 크기: `raw = s.label.size * cam.scale`; `raw < 14 && s.code !== selected`이면 생략; `px = Math.min(34, raw)`.
  - 자간: `letterSpacing = (px * 0.22).toFixed(1) + 'px'`.
  - 불투명도:
    - 지형 모드: `alpha = clamp(0.66 - (z - 1) * 0.08, 0.22, 0.66)`
    - 렌즈 모드(`!!app.lens`): 어두운 렌즈 색 위 가독성 보정을 위해 `alpha = clamp(0.74 - (z - 1) * 0.08, 0.26, 0.74)`, 외곽선 `lineWidth = Math.max(2, px * 0.14)`, `strokeStyle = rgba(12,14,18, alpha * 0.75)` (지형 모드에서는 `lineWidth = Math.max(1.5, px * 0.10)`, `rgba(18,16,12, alpha * 0.45)` + 옅은 `shadowBlur = 2`).
    - 선택된 시도(`s.code === selected`): 채움 `rgba(255,214,90, 0.92)`.
  - 위치 탐색: 기존 7개 후보 `cands`로 놓인 깃발(`flags`)과의 겹침 면적을 최소화하되, 겹침이 남아도 깃발을 지우지 않는다.
- **"자료 없음" · 부분 합 · 비공개일 때 표시**: 해당 없음(16개 시도 모두 `label` 보유).
- **규칙 문장 (연감 `인구·도시` 또는 `지형 규칙` 탭 초안)**:
  > "시도 이름은 지형·경계 위, 아이콘·도시 깃발 아래에 반투명 명조체로 새긴다. 광역시·특별시·세종처럼 같은 이름의 도시 깃발이 있는 시도는 이름표를 중복 표시하지 않으며, 시도 이름 때문에 도시 깃발을 숨기지 않는다."
- **키보드 · 터치 동작**:
  - `main.js` `click()`/`hover()` 판정 순서는 기존과 동일하게 `깃발 → 아이콘 → 교역로 → 시도 이름표 → 빈 땅(해당 칸의 시도)`를 유지한다.
- **공유 링크 해시 키**: 없음.
- **예상 엣지 케이스**:
  - **광역시와 자치구**: 서울·부산·인천·대구·대전·울산·세종은 같은 이름의 도시 깃발이 있어 이름표가 생략된다(기존 동작 유지).
  - **전남광주통합특별시(`code: '12'`)**: `short`가 `'전남광주'`이고 소속 도시 중 `'전남광주'`라는 이름이 없으므로 이름표가 그려진다. 4글자라 자간 `0.22em`을 그대로 적용하면 폭이 과하게 넓어지므로 **`s.short.length >= 4`일 때 자간을 `0.12em`으로 제한**한다.
  - **인구 10만 미만 군**: `banners.avoid()` 제거로 충북·경북·강원 중앙부에서 시도 이름 근처에 있던 중소 도시 깃발(예: 안동시·충주시·원주시 등)이 부당하게 탈락하지 않는다.

---

### #12. 다섯 산출 5열 1행 스트립 + '기준과 주의' 통합 서랍

- **화면 위치와 동작**:
  - 데스크톱(`#panel` 폭 360px): 도시·시도·전국 패널 `<header>` 바로 아래(도시 패널에서는 4탭 바 바로 위 고정 영역)에 5열 1행(`grid-template-columns: repeat(5, minmax(0, 1fr))`, `gap: 4px`) 산출 스트립 배치.
  - 각 칸 구성(3줄 고정):
    1. `<em>` 아이콘+이름 (`🌾 식량`, `⚙️ 생산`, `💰 금`, `🔬 과학`, `🎭 문화`)
    2. `<b>` 금액 (`fmtWon(v)`) + 부분 합일 때 `<sup class="pm">*</sup>` 및 `.yt.partial` 점선 테두리
    3. `<small>` 도시 패널은 순위(`2위`), 시도·전국 패널은 기준(`공식 '23`)
  - 기존 4번째 줄(`👷 종사자 수`, 구성 산업 규칙 문구, 시도·전국의 `시군구 합`·`잠정치`)은 각 칸의 `data-ytip` 클릭/호버 말풍선(`#fnpop` 재사용)과 `경제` 탭 본문으로 이동한다.
  - 모바일(`<= 700px`): 폭 360px 이상에서는 5열 1행 유지(`font-size: 12px` 압축), 360px 미만에서만 `overflow-x: auto` + `min-width: 64px` 안전장치.
  - `'기준과 주의'` 통합 서랍: `Panel.prototype.footnotes()`를 수정해 구역마다 `<details class="caveats">`를 삽입하는 대신, **도시 패널은 활성 탭 최하단(또는 패널 최하단), 시도·전국 패널은 패널 최하단에 단 1개의 `<details class="caveats">기준과 주의 (N건)</details>`**만 생성한다. 본문 각 값 옆 `ⓘ` 버튼(`data-fn="k"`)의 호버·클릭 `#fnpop` 말풍선 동작은 그대로 유지한다.
- **실제 데이터 필드 경로**:
  - 도시: `cities[i].yields.{food, production, gold, science, culture}`, `cities[i].yields_partial.production`, `cities[i].production_mining_excluded`, `cities[i].ranks.{food, production, gdp, science, culture}`, `cities[i].jobs`, `cities[i].jobs_total`, `cities[i].gdp_undisclosed`
  - 시도·전국: `states[i].official.gdp.{year, yields, latest}`, `states[i].yields`, `nation.nation.official.gdp.{year, yields, latest}`, `nation.nation.yields`
  - 매핑 메타: `nation.econ.{jobs_map, ksic_ko, industry_ko}`
- **계산식**:
  - 도시 산출 `gold`의 순위 키는 `cities[i].ranks.gdp`, 나머지는 `cities[i].ranks[k]` (`food`, `production`, `science`, `culture`).
  - 타일 클릭/호버 시 종사자 보조 합계: `k === 'gold'`이면 `o.jobs_total`, 그 외는 `nation.econ.jobs_map[k].map(L => o.jobs[L])` 중 `null`이 하나라도 있으면 `"비공개 포함"`, 없으면 합계 `명`.
- **"자료 없음" · 부분 합 · 비공개일 때 표시**:
  - `yields[k] == null` → `<b><span class="na">자료 없음</span></b>` + 말풍선에 `gdp_undisclosed` 산업명 나열(현재 167개 도시 중 `yields[k] == null`은 0건이나 데이터 갱신 대비 유지).
  - `yields_partial.production` 존재(18개 도시: 서울·부산·대전·부천·광명·오산·군포·의왕·음성·동두천·과천·속초·담양·남해·증평·구례·화천·울릉) → `.yt.partial` 주황 점선 테두리 + 값 옆 주황 `*` + 클릭 시 `#fnpop`에 `"제조업 + 건설업 (광업 비공개 N곳 제외, 추정해 더하지 않음)"` 즉시 표시.
- **규칙 문장 (연감 `산출` 탭 초안)**:
  > "패널 상단 다섯 산출 칸은 도시의 경우 시군구 합 명목 부가가치와 167개 도시 중 순위를, 시도·전국은 공식 지역소득 값을 5열 한 줄로 요약한다. 점선 테두리와 * 표시는 광업 비공개 몫을 뺀 부분 합계이며, 각 칸을 누르면 구성 산업과 사업장 기준 종사자 수를 확인할 수 있다."
- **키보드 · 터치 동작**:
  - 각 산출 타일을 `<button type="button" class="yt">`로 구현해 `Tab`/`Enter`/`Space` 또는 터치 탭 시 `#fnpop` 상세 말풍선(구성 산업·부분합 사유·종사자 수·시군구 합 대조) 토글, `Esc` 또는 바깥 탭으로 닫기.
- **공유 링크 해시 키**: 없음.
- **예상 엣지 케이스**:
  - **광역시와 자치구**: 서울(`production_mining_excluded: 14`), 부산(`7`), 대전(`2`)은 생산 칸에 `*`와 점선 테두리가 붙는다.
  - **전남광주통합특별시**: 시도 패널(`states[1]`)에서 `official.gdp.combined`가 있으므로 타일 말풍선에 `"광주 + 전남 공식값 합"`을 표기한다.
  - **인구 10만 미만 군**: `울릉군(166)` 등 금액이 `억` 단위(`505억`, `2,665억`)인 도시는 `fmtWon(v)`가 4~5글자라 62px 칸에 들어가도록 `font-size: clamp(11.5px, 3.2vw, 13.5px)` + `tabular-nums`를 적용한다.

---

### #10. 핵심 지표 '전국 기준 대비(▲/▼)' 및 '전국 순위 미니 게이지' 인라인 병기

- **화면 위치와 동작**:
  - 데스크톱/모바일 공통: 도시 패널(`showCity`) `개요`·`경제` 탭의 `.kv` 지표 카드와 `순위` 구역.
  - **전국 기준 대비 1줄(`.ref`)**: 각 `.kv > div` 카드 하단에 `▲ 전국 +3.2%p` 또는 `▼ 전국 4,700만원` 형태의 보조 줄 1줄을 추가한다.
  - **전국 순위 미니 게이지**: 기존 4열 텍스트 박스 `.ranks`를 **1열 9행 콤팩트 게이지 리스트**로 개편한다. 각 행은 `지표명 | 0~100% 가로 트랙 + 점(dot) | N위/167`으로 구성하고, 행을 클릭/탭하면 아래에 **`바로 위(rank-1)` · `바로 아래(rank+1)` 도시 점프 칩**이 아코디언처럼 1줄 펼쳐진다(3장 탐색 흐름 A).
- **실제 데이터 필드 경로**:
  - 도시 값: `cities[i].growth_5y`, `cities[i].age.{over65, under15, working, mean_est, median_est}`, `cities[i].sex_ratio_20_39`, `cities[i].extinction_index`, `cities[i].gdp_per_capita`, `cities[i].gdp_year`, `cities[i].wage.per_filer`, `cities[i].housing.{sale_per_m2, sale_median, jeonse_median}`, `cities[i].employment.rate`, `cities[i].fiscal_independence`, `cities[i].degree.share_15`, `cities[i].ranks.{population, growth, over65, extinction, gdp, gdp_per_capita, wage, housing, export}`
  - 전국 비교 기준:
    - 직접 대조(동일 조사·산식): `nation.nation.growth_5y`, `nation.nation.age.{over65, under15, working, mean_est, median_est}`, `nation.nation.sex_ratio_20_39`, `nation.nation.extinction_index`, `nation.nation.gdp_per_capita`, `nation.nation.wage.per_filer`, `nation.nation.housing.{sale_per_m2, sale_median, jeonse_median}`, `nation.nation.degree.share_15`
    - 도시 중앙값 대조(전국 공식값과 조사가 다르거나 시도 본청 포함): `cities` 배열에서 `employment.rate != null`인 159곳의 중앙값(현재 66.5%), `fiscal_independence != null`인 158곳의 중앙값(현재 13.3%)을 런타임 계산
  - 색상 방향성 기준: `lenses.lenses`의 `higher_is` (`good` / `bad` / `neutral`)
- **계산식**:
  - 비율(`%`)·지수 지표: 차이 `diff = cityVal - refVal`. `|diff| < 0.05`(소멸지수는 `< 0.005`)이면 `= 전국 수준`.
  - 금액·단가 지표(`gdp_per_capita`, `wage.per_filer`, `housing.*`): 비율 `ratio = (cityVal / refVal - 1) * 100` → `▲ 전국 대비 +24% (전국 4,700만)`.
  - 색상 매핑:
    - `higher_is === 'good'` (`extinction_index`, `gdp_per_capita`, `wage`, `employment`, `fiscal`, `degree`): `diff > 0` 초록(`.up`), `diff < 0` 주황(`.down`).
    - `higher_is === 'neutral'` (`growth_5y`, `over65`, `under15`, `working`, `mean_est`, `median_est`, `sex_ratio_20_39`, `housing.*`): 가치 판단 색 없이 중립(`.neu`, `#c8beaa`).
  - 순위 게이지 위치: 유효 도시 수 `N = cities.filter(x => x.ranks && x.ranks[k] != null).length`.
    - `pctPos = N > 1 ? ((N - rank) / (N - 1)) * 100 : 50` (우측 100% = 1위, 좌측 0% = N위).
    - `extinction`은 1위가 가장 위험하므로 점 색을 `#d4553a`로 표시하고 우측 끝에 `위험` 라벨을 병기한다.
- **"자료 없음" · 부분 합 · 비공개일 때 표시**:
  - 도시 값이 `null`이면 대비 줄을 생략한다(예: `옹진군` 아파트 매매가, `포천시`·`여주시` 수출 순위 → 게이지 트랙 대신 `자료 없음 · 순위 제외`).
  - 광역시 `member_ranges`처럼 범위(`min–max%`)만 있는 항목은 단일 대비 화살표를 그리지 않는다(평균 추정 금지).
  - `세종(gdp_year: 2024)`의 `1인당 GRDP` 대비 줄에는 `전국 '23 대비`로 연도 차이를 명시한다.
- **규칙 문장 (연감 `인구·도시` 또는 `산출` 탭 초안)**:
  > "도시 패널의 전국 대비 표시는 같은 조사·같은 산식의 전국값(`nation.json`)과 비교한다. 고용률(시군구 지역별고용조사 반기)과 재정자립도(기초 시·군 기준)는 전국 공식값과 조사·범위가 달라, 값이 있는 도시의 중앙값과 비교하고 기준을 함께 적는다. 순위 막대의 분모는 값이 있는 도시 수(수출 165곳, 아파트 166곳, 그 외 167곳)다."
- **키보드 · 터치 동작**:
  - 순위 게이지 각 행은 `<button aria-expanded="false">`로 동작. `Enter`/`Space`/탭 시 인접 순위 도시 칩 펼침, 칩 클릭 시 `app.selectCity(id, true)`.
- **공유 링크 해시 키**: 없음.
- **예상 엣지 케이스**:
  - **광역시와 자치구**: 서울·부산·인천·대구·대전·광주·울산 7곳은 `employment.rate === null`, `fiscal_independence === null`이므로 대비 줄을 생략하고 기존 `member_ranges` 범위와(`서울`·`대전`·`광주`·`세종`만) `official_sido`를 그대로 보여 준다.
  - **전남광주통합특별시**: 시도 패널이 아닌 도시 패널 기준이므로 `광주(5)`는 광역시 규칙, `무안군(80)` 등 22개 시·군은 단일값 규칙을 따른다.
  - **인구 10만 미만 군**: `울릉군(166)`은 아파트 매매 거래가 `3건`(`housing.trades < 10`)인데 매매가가 전국 대비 낮거나 높게 튈 수 있다. `housing.trades < 10`이면 대비 줄 옆에 `(거래 N건)` 표기를 붙여 소표본 왜곡을 알린다.

---

### #11. 산업 특화도(입지계수 LQ) 계산과 객관적 '도시 특성 태그'

> 검토 의견 반영: 조건부 채택 요건인 **계산 규칙·임계값·비공개 산업·"자료 없음" 처리**를 아래에 완전 명세한다. 핵심 발견: `nation.nation.gdp_by_industry`는 `mining`·`utilities`가 `null`이고 `nation.nation.jobs`는 `A`·`B`가 `null`이므로, **전국 비중 분모는 반드시 공식 전국값(`nation.nation.official.gdp.by`와 `nation.nation.official.jobs`)**을 써야 한다.

- **화면 위치와 동작**:
  - **산업 막대 병기**: `경제` 탭의 `industryBars`(GRDP 16개 산업, `net_taxes` 제외)와 `jobBars`(KSIC 19개 대분류) 각 행의 금액·비중 우측에 입지계수 칩(`×2.6`)을 표시한다.
  - **도시 헤더 특성 태그**: 도시 패널 `<header>`의 행정 배지(`.badges`) 아래에 최대 **3개**의 객관적 태그(`.tags`)를 1줄 wrap으로 배치한다. 각 태그는 버튼이며 클릭/호버 시 `#fnpop`으로 산식과 실제 분자·분모 수치를 보여 준다.
  - 데스크톱/모바일 공통: 모바일에서는 2줄 이상 늘어나지 않게 `gap: 4px`, `font-size: 10.5px`로 압축한다.
- **실제 데이터 필드 경로**:
  - 부가가치 LQ:
    - 분자(도시): `cities[i].gdp_by_industry[k]` ÷ `cities[i].gdp_by_industry.grdp` (`k ∈ nation.econ.industry_keys` 16개)
    - 분모(전국 공식): `nation.nation.official.gdp.by[k]` ÷ `nation.nation.official.gdp.by.grdp`
    - 비공개 목록: `cities[i].gdp_undisclosed`, 한글명: `nation.econ.industry_ko[k]`
  - 종사자 LQ:
    - 분자(도시): `cities[i].jobs[L]` ÷ `cities[i].jobs_total` (`L ∈ Object.keys(nation.econ.ksic_ko)` 19개)
    - 분모(전국 공식): `nation.nation.official.jobs.by[L]` ÷ `nation.nation.official.jobs.total`
  - 특성 태그 보조 필드: `cities[i].ranks.{gdp_per_capita, export, wage}`, `cities[i].extinction_index`, `cities[i].growth_5y`, `cities[i].gdp_year`, `nation.nation.official.gdp.year`
- **계산식**:
  - 부가가치 입지계수:
    $$\text{LQ}_{c,k} = \frac{\text{gdp\_by\_industry}[k] / \text{gdp\_by\_industry.grdp}}{\text{official.gdp.by}[k] / \text{official.gdp.by.grdp}}$$
  - 종사자 입지계수:
    $$\text{LQ}^{\text{job}}_{c,L} = \frac{\text{jobs}[L] / \text{jobs\_total}}{\text{official.jobs.by}[L] / \text{official.jobs.total}}$$
  - **막대 표시 임계값**:
    - 도시 내 비중 `>= 1.0%`이고 분자·분모 모두 `> 0`인 업종에만 `×{LQ.toFixed(1)}` 표시(`LQ >= 10`이면 소수점 없이 `×{Math.round(LQ)}`).
    - `도시 내 비중 >= 5.0% && LQ >= 1.5`이면 금색 강조(`.lq.hi`).
  - **헤더 특성 태그 선정 규칙 (최대 3슬롯, 주관적 수식어 금지)**:
    1. **슬롯 1 — 특화 산업 (0~1개)**: 16개 부가가치 산업 중 `비공개 제외` ∧ `도시 내 비중 >= 5.0%` ∧ `LQ >= 1.5`를 만족하는 업종 중 `LQ` 최댓값 1개 → `{산업명} 특화 ×{v}` (실측 결과 167개 도시 중 166곳 해당, `익산시` 1곳만 미해당 → 생략).
    2. **슬롯 2 — 경제·교역 상위 (0~1개, 우선순위 순 첫 일치 1개)**:
       - `ranks.gdp_per_capita <= 10` → `1인당 GRDP 상위 10`
       - else `ranks.export != null && ranks.export <= 10` → `수출 상위 10`
       - else `ranks.wage <= 10` → `총급여 상위 10`
    3. **슬롯 3 — 인구 추세 (0~1개, 우선순위 순 첫 일치 1개)**:
       - `extinction_index != null && extinction_index < 0.2` → `소멸 고위험`
       - else `growth_5y != null && growth_5y >= 10.0` → `5년 인구 +10%↑`
- **"자료 없음" · 부분 합 · 비공개일 때 표시**:
  - `gdp_by_industry[k] == null`(현재 25개 도시, `mining` 18·`utilities` 10) 또는 `jobs[L] == null`(현재 47개 도시): 해당 행의 LQ 칸은 비우거나 `–`로 두고 기존 `비공개` 표기를 유지한다. **비공개 산업은 절대 0으로 두지 않으며 특성 태그 후보에서 제외한다.**
  - `cities[i].gdp_by_industry == null` 또는 `grdp == null`: LQ와 산업 태그를 모두 생략한다("자료 없음").
  - 조건을 충족하는 특화 산업이 없는 도시(`익산시` 등): 산업 태그를 강제로 만들지 않고 슬롯 1을 비운다.
  - `cities[i].gdp_year !== nation.nation.official.gdp.year` (`세종` 2024 vs 전국 2023): 산업 태그 말풍선에 `"세종은 2024년, 전국 분모는 2023년 공식 GRDP 기준"` 경고를 자동 포함한다.
- **규칙 문장 (연감 `산출` 탭 초안)**:
  > "입지계수(LQ)는 도시의 업종별 비중을 전국 공식 비중(부가가치는 지역소득 공식 전국값, 종사자는 전국사업체조사 공식 전국값)으로 나눈 값이다. 1.0이면 전국 평균과 같고, 1.5 이상이면서 도시 내 비중이 5% 이상인 업종을 특화 산업으로 강조한다. 비공개 업종은 계산과 태그 선정에서 제외하며 0으로 추정하지 않는다. 인구가 적은 군에서는 발전소·광산 등 단일 시설 비중이 커 배수가 높게 나올 수 있다."
- **키보드 · 터치 동작**:
  - 각 특성 태그는 `<button type="button" class="ctag">`로 구현, 포커스·호버·탭 시 `#fnpop`에 산식과 실제 수치(예: `화성시 제조업 66.6% ÷ 전국 25.4% = ×2.6`) 표시.
- **공유 링크 해시 키**: 없음.
- **예상 엣지 케이스**:
  - **광역시와 자치구**: 서울(`mining` 비공개), 부산(`mining` 비공개), 대전(`mining` 비공개)은 광업 LQ만 비우고 나머지 15개 산업은 정상 산출(예: 서울 `정보통신업 특화 ×2.3`, 부산 `운수·창고업 특화 ×2.4`).
  - **전남광주통합특별시**: `무안군(80)`은 도청 소재 효과로 `공공행정·국방 특화 ×6.0`(38.9%), `광주(5)`는 `보건·사회복지 특화 ×1.8`(9.8%)로 객관적으로 구분된다.
  - **인구 10만 미만 군**: `울진군(4.6만)`은 원전 때문에 `전기·가스·증기 ×33`(39.5%), `영월군(3.6만)`은 `광업 ×59`(5.7%)처럼 배수가 매우 크게 나온다. `population < 50000 && lq >= 10`일 때 말풍선에 `"소규모 지역에서는 단일 시설·광산 비중으로 배수가 높게 나올 수 있다"` 주석을 자동 붙이고, `익산시`처럼 전 업종이 `비중 >= 5% ∧ LQ >= 1.5` 미만이면 태그를 비워 정직성을 지킨다.

---

### #9. 도시 패널 4탭 구조화(개요 · 경제 · 시설·교역 · 땅·행정)와 탭 기억

- **화면 위치와 동작**:
  - 데스크톱/모바일 공통: 도시 패널(`showCity`)에만 우선 적용한다(시도·전국 패널은 기존 흐름 유지).
  - 패널 상단 고정 블록(`.phead-sticky`): `<header>`(배지·도시명·시도 링크·특성 태그 #11·`비교` 버튼 #14) + 핵심 인구 1줄(`population`, `growth_5y`) + 5열 산출 스트립(#12) + **4탭 바(`role="tablist"`)**.
  - 4개 탭 구성:
    1. **`개요` (`overview`)**: 인구 시계열 SVG, 5세 피라미드 SVG, 연령·청년성비·소멸위험지수(#10 대비 포함), 순위 9칸 게이지(#10), 닮은 도시 5곳(#13).
    2. **`경제` (`econ`)**: 부가가치/종사자 전환 막대(#11 LQ 포함), 경제 `.kv.econ` 14칸(#10 대비 포함), 주력 업종(`keyIndBlock`).
    3. **`시설·교역` (`infra`)**: 탭 라벨에 보유 층 항목 수 표시(예: `시설·교역 14`, 층 로딩 전엔 숫자 생략). 수출입·HS 상위 품목(`tradeBlock`), 지도 층 목록(`layerBlock`), 일반산단(`gicLine`), 발전설비(`powerBlock`), 식량(`farmBlock`), 가행 광산(`minesBlock`).
    4. **`땅·행정` (`land`)**: 국가토지피복통계 + 칸 피복(`terrainBlock`), 건강·렌즈 막대에서 뺀 지표(`retiredBlock`), 보훈대상자(`veteransBlock`), 청사(`officeBlock`), 하단 시군구/칸/깃발 위치 `.foot`.
  - **탭 기억**: `app.panelTab` (기본 `'overview'`)에 현재 탭을 저장해, 도시 A의 `경제` 탭을 보다가 지도에서 도시 B 깃발을 누르면 도시 B도 곧바로 `경제` 탭으로 열린다.
  - 모바일(`<= 700px`): 고정 상단 블록의 높이를 최소화하기 위해 모바일에서는 `<header>`와 탭 바만 sticky로 두고 5열 산출 스트립은 스크롤과 함께 올라가게 해 본문 가시 영역을 확보한다.
- **실제 데이터 필드 경로**:
  - `overview`: `cities[i].{population, pop_series, growth_5y, age, sex_ratio_20_39, extinction_index, extinction_stage, pyramid, ranks, peers, peer_rule}`
  - `econ`: `cities[i].{gdp, gdp_year, gdp_by_industry, gdp_undisclosed, gdp_per_capita, gdp_growth, wage, housing, employment, fiscal_independence, fiscal_year, member_ranges, official_sido, workers, jobs, jobs_total, jobs_year, jobs_year_label, farm, degree}`, `resources.key_industries.by_city[id]`
  - `infra`: `cities[i].trade`, `trade.units`, `trade.hs_names`, `wonders.items`, `resources.items`, `infrastructure.items`, `resources.{general_complexes, power, farm, mines_5d}.by_city[id]`
  - `land`: `cities[i].{land_stats, footprint, veterans, sido_offices, offices, sgg, center_rule}`, `lenses.retired_values.items`, `lenses.lenses` (`id === 'health'`)
- **계산식**:
  - `시설·교역` 탭 배지 건수: `layerR ? layerR.itemsFor(new Set(c.sgg), new Set(c.footprint)).length : null`.
- **"자료 없음" · 부분 합 · 비공개일 때 표시**:
  - `layers` 비동기 로딩 완료 전 `시설·교역` 탭이 열리면 기존 `"지도 층을 불러오는 중…"`을 보여 주고 `setLayers()` 완료 시 활성 탭을 유지한 채 재렌더한다.
  - 각 탭에서 생성된 `.note`는 패널 최하단 단일 `기준과 주의` 서랍(#12)에 해당 탭의 주석만 집계한다(숨은 탭의 주석 번호가 섞이지 않게 활성 탭 기준으로 번호 1..K 부여).
- **규칙 문장 (연감 초안)**: 별도 통계 규칙 없음(도움말 `?`의 `패널` 항목에 4탭 구성 1줄 추가).
- **키보드 · 터치 동작**:
  - `role="tablist"` / `role="tab"` / `role="tabpanel"`. 탭 바 포커스 시 `←`/`→` 탭 이동, `Home`/`End` 첫/끝 탭 이동, `Enter`/`Space` 활성화.
  - 모바일 가로 폭 부족 시 탭 바 `font-size: 11.5px`, 4개 균등 분할(`grid-template-columns: repeat(4, 1fr)`).
- **공유 링크 해시 키**:
  - `tab=econ|infra|land` (기본 `overview`일 때는 해시에서 생략. `city=`가 함께 있을 때만 유효하며, 알 수 없는 값이면 `overview`로 폴백. 신여지도가 탭 구조가 달라도 `tab` 키를 무시하면 안전하게 호환됨).
- **예상 엣지 케이스**:
  - **광역시와 자치구**: 서울(25개 구)의 `tradeBlock`은 구별 `<details class="hsu">` 25개가 있어 매우 길지만 `시설·교역` 탭으로 분리되므로 `개요`·`경제` 탐색을 방해하지 않는다.
  - **전남광주통합특별시**: `광주(5)`·`무안군(80)`의 통합청사 3곳 안내(`officeBlock`)는 `땅·행정` 탭에 들어가되, 헤더 배지 `◇ 통합특별시 청사`는 모든 탭에서 상시 보인다.
  - **인구 10만 미만 군**: `포천시`·`여주시`(`trade: null`), `군위군`(`veterans.count: null`), `옹진군`(`housing.sale_per_m2: null`)처럼 빈 섹션이 있는 도시에서도 탭 자체는 비활성화하지 않고 해당 구역에 `"자료 없음"` 사유를 정직하게 표시한다.

---

### #13. '닮은 도시' 유사 근거 1줄 요약과 원클릭 비교 연결

- **화면 위치와 동작**:
  - 데스크톱/모바일 공통: 도시 패널 `개요` 탭의 `닮은 도시` 목록(`.peers`, 5행).
  - 각 행을 좌측 본체(`data-city`, 클릭 시 해당 도시로 이동)와 우측 끝 `비교` 아이콘 버튼(`data-cmp`, 폭 44px, 클릭 시 현재 도시 vs 그 도시 비교 모드 #14 즉시 진입)의 2분할 구조로 바꾼다.
  - 좌측 본체 2번째 줄에 `cities[i].peer_rule`("인구·고령 비율·1인당 GRDP·산업 구성") 4개 축에서 **가장 비슷한 2개 근거**와, 보유 주요 지표(1인당 총급여·아파트 매매가·5년 증감) 중 **가장 큰 차이 1개**를 1줄로 요약한다(예: `인구·제조 비중 비슷 · 아파트 ㎡당 1.6배 차이`).
- **실제 데이터 필드 경로**:
  - `cities[i].peers` (길이 5, 대상 `id` 배열), `cities[i].peer_rule`
  - 유사도 분해용 필드: `cities[i].population`, `cities[i].age.over65`, `cities[i].gdp_per_capita`, `cities[i].gdp_by_industry` (`nation.econ.industry_keys` 16개 비중)
  - 차이 1줄용 필드: `cities[i].wage.per_filer`, `cities[i].housing.sale_per_m2`, `cities[i].growth_5y`, `cities[i].extinction_index`
- **계산식**:
  - 두 도시 `a`, `b`의 4개 축 표준화 거리(전 도시 표준편차 `σ` 기준):
    - `d_pop = |log10(a.population) - log10(b.population)| / σ_logpop`
    - `d_age = |a.age.over65 - b.age.over65| / σ_over65`
    - `d_gdp = |log10(a.gdp_per_capita) - log10(b.gdp_per_capita)| / σ_loggdp` (둘 다 `> 0`일 때)
    - `d_ind = L2_dist(share_16(a), share_16(b)) / σ_ind` (둘 다 공개된 산업만 비교; 최대 공통 주력 산업명 추출)
  - 4개 축 중 `d`가 가장 작은 2개 축을 라벨로 조합(예: `인구 비슷 · 제조 비중 55% vs 67%`).
  - 차이 1개 후보(`d_diff` 최댓값, 단 임계치 초과 시에만 노출 — 억지 차이 생성 금지):
    - 아파트 ㎡당 매매가 비율 `max(a/b, b/a) >= 1.35` (둘 다 `trades >= 10`일 때) → `매매가 {r.toFixed(1)}배 차`
    - else 5년 인구 증감 차 `|a.growth_5y - b.growth_5y| >= 5.0` → `5년 증감 {a>b?'+':''}{(a-b).toFixed(1)}%p 차`
    - else 1인당 총급여 비율 `max(a/b, b/a) >= 1.15` → `총급여 {r.toFixed(1)}배 차`
- **"자료 없음" · 부분 합 · 비공개일 때 표시**:
  - 한쪽의 `gdp_by_industry[k]`가 비공개면 `d_ind` 계산에서 그 업종을 제외한다.
  - 한쪽의 `housing.sale_per_m2 == null`이거나 `trades < 10`(예: 울릉군·신안군·영양군·옹진군)이면 매매가 차이를 후보에서 제외한다.
  - 세종(2024)과 타 도시(2023) 비교 시 `1인당 GRDP` 유사 축 라벨에 `('24/'23)` 소표기를 붙인다.
- **규칙 문장 (연감 `산출` 탭 기존 닮은 도시 문장 보강 초안)**:
  > "닮은 도시는 인구(로그)·고령 비율·1인당 GRDP(로그)·산업 16분류 비중의 표준화 거리로 5곳을 고른다. 카드 아래 요약은 이 네 축 중 차이가 가장 작은 두 항목과, 총급여·아파트 매매가(거래 10건 이상)·5년 인구 증감 중 차이가 뚜렷한 한 항목을 보여 준다."
- **키보드 · 터치 동작**:
  - 중첩 버튼 금지: `.peer-row` flex 컨테이너 안에 `<button class="peer-go" data-city="...">` + `<button class="peer-cmp" data-cmp="..." aria-label="{도시명}과 비교">` 2개의 형제 버튼으로 분리(모바일 터치 최소 영역 `44×44px`).
- **공유 링크 해시 키**: 없음(`비교` 버튼 클릭 시 #14의 `#cmp=a,b`로 전환).
- **예상 엣지 케이스**:
  - **광역시와 자치구**: 서울의 닮은 도시(`[대전, 부산, 안양시, 수원시, 광주]`)는 인구 규모 차가 크므로 주로 `고령 비율`·`산업 구성`이 유사 근거로 뜨고, `매매가`가 결정적 차이로 자동 포착된다.
  - **전남광주통합특별시**: `무안군(80)`의 닮은 도시(`[홍성군, 안동시, 계룡시, 세종, 나주시]`)는 모두 행정·도청 특화 도시여서 `공공행정 비중 비슷`이 자연스럽게 드러난다.
  - **인구 10만 미만 군**: `울릉군(166)`은 `trades: 3`이므로 매매가 배수 차이가 자동 제외되어 소표본 오해를 막는다.

---

### #14. '도시 대 도시(A vs B)' 나란히 비교 모드 & 지도 연결 아크

- **화면 위치와 동작**:
  - **진입 경로 3곳**: ① 도시 패널 헤더의 `비교` 버튼 → 상단 안내 띠 `"비교할 도시를 지도에서 누르거나 / 검색으로 고르세요 (Esc 취소)"` 활성화 → 깃발 또는 검색으로 B 선택, ② 닮은 도시(#13) 행 우측 `비교` 버튼 즉시 진입, ③ URL 해시 `#cmp=a,b` 직접 진입.
  - **데스크톱**: `#panel.compare` 폭을 `360px → 460px`로 넓히고(`body.compare-open` 시 `#minimap` `right: 480px`, `#lensbar` `left: calc((100vw - 480px) / 2)`), 상단에 `A(금색) vs B(하늘색)` 고정 헤더 + `⇄ 바꾸기` + `B 변경` + `단일 보기` 버튼을 둔다.
  - **모바일(`<= 700px`)**: 기존 바텀시트 폭 100% 안에서 2열 대조표(지표명 중앙 1줄, 좌측 A 막대·값 / 우측 B 막대·값).
  - **지도 위 표시**: `drawOverlay()`에서 도시 A 영토 외곽선은 금색(`#ffd34d`), 도시 B 영토 외곽선은 하늘색(`#63c7ff`)으로 그리고, `(A.x, A.y)`와 `(B.x, B.y)`를 잇는 금색 점선 이차 베지어 아크(제어점 = 중점에서 수직으로 선 길이의 15%)를 그린다. 진입 시 두 도시 영토가 모두 보이도록 `flyTo` 자동 맞춤.
- **실제 데이터 필드 경로**:
  - 도시 A, B 공통: `cities[id].{id, name, sido, kind, capital, x, y, footprint, sgg, population, growth_5y, age.{over65, under15, working, mean_est}, extinction_index, extinction_stage, pyramid.{male, female}, yields.{food, production, gold, science, culture}, yields_partial.production, production_mining_excluded, gdp, gdp_year, gdp_per_capita, gdp_growth.rate, gdp_by_industry, gdp_undisclosed, wage.per_filer, housing.{sale_per_m2, sale_median, jeonse_median, trades, jeonse_trades}, employment.rate, fiscal_independence, member_ranges.{employment, fiscal}, degree.share_15, trade.{export, import, balance}, veterans.per_1000, ranks}`
  - 층·발전 보조: `layerR.itemsFor(sggSet, cellSet)`, `resources.power.by_city[id]`
- **계산식**:
  - **인구 피라미드 겹치기(정규화 필수)**: 원시 명수로 겹치면 대도시와 군을 비교할 수 없다. 각 5세 계급 `k (0..20)`을 도시 총인구 대비 비중 `mPct[k] = pyramid.male[k] / population * 100`, `fPct[k] = pyramid.female[k] / population * 100`으로 변환하고, 두 도시 합집합 최대 비중 `mx`를 공통 척도로 삼아 A는 반투명 채움, B는 굵은 윤곽선으로 겹쳐 그린다(툴팁에는 `%`와 실제 `명` 동시 표기).
  - **양방향 가로 막대**: 두 값이 모두 유효하고 `>= 0`이면 `max(vA, vB)`를 100%로 각 막대 폭 계산; `growth_5y`·`balance`처럼 부호가 다른 지표는 막대 대신 부호 포함 수치와 차이(`%p` / 달러)만 표기.
  - **우세 표시**: `lenses.json`의 `higher_is`가 `'good'`/`'bad'`인 지표만 우세한 쪽 값에 미세 강조, `'neutral'`(인구·고령 비율·매매가 등)은 중립 표기.
- **"자료 없음" · 부분 합 · 비공개일 때 표시**:
  - 한쪽이 `null`이면 그쪽 칸은 `자료 없음` + 막대 폭 `0`, 차이(Δ) 칸은 `–`.
  - `A.gdp_year !== B.gdp_year` (세종 2024 vs 타 도시 2023): 경제 구역 맨 위에 주황 경고 배지 `"GRDP 기준 연도 다름 (세종 2024 · 상대 2023) — 차이 미계산"`을 띄우고 GRDP·산출의 Δ 계산을 숨긴다.
  - 한쪽만 `yields_partial.production`이 있으면 해당 값에 `*` + 점선 테두리 + `"광업 비공개 N곳 제외 부분 합"` 주석을 표시하고 생산 Δ 옆에 `*`를 붙인다.
  - 광역시 `member_ranges` vs 시군 단일값: 광역시 칸은 `자치구 min–max%` 텍스트만 두고 막대와 Δ는 비운다(`비교 불가: 자치구 범위`).
- **규칙 문장 (연감 `인구·도시` 탭 초안)**:
  > "도시 비교는 두 도시의 인구 피라미드를 각 도시 총인구 대비 5세 계급 비중(%)으로 정규화해 겹쳐 그린다. GRDP 기준 연도가 다르거나(세종 2024, 그 외 2023) 한쪽이 자치구 범위·자료 없음인 지표는 차이를 계산하지 않고 각 값과 기준을 나란히 적는다."
- **키보드 · 터치 동작**:
  - 비교 대기 상태에서 `Esc`를 누르면 비교 대기만 취소(원래 도시 A 패널 유지). 비교 패널이 열린 상태에서 `Esc`는 비교를 닫고 일반 상태로 복귀(또는 `단일 보기` 버튼으로 A 패널 복귀).
  - 비교 대기 중 검색(`/`)을 열면 도시 선택 시 `selectCity` 대신 `setCompare(selCity, chosenId)`로 분기한다.
- **공유 링크 해시 키**:
  - `cmp=<a>,<b>` (예: `#v=...&cmp=9,12`). `city`/`state`/`item`/`route`와 상호 배타적.
  - 파싱 안전 규칙: `a`·`b` 모두 유효한 `cityById` 정수이고 `a !== b`일 때만 비교 모드 진입. 하나만 유효하거나 `a === b`이면 해당 단일 도시 패널로 폴백하고 토스트 안내. 신여지도에서도 `cities[i].id`가 동일하므로 그대로 해석 가능.
- **예상 엣지 케이스**:
  - **광역시와 자치구**: `서울(0) vs 부산(1)`은 둘 다 `member_ranges`이므로 고용률·재정자립도를 범위 나란히 병기(막대 없음). `부산(1) vs 기장군(57)`은 같은 시도(`26`)지만 도시가 다르므로 정상 비교되며 `부산` 쪽만 범위 표기.
  - **전남광주통합특별시**: `광주(5) vs 무안군(80)` 비교 시 둘 다 `◇ 통합특별시 청사` 배지 유지, 아크가 전남광주 내부를 연결한다.
  - **인구 10만 미만 군**: `서울(928만) vs 울릉군(8,724명)` 비교 시 총량 막대는 울릉군이 0.1%이지만 최소 폭 `2px`을 보장하고, 피라미드는 비중 정규화로 두 지역의 연령 구조 차이가 선명하게 대비된다. `옹진군` 매매가 `null`, `포천시`/`여주시` 수출 `null`, `군위군` 보훈 `null`은 모두 `자료 없음`으로 처리.

---

### #18. 렌즈 '직전 대비 토글(`B`)'과 '지형 엿보기(`Space` 홀드)'

- **화면 위치와 동작**:
  - **직전 대비 토글**: `App`에 `prevLensId`(직전에 켜져 있던 렌즈 ID, 지형은 `null`)를 보관한다. `B` 키 또는 범례(`#legend`) 제목 우측 작은 `⇄` 버튼(직전 렌즈가 있을 때만 표시, 툴팁: `"직전 렌즈 '{이름}'과 맞바꾸기 (B)"`)을 누르면 현재 렌즈와 직전 렌즈를 즉시 맞바꾼다.
  - **지형 엿보기**: 렌즈가 켜진 상태에서 `Space` 키를 누르고 있는 동안(또는 모바일·마우스용 범례 제목 옆 `👁` 버튼을 누르고 있는 동안) 지도 지형 타일만 임시로 지형 모드(`terrain.peekTerrain(true)` — 렌즈 오버레이 생략, 기존 지형 타일 캐시 별도 1슬롯 유지)로 전환하고, 손을 떼면 즉시 원래 렌즈로 복귀한다.
  - **연관 렌즈 1줄 제안(3장 탐색 흐름 C 연계)**: 렌즈가 켜진 상태의 범례 하단(출처 위)에 현재 렌즈와 교차 해석 가치가 높은 짝 렌즈 1~2개 칩을 조용히 노출한다(예: `gdp_pc` 켜짐 → `함께 보기: 1인당 총급여 · 제조업 비중`; `over65` → `의사 수 · 소멸위험지수`; `home` → `아파트 전세가 · 합계출산율`). 칩을 누르면 해당 렌즈로 전환되고 직전 렌즈가 `prevLensId`에 저장되어 `B`로 왕복 비교할 수 있다.
  - 모바일(`<= 700px`): 키보드가 없으므로 범례가 펼쳐졌을 때 제목 줄 우측의 `⇄`·`👁` 두 미니 버튼(36×36px)으로 동일 기능을 조작한다.
- **실제 데이터 필드 경로**:
  - `lenses.json`: `lenses.lenses[k].{id, name, emoji}` (짝 렌즈 매핑 테이블은 `lenses.lenses`에 실제 존재하는 33개 ID로만 구성하고, 초기화 시 `app.lensById.has(id)`로 필터링).
- **계산식**:
  - `setLens(id)` 호출 시 새 `id`가 현재 `curId`와 다르면 `this.prevLensId = curId`.
  - `peekTerrain(on)`: `terrain.js`에서 `peekCache`를 따로 보존해 `Space` 누름/뗌 시 타일 재렌더 지연을 없앤다(단 `lens` 자체와 URL 해시는 바꾸지 않음!).
- **"자료 없음" · 부분 합 · 비공개일 때 표시**: 해당 없음(지형 엿보기 중에도 기존 툴팁·범례는 유지).
- **규칙 문장 (연감 `렌즈 정의` 탭 또는 도움말 `?` 초안)**:
  > "B 키(또는 범례의 ⇄ 단추)로 방금 보던 렌즈와 지금 렌즈를 번갈아 대조할 수 있다. 렌즈를 켠 채 Space 키(또는 👁 단추)를 누르고 있으면 잠시 지형이 드러나 산맥·강·평야와 통계 분포를 겹쳐 읽을 수 있다."
- **키보드 · 터치 동작**:
  - `keydown` 가드: 기존 `input, textarea, select, [contenteditable]` 외에 **`button, a, summary` 포커스 상태에서도 `Space` 가로채기 금지**(버튼 클릭·스크롤 오동작 방지). `e.repeat` 무시, `keyup` 및 `window.blur` 시 반드시 지형 엿보기 해제.
  - 터치: `👁` 버튼은 `pointerdown`에 켜고 `pointerup`/`pointercancel`/`pointerleave`에 해제(터치 홀드).
- **공유 링크 해시 키**: 없음(`peek`과 `prevLensId`는 세션 휘발 상태).
- **예상 엣지 케이스**:
  - **광역시와 자치구 / 전남광주통합특별시 / 인구 10만 미만 군**: 시군구 단위 렌즈(`by_county`)와 읍면동/칸 단위 렌즈(`values`/`land_values`) 사이를 `B`로 맞바꿀 때, 기존 범례 필터(`terrain.setFilter(null)`)가 깔끔히 초기화되고 툴팁이 새 렌즈 값으로 갱신돼야 한다.
  - 창 전환(`Alt+Tab`) 중 `Space` 키의 `keyup`을 놓쳐 지형 엿보기가 고정되는 버그를 막기 위해 `window.addEventListener('blur', ...)` 해제를 필수 구현한다.

---

### #20. '추천 시점(관전 포인트)' 프리셋 6선

- **화면 위치와 동작**:
  - 첫 화면 지도를 가리는 웰컴 모달이나 상단 고정 배너를 두지 않는다.
  - **노출 위치 2곳**:
    1. 검색창(`#search`, `/` 또는 상단 `찾기` 버튼)을 열었을 때 입력란이 비어 있으면, 기존 인구 상위 도시 8곳 아래에 **`추천 시점 6선`** 2열 카드(모바일 1열)를 표시한다.
    2. 도움말(`#help`, `?` 버튼) 하단에 같은 6개 시점 버튼을 둔다.
  - 항목을 누르면 모달을 닫고 해당 프리셋의 `lens`, `ly`, `hide`, `city`를 적용한 뒤 목표 영역으로 `flyTo`한다. 적용 후 모든 상태는 잠기지 않으며 사용자가 자유롭게 수정할 수 있다.
- **실제 데이터 필드 경로 및 6개 프리셋 정의** (모두 `site/data/*.json` 실측 좌표·ID 검증 완료):
  1. **수도권 밀집과 철도망**: `lens: 'density'`, `layerOn: {wonders:true, resources:true, infra:true, trade:false, frontier:false}`, `subOff: []`, `city: 0` (서울), `target: {x: 2290, y: 1760, zMult: 2.8}` (고속철도역·인구밀도 집중 확인)
  2. **동해안 원전·발전 축**: `lens: null`, `layerOn: {wonders:false, resources:true, infra:true, trade:false, frontier:false}`, `subOff: ['farm','fishport','mine','industry','dam','lines','station']`, `city: null`, `target: {x: 4050, y: 2950, zMult: 1.9}` (한울·월성·새울·고리 원전과 동해안 항만·화력)
  3. **영남 제조·수출 벨트와 교역로**: `lens: 'manufacturing_share'`, `layerOn: {wonders:false, resources:true, infra:true, trade:true, frontier:false}`, `subOff: ['farm','fishport','mine','dam','station']`, `city: 12` (울산), `target: {x: 3820, y: 3580, zMult: 2.1}` (제조업 비중 + 수출 거점 + 교역로)
  4. **산간 지형과 소멸위험**: `lens: 'extinction'`, `layerOn: {wonders:true, resources:false, infra:false, trade:false, frontier:false}`, `subOff: ['heritage_cluster','knowledge']`, `city: null`, `target: {x: 3180, y: 2700, zMult: 1.45}` (태백·소백 산줄기 기복 + 국립공원 + 소멸위험지수)
  5. **호남평야 논과 쌀 생산**: `lens: 'paddy_share'`, `layerOn: {wonders:false, resources:true, infra:false, trade:false, frontier:false}`, `subOff: ['power','dam','mine','industrial','industry','fishport']`, `city: 18` (전주시), `target: {x: 2200, y: 3680, zMult: 2.4}` (토지피복지도 논 비중 + 쌀 상위 생산지)
  6. **접경지역과 휴전선**: `lens: null`, `layerOn: {wonders:true, resources:false, infra:false, trade:false, frontier:true}`, `subOff: ['heritage_cluster','knowledge']`, `city: null`, `target: {x: 2750, y: 1280, zMult: 2.2}` (시행령 제1·2항 접경 17개 시·군 + 휴전선 + 공개제한 구역)
- **계산식**:
  - `scale = clamp(cam.minScale * preset.target.zMult, cam.minScale, cam.maxScale)` — 화면 크기(데스크톱 1440×900 / 모바일 390×844)가 달라도 같은 상대 배율(`z`)로 열려 `tier 1`/`tier 2` 아이콘 노출이 일관된다.
- **"자료 없음" · 부분 합 · 비공개일 때 표시**:
  - 프리셋 #6(접경지역)은 공개제한 구역(ESA WorldCover 보완 칸)을 포함하므로 지형 범례와 칸 툴팁의 기존 `"공개제한 구역 — 대체 자료 ESA WorldCover"` 표시가 그대로 노출된다.
  - `layers` 로딩 완료 전에 프리셋을 누르면 `layerOn`/`subOff` 상태만 즉시 반영하고 `setLayers()` 완료 시 자동 렌더된다.
- **규칙 문장 (연감 초안)**: 별도 통계 규칙 없음(중립적 사실 묘사 제목만 사용, 가치 판단 문구 금지).
- **키보드 · 터치 동작**:
  - `#search`에서 빈 입력 상태일 때 `↑`/`↓`로 도시 목록에서 추천 시점 6선까지 연속 탐색, `Enter`로 즉시 적용.
- **공유 링크 해시 키**:
  - **신규 해시 키 없음**. 프리셋 실행 결과는 기존 `v`, `lens`, `ly`, `hide`, `city` 해시로 직렬화되므로 신여지도에 같은 링크를 열어도 동일 장면이 복원된다.
- **예상 엣지 케이스**:
  - **광역시와 자치구**: 프리셋 #1(서울)과 #3(울산)은 광역시 패널을 연다. 패널이 열린 데스크톱에서 목표 지점이 패널(360px)에 가리지 않도록 `cam.x`를 오른쪽 패널 폭의 절반만큼 보정(`tx = preset.target.x + (vw > 700 && preset.city != null ? 180 / scale : 0)`).
  - **전남광주통합특별시**: 프리셋 #5(호남평야) 범위 안에 전남광주 북부·서부 평야(나주·영암·김제·익산)가 함께 들어가며, 지형·논 비중 경계가 자연스럽게 보인다.
  - **인구 10만 미만 군**: 프리셋 #4(산간 지형)·#6(접경지역)에서 군 단위 지명·접경 띠가 `z >= 2.0` 기준으로 적절히 나타난다.

---

### #32. PNG 내보내기 크로스브라우저 안정화 및 1:1 정사각 카드 (#25 흡수)

- **화면 위치와 동작**:
  - 상단 `공유` 메뉴(`#sharemenu`)를 3개 항목으로 확장한다:
    1. `🔗 지금 화면 링크 복사`
    2. `🖼️ 그림 내려받기 — 정사각 1:1` (`1200×1200`, 한반도 전국 화면 권장)
    3. `🖼️ 그림 내려받기 — 와이드 16:9` (`1600×900`, 확대·가로 구간용)
  - 1:1 정사각 하단 띠(`BAND = 156`, `MAPH = 1044`)는 2단 레이아웃(윗줄 좌=제목·부제 / 우=기준 시점·출처·`SITE_NAME`, 아랫줄=범례 전체 폭)으로 구성해 1200px 폭에서 글자 겹침을 방지한다.
  - 비교 모드(#14) 활성 시 제목을 `${A.name} vs ${B.name} · ${lens ? lens.name : '지형'}`으로 자동 생성하고, 지도 캔버스에도 두 도시 테두리와 연결 아크를 함께 그린다.
  - **모바일·WebKit 폴백(#25 흡수)**:
    - 터치 환경에서 `navigator.canShare && navigator.canShare({ files: [file] })` 지원 시 네이티브 공유 시트 호출.
    - iOS Safari·인앱 브라우저 또는 내려받기 미지원/실패 시 경량 미리보기 시트(`#pngpreview`)를 띄워 `<img>` + `"이미지를 길게 눌러 저장하거나 아래 버튼으로 내려받으세요"` 안내 + 직접 저장/닫기 버튼 제공.
- **실제 데이터 필드 경로**:
  - `config.js`: `SITE_NAME`, `SITE_URL`
  - `nation.json`: `nation.vintage`
  - `lenses.json`: `lenses.vintage`, `lenses.lenses[k].{name, emoji, unit, basis, vintage, source, scale, higher_is, domain, ramp, breaks, bin_labels, categories}`
  - 선택 상태: `cities[id].name`, `states[code].{name, short}`, `selItem.{name, kind}`, `selRoute.{a, b}`
- **계산식**:
  - 프리셋 치수: `square = { W: 1200, H: 1200, BAND: 156 }`, `wide = { W: 1600, H: 900, BAND: 128 }`.
  - 카메라 매핑: `a.cam.scale <= a.cam.minScale * 1.03`이면 `cam.fit()`(1:1 카드에서 한반도 종횡비가 화면을 80% 이상 채움); 확대 상태이면 `cam.scale = a.cam.scale * Math.min(W / a.cam.vw, MAPH / a.cam.vh)`.
  - 안정화 시퀀스:
    1. `if (document.fonts && document.fonts.ready) await document.fonts.ready;`
    2. `render(preset)`으로 오프스크린 캔버스 생성.
    3. `blob = await canvasToPngBlob(cv)` — `cv.toBlob`이 `null`이거나 예외면 `cv.toDataURL('image/png')`를 디코드해 `Blob` 생성.
    4. `isMobileTouch && navigator.canShare?.({ files: [file] })` → `navigator.share({ files: [file], title })` (`AbortError`는 정상 취소로 토스트 생략).
    5. 그 외 → `<a download>` 클릭 + `setTimeout(() => URL.revokeObjectURL(url), 15000)` + iOS/WebKit(`isIOS || isInApp`) 감지 시 미리보기 시트 `#pngpreview` 병행 오픈.
    6. 미리보기 닫힘 시 즉시 `URL.revokeObjectURL(url)` 및 `cv.width = cv.height = 0` 메모리 회수.
- **"자료 없음" · 부분 합 · 비공개일 때 표시**:
  - 렌즈 범례의 기존 `"자료 없음"` 빗금 칩과 `higher_is` 방향 문구 유지.
  - 캔버스 생성 실패(극단적 메모리 부족) 시 토스트 `"그림을 만들지 못했습니다. 화면을 축소하거나 다시 시도해 주세요."` 안내.
- **규칙 문장 (연감 초안)**: 별도 통계 규칙 없음(도움말 `?`의 공유 문구를 `"1:1 정사각(1200×1200) · 16:9 와이드(1600×900) 그림 내려받기"`로 갱신).
- **키보드 · 터치 동작**:
  - `#sharemenu` 및 `#pngpreview` 모두 `Esc` 닫기 순서(`main.js` `escape()`)에 포함.
  - `#pngpreview`의 이미지는 `user-select: none; -webkit-touch-callout: default;`를 유지해 iOS Safari 길게 눌러 사진 저장이 정상 동작하게 한다.
- **공유 링크 해시 키**: 없음.
- **예상 엣지 케이스**:
  - **광역시와 자치구 / 전남광주통합특별시**: 긴 이름(`전남광주통합특별시 · 소멸위험지수`, `화성시 vs 전남광주 무안군` 등)이 1:1 카드 1200px 윗줄에서 우측 기준 시점 텍스트와 충돌하지 않도록 제목 최대 폭 `760px`으로 `measureText` 말줄임(`…`) 처리.
  - **인구 10만 미만 군**: 전국 화면 1:1 출력 시 `exporting = true`로 기존 `hoverCell`·`hoverCity`가 제거되고, #1·#2 규칙이 그대로 적용돼 깔끔한 한반도 카드가 생성된다.

---

## 3. "게임 느낌" 강화 — 탐색 동기 안 3개와 절제 기준

숫자를 꾸미거나 가짜 점수·뱃지·연출을 덧붙이지 않고, **보유한 실측 필드만으로 "다음 한 클릭"을 자연스럽게 유도하는 3개 흐름**을 설계한다. 모두 위 11개 채택안의 내부 인터랙션으로 녹아들어 별도 화면이나 무거운 구조를 추가하지 않는다.

### 흐름 A. 순위 인접 사다리 & 같은 시도 1위 점프 (#10 내부)
- **메커니즘**: 도시 패널 `개요` 탭의 순위 미니 게이지(#10)에서 어느 지표(예: `1인당 GRDP 3위/167`)를 누르면, 그 행 바로 아래에 **3개의 1클릭 점프 칩**이 펼쳐진다:
  1. `▲ 바로 위 ({rank-1}위 {도시명} · {값})`
  2. `▼ 바로 아래 ({rank+1}위 {도시명} · {값})`
  3. `같은 시도 1위 ({도시명} · {값})` (현재 도시가 이미 도내 1위거나 단일 도시 시도이면 생략)
- **사용 필드**: `cities[i].ranks.*`, `cities[i].sido`, `states[s].cities`, 해당 지표 원본 값(`population`, `growth_5y`, `age.over65`, `extinction_index`, `gdp`, `gdp_per_capita`, `wage.per_filer`, `housing.sale_per_m2`, `trade.export`).
- **탐색 동기**: "화성시가 1인당 GRDP 3위면 2위·1위는 어디지?", "우리 군보다 소멸위험이 한 단계 덜한 곳은 어디가 다르지?"라는 호기심을 보고서 모달을 열지 않고도 도시 패널 안에서 사다리 타듯 연속 탐색하게 만든다.
- **절제 기준 (장난감 방지)**:
  - 왕관·트로피·메달·"역전까지 OO원" 같은 경쟁 연출을 일절 쓰지 않는다.
  - 기본 상태에서는 접혀 있어 패널 정보 밀도를 늘리지 않고, 사용자가 순위 행을 직접 눌렀을 때만 1줄 펼친다.
  - 1위(`rank === 1`)나 최하위(`rank === N`)에서는 없는 방향 칩을 생략하고, `자료 없음`(순위 미산정) 행은 아예 펼침을 비활성화한다.

### 흐름 B. '닮은 도시' 유사 근거 + 결정적 차이 → 1클릭 대결 (#13 → #14)
- **메커니즘**: `cities[i].peers` 5곳을 단순 이름 링크가 아니라 **"왜 닮았고 무엇이 다른가"**로 읽어 준다(#13). 예를 들어 `화성시`를 열면 `울산 — 제조 비중 67% vs 55% · 5년 증감 +18.2%p 차 [비교]`처럼 뜨고, 우측 `비교` 버튼 한 번으로 두 도시 영토를 잇는 금색 점선 아크와 2열 대조표(#14)로 이어진다. 비교 패널 안에서도 상대 도시의 `peers`나 같은 시도의 다른 도시로 `B 변경`이 가능하다.
- **사용 필드**: `cities[i].peers`, `cities[i].peer_rule`, `cities[i].{population, age.over65, gdp_per_capita, gdp_by_industry, wage.per_filer, housing.sale_per_m2, growth_5y}`.
- **탐색 동기**: 4X 전략 게임에서 다른 문명·도시의 산출을 나란히 대조해 보는 재미를 실제 한국 도시 비교로 옮긴다. "산업 구조는 비슷한데 왜 한쪽은 인구가 늘고 다른 쪽은 줄까?"라는 질문이 다음 클릭을 부른다.
- **절제 기준 (장난감 방지)**:
  - "승자/패자", 점수 합산(예: "화성시 7승 3패"), 승부 게이지 같은 판정 UI를 **절대 넣지 않는다**.
  - 모든 지표 비교는 `lenses.json`의 `higher_is` 규칙을 엄격히 따라, 중립 지표(인구·매매가·고령 비율)는 색칠 우열 표시 없이 수치만 나란히 놓는다.
  - 차이 1줄은 임계값(매매가 1.35배↑, 5년 증감 5%p↑, 총급여 1.15배↑)을 넘을 때만 표시하고, 기준 연도가 다르거나 표본이 적으면(`trades < 10`) 생략한다.

### 흐름 C. 관전 시점(#20) → 연관 렌즈 짝 제안 & `B` 맞교환 (#18)
- **메커니즘**: 첫 방문자가 `#search` 빈 상태나 `?`에서 추천 시점 6선(#20) 중 하나(예: `영남 제조·수출 벨트`)를 누르면, 지도가 즉시 완성된 장면으로 이동한다. 이어서 범례 하단에 **현재 렌즈와 짝을 이루는 1~2개 렌즈 칩**이 조용히 표시된다(예: `1인당 GRDP` → `1인당 총급여`, `고령 인구` → `의사 수`, `제조업 비중` → `초미세먼지`·`1인당 수출`, `아파트 매매가` → `아파트 전세가`·`합계출산율`). 칩을 눌러 전환한 뒤 `B` 키(또는 `⇄`)로 두 렌즈를 번갈아 뒤집어 보며 공간 상관을 스스로 발견한다.
- **사용 필드**: `lenses.lenses[k].{id, name, emoji}`, 정적 짝 테이블(최대 10쌍, 모두 `lenses.json` 실존 ID 검증).
- **탐색 동기**: 33개 렌즈를 목록에서 고르는 인지 부담을 없애고, "생산지 부자(`gdp_pc`)를 봤으니 주소지 소득(`wage`)으로 뒤집어 보자"는 전략 지도 본연의 교차 분석 루프를 만든다.
- **절제 기준 (장난감 방지)**:
  - "다음 미션", "추천 퀘스트", 알림 배지, 깜빡임 효과를 쓰지 않는다.
  - 범례 하단 출처 위에 작은 텍스트 링크 1줄(`함께 보기: 1인당 총급여`)로만 절제해 두고, 짝이 정의되지 않은 렌즈에서는 줄 자체를 숨긴다.
  - 해석 문구("수도권은 생산과 소득이 괴리됩니다" 같은 결론 주입)를 쓰지 않고, 렌즈 이름만 제시해 판단을 사용자에게 맡긴다.

---

## 4. 전국 화면 표시 우선순위 — 단일 결정 규칙

전국 배율(`z < 2.0`, `tier === 0`)과 확대 배율(`z >= 2.0`)에서 **깃발 · 시도 이름 · 층 아이콘 · 강/호수 이름표** 4종이 한 화면 예산 안에서 자리를 얻는 단일 규칙이다.

### 4.1 그리기 층위 (Z-order, 아래 → 위)
1. **지형 타일 + 경계** (`TerrainRenderer`: 표고·피복·기복·호수·강 선·해안선·시군구/시도 경계·휴전선)
2. **선형·면형 지도 층** (`drawLines` 도로·철도 → `drawFrontier` 접경 띠 → `drawParks` 국립공원 빗금 → `drawRoutes` 교역로)
3. **선택 영토 테두리 및 비교 아크** (`drawOverlay`: `outline`, 비교 도시 B 테두리·아크, `selItem` 칸, `hoverCell`)
4. **시도 이름 각인** (`StateLabels.draw` — **#2에서 깃발·아이콘 아래로 하향**)
5. **강·호수 이름표** (`GeoLabels.draw` — `z >= 2.4`/`2.8`, 깃발·아이콘 아래)
6. **지도 층 아이콘 + 오프셋 지시선** (`LayerRenderer.drawIcons`)
7. **도시 깃발** (`Banners.draw` — 최상단, 선택 깃발이 마지막에 그려져 항상 가장 위)

### 4.2 화면 배치 예산과 결정 순서 (단일 파이프라인)

매 렌더 프레임의 `drawScene()`은 아래 5단계를 결정적(deterministic) 순서로 실행한다.

| 단계 | 대상 | 우선순위 및 배치 규칙 | 화면 예산 상한 (`z < 2.0` 전국 배율) | 충돌 시 동작 |
|---|---|---|---|---|
| **1단계** | **P1a 최우선 아이콘** (`selItem`, `nuclear` 5곳) | `wonders.zoom.draw_priority.first` 항목의 제자리 상자(`r0 + 2`)를 `prioBoxes`로 예약 | `nuclear` 5/5 전부 보장 | 2단계 깃발이 먼저 피함; 못 피한 대도시 깃발과 겹칠 때만 3단계에서 이웃 칸 오프셋 + 지시선 |
| **2단계** | **도시 깃발** (`Banners.layout`) | ① `selCity` · `cmpCity` (항상 표시) → ② `capital !== '없음'` (수도·도청·통합청사 18곳, 인구 내림차순) → ③ `population >= 500,000` → ④ 나머지 `population >= 150000 / (z*z)` | 데스크톱 **최대 24개**, 모바일(`vw <= 700`) **최대 12개** (`z >= 2.0`에서는 상한 해제) | 이미 놓인 깃발과 겹치면 숨김(`selCity`/`cmpCity` 예외). `prioBoxes`와 겹치면 좌우/아래 비켜 서기 → 실패 시 `big`(선택·청사·50만+)만 제자리 유지, 그 외 숨김 |
| **3단계** | **지도 층 아이콘** (`LayerRenderer.layout`) | ① `selItem` → ② **P1a** (`nuclear` 5) → ③ **P1b** (`tier === 0` `airport` 6, `trade_port` 8, `value` 순) → ④ **P2** (나머지 `tier` 허용 항목, `KINDS[kind].pri` → `value` 내림차순) | 데스크톱 **총 52개**, 모바일 **총 24개** (`P1a + P1b` 우선 차감 후 `P2` 채움; `z >= 2.0` 상한 해제) | **P1a/P1b**: 깃발·기존 아이콘과 겹치면 `maxDist <= 2.4*r0` 이내 가장 가까운 빈 이웃 칸으로 이동 + 원래 칸 지시선(실패 시 제자리). **P2**: 전국·중간은 깃발 상자 겹침 시, 가까이는 중심이 깃발 안이면 숨김; 아이콘 간 `0.8*(r1+r2)` 겹침 시 숨김 |
| **4단계** | **시도 이름표** (`StateLabels.layout`) | 광역시 등 동명 도시 깃발이 있는 시도 제외(`경기·강원·충북·충남·전북·전남광주·경북·경남·제주` 9곳). 7개 후보 위치 중 `2단계 깃발 + 3단계 P1 아이콘`과 겹침 면적 최소 위치 선택 | `raw = label.size * scale >= 14px`인 시도만(선택 시도 예외) | **겹침이 남아도 어떤 깃발·아이콘도 제거하지 않음**(`banners.avoid()` 폐지). 반투명 명조 각인이므로 배경으로 안전하게 깔림 |
| **5단계** | **강·호수 이름표** (`GeoLabels.layout/draw`) | 강: `z >= 2.4` (`world.river_labels` 15개 후보 지점), 호수: `z >= 2.8` (`world.lake_labels` 넓이 내림차순 16개) | `z < 2.4` 전국 화면에서는 **0개**(미표시). `z >= 2.4`에서 강당 최대 1~2지점 | `2단계 깃발 + 3단계 아이콘 + 이미 놓인 강/호수 이름표` 상자와 하나라도 겹치면 그 후보 지점을 건너뜀(강은 3개 후보 지점 중 빈 곳을 자동 선택) |

### 4.3 히트 테스트(포인터 클릭·호버) 우선순위
화면에서 위에 그려진 객체가 먼저 선택되도록 아래 순서를 고정한다:
`도시 깃발 (선택/비교 깃발 우선) → 지도 층 아이콘 (P1a/P1b 포함) → 교역로 선 → 시도 이름표 → 빈 육지 칸(해당 칸의 시도)`

---

## 5. 채택안 간 충돌 · 구현 순서 · 검증 방법

### 5.1 채택안 간 충돌과 해소

| 충돌 쌍 | 충돌 내용 | 해소 방식 |
|---|---|---|
| **#1 ↔ #2** | 기존 `main.js`는 `banners.avoid(labels)` 후 `layerR.layout(banners)`를 실행해 시도 이름이 깃발과 아이콘 연쇄 배치를 흔들었다 | 4장의 단일 파이프라인으로 통합: `banners.avoid()` 제거, 시도 이름 배치를 3단계 아이콘 배치 뒤로 보내고 깃발·P1 상자만 회피 참조 |
| **#12 ↔ #9** | #12는 5산출을 상단 고정 HUD로 올리고, #9는 상단에 4탭 바를 추가해 모바일(`62vh`)에서 상단 고정부가 본문을 과도하게 점유할 수 있음 | 데스크톱은 `헤더 + 5산출 + 4탭` 모두 상단 고정; 모바일(`<= 700px`)은 `헤더 + 4탭`만 sticky로 두고 5산출 스트립은 스크롤과 함께 넘겨 본문 높이 확보 |
| **#12 ↔ #9 (주의 서랍)** | #9에서 탭 4개 중 3개가 `hidden`일 때 패널 전체 주석을 1개 서랍에 모으면 숨은 탭의 주석 번호까지 섞여 번호가 건너뜀 | `footnotes()`가 각 `.ptab` 패널 단위로 독립 실행되거나 활성 탭의 `.note`만 번호 1..K로 수집해 서랍 1개를 생성하도록 스코프 분리 |
| **#10 ↔ #11 ↔ #14** | 세 안 모두 `nation.json` 공식 전국값·도시 중앙값·LQ 계산을 공유함. `panel.js`에 중복 작성 시 수치·결측 규칙이 어긋날 위험 | 공용 순수 계산 모듈 `site/js/metrics.js`(신규 1파일, ~120줄)에 `cityBenchmarks()`, `computeLQ()`, `cityTags()`, `peerReasons()`를 모아 #10·#11·#13·#14가 동일 함수를 호출 |
| **#14 ↔ #32** | 비교 모드(`#cmp=a,b`)에서 PNG 내보내기 시 16:9/1:1 카드 제목과 지도 오버레이(두 도시 테두리+아크)가 빠져 있을 수 있음 | #32 구현 시 `share.title()`과 `drawOverlay()`의 `exporting` 경로가 `app.cmpCity`를 인식하도록 연동 |
| **#14 ↔ #20 (레이아웃)** | 데스크톱에서 비교 패널(`460px`)이 열리면 `#minimap`·`#lensbar`와 겹칠 수 있음 | `body.compare-open` 클래스에서 `#minimap { right: 480px }`, `#lensbar { left: calc((100vw - 480px) / 2); max-width: calc(100vw - 500px); }` 규칙 추가 |

### 5.2 구현 순서 (의존 관계)

> **선행 조건(0단계)**: 별도 감사에서 도출된 결함 수정을 먼저 완료한다.

```text
[0단계: 감사 결함 수정]
   ├──▶ [1단계: 지도 판독성]  #2 (시도 이름 각인화) ──▶ #1 (통합 배치 예산 + GeoLabels 회피)
   ├──▶ [2단계: 공용 계산층 + 패널 개편]
   │        metrics.js (#10 전국대비·순위 + #11 LQ·태그 + #13 유사근거)
   │        ──▶ #12 (5열 산출 스트립 + 단일 주의 서랍)
   │        ──▶ #9 (도시 패널 4탭 구조)
   │        ──▶ #10 · #11 · #13 (각 탭 내부 바인딩)
   ├──▶ [3단계: 비교 & 탐색 루프]
   │        #14 (도시 A vs B 비교 + #cmp= 해시 + 지도 아크)  [의존: metrics.js, #13]
   │        #18 (B 직전 렌즈 토글 + Space 지형 엿보기 + 짝 렌즈)
   │        #20 (추천 시점 프리셋 6선)
   └──▶ [4단계: 공유 마무리]
            #32 (PNG 크로스브라우저 안정화 + 1:1 카드 + 모바일 폴백)  [의존: #1, #2, #14]
```

- **1단계 (#2 → #1)**: `labels.js`, `banners.js`, `layers.js`, `geolabels.js`, `main.js` 수정. 지도 첫 화면 인상을 먼저 정돈.
- **2단계 (`metrics.js` → #12 → #9 → #10/#11/#13)**: 패널 DOM 재편과 계산 로직을 한 번에 정리해 `panel.js` 이중 수정을 방지.
- **3단계 (#14, #18, #20)**: 탐색 동기와 비교 기능 완성. #18과 #20은 독립적이므로 병렬 구현 가능.
- **4단계 (#32)**: 지도(#1·#2)와 비교 오버레이(#14)가 모두 반영된 뒤 PNG 출력 결과를 최종 검증.

### 5.3 각 안의 검증 방법 (완료 판정 기준)

모든 검증은 `site/`에서 로컬 정적 서버(`python -m http.server 8741`)를 띄워 콘솔 에러 `0건`, 네트워크 404 `0건` 상태에서 수행한다.

| # | 검증 항목 및 합격 기준 (Pass Criteria) | 필수 점검 대상 |
|---|---|---|
| **#1** | ① 전국 배율(`z = 1.0`, `1440×900` 및 `390×844`)에서 `layerR.placed` 집계: 원전 **`5/5`**, `tier 0` 공항 **`6/6`**, `tier 0` 무역항 **`8/8`** 전부 표시. ② 총 아이콘 수 데스크톱 `<= 52`, 모바일 `<= 24`. ③ 오프셋된 아이콘마다 `p.ox != null` 지시선이 원래 칸 중심에 연결되고, 툴팁에 안내 문구 노출. ④ `z = 2.6`에서 강 이름표가 깃발·아이콘 상자와 겹침 `0건` | 전국 화면(데스크톱/모바일), 부산·울산·인천·서울·제주 확대 |
| **#2** | ① `drawScene()`에서 시도 이름이 깃발·아이콘 아래에 그려짐(스크린샷 육안 확인). ② `banners.avoid()` 제거 후 전국 배율에서 비청사 도시 깃발이 시도 이름 때문에 삭제되지 않음. ③ `전남광주` 4글자가 시도 경계 밖으로 과도하게 튀지 않음. ④ 진한 렌즈(`over65`, `extinction`) 켜짐 시 시도 이름 대비 유지 | `지형` 모드 + `over65` + `extinction` 전국 화면 |
| **#12** | ① `360px` 데스크톱 패널 및 `390px` 모바일 시트에서 `.yields`가 정확히 **1행 5열**로 줄바꿈 없이 렌더(각 타일 `offsetTop` 동일). ② `details.caveats`가 열린 탭 당 **최대 1개**만 DOM에 존재. ③ `서울(0)` 생산 칸에 점선 테두리·`*`가 보이고 클릭 시 `#fnpop`에 `광업 비공개 14곳 제외` 출력 | `서울(0)`, `화성시(9)`, `울릉군(166)`, `전남광주(12)` 시도 패널 |
| **#10** | ① 동일 기준 지표(인구·고령·소멸·GRDP·총급여·아파트·대졸)의 대비값이 `nation.json`과 소수 첫째 자리까지 일치. ② 고용률·재정자립도는 전국 공식값이 아닌 `도시 중앙값`으로 표기되고, 광역시(`서울`·`부산`)에는 대비 화살표 미생성. ③ 순위 게이지 `export` 분모 `165`, `housing` `166`, 나머지 `167`. ④ 순위 행 클릭 시 `rank-1`/`rank+1` 칩으로 정상 이동 | `화성시(9)`, `세종(30)`, `서울(0)`, `부산(1)`, `옹진군(164)`, `포천시(63)`, `울릉군(166)` |
| **#11** | ① 167개 도시 전체 루프 테스트: `NaN`/`Infinity` `0건`, 비공개 산업(`gdp_undisclosed` 25곳, `jobs` 47곳)에 LQ 미표시. ② `화성시`=`제조업 특화 ×2.6`, `세종`=`공공행정·국방 특화 ×4.4`(+2024/2023 주석), `익산시`=산업 태그 생략(0개), `울진군`=`전기·가스·증기 특화 ×33`(+소규모 주석) 확인. ③ 연감 `산출` 탭에 규칙 문장 노출 | `서울(0)`, `부산(1)`, `화성시(9)`, `세종(30)`, `무안군(80)`, `익산시`, `울진군`, `울릉군(166)` |
| **#9** | ① 도시 패널 `개요` 탭 초기 `scrollHeight`가 기존 6단계 대비 **50% 이상 감소**. ② 도시 A의 `경제` 탭에서 도시 B 깃발 클릭 시 `경제` 탭 유지. ③ URL `#city=9&tab=econ` 새로고침 시 `경제` 탭 복원, `overview`일 때 해시에 `tab=` 미기록. ④ `←`/`→` 키보드 탭 이동 정상 | 데스크톱(`1440×900`) + 모바일(`390×844`), `서울(0)`(구 25개), `무안군(80)` |
| **#13** | ① 167개 도시 전체의 `peers` 5곳 모두 요약 1줄 생성에 예외 `0건`. ② `울릉군(166)`(`trades: 3`)·`옹진군(164)`(`null`)에서 매매가 배수 차이 미노출. ③ 좌측 이동 버튼과 우측 `비교` 버튼(터치 영역 `>= 44px`)이 독립 클릭됨 | `서울(0)`, `화성시(9)`, `무안군(80)`, `울릉군(166)`, `옹진군(164)` |
| **#14** | ① `#cmp=9,12` 진입·새로고침·`⇄ 바꾸기`·`Esc` 닫기 정상. ② `서울(0) vs 울릉군(166)` 피라미드가 비중(%) 정규화로 양쪽 모두 판독 가능. ③ `세종(30) vs 화성시(9)`에서 GRDP 연도 차이 경고 표시 및 Δ 미계산. ④ `서울(0) vs 수원시(6)`에서 고용률·재정자립도 범위/단일값 Δ 미계산. ⑤ `#cmp=9,9`·`#cmp=9,999` 같은 잘못된 해시 입력 시 폴백+토스트 | `화성시 vs 울산`, `서울 vs 울릉군`, `세종 vs 화성시`, `광주 vs 무안군`, `포천시 vs 옹진군` |
| **#18** | ① `gdp_pc` → `wage` 전환 후 `B` 3회 연속 누름 시 `wage ↔ gdp_pc` 왕복, URL 해시 정상 갱신. ② `Space` 홀드 중 지형 표시·해제 시 렌즈 복원, `window.blur` 시 고정 버그 `0건`, 버튼 포커스 중 `Space` 미가로채기. ③ 짝 렌즈 칩 클릭 후 `B`로 직전 렌즈 복귀 확인 | 데스크톱 키보드 + 모바일 터치(`⇄`, `👁`) |
| **#20** | ① `#search` 빈 상태와 `?` 도움말에서 6개 프리셋 모두 클릭 시 의도한 렌즈·층·위치로 이동하고, 생성된 URL 해시를 새 탭에 붙여 넣었을 때 동일 화면 복원. ② URL 해시에 신규 프리셋 전용 키가 추가되지 않음 확인 | 6개 프리셋 전부(데스크톱 `1440×900` + 모바일 `390×844`) |
| **#32** | ① Chromium·Firefox·WebKit(Playwright 3엔진)에서 1:1(`1200×1200`) 및 16:9(`1600×900`) PNG 파일 실제 크기 > 50KB, 다운로드 이벤트 또는 미리보기 시트 정상 트리거. ② 1:1 카드에서 한반도 좌우 빈 여백이 16:9 대비 대폭 축소되고 하단 띠 글자 겹침 `0건`. ③ 비교 모드(`#cmp=9,12`) PNG에 제목(`화성시 vs 울산`)과 두 도시 테두리·아크 정상 출력 | Chromium / Firefox / WebKit, 모바일 뷰포트, 일반·렌즈·비교 3가지 상태 |
