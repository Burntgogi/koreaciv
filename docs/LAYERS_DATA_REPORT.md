# koreaciv 공공데이터 수집 4차

기준일은 2026-11-26이다. 지형·지도·렌즈 정리표는 [data/build/layers](../data/build/layers)에 있다. 전국·시도 경제 공식값과 시군구 GRDP 보강분은 [data/build/econ](../data/build/econ)에 새 파일로 추가했다. 이번 원자료의 출처, 다운로드 URL, 시간대 포함 수집 시각, SHA-256, 크기, 이용허락은 [층 매니페스트](../data/raw/layers/manifest.json)에 있다. 기존 원자료를 재사용한 표의 출처는 [경제 매니페스트](../data/raw/econ/manifest.json)에 있다.

## A. 지형

| 항목 | 결과 | 출처와 처리 |
|---|---|---|
| A1 토지피복 | `landcover.tif`는 전국 250m, 2,568×2,442 격자, 분류 셀 1,642,757개. `farmmap.tif`는 전북·종전 전남·경남 54개 시군, 분류 셀 286,092개. | 환경공간정보서비스 대·중·세분류 도엽은 로그인 후 자료신청이 필요하다. 공공데이터포털의 환경부 중분류는 면적 현황이다. 농정원 2025년 팜맵 SHP는 세 지역의 54개 시군 묶음을 공개 다운로드했다. 전국 기본 격자는 ESA WorldCover 2021 v200 대체 자료다. [환경부 신청 안내](https://egis.mcee.go.kr/req/intro.do) · [환경부 중분류 면적](https://www.data.go.kr/data/15124208/fileData.do) · [전북 팜맵](https://www.data.go.kr/data/15104486/fileData.do) · [전남 팜맵](https://www.data.go.kr/data/15104487/fileData.do) · [경남 팜맵](https://www.data.go.kr/data/15104489/fileData.do) · [ESA WorldCover](https://esa-worldcover.org/en/data-access) |
| A2 강·호수 | `rivers.geojson` 국가하천 72건, 지방하천 3,761건. `lakes.geojson` 호수·저수지 등 1,196건. | WAMIS 공개 WFS의 `rivlinen`과 `rivlinel` 유로선을 받았다. 한강·낙동강·금강·영산강·섬진강 본류를 이름으로 확인했다. 공식 호소 API는 키/신청이 필요했고 WAMIS 공개 WFS에는 별도 호소 수면 층이 없었다. 수면은 Geofabrik 한국 OSM 추출본의 `natural=water` 중 하천·수로·유수지 표기를 제외한 0.1km² 이상 면을 대체로 사용했다. 소양호·충주호·대청호·안동호를 확인했다. [WAMIS](https://map.wamis.go.kr:8445/) · [공개 WFS](https://map.wamis.go.kr:8444/geoserver/mbrf/wfs?service=WFS&request=GetCapabilities) · [공식 호소 API](https://www.data.go.kr/data/15062700/openapi.do) · [Geofabrik 한국 추출본](https://download.geofabrik.de/asia/south-korea.html) |
| A3 갯벌 | `tidal_flats.geojson` 2,117면. `tidal_flat_points.csv` 55점. | 해양수산부 연안포털에서 2011년 제작 1:25,000 첨부 ZIP을 받았다. SHP 투영을 EPSG:4326으로 변환했다. 공공데이터포털의 ‘갯벌면적’ CSV에서는 명칭과 좌표를 확인했다. [연안포털 SHP](https://coast.mof.go.kr/coastKnowledge/coastDatumView.do?seq=48&data_type=3&page=) · [갯벌 지점 CSV](https://www.data.go.kr/data/15126804/fileData.do) |

두 피복 래스터는 EPSG:5179의 같은 격자에 맞췄다. WorldCover는 한국의 현재 행정경계와 겹치는 3도 타일 여섯 장을 받았다. 타일별 10m 분류를 250m 최빈값으로 바꿔 모자이크했고, 육지 경계에 닿는 셀을 남겼다. 값 0은 NoData다. ESA 분류 40은 경작지이며 논·밭이 같은 분류다. ESA 이용허락은 CC BY 4.0이다.

팜맵은 원본 `CLSF_CD`의 논·밭·과수·시설을 25m 셀 중심에 찍고 250m 셀마다 네 분류 중 표본이 가장 많은 분류를 기록했다. 동률이면 원표 분류 코드가 작은 쪽을 택했다. 값 0은 분류 표본 없음이다. 전국 래스터와 별도로 사용할 수 있다. 공공데이터포털은 세 SHP의 이용허락범위를 ‘제한 없음’으로 표시한다. 별도 공공누리 유형은 확인하지 못했다.

강·도로 선은 각각 원본 평면 좌표계에서 20m·10m로 단순화한 뒤 EPSG:4326으로 변환했다. WAMIS 유로선의 공공누리 유형은 미확인이다. OSM 수면은 2026-11-24 추출본이며 ODbL 1.0과 OpenStreetMap 기여자 표기를 적용한다.

## B. 전국·시도 공식값

| 항목 | 결과 | 출처와 기준 |
|---|---|---|
| B1 고용·실업률 | 공표값 494행, 전국 포함 19개 공표 지역. | 경제활동인구조사 2025-10~2026-10 월별 고용률·실업률이다. 기존 시군구 표의 2026년 상반기는 지역별고용조사 기준이다. 같은 반기의 경제활동인구조사 공표값은 미확보했다. `basis`에 월을 보존했다. [KOSIS 경제활동인구조사](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1DA7004S) |
| B2 재정자립도 | 전국·시도 평균 18행, 시도 본청 17행. | 지방재정365의 2026년 당초예산, 세입과목 개편 후 시도별 현황에서 공표한 전체 평균과 본청 값을 가져왔다. 광주와 전남은 당초예산 공표 기준에 따라 별도 행이다. [지방재정365 시도별 현황](https://www.lofin365.go.kr/portal/LF3110300.do?tab=retvLstBysdSitu&jiPyo=01&srchYr=2026&rgnzDvCd=02) |
| B3 논·밭 면적 | 2025년 54행, 전국과 시도 18개 공표 지역. | 농업면적조사 시군표의 전국·시도 소계에서 논·밭·계(ha)를 사용했다. [KOSIS 경지면적](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1EB002) |
| B4 지역소득 | 2018~2024년 4,158행, 전국과 17개 시도, 33개 경제활동·합계 분류. | 지역소득의 명목 GRDP, 총부가가치, 경제활동별 부가가치, 순생산물세를 백만원으로 보존했다. 2024년은 잠정이다. 과거 광주·전남은 공표 단위를 보존했다. [KOSIS 지역소득](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1C91) |
| B5 산업별 종사자 | 2024년 360행, 전국과 17개 시도. | 전국사업체조사 2024년 등록기반 종사자 수에서 산업 대분류 및 전산업 합계를 사용했다. 기존 파일의 보조 비교연도인 2019년 공식 대분류 합계는 미확보했다. [KOSIS 전국사업체조사](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1K52F08) |
| B6 시군구 GRDP 과거 | 2020년 기준 개편표 13,390행, 현재 시군구 코드 146곳. 2015년 기준표 1,900행, 코드 48곳. | 기존 최신 연도만 있던 인천·광주·대전·울산·경기·강원·충북·충남·전북·전남·경북·제주 표를 2018~2022년으로 조회했다. 대전·울산·충남·경북·제주 개편표는 2020년부터 제공돼 2018~2019년을 `grdp_history_2015.csv`에 별도로 보존했다. [인천 예시](https://kosis.kr/statHtml/statHtml.do?orgId=204&tblId=DT_2020Y23GRDP1) · [울산 2020년 기준](https://kosis.kr/statHtml/statHtml.do?orgId=207&tblId=DT_GRDP_2020_01) · [울산 2015년 기준](https://kosis.kr/statHtml/statHtml.do?orgId=207&tblId=DT_GRDP_2015_01) |
| B7 청사 | `municipal_offices.csv` 주소 282건. `special_city_offices.csv` 법률의 청사명 3건. 좌표 없음. | 행정안전부 2025-12-31 기준 공표본 인쇄면 423~434의 사무소 소재지 표를 추출했다. 한 기관의 복수 청사와 개편 전 명칭을 보존했다. 「전남광주통합특별시 설치를 위한 특별법」 제7조제3항은 종전 전남동부청사·무안청사·광주청사를 균형 있게 활용·운영하도록 한다. [행정안전부 공표본](https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000055&nttId=128138) · [국가법령정보센터 제7조](https://www.law.go.kr/법령/전남광주통합특별시설치를위한특별법/제7조) |

`official_totals.csv` 5,101행은 기존 경제 정리표와 같은 열을 사용한다. 전국·시도 행에는 시군구 코드가 없다. 광주·전남과 통합특별시의 값은 각 원표가 공표한 경계와 시점을 따른다. 시만 공표된 관측은 일반구로 배분하지 않았다. B1~B6 통계에는 좌표가 없다.

## C. 지도 층

| 항목 | 결과 | 출처와 남은 범위 |
|---|---|---|
| C1 발전설비 | `generators.csv` 189,887기. 2026-08-05, 발전기명·연료원·MW·소재지, 좌표 없음. | 한국전력거래소 EPSIS 발전기 현황 화면의 공개 조회 결과에서 발전기 행을 읽었다. 주소 상세도는 원표와 같다. 별도 시군구 용량 집계는 만들지 않았다. [EPSIS 발전기 현황](https://epsis.kpx.or.kr/epsisnew/selectEkpoBcrGrid.do?menuId=020901) · [공공데이터포털 안내](https://www.data.go.kr/data/15046119/fileData.do) |
| C2 항만 | `ports.csv` 무역항 31곳 위치 문자열. `port_traffic.csv` 2025년 화물 32행, 컨테이너 4행. | 국가물류통합정보센터에서 PORT-MIS 12월 엑셀의 1~12월 누계(톤 R/T)를 받았다. 원표의 전체·기타 행을 포함한다. 부산항만공사 원자료 2,236행의 합계는 24,882,481 TEU다. 전국·인천항·광양항은 해양수산부 발표의 천·만 단위 공표값을 TEU로 환산했다. 나머지 항만의 TEU는 미확보다. 위치 문자열과 일부 항구역 경계 설명이 있어 대표점은 공란으로 뒀다. [항만 위치](https://www.data.go.kr/data/15088273/fileData.do) · [항만별 물동량](https://www.nlic.go.kr/nlic/seaHarborGtqy.action) · [2025년 해양수산부 발표](https://www.mof.go.kr/doc/ko/selectDoc.do?bbsSeq=10&docSeq=64735&menuSeq=971) · [부산항 TEU](https://www.data.go.kr/data/15147941/fileData.do) |
| C3 공항 | `airport_locations.csv` 15곳 좌표·주소. `airport_traffic.csv` 2025년 30행, 인천 포함 14개 공항과 전국 합계. | 한국공항공사 좌표 14곳과 국토교통부 AIP의 인천 ARP를 사용했다. 인천은 공식 도분초를 십진도로 환산했다. 항공정보포털 공항별 공개 엑셀에서 인원과 톤을 받았다. 무안은 원표 2025년 실적 행이 없다. [한국공항공사 위치](https://www.data.go.kr/data/15002851/fileData.do) · [인천 AIP AD 2](https://aim.koca.go.kr/eaipPub/Package/2026-11-25-AIRAC/html/eAIP/KR-AD-2.RKSI-en-GB.html) · [항공통계](https://www.airportal.go.kr/stats/transport/chartDetail2.do) |
| C4 도로·철도 | `roads.geojson` 전국 표준노드링크 170,809선. 고속선·일반철도 선형 미확보. | 2026-11-11 공개 ZIP에서 `MOCT_LINK`의 `ROAD_RANK` 101·103, 등급·노선번호·링크 ID를 보존했다. 국가철도공단 역 위치와 코레일 노선별 역 목록을 확인했다. [국가교통정보센터 자료실](https://www.its.go.kr/nodelink/nodelinkRef) · [코레일 KTX 노선별 역](https://www.data.go.kr/data/15127571/fileData.do) |
| C5 국립공원 | `park_visitors.csv` 2025년 23개 공원, 좌표 없음. | 2026년 기본통계 수정 공표 PDF 인쇄면 27에서 추출했다. 오동도는 한려해상에 포함되어 별도 합산에서 뺐다. 23개 값 합계가 공표 전국값 43,310,477과 일치했다. 2026년 지정 금정산은 이 표에 없다. [국립공원공단 수정 공표](https://www.knps.or.kr/front/portal/stats/statsDtl.do?menuNo=8000627&refId=REFM000902) |
| C6 지리적표시 | `geographical_indications.csv` 농산물 106건, 수산물 24건, 임산물 64건. 좌표 없음. | 농산물은 농식품부 2026-03-17 첨부 CSV의 등록지를 보존했다. 수산물 공개표 3쪽은 업체 주소를 제공한다. 산림청 2026년 7월 PDF에서 운영 58건과 취소 6건을 정리했다. 시군 단위 등록지역을 제공하지 않는 수산물·임산물은 등록지역 칸을 비웠다. [농산물 등록 첨부](https://data.mafra.go.kr/opendata/data/indexOpenDataDetail.do?data_id=20220204000000001691) · [수산물 등록 현황](https://www.nfqs.go.kr/hpmg/data/actionMarineGeographicForm.do?menuId=M0000230) · [산림청 임산물 등록 현황](https://www.forest.go.kr/kfsweb/cop/bbs/selectBoardArticle.do?bbsId=BBSMSTR_1068&mn=AR01_05_01_04&nttId=3222047) |
| C7 지식 불가사의 | `research_institutes.csv` 출연연 기관명 25건. | 국가과학기술연구회 인력 공표 CSV가 기관명을 제공한다. 주소, 대학별 연구비, 과학기술원 정리표는 미확보다. [NST 공표 CSV](https://www.data.go.kr/data/15045195/fileData.do) · [NST 소관기관](https://www.nst.re.kr/www/contents.do?key=20) · [대학알리미](https://www.academyinfo.go.kr/) |
| C8 주력 업종 | `key_industries.csv` 2024년 640행, 경기·충북·전북·종전 전남·제주 80개 시군. | 3차에 받은 도별 전국사업체조사 통계표 2의 C19·20·24·26·30·31·261·311 종사자 수를 사용했다. 시 전체 공표값은 일반구로 배분하지 않았다. 인천 제조업 중분류 CSV는 별도 원본으로 보관했다. [기존 경제 매니페스트](../data/raw/econ/manifest.json) · [인천 중분류](https://www.data.go.kr/data/15055167/fileData.do) |
| C9 농축산 | `rice.csv` 2026년 151행, 현재 코드 137곳. `livestock.csv` 2019년 380행, 공표 지역명 190곳, 현재 코드 175곳. | 농작물생산조사 논벼 정곡 92.9% 생산량(톤)과 국립환경과학원 전국오염원조사 돼지·한우(육우 포함) 마릿수다. 축산 원표에서 같은 시도·시군 이름이 반복된 10곳은 어느 값이 시군 전체인지 구분할 근거가 없어 두 지표를 공란으로 뒀다. 한우만 분리한 시군구 공표값은 미확보다. [KOSIS 시군별 논벼](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1ET0034) · [전국오염원조사 축산](https://www.data.go.kr/data/15071107/fileData.do) |
| C10 교역로 | 미수집. | 고속도로 공공데이터포털 영업소 간 교통량 다운로드 동작에서 로그인 검사를 확인했다. 관세청 시군구 수출입 공식 API는 키/신청이 필요하다. KTDB 화물 O/D는 자료 선택, 신청서 작성, 만족도 조사, 다운로드 순으로 제공한다. [한국도로공사 영업소 간 교통량](https://data.ex.co.kr/portal/fdwn/view?type=TCS&num=35&requestfrom=dataset) · [관세청 시군구 수출입](https://www.data.go.kr/data/15134344/openapi.do) · [KTDB 신청 방법](https://www.ktdb.go.kr/www/contents.do?key=203) |
| C11 접경 | `border_areas.csv` 17개 시·군. 군사시설보호구역 면적 미수집. | 시행령 제2조제1항 10곳과 제2항 7곳을 정리했다. 2025-03-11 시행 개정에 가평군·속초시가 포함된다. 고양시는 시 단위로 보존했다. [현행 시행령 제2조](https://www.law.go.kr/법령/접경지역지원특별법시행령/제2조) · [법률 제2조](https://www.law.go.kr/법령/접경지역지원특별법/제2조) |
| C12 가행 광산 | 미수집. | 공공데이터포털에서 개별 위치가 공개된 자료는 폐광산이다. 기존 가행 광산 자료는 시도·광종 집계다. [광해광업공단 폐광산 위치](https://www.data.go.kr/data/15117195/fileData.do) · [광산 통계](https://www.data.go.kr/data/15067760/fileData.do) |

## D. 렌즈

| 항목 | 결과 | 출처와 남은 범위 |
|---|---|---|
| D1 외국인주민 | `foreign_residents.csv` 2024년 528행, 공표 지역 264곳, 현재 코드 248곳. | 행정안전부 시군구 현황에서 외국인주민 합계와 같은 조사 총인구를 보존했다. [KOSIS 외국인주민](https://kosis.kr/statHtml/statHtml.do?orgId=110&tblId=TX_11025_A001_A) |
| D2 PM2.5 | `pm25_stations.csv` 2025년 측정소 658행, 수치 656건, 좌표 646건. | 대기환경연보 부록 1.4.6 가로 표의 2025년 연평균과 부록 13.1 제원 좌표를 측정소 코드로 연결했다. 이동식·선박 표는 별도로 처리하지 않았다. 원표의 유효측정비율 별표를 `kind`에 보존했다. [2025 대기환경연보](https://www.airkorea.or.kr/jfile/readDownloadFile.do?fileId=1a1c46fd3e036&fileSeq=1) |
| D3 지역 건강 | `health.csv` 2025년 1,104행, 현재 코드 241곳. | 지역사회건강조사의 흡연·주관적 건강·우울감·자가보고 비만 연령표준화율을 보존했다. [흡연](https://kosis.kr/statHtml/statHtml.do?orgId=177&tblId=DT_H_SM) · [주관적 건강](https://kosis.kr/statHtml/statHtml.do?orgId=177&tblId=DT_HEALTH_RECOG) · [우울감](https://kosis.kr/statHtml/statHtml.do?orgId=177&tblId=DT_H_MENTAL_DEPRESS) · [비만](https://kosis.kr/statHtml/statHtml.do?orgId=177&tblId=DT_H_OBE_OBE) |
| D4 재해 | `disaster_damage.csv` 2024년 203행, 현재 코드 187곳. | 행정안전부 자연재난 피해·복구비 선공개 ZIP의 `2.9` 시군구별 표에서 총피해액(천원)을 추출하고 시도별 합계와 대조했다. 표에 없는 지역은 추가하지 않았다. [국민재난안전포털 선공개](https://www.safekorea.go.kr/cmmn/bbs/bbsView.do?menuSn=45&bbscttSn=99) · [재해연보 공개 안내](https://www.data.go.kr/data/15016405/fileData.do) |
| D5 학원 | `academies.csv` 2025년 247행, 수치 246행, 현재 코드 212곳. | KOSIS 지역통계의 사설학원 수 원값을 전국·시도·시군구 공표 단위로 보존했다. 통합특별시의 2025년 값은 원표에서 공란이다. [KOSIS 사설학원 수](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1YL21191) |

## 재실행과 인증

현재 산출물을 재현하는 데 인증키는 0개다. 환경부 토지피복지도 도엽은 로그인·자료 신청이 필요하다. 연안·호소 공간 API와 관세청 시군구 수출입 API는 각 기관의 키·신청 대상이다. 한국도로공사 영업소 간 교통량은 로그인, KTDB 화물 O/D는 자료 신청이 필요하다.

```powershell
python -m pip install requests beautifulsoup4 playwright openpyxl xlrd pymupdf rasterio pyogrio shapely pyproj pyshp osmium truststore pyarrow
python -I -B pipeline/collect_layers.py
python -I -B pipeline/collect_layers_agencies.py
python -I -B pipeline/collect_layers_kosis.py official history agriculture health legacy lenses academies
python -I -B pipeline/collect_layers_terrain.py
python -I -B pipeline/collect_layers_normalize.py
```

수집기를 순서대로 실행한다. 설치된 Chrome으로 KOSIS 공개 조회 설정에서 필요한 연도와 항목을 선택해 코드 포함 UTF-8 CSV를 받는다. 기존 KOSIS 수집기의 순차 요청 간격 1.2초를 사용했다. 다른 기관은 같은 세션에서 요청 사이에 0.8초를 뒀다. 저장된 원본은 다시 사용한다. 일부 공공데이터포털 첨부는 카탈로그 확장자 `.shp`·`.csv`를 달고 ZIP으로 내려온다. 정리기는 해당 ZIP 안 필요한 멤버를 직접 읽는다.

통계 비공개·결측 표기는 빈 값으로 보존했다. 기존 지역 코드 대응표를 읽고 이름을 대조했다. 좌표는 원본 좌표에서 변환했다. 자료에 대표 좌표가 없는 항만, 등록 지역, 발전기에는 좌표를 생성하지 않았다.

새 원자료 70개와 기존 경제 원자료 111개의 크기·해시를 매니페스트와 대조했다. 정리표의 출처 ID와 시군구 대응 코드, 네 GeoJSON의 범위와 도형 유효성, 두 래스터의 좌표계·해상도·NoData를 확인했다. 항목별 원자료 이용허락은 매니페스트에 기록했다. ESA와 OSM 외 확인된 공공누리 유형은 국립공원공단 기본통계의 제1유형이다. C7 기관명, C8·C9·C11 통계·목록, D1·D3~D5 시군구 통계에는 좌표가 없다. [층 매니페스트](../data/raw/layers/manifest.json) · [경제 매니페스트](../data/raw/econ/manifest.json)
