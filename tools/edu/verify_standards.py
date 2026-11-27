"""성취기준 문장을 고시 원문과 글자 그대로 견준다: python tools/edu/verify_standards.py <원문 글 폴더>

<원문 글 폴더>에는 국가교육과정정보센터(ncic.re.kr → 교육과정 자료실 → 교육과정 원문 및 해설서 → 2022 개정)에서 받은 PDF 의
글 층을 뽑은 파일이 있어야 한다 (PyMuPDF page.get_text() 를 쪽마다 이어 붙인 것):
  s7.txt   별책 7 사회과 교육과정 (국가교육위원회 고시 제2024-3호 일부개정 포함본)
  s10.txt  별책 10 실과(기술·가정)/정보과 교육과정
site/edu/content.json 의 standards 표에서 '[코드] 문장'을 만들어, 공백과 가운뎃점 종류(⋅·ㆍ)를 뺀 글로 원문에 그대로 있는지 본다.
이 저장소에는 원문을 싣지 않는다. 결과만 표준 출력에 적는다.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def norm(s):
    return re.sub(r"[\s⋅·ㆍ․‧∙•]", "", s)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    d = sys.argv[1]
    content = json.load(open(os.path.join(ROOT, "site", "edu", "content.json"), encoding="utf-8"))
    texts = {}
    bad = 0
    for code, s in content["standards"].items():
        doc = s["doc"]
        if doc not in texts:
            texts[doc] = norm(open(os.path.join(d, doc + ".txt"), encoding="utf-8").read())
        ok = norm(code + s["text"]) in texts[doc]
        unit_ok = norm(s["unit"]) in texts[doc]
        bad += (not ok) + (not unit_ok)
        print(("같음  " if ok else "다름  ") + ("단원 같음  " if unit_ok else "단원 다름  ") + code)
    print(f"성취기준 {len(content['standards'])}개 가운데 문장이나 단원 이름이 원문과 다른 것 {bad}개")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
