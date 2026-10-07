---
id: social-platform-review-modules
category: social_proof_two_stage
expected_handling: detect_classify_question_then_revise
expected_risk_effect: provisional_then_full_rubric_recalculation
expected_report_location: material_missing_context_and_post_report_follow_up
prohibited_behavior: appearance_only_fake_claim_fixed_increment_or_default_research
scenario_count: 11
---

# Evidence

These controlled scenarios cover platform-attributed review modules in checkout and sales-funnel screenshots. They are policy regressions, not legal evidence and not proof that any displayed review is genuine or fabricated.

# Expected Behavior

For each unresolved material module, capture all visible review and platform cues, use the staged classification, preserve report v3, and ask exactly once after the report:

“Are the displayed social-platform reviews or testimonials fake, fabricated, purchased, or presented without a genuine underlying customer experience? Reply Yes, No, or Unknown. If No, you may optionally provide the original post, review-page, platform ID, or official-widget confirmation.”

Batch handling: collect unresolved review questions in one compact post-report table with one grouped question per module. F↔L handling: Preserve bidirectional links for every retained material finding and liability block. Privacy handling: do not request customer identities, orders, or transaction records during normal review; request them only after a dispute or an explicit stronger-verification request.

## SP01 - Trustpilot-style reviews with unknown authenticity

Evidence: A Trustpilot-style card with stars, reviewer names, dates, review count, logo, and nearby source text appears beside the plan selector and CTA; no authenticity evidence accompanies the screenshot.

Expected classification: Unverified social proof. Report state: Initial provisional report v3. Risk handling: Apply the rubric provisionally, publish only the risk label, and state that authenticity is unresolved. Follow-up handling: put a concise authenticity question in Missing Context and repeat the exact grouped question once immediately after the report. Research handling: No external research by default. F↔L handling: Preserve bidirectional links when the normal gates support a material finding.

## SP02 - Operator answers Yes

Evidence: The SP01 module materially supports conversion and the operator answers Yes.

Recorded fact: operator-confirmed fake or fabricated social proof; not independently verified. Expected classification: Confirmed or operator-confirmed fabricated platform reviews. Severity handling: High when the module materially supports conversion. Risk handling: re-run the normal rubric with no fixed increment and publish only the label. Report state: Complete revised report v3. Jurisdiction handling: map law only for supplied jurisdictions and supported local norms. Comparator handling: Amazon Prime only for an exact relevant pattern match. F↔L handling: Preserve bidirectional links.

## SP03 - Operator answers No and supplies a matching official source

Evidence: The operator answers No and supplies a matching official source or official-widget confirmation, and requests a lightweight check.

Expected classification: Verified for this evaluation; remove or mitigate the finding. Source handling: check only the supplied source when requested and permit no more than two lightweight supplied-source checks per screenshot. Risk handling: re-run the normal rubric and publish only the label. Report state: Complete revised report v3. F↔L handling: Preserve bidirectional links for any retained finding.

## SP04 - Operator answers No without supporting source information

Evidence: The operator answers No but provides no source, platform ID, or official-widget confirmation.

Recorded fact: merchant-asserted genuine; not independently verified. Expected classification: retain Unverified social proof when material. Do not call it fake. Risk handling: re-run the normal rubric, publish only the label, and state the limitation. Report state: Complete revised report v3. F↔L handling: Preserve bidirectional links.

## SP05 - Operator answers Unknown

Evidence: The operator answers Unknown.

Expected classification: Keep Unverified social proof. Risk handling: re-run the normal rubric using only supported evidence, publish only the label, and state the authenticity limitation. Report state: Complete revised report v3. F↔L handling: Preserve bidirectional links.

## SP06 - No follow-up response

Evidence: The operator does not answer the grouped authenticity question.

Report state: Preserve the provisional report. Research handling: Do not perform independent research. Score handling: do not issue a revised or final score.

## SP07 - Genuine official widget

Evidence: A supplied official widget or directly traceable source visibly matches the displayed platform, text, rating, date, reviewer details, count, badge, and identifier available in the screenshot.

Expected handling: Do not flag the module. Do not ask the review follow-up. A missing visibly printed URL would not alter the result. Score handling: score only other supported issues.

## SP08 - Static Facebook-style comment block near the CTA

Evidence: A static Facebook-style comment block with logo, likes, replies, reviewer names, dates, and platform styling appears immediately above the purchase CTA; no authenticity evidence is supplied.

Expected classification: Unverified social proof when the normal gates pass. Record the block as one module, issue a provisional report and score, and ask the grouped question once after the report. Never infer fake from the static appearance.

## SP09 - Ordinary Facebook footer icon

Evidence: A Facebook icon appears with ordinary footer social links and is unattached to a review or endorsement.

Expected handling: Do not flag. Do not classify a review module and do not ask an authenticity question.

## SP10 - Small or low-prominence platform mark

Evidence: A small or low-prominence platform mark sits inside a star-rating testimonial card near the registration control.

Expected handling: the vision pass must still record it and the nearby stars, source text, names, dates, counts, badges, likes, or replies. Treat it as a candidate only when it is attached to the review module and materially supports conversion; small size does not erase the cue.

## SP11 - Unrelated Amazon Prime comparator

Evidence: A materially conversion-supporting platform review is operator-confirmed fabricated, but the available Amazon Prime material concerns a different cancellation pattern.

Comparator handling: Do not select Amazon Prime. Require an exact relevant pattern match; otherwise abstain or use a supported exact-match local authority. Report state: Complete revised report v3 with ordinary jurisdiction, norm, private-score/public-label, and F↔L gates.
