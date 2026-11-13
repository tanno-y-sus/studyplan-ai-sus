"use client";

import { useMemo, useState } from "react";

import { Legend } from "@/components/ui";
import { fmtDate } from "@/lib/api";

interface CalTask {
  title: string;
  type: string;
  hours: number;
  done?: boolean;
}

const CHIP: Record<string, string> = {
  learn: "border-l-blue-600 bg-blue-50 text-blue-900",
  review: "border-l-green-700 bg-green-50 text-green-900",
  exercise: "border-l-violet-600 bg-violet-50 text-violet-900",
  video: "border-l-violet-600 bg-violet-50 text-violet-900",
  buffer: "border-l-slate-400 bg-slate-100 text-slate-700",
};

/** 予定のある日を5日ずつ表示する週カレンダー */
export function WeekCalendar({ days }: { days: { date: string; tasks: CalTask[] }[] }) {
  const sorted = useMemo(() => [...days].sort((a, b) => a.date.localeCompare(b.date)), [days]);
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(sorted.length / 5));
  const view = sorted.slice(page * 5, page * 5 + 5);
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between text-xs text-slate-500">
        <button disabled={page === 0} onClick={() => setPage(page - 1)} className="px-2 disabled:opacity-30">◀ 前へ</button>
        <span>
          {view[0] && `${fmtDate(view[0].date, false)}〜${fmtDate(view[view.length - 1].date, false)}`}（{page + 1}/{pages}）
        </span>
        <button disabled={page >= pages - 1} onClick={() => setPage(page + 1)} className="px-2 disabled:opacity-30">次へ ▶</button>
      </div>
      <div className="grid grid-cols-5 gap-2">
        {view.map((d) => (
          <div key={d.date} className="flex min-h-[120px] flex-col gap-1.5 rounded-lg border border-slate-200 bg-white p-2">
            <span className="text-xs font-bold text-slate-600">{fmtDate(d.date)}</span>
            {d.tasks.map((t, i) => (
              <span key={i} className={`rounded-md border-l-[3px] px-1.5 py-1 text-[11px] leading-snug ${CHIP[t.type] ?? CHIP.learn} ${t.done ? "opacity-50 line-through" : ""}`}>
                {t.title} {t.hours}h
              </span>
            ))}
          </div>
        ))}
      </div>
      <div className="flex gap-4 text-xs text-slate-600">
        <Legend color="bg-blue-600">学習</Legend>
        <Legend color="bg-green-700">復習</Legend>
        <Legend color="bg-violet-600">動画・演習</Legend>
        <Legend color="bg-slate-400">予備</Legend>
      </div>
    </div>
  );
}
