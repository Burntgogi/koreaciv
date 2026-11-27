# 3단계 제작 명세 — 경제 산출과 살림 렌즈

상위 문서: `docs/DESIGN.md` §4(2026-11-26 개정), `docs/SPEC_PHASE1.md`. 자료 설명: `docs/ECON_DATA_REPORT.md`.

## 0. 작업 구역

| 경로 | 권한 |
|---|---|
| `data/build/econ/*.csv`, `data/raw/econ/` | **읽기만.** 다른 작업자가 `business.csv`를 보강하는 중이라 빌드 도중 바뀔 수 있다 |
| `pipeline/build_econ.py`, `pipeline/lib/`, 기존 `build_*.py`, `validate.py` | 만들고 고친다 |
| `site/` | 고친다 |

건드리지 않는 것: `pipeline/collect_*.py`, `data/raw/`, `docs/DESIGN.md`, `docs/ECON_DATA_REPORT.md`.

## 1. 입력

정리표는 모두 같은 열을 쓴다: `sgg_code_raw, sgg_name_raw, sgg_code_now, sido_now, year, indicator, industry, value, unit, basis, source_id`. `sgg_code_now`가 현재 5자리 코드다. 빈 `value`는 비공개 또는 자료 없음이며 0이 아니다. `unmapped.csv`는 현재 코드에 대응시키지 못한 행이다.

통계는 시 단위로 공표되는 것이 많다(일반구가 있는 시는 시 전체 값만 있음). 정리표에서 시 전체 값이 어떤 코드로 들어 있는지 먼저 확인하고, 1단계의 도시 묶음 규칙으로 도시에 붙인다. 시 값을 일반구에 나누지 않는다.

## 2. 산출 — `build_econ.py`

### 2.1 산업 이름 통일

`grdp.csv`의 `industry`는 시도마다 표기가 다르다("금융 및 보험업"/"금융보험업", 띄어쓰기 차이, 세종의 "총생산액"/"총부가가치"). 표준 키 19개로 가는 대응표를 코드에 두고, 대응표에 없는 이름이 나오면 빌드 오류로 낸다.

표준 키: `agriculture, mining, manufacturing, utilities, construction, wholesale_retail, transport, accommodation, information, finance, real_estate, business_services, public_admin, education, health, culture_other, net_taxes, gva, grdp`.

### 2.2 다섯 산출

| 산출 | 계산 | 단위 |
|---|---|---|
| `food` | `agriculture` | 원 |
| `production` | `manufacturing + construction + mining` | 원 |
| `gold` | `grdp` | 원 |
| `science` | `information + business_services` | 원 |
| `culture` | `culture_other` | 원 |

- 도시마다 가장 최근 연도를 쓰고 `gdp_year`에 적는다. 도시 = 소속 시군구의 합(특별·광역시는 자치구 합, 시 단위로 공표된 곳은 그 값).
- 구성 산업 중 하나라도 비공개면 그 산출은 `null`이고, `gdp_undisclosed`에 빠진 산업을 적는다. 추정으로 메우지 않는다.
- GRDP가 없는 도시는 경제 필드 전체가 `null`이고 패널에 "자료 없음"으로 나온다.
- 시도·전국 값은 도시 합이 아니라 **소속 시군구 합**으로 내고, 연도가 섞이면 `gdp_year`를 `"2023 (세종 2024)"`처럼 적는다. 전국 합이 한국은행·국가데이터처의 전국 GDP와 다르다는 점(시도별 작성, 순생산물세 처리)을 연감에 적는다. 전국 공식값을 따로 입력하지 않는다.

### 2.3 도시에 더할 필드

```
yields{food, production, gold, science, culture}, gdp, gdp_year, gdp_by_industry{표준 키: 원},
gdp_undisclosed[], gdp_per_capita, gdp_growth{from, to, rate},
wage{per_filer, year}, housing{sale_per_m2, sale_median, jeonse_median, months, trades},
employment{rate, unemployment, period}, fiscal_independence, 
workers{total, manufacturing, year}, farm{households, population, paddy_ha, field_ha, year},
ranks{gdp, gdp_per_capita, food, production, science, culture, wage, housing}
```

- `gdp_per_capita`: GRDP ÷ 같은 해 12월 주민등록 인구(1단계에서 받은 시계열). 생산지 기준 GRDP를 등록 인구로 나눈 값이라 통근 유입이 큰 도시가 높게 나온다는 설명을 붙인다.
- `gdp_growth`: 같은 도시의 5년 전(없으면 가장 이른 연도)과 최신 연도의 명목 증가율. 연도를 함께 적는다.
- `housing`: 12개월치 월별 중위값이 들어 있다. 12개월의 거래량 가중이 가능하면 그렇게, 정리표에 거래 건수가 없으면 월 중위값의 중위값을 쓰고 방식을 설명에 적는다.
- `peers`(닮은 도시)를 인구·고령 비율에 더해 1인당 GRDP와 산업 구성까지 반영하도록 고친다. 경제 자료가 없는 도시는 기존 방식 그대로.

## 3. 렌즈 추가

1단계 렌즈는 그대로 두고 묶음을 더한다. 시군구 값을 그 시군구의 칸에 칠한다. 시 단위 값만 있는 곳은 소속 일반구 칸 전부에 같은 값을 칠한다.

| 묶음 | id | 정의 | 자료 | 방향 |
|---|---|---|---|---|
| 살림 | `gdp_pc` | 1인당 GRDP | grdp, 주민등록 | 높을수록 좋음 |
| 살림 | `wage` | 근로소득자 1인당 총급여 (주소지) | income | 높을수록 좋음 |
| 살림 | `home` | 아파트 ㎡당 매매 중위가격 | housing | 중립 |
| 살림 | `jeonse` | 아파트 전세 중위가격 | housing | 중립 |
| 살림 | `employment` | 고용률 | employment | 높을수록 좋음 |
| 살림 | `fiscal` | 재정자립도 | finance | 높을수록 좋음 |
| 살림 | `assistance` | 기초생활보장 일반수급자 ÷ 주민등록 인구 | assistance | 낮을수록 좋음 |
| 산업 | `manufacturing_share` | GRDP 중 제조업 비중 | grdp | 중립 |
| 산업 | `farm_share` | GRDP 중 농림어업 비중 | grdp | 중립 |
| 산업 | `top_industry` | 부가가치가 가장 큰 산업 (범주형, 공공행정·부동산 포함 전체에서) | grdp | — |
| 사람 | `fertility` | 합계출산율 | fertility | 높을수록 좋음 |
| 사람 | `migration` | 순이동률 (순이동 ÷ 인구, 천 명당) | migration | 중립, 0 중심 |
| 일상 | `single` | 1인 가구 비율 | households | 중립 |
| 일상 | `owner` | 자가 점유 비율 | tenure | 중립 |
| 일상 | `long_commute` | 통근·통학 60분 이상 비율 (구간 인원에서 직접 계산, 평균 추정 없음) | commute | 낮을수록 좋음 |
| 일상 | `doctors` | 인구 천 명당 의사 수 | doctors | 높을수록 좋음 |
| 배움 | `degree` | 15세 이상 내국인 중 대학(4년제 미만 포함) 졸업 이상 비율. 25세 이상 기준은 하위 연령 칸이 비공개라 쓰지 않는다는 점을 설명에 적는다 | education | 높을수록 좋음 |
| 신앙 | `religion` | 종교가 있는 인구 비율 (2015) | religion | 중립 |
| 신앙 | `religion_top` | 가장 많은 종교 (범주형, 2015) | religion | — |
| 땅 | `paddy` | 시군구 넓이 중 논 비율 | land | 중립 |

정리표를 열어 보고 정의대로 계산할 수 없는 렌즈는 만들지 말고, 왜 안 되는지 보고한다. 렌즈마다 기준 시점과 "어디서 센 값인지"(생산지/주소지/거주지)를 범례에 보여준다. 렌즈가 27개쯤 되므로 렌즈 선택 UI를 묶음별로 접고 펼 수 있게 고친다.

## 4. 화면

- **상단 띠**: 전국 다섯 산출(금은 조 원 단위)을 인구 지표 옆에 넣는다. 누르면 전국 보고서: 산업별 부가가치 막대, 시도별 순위.
- **도시 깃발**: 확대했을 때 인구 아래에 다섯 산출 아이콘과 값을 작게 보여준다. 전국 화면에서는 지금처럼 이름과 인구만.
- **도시 패널**: "자료 준비 중" 자리를 채운다. 다섯 산출과 전국 순위, 산업별 부가가치 가로 막대(19분류, 비공개는 "비공개"), 1인당 GRDP, 명목 증가율, 1인당 총급여, 아파트 매매·전세, 고용률, 재정자립도, 종사자(합계·제조업), 농가·논밭. 각 값 옆에 기준 연도.
- **시도 패널**: 같은 구성 + 소속 도시를 산출별로 정렬해 볼 수 있는 목록.
- **연감**: 산출 정의와 DESIGN §4의 한계 세 가지, 지표별 출처(`data/raw/econ/manifest.json`을 `sources.json`에 합친다), 덮은 범위.
- 금액 표기: `34.3조`, `8,120억` 꼴.
- 1단계에서 남은 흠도 고친다: 전국 화면에서 시도 이름이 도시 깃발에 가려지는 것, 제주가 아래 렌즈 띠에 걸리는 첫 화면 구도.

## 5. 검증 (기존 `validate.py`에 추가)

1. 도시마다 `gdp_by_industry`의 산업 합 + 순생산물세가 `grdp`와 0.5% 안에서 맞는다(비공개가 있는 도시는 제외하고 그 수를 출력).
2. 도시 GRDP 합 = 시군구 GRDP 합(같은 연도 선택 규칙에서).
3. 다섯 산출이 모두 `null`이 아닌 도시 수, GRDP가 있는 도시 수를 출력한다. GRDP가 있는 도시는 160곳 이상이어야 한다.
4. 렌즈마다 값이 있는 육지 칸 비율을 출력하고, 50% 미만이면 실패.
5. 비율 렌즈 값이 0–100% 범위 안. 1인당 값이 음수가 아님.
6. 정리표의 빈 값이 0으로 바뀌어 들어간 곳이 없다(원자료 빈 칸 수와 산출 `null` 수를 대조).
7. 1단계 검증 10개가 그대로 통과한다.

## 6. 보고

헤드리스 브라우저로 도시 패널(울산, 서울), 1인당 GRDP 렌즈, 최대 산업 렌즈, 전국 보고서를 찍어 `docs/screenshots/`에 `2x_` 접두로 둔다. 보고에는 validate.py 실제 출력, 산출이 빈 도시 목록과 이유, 만들지 못한 렌즈와 이유, 명세에서 벗어난 점, 눈에 띄게 이상한 값(예: 1인당 GRDP 상·하위 5곳)을 담는다.
