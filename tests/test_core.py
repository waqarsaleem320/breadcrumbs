"""Run: python tests/test_core.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from breadcrumbs.agents import (  # noqa: E402
    clean_moves,
    clean_theory,
    is_misled,
    match_winner,
    padded,
)
from breadcrumbs.geo import (  # noqa: E402
    distance_m,
    posts_to_fix,
    routine_area,
    search_names,
    tightest_cluster,
)
from breadcrumbs.tipping import level, tipping_post  # noqa: E402
from breadcrumbs.importer import photos_from_export  # noqa: E402
from breadcrumbs.spark import clean_finding, parse_json, pixel_box  # noqa: E402

# Routine area
assert routine_area([]) is None
assert routine_area([(38.95, -92.33)]) is None
area = routine_area([(38.95, -92.33), (38.96, -92.33)])
assert area["places"] == 2 and 500 < area["radius_m"] < 600
far = routine_area([(38.95, -92.33), (38.96, -92.33), (38.96, -92.34), (40.0, -80.0)])
assert far["places"] == 3  # A geocoding mistake must not inflate the circle.
assert 1000 < distance_m((38.95, -92.33), (38.96, -92.33)) < 1200

spots = {0: (38.95, -92.33), 1: (38.951, -92.33), 2: (38.99, -92.33)}
assert tightest_cluster(spots) == [0, 1]
assert len(posts_to_fix(spots)) == 1 and posts_to_fix(spots)[0] in (0, 1)
assert posts_to_fix({}) == [] and posts_to_fix({0: (38.95, -92.33)}) == []
trio = {0: (38.95, -92.33), 1: (38.951, -92.33), 2: (38.952, -92.33)}
assert not tightest_cluster({k: v for k, v in trio.items() if k not in posts_to_fix(trio)})

assert search_names("A, B, City, MO") == ["A, B, City, MO", "A, City, MO", "B, City, MO"]
assert search_names("A, MO") == ["A, MO"]
assert search_names("A, City, MO") == ["A, City, MO"]  # Never just the city center.

# Spark replies
assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
assert parse_json("I can't help with that.") == {}
weak = clean_finding({"place": "X", "confidence": 0.2, "box_2d": [1, 2, 3, 4]})
assert weak["place"] == "" and weak["box_2d"] is None
good = clean_finding({"place": "X", "confidence": "0.9", "box_2d": [1.5, 2, 3, 2000]})
assert good["place"] == "X" and good["box_2d"] == [1, 2, 3, 1000]
assert clean_finding({"place": "X", "confidence": 0.9, "box_2d": [5, 5, 5, 9]})["box_2d"] is None
assert clean_finding({"place": "X", "confidence": "high"})["place"] == ""

# Agents
weak_theory = clean_theory({"area": "X", "confidence": 0.3, "evidence_posts": [1]}, {1, 2})
assert weak_theory["area"] == "" and weak_theory["evidence"] == []
theory = clean_theory({"area": "X", "confidence": 0.9, "evidence_posts": [1, 9, "a"]}, {1, 2})
assert theory["area"] == "X" and theory["evidence"] == [1]
odd = clean_theory({"area": "X", "confidence": 0.9, "evidence_posts": [[1], 2.0, "1"]}, {1, 2})
assert odd["evidence"] == [1, 2]
assert clean_moves("bad", [3]) == [{"post": 3, "action": "hide", "why": "Fallback move."}]
moves = [{"post": 3, "action": "blur"}, {"post": 3, "action": "hide"}, {"post": 9, "action": "blur"}]
assert [m["action"] for m in clean_moves(moves, [3])] == ["blur"]

assert match_winner({"area": "", "evidence": [], "timed_out": True}) == "inconclusive"
assert match_winner({"area": "", "evidence": []}) == "defender"
assert match_winner({"area": "X", "evidence": [1]}) == "defender"
assert match_winner({"area": "X", "evidence": [1, 2]}) is None

assert clean_theory({"area": "X", "city": "A, MO", "confidence": 0.9}, {1})["city"] == "A, MO"
assert is_misled((38.95, -92.33), (39.17, -86.53))
assert not is_misled((38.95, -92.33), (38.96, -92.33))
assert not is_misled(None, (38.96, -92.33)) and not is_misled((38.95, -92.33), None)

# Tipping point
assert level({"area": ""}) == "hidden"
assert level({"failed": True}) == "failed"
assert level({"area": "X", "evidence": [1]}) == "place"
assert level({"area": "X", "evidence": [1, 2]}) == "pattern"
rows = [{"posts": 1, "level": "place"}, {"posts": 2, "level": "hidden"}, {"posts": 3, "level": "pattern"}]
assert tipping_post(rows)["posts"] == 3
assert tipping_post(rows[:2])["posts"] == 1
assert tipping_post([{"posts": 1, "level": "hidden"}]) is None

# Boxes
box = pixel_box([100, 200, 300, 400], Image.new("RGB", (1000, 500)))
assert box == (200, 50, 400, 150)
assert padded((100, 100, 200, 120), (1000, 500)) == (85, 97, 215, 123)
assert padded((0, 0, 100, 100), (100, 100)) == (0, 0, 100, 100)
# Instagram/Facebook export import: posting order from the JSON, not file order.
import io  # noqa: E402
import json  # noqa: E402
import zipfile  # noqa: E402


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "JPEG")
    return buf.getvalue()


export = io.BytesIO()
with zipfile.ZipFile(export, "w") as z:
    z.writestr("media/posts/b.jpg", _jpeg())
    z.writestr("media/posts/a.jpg", _jpeg())
    z.writestr("media/other/x.jpg", _jpeg())
    posts = [{"media": [{"uri": "media/posts/b.jpg", "creation_timestamp": 200}]},
             {"media": [{"uri": "media/posts/a.jpg", "creation_timestamp": 100}]},
             {"media": [{"uri": "media/posts/missing.jpg", "creation_timestamp": 50}]}]
    z.writestr("your_instagram_activity/content/posts_1.json", json.dumps(posts))
assert [f.name for f in photos_from_export(export)] == ["a.jpg", "b.jpg"]
try:
    photos_from_export(io.BytesIO(b"not a zip"))
    raise AssertionError("bad zip accepted")
except ValueError:
    pass
print("ok")
