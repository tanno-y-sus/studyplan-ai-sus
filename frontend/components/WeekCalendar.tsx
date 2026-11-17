"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Legend } from "@/components/ui";
import { fmtDate } from "@/lib/api";

interface CalTask {
  title: string;
  type: string;
  hours: number;
  done?: boolean;
  /** 複数単元のプランで、どの単元かを表す色（例：bg-sky-500） */
  topicColor?: string;
  topic?: string | null;
}

const CHIP: Record<string, string> = {
  learn: "border-l-blue-600 bg-blue-50 text-blue-900",
  review: "border-l-green-700 bg-green-50 text-green-900",
  exercise: "border-l-violet-600 bg-violet-50 text-violet-900",
  video: "border-l-violet-600 bg-violet-50 text-violet-900",
  buffer: "border-l-slate-400 bg-slate-100 text-slate-700",
};
const TYPE_NAME: Record<string, string> = { learn: "学習", review: "復習", exercise: "演習", video: "動画", buffer: "予備" };

const PER_PAGE = 5;
/** この幅（px）より狭いときは、日付ごとの縦リストで表示する */
const LIST_BELOW = 640;

type Mode = "auto" | "calendar" | "list";

/** 予定のある日を5日ずつ表示する。幅が狭いときは日付ごとのリストに切り替える */
export function WeekCalendar({ days, topics }: { days: { date: string; tasks: CalTask[] }[]; topics?: { name: string; color: string }[] }) {
  const sorted = useMemo(() => [...days].sort((a, b) => a.date.localeCompare(b.date)), [days]);
  const [page, setPage] = useState(0);
  const [mode, setMode] = useState<Mode>("auto");
  const [narrow, setNarrow] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setNarrow(entry.contentRect.width < LIST_BELOW));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const list = mode === "list" || (mode === "auto" && narrow);
  const pages = Math.max(1, Math.ceil(sorted.length / PER_PAGE));
  const current = Math.min(page, pages - 1);
  const view = sorted.slice(current * PER_PAGE, current * PER_PAGE + PER_PAGE);

  return (
    <div ref={ref} className="flex min-w-0 flex-col gap-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <div className="flex items-center gap-1">
          <button disabled={current === 0} onClick={() => setPage(current - 1)} className="whitespace-nowrap px-2 py-1 disabled:opacity-30">
            ◀ 前へ
          </button>
          <span className="whitespace-nowrap">
            {view[0] && `${fmtDate(view[0].date, false)}〜${fmtDate(view[view.length - 1].date, false)}`}（{current + 1}/{pages}）
          </span>
          <button disabled={current >= pages - 1} onClick={() => setPage(current + 1)} className="whitespace-nowrap px-2 py-1 disabled:opacity-30">
            次へ ▶
          </button>
        </div>
        <div className="flex overflow-hidden rounded-lg border border-slate-200" role="group" aria-label="表示の切り替え">
          {(["calendar", "list"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              aria-pressed={(m === "list") === list}
              className={`px-2.5 py-1 ${(m === "list") === list ? "bg-slate-800 text-white" : "bg-white text-slate-600"}`}
            >
              {m === "calendar" ? "カレンダー" : "リスト"}
            </button>
          ))}
        </div>
      </div>

      {list ? (
        <div className="flex flex-col gap-2">
          {view.map((d) => {
            const total = d.tasks.reduce((s, t) => s + t.hours, 0);
            return (
              <div key={d.date} className="rounded-lg border border-slate-200 bg-white">
                <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2 text-xs">
                  <b className="text-slate-700">{fmtDate(d.date)}</b>
                  <span className="text-slate-500">合計 {Math.round(total * 100) / 100}h</span>
                </div>
                <ul className="flex flex-col">
                  {d.tasks.map((t, i) => (
                    <li
                      key={i}
                      className={`flex items-center gap-2 border-l-[3px] px-3 py-2 text-sm ${CHIP[t.type] ?? CHIP.learn} ${t.done ? "opacity-50" : ""}`}
                    >
                      {t.topicColor && <span className={`h-2 w-2 shrink-0 rounded-full ${t.topicColor}`} title={t.topic ?? undefined} />}
                      <span className={`min-w-0 flex-1 break-words ${t.done ? "line-through" : ""}`}>{t.title}</span>
                      <span className="shrink-0 text-[11px] text-slate-500">{TYPE_NAME[t.type] ?? t.type}</span>
                      <span className="w-10 shrink-0 text-right text-xs font-bold">{t.hours}h</span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="grid grid-cols-5 gap-2">
          {view.map((d) => (
            <div key={d.date} className="flex min-h-[120px] min-w-0 flex-col gap-1.5 rounded-lg border border-slate-200 bg-white p-2">
              <span className="text-xs font-bold text-slate-600">{fmtDate(d.date)}</span>
              {d.tasks.map((t, i) => (
                <span
                  key={i}
                  className={`flex gap-1 break-words rounded-md border-l-[3px] px-1.5 py-1 text-[11px] leading-snug ${CHIP[t.type] ?? CHIP.learn} ${t.done ? "opacity-50 line-through" : ""}`}
                >
                  {t.topicColor && <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${t.topicColor}`} />}
                  <span className="min-w-0">
                    {t.title} {t.hours}h
                  </span>
                </span>
              ))}
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
        <Legend color="bg-blue-600">学習</Legend>
        <Legend color="bg-green-700">復習</Legend>
        <Legend color="bg-violet-600">動画・演習</Legend>
        <Legend color="bg-slate-400">予備</Legend>
        {topics && topics.length > 1 &&
          topics.map((t) => (
            <span key={t.name} className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${t.color}`} />
              {t.name}
            </span>
          ))}
      </div>
    </div>
  );
}
