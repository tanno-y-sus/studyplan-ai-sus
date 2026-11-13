"use client";

// S01 ログイン（MVP は簡易ログイン：ユーザーを選ぶだけ。本番は社内 SSO に置き換える）

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert, Button } from "@/components/ui";
import { api, setUserId, type User } from "@/lib/api";

const ROLE_LABEL = { member: "メンバー", mentor: "育成担当", admin: "管理者" } as const;

export default function LoginPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<User[]>("/users")
      .then(setUsers)
      .catch(() => setError("サーバーに接続できません。バックエンド（既定は http://localhost:8000）が起動しているか確認してください"));
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-[#F5F7FB]">
      <div className="flex w-[440px] flex-col items-center gap-6 rounded-xl border border-slate-200 bg-white p-10 shadow-[0_12px_40px_rgba(15,23,42,0.08)]">
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600 text-xl font-bold text-white">SP</span>
        <div className="flex flex-col gap-2 text-center">
          <h1 className="text-2xl font-bold">StudyPlan AI</h1>
          <p className="text-sm text-slate-600">
            待機期間を、計画的な学習期間に。
            <br />
            学びたい技術を入力するだけで、教材と日程を提案します。
          </p>
        </div>
        <Alert tone="gray" title="MVP の簡易ログイン">本番では社内アカウント（SSO）でログインします</Alert>
        {error && <Alert tone="red">{error}</Alert>}
        <div className="flex w-full flex-col gap-2">
          {users.map((u) => (
            <Button
              key={u.id}
              variant={u.role === "member" ? "primary" : "secondary"}
              className="h-12 w-full justify-between"
              onClick={() => {
                setUserId(u.id);
                router.push(u.role === "member" ? "/" : "/mentor");
              }}
            >
              <span>{u.name}</span>
              <span className="text-xs font-normal opacity-80">{ROLE_LABEL[u.role]}</span>
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
}
