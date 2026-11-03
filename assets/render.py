"""Render the logo and README banner to PNG with a headless browser.

Usage: python assets/render.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
LOGO = (HERE / "logo.svg").read_text(encoding="utf-8")
FONTS = (
    '<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,800'
    '&family=Public+Sans:wght@500&display=swap" rel="stylesheet">'
)
BANNER = f"""<html><head>{FONTS}<style>
body {{ margin:0; width:1280px; height:420px; display:flex; align-items:center; gap:48px;
  padding:0 90px; box-sizing:border-box; font-family:'Public Sans',sans-serif; color:#13243a;
  background:#eef1ee; }}
svg {{ width:220px; height:220px; flex:none; }}
h1 {{ font:800 96px 'Bricolage Grotesque',sans-serif; margin:0 0 14px; letter-spacing:-3px; }}
p {{ font-size:30px; margin:0; color:#56677a; line-height:1.35; }}
p b {{ color:#13243a; font-weight:500; }}
</style></head><body>{LOGO}<div><h1>Breadcrumbs</h1>
<p>Each post looks harmless.<br><b>Together, they draw a map.</b></p></div></body></html>"""


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 512, "height": 512})
        page.set_content(f"<html><body style='margin:0'>{LOGO.replace('<svg ', '<svg width=512 height=512 ')}</body></html>")
        page.screenshot(path=HERE / "logo.png", omit_background=True)
        page = browser.new_page(viewport={"width": 1280, "height": 420})
        page.set_content(BANNER, wait_until="networkidle")
        page.screenshot(path=HERE / "banner.png")
        browser.close()


if __name__ == "__main__":
    main()
