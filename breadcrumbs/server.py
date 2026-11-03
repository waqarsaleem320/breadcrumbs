"""Local check service for the Breadcrumbs browser extension.

The extension sends a photo the moment you pick it in a post composer; this
service asks the attacker agent whether that photo links with your feed.
It listens on localhost only and needs the token it prints at start.

Usage: python -m breadcrumbs.server [--sample]
"""
import argparse
import base64
import io
import json
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageOps

from breadcrumbs.agents import ATTACKER_PROMPT, clean_theory, safe_blur
from breadcrumbs.config import SPARK_MODEL
from breadcrumbs.importer import photos_from_export
from breadcrumbs.spark import _client, locate_photo, parse_json
from breadcrumbs.tipping import MAX_FEED, final_theory

PORT = 8765
MAX_BODY = 60_000_000
MAX_EDGE = 1600
DEMO = Path(__file__).resolve().parent.parent / "demo" / "photos"


def open_image(data: bytes) -> Image.Image:
    """Decode, rotate, strip metadata and shrink an uploaded photo."""
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    image.thumbnail((MAX_EDGE, MAX_EDGE))
    return image


QUICK_PROMPT = ATTACKER_PROMPT.split("Finish by")[0] + """Use web search to check public places, then answer once.
Return only JSON: {"area": "<public area or empty>", "city": "<City, State>", "confidence": <0-1>,
"evidence_posts": [<post numbers that support the area>], "reasoning": "<two short sentences>"}"""
QUICK_EDGE = 1024


def _input_image(image: Image.Image) -> dict:
    copy = image.copy()
    copy.thumbnail((QUICK_EDGE, QUICK_EDGE))
    buffer = io.BytesIO()
    copy.save(buffer, "JPEG", quality=85)
    return {"type": "input_image", "image_url": "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()}


def quick_theory(posts: dict[int, Image.Image]) -> dict:
    """One Muse Spark pass with hosted web search: about 40 s, fast enough while posting."""
    content: list = [{"type": "input_text", "text": QUICK_PROMPT}]
    for number, image in posts.items():
        content += [{"type": "input_text", "text": f"Post {number}:"}, _input_image(image)]
    reply = _client().responses.create(
        model=SPARK_MODEL, tools=[{"type": "web_search"}], input=[{"role": "user", "content": content}]
    )
    return clean_theory(parse_json(reply.output_text or ""), set(posts))


def check_post(feed: list[Image.Image], photo: Image.Image, deep: bool = False) -> dict:
    """Ask whether a new photo, added after the feed, links into a pattern."""
    posts = feed[-(MAX_FEED - 1):] + [photo]
    number = len(posts)
    numbered = {i + 1: p for i, p in enumerate(posts)}
    with ThreadPoolExecutor(2) as pool:
        alone_job = pool.submit(locate_photo, photo)
        theory_job = pool.submit(final_theory if deep else quick_theory, numbered)
        alone, theory = alone_job.result(), theory_job.result()
    evidence = theory.get("evidence") or []
    linked = bool(theory.get("area")) and number in evidence and len(evidence) >= 2
    return {
        "linked": linked,
        "area": theory.get("area") or "",
        "evidence": evidence,
        "new_post": number,
        "alone": alone.get("place") or "",
        "reasoning": (theory.get("reasoning") or "")[:400],
        "failed": bool(theory.get("failed")),
        "mode": "deep" if deep else "quick",
    }


class State:
    """The feed held in memory for this run only."""

    def __init__(self, token: str) -> None:
        self.token = token
        self.feed: list[Image.Image] = []


def make_handler(state: State) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: dict | bytes, kind: str = "application/json") -> None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "X-Breadcrumbs-Token, Content-Type")
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self) -> bool:
            sent = self.headers.get("X-Breadcrumbs-Token", "")
            return secrets.compare_digest(sent, state.token)

        def _body(self) -> bytes:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_BODY:
                raise ValueError("Upload too large.")
            return self.rfile.read(length)

        def do_OPTIONS(self) -> None:  # noqa: N802 - http.server naming
            self._send(204, b"", "text/plain")

        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/health":
                return self._send(404, {"error": "Not found."})
            if not self._authorized():
                return self._send(401, {"error": "Wrong or missing token."})
            self._send(200, {"ok": True, "feed": len(state.feed)})

        def do_POST(self) -> None:  # noqa: N802
            if not self._authorized():
                return self._send(401, {"error": "Wrong or missing token."})
            try:
                body = self._body()
                if self.path == "/feed":
                    files = photos_from_export(io.BytesIO(body))
                    state.feed = [open_image(f.getvalue()) for f in files]
                    return self._send(200, {"feed": len(state.feed)})
                if self.path.split("?")[0] == "/check":
                    if not state.feed:
                        return self._send(409, {"error": "Load your feed first, in the extension popup."})
                    start = time.time()
                    result = check_post(state.feed, open_image(body), deep="deep=1" in self.path)
                    return self._send(200, {**result, "seconds": round(time.time() - start)})
                if self.path == "/blur":
                    blurred = safe_blur(open_image(body))
                    if blurred is None:
                        return self._send(422, {"error": "Could not blur this photo safely. Consider not posting it."})
                    out = io.BytesIO()
                    blurred.save(out, "JPEG", quality=90)
                    return self._send(200, {"image": base64.b64encode(out.getvalue()).decode()})
                return self._send(404, {"error": "Not found."})
            except (ValueError, OSError) as error:
                return self._send(400, {"error": str(error)})

        def log_message(self, *_args) -> None:  # Quiet: photos must not end up in logs.
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sample", action="store_true", help="start with the sample feed loaded")
    args = parser.parse_args()
    state = State(secrets.token_urlsafe(16))
    if args.sample:
        demo = sorted(DEMO.glob("*.jpg"))[:2]  # Adding post 3 is what tips the sample feed.
        state.feed = [open_image(p.read_bytes()) for p in demo]
    server = ThreadingHTTPServer(("127.0.0.1", PORT), make_handler(state))
    print(f"Breadcrumbs check service on http://localhost:{PORT}")
    print(f"Paste this token into the extension popup: {state.token}")
    print(f"Feed loaded: {len(state.feed)} photos", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
