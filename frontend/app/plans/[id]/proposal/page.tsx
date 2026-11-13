"use client";

// S05 プラン提案・確認（02-3 教材選定 / 02-4 AI のスケジュール作成）

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { MaterialCard } from "@/components/MaterialCard";
import { Alert, Button, Card, Split } from "@/components/ui";
import { WeekCalendar } from "@/components/WeekCalendar";
import { api, fmtDate, type Plan } from "@/lib/api";

export default function ProposalPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Plan>(`/plans/${id}`).then(setPlan);
  }, [id]);

  const confirm = async () => {
    setBusy(true);
    await api(`/plans/${id}/confirm`, { method: "POST" });
    router.push(`/plans/${id}`);
  };
  const discard = async () => {
    await api(`/plans/${id}`, { method: "DELETE" });
    router.push("/plans/new");
  };

  return (
    <AppShell
      crumb={<>新しいプランを作る ／ <b className="text-slate-900">3. 提案の確認</b></>}
      actions={
        plan?.status === "proposed" && (
          <>
            <Button variant="secondary" onClick={discard}>条件を変更</Button>
            <Button onClick={confirm} disabled={busy}>このプランで確定</Button>
          </>
        )
      }
    >
      {plan && <Proposal plan={plan} />}
    </AppShell>
  );
}

function Proposal({ plan }: { plan: Plan }) {
  const note = plan.ai_note;
  const days = useMemo(() => {
    const map = new Map<string, { title: string; type: string; hours: number }[]>();
    for (const t of plan.tasks) {
      const list = map.get(t.date) ?? [];
      list.push({ title: t.title, type: t.type, hours: t.planned_hours });
      map.set(t.date, list);
    }
    return [...map.entries()].map(([date, tasks]) => ({ date, tasks }));
  }, [plan.tasks]);

  return (
    <>
      <div className="flex items-end justify-between gap-6">
        <div>
          <h1 className="text-2xl font-bold">
            {plan.topic} Lv{plan.current_level} → Lv{plan.target_level}
          </h1>
          <p className="text-sm text-slate-600">
            {fmtDate(plan.start_date, false)}〜{fmtDate(plan.end_date, false)} ・ 学習できる日 {plan.availability.available_days} 日 ・ 1日
            {plan.hours_per_day}h ・ 最大 {plan.availability.max_hours}h
          </p>
        </div>
        {note?.allocation && (
          <div className="flex w-[400px] flex-col gap-1.5">
            <span className="text-xs text-slate-500">AI が決めた配分</span>
            <Split {...note.allocation} />
          </div>
        )}
      </div>

      {note?.check_passed ? (
        <Alert tone="green" title="✓ チェック済み">
          日付（学習しない日に予定なし）・1日の時間（{plan.hours_per_day}h 以内）・合計時間（{plan.availability.max_hours}h 以内）・教材の抜け漏れを確認しました
          {note.retries > 0 && `（AI に ${note.retries} 回作り直してもらいました）`}
        </Alert>
      ) : (
        <Alert tone="orange" title="確認で問題が見つかりました">
          <ul className="list-disc pl-4">
            {note?.check_issues.map((i) => <li key={i}>{i}</li>)}
          </ul>
        </Alert>
      )}
      {plan.warnings.map((w) => (
        <Alert key={w} tone="purple">{w}</Alert>
      ))}

      <div className="flex gap-4">
        <div className="flex flex-[1.1] flex-col gap-2.5">
          <h2 className="font-bold">おすすめ教材（{plan.materials.length}件）</h2>
          {plan.materials.map((m) => <MaterialCard key={m.id} m={m} />)}
          {plan.materials.some((m) => m.status !== "approved") && (
            <Alert tone="purple">
              「AI提案」の教材は、無料検索API（Tavily・Qiita・YouTube など）で集めた候補から AI が選んだもので、育成担当のレビュー前です。
            </Alert>
          )}
        </div>
        <div className="flex flex-1 flex-col gap-3">
          <Card className="flex flex-col gap-2.5 p-4">
            <h2 className="font-bold">スケジュール</h2>
            <WeekCalendar days={days} />
          </Card>
          {note && (
            <Card className="flex flex-col gap-2 border-violet-200 bg-violet-50/60 p-4">
              <h2 className="font-bold text-violet-800">AI の判断 <span className="text-xs font-normal text-violet-600">（{note.provider === "demo" ? "デモ AI" : note.provider}）</span></h2>
              <div className="flex flex-col gap-1.5 text-xs leading-relaxed text-violet-950">
                <span><b>学ぶ順番：</b>{note.order_reason}</span>
                <span><b>重点：</b>{note.focus}</span>
                {note.dropped.length > 0 && (
                  <span>
                    <b>後回し・対象外：</b>
                    {note.dropped.map((d) => `${d.title}（${d.reason}）`).join("、")}
                  </span>
                )}
                {note.allocation && <span><b>予備：</b>{note.allocation.buffer}h（遅れたときのリスケ用）</span>}
              </div>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
