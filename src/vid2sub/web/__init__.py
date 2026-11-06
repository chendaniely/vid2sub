"""The local web app: the editor's backend, the app shell and its server (spec §19)."""

from pathlib import Path

# The built frontend (`ui.js`, `ui.css`) and its fonts, which `vid2sub serve` needs (spec §18).
WWW = Path(__file__).parent / "www"
