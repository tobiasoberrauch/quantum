export interface Status {
  key_present: boolean;
  openrouter_installed: boolean;
  jsonschema_installed: boolean;
  chains: Record<string, string[]>;
  reference_costs: Record<string, number>;
  baseline_ratios: Record<string, number>;
  baseline_score: number;
  venv_qvc: string;
  venv_chem: string;
  runs_dir: string;
  adapters_dir: string;
  examples_dir: string;
}

export interface JobSummary {
  id: string;
  kind: string;
  status: string;
  created?: number;
  finished?: number;
  error?: string | null;
}

export interface Job extends JobSummary {
  params: any;
  result: any;
  started?: number;
}

export interface TraceRec {
  schema: string;
  chain: string[];
  prompt: string;
  started: number;
  ok: boolean;
  attempts: string[];
  served_model?: string;
  requested_model?: string;
  response_mode?: string;
  error?: string;
  elapsed?: number;
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number; cost: number };
}

export interface LogRec { ts: number; level: string; msg: string; }
export interface Artifact { path: string; size: number; }

export interface Analogy {
  source_domain: string; transfer_principle: string;
  formal_mapping: string; breakdown_conditions: string;
}
export interface Proposal {
  id: string; task: string; origin_role: string; origin_model: string;
  verification_status: string; title: string; novel_mechanism: string;
  analogy: Analogy; change_to_existing_baseline: string;
  needed_source_assets: string[]; mathematical_invariants: string[];
  predicted_resource_tradeoff: string; implementation_plan: string[];
  cheap_precheck: string; official_verifier_plan: string;
  falsification_condition: string; prior_art_queries: string[];
  known_failure_avoidance: string; blocking_risks: string[];
  survives?: boolean;
  debate_scores?: { feasibility?: number; impact?: number; novelty?: number };
}
export interface Review {
  proposal_id: string; thesis: string; antithesis: string; synthesis: string;
  hardest_counterexample: string; invariant_violation_risk: string;
  decisive_experiment: string; feasibility: number; potential_impact: number;
  novelty_status: string; reviewer_model?: string;
}
export interface Selected {
  proposal_id: string; rationale: string; first_implementation_step: string;
  success_threshold: string; abort_condition: string; required_assets: string[];
}
export interface ResearchData {
  created_utc: string; baseline_score_approx: number; target_score: number;
  novelty_status: string; experiment_status: string; scope: string[];
  proposals: Proposal[]; reviews: Review[];
  selection: { research_strategy: string; priority_queue: Selected[]; shared_falsification_risks: string[] };
  generation_provenance: Record<string, { model: string; fallback_failures: string[] }>;
  synthesis_model?: string;
  debates?: Record<string, { pro?: any; con?: any; judge?: any; models?: { pro?: string; con?: string; judge?: string } }>;
  debate_provenance?: Record<string, { pro?: string; con?: string; judge?: string }>;
  top10_target?: number;
}
export interface VerifyRun {
  salt: string; status: string; cost: number | null; shots: number | null;
  cached?: boolean; error?: string; stderr_tail?: string;
  num_qubits?: number; worst_error_over_tolerance?: number; estimated_ratio?: number;
  precheck?: boolean; cost_is_estimate?: boolean;
}
export interface VerifyResult {
  task: string; candidate: string; sha256: string; source: string; executed: boolean;
  status: string; all_passed?: boolean; runs: VerifyRun[]; command_preview?: string[][];
  official_cost_if_identical_across_salts?: number | null; warning?: string; _precheck?: boolean;
}
export interface ScoreResult { ratios: Record<string, number>; score: number; target: number; above_target: boolean; }

// ---- Team (multi-agent discussion) ----
export interface Model {
  id: string; label: string; kind: "local" | "cloud" | "custom";
  base_url: string; model: string; api_key_env?: string; max_tokens?: number;
  extra_body?: Record<string, unknown>;
}
export interface TeamAgent { name: string; role: string; model_id: string; }
export interface TeamMsg { round: number; agent: string; role: string; model: string; content: string; status?: "ok" | "error"; }
export interface TeamResult {
  starting_prompt: string;
  agents: { name: string; role: string; model: string }[];
  rounds: number;
  transcript: TeamMsg[];
  final_solution: string;
  synthesis_model: string;
  files?: { team_json: string; solution_md: string };
}
