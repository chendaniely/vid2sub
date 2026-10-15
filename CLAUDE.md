# vid2sub

A Python CLI (and, from M2, a local web app) that turns videos and YouTube URLs into subtitle
files next to the video. Spec: `docs/superpowers/specs/2026-10-14-vid2sub-design.md`; current
plan: `docs/superpowers/plans/`.

## ⛔ Hard rules

- **Never read or print secrets.** Keys are used by env var name (`key_env` in `vid2sub.toml`).
  Check a variable with `python -c "import os; print(bool(os.environ.get('X')))"`, never its value.
- **Never overwrite an artifact.** The sidecar is append-only; subtitle files are rewritten only
  when the sidecar has a projection record for them (spec §14, §15.3).
- **Pure packages stay pure:** `vid2sub.subs`, `vid2sub.parse`, `vid2sub.catalog` (spec §3.2).
  `tests/test_purity.py` enforces it.
- **One client factory:** only `src/vid2sub/engines/clients.py` imports openai, httpx or chatlas.
- **No titles, paths, tokens or keys in logs or `--json` output** (spec §6.8).
- **Everything runs through uv** (`uv run …`); never `pip install`.

## Commands

- `make setup` · `make test` · `make lint` · `make live` (opt-in tests against real models).

## Check the docs, never write from memory

These change quickly. Before writing code that uses one, read its current docs; say in the
commit what you checked. If the docs don't cover it, say so instead of guessing.

| Library | Docs |
|---|---|
| chatlas | https://posit-dev.github.io/chatlas/ (or the context7 docs tool) |
| openai (transcriptions) | https://platform.openai.com/docs/api-reference/audio |
| pysubs2 | https://pysubs2.readthedocs.io/ |
| yt-dlp | https://github.com/yt-dlp/yt-dlp#usage-and-options |
| whisper.cpp server | https://github.com/ggml-org/whisper.cpp/tree/master/examples/server |
| mlx-qwen3-asr | https://github.com/moona3k/mlx-qwen3-asr |
| opencc-purepy | https://pypi.org/project/opencc-purepy/ |
| onnxruntime | https://onnxruntime.ai/docs/api/python/ |

## Style

- Module docstrings: one sentence of purpose, then why, citing spec sections and who decided.
- British spelling. Test names are sentences. Guard tests must fail without their fix.
- Commits: `type(scope): plain behavioural sentence`; the body says what was checked.
