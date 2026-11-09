// @vitest-environment node
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import config, { EXTERNAL, GLOBALS } from "../vite.config.js";

describe("the build", () => {
  it("keeps React and react-dom/client external and bundles the react-dom index", () => {
    // why: shinyreact's ReactDOM global is react-dom/client only, with no createPortal or
    // flushSync (recordings' docs/upstream-issues.md). Mapping "react-dom" to it breaks every
    // portal (the plan's Global Constraints).
    expect(EXTERNAL).toEqual(["react", "react-dom/client"]);
    expect(GLOBALS).toEqual({
      react: "window.shinyreact.React",
      "react-dom/client": "window.shinyreact.ReactDOM",
    });
    type Rollup = { external: unknown; output: { globals: unknown } };
    const rollup = (config as unknown as { build: { rollupOptions: Rollup } }).build.rollupOptions;
    expect(rollup.external).toBe(EXTERNAL);
    expect(rollup.output.globals).toBe(GLOBALS);
  });
});

// why: the config test above checks what the build is told; this one checks what it made, as
// recordings' build.test.ts does. It reads the built www/ui.js (build output, not in git) and
// shinyreact.js from the project's venv. Where either is missing the checks skip, unless told they
// must run: CI=true (set by GitHub Actions) fails a missing ui.js, and
// VID2SUB_REQUIRE_SHINYREACT=1 (make check, and CI's job that has the venv) fails a missing
// shinyreact.js.
const here = dirname(fileURLToPath(import.meta.url));
const built = join(here, "../../src/vid2sub/web/www/ui.js");
const venvLib = join(here, "../../.venv/lib");
const mustBuild = Boolean(process.env.CI);
const mustHaveShinyreact = process.env.VID2SUB_REQUIRE_SHINYREACT === "1";

function shinyreactJs(): string | undefined {
  if (!existsSync(venvLib)) return undefined;
  for (const py of readdirSync(venvLib)) {
    const path = join(venvLib, py, "site-packages/shinyreact/www/shinyreact.js");
    if (existsSync(path)) return path;
  }
  return undefined;
}

const shinyreact = shinyreactJs();

describe.skipIf(!existsSync(built) && !mustBuild)("the built bundle", () => {
  const have = existsSync(built);
  const bundle = have ? readFileSync(built, "utf8") : "";

  it("exists (CI builds before it tests)", () => {
    expect(have, `${built} is missing: run npm run build first`).toBe(true);
  });

  it.skipIf(!have)("is called with the one React that shinyreact exposes, and carries no copy of its own", () => {
    expect(bundle.trimEnd().endsWith("(window.shinyreact.React);")).toBe(true);
    expect(bundle).not.toMatch(/react\.production/);
    expect(bundle).not.toMatch(/react-dom-client/);
    expect(bundle).not.toMatch(/scheduler\.production/);
    // the react-dom index is bundled on purpose (it has createPortal and flushSync)
    expect(bundle).toMatch(/react-dom\.production/);
  });

  it.skipIf(!have || (shinyreact === undefined && !mustHaveShinyreact))(
    "bundles a react-dom of the same major.minor as the React it runs beside",
    () => {
      expect(shinyreact, "shinyreact.js not found in .venv: run uv sync").toBeDefined();
      // react-dom's own version line follows its useHostTransitionStatus export; React's in
      // shinyreact.js is the one before `.exports=`.
      const mine = bundle.match(/useHostTransitionStatus\(\)\},\w+\.version="(\d+\.\d+)\.\d+"/)?.[1];
      const theirs = readFileSync(shinyreact as string, "utf8").match(/\.version="(\d+\.\d+)\.\d+",\w+\.exports=/)?.[1];
      expect(mine).toBeDefined();
      expect(theirs).toBeDefined();
      expect(mine).toBe(theirs);
    },
  );
});
