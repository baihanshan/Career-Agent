import type { ReactNode } from "react";

import "./globals.css";

export const metadata = {
  title: "CareerPilot Agent",
  description: "证据支撑的求职内容生成 Agent",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
