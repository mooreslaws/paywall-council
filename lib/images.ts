// Screenshot processing (§7.3 + decision #8).
//
// Decision #8: the ORIGINAL is what gets stored and evaluated: sharp
// re-encodes at FULL resolution (pixels preserved, EXIF/GPS/ICC metadata
// dropped) and rejects corrupt/animated/tiny files. Compression exists only
// for the interface (thumb). The Examiner input respects the Anthropic vision
// ceiling (~1568 px long edge): normal shots are downscaled once; very tall
// stitched screenshots are sliced into overlapping portrait tiles so the text
// stays legible instead of being crushed by a single downscale.
import sharp, { type Metadata, type Sharp } from "sharp";
import { LIMITS } from "@/config/limits";
import { detectCaptureKind } from "./capture-kind";

export class ImageError extends Error {
  constructor(public readonly reason: "corrupt" | "animated" | "too_small") {
    super(reason);
  }
}

export interface ProcessedUpload {
  original: Buffer; // re-encoded full-resolution, upright, metadata stripped
  thumb: Buffer; // webp display copy (THUMB_WIDTH_PX), UI only
  width: number; // of the upright image, which is what every frame shows
  height: number;
  mime: string;
}

// The display copy every product page shows, the original being for the
// Examiner and the admin only (§21.1). It was 360 px wide, sized for the
// spec's 320 px thumbnail, and the evidence panel now draws it far larger:
// a desktop capture filled a ~744 px column from 360 px, about 4x on a
// retina screen, and the fine print the marks point at could not be read.
// Wide enough to stay sharp at 2x in the frame it is shown in.
const THUMB_WIDTH_PX = { mobile: 720, desktop: 1200 } as const;

// WebP cannot encode an edge past 16383 px. A scroll capture past about 45:1
// went over it at thumb width and the whole upload failed, so the thumb is
// held under it and narrows instead. The Examiner reads the original.
const THUMB_MAX_HEIGHT_PX = 16000;

export async function processUpload(input: Buffer): Promise<ProcessedUpload> {
  let meta: Metadata;
  try {
    meta = await sharp(input).metadata();
  } catch {
    throw new ImageError("corrupt");
  }
  const width = meta.width ?? 0;
  const height = meta.height ?? 0;
  if (!width || !height) throw new ImageError("corrupt");
  if ((meta.pages ?? 1) > 1) throw new ImageError("animated");
  if (width < 2 || height < 2) throw new ImageError("too_small");
  const format = meta.format;
  if (format !== "png" && format !== "jpeg" && format !== "webp") {
    throw new ImageError("corrupt");
  }

  // Upright first. Re-encoding drops the EXIF orientation tag, and without
  // applying it a photo of a screen taken on its side was stored, framed and
  // read by the Examiner sideways.
  let original: Buffer;
  let mime: string;
  try {
    const upright = () => sharp(input).autoOrient();
    if (format === "png") {
      original = await upright().png().toBuffer();
      mime = "image/png";
    } else if (format === "webp") {
      original = await upright().webp({ quality: 92 }).toBuffer();
      mime = "image/webp";
    } else {
      original = await upright().jpeg({ quality: 92, mozjpeg: true }).toBuffer();
      mime = "image/jpeg";
    }
  } catch {
    throw new ImageError("corrupt");
  }

  // The size of what was stored, not of the input: a rotation swaps them.
  const stored = await sharp(original).metadata();
  const uprightWidth = stored.width ?? width;
  const uprightHeight = stored.height ?? height;

  let thumb: Buffer;
  try {
    thumb = await sharp(original)
      .resize({
        width: THUMB_WIDTH_PX[detectCaptureKind(uprightWidth, uprightHeight).kind],
        height: THUMB_MAX_HEIGHT_PX,
        fit: "inside",
        withoutEnlargement: true,
      })
      .webp({ quality: 80 })
      .toBuffer();
  } catch {
    throw new ImageError("corrupt");
  }

  return { original, thumb, width: uprightWidth, height: uprightHeight, mime };
}

export interface ExaminerImage {
  buffer: Buffer;
  mime: string;
  // Which slice of the whole screenshot this tile is, as fractions (0..1).
  // The Examiner reports element boxes inside the tile it was shown; this is
  // what turns those back into coordinates on the page the user uploaded.
  slice: { y: number; h: number };
}

export interface ExaminerImageSet {
  tiles: ExaminerImage[];
  // True when the source was taller than TILE_CAP tiles could cover even
  // after widening. Long scroll-captured funnels (quiz results, testimonial
  // walls, award/press strips, guarantee badges) routinely run past a fixed
  // 8-tile budget, and that content sits BELOW the price/CTA, not above it,
  // so a silent head-only crop was reliably eating exactly the evidence the
  // Social/Review-Platform Module, fake-awards, fake-media-features,
  // before-after-social-proof, and money-back-misdirection patterns need.
  // Downstream must disclose this rather than let the Examiner assume it
  // saw the whole page.
  coverageLimited: boolean;
}

// Soft target: prefer this many tiles at the normal tile height. Hard
// ceiling exists only to bound cost/latency on pathological inputs, and
// widens tiles (trading resolution for coverage) before it ever drops
// content, so a long page loses sharpness at the margins before it loses
// entire sections.
const SOFT_TILE_TARGET = 8;
const HARD_TILE_CAP = 20;

export async function examinerImages(original: Buffer): Promise<ExaminerImageSet> {
  const meta = await sharp(original).metadata();
  const w = meta.width ?? 0;
  const h = meta.height ?? 0;
  if (!w || !h) throw new ImageError("corrupt");

  const maxEdge = LIMITS.screenshot.examinerLongEdgePx;
  const encodeResized = (s: Sharp, edge: number = maxEdge) =>
    s
      .resize({ width: edge, height: edge, fit: "inside", withoutEnlargement: true })
      .webp({ quality: 82 })
      .toBuffer();

  if (Math.max(w, h) <= maxEdge || h / w <= LIMITS.screenshot.tallAspectRatioForTiling) {
    return {
      tiles: [
        { buffer: await encodeResized(sharp(original)), mime: "image/webp", slice: { y: 0, h: 1 } },
      ],
      coverageLimited: false,
    };
  }

  // tall stitched screenshot → overlapping portrait tiles covering the WHOLE
  // page. Start at the normal ≈1:2 tile height; if that would need more than
  // SOFT_TILE_TARGET tiles, grow the tile height (not the tile count) so the
  // full page still fits within a bounded number of calls. Only if the page
  // is so tall that even HARD_TILE_CAP tiles at a legible minimum height
  // can't cover it do we fall back to a head-only crop, and in that case we
  // say so via coverageLimited so the report can disclose the gap instead of
  // silently pretending full coverage.
  const baseTileH = Math.round(w * 2);
  const neededAtBase = Math.ceil(h / (baseTileH * 0.94));
  const tileH =
    neededAtBase <= SOFT_TILE_TARGET
      ? baseTileH
      : Math.min(Math.round(h / (SOFT_TILE_TARGET * 0.94)), Math.round(w * 6));
  // Widened tiles (taller than the ~1:2 base shape) lose text sharpness when
  // downscaled to the normal edge, so they get the larger rescue edge,
  // legibility is exactly what widening was trading away.
  const tileEdge =
    tileH > baseTileH
      ? LIMITS.screenshot.examinerLongEdgeTallRescuePx
      : LIMITS.screenshot.examinerLongEdgePx;
  const overlap = Math.round(tileH * 0.06);

  const tiles: ExaminerImage[] = [];
  let top = 0;
  let coverageLimited = false;
  while (top < h) {
    if (tiles.length >= HARD_TILE_CAP) {
      coverageLimited = true;
      break;
    }
    const th = Math.min(tileH, h - top);
    const buffer = await encodeResized(
      sharp(original).extract({ left: 0, top, width: w, height: th }),
      tileEdge,
    );
    tiles.push({ buffer, mime: "image/webp", slice: { y: top / h, h: th / h } });
    if (top + th >= h) break;
    top = top + th - overlap;
  }
  return { tiles, coverageLimited };
}
