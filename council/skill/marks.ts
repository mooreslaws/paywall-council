// Ties a finding to the pixels it is about.
//
// The report says what is wrong in prose; the Examiner separately reports the
// elements it read, each with a box. Nothing in the report names an element
// id, and deliberately so: the report contract, the validator and the Counsel
// prompt are the most load-bearing things in the engine, and a marked-up
// screenshot is not worth reopening them. So the link is made here, in code,
// after the report parses, by finding the elements whose own text the finding
// quotes back.
//
// Failure is silence. An unmatched finding simply carries no mark and still
// appears in the report, which is the decision on record: a circle drawn
// around the wrong thing is worse than no circle.

import type { CouncilFinding, FindingMark, MarkKind, ScreenElement } from "@/council/interface";

// Below this the Examiner is guessing at the box, and a guessed box is the
// failure this whole feature has to avoid.
const MIN_CONFIDENCE = 0.6;

// Shorter than this and a match means nothing: "12", "$5" and "Yes" occur all
// over a paywall.
const MIN_TEXT = 4;

// A partial match has to share at least this many real words in a row. One
// word was never enough: "plan", "trial", "month" and "price" sit in half the
// findings and on half the buttons, and a single shared word drew a confident
// circle around the "Get my plan" button for a finding about the fine print.
const MIN_SHARED_WORDS = 2;

// Words that identify nothing on a paywall. A run made of these plus one
// real word is still a one-word match.
const STOP_WORDS = new Set([
  "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is",
  "it", "its", "me", "my", "of", "on", "or", "our", "per", "so", "that",
  "the", "this", "to", "us", "we", "with", "you", "your",
]);

// One finding, one circle. The extras exist because a single claim often
// spans a price and the fine print that qualifies it, but they stay quiet.
const MAX_MARKS = 3;

const KIND_TO_MARK: Record<ScreenElement["kind"], MarkKind> = {
  button: "circle",
  badge: "circle",
  price: "circle",
  toggle: "circle",
  checkbox: "circle",
  timer: "circle",
  image: "circle",
  // Circled like the rest. A bracket beside the paragraph read as pointing
  // away from it, on every screen it was tried on (issue #104), and now that
  // a loop runs outside its element it no longer covers the words.
  fine_print: "circle",
  phrase: "highlight",
  text: "underline",
};

function normalise(s: string): string {
  return s
    .toLowerCase()
    .replace(/[‘’“”]/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

// Whole words, so "discount" is not found inside "discounted". A price or a
// count keeps its separators ("159.99", "1,000") and stays one word, which is
// how the finding quotes it back.
function words(s: string): string[] {
  return normalise(s).match(/[\p{L}\p{N}]+(?:[.,'][\p{L}\p{N}]+)*/gu) ?? [];
}

// How much of this element's own text the finding repeats, compared word by
// word. Quoting the whole element scores highest; otherwise the longest run
// of consecutive words they share, which survives Counsel rewording a quote
// slightly, counts only when it holds MIN_SHARED_WORDS real words.
function overlap(elementText: string, findingText: string): number {
  if (normalise(elementText).length < MIN_TEXT) return 0;
  const el = words(elementText);
  if (el.length === 0) return 0;
  // Padded with spaces so a run can only match on word boundaries.
  const found = ` ${words(findingText).join(" ")} `;
  const whole = el.join(" ");
  if (found.includes(` ${whole} `)) return whole.length;

  let best = 0;
  for (let start = 0; start < el.length; start++) {
    for (let end = el.length; end > start; end--) {
      const runWords = el.slice(start, end);
      const run = runWords.join(" ");
      if (run.length <= best) continue;
      if (runWords.filter((w) => !STOP_WORDS.has(w)).length < MIN_SHARED_WORDS) continue;
      if (found.includes(` ${run} `)) {
        best = run.length;
        break;
      }
    }
  }
  return best;
}

export function marksForFinding(
  finding: Pick<CouncilFinding, "observedEvidence" | "title" | "recommendedCorrection">,
  elements: ScreenElement[],
): FindingMark[] {
  // Observed evidence is the field that must describe what is on screen, so
  // it carries the most weight; the title and the correction often name the
  // same element in fewer words.
  const haystack = [finding.observedEvidence, finding.title, finding.recommendedCorrection]
    .filter(Boolean)
    .join(" · ");

  const scored = elements
    .filter((e) => (e.confidence ?? 0) >= MIN_CONFIDENCE && e.text)
    .map((e) => ({ element: e, score: overlap(e.text, haystack) }))
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score || a.element.id.localeCompare(b.element.id))
    .slice(0, MAX_MARKS);

  return scored.map(({ element }, i) => ({
    kind: KIND_TO_MARK[element.kind] ?? "circle",
    box: element.box,
    primary: i === 0,
    elementId: element.id,
  }));
}

export function attachMarks(findings: CouncilFinding[], elements: ScreenElement[]): void {
  if (elements.length === 0) return;
  for (const f of findings) {
    const marks = marksForFinding(f, elements);
    if (marks.length > 0) {
      f.marks = marks;
      f.elementIds = marks.map((m) => m.elementId);
    }
  }
}

// The Examiner is shown one image per tile of a tall screenshot and reports
// boxes inside the tile it saw. The interface stores one coordinate space:
// fractions of the whole submitted screenshot. Tiles overlap slightly, so a
// box near a seam lands inside whichever tile the Examiner named, which is
// the one it actually read.
export function toFullImageBox(
  box: ScreenElement["box"],
  tile: { y: number; h: number } | undefined,
): ScreenElement["box"] {
  if (!tile) return box;
  return { x: box.x, y: tile.y + box.y * tile.h, w: box.w, h: box.h * tile.h };
}
