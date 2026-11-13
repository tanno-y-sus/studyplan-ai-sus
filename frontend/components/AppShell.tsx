"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, getUserId, setUserId, type User } from "@/lib/api";

const UserContext = createContext<User | null>(null);
export const useUser = () => useContext(UserContext);

const ROLE_LABEL = { member: "メンバー", mentor: "育成担当", admin: "管理者" } as const;

export function AppShell({ children, crumb, actions }: { children: ReactNode; crumb: ReactNode; actions?: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!getUserId()) {
      router.replace("/login");
      return;
    }
    api<User>("/me")
      .then(setUser)
      .catch(() => {
        setUserId(null);
        router.replace("/login");
      });
  }, [router]);

  if (!user) return <div className="p-10 text-sm text-slate-500">読み込み中…</div>;

  return (
    <UserContext.Provider value={user}>
      <div className="flex min-h-screen bg-[#F5F7FB]">
        <Sidebar user={user} />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-8">
            <div className="text-sm text-slate-500">{crumb}</div>
            <div className="flex gap-2">{actions}</div>
          </header>
          <main className="flex flex-1 flex-col gap-5 px-8 py-7">{children}</main>
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
          onClick={() => {
            setUserId(null);
            router.push("/login");
          }}
        >
          切替
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
