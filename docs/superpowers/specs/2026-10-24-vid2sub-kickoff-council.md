# vid2sub: the kickoff council

The kickoff council (plan-driven-development, `references/phase-end.md`, *Councils*) on the spec,
`AGENTS.md` and the Phase 2, 3 and 4 plans, before Dan's approval. Four read-only reviewers, one
per lens, 2026-10-24, on `phase-2` at `cc54452`. Their reports follow as they wrote them, before
anyone acted on them. Two edits were made so nothing private is committed: a scratch folder's
absolute path is now "the session's scratch `clones/` folder", and a home-relative path to the
skill is now the skill's own name. The clone paths they cite (`final/`, `p3final/`, `p4b/`) are
those scratch builds of the plans' listings, which aren't in the repository.

Phase 4's listings were being replayed onto Phase 3's finished code while the council read them,
so the reviewers were told not to report Phase 4's anchors and counts against Phase 3's code, nor
the dot-named staging bug moving from Phase 4 Task 3 into Task 1.

What became of each finding (checked against the plans and code it cites, then fixed, put on a
phase-end list, moved to Later, or put to Dan) is in the commits that follow this one.

## Kickoff council: goal fit and scenarios

The three plans build what §25 asks of each phase. Every row from S22 to S53, plus S63, has a task in the phase §25 gives it, and each proof is a named test in a listing or an exit-test step. The weak spots are in the exit tests and the cross-phase decisions. Phase 2's exit test never saves a retranslation. It also measures "whisper.cpp" timing on an episode that is probably Qwen3-ASR's. And Phase 2 can't finish until local-ai serves Qwen3-ASR. Three things the spec promises have no task and aren't on the Later list, and one Phase 3 Decision describes the app wrongly. No Criticals.

Paths used below: **spec** = `docs/superpowers/specs/2026-10-14-vid2sub-design.md`; **P2**, **P3**, **P4** = `docs/superpowers/plans/2026-10-23-vid2sub-phase-{2,3,4}.md`.

### Findings

#### 1. Phase 2 can't close until local-ai serves Qwen3-ASR, and S22 is marked verified with no Cantonese audio (Important)
- **Where:** P2:31888–31889, P2:31930, P2:33132–33138, P2:33295–33298; spec:62 (S22), spec:1522–1523.
- **Evidence:**
  - Spec §25: "**In parallel (local-ai, Dan's call):** the Qwen3-ASR service on the Spark … Until it exists, Mandarin and Cantonese use the Mac engine."
  - Task 20, Step 21: "If Step 1 found no Qwen3-ASR, wait here … until Dan says local-ai serves it". No step says what happens if it never does. Under `AGENTS.md`, nothing starts until a task's closing commit, so Tasks 21–24 wait too.
  - Only an English JFK clip is required (`record English jfk-14s.en.json`). A Cantonese clip is "only if Dan has a public-domain one".
  - Even so, the close sets S22, "a Cantonese episode through the Spark's Qwen3-ASR …", to `verified`.
- **Why it matters:** the editor phase (M2) is held up by another repo's schedule, for a scenario that isn't in §25's M2 exit test. Separately, S22 would read `verified` although the Spark never got Cantonese audio. That includes the claim that it accepts Qwen's language name "Cantonese" (P2:32518 tests this only against a fake server).
- **Fix:** add a branch to Task 20. If local-ai doesn't list Qwen3-ASR when Steps 2–20 are done, close the task with S22 at `built` (the documented-shape fixture and the fake-server tests), and move Steps 21–23 to a follow-up that Dan schedules. Set S22 to `verified` only once a Cantonese answer has been recorded. Otherwise reword S22's situation to the language that was actually checked.

#### 2. Phase 2's exit test never saves after "Retranslate stale" (Important)
- **Where:** P2:34262–34274; spec:26, spec:1508–1509; P2:7887 and P2:24037 (a retranslation is an unsaved, undoable edit).
- **Evidence:**
  - §25 M2 exit test: "open an M1 episode, fix lines, retranslate stale cues, save".
  - Task 23 runs Step 4 "fix … then Save", then Step 5 "**Retranslate stale**", which has no Save. Step 6 then edits the `.en.srt` outside and reopens the episode.
- **Why it matters:**
  - Nothing proves that a retranslation gets written to the sidecar and the SRT.
  - Step 6 reopens the episode while the retranslation is still unsaved in the tab, so Dan gets a close warning or a draft offer, and either may throw away the step that was being tested.
  - S30 would be set to `verified` on output that was never written to disk.
- **Fix:** in Step 5, add "then **Save**. Expected: the `.en.srt` now holds the new English." Step 6 then edits that saved file.

#### 3. The §29 "whisper.cpp tokens without DTW" timing check will probably measure Qwen3-ASR (Important)
- **Where:** P2:34232–34233, P2:34257, P2:34276–34298; P2:213–249; spec:1642–1643, spec:846–849; `src/vid2sub/catalog.py:93–101`.
- **Evidence:**
  - §29 asks for "the real cue-timing quality of whisper.cpp tokens without DTW, against a hand-corrected episode".
  - Task 23 Step 3 says only "type the path of an episode Task 1 made", and Step 8 compares the cues against the first `auto` head without checking which engine made it.
  - Under M1's routes and the starter config, Task 1's Cantonese run (`--from yue`), its Japanese runs (detection, and the `--from ja` season) all go to `mac-qwen`. Japanese's first choice, `whisper-large-v3`, isn't configured.
  - Only the English YouTube run (Step 6) and the optional `--model spark-turbo` copy in Step 4 use whisper.cpp.
- **Why it matters:** §29 would record Qwen3-ForcedAligner's timing as whisper.cpp's. That answer feeds §26.1 item 5 (whether DTW is worth local-ai's effort).
- **Fix:**
  - In Task 1, make Step 4's `--model spark-turbo` run required.
  - In Task 23, Steps 3–4 must use that episode.
  - Step 8 should print the transcript's `engine`/`model` and refuse to run unless it is `whisper.cpp`.

#### 4. Phase 3 keeps Phase 2's Jobs-page path box, which skips Add's checks; Decisions 1 and 2 describe the app wrongly (Important)
- **Where:** P3:27–34 (Decisions 1, 2), P3:3101, P3:9007–9008, P3:9606–9607, P3:16334; P2:29684–29687; spec:1246–1247.
- **Evidence:**
  - Decision 1: "a typed path through one [a link] is refused … a media folder linked into home … is added from the app by its real path under `/Volumes`, or from the CLI."
  - Decision 2: "a Linux library under `/srv` is added from the CLI, not the app."
  - Add does take typed paths only "through browse.expand's checks". But Phase 3 Task 6 keeps the `jobs-paths` box ("Videos to make subtitles for: one full path a line"), and its `jobs_submit` accepts any fully qualified path (P2:29684). The Phase-end row at P3:16334 even counts on "the Jobs page's typed paths".
  - Decision 2 also narrows §19.2's "**Add** (local only): paste paths" without the "This changes the spec" flag.
- **Why it matters:** Dan would approve a rule ("links and paths outside the roots stay out of the app") that the same app breaks one screen over. Linux users get a confusing split: Add refuses `/srv/tv/...`, and Jobs accepts it with no Review.
- **Fix:** choose one, and record it as a Decision:
  - **(a)** in Phase 3, route `jobs_submit` through `browse.expand` too, or remove the box now that Add exists;
  - **(b)** reword Decisions 1 and 2 to say the Jobs box stays as the way around Add.
  
  Either way, flag Decision 2 against §19.2.

#### 5. Spec §6.6's "the UI asks per file" isn't built and no Decision records that (Important)
- **Where:** spec:538–539; P2:4545–4548, P2:6110, P2:22638; P2:31–123 (no Decision covers it). P4 Task 1 inherits the same Save through `web.folder` (P4:166–169).
- **Evidence:**
  - Spec: "never overwrite a file vid2sub didn't write … **the UI asks per file**, the CLI needs `--overwrite-foreign`".
  - The plans' Save always leaves such a file alone ("`foreign` is left alone … and reported"), and no screen offers to replace it.
- **Why it matters:** suppose a downloaded or Bazarr `.en.srt` sits next to a video. However often the person saves, the editor and the Pages editor can never write vid2sub's English there. The only way out is `vid2sub write --overwrite-foreign`, which no notice mentions. This quietly narrows the spec.
- **Fix:**
  - **(a)** Build the per-file confirm: a native `<dialog>` naming the file, then `overwrite_foreign` for that file only. Phase 4's Chrome Save needs the same.
  - **(b)** Or add a Decision marked "This changes the spec" (§6.6), and have the save notice name `vid2sub write --overwrite-foreign`.

#### 6. Two spec promises have no task and aren't on the Later list (Important)
- **Where:** spec:651–652 (§8.3), spec:812–813 (§10 step 6), spec:96–108 (Later). A grep of all three plans for re-link/orphan, and for the first-chunk re-check, finds nothing that builds either.
- **Evidence:**
  - §8.3: "it can re-link an orphaned sidecar after a rename by identity".
  - §10 step 6: "Each job re-checks its first chunk's language and flags a disagreement in the editor rather than stopping." M1's pipeline does neither (`src/vid2sub/pipeline.py` warns only on a changed video, at :249–258).
- **Why it matters:**
  - Renaming episodes, as Sonarr and Plex workflows do, leaves the sidecar named after the old stem. The editor then opens the renamed video with no subtitles: nothing is lost, but nothing is found either.
  - A folder that inherits one sampled language never flags the episode that is in another.
  - Neither is on Later, so P4's phase end, step 5 (P4:13816–13818), which offers only the Later rows, would never raise them with Dan.
- **Fix:** for each, either add a task (re-link fits Phase 2's open path; the first-chunk check fits Phase 3 Task 3 or 5 with an editor badge), or move it to Later with a reason. Dan decides.

#### 7. Phase 3's exit test: no hand-back step, and Step 5 assumes a Spark transcription the default routes won't give (Minor)
- **Where:** P3:16127–16128, P3:16137–16140, P3:16160–16166, P3:16171–16194, P3:16205–16207.
- **Evidence:**
  - Step 1 lists Steps "2 to 7" as Dan's, but unlike P2 Task 1 (Step 8), P2 Task 23 (Step 7) and P4 Task 11 (Step 6), no step says what Dan hands back. Step 9 then sets S38–S42 to verified "where they passed".
  - Step 5 starts: "while an episode is transcribing on the Spark, stop the tunnel". But a Cantonese or Japanese season routes to `mac-qwen` unless Phase 2 Task 20's `spark-qwen` exists or Dan picks `spark-turbo` in Review, and Step 4 asks him to change only a target.
  - The task header says it covers §29's "CUDA's libraries for faster-whisper on Windows", but Step 7 allows "whichever machine you have", Linux or CPU only. It doesn't say the check stays pending then, and doesn't mention installing ffmpeg and git on Windows first.
- **Why it matters:** Dan may be unable to do Step 5 as written, and §29's M3 line could be marked done when it wasn't.
- **Fix:**
  - Add "Step 8: [Dan] Hand back the notes from Steps 2–7" (and renumber).
  - In Step 4, have Dan pick a Spark model for at least one row, or let Step 5 say "transcribing or translating on the Spark".
  - In Step 9, keep §29's Windows CUDA line *pending* unless Step 7 ran on Windows with an NVIDIA GPU.
  - In Step 7, list the Windows prerequisites.

#### 8. Phase 4 Decision 15 promises a live Cache-Control check that no step runs (Minor)
- **Where:** P4:91–93; P4:13683–13785 (Task 11); P4:13863–13867 (step 9a).
- **Evidence:** "GitHub's docs don't say, so Task 11 checks it on the live site." Task 11 tests only the local build. Step 9a checks that the deploy is green and repeats the Chrome save, with no header check.
- **Why it matters:** Review Focus 3 (a visitor's cached Shinylive assets) relies on the `max-age=600` that `make pages-serve` imitates. If the live site sends something else, nobody finds out.
- **Fix:** add to step 9a: `curl -sSI https://chendaniely.github.io/vid2sub/ | grep -i cache-control`, with the answer recorded in §29's M4 bullet. Then fix Decision 15 to name step 9a.

#### 9. Phase 2 Task 1 drops one of the M1 checks it was meant to run, and misses two smaller ones (Minor)
- **Where:** spec:112–115, spec:1643, spec:1655, spec:45 (S05); P2:213–220, P2:231–233, P2:252–260.
- **Evidence:**
  - Open items lists "whether ffmpeg 6.0 is the right floor" among M1's checks and says "All run in Phase 2's first task". Step 9's list leaves it out, and no later task picks it up (Dan's Mac has ffmpeg 9.0.2).
  - S05 includes `.en`, but Step 5 checks only `zh-CN`/`zh-TW`/`zh-HK`/`ja` in Jellyfin.
  - Step 3's `time vid2sub run` times the whole run, translation on the Spark included, not "Qwen3-ASR's speed".
- **Why it matters:** §29 ends up with a "pending" that nothing will close, and Open items' "all run" isn't true.
- **Fix:**
  - Either name a task for the ffmpeg floor (say, a CI job on Ubuntu 22.04's ffmpeg 4.4 to show it fails, plus the floor recorded from what 24.04's 6.1 shows), or move it to Later.
  - Add `.en` to Step 5.
  - Have Step 3 take the transcribe stage's time from `--json` events.

#### 10. The Scenarios table still lacks task numbers, and three Proof cells name files no plan creates (Minor)
- **Where:** spec:36–37, spec:62–94; P2:4479, P2:7840, P2:29606.
- **Evidence:**
  - The spec says "Later phases' task numbers are filled in when their plans are written". The plans are written, but every Phase 2–4 row still reads just "Phase N".
  - S29 and S32 cite `tests/test_save.py`, S31 `tests/test_external.py` and S35 `tests/test_settings.py`. The plans make `test_backend_save.py`, `test_backend_open.py` and `test_web_settings.py` instead, and fix the cells only at each task's close. P2:4479 even says "a file that doesn't exist".
- **Why it matters:** Dan approves a spec that names proofs that won't exist. A resuming agent reading S29's proof can't find it.
- **Fix:** before approval, fill in each row's "Phase and task" from the plans' Scenarios lines, and correct the three Proof names. Each close then only changes the status.

#### 11. §25's M1 bullet lists two things M1 didn't build (Minor)
- **Where:** spec:1486–1491; `src/vid2sub/cli.py` (no `cache` command), `src/vid2sub/config.py:66` (`parser: Literal["whisper.cpp", "openai"]`).
- **Evidence:**
  - The bullet lists "`config init` and `cache clear`" among M1's commands, and "the endpoint engine (Spark whisper.cpp, OpenAI, `mlx-qwen3-asr serve`)".
  - `cache clear` moved to Phase 2 (Q&A item 13; built by P2 Task 3), and the Qwen endpoint parser is P2 Task 20.
- **Why it matters:** the spec gives the wrong scope for a phase that's already done.
- **Fix:** take both out of M1's bullet and name them under M2.

#### 12. Phase 3 Decision 23 (30 s, then pause) works against "run it unattended" overnight (Minor)
- **Where:** P3:89–92, P3:9013–9020; spec:27, spec:82 (S42), spec:1130–1132.
- **Evidence:**
  - The Decision's own stated cost: "a short overnight blip pauses the queue until someone presses Resume."
  - Its reasons include that "the M3 exit test (Task 12, Step 5) expects the banner within a minute".
  - §17.3 says only that connection errors pause the queue. It sets no 30 s limit.
- **Why it matters:** M3's goal is a season "run unattended" overnight (S42). A 30-second tunnel blip at 2 a.m. would leave the night's queue undone. The CLI rides out ten minutes.
- **Fix:** offer Dan two options: a longer app wait (such as 120 to 300 s, with Step 5's wait adjusted to match), or a queue that resumes itself once the endpoint answers again. Don't let the exit test's convenience set the default.

### Unconfirmed
- S43's "plays straight away": P2 Task 3 makes the whole `.m4a` before returning a path (P2:1063–1066). For a long AC-3 episode on a network share, that could mean a noticeable wait before any sound. I couldn't confirm a timing from the listings; Task 23 Step 3 will show it.
- Phase 4's `browser_runtime` must cover the Runtime parts Phase 3 adds (`roots`, `listing`, `expand`, `add`, `make_preview`, Review). That's part of the replay in flight, so not checked.

### Checked and fine
- Scenario → task, in the phase §25 gives it:
  - Phase 2: S22 (T20), S23 (T9, T11), S24 (T8, T9), S25 (T8), S26 (T8, T12–T14), S27 (T5, T10, T14, T23), S28 (T2, T6, T15), S29 (T6, T16, T23), S30 (T7, T17, T23), S31 (T5, T16, T23), S32 (T6, T16), S33 (T15), S34 (T16), S35 (T18), S36 (T4, T19), S37 (T14, T15, T19), S43 (T3, T10, T23), S46 (T3).
  - Phase 3: S38 (T1, T2), S39 (T2), S40 (T3, T4), S41 (T5, T6), S42 (T5), S44 (T8), S45 (T9, T10), S63 (T7).
  - Phase 4: S47 (T1–T3, T11, step 9a), S48 (T3, T11), S49 (T4), S50 (T2, T5, T7, T11), S51 (T7, T9, step 9d), S52 (T8, step 9c), S53 (T6).
- Statuses: S01–S20 `built`, S21 `verified` and the rest `planned` match the definitions; each close step sets its rows' status.
- Proof files the plans do create: `test_web_auth`, `test_web_guards`, `test_cache`, `test_playback`, `test_edit`, `test_browse`, `test_review`, `test_jobs`, `test_awake` (M1's, extended in P3 T5) and `test_preview`. Each appears in a task's Files and listing.
- §25 scope against the plans:
  - M2: shell, guards, CSP, editor, retranslate, external edits, drawer, Jobs, playback audio and cache.
  - M3: Add/Browse/YouTube, detect→suggest→confirm, Models, pause/resume, awake, preview, faster-whisper.
  - M4: Pages, demo, `release.yml`, index, README.
  - All have tasks, apart from the findings above.
- §20's editor list (find and replace with add to glossary, practice aids at 0.75×/1×/1.25×, the keyboard model, IME safety, Save) is built in P2 T14–T16.
- P2 Task 1 covers each of §25's four M1 exit-test bullets. P4 Task 11 and step 9 together cover §25's M4 exit test.
- Phase 3's Review Focus lines each have a test in the listings (for example P3:3244, P3:4960–4973, P3:14653, P3:14713).
- Phase 2 → 3 interfaces I spot-checked match: Task 19's `job_runner`, `Runtime.job_context`, `Queue.on_change -> stop`, `JobView.stopping`, and Task 18's `Session`. `pipeline.Paused` and `awake.keep_awake` already exist in M1.
- Each flagged spec change (P2 #21; P3 #1, #10, #19, #20; P4 #2, #3, #5, #9) does change the spec text it names. P4 #2's reasoning (a release created with `GITHUB_TOKEN` starts no `release: published` run) matches the GitHub rule the plan quotes; I didn't fetch the page again.
- The demo's targets stay consistent from P2 Decision 29 `("ja",)` through P4 Round 5b's `("en",)` (P4:9144).
- These [Dan] steps say what to run, what to expect and what to hand back: P2 T1 Steps 2–8, P2 T20 Step 1, P2 T23 Steps 2–7, P4 T5 Steps 1 and 10, P4 T7 Step 14, P4 T11 Steps 2–6 and P4 step 9.
- I found nothing large built that the spec didn't ask for. The extras are small and recorded as Decisions: P3's person-pressed Pause, which fits §17.1's `paused(reason)`; the demo's Add; and P2's extra keys.

## Kickoff council: reliability

The plans get the single-writer case right. Every file write is atomic, the projection record is
appended before its file, a write cut short is recognised as vid2sub's own, and the browser's
write is all or none. The gaps show up when two things happen at once, or when the episode is
reopened after a crash. The sidecar's compare-and-swap still leaves a window that nothing locks.
The crash draft can't replay edits to cues made by split, merge or insert. Two tabs share one
draft. Safari's download path tells the person to replace the sidecar by hand. Unattended runs
stop for good on a short connection blip, and fail every episode in turn when the NAS share
drops. The workflow can't resume a task mid-way from git alone. Paths to the reference clones
below are relative to the session's scratch `clones/` folder.

### Findings

#### 1. The sidecar's compare-and-swap can still lose a writer's records, and Phase 2 adds a second writer in the same process (Critical)
- **Where:** `final/src/vid2sub/store.py:109-121` (`append`); `final/src/vid2sub/web/backend.py:136, 231, 295-297` (the per-video lock, editor only); `p3final/src/vid2sub/pipeline.py:626, 705, 717` (the job's appends, which don't take that lock); `final/tests/test_store.py:58-76`; Phase 2 plan 4508 (Task 6, S32), 6827-6829, 29629 (Task 19, the Jobs page).
- **Evidence:** spec §14.6 (line 1030) says "Just before replacing, re-read the hash; if it changed, merge … and retry". `append` re-reads, compares, then calls `safe_write`, which writes the whole sidecar, fsyncs it and runs `os.replace`. A writer that replaces the file inside that window is overwritten. M1's guard test injects the other writer during `serialize`, before the re-check, so the window after the re-check is never tested. Phase 2's backend says "no other writer's records are lost" (plan 6828). But the editor's Save runs on an `asyncio.to_thread` thread while a Jobs-page job runs on the queue's worker thread. Both call `store.append` on the same sidecar with no shared lock, and a CLI batch beside `serve` (§18.3: "Running both at once is safe") has no lock either.
- **Why it matters:** the loss is silent. Save parses the bytes it wrote, so the editor shows "saved", empties undo and clears the draft, and on the next open the edits are gone. A lost projection record turns vid2sub's own SRT into "someone else's file", which is refused from then on. The window is a whole-file write plus an fsync: hundreds of ms for a 0.5–1 MB sidecar on an SMB share, which is where Dan's seasons live. A Save pressed as a job reaches its write stage hits it.
- **Fix:** in `store.append` (and around `project`'s append and write), take a process-wide lock keyed by the sidecar's real path (`os.path.realpath` + `normcase`, or `(st_dev, st_ino)` of its folder). Across processes, either use an advisory lock file next to the sidecar (create it with `O_EXCL`, treat it as stale after N seconds, and `msvcrt` on Windows), or verify after replacing: re-read and check every record of yours is there, and if not, merge and write again. Add a guard test that has another writer replace the file between the re-check and `safe_write`'s replace (monkeypatch `security._replace`). It must fail on today's code.

#### 2. Restoring a crash draft loses every edit made to a cue that split, merge or insert created (Critical)
- **Where:** `final/src/vid2sub/subs/model.py:80-85` (`new_cue_id` is `secrets.token_hex`); `final/src/vid2sub/subs/edit.py:118, 120, 133, 153, 257-261`; `final/frontend/src/components/Editor.tsx:236-243`; Phase 2 plan 84-88 (Decisions 17, 18), 23016, 23278-23281 / 26333-26335 (`onRestore`), 22443-22450 (S34's test).
- **Evidence:** Decision 18 says "The crash draft is a replay of the tab's edits". The draft stores each op as sent, with the cue ids the crashed session's server made. When the draft is replayed, split, merge and insert make new random ids, so a later `set_text` or `set_times` on the old id fails with "there is no cue c…". Decision 17 makes this the everyday path: "Insert makes a cue reading '…' and opens it for editing". The text typed into the new cue is a separate `set_text` on its new id. `onRestore` clears the draft before replaying, so whatever fails is gone for good. S34's Playwright test edits only cues that already exist, so it passes.
- **Why it matters:** S34 ("the localStorage draft is offered back") is the only safety net for unsaved edits. After any insert, split or merge, it brings back "…" placeholders and loses the corrected halves.
- **Fix:** have the client propose the new ids in the op: `Split{…, ids:[a,b]}`, `MergeNext{…, id}`, `Insert{…, id}`. The server checks the `^c[0-9a-f]{8}$` shape and that each id isn't in `taken` (edit functions take the id instead of drawing one), so a replay is deterministic. Clear the draft only after the replay ends with no refused step. Add an e2e test: insert and type, split and edit a half, merge and edit, crash, restore, and check that every text is back.

#### 3. Two tabs on one episode share one crash draft, and each clears the other's (Important)
- **Where:** Phase 2 plan 22493 (`draftKey`: heads only); `final/frontend/src/App.tsx:60-84` (moving or clearing the draft on Save, and "editing again without restoring: the old draft is discarded").
- **Evidence:** the key is `vid2sub.draft.` + the heads. Two tabs opened at the same heads, which is S32 and Review Focus 4's case, write to one key. Each tab's steps interleave in it. Tab B, opened while A has unsaved edits, is offered A's live draft, and editing in B without restoring clears it. A Save in either tab moves the heads and clears the key, wiping the other tab's crash copy.
- **Why it matters:** if one of the two tabs then crashes, the restore replays the other tab's steps, or nothing at all. The two-tab case the plan names in Review Focus 4 is exactly where S34 breaks.
- **Fix:** key the draft by heads plus a tab id kept in `sessionStorage`. On open, offer every draft for these heads with its time. A tab clears only its own key.

#### 4. Safari's Save tells the person to replace the sidecar and SRTs by hand, which undoes append-only (Important)
- **Where:** Phase 4 plan 13437-13439 (README), 13730-13735 (Task 11 Step 4), 4752-4754; Decision 7 (63-65); spec §18.1 (lines 1193-1195), §14.1 (lines 965-967).
- **Evidence:** "Put them next to the video, replacing the old ones." The downloaded sidecar is built on "the files the episode last saw", read when the folder was opened. Spec §14.1 says "Records are never edited or removed; a merge of two writers is the union of their records by id". Spec §18.1 already plans for this case: `vid2sub write` is for use "after a Pages save in a browser that could only download the sidecar".
- **Why it matters:** anything written since the open is lost when the file is replaced: a `vid2sub translate --stale-only`, a Save in `vid2sub serve` (which Task 11 Step 3 has Dan do), or a Chrome Save in another window. The downloaded SRTs also overwrite edits made since the open in Aegisub or Bazarr, which the local engine refuses to overwrite (`EditedOnDisk`). The person, following the README, overwrites the artifact the rule exists to protect.
- **Fix:** offer only the sidecar, plus a CLI step that merges it: union the downloaded sidecar's records into the one next to the video, then run `vid2sub write`, whose `project` honours foreign and edited files. For example `vid2sub write VIDEO --merge DOWNLOADED.jsonl`, or an `import --sidecar`. This changes §21 and S48, so it is Dan's call. Until then the README should say to replace the files only if nothing else touched the episode since it was opened.

#### 5. Chrome's Save re-reads the sidecar before the permission check, so a permission prompt sits inside the compare-and-swap window (Important)
- **Where:** Phase 4 plan 7443-7447 (the page's re-read, then `into.write`), 5066-5069 (`writeAll` queries, then `requestPermission`), 4741-4744 ("Just before it writes, the page reads the sidecar once more"); `p4b/frontend/src/lib/folder.ts:116-131`, `p4b/frontend/src/App.tsx:205-212`.
- **Evidence:** the page hashes the sidecar and only then calls `writeAll`, which asks for permission. The permission request comes after Python's merge, past the Save click. The plan's own reading says it "needs transient activation". So it either fails at once, or opens a prompt that can stay up to Python's 285-second deadline while the re-read result goes stale.
- **Why it matters:** anything another writer does to the sidecar while the prompt is open is overwritten. Review Focus 1's revoked permission is the case where it happens.
- **Fix:** check permission on the Save click itself (in the button handler, before the merge is asked for), and move the sidecar re-read into `writeAll`, after the permission check and immediately before the writables open. Compare once more just before the sidecar's `close()`.

#### 6. The install index can go empty on any push to `main`, and the smoke job then skips instead of failing (Important)
- **Where:** Phase 4 plan 12481-12484 ("a different form shows as an empty index, which Task 12's step 9c catches"), 13096 and 13171 (`if: needs.build.outputs.wheels != '0'`), 13278; Decision 20 (110-113).
- **Evidence:** `build_index` silently leaves out any asset whose `digest` isn't `sha256:<hex>`, or that is null. Step 9c catches that once, at the first release. `pages.yml` rebuilds and redeploys the index on every push to `main`. If an API change or a transient null leaves it empty, it deploys, and the smoke job is skipped because `wheels` is `0`.
- **Why it matters:** every `uv tool install` and `uv tool upgrade` from the index breaks, with every check green (S51).
- **Fix:** `build_index` exits non-zero, so nothing deploys, when the listing has a published `v` release with a `vid2sub-<version>-py3-none-any.whl` asset but the wheel isn't indexed. Gate the smoke job on "a release exists", not on `wheels != '0'`.

#### 7. A NAS share that drops during the queue fails every remaining episode in turn (Important)
- **Where:** spec §17.3 (lines 1130-1132); Phase 3 plan 16160-16162 (Task 12 Step 5), Review Focus 1 (124-126, listing only); `p3final/src/vid2sub/jobs.py:20-25` ("Any other error fails only its job").
- **Evidence:** §17.3 says connection errors "pause the whole queue … instead of failing every remaining episode in turn". The exit test itself says "Turning the Wi-Fi off would also drop the NAS share, which is a different failure", and no task handles it while a queue runs. ffmpeg's read error, the input's "must exist" check and an `OSError` at write all fail only that job, so the next episode on the same share fails the same way.
- **Why it matters:** M3's exit test is a NAS season run overnight. One Wi-Fi blip drops both the tunnel and the share, and the morning shows every remaining episode failed.
- **Fix:** when an input's or output's folder can't be reached (the folder is gone, `EHOSTDOWN`, `ETIMEDOUT`, `ENOTCONN`, `EIO`; on Windows `ERROR_NETNAME_DELETED` or `BAD_NETPATH`), pause the queue with "the folder isn't reachable" instead of failing the job. Add a test that removes the season folder mid-job.

#### 8. Overnight runs stop for good after a 30-second blip (Important)
- **Where:** Phase 3 plan 89-92 (Decision 23, `APP_WAIT_S = 30`), 48-49 (Decision 9: the machine may sleep while paused); `p3final/src/vid2sub/web/runtime.py:69`; spec §25 M3 exit ("run it unattended").
- **Evidence:** "The cost: a short overnight blip pauses the queue until someone presses Resume." With Decision 9, the Mac then sleeps for the rest of the night. A tunnel restart or a Spark reboot easily takes longer than 30 s.
- **Why it matters:** an unattended season run can do nothing from the first blip until morning, and S41's own test passes only because Dan presses Resume.
- **Fix (Dan's call):** while the queue is paused on a connection error (never on the person's own Pause), probe the endpoint's `/v1/models` on a backoff (30 s up to 15 min) for a bounded time, say 2 h. Resume automatically when it answers, and keep the machine awake while probing. Or keep the CLI's 600 s in the app.

#### 9. A task can't be resumed mid-way from the plan and git alone, and a re-run Step 0 hides the task's own commits from its review (Important)
- **Where:** `AGENTS.md:90` (resume at the first task with no closing commit), `AGENTS.md:111` (record the base), `AGENTS.md:128` (boxes ticked only at the close); every task's Step 0 (Phase 2 plan 196, 344, 1074 …; Phase 3 7782; Phase 4 4807); the phase ends' "resume at the first unticked box" (Phase 3 plan 16256-16257, Phase 4 13794-13795); plan-driven-development's `references/plans.md:88`.
- **Evidence:** build commits stage only code (`git add src/… tests/…`, e.g. Phase 2 plan 1006), so a task's boxes stay unticked until its close. Step 0 (`git rev-parse HEAD > .git/TASK_BASE`) overwrites the base unconditionally. After a crash or compaction there is no wip commit, so an executor following the boxes re-runs Step 0, which records a base past the task's own commits, and then re-runs Step 1, whose test no longer fails. The tier review "from `$(cat .git/TASK_BASE)`" then misses those commits.
- **Why it matters:** the review can quietly cover only part of the task, which is exactly when the earlier, pre-crash work most needs it.
- **Fix:** Step 0 writes `Task N <sha>`, and is skipped when `.git/TASK_BASE` already names Task N or a `Plan: … Task N` commit exists after the last close. A safer base: the previous task's close commit (`git log -1 --format=%H --grep='close Task <N-1>:'`, anchored so Task 1 doesn't match Task 10). Each build commit names its step (a `Step: K` line in the body), and `AGENTS.md`'s Resume step 6 says to resume after the last named step. The fix belongs in the skill's template too.

#### 10. The app's Windows path never runs end to end, in CI or by hand (Important)
- **Where:** Phase 2 plan 33407, 33425 (`frontend` and `e2e` run on `ubuntu-24.04`); `p3final/.github/workflows/ci.yml:114` (e2e, Ubuntu only); Phase 3 plan 16171-16194 (Task 12 Step 7: `doctor`, `models`, `vid2sub run` only); spec Outline (line 27): "add, review and run seasons from the app, on macOS, Windows and Linux".
- **Evidence:** Windows runs the Python suite and the `whisper` job only. Nothing runs `vid2sub serve` there.
- **Why it matters:** the redirect file through `webbrowser.open(page.as_uri())`, Browse's drive letters and UNC shares, `/media/` Range requests on NTFS, and Save's sharing-violation retry (§6.6) against Plex or antivirus holding an SRT are all unproven on the platform Phase 3 claims.
- **Fix:** extend Step 7 with `vid2sub serve`: Browse a drive or share, Add, Review, Start, open the result in the editor, edit, then Save with the SRT open in another program. Or add a windows-2022 entry to `e2e` (Playwright's Chromium runs there).

#### 11. A browser Save that fails after the sidecar is in place, or lands late, leaves the tab on the old heads (Minor)
- **Where:** Phase 4 plan 13912 (Phase-end list: only the notice is wrong); `p4b/src/vid2sub/web/server.py:392-416` (only `ok` keeps the saved episode); `p4b/frontend/src/lib/folder.ts:131` (the deadline is checked only before writes start).
- **Evidence:** the sidecar closes first. If a later close fails, or the writes run past the server's 300 s, the sidecar on disk holds the new version while the tab still has the old heads and the edits as unsaved.
- **Why it matters:** the next Save, after more edits, makes a version whose parent is the old head, beside the version already on disk. The person gets a conflict between two of their own versions.
- **Fix:** the page reports which files it placed. When the sidecar is among them, the server keeps the saved episode and lists the subtitle files it couldn't write.

#### 12. The per-video write lock is keyed by the path as typed (Minor)
- **Where:** `final/src/vid2sub/web/backend.py:136, 295-297`; `final/src/vid2sub/security.py:135-140` (`resolve_input` doesn't resolve).
- **Evidence:** `/Volumes/TV/x.mkv` and `/Volumes/tv/x.mkv` (case-insensitive APFS or NTFS), or a path through a linked folder, get two locks. The dict also grows for the engine's lifetime.
- **Fix:** fold this into Finding 1's lock and key it by the real path, normalised for case (or by `(st_dev, st_ino)`).

#### 13. Some tests wait on fixed sleeps (Minor)
- **Where:** Phase 2 plan 22443 / `p3final/tests/e2e/test_saving.py:167` (`a.wait_for_timeout(500)` before asserting the `beforeunload` dialog); `p3final/tests/test_web_server.py:433, 751, 918, 924`, `p3final/tests/test_jobs.py:340` (sleep, then assert nothing happened).
- **Evidence:** on a loaded runner the dialog can take longer than 500 ms, so that test flakes. The negative checks pass trivially when the server is slow, so on a slow machine those guards don't fail without their fix (§22.1).
- **Fix:** use `page.expect_event("dialog")`. For the negative checks, send a later request through the same queue, wait for its answer, then assert the earlier one didn't apply.

#### 14. Pages' deploy concurrency: Decision 18's "none cancelled" isn't what GitHub does (Minor)
- **Where:** Phase 4 plan 104-106 (Decision 18), 9597-9600, 10378; `p4b/.github/workflows/pages.yml:22-24`.
- **Evidence:** GitHub's "Control workflow concurrency" page says that with `cancel-in-progress` not true, "any existing `pending` job or workflow in the same concurrency group will be canceled". A `queue: max` option exists to keep up to 100 pending runs.
- **Why it matters:** in practice it's harmless, since each run rebuilds the site and the index from `main` and the API, and the newest wins. But the plan's claim is wrong.
- **Fix:** reword it ("an in-progress deploy is never cancelled; a waiting one gives way to a newer one"), or add `queue: max` if every run must deploy.

#### 15. A whole-episode Retranslate holds the tab's queue with no Cancel (Minor)
- **Where:** `p3final/src/vid2sub/engines/clients.py:195` (300 s per call); `p4b/src/vid2sub/web/server.py:453-462` ("Edits sent meanwhile wait their turn").
- **Evidence:** on a slow or busy Spark, every edit and Save in the tab waits behind the retranslation, for minutes per batch, until it ends or times out.
- **Why it matters:** the person can't even save the edits they already made.
- **Fix:** add a Cancel checked between batches (as jobs have), or let Save jump ahead of a running retranslation, since it needs only the tracks as they are.

### Unconfirmed
- **A stale `index.html` or `start.js` for up to 10 minutes after a Shinylive bump:** `start.js` revalidates the list it carries, but the page and `start.js` are exempt (`p4b/tests/pages/test_pages_site.py:117-125`: "The page itself is a navigation"). If Chrome serves a fresh-cached main document and module script on a link navigation without revalidating, the old `start.js` runs the new `shinylive.js`, which is the mixed version Review Focus 3 rules out. One fix would be a no-cache fetch of a build id in `start.js`, reloading when it differs. Not checked in a browser.
- **The shared thread pool:** `runtime.blocking` uses `asyncio.to_thread`, the loop's default pool (min(32, CPUs+4) threads). Preview encodes (up to 4 h), the playback audio (up to 1 h), retranslations, and `stat` calls on a hung SMB mount all share it, so a few tabs could starve every other tab's Save. I didn't confirm that the preview encode goes through `blocking`.
- **Safari's download names:** if `~/Downloads` already holds an earlier Save's files, Safari renames the new ones, and the person may move the stale set. I didn't check Safari's naming.

### Checked and fine
- `safe_write`: temp file with `O_EXCL | O_NOFOLLOW`, fsync, `os.replace`, symlink refusal, and Windows sharing-violation retry (`p3final/src/vid2sub/security.py:62-96`).
- The projection record goes in before its file; a file holding any earlier projection hash counts as vid2sub's own interrupted write (`store.projected_digests`); a failed write puts the previous record back.
- The playback audio is written under a temporary name and renamed, so a half-made file is never served (`final/src/vid2sub/media/preview.py:32-41`). Eviction never touches the key in use, and errors are ignored.
- The chunk cache is keyed by quick hash, audio track, model, language, chunk plan hash and vocabulary, so Resume after redoing decode and VAD can't reuse a chunk that doesn't match (`p3final/src/vid2sub/pipeline.py:577-584`).
- Retry classification: a timeout counts as `server` (two retries); a refused or reset connection waits, then raises `Paused`. A Mac that sleeps mid-chunk ends up paused, not failed, once the retry meets the refused tunnel.
- The browser's Save starts no write after Python stops waiting (the deadline less a margin), and `writeAll` aborts and removes files it created when a write fails.
- The e2e server binds port 0 and reports its real port, so there's no free-port race, and the harness polls `/healthz`.
- `release.yml` refuses a tag that already has a release or a draft, a tag off `main`, and a moved tag. The index skips drafts, missing wheels and assets without a digest. Pages is deployed atomically from an artifact, and an in-progress deploy is never cancelled.
- The phase ends resume at the first unticked box, and each step commits with its tick, so a phase end does recover after a crash.
- `make check` covers `TZ=UTC`, and `VID2SUB_REQUIRE_FFMPEG=1` and `VID2SUB_REQUIRE_WHISPER=1` turn skips into failures in CI.

## Kickoff council: security

The web security design is strong as planned, and the reference builds bear it out. That covers
the 127.0.0.1 bind, the HMAC'd launch cookie, Host-, Origin- and Sec-Fetch-checked writes and
websockets, the verbatim CSP, `/media/` tokens, the file browser's walk-by-disk-names, Pages'
frame refusal and `message` filter, the hash-pinned Shinylive assets, vendored wheels and build
constraints, and SHA-pinned workflows with least privilege. I found no Critical. Five findings
are Important:
- Tier 2 is used for the tasks that hold the cloud opt-in gate and the browser's Save.
- §23.4's "can't hijack installs" claim fails whenever the index answers 404, and the PyPI name
  is unclaimed.
- On Windows, a `.bat` or `.cmd` tool would let a file name inject commands.
- Phase 3's own link and credential-folder rules don't hold for the app's two other path boxes.

Clone paths below are under the session's scratch `clones/` folder.
Plan paths are under `docs/superpowers/plans/` in the repo.

### Security checklist (AGENTS.md *Reviews*), over the whole project as planned

- **Secrets:** fine.
  - Keys are used only by `key_env`, and `vid2sub.toml` refuses key values and URL userinfo
    (`clones/final/src/vid2sub/config.py:126`).
  - Typed keys stay in memory only. They are shape-checked, and `KeyRing` has `repr=False`.
  - The typed key's input is nulled after reading, so it leaves Shiny's input map
    (phase-2.md:26553–26557).
  - `redact()` runs on every error.
  - The token reaches no log or `ps`: it is printed only to a TTY, and otherwise only the
    redirect file's path is printed.
  - The workflows use only `GITHUB_TOKEN`, and only at step scope.
  - No leak was found in the spec, the plans or AGENTS.md. The paths in them are placeholders
    (`/Users/someone/…`).
  - See Finding 8 for the cookie's residual risk.
- **Permissions:** a finding (Finding 5); otherwise fine.
  - The browser lists only roots, never links, hidden or credential folders. Pages uses a
    `readwrite` folder handle kept only in a ref.
  - The page writes only names `nearby()` accepts (`clones/p4b/frontend/src/lib/folder.ts:209`).
  - In the workflows, only `release.yml`'s publish job and `pages.yml`'s deploy job can write,
    and neither runs repository code.
- **Network exposure:** fine.
  - The server binds 127.0.0.1 only and answers only to Host `127.0.0.1`. The local app makes no
    third-party requests.
  - Pages fetches only its own files.
  - Phase 2 Decision 24's Test sends a key only to the endpoint's own origin.
  - Phase 3's faster-whisper first-run download sends no user content.
- **Failing closed:** fine.
  - The guards answer 400, 403, 415 and 401, refuse a websocket before accepting it, and never
    reconnect.
  - An unknown media token gets 404.
  - `allow_cloud` must be exactly `true` or `false`, and the cloud check runs before anything is
    sent.
  - The frame check runs before anything loads.
  - A Save is kept only after the page answers `written: ok`.
  - `pages.yml` deploys only from main, and the environment rule backs that up.
- **Injection:** a finding (Finding 4); otherwise fine.
  - Every subprocess gets an argument list, ffmpeg runs with protocol and format allowlists, and
    yt-dlp gets `--` and only the YouTube extractor.
  - Untrusted text is rendered as text. The repo has no `dangerouslySetInnerHTML`.
  - Shinylive's `appName`-into-Python sink is closed by `start.js`'s origin filter.
  - No workflow puts a `${{ }}` in a `run:` block, and `GITHUB_OUTPUT` values are
    regex-validated.
- **Logging:** fine, with one item under Unconfirmed.
  - uvicorn's access log is off and its proxy headers are ignored.
  - The editor's queue logs only exception types.
  - Tests assert that the token, typed keys and paths are absent from log records.
  - The e2e artifact is the `--demo` server log, which holds no token.

### Tier re-check (AGENTS.md:147–149)

The test for Tier 1 is "if wrong, could take the system down, lose or leak data". I would move
these tasks.

**Move to Tier 1 (strong):**
- **Phase 2 Task 7 (retranslate backend), Tier 2.** It is the gate that keeps subtitle text away
  from a cloud model: "Cloud only when this call's `allow_cloud` is set, checked before anything
  is sent" (phase-2.md:7890). If it is wrong, private text leaks to OpenAI.
- **Phase 2 Task 17 (Retranslating UI), Tier 2.** It builds the editor's **Allow cloud models**
  box, "unticked at first and after each request" (phase-2.md:23878), and the server's strict
  `allow_cloud` parsing. Same leak.
- **Phase 3 Task 3 (sampling and suggestions), Tier 2.** It changes M1's cloud enforcement:
  "`pipeline.RunContext.engine(name)` runs `clients.check_allowed` on every call, so an engine
  made for a run that allowed the cloud is refused to a copy…" (phase-3.md:4491). Sampling also
  runs before anyone can tick the box.
- **Phase 3 Task 4 (Review screen), Tier 2.** S40's "**Allow cloud** starts unticked every time"
  is spec §7.2's opt-in (spec:611–614), and `set_allow_cloud` is "the box, the only setter"
  (phase-3.md:4535).
- **Phase 4 Task 1 (browser backend), Tier 2.**
  - It moves Phase 2 Task 6's Save (Tier 1) into `web.folder`, and it runs never-overwrite and
    the sidecar merge in the browser on a staged copy (phase-4.md:164–181). If it is wrong,
    someone's subtitle file is overwritten or a version is lost.
  - Task 3's security review already had to send a Critical back into this task's code.
- **Phase 4 Task 9 (install index and smoke), Tier 2.**
  - It edits `pages.yml`, a Tier-1 workflow (phase-4.md:12516), with new outputs and a new job.
  - Its output decides which bytes users install (§23.4).

**Consider for Tier 1 (moderate):**
- **Phase 2 Task 3 (cache and playback audio).** `Cache.clear` and `evict` call
  `shutil.rmtree`, and the task runs ffmpeg on user media (phase-2.md:1060–1066). Deletion is
  scoped to 64-hex folders with lstat checks, so the risk is a regression that loses data.
- **Phase 2 Task 12 (scaffold and shinyreact server).** It creates `server.py`, the engine's
  whole websocket RPC surface, and overrides Shiny's busy-indicators dependency. It also owns
  the only real-browser CSP test. Phase 2 Task 8 expects Task 12 to be where any `style-src`
  change happens (phase-2.md:9189–9192).
- **Phase 4 Task 2 (Pages build).** It holds the hash pins for Shinylive and the vendored wheels,
  and the first `start.js`: what code runs for every visitor on the shared origin.

No task needs to move down.

### Findings

#### 1. The cloud opt-in gate is built and changed under Tier 2 reviews, with no security checklist (Important)
- **Where:**
  - phase-2.md:7869 (Task 7) and 23817 (Task 17)
  - phase-3.md:4472 (Task 3) and 5773 (Task 4)
  - AGENTS.md:147–148
- **Evidence:** Tier 1 is "if wrong, could … leak data". Spec §7.2 (spec:611–614): "A run may
  use a cloud model only when **that run** sets `allow_cloud` … No config key or environment
  variable can preset it." These four tasks build or alter exactly that gate, and all four are
  Tier 2 ("no safety role").
- **Why it matters:**
  - A box that stays ticked, a shared engine cache, or a parsing slip sends audio or subtitle
    text to OpenAI without the person's consent.
  - Tier 2 runs no security checklist and no re-review discipline for that property.
- **Fix:** set all four to Tier 1 (see the Tier re-check), so each review carries the checklist
  line "failing closed: cloud refused unless this request set it".

#### 2. Phase 4 Task 1 and Task 9 are Tier 2 but carry Tier-1 code (Important)
- **Where:**
  - phase-4.md:156 (Task 1), with the "On a staged copy" and "A Save keeps nothing" bullets at
    164–181
  - phase-4.md:12471 (Task 9), with `pages.yml` modified at 12516
- **Evidence:**
  - Task 1 moves "what both backends share (open, the edit rules, Save, the pick of a conflicted
    version)" out of Phase 2 Task 6 (Tier 1). It also runs never-overwrite and compare-and-swap
    in Pyodide.
  - Task 9 adds the index step, job outputs and a whole `smoke` job to `pages.yml`, which Task 7
    built at Tier 1.
- **Why it matters:**
  - In Task 1, a wrong staging or merge overwrites a foreign SRT or drops a version: data loss.
    Task 3's security review already found a Critical in this code, so the Tier 2 review missed
    one once.
  - In Task 9, a slip in a deploy workflow, or in what the index links, changes what every
    `uv tool install` gets.
- **Fix:** set both to Tier 1.

#### 3. Spec §23.4's "can't hijack installs" holds only while the index answers. uv falls back to PyPI on a 404, and `vid2sub` is unclaimed there (Important)
- **Where:**
  - spec:1424–1425
  - the README's install lines (spec:1440–1442)
  - phase-4.md Task 9 and Task 10
- **Evidence:**
  - Spec: "An index named with `--index` is checked before PyPI, so a later `vid2sub` on PyPI
    can't hijack installs".
  - uv's index docs (docs.astral.sh/uv/concepts/indexes, read 2026-10-24): uv "will always
    continue searching across indexes when it encounters a `404 Not Found`. This cannot be
    overridden."
  - `https://pypi.org/simple/vid2sub/` returns 404 today, so anyone can register the name.
- **Why it matters:**
  - These cases make `/vid2sub/simple/vid2sub/` answer 404: Pages disabled, the repo renamed or
    moved, or a mistyped index URL.
  - Then `uv tool install` or a later `uv tool upgrade vid2sub` (whose receipt keeps the index)
    silently installs whatever PyPI's `vid2sub` is. That is arbitrary code on the user's
    machine, with access to their keys.
  - The council's 2026-10-14 check covered only the case where the index lists the package.
- **Fix:**
  - Reword §23.4 to say the protection holds only while the index answers.
  - Propose to Dan that he claim `vid2sub` on PyPI. That is a publishing act outside the repo,
    so it is his decision and a never-relaxed stop.
  - Add a line to Phase 4 Task 9's or Task 10's docs.

#### 4. On Windows, a batch-file ffmpeg, ffprobe or deno lets a video's file name run commands (Important)
- **Where:**
  - `src/vid2sub/media/tools.py:47–66` (`_exts` and `which`, taken from PATHEXT, which includes
    `.BAT` and `.CMD`)
  - the same file, `run_tool` and `input_args` (unchanged in `clones/p3final/src/vid2sub/media/tools.py:57–77, 97–110, 178–180`)
  - Phase 3 Tasks 9–10, which make Windows a supported path (S45)
- **Evidence:**
  - Spec §6.7 (spec:550) promises "argument lists, no shell".
  - Python's subprocess docs (Security Considerations, read 2026-10-24): "batch files (`*.bat`
    or `*.cmd`) may be launched by the operating system in a system shell regardless of the
    arguments passed … without any escaping added by Python."
  - `subprocess.list2cmdline` quotes only arguments with spaces or tabs. Checked locally:
    `['C:\\ff\\ffmpeg.cmd','-i','file:C:\\TV\\x&calc&y.mkv']` becomes
    `C:\ff\ffmpeg.cmd -i file:C:\TV\x&calc&y.mkv`, and cmd.exe splits that at `&`.
  - None of the three plans mention `.bat`, `.cmd` or PATHEXT.
- **Why it matters:**
  - Suppose the first folder on PATH that matches holds `ffmpeg.cmd` or `ffmpeg.bat`, from a
    wrapper or some package-manager shims. npm's global `deno.cmd` is common.
  - Then a downloaded episode named like `x&calc&y.mkv`, a valid Windows name, runs `calc` when
    vid2sub probes it.
- **Fix:**
  - On Windows, `which` accepts only `.exe` and `.com` for the tools, with a guard test that
    plants `ffmpeg.cmd` earlier on PATH.
  - `doctor` names the refused shim. Its hint says to install deno from deno.com or winget.
  - Put it in Phase 3 Task 10's listing, marked "escaped from M1".

#### 5. Phase 3's link, hidden-folder and credential-folder rules don't hold for the app's two other path boxes, so Decisions 1–2 overstate them (Important)
- **Where:**
  - phase-3.md:27–34 (Decisions 1 and 2)
  - phase-3.md:938 ("whatever the browser wouldn't show can't be added by typing it")
  - `clones/p3final/src/vid2sub/web/server.py:649–655` and `862–875` (`_jobs_submit`)
  - `clones/p3final/src/vid2sub/web/backend.py:705–721` (`_video`)
  - phase-3.md:9570–9607 (the Jobs page keeps its path box)
- **Evidence:**
  - Decision 2: "a Linux library under `/srv` is added from the CLI, not the app".
  - Decision 1 asks Dan to write "never lists or follows a link, and a typed path through one is
    refused" into §6.5.
  - But `jobs_submit` checks only `os.path.isabs(os.path.expanduser(p))` before
    `rt.queue.submit(paths)`, and the editor's open only `isabs` plus `resolve_input`.
  - Neither calls `browse.accept` or `browse.expand`. So `/srv/…`, paths through links, hidden
    and credential folders, `\\host\C$\…` admin shares and `\\.\` device paths all reach the
    pipeline or ffprobe.
- **Why it matters:**
  - Dan is approving a §6.5 addition on the premise that the app enforces it, and two of its
    three path inputs don't.
  - A season folder typed into the Jobs box is expanded by M1's rules, not Task 1's, so any link
    inside the folder still leads outside it.
- **Fix:** choose one and say which in Decisions 1–2.
  - Route `jobs_submit` and the editor's open through `browse.accept` or `browse.expand` in
    Phase 3 (Task 2 or Task 6).
  - Or reword the Decisions: Add enforces the rules, while the Jobs box and the editor's path box
    stay CLI-equivalent escape hatches.

#### 6. The editor's Allow cloud box is a third opt-in surface that §7.2 doesn't name, and no Decision records it (Minor)
- **Where:** phase-2.md:23878 (Task 17's `allow-cloud`); spec:611–613; phase-2.md:31–123 (no
  Decision covers it)
- **Evidence:** §7.2 names two ways only: "the `--allow-cloud` flag, or the checkbox on the
  Review screen". Task 17 adds the box to the editor's Retranslate.
- **Why it matters:** the box is consistent in spirit, unticked each time, but it changes where
  consent is given without Dan seeing it as a decision.
- **Fix:** add a Decision ("a per-request Allow cloud box on Retranslate, unticked after each")
  and amend §7.2's sentence at Task 17's close.

#### 7. Dependabot doesn't watch the frontend's npm lock, and `npm ci` runs lifecycle scripts in the jobs that build what ships (Minor)
- **Where:**
  - `.github/dependabot.yml`, which has only `github-actions` and `uv`, and still has only those
    in `clones/p4b`
  - `clones/p4b/.github/workflows/release.yml` (`npm ci` before `make dist`) and `pages.yml`
  - `clones/p4b/frontend/package-lock.json` (`hasInstallScript` for esbuild 0.21.5, fsevents
    2.3.3, and the root's own `preinstall`)
- **Evidence:** §23.1 calls for "Dependabot on Fridays". Phase 2 Task 12 adds `frontend/` with
  `package-lock.json`, and no plan adds the `npm` ecosystem.
- **Why it matters:** `ui.js` runs on the engine's origin with full control. An advisory against
  a frontend dependency would never raise a PR. Install scripts run inside the job whose output
  is attested and released.
- **Fix:**
  - Add `package-ecosystem: npm`, `directory: /frontend`, on Fridays, in Phase 2 Task 12 or
    Task 21.
  - Check whether `npm ci --ignore-scripts` builds in `release.yml` and `pages.yml`; esbuild
    0.21 ships its binary in optional packages.

#### 8. The launch cookie reaches every server on 127.0.0.1, and the plan "accepts" that citing a spec line that doesn't say so (Minor)
- **Where:**
  - phase-2.md:10690–10692 (Task 9's close)
  - `clones/final/src/vid2sub/web/auth.py:14–16`
  - `clones/final/src/vid2sub/web/guards.py:148, 186` (no Origin passes)
  - spec §6.1–§6.2
- **Evidence:**
  - Plan: "Known and accepted (spec §6.2): cookies ignore ports, so a server the user visits on
    another port of 127.0.0.1 would receive the cookie; HostGuard and WriteGuard are what keep
    pages on other ports out."
  - §6.2 records no such acceptance.
  - The guards stop *pages*. A *server* holding the cookie can replay it with Host `127.0.0.1`
    and no Origin, and is let in (no Origin is read as "no browser").
- **Why it matters:** another user's service or a container's port-forward on loopback, once the
  browser visits it, gets full engine access as Dan. That access covers his files and the use of
  his keys, which is exactly the cross-user boundary the token exists for.
- **Fix:** write the residual risk into §6.1 for Dan to accept, rather than citing §6.2. A
  stronger option, Dan's call, is a port-scoped second factor on the websocket, such as a
  per-tab token held in `sessionStorage`.

#### 9. Pages crash drafts sit in `localStorage` on the shared `chendaniely.github.io` origin, readable by Dan's other sites, and never expire (Minor)
- **Where:**
  - `clones/final/frontend/src/lib/draft.ts:19` (`vid2sub.draft.*`), used unchanged in Pages
  - phase-4.md:6222–6224 (the test reads them in Pages)
  - spec:578–582 (§6.9)
- **Evidence:** §6.9 bases its rules on the shared origin ("never persists folder handles"). A
  draft holds the person's typed subtitle text and is removed only on Save or discard.
- **Why it matters:** `recordings`, `meanwhile`, or any later page on that origin can read every
  abandoned draft, left by any visitor, indefinitely.
- **Fix:** say so in §6.9, and either expire drafts (for example after 7 days, by their `at`
  field) or keep them in `sessionStorage` in Pages.

### Unconfirmed

- Unhandled exceptions in Shiny effects outside the editor's queue go to Shiny's
  `traceback.print_exc()`.
  - Where: `shiny/reactive/_reactives.py:1118, 1132` in the clones' venv; for example
    `_jobs_submit` catches only `RuntimeError`.
  - An `OSError`'s message holds a path, which would reach stderr, the "log" Decision 12 guards.
  - I didn't trace whether any effect can actually raise one.
- Chrome's history database may keep the `/auth#t=<token>` visit despite `history.replaceState`.
  The token is useless off this machine, and dies with the launch.

### Checked and fine

- HostGuard and WriteGuard against spec §6.2:
  - exact Origin, with scheme and port
  - `Sec-Fetch-Site` `same-site` refused
  - security headers replaced, never duplicated, including on 400, 401 and 403
  - DNS rebinding answered 400
  - other-port pages refused for writes and websockets
  - COOP severs `window.open` handles
  - XFO and frame-ancestors stop framing
  - CORP stops cross-origin `/media/` loads
- TokenGuard:
  - open paths matched exactly, HTTP only
  - the cookie is an HMAC of the token, checked across every same-named cookie, so a planted
    cookie can't shadow the real one
  - `SameSite=Strict`, `HttpOnly`, named for the port
  - `/auth` body capped at 1 KiB
  - the redirect file is 0600 in a 0700 folder and is removed at exit
- The CSP is verbatim §6.3. It needs no `style-src`: native `<dialog>` replaces Radix's injected
  styles. The busy indicators are served as a file. No `unsafe-eval`.
- `/media/`:
  - audio and video types only
  - (dev, inode, size) checked against the issued file
  - no `Content-Disposition` filename
  - the sandbox, nosniff and no-store headers
- The file browser:
  - `qualified` refuses device paths, `..`, admin shares (`C$`, `ADMIN$`, `IPC$`), streams and
    reserved names
  - each name is resolved against the disk, case- and NFC-folded, so short names and aliases
    can't pass
  - symlinks, junctions and name-surrogate reparse points are never followed
  - `/Volumes`' boot link is excluded
  - `Library` and `AppData` are hidden in any profile
  - reasons never name a path
- Pages:
  - `start.js` refuses frames before loading anything.
  - Its capturing `message` filter is registered before Shinylive's `openChannel` listener.
  - shiny.js, shinyreact.js and `ui.js` have no window `message` listeners, checked in the
    clones, so the inner frame exposes none.
  - The query string is dropped.
  - `_site` holds only one HTML page.
  - Writes are limited to `nearby()` names, all-or-none.
- Typed keys:
  - only for `allow_typed_key` endpoints
  - an 8–1,024 character charset, which keeps redaction effective
  - nulled from Shiny's input map
  - shown back only as "key entered for this session"
  - `KeyRing` has `repr=False`
- `clients.py`:
  - `follow_redirects=False` and explicit `api_key` and `base_url` on every client
  - `list_models` keeps the safe-transport check
  - no new client-construction site in any plan
- `release.yml`:
  - SHA-pinned actions
  - `persist-credentials: false` and no caches
  - checks that the tag is on main and still names the built commit
  - refuses an existing release, draft included
  - attestations before `gh release create --verify-tag`
  - the write job runs no repository code
- `pages.yml`:
  - least privilege per job
  - `workflow_run` gated on success, push and same repository
  - always builds main
  - deploys only from main, backed by the `github-pages` environment rule
  - its caches are restore-scoped to main and hash-checked before unpacking, and uv's cache is
    off
  - checks `_site/` for symlinks
  - the smoke job has `permissions: {}` and no checkout
- `ci.yml`: SHA pins, gitleaks pinned and checksum-checked over the whole history, no
  `pull_request_target`.
- Install index integrity:
  - links built from repository, tag and name, never `browser_download_url`
  - GitHub's digest only
  - drafts, odd tags and missing digests left out
  - immutable releases, a `v*` tag ruleset and main protection are planned as Dan's settings
    before the first tag (phase-4.md:12434–12436, 13869)
- Supply chain:
  - Shinylive's tarball is pinned by SHA-256.
  - The vendored wheels are checked against uv.lock's hashes.
  - `make dist` uses `--build-constraints build-constraints.txt --require-hashes`.
  - `uv.lock` is used with `UV_FROZEN`.
  - Silero is vendored with its licence.
- Subprocesses: `awake.py`'s `caffeinate` and `systemd-inhibit` use absolute or allowlisted
  executables, argument lists and `child_env()`. yt-dlp's keep-video path is M1's locked-down
  invocation (`bv*+ba/b`, `--`, YouTube extractor only).
- The sidecar can't steer a write: projection paths are computed from the video name and a
  `TRACKS`-validated key, never read from the record.
- The demo (`serve --demo`) goes through the same `create_app` guards. It reads no
  `vid2sub.toml` and no key, and an audit hook confines its reads, writes and network.

## Kickoff council: simplicity

The three plans run to 64,674 lines for about 31,000 lines of code and tests (from the clones' diffs: Phase 2 about 17,000, Phase 3 about 7,900, Phase 4 about 6,100). Full code accounts for half of that. Most of the other half is repetition. Eleven review-fix rounds replay code the same task has just written. Whole files are re-listed two to four times inside one task. Build commit bodies average 29 to 37 lines, and they restate each step. In the design, three things are heavier than they need to be: Phase 4's release path, where `workflow_run` and a hand-written Actions-expression evaluator guard what a dispatch and two repo settings would cover; a Phase 4 refactor of Phase 2 code that isn't built yet; and the file browser's hardening beyond §6.5. Nothing here costs a scenario row. Each finding says what is lost.

### Findings

#### 1. Review-fix rounds and whole-file re-listings make the build write known-wrong code, then fix it (Important)
- **Where:** review-fix rounds at Phase 2 `:12247` (11c), `:28718` (18c); Phase 3 `:1007` (1c), `:1903` (1e), `:2564` (1f); Phase 4 `:6654` (3d), `:8131` (4b), `:10118` (7b), `:10546` (7c), `:11752` (8d), `:12301` (8e). Whole-file re-listings inside one task: Phase 3 Task 1 lists `browse.py` in full three times (`:539`, `:1389`, `:2048`: 256, 350 and 433 lines, for a final file of 435) and `test_browse.py` twice (`:230`, `:1019`). Phase 3 Task 5 lists `jobs.py` twice (`:8095`, `:8589`). Phase 4 Task 8 lists `tests/test_release.py` four times (`:10903`, `:11056`, `:11355`, `:11765`: about 78, 146, 222 and 346 lines, for a final file of 356).
- **Evidence:** Phase 2 `:28720`: "its findings are fixed here, as their own round, so the implementer builds them in." Phase 3 Task 1 takes 2,605 lines for about 1,000 lines of final code and tests (`browse.py` 435 and `test_browse.py` 510 in `p3final`). Together the eleven rounds hold about 5,700 lines.
- **Why it matters:** each round makes the implementer write, test, commit and (under the standing push OK, `AGENTS.md` *Pushing*: "every commit is pushed") push code the plan already knows is wrong. That includes known Critical holes, such as Phase 3 1e's AppData listing and Phase 4 4b's cross-origin Python. They sit on the public phase branch until the next round. The cost recurs: Phases 3 and 4 are replayed again at their phase starts (Q&A item 9), and each replay re-runs every superseded listing.
- **Fix:** in the replay now under way, and at each phase start, fold each round's fixes into the listing they fix. The first listing becomes the fixed code. Its tests include the review's tests, which still fail first, so guard tests still "fail without their fix". One line in "Why it is built this way" records what the drafting review found. When a file changes twice in one task, use a `diff` or edit step, as Phase 4 already does, not a second whole-file listing. AGENTS.md step 3's build-time review still runs. The in-flight move of round 3d's fix into Phase 4 Task 1 is the same move, applied once.
- **Lost:** the plan no longer shows the drafting review's sequence, which is history, not instructions. Probable saving: half or more of the 5,700 lines, plus about 1,000 lines of re-listed files.
- **Keeps:** every row; the rounds' fixes stay in.

#### 2. Commit bodies, per-commit boilerplate and full-suite counts repeat the step around them (Minor)
- **Where:** 119 build commit messages: 1,768 lines in Phase 2, 1,073 in Phase 3 and 1,024 in Phase 4 (averages 29, 36 and 37 lines). For example, Phase 3 `:2505` runs to 54 lines. Each of about 110 commit steps repeats "Write the message to `.git/COMMIT_MSG`", `git add`, `git commit -F` and the `%(trailers)` check. Phase 2 carries 50 full-suite `make check` counts, such as `:1312`'s "`512 passed, 2 skipped, 4 deselected` twice".
- **Evidence:** `AGENTS.md:207` asks only that each body say "what changed and why (a new test: the output line that showed it failing)", and `AGENTS.md:74` that it say what was checked and which docs were read. The bodies also restate the guard checks and the "Why it is built this way" bullets from the same task. Each plan's header says it "never restates" `AGENTS.md`'s commit formats (Phase 2 `:6`), yet every step restates the commit procedure. Phases 3 and 4 already say "yours are higher once Phase 3 is in. What matters is no failure" (for example Phase 4 `:255`).
- **Why it matters:** about 2,500 of these lines could go. The full-suite counts go stale whenever an earlier task adds a test, so every replay rewrites dozens of numbers that nobody checks.
- **Fix:** each body becomes about 8 to 12 lines: what changed, the failing line, the guard checks by name, and the docs read by name. The procedure is written once in each plan's header ("each Commit step: message to `.git/COMMIT_MSG`, stage the paths listed, `git commit -F`, check `Plan:`"), and steps list only the subject and paths. Phase 2 adopts Phases 3 and 4's rule: each new test file keeps its exact count, and `make check` is "green" plus ruff's and gitleaks' lines.
- **Lost:** a shorter `git log` narrative. The plan and spec keep the reasons.
- **Keeps:** every row.

#### 3. Phase 4 Task 1 refactors Phase 2 code that isn't built yet (Important)
- **Where:** Phase 4 Decision 3 (`:48-54`); Task 1 Round 1b (`:405-1506`, which replaces `backend.py` whole at Step 11, `:1102`); Phase 2 Tasks 5 and 6 (`LocalBackend`).
- **Evidence:** "What both backends do with an episode's files moves into `vid2sub.web.folder` … a refactor of Phase 2's `LocalBackend`, with no change in behaviour." In `p4b` that rewrites 537 lines of `backend.py` and adds 525 in `folder.py`. Phase 2 already designs the server for Pages: "The Shiny server runs in Pages too … so `vid2sub.web.server` and `vid2sub.web.views` import, at module level, only the pure packages …" (Phase 2 `:150-156`).
- **Why it matters:** none of the three phases is built yet. Building `LocalBackend` one way in Phase 2 and moving its Save path in Phase 4 costs about 1,100 plan lines. It also re-opens the code where data loss lives (Save, compare-and-swap, projections) for a move that a single build could avoid.
- **Fix:** Phase 2 Tasks 5 and 6 produce the Pages-safe `vid2sub.web.folder` from the start, with `LocalBackend` calling it. `video_change` and `MEDIA_SUFFIXES` move to `subs.sidecar` and `subs.naming` there, callers updated. Phase 4 Task 1 keeps only `web.browser`. Decision 3's spec change is up for approval now either way.
- **Lost:** Phase 2 gains a module boundary that only Pages needs.
- **Keeps:** S28, S29, S31, S32, S47, S48.

#### 4. Decision 2's `workflow_run` adds a privileged trigger, three conditions and Decision 22; a dispatch would do (Important)
- **Where:** Phase 4 Decision 2 (`:36-47`), Decision 22 (`:117-118`), Task 7 (`:9561-9568`), Task 8 round 8e (`:12301`).
- **Evidence:** Decision 2 notes, "The other ways each cost more: `release.yml` dispatching `pages.yml` needs `actions: write`." Task 7 adds: "`workflow_run` is a trigger with write tokens for anyone's run … So both jobs run for it only when the run succeeded, was a `push`, and came from this repository." Decision 22 forbids any `if:` in `release.yml` and pins its name, "since `pages.yml` follows every workflow by that name." GitHub's GITHUB_TOKEN page (read now) says "`workflow_dispatch` and `repository_dispatch` events always create workflow runs."
- **Why it matters:** the chosen path is the most complex of the three options. Its safety rests on three expression conditions, a naming rule across workflows and an evaluator to test them (finding 5). Decision 2 changes §23.3 anyway, so by AGENTS.md's fifth stop the simpler options should be re-offered to Dan with it.
- **Fix:** put these to Dan at approval, beside Decision 2:
  - **A (simplest).** `release.yml`'s publish job ends with `gh workflow run pages.yml --ref main`. `pages.yml` keeps push, pull_request and workflow_dispatch with its existing main-only deploy condition. The `workflow_run` trigger, its three conditions, Decision 22 and the "only workflow named `release`" test all go.
  - **B.** No automatic redeploy: Dan runs `pages.yml` by hand after a release, as a step in Task 12's 9c.
  - **C.** As planned.
- **Lost:** with A, the publish job, which runs no repository code, holds `actions: write` for its few minutes. With B, the index lags a release until Dan clicks.
- **Keeps:** S51, S52.

#### 5. 743 lines of Python tests, including an Actions-expression parser, pin 279 lines of workflow YAML (Minor)
- **Where:** `p4b` `tests/test_pages_workflow.py` (387 lines; `value_of`, a recursive-descent parser of `${{ }}` at `:47-135`, and a ten-event `EVENTS` matrix) and `tests/test_release.py` (356 lines, which runs workflow steps against scratch git repos); `pages.yml` is 177 lines and `release.yml` 102. Plan: Phase 4 Task 7 `:9580-9581`, Task 8.
- **Evidence:** S52's Proof is "the `release.yml` and `pages.yml` runs" (spec `:92`), and S51's is "the post-deploy smoke job; the exit test" (`:91`). `make actionlint` is already in the stack (Phase 2 Task 21). Decision 19 (`:107-109`) says the `github-pages` environment's rule "is the real deploy gate", not the conditions.
- **Why it matters:** these tests go beyond what the scenarios ask for. Their main subject is the `workflow_run` conditions that finding 4 removes, and every workflow edit means updating them alongside the YAML.
- **Fix:** keep `actionlint` plus the cheap §23.1 hardening checks: every action pinned by SHA, per-job permissions, `persist-credentials: false`, no `${{ }}` in a `run:` step, and `release.yml`'s `--clobber` ban. Drop the evaluator, the event matrix, the step-order assertions and the scratch-repo step runs. The real runs in Task 12 step 9 are the proof.
- **Lost:** a broken `if:` shows up on the next real run rather than in `make check`. For deploys, the environment rule still holds.
- **Keeps:** S50, S51, S52.

#### 6. `release.yml`'s overwrite guards duplicate the repo settings that step 9b turns on anyway (Minor)
- **Where:** Phase 4 Task 8 (`:10775-10793`: the drafts-listing pre-check, the `git ls-remote` moved-tag check, the off-`main` check), `:12284-12286`, Task 12 step 9b (`:13867-13873`).
- **Evidence:** the plan itself says "A commit carrying a modified `release.yml` can drop any of these checks; only repo settings stop that (immutable releases, a tag ruleset …)". Step 9b turns those settings on before the first tag. GitHub's immutable-releases docs (read now): "Git tags cannot be moved", "Release assets cannot be modified or deleted", and a tag "cannot be deleted while the release exists". Delete the release and the tag name can't be used again.
- **Why it matters:** once immutable releases is on, Review Focus 4 (a re-run, or the same tag pushed again) is answered by the setting. The drafts pre-check exists for "deleting a tag turns its release into a draft", which the setting prevents.
- **Fix:** keep `gh release create --verify-tag`, the one-line tag-on-`main` check, the version check and the frontend-in-wheel check. Drop the drafts listing, the `ls-remote` check and their tests. State the step 9b settings as a precondition for the first tag.
- **Lost:** protection if Dan never turns immutable releases on.
- **Keeps:** S52, Review Focus 4.

#### 7. The file browser's hardening beyond §6.5 protects folder names, since only videos, subtitles and folders are ever listed or added (Minor; a judgement call for Dan)
- **Where:** Phase 3 Decision 24 (`:93-95`), Task 1 rounds 1c (`:1007-1013`), 1e (`:1903-1912`) and 1f (`:2564-2567`); `p3final` `src/vid2sub/web/browse.py:57-59`, `:196-200`, `:224-228`, `:247-248`.
- **Evidence:** `listing` adds a file only when `_file_kind` is video or subtitle (`:226-228`), and `accept` takes only a folder or a video (`:247-248`). So no key, token or config file can be named in a listing or read by a job, whatever path is typed. The extras guard against something smaller: Windows short names and streams (`SSH~1`, `::$INDEX_ALLOCATION`), `Library` and `AppData` under any `Users/<name>/` on any root, admin shares, and non-Unicode names. At most, they could expose subfolder names and stray videos inside a credential folder. Meanwhile `CREDENTIALS`' eight dot-names (`:57-58`) duplicate the dotfile rule, which `listing` (`_hidden_name`) and `place` (`:195-197`) already apply. Only `Library` and `AppData` do any work. Decision 24 is also a spec addition (Decision 1: "writes it, with Decisions 3 and 24, into §6.5").
- **Why it matters:** these rules account for most of Task 1's rounds (about 1,600 plan lines) and some 100 lines of code that every later browser change has to respect.
- **Fix:** keep S38's rules, link refusal (Decision 1), `_roots_near` (Review Focus 1's sleeping NAS), `MAX_ENTRIES` and the kind filter. Drop the dot-names from `CREDENTIALS`. Move Decision 24, round 1c's typed-name walk and the non-Unicode rule to the Phase-end list or Later, which also drops Decision 24's spec change.
- **Lost:** a typed `SSH~1` or WSL `/mnt/c/Users/x/AppData` path could list the subfolder names and any video or subtitle files inside. The Tier 1 reviewer rated the profile case Critical; Dan should weigh that against the kind filter.
- **Keeps:** S38.

#### 8. Phase 2 muxes the demo video at start-up, then Phase 4 deletes the mux and commits the same bytes (Minor)
- **Where:** Phase 2 Decision 6 (`:45-49`), Task 13's `scripts/demo_sidecar.py` docstring (`:16323-16327`: "`vid2sub serve --demo` muxes its own and points the sidecar's header at it"), Task 21's VP9 and Opus ffmpeg notes (`:33341-33343`, `:33440-33442`); Phase 4 Task 5 (`:8463-8477`), Round 5a (`:8567`).
- **Evidence:** Phase 4 Task 5 says the stand-in is "made once with Phase 2's mux command and committed … (79,186 bytes …), so the sidecar and subtitles stay as they are."
- **Why it matters:** two mechanisms do one job across two phases: start-up muxing with header re-pointing, then a committed clip. Phase 4 Task 2 also has to carry ffmpeg in `make pages` until Task 5 takes it out again.
- **Fix:** Phase 2 commits `demo/jfk.mp4`, made once with the same `+bitexact` command, and its canned sidecar names it. `serve --demo` copies `demo/`; `web.demo.mux`, `CLIP` and the header re-pointing are never written. Phase 4 Round 5a goes, and Task 5 keeps only Dan's choice of clip (Round 5b).
- **Lost:** a 79 KB binary enters git one phase earlier.
- **Keeps:** S27, S50.

#### 9. The version is written twice, so a script and a test exist to keep the two copies equal; and hatchling is hash-pinned (Minor)
- **Where:** `src/vid2sub/__init__.py:3` and `pyproject.toml:3`; Phase 4 Task 8 (`:10758-10773`); `p4b` `scripts/release_check.py` (`versions()` parses `__init__.py` with `ast`); `tests/test_release.py:95` ("the package version is the same in pyproject and the package"); `build-constraints.txt` and `make build-constraints` (`:10760-10762`).
- **Evidence:** `release_check.py`'s docstring says "The version is written twice, in pyproject.toml … and as vid2sub.__version__ … and the tag must name both." Hatch's version docs (read now) say hatchling's built-in regex source reads `__version__` from `[tool.hatch.version] path`, with no plugin.
- **Fix:** set `dynamic = ["version"]` with `[tool.hatch.version] path = "src/vid2sub/__init__.py"`. `__init__.py` keeps its literal, so Pages is unaffected. The tag check becomes one comparison, and `release_check.py` keeps only `dist_problems`. Pin `hatchling==1.32.4` in `[build-system]` and drop the constraints file and its target.
- **Lost:** hash checking of hatchling's four dependencies at release time. PyPI doesn't let a published file be replaced, so the exact pin already fixes hatchling's own bytes. See Unconfirmed for uv and dynamic versions.
- **Keeps:** S52.

#### 10. FastAPI is used only as a Starlette container with its own pages switched off (Minor)
- **Where:** `p3final` `src/vid2sub/web/app.py:24`, `:40-44`; spec §4.2 (`:323`), §19.1 (`:1231`); Phase 2 round 11c (`:12256`: "every command imported FastAPI").
- **Evidence:** `FastAPI(title="vid2sub", docs_url=None, redoc_url=None, openapi_url=None, …)`. It has one `@api.get("/healthz")`, and every other route is a Starlette `Route` (`auth.py`, `media.py`). Starlette is already installed with shiny.
- **Fix:** use `Starlette(routes=[Route("/healthz", …), *auth.routes(…), media.route(…), Mount("/", shiny_app)], lifespan=…)`, drop `fastapi` from the core dependencies, and change §4.2's and §19.1's wording. That is a spec change for Dan.
- **Lost:** line-for-line parity with `recordings`' `create_app`.
- **Keeps:** S23, S24, S25.

#### 11. `radix-ui` and `class-variance-authority` serve one three-button theme switch (Minor)
- **Where:** Phase 2 Task 12 `package.json` (`:13519-13526`), `ui/toggle.tsx` and `ui/toggle-group.tsx` (`:14109-14111`, `:14158-14160`); Decision 13 (`:69-72`).
- **Evidence:** in `p3final` and `p4b`, `radix-ui` is imported only by `components/ui/toggle.tsx` and `toggle-group.tsx`, and those only by `ThemeSwitch.tsx`. Decision 13 already replaced Radix's modals and Select with native `<dialog>` and `<select>` because of the CSP.
- **Fix:** three native `<button aria-pressed>` in a `role="group"`. Keep shadcn's CSS tokens (§19.3's look) and lucide's icons.
- **Lost:** copy-parity with `recordings`' `ThemeSwitch` (§4.4), and Radix's arrow-key roving focus (Tab moves between the three buttons instead).
- **Keeps:** S37.

#### 12. The three-system smoke install runs after every push to `main`, not only when the index changes (Minor)
- **Where:** Phase 4 Decision 21 (`:114-116`); Task 9 (`:12535`: "job `smoke` (needs build and deploy; if the index has a wheel …)"); `pages.yml` triggers on `push: branches: [main]` (`:9628`).
- **Evidence:** once one wheel is indexed, every docs or code push to `main` installs vid2sub on Ubuntu, Windows and macOS. macOS-14 is the most expensive runner.
- **Fix:** run `smoke` only on the run a release starts (the dispatch in finding 4A), or when the builder's `newest=` differs from the live index's. §23.4's "post-deploy" still holds.
- **Lost:** an install break caused by a non-release change, such as one to `build_index.py`, is found at the next release.
- **Keeps:** S51.

#### 13. Compatibility shims inside one repository (Minor)
- **Where:** Phase 4 Decision 3 (`:50`, "the pipeline keeping both names") and Decision 16 (`:96-97`, "`web.demo.prepare` keeps its unused `tools` argument for its callers").
- **Evidence:** vid2sub has no Python API that anyone outside the repo imports (§4.4, §26.2: `recordings` would copy code, not import it).
- **Fix:** update the callers in the same commit, with no aliases and no unused parameters.
- **Lost:** nothing outside the repo.
- **Keeps:** every row.

#### 14. The preview copy records and displays which encoder made it (Minor)
- **Where:** Phase 3 Decision 16 (`:62-64`); Task 7 (`:9779`, `:9851-9862`): `preview-a<N>.json`, plus `preview_encoder` in `runtime.Media`, `views.episode_view`, `types.ts` and `Player`, `encoderLabel`, and the notice "ready (<encoder>)".
- **Evidence:** S63 asks for a copy "from a hardware encoder when there is one, else libx264". Nothing reads the record except the label. The copy's completeness comes from the rename into place (`:9793-9794`).
- **Fix:** log the encoder's name, with no path, and drop the JSON file and the field from every layer.
- **Lost:** the editor can't say which encoder made a cached copy; it becomes a log line.
- **Keeps:** S63.

### Unconfirmed

- That `gh workflow run` with the GITHUB_TOKEN needs `actions: write` (finding 4A). This is the plan's own Decision 2 claim; GitHub's REST page for workflow dispatch, read now, names only classic-token scopes.
- How uv treats a hatchling dynamic version (finding 9): `uv lock` and `uv sync` build the project's metadata, and `uv version --bump` may refuse a dynamic version. I didn't check uv's docs.
- Whether `recordings`' `ThemeSwitch` is the Radix ToggleGroup this one copies (finding 11). I didn't open `recordings`.

### Checked and fine

- Phase 4 Decision 4 (`store` runs unchanged on a staged copy in Pyodide): the simple option, with one copy of the write logic.
- The index builder itself (139 lines): without PyPI, a PEP 503 index is the smallest thing that keeps `uv tool upgrade` working. Its exclusions are a few lines each.
- Attestations: one `actions/attest` step and two permissions in a job that runs no repository code. That is proportionate.
- Phase 2 Decisions 13 and 14 (native `<dialog>` and `<select>`; the busy-indicator script served as a file): simpler than the alternatives, and the CSP stays verbatim.
- Phase 4 Task 6 (the npm `pyodide` package under Node rather than pyodide-build): the smaller harness. Task 1's offline Vitest check does a different job (no network, inside `make check`), so two entry points are justified.
- Phase 3 Task 9's GPU library check before choosing CUDA: justified by cuDNN loading its parts lazily.
- Phase 2 Task 20: in v1 scope (§9.2 and §9.3 name `mlx-qwen3-asr serve`'s parser), and it proceeds without the Spark's recording.
- `@tanstack/react-virtual`: earns its place for Review Focus 3's 2,000-cue episode.
- Phase 3 Task 6 re-lists Phase 2's Jobs files whole, but the code mostly survives (`jobs.ts` 44 to 53 lines, `JobsPage.tsx` 78 to 97), so Phase 2's minimal page isn't thrown away.
- Phase 3 Decision 20's separate `whisper` CI job: small, and it keeps the core matrix fast.
- Full code in every step stays, as the project chose. Findings 1 and 2 cut only the repetition around it.
