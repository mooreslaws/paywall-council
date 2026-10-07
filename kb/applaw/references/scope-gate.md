# Scope Gate (A0)

Run this before A1 Intake, on every supplied screenshot, before spending any pattern, legal, or scoring effort.

## Classify

- `checkout_or_pricing`: the screen shows a specific price tied to a plan or item, a payment control (pay now, place order, an express-pay button, a card-entry field), a plan/subscription selector, or a negative-option consent step (a checkbox or toggle that adds a recurring charge).
- `non_checkout`: the screen is a marketing or informational page instead. Signals include a hero headline and tagline, a feature grid, a "trusted by" logo strip, blog or article cards, an FAQ, or testimonials, with no price, payment control, plan selector, or negative-option step anywhere on the page.

A page that only names a "Pricing" nav link without showing a price is `non_checkout`. A page with a visible price table plus a "cancel anytime" or "no subscription" line is `checkout_or_pricing`, even without a payment form, because it is still a plan-selection or pricing step in the funnel.

## If non_checkout

Skip A2-A6. Produce the report directly at A7 using the ordinary Report Contract v3 section order, filled as follows:

- `RISK`: `very low`. The private score stays in the 1-15 band; never print it.
- `Verdict`: state plainly, in one sentence, that the supplied screen is a marketing or informational page, not a checkout or pricing screen.
- `Material Findings`: `None.`
- `Liability and Consequences`: `None.`
- `Mitigating and Low-Risk Elements`: 1-4 short bullets noting the absence of price, payment controls, timers, or preselected options.
- `Missing Context`: state that this is not a checkout or pricing screen and that target jurisdiction was not supplied; ask for the actual checkout or pricing screen.
- `Priority Actions`: ask for the real checkout or pricing screen, the explicit target jurisdiction(s), and the buyer type (consumer vs. business).
- `Disclaimer`: the exact contract sentence, unchanged.

Do not manufacture a checkout finding from marketing copy, a logo strip, or a testimonial alone merely because the page is persuasive. A logo strip or testimonial without a platform-review attribution stays in `Mitigating and Low-Risk Elements` or `Missing Context`, per `references/evaluation-workflow.md`.

A `non_checkout` classification does not by itself raise a review-authenticity question. Ask that question only when an unresolved social/review-platform module is actually visible, per `references/report-contract.md`.

## If checkout_or_pricing

Continue the ordinary A1-A8 flow in `references/evaluation-workflow.md`. A visible price or plan table without a final payment form is still in scope; treat the absent payment step as an ordinary `Missing Context` limitation, not a reason to skip the pattern specialists.

## Ambiguous Cases

If a screen mixes both, for example a pricing table embedded inside a longer marketing page, classify as `checkout_or_pricing` and run the full flow, scoped to the pricing or plan module for the pattern specialists.
