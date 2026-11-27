"""Normalize fifth-pass official sources with their published units and blanks."""

import argparse
import csv
import io
import json
import re
import site
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

if __name__ == "__main__" and __package__ is None:
    sys.path.extend([str(Path(__file__).resolve().parent), site.getusersitepackages()])

from bs4 import BeautifulSoup
from collect_layers2 import HERITAGE_PAGES, INSTITUTIONS, LayerArchive, RAW, ROOT, heritage_year, heritage_years
from collect_econ_normalize import FIELDS, Regions, clean, coded, number, read_text
from collect_layers_normalize import POINT_FIELDS
from lib import crosswalk

OUT = ROOT / "data/build/layers"


def source_path(archive, source):
    if not archive.has(source):
        raise ValueError(f"Collect missing source first: {source}")
    return RAW / archive.entries[source]["file"]


def write(name, header, rows):
    target = OUT / name
    pending = target.with_suffix(".tmp")
    with pending.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)
    pending.replace(target)
    print(f"{name}: {len(rows):,} rows")


def road(archive):
    import xlrd

    source = "nlic-road-od-2024"
    book = xlrd.open_workbook(str(source_path(archive, source)), on_demand=True)
    try:
        table, = book.sheets()
        if "기간: (2024~2024)" not in table.row_values(0) or "단위(톤/년)" not in table.row_values(0):
            raise ValueError("Unexpected road OD vintage or unit")
        destinations = table.row_values(1)[1:]
        origins = table.col_values(0)[2:]
        if len(origins) != 17 or len(destinations) != 17 or set(origins) != set(destinations):
            raise ValueError("Expected the 17 × 17 road OD matrix")
        rows = []
        for index, origin in enumerate(origins, start=2):
            for destination, value in zip(destinations, table.row_values(index)[1:]):
                if value != "" and (not isinstance(value, float) or not value.is_integer() or value < 0):
                    raise ValueError(f"Unexpected OD cell: {origin}, {destination}, {value}")
                rows.append((origin, destination, 2024, "road", "" if value == "" else int(value), "톤/년", source))
    finally:
        book.release_resources()
    write("flows_od.csv", ("origin", "destination", "year", "mode", "value", "unit", "source_id"), rows)


def trade(archive):
    regions = Regions()
    population = ROOT / "data/raw/population/jumin_age5_sgg_202512.csv"
    historical = {}
    for row in csv.reader(read_text(population).splitlines()):
        match = re.fullmatch(r"(.+?)\s*\((\d{5})0{5}\)", row[0])
        if match:
            historical[clean(match[1])] = match[2]
    metrics = dict(expUsdAmt="trade_export", impUsdAmt="trade_import", cmtrBlncAmt="trade_balance")
    rows = []
    for source, entry in sorted(archive.entries.items()):
        if not source.startswith("customs-trade-sgg-"):
            continue
        result = json.loads(source_path(archive, source).read_bytes())
        places = set()
        for row in result["items"]:
            year, name = row["priodTitle"], row["sidoSggNm"]
            if year == "총계":
                continue
            if year != entry["vintage"] or not name or name in places:
                raise ValueError(f"Unexpected 2025 trade row: {source}, {year}, {name}")
            places.add(name)
            raw_code = row["sggCd"].strip()
            current, province, _ = regions.resolve(name, entry["province"])
            historical_code = raw_code or historical.get(clean(name), "")
            if historical_code in crosswalk.SPLITS:
                current = ""
            elif historical_code:
                try:
                    mapped, = crosswalk.to_current(historical_code, regions.by_code)
                except crosswalk.CrosswalkError:
                    pass
                else:
                    current = mapped
                    province = regions.by_code[current][0]
            for field, indicator in metrics.items():
                value = number(row[field])
                rows.append((raw_code, name, current, province, year, indicator, "",
                             "" if value is None else value * 1000, "USD",
                             "연간·신고수리일·원표 천 달러", source))
    if len({row[-1] for row in rows}) != 17:
        raise ValueError("Expected 17 trade overview exports")
    write("trade_sgg.csv", FIELDS, rows)
    geography = {row[1]: (row[2], row[3]) for row in rows}
    hs2 = defaultdict(list)
    hs2_sources = 0
    for source, entry in sorted(archive.entries.items()):
        if not source.startswith("customs-trade-hs2-"):
            continue
        hs2_sources += 1
        result = json.loads(source_path(archive, source).read_bytes())
        seen = set()
        for row in result["items"]:
            if row["priodTitle"] == "총계":
                continue
            name, hs_code = row["sggNm"], row["hsSgn"]
            key = (name, hs_code)
            if row["priodTitle"] != entry["vintage"] or name not in geography or key in seen:
                raise ValueError(f"Unexpected HS2 region, vintage or duplicate: {source}, {key}")
            seen.add(key)
            if not re.fullmatch(r"\d{2}", hs_code):
                continue
            industry = f"HS{hs_code} {row['korePrlstNm']}".rstrip()
            for field, indicator in list(metrics.items())[:2]:
                value = number(row[field])
                if value is not None and value > 0:
                    hs2[name, indicator].append((value, industry, source, row["priodTitle"]))
    if hs2:
        top = []
        for (name, indicator), values in sorted(hs2.items()):
            current, province = geography[name]
            for value, industry, source, year in sorted(values, key=lambda item: (-item[0], item[1]))[:5]:
                top.append(("", name, current, province, year, indicator, industry, value * 1000, "USD",
                            "연간·신고수리일·원표 천 달러·양수 상위 5품목", source))
        write("trade_sgg_hs2.csv", FIELDS, top)
        print(f"HS2 sources: {hs2_sources}")


def park(archive):
    import pymupdf

    source = "knps-area-2025"
    with pymupdf.open(source_path(archive, source)) as document:
        table, = document[103].find_tables().tables
        values = table.extract()
    if values[0][4] != "공원구역 면적(㎢)":
        raise ValueError("Unexpected park area heading")
    total = Decimal(values[1][4].replace(",", ""))
    rows = []
    part_totals = {"land": Decimal(0), "sea": Decimal(0)}
    for _, name, designated, address, value, note in (r for r in values if (r[0] or "").isdigit()):
        name = re.sub(r"\s+", "", name)
        designated = re.sub(r"\s+", "", designated).strip(".")
        area = Decimal(value.replace(",", ""))
        parts = re.fullmatch(r"육상:\s*([\d,.]+)\s+해면:\s*([\d,.]+)", note or "")
        if note and not parts:
            raise ValueError(f"Unrecognized land/water annotation: {name}")
        land, sea = (Decimal(part.replace(",", "")) for part in parts.groups()) if parts else (area, Decimal(0))
        if land + sea != area:
            raise ValueError(f"Area components disagree: {name}")
        part_totals["land"] += land
        part_totals["sea"] += sea
        rows.append((name, "국립공원 지정면적", area, "km²", 2025, "", "", address, source,
                     designated, land if parts else "", sea if parts else "", "원표 비고" if parts else ""))
    printed = [Decimal(re.search(r":\s*([\d,.]+)", values[idx][5])[1].replace(",", "")) for idx in (1, 2)]
    tolerance = Decimal("0.001")
    if (len(rows) != 23 or abs(sum(row[2] for row in rows) - total) > tolerance
            or any(abs(actual - stated) > tolerance for actual, stated in zip(part_totals.values(), printed))):
        raise ValueError("Park area totals do not match the published totals")
    write("park_area.csv", (*POINT_FIELDS, "designated", "land_km2", "sea_km2", "area_basis"), rows)


def dam(archive):
    source = "wamis-dam-observations"
    collection = json.loads(source_path(archive, source).read_bytes())
    if collection["crs"]["properties"]["name"] != "urn:ogc:def:crs:EPSG::4326":
        raise ValueError("Unexpected WAMIS coordinate system")
    rows = []
    codes = set()
    for feature in collection["features"]:
        geom = feature["geometry"]
        props = feature["properties"]
        lon, lat = geom["coordinates"] if geom else ("", "")
        if geom and (geom["type"] != "Point" or not (124 <= lon <= 132 and 32 <= lat <= 40)):
            raise ValueError("Unexpected WAMIS point")
        if props["dm_cd"] in codes:
            raise ValueError(f"Duplicate WAMIS dam code: {props['dm_cd']}")
        codes.add(props["dm_cd"])
        rows.append((props["dm_nm"], "댐 관측소", "", "", "", lon, lat, "", source))
    if len(rows) != collection["totalFeatures"]:
        raise ValueError("WAMIS response returned a partial feature set")
    write("dam_observations.csv", POINT_FIELDS, rows)


def hanwoo(archive):
    source = "mtrace-hanwoo-202610"
    regions = Regions()
    reader = csv.reader(read_text(source_path(archive, source)).splitlines())
    period, breed, sex, series = (next(reader) for _ in range(4))
    month = archive.entries[source]["vintage"]
    if (not period[2].startswith(f"M{month} ") or not breed[2].endswith(" 한우")
            or not sex[2].endswith(" 전체") or series[2] != "DTVAL_CO 원데이터"):
        raise ValueError("Unexpected livestock table headings")
    rows = []
    for province_label, region_label, value, _ in reader:
        _, province_name = coded(province_label)
        code, name = coded(region_label)
        current, province, _ = regions.resolve(name, province_name)
        # The statistical geography uses its own codes. Match the published names within the province.
        count = number(value)
        rows.append((code, name, current, province, month[:4], "hanwoo_stock", "",
                     count if count is not None else "", "두", f"농장 소재지·암수 전체·{month}", source))
    write("livestock_hanwoo.csv", FIELDS, rows)


def pig_sido(archive):
    source = "mtrace-pig-sido-2026q3"
    regions = Regions()
    reader = csv.reader(read_text(source_path(archive, source)).splitlines())
    period, items, series = next(reader), next(reader), next(reader)
    value_col = next(i for i, item in enumerate(items) if "마리수" in item)
    if not period[value_col].startswith("Q202603 ") or series[value_col] != "DTVAL_CO 원데이터":
        raise ValueError("Unexpected pig stock quarter")
    rows = []
    for row in reader:
        _, name = coded(row[0])
        value = number(row[value_col])
        province = regions.aliases.get(name, name)
        rows.append(("", name, "", province, 2026, "pig_stock", "",
                     "" if value is None else value, "두", "2026년 3분기·시도·사육규모 합계", source))
    write("livestock_pig_sido.csv", FIELDS, rows)


def institutions(archive):
    rows = []
    for key, (name, kind, _, locality) in INSTITUTIONS.items():
        source = f"institution-{key}"
        if not archive.has(source):
            continue
        page = BeautifulSoup(source_path(archive, source).read_bytes(), "html.parser")
        pattern = re.compile(re.escape(locality) + r"\s+(?:[가-힣]+[읍면동]\s+)?"
                             r"(?:[가-힣0-9]+(?:로|길)\s*)+\d+(?:-\d+)?(?:\s+\([가-힣]+동\))?")
        matches = set()
        for element in page.select("address,footer p,footer li,#footer p,#foot p,.address"):
            match = pattern.search(" ".join(element.get_text(" ", strip=True).split()))
            if match:
                matches.add(match[0])
        if len(matches) != 1:
            raise ValueError(f"Expected one published address: {name}, {matches}")
        rows.append((name, kind, "", "", "", "", "", matches.pop(), source))
    if rows:
        write("research_campuses.csv", POINT_FIELDS, rows)


def university_funding(archive):
    from openpyxl import load_workbook

    source = "academyinfo-research-funding-2026"
    with ZipFile(source_path(archive, source)) as package:
        member, = package.infolist()
        if not member.filename.endswith(".xlsx") or member.file_size > 5_000_000:
            raise ValueError("Unexpected university funding workbook")
        content = package.read(member)
    book = load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False)
    try:
        sheet, = book.worksheets
        sheet.reset_dimensions()
        cells = iter(sheet.values)
        title, _, unit, headings, group, _, metric, sex = (next(cells) for _ in range(8))
        if ("2026년" not in title[0] or "천원" not in unit[0] or headings[5] != "학교"
                or group[8] != "계" or metric[10] != "연구비" or sex[10:12] != ("남", "여")):
            raise ValueError("Unexpected disclosure columns")
        rows = []
        year = ""
        for row in cells:
            if len(row) < 12 or not row[5]:
                continue
            year = str(row[0] if row[0] else year)
            if year != "2025":
                raise ValueError(f"Unexpected research funding reference year: {year}")
            sources = [number(value) for value in row[10:12]]
            value = sum(sources) if None not in sources else ""
            rows.append((row[5], "연구비 지원 계", value, "천원", year, "", "", row[3], source))
    finally:
        book.close()
    rows.sort(key=lambda row: (row[2] == "", -row[2] if row[2] != "" else 0, row[0]))
    write("university_research_funding.csv", POINT_FIELDS, rows)


def mine_locations(archive):
    sources = sorted(k for k in archive.entries if k.startswith("komir-mine-grid-"))
    if not sources:
        raise ValueError("Collect the mine grid first")
    rows = []
    ids = set()
    for source in sources:
        result = json.loads(source_path(archive, source).read_bytes())
        for fid, name, status, _, _, ore, _, address, _ in result["data"]:
            if fid in ids:
                raise ValueError(f"Duplicated mine grid entry: {fid}")
            ids.add(fid)
            if status == "가행":
                rows.append((name, f"가행광산·{ore}" if ore else "가행광산", "", "", "", "", "", address, source))
    if len(ids) != result["recordsTotal"]:
        raise ValueError("Incomplete mine grid")
    write("active_mines.csv", POINT_FIELDS, rows)


def heritage_components(archive):
    single_sites = {
        "khs-haeinsa": "합천", "khs-jongmyo": "서울", "khs-changdeokgung": "서울",
        "khs-hwaseong": "수원", "khs-namhansanseong": "경기도",
    }
    expected = (5, 3, 3, 40, 2, 8, 7, 9, 4, 7, 2, 2, 1, 1, 1, 1, 1)
    counts = dict(zip(HERITAGE_PAGES, expected, strict=True))
    rows = []
    index = source_path(archive, "khs-world-heritage-index")
    years = heritage_years(index.read_bytes())
    for source, (url, kind) in HERITAGE_PAGES.items():
        page = BeautifulSoup(source_path(archive, source).read_bytes(), "html.parser")
        paragraphs = [node.get_text(" ", strip=True) for node in page.select("p")]
        text = page.get_text(" ", strip=True)
        related = [link.get_text(" ", strip=True) for link in page.select("a") if "바로가기" in link.get_text()]
        parts = []
        if source == "khs-tombs":
            table = next(table for table in page.select("table") if "조선왕릉 일람표" in table.caption.get_text())
            for row in table.select("tbody tr"):
                cells = row.select("td,th")
                if len(cells) == 4:
                    place = cells.pop(0).get_text(" ", strip=True)
                parts.append((cells[0].get_text(" ", strip=True), place))
        elif source == "khs-gyeongju":
            parts = [(tag.get_text(strip=True), "경주") for tag in page.select("h4")
                     if tag.get_text(strip=True).endswith("지구") and tag.get_text(strip=True) != kind]
        elif source == "khs-dolmens":
            names = [tag.get_text(strip=True) for tag in page.select("h5") if tag.get_text(strip=True).endswith("고인돌유적")]
            places = [re.match(r"(전라북도 고창군|전라남도 화순군|인천광역시 강화군)\b", p)
                      for p in paragraphs]
            parts = list(zip(names, (place[1] for place in places if place), strict=True))
        elif source == "khs-jeju-volcanic":
            intro = next(p for p in paragraphs if p.startswith("세계유산으로 지정된 지역은"))
            names = re.search(r"지역은 (.+?) 등 \d+개", intro)[1].split(", ")
            parts = [(name, "제주도") for name in names]
        elif source == "khs-historic-villages":
            for city, name in (("안동", "하회마을"), ("경주", "양동마을")):
                if name not in text:
                    raise ValueError(f"Missing historic village: {name}")
                parts.append((name, city))
        elif source == "khs-baekje":
            intro = next(p for p in paragraphs if "백제 후기" in p and "구성된 연속유산" in p)
            names = re.sub(r"「[^」]+」\s*(?:는)?\s*", "", intro.split("유산으로 ", 1)[1])
            names = names.replace("과 익산 ", ", 익산 ")
            parts = [(name.strip(), name.strip().split()[0])
                     for name in names.split("로 구성된", 1)[0].split(",")]
        elif source == "khs-sansa":
            intro = next(p for p in paragraphs if "승원-" in p)
            names = re.search(r"승원-([^-]+)-", intro)[1].split(",")
            for name in map(str.strip, names):
                label = next(item for item in related if f" {name}" in item)
                address = re.search(r"([가-힣]+) " + name, label)[1]
                parts.append((name, address))
        elif source == "khs-seowon":
            intro = next(p for p in paragraphs if "서원으로 구성되어" in p)
            names = intro.split(" 등", 1)[0].split(", ")
            for name in names:
                label_name = "옥산사원" if name == "옥산서원" else name
                label = next(item for item in related if f" {label_name} " in item)
                parts.append((name, re.search(r"([가-힣]+) " + label_name, label)[1]))
        elif source == "khs-tidal-flats":
            intro = next(p for p in paragraphs if "개 구성요소로 이루어져 있다" in p)
            names = re.search(r"위치하고 있으며, (.*?갯벌)의 \d+개", intro)[1].split(", ")
            parts = [(name, name.removesuffix("갯벌")) for name in names]
        elif source == "khs-gaya":
            parts = [(label.removeprefix("사적 ").removesuffix(" 바로가기"), label.split()[1])
                     for label in related if "고분군 바로가기" in label and label.startswith("사적 ")]
        elif source == "khs-bangucheon":
            parts = [(label.removeprefix("국보 ").removesuffix(" 바로가기"), "울주")
                     for label in related if label.startswith("국보 울주 ") and "암각화 바로가기" in label]
        elif source == "khs-seokguram-bulguksa":
            kind = "석굴암·불국사"
            parts = [(name, "경주") for name in ("석굴암", "불국사") if name in text]
        elif source in single_sites:
            locality = single_sites[source]
            if kind not in text:
                raise ValueError(f"Missing World Heritage site: {kind}")
            parts = [(kind, locality if locality in text else "")]
        if len(parts) != counts[source]:
            raise ValueError(f"Unexpected heritage component count: {source}, {parts}")
        year = heritage_year(source, url, years)
        rows.extend((name, kind, "", "", year, "", "", address, source) for name, address in parts)
    write("world_heritage_components.csv", POINT_FIELDS, rows)


def main():
    normalizers = {"trade": trade, "road": road, "park": park, "dam": dam, "hanwoo": hanwoo,
                   "pigs": pig_sido, "mines": mine_locations, "heritage": heritage_components,
                   "institutions": institutions, "funding": university_funding}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groups", nargs="*", metavar="GROUP")
    args = parser.parse_args()
    groups = args.groups or list(normalizers)
    if set(groups) - normalizers.keys():
        parser.error("Groups: " + ", ".join(normalizers))
    archive = LayerArchive()
    for group in groups:
        normalizers[group](archive)


if __name__ == "__main__":
    main()
