# Paywall Council

The review engine behind [AppLaw](https://applaw.dev). It reads a screenshot
of a subscription paywall, together with what the seller declares about the
funnel, and writes a consumer-protection review against US, EU and UK rules:
what on the screen is a risk, which norm it meets, how serious it is, and
what to change.

This repository holds the engine and its knowledge base. The AppLaw web app
(accounts, the wizard, the report pages) is not part of it.

## How a review is made

A review is a chain of model calls with deterministic code between them, so
the legal reasoning runs on rules you can read rather than on whatever a
model happens to remember.

1. **Scope gate** (model) decides whether the screen is a checkout or pricing
   step at all. If it is not, the review says so instead of judging it.
2. **Examiner** (model, vision) reads the screen into elements (price,
   button, timer, checkbox, fine print and so on) with their positions, and
   into facts from a fixed vocabulary.
3. **Routing** (code, `kb/applaw/scripts/route_norms.py`) maps the confirmed
   facts to the norms they trigger in the declared markets: established,
   conditional, or not reached.
4. **Pattern judges** (models, one per family: pressure, disclosure, consent,
   cancellation, upsell) decide which catalogued patterns the screen shows.
5. **Legal dossier** (code) assembles the slice of norms, cases and
   enforcement outcomes the report may cite, and nothing else.
6. **Counsel** (model) writes the report in Public Report Contract v3
   (`kb/applaw/references/`).
7. **Validator** (code, `kb/applaw/scripts/validate_report.py`) checks the
   report's form and that every citation comes from the dossier. A rejected
   draft goes back to Counsel.
8. **Marks** (code, `council/skill/marks.ts`) tie each finding to the
   elements it is about, so an interface can draw it on the screenshot.

## Layout

| Path | What |
|---|---|
| `council/` | The engine. `skill/` is the real pipeline, `stub/` returns fixture verdicts for offline work, `interface.ts` is the contract between the engine and whatever drives it |
| `kb/applaw/` | The knowledge base: `taxonomy/` (patterns, norms, jurisdiction routes, enforcement outcomes), `references/` (the report contract and method), `cases/`, `sources/`, `constitutions/`, the Python `scripts/` the engine calls, and `eval/` fixtures |
| `lib/images.ts` | How a screenshot is cut into tiles for the Examiner, each with the slice of the page it covers |
| `config/` | Which model runs (`models.ts`), what it costs (`model-prices.ts`), product limits (`limits.ts`) |
| `scripts/` | Build, tests, and `review.mjs` for reviewing a screenshot from the command line |

## Run it

Needs Node 22 or later and Python 3 (standard library only).

```bash
npm install
npm run verify
```

`verify` type-checks the engine, replays its orchestration with scripted
model replies (no API key, no network; the knowledge base, the Python
validator and the pricing table stay real), checks the report parser and
the marks, and runs the knowledge base's own validation and checksum suite.

To review a screenshot with real models (an Anthropic API key; one review
costs roughly $0.15 to $0.30):

```bash
ANTHROPIC_API_KEY=... node scripts/review.mjs paywall.png \
  --markets US,EU --hook "Lose 10 kg in 12 weeks" --out report.md --json result.json
```

`--stub` runs the fixture council instead: no key, no cost, useful for
checking the plumbing. `COUNCIL_PROVIDER=openai` with `OPENAI_API_KEY` runs
the same pipeline on an OpenAI model; the model ids live in
`config/models.ts`.

## What is left out

- Reviews of identifiable businesses. A risk verdict on a named company's
  paywall, published without being asked for, is an accusation. The report
  samples kept in `kb/applaw/eval/report_samples/` are about generic or
  anonymised screens.
- Screenshots of third-party products used in AppLaw's own evaluations.

## Not legal advice

What the engine produces is automated analysis for information. It is not
legal advice and does not replace a qualified lawyer.

## License

MIT, see `LICENSE`. The knowledge base quotes and summarises public legal
sources (EU, UK and US legislation, regulator guidance and decisions, court
documents); those texts remain subject to their publishers' terms.

This repository is a snapshot of the engine as it runs in AppLaw, refreshed
from time to time.
