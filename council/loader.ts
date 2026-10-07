import type { CouncilModule } from "./interface";

// COUNCIL_MODULE env selects the implementation (§4.1c). Decision #2: modules
// live in this repo. "stub" returns fixture verdicts for offline work; "real"
// is council/skill: the Examiner and Counsel model calls on the model
// config/models.ts names, with the deterministic legal slice and the report
// validator between them. Swapping requires no code changes anywhere else
// in the app.
export async function loadCouncil(): Promise<CouncilModule> {
  const which = process.env.COUNCIL_MODULE ?? "stub";
  if (which === "stub") {
    return (await import("./stub")).default;
  }
  if (which === "real") {
    return (await import("./skill")).default;
  }
  throw new Error(`Unknown COUNCIL_MODULE "${which}": expected "stub" or "real".`);
}
