# 공개 전 보안·개인정보 감사

**지금은 공개를 보류한다.** 저장소와 Pages 양쪽에 배포되는 지도 JSON에서 WMS 파생값, 계약일 기준 실거래가 지표, 제3자 제공 조건이 있는 자료, 지정 고지가 빠진 표고 자료를 확인했다. 치명 0건, 높음 4건이다.

**공개 전에 반드시 고칠 것**

1. 01~03의 자료는 공개 범위를 뒷받침하는 근거를 확보하거나 허용된 자료로 교체한다. 해결되지 않은 항목은 지도·공유 이미지뿐 아니라 공개 저장소에 담기는 JSON·표·문서의 해당 산출값에서도 제외한다.
2. 04의 표고 자료 고지 원문을 공개 저장소와 Pages 양쪽에 제공하고, 05의 조건부·미확인 출처는 실제 배포 필드별로 대조한다. 가공·배포 근거를 설명할 수 없는 부분은 보류한다.
3. README에서 실제로 열리는 이용조건 안내를 연결하고(06), 최종 빌드에서 파일 목록·해시와 두 판의 요청을 다시 검사한다. 아래 결과는 동시 편집 중 얻은 로컬 파일 기준이다.

## 발견

**01 · 높음 · WMS 그림에서 계산한 토지피복이 배포된다.** `docs/LAYERS4_DATA_REPORT.md:108`, `pipeline/build_sources.py:284`, `site/data/sources.json:1`의 `restrictions`, `site/data/world.json:1`의 `cover_src`. 직접 확인한 5,027개 육지 칸 중 4,738칸은 WMS 그림에서, 289칸은 ESA 대체 자료에서 왔다. 원본 그림 28장을 제외해도 칸별 피복과 렌즈 값이 남는다. 포털의 제1유형 표기와 별도로 프로젝트가 보관한 API 조건은 실시간 연동 외 저장·전송을 제한하고, 생성기 자체가 현 빌드를 내부 열람용으로 명시한다. 공개용 벡터 등 허용된 입력으로 재생성하거나 현재 방식의 저장·가공·공개를 포괄하는 확인을 확보한다. 대체 시 지도 바탕, 관련 렌즈, 범례 및 출처를 함께 갱신한다.

**02 · 높음 · 주택 가격의 공개 기준과 산출 기준이 다르다.** `docs/ECON_DATA_REPORT.md:21`, `docs/ECON_DATA_REPORT.md:100`, `docs/LAYERS4_DATA_REPORT.md:75`, `site/data/sources.json:1`의 `attribution.lenses.home`, `jeonse`. 매매·전월세 12개월분 파일 24개(각 12개)을 계약일 기준으로 내려받아 중위값을 계산한다. 보관된 이용 안내는 외부 공개 시 신고일 기준 공식통계 사용을 요구한다. 거래자 개인정보 노출을 발견한 건은 아니다. 해당 용도의 신고일 기준 공식통계로 바꾸거나 현재 집계의 공개 가능 여부를 확인한 뒤 배포한다.

**03 · 높음 · 광산·한우 통계의 제3자 제공 조건이 해결되지 않았다.** `docs/LAYERS4_DATA_REPORT.md:102`, `docs/LAYERS4_DATA_REPORT.md:104`, `site/data/sources.json:1`의 `komir-mine-grid`, `mtrace-hanwoo-202610`, `site/data/resources.json:1`. 사용처에 가행 광산 293곳의 광종·소재지 집계, 한우 상위 15개 아이콘·도시 패널이 기록돼 있다. 광산검색에는 웹을 통한 제공에 사전 협의·허락, 한우 자료에는 제3자 제공 시 사전승낙 문구가 있다. 이 산출물에 해당하는 승인 근거를 공개 대상에서 찾지 못했다. 비상업 공개에도 적용 범위를 확인하고 승인 기록·허용 대체 출처·해당 필드 제외 중 하나로 해소한다.

**04 · 높음 · SRTM30+ 복제 조건에 지정된 문단이 없다.** `docs/LAYERS4_DATA_REPORT.md:96`, `site/data/sources.json:1`의 `terrain_srtm30plus`, `site/data/world.json:1`의 `elev`·`elev_sd`. 표고·기복·연안 구분이 공개 데이터에 포함된다. 로컬에 보존된 제공자 페이지 `data/raw/layers4/terrain.html`에는 저작권 고지와 지정 문단을 포함하라는 조건이 있다. 공개 트리에서 캘리포니아대 이사회 명의의 고지와 그 문단의 첫 구절을 찾지 못했다. 현재는 목적 제한을 요약하고 원문을 연결한다. 고지·면책 원문을 복제 조건에 맞춰 동봉하고, 사이트와 재배포용 데이터에서 찾아갈 수 있게 한다. 상업 이용 조건도 코드의 MIT 조건과 구별해 적는다.

**05 · 중간 · 출처마다 가공·배포 허용 범위의 확인 정도가 다르다.** `docs/LAYERS4_DATA_REPORT.md:90`, `:94`, `:98`, `:106`, `:111`, `site/data/sources.json:1`. 경북·세종 사업체조사와 복지부 수급자 자료는 변경금지 조건이며 도시 패널 또는 렌즈에 쓰인다. 인천공항 AIP는 좌표에, OSM은 호수 칸·폴리곤에 쓰인다. OSM 파생 데이터베이스의 동일조건 범위, AIP의 개별 사실 좌표 이용, 변경금지 자료의 통계 재가공은 각각 판단해야 한다. 보고서 당시 230행 중 35행, 검사한 파일은 231행(고유 키 228개) 중 36행이 미확인이다. 추가 행은 대학 주소 표준데이터다. 미확인은 위반을 뜻하지 않는다. 수작업 표, 개별 사실, 원표·도형을 구별해 근거와 적용 필드를 남기고 ODbL 대상의 이용조건·접근 방법을 명시한다.

**06 · 중간 · README의 이용조건 안내와 데이터 설명이 현재 트리와 어긋난다.** `README.md:4`, `:12`, `:35`, `:43`, `site/index.html:7`, `pipeline/build_sources.py:183`. 검사 시점에 루트의 NOTICE.md와 site/sources/, site/edu/가 없었다. 이용자는 README가 가리키는 고지를 열 수 없다. 수작업 수도·특례시 표와 행정구역 대응표가 있고, OSM 등 기여자 자료와 외부 글꼴 윤곽도 사용하므로 모든 숫자·위치·그림에 대한 단정은 범위를 좁힌다. 지도에는 집계·계산한 값과 수작업 대응이 있음을 밝히고, 존재하는 고지·연감으로 연결한다. 정부·공공기관과 무관하다는 README 마지막 문구와 글꼴별 OFL 표시는 확인했다.

**07 · 중간 · 기본판이 일부 JSON 문자열을 HTML로 해석한다.** `site/js/ui/topbar.js:19`, `:24`, `:32`, `:46`, `site/js/ui/report.js:133`, `site/js/ui/tooltip.js:27`. 전국 자료의 연도·라벨·기준 시점, 보고서 ID·이름·이모지를 속성 또는 본문에 그대로 보간하는 경로가 남아 있다. 현재 JSON에서 실행성 마크업을 발견하지 못했다. 데이터가 바뀌었을 때 페이지 출처 권한으로 해석될 수 있다는 조건부 위험이다. 보고서 메뉴와 헤더는 DOM 노드·textContent·속성 대입으로 만들고, 숫자와 ID도 타입·허용 목록을 검증한다. 해시만으로 이 경로에 임의 문자열을 직접 넣는 흐름은 확인되지 않았다.

**08 · 중간 · 출처 수집기가 입력에서 받은 URL과 파일 이름을 신뢰한다.** `pipeline/collect_layers4.py:20`, `:37`, `:46`, `:49`, `:54`, `:81`. 로컬 sources.json의 key에서 출력 이름을 만들고 일부 URL과 리디렉션을 별도 허용 목록 없이 따라간다. 현재 출처 파일이 변조되면 실행한 사람의 권한으로 의도 밖 주소를 조회하거나 원자료 디렉터리 밖에 쓸 가능성이 있다. 다운로드 본문 크기 상한도 없다. 현재 231개 출처 키에는 경로 구분자·상위 디렉터리 표기가 없다. 출처 key 문자 제한, 최종 경로의 RAW 하위 여부, 각 요청·이동의 허용 호스트/HTTPS 및 응답 크기를 검증한다.

**09 · 중간 · 국가유산 수집을 평문 HTTP로 시작한다.** `pipeline/collect_keyless.py:156`, `:158`, `:169`. 첫 요청과 출처 기록에 HTTP가 명시돼 있다. 수신 뒤의 체크섬은 첫 전송의 무결성을 보증하지 않는다. 확인된 HTTPS 주소를 사용하고 평문으로의 이동도 거부한다. 이 감사에서는 제공기관에 접속하지 않았다.

**10 · 낮음 · QA 결과와 작업용 사본을 제외하는 규칙이 좁다.** `.gitignore:6`, `:13`, `tools/yeojido/qa.py:557`, `tools/yeojido/qa_result.txt:1`. 자동 생성된 QA 로그가 포함되고 그 안의 파일 용량·요청 결과는 과거 실행값이다. 지정 폴더 밖의 스크린샷 사본, 백업 폴더, *.bak, *.tmp, *.log, *.swp, *~, .idea/, .vscode/, 테스트 추적·다운로드 폴더에는 대응 규칙이 없다. 생성 위치별로 필요한 제외 규칙을 추가한다. 검증기가 읽는 기준값 `tools/qa_caveats_baseline.json`은 보존한다(`tools/qa_interaction.py:265`). Pages는 디렉터리 단위 업로드이므로 site/ 안 사본은 배포 직전에도 검사한다.

**11 · 낮음 · Pages 권한은 목적에 맞지만 액션 참조가 이동 가능한 태그다.** `.github/workflows/pages.yml:2`, `:6`, `:19`. main push와 수동 실행만 있고 PR·pull_request_target 이벤트, 명시적 비밀 참조, 외부 입력을 실행하는 셸 단계는 없다. 단일 작업은 contents: read, pages: write, id-token: write로 site/만 올린다. checkout·configure-pages·upload-pages-artifact·deploy-pages 모두 주 버전 태그다. 검증한 전체 커밋 SHA로 고정하고 checkout에 persist-credentials: false를 설정한다. 작업을 향후 분리하면 쓰기·OIDC 권한을 배포 작업에만 둔다. 원격 저장소의 보호 규칙·환경 설정은 아직 검증 대상이 없다.

## 검사 범위와 재현

- **공개 대상 결정.** 저장소 루트에 .git을 만들지 않았다. 빈 Git 메타데이터를 별도로 두고 원본 작업 트리에 대해 `git ls-files -z --others --exclude-per-directory=.gitignore`를 실행했다. 전역 제외 규칙은 적용하지 않았다. 감사 보고서 작성 전 총 180개로, site 90, pipeline 47, docs 25, tools 12, .github 1, 루트 파일 5개다. 전체 경로는 부록에, 당시 내용을 식별하는 SHA-256과 크기는 로컬 감사 폴더의 public-inventory-initial.json에 기록했다. 보고서 추가 후 동일한 방법으로 다시 열거한 결과 181개였다. 새 파일은 이 보고서 한 개였고 최초 180개의 SHA-256은 같았다. data/raw, data/build, design2, docs/screenshots, tools/yeojido/fonts_src, tools/audit 아래의 파일은 포함되지 않았다. .nojekyll, CSS·JS, 데이터, 글꼴과 라이선스는 포함됐다. 제외 규칙 때문에 두 판의 실행에 필요한 파일이 누락된 증거는 없다.
- **원자료·대형 파일.** data/raw와 data/build에서 공개 파일과 크기가 일치하는 파일을 SHA-256으로 비교한 결과 같은 파일은 0개다. 이는 가공·부분 복사까지 판별하지는 않는다. 공개 트리에 압축 원본·WMS 타일·원본 TTF/OTF·스크린샷은 없었다. 1,000,000바이트 이상은 site/data/world.json(1,433,754바이트) 한 개로, 격자·지형·도형 파생 자료다. 원자료의 상대 경로·체크섬은 출처 기록에 남는다.
- **비밀·개인정보.** 파일명, UTF-8 본문, 바이너리의 인쇄 가능 문자열을 검사했다. URL 디코딩 후 민감한 질의·헤더·쿠키, JSESSIONID/PHPSESSID, serviceKey/apiKey/crtfc_key, password/pwd, Bearer/Basic, 서명·토큰, 비밀키 헤더, GitHub/AWS/Google/Slack/OpenAI 키·JWT 패턴을 검색했다. 출처 URL의 질의 이름을 별도 분해했다. key라는 숫자 인자는 충북·세종 게시판의 메뉴·게시판 주소에서 반복된다. OAuth 토큰·서명으로 볼 증거는 없었다. 일반 키 대입 두 후보는 Actions 권한과 수집기의 세션 객체였다. 엔트로피는 20자 이상 ASCII 토큰에 Shannon 4.2비트/문자 이상을 적용했다. 194개 후보는 경로·표 식별자·첨부 파일 식별자·문자표 등이다. 별도 확인한 64자리 16진수는 sha256 필드 360회와 수집기의 고정 파일 해시 1회였다.
- **사람과 기기.** 이메일·전화·주민번호 형태, 사용자 홈·Chrome 프로필 경로, 실제 작업기/계정 문자열, 로그인·로그아웃·담당자·작성자 문구를 점검했다. 로그인 관련 기록은 접근 요건이나 수집 과정 설명이었다. 사설 IPv4 주소, 개인 세션·계정 연락처·사적 실명으로 확인한 항목은 없다. 대학·공공기관 주소와 서체 원작자 실명·공개 계정은 출처·권리자 표기로 분류했다. 자유 서술 속 모든 한국어 이름을 기계적으로 판별할 수는 없다.
- **이미지·글꼴.** 공개 이미지 파일은 seal.svg, seal-mask.svg, title-hanja.svg 세 개다. 세 파일을 렌더링해 한글 낙관 두 벌과 한자 제호를 확인했다. SVG 요소·속성과 주석에는 화면 캡처, 내장 사진, metadata, 외부 참조가 없고 EXIF를 담는 래스터 파일도 없다. WOFF2 네 개의 name 테이블은 원서체 제작자·공식 사이트를 가리킨다. 네 OFL 문서가 동봉되고 Pretendard 수정 서체의 이름 변경 근거가 있다(`site/yeojido/fonts/README.md:15`).
- **브라우저.** Python Playwright와 설치된 Chrome을 사용했다. `python -m http.server 0 --bind 127.0.0.1`로 site/만 제공하고 각 판을 새 컨텍스트에서 열었다. 같은 출처만 통과시키고 외부 요청 시도는 전송 전에 기록·차단하도록 했다. 서비스 워커를 차단하고 외부 주소 해석·프록시 경로도 막았다. 최초 로딩 후 기본판은 Escape, 신여지도는 Enter를 누르고 글꼴 준비까지 기다렸다. 아래 합계는 이 경로에서 실제 관측한 HTTP 요청이다. HTTP 오류와 페이지 예외는 양쪽 모두 0건이었다. 서버는 종료했다. 로컬 상세 목록은 tools/audit/public-network.json에 판·메서드·경로·리소스 종류별로 있다.

| 판 | 동일 출처 요청 | 외부 시도 | 쿠키 | 세션 저장소 |
|---|---:|---:|---:|---|
| 기본판 | 35 | 0 | 0 | 비어 있음 |
| 신여지도 | 55 | 0 | 0 | 표지 확인 여부 yeojido.seen |

- **링크·공유.** 정적 코드에서도 분석 SDK, 원격 스크립트·글꼴, 추적 픽셀, 자동 업로드를 발견하지 못했다. SVG 네임스페이스 URL은 네트워크 요청을 만들지 않는다. 외부 출처 링크는 사용자가 누르면 나간다. 해시는 URLSearchParams로 읽고 카메라 숫자·도시·렌즈·탭을 검증하거나 기존 항목을 조회한다(`site/js/main.js:729`, `site/yeojido/js/main.js:688`). 판 전환은 고정 상대 경로 뒤에 프래그먼트를 붙인다(`site/js/ui/topbar.js:71`, `site/yeojido/js/main.js:141`). 열린 리디렉션을 발견하지 못했다. 기본판 연감은 HTTP(S) 스킴을 검사하고 신여지도는 DOM 생성 도우미에서 자식 문자열을 텍스트 노드로 만든다. 공유는 사용자 동작으로 링크를 클립보드에 복사하거나 로컬 캔버스 PNG를 다운로드·OS 공유 대상으로 전달한다(`site/js/ui/share.js:111`, `:411`, `site/yeojido/js/ui/share.js:367`). OS 공유 수신자의 동작은 실행하지 않았다. 제3자 저장소·쿠키 접근은 발견하지 못했다.
- **수집기.** 외부 수집은 실행하지 않았다. User-Agent는 일반 브라우저 형태이며 이메일·기기명·계정명이 없다. CookieJar와 공개 페이지에서 발급되는 쿠키를 다루는 코드에 로그인 쿠키 상수는 없었다. TLS 검증 해제(verify=False, CERT_NONE, unverified_context), eval/exec, shell=True, os.system, 신뢰하지 않는 pickle 로딩, 아카이브 이름을 그대로 풀어 쓰는 extractall을 찾지 못했다. build_all.py:17은 고정 스크립트를 인자 배열로 실행한다. ZIP은 멤버를 열어 읽고 표 추출용 extract()는 PDF 테이블 처리였다. 원격 라이브러리와 OS 자체는 이 감사의 대상 밖이다.
- **판정 범위.** 로컬 파일·보관된 제공기관 문구·실행 기록은 직접 확인했다. 제3자 계약, 통계 사실의 저작물성, 가공물에 적용되는 개별 조건, 실제 GitHub Pages 운영 시 호스팅 사업자의 기록은 확인하지 않았다. 높음 등급은 현재 파일을 공개하기 위한 근거의 공백을 나타낸다.

## 부록 · 감사 시작 시 공개 대상 전체 경로


```text
.github/workflows/pages.yml
.gitignore
LICENSE
README.md
docs/AUDIT_CODEX.md
docs/AUDIT_RESPONSE.md
docs/DESIGN.md
docs/DESIGN2_CONCEPT.md
docs/ECON_DATA_REPORT.md
docs/LANDCOVER_ME_REPORT.md
docs/LAYERS2_DATA_REPORT.md
docs/LAYERS4_DATA_REPORT.md
docs/LAYERS_DATA_REPORT.md
docs/PLAN_NEXT.md
docs/QA_INTERACTION.md
docs/SPEC_PHASE1.md
docs/SPEC_PHASE3.md
docs/SPEC_PHASE5A.md
docs/SPEC_PHASE5B.md
docs/SPEC_PHASE5C.md
docs/SPEC_PHASE5E.md
docs/SPEC_PHASE6.md
docs/YEOJIDO.md
docs/ideas/sinyeojido_r1.md
docs/ideas/sinyeojido_r2.md
docs/ideas/sinyeojido_r3.md
docs/ideas/site_r1.md
docs/ideas/site_r2.md
docs/ideas/site_r3.md
index.html
pipeline/build_all.py
pipeline/build_econ.py
pipeline/build_insights.py
pipeline/build_layers.py
pipeline/build_layers2.py
pipeline/build_layers3.py
pipeline/build_layers5e.py
pipeline/build_lenses.py
pipeline/build_phase6.py
pipeline/build_regions.py
pipeline/build_ridges.py
pipeline/build_sources.py
pipeline/build_world.py
pipeline/collect_econ.py
pipeline/collect_econ_housing.py
pipeline/collect_econ_kosis.py
pipeline/collect_econ_normalize.py
pipeline/collect_econ_publications.py
pipeline/collect_econ_tax.py
pipeline/collect_econ_web.py
pipeline/collect_keyless.py
pipeline/collect_landcover_me.py
pipeline/collect_layers.py
pipeline/collect_layers2.py
pipeline/collect_layers2_industries.py
pipeline/collect_layers2_kosis.py
pipeline/collect_layers2_livestock.py
pipeline/collect_layers2_normalize.py
pipeline/collect_layers2_trade.py
pipeline/collect_layers4.py
pipeline/collect_layers_agencies.py
pipeline/collect_layers_kosis.py
pipeline/collect_layers_normalize.py
pipeline/collect_layers_terrain.py
pipeline/collect_population.py
pipeline/lib/address.py
pipeline/lib/common.py
pipeline/lib/crosswalk.py
pipeline/lib/econ.py
pipeline/lib/hexgrid.py
pipeline/lib/housing.py
pipeline/lib/jumin.py
pipeline/lib/official.py
pipeline/lib/popstats.py
pipeline/lib/terrain.py
pipeline/lib/units.py
pipeline/validate.py
serve.cmd
site/.nojekyll
site/css/style.css
site/data/cities.json
site/data/frontier.json
site/data/infrastructure.json
site/data/lenses.json
site/data/nation.json
site/data/resources.json
site/data/ridges.json
site/data/sources.json
site/data/states.json
site/data/trade.json
site/data/wonders.json
site/data/world.json
site/index.html
site/js/camera.js
site/js/config.js
site/js/hex.js
site/js/main.js
site/js/render/banners.js
site/js/render/geolabels.js
site/js/render/labels.js
site/js/render/layers.js
site/js/render/lens.js
site/js/render/terrain.js
site/js/ui/almanac.js
site/js/ui/help.js
site/js/ui/layerctl.js
site/js/ui/lensbar.js
site/js/ui/minimap.js
site/js/ui/panel.js
site/js/ui/report.js
site/js/ui/search.js
site/js/ui/share.js
site/js/ui/tooltip.js
site/js/ui/topbar.js
site/yeojido/css/app.css
site/yeojido/css/fonts.css
site/yeojido/css/layers.css
site/yeojido/css/lens.css
site/yeojido/css/modals.css
site/yeojido/css/panels.css
site/yeojido/css/tokens.css
site/yeojido/fonts/Hahmlet-OFL.txt
site/yeojido/fonts/Hahmlet-VF.subset.woff2
site/yeojido/fonts/NotoSerifKR-OFL.txt
site/yeojido/fonts/NotoSerifKR-VF.hanja.woff2
site/yeojido/fonts/README.md
site/yeojido/fonts/YeojidoSans-Pretendard-OFL.txt
site/yeojido/fonts/YeojidoSans-VF.subset.woff2
site/yeojido/fonts/YujiSyuku-OFL.txt
site/yeojido/fonts/charset.txt
site/yeojido/fonts/fonts.json
site/yeojido/fonts/seal-mask.svg
site/yeojido/fonts/seal.svg
site/yeojido/fonts/title-hanja.svg
site/yeojido/fonts/title-hanja.woff2
site/yeojido/index.html
site/yeojido/js/adapter.js
site/yeojido/js/adapter/core.js
site/yeojido/js/adapter/layers.js
site/yeojido/js/adapter/places.js
site/yeojido/js/adapter/reports.js
site/yeojido/js/adapter/sources.js
site/yeojido/js/camera.js
site/yeojido/js/config.js
site/yeojido/js/dom.js
site/yeojido/js/fmt.js
site/yeojido/js/hex.js
site/yeojido/js/icons.js
site/yeojido/js/main.js
site/yeojido/js/map/labels.js
site/yeojido/js/map/land.js
site/yeojido/js/map/layers.js
site/yeojido/js/map/lenscolor.js
site/yeojido/js/map/lines.js
site/yeojido/js/map/plates.js
site/yeojido/js/paper.js
site/yeojido/js/ui/a11y.js
site/yeojido/js/ui/almanac.js
site/yeojido/js/ui/help.js
site/yeojido/js/ui/layerctl.js
site/yeojido/js/ui/lensui.js
site/yeojido/js/ui/masthead.js
site/yeojido/js/ui/modal.js
site/yeojido/js/ui/panel.js
site/yeojido/js/ui/panel_charts.js
site/yeojido/js/ui/search.js
site/yeojido/js/ui/share.js
site/yeojido/js/ui/tooltip.js
tools/qa_caveats_baseline.json
tools/qa_interaction.py
tools/screens_7b.py
tools/screens_phase6.py
tools/screens_phase6b.py
tools/validator_mutations.py
tools/yeojido/build_fonts.py
tools/yeojido/qa.py
tools/yeojido/qa_lens.py
tools/yeojido/qa_result.txt
tools/yeojido/screens.py
tools/yeojido/shot.py
```

## 최종 점검 (2026-11-27, 저장소 공개 직전)

감사 이후 바뀐 것: 토지피복은 두 판 모두 공공데이터포털 15150509(공공누리 제1유형) 도엽 통계로 바꿔 WMS 그림을 어느 빌드도 읽지 않는다(01 해소). 인천공항 위치는 국가철도공단 공항철도 역위치(15041331, 이용허락범위 제한 없음)로 바꿨다. 패널 '땅' 통계는 15163128(공공누리 제1유형)에서 만든다. 02·03은 공개판에서 빼는 것으로 처리했다. 04~11은 `docs/AUDIT_RESPONSE.md` 이후의 수정으로 처리했다.

공개 대상은 `.gitignore`를 적용한 파일 221개, 10.0 MB다(`tools/publish_check/final_scan.py`). 비밀 키·토큰·세션·JWT·질의 문자열 비밀·주민번호 형식·사용자 홈 경로·작업자 이름은 0건이다. 전자우편 형식 2건은 수집기 시험의 가짜 주소(`user:pw@…`)이고, 전화번호 형식 118건은 게시판 주소의 숫자 식별자와 sha256 이다. 원자료 형식(xlsx·zip·tif·shp·pbf·pdf 등)은 없고, 1 MB 넘는 파일은 `site/data/world.json` 하나다.

공개판 `site/` 를 로컬 서버로 띄워 두 판·출처·교육 쪽 6개 화면을 열었을 때 외부 출처 요청 0건, 쿠키 0개, 페이지 오류 0건이다(`tools/publish_check/net_check.py`). 사이트 코드에 루트 절대 경로(`/…`)가 없어 GitHub Pages 하위 경로에서도 같은 상대 경로로 읽는다. 커밋 작성자 전자우편은 GitHub noreply 주소를 쓴다.
