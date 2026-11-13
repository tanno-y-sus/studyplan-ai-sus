"use client";

// S03 プラン作成フォーム（02-1 入力・単元正規化 / 02-2 スキル判定）

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { Alert, Badge, Button, Card, Spinner } from "@/components/ui";
import { api, ApiError, type Plan } from "@/lib/api";

interface Suggestion {
  name: string;
  category: string;
  in_catalog: boolean;
}
interface Guide {
  level: number;
  description: string;
}
interface Availability {
  available_days: number;
  excluded_days: number;
  max_hours: number;
}

const LEVEL_NAMES = ["未経験", "入門", "初級", "中級", "実務"];
const WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"];

function isoAfter(days: number) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export default function NewPlanPage() {
  return (
    <AppShell crumb={<>新しいプランを作る ／ <b className="text-slate-900">1. 学習条件の入力</b></>}>
      <NewPlanForm />
    </AppShell>
  );
}

function NewPlanForm() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggest, setShowSuggest] = useState(false);
  const [purpose, setPurpose] = useState("");
  const [current, setCurrent] = useState(2);
  const [target, setTarget] = useState(3);
  const [guides, setGuides] = useState<Guide[]>([]);
  const [start, setStart] = useState(isoAfter(1));
  const [end, setEnd] = useState(isoAfter(29));
  const [hpd, setHpd] = useState(2);
  const [excluded, setExcluded] = useState<number[]>([5, 6]);
  const [avail, setAvail] = useState<Availability | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      api<Suggestion[]>(`/topics/suggest?q=${encodeURIComponent(topic)}`).then(setSuggestions).catch(() => {});
      api<Guide[]>(`/topics/level-guides?topic=${encodeURIComponent(topic)}`).then(setGuides).catch(() => {});
    }, 200);
    return () => clearTimeout(t);
  }, [topic]);

  useEffect(() => {
    if (!start || !end || end < start) return setAvail(null);
    api<Availability>(
      `/availability?start_date=${start}&end_date=${end}&hours_per_day=${hpd}&excluded_weekdays=${excluded.join(",")}`,
    )
      .then(setAvail)
      .catch(() => setAvail(null));
  }, [start, end, hpd, excluded]);

  const guide = (lv: number) => guides.find((g) => g.level === lv)?.description;

  const submit = async (topicName = topic) => {
    setSubmitting(true);
    setError(null);
    try {
      const plan = await api<Plan>("/plans", {
        method: "POST",
        body: JSON.stringify({
          topic: topicName,
          purpose: purpose || null,
          current_level: current,
          target_level: target,
          start_date: start,
          end_date: end,
          hours_per_day: hpd,
          excluded_weekdays: excluded,
        }),
      });
      router.push(`/plans/${plan.id}/proposal`);
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("エラーが発生しました", 0));
      setSubmitting(false);
    }
  };

  return (
    <div className="flex gap-6">
      <div className="flex flex-1 flex-col gap-5">
        <Card className="flex flex-col gap-3.5">
          <h2 className="font-bold">何を学習しますか？</h2>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-bold">学習したい単元（IT技術）</span>
            <div className="relative">
              <input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                onFocus={() => setShowSuggest(true)}
                onBlur={() => setTimeout(() => setShowSuggest(false), 150)}
                placeholder="例：Python、SQL、AWS（EC2・VPC）、Docker、React …"
                className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-2 focus:border-blue-600"
              />
              {showSuggest && suggestions.length > 0 && (
                <div className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
                  {suggestions.map((s) => (
                    <button
                      key={s.name}
                      type="button"
                      onMouseDown={() => setTopic(s.name)}
                      className="flex w-full items-center justify-between border-b border-slate-100 px-3 py-2.5 text-left text-sm hover:bg-blue-50"
                    >
                      <span>
                        <b>{s.name}</b> <span className="text-slate-500">（{s.category}）</span>
                      </span>
                      {s.in_catalog ? <Badge tone="blue">カタログあり</Badge> : <Badge tone="purple">AI探索</Badge>}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <span className="text-xs text-slate-500">カタログにない単元は、AI が無料検索API（公式ドキュメント・記事・動画）で教材を探します</span>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-bold">学習の目的（任意）</span>
            <input
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
              placeholder="例：次の案件で EC2 上に Web アプリを構築する"
              className="h-11 rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-2 focus:border-blue-600"
            />
          </label>
        </Card>

        <Card className="flex flex-col gap-4">
          <h2 className="font-bold">現在のスキルと目標</h2>
          <LevelPicker label="現在のレベル" value={current} onChange={(v) => { setCurrent(v); if (target < v) setTarget(v); }} tone="blue" />
          <p className="-mt-2 text-xs text-slate-500">Lv{current} の目安：{guide(current)}</p>
          <LevelPicker label="目標レベル" value={target} onChange={setTarget} min={current} tone="green" />
          <p className="-mt-2 text-xs text-slate-500">Lv{target} の目安：{guide(target)}</p>
        </Card>
      </div>

      <div className="flex w-[420px] flex-col gap-5">
        <Card className="flex flex-col gap-3.5">
          <h2 className="font-bold">期間と学習時間</h2>
          <div className="flex gap-3">
            <DateField label="開始日" value={start} onChange={setStart} />
            <DateField label="終了日" value={end} onChange={setEnd} />
          </div>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-bold">1日に確保できる時間</span>
            <select
              value={hpd}
              onChange={(e) => setHpd(Number(e.target.value))}
              className="h-11 rounded-lg border border-slate-300 px-3 text-sm"
            >
              {[0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8].map((h) => (
                <option key={h} value={h}>{h} 時間</option>
              ))}
            </select>
          </label>
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-bold">学習しない曜日</span>
            <div className="flex gap-2">
              {WEEKDAYS.map((w, i) => {
                const on = excluded.includes(i);
                return (
                  <button
                    key={w}
                    type="button"
                    onClick={() => setExcluded(on ? excluded.filter((x) => x !== i) : [...excluded, i])}
                    className={`h-8 w-9 rounded-full text-xs font-bold ${on ? "bg-blue-50 text-blue-700" : "bg-slate-100 text-slate-600"}`}
                  >
                    {w}{on ? "×" : ""}
                  </button>
                );
              })}
            </div>
            <span className="text-xs text-slate-500">祝日・年末年始（12/29〜1/3）は自動で除外します</span>
          </div>
        </Card>

        <div className="flex flex-col gap-2 rounded-xl bg-slate-900 p-5 text-white">
          <span className="text-xs text-slate-400">学習できる時間（最大）</span>
          <span className="text-4xl font-bold">{avail ? `${avail.max_hours} h` : "—"}</span>
          {avail && (
            <span className="text-xs text-slate-300">
              学習できる日 {avail.available_days} 日 × {hpd}h（祝日・休みなど {avail.excluded_days} 日を除外）
            </span>
          )}
          <span className="text-xs text-slate-300">学習・復習・予備の配分は、教材の参考時間をもとに AI が決めます</span>
        </div>

        {error && (
          <Alert tone="orange" title={error.message}>
            {error.suggestions.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-2">
                {error.suggestions.map((s) => (
                  <button key={s} onClick={() => { setTopic(s); submit(s); }} className="rounded-full bg-white px-3 py-1 text-xs font-bold text-blue-700">
                    {s}
                  </button>
                ))}
              </div>
            )}
          </Alert>
        )}
        <Alert tone="purple" title="次の画面で AI が提案します">
          教材（公式ドキュメント・記事・動画など）を探し、それぞれの参考時間を読み取って、学ぶ順番と日別のスケジュールを作ります。
        </Alert>
        {submitting ? (
          <Spinner label="AI が教材を探し、スケジュールを作っています…" />
        ) : (
          <Button className="h-12 text-[15px]" disabled={!topic.trim() || !avail?.available_days} onClick={() => submit()}>
            AI に教材とスケジュールを提案してもらう
          </Button>
        )}
      </div>
    </div>
  );
}

function LevelPicker({
  label, value, onChange, min = 1, tone,
}: { label: string; value: number; onChange: (v: number) => void; min?: number; tone: "blue" | "green" }) {
  const sel = tone === "blue" ? "border-2 border-blue-600 bg-blue-50 text-blue-700" : "border-2 border-green-700 bg-green-50 text-green-700";
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-bold">{label}</span>
      <div className="flex gap-2">
        {LEVEL_NAMES.map((name, i) => {
          const lv = i + 1;
          return (
            <button
              key={lv}
              type="button"
              disabled={lv < min}
              onClick={() => onChange(lv)}
              className={`flex flex-1 flex-col items-center rounded-lg py-2.5 text-xs disabled:opacity-40 ${value === lv ? sel : "border border-slate-300 bg-white"}`}
            >
              <b className="text-[15px]">Lv{lv}</b>
              {name}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function DateField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex flex-1 flex-col gap-1.5">
      <span className="text-sm font-bold">{label}</span>
      <input type="date" value={value} onChange={(e) => onChange(e.target.value)} className="h-11 rounded-lg border border-slate-300 px-3 text-sm" />
    </label>
  );
}
