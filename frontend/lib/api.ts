import type {
  AnalysisRequest,
  AnalysisResponse,
  ModelListRequest,
  ModelListResponse,
  PDFParseError,
  PDFParseResponse,
} from "./types";

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

export class PDFParseRequestError extends Error {
  constructor(public readonly code: string, message: string) {
    super(message);
    this.name = "PDFParseRequestError";
  }
}

export async function listModels(request: ModelListRequest): Promise<ModelListResponse> {
  const response = await fetch(`${API_BASE_URL}/models/list`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    return {
      models: [],
      warning: "模型列表获取失败，请检查 API Key、Base URL 或手动输入模型名。",
    };
  }

  return (await response.json()) as ModelListResponse;
}

export async function parsePdfResume(file: File): Promise<PDFParseResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/documents/parse-pdf`, {
    method: "POST",
    body: formData,
  });
  const payload = (await response.json()) as PDFParseResponse & PDFParseError;

  if (!response.ok) {
    throw new PDFParseRequestError(
      payload.error?.code ?? "PDF_PARSE_FAILED",
      payload.error?.message ?? "PDF 解析失败。"
    );
  }

  return payload;
}
