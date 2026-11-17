"use client";

import { useState } from "react";

import { Badge } from "@/components/ui";
import { api, TASK_LABEL, type Task } from "@/lib/api";

const TONE = { learn: "blue", review: "green", exercise: "purple", video: "purple", buffer: "gray" } as const;

export function TaskRow({ task, onChange }: { task: Task; onChange?: () => void }) {
  const [busy, setBusy] = useState(false);
  const done = task.status === "done";
  const toggle = async () => {
    setBusy(true);
    await api(`/tasks/${task.id}`, {
      method: "PATCH",
      // チェック＝予定どおり完了（実績＝計画）。取り消すと実績も消える
      body: JSON.stringify({ status: done ? "todo" : "done" }),
    });
    setBusy(false);
    onChange?.();
  };
  return (
    <div className="flex items-center gap-3.5 rounded-xl border border-slate-200 bg-white px-3.5 py-3">
      <button
        aria-label={done ? "未完了に戻す" : "完了にする"}
        disabled={busy || task.type === "buffer"}
        onClick={toggle}
        className={`h-[18px] w-[18px] shrink-0 rounded-[5px] border-2 ${done ? "border-blue-600 bg-blue-600" : "border-slate-400 bg-white"} disabled:opacity-40`}
      />
      <div className="min-w-0 flex-1">
        <div className={`text-sm font-bold ${done ? "text-slate-400 line-through" : ""}`}>{task.title}</div>
      </div>
      <Badge tone={TONE[task.type]}>{TASK_LABEL[task.type]}</Badge>
      <span className="text-xs text-slate-500">{task.planned_hours}h</span>
    </div>
  );
}
