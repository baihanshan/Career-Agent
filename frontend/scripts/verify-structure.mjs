import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const requiredPaths = [
  "app/page.tsx",
  "app/layout.tsx",
  "components/JobDescriptionInput.tsx",
  "components/ProfileInput.tsx",
  "components/ProcessingWarnings.tsx",
  "components/ResultView.tsx",
  "components/RiskWarnings.tsx",
  "components/RunStatus.tsx",
  "lib/api.ts",
  "tsconfig.json",
  "package.json",
];

const missing = requiredPaths.filter((path) => !existsSync(join(process.cwd(), path)));

if (missing.length > 0) {
  console.error(`Missing frontend files: ${missing.join(", ")}`);
  process.exit(1);
}

const page = readFileSync(join(process.cwd(), "app/page.tsx"), "utf8");
const profileInput = readFileSync(join(process.cwd(), "components/ProfileInput.tsx"), "utf8");
const api = readFileSync(join(process.cwd(), "lib/api.ts"), "utf8");
const requiredCopy = [
  "个人材料",
  "目标岗位 JD",
  "开始分析",
  "匹配总结",
  "风险提示",
  "流程警告",
];
const missingCopy = requiredCopy.filter((copy) => !page.includes(copy));

if (missingCopy.length > 0) {
  console.error(`Missing Chinese UI copy: ${missingCopy.join(", ")}`);
  process.exit(1);
}

const resultView = readFileSync(join(process.cwd(), "components/ResultView.tsx"), "utf8");
const riskWarnings = readFileSync(join(process.cwd(), "components/RiskWarnings.tsx"), "utf8");
const requiredResultLabels = ["低风险", "中风险", "高风险"];
const missingResultLabels = requiredResultLabels.filter((copy) => !resultView.includes(copy));
const requiredWarningLabels = ["低严重程度", "中严重程度", "高严重程度"];
const missingWarningLabels = requiredWarningLabels.filter((copy) => !riskWarnings.includes(copy));

if (missingResultLabels.length > 0 || missingWarningLabels.length > 0) {
  console.error(
    `Missing Chinese enum labels: ${[
      ...missingResultLabels,
      ...missingWarningLabels,
    ].join(", ")}`
  );
  process.exit(1);
}

if (riskWarnings.includes("未覆盖要求：{gap.requirement_id}")) {
  console.error("Risk warnings must show user-readable requirement text, not internal IDs.");
  process.exit(1);
}

if (riskWarnings.includes("warning.asset_id") || riskWarnings.includes("gap.requirement_id")) {
  console.error("Risk warning keys must not depend on internal IDs.");
  process.exit(1);
}

const outputOrder = ["匹配总结", "简历要点", "面试准备", "<RiskWarnings", "<AgentTraceDetails"];
const outputPositions = outputOrder.map((label) => resultView.indexOf(label));
if (
  outputPositions.some((position) => position < 0) ||
  outputPositions.some((position, index) => index > 0 && position <= outputPositions[index - 1])
) {
  console.error(`Result modules must appear in order: ${outputOrder.join(" -> ")}`);
  process.exit(1);
}

if (resultView.includes("bullet.evidence_ids")) {
  console.error("Resume bullets must not render internal evidence IDs.");
  process.exit(1);
}

if (!resultView.includes("resume_bullets.slice(0, 3)")) {
  console.error("Resume bullet output must be limited to 3 items.");
  process.exit(1);
}

if (!riskWarnings.includes("riskReport.risks.slice(0, 3)")) {
  console.error("Risk output must be limited to 3 items.");
  process.exit(1);
}

if (!resultView.includes("<details") || resultView.includes("<details open")) {
  console.error("Agent trace must use a collapsed details element by default.");
  process.exit(1);
}

if (
  resultView.includes("key={item.question}") ||
  resultView.includes("item.supporting_evidence_ids") ||
  !resultView.includes('key={`${title}-${questionIndex}`}')
) {
  console.error("Interview question keys must not depend on internal evidence IDs.");
  process.exit(1);
}

if (
  resultView.includes('trace.steps.map((step) =>') ||
  resultView.includes('key={`${step.tool_name}-${step.arguments_summary}`}')
) {
  console.error("Agent trace step keys must include the step index to avoid duplicate React keys.");
  process.exit(1);
}

if (
  riskWarnings.includes('key={`${risk.risk_type}-${risk.title}`}') ||
  !riskWarnings.includes(
    'key={`${risk.risk_type}-${risk.title}-${risk.jd_requirement_summary}`}'
  )
) {
  console.error("Risk keys must distinguish identical titles for different JD requirements.");
  process.exit(1);
}

if (page.includes("response.error?.message") || page.includes("response.error?.details")) {
  console.error("Error UI must map internal workflow errors to controlled user-facing copy.");
  process.exit(1);
}

if (
  !page.includes("LLM_PROVIDER_TIMEOUT") ||
  !page.includes("模型响应超时，请稍后重试或更换模型。")
) {
  console.error("Provider timeouts must have controlled, accurate user-facing copy.");
  process.exit(1);
}

const reactErrorMessages = [
  ["REACT_MODEL_UNAVAILABLE", "当前模型不支持智能体工具调用，请更换模型。"],
  ["REACT_TOOL_CALL_ERROR", "模型工具调用失败，请稍后重试或更换模型。"],
  ["REACT_OUTPUT_PARSE_ERROR", "模型未生成有效的结构化结果，请重试或更换模型。"],
  ["REACT_QUALITY_GATE_FAILED", "生成结果未通过质量校验，请重新分析。"],
  ["REACT_EVIDENCE_VIOLATION", "生成结果引用了无效证据，系统已阻止展示。"],
];
const missingReactErrors = reactErrorMessages.filter(
  ([code, message]) => !page.includes(code) || !page.includes(message)
);
if (missingReactErrors.length > 0) {
  console.error(
    `ReAct failures must have controlled user-facing copy: ${missingReactErrors
      .map(([code]) => code)
      .join(", ")}`
  );
  process.exit(1);
}

const uiSourceFiles = ["app", "components"].flatMap((directory) =>
  readdirSync(join(process.cwd(), directory), { recursive: true })
    .filter((path) => /\.(?:ts|tsx)$/.test(path))
    .map((path) => join(process.cwd(), directory, path))
);
const internalUiFieldPattern =
  /\b(?:evidence_ids?|supporting_evidence_ids?|requirement_ids?|chunk_ids?|experience_ids?|internal_supporting_evidence_ids?)\b/;
const internalFieldReaders = uiSourceFiles.filter((path) =>
  internalUiFieldPattern.test(readFileSync(path, "utf8"))
);

if (internalFieldReaders.length > 0) {
  console.error(
    `UI source must not read or render internal reference fields: ${internalFieldReaders.join(", ")}`
  );
  process.exit(1);
}

const pdfUploadMarkers = [
  'accept="application/pdf,.pdf"',
  "正在解析 PDF",
  "PDF_NO_TEXT",
];
const missingPdfMarkers = pdfUploadMarkers.filter(
  (marker) => !profileInput.includes(marker)
);

if (missingPdfMarkers.length > 0 || !api.includes("parsePdfResume")) {
  console.error(`Missing PDF upload behavior: ${missingPdfMarkers.join(", ")}`);
  process.exit(1);
}

const llmSettings = readFileSync(join(process.cwd(), "components/LlmSettings.tsx"), "utf8");
const modelListMarkers = [
  "listModels",
  "获取模型列表",
  "<datalist",
  "模型可下拉选择，也可以手动输入。",
];
const missingModelListMarkers = modelListMarkers.filter(
  (marker) => !llmSettings.includes(marker)
);

if (
  missingModelListMarkers.length > 0 ||
  !api.includes("/models/list") ||
  !api.includes("ModelListResponse")
) {
  console.error(`Missing model list combo-box behavior: ${missingModelListMarkers.join(", ")}`);
  process.exit(1);
}

console.log("Frontend structure and Chinese UI copy look ready.");
