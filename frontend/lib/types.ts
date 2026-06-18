export type SourceType = "text" | "markdown";
export type RequirementCategory =
  | "responsibility"
  | "hard_skill"
  | "soft_skill"
  | "qualification"
  | "nice_to_have";
export type Importance = "high" | "medium" | "low";
export type MatchLevel = "strong" | "partial" | "weak" | "missing";
export type RiskLevel = "low" | "medium" | "high";
export type Severity = "low" | "medium" | "high";
export type OverallStatus = "pass" | "pass_with_warnings" | "fail";
export type AnalysisStatus = "completed" | "failed";
export type LlmProvider = "local" | "openai" | "deepseek" | "openai_compatible";
export type ProfileSectionType = "internship" | "project" | "skill" | "education" | "other";

export interface ProfileDocument {
  document_id?: string;
  source_name: string;
  source_type: SourceType;
  content: string;
  created_at?: string;
}

export interface ProfileChunk {
  chunk_id: string;
  document_id: string;
  source_name: string;
  section_label?: string | null;
  section_type: ProfileSectionType;
  section_title?: string | null;
  company_name?: string | null;
  role_title?: string | null;
  project_name?: string | null;
  technologies: string[];
  text: string;
  start_char?: number | null;
  end_char?: number | null;
  embedding_id?: string | null;
}

export interface JDRequirement {
  requirement_id: string;
  category: RequirementCategory;
  text: string;
  importance: Importance;
  keywords: string[];
}

export interface MatchItem {
  requirement_id: string;
  match_level: MatchLevel;
  rationale: string;
  evidence_ids: string[];
  gap_note?: string | null;
}

export interface MatchStrategyItem {
  evidence_id: string;
  section_type: ProfileSectionType;
  priority_score: number;
  rationale: string;
  requirement_id?: string | null;
}

export interface MatchStrategy {
  ranked_evidence: MatchStrategyItem[];
  covered_requirement_ids: string[];
  missing_requirement_ids: string[];
  summary?: string | null;
}

export interface ResumeBullet {
  text: string;
  target_requirement_ids: string[];
  evidence_ids: string[];
  risk_level: RiskLevel;
}

export interface InterviewPrepQuestion {
  question: string;
  sample_answer: string;
  supporting_evidence_ids: string[];
}

export interface InterviewPrep {
  jd_questions: InterviewPrepQuestion[];
  resume_deep_dive_questions: InterviewPrepQuestion[];
}

export interface GeneratedAssets {
  match_summary: string;
  resume_bullets: ResumeBullet[];
  interview_prep: InterviewPrep;
}

export interface GroundingWarning {
  asset_type: "resume_bullet" | "match_summary" | "interview_prep";
  asset_id: string;
  claim: string;
  reason: string;
  severity: Severity;
}

export interface CoverageGap {
  requirement_id: string;
  requirement_text?: string | null;
  reason: string;
  severity: Severity;
}

export interface ProcessingWarning {
  code: string;
  message: string;
  source?: string | null;
}

export interface AgentToolResult {
  tool_name: string;
  arguments_summary: string;
  return_summary: string;
  status: "success" | "error";
}

export interface AgentTrace {
  agent_name: string;
  steps: AgentToolResult[];
  final_decision_summary: string;
}

export interface EvaluationReport {
  grounding_warnings: GroundingWarning[];
  coverage_gaps: CoverageGap[];
  specificity_notes: string[];
  risk_summary: string;
  overall_status: OverallStatus;
}

export interface RiskItem {
  risk_type: "JD 未覆盖" | "简历表述太泛" | "证据不足" | "生成内容可能夸大";
  title: string;
  jd_requirement_summary: string;
  resume_current_state: string;
  risk_reason: string;
  recommendation: string;
  severity: Severity;
}

export interface RiskReport {
  risks: RiskItem[];
}

export interface AnalysisResult {
  jd_requirements: JDRequirement[];
  match_analysis: MatchItem[];
  match_strategy?: MatchStrategy | null;
  generated_assets: GeneratedAssets;
  evaluation_report: EvaluationReport;
  risk_report?: RiskReport | null;
  processing_warnings?: ProcessingWarning[];
  agent_traces?: AgentTrace[];
}

export interface AnalysisRequest {
  profile_documents: ProfileDocument[];
  job_description: string;
  run_config?: {
    provider?: LlmProvider;
    model?: string;
    temperature?: number;
    top_k?: number;
    api_key?: string;
    base_url?: string;
  };
}

export interface AnalysisResponse {
  analysis_id: string;
  status: AnalysisStatus;
  result?: AnalysisResult | Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
}
