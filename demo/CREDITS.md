# The demo

`vid2sub serve --demo` (`make demo`) serves a fresh copy of this folder. It holds no video: at
start-up vid2sub muxes `tests/fixtures/speech/jfk-14s.wav` under a still picture into `jfk.mp4`
in the copy. `make demo-sidecar` remakes the sidecar and subtitles here with the real pipeline
and the canned engine in `src/vid2sub/web/demo.py`.

| File | Source | License |
|---|---|---|
| `jfk.mp4` (made at start-up) | 14 s from 0:30 of "JFK at Rice University", https://commons.wikimedia.org/wiki/File:Jfk_rice_university_we_choose_to_go_to_the_moon.ogg (via `recordings`' demo, as `tests/fixtures/speech/jfk-14s.wav`) | Public domain (John F. Kennedy Presidential Library & Museum) |
| `jfk.vid2sub.jsonl`, `jfk.en.srt` | the clip's words with their times from `recordings`' demo transcript of the same speech (local Whisper output, `demo/canned/transcripts/jfk-rice.json` at 8deb039), cut into cues by vid2sub | Public domain speech; the transcript is Dan's, MIT here |
| `jfk.ja.srt` | a Japanese translation written for this demo | MIT |
