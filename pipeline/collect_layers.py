"""Archive the public, keyless inputs for the map layers."""
import argparse
import datetime as dt
import hashlib
import json
import re
import time
from pathlib import Path

import requests
from lib import netguard as NG  # noqa: E402  (감사 08·09: 허용 호스트·HTTPS·리디렉션·크기 상한·RAW 밖 경로)
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/layers"
ECON = ROOT / "data/raw/econ"
PORTAL = "https://www.data.go.kr"
CATALOG = {
    "terrain": ("A3/15126804", "A1/15104486", "A1/15104487", "A1/15104489"),
    "layers": (
        "C1/3070081", "C1/15003687", "C2/15088273", "C2/15147941", "C3/15002851",
        "C5/15107577", "C7/15045195", "C8/15055167", "C9/15071107",
    ),
}
COAST = "https://coast.mof.go.kr"
LAW = "https://www.law.go.kr/법령/"
KNPS = "https://www.knps.or.kr"
KNPS_REVISION = KNPS + "/front/portal/stats/statsDtl.do?menuNo=8000627&refId=REFM000902"
FOREST = "https://www.forest.go.kr/kfsweb"
MOIS = "https://www.mois.go.kr"
AIRKOREA = "https://www.airkorea.or.kr"
SAFEKOREA = "https://www.safekorea.go.kr/safekorea-kor"
DIRECT = {
    "tidal-flat-shp": (
        "A3/tidal-flat-2011.zip", COAST + "/file/download.do?type=004&seq=48",
        "1/25,000 연안정보도 갯벌", "해양수산부", "2011", None,
        COAST + "/coastKnowledge/coastDatumView.do?seq=48&data_type=3&page=",
    ),
    "border-law": (
        "C11/border-law.html", LAW + "접경지역지원특별법시행령",
        "접경지역 지원 특별법 시행령", "법제처 국가법령정보센터", None, None, None,
    ),
    "knps-statistics": (
        "C5/knps-basic-statistics-2026-rev.pdf",
        KNPS + "/portal/file/cdown.do?tfId=TF030&fileId=POMxo6eh0JayRIgt3HnGIA%3D%3D&fileNo=0",
        "2026 국립공원기본통계 수정 공표", "국립공원공단", "2025", "공공누리 제1유형", KNPS_REVISION,
    ),
    "forest-gi": (
        "C6/forest-gi-202607.pdf",
        FOREST + "/cmm/fms/FileDown.do?atchFileId=AFID_05405VqpIrU1VlW&fileSn=0&dwldHistYn=Y&bbsId=BBSMSTR_1068&dnldCntYn=Y",
        "임산물 지리적표시 등록 현황", "산림청", "2026-07", None,
        FOREST + "/cop/bbs/selectBoardArticle.do?bbsId=BBSMSTR_1068&mn=AR01_05_01_04&nttId=3222047",
    ),
    "municipalities-2025": (
        "B7/municipalities-20251231.pdf",
        MOIS + "/cmm/fms/FileDown.do?atchFileId=FILE_001474525FYYt_S&fileSn=0",
        "2026년 지방자치단체 행정구역 및 인구 현황", "행정안전부", "2025-12-31", None,
        MOIS + "/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000055&nttId=128138",
    ),
    "air-yearbook-2025": (
        "D2/air-yearbook-2025.pdf",
        AIRKOREA + "/jfile/readDownloadFile.do?fileId=1a1c46fd3e036&fileSeq=1",
        "2025 대기환경연보", "국립환경과학원", "2025", None, AIRKOREA,
    ),
    "disaster-2024": (
        "D4/disaster-2024-early.zip",
        SAFEKOREA + "/cmmn/file/fileDown.do?atchFileSn=5156&atchFileDtlSn=2",
        "2024년 자연재해상황통계 선공개", "행정안전부", "2024", None,
        SAFEKOREA + "/cmmn/bbs/bbsView.do?menuSn=45&bbscttSn=99",
    ),
    "mof-ports-2025": (
        "C2/mof-ports-2025.pdf",
        "https://www.mof.go.kr/jfile/readDownloadFile.do?fileType=MOF_ARTICLE&fileTypeSeq=64735&fileNum=2",
        "2025년 전국 항만 물동량 발표", "해양수산부", "2025", None,
        "https://www.mof.go.kr/doc/ko/selectDoc.do?bbsSeq=10&docSeq=64735&menuSeq=971",
    ),
}


def direct_file(session, archive, source_id):
    if archive.has(source_id):
        return
    file, url, title, publisher, vintage, license_type, catalog_url = DIRECT[source_id]
    with session.get(url, stream=True, timeout=60) as response:
        content_type = response.headers.get("Content-Type", "").lower()
        if "html" in content_type and not file.endswith(".html"):
            raise ValueError(f"File download returned HTML: {url}")
        archive.save(source_id, file, response.iter_content(1024 * 1024), title=title,
                     publisher=publisher, url=url, vintage=vintage, license=license_type,
                     catalog_url=catalog_url)


class PublicSession(NG.guarded_session_class(requests.Session)):
    """모든 요청·리디렉션을 허용 호스트·HTTPS 로 검사하고 응답 크기에 상한을 둔다 (lib/netguard.py)."""
    def __init__(self):
        super().__init__()
        self.headers["User-Agent"] = "Mozilla/5.0"
        self.last = 0.0

    def send(self, request, **kwargs):
        time.sleep(max(0, 0.8 - (time.monotonic() - self.last)))
        try:
            response = super().send(request, **kwargs)
        finally:
            self.last = time.monotonic()
        response.raise_for_status()
        return response


class Archive:
    def __init__(self):
        self.path = RAW / "manifest.json"
        self.entries = self.read()

    def read(self):
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def has(self, source_id):
        if source_id not in self.entries:
            return False
        entry = self.entries[source_id]
        path = NG.check_path(RAW, entry["file"])
        if not path.is_file() or path.stat().st_size != entry["bytes"]:
            raise ValueError(f"Missing or changed archive file: {path}")
        return True

    def save(self, source_id, file, content, *, title, publisher, url, vintage=None,
             license=None, **metadata):
        path = NG.check_path(RAW, file)
        if path.exists():
            raise FileExistsError(path)
        if isinstance(content, bytes):
            content = (content,)
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_suffix(path.suffix + ".tmp")
        digest = hashlib.sha256()
        try:
            with pending.open("wb") as stream:
                for chunk in content:
                    digest.update(chunk)
                    stream.write(chunk)
            size = pending.stat().st_size
            if not size:
                raise ValueError(f"Empty download: {url}")
            pending.replace(path)
        finally:
            pending.unlink(missing_ok=True)
        entry = dict(title=title, publisher=publisher, file=file, url=url,
                     retrieved=dt.datetime.now(dt.timezone.utc).isoformat(),
                     sha256=digest.hexdigest(), bytes=size, vintage=vintage,
                     license=license or "미확인", **metadata)
        self.entries = self.read()
        self.entries[source_id] = entry
        manifest_pending = self.path.with_suffix(".tmp")
        manifest_pending.write_text(
            json.dumps(self.entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        manifest_pending.replace(self.path)
        print(f"{source_id} {file} {size:,} bytes", flush=True)


def catalog_file(session, archive, target):
    group, pk = target.split("/")
    source_id = f"data-{pk}"
    if archive.has(source_id):
        return
    catalog_url = f"{PORTAL}/data/{pk}/fileData.do"
    response = session.get(catalog_url, timeout=30)
    page = BeautifulSoup(response.content, "html.parser")
    button = page.select_one('button[onclick*="fn_fileDataDown("]')
    if button is None:
        raise ValueError(f"No direct public file button: {catalog_url}")
    data_pk, detail_pk, _, serial, history = re.findall(r"'([^']*)'", button["onclick"])
    info = session.get(f"{PORTAL}/tcs/dss/selectFileDataDownload.do", params={
        "publicDataPk": data_pk, "publicDataDetailPk": detail_pk, "fileDetailSn": serial,
        "publicDataHistSn": history,
    }, timeout=30).json()
    info_text = json.dumps(info)
    attachment = re.search(r'"atchFileId"\s*:\s*"([^"]+)"', info_text)
    extension = re.search(r'"atchFileExtsn"\s*:\s*"([A-Za-z0-9]+)"', info_text)
    if not attachment or not extension:
        raise ValueError(f"No public attachment metadata: {catalog_url}")
    mime = extension[1].lower()
    text = page.get_text(" ", strip=True)
    title = re.search(r'"name"\s*:\s*"([^"]+)"', response.text)
    publisher = re.search(r'"creator"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', response.text)
    license_type = re.search(r"제\s*([1-4])\s*유형", text[text.find("이용 조건 및 라이선스 정보"):])
    with session.get(f"{PORTAL}/cmm/cmm/fileDownload.do", params={
        "atchFileId": attachment[1], "fileDetailSn": serial,
    }, stream=True, timeout=60) as download:
        content_type = download.headers.get("Content-Type", "").lower()
        if "html" in content_type or "json" in content_type:
            raise ValueError(f"Unexpected download type {content_type}: {catalog_url}")
        archive.save(source_id, f"{group}/{pk}.{mime}", download.iter_content(1024 * 1024),
                     title=title[1] if title else page.title.get_text(strip=True),
                     publisher=publisher[1] if publisher else "공공데이터포털",
                     url=download.url, catalog_url=catalog_url,
                     license=f"공공누리 제{license_type[1]}유형" if license_type else None,
                     license_note="이용허락범위 제한 없음" if "이용허락범위 제한 없음" in text else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*", help="Catalog group or subfolder/dataset ID")
    args = parser.parse_args()
    archive = Archive()
    failed = False
    with PublicSession() as session:
        for target in args.targets or [*CATALOG, *DIRECT]:
            for item in CATALOG.get(target, (target,)):
                try:
                    if item in DIRECT:
                        direct_file(session, archive, item)
                    else:
                        catalog_file(session, archive, item)
                except (OSError, ValueError) as error:
                    print(f"{item}: {error}", flush=True)
                    failed = True
                    if getattr(getattr(error, "response", None), "status_code", None) in {401, 403, 429}:
                        return 1
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
