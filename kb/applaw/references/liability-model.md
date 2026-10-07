# Liability Model

Read this reference whenever a task adds, reviews, or reports liability, remedies, penalties, redress, damages, enforcement outcomes, or case-specific estimates.

## Public Wording

Keep direct legal citations and required posture labels accurate. Describe the route, limits, uncertainty, and practical consequence in plain language. Do not copy source-file legalese into the report narrative.

## Evidence Chain

Resolve in this order:

1. visible finding;
2. explicitly supplied canonical jurisdiction/country and a supported material norm;
3. actor, transaction, factual-trigger, effective-date, availability, and source-anchor gates;
4. an optional procedural enforcement or remedy companion declared for that material norm;
5. consumer, public, private, monetary, and non-monetary routes;
6. eligible final outcome matching the explicit country scope, if a comparator is useful;
7. estimate gate.

A pattern label is never a liability conclusion. A procedural norm is never the primary duty derived from a visual pattern and cannot support liability without a surviving material norm.

## Three Monetary Layers

### Statutory ceiling

State the exact maximum or formula, unit, legal predicate, and adjustment/effective date. Label it `not an expected outcome`.

### Observed enforcement benchmark

Use only `eligible_monetary` or `eligible_non_monetary` records from `taxonomy/enforcement_outcomes.yml`. State the matter, date, posture, amount type, legal basis, similarity, and non-predictive limits. Do not use complaints, pending matters, proposed orders, no-finding commitments, press-release-only records, or superseded routes.

### Case-specific estimate

Require jurisdiction, actor, relevant turnover, affected consumers, charges, duration, conduct, knowledge, prior orders, injury, redress already paid, defenses, and methodology. If those inputs are insufficient, use exactly:

`Estimate status: Not estimable from the supplied interface and business data.`

## Posture Ladder

- allegation or complaint: theory only;
- pending proceeding: unresolved;
- undertaking or commitment: corrective conduct, usually no finding;
- consent order: final within its terms, not judicial precedent;
- settlement: enforcement outcome, not precedent;
- final administrative notice or decision: final regulator outcome, subject to appeal metadata;
- court order: binding relief within its terms;
- judgment: precedential only to the extent the legal system gives it precedential weight.

## Amount Types

Keep public penalty, consumer redress, refund, damages, settlement payment, suspended judgment, turnover ceiling, per-day amount, and aggregate multi-breach amount separate. Never sum a suspended face judgment with its payable amount. Never allocate an aggregate amount without an official allocation.

## Scope Traps

- FTC Act money needs a separate rule, order, or statutory route after `AMG Capital`.
- The vacated 2024 FTC negative-option amendment is not current law.
- The FTC Fees Rule is limited to live-event tickets and short-term lodging.
- UK original-infringement penalties differ from breach-of-undertaking/direction penalties.
- EU directive ceiling rules depend on national implementation and the CPC widespread-infringement context.
- DSA Article 25 requires an online-platform actor and yields where UCPD or GDPR covers the practice.
- GDPR requires a specific personal-data operation and breached duty; purchase consent is not automatically GDPR consent.
- French cookie-consent outcomes in this KB are ePrivacy/national-law outcomes, not GDPR outcomes.

## Authoring And Validation

- Keep duties and ceilings in `taxonomy/norms.yml`.
- Keep dated outcomes in `taxonomy/enforcement_outcomes.yml`.
- Link eligible records in both directions through norm and outcome ids.
- Store official URLs and pinpoints in the KB; show short citations in public reports.
- Run `validate_enforcement_outcomes.py` and `validate_report.py` after changes.

