"use client";

// 今どの AI でプランを作るかの表示（S03・S08）。設定はバックエンドの .env（AI_PROVIDER・GEMINI_API_KEY）

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui";
import { api, type AIStatus } from "@/lib/api";

const SEARCH_NAME: Record<string, string> = { demo: "デモ", tavily: "Tavily", qiita: "Qiita", youtube: "YouTube" };

export function AIStatusNote({ detail = false }: { detail?: boolean }) {
  const [status, setStatus] = useState<AIStatus | null>(null);

  useEffect(() => {
    api<AIStatus>("/ai/status")
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  if (!status) return null;
  const gemini = status.provider === "gemini";
  const demoSearch = status.search.includes("demo");
  return (
    <div className="flex flex-col gap-1 text-xs text-slate-600">
      <div className="flex items-center gap-2">
        <span>使用中の AI</span>
        <Badge tone={gemini ? "purple" : "gray"}>{gemini ? `Gemini（${status.model}）` : "デモ AI"}</Badge>
        {gemini && status.daily_limit !== null && (
          <span className="text-slate-500">
            今日 {status.today_count ?? 0} / {status.daily_limit} 回
          </span>
        )}
      </div>
      {(detail || status.provider !== status.configured) && <span className="text-[11px] text-slate-500">{status.reason}</span>}
      <div className="flex flex-wrap items-center gap-2">
        <span>教材の検索</span>
        {status.search.map((s) => (
          <Badge key={s} tone={s === "demo" ? "orange" : "blue"}>
            {SEARCH_NAME[s] ?? s}
          </Badge>
        ))}
      </div>
      {demoSearch && (
        <span className="text-[11px] text-orange-700">
          デモ検索の教材は実在しない URL（example.com）です。.env の SEARCH_PROVIDERS で本物の検索に切り替えられます
        </span>
      )}
      {detail && status.search_missing.map((m) => <span key={m} className="text-[11px] text-slate-500">使えない検索：{m}</span>)}
    </div>
  );
}
