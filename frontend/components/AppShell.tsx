"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, ROLE_LABEL, type User } from "@/lib/api";

const UserContext = createContext<User | null>(null);
export const useUser = () => useContext(UserContext);

export function AppShell({ children, crumb, actions }: { children: ReactNode; crumb: ReactNode; actions?: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  // 画面を移動したら、スマホ幅のメニューを閉じる
  useEffect(() => setMenuOpen(false), [pathname]);

  useEffect(() => {
    // ログインしていなければ（Cookie がない・期限切れ）ログイン画面へ
    api<User>("/me")
      .then(setUser)
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!user) return <div className="p-10 text-sm text-slate-500">読み込み中…</div>;

  return (
    <UserContext.Provider value={user}>
      <div className="flex min-h-screen bg-[#F5F7FB]">
        {/* 幅が広いときは左に固定、狭いとき（スマホなど）はメニューボタンで開く */}
        <div className="hidden md:block">
          <Sidebar user={user} />
        </div>
        {menuOpen && (
          <div className="fixed inset-0 z-30 flex md:hidden">
            <Sidebar user={user} />
            <button className="flex-1 bg-slate-900/45" aria-label="メニューを閉じる" onClick={() => setMenuOpen(false)} />
          </div>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex min-h-16 flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-3 md:px-8">
            <div className="flex min-w-0 items-center gap-3 text-sm text-slate-500">
              <button
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-300 text-slate-700 md:hidden"
                aria-label="メニューを開く"
                onClick={() => setMenuOpen(true)}
              >
                ☰
              </button>
              <div className="min-w-0">{crumb}</div>
            </div>
            <div className="flex flex-wrap gap-2">{actions}</div>
          </header>
          <main className="flex min-w-0 flex-1 flex-col gap-5 px-4 py-5 md:px-8 md:py-7">{children}</main>
        </div>
      </div>
    </UserContext.Provider>
  );
}

function Sidebar({ user }: { user: User }) {
  const pathname = usePathname();
  const router = useRouter();
  const isStaff = user.role === "mentor" || user.role === "admin";
  return (
    <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col gap-1 bg-slate-900 px-4 py-6 text-slate-300">
      <div className="flex items-center gap-2.5 px-2 pb-6 text-lg font-bold text-white">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm">SP</span>
        StudyPlan AI
      </div>
      <NavItem href="/" active={pathname === "/"}>ダッシュボード</NavItem>
      <NavItem href="/plans/new" active={pathname === "/plans/new"}>新しいプランを作る</NavItem>
      <NavItem href="/plans" active={pathname.startsWith("/plans") && pathname !== "/plans/new"}>マイプラン</NavItem>
      {isStaff && (
        <>
          <div className="px-3 pb-1.5 pt-4 text-[11px] tracking-wider text-slate-500">育成担当</div>
          <NavItem href="/mentor" active={pathname === "/mentor"}>メンバー進捗</NavItem>
          <NavItem href="/review" active={pathname === "/review"}>AI提案レビュー</NavItem>
        </>
      )}
      {user.role === "admin" && (
        <>
          <div className="px-3 pb-1.5 pt-4 text-[11px] tracking-wider text-slate-500">管理者</div>
          <NavItem href="/admin/users" active={pathname === "/admin/users"}>ユーザー管理</NavItem>
        </>
      )}
      <div className="px-3 pb-1.5 pt-4 text-[11px] tracking-wider text-slate-500">アカウント</div>
      <NavItem href="/settings" active={pathname === "/settings"}>アカウント設定</NavItem>
      <div className="mt-auto flex items-center gap-2.5 border-t border-slate-800 p-3 text-sm">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-700 text-sm font-bold text-white">
          {user.name.slice(0, 1)}
        </span>
        <div className="flex-1">
          {user.name}
          <br />
          <span className="text-xs text-slate-500">{ROLE_LABEL[user.role]}</span>
        </div>
        <button
          className="text-xs text-slate-400 hover:text-white"
          onClick={async () => {
            await api("/auth/logout", { method: "POST" }).catch(() => undefined);
            router.push("/login");
          }}
        >
          ログアウト
        </button>
      </div>
    </aside>
  );
}

function NavItem({ href, active, children }: { href: string; active: boolean; children: ReactNode }) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm ${active ? "bg-slate-800 font-bold text-white" : "hover:bg-slate-800/60"}`}
    >
      <span className={`h-[18px] w-[18px] rounded-[5px] border-2 ${active ? "border-blue-400 bg-blue-700" : "border-slate-500"}`} />
      {children}
    </Link>
  );
}
