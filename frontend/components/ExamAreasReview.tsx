"use client";

// S08：AI が作った資格試験の出題範囲を、育成担当が確認・修正して承認する

import { useCallback, useEffect, useState } from "react";

import { Alert, Badge, Button, Card } from "@/components/ui";
import { api, type ExamArea } from "@/lib/api";

interface PendingExam {
  topic_id: number;
  topic: string;
  syllabus_url: string | null;
  areas: ExamArea[];
}

export function ExamAreasReview({ onChanged }: { onChanged?: () => void }) {
  const [list, setList] = useState<PendingExam[]>([]);

  const load = useCallback(async () => {
    setList(await api<PendingExam[]>("/review/exam-areas"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (list.length === 0) return null;
  return (
    <div className="flex flex-col gap-4">
      {list.map((e) => (
        <ExamCard
          key={e.topic_id}
          exam={e}
          onSaved={() => {
            load();
            onChanged?.();
          }}
        />
      ))}
    </div>
  );
}

function ExamCard({ exam, onSaved }: { exam: PendingExam; onSaved: () => void }) {
  const [areas, setAreas] = useState<ExamArea[]>(exam.areas.map(({ name, description, weight, est_hours }) => ({ name, description, weight, est_hours })));
  const [url, setUrl] = useState(exam.syllabus_url ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const totalWeight = areas.reduce((s, a) => s + (Number(a.weight) || 0), 0);
  const totalHours = areas.reduce((s, a) => s + (Number(a.est_hours) || 0), 0);

  const edit = (i: number, patch: Partial<ExamArea>) => setAreas((list) => list.map((a, j) => (j === i ? { ...a, ...patch } : a)));

  const approve = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`/review/topics/${exam.topic_id}/areas`, {
        method: "PUT",
        body: JSON.stringify({
          areas: areas.map((a) => ({ ...a, weight: Number(a.weight), est_hours: Number(a.est_hours) })),
          syllabus_url: url || null,
        }),
      });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存できませんでした");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-bold">
          {exam.topic} の出題範囲 <Badge tone="purple">AI 作成（未レビュー）</Badge>
        </h2>
        <span className="text-xs text-slate-500">
          比重の合計 {Math.round(totalWeight)}% ・ 目安の合計 {Math.round(totalHours * 10) / 10}h
        </span>
      </div>
      <p className="text-xs text-slate-500">
        公式のシラバスと見比べて、分野名・比重・目安時間を直してから承認してください。承認すると、これからこの試験で作るプランに使われます（作成済みのプランは変わりません）
      </p>
      {error && <Alert tone="red">{error}</Alert>}
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-bold">公式シラバスの URL</span>
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" className="h-9 rounded-lg border border-slate-300 px-2" />
      </label>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500">
            <tr>
              <th className="px-2 py-2">分野名</th>
              <th className="px-2 py-2">内容</th>
              <th className="w-24 px-2 py-2">比重（%）</th>
              <th className="w-24 px-2 py-2">目安（h）</th>
              <th className="w-12 px-2 py-2" />
            </tr>
          </thead>
          <tbody>
            {areas.map((a, i) => (
              <tr key={i} className="border-b border-slate-100">
                <td className="px-2 py-1.5">
                  <input aria-label="分野名" value={a.name} onChange={(e) => edit(i, { name: e.target.value })} className="h-9 w-full rounded border border-slate-300 px-2" />
                </td>
                <td className="px-2 py-1.5">
                  <input aria-label="内容" value={a.description} onChange={(e) => edit(i, { description: e.target.value })} className="h-9 w-full rounded border border-slate-300 px-2 text-xs" />
                </td>
                <td className="px-2 py-1.5">
                  <input aria-label="比重" type="number" min={1} max={100} value={a.weight} onChange={(e) => edit(i, { weight: Number(e.target.value) })} className="h-9 w-full rounded border border-slate-300 px-2" />
                </td>
                <td className="px-2 py-1.5">
                  <input aria-label="目安時間" type="number" min={0.5} step={0.5} value={a.est_hours} onChange={(e) => edit(i, { est_hours: Number(e.target.value) })} className="h-9 w-full rounded border border-slate-300 px-2" />
                </td>
                <td className="px-2 py-1.5 text-right">
                  <button onClick={() => setAreas((list) => list.filter((_, j) => j !== i))} className="text-xs text-red-600" aria-label={`${a.name} を削除`}>
                    削除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap justify-between gap-2">
        <Button variant="secondary" onClick={() => setAreas((list) => [...list, { name: "", description: "", weight: 5, est_hours: 2 }])}>
          ＋ 分野を追加
        </Button>
        <Button variant="ok" disabled={busy || areas.length === 0} onClick={approve}>
          {busy ? "保存中…" : "この内容で承認"}
        </Button>
      </div>
    </Card>
  );
}
