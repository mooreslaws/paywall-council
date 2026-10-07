// Product limits (spec §6.3, §7, §8, §9). Enforced client AND server side.
// Rate limits are env-overridable per §7.5; parse overrides where consumed.

export const LIMITS = {
  hooks: { min: 2, max: 3, maxChars: 300 },
  descriptionMaxChars: 3000,
  // An app name, not a legal entity: long enough for "Calm: Sleep & Meditation".
  brandNameMaxChars: 80,
  billingMaxChars: 500,

  screenshot: {
    maxFiles: 1,
    maxBytes: 10 * 1024 * 1024,
    mimes: ["image/png", "image/jpeg", "image/webp"],
    // Decision #8 (2026-07-13): the ORIGINAL file is stored and evaluated;
    // compression is for the interface only. 1568 px was the vision ceiling
    // when this was written; Sonnet 5 accepts up to 2576 px on the long edge.
    // We keep 1568 as the normal tile edge because a 2576 tile costs ~2.8x
    // the image tokens, and at the standard ~1:2 tile shape 1568 is already
    // legible. Very tall stitched screenshots are sliced into vertical tiles
    // for the Examiner so text stays legible (M4/M5).
    examinerLongEdgePx: 1568,
    // Rescue edge for pages so tall that tiles had to grow past the ~1:2
    // shape (examinerImages widens tiles before it drops content). A widened
    // tile downscaled to 1568 crushes the text; re-encoding just those tiles
    // at the Sonnet 5 ceiling keeps them readable at a bounded extra cost.
    examinerLongEdgeTallRescuePx: 2576,
    tallAspectRatioForTiling: 2.2,
  },

  // Phone or browser window, for the frame the screenshot is shown in
  // (lib/capture-kind.ts). Display only, per decision 22: nothing the engine
  // reads depends on these.
  capture: {
    // Taller than one screen. The tallest phone screen shipping today is
    // about 2.23 to one, so anything past this was scrolled, not snapped.
    // It matches tallAspectRatioForTiling by coincidence rather than by
    // dependency: that number answers "does this need slicing for the
    // model", this one answers "does the frame need to scroll".
    longAspectRatio: 2.2,
    // Portrait enough to be a phone screen rather than a monitor. Only
    // consulted for captures of one whole screen, where the two do not
    // overlap.
    portraitAspectRatio: 1.6,
    // Raw width at or below which a scroll capture is read as a phone.
    // Galaxy S24 Ultra and the 1440p laptops both sit exactly here; the tie
    // goes to the phone and the manual switch settles the rest.
    widestPhonePx: 1440,
  },

  rate: {
    uploadsPerMin: 10,
    // A submit starts a two-to-three minute run, so this is a guard against
    // a stuck button rather than against volume: the money guards are what
    // bound volume. It used to be a bare 6 inline in the route, which is
    // also why it was the one rate limit with no env override.
    submitsPerMin: 6,
    promoAttemptsPerHour: 5, // per user AND per IP (§7.5)
    // The wizard's autosave sends at most one PATCH every four seconds while
    // someone types (components/wizard/autosave.ts), fifteen a minute, plus
    // one on every step change. 20 was workable but left almost nothing for
    // the step saves or a second open tab; a refused save is held and resent
    // rather than lost, so meeting the ceiling costs time, not answers. 60 is
    // four times what typing alone produces. 120 was also proposed; it
    // doubles what a script holding a session can write, for no case a
    // person meets.
    draftPatchesPerMin: 60,
    // Problem reports (/report), per address and per signed-in person. Room
    // for someone who finds three things in one sitting and sends each with
    // a screenshot; a person who needs more can write to the contact address.
    // RATE_REPORTS_PER_HOUR overrides it.
    reportsPerHour: 10,
  },

  // What /report takes. The screenshot obeys the same rules as a review's
  // (screenshot.maxBytes and mimes above).
  report: {
    messageMaxChars: 2000,
    contactMaxChars: 200,
  },

  // targetUsd / hardCapUsd bound ONE run. perUserDailyUsd and globalDailyUsd
  // bound volume, which is what public sign-up exposes. Both are
  // env-overridable: BUDGET_PER_USER_DAILY_USD, BUDGET_GLOBAL_DAILY_USD.
  budget: {
    targetUsd: 0.5,
    hardCapUsd: 1.0,
    perUserDailyUsd: 1.0,
    // Invited testers only (profiles.is_tester). Three settled runs a day at
    // the observed ~$0.40, which is exactly the rounds an invite hands out.
    perTesterDailyUsd: 2.0,
    globalDailyUsd: 50.0,
  },
  rounds: { newUser: 1, promoDefault: 5 },

  // Re-issues of one report. Answering its open question re-runs the whole
  // council and costs no round, so both numbers are what keeps a free action
  // bounded (lib/council-run.ts).
  //
  // `answers` is the product limit: answers that came back as a revised
  // report. The report contract allows one follow-up question, and the
  // second leaves room for a correction. An answer whose revision failed is
  // put back and does not count, so a provider outage cannot use it up.
  //
  // `runs` is the money limit: revisions started, failed ones included. It
  // is what stops a revision that fails the same way every time from being
  // retried for free without end, and it leaves one failed run per answer
  // before it is reached.
  reissue: { answers: 2, runs: 4 },

  // How many reviews may run at once across the whole service. The per-user
  // limit is a unique index in the schema; this is the global one. Env
  // override: MAX_RUNNING_CHECKS, where 0 is honoured and means "accept no
  // new runs".
  //
  // This was 2, guessed from "a run holds a process for two to three minutes
  // and the container has 2 GB". Measured, the guess was wrong by an order of
  // magnitude, because a run spends those minutes waiting on HTTP rather than
  // holding anything:
  //
  //   tiling the tallest capture in the corpus (1234x13475, six tiles)
  //     peaks at +14 MB for 0.7 s and then releases
  //   the tiles a run holds for its whole life        0.4 MB
  //   the KB's Python, spawned twice per run          29 MB for a fraction
  //                                                   of a second each time
  //
  // So a concurrent run costs about 2 MB of steady state, and even twenty
  // starting their tiling in the same instant is under 300 MB of transient.
  // The real ceiling above this number is the model provider's rate limit,
  // not the box, and the SDK already retries a 429 with backoff before the
  // run's own retry sees it.
  concurrency: { maxRunningChecks: 20 },

  // How long a check may sit in 'running' before it is treated as dead. Both
  // the capacity guard and the per-user spend reserve exclude runs older than
  // this, so a crashed run stops holding a slot and stops holding its owner
  // at their daily ceiling, and the janitor settles it. A live run stops
  // itself a minute before this, so only a run whose process is gone ever
  // reaches the janitor. Measured from submitted_at, which a revision resets.
  run: { staleMs: 15 * 60 * 1000 },
} as const;
