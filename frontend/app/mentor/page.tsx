"use client";

// S07 育成担当ビュー

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { statusBadge } from "@/components/PlanCard";
import { Bar, Card, Kpi } from "@/components/ui";
import { api, fmtDate, type PlanSummary } from "@/lib/api";

interface MemberRow {
  user: { id: number; name: string };
  plans: PlanSummary[];
}

export default function MentorPage() {
  const [data, setData] = useState<{ members: MemberRow[]; pending_reviews: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<{ members: MemberRow[]; pending_reviews: number }>("/mentor/members").then(setData).catch((e) => setError(e.message));
  }, []);

  const rows: { m: MemberRow; p: PlanSummary | null }[] =
    data?.members.flatMap((m): { m: MemberRow; p: PlanSummary | null }[] =>
      m.plans.length ? m.plans.map((p) => ({ m, p })) : [{ m, p: null }],
    ) ?? [];
  const learning = rows.filter((r) => r.p?.status === "active").length;
  const delayed = new Set(rows.filter((r) => r.p && r.p.status === "active" && r.p.progress.delay_hours > 0).map((r) => r.m.user.id)).size;

  return (
    <AppShell crumb={<b className="text-slate-900">メンバー進捗</b>}>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {data && (
        <>
          <div className="flex gap-5">
            <Kpi label="担当メンバー" value={`${data.members.length} 名`} />
            <Kpi label="学習中のプラン" value={learning} />
            <Kpi label="遅れているメンバー" value={`${delayed} 名`} tone={delayed ? "text-orange-700" : ""} />
            <Kpi
              label="AI提案のレビュー待ち"
              value={<span className="text-violet-700">{data.pending_reviews} 件</span>}
              sub={<Link href="/review" className="text-sm font-bold text-blue-600">レビューする →</Link>}
            />
          </div>
          <Card className="flex flex-col gap-3">
            <h2 className="font-bold">メンバー一覧</h2>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs text-slate-500">
                <tr>
                  <th className="px-3 py-2.5">メンバー</th>
                  <th className="px-3 py-2.5">単元</th>
                  <th className="px-3 py-2.5">レベル</th>
                  <th className="px-3 py-2.5">期間</th>
                  <th className="w-56 px-3 py-2.5">達成率</th>
                  <th className="px-3 py-2.5">状態</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ m, p }, i) => (
                  <tr key={`${m.user.id}-${p?.id ?? i}`} className="border-b border-slate-100">
                    <td className="px-3 py-3">{m.user.name}</td>
                    <td className="px-3 py-3">{p ? <Link className="text-blue-600" href={`/plans/${p.id}`}>{p.topic}</Link> : "―"}</td>
                    <td className="px-3 py-3">{p ? `Lv${p.current_level} → Lv${p.target_level}` : "―"}</td>
                    <td className="px-3 py-3">{p ? `${fmtDate(p.start_date, false)}〜${fmtDate(p.end_date, false)}` : "―"}</td>
                    <td className="px-3 py-3">{p && <Bar percent={p.progress.percent} />}</td>
                    <td className="px-3 py-3">{p ? statusBadge(p) : <span className="text-xs text-slate-500">プランなし</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </AppShell>
  );
}
