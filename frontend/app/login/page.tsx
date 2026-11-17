"use client";

// S01 ログイン（メールアドレスとパスワード）

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { AuthCard, Field } from "@/components/AuthCard";
import { Alert, Button } from "@/components/ui";
import { api, type AuthConfig, type User } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState<AuthConfig | null>(null);

  useEffect(() => {
    api<AuthConfig>("/auth/config")
      .then(setConfig)
      .catch(() => setError("サーバーに接続できません。バックエンド（既定は http://localhost:8000）が起動しているか確認してください"));
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { user } = await api<{ user: User }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      router.push(user.role === "member" ? "/" : "/mentor");
    } catch (err) {
      setError(err instanceof Error ? err.message : "ログインできませんでした");
      setBusy(false);
    }
  };

  return (
    <AuthCard
      title="StudyPlan AI"
      lead={
        <>
          待機期間を、計画的な学習期間に。
          <br />
          学びたい技術を入力するだけで、教材と日程を提案します。
        </>
      }
    >
      {config?.first_user && (
        <Alert tone="blue" title="はじめての方へ">
          まだ誰も登録していません。<Link href="/register" className="font-bold underline">新規登録</Link>した最初の人が管理者になります
        </Alert>
      )}
      {error && <Alert tone="red">{error}</Alert>}
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="メールアドレス" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Field
          label="パスワード"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Button type="submit" className="h-12 w-full text-[15px]" disabled={busy}>
          {busy ? "ログイン中…" : "ログイン"}
        </Button>
      </form>
      <div className="flex flex-col items-center gap-1 text-sm text-slate-600">
        <span>
          はじめての方は <Link href="/register" className="font-bold text-blue-600 hover:underline">新規登録</Link>
        </span>
        <span className="text-xs text-slate-500">パスワードを忘れたときは、管理者に仮パスワードの発行を依頼してください</span>
      </div>
    </AuthCard>
  );
}
