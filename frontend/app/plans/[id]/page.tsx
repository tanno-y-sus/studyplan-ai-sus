"use client";

// S06 プラン詳細・進捗（02-6 進捗管理・AI のリスケ）

import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { MaterialCard } from "@/components/MaterialCard";
import { Alert, Badge, Bar, Button, Card, Kpi, Legend, Spinner } from "@/components/ui";
import { api, fmtDate, TASK_LABEL, topicColor, type Plan, type ReschedulePreview, type Task, type TaskUpdateResult } from "@/lib/api";

const TONE = { learn: "blue", review: "green", exercise: "purple", video: "purple", buffer: "gray" } as const;

export default function PlanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [preview, setPreview] = useState<ReschedulePreview | null>(null);
  const [reason, setReason] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const load = useCallback(() => api<Plan>(`/plans/${id}`).then(setPlan), [id]);

  const openReschedule = useCallback(
    async (why: string | null = null) => {
      setLoadingPreview(true);
      setReason(why);
      try {
        setPreview(await api<ReschedulePreview>(`/plans/${id}/reschedule/preview`, { method: "POST", body: "{}" }));
      } finally {
        setLoadingPreview(false);
      }
    },
    [id],
  );

  // 実績が予定より少なかったとき：残りのタスクを入れたリスケ案を自動で作り、確認してもらう
  const onTaskUpdated = useCallback(
    async (result: TaskUpdateResult) => {
      await load();
      if (result.remainder) {
        await openReschedule(
          `「${result.task.title}」の実績が予定より ${result.shortfall_hours}h 少なかったため、残り ${result.shortfall_hours}h を「${result.remainder.title}」として、AI が今後の予定に組み直す案を作りました。`,
        );
      }
    },
    [load, openReschedule],
  );

  useEffect(() => {
    load();
    if (typeof window !== "undefined" && new URLSearchParams(window.location.search).get("reschedule")) openReschedule();
  }, [load, openReschedule]);

  const apply = async () => {
    if (!preview) return;
    const updated = await api<Plan>(`/plans/${id}/reschedule/apply`, { method: "POST", body: JSON.stringify(preview) });
    setPlan(updated);
    setPreview(null);
  };

  return (
    <AppShell
      crumb={<>マイプラン ／ <b className="text-slate-900">{plan?.topic}</b></>}
      actions={
        <Button onClick={() => openReschedule()} disabled={loadingPreview}>
          {loadingPreview ? "AI が組み直しています…" : "リスケする"}
        </Button>
      }
    >
      {plan && <Detail plan={plan} onTaskUpdated={onTaskUpdated} />}
      {preview && <RescheduleModal preview={preview} reason={reason} onClose={() => setPreview(null)} onApply={apply} />}
    </AppShell>
  );
}

function Detail({ plan, onTaskUpdated }: { plan: Plan; onTaskUpdated: (r: TaskUpdateResult) => void }) {
  const p = plan.progress;
  const multi = plan.topics.length > 1;
  return (
    <>
      <div className="grid grid-cols-2 gap-3 lg:flex lg:gap-5">
        <Kpi label="達成率" value={`${p.percent}%`} sub={<Bar percent={p.percent} />} />
        <Kpi label="実績 / 計画" value={<>{p.actual_hours}h <span className="text-xs text-slate-500">/ {p.planned_hours}h</span></>} />
        <Kpi label="遅れ（今日まで）" value={`${p.delay_hours}h`} tone={p.delay_hours > 0 ? "text-orange-700" : ""} />
        <Kpi label="残りの予備時間" value={`${p.buffer_left_hours}h`} />
      </div>
      {(multi || plan.topics.some((t) => t.kind === "exam")) && (
        <Card className="flex flex-col gap-3">
          <h2 className="font-bold">単元ごとの進み具合</h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {plan.topics.map((t) => (
              <div key={t.name} className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span className="flex items-center gap-1.5 font-bold">
                    <span className={`h-2.5 w-2.5 rounded-full ${topicColor(plan, t.name)}`} />
                    {t.name}
                  </span>
                  <span className="text-xs text-slate-500">
                    {t.percent}%（{t.done_hours}h / {t.planned_hours}h）
                  </span>
                </div>
                <Bar percent={t.percent} />
                {t.kind === "exam" && (
                  <div className="mt-1 flex flex-col gap-1 rounded-lg bg-slate-50 p-2">
                    <span className="text-[11px] text-slate-500">
                      試験日 {t.exam_date ? fmtDate(t.exam_date) : "―"} ・ 分野ごと
                    </span>
                    {t.areas.map((a) => {
                      const pct = a.planned_hours ? Math.round((a.done_hours / a.planned_hours) * 100) : 0;
                      return (
                        <div key={a.name} className="flex items-center gap-2 text-[11px]">
                          <span className="min-w-0 flex-1 truncate" title={a.name}>{a.name}</span>
                          <span className="w-16 shrink-0"><Bar percent={pct} color={pct >= 100 ? "bg-green-700" : "bg-blue-600"} /></span>
                          <span className="w-8 shrink-0 text-right text-slate-500">{pct}%</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
      <div className="flex flex-col gap-5 xl:flex-row">
        <Card className="flex min-w-0 flex-col gap-3 xl:flex-[1.3]">
          <h2 className="font-bold">タスク一覧</h2>
          <p className="text-xs text-slate-500">
            チェック＝予定どおり終わった。実績を入れると、その時間で完了になります（予定より少ないときは、残りを組み直す案を出します）
          </p>
          <TaskTable plan={plan} today={p.today} onUpdated={onTaskUpdated} />
        </Card>
        <div className="flex min-w-0 flex-col gap-5 xl:flex-1">
          <Card className="flex flex-col gap-3">
            <h2 className="font-bold">計画と実績（累計時間）</h2>
            <ProgressChart tasks={plan.tasks} today={p.today} />
          </Card>
          <Card className="flex flex-col gap-2.5">
            <h2 className="font-bold">教材</h2>
            {plan.materials.map((m) => <MaterialCard key={m.id} m={m} />)}
          </Card>
        </div>
      </div>
    </>
  );
}

function TaskTable({ plan, today, onUpdated }: { plan: Plan; today: string; onUpdated: (r: TaskUpdateResult) => void }) {
  const [error, setError] = useState<string | null>(null);
  const multi = plan.topics.length > 1;
  const update = async (t: Task, body: object) => {
    setError(null);
    try {
      onUpdated(await api<TaskUpdateResult>(`/tasks/${t.id}`, { method: "PATCH", body: JSON.stringify(body) }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存できませんでした");
    }
  };
  const commitActual = (t: Task, raw: string) => {
    const value = raw === "" ? 0 : Number(raw);
    if (Number.isNaN(value) || value === (t.actual_hours ?? 0)) return;
    update(t, { actual_hours: value });
  };
  return (
    <div className="flex flex-col gap-2">
      {error && <Alert tone="red">{error}</Alert>}
      <div className="max-h-[640px] overflow-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="sticky top-0 z-[1] bg-slate-50 text-left text-xs text-slate-500">
            <tr>
              <th className="px-3 py-2.5" />
              <th className="px-3 py-2.5">日付</th>
              <th className="px-3 py-2.5">タスク</th>
              <th className="px-3 py-2.5">種類</th>
              <th className="px-3 py-2.5">計画</th>
              <th className="px-3 py-2.5">実績</th>
              <th className="px-3 py-2.5">メモ</th>
            </tr>
          </thead>
          <tbody>
            {plan.tasks.map((t) => {
              const done = t.status === "done";
              const late = t.status === "todo" && t.date < today && t.type !== "buffer";
              return (
                <tr key={t.id} className={`border-b border-slate-100 ${late ? "bg-orange-50" : ""}`}>
                  <td className="px-3 py-2.5">
                    <button
                      aria-label={done ? "未完了に戻す" : "予定どおり完了"}
                      title={done ? "未完了に戻す（実績も消えます）" : "予定どおり完了（実績＝計画）"}
                      disabled={t.type === "buffer"}
                      onClick={() => update(t, { status: done ? "todo" : "done" })}
                      className={`inline-block h-[18px] w-[18px] rounded-[5px] border-2 ${done ? "border-blue-600 bg-blue-600" : "border-slate-400 bg-white"} disabled:opacity-30`}
                    />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">{fmtDate(t.date)}</td>
                  <td className={`px-3 py-2.5 ${done ? "text-slate-400 line-through" : ""}`}>
                    <span className="flex items-center gap-1.5">
                      {multi && t.topic && <span className={`h-2 w-2 shrink-0 rounded-full ${topicColor(plan, t.topic)}`} title={t.topic} />}
                      <span>
                        {t.title}
                        {t.area && t.area !== t.title && <span className="block text-[11px] text-slate-500">分野：{t.area}</span>}
                      </span>
                    </span>
                  </td>
                  <td className="px-3 py-2.5"><Badge tone={TONE[t.type]}>{TASK_LABEL[t.type]}</Badge></td>
                  <td className="px-3 py-2.5">{t.planned_hours}h</td>
                  <td className="px-3 py-2.5">
                    {t.type !== "buffer" && (
                      <input
                        // 保存後の値で入力欄を作り直す（表示と保存した値がずれないように）
                        key={`${t.id}-${t.actual_hours ?? ""}`}
                        type="number"
                        step={0.25}
                        min={0}
                        aria-label={`${t.title} の実績（時間）`}
                        defaultValue={t.actual_hours ?? ""}
                        onBlur={(e) => commitActual(t, e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
                        className="h-8 w-16 rounded border border-slate-300 px-1.5"
                      />
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    {late ? <Badge tone="orange">未完了</Badge> : (
                      t.type !== "buffer" && (
                        <input
                          defaultValue={t.memo ?? ""}
                          onBlur={(e) => e.target.value !== (t.memo ?? "") && update(t, { memo: e.target.value })}
                          placeholder="メモ"
                          className="h-8 w-28 rounded border border-slate-200 px-1.5 text-xs"
                        />
                      )
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ProgressChart({ tasks, today }: { tasks: Task[]; today: string }) {
  const { plan, actual, max } = useMemo(() => {
    const dates = [...new Set(tasks.map((t) => t.date))].sort();
    let p = 0;
    let a = 0;
    const plan: number[] = [];
    const actual: number[] = [];
    for (const d of dates) {
      for (const t of tasks.filter((x) => x.date === d && x.type !== "buffer")) {
        p += t.planned_hours;
        if (t.status === "done") a += t.actual_hours ?? t.planned_hours;
      }
      plan.push(p);
      if (d <= today) actual.push(a);
    }
    return { plan, actual, max: Math.max(p, a, 1) };
  }, [tasks, today]);
  const W = 400;
  const H = 220;
  const pts = (arr: number[]) =>
    arr.map((v, i) => `${(i / Math.max(1, plan.length - 1)) * W},${H - (v / max) * (H - 10)}`).join(" ");
  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-56 w-full border-b border-l border-slate-200" preserveAspectRatio="none">
        <polyline points={pts(plan)} fill="none" stroke="#9CA3AF" strokeWidth={2} strokeDasharray="6 4" />
        <polyline points={pts(actual)} fill="none" stroke="#2563EB" strokeWidth={3} />
      </svg>
      <div className="flex gap-4 text-xs text-slate-600">
        <Legend color="bg-slate-400">計画</Legend>
        <Legend color="bg-blue-600">実績</Legend>
      </div>
    </>
  );
}

function RescheduleModal({
  preview,
  reason,
  onClose,
  onApply,
}: {
  preview: ReschedulePreview;
  reason: string | null;
  onClose: () => void;
  onApply: () => void;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-slate-900/45 p-4">
      <div className="flex max-h-[90vh] w-full max-w-[620px] flex-col gap-4 overflow-auto rounded-2xl bg-white p-6 shadow-2xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">AI のリスケ案</h2>
          <button onClick={onClose} className="text-slate-400" aria-label="閉じる">✕</button>
        </div>
        {reason && (
          <Alert tone="blue" title="実績が予定より少なかったため">
            {reason}「キャンセル」した場合、残りのタスクは元の日付に未完了のまま残ります（あとから「リスケする」で組み直せます）。
          </Alert>
        )}
        <p className="text-sm text-slate-600">
          未完了のタスク {preview.pending_hours}h を、AI が {fmtDate(preview.today)} 以降の学習できる日（{preview.remaining_days}日）に再配分しました。
        </p>
        {preview.check_passed ? (
          <Alert tone="green" title="✓ チェック済み">日付・1日の時間・合計時間を確認しました</Alert>
        ) : (
          <Alert tone="orange" title="確認で問題が見つかりました">{preview.check_issues.join(" / ")}</Alert>
        )}
        {preview.changes.length === 0 ? (
          <p className="text-sm text-slate-500">日付が変わるタスクはありません</p>
        ) : (
          <div className="max-h-64 overflow-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs text-slate-500">
                <tr><th className="px-3 py-2">変更内容</th><th className="px-3 py-2">移動先</th></tr>
              </thead>
              <tbody>
                {preview.changes.slice(0, 30).map((c, i) => (
                  <tr key={i} className="border-b border-slate-100">
                    <td className="px-3 py-2">{c.title}（{c.hours}h）{c.from_date && <span className="text-xs text-slate-500"> {fmtDate(c.from_date, false)} から</span>}</td>
                    <td className="whitespace-nowrap px-3 py-2">{fmtDate(c.to_date)} に移動</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {preview.dropped.length > 0 && (
          <Alert tone="orange" title="収まらないタスク">
            {preview.dropped.map((d) => `${d.title}（${d.reason}）`).join("、")}
          </Alert>
        )}
        <Alert tone="purple" title="AI の判断">{preview.advice}</Alert>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>キャンセル</Button>
          {busy ? <Spinner label="適用しています…" /> : (
            <Button disabled={!preview.check_passed} onClick={() => { setBusy(true); onApply(); }}>この内容でリスケ</Button>
          )}
        </div>
      </div>
    </div>
  );
}
