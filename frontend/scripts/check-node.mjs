// Fail fast on a Node older than 22: shinyreact builds and tests its JS with Node 22
// (pkg-js/.nvmrc), and Vite 5 and Vitest 3 need 18 or later. Newer majors are accepted: CI and
// .nvmrc pin 22, and a developer's Node may be ahead of it.
const major = Number(process.versions.node.split(".")[0]);
if (!(major >= 22)) {
  console.error(`Node 22 or later is required (found ${process.versions.node}). Run: nvm use`);
  process.exit(1);
}
