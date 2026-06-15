import type { ReactNode } from "react";

export const metadata = {
  title: "CareerPilot Agent",
  description: "Evidence-grounded career application agent",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
