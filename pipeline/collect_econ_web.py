"""Shared rate limiter and provenance for keyless economic downloads."""
import datetime as dt
import hashlib
import json
import time
from urllib.parse import urlsplit

import requests

from collect_econ import RAW
from lib import netguard as NG  # noqa: E402  (감사 08·09: 허용 호스트·HTTPS·리디렉션·크기 상한·RAW 밖 경로)


class SiteBlocked(RuntimeError):
    pass


class PublicSession(NG.guarded_session_class(requests.Session)):
    """모든 요청·리디렉션을 허용 호스트·HTTPS 로 검사하고 응답 크기에 상한을 둔다 (lib/netguard.py)."""
    def __init__(self):
        super().__init__()
        self.headers["User-Agent"] = "Mozilla/5.0"
        self.last = 0
        self.delay = 1.2

    def send(self, request, **kwargs):
        time.sleep(max(0, self.delay - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        result = super().send(request, **kwargs)
        if result.status_code in (401, 403, 429):
            raise SiteBlocked(f"HTTP {result.status_code} {urlsplit(result.url).path}")
        self.delay = min(self.delay * 2, 15) if result.status_code >= 500 else 1.2
        return result


class Archive:
    def __init__(self):
        self.path = RAW / "manifest.json"
        self.entries = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def has(self, source_id):
        entry = self.entries.get(source_id)
        if entry is None:
            return False
        path = NG.check_path(RAW, entry["file"])
        return path.is_file() and path.stat().st_size == entry["bytes"]

    def save(self, source_id, file, content, *, title, publisher, url, vintage,
             table_id=None, license=None, **metadata):
        if not content or content.lstrip().lower().startswith((b"<html", b"<!doctype", b"{")):
            raise ValueError("Expected a file, received HTML, JSON or an empty response")
        entry = dict(title=title, publisher=publisher, file=file, url=url,
                     retrieved=dt.datetime.now(dt.timezone.utc).isoformat(),
                     sha256=hashlib.sha256(content).hexdigest(), bytes=len(content),
                     vintage=vintage, table_id=table_id, license=license, **metadata)
        path = NG.check_path(RAW, file)
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_suffix(path.suffix + ".tmp")
        pending.write_bytes(content)
        pending.replace(path)
        self.entries[source_id] = entry
        pending = self.path.with_suffix(".tmp")
        pending.write_text(json.dumps(self.entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pending.replace(self.path)
        print(f"{source_id} {file} {len(content):,} bytes", flush=True)
