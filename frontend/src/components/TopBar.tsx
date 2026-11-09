import type { Capabilities, EndpointStatus, Status } from "@/types";

import { ThemeSwitch } from "./ThemeSwitch";

const ENGINE: Record<Capabilities["engine"], string> = {
  local: "Local engine",
  browser: "Browser editor",
};

/** One endpoint in words, not colour alone: reachable or not (cloud ones are never contacted),
 * and its key by presence only (spec §19.2). */
export function endpointLabel(e: EndpointStatus): string {
  const reach = e.reachable === null ? (e.local ? "checking…" : "cloud") : e.reachable ? "reachable" : "not reachable";
  const key = e.key === "none" ? "" : e.key === "present" ? ", key set" : ", key missing";
  return `${e.name}: ${reach}${key}`;
}

/** Which engine this is (from `capabilities`, not a toggle), the engine's status, and the theme
 * switch (spec §19.2). */
export function TopBar({ capabilities, status }: { capabilities?: Capabilities; status?: Status }) {
  return (
    <header className="flex items-center gap-4 border-b border-border bg-card px-4 py-2" data-testid="topbar">
      <span className="flex items-center gap-2 font-bold">
        <i aria-hidden className="inline-block size-2.5 rounded-full bg-(--brand-orange)" />
        vid2sub
      </span>
      {capabilities && <span className="text-sm text-muted-foreground" data-testid="engine">{ENGINE[capabilities.engine]}</span>}
      {status && (
        <ul className="flex flex-wrap gap-2 text-sm" aria-label="Engine status" data-testid="status">
          {!status.ffmpeg && <li className="rounded-full bg-muted px-2 text-destructive">ffmpeg missing</li>}
          {status.endpoints.map((e) => (
            <li key={e.name} className="rounded-full bg-muted px-2" data-testid="endpoint">{endpointLabel(e)}</li>
          ))}
        </ul>
      )}
      <ThemeSwitch />
    </header>
  );
}
