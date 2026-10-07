# Case Authoring

## Add A Case

1. Create `cases/<case-folder>/`.
2. Add `_case.md` with case posture, source id, source anchors, legal counts, outcome, and availability.
3. Add maintenance evidence assets to `assets/<case-folder>/`; they remain regeneration and review inputs and are not bundled in portable-core.
4. Add one card per screen or figure.
5. Add `_coverage.json` with card, asset, figure, norm, and provisional pattern inventory.
6. Add or update the source record in `sources/source_capsules.json`; keep the binary PDF outside portable releases.
7. Run reference and case validators.

## Card Rules

A card is evidence plus reasoning, not just a label. It must explain:

- What is visible in the UI.
- Which pattern id is supported.
- Which norm id may apply.
- Why the source treats the behavior as material.
- What citation fields support the claim.
- What limitations remain.

Use existing ids where possible. Add a new pattern only when existing ids cannot capture a supported, recurring behavior.

Select at least one supported material norm for the explicit jurisdiction before recording any procedural norm. A procedural norm must declare that material norm in `companion_to_material_norm_ids`; it is an enforcement or remedy companion, never the duty inferred directly from the screen. Do not mix jurisdictions or country-specific norms without matching canonical `jurisdiction` and `sub_jurisdiction` scope.

## Naming

Use stable case folders such as `amazon_prime`. Use stable card ids matching source figures or screen handles. Keep canonical maintenance `asset` paths repo-relative.

For legacy records, `source_file` may retain the original PDF filename as an alias. It must resolve to a verified capsule. New records should use `source_id` plus `source_anchor_ids`; a URL or digest alone is not a citation.

Portable copies are builder outputs, not canonical authoring targets. The builder adds direct source fields, removes `asset` frontmatter and local image paths, preserves the card body, and requires symmetric reverse references. Historical visual anchors must retain the existing `EVIDENCE.` summary and an explicit limitation that capsule text does not preserve pixel-level visual properties. Missing optional visuals fall back to capsule evidence; an optional image identifier never replaces a local anchor.

## Do Not

- Do not infer legal violations from aesthetics alone.
- Do not cite `_coverage.json` as legal evidence.
- Do not create dangling pattern or norm ids.
- Do not rename existing ids without updating all references.
- Do not add PDFs to a portable release.

