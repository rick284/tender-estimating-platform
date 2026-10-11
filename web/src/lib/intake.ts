// The platform's version of the Estimate Intake Block (core fields). Keys match the API (engine/tender_engine/blank.py).
export const TENDER_LEVELS = ["Concept", "Feasibility", "Tender", "Variation"] as const;

export const INTAKE_FIELDS: { key: string; label: string; hint: string; long?: boolean }[] = [
  { key: "client", label: "Client or head contractor", hint: "Who are we pricing for?" },
  { key: "location", label: "Location", hint: "Site address or suburb" },
  { key: "contract_type", label: "Contract type", hint: "e.g. NZS 3910, lump sum, measure and value" },
  { key: "pricing_basis", label: "Pricing basis", hint: "e.g. lump sum with provisional quantities" },
  { key: "scope", label: "Scope summary", hint: "What is being built, in a few sentences", long: true },
  { key: "drawings", label: "Drawings and documents received", hint: "Drawing set, revision, specs, addenda", long: true },
  { key: "programme", label: "Programme constraints", hint: "Start, finish, staging, seasonal limits", long: true },
  { key: "site_constraints", label: "Site constraints", hint: "Access, live services, neighbours, working hours", long: true },
  { key: "inclusions_exclusions", label: "Inclusions and exclusions", hint: "What the price does and doesn't cover", long: true },
  { key: "assumptions", label: "Locked assumptions", hint: "Things you are assuming, to be confirmed", long: true },
  { key: "missing_info", label: "Missing information", hint: "Anything you still need from the client (becomes RFIs)", long: true },
];
