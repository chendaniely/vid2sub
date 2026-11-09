// Whether this browser can play a video itself (spec §8.2: "Browser playability comes from the
// probe plus the browser's own canPlayType, reported by the UI"). The server sends ffprobe's
// container and codec names; this asks canPlayType about each, as RFC 6381 names them, before
// the video is loaded. It must ask first: Chromium plays an MP4's sound while dropping a picture
// it can't decode, and fires no error (checked in Playwright 1.64's Chromium with MPEG-4 Part 2
// and Opus). canPlayType's "" means "cannot be played on the current device" (MDN), so an empty
// answer is no; so is a codec or container this file doesn't know, since the playback audio
// always plays. The player's own error event and a picture with no size back this up.

type Ask = (type: string) => string;
type Video = { name: string; container: string; video_codec: string | null; audio_codec: string };

// The types to ask about for each codec ffprobe names: any one the browser can play will do.
const VIDEO: Record<string, string[]> = {
  h264: ['video/mp4; codecs="avc1.640028"'],
  hevc: ['video/mp4; codecs="hvc1.1.6.L93.B0"', 'video/mp4; codecs="hev1.1.6.L93.B0"'],
  vp8: ['video/webm; codecs="vp8"'],
  vp9: ['video/webm; codecs="vp9"', 'video/mp4; codecs="vp09.00.10.08"'],
  av1: ['video/mp4; codecs="av01.0.05M.08"', 'video/webm; codecs="av01.0.05M.08"'],
  mpeg4: ['video/mp4; codecs="mp4v.20.9"'],
  theora: ['video/ogg; codecs="theora"'],
};
const AUDIO: Record<string, string[]> = {
  aac: ['audio/mp4; codecs="mp4a.40.2"'],
  mp3: ["audio/mpeg"],
  opus: ['audio/webm; codecs="opus"', 'audio/ogg; codecs="opus"', 'audio/mp4; codecs="opus"'],
  vorbis: ['audio/webm; codecs="vorbis"', 'audio/ogg; codecs="vorbis"'],
  flac: ["audio/flac", 'audio/mp4; codecs="flac"'],
  alac: ['audio/mp4; codecs="alac"'],
  ac3: ['audio/mp4; codecs="ac-3"'],
  eac3: ['audio/mp4; codecs="ec-3"'],
};

function containerTypes(container: string, name: string): string[] {
  const formats = container.split(",");
  if (formats.includes("mp4") || formats.includes("mov")) {
    return name.toLowerCase().endsWith(".mov") ? ["video/quicktime", "video/mp4"] : ["video/mp4"];
  }
  if (formats.includes("matroska") || formats.includes("webm")) return ["video/webm", "video/x-matroska"];
  if (formats.includes("ogg")) return ["video/ogg"];
  if (formats.includes("mpegts")) return ["video/mp2t"];
  if (formats.includes("avi")) return ["video/x-msvideo"];
  return [];
}

/** The types canPlayType is asked about: the container's, the picture's and the sound's. */
export function mediaTypes(video: Video): { container: string[]; video: string[]; audio: string[] } {
  return {
    container: containerTypes(video.container, video.name),
    video: video.video_codec ? (VIDEO[video.video_codec] ?? []) : [],
    audio: AUDIO[video.audio_codec] ?? [],
  };
}

/** Yes when the container, the picture (if there is one) and the sound each have a type the
 * browser doesn't answer "" for. */
export function canPlay(ask: Ask, video: Video): boolean {
  const types = mediaTypes(video);
  const any = (list: string[]) => list.some((t) => ask(t) !== "");
  return any(types.container) && (video.video_codec === null || any(types.video)) && any(types.audio);
}
