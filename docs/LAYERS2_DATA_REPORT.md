# koreaciv 공공데이터 수집 5차

확인일은 2026-11-27이다. 공식 기관의 공개 조회 화면, 엑셀 내려받기, 공표 첨부를 사용했다. 파일마다 출처 URL, 조회 조건, 수집 시각, SHA-256, 크기와 이용허락을 기록했다. 공개 페이지에서 이용허락 유형을 확인하지 못한 자료는 매니페스트에 미확인으로 표시했다. [원자료 매니페스트](../data/raw/layers2/manifest.json)

## 1. 시군구별 수출입

2025년 연간 17개 시도, 229개 시군구 공표 단위, 687행이다. 관세청 **수출입통계 → 지역별 총괄 → 시군구 → 시도 선택 → 시군구 전체 → 연도별 2025 → 수리일**의 조회 화면에서 페이지 크기 100으로 시도별 전체 결과를 얻었다. 시도 총계 17개는 원자료에 남겼다. 수출은 제조장소 우편번호, 수입은 납세의무자 주소지 우편번호 기준이다. 원표 천 달러를 1,000배해 USD로 기록했다. 원표 무역수지를 그대로 환산했다. 수출·수입 각 공표액을 차감한 결과와 천 달러 차이가 나는 사례가 있다. 별도 확정 상태 필드는 응답에서 확인되지 않았다. [관세청 수출입무역통계](https://tradedata.go.kr/cts/index.do) · [총괄 정리표](../data/build/layers/trade_sgg.csv)

**지역별 실적 → 품목별 → HS 2단위**에서 같은 조건을 적용했다. 시도별 조회 건수와 화면의 JSON 다운로드 행 수를 대조했다. 시군구와 수출·수입 각각에서 양수인 상위 5개 품목을 골라 2,286행을 정리했다. 동률은 HS 코드 순이다. 두 정리표에는 좌표가 없다. [품목 정리표](../data/build/layers/trade_sgg_hs2.csv)

원표의 2025년 광주·전남을 별도 공표 단위로 보존했다. 명칭과 행정구역 코드 대응으로 현재 코드 211개를 붙였다. 인천 개편 전 3개 구와 일반구가 있는 13개 시 전체 행에는 일대일 현재 코드가 없다. 원표의 옛 지명 여주군·포천군도 현재 코드가 공란이다. 원자료의 시군구 코드 필드는 비어 있다. [코드 대응](../pipeline/lib/crosswalk.py)

## 2. 지역 간 도로 화물

국가물류통합정보센터 **내륙화물통계 → 도로 → O·D별 수송실적 → 2024 → 엑셀다운로드**를 사용했다. 화면에서 확인한 최신 기준년도는 2024년이며 출처는 국가교통DB다. 17×17의 방향성 있는 시도 쌍 289행으로 시도 내부 쌍과 원표의 0을 포함한다. 표의 시도 약칭과 단위 톤/년을 보존했다. 이 표의 지역 해상도는 시도이며 좌표는 없다. [공개 조회 및 엑셀](https://www.nlic.go.kr/nlic/frghtRoad0010.action) · [기종점 정리표](../data/build/layers/flows_od.csv)

## 3. 제조업 중분류 종사자

대상 분류 C19·C20·C24·C26·C30·C31 가운데 4차에서 확보한 경기·충북·전북·종전 전남·제주 2024년 480행을 재사용했다. 기존 다섯 자료의 출처와 이용허락은 경제 매니페스트에 있다. 지역별 보강값과 시점은 정리표에서 확인할 수 있다. 좌표는 없다. [기존 경제 매니페스트](../data/raw/econ/manifest.json) · [제조업 정리표](../data/build/layers/key_industries_all.csv)

KOSIS 대구와 경남의 2024년 통계표에서 **조회설정 → 종사자수 → 시군구 → 제조업 6개 중분류 → 코드 포함 UTF-8 CSV**로 조회했다. 대구는 사업체 구분 계, 경남은 산업소분류 소계를 사용했다. 대구 9개 구·군 54행, 경남 18개 시·군 108행을 받았다. 시 전체 수치는 일반구에 배분하지 않았다. [대구 KOSIS](https://kosis.kr/statHtml/statHtml.do?orgId=203&tblId=DT_203N300003_2024_01) · [경남 KOSIS](https://kosis.kr/statHtml/statHtml.do?orgId=217&tblId=DT_217004_2026D005)

서울 열린데이터광장의 2024년 ZIP 안 사업체 자료에서 제조업 중분류와 행정구역 코드로 종사자수를 집계했다. 원자료에 해당 사업체 행이 존재하는 조합은 132행이다. 경북 사업체조사 첨부의 시군별 산업세세분류 XLSX에서 중분류 총종사자수 144행을 얻었다. 경북의 포항시 전체와 일반구가 함께 공표돼 각각 남겼다. 세종 통계표 ZIP의 표 2에서 세종 전체 6행을 뽑았다. 충남 보고서의 표 2는 양면에 걸쳐 있어 행 위치와 종사자수 열을 맞추고, 15개 시군의 합을 중분류별 도 공표 합계와 대조했다. 충남 90행이다. [서울 첨부](https://data.seoul.go.kr/dataList/OA-20326/F/1/datasetView.do) · [경북 첨부](https://www.gb.go.kr/Sub/datastat/page.do?mnu_uid=7878&cmd=2&B_STEP=260567300&V_NUM=102) · [세종 첨부](https://www.sejong.go.kr/stat/bbs/view.do?bbsSn=705&key=1910168796725) · [충남 보고서](https://alldam.chungnam.go.kr/board/view.chungnam?boardId=BBS_0000026&menuCd=DOM_000000202007001006&paging=ok&startPage=1&dataSid=2323)

인천 공공데이터포털의 2022년 공개 CSV에서 10개 구·군 60행을 얻었다. 이용허락범위는 제한 없음이다. 정리표는 2024년 11개 시도 1,014행과 인천 2022년 60행이다. 총 1,074행 중 비공개·결측 219행은 값이 공란이다. 추가 대상 가운데 부산·광주·대전·울산·강원의 2024년 6개 중분류 값은 미확보다. 확인한 지역 KOSIS 후보에서는 시군구 축과 대상 중분류 6개를 함께 선택할 수 없었다. 부산은 전자책을 확인했고 대전·울산 공표 PDF는 조사대상 표가 이미지여서 숫자 추출을 완료하지 못했다. 울산 PDF는 원자료에 보존했다. [인천 CSV](https://www.data.go.kr/data/15055167/fileData.do) · [부산 전자책](https://book.busan.go.kr/Viewer/AUS1UOF55FGI) · [대전 공표](https://www.daejeon.go.kr/sta/StaSocialindicatorList.do?categorySeq=594&menuSeq=6777) · [울산 공표](https://www.ulsan.go.kr/s/statData/public/list.ulsan?codeId=PBL003&mId=001004003000000000)

비교용 2020년 경제총조사는 전국의 261개 구역에 대해 1,566행이다. 수치 1,073행, 현재 코드 245개다. 같은 방식으로 종사자수, 시군구, 2자리 중분류를 선택했다. 2024년 전국사업체조사 시도표 DT_1K52F01에는 제조업 중분류가 있지만 지역축은 전국과 17개 시도다. [2020년 KOSIS](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_2KI2010_11) · [2020년 비교표](../data/build/layers/key_industries_2020.csv) · [2024년 KOSIS 시도표](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1K52F01)

## 4. 위치 자료

**댐.** WAMIS 공개 WFS GetCapabilities에서 mbrf:dm_obsvtr 댐 관측소 레이어를 확인했다. GetFeature를 EPSG:4326으로 받아 50행을 정리했다. 원표 좌표가 있는 관측소는 49곳이다. 별도의 댐 구조물 중심점과 공표 기준일은 미확인이다. [WAMIS 공개 WFS](https://map.wamis.go.kr:8444/geoserver/mbrf/wfs?service=WFS&request=GetCapabilities) · [댐 관측소](../data/build/layers/dam_observations.csv)

**철도.** 브이월드에서 국토지리정보원 국가기본도 철도중심선·철도링크와 연속수치지형도 철도중심선 SHP 목록을 확인했다. 상세 화면의 개별 다운로드와 선택다운로드는 비로그인 상태에서 모두 “로그인 후 이용해주세요” 조건으로 중단된다. 고속선·일반선 구분 필드는 미확인이다. 공공데이터포털에서 확인한 국가철도공단 신분당선 파일은 역 구조 속성을 제공한다. [국가기본도 철도중심선](https://www.vworld.kr/dtmk/dtmk_ntads_s002.do?svcCde=MK&dsId=20250122DS00010) · [연속수치지형도 철도중심선](https://www.vworld.kr/dtmk/dtmk_ntads_s002.do?svcCde=MK&dsId=30235) · [국가철도공단 역 구조 자료](https://www.data.go.kr/data/15041146/fileData.do)

**연구기관과 대학.** 기관 누리집의 하단 연락처에서 KAIST·GIST·DGIST·UNIST, 한국과학기술연구원·한국전자통신연구원, 연세대 신촌·고려대 안암 주소를 추출했다. 주소 8곳에 좌표와 별도 기준일은 없다. 이 중 출연연은 2곳, 대학은 2곳만 확인했다. 대학 및 전문대학 표준데이터는 카탈로그에서 확인했으며, 공개 CSV 버튼의 데이터 요청은 HTTP 404를 반환했다. [기관·대학 주소](../data/build/layers/research_campuses.csv) · [전국 대학 표준데이터](https://www.data.go.kr/data/15107736/standard.do)

**가행 광산.** 한국광해광업공단의 **국내광산검색 → 전체 → 검색** 공개 표를 10행씩 30쪽 받았다. 검색 결과 296행 중 가행 293건의 명칭·광종·소재지를 정리했다. 표에 표시된 필드만 사용했다. 조회 표에 좌표와 기준일은 표시되지 않는다. 산업통상부 전국광산현황은 광종·시도 집계다. [광해광업공단 국내광산검색](https://komir.kmrgis.or.kr/kmrgis/search-service/mine.do) · [산업통상부 전국광산현황](https://www.motie.go.kr/mine/emine/mineIntroduction/generalMine/generalMineStatus.jsp) · [가행 광산](../data/build/layers/active_mines.csv)

## 5. 국립공원 공식 면적

2026년 국립공원기본통계 수정 공표 PDF 인쇄면 92의 지정 현황을 읽었다. 2025년 기준 23개 공원의 지정면적, 지정일과 위치를 담았다. 원표에 육상과 해면이 명시된 공원 4곳의 두 면적을 기록했다. 그 외 19개 공원의 구분과 전체 좌표는 공란이다. 공원별 전체 면적 합은 6,888.395 km²이며 공표 합계는 6,888.394 km²다. 0.001 km² 차이를 보존했다. 금정산은 이 공표본이 다루는 시점 이후 지정됐다. 공공누리 제1유형이다. [국립공원공단 수정 공표](https://www.knps.or.kr/front/portal/stats/statsDtl.do?menuNo=8000627&refId=REFM000902) · [공원별 면적](../data/build/layers/park_area.csv)

## 6. 대학별 연구비

대학알리미 **공시 데이터 다운로드 → 대학 → 교육연구성과 → 12-가. 연구비 수혜 실적 → 2026년 → 학교별**의 ZIP을 받았다. 다운로드 화면에는 이용자 유형과 목적 선택이 있으며 일반인, 데이터 활용으로 골랐다. 로그인이나 별도 자료 제공 신청서 없이 즉시 다운로드가 제공된다. [대학알리미 공개 다운로드](https://www.academyinfo.go.kr/popup/main0810/list.do)

2026년 공시의 실적 기준연도는 2025년이다. 공표 학교·캠퍼스 245행의 연구비 지원 계에서 남녀 금액을 더해 천원 단위로 내림차순 정리했다. 별도 캠퍼스는 공표 단위를 보존했다. 시도는 공시 지역 열이며 좌표는 없다. [대학별 연구비 정리표](../data/build/layers/university_research_funding.csv)

## 7. 군사시설보호구역 면적

시군구·시도 집계 미확보다. KOSIS 2025년 용도구역(시군구)의 선택 분류 9개와 공표 그리드에서 군사시설보호구역을 찾지 못했다. LX 2025 도시계획현황 PDF의 용도구역 편도 확인했다. 국방부 구역 조정 게시물은 변경분을 다룬다. [KOSIS 용도구역](https://kosis.kr/statHtml/statHtml.do?orgId=460&tblId=TX_315_2009_H1442) · [LX 도시계획현황통계](https://www.lx.or.kr/kor/publication/city/list.do) · [국방부 구역 조정](https://mnd.go.kr/bbs/mnd/54637/O_399933/artclView.do)

## 8. 세계유산 구성 유산

국가유산포털이 열거한 17개 세계유산을 다뤘고 97행을 정리했다. 궁능유적본부 왕릉 일람표에서 조선왕릉 40기와 사적 명칭을 가져왔다. 국가유산포털의 해설, 소제목과 관련 유산에서 경주 5지구, 고인돌 3곳, 제주 3곳, 역사마을 2곳, 백제 8곳, 산사 7곳, 서원 9곳, 갯벌 4곳, 가야 7곳, 반구천 암각화 2곳과 석굴암·불국사 두 곳을 읽었다. 해인사 장경판전, 종묘, 창덕궁, 수원화성, 남한산성은 각각 등재 유산 단위 한 행이다. 반구천의 암각화는 단일 등재 유산의 하위 유적이다. 등재연도는 포털의 목록에서 읽었다. 소재지 상세도는 시군, 권역 또는 사적명이다. 좌표는 없다. [궁능유적본부 일람표](https://royal.khs.go.kr/ROYAL/contents/R106010000.do) · [국가유산포털 세계유산](https://www.heritage.go.kr/heri/html/HtmlPage.do?pg=/unesco/korHeritageInfo.jsp) · [구성 유산 정리표](../data/build/layers/world_heritage_components.csv)

## 9. 한우와 돼지 사육 마릿수

축산유통 통계누리 **농장지역(시군구)별 소의 품종별 성별 사육두수 → 한우 → 성별 전체 → 시군구 2레벨 전체 → 2026년 10월 → CSV**에서 농장 소재지 195개 공표 단위 195행을 받았다. 현재 코드 195개에 대응했다. 지역 선택 목록에 있고 CSV에 행이 없던 지역은 출력에 추가하지 않았다. 좌표는 없다. [한우 원표](https://www.mtrace.go.kr/statHtml/statHtml.do?orgId=323&conn_path=I2&tblId=DT_323901_A100000004) · [한우 정리표](../data/build/layers/livestock_hanwoo.csv)

같은 사이트의 **돼지 → 사육단계**에서 사육규모별 및 월령·성별 가축동향조사를 확인했다. 사육규모별에서 마리수, 사육규모 합계, 2026년 3분기를 선택했다. 전국과 원표에 행이 있는 15개 시도 공표 단위, 모두 16행이다. 좌표와 시군구별 돼지 사육 마릿수는 미확보다. [돼지 원표](https://www.mtrace.go.kr/statHtml/statHtml.do?orgId=323&conn_path=I2&tblId=DT_1EO311) · [시도별 돼지 정리표](../data/build/layers/livestock_pig_sido.csv)

## 재실행과 확인

작업 폴더에서 순서대로 실행한다. KOSIS는 설치된 Chrome을 사용한다. 수집기는 같은 사이트 요청을 순차 처리하고, 재실행 때 매니페스트의 크기와 해시를 대조한다. 동적 조회의 원문은 갱신될 수 있다. 보관한 원자료를 사용하면 그 시점의 정리표를 재생성할 수 있다.

```powershell
python -m pip install requests beautifulsoup4 xlrd openpyxl pymupdf playwright truststore
python -I -B pipeline/collect_layers2_trade.py --hs2
python -I -B pipeline/collect_layers2.py
python -I -B pipeline/collect_layers2_livestock.py
python -I -B pipeline/collect_layers2_kosis.py
python -I -B pipeline/collect_layers2_normalize.py
python -I -B pipeline/collect_layers2_industries.py
```

보관한 원자료 107개(228,029,826바이트)의 SHA-256과 파일 크기를 대조했다. 정리표 13개를 다시 생성해 6,829행의 출처 ID, 행 중복 여부, 부여된 현재 시군구 코드와 경계 자료의 일치를 확인했다. 신규 원자료 중 이용허락 유형을 확인한 것은 국립공원 공표 PDF와 인천 CSV다.
