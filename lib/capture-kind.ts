// Is this screenshot a phone or a browser window?
//
// Decision 22 of the v2 quiz settled what the answer is allowed to touch:
// display only. The frame around the preview and around the evidence panel,
// and nothing else. No norm, no prompt, no verdict depends on it, which is
// why this module has no model in it and no access to the engine.
//
// Two signals, used where each one is actually informative:
//
//   - For a capture of one whole screen, the aspect ratio separates the two
//     cleanly and with no overlap. Phones are portrait between about 1.78
//     and 2.23 to one; monitors are landscape.
//   - For a scroll capture, the aspect ratio says how long the page is, not
//     what read it, so only the pixel width is left. There the two genuinely
//     overlap: a Galaxy S24 Ultra rasterises at 1440 across, which is also a
//     laptop's width. The threshold below puts that overlap on the mobile
//     side, because the people this is built for screenshot their own
//     paywall on their own phone, and the manual switch on the Evidence step
//     exists for the rest.
//
// Widths are raw pixels, not CSS pixels: a phone at device-pixel-ratio 3
// writes a 1290 px file for a 430 px screen, and the file is what we get.

import { LIMITS } from "@/config/limits";

export type CaptureKind = "mobile" | "desktop";

export interface CaptureShape {
  kind: CaptureKind;
  // Taller than one screen, so the frame has to scroll and the preview has
  // to say so rather than quietly showing only the top.
  long: boolean;
}

export function detectCaptureKind(width: number, height: number): CaptureShape {
  const { longAspectRatio, portraitAspectRatio, widestPhonePx } = LIMITS.capture;
  if (width <= 0 || height <= 0) return { kind: "mobile", long: false };

  const ratio = height / width;
  const long = ratio > longAspectRatio;
  const kind: CaptureKind = long
    ? width <= widestPhonePx
      ? "mobile"
      : "desktop"
    : ratio > portraitAspectRatio
      ? "mobile"
      : "desktop";
  return { kind, long };
}
