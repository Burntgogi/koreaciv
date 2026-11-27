"""전체 빌드: world -> regions -> lenses -> econ -> layers -> layers2(5b 2부) -> layers3(5d) -> layers5e(5e) -> phase6(6단계) -> insights(7b) -> ridges -> sources -> notice(NOTICE.md) -> validate.
(NOTICE.md 는 빌드의 끝에서 sources.json 으로 만들고, 마지막 검증이 둘이 맞는지 본다.)

실행: python pipeline/build_all.py [--profile full|public] [--skip-world]
  --profile full   (기본) 전체판 — 내부 열람용. 지금까지의 빌드 그대로. 끝나면 site/data 를 data/build/site_data_full/ 에도 복사한다.
  --profile public 공개판 — GitHub Pages 에 올리는 판. 빼는 자료와 까닭은 pipeline/lib/profile.py 의 EXCLUDE.
판은 환경 변수 KOREACIV_PROFILE 로 각 단계에 넘긴다(단계를 따로 돌릴 때도 같은 변수).
(인구 원자료를 새로 받으려면 먼저 python pipeline/collect_population.py)
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STEPS = ["build_landstats_open.py", "build_world.py", "build_regions.py", "build_lenses.py", "build_econ.py", "build_layers.py", "build_layers2.py", "build_layers3.py", "build_layers5e.py", "build_phase6.py", "build_insights.py", "build_ridges.py", "build_sources.py", "build_notice.py", "validate.py", "build_edu.py"]
FULL_COPY = os.path.join(ROOT, "data", "build", "site_data_full")


def parse(argv):
    prof = "full"
    for i, a in enumerate(argv):
        if a.startswith("--profile="):
            prof = a.split("=", 1)[1]
        elif a == "--profile":
            if i + 1 >= len(argv):
                raise SystemExit("--profile 다음에 full 또는 public")
            prof = argv[i + 1]
    if prof not in ("full", "public"):
        raise SystemExit(f"알 수 없는 판 {prof!r} — full 또는 public")
    return prof, "--skip-world" in argv


def main():
    prof, skip_world = parse(sys.argv[1:])
    env = dict(os.environ, KOREACIV_PROFILE=prof, PYTHONHASHSEED="0")
    sys.path.insert(0, HERE)
    os.environ["KOREACIV_PROFILE"] = prof
    from lib import profile as P
    print(P.banner(), flush=True)
    steps = STEPS[1:] if skip_world else STEPS
    if skip_world:
        wp = os.path.join(ROOT, "site", "data", "world.json")
        got = json.load(open(wp, encoding="utf-8")).get("build_profile", "full") if os.path.exists(wp) else None
        if got != prof:
            raise SystemExit(f"--skip-world: 지금 world.json 은 {got} 판이다. {prof} 판은 world 부터 다시 빌드한다 (--skip-world 없이).")
    for s in steps:
        print(f"=== {s}  [{prof}]", flush=True)
        r = subprocess.run([sys.executable, os.path.join(HERE, s)], cwd=HERE, env=env)
        if r.returncode:
            print(f"!!! {s} 실패 (코드 {r.returncode}) — 판 {prof}")
            sys.exit(r.returncode)
    if prof == "full":
        # 공개판과 비교할 수 있게 전체판 결과를 사본으로 남긴다 (data/build 는 저장소에 올리지 않는다)
        if os.path.isdir(FULL_COPY):
            shutil.rmtree(FULL_COPY)
        shutil.copytree(os.path.join(ROOT, "site", "data"), FULL_COPY)
        shutil.copyfile(os.path.join(ROOT, "NOTICE.md"), os.path.join(FULL_COPY, "NOTICE.md"))
        print(f"전체판 사본: {os.path.relpath(FULL_COPY, ROOT)}")
    print(P.banner().replace("빌드 판:", "빌드 완료, 검증 통과 — 판:"), flush=True)


if __name__ == "__main__":
    main()
