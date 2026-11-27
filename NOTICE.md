# NOTICE — 출처와 이용조건

> 이 파일은 `pipeline/build_notice.py` 가 `site/data/sources.json` 에서 만든다. 손으로 고치지 않는다.
> 사이트의 출처 페이지(`site/sources/`)가 같은 기록을 더 자세히 보인다.

## 요약

- 이 사이트의 숫자와 위치는 정부·공공기관 등 65개 기관·출처가 공개한 자료 205건(통계표·지도 파일·법령)에서 왔다. 숫자를 손으로 넣지 않았고, 손으로 옮긴 표 4개(이름·코드 대응 등)는 '수작업'으로 표시했다.
- 개인·비상업 목적으로 공개한다. 자료마다 이용조건이 달라, 상업적으로 쓰려면 출처별 조건을 직접 확인해야 한다.
- 이 사이트는 정부·공공기관과 관계가 없다. 통계의 가공·표현에 대한 책임은 제작자에게 있다.
- 기준: 인구 2026-09 주민등록, 자료 수집 2026-11-26–2026-11-27, 이용허락 확인 2026-11-27, 출처 목록 빌드 2026-11-27.
- 이용조건에 제한이 있는 자료 6건, 이용허락을 확인하지 못한 자료 34건 — 아래에 따로 적었다.

## 이 판: 공개판 (`public`)

이 사이트는 공개판(profile public)으로 빌드했다. 개인·비상업 목적의 공개를 위해 이용조건이 공개 배포를 막는 자료 3묶음(26건)을 뺐다. 뺀 것과 까닭은 아래에 있다. 판 차이가 아닌 것: 칸 토지피복 (대표 피복·비율·숲 종류·논밭): 기후에너지환경부 세분류 토지피복지도 도엽단위 현행화 통계(공공데이터포털 15150509, 공공누리 제1유형)를 칸에 나눈 값. 두 판이 같다. 기후에너지환경부 환경공간정보서비스 WMS 그림(Open API 약관이 저장·전송을 막음) — 어느 판에서도 읽지 않는다. 인천공항 위치: 국가철도공단 공항철도 역위치(15041331, 이용허락범위 제한 없음)의 제1·2여객터미널 역 좌표 중점 — 공항 기준점이 아님. 두 판이 같다. 항공정보간행물(AIP) 공항 기준점 좌표(허락 없는 복제·배포 제한) — 어느 판에서도 쓰지 않는다.

| 묶음 | 무엇 | 까닭 | 대신 | 출처 key |
|---|---|---|---|---|
| `housing` | 아파트 매매·전세 실거래 중위값 (렌즈 2종, 도시·시도 패널 값, 순위·전국 기준, 닮은 도시의 매매가 차이) | 국토교통부 실거래가 공개시스템의 계약일 기준 내려받기 자료로 직접 계산한 값이다. 그 안내가 외부 공개 때는 신고일 기준 공식통계를 쓰라고 해 공개판에서는 뺀다 (감사 02). 다른 값으로 메우지 않는다. | 대신하지 않음 (빈 자리로 둔다) | `molit-apartment-lease-2025-11`, `molit-apartment-lease-2025-12`, `molit-apartment-lease-2026-01`, `molit-apartment-lease-2026-02`, `molit-apartment-lease-2026-03`, `molit-apartment-lease-2026-04`, `molit-apartment-lease-2026-05`, `molit-apartment-lease-2026-06`, `molit-apartment-lease-2026-07`, `molit-apartment-lease-2026-08`, `molit-apartment-lease-2026-09`, `molit-apartment-lease-2026-10`, `molit-apartment-sale-2025-11`, `molit-apartment-sale-2025-12`, `molit-apartment-sale-2026-01`, `molit-apartment-sale-2026-02`, `molit-apartment-sale-2026-03`, `molit-apartment-sale-2026-04`, `molit-apartment-sale-2026-05`, `molit-apartment-sale-2026-06`, `molit-apartment-sale-2026-07`, `molit-apartment-sale-2026-08`, `molit-apartment-sale-2026-09`, `molit-apartment-sale-2026-10` |
| `mines` | 가행 광산 293곳 (광산 아이콘, 도시·시도 패널의 광종별 수) | 한국광해광업공단 국내광산검색의 이용 안내가 웹을 통한 제3자 제공에 사전 협의·허락을 요구한다 (감사 03). | 대신하지 않음 (빈 자리로 둔다) | `komir-mine-grid` |
| `hanwoo` | 한우 사육 마릿수 (상위 15 아이콘, 도시·시도 패널 값) | 축산물이력제 저작권보호정책이 저작권자의 사전승낙 없이 제3자에게 제공하는 것을 막는다 (감사 03). | 대신하지 않음 (빈 자리로 둔다) | `mtrace-hanwoo-202610` |

### 변경금지 통계 — 원 통계를 바꾸지 않고 모아 보이기만 한다

변경금지(공공누리 제3·4유형) 조건이 붙은 통계: 원 통계를 바꾸지 않는다 — 원값을 모으고(합·비율) 그대로 보이기만 하며, 출처를 밝힌다.

- 보건복지부 「2025년 국민기초생활보장 수급자 현황」 (`mohw-welfare-2025`, 출처표시·상업적 이용금지·변경금지) — 실린 곳: 렌즈 '기초생활 수급' (lenses.json lenses[id=assistance])
- 경상북도 「2024년 기준 시군별 산업세세분류별 현황」 (`gyeongbuk-business-2024`, 공공누리 제3유형) — 실린 곳: 도시 패널 주력 업종 최신 값 (경북) (resources.json key_industries.by_city)
- 세종특별자치시 「2024년 기준 전국사업체조사 통계표」 (`sejong-business-2024`, 공공누리 제4유형) — 실린 곳: 도시 패널 주력 업종 최신 값 (세종) (resources.json key_industries.by_city)

### 허락 조건이 상업 이용에만 걸려 남긴 자료

- 「SRTM30+ 표고·수심 (30 arc-sec, 약 0.9 km)」 (`terrain_srtm30plus`) — 교육·연구·비영리 목적의 복제·배포는 지정한 고지와 문단을 함께 싣는 조건으로 허용되고, 상업 이용만 UC San Diego 와 협의한다. 고지 원문을 NOTICE.md 와 출처 쪽에 싣는다.
- 「2. 산업소분류 및 시군구별 사업체수, 종사자수」 (`gyeonggi-business-2019`) — 경기도 승인은 상업적 이용에만 필요하다 (서비스 이용약관 제12조).
- 「2. 산업소분류 및 시군구별 사업체수, 종사자수」 (`gyeonggi-business-2024`) — 경기도 승인은 상업적 이용에만 필요하다 (서비스 이용약관 제12조).

판은 둘이다. 공개판: python pipeline/build_all.py --profile public (GitHub Pages 에 올리는 판). 전체판: python pipeline/build_all.py --profile full (내부 열람용, 기본값). 빼는 자료와 까닭은 pipeline/lib/profile.py 의 EXCLUDE 한 곳에 있다.

## 코드

- 이 저장소의 코드: Apache License 2.0 (`LICENSE`). 이 이용허락은 우리가 만든 코드·디자인·문서에만 미친다. 아래 자료·글꼴에는 각자의 조건이 따로 있다.

## 표고 자료 고지 — SRTM30+ 표고·수심 (30 arc-sec, 약 0.9 km) (`terrain_srtm30plus`)

제공자(Scripps·NOAA ERDDAP 자료 정보 쪽의 license 속성)가 교육·연구·비영리 목적의 복제·수정·배포에 붙인 조건: 저작권 고지(아래 첫 문단), 허락 문단(둘째)과 뒤따르는 세 문단을 모든 사본에 싣는다. 원문을 고치지 않고 옮겼다 (줄바꿈은 원문의 <br> 그대로).

원문: https://coastwatch.pfeg.noaa.gov/erddap/info/srtm30plus_LonPM180/index.html (보관본 `data/raw/layers4/terrain.html`, sha256 `bed77451f3f9c0d6a497d0eb725b3a874231383be621cda89a336a6a472dd5bd`)

```text
David T. Sandwell, Joseph J. Becker, and Walter H. F. Smith.
The Regents of the University of California
All Rights Reserved

Permission to copy, modify and distribute any part of this gridded bathymetry at 30 second resolution for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted provided that the above notice, this paragraph and the following three paragraphs appear in all copies.

Those desiring to incorporate this global bathymetry into commercial products or use for commercial purposes should contact the Technology Transfer & Intellectual Property Services, University of California, San Diego, 9500 Gilman Drive, Mail Code 0910, La Jolla, CA 92093-0910, Ph: (858) 534-5815, FAX: (858) 534-7345, E-MAIL:invent@ucsd.edu.

IN NO EVENT SHALL THE UNIVERSITY OF CALIFORNIA BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS, ARISING OUT OF THE USE OF THIS global bathymetry, EVEN IF THE UNIVERSITY OF CALIFORNIA HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

THE global bathymetry PROVIDED HEREIN IS ON AN "AS IS" BASIS, AND THE UNIVERSITY OF CALIFORNIA HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR MODIFICATIONS.  THE UNIVERSITY OF CALIFORNIA MAKES NO REPRESENTATIONS AND EXTENDS NO WARRANTIES OF ANY KIND, EITHER IMPLIED OR EXPRESS, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE, OR THAT THE USE OF THE global bathymetry WILL NOT INFRINGE ANY PATENT, TRADEMARK OR OTHER RIGHTS.
```

상업 이용 조건 (코드의 Apache 2.0 이용허락과 별개): SRTM30+ 에서 낸 표고·수심·기복·먼바다/연안 구분(world.json 의 elev·elev_sd·relief·water, ridges.json 의 산줄기)은 교육·연구·비영리 목적으로만 복제·배포할 수 있다. 상업 제품에 넣거나 상업 목적으로 쓰려면 UC San Diego 기술이전실(invent@ucsd.edu)과 먼저 협의해야 한다. 저장소 코드의 Apache 2.0 이용허락은 이 자료에 미치지 않는다.

## OpenStreetMap 파생 자료 (ODbL) — `osm-water`

이 사이트의 호수·저수지 수면(world.json 의 lakes·lake_labels·lake_meta 와 water = 3 '호수' 칸)은 OpenStreetMap 자료에서 만든 파생 데이터베이스다. © OpenStreetMap 기여자. Open Database License(ODbL) 1.0 으로 이용할 수 있다: https://opendatacommons.org/licenses/odbl/1-0/ · https://www.openstreetmap.org/copyright. 파생 자료 전체는 이 저장소의 site/data/world.json 에 그대로 있고(위 필드), 만든 방법은 pipeline/collect_layers_terrain.py(OSM 추출 -> lakes.geojson)와 pipeline/build_world.py(칸 판정·단순화)에 있다.

## 이용허락 유형별 건수

자료 출처 205건.

| 이용허락 (짧은 표기) | 건수 |
|---|---:|
| KOSIS 이용조건 | 95 |
| 이용허락범위 제한 없음 | 49 |
| 이용허락 미확인 | 34 |
| CC BY 4.0 | 7 |
| 공공누리 제1유형 | 4 |
| 보호받지 못하는 저작물 | 4 |
| 상업적 이용 승인 필요 | 2 |
| 영리 포함 자유 이용 | 2 |
| 퍼블릭 도메인 | 2 |
| ODbL 1.0 | 1 |
| 공공누리 제3유형 | 1 |
| 공공누리 제4유형 | 1 |
| 교육·연구·비영리 이용 조건 | 1 |
| 출처표시 | 1 |
| 출처표시·상업적 이용금지·변경금지 | 1 |

## 이용조건에 제한이 있는 자료

이용조건 분류는 이용허락 원문(license)과 이용허락 표의 메모(license_note)에 그 갈래의 문구가 있는지로 정한다(자료마다 손으로 고르지 않는다; API 이용약관은 기록의 restriction 필드): 비상업 조건: 상업적 이용을 금지하거나, 교육·연구·비영리 목적으로만 허용한다 / 변경 금지: 원 저작물의 변경(가공)을 금지하거나 제한한다 / 사전 허락·협의: (영리) 이용·제3자 제공 전에 제공기관의 승인·허락·협의가 필요하다 / API 이용약관: Open API 약관이 저장·복제·전송과 비상업 이용을 제한한다 (기록의 restriction) / 외부 공개 조건: 외부에 공개할 때 지켜야 할 조건이 원문에 있다. 이용허락을 확인하지 못한 자료('미확인')는 메모에 다른 자료의 조건이 적혀 있어도 분류하지 않고 따로 적는다. 분류에 들지 않았다고 조건이 없다는 뜻은 아니다 — 출처 표시 등 원문의 조건은 모두 지켜야 한다.

| 자료 | 기관 | 분류 | 이용허락 원문 | 사이트에서 쓰는 곳 |
|---|---|---|---|---|
| SRTM30+ 표고·수심 (30 arc-sec, 약 0.9 km) (`terrain_srtm30plus`) | Scripps / NOAA ERDDAP | 비상업 조건 · 사전 허락·협의 | for educational, research and non-profit purposes — SRTM30+ 30초 격자. 복제 시 원문의 고지와 지정 문단을 포함. 상업 제품·상업 목적 이용은 UC San Diego와 협의. | 칸 표고·기복(평지/구릉/산/고봉), 먼바다/연안 구분 · 지도 바탕 · 실린 필드: 지도 바탕 (두 판에 늘 그림) (`world.json` `owner`); 칸 표고 (`world.json` `elev`); 칸 기복 (`world.json` `elev_sd`); 평지·구릉·산·고봉 (`world.json` `relief`); 먼바다·연안 구분 (`world.json` `water`); 산줄기 (신여지도) (`ridges.json` `lines`) |
| 2. 산업소분류 및 시군구별 사업체수, 종사자수 외 1건 (`gyeonggi-business-2019` … `gyeonggi-business-2024`) | 경기도 | 비상업 조건 · 사전 허락·협의 | 경기도의 명시적 승인 없이 상업적으로 사용할 수 없으며 — 서비스 이용약관 제12조. 저작자·출처표시, 제3자 조건 우선, 상업 이용은 승인 필요. | 종사자 (합계·제조업) · 실린 필드: 도시 종사자 합계·제조업 (`cities.json` `[*].workers`); 도시 산업 대분류 종사자 (`cities.json` `[*].jobs`) |
| 2025년 국민기초생활보장 수급자 현황 (`mohw-welfare-2025`) | 보건복지부 | 비상업 조건 · 변경 금지 | 출처표시+상업적이용금지+변경금지 — 보건복지부 원 게시물 공공누리 제4유형. 첨부 PDF SHA-256이 프로젝트 PDF와 일치. | 기초생활 수급 · 렌즈: 기초생활 수급 · 실린 필드: 렌즈 '기초생활 수급' (`lenses.json` `lenses[id=assistance]`) |
| 2024년 기준 시군별 산업세세분류별 현황 (`gyeongbuk-business-2024`) | 경상북도 | 변경 금지 | 공공누리 제3유형(출처표시 + 변경금지) | 주력 업종 최신 값: 경북 2024 (도시 패널 병기) · 실린 필드: 도시 패널 주력 업종 최신 값 (경북) (`resources.json` `key_industries.by_city`) |
| 2024년 기준 전국사업체조사 통계표 (`sejong-business-2024`) | 세종특별자치시 | 비상업 조건 · 변경 금지 | 공공누리 4유형 출처표시 + 상업적 이용금지 + 변경금지 | 주력 업종 최신 값: 세종 2024 (도시 패널 병기) · 실린 필드: 도시 패널 주력 업종 최신 값 (세종) (`resources.json` `key_industries.by_city`) |

## 이용허락 미확인

34건. 이용허락 문구를 확인하지 못했다. 쓰기 전에 제공기관에 확인해야 한다.

- 충청북도 「2019년 기준 충청북도 사업체조사 통계표」 (`chungbuk-business-2019`) — 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함. — 실린 필드: 도시 종사자 합계·제조업 (`cities.json` `[*].workers`); 도시 산업 대분류 종사자 (`cities.json` `[*].jobs`)
- 충청북도 「2024년 기준 충청북도 사업체조사 통계표」 (`chungbuk-business-2024`) — 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함. — 실린 필드: 도시 종사자 합계·제조업 (`cities.json` `[*].workers`); 도시 산업 대분류 종사자 (`cities.json` `[*].jobs`)
- 제주특별자치도 「2019년 기준 제주특별자치도 사업체조사 통계표」 (`jeju-business-2019`) — 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함. — 실린 필드: 도시 종사자 합계·제조업 (`cities.json` `[*].workers`); 도시 산업 대분류 종사자 (`cities.json` `[*].jobs`)
- 제주특별자치도 「2024년 기준 제주특별자치도 사업체조사 통계표」 (`jeju-business-2024`) — 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함. — 실린 필드: 도시 종사자 합계·제조업 (`cities.json` `[*].workers`); 도시 산업 대분류 종사자 (`cities.json` `[*].jobs`)
- 전북특별자치도 「2024년 기준 전북특별자치도 사업체조사 통계표」 (`jeonbuk-business-2024`) — 공식 페이지에서 해당 자료의 이용허락 문구를 확인하지 못함. — 실린 필드: 도시 종사자 합계·제조업 (`cities.json` `[*].workers`); 도시 산업 대분류 종사자 (`cities.json` `[*].jobs`)
- 전라남도 「2019년 기준 사업체조사」 (`jeonnam-business-2019`) — 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함. — 실린 필드: 도시 종사자 합계·제조업 (`cities.json` `[*].workers`); 도시 산업 대분류 종사자 (`cities.json` `[*].jobs`)
- 전라남도 「2024년 기준 전남 사업체조사 결과」 (`jeonnam-business-2024`) — 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함. — 실린 필드: 도시 종사자 합계·제조업 (`cities.json` `[*].workers`); 도시 산업 대분류 종사자 (`cities.json` `[*].jobs`)
- 세종특별자치시 「제13회 세종통계연보」 (`sejong-yearbook-2024`) — 공식 페이지에서 해당 자료의 이용허락 문구를 확인하지 못함. — 실린 필드: 렌즈 '1인당 GRDP' (`lenses.json` `lenses[id=gdp_pc]`); 렌즈 '고용률' (`lenses.json` `lenses[id=employment]`); 렌즈 '기초생활 수급' (`lenses.json` `lenses[id=assistance]`); 렌즈 '최대 산업' (`lenses.json` `lenses[id=top_industry]`); 렌즈 '제조업 비중' (`lenses.json` `lenses[id=manufacturing_share]`); 렌즈 '농림어업 비중 (렌즈 막대에서 뺀 지표)' (`lenses.json` `retired_values.items[id=farm_share]`); 도시 농가 가구·인구 (`cities.json` `[*].farm`); 도시 종사자 합계·제조업 (`cities.json` `[*].workers`); 도시 산업 대분류 종사자 (`cities.json` `[*].jobs`); 도시 고용률·실업률 (`cities.json` `[*].employment`); 도시 GRDP·산업별 부가가치·다섯 산출 (`cities.json` `[*].gdp_by_industry`); 시도 GRDP 시군구 합 (`states.json` `[*].gdp_by_industry`)
- 서울특별시 「사업소 특성별 산업대분류별 구·동별 현황」 (`seoul-business-10160`) — 데이터 허브 응답의 라이선스 항목 값이 비어 있음. — 수집 기록의 값: 자유이용 불가 — 실린 필드: 도시 종사자 합계·제조업 (`cities.json` `[*].workers`); 도시 산업 대분류 종사자 (`cities.json` `[*].jobs`)
- 국세청 「시·군·구별 근로소득 연말정산 신고현황(주소지)」 (`tasis-4-2-15-2022`) — 통계 페이지는 JavaScript 화면으로, 해당 표의 이용조건 원문을 확보하지 못함. — 실린 필드: 렌즈 '1인당 총급여' (`lenses.json` `lenses[id=wage]`); 도시 1인당 총급여 (`cities.json` `[*].wage`)
- 국립환경과학원 「2025 대기환경연보」 (`air-yearbook-2025`) — 2025년 연보의 이용표시 미확인. 포털의 2019년 연보 조건을 이월하지 않음. — 실린 필드: 렌즈 '초미세먼지' (`lenses.json` `lenses[id=pm25]`)
- 한국환경공단 에어코리아 「에어코리아 측정소 정보(측정망 1)」 (`airkorea-stations`) — 웹 측정소 표의 표시 미확인. 별도 포털 API에는 출처표시·변경금지(제3유형). — 실린 필드: 렌즈 '초미세먼지' (`lenses.json` `lenses[id=pm25]`)
- 행정안전부 「2024년 자연재해상황통계 선공개」 (`disaster-2024`) — 공식 페이지에서 해당 자료의 이용허락 문구를 확인하지 못함. — 실린 필드: 렌즈 '자연재난 피해' (`lenses.json` `lenses[id=disaster]`)
- 한국전력거래소 「발전기 현황」 (`epsis-generators`) — 포털 발전설비 등록건의 메뉴 ID와 내려받은 표의 ID가 다름. — 실린 필드: 층 'nuclear' 5개 (`resources.json` `items[kind=nuclear]`); 층 'power_coal' 14개 (`resources.json` `items[kind=power_coal]`); 층 'power_gas' 36개 (`resources.json` `items[kind=power_gas]`); 층 'power_hydro' 13개 (`resources.json` `items[kind=power_hydro]`); 층 'power_oil' 규칙·출처 (`resources.json` `kinds.power_oil`); 층 'power_solar' 14개 (`resources.json` `items[kind=power_solar]`); 층 'power_sums' 규칙·출처 (`resources.json` `kinds.power_sums`); 층 'power_wind' 8개 (`resources.json` `items[kind=power_wind]`)
- 산림청 「임산물 지리적표시 등록 현황」 (`forest-gi`) — 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함. — 실린 필드: 층 'gi' 56개 (`resources.json` `items[kind=gi]`)
- 국립공원공단 「2026 국립공원기본통계 수정 공표」 (`knps-statistics`) — 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함. — 수집 기록의 값: 공공누리 제1유형 — 실린 필드: 층 'national_park' 규칙·출처 (`wonders.json` `kinds.national_park`); 국립공원 탐방객 (`wonders.json` `parks`)
- 행정안전부 지방재정365 「재정자립도[당초] 시도별 현황」 (`lofin-fiscal-2026`) — 지방재정365 이용정책 본문이 응답에 없음. 포털의 API 조건을 웹 조회표에 적용할 수 있는지 미확인. — 실린 필드: 렌즈 '재정자립도' (`lenses.json` `lenses[id=fiscal]`); 전국 공식값 (`nation.json` `nation.official`); 시도 공식값 (`states.json` `[*].official`)
- 해양수산부 「2025년 전국 항만 물동량 발표」 (`mof-ports-2025`) — 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함. — 실린 필드: 층 'trade_port' 규칙·출처 (`infrastructure.json` `kinds.trade_port`); 무역항 컨테이너 발표값 (`infrastructure.json` `items`)
- 행정안전부 「2026년 지방자치단체 행정구역 및 인구 현황」 (`municipalities-2025`) — 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함. — 실린 필드: 시군구청 소재지 (`cities.json` `[*].offices`); 시도청 소재지 (`states.json` `[*].offices`)
- 해양수산부 국가물류통합정보센터 「항만별 물동량 통계」 (`nlic-ports-2025`) — 공식 페이지에서 해당 자료의 이용허락 문구를 확인하지 못함. — 실린 필드: 층 'trade_port' 규칙·출처 (`infrastructure.json` `kinds.trade_port`); 무역항 화물 (`infrastructure.json` `items`)
- 해양수산부 「1/25,000 연안정보도 갯벌」 (`tidal-flat-shp`) — 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함. — 실린 필드: 지도 바탕 (두 판에 늘 그림) (`world.json` `owner`); 갯벌 칸·비율·시도별 넓이 (`world.json` `tidal`)
- 국가수자원관리종합정보시스템(WAMIS) 「하천유로선_지방하천」 (`wamis-rivlinel`) — 공식 페이지를 받지 못함. 500 Server Error:  for url: https://map.wamis.go.kr:8445/ — 실린 필드: 지도 바탕 (두 판에 늘 그림) (`world.json` `owner`); 지방하천 선 (확대 시) (`world.json` `rivers`)
- 국가수자원관리종합정보시스템(WAMIS) 「하천유로선_국가하천」 (`wamis-rivlinen`) — 공식 페이지를 받지 못함. 500 Server Error:  for url: https://map.wamis.go.kr:8445/ — 실린 필드: 지도 바탕 (두 판에 늘 그림) (`world.json` `owner`); 국가하천 선·이름표 (`world.json` `rivers`); 산줄기 계산의 물줄기 (`ridges.json` `lines`)
- 충청남도 「2024년 기준 사업체조사 보고서」 (`chungnam-business-2024`) — 공식 페이지에서 해당 자료의 이용허락 문구를 확인하지 못함. — 실린 필드: 도시 패널 주력 업종 최신 값 (충남) (`resources.json` `key_industries.by_city`)
- 국가수자원관리종합정보시스템 「WAMIS 댐 관측소」 (`wamis-dam-observations`) — OGC 서비스 설명에서 댐 관측소 재배포 조건 미확인. — 실린 필드: 층 'dam' 30개 (`resources.json` `items[kind=dam]`)
- 고려대학교 · 광주과학기술원 · 대구경북과학기술원 등 「과학기술원·출연연·대학 누리집 (하단 연락처 주소) (파일 8개)」 (`institution`) — 여러 대학·연구기관의 연락처 페이지를 합친 기록으로 전체에 적용할 이용조건 미확인. — 실린 필드: 층 'knowledge' 8개 (`wonders.json` `items[kind=knowledge]`)
- 국립공원공단 「2026 국립공원기본통계 수정 공표」 (`knps-area-2025`) — 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함. — 수집 기록의 값: 공공누리 제1유형 — 실린 필드: 층 'national_park' 규칙·출처 (`wonders.json` `kinds.national_park`); 국립공원 공식 지정면적 (`wonders.json` `parks`)
- 국가유산청 「국가유산포털 세계유산 해설·궁능유적본부 왕릉 일람표 (구성 유산) (파일 18개)」 (`khs`) — 여러 해설·왕릉 일람표를 합친 자료로 각각의 공공누리 표시 미확인. — 실린 필드: 층 'world_heritage' 55개 (`wonders.json` `items[kind=world_heritage]`); 세계유산 구성 유산 (`wonders.json` `world_heritage`)
- 국가데이터처 가축동향조사 (축산유통 통계누리) 「돼지 시도 사육규모별 농장수 및 마리수」 (`mtrace-pig-sido-2026q3`) — 축산물이력제의 정책 문구는 쇠고기이력추적제에 한정된다. 돼지 통계표에 적용되는 허락 미확인. — 실린 필드: 층 'pigs' 규칙·출처 (`resources.json` `kinds.pigs`); 시도 패널 돼지 (2026 3분기) (`resources.json` `farm.pigs_sido_2026`)
- 수작업 「수도 표시 (서울)」 (`manual_national_capital`) — 자체 수작업 표로 출판된 원자료와 이용허락 원문을 특정하지 못함. — 실린 필드: 수도 표식 (`cities.json` `[*].capital`)
- 수작업 (지방자치법 제198조 지정 현황) 「특례시 표」 (`manual_special_cities`) — 자체 수작업 표로 출판된 원자료와 이용허락 원문을 특정하지 못함. — 실린 필드: 도시 종류 '특례시' (`cities.json` `[*].kind`)
- 수작업 (pipeline/lib/address.py) 「시도 이름 별칭표 (주소 대응)」 (`manual_address`) — 자체 수작업 표로 출판된 원자료와 이용허락 원문을 특정하지 못함. — 실린 필드: 주소로 놓은 층 항목의 시군구 (`resources.json` `items`)
- 수작업 (pipeline/lib/crosswalk.py) 「행정구역 코드 대응표」 (`manual_crosswalk`) — 자체 수작업 표로 출판된 원자료와 이용허락 원문을 특정하지 못함. — 실린 필드: 과거 인구 시계열 (`cities.json` `[*].pop_series`); 5년 인구 증감 (`cities.json` `[*].growth_5y`)
- 공공데이터포털 「대학 주소 (공공데이터포털 표준데이터 15107736)」 (`data-15107736-univ-address`) — 실린 필드: 연구대학 주소 → 시군구 (`wonders.json` `universities`)

## 출처 표기

그대로 옮겨 쓸 수 있는 표기:

```text
koreaciv · 신여지도 — 공공 통계로 그린 대한민국 지도 (개인·비상업 목적 공개, 정부·공공기관과 관계 없음)
자료: 국가데이터처, 행정안전부, 국가유산청, 제주특별자치도, ESA WorldCover Consortium, 인천광역시 등 65개 기관·출처의 공개 자료 205건을 가공 (인구 기준 2026-09, 빌드 2026-11-27)
행정안전부·통계청 자료 기반, vuski/admdongkor 정리본 — 행정동 경계 (ver20261001) (CC BY 4.0)
Scripps / NOAA ERDDAP — SRTM30+ 표고·수심 (30 arc-sec, 약 0.9 km) (교육·연구·비영리 이용 조건)
© OpenStreetMap contributors / Geofabrik — OpenStreetMap South Korea extract (ODbL 1.0)
ESA WorldCover Consortium — ESA WorldCover 타일 6장 (CC BY 4.0)
출처별 이용허락과 조건: 사이트의 출처 페이지(sources/)와 저장소의 NOTICE.md
```

이용허락별 기관 (출처 표기 줄):

- KOSIS 이용조건: 국가데이터처 · 국세청 · 서울특별시 · 부산광역시 · 대구광역시 · 인천광역시 · 광주광역시 · 대전광역시 · 울산광역시 · 경기도 · 강원특별자치도 · 충청북도 · 충청남도 · 전북특별자치도 · 전라남도 · 경상북도 · 경상남도 · 제주특별자치도 · 행정안전부 · 질병관리청
- 이용허락범위 제한 없음: 행정안전부 · 국립공원공단 · 국가유산청 · 원자력안전위원회 · 한국수자원공사 · 한국산업단지공단 · 해양수산부 · 한국광해광업공단 · 국가철도공단 · 인천광역시 · 충청북도 · 국토교통부 항공정보포털 · 한국공항공사 · 국가과학기술연구회 · 기후에너지환경부 국립환경과학원 · 부산항만공사 · 국립수산물품질관리원 · 국토교통부 국가교통정보센터 · 국립농산물품질관리원 · 국가물류통합정보센터 (국가교통DB) · 국가보훈부
- 이용허락 미확인: 충청북도 · 제주특별자치도 · 전북특별자치도 · 전라남도 · 세종특별자치시 · 서울특별시 · 국세청 · 국립환경과학원 · 한국환경공단 에어코리아 · 행정안전부 · 한국전력거래소 · 산림청 · 국립공원공단 · 행정안전부 지방재정365 · 해양수산부 · 해양수산부 국가물류통합정보센터 · 국가수자원관리종합정보시스템(WAMIS) · 충청남도 · 국가수자원관리종합정보시스템 · 고려대학교 · 광주과학기술원 · 대구경북과학기술원 등 · 국가유산청 · 국가데이터처 가축동향조사 (축산유통 통계누리) · 수작업 · 수작업 (지방자치법 제198조 지정 현황) · 수작업 (pipeline/lib/address.py) · 수작업 (pipeline/lib/crosswalk.py) · 공공데이터포털
- CC BY 4.0: 행정안전부·통계청 자료 기반, vuski/admdongkor 정리본 · ESA WorldCover Consortium
- 공공누리 제1유형: 기후에너지환경부 · 서울특별시 · 가축위생방역지원본부
- 보호받지 못하는 저작물: 법제처 국가법령정보센터
- 상업적 이용 승인 필요: 경기도
- 영리 포함 자유 이용: 관세청
- 퍼블릭 도메인: Natural Earth
- ODbL 1.0: © OpenStreetMap contributors / Geofabrik
- 공공누리 제3유형: 경상북도
- 공공누리 제4유형: 세종특별자치시
- 교육·연구·비영리 이용 조건: Scripps / NOAA ERDDAP
- 출처표시: 대학알리미
- 출처표시·상업적 이용금지·변경금지: 보건복지부

## 계산한 층

원자료에서 이 프로젝트가 계산한 것. 규칙 문장 전문은 출처 페이지에 있다.

- **산줄기 (분수계, 계산한 선)** (`site/data/ridges.json`) — 입력: 출처 4건 — `terrain_srtm30plus`, `wamis-rivlinen`, `wamis-rivlinel`, `boundary_admdong`
- **칸 기복 (평지·구릉·산·고봉)** (`site/data/world.json`) — 입력: 출처 1건 — `terrain_srtm30plus`
- **칸 인구 (읍면동 값을 칸에 내림)** (`site/data/lenses.json`) — 입력: 출처 3건 — `jumin_age5_emd`, `jumin_age5_sgg`, `boundary_admdong`
- **소멸위험지수** (`site/data/lenses.json`) — 입력: 출처 2건 — `jumin_age5_emd`, `jumin_age5_sgg`
- **건강 지수** (`site/data/lenses.json`) — 입력: 출처 4건 — `kosis-177-DT_HEALTH_RECOG`, `kosis-177-DT_H_MENTAL_DEPRESS`, `kosis-177-DT_H_OBE_OBE`, `kosis-177-DT_H_SM`
- **초미세먼지 칸 값 (측정소 거리 역가중)** (`site/data/lenses.json`) — 입력: 출처 2건 — `air-yearbook-2025`, `airkorea-stations`
- **칸 토지피복 비율** (`site/data/world.json`) — 입력: 출처 8건 — `data-15150509`, `worldcover-N33E123`, `worldcover-N33E126`, `worldcover-N33E129`, `worldcover-N36E123` 외 3건
- **다섯 산출 (식량·생산·금·과학·문화)** (`site/data/nation.json`) — 입력: 출처 17건 — `kosis-201-DT_201012_D040027`, `kosis-202-DT_F10107`, `kosis-203-DT_2020Y22GRDP1`, `kosis-204-DT_2020Y23GRDP1`, `kosis-205-DT_2020Y24GRDP1` 외 12건
- **입지계수 (LQ)** (`site/data/nation.json`) — 입력: 출처 54건 — `kosis-201-DT_201012_D040027`, `kosis-202-DT_F10107`, `kosis-203-DT_2020Y22GRDP1`, `kosis-204-DT_2020Y23GRDP1`, `kosis-205-DT_2020Y24GRDP1` 외 49건
- **도시 특성 표시** (`site/data/nation.json`) — 입력: 출처 28건 — `kosis-201-DT_201012_D040027`, `kosis-202-DT_F10107`, `kosis-203-DT_2020Y22GRDP1`, `kosis-204-DT_2020Y23GRDP1`, `kosis-205-DT_2020Y24GRDP1` 외 23건
- **닮은 도시** (`site/data/nation.json`) — 입력: 출처 21건 — `jumin_age5_emd`, `jumin_age5_sgg`, `kosis-201-DT_201012_D040027`, `kosis-202-DT_F10107`, `kosis-203-DT_2020Y22GRDP1` 외 16건
- **전국 기준 대비와 순위 막대** (`site/data/nation.json`) — 입력: 출처 30건 — `jumin_age5_emd`, `jumin_age5_sgg`, `kosis-201-DT_201012_D040027`, `kosis-202-DT_F10107`, `kosis-203-DT_2020Y22GRDP1` 외 25건
- **추천 시점 여섯** (`site/data/nation.json`) — 입력: site/data 의 계산 값 (원자료를 직접 읽지 않는다)

## 글꼴

| 글꼴 | 쓰임 | 만든 이 | 이용허락 | 이용허락 파일 | 실린 파일 |
|---|---|---|---|---|---|
| Hahmlet (함렛) | 제목 · 고을 이름 · 큰 숫자 | The Hahmlet Project Authors — 함민주(한글), Mark Frömberg(라틴) / Hypertype | SIL Open Font License 1.1 | `site/yeojido/fonts/Hahmlet-OFL.txt` | `site/yeojido/fonts/Hahmlet-VF.subset.woff2` |
| Pretendard Variable 1.309 의 수정본 (내부 이름 Yeojido Sans) | 본문 · 표 · 단추 | 길형진 (Kil Hyung-jin). 바탕: Inter (The Inter Project Authors), Source Han Sans (Adobe), M PLUS 1 (The M+ FONTS Project Authors) | SIL Open Font License 1.1 (예약 글꼴 이름: Pretendard, Source, Inter, M PLUS 1) | `site/yeojido/fonts/YeojidoSans-Pretendard-OFL.txt` | `site/yeojido/fonts/YeojidoSans-VF.subset.woff2` |
| Noto Serif KR | 자료 속 한자 (문화유산 이름 등) | Adobe · Google (Source Han Serif 의 Noto 판) | SIL Open Font License 1.1 | `site/yeojido/fonts/NotoSerifKR-OFL.txt` | `site/yeojido/fonts/NotoSerifKR-VF.hanja.woff2` |
| Yuji Syuku Regular | 제호 곁글 한자 新輿地圖 | The Yuji Project Authors — 글씨 片岡佑之(Kataoka Yuji), Kinuta Font Factory | SIL Open Font License 1.1 | `site/yeojido/fonts/YujiSyuku-OFL.txt` | `site/yeojido/fonts/title-hanja.svg`, `site/yeojido/fonts/title-hanja.woff2` |
| Hahmlet 900 윤곽 + 계산한 인변 | 낙관 (한글 「신여지도」) | The Hahmlet Project Authors (글자 윤곽) | SIL Open Font License 1.1 | `site/yeojido/fonts/Hahmlet-OFL.txt` | `site/yeojido/fonts/seal.svg`, `site/yeojido/fonts/seal-mask.svg` |

## 그 밖의 표기

- **koreaciv · 신여지도 — 이 저장소가 만든 것 (코드, 화면 디자인, 문서, 수업안)** — 제작자. 저장소 전체의 코드·디자인·문서·수업안 (자료·글꼴 제외). 이용허락: Apache License 2.0 — 저장소의 LICENSE. 이 이용허락은 우리가 만든 것에만 적용된다. 위 자료와 글꼴에는 각자의 조건이 따로 있다.
- **usaciv — the United States as a strategy game** — karpathy.ai <https://karpathy.ai/usaciv/>. 착안: 실제 나라를 공공 통계로 턴제 전략 게임 지도처럼 그린다는 생각. 이용허락: 해당 없음 — 착안만 했다 (Andrej Karpathy). 자료 출처가 아니며, 원작의 코드·그림·자료를 가져오지 않았다. 원작에 관한 권리와 이용조건은 원작자의 것이며, 2026-11 현재 원작 사이트에서 공개된 이용허락 문서는 찾지 못했다 (README.md).
- **Python 라이브러리 (수집·빌드·검사·갈무리 도구)** — 각 라이브러리 프로젝트. pipeline/·tools/ 의 import (import 이름 그대로). 이용허락: 미확인 — 사이트에 실리지 않는 도구다. 저장소에 이용허락 파일이 없어 유형을 적지 않았다 — 각 패키지의 배포 정보를 본다. (bs4, fontTools, matplotlib, numpy, openpyxl, osmium, PIL, playwright, pymupdf, pyogrio, pyproj, rasterio, requests, scipy, shapefile, shapely, truststore, xlrd)

## 관계 없음

이 사이트는 정부·공공기관과 관계가 없다. 통계의 가공·표현에 대한 책임은 제작자에게 있다.
