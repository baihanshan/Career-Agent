"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";

import { JobDescriptionInput } from "../components/JobDescriptionInput";
import { LlmSettings, type LlmSettingsValue } from "../components/LlmSettings";
import { ProfileInput } from "../components/ProfileInput";
import { ResultView } from "../components/ResultView";
import { RunStatus } from "../components/RunStatus";
import { runAnalysis } from "../lib/api";
import type {
  AnalysisResult,
  AnalysisResponse,
  PDFParseResponse,
  SourceType,
} from "../lib/types";

type UiStatus = "idle" | "loading" | "success" | "error";

const LLM_SETTINGS_STORAGE_KEY = "careerpilot.llmSettings";

const DEFAULT_LLM_SETTINGS: LlmSettingsValue = {
  provider: "deepseek",
  apiKey: "",
  model: "deepseek-v4-flash",
  baseUrl: "https://api.deepseek.com",
  temperature: 0.2,
};

const WORKFLOW_ERROR_MESSAGES: Record<string, string> = {
  JD_ANALYST_ERROR: "岗位描述分析失败，请检查 JD 内容后重试。",
  LLM_OUTPUT_PARSE_ERROR: "岗位描述暂时无法解析，请调整内容后重试。",
  RESUME_EVIDENCE_AGENT_ERROR: "未找到足够的项目或实习经历来支撑本次分析。",
  MATCH_STRATEGIST_ERROR: "岗位匹配分析失败，请稍后重试。",
  RESUME_BULLET_AGENT_ERROR: "简历要点生成失败，请稍后重试。",
  INTERVIEW_PREP_AGENT_ERROR: "面试准备生成失败，请稍后重试。",
  RISK_AUDITOR_AGENT_ERROR: "风险评估失败，请稍后重试。",
  VECTOR_STORE_ERROR: "个人材料处理失败，请稍后重试。",
};

export default function Home() {
  const [profileMaterials, setProfileMaterials] = useState("");
  const [profileSource, setProfileSource] = useState<{
    sourceName: string;
    sourceType: SourceType;
  }>({ sourceName: "profile.md", sourceType: "markdown" });
  const [jobDescription, setJobDescription] = useState("");
  const [llmSettings, setLlmSettings] = useState<LlmSettingsValue>(DEFAULT_LLM_SETTINGS);
  const [status, setStatus] = useState<UiStatus>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);

  const canSubmit = useMemo(
    () =>
      profileMaterials.trim().length > 0 &&
      jobDescription.trim().length > 0 &&
      (llmSettings.provider === "local" || llmSettings.apiKey.trim().length > 0),
    [profileMaterials, jobDescription, llmSettings]
  );

  useEffect(() => {
    const storedSettings = window.localStorage.getItem(LLM_SETTINGS_STORAGE_KEY);
    if (!storedSettings) {
      return;
    }

    try {
      setLlmSettings({ ...DEFAULT_LLM_SETTINGS, ...JSON.parse(storedSettings) });
    } catch {
      window.localStorage.removeItem(LLM_SETTINGS_STORAGE_KEY);
    }
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || status === "loading") {
      setErrorMessage("请先填写个人材料、目标岗位 JD 和模型 API Key。");
      setStatus("error");
      return;
    }

    setStatus("loading");
    setErrorMessage("");
    setResult(null);

    try {
      const settingsToSave = {
        ...llmSettings,
        apiKey: llmSettings.provider === "local" ? "" : llmSettings.apiKey,
      };
      window.localStorage.setItem(LLM_SETTINGS_STORAGE_KEY, JSON.stringify(settingsToSave));
      const response = await runAnalysis({
        profile_documents: [
          {
            source_name: profileSource.sourceName,
            source_type: profileSource.sourceType,
            content: profileMaterials,
          },
        ],
        job_description: jobDescription,
        run_config: {
          provider: llmSettings.provider,
          model: llmSettings.model.trim() || "default",
          temperature: llmSettings.temperature,
          top_k: 5,
          api_key:
            llmSettings.provider === "local" ? undefined : llmSettings.apiKey.trim(),
          base_url:
            llmSettings.provider === "deepseek" ||
            llmSettings.provider === "openai_compatible"
              ? llmSettings.baseUrl.trim()
              : undefined,
        },
      });
      handleAnalysisResponse(response);
    } catch {
      setStatus("error");
      setErrorMessage("分析失败，请检查后端服务是否启动后重试。");
    }
  }

  function handleAnalysisResponse(response: AnalysisResponse) {
    if (response.status === "failed") {
      setStatus("error");
      setErrorMessage(friendlyAnalysisError(response.error?.code));
      return;
    }

    if (!isAnalysisResult(response.result)) {
      setStatus("error");
      setErrorMessage("分析结果格式不完整，请稍后重试。");
      return;
    }

    setResult(response.result);
    setStatus("success");
  }

  return (
    <main className="app-shell">
      <section className="page-header">
        <div>
          <p className="eyebrow">Evidence-grounded Career Agent</p>
          <h1>CareerPilot Agent</h1>
          <p>
            粘贴个人材料和目标岗位 JD，生成带证据引用的匹配分析、简历要点、面试准备和风险提示。
          </p>
        </div>
      </section>

      <form className="input-grid" onSubmit={handleSubmit}>
        <LlmSettings value={llmSettings} onChange={setLlmSettings} />
        <ProfileInput
          value={profileMaterials}
          onChange={setProfileMaterials}
          onPdfParsed={(parsed: PDFParseResponse) => {
            setProfileMaterials(parsed.text);
            setProfileSource({ sourceName: parsed.source_name, sourceType: "text" });
          }}
        />
        <JobDescriptionInput value={jobDescription} onChange={setJobDescription} />
        <div className="form-actions">
          <button type="submit" disabled={!canSubmit || status === "loading"}>
            {status === "loading" ? "分析中..." : "开始分析"}
          </button>
          <span>设置会在首次提交后保存在本机浏览器。</span>
        </div>
      </form>

      <RunStatus status={status} errorMessage={errorMessage} />

      {result ? <ResultView result={result} /> : <EmptyState />}
    </main>
  );
}

function friendlyAnalysisError(code?: string) {
  return code && WORKFLOW_ERROR_MESSAGES[code]
    ? WORKFLOW_ERROR_MESSAGES[code]
    : "分析失败，请检查输入后重试。";
}

function EmptyState() {
  return (
    <section className="empty-state">
      <h2>结果区</h2>
      <p>
        完成分析后，这里会展示匹配总结、简历要点、面试准备、流程警告和风险提示。
      </p>
    </section>
  );
}

function isAnalysisResult(result: AnalysisResponse["result"]): result is AnalysisResult {
  if (!result || typeof result !== "object") {
    return false;
  }

  const candidate = result as Partial<AnalysisResult>;
  return Boolean(
    Array.isArray(candidate.jd_requirements) &&
      Array.isArray(candidate.match_analysis) &&
      candidate.generated_assets &&
      candidate.evaluation_report
  );
}
