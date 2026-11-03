"""Page styling and static HTML for the Breadcrumbs interface."""
import base64
import io
from html import escape
from pathlib import Path

from PIL import Image, ImageOps

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Public+Sans:wght@400;500;600&display=swap');
:root { --paper:#eef1ee; --card:#ffffff; --ink:#13243a; --muted:#56677a; --line:#d3dbd7; --contour:#cdd8d2;
  --route:#1d7a72; --pin:#d23a2f; --warn:#b97a0c; --safe:#2c8459; }
html, body, .stApp { background:var(--paper); color:var(--ink); }
.stApp { background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='520' height='520' viewBox='0 0 520 520'%3E%3Cg fill='none' stroke='%23d9e2dd' stroke-width='1'%3E%3Cpath d='M-20 120 C80 60 180 170 300 110 S470 40 560 100'/%3E%3Cpath d='M-20 170 C90 110 190 220 310 160 S480 90 560 150'/%3E%3Cpath d='M-20 330 C100 280 200 380 320 320 S470 260 560 320'/%3E%3Cpath d='M-20 380 C110 330 210 430 330 370 S480 310 560 370'/%3E%3Cpath d='M-20 430 C120 380 220 480 340 420 S490 360 560 420'/%3E%3C/g%3E%3C/svg%3E"); }
[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer { display:none !important; }
.block-container { max-width:1120px; padding-top:1rem; padding-bottom:4rem; }
.stApp, .stApp p, .stApp li, .stApp label, .stMarkdown { font-family:'Public Sans',sans-serif; }
h1,h2,h3 { font-family:'Bricolage Grotesque',sans-serif !important; color:var(--ink) !important; letter-spacing:-.02em; }

.nav { display:flex; align-items:center; gap:12px; padding:16px 0; border-bottom:1px solid var(--line); }
.nav svg { width:36px; height:36px; }
.nav b { font:800 1.3rem 'Bricolage Grotesque',sans-serif; color:var(--ink); letter-spacing:-.02em; }
.nav .made { margin-left:auto; font-size:.85rem; color:var(--muted); }
.nav .made strong { color:var(--ink); font-weight:600; }

.hero { display:grid; grid-template-columns:1fr 1.05fr; gap:56px; align-items:center; margin:36px 0 28px; }
.hero h1 { font-size:4rem; line-height:.98; font-weight:800; margin:0 0 22px; padding:0; letter-spacing:-.035em; }
.hero p { color:var(--muted); font-size:1.15rem; line-height:1.6; max-width:31rem; margin:0; }
.map { width:100%; height:auto; border-radius:18px; background:var(--card); border:1px solid var(--line);
  box-shadow:0 18px 40px -24px rgba(19,36,58,.35); }
.map .contour { fill:none; stroke:var(--contour); stroke-width:1.2; }
.map .route { fill:none; stroke:var(--route); stroke-width:2.5; stroke-dasharray:2 9; stroke-linecap:round;
  stroke-dashoffset:300; animation:draw 2.4s ease-out .3s forwards; }
.map .frame { fill:#fff; stroke:var(--line); }
.map .label { font:600 12px 'Public Sans',sans-serif; fill:var(--muted); }
.map .found { font:700 13px 'Public Sans',sans-serif; fill:var(--pin); paint-order:stroke; stroke:#fff; stroke-width:5px; opacity:0; animation:show .4s ease-out 2.6s forwards; }
.map .pin { fill:var(--pin); transform-origin:center bottom; transform-box:fill-box; opacity:0; animation:drop .45s ease-out 2.4s forwards; }
@keyframes draw { to { stroke-dashoffset:0; } }
@keyframes drop { from { opacity:0; transform:translateY(-14px); } to { opacity:1; transform:none; } }
@keyframes show { to { opacity:1; } }
@media (prefers-reduced-motion: reduce) { .map .route, .map .pin, .map .found { animation:none; opacity:1; stroke-dashoffset:0; } }

.flow { display:grid; grid-template-columns:repeat(4,1fr); gap:0; margin:0 0 34px; border:1px solid var(--line);
  border-radius:14px; background:var(--card); overflow:hidden; }
.flow div { padding:20px 22px; border-right:1px solid var(--line); }
.flow div:last-child { border-right:0; }
.flow small { color:var(--route); font-weight:600; font-size:.85rem; }
.flow b { display:block; font:700 1.08rem 'Bricolage Grotesque',sans-serif; margin:4px 0 6px; }
.flow span { color:var(--muted); font-size:.93rem; line-height:1.5; }

.sec { margin:64px 0 16px; }
.sec small { color:var(--route); font-weight:600; font-size:.9rem; }
.sec h2 { font-size:2.3rem; font-weight:800; margin:4px 0 8px; padding:0; }
.sec p { color:var(--muted); font-size:1.03rem; line-height:1.6; margin:0; max-width:44rem; }

.source { color:var(--muted); font-size:.96rem; line-height:1.6; }
.source b { color:var(--ink); }
.source ol { margin:8px 0 0 1.1rem; padding:0; } .source li { margin:3px 0; }
[data-testid="stTabs"] button[role="tab"] p { font-weight:600; font-size:.98rem; }
[data-testid="stTabs"] [role="tabpanel"] { background:var(--card); border:1px solid var(--line); border-radius:0 0 14px 14px;
  padding:22px 24px; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background:var(--route); }

.tiles { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin:18px 0; }
.tile { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 20px; }
.tile small { color:var(--muted); font-size:.85rem; }
.tile strong { display:block; font:800 2.3rem 'Bricolage Grotesque',sans-serif; color:var(--ink); margin-top:4px; letter-spacing:-.02em; }
.tile.hot strong { color:var(--pin); }
.verdict { border-left:4px solid var(--pin); background:#fbeeec; border-radius:0 12px 12px 0; padding:16px 20px; margin:10px 0; color:var(--ink); }
.verdict.safe { border-color:var(--safe); background:#e9f4ee; }
.verdict b { font:700 1.2rem 'Bricolage Grotesque',sans-serif; display:block; margin-bottom:4px; }
.stButton > button, .stFileUploader button { border-radius:10px; font-weight:600; }
.stButton > button[kind="primary"] { background:var(--ink); color:#fff; border:0; padding:.6rem 1.2rem; }
.stButton > button[kind="primary"]:hover { background:var(--route); color:#fff; }
.stButton > button:focus-visible { outline:3px solid var(--route); outline-offset:2px; }
[data-testid="stImage"] img { border-radius:10px; }
[data-testid="stExpander"] details { background:var(--card); border-color:var(--line) !important; border-radius:12px !important; }
[data-testid="stFileUploaderDropzoneInstructions"] small { display:none; }
[data-testid="StyledFullScreenButton"] { display:none; }
[data-testid="stCaptionContainer"], .stCaption { color:var(--muted) !important; opacity:1 !important; }
.source ol { margin-bottom:12px; }
.hint { color:var(--muted); font-size:.9rem; margin:4px 0 8px; }
.ext { display:flex; gap:16px; align-items:flex-start; background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:18px 20px; margin:6px 0 18px; }
.ext svg { width:40px; height:40px; flex:none; }
.ext b { display:block; font:700 1.05rem 'Bricolage Grotesque',sans-serif; margin-bottom:4px; }
.ext span { color:var(--muted); font-size:.95rem; line-height:1.55; }
.ext code { background:#eef1ee; border-radius:5px; padding:1px 6px; font-size:.85rem; }
.foot { margin-top:80px; padding-top:22px; border-top:1px solid var(--line); color:var(--muted); font-size:.88rem;
  display:flex; gap:12px; align-items:center; }
.foot svg { width:24px; height:24px; flex:none; }
@media (max-width:760px) { [data-testid="stTabs"] [role="tablist"] { flex-wrap:wrap; }
  .tiles { grid-template-columns:repeat(3,1fr); } .tile strong { font-size:1.6rem; } .hero { grid-template-columns:1fr; } .flow { grid-template-columns:1fr; }
  .flow div { border-right:0; border-bottom:1px solid var(--line); } .hero h1 { font-size:2.7rem; } .nav .made { display:none; } }
</style>
"""

_LOGO = (Path(__file__).parent.parent / "assets" / "logo.svg").read_text(encoding="utf-8")
NAV = (
    f'<nav class="nav">{_LOGO}<b>Breadcrumbs</b>'
    '<span class="made">Built with <strong>Muse Spark</strong> and <strong>SAM 3.1</strong></span></nav>'
)
BRAND = NAV


def _thumb(path: Path, size: int = 150) -> str:
    """Return a small square JPEG of a demo photo as a data URL."""
    with Image.open(path) as image:
        image = ImageOps.fit(image.convert("RGB"), (size, size))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def _hero_map() -> str:
    """Draw three real sample posts on a contour map, joined by a route to one pin."""
    photos = sorted((Path(__file__).parent.parent / "demo" / "photos").glob("*.jpg"))[:3]
    spots = [(40, 46, "Post 1"), (40, 222, "Post 2"), (214, 262, "Post 3")]
    frames = "".join(
        f'<rect class="frame" x="{x - 6}" y="{y - 6}" width="112" height="128" rx="8"/>'
        f'<image href="{_thumb(p)}" x="{x}" y="{y}" width="100" height="100" preserveAspectRatio="xMidYMid slice"/>'
        f'<text class="label" x="{x}" y="{y + 116}">{label}</text>'
        for p, (x, y, label) in zip(photos, spots)
    )
    contours = "".join(
        f'<ellipse class="contour" cx="420" cy="170" rx="{40 + 34 * i}" ry="{26 + 24 * i}" transform="rotate(-14 420 170)"/>'
        for i in range(7)
    )
    return f"""<svg class="map" viewBox="0 0 560 420" role="img"
  aria-label="Three posts on a map, joined by a dotted route to one pin">
  {contours}
  <path class="route" d="M146 96 C250 90 330 120 404 156"/>
  <path class="route" d="M146 272 C250 250 330 210 404 170"/>
  <path class="route" d="M320 312 C350 260 380 210 408 176"/>
  {frames}
  <g class="pin"><path d="M420 104c-18 0-30 13-30 29.5 0 21.5 30 52.5 30 52.5s30-31 30-52.5C450 117 438 104 420 104z"/>
  <circle cx="420" cy="133" r="11" fill="#fff"/></g>
  <text class="found" x="336" y="222">Downtown Columbia, MO</text>
</svg>"""


HERO = f"""
<div class="hero">
  <div>
    <h1>Each post looks harmless. Together, they draw a map.</h1>
    <p>Breadcrumbs reads your feed the way a stranger would, shows the exact post where you became
    findable, and breaks the pattern before anyone can follow it.</p>
  </div>
  {_hero_map()}
</div>
<div class="flow">
  <div><small>Step 1</small><b>Check each post</b><span>Muse Spark looks for signs and landmarks, one photo at a time.</span></div>
  <div><small>Step 2</small><b>Find the tipping point</b><span>An attacker agent reads your feed in order and marks the post that gave you away.</span></div>
  <div><small>Step 3</small><b>Break the pattern</b><span>A defender blurs clues with SAM 3.1, checks the blur held, or hides a post.</span></div>
  <div><small>Step 4</small><b>Check before you post</b><span>In the app, or right inside Instagram and Facebook with the browser extension.</span></div>
</div>
"""

EXTENSION = f"""<div class="ext">{_LOGO}<div><b>Check inside Instagram and Facebook</b>
<span>The Breadcrumbs browser extension runs the same check the moment you pick a photo in a post composer.
It warns you if the photo links with your earlier posts, and can swap in a blurred version.
Run <code>python -m breadcrumbs.server</code>, then load the <code>extension</code> folder in Chrome.</span></div></div>"""

FOOT = (
    f'<div class="foot">{_LOGO}<span>Works on your own photos only. Public places, never people or homes. '
    "A model failing to find you is not safety from people.</span></div>"
)


def section(step: str, title: str, text: str) -> str:
    """Return a section heading with its place in the sequence."""
    return f'<div class="sec"><small>{escape(step)}</small><h2>{escape(title)}</h2><p>{escape(text)}</p></div>'


SOURCES = {
    "instagram": """<div class="source"><b>Import from Instagram.</b> Breadcrumbs never asks for your password. It reads the export
Meta gives you, in memory, and stores nothing.<ol>
<li>In Instagram, open Settings, then <b>Accounts Center</b>, then <b>Your information and permissions</b>.</li>
<li>Choose <b>Download your information</b>, your account, <b>Some of your information</b>, then <b>Content</b>.</li>
<li>Pick format <b>JSON</b> and media quality <b>Medium</b>. When the ZIP is ready, upload it here.</li></ol></div>""",
    "facebook": """<div class="source"><b>Import from Facebook.</b> Same idea: upload your own export, in posting order.<ol>
<li>In Facebook, open Settings and privacy, then <b>Accounts Center</b>, then <b>Your information and permissions</b>.</li>
<li>Choose <b>Download your information</b>, your profile, <b>Some of your information</b>, then <b>Posts</b>.</li>
<li>Pick format <b>JSON</b> and media quality <b>Medium</b>. When the ZIP is ready, upload it here.</li></ol></div>""",
}


def tiles(named: int, total: int, clustered: int, to_change: int) -> str:
    """Return the three headline stats."""
    hot = " hot" if clustered else ""
    return f"""<div class="tiles">
      <div class="tile"><small>Posts that name a place</small><strong>{named} of {total}</strong></div>
      <div class="tile{hot}"><small>Posts in the tightest cluster</small><strong>{clustered}</strong></div>
      <div class="tile"><small>Posts to change</small><strong>{to_change}</strong></div>
    </div>"""


def match_tiles(rounds: int, tool_calls: int, moves: int) -> str:
    """Return the match scoreboard."""
    return f"""<div class="tiles">
      <div class="tile"><small>Rounds played</small><strong>{rounds}</strong></div>
      <div class="tile"><small>Attacker tool calls</small><strong>{tool_calls}</strong></div>
      <div class="tile"><small>Defender moves</small><strong>{moves}</strong></div>
    </div>"""


def verdict(title: str, detail: str, safe: bool = False) -> str:
    """Return a highlighted result line with its text escaped."""
    style = "verdict safe" if safe else "verdict"
    return f'<div class="{style}"><b>{escape(title)}</b>{escape(detail)}</div>'


TOOL_LABELS = {
    "search_web": "Searched the web",
    "map_place": "Mapped a place",
    "measure_distance": "Measured a distance",
}


def trace_line(event: dict) -> str:
    """Return one readable line for a match event, with model text escaped."""
    if event["kind"] == "tool":
        label = TOOL_LABELS.get(event["tool"]) or escape(str(event["tool"]))
        detail = " / ".join(str(v) for v in event["args"].values())
        return f'<div class="trace"><b>{label}</b> {escape(detail)}</div>'
    if event["kind"] == "note":
        return f'<div class="trace">{escape(event["text"][:200])}</div>'
    if event["kind"] == "theory":
        if not event["area"]:
            return '<div class="trace win"><b>Attacker found no area</b></div>'
        posts = ", ".join(str(p) for p in event["evidence"])
        return (
            f'<div class="trace hit"><b>Attacker concluded:</b> {escape(event["area"])}'
            f" (from posts {posts})</div>"
        )
    if event["kind"] == "move":
        return (
            f'<div class="trace fix"><b>Defender {event["done"]} post {event["post"]}:</b> '
            f'{escape(event["why"])}</div>'
        )
    return ""


LEVEL_TEXT = {
    "hidden": "Not findable",
    "place": "Names one place",
    "pattern": "Found",
    "failed": "Run failed",
}


def tipping_chart(rows: list[dict], tipping: int | None) -> str:
    """Return one bar per feed length: how sure the attacker was, and what it found."""
    lines = []
    for row in rows:
        sure = int((row.get("confidence") or 0) * 100) if row["level"] != "hidden" else 0
        found = escape(row.get("area") or "")
        mark = '<em>gave you away</em>' if row["posts"] == tipping else ""
        lines.append(
            f'<div class="tip {row["level"]}"><span class="tip-n">{"Post 1" if row["posts"] == 1 else f"Posts 1-{row['posts']}"}</span>'
            f'<span class="tip-bar"><i style="width:{max(sure, 2)}%"></i></span>'
            f'<span class="tip-t"><b>{LEVEL_TEXT[row["level"]]}</b> {found} {mark}</span></div>'
        )
    legend = '<div class="tip-legend">Bar length is how sure the attacker was.</div>'
    return '<div class="tips">' + "".join(lines) + legend + "</div>"


TRACE_CSS = """
<style>
.tips { margin:10px 0 18px; background:var(--card); border:1px solid var(--line); border-radius:12px; padding:6px 18px; }
.tip { display:grid; grid-template-columns:90px 1fr 1.5fr; gap:16px; align-items:center; padding:10px 0; border-bottom:1px solid var(--line); }
.tip:last-of-type { border-bottom:0; }
.tip-legend { color:var(--muted); font-size:.8rem; padding:8px 0 4px; border-top:1px solid var(--line); }
.tip-n { color:var(--muted); font-size:.88rem; }
.tip-bar { background:#e7ece9; border-radius:5px; height:12px; overflow:hidden; }
.tip-bar i { display:block; height:100%; background:var(--safe); }
.tip.place .tip-bar i { background:var(--warn); }
.tip.pattern .tip-bar i { background:var(--pin); }
.tip.failed .tip-bar i { background:var(--line); }
.tip-t { font-size:.92rem; color:var(--muted); }
.tip-t b { color:var(--ink); font-weight:600; margin-right:6px; }
.tip-t em { font-style:normal; color:#fff; background:var(--pin); font-weight:600; font-size:.78rem;
  border-radius:5px; padding:2px 7px; margin-left:6px; white-space:nowrap; }
@media (max-width:760px) { .tip { grid-template-columns:70px 1fr; } .tip-t { grid-column:1 / -1; } }
.trace { font-size:.93rem; color:var(--muted); padding:8px 12px; border-left:2px solid var(--line); margin:3px 0; }
.trace b { color:var(--ink); font-weight:600; }
.trace.hit { border-color:var(--pin); background:#fbeeec; color:var(--ink); }
.trace.fix { border-color:var(--route); background:#e6f2f0; color:var(--ink); }
.trace.win { border-color:var(--safe); background:#e9f4ee; }
</style>
"""
