"use client";

// S02 ダッシュボード

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell, useUser } from "@/components/AppShell";
import { PlanCard } from "@/components/PlanCard";
import { TaskRow } from "@/components/TaskRow";
import { Alert, Bar, Button, Card, Kpi } from "@/components/ui";
import { api, fmtDate, type Plan, type PlanSummary } from "@/lib/api";

export default function DashboardPage() {
  return (
    <AppShell
      crumb={<b className="text-slate-900">ダッシュボード</b>}
      actions={
        <Link href="/plans/new">
          <Button>＋ 新しいプランを作る</Button>
        </Link>
      }
    >
      <Dashboard />
    </AppShell>
  );
}

function Dashboard() {
  const user = useUser();
  const [plans, setPlans] = useState<PlanSummary[] | null>(null);
  const [current, setCurrent] = useState<Plan | null>(null);

  const load = () =>
    api<PlanSummary[]>("/plans").then(async (list) => {
      setPlans(list);
      // 今日が期間内のプランを優先し、なければ確定済みで未完了のプランを表示する
      const open = list.filter((p) => p.status === "active" && p.progress.percent < 100);
      const active =
        open.find((p) => p.start_date <= p.progress.today && p.progress.today <= p.end_date) ?? open[0];
      setCurrent(active ? await api<Plan>(`/plans/${active.id}`) : null);
    });

  useEffect(() => {
    load();
  }, []);

  if (!plans) return null;
  const today = current?.progress.today ?? new Date().toISOString().slice(0, 10);
  const todays = current?.tasks.filter((t) => t.date === today) ?? [];
  const todayHours = todays.reduce((s, t) => s + t.planned_hours, 0);

  return (
    <>
      <div>
        <h1 className="text-2xl font-bold">こんにちは、{user?.name.split(" ")[0]}さん</h1>
        <p className="text-sm text-slate-600">
          {current ? `今日（${fmtDate(today)}）は ${todays.length} 件・合計 ${todayHours} 時間のタスクがあります` : "学習中のプランはありません"}
        </p>
      </div>

      {current && current.progress.delay_hours > 0 && (
        <Alert tone="orange" title={`予定より ${current.progress.delay_hours} 時間遅れています`}>
          <div className="flex items-center justify-between gap-3">
            <span>「{current.topic}」で未完了のタスクがあります。リスケすると AI が残りの期間に再配分します。</span>
            <Link href={`/plans/${current.id}?reschedule=1`}>
              <Button variant="secondary" className="h-8">AI のリスケ案を見る</Button>
            </Link>
          </div>
        </Alert>
      )}

      {current && (
        <div className="flex gap-5">
          <Kpi label={`達成率（${current.topic}）`} value={`${current.progress.percent}%`} sub={<Bar percent={current.progress.percent} />} />
          <Kpi label="学習の実績" value={`${current.progress.actual_hours}h`} sub={<span className="text-xs text-slate-500">計画 {current.progress.planned_hours}h</span>} />
          <Kpi label="終了日" value={fmtDate(current.end_date)} />
          <Kpi label="残りの予備時間" value={`${current.progress.buffer_left_hours}h`} />
        </div>
      )}

      <div className="flex gap-5">
        <Card className="flex flex-[1.4] flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="font-bold">今日のタスク</h2>
            {current && (
              <Link href={`/plans/${current.id}`} className="text-sm font-bold text-blue-600">
                プラン詳細へ
              </Link>
            )}
          </div>
          {todays.length === 0 && <p className="text-sm text-slate-500">今日のタスクはありません</p>}
          {todays.map((t) => (
            <TaskRow key={t.id} task={t} onChange={load} />
          ))}
        </Card>
        <Card className="flex flex-1 flex-col gap-2">
          <h2 className="font-bold">マイプラン</h2>
          {plans.length === 0 && (
            <p className="text-sm text-slate-500">
              まだプランがありません。<Link href="/plans/new" className="font-bold text-blue-600">新しいプランを作る</Link>
            </p>
          )}
          {plans.map((p) => (
            <PlanCard key={p.id} plan={p} />
          ))}
        </Card>
      </div>
    </>
  );
}
