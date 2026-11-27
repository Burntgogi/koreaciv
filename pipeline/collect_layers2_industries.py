"""Normalize published six manufacturing divisions and a 2020 national comparison."""

import csv
import io
import re
import site
import sys
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

if __name__ == "__main__" and __package__ is None:
    sys.path.extend([str(Path(__file__).resolve().parent), site.getusersitepackages()])

from collect_econ_normalize import FIELDS, Regions, coded, number, read_text
from collect_layers2 import LayerArchive, ROOT
from collect_layers2_normalize import source_path, write
from collect_layers_normalize import workbook_rows

CENSUS = "kosis-101-DT_2KI2010_11"
PROVINCES = dict(zip(
    ("11", "21", "22", "23", "24", "25", "26", "29", "31", "32", "33", "34", "35", "36", "37", "38", "39"),
    ("서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북",
     "전남", "경북", "경남", "제주"),
))
PATTERNS = {
    "19": r"코크스.*석유정제품", "20": r"화학물질.*화학제품", "24": r"1차금속",
    "26": r"전자부품.*컴퓨터.*통신장비", "30": r"자동차.*트레일러", "31": r"기타운송장비",
}


def classification(label):
    text = re.sub(r"[^가-힣0-9]", "", label)
    return next((code for code, pattern in PATTERNS.items() if re.search(pattern, text)), "")


def stat(regions, code, name, province, year, industry, value, basis, source):
    current, province, _ = regions.resolve(name, province)
    parsed = number(value)
    return (code, name, current, province, year, "establishment_workers",
            industry, parsed if parsed is not None else "", "명", basis, source)


def census(archive, regions):
    reader = csv.reader(read_text(source_path(archive, CENSUS)).splitlines())
    time, items = next(reader), next(reader)
    if time[-1] != "5Y2020 2020" or items[-1] != "T20 종사자수":
        raise ValueError("Unexpected 2020 census export")
    places, labels, rows = {}, {}, []
    for raw_place, raw_industry, value in reader:
        raw_code, name = coded(raw_place)
        industry_code, label = coded(raw_industry)
        if raw_code[:2] not in PROVINCES or industry_code not in PATTERNS:
            raise ValueError(f"Unexpected census category: {raw_place}, {raw_industry}")
        places[raw_code] = name
        labels[industry_code] = label
        rows.append(stat(regions, raw_code, name, PROVINCES[raw_code[:2]], 2020,
                         f"C{industry_code} {label}", value, "사업장·2020 경제총조사", CENSUS))
    return rows, places, labels


def regional_kosis(archive, regions, source, entry, labels):
    records = list(csv.reader(read_text(source_path(archive, source)).splitlines()))
    periods = records[0]
    first = next(i for i, item in enumerate(periods) if re.match(r"Y\d{4} ", item))
    header_count = 1
    while header_count < len(records) and records[header_count][:first] == periods[:first]:
        header_count += 1
    headers = records[1:header_count]
    province = entry["publisher"]
    results = {}
    for row in records[header_count:]:
        if len(row) != len(periods):
            raise ValueError(f"Malformed regional KOSIS CSV: {source}")
        for col in range(first, len(periods)):
            year = periods[col][1:5]
            if year != "2024":
                continue
            dims = list(map(coded, [*row[:first], *(header[col] for header in headers)]))
            if not any(label.startswith("종사자수") for _, label in dims):
                continue
            industry = [ic for raw, label in dims if (ic := classification(label))
                        and not re.search(r"C[0-9]{3,}$", raw)]
            if len(set(industry)) != 1 or any(re.search(r"C[0-9]{3,}$", raw) for raw, _ in dims):
                continue
            place = [(raw, label) for raw, label in dims
                     if label.endswith(("시", "군", "구")) and label != province
                     and not classification(label)]
            if len(place) != 1:
                continue
            code, name = place[0]
            key = (code, name, industry[0])
            result = stat(regions, code, name, province, 2024, f"C{industry[0]} {labels[industry[0]]}",
                          row[col], "사업장·전국사업체조사·등록기반", source)
            if key in results and results[key] != result:
                raise ValueError(f"Conflicting regional employment cells: {source}, {key}")
            results[key] = result
    return list(results.values())


def incheon(archive, regions, labels):
    source = "incheon-manufacturing-2022"
    rows = []
    for row in csv.DictReader(read_text(source_path(archive, source)).splitlines()):
        industry = classification(row["제조업중분류별"])
        if industry:
            rows.append(stat(regions, "", row["군구별"], "인천", 2022, f"C{industry} {labels[industry]}",
                             row["종사자수 (명)"], "사업장·인천 제조업 공표표", source))
    return rows


def seoul(archive, regions, places, labels):
    source = "seoul-business-census-2024"
    counts = defaultdict(int)
    missing = set()
    with ZipFile(source_path(archive, source)) as package:
        member, = [info for info in package.infolist() if info.filename.endswith(".csv")]
        if member.file_size > 100_000_000:
            raise ValueError("Unexpected size of the Seoul establishment CSV")
        with package.open(member) as stream:
            for row in csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")):
                if row["INDST_LCLS_CD"] != "C":
                    continue
                industry = row["MBZ_INDST_DIV_CD"][:2]
                if industry not in PATTERNS:
                    continue
                if row["SURV_BASE_YEAR"] != "2024":
                    raise ValueError("Unexpected Seoul establishment year")
                district = row["AD_CD"][:5]
                if district not in places or not district.startswith("11"):
                    raise ValueError(f"Unknown Seoul district: {district}")
                key = district, industry
                workers = number(row["SURV_PHS_WOKE_SUM"])
                if workers is None:
                    missing.add(key)
                elif workers < 0 or workers != int(workers):
                    raise ValueError(f"Invalid Seoul establishment workers: {district}")
                else:
                    counts[key] += int(workers)
    return [
        stat(regions, code, places[code], "서울", 2024, f"C{industry} {labels[industry]}",
             "" if (code, industry) in missing else counts[code, industry],
             "사업장·서울시 2024 사업체조사 원자료 구별 합계", source)
        for code, industry in sorted(counts.keys() | missing)
    ]


def gyeongbuk(archive, regions, labels):
    from openpyxl import load_workbook

    source = "gyeongbuk-business-2024"
    book = load_workbook(source_path(archive, source), read_only=True, data_only=True, keep_links=False)
    try:
        sheet, = book.worksheets
        records = iter(sheet.values)
        if next(records)[:5][1:] != ("행정구역 명칭", "산업분류명칭", "총사업체수", "총종사자수"):
            raise ValueError("Unexpected Gyeongbuk business survey headings")
        rows = []
        for record in records:
            key = re.fullmatch(r"(37\d{3})C(19|20|24|26|30|31)", str(record[0]))
            if key:
                code, industry = key.groups()
                rows.append(stat(regions, code, record[1], "경북", 2024, f"C{industry} {labels[industry]}",
                                 record[4], "사업장·전국사업체조사·총종사자수", source))
    finally:
        book.close()
    if len(rows) != 6 * len({row[0] for row in rows}):
        raise ValueError("Missing or duplicate Gyeongbuk manufacturing cells")
    return rows


def sejong(archive, regions, labels):
    source = "sejong-business-2024"
    with workbook_rows(source_path(archive, source)) as sheets:
        sheet, = sheets
        _, vintage, headings, items = (next(sheet) for _ in range(4))
        if ("2024 기준년도" not in vintage[0] or headings[4] != "세종특별자치시"
                or not items[5].startswith("종사자수")):
            raise ValueError("Unexpected Sejong business survey headings")
        rows = []
        city_total_page = True
        for record in sheet:
            if str(record[0]).startswith("산업분류"):
                city_total_page = record[4] == "세종특별자치시"
            industry = str(record[1])
            if city_total_page and industry in PATTERNS and str(record[2]) == "**":
                rows.append(stat(regions, "", "세종특별자치시", "세종", 2024,
                                 f"C{industry} {labels[industry]}", record[5],
                                 "사업장·전국사업체조사·표 2 세종 소계", source))
                if len(rows) == len(PATTERNS):
                    break
    if len({row[6] for row in rows}) != len(PATTERNS):
        raise ValueError("Missing Sejong manufacturing cells")
    return rows


def chungnam(archive, regions, labels):
    import pymupdf

    source = "chungnam-business-2024"
    data = {}
    counts = r"(?:\d[\d,]*|X|-)"
    place = r"[가-힣]{2,}(?:시|군|도)"
    with pymupdf.open(source_path(archive, source)) as document:
        for i in (307, 309, 311, 313, 315, 317):
            left, right = document[i], document[i + 1]
            headings = []
            for page, size in ((left, 3), (right, 5)):
                listing = re.search(r"^\s*(" + place + (r"\s+" + place) * (size - 1) + r")\s*$",
                                    "\n".join(page.get_text(sort=True).splitlines()[:12]), re.M)
                headings.append(listing[1].split())
            left_text = left.get_text(sort=True)
            right_words = sorted(right.get_text("words"))
            for x, y, _, _, word, *_ in left.get_text("words"):
                match = re.match(r"^(19|20|24|26|30|31)\.", word)
                if x >= 90 or not match:
                    continue
                industry = match[1]
                left_line = next(line for line in left_text.splitlines()
                                 if line.lstrip().startswith(f"{industry}."))
                left_cells = re.search(r"(" + counts + (r"\s+" + counts) * 5 + r")\s*$", left_line)[1].split()
                right_cells = [w[4] for w in right_words if abs(w[1] - y) < 2 and re.fullmatch(counts, w[4])]
                if len(right_cells) != 10:
                    raise ValueError(f"Unexpected Chungnam right-hand table row: {i}, {industry}")
                for name, value in zip(headings[0] + headings[1], left_cells[1::2] + right_cells[1::2], strict=True):
                    if (industry, name) in data:
                        raise ValueError(f"Duplicate Chungnam table cell: {name}, {industry}")
                    data[industry, name] = value
    rows = []
    for industry in PATTERNS:
        total = number(data.pop((industry, "충청남도")))
        values = [(name, value) for (code, name), value in data.items() if code == industry]
        if len(values) != 15 or any(number(value) is None for _, value in values):
            raise ValueError(f"Missing Chungnam territory or value: {industry}")
        if sum(number(value) for _, value in values) != total:
            raise ValueError(f"Chungnam municipal values do not match province total: {industry}")
        rows.extend(stat(regions, "", name, "충남", 2024, f"C{industry} {labels[industry]}",
                         value, "사업장·전국사업체조사·충남 공표본 표 2", source)
                    for name, value in values)
    return rows


def main():
    archive = LayerArchive()
    regions = Regions()
    comparison, places, labels = census(archive, regions)
    write("key_industries_2020.csv", FIELDS, comparison)
    # Retain the five provinces' existing 2024 observations and augment with new releases.
    old_path = ROOT / "data/build/layers/key_industries.csv"
    reader = csv.reader(read_text(old_path).splitlines())
    if tuple(next(reader)) != FIELDS:
        raise ValueError("Unexpected fourth-pass industry output")
    rows = [row for row in reader if row[6].split()[0][1:] in PATTERNS]
    for source, entry in sorted(archive.entries.items()):
        if source.startswith("kosis-") and source != CENSUS:
            extra = regional_kosis(archive, regions, source, entry, labels)
            print(f"{source}: {len(extra):,} 2024 observations")
            rows.extend(extra)
    if archive.has("incheon-manufacturing-2022"):
        rows.extend(incheon(archive, regions, labels))
    if archive.has("seoul-business-census-2024"):
        rows.extend(seoul(archive, regions, places, labels))
    for source, normalizer in (
        ("gyeongbuk-business-2024", gyeongbuk), ("sejong-business-2024", sejong),
        ("chungnam-business-2024", chungnam),
    ):
        if archive.has(source):
            region_rows = normalizer(archive, regions, labels)
            rows.extend(region_rows)
            print(f"{source}: {len(region_rows):,} 2024 observations")
    write("key_industries_all.csv", FIELDS, rows)


if __name__ == "__main__":
    main()
