// バックエンド（FastAPI）とのやり取り。
// ログイン状態は HttpOnly の Cookie（サーバーが発行。画面の JavaScript からは読めない）で、同じオリジンなので自動で送られる。

// 既定は同じオリジンの /api（next.config.ts の rewrites でバックエンドへ中継）
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

export type Role = "member" | "mentor" | "admin";
export interface User {
  id: number;
  name: string;
  role: Role;
}

export interface AdminUser extends User {
  email: string;
  created_at: string | null;
}

export interface AuthConfig {
  allowed_email_domains: string[];
  first_user: boolean;
  min_password: number;
}

export const ROLE_LABEL: Record<Role, string> = { member: "メンバー", mentor: "育成担当", admin: "管理者" };

export interface Task {
  id: number;
  date: string;
  title: string;
  type: "learn" | "review" | "exercise" | "video" | "buffer";
  planned_hours: number;
  status: "todo" | "done" | "skipped";
  actual_hours: number | null;
  memo: string | null;
  material_id: number | null;
  topic: string | null;
  remainder_of_id: number | null;
}

export interface TaskUpdateResult {
  task: Task;
  remainder: Task | null;
  shortfall_hours: number;
}

export interface Material {
  id: number;
  topic: string;
  title: string;
  url: string | null;
  type: string;
  source: string;
  status: string;
  supplementary: boolean;
  url_check: string;
  reference_hours: number;
  reference_basis: string;
  sections: string[];
}

export interface Dropped {
  title: string;
  reason: string;
}

export interface Progress {
  planned_hours: number;
  done_hours: number;
  percent: number;
  delay_hours: number;
  actual_hours: number;
  buffer_left_hours: number;
  today: string;
}

export interface PlanTopic {
  name: string;
  purpose: string;
  purpose_label: string;
  purpose_note: string | null;
  can_do: string[];
  goals: string[];
  current_level: number;
  target_level: number;
  planned_hours: number;
  done_hours: number;
  percent: number;
}

export interface Plan {
  id: number;
  user_id: number;
  user_name: string;
  topic: string;
  topics: PlanTopic[];
  start_date: string;
  end_date: string;
  hours_per_day: number;
  excluded_weekdays: number[];
  status: "proposed" | "active" | "completed";
  warnings: string[];
  availability: { available_days: number; excluded_days: number; max_hours: number };
  materials: Material[];
  ai_note: {
    provider: string;
    order_reason: string;
    focus: string;
    dropped: Dropped[];
    allocation: { learn: number; review: number; buffer: number } | null;
    strategy: string;
    topic_allocation: { topic: string; hours: number }[];
    check_passed: boolean;
    check_issues: string[];
    retries: number;
  } | null;
  tasks: Task[];
  progress: Progress;
}

export interface PlanSummary {
  id: number;
  topic: string;
  topics: PlanTopic[];
  start_date: string;
  end_date: string;
  hours_per_day: number;
  status: string;
  progress: Progress;
}

export interface ReschedulePreview {
  today: string;
  pending_hours: number;
  remaining_days: number;
  changes: { title: string; hours: number; from_date: string | null; to_date: string }[];
  dropped: Dropped[];
  advice: string;
  check_passed: boolean;
  check_issues: string[];
  days: { date: string; tasks: { type: string; title: string; hours: number; material_id: number | null }[] }[];
}

export interface ReviewMaterial {
  id: number;
  topic: string;
  title: string;
  url: string | null;
  type: string;
  source: string;
  status: string;
  supplementary: boolean;
  url_check: string;
  reference_hours: number;
  reference_basis: string;
  sections: { title: string; est_hours: number; level_from: number; level_to: number }[];
  comment: string | null;
}

export interface Usage {
  provider: string;
  period: string;
  count: number;
  limit: number;
}

export interface AIStatus {
  provider: "gemini" | "demo";
  model: string | null;
  configured: string;
  reason: string;
  today_count: number | null;
  daily_limit: number | null;
  search: string[];
  search_missing: string[];
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public suggestions: string[] = [],
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const res = await fetch(`${API_BASE}${path}`, { credentials: "same-origin", ...init, headers });
  if (!res.ok) {
    let message = `エラーが発生しました（${res.status}）`;
    let suggestions: string[] = [];
    try {
      const body = await res.json();
      const detail = body.detail;
      if (typeof detail === "string") message = detail;
      else if (detail?.message) {
        message = detail.message;
        suggestions = detail.suggestions ?? [];
      } else if (Array.isArray(detail)) message = detail.map((d: { msg: string }) => d.msg).join(" / ");
    } catch {
      /* 本文が JSON でない */
    }
    throw new ApiError(message, res.status, suggestions);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** 単元の色（複数単元のプランで、どの単元のタスクかを見分ける） */
export const TOPIC_COLORS = ["bg-sky-500", "bg-amber-500", "bg-emerald-500", "bg-rose-500", "bg-violet-500"];
export function topicColor(plan: { topics: { name: string }[] }, name: string | null | undefined): string {
  const i = plan.topics.findIndex((t) => t.name === name);
  return i >= 0 ? TOPIC_COLORS[i % TOPIC_COLORS.length] : "bg-slate-300";
}

/** 単元ごとのレベルの目安（例：Java Lv2→4 ・ SQL Lv1→3） */
export function levelSummary(topics: PlanTopic[]): string {
  return topics.map((t) => `${t.name} Lv${t.current_level}→${t.target_level}`).join(" ・ ");
}

export const TYPE_LABEL: Record<string, string> = {
  official_doc: "公式",
  official_learning: "公式学習",
  article: "記事",
  video: "動画",
  roadmap: "ロードマップ",
  exercise: "課題",
};

export const TASK_LABEL: Record<Task["type"], string> = {
  learn: "学習",
  review: "復習",
  exercise: "演習",
  video: "動画",
  buffer: "予備",
};

export const SOURCE_LABEL: Record<string, string> = {
  catalog: "カタログ",
  tavily: "Tavily",
  qiita: "Qiita API",
  youtube: "YouTube Data API",
  demo: "デモ検索",
  ai: "AI生成",
};

const WEEK = ["日", "月", "火", "水", "木", "金", "土"];

export function fmtDate(iso: string, withWeek = true): string {
  const d = new Date(`${iso}T00:00:00`);
  const s = `${d.getMonth() + 1}/${d.getDate()}`;
  return withWeek ? `${s}（${WEEK[d.getDay()]}）` : s;
}

export function hours(h: number): string {
  return `${Math.round(h * 100) / 100}h`;
}
