"use client";

// アカウント設定（自分の情報とパスワード変更）

import { useState, type FormEvent } from "react";

import { AppShell, useUser } from "@/components/AppShell";
import { Field } from "@/components/AuthCard";
import { Alert, Button, Card } from "@/components/ui";
import { api, ROLE_LABEL } from "@/lib/api";

export default function SettingsPage() {
  return (
    <AppShell crumb={<b className="text-slate-900">アカウント設定</b>}>
      <div className="flex max-w-[560px] flex-col gap-5">
        <Profile />
        <PasswordForm />
      </div>
    </AppShell>
  );
}

function Profile() {
  const user = useUser();
  if (!user) return null;
  return (
    <Card className="flex flex-col gap-2">
      <span className="text-sm font-bold">あなたの情報</span>
      <div className="text-sm">
        {user.name}（{ROLE_LABEL[user.role]}）
      </div>
      <span className="text-xs text-slate-500">権限の変更は管理者に依頼してください</span>
    </Card>
  );
}

function PasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState<{ tone: "green" | "red"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (next !== confirm) {
      setMessage({ tone: "red", text: "確認用のパスワードが一致しません" });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      await api("/auth/password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      setMessage({ tone: "green", text: "パスワードを変更しました（ほかの端末ではログアウトされます）" });
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (err) {
      setMessage({ tone: "red", text: err instanceof Error ? err.message : "変更できませんでした" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <span className="text-sm font-bold">パスワードの変更</span>
        {message && <Alert tone={message.tone}>{message.text}</Alert>}
        <Field
          label="今のパスワード（仮パスワードを受け取った場合はそれ）"
          type="password"
          autoComplete="current-password"
          required
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
        <Field
          label="新しいパスワード"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={next}
          onChange={(e) => setNext(e.target.value)}
          hint="8文字以上"
        />
        <Field
          label="新しいパスワード（確認）"
          type="password"
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        <Button type="submit" disabled={busy} className="self-start">
          {busy ? "変更中…" : "変更する"}
        </Button>
      </form>
    </Card>
  );
}
