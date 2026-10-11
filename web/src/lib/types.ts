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
  row_id: string; qs_code: string; task: string; mode: string; resource_type: string; resource_code: string;
  resource: string; unit: string; qs_qty: number; productivity: number | null; productivity_unit: string;
  hours: number; duration_override: number | null; count: number | null; manual_qty: number | null; utilisation: number | null; waste: number | null;
  library_rate: number; job_override: number | null; applied_rate: number; cost: number; weather_exposed: boolean;
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
export interface Edit { target: string; key: string; field: string; value: string }
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
