"use client";

import type { ChangeEvent } from "react";
import { useState } from "react";

import { parsePdfResume, PDFParseRequestError } from "../lib/api";
import type { PDFParseResponse } from "../lib/types";

interface ProfileInputProps {
  value: string;
  onChange: (value: string) => void;
  onPdfParsed: (result: PDFParseResponse) => void;
}

const MAX_PDF_BYTES = 10 * 1024 * 1024;
const PDF_ERROR_MESSAGES: Record<string, string> = {
  PDF_INVALID_TYPE: "仅支持 PDF 文件。",
  PDF_TOO_LARGE: "PDF 文件不能超过 10 MB。",
  PDF_EMPTY: "PDF 文件为空。",
  PDF_ENCRYPTED: "PDF 已加密，请先移除密码。",
  PDF_CORRUPT: "PDF 已损坏或无法读取。",
  PDF_NO_TEXT: "未提取到文字，请使用文字型 PDF 或粘贴文本。",
};

export function ProfileInput({ value, onChange, onPdfParsed }: ProfileInputProps) {
  const [isParsing, setIsParsing] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState("");

  async function handlePdfUpload(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) {
      return;
    }

    setUploadMessage("");
    setUploadError("");
    if (!file.name.toLowerCase().endsWith(".pdf") || file.type !== "application/pdf") {
      setUploadError(PDF_ERROR_MESSAGES.PDF_INVALID_TYPE);
      input.value = "";
      return;
    }
    if (file.size > MAX_PDF_BYTES) {
      setUploadError(PDF_ERROR_MESSAGES.PDF_TOO_LARGE);
      input.value = "";
      return;
    }

    setIsParsing(true);
    try {
      const result = await parsePdfResume(file);
      onPdfParsed(result);
      setUploadMessage(`已解析 ${result.source_name}（${result.page_count} 页），可继续编辑。`);
    } catch (error) {
      const code = error instanceof PDFParseRequestError ? error.code : "PDF_PARSE_FAILED";
      setUploadError(PDF_ERROR_MESSAGES[code] ?? "PDF 解析失败，请稍后重试。");
    } finally {
      setIsParsing(false);
      input.value = "";
    }
  }

  return (
    <label className="field">
      <span>个人材料</span>
      <input
        type="file"
        accept="application/pdf,.pdf"
        onChange={handlePdfUpload}
        disabled={isParsing}
      />
      {isParsing ? <small>正在解析 PDF…</small> : null}
      {uploadMessage ? <small role="status">{uploadMessage}</small> : null}
      {uploadError ? <small role="alert">{uploadError}</small> : null}
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="粘贴简历、项目经历、课程笔记或 Markdown 材料"
        rows={12}
      />
    </label>
  );
}
