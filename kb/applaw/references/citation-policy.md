# Citation Policy

## Cite Or Abstain

Use only local KB anchors for legal and case claims:

- `taxonomy/norms.yml` for norm ids and source URLs.
- `taxonomy/enforcement_outcomes.yml` for dated finality, amount type, benchmark eligibility, official source, and comparability limits.
- `cases/<case-id>/_case.md` for case posture and source file.
- `cases/<case-id>/<figure-id>.md` for screen evidence.
- `asset` paths for visual evidence.
- `source_id`, `source_anchor_ids`, `source_ref`, `source_page`, and `complaint_paras` for complaint, notice, judgment, or order anchors.
- `sources/source_capsules.json` for portable provenance, reviewed pinpoint extracts/summaries, reverse references, original-document hashes, and official retrieval URLs.
- A legacy `source_file` may resolve to an active-workspace binary or a verified capsule alias. Portable releases contain no PDFs.

If an anchor is absent, say what is missing and abstain from the claim.

## Source Fields

`source_id` identifies a portable source capsule. `source_anchor_ids` identifies one or more reviewed local pinpoints within it.

`source_file` is a compatibility and provenance field. In an active workspace it may resolve to `case_law/` or `downloaded_pdfs/`; in a PDF-free release it must resolve through a capsule alias. A URL or SHA-256 alone is not a sufficient local anchor.

`source_ref` identifies an attachment, figure, exhibit, page label, or other source-local handle.

`source_page` is the PDF page or source page used by this repo. Do not silently convert it to a legal page number.

`complaint_paras` identifies complaint paragraphs where available. It is not a substitute for reading the case card reasoning.

Every referenced capsule preserves the original filename, SHA-256, byte and page metadata, procedural posture, an official HTTPS source, reverse references, and at least one local anchor. Capsule coverage is intentionally excerpt-only. Retrieve the original and verify its hash for full-document review.

## Genesis Path

For Genesis/Growthmind cards, bridge through per-card frontmatter and extracted complaint page/paragraph mappings. `_coverage.json` is inventory support only; it is not enough for legal citation.

## EU/UK Limits

EU and UK material may be press-release-only or administrative rather than court-adjudicated. Mark confidence and availability limits. Do not present allegations, undertakings, final notices, or press releases as the same thing.

## Liability And Consequence Claims

Use the selected norm's `consumer_redress`, `public_enforcement`, `private_enforcement`, `penalty_basis`, `non_monetary_relief`, `limitations`, `liability_source_urls`, and `verified_as_of` fields.

Use an observed benchmark only when its registry record is `eligible_monetary` or `eligible_non_monetary`. Resolve it through the norm's `eligible_outcome_ids`, then verify posture, finality, amount type, source availability, pinpoint, similarity, and limitations.

- State the enforcement predicate, not only the maximum possible sanction.
- Do not imply that a maximum fine is automatic or typical.
- Do not imply a private right of action where the norm says none exists.
- Do not turn complaint allegations into assessed liability or a final remedy.
- Do not use a procedural norm without a supported material norm.
- Do not map a procedural enforcement or remedy provision directly from a visual pattern or place it in the primary `Applicable norm` field. It may appear only after the material duty and only as its declared companion.
- Do not use complaint, proposed, pending, no-finding, press-release-only, vacated, or superseded records as observed benchmarks.
- Do not allocate an aggregate multi-breach amount to one finding unless the official source allocates it.
- Preserve settlement discounts and suspended face/payable amounts as separate metadata.
- Keep app-store, chargeback, processor, platform, and commercial-account consequences separate from legal liability.
- If the liability source is stale, outside the target jurisdiction, or dependent on national implementation, state the limitation or abstain.
- Normalize internal scope to `jurisdiction: US|UK|EU` plus nullable ISO-style `sub_jurisdiction`. A regional EU source may support a named EU country, but a country-specific norm, remedy, or outcome requires that exact country to be explicit. Never use a French or Dutch record for base EU or another country by analogy.

## Public Report Display

Keep full provenance in the KB and verification pass. In the public report:

- cite the instrument and provision in human-readable form;
- name only the minimum comparable case or authority and state its posture;
- do not expose local paths, filenames, line numbers, internal IDs, raw URLs, complaint-paragraph inventories, or source dumps;
- do not add a separate sources appendix;
- move an unverified or low-confidence issue to `Missing Context` instead of padding a material finding.
- link each material finding to a separate liability block rather than repeating consequences in the finding.

## Public Wording

- Keep direct instrument and provision names in the citation fields.
- Explain the practical effect, limits, routes, and consequences in plain language outside those citations.
- Do not copy legalese from a norm, complaint, order, or case card into a narrative field.

## Supplied Review-Source Checks

No web searches by default. A screenshot's appearance, platform styling, static state, missing visibly printed URL, or inability to test a link does not prove fabrication. A missing visibly printed URL in a screenshot also does not prove that an official widget is not clickable.

Check a user-supplied review source only when the operator requests that check. Permit at most two lightweight supplied-source checks per screenshot and count them against the existing external-verification budget. Treat a carousel or testimonial section as one module; do not investigate each reviewer. If a match would require serious research, stop at `Unverified social proof`.

A matching source or official-widget confirmation should align on the material visible details available for comparison, such as platform, review text, rating, date, reviewer display name, review count, badge, post or platform identifier, and widget branding. Do not demand that every field be visible. When the supplied traceable source materially matches, treat the module as verified for this evaluation and remove or mitigate the finding.

An operator Yes is evidence only of `operator-confirmed fake or fabricated social proof`; it is not independent verification. A No without supporting source information is `merchant-asserted genuine; not independently verified`. Unknown and no response remain unresolved. Do not request customer identities, orders, or transaction records during normal review; those may be requested only when the operator disputes the result or explicitly asks for stronger verification.

Map a review finding to law only for explicitly supplied jurisdictions and supported local norms. For the US FTC reviews rule, identify the applicable provision and required knowledge or conduct elements; an unverified screenshot alone is insufficient. For the UK DMCC Schedule 20 route, require confirmed fabrication plus supported trader submission, commissioning, or publication facts; suspicion or missing source information is insufficient. Do not use Amazon Prime as a comparable authority unless the finding has an exact relevant pattern match. If the operator does not respond, preserve the provisional report and perform no independent research.

## Bad Citations

Reject:

- Statutes not in `taxonomy/norms.yml`.
- Cases not represented in the local KB.
- Paragraphs or pages that are not in the source fields.
- Legal conclusions supported only by a pattern cue.
- Broad statements like "illegal dark pattern" without a local norm and source anchor.
- Monetary penalties, refunds, damages, private claims, injunctions, or operational sanctions that are not supported by the norm's consequence fields.


## Conditional Citation

A material norm whose jurisdiction route has unestablished required facts is
citable as a finding's primary Applicable norm only under the conditional
discipline, enforced by the live validator:

- `Confidence and limitations` starts with `Medium - ` (never High), and
- it contains an explicit `conditional on ...` clause naming the predicate
  facts the supplied evidence does not establish.

An unconditioned citation of such a norm is rejected. The inverse holds too:
an on-screen pattern whose only authority is conditional still produces a
finding, written under this discipline. Silence is reserved for patterns with
no on-screen evidence, not for unestablished predicate facts.
