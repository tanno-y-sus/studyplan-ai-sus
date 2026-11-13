import Link from "next/link";

import { Badge, Bar } from "@/components/ui";
import { fmtDate, type PlanSummary } from "@/lib/api";

export function statusBadge(p: PlanSummary) {
  if (p.status === "proposed") return <Badge tone="purple">提案中（未確定）</Badge>;
  if (p.progress.percent >= 100) return <Badge tone="green">完了</Badge>;
  if (p.progress.today < p.start_date) return <Badge tone="gray">開始前</Badge>;
  if (p.progress.delay_hours > 0) return <Badge tone="orange">遅れ {p.progress.delay_hours}h</Badge>;
  return <Badge tone="green">順調</Badge>;
}

export function PlanCard({ plan }: { plan: PlanSummary }) {
  const href = plan.status === "proposed" ? `/plans/${plan.id}/proposal` : `/plans/${plan.id}`;
  return (
    <Link href={href} className="flex flex-col gap-1.5 rounded-lg p-2 hover:bg-slate-50">
      <div className="flex items-center justify-between gap-2">
        <b className="text-sm">{plan.topic}</b>
        {statusBadge(plan)}
      </div>
      <span className="text-xs text-slate-500">
        Lv{plan.current_level} → Lv{plan.target_level} ・ {fmtDate(plan.start_date, false)}〜{fmtDate(plan.end_date, false)} ・
        1日{plan.hours_per_day}h
      </span>
      <Bar percent={plan.progress.percent} color={plan.progress.percent >= 100 ? "bg-green-700" : "bg-blue-600"} />
    </Link>
  );
}
