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
  reconciled: boolean;
}
export interface QSLine {
  code: string; section: string; description: string; unit: string; quantity: number; amount: number; rate: number;
  basis: string; source: string; status: string; rag: string; owner: string; verification: string; quote_ref: string;
  notes: string; rows: string[];
}
export interface BuildUpLine {
  row_id: string; qs_code: string; task: string; mode: string; resource_type: string; resource_code: string;
  resource: string; unit: string; qs_qty: number; productivity: number | null; productivity_unit: string;
  hours: number; count: number | null; manual_qty: number | null; utilisation: number | null; waste: number | null;
  library_rate: number; job_override: number | null; applied_rate: number; cost: number; weather_exposed: boolean;
  qa: string; workbook_qa: string; verified: boolean; confidence: string; rag: string; quote_ref: string;
  source_date: string; assumption: string; note: string; library_source: string;
}
