# Tests

- `uv run pytest` runs everything except live tests. Tests marked `media` need ffmpeg and
  ffprobe; they skip without them unless `VID2SUB_REQUIRE_FFMPEG=1` (CI sets it).
- Live tests (`uv run pytest -m live`) use real models and networks, opt-in:
  - `VID2SUB_LIVE_MLX=1` on an Apple Silicon Mac with `uv sync --extra mac`: Qwen3-ASR on the
    speech fixture (downloads the model on first run).
  - `VID2SUB_LIVE_SPARK=1` with local-ai's `make tunnel` running and `SPARK_API_KEY` exported:
    the Spark's whisper.cpp and Gemma 4.
  - YouTube: set VID2SUB_LIVE_YOUTUBE_URL to a short public-domain video's link (no URL is built in); the test downloads its audio.
- Fixtures are synthetic or public domain (`tests/fixtures/CREDITS.md`).
