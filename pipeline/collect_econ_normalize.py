"""Normalize archived economic statistics without distributing older city totals."""
import argparse
import csv
import io
import json
import re
import time
import zipfile
from collections import defaultdict
from contextlib import ExitStack
from decimal import Decimal, InvalidOperation
from statistics import median
from pathlib import Path
from tempfile import NamedTemporaryFile

from collect_econ import RAW, ROOT

FIELDS = ("sgg_code_raw", "sgg_name_raw", "sgg_code_now", "sido_now", "year",
          "indicator", "industry", "value", "unit", "basis", "source_id")
OUT = ROOT / "data/build/econ"
PROVINCES = {
    "서울특별시": ["서울"], "부산광역시": ["부산"], "대구광역시": ["대구"],
    "인천광역시": ["인천"], "대전광역시": ["대전"], "울산광역시": ["울산"],
    "세종특별자치시": ["세종", "세종시"], "경기도": ["경기"],
    "강원특별자치도": ["강원도", "강원"], "충청북도": ["충북"], "충청남도": ["충남"],
    "전북특별자치도": ["전라북도", "전북"], "경상북도": ["경북"], "경상남도": ["경남"],
    "제주특별자치도": ["제주도", "제주"],
    "전남광주통합특별시": ["전라남도", "전남", "광주광역시", "광주", "전남광주"],
}
MAJOR_CITIES = {"서울특별시", "부산광역시", "대구광역시", "인천광역시",
                "대전광역시", "울산광역시"}


def clean(label):
    return re.sub(r"\s+", "", label.strip())


def read_text(path):
    content = path.read_bytes()
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Unknown encoding: {path}")


def write_csv(path, rows):
    with NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent,
                            prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
        pending = Path(stream.name)
        try:
            writer = csv.writer(stream)
            writer.writerow(FIELDS)
            writer.writerows(rows)
            stream.close()
            for attempt in range(10):
                try:
                    pending.replace(path)
                    return
                except PermissionError:
                    if attempt == 9:
                        raise
                    time.sleep(0.5)
        finally:
            stream.close()
            pending.unlink(missing_ok=True)


class Regions:
    def __init__(self):
        path = ROOT / "data/raw/boundary/HangJeongDong_ver20261001.geojson"
        features = json.loads(path.read_text(encoding="utf-8"))["features"]
        self.by_code = {p["sgg"]: (p["sidonm"], p["sggnm"])
                        for f in features if (p := f["properties"])["sgg"]}
        self.aliases = {alias: province for province, aliases in PROVINCES.items()
                        for alias in [province, *aliases]}
        self.by_name = defaultdict(set)
        self.city_members = defaultdict(set)
        self.city_only = {}
        for code, (province, name) in self.by_code.items():
            self.by_name[clean(name)].add((province, code))
            city = self.city(province, name)
            self.city_members[city].add(code)
            if (district := re.fullmatch(r"(.+시)(.+구)", clean(name))):
                self.city_only[(province, district[1])] = city
                self.by_name[district[2]].add((province, code))
        self.cities = set(self.city_members)

    @staticmethod
    def city(province, name):
        name = clean(name)
        if name.endswith("구") and (province in MAJOR_CITIES or province == "전남광주통합특별시"):
            return province, "광주" if province == "전남광주통합특별시" else province
        if district := re.fullmatch(r"(.+시).+구", name):
            return province, district[1]
        return province, name

    def split(self, label):
        name = clean(label)
        if name in self.by_name and name != "세종시":
            return "", name
        for prefix in sorted(self.aliases, key=len, reverse=True):
            if name.startswith(prefix):
                tail = name[len(prefix):]
                if tail or prefix in {"세종", "세종시", "세종특별자치시"}:
                    if self.aliases[prefix] == "세종특별자치시" and tail in {"", "세종시", "세종특별자치시"}:
                        tail = "세종시"
                    return self.aliases[prefix], tail
        return "", name

    def resolve(self, name, province="", code=""):
        if name == "미추홀구(남구)":
            name = "미추홀구"
        explicit, name = self.split(name)
        province = explicit or self.aliases.get(clean(province), province)
        if name == "남구" and province == "인천광역시":
            name = "미추홀구"
        if name == "군위군" and province == "경상북도":
            province = "대구광역시"
        if name == "세종시":
            province = "세종특별자치시"
        if code in self.by_code and (p := self.by_code[code])[1] == name and p[0] == (province or p[0]):
            return code, p[0], self.city(*p)
        candidates = [(p, c) for p, c in self.by_name[name] if not province or p == province]
        if len(candidates) == 1:
            p, c = candidates[0]
            return c, p, self.city(*self.by_code[c])
        if province:
            city = self.city_only.get((province, name))
            return "", province, city
        cities = [city for (p, city_name), city in self.city_only.items() if city_name == name]
        return ("", cities[0][0], cities[0]) if len(cities) == 1 else ("", "", None)

    def location(self, address):
        parts = address.split()
        if len(parts) < 2:
            return address
        if len(parts) > 2 and parts[1].endswith("시") and parts[2].endswith("구"):
            return " ".join(parts[:3])
        if parts[0] == "세종특별자치시":
            return parts[0]
        return " ".join(parts[:2])


def number(value):
    try:
        result = Decimal(str(value).strip().replace(",", ""))
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


class Output:
    def __init__(self, regions):
        self.regions = regions
        self.rows = defaultdict(list)
        self.direct = defaultdict(set)
        self.city_totals = defaultdict(set)
        self.unmapped = defaultdict(set)
        self.by_source = defaultdict(set)

    def add(self, group, source, code, name, year, indicator, value, unit, basis,
            province="", industry=""):
        district, province, city = self.regions.resolve(name, province, code)
        if not city:
            self.unmapped[source].add((code, name, province))
        numeric = number(value)
        row = (code, name, district, province, year, indicator, industry,
               "" if numeric is None else numeric, unit, basis, source)
        self.rows[group].append(row)
        if numeric is not None and city:
            key = (group, indicator, str(year))
            source_key = (source, indicator, str(year))
            if district:
                self.direct[key].add(district)
                self.by_source[source_key].add(district)
            else:
                self.city_totals[key].add(city)

    def write(self):
        OUT.mkdir(parents=True, exist_ok=True)
        for group, rows in sorted(self.rows.items()):
            write_csv(OUT / f"{group}.csv", rows)
            print(f"{group}: {len(rows):,} observations")
        for key in sorted(self.direct.keys() | self.city_totals.keys()):
            districts = self.direct[key]
            cities = self.city_totals[key] | {
                city for city, members in self.regions.city_members.items() if members <= districts
            }
            provinces = {self.regions.by_code[code][0] for code in districts} | {city[0] for city in cities}
            print("/".join(key), f"{len(districts)}/{len(self.regions.by_code)} districts",
                  f"{len(cities)}/{len(self.regions.cities)} cities", ", ".join(sorted(provinces)))
        write_csv(OUT / "unmapped.csv", (
            (code, name, "", province, "", "", "", "", "", "", source)
            for source, entries in sorted(self.unmapped.items())
            for code, name, province in sorted(entries)
        ))


def housing(out, source, entry):
    data = io.StringIO(read_text(RAW / entry["file"]))
    for line in data:
        if line.startswith('"NO","시군구"'):
            data.seek(data.tell() - len(line))
            break
    else:
        raise ValueError(f"Transaction CSV has no header: {source}")
    sales = entry["deal"] == "sale"
    values = defaultdict(list)
    for row in csv.DictReader(data):
        if row["계약년월"] != entry["vintage"].replace("-", ""):
            raise ValueError(f"Wrong contract month in {source}")
        name = out.regions.location(row["시군구"])
        if sales:
            if row["해제사유발생일"].strip() not in {"", "-"}:
                continue
            amount = number(row["거래금액(만원)"])
            area = number(row["전용면적(㎡)"])
            if amount is not None and area and area > 0:
                values[name, "apartment_sale_median_per_m2", "만원/㎡"].append(amount / area)
                values[name, "apartment_sale_median", "만원"].append(amount)
        else:
            deposit = number(row["보증금(만원)"])
            rent = number(row["월세금(만원)"])
            if deposit is None or rent is None:
                continue
            if rent == 0:
                values[name, "apartment_jeonse_median", "만원"].append(deposit)
            else:
                values[name, "apartment_monthly_rent_median", "만원/월"].append(rent)
                values[name, "apartment_monthly_deposit_median", "만원"].append(deposit)
    for (name, indicator, unit), observations in sorted(values.items()):
        out.add("housing", source, "", name, entry["vintage"][:4], indicator,
                median(observations).quantize(Decimal("0.0001")), unit, "주소지")


def legacy(out, source, entry):
    group = entry["file"].split("/")[0]
    with io.StringIO(read_text(RAW / entry["file"])) as data:
        for row in csv.DictReader(data):
            if source == "15132649":
                out.add(group, source, row["시군구코드"], row["군구명"], entry["vintage"],
                        "total_fertility_rate", row["출산율"], "명/여성", "거주지", "인천광역시")
            elif row["기관코드"] != "43000":
                for indicator, value in (("fiscal_independence_final", row["재정자립도_최종"]),
                                         ("fiscal_autonomy_initial", row["재정자주도_당초"])):
                    out.add(group, source, row["기관코드"], row["기관명"], row["회계연도"],
                            indicator, value, "%", "주소지", "충청북도")


def coded(value):
    code, sep, label = value.strip().partition(" ")
    if sep and re.fullmatch(r"[A-Za-z0-9_+.\-]+", code):
        return code, label.lstrip()
    return "", value.strip()


KSIC_NAMES = (
    "농업, 임업 및 어업", "광업", "제조업", "전기, 가스, 증기 및 공기조절 공급업",
    "수도, 하수 및 폐기물 처리, 원료 재생업", "건설업", "도매 및 소매업", "운수 및 창고업",
    "숙박 및 음식점업", "정보통신업", "금융 및 보험업", "부동산업", "전문, 과학 및 기술 서비스업",
    "사업시설 관리, 사업 지원 및 임대 서비스업", "공공행정, 국방 및 사회보장 행정", "교육 서비스업",
    "보건업 및 사회복지 서비스업", "예술, 스포츠 및 여가관련 서비스업",
    "협회 및 단체, 수리 및 기타 개인 서비스업",
)
BUSINESS_COUNTS = {
    "사업체": ("establishments", "개"),
    "사업체수": ("establishments", "개"),
    "종사자": ("establishment_workers", "명"),
    "종사자수": ("establishment_workers", "명"),
}


def business_industry(value):
    code, title = coded(value)
    if code in "ABCDEFGHIJKLMNOPQRS" and len(code) == 1:
        return f"{code} {KSIC_NAMES[ord(code) - ord('A')]}"
    key = re.sub(r"[^가-힣]", "", title)
    if key in {"계", "합계", "전체", "전산업", "전체산업"}:
        return "합계"
    if key == "사업시설관리지원및임대서비스업":
        return "N " + KSIC_NAMES[13]
    for letter, label in zip("ABCDEFGHIJKLMNOPQRS", KSIC_NAMES, strict=True):
        if key == re.sub(r"[^가-힣]", "", label):
            return f"{letter} {label}"
    return ""


def local_business(out, source, entry, table, period_start, header_count):
    names = [coded(cell)[1] for cell in table[0][:period_start]]
    location = [i for i, name in enumerate(names) if re.search(r"행정구역|시[·ㆍ]?군|[구군][·ㆍ]?[군구]|지역", name)]
    activity = [i for i, name in enumerate(names) if "산업" in name]
    metrics = [i for i, name in enumerate(names) if "항목" in name]
    columns = []
    for i in range(period_start, len(table[0])):
        year = re.search(r"Y(\d{4})", table[0][i])
        if year is None:
            raise ValueError(f"{source}: unexpected period {table[0][i]}")
        headers = [row[i] for row in table[1:header_count] if len(row) == len(table[0])]
        columns.append((i, year[1], headers))
    def district(labels):
        for value in labels:
            code, name = coded(value)
            title = clean(name)
            if title not in out.regions.aliases and re.search(r"[시군구]$", title):
                return code, name
        return "", ""

    seen = set()
    for row in table[header_count:]:
        if len(row) != len(table[0]):
            continue
        for i, year, headers in columns:
            code, name = district([row[j] for j in reversed(location)] if location else headers)
            if not name:
                continue
            industry_values = [row[j] for j in reversed(activity)] if activity else headers
            industry = next((label for value in industry_values if (label := business_industry(value))), "")
            if not industry:
                continue
            captions = [coded(value)[1] for value in [*headers, *(row[j] for j in metrics)]]
            if any(clean(label) in {"여성대표자", "여자", "남자", "여성", "남성", "여", "남"} for label in captions):
                continue
            indicator = next((BUSINESS_COUNTS[key] for label in captions
                              if (key := re.split(r"[(：:]", clean(label), maxsplit=1)[0]) in BUSINESS_COUNTS), None)
            if indicator is None:
                continue
            key = code, name, year, industry, indicator[0]
            if key in seen:
                raise ValueError(f"{source}: duplicate district/industry item {key}")
            seen.add(key)
            out.add("business", source, code, name, year, indicator[0], row[i], indicator[1],
                    "사업장", entry["publisher"], industry)
    if not seen:
        raise ValueError(f"{source}: no district business observations")


def regional_business_workbook(out, source, entry):
    path = RAW / entry["file"]
    extension = path.suffix
    maximum_size = 10 * 1024 * 1024
    if extension == ".zip":
        with zipfile.ZipFile(path) as archive:
            member, = (item for item in archive.infolist()
                       if re.match(r"(?:통계표\s*)?0?2[. _-]", Path(item.filename).name)
                       and item.filename.endswith((".xls", ".xlsx")))
            if not 0 < member.file_size <= maximum_size:
                raise ValueError(f"{source}: unexpected workbook size")
            extension = Path(member.filename).suffix
            content = archive.read(member)
    else:
        if not 0 < path.stat().st_size <= maximum_size:
            raise ValueError(f"{source}: unexpected workbook size")
        content = path.read_bytes()
    counts = {}
    year = entry["vintage"]
    with ExitStack() as cleanup:
        if extension == ".xls":
            import xlrd

            book = xlrd.open_workbook(file_contents=content, on_demand=True)
            cleanup.callback(book.release_resources)
            sheets = ((sheet.name, map(sheet.row_values, range(sheet.nrows))) for sheet in book.sheets())
        else:
            from openpyxl import load_workbook

            with zipfile.ZipFile(io.BytesIO(content)) as package:
                if sum(item.file_size for item in package.infolist()) > 64 * 1024 * 1024:
                    raise ValueError(f"{source}: XLSX contents exceed size limit")
            book = load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False)
            cleanup.callback(book.close)
            for sheet in book:
                sheet.reset_dimensions()
            sheets = ((sheet.title, iter(sheet.values)) for sheet in book)
        for sheet_name, rows in sheets:
            columns = {}
            year_verified = False
            for row in rows:
                if not row:
                    continue
                if any(f"{year} 기준년도" in str(cell) for cell in row):
                    year_verified = True
                if str(row[0]).startswith("산업분류"):
                    if not year_verified:
                        raise ValueError(f"{source}: missing reference year in {sheet_name}")
                    columns.clear()
                    region = ""
                    for i, (header, item) in enumerate(zip(row, next(rows, ()))):
                        if header:
                            region = str(header).splitlines()[0].strip()
                        label = str(item).partition("\n")[0].strip()
                        if label in BUSINESS_COUNTS and (region == entry["publisher"] or region.endswith(("시", "군", "구"))):
                            columns[i] = (region, BUSINESS_COUNTS[label])
                    continue
                letter = str(row[0]).strip()
                if re.fullmatch(r"[A-S]", letter) and any(
                    str(cell).strip().startswith(letter + ".") for cell in row[:6]
                ):
                    industry = f"{letter} {KSIC_NAMES[ord(letter) - ord('A')]}"
                elif any(str(cell).strip().startswith("TT 전체산업") for cell in row[:6]):
                    industry = "합계"
                else:
                    continue
                for col, (region, (indicator, unit)) in columns.items():
                    key = region, industry, indicator, unit
                    value = number(row[col]) if col < len(row) else None
                    if value is not None and value != value.to_integral_value():
                        raise ValueError(f"{source}: count is not an integer at {key}")
                    value = int(value) if value is not None else None
                    if key in counts and counts[key] != value:
                        raise ValueError(f"{source}: inconsistent repeated workbook cell {key}")
                    counts[key] = value

    province = entry["publisher"]
    districts = {region for region, _, _, _ in counts if region != province}
    if not districts:
        raise ValueError(f"{source}: no district cells in workbook")
    sections = {"합계", *(f"{letter} {name}" for letter, name in zip("ABCDEFGHIJKLMNOPQRS", KSIC_NAMES))}
    for indicator, unit in set(BUSINESS_COUNTS.values()):
        regional_total = counts[(province, "합계", indicator, unit)]
        if sum(counts[(region, "합계", indicator, unit)] for region in districts) != regional_total:
            raise ValueError(f"{source}: district {indicator} totals differ from the published province total")
        for region in sorted(districts):
            if any((region, section, indicator, unit) not in counts for section in sections):
                raise ValueError(f"{source}: incomplete industry headings for {region}")
    for (region, industry, indicator, unit), value in counts.items():
        if region in districts:
            out.add("business", source, "", region, year, indicator, value, unit, "사업장", province, industry)


def kosis(out, source, entry):
    group = entry["file"].split("/")[0]
    table_id = entry["table_id"]
    table = list(csv.reader(io.StringIO(read_text(RAW / entry["file"]))))
    period_start = next((i for i, value in enumerate(table[0])
                         if re.fullmatch(r"\d*[YHMQ]\d{4,6} .+", value)), None)
    if period_start is None:
        print(f"{source}: unsupported CSV header")
        return
    periods = table[0][period_start:]
    names = [coded(cell)[1] for cell in table[0][:period_start]]
    header_count = next((i for i, row in enumerate(table[1:], 1) if row[0] != table[0][0]), len(table))
    if group == "business" and entry["org_id"] != "101":
        local_business(out, source, entry, table, period_start, header_count)
        return
    headers = table[1:header_count]
    codes = [coded(cell) for cell in headers[0][period_start:]] if headers else [("", "")] * len(periods)
    try:
        geography = next(i for i, name in enumerate(names)
                         if any(x in name for x in ("시군", "시·군", "구군", "자치구", "행정구역", "시도",
                                                    "지역별", "거주지")) or name.startswith("동별"))
    except StopIteration:
        print(f"{source}: no geographic row dimension")
        return
    industry = next((i for i, x in enumerate(names) if "경제활동" in x or "산업" in x), None)
    simple = {
        "employment": {"T7": ("employment_rate", "%"), "T8": ("unemployment_rate", "%")},
        "fertility": {"T2": ("total_fertility_rate", "명/여성"), "T1": ("births", "명")},
        "land": {"T10": ("cultivated_area", "ha"), "T20": ("paddy_area", "ha"),
                 "T30": ("upland_area", "ha")},
        "migration": {"T10": ("in_migration", "명"), "T20": ("out_migration", "명"),
                      "T25": ("net_migration", "명")},
        "tenure": {"T10": ("general_households", "가구"), "T11": ("owner_occupied_households", "가구")},
    }
    agriculture_trend = {
        "DT_1NG0001": {"T20": ("personal_farm_households", "가구"),
                      "T30": ("personal_farm_population", "명")},
        "DT_1FS000": {"T00": ("marine_fishing_households", "가구"),
                    "T01": ("marine_fishing_population", "명")},
        "DT_1FI000": {"T00": ("inland_fishing_households", "가구"),
                    "T01": ("inland_fishing_population", "명")},
    }
    totals = {"계", "소계", "합계", "전체", "전체산업", "총계", "일반가구"}
    agriculture = {
        "DT_1AG20103": ("농가", "farm_households", "가구"),
        "DT_1AG20201": ("농가인구", "farm_population", "명"),
        "DT_1FO20103": ("임가", "forestry_households", "가구"),
        "DT_1FO20112": ("임가인구", "forestry_population", "명"),
        "DT_1FS20102": ("어가", "marine_fishing_households", "가구"),
        "DT_1FS20202": ("어가인구", "marine_fishing_population", "명"),
        "DT_1FI20102": ("어가", "inland_fishing_households", "가구"),
        "DT_1FI20202": ("어가인구", "inland_fishing_population", "명"),
    }
    e_local = {
        "DT_1YL5701": ("establishments", "개", "B", "C 제조업"),
        "DT_1YL5702": ("establishments", "개", "B", "C 제조업"),
        "DT_1YL5801": ("establishment_workers", "명", "B", "C 제조업"),
        "DT_1YL5802": ("establishment_workers", "명", "B", "C 제조업"),
        "DT_1YL20831": ("establishments", "개", "B", "합계"),
        "DT_1YL20832": ("establishments", "개", "B", "합계"),
        "DT_1YL15012": ("establishment_workers", "명", "B", "합계"),
        "DT_1YL15014": ("establishment_workers", "명", "B", "합계"),
        "DT_1YL20921": ("fiscal_independence", "%", "F", ""),
        "DT_1YL20981": ("medical_doctors_per_1000", "명/천명", "M", ""),  # 감사 06: 분자는 의료기관 소재지별 종사 의사
        "DT_1YL13801E": ("livelihood_guarantee_recipients", "명", "R", ""),
        "DT_1YL21161": ("one_person_household_share", "%", "R", ""),
    }
    basis_names = {"B": "사업장", "F": "주소지", "R": "거주지", "M": "의료기관 소재지 종사 의사 ÷ 같은 지역 주민등록인구"}
    current_province = ""
    education = defaultdict(lambda: defaultdict(dict))
    for row in table[header_count:]:
        if len(row) != len(table[0]):
            continue
        region_code, name = coded(row[geography])
        province = current_province
        if group == "grdp":
            province = entry["publisher"]
        if group == "employment" and name == "고성군":
            province = {"3240": "강원특별자치도", "3834": "경상남도"}.get(region_code, "")
        if geography + 1 < period_start and names[geography + 1].endswith("(2)"):
            if name in {"세종", "세종특별자치시"} and coded(row[geography + 1])[1] == "소계":
                province = name
            else:
                province, (region_code, name) = name, coded(row[geography + 1])
            if geography + 2 < period_start and names[geography + 2].endswith("(3)"):
                district_code, district_name = coded(row[geography + 2])
                if district_name not in totals:
                    region_code, name = district_code, district_name
        elif geography == 0 and clean(name) in out.regions.aliases:
            province = current_province = clean(name)
        if clean(name) in {"", "전국", "소계", "계", "합계", "시부", "군부", "동부", "읍부", "면부",
                           "미상", "국외", "기타", "본청", "기타시군구"}:
            continue
        if clean(name) in out.regions.aliases and clean(name) not in {"세종", "세종시", "세종특별자치시"}:
            continue
        if name == "서울시":
            continue
        if group == "land" and any(clean(name).startswith(prefix) for prefix in ("시지역", "군지역")):
            continue
        if (group == "tenure" and period_start > 1 and clean(coded(row[1])[1]) not in totals):
            continue
        if group == "religion" and any(clean(coded(row[i])[1]) not in totals for i in range(1, period_start)):
            continue
        for offset, ((item, caption), period) in enumerate(zip(codes, periods), period_start):
            period_code = period.split()[0]
            year = re.search(r"[YHMQ](\d{4})", period_code)[1]
            activity = ""
            if group == "grdp":
                if not any(x in clean(caption) for x in ("당해년가격", "명목", "당해연도가격")):
                    continue
                activity = coded(row[industry])[1] if industry is not None else ""
                if not activity:
                    continue
                indicator, unit, basis = "grdp_current", entry.get("unit", "백만원"), "생산지"
            elif group in simple:
                field = simple[group].get(item)
                if field is None or (group == "migration" and not period_code.startswith("Y")):
                    continue
                indicator, unit = field
                basis = "생산지" if group == "land" else "거주지"
            elif table_id in agriculture_trend:
                field = agriculture_trend[table_id].get(item)
                if field is None:
                    continue
                indicator, unit = field
                basis = "거주지"
            elif table_id in e_local:
                indicator, unit, basis_key, activity = e_local[table_id]
                basis = basis_names[basis_key]
                if table_id == "DT_1YL20921" and "개편후" not in clean(caption):
                    continue
                if table_id == "DT_1YL20981" and not clean(caption).startswith("인구천명당"):
                    continue
                if table_id == "DT_1YL15014" and item != "T001":
                    continue
                if table_id == "DT_1YL21161" and not clean(caption).startswith("1인가구비율"):
                    if item not in {"T001", "T002"}:
                        continue
                    indicator = "one_person_households" if item == "T001" else "general_households"
                    unit = "가구"
            elif group == "religion":
                unit, basis = "명", "거주지"
                indicator = {"T10": "census_population", "T20": "population_with_religion",
                             "T40": "population_without_religion"}.get(item, "religion_population")
                activity = caption if indicator == "religion_population" else ""
            elif group == "education":
                age_detail = table_id == "DT_1PM2501"
                if item not in {"T10", "T51", "T61", "T71", "T81"} or period_start != (3 if age_detail else 4):
                    continue
                age_label = clean(coded(row[2])[1])
                age = re.match(r"\d+", age_label)
                if not age and age_label not in totals:
                    continue
                if any(clean(coded(row[i])[1]) not in totals for i in ((1,) if age_detail else (1, 3))):
                    continue
                education[(region_code, name, province, year)][item][int(age[0]) if age else None] = number(row[offset])
                out.add(group, source, region_code, name, year, "education_population", row[offset], "명",
                        "거주지", province, f"{coded(row[2])[1]} / {caption}")
                continue
            elif group == "commute":
                duration_col = next((i for i, axis in enumerate(names) if "소요시간" in axis), None)
                if duration_col is None:
                    continue
                activity = coded(row[duration_col])[1]
                indicator, unit, basis = "commuter_population", "명", "거주지"
            elif table_id in agriculture:
                expected, indicator, unit = agriculture[table_id]
                if not re.fullmatch(rf"{expected}(?::계)?(?:\([^)]*\))?", clean(caption)):
                    continue
                if any(
                    clean(coded(row[i])[1]) not in (totals | {"연령계", "전연령", "전체연령"})
                    for i, axis in enumerate(names)
                    if any(word in axis for word in ("특성", "연령", "성별"))
                ):
                    continue
                basis = "거주지"
            elif group == "income":
                if item != "B02" or len(headers) != 2:
                    continue
                sub_item = coded(headers[1][offset])[0]
                if sub_item == "T001":
                    indicator, unit = "wage_tax_filers", "명"
                elif sub_item == "T002":
                    indicator, unit = "taxable_gross_wages", "백만원"
                    people, amount = number(row[offset - 1]), number(row[offset])
                    average = (amount * 100 / people).quantize(Decimal("0.01")) if people and amount is not None else None
                    out.add(group, source, region_code, name, year, "taxable_gross_wages_per_filer",
                            average, "만원/명", "주소지", province)
                else:
                    continue
                basis = "주소지"
            elif group == "business":
                if industry is None or period_start > 2:
                    continue
                industry_code, industry_name = coded(row[industry])
                if not re.fullmatch(r"[A-S]|0|00", industry_code):
                    continue
                if caption.startswith("사업체수"):
                    indicator, unit = "establishments", "개"
                elif caption.startswith("종사자수"):
                    indicator, unit = "establishment_workers", "명"
                else:
                    continue
                if table_id == "DT_2KI2010_11":
                    activity = business_industry(row[industry])
                else:
                    activity = f"{industry_code} {industry_name}" if industry_code not in {"0", "00"} else "합계"
                basis = "사업장"
            elif table_id == "DT_201004_O110034_2020":
                if tuple(coded(h[offset])[0] for h in headers) != ("001", "001003", ""):
                    continue
                if name not in {n for p, n in out.regions.by_code.values() if p == "서울특별시"}:
                    continue
                province = "서울특별시"
                indicator, unit, basis = "livelihood_guarantee_recipients", "명", "거주지"
            else:
                continue
            out.add(group, source, region_code, name, year, indicator, row[offset],
                    unit, basis, province, activity)
        if group == "tenure" and len(set(periods)) == 1:
            counts = {item: number(row[i]) for i, (item, _) in enumerate(codes, period_start)}
            households, owners = counts.get("T10"), counts.get("T11")
            share = owners * 100 / households if households and owners is not None else None
            out.add(group, source, region_code, name, year, "owner_occupied_household_share",
                    share.quantize(Decimal("0.01")) if share is not None else None, "%", "거주지", province)
    for (code, name, province, year), fields in education.items():
        diploma_items = ["T51", "T61", "T71", "T81"]

        def sum_complete(items):
            total = Decimal(0)
            for item in items:
                values = fields[item]
                if None in values:
                    all_ages, age_15, age_20 = (values.get(i) for i in (None, 15, 20))
                    if any(v is None for v in (all_ages, age_15, age_20)):
                        return None
                    total += all_ages - age_15 - age_20
                elif values.keys() == set(range(25, 86, 5)) and all(v is not None for v in values.values()):
                    total += sum(values.values())
                else:
                    return None
            return total

        adults = sum_complete(["T10"])
        graduates = sum_complete(diploma_items)
        share = (graduates * 100 / adults).quantize(Decimal("0.01")) if adults and graduates is not None else None
        diploma_totals = [fields[item].get(None) for item in diploma_items]
        graduates_15_plus = sum(diploma_totals) if all(value is not None for value in diploma_totals) else None
        for indicator, value, unit in (
            ("population_25_plus", adults, "명"),
            ("college_graduates_25_plus", graduates, "명"),
            ("college_graduate_share_25_plus", share, "%"),
            ("college_graduates_15_plus", graduates_15_plus, "명"),
        ):
            if table_id == "DT_1PM2501" and indicator == "college_graduates_15_plus":
                continue
            out.add(group, source, code, name, year, indicator, value, unit, "거주지", province)


def income(out, source, entry):
    from openpyxl import load_workbook

    with (RAW / entry["file"]).open("rb") as data:
        book = load_workbook(data, read_only=True, data_only=True, keep_links=False)
        sheet = book.active
        sheet.reset_dimensions()
        cells = iter(sheet.values)
        year_header = next(cells)
        columns = next(cells)
        labels = next(cells)
        col_amount = next(i for i, x in enumerate(columns) if x and "(총급여)" in x and labels[i] == "금액")
        col_people = col_amount - 1
        if labels[col_people] != "인원":
            raise ValueError(f"Unexpected gross-salary columns in {source}")
        year = str(year_header[col_amount])
        province = ""
        for row in cells:
            name = str(row[0] or "").strip()
            if name in out.regions.aliases and name not in {"세종", "세종시", "세종특별자치시"}:
                province = name
                continue
            if name in {"세종", "세종시", "세종특별자치시"}:
                province = name
            if not name or name in {"전국", "외국", "기타"} or name.startswith(("기타[", "주)", "자료")):
                continue
            people, amount = number(row[col_people]), number(row[col_amount])
            out.add("income", source, "", name, year, "wage_tax_filers", people, "명", "주소지", province)
            out.add("income", source, "", name, year, "taxable_gross_wages", amount, "백만원", "주소지", province)
            average = amount * 100 / people if amount is not None and people else None
            if average is not None:
                average = average.quantize(Decimal("0.01"))
            out.add("income", source, "", name, year, "taxable_gross_wages_per_filer",
                    average, "만원/명", "주소지", province)
        book.close()


def sejong_yearbook(out, source, entry):
    from openpyxl import load_workbook

    def sheet_rows(archive, file_title, sheet_title):
        chapter = next(n for n in archive.namelist() if file_title in n and n.endswith(".xlsx"))
        book = load_workbook(io.BytesIO(archive.read(chapter)), read_only=True, data_only=True, keep_links=False)
        sheet = next(s for s in book if sheet_title in s.title and s.sheet_state == "visible")
        try:
            return list(sheet.values)
        finally:
            book.close()

    def emit(group, year, indicator, value, unit, basis, activity=""):
        out.add(group, source, "", "세종특별자치시", year, indicator, value, unit,
                basis, "세종특별자치시", activity)

    def title(value):
        return re.split(r"[A-Za-z]", value, maxsplit=1)[0].replace("\n", " ").strip()

    with zipfile.ZipFile(RAW / entry["file"]) as archive:
        rows = sheet_rows(archive, "소득 및 지출", "ⅩⅥ-3. 경제활동별")
        for header, data in ((rows[2], rows[4:10]), (rows[12], rows[13:19])):
            # The first block prints total, tax and GVA on the line above its industry captions.
            captions = list(header)
            if header is rows[2]:
                captions[4:11] = rows[3][4:11]
            for row in data:
                year = re.match(r"20\d\d", str(row[0]))
                if not year:
                    continue
                for col, header_value in enumerate(captions[1:], 1):
                    if not header_value or title(header_value) == "":
                        continue
                    emit("grdp", year[0], "grdp_current", row[col], "백만원", "생산지", title(header_value))

        business = sheet_rows(archive, "Ⅴ. 사업체", "Ⅴ-3 산업별")
        columns = (6, 8, 10, 12, 14, 16, 18, 20, 22, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44)
        for row in business[11:17]:
            for letter, col in zip("ABCDEFGHIJKLMNOPQRS", columns, strict=True):
                activity = f"{letter} {title(business[5][col])}"
                emit("business", row[0], "establishments", row[col], "개", "사업장", activity)
                emit("business", row[0], "establishment_workers", row[col + 1], "명", "사업장", activity)
            emit("business", row[0], "establishments", row[1], "개", "사업장", "합계")
            emit("business", row[0], "establishment_workers", row[3], "명", "사업장", "합계")

        for file_title, sheet_title, group, fields in (
            ("농림수산업(1~11)", "Ⅵ-1 농가", "agriculture",
             ((1, "farm_households", "가구", "거주지"), (4, "farm_population", "명", "거주지"))),
            ("사회보장(18~31)", "수급자_항목추가", "assistance",
             ((2, "livelihood_guarantee_recipients", "명", "거주지"),)),
            ("Ⅳ. 노동", "경제활동인구 총괄", "employment",
             ((10, "employment_rate_annual", "%", "거주지"), (11, "unemployment_rate_annual", "%", "거주지"))),
        ):
            for row in sheet_rows(archive, file_title, sheet_title):
                if group == "employment" and row[0] is None and str(row[1]).strip().startswith("남자"):
                    break
                if not re.fullmatch(r"20\d\d", str(row[0])):
                    continue
                for col, indicator, unit, basis in fields:
                    emit(group, row[0], indicator, row[col], unit, basis)


def welfare_pdf(out, source, entry):
    import pymupdf

    totals = None
    regions = set()
    observed = [0, 0]
    province = ""
    with pymupdf.open(RAW / entry["file"]) as pdf:
        for page_index in range(146, 156):
            tables = pdf[page_index].find_tables(strategy="lines_strict").tables
            if len(tables) != 1:
                raise ValueError(f"{source}: unexpected table count at page {page_index + 1}")
            rows = tables[0].extract()
            if [clean(name) for name in rows[0]] != ["시･도", "시･군･구", "가구수", "수급자수"]:
                raise ValueError(f"{source}: unexpected welfare PDF columns")
            for label, districts, household_counts, recipient_counts in rows[1:]:
                if label == "합계":
                    totals = [number(household_counts), number(recipient_counts)]
                    continue
                if label:
                    province = label
                for name, households, recipients in zip(
                    districts.splitlines(), household_counts.splitlines(), recipient_counts.splitlines(),
                    strict=True,
                ):
                    key = province, name
                    if key in regions or province not in out.regions.aliases:
                        raise ValueError(f"{source}: unexpected district {key}")
                    regions.add(key)
                    for i, (indicator, value, unit) in enumerate((
                        ("livelihood_general_recipient_households", households, "가구"),
                        ("livelihood_general_recipients", recipients, "명"),
                    )):
                        observed[i] += number(value)
                        out.add("assistance", source, "", name, entry["vintage"], indicator,
                                value, unit, "거주지", province)
    if observed != totals:
        raise ValueError(f"{source}: sums {observed} differ from printed totals {totals}")
    print(f"{source}: {len(regions)} source districts, sums match PDF")


def seoul_business(out, source, entry):
    required_categories = {"공장,지사", "단독", "본사,본점"}
    totals = defaultdict(dict)
    with zipfile.ZipFile(RAW / entry["file"]) as archive:
        file = next(name for name in archive.namelist() if name.endswith(".csv"))
        with archive.open(file) as content, io.TextIOWrapper(content, encoding="cp949", newline="") as text:
            rows = csv.reader(text)
            next(rows)
            next(rows)
            # The exported header places the year first, but each data line ends with it.
            for district, dong, industry, group, category, businesses, workers, year in rows:
                if year not in {"2019", "2023"} or dong != "전체" or group != "사업체구분":
                    continue
                key = district, industry, year
                if category in totals[key]:
                    raise ValueError(f"{source}: duplicate category {key}, {category}")
                totals[key][category] = (number(businesses), number(workers))
    for (district, industry, year), categories in sorted(totals.items()):
        if categories.keys() != required_categories:
            raise ValueError(f"{source}: incomplete business-type categories in {district}, {industry}, {year}")
        for i, (indicator, unit) in enumerate((("establishments", "개"), ("establishment_workers", "명"))):
            values = [counts[i] for counts in categories.values()]
            total = sum(values) if all(value is not None for value in values) else None
            out.add("business", source, "", district, year, indicator, total, unit, "사업장",
                    "서울특별시", "합계" if industry in {"전산업", "전 산업", "전체"} else industry)


def normalize(append=()):
    out = Output(Regions())
    manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))
    if append:
        manifest = {source: manifest[source] for source in append}
    for source, entry in sorted(manifest.items()):
        if source.startswith("molit-apartment-"):
            housing(out, source, entry)
        elif source.startswith("tasis-"):
            income(out, source, entry)
        elif source.startswith("kosis-"):
            kosis(out, source, entry)
        elif source == "sejong-yearbook-2024":
            sejong_yearbook(out, source, entry)
        elif source == "mohw-welfare-2025":
            welfare_pdf(out, source, entry)
        elif source == "seoul-business-10160":
            seoul_business(out, source, entry)
        elif source.startswith(("jeonnam-business-", "chungbuk-business-", "jeonbuk-business-",
                                "jeju-business-", "gyeonggi-business-")):
            regional_business_workbook(out, source, entry)
        elif source in {"15132649", "15135703"}:
            legacy(out, source, entry)
    if not append:
        out.write()
        return
    emitted = {row[-1] for rows in out.rows.values() for row in rows}
    if missing := set(append) - emitted:
        raise ValueError(f"No rows normalized for {', '.join(sorted(missing))}")
    for group, rows in sorted(out.rows.items()):
        path = OUT / f"{group}.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream)
            if tuple(next(reader)) != FIELDS:
                raise ValueError(f"Unexpected header in {path}")
            existing = list(reader)
        known = {tuple(row) for row in existing}
        new = []
        for row in rows:
            formatted = tuple(str(value) if value is not None else "" for value in row)
            if formatted not in known:
                new.append(row)
                known.add(formatted)
        if new:
            write_csv(path, [*existing, *new])
        print(f"{group}: kept {len(existing):,}, appended {len(new):,}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--append", nargs="+", metavar="SOURCE_ID")
    normalize(parser.parse_args().append)
