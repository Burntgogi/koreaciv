"""Find official KOSIS table IDs and use the public CSV export."""
import argparse
import asyncio
import re
import time
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from collect_econ_web import Archive, PublicSession, SiteBlocked

BASE = "https://kosis.kr/statHtml/"
DOWNLOAD = BASE + "downNormal.do"
GRDP = {
    "201": ("DT_201012_D040027", "서울특별시"),
    "202": ("DT_F10107", "부산광역시"),
    "203": ("DT_2020Y22GRDP1", "대구광역시"),
    "204": ("DT_2020Y23GRDP1", "인천광역시"),
    "205": ("DT_2020Y24GRDP1", "광주광역시"),
    "206": ("DT_2020Y25GRDP1", "대전광역시"),
    "207": ("DT_GRDP_2020_01", "울산광역시"),
    "210": ("DT_GRDP004_2020", "경기도"),
    "211": ("DT_2020Y32GRDP1", "강원특별자치도"),
    "212": ("DT_2020Y33GRDP1", "충청북도"),
    "213": ("DT_2020Y34GRDP1", "충청남도"),
    "214": ("DT_2020Y35GRDP1", "전북특별자치도"),
    "215": ("DT_2020Y36GRDP1", "전라남도"),
    "216": ("DT_GRDP202037_01", "경상북도"),
    "217": ("DT_2020Y38GRDP1", "경상남도"),
    "218": ("DT_2020GRDP39_01", "제주특별자치도"),
}
REGIONAL_BUSINESS = {
    "202": ("DT_202N_BSY4062",),
    "203": ("DT_203N300003_2024_01", "DT_203N300003_2019"),
    "204": ("DT_20402_D000003",),
    "205": ("DT_20503_D001003",),
    "206": ("DT_20603_D001003",),
    "207": ("DT_2071D03_1",),
    "210": ("DT_1K63001_FRM101",),
    "211": ("DT_211002_D005",),
    "213": ("DT_21303_D000006",),
    "216": ("DT_21603_D001003",),
    "217": ("DT_217004_2026D005",),
    "218": ("DT_21802_D001003",),
}
BUSINESS_YEARBOOKS = {
    "DT_202N_BSY4062", "DT_20402_D000003", "DT_20503_D001003", "DT_20603_D001003",
    "DT_2071D03_1", "DT_211002_D005", "DT_21303_D000006", "DT_21603_D001003", "DT_21802_D001003",
}
TABLES = {
    "employment": [("101", "DT_1ES3A01S", "국가데이터처")],
    "fertility": [("101", "DT_1B81A23", "국가데이터처")],
    "migration": [("101", "DT_1B26001_A01", "국가데이터처")],
    "land": [("101", "DT_1EB002", "국가데이터처")],
    "business": [("101", table, "국가데이터처") for table in (
        "DT_1K52F08", "DT_1K52F01", "DT_1K52E01", "DT_1KI1510_10", "DT_2KI2010_11",
        "DT_1YL5702", "DT_1YL5802", "DT_1YL5701", "DT_1YL5801",
        "DT_1YL20832", "DT_1YL15014", "DT_1YL20831", "DT_1YL15012",
    )] + [(org, table, GRDP[org][1]) for org, tables in REGIONAL_BUSINESS.items() for table in tables],
    "agriculture": [("101", table, "국가데이터처") for table in (
        "DT_1NG0001", "DT_1FO20103", "DT_1FO20112", "DT_1FS000", "DT_1FI000",
        "DT_1AG20103", "DT_1AG20201", "DT_1FS20102", "DT_1FS20202", "DT_1FI20102", "DT_1FI20202",
    )],
    "education": [("101", table, "국가데이터처") for table in ("DT_1PM2503", "DT_1PM2501")],
    "tenure": [("101", "DT_1PE2502", "국가데이터처")],
    "religion": [("101", "DT_1PM1502", "국가데이터처")],
    "commute": [("101", "DT_1PA2504", "국가데이터처")],
    "households": [("101", "DT_1JC1505", "국가데이터처"), ("101", "DT_1YL21161", "국가데이터처")],
    "finance": [("101", "DT_1YL20921", "국가데이터처")],
    "doctors": [("101", "DT_1YL20981", "국가데이터처")],
    "income": [("133", "DT_133001N_4215", "국세청")],
    "assistance": [("101", "DT_1YL13801E", "국가데이터처"),
                   ("201", "DT_201004_O110034_2020", "서울특별시")],
    "grdp": [(org, table, province) for org, (table, province) in GRDP.items()],
}

YEARS = {
    "DT_1B26001_A01": [2025], "DT_1K52F08": [2024], "DT_1K52F01": [2024],
    "DT_1K52E01": [2019], "DT_1KI1510_10": [2020],
    "DT_133001N_4215": [2024], "DT_1JC1505": [2025],
    "DT_1YL5702": [2024], "DT_1YL5802": [2024], "DT_1YL5701": [2019], "DT_1YL5801": [2019],
    "DT_1YL20832": [2024], "DT_1YL15014": [2024], "DT_1YL20831": [2019], "DT_1YL15012": [2019],
}

SELECT = r"""
({table, years, group, org}) => {
    const tree = id => $.ui.fancytree.getTree("#" + id);
    const each = (id, action) => tree(id).getRootNode().visit(action);
    const result = {};
    const choose = (id, test) => {
        if (!tree(id)) return;
        each(id, node => {
            node.setSelected(test(node), {noEvents: true});
        });
        if (id === "fancytree_0") {
            g_itmCnt = tree(id).getSelectedNodes().length;
        } else {
            const levels = "multiSelect_" + id.split("_").pop();
            if (document.getElementById(levels)) fn_changeMultiselectVal(levels, id);
            fn_setDefaultClassArr(id);
        }
    };
    const total = node => /^(계|합계|소계|전체|총계|일반가구)$/.test(node.title.replace(/\s/g, ""));
    const regionalBusiness = group === "business" && org !== "101";
    const areaId = table === "DT_1KI1510_10" ? "fancytree_2" : "fancytree_1";
    const selectArea = () => {
        if (!tree(areaId)) return;
        choose(areaId, node => {
            const isDistrict = /[시군구도]$/.test(node.title.trim()) || /전국|합계|소계/.test(node.title);
            const districtOnly = group === "agriculture" || table === "DT_1PM2501";
            return (!node.data.lvl || node.data.lvl <= 3) && (!districtOnly || isDistrict);
        });
        result.regions = tree(areaId).getSelectedNodes().length;
    };
    if (group === "tenure" || table === "DT_1JC1505") {
        choose("fancytree_2", total);
    }
    if (group === "tenure") {
        choose("fancytree_0", node => ["T10", "T11"].includes(node.data.itmId));
    }
    if (group === "commute") {
        const first = tree("fancytree_0").getSelectedNodes()[0];
        choose("fancytree_0", node => node === first);
        choose("fancytree_2", total);
    }
    if (group === "agriculture" && /^(DT_1AG|DT_1FO|DT_1FS20|DT_1FI20)/.test(table)) {
        choose("fancytree_0", node => /^(농가|임가|어가)(인구)?(:계)?$/.test(node.title.replace(/\s/g, "")));
        for (const id of ["fancytree_2", "fancytree_3"]) {
            if (tree(id)?.getRootNode().children.some(total)) {
                choose(id, total);
            }
        }
    }
    if (["DT_1K52F01", "DT_1K52E01"].includes(table)) {
        choose("fancytree_3", total);
    }
    if (table === "DT_1KI1510_10") {
        choose("fancytree_0", node => /^(사업체수|종사자수|사업체 수|종사자 수)(\s|$)/.test(node.title));
        choose("fancytree_1", node => /^(0|[A-S])$/.test(node.data.itmId));
    }
    if (table === "DT_2KI2010_11") {
        choose("fancytree_0", node => ["T10", "T20"].includes(node.data.itmId));
        choose("fancytree_2", node => /^(0|[A-S])$/.test(node.data.itmId));
    }
    if (regionalBusiness) {
        const ids = [...document.querySelectorAll('[id^=fancytree_]')]
            .map(element => element.id).filter(id => /^fancytree_[1-9]\d*$/.test(id) && tree(id));
        const nodes = id => {
            const matches = [];
            each(id, node => matches.push(node));
            return matches;
        };
        const sectionCode = node => /^[A-U]$/.test(node.data.itmId);
        const title = node => node.title.replace(/[^가-힣]/g, "");
        const signatures = ["제조업", "광업", "정보통신업", "금융및보험업"];
        const district = node => /[시군구도]$/.test(node.title.trim());
        const industry = ids.find(id => nodes(id).filter(sectionCode).length >= 15)
            || ids.find(id => signatures.every(label => nodes(id).some(node => title(node) === label)));
        const area = ids.find(id => id !== industry && nodes(id).filter(district).length >= 2);
        if (!industry || !area) throw Error("Cannot identify district and KSIC axes");
        const major = nodes(industry).filter(sectionCode).length >= 15
            ? sectionCode : node => node.data.lvl === 1;
        choose("fancytree_0", node => /^(사업체수|종사자수)(\(|:계|$)/.test(node.title.replace(/\s/g, "")));
        choose(industry, node => major(node) || total(node) || /^전산업$/.test(node.title.replace(/\s/g, "")));
        choose(area, district);
        result.regions = tree(area).getSelectedNodes().length;
        for (const id of ids.filter(id => id !== industry && id !== area)) {
            const subtotal = nodes(id).find(node => total(node) || /^전산업$/.test(node.title.replace(/\s/g, "")));
            if (!subtotal) throw Error("No total in " + id);
            choose(id, node => node === subtotal);
        }
    }
    if (group === "education") {
        const ageId = "fancytree_3";
        choose("fancytree_0", node => ["T10", "T51", "T61", "T71", "T81"].includes(node.data.itmId));
        if (table === "DT_1PM2501") {
            choose(ageId, node => node.data.lvl === 1 && parseInt(node.title, 10) >= 25);
        } else {
            choose(ageId, node => total(node) || /^(15|20)\D/.test(node.title.trim()));
        }
        result.age = tree(ageId).getSelectedNodes().map(node => node.title);
    }
    const annual = g_result.find(frequency => frequency.endsWith("Y"));
    if (regionalBusiness && !years.length && annual) {
        const available = tree("timeList" + annual).getRootNode().children.map(
            node => Number(String(node.data.prdDe).slice(0, 4))
        );
        const latest = Math.max(...available);
        years = [latest, latest - 5];
    }
    if (years.length && annual) {
        const match = tree("timeList" + annual).getRootNode().children.filter(node =>
            years.includes(Number(String(node.data.prdDe).slice(0, 4))));
        if (match.length) {
            for (const frequency of g_result) {
                const id = "timeList" + frequency;
                each(id, node => {
                    node.setSelected(frequency === annual && match.includes(node), {noEvents: true});
                });
                fn_setTimeCheckIcon(frequency);
            }
            g_headType = annual;
            g_timeCnt = match.length;
            result.periods = match.map(node => node.title);
        }
    }
    if (!regionalBusiness) selectArea();
    g_itmCnt = tree("fancytree_0").getSelectedNodes().length;
    fn_countView(g_itmCnt,g_classCnt,g_timeCnt,g_classViewCntStr);
    fn_setPivotColChk();
    result.items = tree("fancytree_0").getSelectedNodes().map(node => node.title);
    fn_searchCond();
    result.axis = JSON.parse(document.querySelector("#fieldList").value)
        .reduce((counts, x) => {counts[x.targetId] = (counts[x.targetId] || 0) + 1;return counts}, {});
    return result;
}
"""


def search(keywords, catalog):
    with PublicSession() as session:
        for keyword in keywords:
            print(f"\n{keyword}", flush=True)
            response = session.post(BASE + "treeSearch.do", data={
                "treeSearchOption": "statTblNm", "treeSearchKeyword": keyword,
                "vwCd": catalog, "dbUser": "NSI.", "pageStart": "0",
                "pageNow": "1", "pageEnd": "80", "language": "ko",
            }, timeout=30)
            response.raise_for_status()
            for node in BeautifulSoup(response.json()["searchData"], "html.parser").select("li[id]"):
                args = re.findall(r'"([^"]*)"', node.get("onclick", ""))
                if len(args) >= 3:
                    print(args[2], node["id"], node.get("title", ""), args[0], flush=True)


async def download(groups, channel, force, only, trace=False, inspect_tables=()):
    archive = Archive()
    failures = []
    async with async_playwright() as driver:
        browser = await driver.chromium.launch(channel=channel)
        context = await browser.new_context(accept_downloads=True, locale="ko-KR")
        lock = asyncio.Lock()
        cached_resources = {}
        last = 0
        blocked = None
        interval = 1.2

        async def serial(route):
            nonlocal blocked, last, interval
            host = urlsplit(route.request.url).hostname or ""
            resource = route.request.resource_type
            if not (host == "kosis.kr" or host.endswith(".kosis.kr")) or resource in {"image", "font", "media"}:
                if trace and resource in {"document", "xhr"}:
                    print("skipped", resource, host, urlsplit(route.request.url).path, flush=True)
                await route.abort()
                return
            async with lock:
                if blocked:
                    await route.abort()
                    return
                url = route.request.url
                cacheable = resource in {"stylesheet", "script", "image", "font"} and route.request.method == "GET"
                if cacheable and url in cached_resources:
                    await route.fulfill(**cached_resources[url])
                    return
                await asyncio.sleep(max(0, interval - (time.monotonic() - last)))
                last = time.monotonic()
                try:
                    response = await route.fetch(max_redirects=0, timeout=30000)
                except Exception as error:
                    if trace:
                        print("network", resource, urlsplit(url).path, str(error)[:350], flush=True)
                    interval = min(interval * 2, 15)
                    await route.abort()
                    return
                if response.status in (401, 403, 429):
                    blocked = f"HTTP {response.status} {urlsplit(url).path}"
                    await route.abort()
                    return
                interval = min(interval * 2, 15) if response.status >= 500 else 1.2
                if trace:
                    print(response.status, resource, urlsplit(url).path, flush=True)
                if cacheable and response.ok:
                    headers = {key: value for key, value in response.headers.items()
                               if key.lower() not in {"content-encoding", "content-length", "set-cookie"}}
                    cached_resources[url] = dict(status=response.status, headers=headers,
                                                 body=await response.body())
                await route.fulfill(response=response)
                await response.dispose()

        await context.route("**/*", serial)
        page = await context.new_page()
        dialogs = []

        async def record_dialog(dialog):
            dialogs.append(dialog.message)
            await dialog.dismiss()

        page.on("dialog", record_dialog)
        if trace:
            page.on("pageerror", lambda error: print("page script:", error, flush=True))
        targets = {group: TABLES[group] for group in groups}
        if inspect_tables:
            targets = {"inspect": [(*target.split("/", 1), "") for target in inspect_tables]}
        for group, tables in targets.items():
            for org, table, publisher in tables:
                source_id = f"kosis-{org}-{table}"
                if only and table not in only:
                    continue
                if not inspect_tables and not force and archive.has(source_id):
                    continue
                url = BASE + f"statHtml.do?orgId={org}&tblId={table}"
                dialogs.clear()
                print(f"{group} {org}/{table}", flush=True)
                try:
                    await page.goto(url, wait_until="commit", timeout=45000)
                    scope = page.frame_locator("#iframe_rightMenu").frame_locator('iframe[id^="iframe_centerMenu"]')
                    await scope.locator("#mainTable tbody tr").first.wait_for(timeout=210000)
                    title = await scope.locator("#tblNm").input_value()
                    if inspect_tables:
                        await scope.locator("#ico_querySetting").click()
                        axes = await scope.locator("body").evaluate(r"""() => {
                            const axes = {};
                            for (const element of document.querySelectorAll('[id^=fancytree_], [id^=timeList]')) {
                                const nodes = [];
                                $.ui.fancytree.getTree(element)?.getRootNode().visit(node => {
                                    nodes.push([node.data.itmId || node.data.prdDe || node.key,
                                                node.title, node.data.lvl, node.isSelected()]);
                                });
                                if (nodes.length) {
                                    axes[element.id] = [nodes.length, ...nodes.slice(0, 24),
                                                        ...nodes.slice(Math.max(24, nodes.length - 3))];
                                }
                            }
                            return axes;
                        }""")
                        print(title, axes, flush=True)
                        print(await scope.locator("#mainTable").evaluate(
                            "t => [t.tHead.innerText.slice(0, 500), t.tBodies[0].innerText.slice(0, 500)]"),
                              flush=True)
                        continue
                    if group not in {"grdp", "employment", "land"} and org != "201" and table not in BUSINESS_YEARBOOKS:
                        await scope.locator("#ico_querySetting").click()
                        selection = await scope.locator("body").evaluate(
                            "(body, config) => (" + SELECT + ")(config)",
                            {"table": table, "years": YEARS.get(table, []), "group": group, "org": org})
                        print("query", selection, flush=True)
                        notice = scope.locator("#pop_alert")
                        if await notice.is_visible():
                            message = await notice.inner_text()
                            if "조회시간이 지연될 수 있" not in message:
                                raise ValueError(f"KOSIS notice: {message.strip()}")
                            await notice.get_by_text("확인", exact=True).click()
                        if not selection["items"]:
                            raise ValueError(f"No matching items in {table}")
                        if not await scope.locator("#btnSearch").is_visible():
                            raise ValueError(f"regular view unavailable for selected cells: {selection}")
                        async with page.expect_response(
                            lambda response: urlsplit(response.url).path == "/statHtml/html.do", timeout=45000
                        ) as grid:
                            await scope.locator("#btnSearch").click()
                        response = await grid.value
                        if not response.ok:
                            raise ValueError(f"Grid HTTP {response.status}")
                        await response.finished()
                        await scope.locator("#mainTable tbody tr").first.wait_for()
                    print(await scope.locator("#mainTable").evaluate(
                        "t => [t.tBodies[0].rows.length, t.tHead.innerText.slice(0, 230), "
                        "t.tBodies[0].innerText.slice(0, 180)]"), flush=True)
                    await scope.locator("#ico_download").click(timeout=15000)
                    await scope.locator("#csvradio").check()
                    await scope.locator("#csvType").select_option("UTF-8")
                    await scope.locator("#codeYn").check()
                    await scope.locator("#expDash").uncheck()
                    button = scope.locator('#pop_downgrid a[href*="fn_downGridSubmit"]')
                    async with page.expect_download(timeout=100000) as pending, page.expect_request(
                        lambda request: request.url == BASE + "downGrid.do", timeout=50000
                    ) as request:
                        await button.click()
                    export = await pending.value
                    path = await export.path()
                    fields = parse_qs((await request.value).post_data)
                    view = fields.get("fieldList", [""])[0]
                    periods = re.findall(r'"prdValue"\s*:\s*"([^"]+)"', view)
                    archive = Archive()
                    archive.save(source_id, f"{group}/{source_id}.csv", path.read_bytes(),
                                 title=title, publisher=publisher, url=DOWNLOAD,
                                 catalog_url=url, vintage=periods[0] if periods else None,
                                 table_id=table, org_id=org, request_fields=list(fields))
                except Exception as error:
                    if blocked:
                        raise SiteBlocked(blocked) from error
                    failures.append(source_id)
                    print(f"{source_id}: {error}; dialogs={dialogs}", flush=True)
        await browser.close()
    return int(bool(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groups", nargs="*", choices=list(TABLES))
    parser.add_argument("--search", nargs="+")
    parser.add_argument("--catalog", default="MT_ZTITLE")
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--channel", default="chrome")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--inspect", nargs="+", metavar="ORG/TABLE")
    args = parser.parse_args()
    if args.search:
        search(args.search, args.catalog)
        return 0
    return asyncio.run(download(args.groups or list(TABLES), args.channel, args.force,
                                args.only, args.trace, args.inspect))


if __name__ == "__main__":
    raise SystemExit(main())
