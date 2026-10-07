# Scoring Rubric

## Private Score And Public Label

Calculate a private legacy score from 1 to 100. Never print it, its range, its calculation, or a color alias in the public report. Convert it deterministically:

- 1-15: `very low`
- 16-30: `low`
- 31-60: `medium`
- 61-80: `high`
- 81-100: `very high`

`very low` and `low` ordinarily indicate a transparent flow or no supported material finding. `medium` indicates at least one material ambiguity or supported moderate issue. `high` and `very high` require strong visible evidence and supported material legal mapping; `very high` is reserved for the most serious or compounded supported risks.

## Factors

Increase score for:

- Material price, renewal, cancellation, or consent terms hidden at payment.
- Preselection, bundled consent, or consent inferred from inaction.
- Repeated friction across enrollment, payment, and cancellation.
- Vulnerable audience or high-stakes product claims. This is established from the screen,
  never assumed: the flow addresses a judgement-impairing condition of this consumer, such
  as a named health or diagnosis worry, appearance with body or face photographs,
  loneliness, debt or overdue bills, or a recorded age under 18, rather than treating the
  reader as an ordinary adult buyer. Where it is present, a finding whose practice acts on
  that condition is High severity and the label moves up one step. A general-audience offer
  that merely mentions a sensitive topic is not this, and neither is a product that happens
  to be about health, money or dating.
- Strong local case/source similarity.
- Multiple supported norms across material and procedural duties.

Decrease score for:

- Clear, proximate disclosures before payment.
- Active, informed consent near the relevant action.
- Easy cancellation through the same channel.
- Evidence that the element is optional and unselected by default.
- Missing or weak local source support.

## Patterns With No Routed Norm

A pattern the Examiner saw but no routed norm reaches is not a violation and never becomes
a Material Finding. It is recorded as an observation, and it moves the label at most one
step, never past `medium`, and only under the compounding rule below.

Two reasons must be told apart, because they mean opposite things:

- The screen shows the trader doing the right thing, so a disqualifying fact fired and the
  route abstained. This is evidence of compliance and belongs in Mitigating and Low-Risk
  Elements. It does not raise the label at all.
- No route reaches that pattern in that jurisdiction. This is silence in the knowledge
  base, not a finding of lawfulness. Report the pattern plainly, say no mapped norm was
  found, and leave the legal question open.

Never write that a practice is lawful because the knowledge base has no norm for it.

## Compounding Small Practices

Several individually minor practices may raise the label where they combine into one
deceptive impression about the same matter. Read `cumulative-assessment.md` first; it sets
out how far the sources actually go.

Apply this deterministically:

- Three or more observed practices that shape the same impression, about price, the
  existence of a recurring commitment, or the ability to cancel, raise the label one step.
- Practices that mislead about nothing in particular, or that concern unrelated matters,
  do not combine. Count them separately and leave the label alone.
- Compounding raises the label only. It never creates a Material Finding and never
  supplies a citation. If the combination is to be a finding, it needs a routed norm that
  reaches presentation as such: Section 226 in the UK, the Article 6 overall-presentation
  limb in the EU, a Section 5(a) net-impression theory in the US.
- Say in `Verdict` that the label rests on the combination, and name the impression.

## Confidence

High confidence requires visible UI evidence plus local pattern, norm, and case/source anchors.

Medium confidence can rely on visible evidence plus partial source anchors, with limitations stated.

Low confidence should not produce a detailed legal-risk card unless the user asked for exploratory analysis.

## Social/Review-Platform Two-Stage Scoring

When a material social/review-platform module is visible but authenticity evidence was not supplied, apply the normal factors and issue a provisional public risk label. Do not treat appearance as proof of fabrication. State briefly in `Verdict` or `Confidence and limitations` that review authenticity is unresolved.

After the operator answers the grouped authenticity question, re-run the complete rubric and issue a final public risk label for Yes, No, or Unknown. Do not add a fixed number of points to the private score for any answer.

- **Yes:** record operator-confirmed fabrication, not independent verification. Make the finding High severity when it materially supports conversion, then weigh all normal increase and decrease factors.
- **No with a matching source or official-widget confirmation:** treat the module as verified for this evaluation, remove or mitigate the finding, and reassess the remaining supported issues.
- **No without supporting source information:** record `merchant-asserted genuine; not independently verified`, keep `Unverified social proof` if it remains material, and retain that limitation.
- **Unknown:** keep `Unverified social proof` and assess only supported evidence.
- **No response:** preserve the provisional label; do not rescore or perform independent research.

Comparable-authority similarity remains an ordinary rubric factor. Do not select Amazon Prime as a comparator for a review finding unless the evidence has an exact relevant pattern match.

## Compounding

Repeated small issues can raise risk when they reinforce the same consumer harm, such as trial framing plus small-print renewal plus hard cancellation. Do not stack unrelated weak cues into a high-risk finding.
