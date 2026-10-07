# Jurisdiction-First Norm Routing

Use this reference before writing any legal finding or liability block. It defines candidate routing, not a substitute for legal review.

## Required Scope Input

The evaluation context must state one or more target jurisdictions explicitly:

- `US`
- `UK`
- `EU`
- documented EU-country aliases: `EU:France`, `EU:FR`, `EU-France`, and `EU-FR`; the equivalent Netherlands forms are also accepted.

Normalize every accepted external alias immediately to the single internal schema:

```yaml
jurisdiction: EU
sub_jurisdiction: FR
```

`jurisdiction` is exactly `US`, `UK`, or `EU`. `sub_jurisdiction` is null or a supported ISO-style country code (`FR` or `NL`). Base-only US, UK, and EU scopes use null. Combined values such as `EU-FR` and country names such as `France` are input aliases only and must not be stored or returned as canonical internal fields.

The target list describes the market or consumer scope being assessed. Currency, language, domain, merchant location, payment processor, or a filename is not enough to establish it. If the target list is empty or unknown, abstain from jurisdiction-specific legal mapping and state that no jurisdiction-specific legal conclusion was made.

## Candidate Selection

For each detected pattern:

1. Read the pattern's `maps_to_norms` candidates and any matching group in `taxonomy/jurisdiction_routes.yml`.
2. Keep only candidates whose base jurisdiction matches an explicitly supplied target. A regional EU norm may remain a candidate for an explicitly named EU country, but a country-specific norm or outcome requires that exact country code to have been supplied. A base `EU` target never activates a country-specific record.
3. Keep only `material` norms for the primary `Applicable norm` field.
4. Apply each route's exact `required_facts` and `disqualifying_facts` tokens using the structured `confirmed`, `rejected`, and `unknown` states. Free-form evidence text never satisfies a token. Missing and explicitly unknown required facts keep the authority conditional; a rejected required fact or confirmed disqualifying fact excludes that route.
5. Check actor scope, transaction type, factual trigger, contract stage, effective date, source availability, and national implementation limits from the material norm's fields.
6. Resolve the route's `source_anchor_ids`. A pattern label, route candidate, broad statutory title, or procedural enforcement provision alone is insufficient.
7. If no candidate survives for a target, return an explicit abstention for that target. Never fall back to US, UK, EU, or another analogue because a requested jurisdiction is unsupported.
8. Add a `procedural` norm only after a supported material norm has been selected, only when its declared `companion_to_material_norm_ids` includes that material norm, and only when its jurisdiction and enforcement route fit. Never map a procedural norm directly from a visual pattern or use it as the primary duty.

The route output is therefore a filtered candidate set, not a promise that every candidate applies. Where several candidates survive, the evaluator must explain the factual reason for the selected authority or name the supported authorities together.

## Route Classifications

The deterministic router uses three review states for each target jurisdiction:

- `supported_route`: declared factual gates are satisfied and the route contains a resolvable local norm, outcome, or case-card anchor. Final legal selection still requires actor, transaction, contract-stage, implementation, and posture review.
- `conditional_candidate`: a same-jurisdiction material norm candidate exists, but one or more factual or source gates have not been supplied or finally reviewed.
- `intentional_abstention`: no same-jurisdiction material route survives, a required fact is explicitly rejected, or a documented false-positive fact is confirmed.

An abstained jurisdiction result carries no `source_anchor_ids`. The context builder materializes every surviving symbolic route anchor in the corresponding `norms`, `outcomes`, or `cases` collection. An exact route-anchored case is retained even when its pattern tags differ from the candidate pattern, and a corrective or no-finding outcome retains its original posture plus `selected_as_route_anchor: true`; it never becomes an enforcement benchmark.

Candidate arrays are unordered sets. Their file order never selects the applicable authority, and the router exposes no selected authority field.

For multiple target jurisdictions, keep a separate canonical `{jurisdiction, sub_jurisdiction}` result and reason for every target. The aggregate status is `mixed` when at least one jurisdiction has candidates and another abstains; a surviving US candidate must never suppress a UK or EU abstention.

## Factual-Gate Tokens And Anchors

Route records may declare inline `required_facts`, `disqualifying_facts`, and `source_anchor_ids`. These route records are the single allowed-token registry supplied to the Examiner. Tokens must be returned exactly and separately from human-readable evidence; unrecognized values are ignored with a warning. Anchor prefixes are `norm:`, `outcome:`, and `case:`. A commitment or no-finding outcome may support a corrective-design example only when its posture is explicit; it may not become an observed enforcement benchmark.

When facts are omitted, explicitly unknown, or only partly confirmed, a mapped norm remains a conditional candidate. Confirming every required fact may support the route when its local anchors resolve. Explicitly rejecting a required fact excludes that governed candidate. A governed narrow authority never silently re-enters through the pattern's baseline `maps_to_norms` field.

## Public Report Behavior

- `Applicable norm` names the selected instrument and provision in human-readable form and explains its jurisdiction-specific fit.
- Use one liability block per materially different jurisdiction and exposure category.
- If target jurisdiction is missing, use `Jurisdictions assessed: Not established; no jurisdiction-specific legal conclusion was made.` Do not add a legal finding or liability block merely as an analogue.
- If several jurisdictions are explicitly in scope, assess each separately and preserve national-implementation and remedy limits.
- Authority citations in the final report must belong to a jurisdiction stated in the report preamble. A multi-jurisdiction report must keep materially different liability routes in separate blocks.

## Routing Registry

`taxonomy/jurisdiction_routes.yml` supplies conservative jurisdiction-specific candidate bridges. Every route now declares `required_facts`, `disqualifying_facts` where a documented false-positive exists, and local `source_anchor_ids`, so each route can reach `supported_route` when its observable facts are confirmed and abstain when a disqualifying fact is confirmed. Factual-gate tokens name single observable elements (what the screen requests, what is present or subordinated, at which contract stage); a legal conclusion is composed from confirmed tokens, never demanded as one compound token. The existing `maps_to_norms` field remains a conditional baseline and can be used for a jurisdiction only after the same jurisdiction filter is applied.
