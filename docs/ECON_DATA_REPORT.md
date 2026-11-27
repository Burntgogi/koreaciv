# koreaciv 경제 통계 수집 결과

수집일은 2026-11-26이다. 원자료 111개(340,172,169바이트)와 지표 정리표 17개(87,311행)를 검증했다. 전국 시군구는 2026-10-01 경계에서 일반구를 포함한 256개다. 도시 분모 167개는 같은 경계를 제작 명세 §4.1에 따라 묶어 계산했다. 시 전체 공표값이 있거나 도시의 현재 구성 시군구에 모두 값이 있을 때 도시를 집계했다. 시 단위 관측은 시 이름을 보존하며 일반구에 배분하지 않았다. 과거 인천 중구·동구·서구의 분할·통합 전 값에는 현재 구 코드를 붙이지 않았다.

## 지표별 결과

| 지표 | 기관·통계 | 기준시점 | 시군구 / 도시 | 시도 | 방식·상태 |
|---|---|---|---:|---|---|
| 명목 GRDP | 각 시도 지역소득 및 세종통계연보. 아래 표 참조 | 2023, 세종 2024 잠정 | 213/256 · 166/167 | 16 | KOSIS 코드 포함 CSV 및 세종 공개 연보 ZIP |
| 사업체·종사자, 전산업 합계와 제조업 | 국가데이터처 e-지방지표, 전국사업체조사 기반. [합계 사업체 2019 / DT_1YL20831](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1YL20831) · [2024 / DT_1YL20832](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1YL20832) · [합계 종사자 2019 / DT_1YL15012](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1YL15012) · [2024 / DT_1YL15014](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1YL15014) | 2019, 2024 | 각각 213/256 · 166/167 | 16 | CSV. 제조업 사업체 `DT_1YL5701/5702`, 종사자 `DT_1YL5801/5802`. 모두 orgId 101 |
| 사업체·종사자, 산업 대분류 | 국가데이터처 경제총조사와 시도별 사업체조사·통계연보. 아래 표 참조 | 2019, 2020, 2023, 2024 | 2024년 188/256 · 165/167. 보유 연도 합집합 245/256 · 166/167 | 2024년 15, 합집합 16 | 23개 출처에서 22,880행 추가. 연도별 종사자 범위와 비공개 셀은 아래 참조 |
| 고용률·실업률 | 국가데이터처 지역별고용조사 [101 / DT_1ES3A01S](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1ES3A01S) | 2026 상반기 | 212/256 · 165/167 | 15 | KOSIS CSV. 세종 연간 값은 연보에서 별도 지표로 보관 |
| 합계출산율·출생아 | 국가데이터처 인구동향조사 [101 / DT_1B81A23](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1B81A23) | 2025 | 248/256 · 166/167 | 16 | 시군구 조회 CSV |
| 전입·전출·순이동 | 국가데이터처 국내인구이동통계 [101 / DT_1B26001_A01](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1B26001_A01) | 2025 연간 | 213/256 · 166/167 | 16 | 월간 기본값을 연간으로 변경해 CSV 확보 |
| 논·밭 경지면적 | 국가데이터처 농업면적조사 [101 / DT_1EB002](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1EB002) | 2025 | 논 144/256 · 155/167, 밭 147/256 · 159/167 | 14 | 시군표 CSV. 특·광역시에서 일부 구는 여러 구를 합친 항목으로 공표 |
| 농가 가구·인구 | 국가데이터처 농림어업총조사 [101 / DT_1AG20103](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1AG20103) · [DT_1AG20201](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1AG20201) | 2020 | 245/256 · 166/167 | 16 | KOSIS 시군구 CSV. 세종은 별도로 연보의 2024 농가와 총조사의 2025 개인농가도 확보 |
| 임가 가구·인구 | 국가데이터처 농림어업총조사 [101 / DT_1FO20103](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1FO20103) · [DT_1FO20112](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1FO20112) | 2020 | 245/256 · 166/167 | 16 | KOSIS 시군구 CSV |
| 해수면 어가 가구·인구 | 국가데이터처 농림어업총조사 [101 / DT_1FS20102](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1FS20102) · [DT_1FS20202](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1FS20202) | 2020 | 153/256 · 106/167 | 16 | KOSIS 시군구 CSV. 값이 있는 지역만 집계 |
| 내수면 어가 가구·인구 | 국가데이터처 농림어업총조사 [101 / DT_1FI20102](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1FI20102) · [DT_1FI20202](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1FI20202) | 2020 | 195/256 · 151/167 | 16 | KOSIS 시군구 CSV. 값이 있는 지역만 집계 |
| 주소지별 근로소득 | 국세청 국세통계 [133 / DT_133001N_4215](https://kosis.kr/statHtml/statHtml.do?orgId=133&tblId=DT_133001N_4215), [TASIS 4-2-15](https://tasis.nts.go.kr/websquare/websquare.html?w2xPath=/ui/ep/e/a/UTWEPEAA02.xml&sttPblYr=2023&sttsMtaInfrId=20230103D01202347667) | KOSIS 2023, TASIS 2022 귀속 | 213/256 · 166/167 | 16 | CSV와 XLSX. 과세대상 총급여·인원 및 1인당 총급여 |
| 아파트 매매 | 국토교통부 [실거래가 공개시스템](https://rt.molit.go.kr/pt/xls/xls.do?mobileAt=) | 2025-11~2026-10 | 255/256 · 166/167 | 16 | 전국 월별 CSV 12개 |
| 아파트 전월세 | 국토교통부 [실거래가 공개시스템](https://rt.molit.go.kr/pt/xls/xls.do?mobileAt=) | 2025-11~2026-10 | 전세 252/256 · 163/167, 월세 253/256 · 164/167 | 16 | 전국 월별 CSV 12개 |
| 재정자립도 | 국가데이터처·행정안전부 e-지방지표 [101 / DT_1YL20921](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1YL20921) | 2026 | 211/256 · 164/167 | 15 | 개편 후 기준 CSV. 별도 시군구 재정자립도 공표가 없는 제주 행정시 2곳 제외 |
| 일반수급자 가구·인원 | 보건복지부 [국민기초생활보장 수급자 현황, 별첨 표 1](https://www.korea.kr/archive/expDocView.do?docId=41874) | 2025 | 213/256 · 166/167 | 16 | PDF 인쇄면 133~142의 229개 원본 지역. 추출 집계가 인쇄 전국 합계와 일치 |
| 인구 천 명당 의사 수 | 국가데이터처 e-지방지표 [101 / DT_1YL20981](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1YL20981) | 2025 | 213/256 · 166/167 | 16 | CSV. 원표의 등록인구 분모 사용 |
| 1인 가구 수·비율 | 국가데이터처 e-지방지표, 인구총조사 기반 [101 / DT_1YL21161](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1YL21161) | 2025 | 213/256 · 166/167 | 16 | 1인 가구, 일반가구, 비율 CSV |
| 자가점유 일반가구 | 국가데이터처 인구총조사 [101 / DT_1PE2502](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1PE2502) | 2025 | 248/256 · 166/167 | 16 | 모든 거처 합계에서 일반가구 수·자기집 가구 수 CSV와 비율 |
| 통근·통학 소요시간 | 국가데이터처 인구총조사 [101 / DT_1PA2504](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1PA2504) | 2025 | 248/256 · 166/167 | 16 | 12세 이상, 교통수단 합계, 소요시간 7개 구간과 전체 인원 CSV. 시군구별 평균 분은 인구총조사 통계목록에서 찾지 못함 |
| 교육정도 | 국가데이터처 인구총조사 [101 / DT_1PM2503](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1PM2503) · [DT_1PM2501](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1PM2501) | 2025 | 15세 이상 대졸 이상 인원과 25세 이상 분모 248/256 · 166/167. 25세 이상 대졸 이상 비율 81/256 · 32/167 | 25세 이상 비율 14 | 별도 표에서 25~29세부터 85세 이상까지 13개 공표 연령대를 합산해 대졸 이상 인원과 비율을 구함 |
| 종교 인구 | 국가데이터처 인구주택총조사 [101 / DT_1PM1502](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1PM1502) | 2015 | 248/256 · 166/167 | 16 | 시군구·종교 분류, 성·연령 합계 CSV |

## GRDP 시도별

경제활동별 표에서 명목 또는 당해년가격을 사용했다. 분류 수는 시장가격 총액·순생산물세·총부가가치 세 항목을 포함한 표의 분류 수다. 광주·전남은 2023년 두 작성기관을 각각 보존했다.

| 작성기관 | 통계표·출처 | 최신 연도 | 산업·합계 분류 수 | 파일 |
|---|---|---:|---:|---|
| 서울 | [201 / DT_201012_D040027](https://kosis.kr/statHtml/statHtml.do?orgId=201&tblId=DT_201012_D040027) | 2023 | 19 | CSV |
| 부산 | [202 / DT_F10107](https://kosis.kr/statHtml/statHtml.do?orgId=202&tblId=DT_F10107) | 2023 | 19 | CSV |
| 대구 | [203 / DT_2020Y22GRDP1](https://kosis.kr/statHtml/statHtml.do?orgId=203&tblId=DT_2020Y22GRDP1) | 2023 | 19 | CSV |
| 인천 | [204 / DT_2020Y23GRDP1](https://kosis.kr/statHtml/statHtml.do?orgId=204&tblId=DT_2020Y23GRDP1) | 2023 | 19 | CSV |
| 광주 | [205 / DT_2020Y24GRDP1](https://kosis.kr/statHtml/statHtml.do?orgId=205&tblId=DT_2020Y24GRDP1) | 2023 | 19 | CSV |
| 대전 | [206 / DT_2020Y25GRDP1](https://kosis.kr/statHtml/statHtml.do?orgId=206&tblId=DT_2020Y25GRDP1) | 2023 | 19 | CSV |
| 울산 | [207 / DT_GRDP_2020_01](https://kosis.kr/statHtml/statHtml.do?orgId=207&tblId=DT_GRDP_2020_01) | 2023 | 19 | CSV |
| 세종 | [제13회 세종통계연보](https://www.sejong.go.kr/stat/bbs/statsYearList.do?key=1910168795947) ⅩⅥ-3 | 2024 잠정 | 19 | ZIP 안 XLSX |
| 경기 | [210 / DT_GRDP004_2020](https://kosis.kr/statHtml/statHtml.do?orgId=210&tblId=DT_GRDP004_2020) | 2023 | 19 | CSV |
| 강원 | [211 / DT_2020Y32GRDP1](https://kosis.kr/statHtml/statHtml.do?orgId=211&tblId=DT_2020Y32GRDP1) | 2023 | 19 | CSV |
| 충북 | [212 / DT_2020Y33GRDP1](https://kosis.kr/statHtml/statHtml.do?orgId=212&tblId=DT_2020Y33GRDP1) | 2023 | 19 | CSV |
| 충남 | [213 / DT_2020Y34GRDP1](https://kosis.kr/statHtml/statHtml.do?orgId=213&tblId=DT_2020Y34GRDP1) | 2023 | 19 | CSV |
| 전북 | [214 / DT_2020Y35GRDP1](https://kosis.kr/statHtml/statHtml.do?orgId=214&tblId=DT_2020Y35GRDP1) | 2023 | 19 | CSV |
| 전남 | [215 / DT_2020Y36GRDP1](https://kosis.kr/statHtml/statHtml.do?orgId=215&tblId=DT_2020Y36GRDP1) | 2023 | 19 | CSV |
| 경북 | [216 / DT_GRDP202037_01](https://kosis.kr/statHtml/statHtml.do?orgId=216&tblId=DT_GRDP202037_01) | 2023 | 19 | CSV |
| 경남 | [217 / DT_2020Y38GRDP1](https://kosis.kr/statHtml/statHtml.do?orgId=217&tblId=DT_2020Y38GRDP1) | 2023 | 19 | CSV |
| 제주 | [218 / DT_2020GRDP39_01](https://kosis.kr/statHtml/statHtml.do?orgId=218&tblId=DT_2020GRDP39_01) | 2023 | 19 | CSV |

## 산업 대분류 사업체·종사자

전국사업체조사의 KOSIS 등록기반 11차 개정 목록에는 `DT_1K52F01`~`DT_1K52F08` 8개 표가 있다. 제목에 표시된 지리 분류는 시도다. `DT_1K52F08` 조회 화면에는 전국과 시도 17개를 합친 선택값 18개가 있다. 경기와 전북 기관별 목록에 걸린 상속 표 `INH_DT_1K52F08_31`과 `INH_DT_1K52F08_35`의 조회 화면에는 각 도 전체 하나만 있다. 등록기반 10차 개정 목록의 `DT_1K52D01`~`DT_1K52D08`도 시도별 표다. [전국사업체조사 원표](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1K52F08) · [경기 상속 표](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=INH_DT_1K52F08_31) · [전북 상속 표](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=INH_DT_1K52F08_35)

경제총조사의 전국 시군구 표에서는 2020년의 지역 선택값 279개에서 전산업과 KSIC A–S, 사업체수와 종사자수를 조회했다. 시도별로 더 최근 공표된 KOSIS 표와 지역 통계 포털의 사업체조사 통계표를 추가했다. 2019년 조사기반 자료, 2020년 경제총조사, 2023~2024년 등록기반 자료의 조사 기준과 연도는 출처별로 구분된다. 산업명은 새 행에서 KSIC 문자와 표준 이름으로 맞췄다. [2020 경제총조사 시군구 표](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_2KI2010_11)

| 작성기관 | 확보한 표 | 기준연도 |
|---|---|---:|
| 서울 | 기존 [서울 데이터 허브 10160](https://data.seoul.go.kr/bsp/wgs/dataView/data300View/10160.do) | 2019, 2023 |
| 부산 | [202 / DT_202N_BSY4062](https://kosis.kr/statHtml/statHtml.do?orgId=202&tblId=DT_202N_BSY4062), 구·군 표 | 2024 잠정 |
| 대구 | [203 / DT_203N300003_2024_01](https://kosis.kr/statHtml/statHtml.do?orgId=203&tblId=DT_203N300003_2024_01) · [DT_203N300003_2019](https://kosis.kr/statHtml/statHtml.do?orgId=203&tblId=DT_203N300003_2019), 사업체 구분 계, 구·군 | 2019, 2024 |
| 인천 | [204 / DT_20402_D000003](https://kosis.kr/statHtml/statHtml.do?orgId=204&tblId=DT_20402_D000003), 개편 전 군·구 표 | 2024 |
| 광주 | [205 / DT_20503_D001003](https://kosis.kr/statHtml/statHtml.do?orgId=205&tblId=DT_20503_D001003), 구별 표 | 2024 |
| 대전 | [206 / DT_20603_D001003](https://kosis.kr/statHtml/statHtml.do?orgId=206&tblId=DT_20603_D001003), 구별 표 | 2024 |
| 울산 | [207 / DT_2071D03_1](https://kosis.kr/statHtml/statHtml.do?orgId=207&tblId=DT_2071D03_1), 구·군 표 | 2024 |
| 세종 | 기존 [제13회 세종통계연보](https://www.sejong.go.kr/stat/bbs/statsYearList.do?key=1910168795947) Ⅴ-3 | 2019~2024 |
| 경기 | [210 / DT_1K63001_FRM101](https://kosis.kr/statHtml/statHtml.do?orgId=210&tblId=DT_1K63001_FRM101), 31개 시·군. [경기데이터드림 사업체조사](https://data.gg.go.kr/portal/stat/dataMng/publicationPage.do?infId=542) 통계표 2, 파일 번호 5439·10639 | 2019, 2023, 2024 |
| 강원 | [211 / DT_211002_D005](https://kosis.kr/statHtml/statHtml.do?orgId=211&tblId=DT_211002_D005), 시·군 표 | 2024 |
| 충북 | 기관별 사업체조사 목록에 `101 / INH_DT_1K52F08_33` 표시. 도청 [2024 통계표](https://www.chungbuk.go.kr/stat/selectBbsNttView.do?key=1409&bbsNo=184&nttNo=415240) · [2019 통계표](https://www.chungbuk.go.kr/stat/selectBbsNttView.do?key=1409&bbsNo=184&nttNo=171325), 각 ZIP의 통계표 2 | 2019, 2024 |
| 충남 | [213 / DT_21303_D000006](https://kosis.kr/statHtml/statHtml.do?orgId=213&tblId=DT_21303_D000006), 시·군 표 | 2024 |
| 전북 | `101 / INH_DT_1K52F08_35`는 전북 전체 1개. 도 [2024년 확정 통계표](https://stat.jeonbuk.go.kr/html/sub3/index3_2.jsp?b_idx=9&bd_idx=1569&gubun=view&page=1), ZIP의 통계표 2 | 2024 |
| 전남 | 기관별 사업체조사 목록에 `101 / INH_DT_1K52F08_36` 표시. 도청 [2024 통계표](https://www.jeonnam.go.kr/M4703/boardView.do?seq=1863943&menuId=jeonnam0508010000) · [2019 통계표](https://www.jeonnam.go.kr/M4703/boardView.do?seq=1863938&menuId=jeonnam0508010000), 각 ZIP의 통계표 2 | 2019, 2024 |
| 경북 | [216 / DT_21603_D001003](https://kosis.kr/statHtml/statHtml.do?orgId=216&tblId=DT_21603_D001003), 시·군 표 | 2024 |
| 경남 | [217 / DT_217004_2026D005](https://kosis.kr/statHtml/statHtml.do?orgId=217&tblId=DT_217004_2026D005), 시·군 표 | 2024 |
| 제주 | [218 / DT_21802_D001003](https://kosis.kr/statHtml/statHtml.do?orgId=218&tblId=DT_21802_D001003), 행정시 표. 제주도 [2024 통계표](https://www.jeju.go.kr/stats/mdis/report/company.htm?act=view&seq=2002614) · [2019 확정 통계표](https://www.jeju.go.kr/stats/mdis/report/company.htm?act=view&seq=1304415), 각 ZIP의 통계표 2 | 2019, 2023, 2024 |

종사자 범위는 제조업 외 대분류에서 공표값이 하나 이상 있는 지역으로 계산했다. 도시에는 같은 연도에 시 전체가 공표됐거나 현재 구성 시군구 모두에서 관측이 있는 경우를 포함했다.

| 기준연도 | 시도 / 16 | 시군구 / 256 | 도시 / 167 |
|---|---:|---:|---:|
| 2019 | 7 | 91 | 70 |
| 2020 | 16 | 245 | 166 |
| 2023 | 4 | 51 | 35 |
| 2024 | 15 | 188 | 165 |
| 보유 연도 합집합 | 16 | 245 | 166 |

2024년 도시 단위 공백은 서울과 인천이다. 서울은 기존 2023년 자료가 있다. 인천은 개편 전 중구·동구·서구의 원본 이름과 코드를 보존했다. 현재 인천 제물포·영종·서해·검단구는 이번에 확보한 자료의 공표 경계와 직접 대응하지 않는다. 경기 부천의 원미·소사·오정구와 화성의 만세·효행·병점·동탄구는 확보한 시 단위 값으로 도시 범위에 포함했다. 새 사업체 CSV에서 종사자 231셀과 사업체 109셀의 비공개·공란 부호를 빈 값으로 보존했다.

경기데이터드림에서는 공개 내려받기 화면의 ‘연구·학습 활용’ 목적 선택을 사용했다. 도청 통계표는 원본 XLS·ZIP을 보관하고, ZIP의 통계표 2만 메모리에서 읽었다. 전남·충북·전북·제주·경기 XLS/XLSX의 시군별 전산업 사업체·종사자 합계가 각각 원표의 도 합계와 일치했다.

## 받은 경로와 확인한 한계

- **KOSIS** 공개 브라우저 화면에서 조회 설정 후 CSV UTF-8과 코드 포함을 선택했다. 브라우저는 `POST /statHtml/downGrid.do`에 `ParamInfo`의 `orgId`, `tblId`, `fieldList`, `rowAxis`, `colAxis`, `viewKind`, `viewSubKind`, `downGridCsvType` 등 필드를 보냈다. `fieldList`는 시점 `PRD`, 통계항목 `ITM_ID`, 지역과 그 밖의 분류 `OV_L*_ID`를 담는다. 고용표 HTTP 200 응답의 `file`을 폼에 넣어 `POST /statHtml/downNormal.do`에서 13,453바이트 CSV를 받았다. 첫 수집에서 HTTP 500을 낸 기본 폼 요청은 이 조회값을 갖고 있지 않았다.
- **KOSIS 조회량** 처음 자가·학력·통근 표에서 조회 버튼이 숨거나 팝업에 가렸다. 팝업에서 1만 셀 이상 조회 지연 안내와 “2만셀이 넘는 자료는 엑셀파일로 제공”한다는 안내를 확인했다. 항목과 하위 분류를 먼저 줄이고 지역을 선택한 뒤 지연 안내의 확인 버튼을 처리해 공개 CSV를 받았다.
- **실거래가** 공개 화면의 계약일 검증은 전국 범위를 31일로 제한한다. 웹 방문으로 전국 한 달 CSV를 내려받은 뒤, 관찰한 폼을 HTTP에서 재현했다. `POST /pt/xls/ptXlsDownDataCheck.do`로 건수를 확인하고 `POST /pt/xls/ptXlsCSVDown.do`로 받았다. 최근 완료된 12개 역월을 선택했다. 해제된 매매를 제외하고 지역별 월 중위가격을 계산했다. 전세는 월세 0인 건의 보증금 중위값이다. 정리표의 월은 원본 `source_id`에 있다. 공개시 신고일 기준 공식통계를 이용하라는 원본 안내가 있다. [국토교통부 자료제공](https://rt.molit.go.kr/pt/xls/xls.do?mobileAt=)
- **실거래가 관측 공백** 매매는 옹진군, 전세는 옹진·청송·울릉·장수군, 월세는 신안·옹진·울릉군에 정리 가능한 관측이 없었다. 이 지역에는 중위값을 생성하지 않았다.
- **국세청** 2025년 발행판의 2024년 귀속 주소지 표 직접 링크는 “통계연보 테이블이 존재하지 않습니다”와 0셀을 표시했다. 2023년 발행판의 2022년 귀속 표는 엑셀 버튼으로 받았고, 2023년 귀속 자료는 KOSIS에서 받았다. [TASIS 2025년 발행판](https://tasis.nts.go.kr/websquare/websquare.html?w2xPath=/ui/ep/e/a/UTWEPEAA02.xml&sttPblYr=2025&sttsMtaInfrId=20250103D01202541132)
- **시도 간행물** 세종 지역내총생산 게시판은 “등록된 정보가 없습니다”를 반환했다. 공개 통계연보 FILE 버튼의 ZIP은 경제활동별 GRDP, 2019·2024년 산업별 사업체·종사자, 농가와 고용 연간 자료를 담고 있었다. ZIP의 필요한 XLSX를 메모리에서 읽었다. [세종 GRDP 게시판](https://www.sejong.go.kr/stat/bbs/list.do?key=2510292325355) · [제13회 세종통계연보](https://www.sejong.go.kr/stat/bbs/statsYearList.do?key=1910168795947)
- **서울 사업체** 데이터 다운로드 버튼으로 ZIP을 받았다. 자치구의 행정동 `전체` 행에서 사업체구분 세 범주를 합산했다. 2019년 전산업 사업체·종사자 합계는 서울의 자치구 25개 모두 KOSIS e-지방지표와 일치했다. 실제 파일은 2015~2023년으로, 요청한 2019년과 확인된 최신 2023년을 정리했다. 카탈로그 라이선스 표기는 “자유이용 불가”다. [서울 데이터 허브 10160](https://data.seoul.go.kr/bsp/wgs/dataView/data300View/10160.do)
- **농림어업총조사** 2020년 표에서 지역 트리의 시도·시군구를 선택하고 특성 또는 연령을 계로 줄여 가구와 인구 CSV 8개를 받았다. 2025년 시도별 개인농가·해수면 어가·내수면 어가 추이 CSV도 받았다. 조사 결과 사이트는 2025년 상세 결과를 2026년 12월부터 이용할 수 있다고 안내한다. [농림어업총조사 조사결과](https://www.affcensus.go.kr/sub/ehpa/bb/ehpabb100m01)

## 보강 수집에서 재확인한 공표 여부

- **평균 통근·통학 시간** KOSIS 통계목록에서 ‘평균 소요시간’, ‘소요시간’, ‘통근통학’을 검색했다. 2025년 인구총조사의 시군구 표 `DT_1PA2504` 조회 화면에는 시간 구간과 인원만 있고, `DT_1PA2517`은 학교급·시간 구간별 인원을 시도 수준에서 공표한다. 평균 시간을 직접 공표하는 인구총조사 시군구 표는 찾지 못했다. ‘평균 소요시간’ 검색에서 나온 양천구 등 지자체 표는 별도 사회조사다. [인구총조사 시군구 소요시간표](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1PA2504) · [학교급별 시도표](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1PA2517) · [지역 사회조사 예시](https://kosis.kr/statHtml/statHtml.do?orgId=512&tblId=DT_512002_F002)
- **25세 이상 학력** `DT_1PM2501`에서 내국인 계와 대학·대학교·석사·박사 졸업 인원 4개 항목을 받았다. 25세 이상 13개 연령대의 필요한 셀이 전부 공표된 곳에서만 인원과 비율을 계산했다. 265개 원본 지역 중 170개는 필요한 셀에 공란 또는 비공개 부호가 있어 비율이 비어 있다. 비교 가능한 25세 이상 분모 265개는 기존 `DT_1PM2503` 결과와 일치했다. [별도 교육상태별 인구 표](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1PM2501)
- **2024년 귀속 주소지 근로소득** TASIS 2025년 발행판의 4-2-15 링크를 다시 열었다. 화면에 ‘통계연보 테이블이 존재하지 않습니다’가 표시됐다. KOSIS의 주소지 표 `DT_133001N_4215` 조회 화면에도 2023년까지만 표시됐다. [TASIS 2025년 발행판](https://tasis.nts.go.kr/websquare/websquare.html?w2xPath=/ui/ep/e/a/UTWEPEAA02.xml&sttPblYr=2025&sttsMtaInfrId=20250103D01202541132) · [KOSIS 주소지 표](https://kosis.kr/statHtml/statHtml.do?orgId=133&tblId=DT_133001N_4215)
- **2025년 농림어업총조사 시군구 상세** 결과 페이지의 ‘2026년 12월부터 이용’ 안내와 KOSIS 시군구 농가 표 `DT_1AG20103`의 2020년만 있는 시점 선택을 재확인했다. 2025년 자료는 기존에 확보한 시도별 추이까지다. [농림어업총조사 조사결과](https://www.affcensus.go.kr/sub/ehpa/bb/ehpabb100m01) · [시군구 농가 표](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1AG20103)

## 최소 API 목록

현재 정리표를 재현하는 데 필요한 키는 **0개**다.

| 공백 | 인증키·요청 대상 | 확인 결과 |
|---|---|---|
| 2019년 시군구 × 대분류가 남은 지역 | SGIS 키 1개와 액세스토큰 | 사업체통계 `stats/company.json` 문서에 시군구 5자리 `adm_cd`, 산업 `class_code`, 사업체수 `corp_cnt`, 종사자수 `tot_worker`, 기준연도 2000~2019가 명시돼 있다. 산업분류 `stats/industrycode.json`의 최상위 1자리 분류도 문서에 있다. [SGIS 사업체통계](https://sgis.mods.go.kr/developer/html/openApi/api/data.html#8) · [SGIS 산업분류](https://sgis.mods.go.kr/developer/html/openApi/api/data.html#9) |
| 2024 등록기반·현행 구 경계의 공백 | 확인된 추가 키 없음 | SGIS 사업체통계 문서의 연도 상한은 2019다. KOSIS OpenAPI의 해당 표 분류 지정에 키가 필요하며 `DT_1K52F08`의 확인된 지역 분류는 시도다. [KOSIS 통계자료 API](https://kosis.kr/openapi/devGuide/devGuide_0201List.do) |
| 인구총조사 평균 통근·통학, 학력 비공개 셀, 2024 귀속 주소지 근로소득, 2025 농림어가 시군구 상세 | 확인된 추가 키 없음 | 위 공표 확인 결과를 바탕으로 해당 셀은 비워 뒀다. |

SGIS와 KOSIS의 공개 설명 문서만 확인했다. 키 발급과 API 호출은 수행하지 않았다.

## 재실행

```powershell
python -m pip install requests beautifulsoup4 playwright openpyxl xlrd pymupdf
python -B -X utf8 pipeline/collect_econ_kosis.py grdp employment land
python -B -X utf8 pipeline/collect_econ_kosis.py fertility migration finance doctors assistance households tenure religion commute education income agriculture business
python -B -X utf8 pipeline/collect_econ_housing.py 2025-11 2026-10
python -B -X utf8 pipeline/collect_econ_tax.py
python -B -X utf8 pipeline/collect_econ_publications.py
python -B -X utf8 pipeline/collect_econ_publications.py --business-surveys
python -B -X utf8 pipeline/collect_econ_normalize.py
```

Chrome이 설치된 Windows에서 실행했다. 수집기를 순서대로 실행한다. KOSIS와 실거래가 수집기는 매니페스트의 원본을 재사용한다. 같은 대상의 새 파일이 필요하면 `--force`를 사용한다. KOSIS의 `--search`는 공개 통계목록을 검색한다. `--inspect 101/INH_DT_1K52F08_31`처럼 기관·표 ID를 지정하면 공개 화면의 조회 항목과 시점을 출력한다. 수집기의 요청 간격은 1.2초 이상으로 설정했다. KOSIS 자산은 실행 안에서 재사용하며 서버 오류 후 간격을 늘린다.

보강분은 정리기에 `--append`와 매니페스트 출처 ID를 지정해 사업체·학력 CSV에 추가했다. 정리기는 임시 파일을 작성한 뒤 해당 CSV를 한 번에 교체한다. 기존 두 파일의 헤더와 행은 바이트 단위로 보존됐다. 원본 111개 크기·SHA-256, 새 행의 출처 ID와 현재 지역 코드, 출처 내 행 중복을 확인했다.

원본의 파일 경로·기관·다운로드 URL·UTC 수집시각·SHA-256·크기·기준시점·통계표 ID·라이선스는 [매니페스트](../data/raw/econ/manifest.json)에 있다. `license: null`은 별도 이용허락을 확인하지 못했다는 뜻이다. 정리표는 `data/build/econ`의 UTF-8 CSV다. 현재 시군구와 대응하지 않는 보강분은 해당 CSV의 `sgg_code_now`가 비어 있다. 전체 정리 시에는 `unmapped.csv`에도 기록한다. `basis=주소지`의 주소는 근로소득에서 신고인의 주소, 실거래가에서 물건 주소, 재정자립도에서 지자체 관할구역이다. 비밀보호·무응답 부호는 빈 값으로 보존했다.
