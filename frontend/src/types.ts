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

/** The `episode` output: views.episode_view. `video.url` plays the video; `audio_url` the
 * playback audio when the browser can't play the video's audio (Decision 2). No path, ever. */
export type EpisodeView = {
  id: string;
  video: { name: string; duration_ms: number; url: string | null; audio_url: string | null; playable_audio: boolean };
  source: string;
  tracks: TrackInfo[];
  rows: Row[];
  words: SpokenWord[];
  dirty: boolean;
  can_undo: boolean;
  can_redo: boolean;
  notes: string[];
  conflicts: Record<string, Version[]>;
  glossary_adds: Record<string, string>;
};

/** The `busy` output: what the tab's editor is doing, or null. */
export type Busy = "opening" | null;
