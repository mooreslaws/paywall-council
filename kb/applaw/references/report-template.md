# Checkout-Funnel Risk Assessment: <Product or flow>

Use plain, conversational language in the values. Keep formal legal wording inside direct citations or exact contract strings only. The headings and field labels are fixed English schema tokens; see `output-style.md` for the language and field rules.

Start with this title and add no introductory prose. Retain every level-two section. If no Medium/High finding is supported, replace the example F and L blocks with literal `None.` in their respective sections. Validate the complete final text with `validate_live_report.py`, correct all failures, and return it unchanged.

Omit the `Evidence integrity:` line by default. Only when the initial operator prompt explicitly requests disclosure, add exactly one line of no more than 30 words immediately after `Verdict` and validate with `--evidence-integrity-requested`. Calculate the legacy score privately and never expose it.

Assessment date: YYYY-MM-DD
Jurisdictions assessed: <Explicit target scope and material limits, or Not established; no jurisdiction-specific legal conclusion was made.>

## Assessment Summary

RISK: <very low|low|medium|high|very high>
Verdict: <Maximum 80 words>

## Material Findings

### F1 - <Finding title>

Severity: <Medium|High>
Observed evidence: <What is visibly on the screen>
Pattern: <Human-readable pattern names>
Risk explanation: <What could go wrong for the shopper, in plain language>
Applicable norm: <Direct norm citation followed by a plain-language explanation>
Comparable KB authority: <Case or authority and procedural posture>
Linked liability blocks: <L1>
Confidence and limitations: <High|Medium> - <Material limitations>
Recommended correction: <Specific product, UX, checkout, or process change>

## Liability and Consequences

### L1 - <Jurisdiction and exposure category>

Linked findings: <F1>
Liability trigger: <In plain English, what would make the rule apply>
Consumer or contract remedies: <In plain English, what help may be available, or none identified>
Public enforcement: <Who may act and what they may do, in plain English>
Private exposure: <In plain English, what other claims may exist, or why none are identified>
Monetary exposure: Statutory ceiling - not an expected outcome: <Formula, predicate, unit, and date>
Observed enforcement benchmark: <Eligible final outcome described plainly, with posture and limits, or None identified.>
Non-monetary orders: <Plain-language description of eligible orders, or None identified>
Authority citations: <Short direct citations>
Estimate status and limitations: Estimate status: Not estimable from the supplied interface and business data. <Other limits>

## Mitigating and Low-Risk Elements

- <Compact mitigating fact written plainly>

## Observed Without a Mapped Norm

- <Pattern name in plain language>: <what is on screen>. No mapped norm or enforcement example was found for this in the supplied material.

## Missing Context

- <Plain-language fact that could materially change the result>

## Priority Actions

- <Concrete product or process action>
- <Second concrete action>
- <Third concrete action>

## Disclaimer

This report is a risk assessment based on the supplied interface and available context. It is not legal advice.
