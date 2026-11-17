"use client";

// 新規登録（氏名・メールアドレス・パスワード）。登録するとそのままログインする

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { AuthCard, Field } from "@/components/AuthCard";
import { Alert, Button } from "@/components/ui";
import { api, type AuthConfig, type User } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<AuthConfig>("/auth/config")
      .then(setConfig)
      .catch(() => setError("サーバーに接続できません。バックエンドが起動しているか確認してください"));
  }, []);

  const minPassword = config?.min_password ?? 8;
  const domains = config?.allowed_email_domains ?? [];
  const mismatch = confirm.length > 0 && password !== confirm;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      setError("確認用のパスワードが一致しません");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const { user } = await api<{ user: User }>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ name, email, password }),
      });
      router.push(user.role === "admin" ? "/admin/users" : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登録できませんでした");
      setBusy(false);
    }
  };

  return (
    <AuthCard title="新規登録" lead="StudyPlan AI のアカウントを作ります">
      {config?.first_user && (
        <Alert tone="purple" title="最初の登録者です">
          あなたは<b>管理者</b>として登録されます。あとから登録した人の権限（メンバー・育成担当・管理者）を「ユーザー管理」で変更できます
        </Alert>
      )}
      {error && <Alert tone="red">{error}</Alert>}
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="氏名" autoComplete="name" required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
        <Field
          label="メールアドレス"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          hint={domains.length > 0 ? `登録できるのは ${domains.map((d) => `@${d}`).join("・")} のアドレスだけです` : undefined}
        />
        <Field
          label="パスワード"
          type="password"
          autoComplete="new-password"
          required
          minLength={minPassword}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          hint={`${minPassword}文字以上`}
        />
        <Field
          label="パスワード（確認）"
          type="password"
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          hint={mismatch ? <span className="text-red-600">パスワードが一致しません</span> : undefined}
        />
        <Button type="submit" className="h-12 w-full text-[15px]" disabled={busy || mismatch}>
          {busy ? "登録中…" : "登録してはじめる"}
        </Button>
      </form>
      <p className="text-center text-sm text-slate-600">
        すでにアカウントがある方は <Link href="/login" className="font-bold text-blue-600 hover:underline">ログイン</Link>
      </p>
    </AuthCard>
  );
}
