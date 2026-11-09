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
