"use client";

// S05 プラン提案・確認（02-3 教材選定 / 02-4 AI のスケジュール作成）

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { MaterialCard } from "@/components/MaterialCard";
import { Alert, Button, Card, Split } from "@/components/ui";
import { WeekCalendar } from "@/components/WeekCalendar";
import { api, fmtDate, topicColor, type Plan } from "@/lib/api";

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
  const multi = plan.topics.length > 1;
  const days = useMemo(() => {
    const map = new Map<string, { title: string; type: string; hours: number; topic: string | null; topicColor?: string }[]>();
    for (const t of plan.tasks) {
      const list = map.get(t.date) ?? [];
      list.push({
        title: t.title,
        type: t.type,
        hours: t.planned_hours,
        topic: t.topic,
        topicColor: multi && t.topic ? topicColor(plan, t.topic) : undefined,
      });
      map.set(t.date, list);
    }
    return [...map.entries()].map(([date, tasks]) => ({ date, tasks }));
  }, [plan, multi]);
  const legend = plan.topics.map((t) => ({ name: t.name, color: topicColor(plan, t.name) }));

  return (
    <>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex min-w-0 flex-col gap-2">
          <h1 className="text-2xl font-bold">{plan.topic}</h1>
          <p className="text-sm text-slate-600">
            {fmtDate(plan.start_date, false)}〜{fmtDate(plan.end_date, false)} ・ 学習できる日 {plan.availability.available_days} 日 ・ 1日
            {plan.hours_per_day}h ・ 最大 {plan.availability.max_hours}h
          </p>
          <div className="flex flex-wrap gap-2">
            {plan.topics.map((t) => (
              <span key={t.name} className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs">
                {multi && <span className={`h-2 w-2 rounded-full ${topicColor(plan, t.name)}`} />}
                <b>{t.name}</b>
                {t.kind === "exam" ? (
                  <span className="text-slate-500">
                    資格試験 ・ 試験日 {t.exam_date ? fmtDate(t.exam_date) : "―"} ・ 出題範囲 {t.areas.length} 分野
                  </span>
                ) : (
                  <span className="text-slate-500">
                    {t.purpose_label}
                    {t.purpose_note && `（${t.purpose_note}）`} ・ 目安 Lv{t.current_level}→{t.target_level}
                  </span>
                )}
              </span>
            ))}
          </div>
        </div>
        {note?.allocation && (
          <div className="flex w-full flex-col gap-1.5 lg:w-[400px] lg:shrink-0">
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
      {plan.topics
        .filter((t) => t.kind === "exam")
        .map((t) => {
          const missing = t.areas.filter((a) => a.planned_hours <= 0);
          return missing.length === 0 ? (
            <Alert key={t.name} tone="green" title={`✓ ${t.name}：出題範囲 ${t.areas.length} 分野をすべて含みます`}>
              {t.areas.map((a) => `${a.name} ${a.planned_hours}h`).join("・")}
              {t.exam_date && `。試験日（${fmtDate(t.exam_date)}）より後には予定を入れていません`}
            </Alert>
          ) : (
            <Alert key={t.name} tone="orange" title={`${t.name}：スケジュールに入っていない分野があります`}>
              {missing.map((a) => a.name).join("・")}
            </Alert>
          );
        })}
      {plan.warnings.map((w) => (
        <Alert key={w} tone="purple">{w}</Alert>
      ))}

      <div className="flex flex-col gap-4 xl:flex-row">
        <div className="flex min-w-0 flex-col gap-2.5 xl:flex-[1.1]">
          <h2 className="font-bold">おすすめ教材（{plan.materials.length}件）</h2>
          {plan.topics.map((t) => {
            const list = plan.materials.filter((m) => m.topic === t.name);
            return (
              <div key={t.name} className="flex flex-col gap-2.5">
                {multi && (
                  <h3 className="mt-1 flex items-center gap-2 text-sm font-bold text-slate-700">
                    <span className={`h-2.5 w-2.5 rounded-full ${topicColor(plan, t.name)}`} />
                    {t.name}（{list.length}件）
                  </h3>
                )}
                {list.map((m) => <MaterialCard key={m.id} m={m} />)}
              </div>
            );
          })}
          {plan.materials.some((m) => m.status !== "approved") && (
            <Alert tone="purple">
              「AI提案」の教材は、無料検索API（Tavily・Qiita・YouTube など）で集めた候補から AI が選んだもので、育成担当のレビュー前です。
            </Alert>
          )}
        </div>
        <div className="flex min-w-0 flex-col gap-3 xl:flex-1">
          <Card className="flex flex-col gap-2.5 p-4">
            <h2 className="font-bold">スケジュール</h2>
            <WeekCalendar days={days} topics={legend} />
          </Card>
          {note && (
            <Card className="flex flex-col gap-2 border-violet-200 bg-violet-50/60 p-4">
              <h2 className="font-bold text-violet-800">AI の判断 <span className="text-xs font-normal text-violet-600">（{note.provider === "demo" ? "デモ AI" : note.provider}）</span></h2>
              <div className="flex flex-col gap-1.5 text-xs leading-relaxed text-violet-950">
                {note.strategy && <span><b>単元の進め方：</b>{note.strategy}</span>}
                {multi && note.topic_allocation.length > 0 && (
                  <span>
                    <b>単元ごとの時間：</b>
                    {note.topic_allocation.map((a) => `${a.topic} ${Math.round(a.hours * 100) / 100}h`).join("・")}
                  </span>
                )}
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
