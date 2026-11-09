// A cue's flags as badges, in words (spec §12.5, §20): the lint flags the server recomputes each
// time (reading speed, width, duration) and the stored ones (est, halluc, edited), with stale and
// untranslated from the view. An unknown flag shows as it came, as text.

const LABELS: Record<string, string> = {
  cps: "reading speed",
  width: "too wide",
  duration: "duration",
  est: "estimated time",
  halluc: "possible hallucination",
  edited: "edited",
  stale: "stale",
  untranslated: "untranslated",
};

export function flagLabel(flag: string): string {
  return LABELS[flag] ?? flag;
}

export function Flags({ flags }: { flags: readonly string[] }) {
  if (!flags.length) return null;
  return (
    <ul className="flex flex-wrap gap-1" aria-label="Flags">
      {[...new Set(flags)].map((f) => (
        <li key={f} data-flag={f} className="rounded-sm bg-muted px-1.5 text-xs text-muted-foreground">
          {flagLabel(f)}
        </li>
      ))}
    </ul>
  );
}
