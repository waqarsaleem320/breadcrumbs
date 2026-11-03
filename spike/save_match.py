"""Run one full match on the demo photos and save it for the sample replay.

Usage: python spike/save_match.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from breadcrumbs.agents import play_match  # noqa: E402

OUTPUT = ROOT / "demo" / "match"


def main() -> None:
    images = []
    for file in sorted((ROOT / "demo" / "photos").glob("*.jpg")):
        image = Image.open(file).convert("RGB")
        image.thumbnail((1280, 1280))
        images.append(image)
    OUTPUT.mkdir(exist_ok=True)
    start = time.time()
    log = []
    round_number = 0
    for event in play_match(images):
        record = {k: v for k, v in event.items() if k not in ("images", "image")}
        if event["kind"] == "round":
            round_number = event["round"]
        if event.get("image"):
            record["photo"] = f"r{round_number}_post{event['post']}.jpg"
            event["image"].save(OUTPUT / record["photo"], quality=88)
        if event["kind"] == "end":
            record["left"] = sorted(event["images"])
            for number, image in event["images"].items():
                image.save(OUTPUT / f"post{number}.jpg", quality=88)
        record["seconds"] = round(time.time() - start)
        log.append(record)
        print(record["seconds"], json.dumps(record)[:240], flush=True)
    (OUTPUT / "match.json").write_text(json.dumps(log, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
