// Pure transformations at the deterministic retrieval/report boundary.
// Internal ids are used to join router output to KB records, then removed
// before Counsel sees the working set.

type Row = Record<string, unknown>;

function rows(value: unknown): Row[] {
  return Array.isArray(value)
    ? value.filter((item): item is Row => Boolean(item) && typeof item === "object" && !Array.isArray(item))
    : [];
}

function values(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function dedupe<T>(items: T[], key: (item: T) => string): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const itemKey = key(item);
    if (seen.has(itemKey)) return false;
    seen.add(itemKey);
    return true;
  });
}

export function humanAuthority(norm: Row | undefined): string {
  if (!norm) return "";
  const instrument = String(norm.instrument ?? "").trim();
  const citation = String(norm.citation ?? "").trim();
  if (!instrument) return citation;
  if (!citation || instrument.toLocaleLowerCase().includes(citation.toLocaleLowerCase())) {
    return instrument;
  }
  return `${instrument} — ${citation}`;
}

function jurisdictionLabel(result: Row): string {
  const jurisdiction = String(result.jurisdiction ?? "").trim();
  const subJurisdiction = String(result.sub_jurisdiction ?? "").trim();
  return subJurisdiction ? `${jurisdiction}:${subJurisdiction}` : jurisdiction;
}

function normClassifications(result: Row): Map<string, string> {
  const explicit = result.material_norm_classifications;
  if (explicit && typeof explicit === "object" && !Array.isArray(explicit)) {
    return new Map(
      Object.entries(explicit as Row).map(([normId, classification]) => [
        normId,
        String(classification),
      ]),
    );
  }
  return new Map(
    values(result.material_norm_ids).map((normId) => [
      normId,
      String(result.classification ?? "conditional_candidate"),
    ]),
  );
}

function strongestClassification(current: string | undefined, candidate: string): string {
  if (current === "supported_route" || candidate === "supported_route") return "supported_route";
  return "conditional_candidate";
}

function classificationByNorm(context: Row): Map<string, string> {
  const result = new Map<string, string>();
  for (const route of rows(context.routes)) {
    for (const jurisdiction of rows(route.jurisdiction_results)) {
      for (const [normId, classification] of normClassifications(jurisdiction)) {
        result.set(normId, strongestClassification(result.get(normId), classification));
      }
    }
  }
  return result;
}

export function selectedSupportedMaterialNormIds(context: Row): string[] {
  return [...classificationByNorm(context)]
    .filter(([, classification]) => classification === "supported_route")
    .map(([normId]) => normId)
    .sort();
}

// validate_report.py's routed-slice check reads this same set (via the ids
// index.ts passes it), but the model never sees `context.routes` itself -
// trimContextForCounsel drops it as engine plumbing. Without this, Counsel
// has no way to tell a fact-supported norm apart from every other candidate
// sitting in `context.norms`, and cites whichever reads best; the validator
// then rejects it on every retry because the complaint names a rule the
// prompt never stated. This turns the routing gate into prompt text.
export function citableMaterialAuthorities(context: Row): { id: string; name: string }[] {
  const byId = new Map(rows(context.norms).map((norm) => [String(norm.id), norm]));
  return selectedSupportedMaterialNormIds(context)
    .map((id) => ({ id, name: humanAuthority(byId.get(id)) }))
    .filter((entry) => entry.name);
}

// Every other material norm in the slice: citable, but only under the
// conditional discipline (Medium confidence + an explicit "conditional on"
// clause naming the unestablished predicate). Binary supported-or-silent was
// the Wave 6 regression: 10 of 18 routes carry no facts or anchors yet, so
// their norms could never be cited and findings collapsed 82 -> 8 -> 0. Two
// tiers keep the anti-over-citation gate (an unconditioned citation still
// fails) while the report can always name the norm and its liability.
export function conditionalMaterialAuthorities(
  context: Row,
): { id: string; name: string }[] {
  const supported = new Set(selectedSupportedMaterialNormIds(context));
  return rows(context.norms)
    .filter((norm) => norm.type !== "procedural" && !supported.has(String(norm.id)))
    .map((norm) => ({ id: String(norm.id), name: humanAuthority(norm) }))
    .filter((entry) => entry.name)
    .sort((a, b) => a.id.localeCompare(b.id));
}

// Patterns the Examiner saw but no authority backs, with the reason.
//
//   ruled_out  - a disqualifying fact fired. Those facts are COMPLIANCE
//                observations ("full charge and cadence equally prominent",
//                "express opt-in action required"), so the route abstains and
//                its norms leave both lists. Correctly: the screen shows the
//                trader doing the right thing.
//   unmapped   - no route reaches that pattern in that jurisdiction at all.
//                Some of these are deliberate legal positions; third-party
//                reviews stay unciteable until fabrication is established.
//
// Counsel was told neither. It still saw the pattern in its evidence, reached
// for the obvious instrument, and the validator killed the entire report over
// a finding the legal layer had already decided against. That is the largest
// single cause of lost reports on the live bench - it took the Sonnet pass
// rate from 20/20 to 8/20 - and it bites hardest on the most compliant
// screens, because those are the ones whose disqualifiers can be confirmed.
//
// So name them and say what to do instead: a ruled-out pattern is material for
// Mitigating and Low-Risk Elements, an unmapped one for Missing Context, and
// neither is ever a Material Finding.
export function neutralizedPatterns(
  context: Row,
): {
  patternId: string;
  name: string;
  jurisdictions: string[];
  reason: "ruled_out" | "unmapped";
  facts: string[];
}[] {
  const byPattern = new Map<
    string,
    { jurisdictions: Set<string>; facts: Set<string>; ruledOut: boolean }
  >();
  for (const route of rows(context.routes)) {
    const patternId = String(route.pattern_id ?? "").trim();
    if (!patternId) continue;
    for (const jurisdiction of rows(route.jurisdiction_results)) {
      const triggered = values(jurisdiction.triggered_disqualifying_facts);
      const abstained =
        String(jurisdiction.status ?? "") === "abstain" ||
        values(jurisdiction.material_norm_ids).length === 0;
      if (!triggered.length && !abstained) continue;
      const entry =
        byPattern.get(patternId) ?? { jurisdictions: new Set(), facts: new Set(), ruledOut: false };
      entry.jurisdictions.add(jurisdictionLabel(jurisdiction));
      triggered.forEach((fact) => entry.facts.add(fact));
      if (triggered.length) entry.ruledOut = true;
      byPattern.set(patternId, entry);
    }
  }
  // Prose must carry the plain pattern name, never the hyphenated id: the
  // output-safety scan rejects an id echoed into the report, and the model
  // reliably echoes whatever this block gives it.
  const nameById = new Map(
    rows(context.patterns).map((pattern) => [String(pattern.id), String(pattern.name ?? "").trim()]),
  );
  return [...byPattern]
    .map(([patternId, entry]) => ({
      patternId,
      name: nameById.get(patternId) || patternId,
      jurisdictions: [...entry.jurisdictions].sort(),
      reason: (entry.ruledOut ? "ruled_out" : "unmapped") as "ruled_out" | "unmapped",
      facts: [...entry.facts].sort(),
    }))
    .filter((entry) => nameById.has(entry.patternId))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function strip(row: unknown, drop: Set<string>): unknown {
  return row && typeof row === "object" && !Array.isArray(row)
    ? Object.fromEntries(Object.entries(row as Row).filter(([key]) => !drop.has(key)))
    : row;
}

export function trimContextForCounsel(context: Row, markets: string[]): Row {
  const dropTop = new Set([
    "routes",
    "sources",
    "route_anchor_coverage",
    "kb_fingerprint",
    "output_bytes",
    "request",
    "release_version",
    "schema_version",
    "omissions",
  ]);
  const dropNorm = new Set([
    "id",
    "liability_source_urls",
    "eligible_outcome_ids",
    "companion_to_material_norm_ids",
    "source_url",
    "verified_as_of",
    "availability",
  ]);
  const dropOutcome = new Set([
    "id",
    "source_url",
    "source_pinpoint",
    "selected_as_route_anchor",
    "selected_for_norm_ids",
    "linked_norm_ids",
    "linked_patterns_or_practices",
    "local_staged_source_file",
    "verified_date",
  ]);
  const dropCaseMeta = new Set([
    "source_anchor_ids",
    "source_file",
    "source_id",
    "source_page",
    "complaint_paras",
    "availability",
    "case_id",
    "figure_id",
  ]);

  const patternName = new Map<string, string>();
  for (const pattern of rows(context.patterns)) {
    const id = String(pattern.id ?? "").trim();
    const name = String(pattern.name ?? "").trim();
    if (id && name) patternName.set(id, name);
  }
  const normCitation = new Map<string, string>();
  for (const norm of rows(context.norms)) {
    const id = String(norm.id ?? "").trim();
    const authority = humanAuthority(norm);
    if (id && authority) normCitation.set(id, authority);
  }
  const toNames = (ids: unknown, lookup: Map<string, string>): string[] =>
    values(ids).map((id) => lookup.get(id)).filter((name): name is string => Boolean(name));
  const normStatus = classificationByNorm(context);
  const routeByPattern = new Map<string, Row>();
  for (const route of rows(context.routes)) {
    const patternId = String(route.pattern_id ?? "").trim();
    if (patternId) routeByPattern.set(patternId, route);
  }

  const out: Row = {};
  for (const [key, value] of Object.entries(context)) {
    if (dropTop.has(key)) continue;
    if (key === "patterns" && Array.isArray(value)) {
      out[key] = rows(value).map((pattern) => {
        const patternId = String(pattern.id ?? "");
        const trimmed = strip(
          pattern,
          new Set(["id", "maps_to_norms", "example_cases"]),
        ) as Row;
        const route = routeByPattern.get(patternId);
        const authorities = new Map<
          string,
          { authority: string; supported: Set<string>; conditional: Set<string> }
        >();
        const routingStatus: Row[] = [];
        for (const result of rows(route?.jurisdiction_results)) {
          const jurisdiction = jurisdictionLabel(result);
          const classifications = normClassifications(result);
          for (const normId of values(result.material_norm_ids)) {
            const authority = normCitation.get(normId);
            if (!authority) continue;
            const supported = classifications.get(normId) === "supported_route";
            const aggregate = authorities.get(authority) ?? {
              authority,
              supported: new Set<string>(),
              conditional: new Set<string>(),
            };
            (supported ? aggregate.supported : aggregate.conditional).add(jurisdiction);
            authorities.set(authority, aggregate);
          }
          if (String(result.status) === "abstain") {
            routingStatus.push({
              jurisdiction,
              status: "No authority routed for this jurisdiction; abstain.",
            });
          }
        }
        trimmed.applies_to_norms = [...authorities.values()].map((authority) => {
          const supported = [...authority.supported].sort();
          const conditional = [...authority.conditional].sort();
          const jurisdiction = [...new Set([...supported, ...conditional])].join(", ");
          const applicability =
            supported.length && conditional.length
              ? `Supported for ${supported.join(", ")}; conditional only for ${conditional.join(", ")}. Do not state the conditional scope as applicable.`
              : supported.length
                ? "Supported by routed facts and source anchors; final legal fit still requires review."
                : "Conditional candidate only; factual or source gates remain unresolved and it must not be stated as applicable.";
          return { authority: authority.authority, jurisdiction, applicability };
        });
        if (routingStatus.length) trimmed.routing_status = routingStatus;
        return trimmed;
      });
    } else if (key === "norms" && Array.isArray(value)) {
      out[key] = rows(value).map((norm) => {
        const id = String(norm.id ?? "");
        const trimmed = strip(norm, dropNorm) as Row;
        trimmed.applicability =
          norm.type === "procedural"
            ? "Procedural companion only; never use as the primary Applicable norm."
            : normStatus.get(id) === "supported_route"
              ? "Supported by routed facts; final legal fit still requires review."
              : "Conditional candidate only; do not state as applicable.";
        return trimmed;
      });
    } else if (key === "outcomes" && Array.isArray(value)) {
      out[key] = rows(value)
        .filter((outcome) => {
          const subJurisdiction = String(outcome.sub_jurisdiction ?? "");
          return !subJurisdiction || markets.includes(subJurisdiction);
        })
        .map((outcome) => {
          const trimmed = strip(outcome, dropOutcome) as Row;
          trimmed.applies_to_norms = toNames(outcome.linked_norm_ids, normCitation);
          trimmed.applies_to_patterns = toNames(
            outcome.linked_patterns_or_practices,
            patternName,
          );
          const eligibility = String(outcome.benchmark_eligibility ?? "");
          if (eligibility.startsWith("eligible")) {
            let posture = String(outcome.posture ?? "").trim();
            if (/final administrative decision/i.test(posture) && !/final decision/i.test(posture)) {
              posture = `${posture} (final decision)`;
            }
            if (/final infringement notice/i.test(posture) && !/settlement|order|judgment/i.test(posture)) {
              posture = `${posture} (final notice)`;
            }
            const date = outcome.date ? ` (${String(outcome.date)})` : "";
            trimmed.benchmark_citation =
              `${String(outcome.matter_name ?? "").trim()}, ${posture}${date}; ` +
              "comparison is limited and not predictive of this matter.";
          } else if (eligibility) {
            trimmed.benchmark_citation =
              "NOT ELIGIBLE as an Observed enforcement benchmark (" +
              eligibility +
              "). If no eligible outcome applies, the benchmark field is exactly 'None identified.' " +
              "and nothing else; this matter may be mentioned only as non-benchmark context elsewhere.";
          }
          return trimmed;
        });
    } else if (key === "cases" && Array.isArray(value)) {
      out[key] = rows(value).map((caseRecord) => {
        const frontmatter = strip(caseRecord.frontmatter, dropCaseMeta) as Row | undefined;
        if (frontmatter) {
          const original = caseRecord.frontmatter as Row;
          frontmatter.patterns = toNames(original.patterns, patternName);
          frontmatter.norms = toNames(original.norms, normCitation);
        }
        const rest = strip(caseRecord, new Set(["logical_path"])) as Row;
        return { ...rest, frontmatter };
      });
    } else if (key === "warnings" && Array.isArray(value)) {
      out[key] = dedupe(
        value.map((warning) => {
          const text = String(warning);
          if (/conditional/i.test(text)) {
            return "One or more authorities remain conditional and must not be stated as applicable.";
          }
          if (/abstain|abstention/i.test(text)) {
            return "One or more requested pattern/jurisdiction routes require abstention.";
          }
          return text;
        }),
        (warning) => warning,
      );
    } else {
      out[key] = value;
    }
  }
  const scrubInternalIds = (value: unknown): unknown => {
    if (typeof value === "string") {
      let text = value;
      for (const [id, name] of [...patternName].sort((a, b) => b[0].length - a[0].length)) {
        text = text.split(id).join(name);
      }
      for (const [id, authority] of [...normCitation].sort((a, b) => b[0].length - a[0].length)) {
        text = text.split(id).join(authority);
      }
      return text;
    }
    if (Array.isArray(value)) return value.map(scrubInternalIds);
    if (value && typeof value === "object") {
      return Object.fromEntries(
        Object.entries(value as Row).map(([entryKey, entryValue]) => [
          entryKey,
          scrubInternalIds(entryValue),
        ]),
      );
    }
    return value;
  };
  return scrubInternalIds(out) as Row;
}
