"""Measure place-finding accuracy on geotagged open-licensed Wikimedia Commons photos.

Usage: python spike/eval_online.py [photos_per_city]
Writes demo/eval_results.json.
"""
import json
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from breadcrumbs.geo import distance_m, geocode  # noqa: E402
from breadcrumbs.spark import locate_photo  # noqa: E402

API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "BreadcrumbsHackathonDemo/0.1"}
CITIES = {
    "Eugene OR": (44.0521, -123.0868),
    "Burlington VT": (44.4759, -73.2121),
}
OK_LICENSE = re.compile(r"CC|Public domain", re.I)
SCENE = re.compile(
    r"street|avenue|ave|building|hall|park|church|store|shop|sign|theat|hotel|downtown"
    r"|bridge|library|museum|station|restaurant|cafe|tower|plaza|square|house",
    re.I,
)
PEOPLE = re.compile(r"vs|portrait|player|game|student|children", re.I)
BATCH = 40
RETRIES = 5
RETRY_WAIT_S = 20


def api_query(params: dict) -> dict:
    """Call the Commons API, waiting and retrying when it rate-limits us."""
    for attempt in range(RETRIES):
        time.sleep(RETRY_WAIT_S * attempt + 1)
        response = requests.get(
            API, params={"action": "query", "format": "json", **params},
            headers=HEADERS, timeout=30,
        )
        try:
            return response.json()["query"]
        except (ValueError, KeyError):
            print("retrying:", response.status_code, response.text[:120], flush=True)
    raise RuntimeError("Commons API kept failing")


def city_photos(lat: float, lon: float, limit: int) -> list[dict]:
    """Return open-licensed geotagged photos near a point, with true coordinates."""
    found = api_query(
        {"list": "geosearch", "gscoord": f"{lat}|{lon}", "gsradius": 10000,
         "gslimit": 300, "gsnamespace": 6}
    )["geosearch"]
    scenes = [f for f in found if SCENE.search(f["title"]) and not PEOPLE.search(f["title"])]
    step = max(1, len(scenes) // (limit * 2))  # Spread picks over the whole result list.
    picked = scenes[::step][: limit * 2]
    by_id = {str(f["pageid"]): f for f in picked}
    pages: dict = {}
    for start in range(0, len(picked), BATCH):
        ids = "|".join(str(f["pageid"]) for f in picked[start : start + BATCH])
        pages.update(
            api_query(
                {"pageids": ids, "prop": "imageinfo", "iiprop": "url|extmetadata",
                 "iiurlwidth": 1280}
            )["pages"]
        )
    photos = []
    for page_id, page in pages.items():
        info = page["imageinfo"][0]
        item = by_id[page_id]
        license_name = info.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")
        if item["title"].lower().endswith((".jpg", ".jpeg")) and OK_LICENSE.search(license_name):
            photos.append(
                {"title": item["title"], "url": info["thumburl"], "true": (item["lat"], item["lon"])}
            )
    return photos[:limit]


def check(photo: dict) -> dict:
    """Locate one photo and score it against its true coordinates."""
    try:
        data = requests.get(photo["url"], headers=HEADERS, timeout=30)
        data.raise_for_status()
        data = data.content
        image = Image.open(BytesIO(data)).convert("RGB")
        finding = locate_photo(image)
    except Exception as error:
        return {**photo, "place": "", "error": str(error)[:120]}
    return {**photo, **{k: finding[k] for k in ("place", "confidence", "clue")}}


def summarize(rows: list[dict]) -> dict:
    """Return headline accuracy numbers for a list of scored photos."""
    named = [r for r in rows if r.get("place")]
    errors = [r["error_m"] for r in named if r.get("error_m") is not None]
    return {
        "photos": len(rows),
        "failed": sum("error" in r for r in rows),
        "named": len(named),
        "placed_on_map": len(errors),
        "within_1km": sum(e <= 1000 for e in errors),
        "within_5km": sum(e <= 5000 for e in errors),
        "over_25km": sum(e > 25000 for e in errors),
        "median_error_m": round(statistics.median(errors)) if errors else None,
    }


def main() -> None:
    per_city = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    rows = []
    for city, (lat, lon) in CITIES.items():
        photos = city_photos(lat, lon, per_city)
        with ThreadPoolExecutor(3) as pool:
            checked = list(pool.map(check, photos))
        for row in checked:
            point = geocode(row["place"])
            row["city"] = city
            row["point"] = point
            row["error_m"] = round(distance_m(point, row["true"])) if point else None
        rows += checked
        print(city, summarize(checked), flush=True)
    output = {"all": summarize(rows), "rows": rows}
    (ROOT / "demo" / "eval_results.json").write_text(json.dumps(output, indent=1))
    print("ALL", output["all"])


if __name__ == "__main__":
    start = time.time()
    main()
    print(round(time.time() - start), "seconds")
