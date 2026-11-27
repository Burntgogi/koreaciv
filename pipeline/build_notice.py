"""NOTICE.md (저장소 맨 위) <- site/data/sources.json

출처·이용허락 유형별 건수, 이용조건에 제한이 있는 자료, 이용허락 미확인 자료, 출처 표기 줄, 계산한 층, 글꼴을 적는다.
sources.json 만 읽으므로 원자료가 없는 저장소에서도 다시 만들 수 있다. validate.py 가 같은 함수로 다시 만들어 파일과 대조한다.

실행: python pipeline/build_notice.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import notice as NT  # noqa: E402


def main():
    txt = NT.render_notice(NT.load_sources_json())
    with open(NT.NOTICE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(txt)
    print(f"[notice] {os.path.relpath(NT.NOTICE, NT.ROOT)} {len(txt.encode('utf-8')):,} 바이트")


if __name__ == "__main__":
    sys.exit(main())
