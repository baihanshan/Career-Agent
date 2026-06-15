import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const requiredPaths = [
  "app/page.tsx",
  "app/layout.tsx",
  "components/EvidenceTable.tsx",
  "components/JobDescriptionInput.tsx",
  "components/ProfileInput.tsx",
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
const requiredCopy = [
  "个人材料",
  "目标岗位 JD",
  "开始分析",
  "匹配总结",
  "证据表",
  "风险提示",
];
const missingCopy = requiredCopy.filter((copy) => !page.includes(copy));

if (missingCopy.length > 0) {
  console.error(`Missing Chinese UI copy: ${missingCopy.join(", ")}`);
  process.exit(1);
}

console.log("Frontend structure and Chinese UI copy look ready.");
