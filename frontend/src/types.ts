/* ─── API Types ─── */

export interface Element {
  position: number;
  value: string;
  sub_elements: string[];
}

export interface Segment {
  segment_id: string;
  elements: Element[];
  raw: string;
  line_number: number;
  ui_label: string;
}

export interface Loop {
  loop_id: string;
  ui_label: string;
  segments: Segment[];
  children: Loop[];
}

export interface EnvelopeInfo {
  interchange_control_number: string;
  sender_id: string;
  receiver_id: string;
  functional_group_control_number: string;
  transaction_set_control_number: string;
  gs_code: string;
  st_code: string;
  isa_date: string;
  isa_time: string;
}

export interface Delimiters {
  element_separator: string;
  sub_element_separator: string;
  segment_terminator: string;
}

export interface ParseResult {
  transaction_type: string;
  envelope: EnvelopeInfo;
  loops: Loop[];
  segment_count: number;
  raw_segment_count: number;
  delimiters: Delimiters | null;
  metadata: Record<string, unknown>;
}

export interface ValidationError {
  segment_id: string;
  element_position: number | null;
  loop_id: string;
  snip_level: number;
  severity: 'error' | 'warning' | 'info';
  code: string;
  message: string;
  suggestion: string;
}

export interface ValidationSummary {
  snip1_errors: number;
  snip2_errors: number;
  snip3_errors: number;
  total_errors: number;
  total_warnings: number;
}

export interface ParseResponse {
  interchange_id: number;
  parse_result: ParseResult;
}

export interface ValidateResponse {
  interchange_id: number;
  parse_result: ParseResult;
  validation_errors: ValidationError[];
  summary: ValidationSummary;
}

export interface ReconciliationMatch {
  claim_id: string;
  billed_amount: number;
  paid_amount: number;
  patient_responsibility: number;
  total_adjustments: number;
  adjustment_codes: string;
  adjustment_groups: string;
  claim_status: string;
  status: string;
}

export interface ReconciliationReport {
  matched: ReconciliationMatch[];
  unmatched_claims: { claim_id: string; billed_amount: number; status: string }[];
  unmatched_remittances: { claim_id: string; billed_amount: number; paid_amount: number; status: string }[];
  summary: {
    total_matched: number;
    total_unmatched_claims: number;
    total_unmatched_remittances: number;
    total_billed: number;
    total_paid: number;
    total_adjustments: number;
    net_difference: number;
  };
}

export interface DeltaMember {
  subscriber_id: string;
  name: string;
  status: string;
  maintenance_code?: string;
  insurance_type?: string;
  benefit_start?: string;
  benefit_end?: string;
  changes?: { field: string; old_value: string; new_value: string }[];
}

export interface DeltaReport {
  added: DeltaMember[];
  terminated: DeltaMember[];
  changed: DeltaMember[];
  unchanged_count: number;
  summary: {
    total_added: number;
    total_terminated: number;
    total_changed: number;
    total_unchanged: number;
  };
}

export interface ExplainResponse {
  error_code: string;
  snip_level: number;
  severity: string;
  plain_english: string;
  regulatory_context: string[];
  suggested_fix: string;
  sources: string[];
}

/* ─── Active View ─── */
export type ActiveView = 'upload' | 'validate' | 'reconcile' | 'delta';
