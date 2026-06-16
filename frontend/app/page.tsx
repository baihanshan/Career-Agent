"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { JobDescriptionInput } from "../components/JobDescriptionInput";
import { ProfileInput } from "../components/ProfileInput";
import { ResultView } from "../components/ResultView";
import { RunStatus } from "../components/RunStatus";
import { runAnalysis } from "../lib/api";
import type { AnalysisResult, AnalysisResponse } from "../lib/types";

type UiStatus = "idle" | "loading" | "success" | "error";

export default function Home() {
  const [profileMaterials, setProfileMaterials] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [status, setStatus] = useState<UiStatus>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);

  const canSubmit = useMemo(
    () => profileMaterials.trim().length > 0 && jobDescription.trim().length > 0,
    [profileMaterials, jobDescription]
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || status === "loading") {
      setErrorMessage("请先填写个人材料和目标岗位 JD。");
      setStatus("error");
      return;
    }

    setStatus("loading");
    setErrorMessage("");
    setResult(null);

    try {
      const response = await runAnalysis({
        profile_documents: [
          {
            source_name: "profile.md",
            source_type: "markdown",
            content: profileMaterials,
          },
        ],
        job_description: jobDescription,
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
      setErrorMessage(
        typeof response.error?.message === "string"
          ? response.error.message
          : "分析失败，请检查输入后重试。"
      );
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
            粘贴个人材料和目标岗位 JD，生成带证据引用的匹配分析、简历要点、求职信草稿和面试准备建议。
          </p>
        </div>
      </section>

      <form className="input-grid" onSubmit={handleSubmit}>
        <ProfileInput value={profileMaterials} onChange={setProfileMaterials} />
        <JobDescriptionInput value={jobDescription} onChange={setJobDescription} />
        <div className="form-actions">
          <button type="submit" disabled={!canSubmit || status === "loading"}>
            {status === "loading" ? "分析中..." : "开始分析"}
          </button>
          <span>空输入时提交按钮不可用。</span>
        </div>
      </form>

      <RunStatus status={status} errorMessage={errorMessage} />

      {result ? <ResultView result={result} /> : <EmptyState />}
    </main>
  );
}

function EmptyState() {
  return (
    <section className="empty-state">
      <h2>结果区</h2>
      <p>
        完成分析后，这里会展示匹配总结、证据表、简历要点、求职信草稿、面试准备、流程警告和风险提示。
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
      Array.isArray(candidate.evidence_table) &&
      Array.isArray(candidate.match_analysis) &&
      candidate.generated_assets &&
      candidate.evaluation_report
  );
}
