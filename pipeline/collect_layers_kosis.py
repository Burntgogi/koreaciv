"""Export selected KOSIS tables through the existing public CSV workflow."""
import argparse
import asyncio
import sys
import site
from pathlib import Path

# Isolated Python excludes both the script directory and user-installed Playwright.
if __name__ == "__main__" and __package__ is None:
    sys.path.extend([str(Path(__file__).resolve().parent), site.getusersitepackages()])

import collect_econ_kosis as kosis
from collect_layers import Archive

STATS = "국가데이터처"
OFFICIAL = [
    ("101", "DT_1DA7004S", STATS),
    ("101", "DT_1C91", STATS),
]
HISTORY = {"204", "205", "206", "207", "210", "211", "212", "213", "214", "215", "216", "218"}
OLD_HISTORY = {
    "206": "DT_2015Y25GRDP1", "207": "DT_GRDP_2015_01", "213": "DT_2015Y34GRDP1",
    "216": "DT_I30002", "218": "DT_2015Y39GRDP1",
}
LENSES = [("110", "TX_11025_A001_A", "행정안전부")]
HEALTH = [("177", table, "질병관리청") for table in (
    "DT_H_SM", "DT_HEALTH_RECOG", "DT_H_MENTAL_DEPRESS", "DT_H_OBE_OBE",
)]

SELECT_EXTRA = r"""
    if (group === "history" || group === "legacy") {
        // Use the nominal item and preserve the geographic and activity axes.
        choose("fancytree_0", node => /명목|당해년가격|당해연도가격/.test(node.title.replace(/\s/g, "")));
    }
    if (table === "DT_1C91") {
        choose("fancytree_0", node => /당해년가격|당해연도가격|명목/.test(node.title.replace(/\s/g, "")));
    }
    if (table === "DT_1DA7004S" || table === "DT_1ES3B01S") {
        choose("fancytree_0", node => /^(고용률|실업률)(\s|$)/.test(node.title));
        for (const id of ["fancytree_1", "fancytree_2"]) {
            const nodes = tree(id)?.getRootNode().children || [];
            if (nodes.some(node => node.title.trim() === "남자")) choose(id, total);
        }
    }
"""
SELECT_PERIODS = r"""
    if (years.length && annual) {
        const start = document.getElementById("selectStrtTime" + annual);
        const end = document.getElementById("selectEndTime" + annual);
        if (start && end) {
            const offered = [...start.options].map(option => Number(option.value));
            const intersection = years.filter(year => offered.includes(year));
            if (!intersection.length) throw Error("Requested years unavailable: " + offered.join(","));
            start.value = Math.min(...intersection);
            end.value = Math.max(...intersection);
            fn_searchPeriod(annual);
            for (let i = 0; i < 80; i++) {
                const visibleYears = tree("timeList" + annual)?.getRootNode().children || [];
                if (intersection.every(year => visibleYears.some(node => Number(node.data.prdDe) === year))) break;
                await new Promise(resolve => setTimeout(resolve, 250));
            }
            const visibleYears = tree("timeList" + annual)?.getRootNode().children || [];
            if (!intersection.every(year => visibleYears.some(node => Number(node.data.prdDe) === year))) {
                throw Error("Could not set the requested annual range");
            }
        }
    }
"""


class LayerArchive(Archive):
    def has(self, source_id):
        if source_id.split("-")[1] in HISTORY:
            source_id = f"layers-{source_id}"
        return super().has(source_id)

    def save(self, source_id, file, content, **metadata):
        group, name = file.split("/")
        folder = {
            "official": "../econ/official_totals",
            "history": "../econ/grdp_history",
            "legacy": "../econ/grdp_history_2015",
            "lenses": "D1",
            "agriculture": "C9",
            "health": "D3",
            "academies": "D5",
        }[group]
        if group in {"history", "legacy"}:
            source_id = f"layers-{source_id}"
        super().save(source_id, f"{folder}/{name}", content, **metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groups", nargs="*", metavar="GROUP")
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--inspect", nargs="+")
    args = parser.parse_args()
    kosis.Archive = LayerArchive
    kosis.TABLES = {
        "official": OFFICIAL,
        "history": [(org, table, province) for org, (table, province) in kosis.GRDP.items()
                    if org in HISTORY],
        "legacy": [(org, table, kosis.GRDP[org][1]) for org, table in OLD_HISTORY.items()],
        "agriculture": [("101", "DT_1ET0034", STATS)],
        "health": HEALTH,
        "academies": [("101", "DT_1YL21191", STATS)],
        "lenses": LENSES,
    }
    if any(group not in kosis.TABLES for group in args.groups):
        parser.error("Groups: " + ", ".join(kosis.TABLES))
    kosis.YEARS = {
        "DT_1C91": list(range(2018, 2026)),
        **{table: list(range(2018, 2023)) for org, (table, _) in kosis.GRDP.items()
           if org in HISTORY},
        **{table: [2018, 2019] for table in OLD_HISTORY.values()},
    }
    kosis.SELECT = kosis.SELECT.replace("({table, years, group, org}) =>",
                                        "async ({table, years, group, org}) =>").replace(
        'const annual = g_result.find(frequency => frequency.endsWith("Y"));',
        'const annual = g_result.find(frequency => frequency.endsWith("Y"));' + SELECT_PERIODS,
    ).replace(
        "if (!regionalBusiness) selectArea();",
        "if (!regionalBusiness) selectArea();" + SELECT_EXTRA,
    )
    return asyncio.run(kosis.download(args.groups or list(kosis.TABLES), "chrome", False,
                                      args.only, args.trace, args.inspect or ()))


if __name__ == "__main__":
    raise SystemExit(main())
