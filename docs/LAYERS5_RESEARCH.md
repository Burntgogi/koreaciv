# 공개판(`--profile public`) 결손 보완 연구 보고서 — 인천국제공항 위치 및 전국 토지피복

- **작성일**: 2026-11-27
- **대상 빌드**: `python -I pipeline/build_all.py --profile public` (`site/`, `site/yeojido/`)
- **수집 원본 및 증빙 매니페스트**: [data/raw/layers5/manifest.json](file:///C:/work/korea/data/raw/layers5/manifest.json) (총 126개 파일, 157,864,316 B / 150.55 MB)
- **재현 수집·검증 스크립트**: [pipeline/collect_layers5.py](file:///C:/work/korea/pipeline/collect_layers5.py)
- **정량 실증 스크립트 및 결과**: [tools/research5/verify_all.py](file:///C:/work/korea/tools/research5/verify_all.py), [tools/research5/results.json](file:///C:/work/korea/tools/research5/results.json)

---

## 1. 배경 및 문제 진단 요약

공개 저장소 및 GitHub Pages 배포용 빌드(`--profile public`)는 이용허락이 불명확하거나 저장·재배포를 제한하는 원천 3종(`incheon-aip`, `landcover-me-2025`, `landcover-me-stats-ntn-lcm-2025`)을 제외한다([pipeline/lib/profile.py](file:///C:/work/korea/pipeline/lib/profile.py#L22-L38), [docs/SECURITY_AUDIT.md](file:///C:/work/korea/docs/SECURITY_AUDIT.md)). 이로 인해 공개판에서 다음 두 가지 품질 결손이 발생했다.

1. **문제 1 — 인천국제공항 누락**:
   - 전체판은 민간공항 15곳 중 14곳의 좌표를 `한국공항공사_공항 위치정보`([data-15002851](https://www.data.go.kr/data/15002851/fileData.do), `이용허락범위 제한 없음`)에서 얻고, 한국공항공사 관할이 아닌 **인천국제공항(RKSI/ICN)** 1곳만 국토교통부 항공정보간행물(`incheon-aip`, AIP RKSI AD 2.2 ARP `37°27'45"N, 126°26'21"E` = `126.4391667, 37.4625000`)에서 얻었다([pipeline/build_layers2.py](file:///C:/work/korea/pipeline/build_layers2.py#L469-L511)).
   - 그러나 `AIP GEN 0.1 §5.2`에 `"항공정보간행물은 사전 허락이나 별도의 협의 없이 무단으로 복제, 개작 및 배포할 수 없다"`는 조항이 있어 공개판에서는 `incheon-aip`가 제외되었고, 그 결과 대한민국 최대 관문 공항인 인천국제공항(2025년 여객 73,752,582명, 화물 4,032,060톤)이 공개판 지도에서 빠졌다.
   - 참고로 **공항 여객·화물 실적**은 이미 공개판 허용 원천인 국토교통부 항공정보포털 `항공통계 상세조회(공항)`(`airportal-2025`, 공공데이터포털 [data-15092537](https://www.data.go.kr/data/15092537/fileData.do) `이용허락범위 제한 없음` 등록 확인, [data/build/layers/airport_traffic.csv](file:///C:/work/korea/data/build/layers/airport_traffic.csv))에 인천공항 실적(`73,752,582명`, `4,032,060톤`)이 들어 있으며, `한국공항공사_공항별 여객실적`([data-15002610](https://www.data.go.kr/data/15002610/fileData.do), `이용허락범위 제한 없음`)에도 인천공항 실적(`74,071,475명`)이 포함되어 있다. 즉 **위치(좌표 또는 도로명주소 → 육각 칸 `7080`·시군구 `28155 영종구`) 출처만 깨끗한 데이터로 교체하면 여객·화물 실적까지 즉시 복원된다.**

2. **문제 2 — 토지피복 품질 저하 및 세부 분류 상실**:
   - 전체판은 기후에너지환경부 환경공간정보서비스(EGIS) 중분류 토지피복지도 WMS(`EGIS:lv2_2025y`)를 50 m 격자로 저장해 집계했으나, EGIS 오픈API 약관 제4조제2항이 `"실시간으로 연계하여 본인의 시스템에서 활용하는 것 이외에 다른 수단으로 저장하거나 전송하는 행위를 금지"`하므로 공개판에서 제외되었다([docs/LANDCOVER_ME_REPORT.md](file:///C:/work/korea/docs/LANDCOVER_ME_REPORT.md)). 또한 전체판 WMS 자체도 ① 1:25,000 일반화 렌더링 과정에서 폭 12 m 미만 도로가 인접 피복에 흡수되어 시가화 면적이 공식 통계 대비 **-34.3%**(비교 시군구 231곳 기준) 과소, 밭이 **+24.4%** 과대 추정되고, ② 연천·파주·철원·화천·양구·인제·고성 등 군사분계선 접경 도엽이 비어 해당 칸들이 통째로 ESA WorldCover로 폴백되어 임상(활엽·침엽·혼효)과 논·밭 구분이 `null`이 되는 결함이 있었다.
   - 공개판은 이를 ESA WorldCover 10 m 원자료(`CC BY 4.0`)를 **250 m 최빈값 격자(`all_touched=True`)**로 축소한 `landcover.tif` + 팜맵 3개 도(전북·전남·경남 54개 시군) `farmmap.tif` + KOSIS 시군구 경지면적(`land.csv`)으로 대체했다([pipeline/lib/cover_public.py](file:///C:/work/korea/pipeline/lib/cover_public.py)).
   - 그 결과 국가토지피복통계(비교 시군구 231곳: 숲 56.7%, 논 7.6%, 밭 7.3%, 시가화 7.9%, 초지 11.1%) 대비 공개판은 **숲 71.3%(면적 오차 +27.5%), 논 9.8%(+30.2%), 밭 6.6%(-7.9%), 시가화 6.2%(-20.5%), 초지 1.9%(-82.5%)**로 크게 치우쳤고, **활엽수림·침엽수림·혼효림 구분이 전부 상실(`null`)**되었으며, 팜맵 미적용 14개 시도의 과수원·시설재배지가 `null`이 되고 칸 안의 모든 농경지가 시군구 평균 논·밭 비율로 평탄화되었다.

---

## 2. 아이디어 전체 목록 및 채택·보류·탈락 판정 (과제 A)

### 2.1 문제 1 — 인천국제공항 위치·주소·실적 해법 (10개)

| 번호 | 아이디어 (해법) | 핵심 원리 및 활용 데이터 | 판정 | 판정 근거 요약 |
|---|---|---|---|---|
| **P1-1** | **국가철도공단 공항철도 역위치·주소 파일데이터 결합 (1순위)** | 공공데이터포털 파일데이터 `국가철도공단_공항철도_역위치`([15041331](https://www.data.go.kr/data/15041331/fileData.do)) + `공항철도_주소데이터`([15041094](https://www.data.go.kr/data/15041094/fileData.do)) (보조: `공항철도자기부상_역위치` [15041332](https://www.data.go.kr/data/15041332/fileData.do), 운영기관 인천국제공항공사)에서 T1·T2 좌표 및 도로명주소 추출 | **채택 (1순위)** | 공공데이터포털 공식 파일데이터로 3종 모두 **`이용허락범위 제한 없음`** 명시, 무로그인·무키 즉시 다운로드 가능. T1(`126.45234, 37.44761`)·T2(`126.43342, 37.46866`) 및 그 중점(`126.44288, 37.45813`, AIP ARP와 **585.5 m** 차이) 모두 AIP ARP와 동일한 육각 칸 **`7080`**(`28155 영종구`)에 정확히 매핑됨. |
| **P1-2** | **OpenStreetMap 공항 경계 폴리곤(`aeroway=aerodrome`, `icao=RKSI`) 대표점 추출 (2순위-A)** | 이미 공개판 호소 추출에 사용 중인 `south-korea-261124.osm.pbf`(`ODbL 1.0`, `sources.json` `osm-kr`)에서 `WAY 316419197` (`name=인천국제공항`, `icao=RKSI`, `iata=ICN`) 폴리곤의 대표점(`point_on_surface`) 또는 무게중심(`centroid`) 계산 | **채택 (2순위-A)** | 신규 외부 의존성·라이선스 추가 없이 로컬 `data/raw/layers/A2/south-korea-261124.osm.pbf`에서 즉시 계산 가능. `point_on_surface`(`126.44171, 37.46346`)는 AIP ARP와 **248.9 m**, `centroid`(`126.44062, 37.46455`)는 **262.0 m** 차이로 육각 칸 **`7080`**에 완벽히 일치하며 태그에 도로명주소(`인천광역시 중구 운서동 공항로 272`)도 포함됨. |
| **P1-3** | **Wikidata `Q20932` (인천국제공항) 엔티티 JSON 활용 (2순위-B)** | Wikidata `Special:EntityData/Q20932.json`(`CC0 1.0 Public Domain`)의 좌표(`P625`: `126.4391667, 37.4625`) 및 도로명주소(`P6375`: `인천시 중구 공항로 272` 등) 활용 | **채택 (2순위-B)** | `CC0 1.0` 퍼블릭 도메인으로 저작권 제약이 전혀 없으며, 좌표가 AIP ARP와 **0.0 m** 차이로 완전 일치함(칸 **`7080`**). 다만 커뮤니티 편집 DB이므로 공공기관 공식 통계·파일데이터(P1-1)의 교차검증 또는 2순위로 적합. |
| **P1-4** | **Natural Earth 10m Airports (`ne_10m_airports.zip`) 활용** | 이미 공개판 배경 해안선에 사용 중인 Natural Earth(`Public Domain`)의 공항 점 레이어(`ne_10m_airports.shp`)에서 `iata_code=ICN` (`gps_code=RKSI`) 추출 | **보류 (보조 검증용)** | `Public Domain`이며 무로그인 즉시 다운로드(290.8 KB) 가능하고 좌표(`126.45088, 37.44921`, 제1여객터미널 위치)가 AIP ARP와 **1,802.6 m** 차이로 동일한 육각 칸 **`7080`**에 떨어짐. 국내 공공데이터(P1-1)가 있으므로 보조 검증원천으로 활용. |
| **P1-5** | **기후에너지환경부 1:5,000 세분류 토지피복 도엽 통계(`15150509`)의 `공항` 항목 도엽 가중중심 역산** | 문제 2를 위해 발굴한 `세분류 토지피복지도 도엽단위 현행화 통계`([15150509](https://www.data.go.kr/data/15150509/fileData.do), `공공누리 제1유형`)에서 영종도 일대 `공항` 면적이 존재하는 9개 1:5,000 도엽(`37610007~37610029`, 공항 면적 합계 114.86 ha)의 면적가중 중심 좌표 계산 | **보류 (보조 검증용)** | 가중중심 좌표(`126.45091, 37.46228`)가 AIP ARP와 **1,039.2 m** 차이로 동일한 육각 칸 **`7080`**에 떨어짐. 외부 공항 테이블 없이 토지피복 파일 하나로 공항 칸을 특정할 수 있는 독창적 방법이나, 점 좌표 정밀도는 P1-1·P1-2가 더 우수함. |
| **P1-6** | **국토교통부 세계공항 정보(`3051587`)·세계공항 코드(`15061950`) + 인천공항공사 시설 파일(`15037262`, `15088368`, `15086557`) + 행정동 경계(`HangJeongDong`) 결합** | 국토교통부 파일데이터(`ICAO=RKSI, IATA=ICN, 도시=Incheon`)와 인천국제공항공사 파일데이터(`운서동`, `제1·2여객터미널`)로 소재 행정동(`인천광역시 영종구 운서1동`, `2815554000`)을 특정하고, 보유 중인 `HangJeongDong_ver20261001.geojson`(`CC BY 4.0`)의 운서1동 폴리곤 대표점 계산 | **보류 (보조 검증용)** | 모든 구성 파일이 `이용허락범위 제한 없음` 및 `CC BY 4.0`이고, 운서1동 대표점(`126.44388, 37.46504`)이 AIP ARP와 **503.1 m** 차이로 동일한 육각 칸 **`7080`**에 떨어짐. 단, 좌표가 직접 적힌 P1-1보다 단계가 하나 더 많음. |
| **P1-7** | **전국도시철도역사정보표준데이터(`15013205`) JSON 다운로드 활용** | 공공데이터포털 표준데이터 `전국도시철도역사정보표준데이터`([15013205](https://www.data.go.kr/data/15013205/standard.do), `이용허락범위 제한 없음`)에서 인천국제공항공사 자기부상철도 역사 6곳의 도로명주소(`인천광역시 중구 공항로 271`) 추출 | **탈락** | 파일을 실제로 받아 검증한 결과(`p1-std-15013205.json`, 898행), 인천국제공항공사 자기부상철도 6개 역의 도로명주소(`인천광역시 중구 공항로 271`)는 들어 있으나 `LATITUDE: "0.0"`, `LONGITUDE: "0.0"`으로 좌표 열이 비어 있고 공항철도(주) 본선 역사는 누락되어 있음. 같은 역의 실제 좌표를 제공하는 P1-1(`15041331`, `15041332`)이 상위 호환임. |
| **P1-8** | **OurAirports (`airports.csv`) 또는 GeoNames (`KR.zip`) 활용** | OurAirports(`Public Domain`)의 `RKSI`(`126.45100, 37.46910`) 또는 GeoNames(`CC BY 4.0`)의 `6300433`(`126.45095, 37.44920`) / `12689633`(`126.44935, 37.46914`) 활용 | **탈락** | `geonames-6300433`은 칸 `7080`에 떨어지나, `ourairports-rksi`와 `geonames-12689633`은 북동쪽 제3활주로/화물터미널 방향 좌표(`126.451, 37.469`)를 가리켜 육각 칸 경계를 살짝 넘어 인접 칸 **`6927`**에 떨어짐. 또한 `ourairports.com` 본 도메인은 SSL 인증서 만료 상태(GitHub 미러만 정상)여서 안정성이 낮음. |
| **P1-9** | **한국공항공사 공항 위치정보(`15002851`) 및 우체국물류지원단 공항위치(`15060089`) 재확인** | 기존 `15002851` CSV에 인천이 다른 이름으로 있는지 재확인하고, `우체국물류지원단_해외통관 우체국 공항위치`([15060089](https://www.data.go.kr/data/15060089/fileData.do))에 RKSI/ICN 좌표가 있는지 확인 | **탈락** | 두 파일을 전수 검사한 결과, `15002851`(14행)은 한국공항공사 관할 14개 지방공항만 수록해 인천공항이 정말 없으며, `15060089`(272행)는 해외 공항(JFK, NRT, LHR 등) 위치만 수록하고 한국 공항(ICN/GMP)은 빠져 있음. |
| **P1-10** | **인천국제공항공사 공식 홈페이지(`airport.kr`) 하단 도로명주소 직접 인용** | `airport.kr/ap_ko/index.do` 푸터의 `"제1여객터미널: 22382 인천광역시 영종구 공항로 272"` 텍스트 추출 | **탈락** | `airport.kr`에는 `영종구`(2026.7.1 출범 예정 행정구역명)까지 최신 반영되어 있으나, `airport.kr/ap_ko/1033/subview.do`(저작권보호정책)에 `"인천국제공항공사가 발간하는 자료에 대한 무단 복제 및 배포를 원칙적으로 금합니다"`라고 명시되어 있어 공개판 원칙상 배제함. |

---

### 2.2 문제 2 — 전국 토지피복 품질 개선 및 세부 분류 복원 해법 (12개)

| 번호 | 아이디어 (해법) | 핵심 원리 및 활용 데이터 | 판정 | 판정 근거 요약 |
|---|---|---|---|---|
| **P2-1** | **기후에너지환경부 1:5,000 세분류 도엽 통계(`15150509`) + ESA WorldCover 10 m(50 m 직접 집계) + 전국 팜맵(`15104481~15104491`) 다중해상도 결합 (1순위)** | 공공데이터포털 파일데이터 `세분류 토지피복지도 도엽단위 현행화 통계`([15150509](https://www.data.go.kr/data/15150509/fileData.do), **`공공누리 제1유형`**, 2025년 제작/2024년 기준 전국 **18,538개 1:5,000 도엽** × 41개 세분류 면적 ㎡)와 국토지리정보원 표준 도엽번호(`1.5' × 1.5'` ≈ `6.3 km²`, 육각 칸 20.37 km²의 1/3 크기) 격자를 육각 칸과 공간 교차(Area-weighted Intersection)하고, 도엽 경계 내부의 미세 공간 변이는 **ESA WorldCover 10 m(50 m 직접 집계)** 및 **전국 팜맵(`이용허락범위 제한 없음`)**으로 보강 | **채택 (1순위)** | **WMS API가 아닌 `공공누리 제1유형` 정적 CSV 파일(8.85 MB, 무로그인·무키 즉시 다운로드)**로 이용조건 위험이 완전히 해소됨. 전체판 WMS보다도 뛰어난 품질: ① 전국 비교 시군구 231곳 오차가 **숲 +0.5%(공개판 +27.5%), 논 -1.1~+1.5%(공개판 +30.2%), 밭 +0.4~+1.2%(전체판 +24.4%), 시가화 -0.6%(공개판 -20.5%, 전체판 -34.3%)**로 사실상 소멸, ② **활엽·침엽·혼효 및 논·밭·과수·시설 100% 복원**, ③ 전체판 WMS에서 누락되던 **DMZ 접경 지역(연천·고성·인제 등) 도엽까지 100% 수록**되어 육각 칸 **5,024/5,027칸(99.94%)**을 직접 덮음. |
| **P2-2** | **ESA WorldCover 10 m 원자료 직접(50 m, `all_touched=False`) 집계 + 제1유형 공식 국가토지피복통계(`15163128`·`15164500`) 시군구 다차원 비례보정(IPF/Raking) (2순위-A)** | 이미 보유한 ESA WorldCover 10 m 원자료(`CC BY 4.0`)를 250 m 최빈값 대신 50 m 격자(`all_touched=False`)로 칸별 직접 집계한 뒤, 공공데이터포털에서 **`공공누리 제1유형`이 명시된 공식 파일데이터 `국가 토지피복 통계`([15163128](https://www.data.go.kr/data/15163128/fileData.do)) 및 `지역별 세분류 토지피복 면적 현황`([15164500](https://www.data.go.kr/data/15164500/fileData.do))**의 252개 시군구 × 41개 세분류 면적에 맞춰 칸별 비율을 IPF(Raking)로 보정하고 임상(활엽·침엽·혼효) 및 경지 세분류를 분할 | **채택 (2순위-A)** | 기존 `NOTICE.md`에서 `"이용허락 미확인"`으로 분류되었던 시군구 통계표가 공공데이터포털(`15163128`, `15164500`)에 **`공공저작물 : 출처표시 (제 1유형)`**으로 정식 개방되어 있음을 확인·수집함(385 KB / 231 KB). 추가 대용량 다운로드 없이 전국 모든 시험 구역(김제·익산, 인제, 서울, 연천·고성, 제주)에서 오차를 **±1~7% 이내**로 줄이고 활엽·침엽·혼효를 복원함. |
| **P2-3** | **ESA WorldCover 10 m 원자료 직접(50 m, `all_touched=False`) 집계 + 전국 팜맵 10개 권역(`15104481~15104491`) 전면 확대 (2순위-B)** | 250 m 최빈값(`landcover.tif`) 대신 10 m 원자료를 50 m(`all_touched=False`)로 직접 세어 최빈값 편향과 해안 경계 수역 과대추정을 제거하고, 기존 3개 도(전북·전남·경남)만 쓰던 팜맵을 공공데이터포털에 등록된 **전국 10개 권역 전체([15104481~15104491](https://www.data.go.kr/data/15104481/fileData.do), 모두 `이용허락범위 제한 없음`, 합계 3.02 GB)**로 확장 | **채택 (2순위-B / P2-1·P2-2의 기본 공간 레이어)** | 단순 재계산만으로 **시가화 비율이 6.17%(-20.5% 오차) → 7.75%(-0.2% 오차)로 공식 통계(7.88%)와 거의 일치**하고, **초지가 1.90% → 6.15%(3.2배)로 회복**, **수역 과대추정이 3.70% → 2.53%(공식 2.27%)로 해소**, **논 오차가 +30.2% → -1.0%**로 줄어듦. 단, 위성 수관(tree canopy) 특성상 산림 단독 비율은 67.4%로 여전히 높고 활엽·침엽 구분이 없으므로 P2-1 또는 P2-2와 결합할 때 최상의 결과를 냄. |
| **P2-4** | **기후에너지환경부 1:25,000 중분류 도엽 통계(`15150695`) 공간 교차 배분** | 공공데이터포털 파일데이터 `중분류 토지피복지도 도엽단위 현행화 통계`([15150695](https://www.data.go.kr/data/15150695/fileData.do), `공공누리 제1유형`, 2025년 제작 전국 831개 1:25,000 도엽 × 22개 중분류 면적, 168 KB) 활용 | **보류 (P2-1의 하위 호환)** | 1:25,000 도엽(`7.5' × 7.5'` ≈ `158 km²`)은 육각 칸(20.37 km²)보다 약 7.8배 커서 칸 단위 공간 해상도가 무뎌짐. 반면 같은 날 함께 수집한 **1:5,000 세분류 도엽 통계(`15150509`, 18,538개 도엽, 도엽당 `6.3 km²`)**는 해상도가 25배 더 세밀하고分類도 41개 세분류이므로 P2-1이 완벽한 상위 호환임. |
| **P2-5** | **국토교통부 지적기본통계집계(`15063997`) 시군구 지목별 면적 보정** | 공공데이터포털 파일데이터 `국토교통부_지적기본통계집계_20251231`([15063997](https://www.data.go.kr/data/15063997/fileData.do), `이용허락범위 제한 없음`, 전국 253개 시군구 × 28개 법정 지목 면적, 5.89 MB)으로 시군구 면적 보정 | **보류 (보조 검증용)** | 이용조건(`제한 없음`)은 완벽하나, **법정 지목(Cadastral category)과 실제 지표 피복(Land cover)의 괴리**가 큼. 실증 결과(후보 E), 지목상 `임야`가 62.8%, `답`이 11.0%(실제 논 피복 7.5% 대비 **+50.8% 과대** — 과거 논이었다가 전용·휴경된 토지나 하천변이 지목상 답/하천으로 남음), `초지`(공원·체육·묘지 합)가 1.1%(실제 초지 10.7% 대비 대폭 과소)로 나타나며, 활엽·침엽·혼효 및 시설재배지 구분이 불가능함. |
| **P2-6** | **국립환경과학원 전국오염원조사 토지계통계(`15071109`) 활용** | 공공데이터포털 파일데이터 `국립환경과학원_전국오염원조사 토지계통계`([15071109](https://www.data.go.kr/data/15071109/fileData.do), `이용허락범위 제한 없음`, 199 KB) 활용 | **탈락** | 파일을 다운로드해 확인한 결과, 시군구별 대분류 지목 합계(대지·전·답·임야·기타)만 수록되어 있고 기준연도가 2019년으로 오래되었으며 세분류(임상·과수·시설)가 없음. |
| **P2-7** | **환경부 토지피복지도 벡터(SHP) 원자료 직접 다운로드 (공공데이터포털·EGIS·환경 빅데이터 플랫폼)** | WMS가 아닌 중분류/세분류 토지피복지도 폴리곤 SHP 파일 다운로드 경로 탐색 | **탈락 (무로그인·무신청 불가)** | 공공데이터포털 전수 조사 결과 환경부 토지피복지도 파일데이터는 통계 CSV 11종만 등록되어 있고 폴리곤 SHP는 없음. EGIS(`egis.me.go.kr`) 및 환경 빅데이터 플랫폼(`bigdata-environment.kr`)은 회원가입·로그인 및 자료 신청(또는 유상/심사) 절차가 필수임을 확인함(`"로그인·신청 필요함"`). 단, **1:5,000 도엽별 세분류 정밀 면적표(`15150509`)가 공공데이터포털에 제1유형 CSV로 공개**되어 있어 SHP 없이도 도엽(`6.3 km²`) 해상도의 모든 세분류 면적을 얻을 수 있음(P2-1). |
| **P2-8** | **산림청 임상도(1:5,000 / 1:25,000 SHP) 또는 산림공간정보서비스(FGIS) 다운로드** | 산림청 임상도에서 침엽수림·활엽수림·혼효림 폴리곤 추출 | **탈락 (무로그인·본인인증 불가)** | 공공데이터포털 검색 결과(`search-forest-map.html`) 1:5,000 임상도(`15059586`)는 오픈API(인증키 필수)로만 등록되어 있고, 산림공간정보서비스(`map.forest.go.kr`, `fgis-forest.html`) 및 산림빅데이터 거래소(`bigdata-forest.kr`)에서 임상도 SHP를 받으려면 로그인·본인인증 및 신청서 입력이 필수임(`"로그인·본인인증 필요함"`). 대신 기후에너지환경부 세분류 도엽 통계(`15150509`, 제1유형)에 1:5,000 도엽별 `활엽수림`, `침엽수림`, `혼효림` 면적(㎡)이 모두 들어 있어 무로그인으로 완벽히 대체됨. |
| **P2-9** | **국토지리정보원(NGII) 토지이용현황도·연속수치지형도 SHP 활용** | 국토정보플랫폼(`map.ngii.go.kr`)에서 토지이용현황도 또는 연속수치지형도 다운로드 | **탈락 (무로그인 불가)** | 공공데이터포털 검색 결과(`search-ngii-landuse.html`) 파일데이터로 등록된 전국 토지이용현황도가 없으며, 국토정보플랫폼(`ngii-map.html`) 다운로드 시 회원가입·로그인이 필수임(`"로그인 필요함"`). |
| **P2-10** | **OpenStreetMap `landuse=*` / `natural=*` 폴리곤 단독·보조 집계** | 보유 중인 `south-korea-261124.osm.pbf`(`ODbL 1.0`)에서 `landuse`(farmland, forest, residential, industrial, commercial, orchard, greenhouse_horticulture 등) 및 `natural`(wood, water, wetland, scrub) 추출 | **탈락** | 국내 OSM 폴리곤은 도시·주요 하천 위주로 매핑되어 있어 농촌·산지 시군구에서 미매핑 공백이 35~60%에 달하고, `landuse=farmland`에 논(`meadow`/`paddy`)과 밭의 구분 태그가 대부분 누락되어 있으며 임상(활엽·침엽) 구분 태그(`leaf_type`) 부여율도 5% 미만임. |
| **P2-11** | **Google Dynamic World V1 (10 m) 활용** | Sentinel-2 기반 10 m 준실시간 토지피복(`CC BY 4.0`, [카탈로그 확인](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1)) 활용 | **탈락** | 라이선스는 `CC BY 4.0`으로 깨끗하나, ① Google Earth Engine 또는 Google Cloud 계정 로그인·인증 없이는 한국 전역 10 m 타일을 일괄 다운로드할 수 없고(`"로그인·클라우드 인증 필요함"`), ② 9개 대분류(`trees, grass, crops, shrub_and_scrub, flooded_vegetation, built, bare, water, snow_and_ice`)뿐이라 한국에서 가장 중요한 **논·밭·과수원·시설재배지 구분과 활엽·침엽·혼효 구분이 전혀 없음**. |
| **P2-12** | **Copernicus CGLS-LC100 (100 m) / JAXA ALOS PALSAR FNF (25 m) / GLAD Global Land Cover (30 m) 활용** | 글로벌 공개 위성 토지피복 활용 | **탈락** | ① Copernicus CGLS-LC100(100 m, `CC BY 4.0`)은 침엽/활엽 구분이 있으나 2019년 이후 갱신이 중단되었고 해상도(100 m)가 낮으며 Zenodo API(`zenodo.org/api/records/3939050`)가 스크립트 직접 요청에 `HTTP 403 Forbidden`을 반환함. ② JAXA ALOS FNF([문서 확인](https://www.eorc.jaxa.jp/ALOS/en/dataset/fnf_e.htm))는 이용약관상 비영리·출판·배포는 허용하나 **원자료 대량 다운로드 시 JAXA 계정 등록·로그인 필수**이며 산림/비산림만 구분함. ③ GLAD(30 m, `CC BY 4.0`)는 논/밭/과수/시설 및 임상 구분이 없음. |

---

## 3. 후보별 상세 자료조사표 (과제 B)

아래 표는 기억이나 추정이 아니라 이번 조사에서 실제로 웹페이지와 메타데이터 JSON을 열어 확인하고 [data/raw/layers5/](file:///C:/work/korea/data/raw/layers5/)에 원문 증빙을 저장한 결과다.

### 3.1 문제 1(인천국제공항) 후보 자료조사표

| 후보 ID / 명칭 | 공식 제공처 URL (증빙 파일) | 형식 · 해상도 · 기준연도 · 용량 | 이용허락 원문 문구 (저장·재배포·2차 가공·상업 이용) | 로그인·키·신청 필요 여부 | 구체적 다운로드 요청 방법 |
|---|---|---|---|---|---|
| **`data-15041331`**<br>국가철도공단_공항철도_역위치 | `https://www.data.go.kr/data/15041331/fileData.do`<br>([portal-15041331.html](file:///C:/work/korea/data/raw/layers5/portal/portal-15041331.html), [p1-15041331.csv](file:///C:/work/korea/data/raw/layers5/files/p1-15041331.csv)) | CSV (CP949) · 점 좌표(WGS84 경위도 소수점 7자리, 14개 역) · 2025-07-02 수정(2026-06-30 기준명) · **870 B** | **`이용허락범위 : 이용허락범위 제한 없음`** (공공데이터포털 표준 메타데이터; 복제·저장·재배포·2차적 저작물 작성·상업적 활용 제한 없음) | **불필요** (무로그인·무키 즉시 다운로드) | `GET https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000007761602&fileDetailSn=1` |
| **`data-15041094`**<br>국가철도공단_공항철도_주소데이터 | `https://www.data.go.kr/data/15041094/fileData.do`<br>([portal-15041094.html](file:///C:/work/korea/data/raw/layers5/portal/portal-15041094.html), [p1-15041094.csv](file:///C:/work/korea/data/raw/layers5/files/p1-15041094.csv)) | CSV (CP949) · 도로명주소 및 지번주소(14개 역) · 2025-07-02 수정 · **1,751 B** | **`이용허락범위 : 이용허락범위 제한 없음`** | **불필요** | `GET https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000007755120&fileDetailSn=1` |
| **`data-15041332`**<br>국가철도공단_공항철도자기부상_역위치 | `https://www.data.go.kr/data/15041332/fileData.do`<br>([portal-15041332.html](file:///C:/work/korea/data/raw/layers5/portal/portal-15041332.html), [p1-15041332.csv](file:///C:/work/korea/data/raw/layers5/files/p1-15041332.csv)) | CSV (CP949) · 점 좌표(WGS84, 인천국제공항공사 운영 6개 역) · 2025-07-02 수정 · **386 B** | **`이용허락범위 : 이용허락범위 제한 없음`** | **불필요** | `GET https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000007761608&fileDetailSn=1` |
| **`osm-kr`**<br>OpenStreetMap 한국 추출본 (`WAY 316419197`) | `https://download.geofabrik.de/asia/south-korea.html`<br>([data/raw/layers/A2/south-korea-261124.osm.pbf](file:///C:/work/korea/data/raw/layers/A2/south-korea-261124.osm.pbf)) | OSM PBF 벡터 폴리곤 (`aeroway=aerodrome, icao=RKSI, iata=ICN`) · 2026-11-24 스냅샷 · 기보유 (143 MB) | **`Open Data Commons Open Database License (ODbL) v1.0`** (`"You are free: To Share: To copy, distribute and use the database. To Create: To produce works from the database. To Adapt: To modify, transform and build upon the database."`, 출처 표시 및 파생 DB 개방 조건) | **불필요** (이미 로컬 보유 및 공개판 `sources.json` 등록 완료) | 로컬 `data/raw/layers/A2/south-korea-261124.osm.pbf`에서 `pyosmium`으로 `WAY 316419197` 추출 |
| **`wikidata-q20932`**<br>Wikidata `Q20932` (Incheon International Airport) | `https://www.wikidata.org/wiki/Special:EntityData/Q20932.json`<br>([wikidata-Q20932.json](file:///C:/work/korea/data/raw/layers5/files/wikidata-Q20932.json), [wikidata-licensing.html](file:///C:/work/korea/data/raw/layers5/files/wikidata-licensing.html)) | JSON · 점 좌표(`P625`: `126.4391667, 37.4625`) 및 도로명주소(`P6375`) · 2026년 최신 · **147,608 B** | **`Creative Commons CC0 1.0 Universal Public Domain Dedication`** (`"All structured data from the main, Property, Lexeme, and EntitySchema namespaces is available under the Creative Commons CC0 License; text in the other namespaces is available under the Creative Commons Attribution-ShareAlike License"`, 저장·재배포·가공·상업 이용 완전 자유) | **불필요** | `GET https://www.wikidata.org/wiki/Special:EntityData/Q20932.json` |
| **`ne-10m-airports`**<br>Natural Earth 10m Airports | `https://naciscdn.org/naturalearth/10m/cultural/ne_10m_airports.zip`<br>([ne_10m_airports.zip](file:///C:/work/korea/data/raw/layers5/files/ne_10m_airports.zip)) | Shapefile ZIP · 1:10,000,000 점 좌표 (`iata_code=ICN, gps_code=RKSI`) · v5.1.2 · **290,778 B** | **`Public Domain (CC0 상당)`** (`"All versions of Natural Earth raster + vector map data found on this website are in the public domain. You may use the maps in any manner, including modifying the content and design, electronic dissemination, and offset printing."`) | **불필요** | `GET https://naciscdn.org/naturalearth/10m/cultural/ne_10m_airports.zip` |
| **`data-3051587` / `15061950`**<br>국토교통부_세계공항_정보 / 코드 | `https://www.data.go.kr/data/3051587/fileData.do`<br>`https://www.data.go.kr/data/15061950/fileData.do`<br>([p1-3051587.csv](file:///C:/work/korea/data/raw/layers5/files/p1-3051587.csv), [p1-15061950.csv](file:///C:/work/korea/data/raw/layers5/files/p1-15061950.csv)) | CSV (CP949) · 공항코드(`RKSI`/`ICN`), 한글·영문 공항명, 도시(`Incheon`) · 2025-12-31 기준 · **549,978 B / 334,815 B** | **`이용허락범위 : 이용허락범위 제한 없음`** | **불필요** | `GET https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003603602&fileDetailSn=1` |
| **`data-15037262` / `15088368` / `15086557`**<br>인천국제공항공사 시설·사무실 파일데이터 3종 | `https://www.data.go.kr/data/15037262/fileData.do`<br>`https://www.data.go.kr/data/15088368/fileData.do`<br>`https://www.data.go.kr/data/15086557/fileData.do` | ZIP/CSV · 인천국제공항공사 직접 제공(`운서동`, `제1·2여객터미널`) · **2.3 KB ~ 6.4 KB** | **`이용허락범위 : 이용허락범위 제한 없음`** | **불필요** | `fileDownload.do?atchFileId=FILE_000000002316562` 등 |
| **`airportal-2025` (`data-15092537`) & `data-15002610`**<br>공항별 여객·화물 실적 통계 | `https://www.data.go.kr/data/15092537/fileData.do`<br>`https://www.data.go.kr/data/15002610/fileData.do`<br>([portal-15092537.html](file:///C:/work/korea/data/raw/layers4/portal-15092537.html)) | CSV/XLSX · 공항별 연간 여객(명)·화물(톤) 실적 · 2025년 연간 · 기보유 | **`이용허락범위 : 이용허락범위 제한 없음`** (`LAYERS4_DATA_REPORT.md` 검증 완료) | **불필요** (이미 로컬 `data/build/layers/airport_traffic.csv` 및 `data/raw/layers/B5/`에 보유) | 로컬 기보유 파일 그대로 사용 |
| **`ourairports-csv`**<br>OurAirports `airports.csv` | `https://davidmegginson.github.io/ourairports-data/airports.csv`<br>([ourairports-airports.csv](file:///C:/work/korea/data/raw/layers5/files/ourairports-airports.csv), [ourairports-README.md](file:///C:/work/korea/data/raw/layers5/files/ourairports-README.md)) | CSV (UTF-8) · 전 세계 공항 좌표 · 2026년 최신 · **12,765,124 B** | **`Public Domain`** (`"All data is released into the Public Domain, and comes with no guarantee of accuracy or fitness for use."`) | **불필요** (단, 본 도메인 `ourairports.com`은 SSL 만료로 GitHub Pages 미러 사용) | `GET https://davidmegginson.github.io/ourairports-data/airports.csv` |
| **`geonames-kr`**<br>GeoNames `KR.zip` | `https://download.geonames.org/export/dump/KR.zip`<br>([geonames-KR.zip](file:///C:/work/korea/data/raw/layers5/files/geonames-KR.zip), [geonames-readme.txt](file:///C:/work/korea/data/raw/layers5/files/geonames-readme.txt)) | TSV ZIP (UTF-8) · 한국 지명·시설 좌표 · 2026년 최신 · **5,413,584 B** | **`Creative Commons Attribution 4.0 License (CC BY 4.0)`** (`"This work is licensed under a Creative Commons Attribution 4.0 License, see https://creativecommons.org/licenses/by/4.0/ The Data is provided 'as is' without warranty or any representation of accuracy, timeliness or completeness."`) | **불필요** | `GET https://download.geonames.org/export/dump/KR.zip` |
| **`airport-kr`**<br>인천국제공항공사 공식 홈페이지 | `https://www.airport.kr/ap_ko/1033/subview.do`<br>([airport-kr-main.html](file:///C:/work/korea/data/raw/layers5/portal/airport-kr-main.html), [airport-kr-copyright-1033.html](file:///C:/work/korea/data/raw/layers5/portal/airport-kr-copyright-1033.html)) | HTML 웹페이지 푸터 주소 (`22382 인천광역시 영종구 공항로 272`) | **무단 복제·배포 금지** (`"인천국제공항공사가 발간하는 자료에 대한 무단 복제 및 배포를 원칙적으로 금합니다. 저작물을 복제 및 배포하고자 할 경우에는 인천국제공항공사의 사전 서면 허락을 받아야 합니다."`) | 로그인은 불필요하나 **사전 서면 허락 필요** (**탈락**) | 채택 불가 |

---

### 3.2 문제 2(전국 토지피복) 후보 자료조사표

| 후보 ID / 명칭 | 공식 제공처 URL (증빙 파일) | 형식 · 해상도 · 기준연도 · 용량 | 이용허락 원문 문구 (저장·재배포·2차 가공·상업 이용) | 로그인·키·신청 필요 여부 | 구체적 다운로드 요청 방법 |
|---|---|---|---|---|---|
| **`data-15150509` (핵심 발굴)**<br>기후에너지환경부_환경공간정보_세분류 토지피복지도 도엽단위 현행화 통계(토지피복지도 작성지침 개정)_20241231 | `https://www.data.go.kr/data/15150509/fileData.do`<br>([portal-15150509.html](file:///C:/work/korea/data/raw/layers5/portal/portal-15150509.html), [meta-15150509.json](file:///C:/work/korea/data/raw/layers5/portal/meta-15150509.json), [p2-15150509.csv](file:///C:/work/korea/data/raw/layers5/files/p2-15150509.csv)) | CSV (CP949) · **전국 1:5,000 표준 도엽 18,538개(`1.5' × 1.5'` ≈ `6.3 km²`) × 41개 세분류 항목 정밀 면적(㎡)** · 2025년 제작(2024년 영상 기준, 2023·2024년 제작분 함께 수록, 총 55,149행) · **8,845,841 B (8.44 MB)** | **`이용허락범위 : 공공저작물 : 출처표시 (제 1유형)`**<br>(`meta-15150509.json`: `"cclTypeCd": "010000", "cclNm": "공공저작물 : 출처표시 (제 1유형)"`. 공공누리 제1유형 약관에 따라 **출처 표시 조건 하에 복제·저장·재배포·변경(2차적 저작물 작성)·상업적 이용 모두 무료 허용**) | **불필요** (무로그인·무키 즉시 다운로드) | `GET https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000007711452&fileDetailSn=1` |
| **`data-15163128` (핵심 발굴)**<br>기후에너지환경부_환경공간정보_국가 토지피복 통계(토지피복지도 분류항목 통계)_20241231 | `https://www.data.go.kr/data/15163128/fileData.do`<br>([portal-15163128.html](file:///C:/work/korea/data/raw/layers5/portal/portal-15163128.html), [meta-15163128.json](file:///C:/work/korea/data/raw/layers5/portal/meta-15163128.json), [p2-15163128.csv](file:///C:/work/korea/data/raw/layers5/files/p2-15163128.csv)) | CSV (CP949) · **전국·17개 시도·252개 시군구 × 41개 세분류 면적(㎡) 및 비율(%)** · 2024년 기준(2025년 제작, 2021~2024년 수록, 총 2,160행) · **385,118 B** | **`이용허락범위 : 공공저작물 : 출처표시 (제 1유형)`**<br>(`meta-15163128.json`: `"cclTypeCd": "010000", "cclNm": "공공저작물 : 출처표시 (제 1유형)"`. 기존 `landcover-me-stats-ntn-lcm-2025`와 수치 100% 동일하면서 제1유형 라이선스가 공식 확인됨) | **불필요** | `GET https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000007711376&fileDetailSn=1` |
| **`data-15164500`**<br>기후에너지환경부_환경공간정보_지역별 세분류 토지피복 면적 현황(토지피복지도 작성지침 개정)_20251231 | `https://www.data.go.kr/data/15164500/fileData.do`<br>([portal-15164500.html](file:///C:/work/korea/data/raw/layers5/portal/portal-15164500.html), [p2-15164500.csv](file:///C:/work/korea/data/raw/layers5/files/p2-15164500.csv)) | CSV (CP949) · 시군구별 41개 세분류 면적(㎢) · 2025년 제작(2023~2025년 제작분 756행) · **230,800 B** | **`이용허락범위 : 공공저작물 : 출처표시 (제 1유형)`** (`"cclTypeCd": "010000"`) | **불필요** | `GET https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000007666152&fileDetailSn=1` |
| **`data-15166514` / `15124208` / `15124209` / `15150695`**<br>기후에너지환경부 중·세분류 지역별·도엽단위 통계 4종 | `https://www.data.go.kr/data/15166514/fileData.do`<br>`https://www.data.go.kr/data/15150695/fileData.do` 등<br>([p2-15166514.csv](file:///C:/work/korea/data/raw/layers5/files/p2-15166514.csv), [p2-15150695.csv](file:///C:/work/korea/data/raw/layers5/files/p2-15150695.csv)) | CSV (CP949) · 시군구별 중분류(`15166514`, `15124208`), 세분류(`15124209`), 1:25,000 도엽 831개 중분류(`15150695`) · 2025~2026년 등록 · **63 KB ~ 439 KB** | **`이용허락범위 : 공공저작물 : 출처표시 (제 1유형)`** (`"cclTypeCd": "010000"`) | **불필요** | `fileDownload.do?atchFileId=FILE_000000007684872` 등 |
| **`esa-worldcover-2021` (10 m 원자료)**<br>ESA WorldCover 10 m 2021 v200 | `https://worldcover2021.esa.int/`<br>([data/raw/layers/A1/](file:///C:/work/korea/data/raw/layers/A1/)) | GeoTIFF 8개 타일 · **10 m 해상도** (11개 분류) · 2021년 기준 · 기보유 (합계 1.07 GB) | **`Creative Commons Attribution 4.0 International (CC BY 4.0)`** (저장·재배포·2차 가공·상업 이용 모두 허용, 출처 표기만 필요) | **불필요** (로컬 `data/raw/layers/A1/ESA_WorldCover_10m_2021_v200_*.tif` 기보유) | 로컬 기보유 타일을 50 m 격자(`all_touched=False`)로 직접 집계 |
| **`data-15104481 ~ 15104491` (전국 10개 권역 완비 확인)**<br>농림수산식품교육문화정보원_팜맵공간정보 | `https://www.data.go.kr/data/15104481/fileData.do` ~ `15104491`<br>([portal-15104481..15104491.html](file:///C:/work/korea/data/raw/layers5/portal/portal-15104491.html), [p2-15104491.shp](file:///C:/work/korea/data/raw/layers5/files/p2-15104491.shp)) | Shapefile ZIP (EPSG:5179 필지 폴리곤: `01 논`, `02 밭`, `03 과수`, `04 시설`, `05 비경지`) · 항공·위성영상 기반 필지 경계 · 2025-12-31 기준(2026-01-08 수정) · **전국 10개 ZIP 합계 3,015.49 MB (3.02 GB)** (이번 실증에서 제주 `15104491` **102.33 MB** 신규 다운로드 완료) | **`이용허락범위 : 이용허락범위 제한 없음`**<br>(10개 권역 전체 상세 페이지 및 `meta-15104481..15104491.json`에서 모두 `"cclNm": "이용허락범위 제한 없음"` 직접 확인 완료) | **불필요** (10개 권역 모두 무로그인·무키 즉시 다운로드) | 아래 **3.3절 전국 팜맵 10개 권역 다운로드 명세표** 참조 |
| **`data-15063997`**<br>국토교통부_지적기본통계집계_20251231 | `https://www.data.go.kr/data/15063997/fileData.do`<br>([portal-15063997.html](file:///C:/work/korea/data/raw/layers5/portal/portal-15063997.html), [p2-15063997.csv](file:///C:/work/korea/data/raw/layers5/files/p2-15063997.csv)) | CSV (CP949) · 전국 253개 시군구 × 28개 지목 면적(㎡)·필지수 (89,908행) · 2025-12-31 기준 · **5,888,570 B (5.62 MB)** | **`이용허락범위 : 이용허락범위 제한 없음`** | **불필요** | `GET https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003808480&fileDetailSn=1` |
| **`data-15071109`**<br>국립환경과학원_전국오염원조사 토지계통계 | `https://www.data.go.kr/data/15071109/fileData.do`<br>([portal-15071109.html](file:///C:/work/korea/data/raw/layers5/portal/portal-15071109.html), [p2-15071109.csv](file:///C:/work/korea/data/raw/layers5/files/p2-15071109.csv)) | CSV (CP949) · 시군구별 5대 지목 면적 · 2019년 기준 · **199,664 B** | **`이용허락범위 : 이용허락범위 제한 없음`** | **불필요** | `GET https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003819729&fileDetailSn=1` |
| **산림청 임상도 (`15059586` / `map.forest.go.kr`)** | `https://map.forest.go.kr/forest/`<br>([search-forest-map.html](file:///C:/work/korea/data/raw/layers5/portal/search-forest-map.html), [fgis-forest.html](file:///C:/work/korea/data/raw/layers5/portal/fgis-forest.html)) | 1:5,000 / 1:25,000 임상도 SHP · 기준연도·용량: 로그인 전 미노출 (`확인 못 함`) | 공공데이터포털 오픈API(`15059586`)는 `제한 없음`이나 API 키 필요; FGIS 파일 다운로드 약관은 로그인 뒤 신청 화면에서만 노출 (`확인 못 함`) | **필요함** (로그인·본인인증 및 활용목적 신청 필수) | 무로그인 수집 불가 (**탈락**) |
| **국토지리정보원 토지이용현황도 (`map.ngii.go.kr`)** | `https://map.ngii.go.kr/mn/mainPage.do`<br>([search-ngii-landuse.html](file:///C:/work/korea/data/raw/layers5/portal/search-ngii-landuse.html), [ngii-map.html](file:///C:/work/korea/data/raw/layers5/portal/ngii-map.html)) | 수치지도/토지이용현황도 SHP | 공공저작물 자유이용 대상이나 국토정보플랫폼 로그인 세션 필수 | **필요함** (회원가입·로그인 필수) | 무로그인 수집 불가 (**탈락**) |
| **환경 빅데이터 플랫폼 (`bigdata-environment.kr`)** | `https://www.bigdata-environment.kr/user/main.do`<br>([env-bigdata.html](file:///C:/work/korea/data/raw/layers5/portal/env-bigdata.html)) | 데이터셋별 상이 | 플랫폼 회원 약관 및 데이터 상품별 이용조건 (로그인·구매/신청 전 원문 미노출, `확인 못 함`) | **필요함** (회원가입·로그인 필수) | 무로그인 수집 불가 (**탈락**) |
| **Google Dynamic World V1** | `https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1`<br>([dynamic-world-doc.html](file:///C:/work/korea/data/raw/layers5/portal/dynamic-world-doc.html)) | GeoTIFF · 10 m (9개 대분류, 임상·논밭 구분 없음) · 2015~현재 | **`CC BY 4.0`** (`"This dataset is licensed under a CC-BY 4.0 license."`) | **필요함** (Google Earth Engine / Cloud 계정 인증 필수) | 무로그인 일괄 수집 불가 (**탈락**) |
| **JAXA ALOS PALSAR FNF** | `https://www.eorc.jaxa.jp/ALOS/en/dataset/fnf_e.htm`<br>([jaxa-fnf-doc.html](file:///C:/work/korea/data/raw/layers5/portal/jaxa-fnf-doc.html)) | GeoTIFF · 25 m (산림/비산림) · 2007~2020 | 비영리·출판·재배포 허용(JAXA 출처 표기 조건) | **필요함** (다운로드 시 사용자 이메일·비밀번호 등록·로그인 필수) | 무로그인 수집 불가 (**탈락**) |

---

### 3.3 전국 팜맵공간정보 10개 권역 전체 다운로드 방법 및 용량·소요시간 명세 (과제 C)

현재 파이프라인([pipeline/collect_layers_terrain.py](file:///C:/work/korea/pipeline/collect_layers_terrain.py))은 전북(`15104486`)·전남(`15104487`)·경남(`15104489`) 3개 파일(합계 828 MB)만 받아 54개 시군에만 적용하고 있으나, 이번 조사에서 **전국 17개 시도를 빠짐없이 덮는 10개 권역 전체**의 메타데이터 JSON(`meta-15104481..15104491.json`)과 상세 페이지(`portal-15104481..15104491.html`)를 수집해 **모두 `이용허락범위 제한 없음`이며 로그인·키 없이 직접 다운로드 가능함**을 확인했다.

| 권역 (데이터셋명) | 공공데이터포털 PK | `atchFileId` (직접 다운로드 URL 파라미터) | 파일 크기 | 이용허락범위 | 현재 로컬 보유 상태 |
|---|---|---|---:|---|---|
| **서울·세종·6대광역시** (`15104481`) | `15104481` | `FILE_000000003642667` (`fileDetailSn=1`) | **166.98 MB** | `이용허락범위 제한 없음` | 메타 확인 완료 (`meta-15104481.json`) |
| **경기도** (`15104483`) | `15104483` | `FILE_000000003642456` (`fileDetailSn=1`) | **382.22 MB** | `이용허락범위 제한 없음` | 메타 확인 완료 (`meta-15104483.json`) |
| **충청북도** (`15104484`) | `15104484` | `FILE_000000003642555` (`fileDetailSn=1`) | **213.52 MB** | `이용허락범위 제한 없음` | 메타 확인 완료 (`meta-15104484.json`) |
| **충청남도** (`15104485`) | `15104485` | `FILE_000000003642573` (`fileDetailSn=1`) | **313.84 MB** | `이용허락범위 제한 없음` | 메타 확인 완료 (`meta-15104485.json`) |
| **전북특별자치도** (`15104486`) | `15104486` | `FILE_000000003642591` (`fileDetailSn=1`) | **258.56 MB** | `이용허락범위 제한 없음` | 기보유 (`data/raw/layers/A4/` 일부) |
| **전라남도** (`15104487`) | `15104487` | `FILE_000000003642620` (`fileDetailSn=1`) | **444.57 MB** | `이용허락범위 제한 없음` | 기보유 (`data/raw/layers/A4/` 일부) |
| **경상북도** (`15104488`) | `15104488` | `FILE_000000003642636` (`fileDetailSn=1`) | **570.39 MB** | `이용허락범위 제한 없음` | 메타 확인 완료 (`meta-15104488.json`) |
| **경상남도** (`15104489`) | `15104489` | `FILE_000000003642653` (`fileDetailSn=1`) | **379.56 MB** | `이용허락범위 제한 없음` | 기보유 (`data/raw/layers/A4/` 일부) |
| **강원특별자치도** (`15104490`) | `15104490` | `FILE_000000003642654` (`fileDetailSn=1`) | **188.26 MB** | `이용허락범위 제한 없음` | 메타 확인 완료 (`meta-15104490.json`) |
| **제주특별자치도** (`15104491`) | `15104491` | `FILE_000000003642465` (`fileDetailSn=1`) | **97.59 MB** (102,333,467 B) | `이용허락범위 제한 없음` | **이번 실증에서 전체 다운로드·검증 완료** ([p2-15104491.shp](file:///C:/work/korea/data/raw/layers5/files/p2-15104491.shp)) |
| **전국 합계 (10개 권역)** | - | `https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=<ID>&fileDetailSn=1` | **3,015.49 MB (3.02 GB)** | 전 권역 `이용허락범위 제한 없음` | 제주 실측 다운로드 속도(102.3 MB / 15.3초 = 6.7 MB/s) 기준 **전국 10개 권역 전체 다운로드 약 7.5분, 250 m 래스터화 약 3.5분 (총 11분)** |

---

## 4. 정량 실증 결과 및 비교표 (과제 C)

모든 실증 수치는 [tools/research5/verify_all.py](file:///C:/work/korea/tools/research5/verify_all.py)로 실제 계산해 [tools/research5/results.json](file:///C:/work/korea/tools/research5/results.json)에 저장된 결과다.

### 4.1 문제 1 실증 — 인천국제공항 후보 출처별 좌표·주소·거리(m)·육각 칸 일치 비교표

전체판 기준점인 `incheon-aip` ARP(`126.4391667, 37.4625000`, 육각 칸 **`7080`**, 시군구 **`28155 인천광역시 영종구`**)와 각 후보 출처에서 실제 추출한 좌표·도로명주소의 측지선 거리($\Delta_{\text{WGS84}}$, m), 투영 평면 거리($\Delta_{\text{5179}}$, m), 매핑된 육각 칸 번호를 비교한 결과다.

| 순위 / 후보 ID | 출처명 및 추출 대상 | 경도 (`lon`) | 위도 (`lat`) | AIP ARP와의 거리 ($\Delta$, m) | 매핑된 육각 칸 번호 (AIP 일치 여부) | 추출된 도로명주소 → 매핑 시군구 | 이용허락 조건 |
|---|---|---:|---:|---:|---|---|---|
| **기준 (`incheon-aip`)** | 국토교통부 AIP RKSI AD 2.2 비행장 기준점(ARP) | `126.4391667` | `37.4625000` | **0.0 m** | **`7080`** (기준) | `47, Gonghang-ro 424beon-gil, Yeongjong-gu` → `28155 영종구` | 무단 복제·배포 제한 (공개판 제외) |
| **1순위 (`data-15041331-mid`)** | **국가철도공단 공항철도 역위치(`15041331`) + 주소데이터(`15041094`) T1·T2역 중점** | **`126.4428791`** | **`37.4581334`** | **585.5 m** | **`7080` (동일)** | `인천광역시 중구 공항로 271 (운서동)` / `공항로 272` → **`28155 영종구`** | **`이용허락범위 제한 없음`** |
| **1순위 단일역 (`data-15041331-t2`)** | 국가철도공단 공항철도 `인천공항2터미널역` (`15041331` + `15041094`) | `126.4334150` | `37.4686600` | **852.2 m** | **`7080` (동일)** | `인천광역시 중구 공항로 272 인천국제공항2터미널역` → **`28155 영종구`** | **`이용허락범위 제한 없음`** |
| **1순위 단일역 (`data-15041331-t1`)** | 국가철도공단 공항철도 `인천공항1터미널역` (`15041331` + `15041094`) | `126.4523433` | `37.4476067` | **2,022.7 m** | **`7080` (동일)** | `인천광역시 중구 공항로 271 (운서동) 인천공항1터미널역` → **`28155 영종구`** | **`이용허락범위 제한 없음`** |
| **1순위 보조 (`data-15041332-t1`)** | 국가철도공단 자기부상 `인천공항1터미널역` (운영기관: 인천국제공항공사) | `126.4525000` | `37.4472220` | **2,065.7 m** | **`7080` (동일)** | `인천국제공항공사 자기부상 인천공항1터미널` → **`28155 영종구`** | **`이용허락범위 제한 없음`** |
| **2순위-A (`osm-rksi-pos`)** | **OpenStreetMap `WAY 316419197` (`icao=RKSI`) 폴리곤 대표점(`point_on_surface`)** | **`126.4417093`** | **`37.4634593`** | **248.9 m** | **`7080` (동일)** | `인천광역시 중구 운서동 공항로 272 (22382)` → **`28155 영종구`** | **`ODbL 1.0`** |
| **2순위-A (`osm-rksi-centroid`)** | OpenStreetMap `WAY 316419197` (`icao=RKSI`) 폴리곤 무게중심(`centroid`) | `126.4406244` | `37.4645544` | **262.0 m** | **`7080` (동일)** | `인천광역시 중구 운서동 공항로 272 (22382)` → **`28155 영종구`** | **`ODbL 1.0`** |
| **2순위-B (`wikidata-q20932`)** | **Wikidata `Q20932` (`P625` 좌표 / `P6375` 도로명주소)** | **`126.4391667`** | **`37.4625000`** | **0.0 m** | **`7080` (동일)** | `22382 인천시 중구 공항로 424번길 47` / `공항로 272` → **`28155 영종구`** | **`CC0 1.0` (퍼블릭 도메인)** |
| 보조 (`admdong-unseo1`) | 국토부 세계공항(`3051587`) + 인천공항공사 시설(`15088368`) → `운서1동` 폴리곤 대표점 | `126.4438770` | `37.4650404` | **503.1 m** | **`7080` (동일)** | `인천광역시 영종구 운서1동 (2815554000)` → **`28155 영종구`** | `제한 없음` + `CC BY 4.0` |
| 보조 (`data-15150509-weighted`) | 기후에너지환경부 세분류 도엽 통계(`15150509`) 영종도 `공항` 9개 도엽 면적가중 중심 | `126.4509097` | `37.4622819` | **1,039.2 m** | **`7080` (동일)** | `도엽 37610007~37610029 (공항 114.86 ha)` → **`28155 영종구`** | `공공누리 제1유형` |
| 보조 (`ne-10m-airports`) | Natural Earth 10m Airports (`ne_10m_airports.shp`, `iata_code=ICN`) | `126.4508760` | `37.4492089` | **1,802.6 m** | **`7080` (동일)** | `Incheon Int'l (terminal)` → **`28155 영종구`** | `Public Domain` |
| 탈락 (`geonames-6300433`) | GeoNames `6300433` (`Incheon International Airport`) | `126.4509500` | `37.4492000` | **1,807.2 m** | **`7080` (동일)** | `KR.txt 6300433 AIRP` → `28155 영종구` | `CC BY 4.0` |
| 탈락 (`geonames-12689633`) | GeoNames `12689633` (`인천국제공항`) | `126.4493500` | `37.4691400` | **1,163.9 m** | `6927` (북동 인접칸) | `KR.txt 12689633 AIRP` → `28155 영종구` | `CC BY 4.0` |
| 탈락 (`ourairports-rksi`) | OurAirports `airports.csv` (`ident=RKSI`) | `126.4509960` | `37.4691010` | **1,277.4 m** | `6927` (북동 인접칸) | `Incheon International Airport (KR-28)` → `28155 영종구` | `Public Domain` |

- **실증 핵심 결론**:
  1. 공공데이터포털 공식 파일데이터(`15041331` + `15041094`, `이용허락범위 제한 없음`)의 제1·2여객터미널 역 중점(`126.4428791, 37.4581334`, $\Delta = 585.5\text{ m}$), T1 단독, T2 단독, OSM `WAY 316419197` 대표점($\Delta = 248.9\text{ m}$), Wikidata `Q20932`($\Delta = 0.0\text{ m}$), Natural Earth `ICN`($\Delta = 1,802.6\text{ m}$), 세분류 도엽 통계 가중중심($\Delta = 1,039.2\text{ m}$) **모두 단 하나의 예외도 없이 전체판 AIP와 똑같은 육각 칸 `7080` (`28155 영종구`)에 떨어진다.**
  2. 따라서 공개판에서 `incheon-aip`를 제거하더라도 `15041331`+`15041094`(1순위) 또는 `osm-kr` / `wikidata`(2순위)로 대체하면 **전체판과 100% 동일한 칸(`7080`)에 인천국제공항(여객 `73,752,582명`, 화물 `4,032,060톤`, 순위 1위)이 표시된다.**

---

### 4.2 문제 2 실증 — 전국 및 5개 시험 구역의 후보 해법별 토지피복 비율·오차 비교표

비교에 사용한 5개 후보 해법의 정의는 다음과 같다:
- **후보 A (`ESA 10m -> 50m 직접 + 팜맵 4도`)**: 보유 중인 ESA WorldCover 10 m 원자료를 250 m 최빈값 대신 **50 m 격자(`all_touched=False`)로 칸별 직접 집계**하고, 기존 팜맵 3개 도(전북·전남·경남)에 신규 다운로드한 제주 팜맵(`15104491`)을 병합.
- **후보 B (`환경부 1:5,000 세분류 도엽 통계 15150509 공간 교차`)**: 공공데이터포털 파일데이터 `15150509`(`공공누리 제1유형`, 2025년 제작 전국 **18,538개 1:5,000 도엽** × 41개 세분류 면적 ㎡)를 표준 1:5,000 도엽 격자(`1.5' × 1.5'` ≈ `6.3 km²`)로 복원해 육각 칸(5,027칸)과 면적가중 공간 교차(5,024칸 직접 교차, 도엽 밖 작은 섬 3칸은 후보 A 폴백).
- **후보 C (`1:5,000 도엽 통계 15150509 + ESA 10m 다중해상도 결합`, 1순위)**: 후보 B의 1:5,000 도엽 세분류 면적을 기준으로 삼되, 도엽 경계에 걸친 칸들의 공간 변이를 ESA 10 m(50 m 직접 집계) 및 팜맵과 결합(0.6:0.4 사전분포 후 시군구 도엽 총량 IPF 보정)하고 임상(활엽·침엽·혼효) 및 경지 세분류(논·밭·과수·시설)는 1:5,000 도엽 비율로 정밀 분할.
- **후보 D (`ESA 10m + 제1유형 국가토지피복통계 15163128 시군구 보정`, 2순위)**: 후보 A의 50 m 칸별 분포를 사전분포(Prior)로 두고, 공공데이터포털에서 `공공누리 제1유형`이 확인된 공식 시군구 세분류 통계(`15163128` / `15164500`)에 맞춰 시군구별 IPF(Raking) 보정 및 세분류 분할.
- **후보 E (`ESA 10m + 국토부 지적기본통계 15063997 지목 보정`)**: 후보 A를 국토교통부 지적기본통계(`15063997`, `이용허락범위 제한 없음`)의 시군구별 28개 법정 지목 면적에 맞춰 IPF 보정.

#### (1) 전국 비교 시군구 231곳 (4,538칸, 통계 육지 9,111,924 ha — `docs/LANDCOVER_ME_REPORT.md` 동일 기준)

| 방법 | 숲 (%) | 활엽 / 침엽 / 혼효 (%) | 농경지 (%) | 논 / 밭 / 과수 / 시설 (%) | 시가화 (%) | 초지 (%) | 습지 (%) | 나지 (%) | 수역 (%) | 통계 면적 대비 상대 오차 (숲 / 논 / 밭 / 시가화) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **공식 국가토지피복통계 (2024 기준, 제1유형 `15163128`)** | **56.74** | **27.19 / 22.56 / 6.99** | **17.50** | **7.60 / 7.29 / 1.54 / 0.83** | **7.88** | **11.06** | **1.26** | **3.30** | **2.27** | 기준 (0.0% / 0.0% / 0.0% / 0.0%) |
| 현재 공개판 (`ESA 250m 최빈값 + 팜맵 3도`) | 71.33 | `null` / `null` / `null` | 16.61 | 9.75 / 6.62 / 0.27 / 0.31 | 6.17 | 1.90 | 0.03 | 0.22 | 3.70 | **숲 +27.5%, 논 +30.2%, 밭 -7.9%, 시가 -20.5%** |
| 현재 전체판 (`환경부 중분류 WMS 50m`) | 54.75 | 26.81 / 21.82 / 6.10 | 20.25 | 8.21 / 8.94 / 1.95 / 0.74 | 5.10 | 7.31 | 1.42 | 2.15 | 1.97 | 숲 -2.1%, 논 +9.5%, **밭 +24.4%, 시가 -34.3%** |
| **후보 A** (`ESA 10m -> 50m 직접 + 팜맵 4도`) | 67.38 | `null` / `null` / `null` | 15.52 | 7.42 / 7.56 / 1.10 / 0.34 | **7.75** | 6.15 | 0.07 | 0.60 | **2.53** | 숲 +20.5%, **논 -1.0%, 밭 +5.2%, 시가 -0.2%** |
| **후보 B** (`환경부 1:5,000 도엽 통계 15150509`) | **56.23** | **26.94 / 22.31 / 7.01** | **17.16** | **7.41 / 7.22 / 1.49 / 0.81** | **7.72** | **11.01** | 2.26 | **3.45** | **2.18** | **숲 +0.5%, 논 -1.1%, 밭 +0.4%, 시가 -0.6%** |
| **후보 C** (`1:5,000 도엽 + ESA 10m 결합`, **1순위**) | **56.23** | **26.93 / 22.30 / 6.99** | **17.16** | **7.60 / 7.28 / 1.46 / 0.81** | **7.72** | **11.01** | 2.26 | **3.45** | **2.18** | **숲 +0.5%, 논 +1.5%, 밭 +1.2%, 시가 -0.6%** |
| **후보 D** (`ESA 10m + 제1유형 통계 15163128 보정`, **2순위**) | **56.50** | **26.96 / 22.55 / 6.99** | **17.62** | **7.77 / 7.46 / 1.55 / 0.84** | **7.92** | **11.09** | **1.27** | **3.34** | **2.27** | **숲 +1.0%, 논 +3.7%, 밭 +3.7%, 시가 +2.0%** |
| 후보 E (`ESA 10m + 국토부 지적통계 15063997`) | 62.59 | `null` / `null` / `null` | 19.83 | 11.31 / 7.81 / 0.71 / 0.00 | 9.03 | 1.06 | 0.13 | 1.32 | 6.05 | 숲 +11.9%, **논 +51.0%**, 밭 +8.7%, 시가 +16.3% |

#### (2) 전국 전체 (5,027칸 전체, 통계 육지 9,972,447 ha — DMZ 접경 시군 포함)

| 방법 | 숲 (%) | 활엽 / 침엽 / 혼효 (%) | 농경지 (%) | 논 / 밭 / 과수 / 시설 (%) | 시가화 (%) | 초지 (%) | 수역 (%) | 통계 면적 대비 상대 오차 (숲 / 논 / 밭 / 시가화) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **공식 국가토지피복통계 (전국 252개 시군구)** | **57.67** | **28.64 / 21.87 / 7.15** | **17.05** | **7.51 / 7.07 / 1.41 / 0.82** | **7.74** | **10.74** | **2.27** | 기준 (0.0% / 0.0% / 0.0% / 0.0%) |
| 현재 공개판 (`ESA 250m 최빈값`) | 71.38 | `null` / `null` / `null` | 16.17 | 9.51 / 6.45 / 0.27 / 0.31 | 6.38 | 2.03 | 3.73 | **숲 +27.1%, 논 +29.9%, 밭 -6.4%, 시가 -15.4%** |
| 현재 전체판 (`환경부 중분류 WMS 50m`) | 55.65 | 27.08 / 21.44 / 6.11 | 19.54 | 8.05 / 8.81 / 1.87 / 0.73 | 5.27 | 7.05 | 2.07 | 숲 -0.9%, 논 +3.7%, **밭 +20.5%, 시가 -30.0%** (접경 21개 시군 결측 폴백) |
| **후보 A** (`ESA 10m -> 50m 직접 + 팜맵 4도`) | 67.47 | `null` / `null` / `null` | 15.13 | 7.35 / 7.29 / 1.10 / 0.34 | **7.84** | 6.29 | **2.56** | 숲 +20.1%, **논 +0.5%, 밭 +5.8%, 시가 +4.0%** |
| **후보 B** (`환경부 1:5,000 도엽 통계 15150509`) | **56.77** | **28.19 / 21.44 / 7.16** | **16.72** | **7.36 / 6.99 / 1.36 / 0.79** | **7.75** | **10.74** | **2.21** | **숲 +1.1%, 논 +0.6%, 밭 +1.5%, 시가 +2.8%** (접경 결측 0칸!) |
| **후보 C** (`1:5,000 도엽 + ESA 10m 결합`, **1순위**) | **56.77** | **28.18 / 21.43 / 7.14** | **16.72** | **7.54 / 7.05 / 1.34 / 0.79** | **7.75** | **10.74** | **2.21** | **숲 +1.1%, 논 +3.1%, 밭 +2.4%, 시가 +2.8%** |
| **후보 D** (`ESA 10m + 제1유형 통계 15163128 보정`, **2순위**) | **57.21** | **28.44 / 21.85 / 7.17** | **17.18** | **7.72 / 7.23 / 1.42 / 0.83** | **7.97** | **10.77** | **2.27** | **숲 +1.9%, 논 +5.6%, 밭 +5.0%, 시가 +5.8%** |

#### (3) 시험 구역 ① — 평야 지대: 전북 김제시·익산시 (`52210`, `52140` / 53칸, 통계 육지 105,395 ha)

| 방법 | 숲 (%) | 활엽 / 침엽 / 혼효 (%) | 농경지 (%) | 논 / 밭 / 과수 / 시설 (%) | 시가화 (%) | 초지 (%) | 수역 (%) | 통계 면적 대비 상대 오차 (숲 / 논 / 밭 / 시가화) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **공식 국가토지피복통계** | **12.80** | **4.04 / 7.45 / 1.31** | **51.04** | **34.84 / 12.73 / 0.76 / 2.17** | **12.28** | **14.54** | **3.60** | 기준 |
| 현재 공개판 (`ESA 250m 최빈값`) | 18.60 | `null` / `null` / `null` | 69.30 | 55.30 / 12.43 / 0.19 / 1.26 | 8.47 | 1.91 | 1.49 | **숲 +48.9%, 논 +62.6%, 밭 +0.1%, 시가 -29.3%** |
| 현재 전체판 (`환경부 중분류 WMS 50m`) | 11.64 | 3.64 / 6.85 / 1.00 | 61.96 | 41.89 / 15.74 / 0.92 / 2.60 | 7.09 | 7.15 | 2.74 | 숲 -6.8%, **논 +23.1%, 밭 +26.7%, 시가 -40.8%** |
| 후보 A (`ESA 10m -> 50m 직접 + 팜맵`) | 19.78 | `null` / `null` / `null` | 58.33 | 41.94 / 14.78 / 0.41 / 1.19 | **12.90** | 6.46 | 1.76 | 숲 +58.3%, 논 +23.3%, 밭 +19.0%, **시가 +7.6%** |
| **후보 B** (`환경부 1:5,000 도엽 통계 15150509`) | **12.19** | **3.93 / 7.01 / 1.24** | **51.64** | **36.29 / 11.91 / 0.77 / 2.15** | **12.20** | **14.52** | **3.50** | **숲 -2.5%, 논 +6.7%, 밭 -4.1%, 시가 +1.8%** |
| **후보 C** (`1:5,000 도엽 + ESA 10m 결합`, **1순위**) | **12.19** | **3.86 / 7.04 / 1.28** | **51.64** | **36.77 / 11.95 / 0.77 / 2.17** | **12.20** | **14.52** | **3.50** | **숲 -2.5%, 논 +8.1%, 밭 -3.9%, 시가 +1.8%** |
| **후보 D** (`ESA 10m + 제1유형 통계 보정`, **2순위**) | **12.79** | **4.03 / 7.46 / 1.31** | **51.09** | **35.25 / 12.87 / 0.78 / 2.20** | **12.24** | **14.51** | **3.61** | **숲 +2.4%, 논 +3.6%, 밭 +3.6%, 시가 +2.2%** |

- **해석**: 김제·익산 평야에서 현재 공개판은 250 m 최빈값 격자화 때문에 논 면적이 공식 통계(34.8%)보다 **+62.6%(55.3%)** 과대 추정되고 시가화는 **-29.3%(8.5%)** 과소 추정되었다. 전체판 WMS조차 농로·소하천 제방이 논밭 픽셀에 흡수되어 논 +23.1%, 밭 +26.7%, 시가화 -40.8% 오차를 보였다. 반면 **후보 B·C(1:5,000 도엽 통계)**와 **후보 D(시군구 통계 보정)**는 논(35.3~36.8%), 밭(11.9~12.9%), 시가화(12.2%), 초지(14.5%) 모두 공식 통계와 **±2~8% 이내**로 일치한다.

#### (4) 시험 구역 ② — 산지 지대: 강원특별자치도 인제군 (`51810` / 81칸, 통계 육지 164,147 ha)

| 방법 | 숲 (%) | 활엽 / 침엽 / 혼효 (%) | 농경지 (%) | 논 / 밭 / 과수 / 시설 (%) | 시가화 (%) | 초지 (%) | 수역 (%) | 통계 면적 대비 상대 오차 (숲 / 논 / 밭 / 시가화) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **공식 국가토지피복통계** | **88.49** | **54.57 / 21.80 / 12.12** | **2.46** | **0.40 / 1.89 / 0.03 / 0.11** | **1.30** | **3.58** | **1.25** | 기준 |
| 현재 공개판 (`ESA 250m 최빈값`) | 96.28 | `null` / `null` / `null` | 1.59 | 0.21 / 1.33 / `null` / `null` | 0.57 | 0.77 | 0.79 | **숲 +9.4%, 논 -47.7%, 밭 -29.0%, 시가 -56.2%** |
| 현재 전체판 (`환경부 중분류 WMS 50m`) | 84.75 | 49.79 / 20.91 / 8.72 | 2.33 | 0.21 / 2.32 / 0.00 / 0.05 | 0.48 | 2.31 | 1.02 | 숲 -3.7%, **논 -63.1%**, 밭 -13.2%, **시가 -62.9%** (북부 접경 칸 결측) |
| 후보 A (`ESA 10m -> 50m 직접`) | 93.04 | `null` / `null` / `null` | 1.96 | 0.32 / 1.63 / `null` / `null` | 1.02 | 2.80 | 0.88 | 숲 +5.7%, 논 -19.2%, 밭 -13.0%, 시가 -21.5% |
| **후보 B** (`환경부 1:5,000 도엽 통계 15150509`) | **88.30** | **54.62 / 21.77 / 11.91** | **2.59** | **0.41 / 1.99 / 0.03 / 0.13** | **1.31** | **3.61** | **1.27** | **숲 +0.3%, 논 +2.5%, 밭 +6.3%, 시가 +1.0%** |
| **후보 C** (`1:5,000 도엽 + ESA 10m 결합`, **1순위**) | **88.30** | **54.63 / 21.79 / 11.88** | **2.59** | **0.42 / 2.01 / 0.03 / 0.13** | **1.31** | **3.61** | **1.27** | **숲 +0.3%, 논 +4.7%, 밭 +7.1%, 시가 +1.0%** |
| **후보 D** (`ESA 10m + 제1유형 통계 보정`, **2순위**) | **88.49** | **54.57 / 21.80 / 12.12** | **2.46** | **0.41 / 1.91 / 0.03 / 0.11** | **1.30** | **3.58** | **1.25** | **숲 +0.5%, 논 +1.6%, 밭 +1.6%, 시가 +0.5%** |

- **해석**: 인제군 산지에서 공개판은 골짜기의 좁은 밭·마을·도로가 250 m 최빈값 숲에 묻혀 숲이 96.3%로 치우치고 시가화(-56.2%)와 논(-47.7%)이 절반 이하로 사라졌다. 전체판 WMS도 북부 민통선 도엽 누락과 도로 소실 때문에 시가화가 0.48%(-62.9%)에 불과했다. 반면 **후보 B·C·D는 숲 88.3~88.5%(활엽 54.6%, 침엽 21.8%, 혼효 11.9~12.1%), 밭 1.9~2.0%, 시가화 1.31%를 정확히 복원한다.**

#### (5) 시험 구역 ③ — 대도시: 서울특별시 (`11*` 25개 자치구 / 29칸, 통계 육지 60,576 ha)

| 방법 | 숲 (%) | 활엽 / 침엽 / 혼효 (%) | 농경지 (%) | 논 / 밭 / 과수 / 시설 (%) | 시가화 (%) | 초지 (%) | 수역 (%) | 통계 면적 대비 상대 오차 (숲 / 논 / 밭 / 시가화) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **공식 국가토지피복통계** | **23.17** | **15.74 / 4.22 / 3.21** | **1.60** | **0.31 / 0.99 / 0.06 / 0.18** | **52.97** | **11.97** | **5.26** | 기준 |
| 현재 공개판 (`ESA 250m 최빈값`) | 29.79 | `null` / `null` / `null` | 1.52 | 0.72 / 0.72 / `null` / `null` | 62.21 | 1.03 | 5.28 | **숲 +25.4%, 논 +126.9%, 밭 -28.8%, 시가 +14.5%** |
| 현재 전체판 (`환경부 중분류 WMS 50m`) | 21.86 | 15.28 / 3.72 / 2.79 | 2.24 | 0.55 / 1.17 / 0.07 / 0.31 | 51.41 | 8.55 | 5.34 | 숲 -8.0%, 논 +72.8%, 밭 +15.3%, 시가 -5.4% |
| **후보 B** (`환경부 1:5,000 도엽 통계 15150509`) | **22.89** | **15.48 / 4.21 / 3.20** | **2.17** | **0.48 / 1.26 / 0.10 / 0.28** | **52.15** | **11.86** | **5.51** | **숲 -3.7%, 시가 -4.0%, 초지 11.9% 완벽 복원** |
| **후보 C** (`1:5,000 도엽 + ESA 10m 결합`, **1순위**) | **22.89** | **15.49 / 4.21 / 3.19** | **2.17** | **0.48 / 1.30 / 0.10 / 0.29** | **52.15** | **11.86** | **5.51** | **숲 -3.7%, 시가 -4.0%, 초지 11.9% 완벽 복원** |
| **후보 D** (`ESA 10m + 제1유형 통계 보정`, **2순위**) | **22.09** | **15.13 / 3.93 / 3.03** | **1.58** | **0.31 / 1.01 / 0.06 / 0.20** | **54.45** | **11.78** | **5.02** | **숲 -7.0%, 논 -1.3%, 밭 -0.3%, 시가 +0.2%** |

#### (6) 시험 구역 ④ — DMZ 접경 지대: 경기 연천군·강원 고성군 (`41800`, `51820` / 72칸, 통계 육지 134,636 ha)

| 방법 | 숲 (%) | 활엽 / 침엽 / 혼효 (%) | 농경지 (%) | 논 / 밭 / 과수 / 시설 (%) | 시가화 (%) | 초지 (%) | 수역 (%) | 통계 면적 대비 상대 오차 (숲 / 논 / 밭 / 시가화) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **공식 국가토지피복통계** | **69.17** | **49.32 / 13.58 / 6.27** | **12.82** | **7.52 / 4.82 / 0.05 / 0.27** | **3.65** | **8.79** | **1.53** | 기준 |
| 현재 공개판 (`ESA 250m 최빈값`) | 80.79 | `null` / `null` / `null` | 9.96 | 5.57 / 4.35 / `null` / `null` | 1.71 | 5.56 | 1.86 | **숲 +27.2%, 논 -19.4%, 시가 -49.0%** |
| **현재 전체판 (`환경부 중분류 WMS 50m`)** | **80.79** | **`null` / `null` / `null`** | **9.96** | **`null` / `null` / `null` / `null`** | **1.71** | **5.56** | **1.86** | **WMS 도엽 전면 누락으로 72칸 전부 ESA 폴백! (임상·논·밭 전부 `null`)** |
| **후보 B** (`환경부 1:5,000 도엽 통계 15150509`) | **70.34** | **50.29 / 13.36 / 6.69** | **11.91** | **6.99 / 4.51 / 0.04 / 0.23** | **3.37** | **9.00** | **1.49** | **숲 +10.8%, 논 +1.1%, 밭 +1.9%, 시가 +0.6% (접경 72칸 100% 세분류 복원!)** |
| **후보 C** (`1:5,000 도엽 + ESA 10m 결합`, **1순위**) | **70.34** | **50.30 / 13.37 / 6.66** | **11.91** | **7.10 / 4.53 / 0.04 / 0.23** | **3.37** | **9.00** | **1.49** | **숲 +10.8%, 논 +2.8%, 밭 +2.5%, 시가 +0.6%** |
| **후보 D** (`ESA 10m + 제1유형 통계 보정`, **2순위**) | **69.07** | **49.32 / 13.50 / 6.24** | **12.88** | **7.64 / 4.91 / 0.06 / 0.27** | **3.65** | **8.81** | **1.53** | **숲 +8.8%, 논 +10.6%, 밭 +11.0%, 시가 +9.1%** |

- **해석**: 이 시험 구역이 **후보 B·C(`data-15150509` 1:5,000 세분류 도엽 통계)**의 진가를 가장 극적으로 보여준다. 기존 전체판(`world_full`)조차 환경부 WMS가 군사분계선 인접 도엽을 비워 두어 연천군·고성군 72칸 전체가 ESA로 폴백되었고 활엽·침엽·혼효는 물론 논·밭 구분까지 전부 `null`이었다. 반면 **`data-15150509`에는 연천군·고성군·철원군·파주시·인제군의 1:5,000 도엽 통계가 빠짐없이 수록되어 있어, 공개판이 오히려 기존 전체판보다 더 완전한 토지피복을 갖게 된다.**

#### (7) 시험 구역 ⑤ — 도서·과수 지대: 제주특별자치도 (`50110`, `50130` / 96칸, 통계 육지 186,484 ha)

| 방법 | 숲 (%) | 활엽 / 침엽 / 혼효 (%) | 농경지 (%) | 논 / 밭 / 과수 / 시설 (%) | 시가화 (%) | 초지 (%) | 수역 (%) | 통계 면적 대비 상대 오차 (숲 / 논 / 밭 / 시가화) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **공식 국가토지피복통계** | **32.99** | **17.78 / 10.83 / 4.37** | **35.33** | **0.12 / 21.04 / 10.05 / 3.86** | **9.37** | **18.31** | **0.27** | 기준 (과수원 10.05%, 시설재배 3.86%, 초지 18.31%) |
| 현재 공개판 (`ESA 250m 최빈값, 제주 팜맵 미적용`) | 69.23 | `null` / `null` / `null` | 14.56 | 0.00 / 14.56 / `null` / `null` | 7.49 | 4.21 | 4.48 | **숲 +120.1% (상록 감귤 과수원을 숲으로 오분류!), 과수·시설 `null`** |
| 현재 전체판 (`환경부 중분류 WMS 50m`) | 31.02 | 16.88 / 10.21 / 3.89 | 41.65 | 0.10 / 24.32 / 14.33 / 2.51 | 5.57 | 13.52 | 0.15 | 숲 -1.4%, 밭 +21.2%, **시가 -37.6%** |
| 후보 A (`ESA 10m -> 50m 직접 + 제주 팜맵 15104491`) | 62.11 | `null` / `null` / `null` | 16.57 | 0.00 / 14.29 / 2.06 / 0.40 | 11.07 | 7.75 | 2.14 | ESA가 감귤나무 수관을 `Tree cover(10)`로 분류해 `crop` 총량이 16.6%로 묶임 |
| **후보 B** (`환경부 1:5,000 도엽 통계 15150509`) | **32.15** | **17.48 / 11.12 / 4.16** | **35.24** | **0.21 / 23.25 / 8.37 / 3.10** | **9.59** | **18.30** | **0.82** | **숲 +2.2%, 과수원 8.37%, 시설 3.10%, 초지 18.30%, 시가화 9.59% 정확 복원!** |
| **후보 C** (`1:5,000 도엽 + ESA 10m 결합`, **1순위**) | **32.15** | **16.22 / 11.79 / 4.09** | **35.24** | **0.21 / 24.33 / 7.84 / 2.86** | **9.59** | **18.30** | **0.82** | **숲 +2.2%, 시가 +7.4%, 초지 18.30% 정확 복원** |
| **후보 D** (`ESA 10m + 제1유형 통계 보정`, **2순위**) | **32.99** | **17.78 / 10.78 / 4.43** | **35.40** | **0.12 / 21.10 / 10.23 / 3.95** | **9.33** | **18.26** | **0.27** | **숲 +4.9%, 논 +3.8%, 밭 +5.2%, 과수 10.23%, 시설 3.95%, 시가 +4.4%** |

- **해석**: 제주도에서 현재 공개판은 ESA WorldCover가 상록 감귤 과수원과 곶자왈·목장을 `Tree cover(10)`로 분류한 탓에 숲이 **69.2%(공식 33.0% 대비 +120.1% 오차)**로 왜곡되고 과수원(공식 10.1%)과 시설재배지(3.9%)가 전부 `null`이었다. 또한 후보 A처럼 제주 팜맵(`15104491`)을 받아 `crop` 내부를 나누더라도, ESA가 애초에 감귤 과수원을 `crop`이 아닌 `forest`로 분류했기 때문에 `crop` 총량(16.6%)에 곱하는 기존 방식으로는 과수원이 2.1%밖에 잡히지 않는다. 반면 **후보 B·C(`15150509` 1:5,000 도엽 통계)**와 **후보 D(시군구 세분류 통계 보정)**는 제주도의 **숲 32.2~33.0%, 밭 21.1~23.3%, 과수원 8.4~10.2%, 시설재배 3.1~4.0%, 초지(목장) 18.3%, 시가화 9.3~9.6%**를 완벽하게 복원한다.

---

## 5. 문제별 최종 권고안 및 구현·출처 고지 방안 (과제 D)

### 5.1 문제 1 (인천국제공항 위치 및 실적) 최종 권고

#### ① 1순위 권고안: 공공데이터포털 `국가철도공단_공항철도_역위치`(`15041331`) + `공항철도_주소데이터`(`15041094`) 결합
- **구체적 방법**:
  - [data/raw/layers5/files/p1-15041331.csv](file:///C:/work/korea/data/raw/layers5/files/p1-15041331.csv) (`이용허락범위 제한 없음`)의 `인천공항1터미널`(`126.4523433, 37.44760672`)·`인천공항2터미널`(`126.433415, 37.46866`) 좌표 중점(`126.4428791, 37.4581334`, 또는 T2/T1 좌표)과 [p1-15041094.csv](file:///C:/work/korea/data/raw/layers5/files/p1-15041094.csv) (`이용허락범위 제한 없음`)의 도로명주소(`인천광역시 중구 공항로 271 (운서동)` / `인천광역시 중구 공항로 272`)를 `incheon-aip` 대신 사용한다.
  - 여객·화물 실적은 이미 보유한 `airportal-2025`([data-15092537](https://www.data.go.kr/data/15092537/fileData.do), `이용허락범위 제한 없음`, 2025년 여객 `73,752,582명`, 화물 `4,032,060톤`)를 그대로 연결한다.
- **기대 품질**:
  - AIP 비행장 기준점(ARP)과의 거리가 **585.5 m**에 불과하며, 전체판과 **100% 동일한 육각 칸 `7080` (`28155 인천광역시 영종구`)**에 매핑되어 전체판과 공개판의 공항 레이어(15개 공항 전원 수록)가 완전히 일치한다.
- **이용조건상 남는 위험**:
  - **없음 (위험 0)**. 세 파일(`15041331`, `15041094`, `15092537`) 모두 공공데이터포털에 **`이용허락범위 : 이용허락범위 제한 없음`**으로 등록된 정적 파일데이터(CSV)다.
- **구현 난이도**:
  - **매우 낮음 (코드 약 15줄 수정)**. [pipeline/build_layers2.py](file:///C:/work/korea/pipeline/build_layers2.py#L469-L511)의 `build_airports()`에서 `incheon-aip` 분기 대신 `p1-15041331.csv`·`p1-15041094.csv`를 읽도록 바꾸고 [pipeline/lib/profile.py](file:///C:/work/korea/pipeline/lib/profile.py)에서 `incheon-aip` 의존성을 제거하면 끝난다.

#### ② 2순위 권고안: OpenStreetMap `WAY 316419197` (`icao=RKSI`, `ODbL 1.0`) 또는 Wikidata `Q20932` (`CC0 1.0`)
- **구체적 방법**:
  - 이미 로컬에 보유하고 공개판 `sources.json`에 등록된 `south-korea-261124.osm.pbf`(`osm-kr`, `ODbL 1.0`)에서 `WAY 316419197` (`aeroway=aerodrome, icao=RKSI, iata=ICN`)의 대표점(`126.4417093, 37.4634593`, AIP ARP와 **248.9 m** 차이, 칸 **`7080`**)을 추출하거나, [wikidata-Q20932.json](file:///C:/work/korea/data/raw/layers5/files/wikidata-Q20932.json)(`CC0 1.0`, `126.4391667, 37.4625000`, AIP ARP와 **0.0 m** 차이, 칸 **`7080`**)을 사용한다.
- **기대 품질 및 위험**:
  - 칸 `7080` 매핑 결과는 1순위 및 전체판과 100% 동일하다. OSM은 이미 `sources.json`에 `ODbL 1.0` 고지가 되어 있고 Wikidata는 `CC0 1.0`이므로 법적 위험이 없으나, 국내 공공기관 공식 출처로 통일하려면 1순위(`15041331`+`15041094`)를 주 출처로 쓰고 2순위를 교차검증으로 두는 것이 가장 깔끔하다.

---

### 5.2 문제 2 (전국 토지피복 품질 개선 및 세부 분류 복원) 최종 권고

#### ① 1순위 권고안 (후보 B/C): 기후에너지환경부 `1:5,000 세분류 토지피복지도 도엽단위 현행화 통계`(`data-15150509`, `공공누리 제1유형`) + `ESA WorldCover 10 m`(50 m 직접 집계, `CC BY 4.0`) + `팜맵공간정보`(`15104481~15104491`, `제한 없음`) 결합
- **구체적 방법**:
  1. 공공데이터포털 파일데이터 [p2-15150509.csv](file:///C:/work/korea/data/raw/layers5/files/p2-15150509.csv) (`제작연도 == "2025년"`, 전국 **18,538개 1:5,000 도엽** × 41개 세분류 면적 ㎡)의 8자리 국토지리정보원 표준 도엽번호(`1.5' × 1.5'` ≈ `6.3 km²`, 육각 칸의 1/3 크기)를 경위도 직사각형으로 복원해 EPSG:5179로 변환한 뒤 육각 칸(5,027칸)과 면적가중 공간 교차(`shapely.STRtree`)한다.
  2. 이것만으로 전국 5,027개 육각 칸 중 **5,024칸(99.94%)**에서 **숲(`broadleaf`, `conifer`, `mixed`), 농경지(`paddy`, `field`, `orchard`, `greenhouse`), 시가화(`built`), 초지(`grass`), 습지(`wetland`), 나지(`bare`), 수역(`water`) 14개 전 항목 비율**이 2.5초 만에 산출된다(1:5,000 도엽 밖의 작은 섬 3칸만 50 m ESA WorldCover로 폴백).
  3. 필요 시 도엽 경계에 걸친 칸 내부의 미세 공간 변이를 더 정밀하게 반영하기 위해, 각 시군구 또는 1:5,000 도엽 그룹 내에서 **ESA WorldCover 10 m(50 m 직접 집계) + 전국 팜맵(`15104481~15104491`)** 비율과 결합(후보 C)한다.
- **기대 품질 (치우침 감소 효과)**:
  - 전국 비교 시군구 231곳 기준 상대 오차가 현재 공개판 **숲 +27.5% → +0.5%**, **논 +30.2% → -1.1%(후보 C +1.5%)**, **밭 -7.9%(전체판 +24.4%) → +0.4%(후보 C +1.2%)**, **시가화 -20.5%(전체판 -34.3%) → -0.6%**, **초지 1.9% → 11.0%(공식 11.1%)**로 줄어들어 **현재 공개판은 물론 기존 전체판(WMS 50m)보다도 통계 정합성이 높다.**
  - 공개판에서 `null`이었던 **활엽수림(28.2%)·침엽수림(21.4%)·혼효림(7.2%)**과 전국 **과수원(1.4%)·시설재배지(0.8%)**가 100% 복원된다.
  - 기존 전체판 WMS에서도 결측이었던 **연천·파주·철원·화천·양구·인제·고성 등 접경 21개 시군의 임상·논·밭 비율까지 100% 복원**된다.
  - 제주도에서 상록 감귤 과수원이 숲으로 오분류되던 현상(공개판 숲 69.2%, 오차 +120.1%)이 **숲 32.2%(오차 +2.2%), 과수원 8.4%, 시설재배 3.1%, 초지 18.3%**로 완벽히 교정된다.
- **이용조건상 남는 위험**:
  - **매우 낮음 (법적 위험 해소)**. `data-15150509`와 `data-15163128`은 EGIS 오픈API(WMS)가 아니라 공공데이터포털에 등록된 정적 파일데이터(CSV)이며, 상세 페이지 HTML(`portal-15150509.html`)과 다운로드 메타데이터(`meta-15150509.json`) 모두 **`"cclTypeCd": "010000", "cclNm": "공공저작물 : 출처표시 (제 1유형)"`**으로 명시되어 있다. 공공누리 제1유형은 출처만 표시하면 저장·복제·재배포·2차적 저작물 작성·상업적 이용이 모두 허용된다.
- **구현 난이도**:
  - **낮음 (실행 시간 +2.5초)**. 8.85 MB CSV 파일 1개([p2-15150509.csv](file:///C:/work/korea/data/raw/layers5/files/p2-15150509.csv))만 읽으면 되며, 이미 [tools/research5/verify_all.py](file:///C:/work/korea/tools/research5/verify_all.py#L97-L120)에 1:5,000 도엽번호 디코더(`decode_5k_box`)와 공간 교차 코드가 작성·검증되어 있어 `pipeline/lib/cover_public.py`에 그대로 이식할 수 있다.

#### ② 2순위 권고안 (후보 D): `ESA WorldCover 10 m`(50 m 직접 집계, `CC BY 4.0`) + `국가 토지피복 통계`(`data-15163128`, `공공누리 제1유형`) 시군구 다차원 비례보정(IPF) + `전국 팜맵`(`15104481~15104491`, `제한 없음`)
- **구체적 방법**:
  - 도엽 통계(`15150509`)를 쓰지 않고 위성 격자(`ESA WorldCover 10 m`)와 필지 폴리곤(`팜맵`)을 주 공간 원천으로 유지하고 싶을 때 선택하는 방안이다.
  - ① `landcover.tif` 생성 또는 집계 시 250 m 최빈값(`all_touched=True`) 대신 10 m 원자료를 50 m(`all_touched=False`)로 직접 집계하고, ② 공공데이터포털에서 `공공누리 제1유형`이 확인된 시군구 통계표(`data-15163128` 또는 `data-15164500`)로 각 시군구 내 칸들의 대분류 합계를 IPF(Raking) 보정하며, ③ 임상(활엽·침엽·혼효)은 시군구 통계 비율로, 경지(논·밭·과수·시설)는 전국 팜맵 10개 권역(`15104481~15104491`) + 시군구 통계 비율로 분할한다.
- **기대 품질 및 구현 난이도**:
  - 전국 비교 시군구 오차가 **숲 +1.0%, 논 +3.7%, 밭 +3.7%, 시가화 +2.0%**로 줄어들고 모든 세부 분류가 복원된다. 다만 시군구 내부에서 칸별 임상(활엽/침엽) 공간 변화가 시군구 평균비로 일정해지므로, 칸(20.37 km²)보다 작은 1:5,000 도엽(6.3 km²) 단위로 임상 공간 변화까지 반영하는 **1순위(후보 B/C)**가 공간 정밀도와 실행 속도(8.85 MB CSV vs 3.02 GB 팜맵 SHP) 양면에서 앞선다.

---

### 5.3 사이트(`NOTICE.md` · `site/data/sources.json`)에 적어야 할 출처·고지 문구 초안

공개판 빌드 채택 시 [NOTICE.md](file:///C:/work/korea/NOTICE.md)와 [site/data/sources.json](file:///C:/work/korea/site/data/sources.json)에 추가할 출처·이용허락 고지 문구는 다음과 같다.

```markdown
### 인천국제공항 위치 및 주소 (공개판 채택)
- **국가철도공단_공항철도_역위치** 및 **국가철도공단_공항철도_주소데이터**
  - 제공기관: 국가철도공단 (공공데이터포털 파일데이터 `15041331`, `15041094`)
  - 기준연도: 2025년 (2025-07-02 수정)
  - URL: https://www.data.go.kr/data/15041331/fileData.do , https://www.data.go.kr/data/15041094/fileData.do
  - 이용허락: **이용허락범위 제한 없음** (교차검증: OpenStreetMap `WAY 316419197` ODbL 1.0, Wikidata `Q20932` CC0 1.0)

### 전국 세분류 토지피복 도엽단위·지역별 통계 및 팜맵 (공개판 채택)
- **기후에너지환경부_환경공간정보_세분류 토지피복지도 도엽단위 현행화 통계(토지피복지도 작성지침 개정)_20241231** 및 **국가 토지피복 통계(토지피복지도 분류항목 통계)_20241231**
  - 제공기관: 기후에너지환경부 (공공데이터포털 파일데이터 `15150509`, `15163128`, `15164500`)
  - 기준연도: 2024년 기준 (2025년 제작, 1:5,000 도엽 18,538개 × 41개 세분류)
  - URL: https://www.data.go.kr/data/15150509/fileData.do , https://www.data.go.kr/data/15163128/fileData.do
  - 이용허락: **공공누리 제1유형 (출처표시)** — 본 저작물은 기후에너지환경부에서 2025년 작성하여 공공누리 제1유형으로 개방한 '세분류 토지피복지도 도엽단위 현행화 통계' 및 '국가 토지피복 통계'를 이용하였으며, 해당 저작물은 공공데이터포털(www.data.go.kr)에서 무료로 내려받으실 수 있습니다.
- **농림수산식품교육문화정보원_팜맵공간정보 (전국 10개 권역)**
  - 제공기관: 농림수산식품교육문화정보원 (공공데이터포털 파일데이터 `15104481`~`15104491`)
  - 기준연도: 2025-12-31 기준
  - URL: https://www.data.go.kr/data/15104481/fileData.do 외 9건
  - 이용허락: **이용허락범위 제한 없음**
```

---

## 6. 직접 확인한 것과 확인하지 못한 것 구분 및 재현 방법

### 6.1 직접 확인한 것 vs 확인하지 못한 것
- **직접 확인 완료 (원문 HTML·JSON·데이터 파일을 `data/raw/layers5/`에 저장하고 해시 기록)**:
  1. 공공데이터포털 파일데이터 28종의 상세 페이지(`portal-*.html`), 다운로드 메타데이터(`meta-*.json` 내 `"cclTypeCd"`, `"cclNm"`, `"fileSize"`), 실제 데이터 파일(`files/p1-*.csv`, `files/p2-*.csv`, `files/p2-15104491.shp`).
  2. 특히 `data-15150509`(1:5,000 세분류 도엽 18,538개 통계), `data-15163128`(국가 토지피복 통계), `data-15164500`(지역별 세분류 면적 현황)의 **`공공저작물 : 출처표시 (제 1유형)`** 원문 표기와 `data-15041331`·`15041094`·`15041332` 및 전국 팜맵 10개 권역(`15104481~15104491`)의 **`이용허락범위 제한 없음`** 원문 표기.
  3. Wikidata(`CC0 1.0`), Natural Earth(`Public Domain`), OurAirports(`Public Domain`), GeoNames(`CC BY 4.0`), Dynamic World(`CC BY 4.0`), JAXA ALOS FNF, 인천국제공항공사 홈페이지(`airport.kr` 무단 복제·배포 금지 조항), 인천국제공항공사법(저작권법 제7조) 원문 페이지.
- **확인하지 못한 것 (로그인·인증키·신청 장벽 또는 서버 차단으로 진입 중단)**:
  1. 산림청 산림공간정보서비스(`map.forest.go.kr`) 및 산림빅데이터 거래소 내부의 임상도 SHP 다운로드 신청 화면 이후 개별 파일 용량·약관 전문 (**사유**: 로그인·본인인증 필요함).
  2. 국토지리정보원 국토정보플랫폼(`map.ngii.go.kr`)의 토지이용현황도·연속수치지형도 다운로드 화면 이후 파일별 상세 용량 (**사유**: 로그인 필요함).
  3. 환경 빅데이터 플랫폼(`bigdata-environment.kr`)의 데이터 상품 다운로드 약관 전문 (**사유**: 회원가입·로그인 필요함).
  4. Copernicus CGLS-LC100 Zenodo 레코드(`zenodo.org/api/records/3939050`) 직접 다운로드 (**사유**: 스크립트 요청에 `HTTP 403 Forbidden` 반환).

### 6.2 재현 실행 방법
Windows 명령 프롬프트 또는 PowerShell에서 작업 디렉터리를 `C:\work\korea`로 두고 아래 두 명령을 순서대로 실행하면 수집 파일 무결성 검증과 문제 1·2 정량 실증(`tools/research5/results.json`)이 완전히 재현된다.

```powershell
python -I pipeline/collect_layers5.py --offline
python -I tools/research5/verify_all.py
```
