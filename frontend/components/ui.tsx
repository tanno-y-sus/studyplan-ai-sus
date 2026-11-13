// 画面で共通に使う部品（Figma UI案 v0.2 の配色：青＝通常・カタログ、紫＝AI、緑＝復習・完了、オレンジ＝遅れ・警告）

import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-slate-200 bg-white p-5 ${className}`}>{children}</div>;
}

type Tone = "blue" | "purple" | "green" | "orange" | "gray" | "red";
const TONES: Record<Tone, string> = {
  blue: "bg-blue-50 text-blue-700",
  purple: "bg-violet-100 text-violet-700",
  green: "bg-green-50 text-green-700",
  orange: "bg-orange-50 text-orange-700",
  gray: "bg-slate-100 text-slate-600",
  red: "bg-red-50 text-red-700",
};

export function Badge({ tone = "gray", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex h-[22px] items-center whitespace-nowrap rounded-full px-2 text-[11px] font-bold ${TONES[tone]}`}>
      {children}
    </span>
  );
}

const ALERTS: Record<Tone, string> = {
  blue: "border-blue-200 bg-blue-50 text-blue-900",
  purple: "border-violet-200 bg-violet-50 text-violet-900",
  green: "border-green-200 bg-green-50 text-green-900",
  orange: "border-orange-200 bg-orange-50 text-orange-900",
  gray: "border-slate-200 bg-slate-50 text-slate-700",
  red: "border-red-200 bg-red-50 text-red-900",
};

export function Alert({ tone = "blue", title, children }: { tone?: Tone; title?: string; children?: ReactNode }) {
  return (
    <div className={`flex flex-wrap items-start gap-x-3 gap-y-1 rounded-lg border px-4 py-3 text-sm ${ALERTS[tone]}`}>
      {title && <b className="whitespace-nowrap">{title}</b>}
      {children && <div className="min-w-0 flex-1">{children}</div>}
    </div>
  );
}

export function Button({
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "ok" | "danger" }) {
  const styles = {
    primary: "bg-blue-600 text-white hover:bg-blue-700",
    secondary: "border border-slate-300 bg-white text-slate-900 hover:bg-slate-50",
    ghost: "text-blue-600 hover:underline",
    ok: "bg-green-700 text-white hover:bg-green-800",
    danger: "border border-red-300 bg-white text-red-700 hover:bg-red-50",
  }[variant];
  return (
    <button
      className={`inline-flex h-10 items-center justify-center whitespace-nowrap rounded-lg px-4 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}
      {...props}
    />
  );
}

export function Bar({ percent, color = "bg-blue-600" }: { percent: number; color?: string }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-slate-200">
      <div className={`h-2 rounded-full ${color}`} style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />
    </div>
  );
}

export function Kpi({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string }) {
  return (
    <div className="flex flex-1 flex-col gap-1.5 rounded-xl border border-slate-200 bg-white px-5 py-4">
      <span className="text-xs text-slate-500">{label}</span>
      <span className={`text-2xl font-bold ${tone ?? ""}`}>{value}</span>
      {sub}
    </div>
  );
}

export function Split({ learn, review, buffer }: { learn: number; review: number; buffer: number }) {
  const total = learn + review + buffer || 1;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex h-3.5 overflow-hidden rounded-full">
        <span className="bg-blue-500" style={{ width: `${(learn / total) * 100}%` }} />
        <span className="bg-green-500" style={{ width: `${(review / total) * 100}%` }} />
        <span className="bg-slate-400" style={{ width: `${(buffer / total) * 100}%` }} />
      </div>
      <div className="flex gap-4 text-xs text-slate-600">
        <Legend color="bg-blue-500">学習 {learn}h</Legend>
        <Legend color="bg-green-500">復習 {review}h</Legend>
        <Legend color="bg-slate-400">予備 {buffer}h</Legend>
      </div>
    </div>
  );
}

export function Legend({ color, children }: { color: string; children: ReactNode }) {
  return (
    <span className="flex items-center gap-1.5">
      <i className={`inline-block h-2.5 w-2.5 rounded-sm ${color}`} />
      {children}
    </span>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 text-sm text-slate-600">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      {label}
    </div>
  );
}
