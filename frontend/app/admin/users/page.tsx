"use client";

// ユーザー管理（管理者のみ）：権限の変更と、パスワードを忘れた人への仮パスワードの発行

import { useCallback, useEffect, useState } from "react";

import { AppShell, useUser } from "@/components/AppShell";
import { Alert, Badge, Button, Card } from "@/components/ui";
import { api, ROLE_LABEL, type AdminUser, type Role } from "@/lib/api";

const ROLES: Role[] = ["member", "mentor", "admin"];

export default function AdminUsersPage() {
  return (
    <AppShell crumb={<b className="text-slate-900">ユーザー管理</b>}>
      <UserTable />
    </AppShell>
  );
}

function UserTable() {
  const me = useUser();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ name: string; password: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setUsers(await api<AdminUser[]>("/admin/users"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "読み込めませんでした");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (me && me.role !== "admin") return <Alert tone="red">この画面は管理者だけが使えます</Alert>;

  const changeRole = async (u: AdminUser, role: Role) => {
    setError(null);
    try {
      await api(`/admin/users/${u.id}`, { method: "PATCH", body: JSON.stringify({ role }) });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "変更できませんでした");
    }
  };

  const issueTemporary = async (u: AdminUser) => {
    if (!window.confirm(`${u.name} さんの仮パスワードを発行します。今のパスワードは使えなくなります。よろしいですか？`)) return;
    setError(null);
    try {
      const { password } = await api<{ password: string }>(`/admin/users/${u.id}/temporary-password`, { method: "POST" });
      setNotice({ name: u.name, password });
    } catch (err) {
      setError(err instanceof Error ? err.message : "発行できませんでした");
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Alert tone="gray" title="権限について">
        メンバー：自分のプランを作る・進める ／ 育成担当：メンバーの進捗を見る・AI が探した教材を承認する ／ 管理者：育成担当の権限＋ユーザー管理。新しく登録した人はメンバーになります
      </Alert>
      {error && <Alert tone="red">{error}</Alert>}
      {notice && (
        <Alert tone="orange" title={`${notice.name} さんの仮パスワード`}>
          <code className="rounded bg-white px-2 py-0.5 font-mono text-base">{notice.password}</code>
          <div className="mt-1 text-xs">
            この画面を閉じると二度と表示されません。本人に直接伝え、ログイン後に「アカウント設定」で変更してもらってください
          </div>
        </Alert>
      )}
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="border-b border-slate-200 text-left text-xs text-slate-500">
            <tr>
              <th className="px-5 py-3">氏名</th>
              <th className="px-5 py-3">メールアドレス</th>
              <th className="px-5 py-3">権限</th>
              <th className="px-5 py-3">登録日</th>
              <th className="px-5 py-3" />
            </tr>
          </thead>
          <tbody>
            {users === null && (
              <tr>
                <td className="px-5 py-4 text-slate-500" colSpan={5}>
                  読み込み中…
                </td>
              </tr>
            )}
            {users?.map((u) => (
              <tr key={u.id} className="border-b border-slate-100 last:border-0">
                <td className="px-5 py-3">
                  {u.name} {u.id === me?.id && <Badge tone="blue">あなた</Badge>}
                </td>
                <td className="px-5 py-3 text-slate-600">{u.email}</td>
                <td className="px-5 py-3">
                  <select
                    className="h-9 rounded-lg border border-slate-300 bg-white px-2"
                    value={u.role}
                    onChange={(e) => changeRole(u, e.target.value as Role)}
                    aria-label={`${u.name} の権限`}
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {ROLE_LABEL[r]}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-5 py-3 text-slate-500">{u.created_at ? new Date(u.created_at).toLocaleDateString("ja-JP") : "-"}</td>
                <td className="px-5 py-3 text-right">
                  {u.id !== me?.id && (
                    <Button variant="secondary" className="h-9" onClick={() => issueTemporary(u)}>
                      仮パスワードを発行
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
