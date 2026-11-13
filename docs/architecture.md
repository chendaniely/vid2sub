# vid2sub: architecture

Every diagram of vid2sub lives on this page; the spec
(`docs/superpowers/specs/2026-10-14-vid2sub-design.md`) and the other docs link here rather than
drawing their own copy. Built parts are solid; planned parts are dashed and labelled with the
phase that brings them.

## Three ways to run it

The CLI and the local web app call the same core; the Pages editor runs the pure subtitle code in
the browser and can't generate subtitles (spec §3.1).

```mermaid
flowchart LR
  subgraph user["User's machine"]
    term["Terminal<br/>vid2sub run · detect · translate"]
    browser["Browser<br/>React UI"]
    web["vid2sub serve<br/>FastAPI + Shiny on 127.0.0.1"]
    core["vid2sub core library<br/>media · engines · subs · translate"]
    tools["ffmpeg · ffprobe · yt-dlp + deno"]
    mlx["In-process engine<br/>mlx-qwen3-asr (Mac)"]
    fw["In-process engine<br/>faster-whisper<br/>(Phase 3)"]
    files[("Video folder<br/>video · .vid2sub.jsonl · .xx.srt")]
  end
  spark["DGX Spark: the front at 127.0.0.1:9100/v1<br/>(through make tunnel, or on the Spark itself)<br/>whisper.cpp · Gemma 4"]
  sparkqwen["DGX Spark<br/>Qwen3-ASR + forced aligner<br/>(Phase 2, once local-ai serves it)"]
  cloud["OpenAI<br/>models only with --allow-cloud"]
  pages["GitHub Pages<br/>Shinylive editor<br/>(Phase 4)"]
  term --> core
  browser -->|"websocket + token cookie"| web
  web --> core
  core --> tools
  core --> mlx
  core -.-> fw
  core <--> files
  core -->|"chunks, cue text; Test: its model list"| spark
  core -.->|"chunks"| sparkqwen
  core -->|"chunks, cue text (--allow-cloud); Test: its model list, on a click"| cloud
  pages -.->|"File System Access"| files
  classDef planned stroke-dasharray: 5 5
  class fw,sparkqwen,pages planned
```
