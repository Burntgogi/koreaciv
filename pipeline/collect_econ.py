"""Download public economic source files. Run with a topic or without arguments."""
import argparse
import datetime
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from lib import netguard as NG  # noqa: E402  (감사 08·09: 허용 호스트·HTTPS·리디렉션·크기 상한·RAW 밖 경로)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/econ"
BASE = "https://www.data.go.kr"
SOURCES = {
    "grdp": ("3074490", "15062826", "15051273", "15113706", "15085963",
             "3033624", "15113701", "15085925", "15052025"),
    "business": ("15087673", "3073433", "15055821"),
    "agriculture": ("15046521", "15046525"),
    "finance": ("15081209", "15148291", "15061930", "15135703"),
    "fertility": ("15132649",),
}


# Reference periods were verified against the downloaded content or catalog.
VINTAGES = {
    "15051273": [2011, 2013],
    "15113701": [2000, 2009],
    "15087673": 2024,
    "15132649": 2024,
    "15135703": 2022,
}


def fetch(url):
    time.sleep(1.2)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    _, body = NG.urllib_open(request, timeout=30)
    return body


def collect(pk, group, manifest):
    page_url = f"{BASE}/data/{pk}/fileData.do"
    page = fetch(page_url).decode("utf-8")
    detail = re.search(r"fn_fileDataDown\('\d+',\s*'([^']+)'", page)
    if detail is None:
        raise ValueError("no direct file download button")
    query = urlencode({"publicDataPk": pk, "publicDataDetailPk": detail[1], "fileDetailSn": 1})
    info = fetch(f"{BASE}/tcs/dss/selectFileDataDownload.do?{query}").decode()
    attachment = re.search(r'"atchFileId"\s*:\s*"([^"]+)"', info)
    extension = re.search(r'"atchFileExtsn"\s*:\s*"([a-zA-Z0-9]+)"', info)
    if not attachment or not extension:
        raise ValueError("missing attachment or extension")
    query = urlencode({"atchFileId": attachment[1], "fileDetailSn": 1})
    url = f"{BASE}/cmm/cmm/fileDownload.do?{query}"
    content = fetch(url)
    if not content or content.lstrip().startswith((b"<!", b"<html", b"{")):
        raise ValueError("file response was empty, HTML or JSON")
    title = re.search(r'"name"\s*:\s*"([^"]+)"', page)
    publisher = re.search(r'"creator"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', page)
    label = title[1] if title else pk
    relative = f"{group}/{pk}.{extension[1].lower()}"
    destination = NG.check_path(RAW, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    manifest[pk] = {
        "title": label, "publisher": publisher[1] if publisher else label.split("_")[0],
        "file": relative, "url": url, "catalog_url": page_url,
        "retrieved": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
        "vintage": VINTAGES.get(pk), "table_id": None, "license": None,
        "license_note": "이용허락범위 제한 없음" if "이용허락범위 제한 없음" in page else None,
    }
    print(f"{pk} {relative} {len(content):,} bytes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groups", nargs="*", metavar="TOPIC")
    args = parser.parse_args()
    groups = args.groups or list(SOURCES)
    for group in groups:
        if group not in SOURCES:
            parser.error(f"unknown topic {group!r}; available: {', '.join(SOURCES)}")
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    failed = False
    for group in groups:
        for pk in SOURCES[group]:
            try:
                collect(pk, group, manifest)
            except (OSError, ValueError) as error:
                print(f"{pk}: {error}")
                if isinstance(error, HTTPError) and error.code in (401, 403, 429):
                    return 1
                failed = True
            else:
                pending = path.with_suffix(".tmp")
                pending.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                pending.replace(path)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())

