export interface Estimate {
  meta: Record<string, string>;
  controls: Record<string, string>;
  summary: {
    all_in: number; siteworks_tender: number; known_cost: number; siteworks_precommercial: number;
    management_reserve: number; weather_allowance: number; gross_margin_on_sell: number; base_direct: number;
    dry_programme_wd: number; planning_wd: number;
  };
  consolidated: {
    own_works: number; overlays: { name: string; amount: number; kind: string }[]; overlays_total: number;
    gross_known_package: number; confirmed_overlap: number; known_after_overlap: number; overhead: number;
    profit: number; all_in: number; gross_margin_on_sell: number; overhead_rate: number; margin: number;
  };
  tender: {
    base_direct: number; pre_margin_total: number; subtotal: number; overhead: number; profit: number;
    commercial_total: number; total_excl_gst: number; gst: number; total_incl_gst: number;
  };
  commercial: { ref: string; name: string; method: string; include: boolean; pct: number; pc_sum: number; amount: number; stage: string }[];
  qs: QSLine[];
  sections: { section: string; amount: number; items: string[] }[];
  buildup: BuildUpLine[];
  library: { code: string; category: string; description: string; unit: string; rate: number; operator_included: string; fuel_included: string; source: string }[];
  weather: Record<string, any>;
  schedule: PriceSchedule;
  register: RegisterItem[];
  register_summary: { rfis: number; open_rfis: number; open_red_rfis: number; red_risks: number };
  quotes: QuoteItem[];
  programme: ProgrammeData;
  risk_truth: RiskTruth;
  management_reserve: ManagementReserve | null;
  reconciliation: { name: string; engine: number; workbook: number; difference: number; ok: boolean }[];
  qa_counts: Record<string, number>;
  reconciled: boolean | null;
  edited: boolean;
}
export interface QSLine {
  code: string; section: string; description: string; unit: string; quantity: number; amount: number; rate: number;
  basis: string; source: string; status: string; rag: string; owner: string; verification: string; quote_ref: string;
  notes: string; rows: string[];
}
export interface BuildUpLine {
  row_id: string; uid: string; qs_code: string; task: string; mode: string; resource_type: string; resource_code: string;
  resource: string; unit: string; qs_qty: number; productivity: number | null; productivity_unit: string;
  hours: number; duration_override: number | null; count: number | null; manual_qty: number | null; utilisation: number | null; waste: number | null;
  library_rate: number; job_override: number | null; applied_rate: number; cost: number; weather_exposed: boolean; weather_task_type?: string;
  qa: string; workbook_qa: string; verified: boolean; confidence: string; rag: string; quote_ref: string;
  source_date: string; assumption: string; note: string; library_source: string;
}

export interface User { id: string; email: string; name: string; role: string; org_id: string; org_name: string | null }
export type Stage = "estimating" | "submitted" | "won" | "lost" | "withdrawn";
export const STAGES: { id: Stage; label: string }[] = [
  { id: "estimating", label: "Estimating" }, { id: "submitted", label: "Submitted" },
  { id: "won", label: "Won" }, { id: "lost", label: "Lost" }, { id: "withdrawn", label: "Withdrawn" },
];
export interface TenderSummary {
  label: string; all_in: number; siteworks_tender: number; known_cost: number; release: string;
  red_risks: number | null; reconciled: boolean | null; edited?: boolean; gross_margin_on_sell: number;
}
export interface Tender {
  id: string; name: string; client: string; location: string; stage: Stage; latest_rev: number;
  summary: TenderSummary; created_at: string; updated_at: string;
}
export interface RevisionInfo {
  n: number; label: string; lifecycle: string; created_at: string; source_filename: string; all_in: number | null;
  has_inputs: boolean; parent_n: number | null; note: string; change_count: number; edited: boolean;
}
export interface Change { target: string; key: string; field: string; label: string; before: string; after: string }
export interface Edit { target: string; key: string; field?: string; op?: "add" | "delete"; value?: unknown }
export interface TenderDetail extends Tender { revisions: RevisionInfo[] }
export interface TenderList { tenders: Tender[]; totals: { count: number; by_stage: Record<Stage, { count: number; value: number }> } }
export interface Diff {
  settings: { key: string; label: string; a: number; b: number }[];
  headline: { key: string; label: string; a: number | null; b: number | null; delta: number }[];
  sections: { section: string; a: number | null; b: number | null; delta: number }[];
  qs: { code: string; description: string; unit: string; kind: string; qty_a: number | null; qty_b: number | null; amount_a: number | null; amount_b: number | null; delta: number }[];
  buildup: { row_id: string; qs_code: string; task: string; resource: string; kind: string; rate_a: number | null; rate_b: number | null; hours_a: number | null; hours_b: number | null; cost_a: number | null; cost_b: number | null; delta: number }[];
  commercial: { ref: string; name: string; include_a: boolean | null; include_b: boolean; amount_a: number | null; amount_b: number; delta: number }[];
  overlays: { name: string; a: number | null; b: number | null; delta: number }[];
  counts: Record<string, number>;
  identical: boolean;
}

export interface WeatherTask { name: string; category: string; rain_exposure: number; rain_loss: number; carryover: number; wind_sensitivity: number; wind_loss: number; nonrecoverable: number; basis: string }
export interface WeatherCatalog { version: string; engine_from: string; engine_to: string; attribution: string; stations: string[]; wind_proxy_stations: string[]; tasks: WeatherTask[] }

export interface ScheduleLine { ref: string; trade: string; kind: "work" | "pg" | "margin"; amount: number; sources: { key: string; label: string; amount: number }[] }
export interface ScheduleGroup { id: string; name: string; code: string; subtotal: number; total: number; cost: number; hidden: number; lines: ScheduleLine[] }
export interface ScheduleSource { key: string; label: string; amount: number; own: boolean; map: string | { to: string; amount?: string }[] | null | undefined }
export interface PriceSchedule {
  auto: boolean; name: string; client: string; reconciles: boolean; problems: string[]; total: number; all_in: number; difference: number; gross_package: number;
  groups: ScheduleGroup[]; unmapped: { key: string; label: string; amount: number }[]; sources: ScheduleSource[];
  targets: { value: string; label: string; group: string }[];
}

export type RegisterKind = "rfi" | "risk" | "assumption" | "exclusion" | "inclusion" | "document";
export interface RegisterItem {
  id: string; kind: RegisterKind; ref: string; title: string; detail: string; action: string; status: string; rag: string;
  owner: string; likelihood: string; impact: string; rating: string;
}

export interface QuoteItem {
  id: string; ref: string; package: string; supplier: string; estimate_ref: string; qty: string; unit: string; amount: string; scope: string; documents: string;
  status: string; action: string; notes: string; treatment: string; verification: string; source: string; quote_date: string; valid_until: string;
}

export interface ProgrammeTask {
  id: string; code: string; name: string; qs_code: string; section: string; amount: number | null; duration: number; derived: number | null; override: string | null;
  predecessors: string[]; hammock: boolean; basis: string; note: string; es: number; ef: number; float: number; critical: boolean; start: string | null; finish: string | null;
}
export interface ProgrammeData {
  set_up: boolean; tasks: ProgrammeTask[]; duration: number; critical_path: string[]; problems: string[]; start: string; days_per_week: number; hours_per_day: number;
  finish: string | null; missing: { code: string; description: string; amount: number | null }[];
}

export type RiskMode = "Already in Base / No Add" | "Unit Rate Delta" | "Probability x Impact" | "Scenario Weighted" | "Fixed Allowance" | "Specialist Engine" | "By Others / Excluded" | "RFI Hold";
export interface RiskExposure {
  id: string; ref: string; risk_id: string; consequence: string; driver: string; cost_ref: string; treatment: string; baseline_amount: string; residual: string;
  mode: RiskMode | ""; qty: string; unit: string; unit_rate: string; probability: string; provision: string; owner: string; distinct: string; target: string;
  include: string; overlap_group: string; embedded: string; evidence: string; evidence_note: string; integration_complete: string; basis: string; action: string;
  source: string; modelled: number | null; addition: number; duplication: string; status: "RED" | "AMBER" | "GREEN"; reasons: string[]; flows: boolean; provision_unused: boolean;
}
export interface RiskTruth {
  exposures: RiskExposure[]; ca01: number; ca02: number; residual_total: number; red_risks: number; red_exposures: number; amber_exposures: number;
  duplicate_gate: string; programme_gate: string; gate: string; issues: string[]; live: boolean;
}

export interface ReserveItem {
  id: string; ref: string; title: string; source_ref: string; exposure_ref: string; description: string; basis: "Sell" | "Cost"; impact: string;
  impact_status: "Quantified" | "Proxy" | "Unquantified"; probability_low: string; probability_high: string; prob_status: "GREEN" | "AMBER" | "UNKNOWN";
  prob_basis: string; overlap_group: string; owner: string; action: string;
  cost_impact: number | null; weighted_low: number | null; weighted_high: number | null; weighted_low_sell: number | null; weighted_high_sell: number | null;
  sensitivity: number | null; counted: boolean; status: "RED" | "AMBER" | "GREEN"; reasons: string[];
}
export interface ManagementReserve {
  items: ReserveItem[]; selected: number | null; selected_sell: number | null; selected_pct: number | null; selected_basis: string; adjudicated_by: string; adjudicated_on: string;
  weighted_low: number; weighted_high: number; weighted_mid: number; weighted_low_sell: number; weighted_high_sell: number; weighted_mid_sell: number;
  position: "below" | "within" | "above" | null; gap: number | null; factor: number; unknown_items: number; unquantified_items: number; issues: string[]; notes: string[]; status: "RED" | "AMBER" | "GREEN";
}
