// Compiles the Council engine to CommonJS under .bench/ so plain node scripts
// can require it. Shared by run-eval-wave.mjs (live waves) and
// verify_council_orchestration.mjs (offline replay), which must run the exact
// same build: a harness that tested a differently-compiled engine would be
// testing something the waves never execute.
import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";

export function walk(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)],
  );
}

export function ensureBenchBuild(root) {
  const marker = path.join(root, ".bench", "council", "skill", "index.js");
  const srcNewest = ["council", "config", "lib"]
    .flatMap((d) => walk(path.join(root, d)))
    .filter((f) => f.endsWith(".ts"))
    .reduce((t, f) => Math.max(t, statSync(f).mtimeMs), 0);
  if (existsSync(marker) && statSync(marker).mtimeMs > srcNewest) return;
  execFileSync("npx", ["tsc", "-p", path.join(root, "scripts", "tsconfig.bench.json")], {
    cwd: root,
    stdio: "inherit",
  });
  // tsc emits require("@/...") verbatim; rewrite to relative paths.
  for (const f of walk(path.join(root, ".bench")).filter((f) => f.endsWith(".js"))) {
    const depth = path
      .relative(path.join(root, ".bench"), path.dirname(f))
      .split(path.sep)
      .filter(Boolean).length;
    const prefix = depth === 0 ? "./" : "../".repeat(depth);
    const s = readFileSync(f, "utf8");
    const out = s.replace(/require\("@\//g, `require("${prefix}`);
    if (out !== s) writeFileSync(f, out);
  }
}
