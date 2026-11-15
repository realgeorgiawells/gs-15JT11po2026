"""Builds one self-contained preview page (data and logo inlined) from site/ for screenshots."""
import base64, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
site = ROOT / "site"
html = (site / "index.html").read_text()
data = {k: json.loads((site / "data" / f"{k}.json").read_text()) for k in ("today", "coverage", "history")}
logo = "data:image/svg+xml;base64," + base64.b64encode((site / "logo.svg").read_bytes()).decode()
html = html.replace('src="logo.svg"', f'src="{logo}"')
html = html.replace("<script>\n(function(){", "<script>window.__GS__=" + json.dumps(data) + ";</script>\n<script>\n(function(){", 1)
out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "preview.html"
out.write_text(html)
print("wrote", out)
