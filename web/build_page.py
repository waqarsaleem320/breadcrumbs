"""Write index.html: the sample demo running in the visitor's browser with stlite.

Usage: python web/build_page.py   (run from the repo root, after any change to the app files)
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STLITE = "https://cdn.jsdelivr.net/npm/@stlite/browser@1.12.0/build"
APP_FILES = ("app.py", "breadcrumbs/", "demo/", "assets/logo.svg", "assets/logo.png")
SKIP = ("breadcrumbs/server.py",)


def app_files() -> list[str]:
    """Return the tracked files the app reads at run time."""
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [f for f in tracked.split() if f.startswith(APP_FILES) and f not in SKIP]


def main() -> None:
    files = {f: {"url": f} for f in app_files()}
    files["openai/__init__.py"] = {"url": "web/stubs/openai/__init__.py"}
    files["meta_sam_parser/__init__.py"] = {"url": "web/stubs/meta_sam_parser/__init__.py"}
    options = {
        "entrypoint": "app.py",
        "requirements": ["pydeck", "requests"],
        "files": files,
        "streamlitConfig": {
            "theme.base": "light",
            "theme.primaryColor": "#1d7a72",
            "theme.backgroundColor": "#eef1ee",
            "theme.secondaryBackgroundColor": "#ffffff",
            "theme.textColor": "#13243a",
            "client.toolbarMode": "minimal",
        },
    }
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Breadcrumbs: live demo</title>
<link rel="icon" href="assets/logo.png">
<link rel="stylesheet" href="{STLITE}/stlite.css">
<style>
  body {{ margin: 0; background: #eef1ee; font-family: system-ui, sans-serif; color: #13243a; }}
  #loading {{ max-width: 640px; margin: 18vh auto; padding: 0 16px; text-align: center; }}
  #loading img {{ width: 72px; height: 72px; }}
  #loading p {{ color: #56677a; line-height: 1.5; }}
</style>
</head>
<body>
<div id="loading">
  <img src="assets/logo.png" alt="">
  <h1>Breadcrumbs</h1>
  <p>Loading the demo in your browser. The first visit takes about 20 to 40 seconds while Python starts up.
  It runs the saved sample; checking your own photos needs the full app (see the README).</p>
</div>
<div id="root"></div>
<script type="module">
  import {{ mount }} from "{STLITE}/stlite.js";
  const options = {json.dumps(options, indent=1)};
  mount(options, document.getElementById("root"));
  new MutationObserver((_, observer) => {{
    if (document.querySelector("#root .stApp, #root [data-testid='stAppViewContainer']")) {{
      document.getElementById("loading").remove();
      observer.disconnect();
    }}
  }}).observe(document.getElementById("root"), {{ childList: true, subtree: true }});
</script>
</body>
</html>
"""
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    print(len(files), "files mounted")


if __name__ == "__main__":
    main()
