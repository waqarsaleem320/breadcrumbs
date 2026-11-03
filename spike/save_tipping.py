"""Scan the demo feed in posting order and save it for the sample tipping point.

Usage: python spike/save_tipping.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from breadcrumbs.tipping import scan_feed  # noqa: E402


def main() -> None:
    images = []
    for file in sorted((ROOT / "demo" / "photos").glob("*.jpg")):
        image = Image.open(file).convert("RGB")
        image.thumbnail((1280, 1280))
        images.append(image)
    start = time.time()
    rows = scan_feed(images)
    for row in rows:
        print(row["posts"], row["level"], row["area"], row["confidence"], row["evidence"])
    print("seconds", round(time.time() - start))
    (ROOT / "demo" / "tipping.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
