# vid2sub

Subtitles for videos and YouTube, made on your own machine. vid2sub extracts the audio,
transcribes it with timestamps in the video's language, translates it, and writes SRT (and
optionally ASS) next to the video, named the way Plex and Jellyfin expect. It runs models on
your computer, on a machine you run (such as a DGX Spark), or, only when you allow it for a run,
on OpenAI.

Status: Phase 1 (M1, the command line) is built; Phase 2 (M2, the web editor) is being planned.
Design: [`docs/superpowers/specs/2026-10-14-vid2sub-design.md`](docs/superpowers/specs/2026-10-14-vid2sub-design.md),
whose Outline and Scenarios say what is built. Diagrams:
[`docs/architecture.md`](docs/architecture.md). How it is built: [`AGENTS.md`](AGENTS.md).
Changes: [`CHANGELOG.md`](CHANGELOG.md).

## Install

You need [uv](https://docs.astral.sh/uv/), ffmpeg 6 or later, and, for YouTube, deno 2.3 or later.
Some Linux distributions ship an older ffmpeg (such as 4.x), so use a newer package or a static
build; `vid2sub doctor` tells you.

| | macOS (Apple Silicon, 14+) | Windows | Linux |
|---|---|---|---|
| uv | `brew install uv` | `winget install astral-sh.uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| ffmpeg | `brew install ffmpeg` | `winget install Gyan.FFmpeg` | your package manager |
| deno | `brew install deno` | `winget install DenoLand.Deno` | `curl -fsSL https://deno.land/install.sh \| sh` |

Then install the CLI from a clone (release wheels arrive with M4). None of this needs Node:

```bash
git clone https://github.com/chendaniely/vid2sub && cd vid2sub
uv tool install --editable '.[mac]'   # on a Mac: Qwen3-ASR in-process
uv tool install --editable .          # elsewhere
vid2sub doctor
```

`--editable` follows your clone, so `git pull` updates it. To work inside the project's own
environment instead: `uv sync --extra mac` and `uv run vid2sub …`.

## Configure

`vid2sub config init` prints a starter `vid2sub.toml` and `vid2sub config path` says where
vid2sub looks for it. Save the starter there, then edit it.

On macOS and Linux:

```bash
mkdir -p "$(dirname "$(vid2sub config path)")"
vid2sub config init > "$(vid2sub config path)"
```

On Windows (PowerShell), create the folder and save the starter the same way:

```powershell
$path = vid2sub config path
New-Item -ItemType Directory -Force (Split-Path $path) | Out-Null
vid2sub config init | Out-File -Encoding utf8 $path
```

`vid2sub.toml` names endpoints and models; it never holds a key, only the *names* of the
environment variables that do. Put keys in your shell's environment (on macOS and Linux, a file
your shell sources; on Windows, `setx NAME value` and a new terminal).

- **The DGX Spark:** start local-ai's tunnel (`make tunnel`, see local-ai's
  `website/how-to/pi.md`) and export `SPARK_API_KEY`. The starter config points at
  `http://127.0.0.1:9100/v1`.
- **OpenAI:** export `OPENAI_API_KEY`. Cloud models are used only on runs with `--allow-cloud`.
- **LM Studio or Ollama** (for translation): add an endpoint with its OpenAI-compatible URL.

## Use

```bash
vid2sub run "Show - S01E02.mkv" --to en              # detect the language, transcribe, translate
vid2sub run ~/TV/Show/Season\ 1 --from yue --to en   # a whole season, Cantonese
vid2sub run ~/TV/Show --recursive --skip-existing     # carry on where a run stopped
vid2sub run https://youtu.be/VIDEO_ID --to none       # captions in the video's own language
vid2sub detect ~/TV/Show/Season\ 1                    # detect each file's language, nothing else
vid2sub import fansub.srt --video ep1.mkv --lang ja   # use an existing SRT as the source
vid2sub translate ep1.mkv --to zh-Hant --stale-only   # translate only what changed
vid2sub write ep1.mkv --format ass                    # add ASS files from the sidecar
vid2sub models                                        # what can run on this machine now
```

Add `--dry-run` to `run` to see what would happen without writing anything.

A `vid2sub.glossary.toml` in a show's folder helps with names:

```toml
description = "Detective Conan, a Japanese anime"
[terms]
"工藤新一" = "Shinichi Kudo"
```

Files written next to `Show - S01E02.mkv`: `Show - S01E02.ja.srt`, `Show - S01E02.en.srt`
(Cantonese is `.zh-HK`, Mandarin `.zh-CN` or `.zh-TW`), and `Show - S01E02.vid2sub.jsonl`, the
sidecar that keeps every version. vid2sub never overwrites a subtitle file it didn't write.

Exit codes: 0 done; 1 an input failed (including a missing tool during `run`); 64 usage;
69 `vid2sub doctor` found an essential tool missing; 75 interrupted or a connection dropped
(run the same command with `--skip-existing`); 78 a settings problem.

## Models

<!-- models:start -->
| Model | Task | Good for | Weak spots | Runs on |
|---|---|---|---|---|
| Qwen3-ASR 1.7B + ForcedAligner 0.6B | transcribe | Mandarin and Cantonese by a wide margin (Qwen's numbers: WenetSpeech-Yue long 8.85 vs Whisper large-v3's 46.64); strong English; Hong Kong and Guangdong accents; vocabulary context | Japanese is supported but has no published benchmark | Mac (mlx-qwen3-asr); the Spark once local-ai serves it |
| Qwen3-ASR 0.6B + ForcedAligner 0.6B | transcribe | the same languages as the 1.7B, lighter and faster | less accurate than the 1.7B | Mac (mlx-qwen3-asr) |
| Whisper large-v3 | transcribe | Japanese (until compared with Qwen3-ASR), 99 languages, vocabulary prompt | slower than turbo; poor on Cantonese | Windows/Linux (faster-whisper, M3); the Spark if local-ai adds it |
| Whisper large-v3-turbo | transcribe | English → English captions, quick drafts | weaker on Cantonese and tonal languages; no translate task | the Spark (always loaded); Windows/Linux from M3 |
| OpenAI whisper-1 | transcribe | a cloud fallback in any language | 25 MB per request (vid2sub's chunks fit); the audio leaves your machine | OpenAI |
| Gemma 4 26B-A4B | translate | Japanese → English, general translation; always loaded on the Spark, two slots | — | the Spark |
| Qwen3.8 27B | translate | Mandarin and Cantonese → English | on the Spark it's Dan's coder: loads on demand, one slot, 41 GiB | the Spark |
| A local chat model | translate | translation on your own machine (LM Studio, Ollama, vLLM) | quality depends on the model you load | your machine |
| OpenAI GPT | translate | a cloud fallback for translation | the text leaves your machine | OpenAI |
<!-- models:end -->

Upgrade yt-dlp when YouTube changes: `uv tool upgrade vid2sub --upgrade-package yt-dlp`.

## Develop

```bash
make help     # list the targets
make setup    # uv sync --group dev
make test     # pytest (media tests need ffmpeg)
make check    # everything CI checks: the suite, again under UTC, lint, the leak scan
make lint
make live     # opt-in tests against real models; see tests/README.md
make readme   # refresh the model table above from the catalog
```
