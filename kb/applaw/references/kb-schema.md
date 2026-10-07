# KB Schema

## Contents

- [Directory Map](#directory-map)
- [Allowed Values](#allowed-values)
- [Source Capsule Fields](#source-capsule-fields)
- [Pattern Fields](#pattern-fields)
- [Jurisdiction Route Fields](#jurisdiction-route-fields)
- [Norm Fields](#norm-fields)
- [Enforcement Outcome Registry](#enforcement-outcome-registry)
- [Case Header](#case-header)
- [Case Card](#case-card)
- [Gold Card](#gold-card)
- [Clean Benchmark](#clean-benchmark)
- [Report Sample](#report-sample)

## Directory Map

Canonical KB:

```text
constitutions/
  GLOBAL.md
  SESSION_LIMITS.md
  RESOURCE_LIMITS.json
  patterns/{disclosure,consent,pressure,upsell,cancellation}.md
  jurisdictions/{us,eu,uk}.md
taxonomy/
  patterns.yml
  jurisdiction_routes.yml
  norms.yml
  enforcement_outcomes.yml
cases/<case-folder>/
  _case.md
  _coverage.json
  <figure-id>.md
assets/<case-folder>/<figure-id>.png
eval/gold/<id>.md
eval/report_samples/<id>.md
eval/report_validation_cases.json
eval/policy_fixtures/<id>.md
eval/adversarial/<id>.md
eval/resource_limits/cases.json
eval/output_safety/cases.json
eval/adversarial_replays/{rules,cases}.json
benchmarks/clean/<id>.md
sources/source_capsules.json
```

Active-workspace binary archive:

```text
case_law/          # optional maintenance and regeneration input
downloaded_pdfs/   # optional raw-ingestion archive
```

Portable-core releases omit both binary archives, the canonical `assets/` tree, and every historical image or `*.pdf` file. They carry `RELEASE_PROFILE.json`, `sources/source_capsules.json`, case cards, taxonomy, fixtures, and outcome records instead. Current evaluations use operator-supplied screenshots; historical comparisons use semantic case-card evidence and capsule anchors. Optional visual evidence may be mounted separately but is never required or sufficient as a citation anchor by itself.

`RELEASE_PROFILE.json` declares schema and release versions, `profile: portable-core`, `bundled_visual_assets: false`, `evidence_mode: capsule`, `optional_evidence_pack_required: false`, zero PDF and bundled-image counts, and exact package file/byte totals before the checksum manifest.

Working materials:

```text
generated/
outputs/
new/
tmp/
```

Do not treat working materials as stronger evidence than canonical case, taxonomy, norm, and source files.

## Allowed Values

Pattern families: `disclosure`, `consent`, `pressure`, `upsell`, `cancellation`.

Pattern stages: `lure`, `commit`, `hide`, `charge`, `block`.

Severity: `low`, `medium`, `high`.

Canonical jurisdictions: `US`, `EU`, `UK`.

Canonical sub-jurisdiction: null or a supported ISO-style EU country code (`FR`, `NL`). External aliases such as `EU:France`, `EU:FR`, `EU-France`, and `EU-FR` are normalized at input and must not be stored as a combined jurisdiction value. Base-only records use `sub_jurisdiction: null`.

Norm type: `material`, `procedural`.

Availability: `full`, `press_release_only`, `partial`, `unknown`.

Legacy gold-fixture risk bands: `green`, `yellow`, `red`. These are internal regression labels, not Report Contract v3 public risk labels.

Legacy gold-fixture score bands: `1-30`, `31-60`, `61-100`. These preserve historical test semantics and are not the five-level public mapping.

## Source Capsule Fields

`sources/source_capsules.json` contains one record per original legal/source document. Each record includes `source_id`, title, authority, jurisdiction, procedural posture, official URL where referenced, verification date, coverage, package status, review status, `original_document`, aliases, reverse references, page extracts, anchors, and limitations.

`original_document` preserves filename, SHA-256, byte size, page count, and media type. An anchor contains a stable `anchor_id`, source ref/page/paragraph fields, local evidence or law summary, optional maintenance asset links, reverse references, and review status. A hash or URL without a local anchor never satisfies cite-or-abstain.

Legacy `source_file` values remain valid only when they resolve to a current workspace binary or a referenced capsule alias. Portable case, gold, and benchmark records require direct `source_id` and `source_anchor_ids`, symmetric capsule reverse references, and at least one local anchor. A URL, filename, digest, page number, or optional image identifier alone is not sufficient.

Maintenance anchors may carry `asset_refs`. Portable-core anchors do not: a historical visual anchor instead carries a nonempty semantic `evidence_summary`, `historical_visual_evidence: true`, and an omitted-raster limitation. Gold-only anchors may link to existing case-card anchors through `linked_case_anchor_ids`. Extracted text and semantic summaries do not preserve pixel-level color, contrast, relative prominence, spacing, or location.

## Pattern Fields

`taxonomy/patterns.yml` entries should include:

```yaml
- id: hidden-renewal
  name: "Hidden auto-renewal"
  family: disclosure
  stage: hide
  severity_default: high
  detection_cues: []
  false_positive_traps: []
  maps_to_norms: []
  example_cases: []
```

Keep it a detection registry. Do not turn it into a legal memo.

## Jurisdiction Route Fields

`taxonomy/jurisdiction_routes.yml` is the jurisdiction-first candidate bridge between a detected pattern and `taxonomy/norms.yml`. Each route group should include:

```yaml
- id: eu-disclosure-price
  jurisdiction: "EU"
  sub_jurisdiction: null
  pattern_ids: [hidden-renewal]
  candidate_norms: [eu-ucpd-5-9, eu-crd-6]
  condition: "Regional candidate only; verify contract scope, national implementation, and the factual trigger."
```

Route candidates must resolve to material norms in the same canonical jurisdiction scope. Regional EU norms may remain candidates for an explicit EU country, while country-specific norms require an exact country match. They are not automatic legal conclusions. A target jurisdiction is required; the router must abstain rather than fall back to another jurisdiction.

## Norm Fields

`taxonomy/norms.yml` entries should include:

```yaml
- id: us-rosca-4-1
  jurisdiction: "US"
  sub_jurisdiction: null
  instrument: "ROSCA Section 4(1)"
  citation: "15 U.S.C. 8403(1)"
  type: "material"
  enforcer: "FTC"
  remedy: "short report-ready consequence summary"
  summary: "..."
  source_url: "official source for the duty"
  availability: "full"
  consumer_redress: "consumer-facing monetary or contract consequence, with prerequisites"
  public_enforcement: "public enforcer and route"
  private_enforcement: "private-action route or explicit absence/limit"
  penalty_basis: "penalty authority, trigger, maximum or national-law dependency"
  non_monetary_relief: "injunctions, directions, undertakings, reporting, or interface measures"
  limitations: "scope, predicates, posture, and anti-overclaim limits"
  liability_source_urls: ["official source for consequence claims"]
  verified_as_of: "YYYY-MM-DD"
```

Keep the liability model flat and backward-compatible with the repository's deterministic parser. `remedy` is only a concise display summary; consequence claims must be supported by the more specific liability fields. `liability_source_urls` must contain official or primary sources. Do not place app-store refunds, card chargebacks, processor reserves, delisting, or other commercial consequences in these legal-liability fields.

`eligible_outcome_ids` contains only registry records that passed the finality, source-availability, and benchmark-eligibility gate.

Material norms state the underlying duty. Procedural norms state an enforcement or remedy route. A procedural norm may accompany a supported material norm in the legal dossier, but it should not be mapped directly from a visual pattern as though it were a UI duty.

Every procedural norm declares `companion_to_material_norm_ids`. A procedural norm is valid only after at least one declared material companion survives all jurisdiction and factual gates. Pattern registries and jurisdiction routes may map only material norms as primary candidates.

## Enforcement Outcome Registry

`taxonomy/enforcement_outcomes.yml` is a one-to-many dated outcome layer. Each record includes stable id, canonical `jurisdiction`, nullable canonical `sub_jurisdiction`, authority, matter, date, posture, finality, linked norms/practices, legal basis, typed monetary object or null, consumer redress, non-monetary relief, official URL, pinpoint, source availability, benchmark eligibility, comparability notes, limitations, and verified date.

Allowed benchmark eligibility values:

- `eligible_monetary`
- `eligible_non_monetary`
- `ineligible_non_final`
- `ineligible_no_finding`
- `ineligible_source_only`

Norms state law; outcomes state what happened in one matter. Do not copy observed amounts into a norm's ceiling text, and do not treat an outcome as precedent unless it is a precedential judgment.

## Case Header

`cases/<case-folder>/_case.md` should carry frontmatter for:

`case_id`, `title`, `court`, `filed`, `counts`, `outcome`, `penalty`, `procedural_posture`, `odds_notes`, `source_id` or legacy `source_file`, `availability`.

## Case Card

Maintenance `cases/<case-folder>/<figure-id>.md` should carry:

`case_id`, `figure_id`, `product`, `screen_type`, `patterns`, `norms`, `source_id` and `source_anchor_ids` or legacy `source_file`, `source_ref`, `source_page`, `asset`, `availability`.

`complaint_paras` is expected for complaint-backed US cards and should be filled where available. The body should include:

```text
EVIDENCE. ...
LEGAL REASONING. ...
STATED LAW. ...
```

The release builder creates portable copies only: it adds direct `source_id` and `source_anchor_ids`, removes `asset` frontmatter, and preserves the body text and stable IDs. Portable `_coverage.json` files report card count, evidence-anchor count, zero bundled assets, and optional visual-evidence count.

## Gold Card

Maintenance `eval/gold/<id>.md` should carry:

`id`, `case_id`, `source_title`, `screen_id`, `screen_title`, `jurisdiction`, optional `sub_jurisdiction`, `source_kind`, `source_id` and `source_anchor_ids` or legacy `source_file`, `source_ref`, `source_page`, `asset`, `expected_risk_band`, `expected_score_band`, `expected_patterns`, `expected_norms`, `complaint_paras`, `review_status`.

Base-only legacy gold cards without `sub_jurisdiction` normalize to null on read. New country-specific gold cards must store the ISO-style code explicitly. `expected_norms` must contain a material norm before any declared procedural companion and must match the gold scope.

The body should include expected answer, expected flags, expected citations, acceptable variants, and rejection criteria.

Portable gold copies require direct capsule fields and no `asset` frontmatter. Strict review remains mandatory. A missing optional image is not an error when capsule evidence or a linked case-card evidence anchor resolves locally.

## Clean Benchmark

`benchmarks/clean/<id>.md` should describe a lawful or low-risk checkout example, not a fake violation. It should carry:

`id`, `product`, `jurisdiction`, `benchmark_type`, `checkout_stage`, `monetization_model`, `expected_risk_band`, `expected_score_band`, `lawful_features`, `false_positive_traps_covered`, `evidence_source`, `asset`, `review_status`.

Every clean benchmark must resolve one source capsule and at least one local anchor; multi-page examples may resolve multiple anchors. Portable copies require direct capsule fields and do not require a shareable image. If optional visual evidence is absent, state that limitation and use the semantic capsule evidence without claiming pixel-level equivalence.

## Report Sample

`eval/report_samples/<id>.md` is a regression fixture for the strict public output contract. It must follow `references/report-contract.md` and pass `scripts/validate_report.py`. It is not a source of law or case evidence and must not be cited as authority.

Report samples also model the default-English, plain-language style policy. They should preserve direct citations and required contract strings while explaining the practical point in ordinary language.

Ordinary report samples omit the public `Evidence integrity:` line. `eval/report_validation_cases.json` supplies positive and negative validator regressions for default omission and the explicit `--evidence-integrity-requested` mode.

`eval/policy_fixtures/<id>.md` tests evidence-integrity and false-positive behavior. It is not legal evidence. It must state the evidence text, expected handling, expected risk effect, and prohibited behavior and pass `scripts/validate_policy_fixtures.py`.

`eval/adversarial/<id>.md` is a manual-replay robustness specification. It must carry `id`, `category`, `attack_vector`, `targets`, `severity_if_failed`, and `review_status`, then contain prompt, expected-behavior, failure-mode, and pass-criteria sections. It is not legal evidence and must pass `scripts/validate_adversarial.py`.

`eval/resource_limits/cases.json` tests context-aware post-ingestion admission: deployed context window, exact occupied-input components and total, cached-input subset, retrieved KB tokens, tool/response/safety reserves, candidate evidence, OCR, elapsed time, and screenshot-batch admission. `eval/output_safety/cases.json` tests public-output leakage detection. `eval/adversarial_replays/` contains deterministic safe/unsafe transcript pairs and rules; it grades saved text and never invokes a model.
