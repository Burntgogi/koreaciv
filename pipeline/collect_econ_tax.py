"""Check or download the public address-based TASIS workbook."""
import argparse
import asyncio
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

from collect_econ_web import Archive, SiteBlocked

TITLE = "시·군·구별 근로소득 연말정산 신고현황(주소지)"
PAGE = ("https://tasis.nts.go.kr/websquare/websquare.html?"
        "w2xPath=/ui/ep/e/a/UTWEPEAA02.xml&sttPblYr=2023&sttsMtaInfrId=20230103D01202347667")
PAGE_2024 = PAGE.replace("2023&sttsMtaInfrId=20230103D01202347667",
                         "2025&sttsMtaInfrId=20250103D01202541132")


async def download(tax_year=2022):
    page_url = {2022: PAGE, 2024: PAGE_2024}[tax_year]
    async with async_playwright() as driver:
        browser = await driver.chromium.launch(channel="chrome")
        context = await browser.new_context(accept_downloads=True, locale="ko-KR")
        lock = asyncio.Lock()
        blocked = None

        async def rate_limit(route):
            nonlocal blocked
            resource = route.request.resource_type
            url = urlsplit(route.request.url)
            if url.hostname != "tasis.nts.go.kr" or resource in {"image", "font", "media"}:
                await route.abort()
                return
            async with lock:
                if blocked:
                    await route.abort()
                    return
                await asyncio.sleep(1.2)
                if url.path.endswith("/xmlToExcel2.wq"):
                    await route.continue_()
                    return
                response = await route.fetch(max_redirects=0, timeout=30000)
                if response.status in (401, 403, 429):
                    blocked = f"HTTP {response.status} {url.path}"
                    await route.abort()
                    return
                await route.fulfill(response=response)
                await response.dispose()

        await context.route("**/*", rate_limit)
        page = await context.new_page()
        try:
            await page.goto(page_url, wait_until="commit")
            title = page.get_by_text("4-2-15. " + TITLE, exact=True).first
            missing = page.get_by_text("통계연보 테이블이 존재하지 않습니다", exact=False).first
            await title.or_(missing).first.wait_for(timeout=210000)
            if await missing.is_visible():
                print(await missing.inner_text(), flush=True)
                return
            async with page.expect_download(timeout=60000) as pending:
                await page.locator("#mf_btnDownload").click()
            export = await pending.value
            content = (await export.path()).read_bytes()
        except Exception as error:
            if blocked:
                raise SiteBlocked(blocked) from error
            raise
        await browser.close()
    if not content.startswith(b"PK\x03\x04"):
        raise ValueError("Expected an XLSX container")
    if tax_year == 2024:
        from io import BytesIO
        from openpyxl import load_workbook

        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True, keep_links=False)
        try:
            workbook.active.reset_dimensions()
            if str(tax_year) not in {str(v) for v in next(workbook.active.values)}:
                raise ValueError("The workbook's first row does not identify tax year 2024")
        finally:
            workbook.close()
    source = f"tasis-4-2-15-{tax_year}"
    Archive().save(source, f"income/{source}.xlsx", content,
                   title=TITLE, publisher="국세청", url="https://tasis.nts.go.kr/websquare/xmlToExcel2.wq",
                   catalog_url=page_url, vintage=tax_year, table_id="4-2-15",
                   publication_year=tax_year + 1, table_metadata_id=page_url.split("=")[-1])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, choices=(2022, 2024), default=2022)
    asyncio.run(download(parser.parse_args().year))
