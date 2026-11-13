// The settings drawer's words (spec §19.2, §5.3): a key by presence only, and a typed one only as
// "key entered for this session"; a Test's answer; and the session's targets, which keep the
// drawer's order and are never none.

import type { EndpointSetting, EndpointTestResult } from "@/types";

export function keyLabel(e: EndpointSetting): string {
  if (e.typed) return "key entered for this session";
  if (e.key === "none") return "no key";
  if (e.key_env) return e.key === "present" ? `${e.key_env} is set` : `${e.key_env} isn't set in the shell vid2sub started from`;
  return "no key yet: type one below to use it this session";
}

export function testSummary(r: EndpointTestResult): string {
  if (!r.ok) return r.error ?? "the test failed";
  if (!r.models.length) return "Answers, serving no models";
  return `Answers, serving ${r.models.join(", ")}${r.more ? ` and ${r.more} more` : ""}`;
}

/** The targets with `key` ticked or unticked, in `order`; unticking the last one changes nothing. */
export function withTarget(targets: readonly string[], key: string, on: boolean, order: readonly string[]): string[] {
  const next = new Set(targets);
  if (on) next.add(key);
  else next.delete(key);
  return next.size ? order.filter((k) => next.has(k)) : [...targets];
}
