import { type RefObject, useEffect, useRef, useState } from "react";

import { canPlay } from "@/lib/playable";
import type { Busy, EpisodeView } from "@/types";

import { CaptionOverlay } from "./CaptionOverlay";

/** The player (spec §20): the video by its media token when the browser can play it, else the
 * playback audio with no picture (§8.8; Decision 2), with the caption overlay over it. Whether it
 * can is the browser's to say (§8.2): canPlayType is asked about the probe's container and codecs
 * before the video loads, and a MEDIA_ERR_DECODE or MEDIA_ERR_SRC_NOT_SUPPORTED, or a picture
 * with no size once its metadata is in, says so too; then `onCantPlay` asks the server for the
 * playback audio, once. Making a preview copy with the picture is Phase 3's (S63). While it plays
 * it reports the time every frame, so the cue list, the spoken word and the captions keep up;
 * paused, it reports each seek. */
export function Player({ video, mediaRef, lines, busy, onTime, onCantPlay }: {
  video: EpisodeView["video"];
  mediaRef: RefObject<HTMLVideoElement | HTMLAudioElement | null>;
  lines: string[];
  busy: Busy;
  onTime: (ms: number) => void;
  onCantPlay: () => void;
}) {
  const report = useRef(onTime);
  report.current = onTime;
  const [failed, setFailed] = useState(false);
  const asked = useRef(false);
  const cantPlay = () => {
    if (asked.current) return;
    asked.current = true;
    onCantPlay();
  };
  // Asked once per video URL, before anything loads.
  const [plays] = useState(() => !video.url || canPlay((t) => document.createElement("video").canPlayType(t), video));
  const showVideo = video.url !== null && plays;
  const src = showVideo ? video.url : video.audio_url;

  useEffect(() => {
    if (video.url && !plays) cantPlay();
  }, [video.url, plays]);

  useEffect(() => {
    const media = mediaRef.current;
    if (!media) return;
    let frame = 0;
    const now = () => report.current(media.currentTime * 1000);
    const tick = () => {
      now();
      if (!media.paused && !media.ended) frame = requestAnimationFrame(tick);
    };
    const play = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(tick);
    };
    const events = ["seeked", "timeupdate", "loadedmetadata", "pause"] as const;
    media.addEventListener("play", play);
    for (const e of events) media.addEventListener(e, now);
    return () => {
      cancelAnimationFrame(frame);
      media.removeEventListener("play", play);
      for (const e of events) media.removeEventListener(e, now);
    };
  }, [mediaRef, src]);

  const onVideoError = (e: { currentTarget: HTMLVideoElement }) => {
    const code = e.currentTarget.error?.code;
    if (code === MediaError.MEDIA_ERR_DECODE || code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED) cantPlay();
    else setFailed(true);
  };
  const onVideoMetadata = (e: { currentTarget: HTMLVideoElement }) => {
    // A picture the browser can't decode can still leave the sound playing, with no error.
    if (video.video_codec && e.currentTarget.videoWidth === 0) cantPlay();
  };

  const box = "relative flex min-h-48 flex-1 items-center justify-center overflow-hidden rounded-lg bg-black";
  if (!src) {
    const making = busy === "playback" || (video.url !== null && !plays);
    return (
      <div className={box} data-testid="player">
        <p className="p-4 text-center text-white/80" data-testid="audio-only">
          {making ? "This browser can't play the video itself, so vid2sub is making a copy of its sound…" : "Nothing to play."}
        </p>
      </div>
    );
  }
  return (
    <div className={box} data-testid="player">
      {showVideo ? (
        <video
          ref={mediaRef as RefObject<HTMLVideoElement>}
          src={video.url ?? undefined}
          controls
          playsInline
          preload="metadata"
          className="max-h-full w-full"
          data-testid="media"
          onError={onVideoError}
          onLoadedMetadata={onVideoMetadata}
        />
      ) : (
        <div className="flex w-full flex-col items-center gap-3 p-4">
          <p className="text-center text-sm text-white/80" data-testid="audio-only">
            {video.playable_audio
              ? "Playing the sound only: this browser can't play the video itself."
              : "Playing the sound only: the browser can't play the audio track these subtitles were made from."}
          </p>
          <audio ref={mediaRef as RefObject<HTMLAudioElement>} src={video.audio_url ?? undefined} controls preload="metadata" className="w-full" data-testid="media" onError={() => setFailed(true)} />
        </div>
      )}
      {failed && (
        <p role="alert" className="absolute inset-x-0 top-0 bg-card px-3 py-2 text-sm text-destructive" data-testid="media-error">
          The browser can't play this file.
        </p>
      )}
      <CaptionOverlay lines={lines} />
    </div>
  );
}
