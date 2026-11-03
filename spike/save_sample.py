"""Audit the demo photos one at a time and save it for the sample view.

Usage: python spike/save_sample.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from breadcrumbs.geo import geocode  # noqa: E402
from breadcrumbs.spark import locate_photo  # noqa: E402


def main() -> None:
    findings = []
    for file in sorted((ROOT / "demo" / "photos").glob("*.jpg")):
        image = Image.open(file).convert("RGB")
        image.thumbnail((1600, 1600))
        finding = {**locate_photo(image), "checked": True}
        finding["point"] = geocode(finding["place"])
        print(file.name, finding["place"] or "-", finding["confidence"])
        findings.append(finding)
    (ROOT / "demo" / "sample_result.json").write_text(json.dumps(findings, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
