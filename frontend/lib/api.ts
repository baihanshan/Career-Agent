import type { AnalysisRequest, AnalysisResponse } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function runAnalysis(request: AnalysisRequest): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/analysis`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  const payload = (await response.json()) as AnalysisResponse;
  if (!response.ok) {
    return {
      analysis_id: payload.analysis_id ?? "analysis_failed",
      status: "failed",
      result: null,
      error: payload.error ?? {
        code: "REQUEST_FAILED",
        message: "分析请求失败，请检查输入后重试。",
      },
    };
  }

  return payload;
}
