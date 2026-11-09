"""Make demo/'s canned sidecar and subtitle files with the real pipeline and the canned engine.

    make demo-sidecar        (uv run python scripts/demo_sidecar.py)

As recordings' demo/build.py makes its canned archive. vid2sub.web.demo muxes the clip; M1's
pipeline transcribes it with the canned engine (the clip's words) and translates it to Japanese
with the canned translation, exactly as `vid2sub run --from en --to ja` would; then the sidecar,
`jfk.en.srt` and `jfk.ja.srt` are copied into demo/. The MP4 isn't kept: `vid2sub serve --demo`
muxes its own and points the sidecar's header at it.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from vid2sub import pipeline
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.store import sidecar_path
from vid2sub.web import demo

CONFIG = Config.model_validate({
    "endpoints": {"canned": {"base_url": "http://127.0.0.1:9/v1"}},
    "models": {
        "canned": {"endpoint": "canned", "model": "canned-jfk", "parser": "whisper.cpp",
                   "local": True},
        "canned-ja": {"endpoint": "canned", "model": "canned-ja", "task": "translate",
                      "local": True},
    },
})


def main() -> int:
    tools = Tools.find()
    with tempfile.TemporaryDirectory(prefix="vid2sub-demo-build-") as tmp:
        video = Path(tmp) / demo.VIDEO
        demo.mux(tools, video)
        options = pipeline.RunOptions(source_lang="en", targets=["ja"], model="canned",
                                      translate_model="canned-ja", formats=["srt"])
        ctx = pipeline.RunContext(config=CONFIG, tools=tools, keys=KeyRing(environ={}),
                                  options=options, engines={"canned": demo.CannedEngine()})
        pipeline.make_ask = lambda *args, **kwargs: demo.canned_ask  # the canned translation
        result = pipeline.run_one(str(video), ctx)
        if result.status != "done":
            print(f"the pipeline failed: {result.reason}", file=sys.stderr)
            return 1
        for path in (sidecar_path(video), video.with_name("jfk.en.srt"),
                     video.with_name("jfk.ja.srt")):
            shutil.copyfile(path, demo.DEMO / path.name)
            print(f"wrote demo/{path.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
