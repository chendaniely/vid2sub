import { describe, expect, it } from "vitest";

import { canPlay, mediaTypes } from "./playable";

type Video = Parameters<typeof canPlay>[1];

const MP4: Video = { name: "Show.mp4", container: "mov,mp4,m4a,3gp,3g2,mj2", video_codec: "h264", audio_codec: "aac" };
const MKV: Video = { name: "Show.mkv", container: "matroska,webm", video_codec: "vp9", audio_codec: "opus" };

/** A browser that answers "probably" for exactly these types, and "" for anything else. */
const browser = (...yes: string[]) => (type: string) => (yes.includes(type) ? "probably" : "");

describe("the types the browser is asked about (spec §8.2)", () => {
  it("names the container's types and each codec as RFC 6381 does", () => {
    expect(mediaTypes(MP4)).toEqual({
      container: ["video/mp4"],
      video: ['video/mp4; codecs="avc1.640028"'],
      audio: ['audio/mp4; codecs="mp4a.40.2"'],
    });
    expect(mediaTypes(MKV)).toEqual({
      container: ["video/webm", "video/x-matroska"],
      video: ['video/webm; codecs="vp9"', 'video/mp4; codecs="vp09.00.10.08"'],
      audio: ['audio/webm; codecs="opus"', 'audio/ogg; codecs="opus"', 'audio/mp4; codecs="opus"'],
    });
    expect(mediaTypes({ ...MP4, name: "Show.MOV" }).container).toEqual(["video/quicktime", "video/mp4"]);
    expect(mediaTypes({ ...MP4, video_codec: "mpeg4" }).video).toEqual(['video/mp4; codecs="mp4v.20.9"']);
  });

  it("names nothing for a codec or container it doesn't know", () => {
    const odd = mediaTypes({ name: "a.wmv", container: "asf", video_codec: "wmv3", audio_codec: "wmav2" });
    expect(odd).toEqual({ container: [], video: [], audio: [] });
  });
});

describe("whether the browser can play a video", () => {
  it("is yes when the container, the picture and the sound each have a type it can play", () => {
    const chrome = browser("video/mp4", 'video/mp4; codecs="avc1.640028"', 'audio/mp4; codecs="mp4a.40.2"');
    expect(canPlay(chrome, MP4)).toBe(true);
  });

  it("is no when the browser can't decode the picture, though it could play the sound", () => {
    // Chromium plays an MP4's Opus while dropping MPEG-4 Part 2 video, with no error at all.
    const chromium = browser("video/mp4", 'audio/mp4; codecs="opus"', 'audio/webm; codecs="opus"');
    expect(canPlay(chromium, { ...MP4, video_codec: "mpeg4", audio_codec: "opus" })).toBe(false);
  });

  it("takes either of Matroska's types, since a browser may answer for WebM only", () => {
    const chromium = browser("video/webm", 'video/webm; codecs="vp9"', 'audio/webm; codecs="opus"');
    expect(canPlay(chromium, MKV)).toBe(true);
  });

  it("counts an empty answer, an unknown codec or an unknown container as no", () => {
    const yesToAll = () => "maybe";
    expect(canPlay(() => "", MP4)).toBe(false);
    expect(canPlay(yesToAll, { ...MP4, video_codec: "wmv3" })).toBe(false);
    expect(canPlay(yesToAll, { ...MP4, audio_codec: "truehd" })).toBe(false);
    expect(canPlay(yesToAll, { ...MP4, container: "avi" })).toBe(true); // video/x-msvideo: "maybe"
    expect(canPlay(yesToAll, { ...MP4, container: "asf" })).toBe(false);
  });

  it("needs no picture type for a file with no picture", () => {
    const ask = browser("video/mp4", 'audio/mp4; codecs="mp4a.40.2"');
    expect(canPlay(ask, { ...MP4, video_codec: null })).toBe(true);
  });
});
