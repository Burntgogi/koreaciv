"""Normalize layer CSVs while preserving the source labels and missing values."""
import csv
import argparse
import io
import json
import re
import site
import sys
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from zipfile import ZipFile

if __name__ == "__main__" and __package__ is None:
    sys.path.extend([str(Path(__file__).resolve().parent), site.getusersitepackages()])

from collect_econ_normalize import Regions, clean, coded, number, read_text, write_csv
from collect_layers import Archive, ECON, RAW, ROOT
from lib import crosswalk

OUT = ROOT / "data/build/layers"
ECON_OUT = ROOT / "data/build/econ"
POINT_FIELDS = ("name", "kind", "value", "unit", "year", "lon", "lat", "address", "source_id")
PERIOD = re.compile(r"\d*([YHMQ])(\d{4})(\d{2})? ")
TOTALS = {"계", "소계", "합계", "전국", "전체", "총계"}
PUBLISHED_PROVINCES = {
    "강원도": "강원특별자치도", "전라북도": "전북특별자치도", "제주도": "제주특별자치도",
}
FISCAL_PROVINCES = {
    "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시",
    "광주": "광주광역시", "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
    "경기": "경기도", "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
    "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도", "경남": "경상남도",
    "제주": "제주특별자치도",
}


def rows_csv(path):
    return csv.reader(io.StringIO(read_text(path)))


def kosis_rows(path):
    reader = rows_csv(path)
    periods, items = next(reader), next(reader)
    period_start = next(i for i, label in enumerate(periods) if PERIOD.match(label))
    columns = [(index, PERIOD.match(label).groups(), coded(items[index]))
               for index, label in enumerate(periods) if PERIOD.match(label)]
    for row in reader:
        if len(row) == len(periods) and row[0] != periods[0]:
            yield [coded(value) for value in row[:period_start]], columns, row


def stat(code, name, sido, year, indicator, value, unit, basis, source, *, industry="", current=""):
    numeric = number(value)
    return (code, name, current, sido, year, indicator, industry, "" if numeric is None else numeric,
            unit, basis, source)


def sido_label(name):
    name = clean(name)
    return "전국" if name in TOTALS else PUBLISHED_PROVINCES.get(name, name)


def official_totals(archive):
    old = json.loads((ECON / "manifest.json").read_text(encoding="utf-8"))
    paths = {
        source: ECON / old[source]["file"]
        for source in ("kosis-101-DT_1YL20921", "kosis-101-DT_1EB002", "kosis-101-DT_1K52F08")
    }
    paths.update({source: RAW / entry["file"] for source, entry in archive.entries.items()
                  if entry["file"].startswith("../econ/official_totals/") and entry["file"].endswith(".csv")})
    fiscal_source = "lofin-fiscal-2026"
    use_lofin = archive.has(fiscal_source)
    if use_lofin:
        del paths["kosis-101-DT_1YL20921"]
    results = []
    for source, path in paths.items():
        table = source.removeprefix("kosis-101-")
        for dims, columns, values in kosis_rows(path):
            raw_code, name = dims[0]
            province = sido_label(name)
            industry = ""
            for index, (frequency, year, subperiod), (item, label) in columns:
                if table == "DT_1YL20921":
                    if year != "2026" or item != "T20" or any(d[1] not in TOTALS for d in dims[1:]):
                        continue
                    indicator, unit, basis = "fiscal_independence", "%", "당초예산·세입과목개편후·공표 소계"
                elif table == "DT_1EB002":
                    if year != "2025" or dims[1][1] != "소계":
                        continue
                    indicator = {"T10": "cultivated_area", "T20": "paddy_area", "T30": "upland_area"}[item]
                    unit, basis = "ha", "경지 소재지"
                elif table == "DT_1K52F08":
                    industry_code, industry = dims[1]
                    if item != "T2" or year != "2024" or not re.fullmatch(r"0|[A-U]", industry_code):
                        continue
                    indicator, unit, basis = "establishment_workers", "명", "사업장·등록기반"
                elif table in {"DT_1DA7004S", "DT_1ES3B01S"}:
                    match = re.match(r"^(고용률|실업률)(\s|$)", label)
                    if not match or any(d[1] not in TOTALS for d in dims[1:]):
                        continue
                    indicator = {"고용률": "employment_rate", "실업률": "unemployment_rate"}[match[1]]
                    survey = "경제활동인구조사" if table == "DT_1DA7004S" else "지역별고용조사"
                    unit, basis = "%", f"거주지·{survey}·{frequency}{year}{subperiod or ''}"
                elif table == "DT_1C91":
                    if "명목" not in label or int(year) < 2018:
                        continue
                    _, industry = dims[1]
                    indicator, unit, basis = "grdp_current", "백만원", "생산지·당해년가격"
                else:
                    continue
                results.append(stat(raw_code, name, province, year, indicator, values[index],
                                    unit, basis, source, industry=industry))
    if use_lofin:
        contents = json.loads((RAW / archive.entries[fiscal_source]["file"]).read_text(encoding="utf-8"))
        for row in contents["firBysdSituIxInqRsltDto"]:
            name = row["bysdDv"]
            province = "전국" if name == "단체별평균" else FISCAL_PROVINCES[name]
            results.append(stat("", name, province, 2026, "fiscal_independence", row["bysdAvgRt"], "%",
                                "당초예산·세입과목개편후·공표 평균", fiscal_source))
            if province != "전국":
                field = "capRt" if province.endswith("도") else "spcSiRt"
                results.append(stat("", name, province, 2026, "fiscal_independence_headquarters",
                                    row[field], "%", "당초예산·세입과목개편후·본청", fiscal_source))
    write_csv(ECON_OUT / "official_totals.csv", results)
    print(f"official_totals.csv: {len(results):,} observations")


def district(regions, raw_code, name, parent):
    # Follow the official code crosswalk when the source code and name corroborate it.
    if len(raw_code) == 5 and raw_code.isdecimal():
        try:
            mapped = crosswalk.to_current(raw_code, regions.by_code.keys())
            if len(mapped) == 1 and clean(regions.by_code[mapped[0]][1]) == clean(name):
                return mapped[0], regions.by_code[mapped[0]][0]
        except crosswalk.CrosswalkError:
            pass
    code, province, _ = regions.resolve(name, parent)
    return code, province


def grdp_history(archive, regions):
    results = {"grdp_history": [], "grdp_history_2015": []}
    for source, entry in archive.entries.items():
        folder = Path(entry["file"]).parent.name
        if folder not in results:
            continue
        parent = entry["publisher"]
        path = RAW / entry["file"]
        headers = next(rows_csv(path))
        activity = next(i for i, label in enumerate(headers) if "경제활동" in label or "산업별" in label)
        geography = 1 - activity
        for dims, columns, values in kosis_rows(path):
            code, name = dims[geography]
            if name == parent or clean(name) in TOTALS:
                continue
            current, province = district(regions, code, name, parent)
            for index, (_, year, _), (_, label) in columns:
                if re.search(r"명목|당해년가격|당해연도가격", clean(label)) and "2018" <= year <= "2022":
                    revision = "2015" if folder.endswith("_2015") else "2020"
                    results[folder].append(stat(code, name, province, year, "grdp_current", values[index],
                                                "백만원", f"생산지·당해년가격·{revision}년 기준 개편",
                                                source, industry=dims[activity][1], current=current))
    for name, rows in results.items():
        if rows:
            write_csv(ECON_OUT / f"{name}.csv", rows)
            print(f"{name}.csv: {len(rows):,} observations")


def write_points(name, rows):
    write_table(name, POINT_FIELDS, rows)


def write_table(name, fields, rows):
    count = 0
    with (OUT / f"{name}.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        for row in rows:
            writer.writerow(row)
            count += 1
    print(f"{name}.csv: {count:,} observations")


def tidal_points(archive):
    source = "data-15126804"
    path = RAW / archive.entries[source]["file"]
    rows = rows_csv(path)
    next(rows)
    write_points("tidal_flat_points", ((name, "갯벌", "", "", "", lon, lat, "", source)
                                       for _, name, lon, lat in rows))


def records(archive, source):
    return csv.DictReader(io.StringIO(read_text(RAW / archive.entries[source]["file"])))


def transport(archive):
    source = "data-15088273"
    if archive.has(source):
        write_points("ports", (
            (r["항만명"], r["항구분"], "", "", "", "", "", r["항만위치"], source)
            for r in records(archive, source) if r["항구분"] == "무역항"
        ))
    source = "data-15147941"
    port_rows = []
    if archive.has(source):
        traffic = [r for r in records(archive, source) if r["연도"] == "2025"]
        if len({int(r["월"]) for r in traffic}) == 12 and all(number(r["전체물동량"]) is not None for r in traffic):
            total = sum(number(r["전체물동량"]) for r in traffic)
            port_rows.append(("부산항", "컨테이너 처리량", total, "TEU", 2025, "", "", "", source))
    source = "nlic-ports-2025"
    if archive.has(source):
        import xlrd

        book = xlrd.open_workbook(RAW / archive.entries[source]["file"])
        sheet = book.sheet_by_index(0)
        if str(sheet.cell_value(0, 4)) != "2025" or "누계" not in str(sheet.cell_value(1, 5)):
            raise ValueError("Unexpected annual port-tonnage columns")
        for index in range(2, sheet.nrows):
            row = sheet.row_values(index)
            if row[1:4] == ["합계", "소계", "소계"]:
                value = number(row[5])
                port_rows.append((row[0], "화물 처리량", "" if value is None else value, "톤(R/T)",
                                  2025, "", "", "", source))
    source = "mof-ports-2025"
    if archive.has(source):
        import pymupdf

        with pymupdf.open(RAW / archive.entries[source]["file"]) as document:
            text = " ".join(" ".join(document[i].get_text(sort=True).split()) for i in (2, 3, 4, 5))
        match = re.search(r"전국 무역항 컨테이너 물동량\(2025년\).*?"
                          r"총물동량\s+((?:[\d,]+\s+){6})전년", text)
        if match:
            total = int(match[1].split()[-1].replace(",", "")) * 1000
            port_rows.append(("전국", "컨테이너 처리량", total, "TEU", 2025, "", "", "", source))
        for name in ("인천항", "광양항"):
            match = re.search(rf"{name}은\s+전년\s*\([^)]*\)\s*대비\s*[\d.]+%\s*"
                              r"(?:감소|증가)한\s*([\d,]+)만\s*TEU", text)
            if not match:
                raise ValueError(f"Port TEU publication value missing: {name}")
            value = int(match[1].replace(",", "")) * 10000
            port_rows.append((name, "컨테이너 처리량", value, "TEU", 2025, "", "", "", source))
    if port_rows:
        write_points("port_traffic", port_rows)
    source = "data-15002851"
    locations = []
    if archive.has(source):
        locations.extend(
            (r["공항명"], "공항", "", "", r["데이터 기준일"][:4], r["경도(WGS84좌표)"],
             r["위도(WGS84좌표)"], r["행정구역"].strip(), source)
            for r in records(archive, source)
        )
    source = "incheon-aip"
    if archive.has(source):
        from bs4 import BeautifulSoup

        page = BeautifulSoup((RAW / archive.entries[source]["file"]).read_bytes(), "html.parser")
        fields = [row.get_text(" ", strip=True) for row in page.select("tr")]
        location = next(text for text in fields if "ARP coordinates and site at AD" in text)
        lat, lon = re.search(r"(\d{6})N\s+(\d{7})E", location).groups()
        operator = next(text for text in fields if "Aerodrome Operator, Address" in text)
        address = re.search(r"Corporation\s+(.+?Republic of Korea)", operator)[1]

        def degrees(dms):
            return round(int(dms[:-4]) + int(dms[-4:-2]) / 60 + int(dms[-2:]) / 3600, 7)

        locations.append(("인천", "공항", "", "", 2026, degrees(lon), degrees(lat), address, source))
    if locations:
        write_points("airport_locations", locations)
    source = "airportal-2025"
    if archive.has(source):
        from openpyxl import load_workbook

        with (RAW / archive.entries[source]["file"]).open("rb") as stream:
            workbook = load_workbook(stream, read_only=True, data_only=True)
            rows = list(workbook.active.values)[1:]
            workbook.close()
        write_points("airport_traffic", (
            (name, metric, "" if value is None else value, unit, 2025, "", "", "", source)
            for name, _, _, people, cargo in rows
            for metric, value, unit in [("여객", people, "명"), ("화물", cargo, "톤")]
            if name
        ))


def geographical_indications(archive):
    from bs4 import BeautifulSoup

    results = []
    source = "mafra-farm-gi"
    if archive.has(source):
        results.extend((r["등록번호"], r["등록명칭"], "", "농산물", r["등록일자"],
                        r["대상지역"], "", "유효", source) for r in records(archive, source))
    for source in ("fish-gi", "fish-gi-2", "fish-gi-3"):
        if not archive.has(source):
            continue
        page = BeautifulSoup((RAW / archive.entries[source]["file"]).read_bytes(), "html.parser")
        table = next(t for t in page.select("table") if "등록번호" in t.get_text() and "업체주소" in t.get_text())
        rows = [[c.get_text(" ", strip=True) for c in tr.select("td")]
                for tr in table.select("tbody tr")]
        for summary, detail in zip(rows[::2], rows[1::2], strict=True):
            if len(summary) != 6 or len(detail) != 3:
                raise ValueError("Unexpected fisheries registration table")
            results.append((detail[0], summary[2], summary[1], "수산물", summary[5], "", detail[2], "", source))
    source = "forest-gi"
    if archive.has(source):
        import pymupdf

        with pymupdf.open(RAW / archive.entries[source]["file"]) as document:
            table = document[0].find_tables().tables[0].extract()
        registrations = {}
        for row in table[1:]:
            for index in range(0, len(row), 3):
                key, label, registered = row[index:index + 3]
                if not key:
                    continue
                state = "취소" if "(취소)" in label else "운영"
                label = " ".join(label.replace("(취소)", "").split())
                date = registered.strip().strip(".")
                year, month, day = map(int, date.split("."))
                registrations[int(re.search(r"\d+", key)[0])] = (
                    key, label, label, "임산물", f"{2000 + year:04}-{month:02}-{day:02}", "", "", state, source,
                )
        if len(registrations) != 64 or sum(r[-2] == "취소" for r in registrations.values()) != 6:
            raise ValueError("Forestry registrations do not match the publication totals")
        results.extend(registrations[key] for key in sorted(registrations))
    if results:
        write_table("geographical_indications", (
            "registration_number", "name", "product", "kind", "registration_date",
            "registration_area", "address", "registration_status", "source_id",
        ), results)


def generators(archive):
    source = "epsis-generators"
    if not archive.has(source):
        return
    path = RAW / archive.entries[source]["file"]
    year = archive.entries[source]["vintage"][:4]
    value = r'"((?:\\.|[^"\\])*)"'
    assignment = re.compile(rf"\b(c1|c2|c11)\s*=\s*{value}\s*;")
    fields = re.compile(rf'"(c[0-9]+)"\s*:\s*{value}')

    def rows():
        # Interpret the literals that populate the public grid, without evaluating JavaScript.
        current = {}
        parts = iter(read_text(path).split("gridData.push("))
        declarations = next(parts)
        for part in parts:
            current.update(assignment.findall(declarations))
            payload, _, declarations = part.partition("});")
            raw = dict(fields.findall(payload))
            if {"c3", "c4", "c7"} <= raw.keys():
                yield (current.get("c2") or current.get("c1"), raw["c7"], raw["c4"], "MW",
                       year, "", "", current.get("c11") or raw.get("c10", ""), source)

    write_points("generators", rows())


def research_institutes(archive):
    source = "data-15045195"
    if archive.has(source):
        write_points("research_institutes", (
            (r["기관명"], "NST 소관 기관", "", "", "", "", "", "", source)
            for r in records(archive, source)
        ))


def local_livestock(archive, regions):
    source = "data-15071107"
    if not archive.has(source):
        return
    with ZipFile(RAW / archive.entries[source]["file"]) as package:
        member, = [name for name in package.namelist() if name.endswith("시군구별_사육두수.csv")]
        with package.open(member) as stream:
            raw = list(csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig")))
    grouped = defaultdict(list)
    for row in raw:
        grouped[row["시도"], row["시군구"]].append(row)
    results = []
    for (parent, name), observations in grouped.items():
        current, province = district(regions, "", name, parent)
        for field, indicator in [("한우(두)_소계", "beef_cattle_including_non_hanwoo"),
                                 ("돼지(두)_소계", "pigs")]:
            if len(observations) == 1:
                value = observations[0][field]
                basis = "전국오염원조사·사육지"
            else:
                value = ""
                basis = "전국오염원조사·동일 지역명 복수 공표"
            results.append(stat("", name, province, 2019, indicator, value, "마리",
                                basis, source, current=current))
    write_csv(OUT / "livestock.csv", results)
    print(f"livestock.csv: {len(results):,} observations")


def legal_layers(archive, regions):
    from bs4 import BeautifulSoup

    source = "border-article"
    if archive.has(source):
        page = BeautifulSoup((RAW / archive.entries[source]["file"]).read_bytes(), "html.parser")
        law = next(node for node in page.select("div.lawcon")
                   if node.get_text(" ", strip=True).startswith("제2조(접경지역의 범위)"))
        article = law.get_text(" ", strip=True)
        listed = list(re.finditer(r"\d\.\s*(인천광역시|경기도|강원특별자치도):\s*"
                                  r"([가-힣]+[시군](?:,\s*[가-힣]+[시군])*)", article))
        results = []
        for line in listed:
            for name in line[2].split(","):
                name = name.strip()
                current, province = district(regions, "", name, line[1])
                paragraph = 2 if article.index("②") < line.start() else 1
                results.append(stat("", name, province, 2025, "border_area_designated", 1,
                                    "지정 여부", f"시행령 제2조제{paragraph}항", source, current=current))
        if len(listed) != 5 or not all(row[3] for row in results):
            raise ValueError("Unexpected or unresolved border designations")
        write_csv(OUT / "border_areas.csv", results)
        print(f"border_areas.csv: {len(results)} observations")
    source = "special-city-act"
    if archive.has(source):
        page = BeautifulSoup((RAW / archive.entries[source]["file"]).read_bytes(), "html.parser")
        paragraph = page.find(string=lambda value: value and value.lstrip().startswith("③ 통합특별시의 청사는"))
        match = re.search(r"종전의 (.+?)를 균형있게", paragraph)
        names = re.split(r",\s*", match[1])
        write_points("special_city_offices", (
            (name, "통합특별시 청사", "", "", 2026, "", "", "", source) for name in names
        ))


def pdf_lines(page, bounds):
    lines = []
    for block in page.get_text("dict", clip=bounds)["blocks"]:
        for line in block.get("lines", []):
            x, y, _, _ = line["bbox"]
            text = "".join(span["text"] for span in line["spans"]).strip()
            if text:
                lines.append((y, x, text))
    lines.sort()
    combined = []
    for y, x, label in lines:
        if combined and abs(y - combined[-1][0]) < 0.6:
            combined[-1][1].append((x, label))
        else:
            combined.append((y, [(x, label)]))
    return [(y, "".join(text for _, text in sorted(pieces))) for y, pieces in combined]


def municipal_offices(archive):
    source = "municipalities-2025"
    if not archive.has(source):
        return
    import pymupdf

    rows = []
    province = ""
    city = ""
    with pymupdf.open(RAW / archive.entries[source]["file"]) as document:
        first_table = document[430].find_tables().tables[0]
        name_x, address_x, postal_x = [cell[0] for cell in first_table.rows[1].cells[:3]]
        postal_right = first_table.rows[1].cells[2][2]
        for index in range(430, 442):
            page = document[index]
            postal_box = (postal_x, 65, postal_right, 570)
            postcodes = [(y, code) for y, code in pdf_lines(page, postal_box) if re.fullmatch(r"\d{5}", code)]
            top = min(y for y, _ in postcodes) - 12
            bottom = max(y for y, _ in postcodes) + 16
            name_box = (name_x, top, address_x, bottom)
            address_box = (address_x, top, postal_x, bottom)
            labels = []
            for y, text in pdf_lines(page, name_box):
                name = clean(text)
                if name == "구분":
                    continue
                if labels and name in {"자치시", "자치도", "특별자치도", "북부청사", "동부청사"}:
                    previous_y, previous = labels.pop()
                    labels.append(((y + previous_y) / 2, previous + name))
                else:
                    labels.append((y, name))
            address_lines = [(y, text) for y, text in pdf_lines(page, address_box)
                             if clean(text) != "소재지"]
            parcel = {n: [] for n in range(len(postcodes))}
            for y, text in address_lines:
                closest = min(parcel, key=lambda n: abs(postcodes[n][0] - y))
                parcel[closest].append(text)
            names = {}
            for n, (y, name) in enumerate(labels):
                if name.endswith(("특별시", "광역시", "자치시", "도")) and not name.startswith("◦"):
                    province, city = name, ""
                    names[n] = name, "시도청"
                elif name.endswith("청사") and not name.startswith("◦"):
                    names[n] = name, "시도청"
                elif name.startswith("◦"):
                    names[n] = f"{province} {city} {name[1:]}", "일반구청"
                elif re.fullmatch(r"\(제?\d+청사\)", name):
                    names[n] = f"{province} {city} {name}", "시군구청"
                else:
                    if name.endswith("시"):
                        city = name
                    names[n] = f"{province} {name}", "시군구청"
            for n, (y, _) in enumerate(postcodes):
                closest = min(names, key=lambda i: abs(labels[i][0] - y))
                name, kind = names[closest]
                if not parcel[n] or abs(labels[closest][0] - y) > 19:
                    raise ValueError(f"Unmatched municipal office column at PDF page {index + 1}, {y}")
                rows.append((name, kind, "", "", 2025, "", "", " ".join(parcel[n]), source))
    if len(rows) < 240:
        raise ValueError("Incomplete municipal office table")
    write_points("municipal_offices", rows)


def annual_pm25(archive):
    source = "air-yearbook-2025"
    if not archive.has(source):
        return
    import pymupdf

    result = {}
    stations = {}
    with pymupdf.open(RAW / archive.entries[source]["file"]) as document:
        if "1.4.6 초미세먼지" not in document[144].get_text():
            raise ValueError("Annual station PM2.5 table missing")
        for index in range(398, 413):
            for line in document[index].get_text(sort=True).splitlines():
                found = re.search(r"\b(\d{6})\s+(.+?)\s+(1[23]\d\.\d+)\s+(3\d\.\d+)\b", line)
                if not found:
                    continue
                code, label, lon, lat = found.groups()
                parts = re.split(r"\s{2,}", label.strip(), maxsplit=1)
                address = " ".join(parts[1].split()) if len(parts) == 2 else ""
                stations.setdefault(code, (lon, lat, address))
        for index in range(144, 153):
            page = document[index]
            for table in page.find_tables().tables:
                header = table.extract()[0]
                if len(header) != 15 or header[3] != "측정소코드" or header[-1] != "'25년":
                    continue
                _, y0, _, y1 = table.bbox
                cells = table.rows[0].cells

                def column(index):
                    return pdf_lines(page, (cells[index][0], y0, cells[index][2], y1))

                names = column(2)
                annual = column(-1)
                for y, code in column(3):
                    if not re.fullmatch(r"\d{6}", code):
                        continue
                    name_y, name = min(names, key=lambda item: abs(item[0] - y))
                    value_y, raw_value = min(annual, key=lambda item: abs(item[0] - y))
                    if abs(name_y - y) > 3:
                        raise ValueError(f"Station name missing at {index + 1}/{code}")
                    reading = re.fullmatch(r"(\d+)(\*{0,2})", raw_value) if abs(value_y - y) <= 3 else None
                    value, flag = reading.groups() if reading else ("", "")
                    if code in result:
                        raise ValueError(f"Duplicate PM2.5 station code: {code}")
                    lon, lat, address = stations.get(code, ("", "", ""))
                    kind = "PM2.5 연평균" + (" " + flag if flag else "")
                    result[code] = (name, kind, value, "µg/m³", 2025, lon, lat, address, source)
    if len(result) < 500 or sum(bool(row[5]) for row in result.values()) < 500:
        raise ValueError("Annual station table extraction yielded too few observations")
    write_points("pm25_stations", result.values())


def park_visitors(archive):
    source = "knps-statistics"
    if not archive.has(source):
        return
    import pymupdf

    with pymupdf.open(RAW / archive.entries[source]["file"]) as document:
        page = document[38].get_text(sort=True)
    if "연간 탐방객 수" not in page:
        raise ValueError("Annual visitor table missing")
    values = {}
    for line in page.splitlines():
        match = re.fullmatch(r"\s*([가-힣\s]+?)(?:\s+2\))?\s+"
                             r"((?:[\d,]+|-)(?:\s+(?:[\d,]+|-)){4})\s*", line)
        if match:
            name = clean(match[1])
            values[name] = int(match[2].split()[-1].replace(",", ""))
    if len(values) != 24 or sum(v for n, v in values.items() if n != "계") != values["계"]:
        raise ValueError("Park totals do not agree with the printed total")
    write_points("park_visitors", (
        (name, "국립공원 탐방객", value, "명", 2025, "", "", "", source)
        for name, value in values.items() if name != "계"
    ))


@contextmanager
def workbook_rows(path):
    if path.suffix == ".zip":
        with ZipFile(path) as package:
            member, = (item for item in package.infolist()
                       if re.match(r"(?:통계표\s*)?0?2[. _-]", Path(item.filename).name)
                       and Path(item.filename).suffix in {".xls", ".xlsx"})
            if member.file_size > 10 * 1024 * 1024:
                raise ValueError(f"Unexpected workbook size: {path}")
            extension = Path(member.filename).suffix
            content = package.read(member)
    else:
        extension = path.suffix
        content = path.read_bytes()
    if extension == ".xls":
        import xlrd

        workbook = xlrd.open_workbook(file_contents=content, on_demand=True)
        try:
            yield (map(sheet.row_values, range(sheet.nrows)) for sheet in workbook.sheets())
        finally:
            workbook.release_resources()
    else:
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False)
        try:
            for sheet in workbook:
                sheet.reset_dimensions()
            yield (iter(sheet.values) for sheet in workbook)
        finally:
            workbook.close()


def key_industries(regions):
    manifest = json.loads((ECON / "manifest.json").read_text(encoding="utf-8"))
    result = []
    targets = {"19", "20", "24", "26", "30", "31", "261", "311"}
    for source, entry in sorted(manifest.items()):
        if not source.endswith("-business-2024"):
            continue
        parent = entry["publisher"]
        values = {}
        with workbook_rows(ECON / entry["file"]) as sheets:
            for rows in sheets:
                columns = {}
                for row in rows:
                    if not row:
                        continue
                    if str(row[0]).startswith("산업분류"):
                        columns.clear()
                        district_name = ""
                        for i, (header, item) in enumerate(zip(row, next(rows))):
                            if header:
                                district_name = str(header).splitlines()[0].strip()
                            if district_name != parent and district_name.endswith(("시", "군", "구")):
                                if str(item).split("\n")[0].strip() == "종사자수":
                                    columns[i] = district_name
                        continue
                    if len(row) < 4:
                        continue
                    code = next((str(x).strip() for x in row[1:3] if str(x).strip() in targets), "")
                    if not code:
                        continue
                    title = re.sub(r"^\s*\d+\.\s*", "", str(row[3]).strip())
                    for i, name in columns.items():
                        key = (name, code, title)
                        value = number(row[i]) if i < len(row) else None
                        if key in values and values[key] != value:
                            raise ValueError(f"Conflicting industry cells: {source}, {key}")
                        values[key] = value
        for (name, code, title), value in values.items():
            current, province = district(regions, "", name, parent)
            result.append(stat("", name, province, 2024, "establishment_workers", value, "명",
                               "사업장·등록기반", source,
                               industry=f"C{code} {title}", current=current))
    if result:
        write_csv(OUT / "key_industries.csv", result)
        print(f"key_industries.csv: {len(result):,} observations")


def foreign_residents(archive, regions):
    source = "kosis-110-TX_11025_A001_A"
    if not archive.has(source):
        return
    reader = rows_csv(RAW / archive.entries[source]["file"])
    periods, items, types, sexes = (next(reader) for _ in range(4))
    indicators = {"15110AA0AA": "foreign_residents_population_base", "15110AA000": "foreign_residents"}
    columns = [(i, PERIOD.match(p)[2], indicators[coded(items[i])[0]])
               for i, p in enumerate(periods) if PERIOD.match(p) and coded(items[i])[0] in indicators
               and types[i] == "소계" and coded(sexes[i])[1] == "계"]
    results = []
    for row in reader:
        if len(row) != len(periods):
            continue
        raw_code, name, parent = regional_dimension(list(map(coded, row[:3])))
        if not name:
            continue
        current, province = district(regions, raw_code, name, parent)
        for position, year, indicator in columns:
            results.append(stat(raw_code, name, province, year, indicator, row[position], "명",
                                "거주지·인구총조사", source, current=current))
    write_csv(OUT / "foreign_residents.csv", results)
    print(f"foreign_residents.csv: {len(results):,} observations")


def regional_dimension(dims):
    _, parent = dims[0]
    parts = [(code, label) for code, label in dims[1:] if label and label not in TOTALS]
    if not parts:
        if parent.startswith("세종"):
            return dims[0][0], "세종시", parent
        return "", "", parent
    raw_code, name = parts[-1]
    if len(parts) > 1 and parts[0][1].endswith("시"):
        prefix = parts[0][1]
        if not name.startswith(prefix):
            name = f"{prefix} {name}"
    return raw_code, name, parent


def recent_regional_stats(archive, regions):
    indicators = {
        "DT_H_SM": "current_smoking_rate",
        "DT_HEALTH_RECOG": "self_rated_good_health_rate",
        "DT_H_MENTAL_DEPRESS": "annual_depressed_mood_rate",
        "DT_H_OBE_OBE": "self_reported_obesity_rate",
        "DT_1ET0034": "paddy_rice_production",
    }
    tables = {"health": [], "rice": []}
    for source, entry in archive.entries.items():
        indicator = indicators.get(entry.get("table_id"))
        if not indicator:
            continue
        rice = entry["table_id"] == "DT_1ET0034"
        path = RAW / entry["file"]
        for dims, columns, row in kosis_rows(path):
            raw_code, name, parent = regional_dimension(dims)
            if not name:
                continue
            current, province = district(regions, raw_code, name, parent)
            for position, (_, year, _), (_, label) in columns:
                if rice and re.match(r"논벼\s*:\s*생산량", label):
                    tables["rice"].append(stat(raw_code, name, province, year, indicator, row[position],
                                               "톤", "생산지·정곡 92.9%", source, current=current))
                elif not rice and re.match(r"표준화율(?:\s|$)", label):
                    tables["health"].append(stat(raw_code, name, province, year, indicator, row[position],
                                                 "%", "거주지·연령표준화율", source, current=current))
    for name, rows in tables.items():
        if rows:
            write_csv(OUT / f"{name}.csv", rows)
            print(f"{name}.csv: {len(rows):,} observations")


def academies(archive, regions):
    source = "kosis-101-DT_1YL21191"
    if not archive.has(source):
        return
    provinces = {}
    results = []
    for ((raw_code, name),), columns, row in kosis_rows(RAW / archive.entries[source]["file"]):
        if len(raw_code) in (2, 4):
            current, province = "", sido_label(name)
            provinces[raw_code] = province
        else:
            parent = provinces[raw_code[:-3]]
            current, province = district(regions, raw_code, name, parent)
        for index, (_, year, _), (item, _) in columns:
            if item == "T001":
                results.append(stat(raw_code, name, province, year, "private_academies", row[index],
                                    "개", "소재지·사설학원수", source, current=current))
    write_csv(OUT / "academies.csv", results)
    print(f"academies.csv: {len(results):,} observations")


def disaster_damage(archive, regions):
    source = "disaster-2024"
    if not archive.has(source):
        return
    import xlrd

    results = []
    path = RAW / archive.entries[source]["file"]
    with ZipFile(path) as package:
        for member in sorted(package.infolist(), key=lambda item: item.filename):
            if not re.fullmatch(r"2\.9\.\d+ 시군구별\(.+\)\.xls", member.filename):
                continue
            book = xlrd.open_workbook(file_contents=package.read(member), on_demand=True)
            sheet = book.sheet_by_index(0)
            if "[2024]" not in clean(sheet.cell_value(0, 0)):
                raise ValueError(f"Unexpected disaster-report year: {member.filename}")
            header = []
            observations = {}
            for index in range(sheet.nrows):
                row = sheet.row_values(index)
                if clean(row[0]) == "구분":
                    header = row
                if clean(row[0]) != "총피해액":
                    continue
                if not header or row[3] != "천원":
                    raise ValueError(f"Unexpected damage table: {member.filename}")
                for label, value in zip(header[4:], row[4:]):
                    if label:
                        observations[label.strip()] = number(value)
            subtotal = observations.pop("총계")
            if all(value is not None for value in observations.values()) and sum(observations.values()) != subtotal:
                raise ValueError(f"District damage amounts disagree with province total: {member.filename}")
            for label, value in observations.items():
                parent, _, name = label.partition(" ")
                current, province = district(regions, "", name, parent)
                results.append(stat("", name, province, 2024, "natural_disaster_damage", value, "천원",
                                    "피해 발생지·선공개", source, current=current))
            book.release_resources()
    if results:
        write_csv(OUT / "disaster_damage.csv", results)
        print(f"disaster_damage.csv: {len(results):,} observations")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    archive = Archive()
    regions = Regions()
    official_totals(archive)
    grdp_history(archive, regions)
    if archive.has("data-15126804"):
        tidal_points(archive)
    transport(archive)
    geographical_indications(archive)
    generators(archive)
    research_institutes(archive)
    local_livestock(archive, regions)
    legal_layers(archive, regions)
    municipal_offices(archive)
    park_visitors(archive)
    key_industries(regions)
    foreign_residents(archive, regions)
    recent_regional_stats(archive, regions)
    annual_pm25(archive)
    disaster_damage(archive, regions)
    academies(archive, regions)


if __name__ == "__main__":
    main()
