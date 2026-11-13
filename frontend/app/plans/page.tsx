"use client";

// マイプラン一覧

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { PlanCard } from "@/components/PlanCard";
import { Button, Card } from "@/components/ui";
import { api, type PlanSummary } from "@/lib/api";

export default function PlansPage() {
  const [plans, setPlans] = useState<PlanSummary[] | null>(null);
  useEffect(() => {
    api<PlanSummary[]>("/plans").then(setPlans);
  }, []);
  return (
    <AppShell
      crumb={<b className="text-slate-900">マイプラン</b>}
      actions={
        <Link href="/plans/new">
          <Button>＋ 新しいプランを作る</Button>
        </Link>
      }
    >
      <Card className="flex flex-col gap-2">
        {plans?.length === 0 && <p className="text-sm text-slate-500">まだプランがありません</p>}
        {plans?.map((p) => <PlanCard key={p.id} plan={p} />)}
      </Card>
    </AppShell>
  );
}
