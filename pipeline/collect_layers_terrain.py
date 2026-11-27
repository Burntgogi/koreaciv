"""Build the terrain layers from the archived spatial files."""
import argparse
import json
import math
from pathlib import Path
import site
import sys
from urllib.parse import urlencode
from zipfile import ZipFile

if __name__ == "__main__" and __package__ is None:
    sys.path.extend([str(Path(__file__).resolve().parent), site.getusersitepackages()])

from collect_layers import Archive, DIRECT, PublicSession, RAW, ROOT, direct_file

OUT = ROOT / "data/build/layers"
BOUNDARY = ROOT / "data/raw/boundary/HangJeongDong_ver20261001.geojson"
WORLD_COVER = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
TILE_CELLS = ("N33E123", "N33E126", "N33E129", "N36E123", "N36E126", "N36E129")
CLASSES = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up",
    60: "Bare/sparse vegetation", 70: "Snow and ice", 80: "Permanent water bodies",
    90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss and lichen",
}
DIRECT.update({
    f"worldcover-{cell}": (
        f"A1/ESA_WorldCover_10m_2021_v200_{cell}_Map.tif",
        WORLD_COVER + f"ESA_WorldCover_10m_2021_v200_{cell}_Map.tif",
        f"ESA WorldCover 10 m 2021 v200 ({cell})", "ESA WorldCover Consortium",
        "2021", "CC BY 4.0", "https://esa-worldcover.org/en/data-access",
    )
    for cell in TILE_CELLS
})
WAMIS = "https://map.wamis.go.kr:8444/geoserver/mbrf/wfs"
RIVERS = {"rivlinen": "국가하천", "rivlinel": "지방하천"}
for layer, grade in RIVERS.items():
    params = urlencode({
        "service": "WFS", "version": "1.1.0", "request": "GetFeature",
        "typeName": f"mbrf:{layer}", "srsName": "EPSG:4326",
        "outputFormat": "application/json",
    })
    DIRECT[f"wamis-{layer}"] = (
        f"A2/{layer}.geojson", f"{WAMIS}?{params}", f"하천유로선_{grade}",
        "국가수자원관리종합정보시스템(WAMIS)", None, None, "https://map.wamis.go.kr:8445/",
    )
DIRECT["osm-water"] = (
    "A2/south-korea-261124.osm.pbf",
    "https://download.geofabrik.de/asia/south-korea/south-korea-261124.osm.pbf",
    "OpenStreetMap South Korea extract", "OpenStreetMap contributors / Geofabrik",
    "2026-11-24", "ODbL 1.0", "https://download.geofabrik.de/asia/south-korea.html",
)


def write_geojson(name, features):
    path = OUT / f"{name}.geojson"
    collection = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")) + "\n",
                    encoding="utf-8")
    print(f"{path.name}: {len(features):,} features", flush=True)


def feature(geometry, **properties):
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def landcover(archive):
    import numpy as np
    import rasterio
    from rasterio.features import bounds, geometry_mask
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject, transform_geom

    crs = "EPSG:5179"
    resolution = 250
    boundary = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    geometries = [transform_geom("EPSG:4326", crs, f["geometry"]) for f in boundary["features"]
                  if f["geometry"]]
    extents = np.array([bounds(geom) for geom in geometries])
    left, bottom = (math.floor(value / resolution) * resolution for value in extents[:, :2].min(0))
    right, top = (math.ceil(value / resolution) * resolution for value in extents[:, 2:].max(0))
    width, height = (right - left) // resolution, (top - bottom) // resolution
    transform = from_origin(left, top, resolution, resolution)
    shape = (height, width)
    raster = np.zeros(shape, dtype=np.uint8)
    with PublicSession() as session:
        for cell in TILE_CELLS:
            source_id = f"worldcover-{cell}"
            direct_file(session, archive, source_id)
            with rasterio.open(RAW / archive.entries[source_id]["file"]) as source:
                part = np.zeros(shape, dtype=np.uint8)
                reproject(
                    rasterio.band(source, 1), part, src_nodata=0,
                    dst_transform=transform, dst_crs=crs, dst_nodata=0,
                    resampling=Resampling.mode, num_threads=1,
                )
            use = (raster == 0) & (part != 0)
            raster[use] = part[use]
    inside = geometry_mask(geometries, shape, transform, all_touched=True, invert=True)
    raster[~inside] = 0
    unknown = set(np.unique(raster)) - {0, *CLASSES}
    if unknown:
        raise ValueError(f"Unknown WorldCover classes: {unknown}")
    with rasterio.open(OUT / "landcover.tif", "w", driver="GTiff", width=width, height=height,
                       count=1, dtype="uint8", crs=crs, transform=transform, nodata=0,
                       compress="deflate", tiled=True) as target:
        target.write(raster, 1)
        target.update_tags(source="ESA WorldCover 10m 2021 v200", license="CC BY 4.0",
                           alternative="true", resampling="mode",
                           classification=json.dumps(CLASSES))
    print(f"landcover.tif: {width} × {height}, {np.count_nonzero(raster):,} classified cells", flush=True)


def tidal_flat(archive):
    import shapefile
    from pyproj import CRS, Transformer
    from shapely import transform
    from shapely.geometry import mapping, shape

    source_id = "tidal-flat-shp"
    with PublicSession() as session:
        direct_file(session, archive, source_id)
    path = RAW / archive.entries[source_id]["file"]
    features = []
    with ZipFile(path) as package:
        names = set(package.namelist())
        for shp in sorted(n for n in names if n.lower().endswith(".shp")):
            stem = shp[:-4]
            if stem + ".prj" in names:
                crs = CRS.from_wkt(package.read(stem + ".prj").decode("ascii"))
            else:
                # The publisher specifies WGS84 / UTM-K with this TM definition.
                crs = CRS.from_proj4("+proj=tmerc +lat_0=38 +lon_0=127.5 +k=0.99996 "
                                     "+x_0=1000000 +y_0=2000000 +datum=WGS84 +units=m")
            project = Transformer.from_crs(crs, 4326, always_xy=True).transform
            with package.open(shp) as shapes:
                reader = shapefile.Reader(shp=shapes)
                for index, item in enumerate(reader.iterShapes(), 1):
                    if not item.points:
                        continue
                    geom = transform(shape(item.__geo_interface__), project, interleaved=False)
                    if geom.is_empty or geom.geom_type not in {"Polygon", "MultiPolygon"}:
                        raise ValueError(f"Unexpected geometry in {shp}: {geom.geom_type}")
                    features.append(feature(mapping(geom), source_id=source_id,
                                            source_file=shp, source_record=index, year=2011))
    if not features:
        raise ValueError("The ZIP held no tidal-flat polygons")
    write_geojson("tidal_flats", features)


def rivers(archive):
    from pyproj import Transformer
    from shapely import transform
    from shapely.geometry import mapping, shape

    project = Transformer.from_crs(4326, 5179, always_xy=True).transform
    unproject = Transformer.from_crs(5179, 4326, always_xy=True).transform
    features = []
    with PublicSession() as session:
        for layer, grade in RIVERS.items():
            source_id = f"wamis-{layer}"
            direct_file(session, archive, source_id)
            raw = json.loads((RAW / archive.entries[source_id]["file"]).read_text(encoding="utf-8"))
            if len(raw["features"]) != raw["totalFeatures"]:
                raise ValueError(f"Public WFS returned a truncated layer: {layer}")
            for row in raw["features"]:
                geom = row["geometry"]
                if not geom or geom["type"] not in {"LineString", "MultiLineString"}:
                    raise ValueError(f"Missing or unexpected river geometry: {layer}")
                line = transform(shape(geom), project, interleaved=False).simplify(20)
                geom = mapping(transform(line, unproject, interleaved=False))
                props = row["properties"]
                features.append(feature(geom, name=props.get("rvr_nm") or props.get("rivnm"),
                                        grade=grade, source_id=source_id, **props))
            print(f"{layer}: {len(raw['features']):,}, {list(raw['features'][0]['properties'])}",
                  flush=True)
    write_geojson("rivers", features)


def farmmap(archive):
    import numpy as np
    import pyogrio
    import rasterio
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    from shapely import from_wkb

    source_ids = ("data-15104486", "data-15104487", "data-15104489")
    classes = {"01": "논", "02": "밭", "03": "과수", "04": "시설"}
    with rasterio.open(OUT / "landcover.tif") as national:
        profile = national.profile
        west, north = int(national.bounds.left), int(national.bounds.top)
        pixel = int(national.res[0])
        width, height = national.width, national.height
    counts = np.zeros((len(classes), height, width), dtype=np.uint16)
    factor = 10
    for source_id in source_ids:
        path = (RAW / archive.entries[source_id]["file"]).resolve()
        with ZipFile(path) as package:
            datasets = sorted(n for n in package.namelist() if n.endswith(".shp"))
        size = 0
        for dataset in datasets:
            url = f"/vsizip/{{{path.as_posix()}}}/{dataset}"
            metadata, table = pyogrio.read_arrow(url, columns=["CLSF_CD"], encoding="CP949")
            if metadata["crs"] != "EPSG:5179":
                raise ValueError(f"Unexpected farm-map CRS: {dataset}: {metadata['crs']}")
            geometry = from_wkb(table["wkb_geometry"].to_pylist(), on_invalid="raise")
            categories = np.array(table["CLSF_CD"].to_pylist())
            west_x, south_y, east_x, north_y = pyogrio.read_info(url)["total_bounds"]
            x0 = max(0, math.floor((west_x - west) / pixel))
            x1 = min(width, math.ceil((east_x - west) / pixel))
            y0 = max(0, math.floor((north - north_y) / pixel))
            y1 = min(height, math.ceil((north - south_y) / pixel))
            fine_shape = ((y1 - y0) * factor, (x1 - x0) * factor)
            fine_pixel = pixel / factor
            transform = from_origin(west + x0 * pixel, north - y0 * pixel, fine_pixel, fine_pixel)
            for band, category in enumerate(classes):
                selected = geometry[categories == category]
                if selected.size:
                    grid = rasterize(selected, out_shape=fine_shape, transform=transform,
                                     default_value=1, dtype="uint8")
                    totals = grid.reshape(y1 - y0, factor, x1 - x0, factor).sum(axis=(1, 3))
                    counts[band, y0:y1, x0:x1] += totals.astype(np.uint16)
            size += len(table)
        print(f"{source_id}: {len(datasets)} district datasets, {size:,} source polygons", flush=True)
    dominant = (counts.argmax(axis=0) + 1).astype(np.uint8)
    dominant[counts.max(axis=0) == 0] = 0
    with rasterio.open(OUT / "farmmap.tif", "w", **profile) as target:
        target.write(dominant, 1)
        target.update_tags(source_ids=",".join(source_ids), year="2025", classification=json.dumps(
            classes, ensure_ascii=False), resampling="dominant among 25 m agricultural samples")
    print(f"farmmap.tif: {np.count_nonzero(dominant):,} classified cells", flush=True)


def lakes(archive):
    import osmium
    from pyproj import Geod
    from shapely.geometry import mapping
    from shapely.wkb import loads

    source_id = "osm-water"
    with PublicSession() as session:
        direct_file(session, archive, source_id)
    geod = Geod(ellps="WGS84")
    factory = osmium.geom.WKBFactory()
    features = []

    class Water(osmium.SimpleHandler):
        def area(self, area):
            tags = area.tags
            kind = tags.get("water", "")
            if tags.get("natural") != "water" or kind in {"river", "canal", "stream", "basin"}:
                return
            if tags.get("waterway") == "riverbank":
                return
            try:
                geom = loads(bytes.fromhex(factory.create_multipolygon(area)))
            except (RuntimeError, ValueError):
                return
            if geom.is_empty or not geom.is_valid:
                return
            size = abs(geod.geometry_area_perimeter(geom)[0])
            if size < 100_000:
                return
            features.append(feature(mapping(geom), name=tags.get("name:ko") or tags.get("name"),
                                    kind=kind or None, area_m2=round(size), osm_id=area.orig_id(),
                                    osm_type="way" if area.from_way() else "relation",
                                    source_id=source_id, alternative=True))

    handler = Water()
    handler.apply_file(str(RAW / archive.entries[source_id]["file"]), locations=True,
                       idx="flex_mem")
    write_geojson("lakes", features)


def roads(archive):
    import pyogrio
    from pyproj import Transformer
    from shapely import from_wkb, simplify, transform
    from shapely.geometry import mapping

    source_id = "its-nodelink-20261111"
    path = (RAW / archive.entries[source_id]["file"]).resolve()
    fields = ["LINK_ID", "ROAD_RANK", "ROAD_NO", "ROAD_NAME"]
    metadata, table = pyogrio.read_arrow(f"/vsizip/{path.as_posix()}/MOCT_LINK.shp",
                                        columns=fields, where="ROAD_RANK IN ('101', '103')",
                                        encoding="CP949")
    lines = from_wkb(table["wkb_geometry"].to_pylist(), on_invalid="raise")
    convert = Transformer.from_crs(metadata["crs"], 4326, always_xy=True).transform
    lines = transform(simplify(lines, 10), convert, interleaved=False)
    features = []
    grades = {"101": "고속국도", "103": "일반국도"}
    for line, row in zip(lines, table.select(fields).to_pylist(), strict=True):
        if line is None or line.is_empty:
            continue
        rank = row["ROAD_RANK"]
        features.append(feature(mapping(line), rank=rank, grade=grades[rank], route=row["ROAD_NO"],
                                name=row["ROAD_NAME"], link_id=row["LINK_ID"], source_id=source_id))
    write_geojson("roads", features)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = {"landcover": landcover, "farmmap": farmmap, "rivers": rivers,
               "lakes": lakes, "tidal-flat": tidal_flat, "roads": roads}
    parser.add_argument("targets", nargs="*", metavar="TARGET")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    archive = Archive()
    for key in args.targets or actions:
        actions[key](archive)


if __name__ == "__main__":
    main()
