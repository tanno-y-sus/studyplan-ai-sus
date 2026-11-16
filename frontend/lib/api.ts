// バックエンド（FastAPI）とのやり取り。MVP の認証は簡易（選んだユーザーの ID を X-User-Id で送る）。

// 既定は同じオリジンの /api（next.config.ts の rewrites でバックエンドへ中継）
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

export type Role = "member" | "mentor" | "admin";
export interface User {
  id: number;
  name: string;
  role: Role;
}

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
}

export interface Material {
  id: number;
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

export interface Plan {
  id: number;
  user_id: number;
  user_name: string;
  topic: string;
  purpose: string | null;
  current_level: number;
  target_level: number;
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
  current_level: number;
  target_level: number;
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

const USER_KEY = "studyplan.userId";

export function getUserId(): number | null {
  try {
    const v = localStorage.getItem(USER_KEY);
    return v ? Number(v) : null;
  } catch {
    return null;
  }
}

export function setUserId(id: number | null) {
  try {
    if (id === null) localStorage.removeItem(USER_KEY);
    else localStorage.setItem(USER_KEY, String(id));
  } catch {
    /* 保存できない環境では毎回ログイン画面に戻る */
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const uid = getUserId();
  if (uid) headers.set("X-User-Id", String(uid));
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
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
