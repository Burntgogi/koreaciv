"""Export KOSIS manufacturing employment from public regional and census tables."""

import argparse
import asyncio
import site
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.extend([str(Path(__file__).resolve().parent), site.getusersitepackages()])

import collect_econ_kosis as kosis
from collect_layers2 import LayerArchive

CENSUS = "DT_2KI2010_11"
TARGETS = {"19", "20", "24", "26", "30", "31"}
REGIONAL = [
    ("203", "DT_203N300003_2024_01", "대구광역시"),
    ("217", "DT_217004_2026D005", "경상남도"),
]

SELECT = r"""
    const keys = ["19", "20", "24", "26", "30", "31"];
    if (table === "DT_2KI2010_11") {
        choose("fancytree_0", node => node.data.itmId === "T20");
        choose("fancytree_1", node => node.data.lvl >= 2);
        choose("fancytree_2", node => keys.includes(node.data.itmId));
    } else {
        const ids = [...document.querySelectorAll('[id^=fancytree_]')]
            .map(x => x.id).filter(id => /^fancytree_[1-9]\d*$/.test(id) && tree(id));
        const rows = id => {
            const out = [];
            each(id, node => out.push(node));
            return out;
        };
        const expressions = [
            /코크스.*석유정제품/, /화학물질.*화학제품/, /^(제)?1차금속/,
            /전자부품.*컴퓨터.*통신장비/, /자동차.*트레일러/, /기타운송장비/
        ];
        const normalized = node => node.title.replace(/[^가-힣0-9]/g, "");
        const industry = ids.find(id => expressions.every(pattern =>
            rows(id).some(node => pattern.test(normalized(node)))));
        const region = ids.find(id => id !== industry &&
            rows(id).filter(node => /[시군구]$/.test(node.title.trim())).length >= 2);
        if (!industry || !region) throw Error("No six industry divisions and district axis");
        choose("fancytree_0", node => /^종사자수$/.test(normalized(node)));
        choose(industry, node => expressions.some(pattern => pattern.test(normalized(node))));
        choose(region, node => /[시군구]$/.test(node.title.trim()) && node.title.trim() !== orgName);
        for (const id of ids.filter(id => id !== industry && id !== region)) {
            const subtotal = rows(id).find(node => total(node) || normalized(node) === "전산업");
            if (!subtotal) throw Error("No aggregate field in " + id);
            choose(id, node => node === subtotal);
        }
    }
"""


class Archive(LayerArchive):
    def save(self, source_id, file, content, *, title, publisher, url, vintage, **metadata):
        if not content or content.lstrip().lower().startswith((b"<html", b"<!doctype")):
            raise ValueError("Expected KOSIS CSV")
        metadata["license"] = metadata.get("license") or "미확인"
        file = "03/" + Path(file).name
        super().save(source_id, file, content, title=title, publisher=publisher, url=url,
                     vintage=vintage, **metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()
    kosis.Archive = Archive
    kosis.TABLES = {"industries": [("101", CENSUS, "국가데이터처"), *REGIONAL]}
    kosis.BUSINESS_YEARBOOKS = set()
    kosis.YEARS = {table: [2024] for _, table, _ in REGIONAL}
    kosis.SELECT = kosis.SELECT.replace(
        "if (!regionalBusiness) selectArea();",
        "const orgName = (" + repr({o: p for o, _, p in REGIONAL}) + ")[org];\n" + SELECT,
    )
    return asyncio.run(kosis.download(["industries"], "chrome", False, args.only, args.trace))


if __name__ == "__main__":
    raise SystemExit(main())
