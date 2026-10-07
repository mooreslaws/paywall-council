#!/usr/bin/env node
// Offline check for the finding-to-element matcher.
//
// The orchestration harness replays whole runs and says nothing about marks;
// a screenshot could be drawn on entirely wrongly and every existing check
// would stay green. This asserts the three things that make a mark worth
// drawing: it points at the element the finding is actually about, it is
// silent when it cannot tell, and its coordinates are on the page the user
// uploaded rather than on whatever tile the model happened to read.

import path from "node:path";
import { ensureBenchBuild } from "./bench-build.mjs";

const ROOT = path.resolve(import.meta.dirname, "..");
ensureBenchBuild(ROOT);
const { marksForFinding, toFullImageBox } = await import(
  path.join(ROOT, ".bench", "council", "skill", "marks.js")
);

let failures = 0;
function check(name, condition, detail = "") {
  if (condition) {
    console.log(`ok   ${name}`);
  } else {
    failures++;
    console.log(`FAIL ${name}${detail ? `: ${detail}` : ""}`);
  }
}

const ELEMENTS = [
  { id: "el-01", kind: "timer", text: "Your discount expires in 09:57", box: { x: 0.04, y: 0.02, w: 0.92, h: 0.04 }, confidence: 0.95 },
  { id: "el-02", kind: "price", text: "$0.44 per day", box: { x: 0.55, y: 0.25, w: 0.35, h: 0.08 }, confidence: 0.93 },
  { id: "el-03", kind: "phrase", text: "billed as $159.99 yearly", box: { x: 0.08, y: 0.33, w: 0.5, h: 0.03 }, confidence: 0.88 },
  { id: "el-04", kind: "checkbox", text: "Personal coach +$9.99/mo", box: { x: 0.06, y: 0.52, w: 0.88, h: 0.08 }, confidence: 0.91 },
  { id: "el-05", kind: "fine_print", text: "renews automatically at $159.99 every 12 months", box: { x: 0.06, y: 0.75, w: 0.88, h: 0.09 }, confidence: 0.86 },
  // Deliberately unsure. Nothing should ever be drawn from this one.
  { id: "el-06", kind: "button", text: "Get my plan", box: { x: 0.06, y: 0.64, w: 0.88, h: 0.07 }, confidence: 0.4 },
];

const finding = (observedEvidence, title = "", recommendedCorrection = "") => ({
  observedEvidence,
  title,
  recommendedCorrection,
});

// 1. The element whose own words the finding quotes is the one marked.
const renewal = marksForFinding(
  finding(
    'The plan card shows "$0.44 per day" while the recurring charge appears only as "billed as $159.99 yearly" in smaller text.',
    "Renewal price not disclosed before commitment",
  ),
  ELEMENTS,
);
check("the quoted price and its fine print are both marked", renewal.length >= 2, JSON.stringify(renewal.map((m) => m.elementId)));
check(
  "exactly one mark is primary",
  renewal.filter((m) => m.primary).length === 1,
);
check(
  "the mark kind follows the element kind",
  renewal.find((m) => m.elementId === "el-03")?.kind === "highlight" &&
    renewal.find((m) => m.elementId === "el-02")?.kind === "circle",
  JSON.stringify(renewal.map((m) => [m.elementId, m.kind])),
);

// 2. A finding about something the Examiner did not report is left alone.
const unmatched = marksForFinding(
  finding("The cancellation route is described only in an email sent after purchase."),
  ELEMENTS,
);
check("a finding with no matching element carries no mark", unmatched.length === 0, JSON.stringify(unmatched));

// 3. A low-confidence element is never drawn, even when the text matches.
const lowConfidence = marksForFinding(finding('The "Get my plan" button starts the trial.'), ELEMENTS);
check("an element the Examiner was unsure of is not drawn", lowConfidence.length === 0, JSON.stringify(lowConfidence));

// 4. Short strings do not match. "97%" or "$5" appear all over a paywall.
const noisy = marksForFinding(finding("The screen shows 09:57 somewhere."), [
  { id: "el-99", kind: "text", text: "09:", box: { x: 0, y: 0, w: 0.1, h: 0.1 }, confidence: 1 },
]);
check("a too-short element text is not a match", noisy.length === 0, JSON.stringify(noisy));

// 5. One shared common word is not a match, and a word is never found inside
// a longer one. This is the stub's own fixture as it used to read: a finding
// about the renewal fine print that paraphrases instead of quoting. The old
// substring matcher made the countdown its primary circle ("discount" inside
// "discounted") and circled the confident CTA on the single word "plan",
// while the fine print the finding is about got nothing.
const STUB_SCREEN = [
  { id: "el-01", kind: "timer", text: "Your discount expires in 09:57", box: { x: 0.04, y: 0.02, w: 0.92, h: 0.04 }, confidence: 0.95 },
  { id: "el-06", kind: "button", text: "Get my plan", box: { x: 0.06, y: 0.64, w: 0.88, h: 0.07 }, confidence: 0.97 },
  { id: "el-07", kind: "fine_print", text: "renews automatically at $159.99 every 12 months, until cancelled", box: { x: 0.06, y: 0.75, w: 0.88, h: 0.09 }, confidence: 0.86 },
];
const paraphrase = marksForFinding(
  finding(
    "The plan block shows a discounted introductory amount; the recurring charge and its cadence appear only in smaller text placed after the payment control.",
    "Renewal price is not disclosed before billing information",
  ),
  STUB_SCREEN,
);
check(
  "a paraphrase sharing one common word marks neither the timer nor the CTA",
  !paraphrase.some((m) => m.elementId === "el-01" || m.elementId === "el-06"),
  JSON.stringify(paraphrase.map((m) => m.elementId)),
);
const quoted = marksForFinding(
  finding(
    'The plan block leads with "$0.44 per day"; the recurring charge appears only as "renews automatically at $159.99 every 12 months, until cancelled".',
  ),
  STUB_SCREEN,
);
check(
  "the same finding quoting the fine print marks the fine print, and only it",
  quoted.length === 1 && quoted[0].elementId === "el-07" && quoted[0].primary,
  JSON.stringify(quoted.map((m) => m.elementId)),
);
const reworded = marksForFinding(
  finding("Only the small line about $159.99 every 12 months mentions the renewal."),
  STUB_SCREEN,
);
check(
  "a run of several real words still matches when the quote is reworded around it",
  reworded.length === 1 && reworded[0].elementId === "el-07",
  JSON.stringify(reworded.map((m) => m.elementId)),
);

// 6. Tile coordinates become page coordinates.
const onPage = toFullImageBox({ x: 0.1, y: 0.5, w: 0.3, h: 0.2 }, { y: 0.4, h: 0.3 });
check(
  "a box inside the second tile lands on the page",
  Math.abs(onPage.y - 0.55) < 1e-9 && Math.abs(onPage.h - 0.06) < 1e-9 && onPage.x === 0.1,
  JSON.stringify(onPage),
);
const untiled = toFullImageBox({ x: 0.1, y: 0.5, w: 0.3, h: 0.2 }, undefined);
check("an untiled image is the whole page", untiled.y === 0.5 && untiled.h === 0.2);

console.log(
  failures === 0
    ? "\nmarks: every check clean"
    : `\nmarks: ${failures} check(s) failed`,
);
process.exit(failures === 0 ? 0 : 1);
