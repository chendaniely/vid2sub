import { describe, expect, it } from "vitest";

import type { SaveResultMessage, TrackInfo } from "@/types";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { OVERWRITE_COMMAND, pressSave, resultNotices, SaveBar } from "./SaveBar";

const TRACKS: TrackInfo[] = [
  { key: "en", label: "English", role: "source", head_by: "editor", in_conflict: false, all_stale: false },
  { key: "ja", label: "Japanese", role: "translation", head_by: "auto", in_conflict: true, all_stale: false },
];
const BASE: SaveResultMessage = { episode: "e1", kind: "save", written: [], foreign: [], conflicts: [], notes: [] };
const VIDEO = "Show - S01E01.mkv";

describe("what a Save says (spec §14.5, §15.3)", () => {
  it("names the files it wrote, and says Saved when there was nothing to write", () => {
    expect(resultNotices({ ...BASE, written: ["a.en.srt", "a.ja.srt"] }, TRACKS, VIDEO)).toEqual([
      { kind: "info", text: "Saved: wrote a.en.srt, a.ja.srt" }]);
    expect(resultNotices(BASE, TRACKS, VIDEO)).toEqual([{ kind: "info", text: "Saved" }]);
  });

  it("names each file left alone with the command that replaces one, each note, and each track in conflict", () => {
    const r = { ...BASE, foreign: ["a.en.ass"], notes: ["kept your outside edit to en"], conflicts: ["ja"] };
    expect(resultNotices(r, TRACKS, VIDEO)).toEqual([
      { kind: "info", text: "Left a.en.ass alone: vid2sub didn't write it, or it was changed outside vid2sub since. To replace a file vid2sub didn't write, run vid2sub write <video> --overwrite-foreign in the video's folder (the video: Show - S01E01.mkv)" },
      { kind: "info", text: "Kept your outside edit to en" },
      { kind: "error", text: "Japanese has two versions: pick the one to keep" },
    ]);
  });

  it("says so of several files left alone at once (Decision 32: never replaced from the UI)", () => {
    expect(resultNotices({ ...BASE, written: ["a.ja.srt"], foreign: ["a.en.srt", "a.en.ass"] }, TRACKS, VIDEO)[1]).toEqual({
      kind: "info",
      text: "Left a.en.srt, a.en.ass alone: vid2sub didn't write them, or they were changed outside vid2sub since. To replace a file vid2sub didn't write, run vid2sub write <video> --overwrite-foreign in the video's folder (the video: Show - S01E01.mkv)",
    });
  });

  it("never puts a file name inside the command a person might paste into a shell", () => {
    // A name from the disk can hold $(…), backticks or quotes, which a shell expands even inside
    // double quotes: the command keeps its placeholder, and the names are plain text beside it.
    const video = "a$(touch x)`b\"c'.mkv";
    const [, left] = resultNotices({ ...BASE, written: ["x.ja.srt"], foreign: ["a$(id).en.srt"] }, TRACKS, video);
    const [text, named] = left.text.split(" (the video: ");
    expect(text).toContain(`run ${OVERWRITE_COMMAND} in the video's folder`);
    expect(OVERWRITE_COMMAND).toBe("vid2sub write <video> --overwrite-foreign");
    expect(named).toBe(`${video})`);
    expect(text.split(OVERWRITE_COMMAND).join("")).not.toContain("touch");
    expect(text.slice(text.indexOf("run "))).toBe(`run ${OVERWRITE_COMMAND} in the video's folder`);
  });

  it("says a pick kept the version picked", () => {
    expect(resultNotices({ ...BASE, kind: "pick", written: ["a.ja.srt"] }, TRACKS, VIDEO)).toEqual([
      { kind: "info", text: "Kept the version you picked: wrote a.ja.srt" }]);
    // a version arrived since the picker opened: nothing was written, the track is still in conflict
    expect(resultNotices({ ...BASE, kind: "pick", conflicts: ["ja"],
      notes: ["another version of the ja track arrived: pick again"] }, TRACKS, VIDEO)).toEqual([
      { kind: "info", text: "Another version of the ja track arrived: pick again" },
      { kind: "error", text: "Japanese has two versions: pick the one to keep" }]);
  });
});

describe("the Save button (Task 16's Spec review, I-3)", () => {
  const bar = (busy: "saving" | "picking" | null) =>
    renderToStaticMarkup(createElement(SaveBar, { dirty: true, busy, formats: ["srt"], drafts: [], onSave: () => {}, onRestore: () => {}, onDiscard: () => {} }));

  it("stays focusable while it works, and says it is unavailable with aria-disabled", () => {
    // a `disabled` button loses focus, so the picker a Save opens couldn't give it back
    for (const busy of ["saving", "picking"] as const) {
      const html = bar(busy);
      expect(html).toContain('aria-disabled="true"');
      expect(html).not.toMatch(/\sdisabled(=|\s|>)/);
    }
    expect(bar(null)).toContain('aria-disabled="false"');
  });

  it("asks for nothing while a Save or a pick is under way, else for SRT and, ticked, ASS", () => {
    const asked: string[][] = [];
    const onSave = (f: string[]) => asked.push(f);
    pressSave("saving", false, onSave);
    pressSave("picking", true, onSave);
    expect(asked).toEqual([]);
    pressSave(null, false, onSave);
    pressSave("opening", true, onSave);
    expect(asked).toEqual([["srt"], ["srt", "ass"]]);
  });
});
