import { existsSync } from "node:fs";
import { join } from "node:path";

const requiredPaths = [
  "app/page.tsx",
  "app/layout.tsx",
  "tsconfig.json",
  "package.json",
];

const missing = requiredPaths.filter((path) => !existsSync(join(process.cwd(), path)));

if (missing.length > 0) {
  console.error(`Missing frontend files: ${missing.join(", ")}`);
  process.exit(1);
}

console.log("Frontend structure looks ready.");
