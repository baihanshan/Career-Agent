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

export interface ResumeBullet {
  text: string;
  target_requirement_ids: string[];
  evidence_ids: string[];
  risk_level: RiskLevel;
}

export interface InterviewPrepItem {
  topic: string;
  why_it_matters: string;
  supporting_evidence_ids: string[];
  prep_suggestion: string;
}

export interface GeneratedAssets {
  match_summary: string;
  resume_bullets: ResumeBullet[];
  interview_prep: InterviewPrepItem[];
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
  reason: string;
  severity: Severity;
}

export interface ProcessingWarning {
  code: string;
  message: string;
  source?: string | null;
}

export interface EvaluationReport {
  grounding_warnings: GroundingWarning[];
  coverage_gaps: CoverageGap[];
  specificity_notes: string[];
  risk_summary: string;
  overall_status: OverallStatus;
}

export interface AnalysisResult {
  jd_requirements: JDRequirement[];
  match_analysis: MatchItem[];
  generated_assets: GeneratedAssets;
  evaluation_report: EvaluationReport;
  processing_warnings?: ProcessingWarning[];
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
