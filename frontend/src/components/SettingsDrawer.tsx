import { type FormEvent, useState } from "react";

import { keyLabel, testSummary, withTarget } from "@/lib/settings";
import type { EndpointSetting, EndpointTestResult, SessionDefaults, SettingsView } from "@/types";

import { Dialog } from "./ui/dialog";

const button = "rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:opacity-50";
const field = "min-w-0 flex-1 rounded-md border border-input bg-background px-2 py-1 font-mono text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring";

export type DefaultsChange = { targets: string[] } | { formats: SessionDefaults["formats"] };

/** The settings drawer (spec §19.2, S35): the native <dialog> at the right edge (Decision 13).
 * Endpoints and models as vid2sub.toml has them, read-only, each endpoint with **Test** (its
 * /v1/models, asked by the engine) and its key by presence only; a typed key only where the file
 * allows one (§5.3), in a password field the browser is asked not to fill or keep, cleared once
 * sent, and shown back only as "key entered for this session". The session's defaults (targets,
 * formats) are for this launch, never written (§5.4); the cue rules are shown as built, since
 * nothing can change them yet (Decision 21); Copy settings gives the [defaults] table as TOML,
 * never a key. Every name, address and server answer is plain text (§6.3). */
export function SettingsDrawer({ open, onClose, settings, tests, onTest, onTypedKey, onDefaults }: {
  open: boolean;
  onClose: () => void;
  settings: SettingsView | null;
  tests: Record<string, EndpointTestResult | "testing">;
  onTest: (endpoint: string) => void;
  onTypedKey: (endpoint: string, key: string) => void; // "" forgets the typed key
  onDefaults: (change: DefaultsChange) => void;
}) {
  return (
    <Dialog open={open} onClose={onClose} title="Settings" side="right" className="overflow-y-auto">
      {settings && (
        <div className="flex flex-col gap-5 text-sm" data-testid="settings">
          <section aria-labelledby="settings-endpoints" className="flex flex-col gap-2">
            <h3 id="settings-endpoints" className="font-bold">Endpoints</h3>
            <p className="text-muted-foreground">As vid2sub.toml declares them: change them there.</p>
            {settings.endpoints.length === 0 && <p>None: vid2sub.toml declares no endpoint.</p>}
            {settings.endpoints.map((e) => (
              <Endpoint key={e.name} endpoint={e} test={tests[e.name]} onTest={onTest} onTypedKey={onTypedKey} />
            ))}
          </section>
          <section aria-labelledby="settings-models" className="flex flex-col gap-1">
            <h3 id="settings-models" className="font-bold">Models</h3>
            {settings.models.length === 0 && <p>None: vid2sub.toml declares no model.</p>}
            <ul className="flex flex-col gap-1" data-testid="settings-models">
              {settings.models.map((m) => (
                <li key={m.name}>
                  <span className="font-mono">{m.name}</span>: {m.task === "translate" ? "translates" : "transcribes"}
                  {m.endpoint ? ` on ${m.endpoint}` : m.engine ? ` in-process (${m.engine})` : ""}, {m.local ? "local" : "cloud"}
                </li>
              ))}
            </ul>
          </section>
          <Defaults settings={settings} onDefaults={onDefaults} />
          <section aria-labelledby="settings-rules" className="flex flex-col gap-1">
            <h3 id="settings-rules" className="font-bold">Cue rules</h3>
            <p className="text-muted-foreground">Cue rules can't be changed yet.</p>
            <table className="text-left text-xs" data-testid="settings-rules">
              <thead>
                <tr><th scope="col">Language</th><th scope="col">Width</th><th scope="col">Lines</th><th scope="col">Chars/s</th><th scope="col">Duration</th></tr>
              </thead>
              <tbody>
                {settings.rules.map((r) => (
                  <tr key={r.lang}>
                    <th scope="row" className="font-normal">{r.label}</th>
                    <td>{r.max_width}</td><td>{r.max_lines}</td><td>{r.cps}</td>
                    <td>{(r.min_ms / 1000).toFixed(3)}–{r.max_ms / 1000} s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <CopySettings toml={settings.toml} />
        </div>
      )}
    </Dialog>
  );
}

function Endpoint({ endpoint: e, test, onTest, onTypedKey }: {
  endpoint: EndpointSetting;
  test: EndpointTestResult | "testing" | undefined;
  onTest: (endpoint: string) => void;
  onTypedKey: (endpoint: string, key: string) => void;
}) {
  const [key, setKey] = useState("");
  const submit = (ev: FormEvent) => {
    ev.preventDefault();
    if (!key) return;
    onTypedKey(e.name, key);
    setKey(""); // out of the page as soon as it is sent
  };
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border p-2" data-testid={`endpoint-${e.name}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-bold">{e.name}</span>
        <span className="text-muted-foreground">{e.local ? "local" : "cloud"}</span>
        <button type="button" className={`${button} ml-auto`} onClick={() => onTest(e.name)} disabled={test === "testing"} data-testid={`test-${e.name}`}>
          {test === "testing" ? "Testing…" : "Test"}
        </button>
      </div>
      <span className="font-mono text-xs break-all">{e.base_url}</span>
      <span data-testid={`key-${e.name}`}>{keyLabel(e)}</span>
      <span role="status" aria-live="polite" className="break-words text-muted-foreground" data-testid={`test-result-${e.name}`}>
        {test && test !== "testing" ? testSummary(test) : ""}
      </span>
      {e.allow_typed_key && (
        <form className="flex items-center gap-2" onSubmit={submit}>
          <label htmlFor={`typed-key-${e.name}`} className="sr-only">Key for {e.name}, for this session only</label>
          <input
            id={`typed-key-${e.name}`}
            type="password"
            autoComplete="off"
            spellCheck={false}
            className={field}
            value={key}
            onChange={(ev) => setKey(ev.target.value)}
            placeholder="key for this session only"
            data-testid={`typed-key-${e.name}`}
          />
          <button type="submit" className={button} disabled={!key} data-testid={`use-key-${e.name}`}>Use</button>
          {e.typed && <button type="button" className={button} onClick={() => onTypedKey(e.name, "")} data-testid={`forget-key-${e.name}`}>Forget</button>}
        </form>
      )}
    </div>
  );
}

function Defaults({ settings, onDefaults }: { settings: SettingsView; onDefaults: (change: DefaultsChange) => void }) {
  const { targets, formats } = settings.defaults;
  const order = settings.targets.map((t) => t.key);
  return (
    <section aria-labelledby="settings-defaults" className="flex flex-col gap-1">
      <h3 id="settings-defaults" className="font-bold">Defaults for this session</h3>
      <p className="text-muted-foreground">For jobs, and for Save in an episode opened from now on; never written to vid2sub.toml (Copy settings has them).</p>
      <fieldset className="flex flex-wrap gap-x-3 gap-y-1">
        <legend className="mb-1">Translate to</legend>
        {settings.targets.map((t) => (
          <label key={t.key} className="flex items-center gap-1">
            <input type="checkbox" className="size-4 accent-(--primary)" checked={targets.includes(t.key)}
              disabled={targets.length === 1 && targets.includes(t.key)}
              onChange={(ev) => onDefaults({ targets: withTarget(targets, t.key, ev.target.checked, order) })} data-testid={`target-${t.key}`} />
            {t.label}
          </label>
        ))}
      </fieldset>
      <label className="flex items-center gap-1">
        <input type="checkbox" className="size-4 accent-(--primary)" checked={formats.includes("ass")}
          onChange={(ev) => onDefaults({ formats: ev.target.checked ? ["srt", "ass"] : ["srt"] })} data-testid="default-ass" />
        ASS too (SRT is always written)
      </label>
    </section>
  );
}

function CopySettings({ toml }: { toml: string }) {
  const [copied, setCopied] = useState<"yes" | "no" | null>(null);
  const copy = () => {
    void navigator.clipboard?.writeText(toml).then(() => setCopied("yes"), () => setCopied("no"));
  };
  return (
    <section aria-labelledby="settings-copy" className="flex flex-col gap-1">
      <h3 id="settings-copy" className="font-bold">Copy settings</h3>
      <p className="text-muted-foreground">This session's defaults as TOML, to paste over [defaults] in vid2sub.toml. It never holds a key.</p>
      <pre className="overflow-x-auto rounded-md border border-border bg-muted p-2 font-mono text-xs" data-testid="settings-toml">{toml}</pre>
      <div className="flex items-center gap-2">
        <button type="button" className={button} onClick={copy} data-testid="copy-settings">Copy settings</button>
        <span role="status" className="text-muted-foreground">{copied === "yes" ? "Copied" : copied === "no" ? "The browser wouldn't copy: select the text instead" : ""}</span>
      </div>
    </section>
  );
}
