import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "StudyPlan AI",
  description: "待機期間を、計画的な学習期間に。学びたい技術を入力すると、教材と日別スケジュールを AI が提案します。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ja">
      <body className="antialiased">{children}</body>
    </html>
  );
}
