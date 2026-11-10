// The JSON the server sends: src/vid2sub/web/views.py makes each shape (spec §19.1).

/** Which controls exist: the local engine, or (Phase 4) the browser editor (spec §19.1). */
export type Capabilities = {
  engine: "local" | "browser";
  generate: boolean;
  save: "disk" | "download";
  path_input: boolean;
};

/** One endpoint from vid2sub.toml: a key by presence only, never its value (spec §19.2). */
export type EndpointStatus = {
  name: string;
  local: boolean;
  key: "present" | "missing" | "none";
  reachable: boolean | null; // null: a cloud endpoint (never contacted), or not checked yet
};

export type Status = { endpoints: EndpointStatus[]; ffmpeg: boolean };

/** The `notice` message: something to tell the person, as plain text. */
export type Notice = { kind: "info" | "error"; text: string };

/** A translation cue in a row (spec §13.4): the source cues it covers, and its flags. */
export type TrCue = {
  id: string;
  start_ms: number;
  end_ms: number;
  text: string;
  src: string[];
  detached: boolean | null;
  flags: string[];
};

/** One translation track's part of a row: its cues there, and `untranslated` when it has none. */
export type TrCell = { cues: TrCue[]; flags: string[] };

/** One source cue with its translations alongside (spec §20): `w` is its word range [i, j) in
 * `words`; `n` its number, for display only. */
export type Row = {
  id: string;
  n: number;
  start_ms: number;
  end_ms: number;
  text: string;
  w: [number, number] | null;
  flags: string[];
  tr: Record<string, TrCell>;
};

export type TrackInfo = {
  key: string;
  label: string;
  role: "source" | "translation";
  head_by: string | null;
  in_conflict: boolean;
  all_stale: boolean;
};

export type SpokenWord = { start_ms: number; end_ms: number; text: string };

/** One of a conflicted track's versions (spec §14.4). */
export type Version = { rendition: string; by: string | null; at: string | null; cue_count: number };

/** A cue where a conflicted track's versions differ: its time, and its text in each version (in
 * `conflicts`' order), or null where a version lacks it (spec §14.4, S32). */
export type Difference = { start_ms: number; end_ms: number; texts: (string | null)[] };

/** The `episode` output: views.episode_view. `video.url` plays the video; `audio_url` the
 * playback audio when the browser can't play the video's audio (Decision 2), or the video itself
 * (spec §8.2: asked with canPlayType about ffprobe's container and codec names). No path, ever. */
export type EpisodeView = {
  id: string;
  video: {
    name: string;
    duration_ms: number;
    url: string | null;
    audio_url: string | null;
    playable_audio: boolean;
    container: string;
    video_codec: string | null;
    audio_codec: string;
  };
  source: string;
  tracks: TrackInfo[];
  rows: Row[];
  words: SpokenWord[];
  dirty: boolean;
  can_undo: boolean;
  can_redo: boolean;
  notes: string[];
  conflicts: Record<string, Version[]>;
  differences: Record<string, { cues: Difference[]; more: number }>; // at most 50 per track
  glossary_adds: Record<string, string>;
  heads: Record<string, string>; // track → head rendition: the crash-recovery draft's key
  formats: ("srt" | "ass")[]; // what Save writes unless the person changes it
};

/** The `busy` output: what the tab's editor is doing, or null. */
export type Busy = "opening" | "playback" | "saving" | "picking" | null;

/** An edit, as `vid2sub.web.ops` takes it: every edit goes through the server's `apply`. */
export type EditOp =
  | { op: "set_text"; cue: string; text: string }
  | { op: "set_translation_text"; track: string; cue: string; text: string }
  | { op: "set_times"; cue: string; start_ms?: number; end_ms?: number }
  | { op: "nudge"; cue: string; delta_ms: number; edge?: "start" | "end" | "both" }
  | { op: "split"; cue: string; at_char: number; at_ms: number; ids: [string, string] }
  | { op: "merge_next"; cue: string; id: string; joined: Record<string, string> }
  | { op: "insert"; start_ms: number; end_ms: number; text: string; id: string }
  | { op: "delete"; cue: string }
  | { op: "detach"; track: string; cue: string; detached: boolean }
  | { op: "replace_all"; find: string; replace: string; tracks: string[] }
  | { op: "glossary_add"; term: string; translation: string };

/** The `save_result` message: what a Save or a pick wrote, left alone or found in conflict. */
export type SaveResultMessage = {
  episode: string;
  kind: "save" | "pick";
  written: string[];
  foreign: string[];
  conflicts: string[];
  notes: string[];
};

/** The `applied` message: whether the edit, undo or redo with this count was made. */
export type AppliedMessage = { episode: string; n: number; ok: boolean };
