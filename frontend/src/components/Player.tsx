import { type RefObject, useEffect, useRef, useState } from "react";

import type { EpisodeView } from "@/types";

import { CaptionOverlay } from "./CaptionOverlay";

/** The player (spec §20): the video by its media token, or, when the browser can't play the
 * video's audio, the playback audio with no picture (Decision 2), with the caption overlay over
 * it. While it plays it reports the time every frame, so the cue list, the spoken word and the
 * captions keep up; paused, it reports each seek. */
export function Player({ video, mediaRef, lines, onTime }: {
  video: EpisodeView["video"];
  mediaRef: RefObject<HTMLVideoElement | HTMLAudioElement | null>;
  lines: string[];
  onTime: (ms: number) => void;
}) {
  const report = useRef(onTime);
  report.current = onTime;
  const [failed, setFailed] = useState(false);
  const src = video.url ?? video.audio_url;

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

  const box = "relative flex min-h-48 flex-1 items-center justify-center overflow-hidden rounded-lg bg-black";
  if (!src) {
    return <div className={box} data-testid="player"><p className="text-white/80">Nothing to play.</p></div>;
  }
  return (
    <div className={box} data-testid="player">
      {video.url ? (
        <video
          ref={mediaRef as RefObject<HTMLVideoElement>}
          src={video.url}
          controls
          playsInline
          preload="metadata"
          className="max-h-full w-full"
          data-testid="media"
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="flex w-full flex-col items-center gap-3 p-4">
          <p className="text-center text-sm text-white/80" data-testid="audio-only">
            Playing the sound only: the browser can't play this video's own audio track.
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
