"""공개판 결손 보완(인천국제공항·토지피복) 후보 자료 및 이용조건 증빙 재현 수집기 (Layers 5).

실행:
  python -I pipeline/collect_layers5.py            # 누락 파일 수집 및 전체 무결성(SHA-256·바이트) 검증
  python -I pipeline/collect_layers5.py --offline  # 네트워크 요청 없이 로컬 파일과 manifest.json 무결성만 검증

원칙:
  - 로그인·회원가입·인증키·자료 신청·CAPTCHA 우회가 필요한 경로는 수집하지 않는다.
  - 요청 헤더에 이름·이메일 등 개인정보를 넣지 않는다.
  - 모든 HTTP 요청은 HTTPS 허용 호스트 화이트리스트 안에서 최소 1.0초 간격으로 순차 실행한다.
  - 저장 경로는 data/raw/layers5/ 하위(portal/, files/)로 제한하고 manifest.json에
    url, final_url, file, retrieved(UTC), sha256, bytes, license_url을 기록한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw" / "layers5"
MANIFEST_PATH = OUT_DIR / "manifest.json"

ALLOWED_HOSTS = frozenset({
    "www.data.go.kr",
    "naciscdn.org",
    "raw.githubusercontent.com",
    "davidmegginson.github.io",
    "www.wikidata.org",
    "download.geonames.org",
    "www.law.go.kr",
    "www.airport.kr",
    "map.forest.go.kr",
    "map.ngii.go.kr",
    "www.bigdata-environment.kr",
    "developers.google.com",
    "www.eorc.jaxa.jp",
})

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
MIN_INTERVAL_SEC = 1.0
MAX_BYTES = 150 * 1024 * 1024  # 단일 파일 상한 150 MB (제주 팜맵 102 MB 포함)

_last_request_ts = 0.0


def _check_url(url: str) -> None:
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https":
        raise ValueError(f"HTTPS만 허용됨: {url}")
    if p.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"허용되지 않은 호스트: {p.hostname} ({url})")
    if p.username or p.password:
        raise ValueError("URL 내 인증정보 금지")


def _safe_dest(rel_path: str) -> Path:
    dest = (OUT_DIR / rel_path).resolve()
    root_res = OUT_DIR.resolve()
    if dest != root_res and root_res not in dest.parents:
        raise ValueError(f"data/raw/layers5 외부 경로 쓰기 금지: {dest}")
    return dest


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_entry(url: str, rel_file: str, license_url: str, data: bytes | None = None, referer: str | None = None) -> dict:
    global _last_request_ts
    _check_url(url)
    dest = _safe_dest(rel_file)
    dest.parent.mkdir(parents=True, exist_ok=True)

    wait = MIN_INTERVAL_SEC - (time.monotonic() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)

    headers = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"

    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=90) as resp:
        final_url = resp.geturl()
        _check_url(final_url)
        chunks = []
        total = 0
        while True:
            buf = resp.read(256 * 1024)
            if not buf:
                break
            total += len(buf)
            if total > MAX_BYTES:
                raise ValueError(f"다운로드 크기 상한 초과 ({total} > {MAX_BYTES}): {url}")
            chunks.append(buf)
        body = b"".join(chunks)

    _last_request_ts = time.monotonic()
    dest.write_bytes(body)
    return {
        "url": url,
        "final_url": final_url,
        "file": rel_file,
        "retrieved": datetime.now(timezone.utc).isoformat(),
        "sha256": sha256_bytes(body),
        "bytes": len(body),
        "license_url": license_url,
    }


def verify_or_collect(offline: bool = False) -> int:
    if not MANIFEST_PATH.exists():
        print(f"[오류] manifest.json 없음: {MANIFEST_PATH}", file=sys.stderr)
        return 1

    manifest: dict[str, dict] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    # 불필요한 404 임시 항목 정리
    if "airport-kr-copyright" in manifest and "airport-kr-copyright-1033" in manifest:
        stale_file = _safe_dest(manifest["airport-kr-copyright"]["file"])
        if stale_file.exists():
            stale_file.unlink()
        del manifest["airport-kr-copyright"]
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ok_count = 0
    fetched_count = 0
    errors = []

    for key, meta in manifest.items():
        rel_file = meta["file"]
        dest = _safe_dest(rel_file)
        if dest.exists() and dest.stat().st_size > 0:
            actual_bytes = dest.stat().st_size
            actual_sha = sha256_file(dest)
            if actual_bytes == meta["bytes"] and actual_sha == meta["sha256"]:
                ok_count += 1
                continue
            if offline:
                errors.append(f"{key} ({rel_file}): 해시/크기 불일치 (expected {meta['bytes']}B/{meta['sha256'][:12]}, got {actual_bytes}B/{actual_sha[:12]})")
                continue

        if offline:
            errors.append(f"{key} ({rel_file}): 파일 누락")
            continue

        # 누락 파일 재수집
        url = meta["url"]
        lic = meta["license_url"]
        post_data = b"lsiSeq=224715&efYd=20201210" if key == "law-iiac-body" else None
        ref = lic if "data.go.kr" in url or "law.go.kr" in url else None
        try:
            updated = fetch_entry(url, rel_file, lic, data=post_data, referer=ref)
            manifest[key] = updated
            fetched_count += 1
            print(f"  [수집] {key} -> {rel_file} ({updated['bytes']:,} B)")
        except Exception as e:
            errors.append(f"{key} ({url}): 수집 실패 - {e}")

    if fetched_count > 0:
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    total_bytes = sum(m["bytes"] for m in manifest.values())
    print(f"[collect_layers5] 항목 {len(manifest)}개 중 검증 완료 {ok_count}개, 신규 수집 {fetched_count}개, 총 용량 {total_bytes:,} B ({total_bytes / (1024*1024):.2f} MB)")
    if errors:
        for err in errors:
            print(f"  [오류] {err}", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Layers 5 후보 자료 및 이용조건 증빙 수집·검증기")
    ap.add_argument("--offline", action="store_true", help="네트워크 요청 없이 로컬 파일과 manifest.json의 SHA-256 무결성만 검증")
    args = ap.parse_args()
    sys.exit(verify_or_collect(offline=args.offline))


if __name__ == "__main__":
    main()
