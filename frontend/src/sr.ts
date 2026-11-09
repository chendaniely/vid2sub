// shinyreact's hooks, read from the window.shinyreact global the server loads (the
// shinyreact-build-app skill, Step 1), as recordings' sr.ts does. The npm package is imported for
// its TYPES only: `import type` is erased, so no second copy of React or the hooks can enter the
// bundle. Every output is subscribed, and every input and message handler lives, in App
// (shinyreact 0.1.0 drops a message that has no handler, and an unmounted output logs errors).
import type * as SR from "@posit-dev/shinyreact";

type Hooks = Pick<
  typeof SR,
  | "useShinyInput" | "useShinyOutputValue" | "useShinyOutputStatus" | "useShinyOutputError"
  | "useShinyInitialized" | "useSetShinyInput" | "useShinyMessageHandler"
>;

const shinyreact = (window as unknown as { shinyreact: Hooks }).shinyreact;

export const {
  useShinyInput, useShinyOutputValue, useShinyOutputStatus, useShinyOutputError,
  useShinyInitialized, useSetShinyInput, useShinyMessageHandler,
} = shinyreact;
