# 이용허락과 연구비 상위 대학 소재지

출처 230행 중 195행에서 이용조건을 확인했다. 여기에는 공개 방법만 규정한 실거래가 자료도 포함된다. 35행(35개 key)은 허락을 확정하지 못했다. 2025년 연구비 상위 40개 공시 단위 중 40개의 캠퍼스 도로명주소를 확인했다.

## 대학 주소

연구비 파일 245행의 kind는 모두 ‘연구비 지원 계’, 단위는 천원, 연도는 2025다. 학교명 전체 문자열 기준으로 중복이 없다. 한 대학의 본교와 분교 또는 제2캠퍼스가 별도 이름으로 등장한다. 공시 단위별 총액을 그대로 숫자 내림차순으로 정렬하고 상위 40행을 취했다. 출력 금액의 소수점 표기까지 원본과 같다.

한국대학교육협의회의 [전국대학및전문대학정보표준데이터](https://www.data.go.kr/data/15107736/standard.do)에서 공개 다운로드용 JSON 1,995행을 받았다. 대학구분명 ‘대학’과 기준연도 2025를 선택했다. 연구비의 학교명·캠퍼스를 기준으로 주소표에서 단일 행만 연결했다. 학교 대표 소재지이므로 같은 대학의 연구비가 그 주소 한 곳에서만 집행됐다는 뜻으로 해석할 수 없다.

가톨릭대학교_제2캠퍼스는 주소표의 ‘제2캠퍼’와 연결했다. 서울 서초구 반포대로 222다. 한양대학교(ERICA)_분교는 안산시 상록구 한양대학로 55, 한양대학교는 서울 성동구 왕십리로 222다. 표시가 없는 학교는 본교 행을 선택했다. 전남대·광주과학기술원·조선대의 시도는 주소 원문에 있는 광주광역시를 유지했다. 일반구가 있는 도시는 시와 구를 함께 남겼다.

주소 미확인 대학 없음. 위도·경도는 주소표에 제공되지 않아 모두 비어 있다.

## 이용조건별 출처 수

입력 배열 순서대로 230행을 기록했다. 고유 key는 227개다. 두 번 등장한 `kosis-101-DT_2KI2010_11`, `kosis-203-DT_203N300003_2024_01`, `kosis-217-DT_217004_2026D005`도 각각 두 행으로 계산했다. 기준은 자료 상세 페이지의 문구, 공식 라이선스 문서, 해당 자료에 적용되는 사이트 정책이다. 사이트가 개별 공공누리 표시를 요구할 때는 정책 문서만으로 유형을 부여하지 않았다.

| 원문에 표시된 이용조건 또는 해당 조항 | 출처 행 |
| --- | ---: |
| 이용자는 KOSIS 통계정보를 자유롭게 사용, 재사용 및 재배포할 수 있으며 통계정보의 비상업적 또는 상업적 활용이 모두 가능합니다. | 95 |
| 이용허락범위 제한 없음 | 47 |
| 미확인 | 35 |
| 외부 공개시에는 반드시 신고일 기준으로 집계되는 공식통계를 이용하여 주시기 바랍니다. | 24 |
| Creative Commons Attribution 4.0 International License | 6 |
| 보호받지 못하는 저작물 | 4 |
| public domain | 2 |
| 경기도의 명시적 승인 없이 상업적으로 사용할 수 없으며 | 2 |
| 공공저작물 : 출처표시 (제 1유형) | 2 |
| 영리 목적의 이용을 포함한 자유로운 활용이 보장됩니다. | 2 |
| Creative Commons Attribution 4.0 International (CC BY 4.0) | 1 |
| for educational, research and non-profit purposes | 1 |
| 출처표시+상업적이용금지+변경금지 | 1 |
| prior permission or consultation with the MOLIT is needed | 1 |
| Open Data Commons Open Database License | 1 |
| 공공누리 1유형 : 출처표시 (상업적 이용 및 변경 가능) | 1 |
| 공공누리 제3유형(출처표시 + 변경금지) | 1 |
| 공공누리 4유형 출처표시 + 상업적 이용금지 + 변경금지 | 1 |
| KOMIR와 사전에 별도의 협의를 하거나 허락을 득하여야 하며 | 1 |
| 출처표시 | 1 |
| 저작권자의 사전승낙 없이 복제, 전송, 출판, 배포, 방송등을 통해 영리목적으로 이용하거나 제3자에게 제공해서는 안됩니다. | 1 |

## 상업 이용·변경·재배포에 제약이 있거나 별도 확인이 필요한 자료

- **KOSIS 국내 통계표** (95행) 출처 명시. 가공 절차 없이 유료 판매하는 행위를 금지한다. 국제·북한통계의 비상업·재배포 금지 예외는 별도 조항이다. [원문](https://kosis.kr/serviceInfo/useGuide.do)

  <details><summary>해당 key 92개</summary>

  - `kosis-101-DT_1AG20103`, `kosis-101-DT_1AG20201`, `kosis-101-DT_1B26001_A01`, `kosis-101-DT_1B81A23`
  - `kosis-101-DT_1EB002`, `kosis-101-DT_1ES3A01S`, `kosis-101-DT_1FI000`, `kosis-101-DT_1FI20102`
  - `kosis-101-DT_1FI20202`, `kosis-101-DT_1FO20103`, `kosis-101-DT_1FO20112`, `kosis-101-DT_1FS000`
  - `kosis-101-DT_1FS20102`, `kosis-101-DT_1FS20202`, `kosis-101-DT_1K52F08`, `kosis-101-DT_1KI1510_10`
  - `kosis-101-DT_1NG0001`, `kosis-101-DT_1PA2504`, `kosis-101-DT_1PE2502`, `kosis-101-DT_1PM1502`
  - `kosis-101-DT_1PM2501`, `kosis-101-DT_1PM2503`, `kosis-101-DT_1YL13801E`, `kosis-101-DT_1YL15012`
  - `kosis-101-DT_1YL15014`, `kosis-101-DT_1YL20831`, `kosis-101-DT_1YL20832`, `kosis-101-DT_1YL20921`
  - `kosis-101-DT_1YL20981`, `kosis-101-DT_1YL21161`, `kosis-101-DT_1YL5701`, `kosis-101-DT_1YL5702`
  - `kosis-101-DT_1YL5801`, `kosis-101-DT_1YL5802`, `kosis-101-DT_2KI2010_11`, `kosis-133-DT_133001N_4215`
  - `kosis-201-DT_201004_O110034_2020`, `kosis-201-DT_201012_D040027`, `kosis-202-DT_202N_BSY4062`, `kosis-202-DT_F10107`
  - `kosis-203-DT_2020Y22GRDP1`, `kosis-203-DT_203N300003_2019`, `kosis-203-DT_203N300003_2024_01`, `kosis-204-DT_2020Y23GRDP1`
  - `kosis-204-DT_20402_D000003`, `kosis-205-DT_2020Y24GRDP1`, `kosis-205-DT_20503_D001003`, `kosis-206-DT_2020Y25GRDP1`
  - `kosis-206-DT_20603_D001003`, `kosis-207-DT_2071D03_1`, `kosis-207-DT_GRDP_2020_01`, `kosis-210-DT_1K63001_FRM101`
  - `kosis-210-DT_GRDP004_2020`, `kosis-211-DT_2020Y32GRDP1`, `kosis-211-DT_211002_D005`, `kosis-212-DT_2020Y33GRDP1`
  - `kosis-213-DT_2020Y34GRDP1`, `kosis-213-DT_21303_D000006`, `kosis-214-DT_2020Y35GRDP1`, `kosis-215-DT_2020Y36GRDP1`
  - `kosis-216-DT_21603_D001003`, `kosis-216-DT_GRDP202037_01`, `kosis-217-DT_2020Y38GRDP1`, `kosis-217-DT_217004_2026D005`
  - `kosis-218-DT_2020GRDP39_01`, `kosis-218-DT_21802_D001003`, `kosis-101-DT_1C91`, `kosis-101-DT_1DA7004S`
  - `kosis-101-DT_1ET0034`, `kosis-101-DT_1YL21191`, `kosis-110-TX_11025_A001_A`, `kosis-177-DT_HEALTH_RECOG`
  - `kosis-177-DT_H_MENTAL_DEPRESS`, `kosis-177-DT_H_OBE_OBE`, `kosis-177-DT_H_SM`, `layers-kosis-204-DT_2020Y23GRDP1`
  - `layers-kosis-205-DT_2020Y24GRDP1`, `layers-kosis-206-DT_2015Y25GRDP1`, `layers-kosis-206-DT_2020Y25GRDP1`, `layers-kosis-207-DT_GRDP_2015_01`
  - `layers-kosis-207-DT_GRDP_2020_01`, `layers-kosis-210-DT_GRDP004_2020`, `layers-kosis-211-DT_2020Y32GRDP1`, `layers-kosis-212-DT_2020Y33GRDP1`
  - `layers-kosis-213-DT_2015Y34GRDP1`, `layers-kosis-213-DT_2020Y34GRDP1`, `layers-kosis-214-DT_2020Y35GRDP1`, `layers-kosis-215-DT_2020Y36GRDP1`
  - `layers-kosis-216-DT_GRDP202037_01`, `layers-kosis-216-DT_I30002`, `layers-kosis-218-DT_2015Y39GRDP1`, `layers-kosis-218-DT_2020GRDP39_01`

  </details>

- **국토교통부 아파트 매매·전월세** (24행) 계약일 기준 다운로드는 참고용이다. 외부 공개에는 신고일 기준 공식통계를 사용하라는 문구가 있다. 상업·변경을 포괄 허용하는 라이선스는 확인하지 못했다. [원문](https://rt.molit.go.kr/pt/xls/xls.do?mobileAt=)

  <details><summary>해당 key 24개</summary>

  - `molit-apartment-lease-2025-11`, `molit-apartment-lease-2025-12`, `molit-apartment-lease-2026-01`, `molit-apartment-lease-2026-02`
  - `molit-apartment-lease-2026-03`, `molit-apartment-lease-2026-04`, `molit-apartment-lease-2026-05`, `molit-apartment-lease-2026-06`
  - `molit-apartment-lease-2026-07`, `molit-apartment-lease-2026-08`, `molit-apartment-lease-2026-09`, `molit-apartment-lease-2026-10`
  - `molit-apartment-sale-2025-11`, `molit-apartment-sale-2025-12`, `molit-apartment-sale-2026-01`, `molit-apartment-sale-2026-02`
  - `molit-apartment-sale-2026-03`, `molit-apartment-sale-2026-04`, `molit-apartment-sale-2026-05`, `molit-apartment-sale-2026-06`
  - `molit-apartment-sale-2026-07`, `molit-apartment-sale-2026-08`, `molit-apartment-sale-2026-09`, `molit-apartment-sale-2026-10`

  </details>

- **경기도 사업체조사** (2행) 서비스 약관은 가공·판매 등 상업 이용에 경기도의 명시적 승인을 요구한다. [원문](https://data.gg.go.kr/portal/termsPolicyPage.do)
  `gyeonggi-business-2019`, `gyeonggi-business-2024`
- **경북 사업체조사** (1행) 제3유형. 변경 금지. [원문](https://www.gb.go.kr/Sub/datastat/page.do?mnu_uid=7878&cmd=2&B_STEP=260567300&V_NUM=102)
  `gyeongbuk-business-2024`
- **세종 사업체조사** (1행) 제4유형. 상업 이용 및 변경 금지. [원문](https://www.sejong.go.kr/stat/bbs/view.do?bbsSn=705&key=1910168796725)
  `sejong-business-2024`
- **보건복지부 수급자 현황** (1행) 제4유형. 보건복지부 게시물의 PDF를 다시 받아 프로젝트 원자료와 SHA-256이 같은지 확인했다. [원문](https://www.mohw.go.kr/board.es?mid=a10411010300&bid=0019&act=view&list_no=1491455)
  `mohw-welfare-2025`
- **SRTM30+** (1행) 교육·연구·비영리 목적 복제 등은 지정 고지문 포함이 조건이다. 상업적 사용자는 UC San Diego에 연락하도록 명시한다. [원문](https://coastwatch.pfeg.noaa.gov/erddap/info/srtm30plus_LonPM180/index.html)
  `terrain_srtm30plus`
- **OpenStreetMap** (1행) ODbL 1.0. 출처와 라이선스 표시 및 파생 데이터베이스 동일조건. [원문](https://www.openstreetmap.org/copyright/en)
  `osm-water`
- **행정동 경계** (1행) CC BY 4.0 가공물. 재배포 시 SGIS 공공누리 제1유형의 출처표시도 유지한다. [원문](https://raw.githubusercontent.com/vuski/admdongkor/master/LICENSE-DATA)
  `boundary_admdong`
- **광해광업공단 광산검색** (1행) 상업 이용·웹을 통한 제3자 제공에 사전 협의 또는 허락 필요. 출처표시, 오류 정정 외 무단변경 금지. [원문](https://www.komir.or.kr/kor/contents/1)
  `komir-mine-grid`
- **한우 이력 통계** (1행) 쇠고기이력추적제 저작물은 영리 이용이나 제3자 제공 시 사전승낙 필요. [원문](https://www.mtrace.go.kr/etc/copyrightPopup.do)
  `mtrace-hanwoo-202610`
- **인천공항 AIP** (1행) 영리 이용 사전 허가 또는 협의. 무단 복제·배포 및 단순 오류 정정 외 무단 변경 제한. [원문](https://aim.koca.go.kr/eaipPub/Package/2026-11-25-AIRAC/html/eAIP/KR-GEN-0.1-en-GB.html)
  `incheon-aip`
- **중분류 토지피복 WMS** (1행) 포털의 제1유형 표기와 제공기관의 API 사용 조건이 병존한다. API 약관 제4조는 비상업적 사용만 허용하고 제5조는 실시간 연동 외 복제·저장·전송을 제한한다. [제공기관 약관 문서](https://aid.mcee.go.kr/files/me_openapi_terms_of_use.doc) [원문](https://www.data.go.kr/data/3045398/openapi.do)
  `landcover-me-wms-lv2-2025y`

## 이용허락을 확인하지 못한 출처

빈 칸은 재배포 허락을 뜻하지 않는다. 사이트 정책 링크가 있어도 개별 파일의 유형을 확인할 수 없는 경우가 있다.

| key | 확인하지 못한 이유 |
| --- | --- |
| `chungbuk-business-2019` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `chungbuk-business-2024` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `jeju-business-2019` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `jeju-business-2024` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `jeonbuk-business-2024` | 공식 페이지에서 해당 자료의 이용허락 문구를 확인하지 못함 |
| `jeonnam-business-2019` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `jeonnam-business-2024` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `sejong-yearbook-2024` | 공식 페이지에서 해당 자료의 이용허락 문구를 확인하지 못함 |
| `seoul-business-10160` | 데이터 허브 응답의 라이선스 항목 값이 비어 있음 |
| `tasis-4-2-15-2022` | 통계 페이지는 JavaScript 화면으로, 해당 표의 이용조건 원문을 확보하지 못함 |
| `air-yearbook-2025` | 2025년 연보의 이용표시 미확인. 포털의 2019년 연보 조건을 이월하지 않음 |
| `airkorea-stations` | 웹 측정소 표의 표시 미확인. 별도 포털 API에는 출처표시·변경금지(제3유형) |
| `disaster-2024` | 공식 페이지에서 해당 자료의 이용허락 문구를 확인하지 못함 |
| `epsis-generators` | 포털 발전설비 등록건의 메뉴 ID와 내려받은 표의 ID가 다름 |
| `forest-gi` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `knps-statistics` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `lofin-fiscal-2026` | 지방재정365 이용정책 본문이 응답에 없음. 포털의 API 조건을 웹 조회표에 적용할 수 있는지 미확인 |
| `mof-ports-2025` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `municipalities-2025` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `nlic-ports-2025` | 공식 페이지에서 해당 자료의 이용허락 문구를 확인하지 못함 |
| `tidal-flat-shp` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `wamis-rivlinel` | WAMIS 지도 페이지가 HTTP 500을 반환했고 해당 레이어의 허락 원문을 확보하지 못함. |
| `wamis-rivlinen` | WAMIS 지도 페이지가 HTTP 500을 반환했고 해당 레이어의 허락 원문을 확보하지 못함. |
| `landcover-me-intro-land-html` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `landcover-me-stats-ntn-lcm-2025` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `chungnam-business-2024` | 공식 페이지에서 해당 자료의 이용허락 문구를 확인하지 못함 |
| `wamis-dam-observations` | OGC 서비스 설명에서 댐 관측소 재배포 조건 미확인 |
| `institution` | 여러 대학·연구기관의 연락처 페이지를 합친 기록으로 전체에 적용할 이용조건 미확인 |
| `knps-area-2025` | 사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함 |
| `khs` | 여러 해설·왕릉 일람표를 합친 자료로 각각의 공공누리 표시 미확인 |
| `mtrace-pig-sido-2026q3` | 축산물이력제의 정책 문구는 쇠고기이력추적제에 한정된다. 돼지 통계표에 적용되는 허락 미확인 |
| `manual_national_capital` | 자체 수작업 표로 출판된 원자료와 이용허락 원문을 특정하지 못함 |
| `manual_special_cities` | 자체 수작업 표로 출판된 원자료와 이용허락 원문을 특정하지 못함 |
| `manual_address` | 자체 수작업 표로 출판된 원자료와 이용허락 원문을 특정하지 못함 |
| `manual_crosswalk` | 자체 수작업 표로 출판된 원자료와 이용허락 원문을 특정하지 못함 |

## 원자료와 재현

공식 페이지·파일 응답 193건을 저장했다. 각 URL, 최종 응답 URL, UTC 수신 시각, SHA-256, 바이트 수는 `data/raw/layers4/manifest.json`에 있다. 검색결과·화면 구성 스크립트·오류 안내가 담긴 HTTP 200 응답도 보존했다. 허락의 근거로 인용한 문서는 CSV의 URL에서 구분할 수 있다. 보훈대상자 묶음은 17개 상세 페이지를 개별 확인하여 첫 근거 URL은 license_url에, 나머지 16개는 note에 입력 순서대로 기록했다.

받지 못한 요청은 다음과 같다. Natural Earth는 공식 저장소 문서로 대조했고, 대학 주소는 표준데이터 다운로드 화면이 실제 사용하는 JSON으로 받았다. 로그인·자료 신청·인증키 발급·외부 지오코딩은 사용하지 않았다.

- `naturalearth.html` — HTTP 406 응답
- `its-nodelink-20261111.html` — TLS 인증서를 검증할 수 없었다.
- `wamis-rivlinel.html` — HTTP 500 응답
- `wamis-rivlinen.html` — HTTP 500 응답
- `institution.html` — 서버가 연결을 종료했다.
- `address-export.csv` — HTTP 404 응답
- `copyright-mobile.html` — HTTP 404 응답
- `law-section.html` — HTTP 404 응답

프로젝트 루트에서 `python -I pipeline/collect_layers4.py`로 수집과 출력을 재현한다. `--offline`은 이미 받은 파일의 바이트 수와 SHA-256을 검사한 뒤 두 CSV와 이 보고서를 다시 만든다. Python 패키지 requests와 beautifulsoup4를 사용한다.
