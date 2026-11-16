"use client";

// 今どの AI でプランを作るかの表示（S03・S08）。設定はバックエンドの .env（AI_PROVIDER・GEMINI_API_KEY）

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui";
import { api, type AIStatus } from "@/lib/api";

export function AIStatusNote({ detail = false }: { detail?: boolean }) {
  const [status, setStatus] = useState<AIStatus | null>(null);

  useEffect(() => {
    api<AIStatus>("/ai/status")
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  if (!status) return null;
  const gemini = status.provider === "gemini";
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
    </div>
  );
}
