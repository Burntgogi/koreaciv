# 신여지도 — 두 번째 프런트엔드 (`site/yeojido/`)

같은 자료(`site/data/*.json`)를 읽는 별도 판이다. 멀리서는 한지 위 먹 지도, 다가가면 칸마다 석채 빛깔이 배어 나오고, 렌즈를 켜면 통계가 먹판 위에 한 판 더 찍힌다. 기존판(`site/`)은 고치지 않았다.

## 1. 돌리기

```
cd site && python -m http.server 8000      →  http://localhost:8000/yeojido/
python pipeline/build_ridges.py            # 산줄기 다시 계산 (site/data/ridges.json)
python tools/yeojido/build_fonts.py        # 글꼴 다시 줄이기 (UI 글이나 자료 글자가 바뀌면)
python tools/yeojido/qa.py [--only chromium|firefox|webkit]   # 점검 (결과 tools/yeojido/qa_result.txt)
python tools/yeojido/screens.py            # docs/screenshots/y_*.png
python tools/yeojido/shot.py out.png "#해시" [w h] [--js "…"]   # 한 장 갈무리
```

빌드 단계·CDN·프레임워크 없음. ES 모듈 + 캔버스 2D.

**주 빌드에 넣을 한 줄** (`pipeline/build_all.py` 의 `STEPS`, `build_sources.py` 앞): `"build_ridges.py",` — `world.json` 과 `data/build/layers/rivers.geojson` 이 만들어진 뒤여야 한다. 검사에 실패하면 0이 아닌 값으로 끝나고 옛 파일을 그대로 둔다. `validate.py` 가 `ridges.json` 을 어떻게 보는지는 확인하지 않았다.

**기존판에 넣을 한 줄** (`site/index.html`, 자리와 꾸밈은 기존판 담당이 정함):
```html
<a id="to-yeojido" href="yeojido/index.html" onclick="location.href='yeojido/index.html'+location.hash;return false">신여지도 판으로</a>
```
이쪽에서 기존판으로 가는 단추(「다른 판으로」)는 `../index.html` + 같은 해시로 간다.

## 2. 짜임

```
site/yeojido/
  index.html            한 장의 종이: #masthead(장부·도구) #slip(제첨) #rail(렌즈 갈피) #plate(도판=캔버스) #layers #foot, #panel(장), #drawer(순위), #modal-root, #places(글로 읽는 목록)
  css/  fonts tokens app(뼈대) lens(장부·보고서·갈피·범례) panels layers modals
  fonts/  글꼴·제호 한자·낙관·이용허락 (fonts.json, README.md)
  js/
    main.js             App: 상태, 그리기 반복, 입력, 해시
    adapter.js + adapter/{core,places,reports,sources,layers}.js   자료 모양을 읽는 단 하나의 문
    camera.js hex.js fmt.js dom.js icons.js config.js paper.js
    map/ plates(조각 피라미드) land(먹판·채색판·렌즈판 그리기) lines(산줄기·물줄기·경계) labels lenscolor layers(아이콘·교역로·공원·길)
    ui/  masthead lensui panel(+panel_charts) layerctl tooltip search almanac help share a11y modal
```

**그리기.** 조각(512 px) 피라미드 세 벌 — 먹판, 채색판, 렌즈판. 매 프레임 먹판을 깔고 채색판을 `k = smoothstep(5.5, 12, 칸 반지름 px)` 의 알파로 덮는다(확대하는 동안 계속 섞인다). 렌즈는 투명 조각을 먹판 위에 `multiply` 0.84 로 찍는다. 선(산줄기·물줄기·해안·경계·휴전선)은 조각에 굽지 않고 프레임마다 벡터로 긋는다. 조각 단계는 √2 간격, 늘 줄여 그린다(0.71–1배).

**해시** (기존판과 같은 열쇠): `v=x,y,scale` · `lens` · `city | state | item | route | report` · `ly`(켠 묶음) · `hide`(끈 세부) · 옛 `off/on`, `cmp=a,b`(첫 고을로) 읽기. `report=1` 은 전국 장, `report=<id>` 는 순위 보고서(기존판에서는 전국 패널로 열린다). `intro=0` 은 표지 건너뛰기. 해시가 바뀌면 지난 선택을 먼저 모두 지운 뒤 검증을 통과한 값만 넣는다.

### 어댑터 계약

- `../data/*.json` 의 필드 이름과 실림 꼴은 `js/adapter/` 안에서만 읽는다. 화면 모듈에는 `.raw` 읽기·자료 `fetch` 가 없다(grep 으로 확인). 자료 모양이 바뀌면 이 폴더만 고친다.
- `core.js`: `loadCore()` → `D`(world·cities·states·lenses·ridges·failed), `loadLayers(D)`, `lensValues / lensT / lensInv / lensSteps / lensUnitOf`. 렌즈 값의 세 실림 꼴(`values`, `land_values`, `by_county`)을 한 꼴로 편다.
- `places.js`: `cityView / stateView / nationView / itemView / routeView` — 장이 그대로 그리는 보기 모형. 값은 꼴(`won|usd|pct|int|fix|text|na`)을 달고 오며, 없는 값은 `na`(→ "자료 없음").
- `reports.js`: `reportsModel`, `nationHead`, `ledgerParts`, `lensMeta`. `sources.js`: `loadSources`, `attributionFor`(내보내는 그림의 출처 줄), 연감 본문용 접근자, `loadFontCredits`. `layers.js`: 아이콘 부가 값, 배율 규칙.
- 파일 하나가 실패해도 나머지로 뜨고 `D.failed` 에 이름이 남는다(world.json 만 필수).
- 층 묶음·세부 id 와 종류→묶음 표(`config.js`)는 자료가 아니라 기존판 `render/layers.js` 의 표를 옮긴 것이다. 기존판에서 묶음이 바뀌면 여기도 고쳐야 한다.
- 아직 느슨한 곳: `almanac.js`, `share.js` 는 `adapter/sources.js` 를 `adapter.js` 를 거치지 않고 바로 불러온다(폴더 안이긴 하다).

## 3. 산줄기 (`pipeline/build_ridges.py` → `site/data/ridges.json`)

- 자료: 이미 가진 `data/raw/terrain/srtm30plus_korea.csv`(SRTM30+, 721×961, 30″ ≈ 0.93×0.74 km)와 물줄기(`world.json` 의 396개 + 새기기용 WAMIS 유로선 3,833개). 새로 받은 자료 없음.
- 방법: 표고를 448 m 격자로 옮김 → 물줄기를 새김 → 우선순위 범람으로 흐름 방향·누적 → 서로 다른 물줄기로 흐르는 두 칸 사이의 변이 분수계. 두 물이 "얼마나 멀리 가서 만나는가"로 네 단계(10/30/70/160 km)를 매기고, 낮거나 물줄기에서 얕은 곳은 지운다. 큰 줄기 사이의 낮은 고개(10 km 이하)는 계산한 분수계 칸으로 다시 잇는다. 다듬기(1-2-1 12회, 모서리 깎기, 0.5 단위 단순화)와 소수 한 자리 맞춤을 **모두 끝낸 좌표로** 검사한다. 그리는 쪽은 꼭짓점을 곧은 변으로만 잇는다(검사한 선 = 그리는 선).
- 규칙과 검사(마지막 실행, 2026-11-27):
  ```
  규칙: 산줄기는 물줄기를 건너지 않는다.
  물줄기 교차: 0건 (산줄기 변 7,796 × 물줄기 396개·변 18,555) / 호수 가로지름 0건 (호수 125개)
  tier 3 큰 분수계 80선 1816 km · tier 2 큰 줄기 77선 1353 km · tier 1 고을 줄기 195선 2212 km · tier 0 작은 줄기 454선 3768 km
  합계 806선, 9149 km, 꼭짓점 8,602 · 표고 100 m 아래 길이 몫 0.26%
  산줄기 평균 표고 507 m / 대한민국 육지 평균 259 m · 낮은 고개 이음 59곳 157 km
  파일 170,608 바이트 (상한 190,000) · site/data/*.json 합계 4.50 MB
  ```
  교차가 0이 아니거나, 호수를 가로지르거나, 크기를 넘거나, 선이 육지 평균보다 낮으면 스크립트가 실패한다.
- 이름: 계산한 선이라 고유 이름(대간·정맥·산맥)을 어디에도 붙이지 않는다. 지도표·연감에는 "산줄기 (계산한 분수계)"로 적는다.
- 그림 처리(자료 아님): 굵기는 표고를 따라 변하고(봉우리 굵게, 고개 가늘게), 다른 선과 닿지 않는 끝은 가늘게 뺀다. 큰 줄기의 남동쪽 엷은 먹 바림.
- r3 의 물러설 자리(음영 그림으로 대체)는 쓰지 않았다.

## 4. 글꼴과 이용허락 (`site/yeojido/fonts/`, 자세히는 그 안 README.md·fonts.json)

| 쓰임 | 실제 글꼴 | 이용허락 | 파일 |
|---|---|---|---|
| 제목·고을 이름·큰 숫자 | Hahmlet 1.002 (가변) | SIL OFL 1.1, 예약 이름 없음 | `Hahmlet-VF.subset.woff2` 551 KB |
| 본문·표·단추 | Pretendard Variable 1.309 의 수정본, 안 이름 **Yeojido Sans** | SIL OFL 1.1. 원본에 예약 글꼴 이름 'Pretendard' 가 있어 줄인 파일의 이름표를 바꿨다 | `YeojidoSans-VF.subset.woff2` 454 KB |
| 자료 속 한자 | Noto Serif KR 2.003 | SIL OFL 1.1 | `NotoSerifKR-VF.hanja.woff2` 36 KB |
| 제호 곁글 한자 新輿地圖 | Yuji Syuku Regular (붓으로 쓴 해서) | SIL OFL 1.1 | `title-hanja.svg` 17 KB (윤곽), `title-hanja.woff2` |
| 낙관 | Hahmlet 900 윤곽으로 짠 한글 낙관 「신여지도」 + 계산한 인변 | SIL OFL 1.1 | `seal.svg`, `seal-mask.svg` |

모두 2026-11-27 에 원 저장소에서 받아 이용허락 글을 읽고 넣었다(`*-OFL.txt`). 네 한자(U+65B0, U+8F3F, U+5730, U+5716)는 cmap 과 그림으로 정자임을 확인했다. 이 글씨는 특정 서예가의 서체가 아니며 그렇게 부르지 않는다. 한자 전서 낙관은 쓰지 않았다(열린 이용허락의 전서 글꼴에서 네 글자를 모두, 검증 가능한 꼴로 얻지 못함).

### 한자 제호 바꿔 끼우기

1. 새 그림(세로로 긴 SVG 또는 알파가 있는 PNG, 위에서 아래로 新輿地圖)을 `fonts/title-hanja.svg` 자리에 덮어쓰거나, `css/fonts.css` 의 `--title-hanja` 를 새 파일로 돌린다.
2. 같은 파일의 `--title-hanja-ratio`(가로/세로)를 새 그림 비율로 고친다. 빛깔과 짙기는 CSS 가 정한다(마스크로 쓴다).
3. `fonts/fonts.json` 의 제호 항목(이름·지은이·이용허락)을 고친다 — 연감의 글꼴 표기가 여기서 나온다. `build_fonts.py` 를 다시 돌리면 `title-hanja.svg` 와 `fonts.json` 이 다시 만들어지므로, 손으로 바꾼 뒤에는 그 스크립트의 제호 부분도 함께 고친다.

## 5. r3 명세와 다른 곳

| r3 | 한 것 | 까닭 |
|---|---|---|
| 차례(인구 일곱 시점 넘기기)와 해시 `turn` | 뺌. 일곱 시점은 고을·시도 장의 추이선에 있다 | 기존판에 없는 기능이고 인구만 바뀌는 반쪽 연동. 아래 여백을 비웠다 |
| 범주 렌즈의 8색 × 목판 무늬 | 무늬 없이 이름으로 정한 빛깔 | 칸 무늬가 산줄기·음영과 다퉈 어지럽다. 색각 검증은 하지 않음(약점) |
| Catmull-Rom 붓 리본 | 빌드에서 다듬고 곧은 변으로 그림 | 그리는 쪽에서 곡선을 만들면 "건너지 않는다" 검사와 어긋날 수 있다 |
| 빈 땅 누르기 = (기존판) 시도 패널 | 마우스는 그 칸의 고을 장, 손가락은 칸 띠 → 고을 장/시도 장 | 영토 테두리 + 고을 장이 이 판의 중심. 시도 장은 시도 이름·고을 장 머리·찾기로 |
| 장이 지도 위에 겹침 | 1024 px 이상에서는 종이 전체가 장 왼쪽으로 물러남 | 도구·층 단추가 가려지지 않게 |
| 현판마다 인구·다섯 산출 | 큰 고을만 현판, 나머지는 테 없는 묵서. 산출은 지도에 깔지 않음 | 절제 |
| 렌즈 `multiply` 0.82, 소멸위험 고위험 `#C44B31` | 0.84, `#CE6549` | 붉은 벽을 조금 누그러뜨림(그래도 붉다 — 5,027칸 중 3,380칸이 최고 단계) |
| 1200×630 렌즈 화보 카드, 키보드 칸 커서, 고을 견주기 | 없음 (고을 카드는 있음) | 범위 |
| 메모리 목표 모바일 28 MB, 데스크톱 72 MB | 조각 상한을 "보이는 조각 × 1.6 + 4"로 낮춤. 점검 끝 실측(머리 없는 Chromium): 1920×1080 44 MB, 390×844 dpr 2 35 MB | 낮추기 전 80–85 MB. 모바일 목표는 아직 넘는다 |
| 글꼴 1.02 MB | 1.07 MB | 자료의 한자 77자와 KS X 1001 한글을 다 실음 |
| 광학 크기 이중 아이콘 전부 | 9종만 작은 꼴을 따로 그림 | 나머지는 한 꼴로 읽힘 |

## 6. 약한 곳

- 소멸위험 렌즈는 여전히 붉은 벽이다. 범주 16색·안료 띠의 색각 안전성은 검증하지 않았다.
- 산줄기는 좁은 골짜기에서 물줄기에 100–300 m 까지 붙고, 제주는 거의 비며, 교과서 산맥·산경표와 꼭 같지 않다. 가까운 배율에서는 강보다 덜 눈에 띈다.
- 낙관은 활자 윤곽으로 짠 한글 낙관이라 새긴 맛이 약하다. 제호 한자는 단정한 해서로, 힘 있는 필획은 아니다.
- 390 px 전도에서 보장 아이콘 19개가 빽빽하다. 768 px 장부에는 숫자가 없고 「순위」 단추뿐이다.
- 내보낸 그림의 출처 띠가 높이 약 270 px 을 차지한다(자르지 않은 대가). 보이는 묶음의 모든 종류를 적어 실제 보이는 것보다 많이 적는다.
- 순위 서랍이 아래 확대 단추에 겹친다. 항목 장의 긴 단위("22,778,513 명 (2025 여객)")가 어색하게 줄바꿈된다. 범주 범례의 긴 이름이 잘린다(전체는 title).
- 한국어 한 가지뿐이다. 색인도는 포인터 전용(`aria-hidden`).
- 가까운 배율에서 층을 다 켜면 길·철도 그리기가 프레임당 약 7 ms(머리 없는 소프트웨어 렌더 기준).
- 자료 차원의 감사 과제(토지피복 WMS 저장 약관, 개편 전 단위 값 등)는 이 판이 고칠 수 없다. 연감 출처 탭과 내보낸 그림에 경고 줄로 드러낸다.

## 7. 확인한 것과 못 한 것

확인(Playwright, 실제 입력): Chromium 1920·1280·768·390(터치, dpr 2), Firefox·WebKit 1280. 세 브라우저 합쳐 713건 가운데 실패 1건(「ridges.json 막음」에서 불러오기 시간 초과). 마지막 변경 뒤 Chromium 만 다시 돌려 463건 가운데 실패 1건(이번에는 「nation.json 막음」에서 같은 시간 초과). 파일을 막고 여는 것을 따로 16번(네 파일 × 4) 돌리면 모두 1.2초 안에 뜬다 — 가끔 나는 이 시간 초과의 원인은 찾지 못했다(점검용 서버 쪽일 수 있으나 확인 못 함). 성능(머리 없는 소프트웨어 렌더, 참고용): 첫 지도 1.2초, 휠 확대 프레임 간격 중앙 16.7 ms / p95 66.7 ms(조각 굽기), 끌기 중앙 16.7 ms. 판 바꾸기는 세 브라우저에서 양방향으로 렌즈·고을·카메라·층이 같게 복원됨(기존판이 다른 작업자 손에 바뀌는 중의 상태). 최종 갈무리 27장은 모두 눈으로 봤다.

못 한 것:
- 실제 휴대전화·실제 GPU 의 프레임 속도와 메모리, 화면 낭독기 출력, 대비비 측정, 색각 모의.
- Firefox·WebKit 의 1280 밖 폭과 터치. 교역로 누르기는 두 브라우저에서 "어떤 교역로든 열리면 통과"로 점검을 느슨히 했다(정확한 맞춤은 미확인).
- 내려받기 링크로 파일이 실제 디스크에 떨어지는지, `navigator.share`, Chromium 밖의 클립보드.
- 조각 상한·판 해상도를 낮춘 뒤(마지막 변경)에는 Chromium 점검만 다시 돌렸다. Firefox·WebKit 은 그 전 결과다.
- 기존 패널과 값 하나하나의 대조(표본만: 나라 인구, 울산 인구·다섯 산출·순위, 공항 1, 교역로 1, 렌즈 칸 값 1).
- `build_ridges.py` 의 바이트 단위 재현성, WAMIS 원자료가 없을 때의 갈래, `validate.py` 와의 궁합.
- 제호 한자의 세부 자형이 한국 표준 자형과 미세하게 다른지(일본 글꼴이다. 구조는 정자와 같다).
