"""Muse Spark call: find the public place, if any, that one photo reveals."""
import base64
import io
import json

from openai import OpenAI
from PIL import Image

from breadcrumbs.config import BASE_URL, SPARK_MODEL, load_key

LOCATE_PROMPT = """You are a privacy self-audit tool. The user uploaded their own photo so they
can see which public place it reveals before posting it. Use only visible signs, logos, and
landmarks. Do not identify any person and do not guess where anyone lives.
Return only JSON: {"place": "<searchable public place, city, state, or empty>",
"confidence": <0-1>, "clue": "<the visible detail>",
"noun": "<1-2 common words naming that object, e.g. sign, logo, tower>",
"box_2d": [ymin, xmin, ymax, xmax]} with box values on a 0-1000 grid."""
MIN_CONFIDENCE = 0.86  # Set on 60 test photos: removed all 4 wrong-city answers.


class NoAnswer(Exception):
    """Spark refused or returned something unreadable."""


def _client() -> OpenAI:
    return OpenAI(api_key=load_key(), base_url=BASE_URL)


def _image_part(image: Image.Image) -> dict:
    """Encode a PIL image as an OpenAI-style content part."""
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=88)
    data = base64.b64encode(buffer.getvalue()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}


def parse_json(text: str) -> dict:
    """Extract the outermost JSON object from model text; empty dict if none."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


def clean_finding(raw: dict) -> dict:
    """Normalize a reply; a weak or empty answer means no place was named."""
    try:
        confidence = float(raw.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    place = str(raw.get("place") or "") if confidence >= MIN_CONFIDENCE else ""
    finding = {
        "place": place,
        "confidence": confidence,
        "clue": str(raw.get("clue") or ""),
        "noun": str(raw.get("noun") or "sign"),
        "box_2d": None,
    }
    try:
        ymin, xmin, ymax, xmax = (min(1000, max(0, int(v))) for v in raw["box_2d"])
    except (KeyError, TypeError, ValueError):
        return finding
    if place and ymax > ymin and xmax > xmin:
        finding["box_2d"] = [ymin, xmin, ymax, xmax]
    return finding


def locate_photo(image: Image.Image) -> dict:
    """Return the place one photo reveals; raise NoAnswer on a refusal."""
    content = [{"type": "text", "text": LOCATE_PROMPT}, _image_part(image)]
    reply = _client().chat.completions.create(
        model=SPARK_MODEL, messages=[{"role": "user", "content": content}]
    )
    parsed = parse_json(reply.choices[0].message.content or "")
    if not parsed:
        raise NoAnswer("Spark refused or returned an unreadable reply.")
    return clean_finding(parsed)


def pixel_box(box_2d: list[int], image: Image.Image) -> tuple[int, int, int, int]:
    """Convert a 0-1000 [ymin, xmin, ymax, xmax] box to pixel left, top, right, bottom."""
    ymin, xmin, ymax, xmax = box_2d
    w, h = image.size
    return (xmin * w // 1000, ymin * h // 1000, xmax * w // 1000, ymax * h // 1000)
