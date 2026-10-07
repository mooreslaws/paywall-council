// Review one paywall screenshot from the command line.
//
//   ANTHROPIC_API_KEY=... node scripts/review.mjs <screenshot> \
//     [--markets US,EU,UK] [--hook "..."]... [--description "..."] \
//     [--cancellation "..."] [--extra-charges "..."] [--budget 1.5] \
//     [--out report.md] [--json result.json] [--stub]
//
// The screenshot is cut into tiles the way AppLaw cuts it
// (lib/images.examinerImages) and every tile keeps its slice, so element
// boxes the Examiner reports inside a tile map back onto the whole page.
// Without the slice a tall capture's marks land in the wrong place.
//
// The hooks, description, cancellation and extra-charge flags are what the
// seller declares about the funnel; the review weighs them against the
// screen. Left out, the review says it had no such context.
//
// --stub runs the fixture council: no key, no cost, for checking the
// plumbing. The report goes to stdout unless --out names a file; --json
// writes the whole result (findings, marks, elements, usage).
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { ensureBenchBuild } from "./bench-build.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    markets: { type: "string", default: "US,EU,UK" },
    hook: { type: "string", multiple: true, default: [] },
    description: { type: "string", default: "" },
    cancellation: { type: "string", default: "" },
    "extra-charges": { type: "string" },
    budget: { type: "string", default: "1.5" },
    out: { type: "string" },
    json: { type: "string" },
    stub: { type: "boolean", default: false },
  },
});

const file = positionals[0];
if (!file) {
  console.error(
    "usage: node scripts/review.mjs <screenshot> [--markets US,EU,UK] [--hook ...] [--out report.md] [--json result.json] [--stub]",
  );
  process.exit(2);
}

ensureBenchBuild(ROOT);
const require = createRequire(import.meta.url);
const { examinerImages } = require(path.join(ROOT, ".bench/lib/images.js"));
const { costUsd } = require(path.join(ROOT, ".bench/config/model-prices.js"));
const council = require(
  path.join(ROOT, ".bench/council", values.stub ? "stub/index.js" : "skill/index.js"),
).default;

// The engine finds its knowledge base here unless told otherwise.
process.env.KB_ROOT ??= path.join(ROOT, "kb", "applaw");

const { tiles, coverageLimited } = await examinerImages(readFileSync(file));
const extra = values["extra-charges"];
const result = await council.run(
  {
    markets: values.markets
      .split(",")
      .map((m) => m.trim().toUpperCase())
      .filter(Boolean),
    hooks: values.hook,
    description: values.description,
    cancellation: values.cancellation,
    extraCharges: extra ? { declared: true, details: extra } : { declared: false },
    screenshots: tiles,
    screenshotCoverageLimited: coverageLimited,
  },
  {
    budgetUsd: Number(values.budget),
    onStage: (e) => process.stderr.write(`${e.agent}: ${e.status}\n`),
  },
);

if (values.out) writeFileSync(values.out, result.reportMarkdown, "utf8");
else process.stdout.write(`${result.reportMarkdown}\n`);
if (values.json) writeFileSync(values.json, JSON.stringify(result, null, 2), "utf8");

// The stub reports fixture usage, so its "cost" is make-believe.
const cost = result.usage.reduce((sum, u) => sum + costUsd(u.model, u), 0);
const spent = values.stub ? "stub, no model was called" : `$${cost.toFixed(3)}`;
process.stderr.write(
  `\nrisk ${result.risk}, ${result.findings.length} finding(s), ${tiles.length} tile(s), ${spent}\n`,
);
