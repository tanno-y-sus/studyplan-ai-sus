"use client";

// S03 プラン作成フォーム（02-1 入力・単元正規化 / 02-2 スキル判定）

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AIStatusNote } from "@/components/AIStatusNote";
import { AppShell } from "@/components/AppShell";
import { Alert, Badge, Button, Card, Spinner } from "@/components/ui";
import { api, ApiError, type ExamArea, type Plan } from "@/lib/api";

interface Suggestion {
  name: string;
  category: string;
  in_catalog: boolean;
}
interface Availability {
  available_days: number;
  excluded_days: number;
  max_hours: number;
}
interface SkillItem {
  text: string;
  level: number;
}
interface Checklist {
  topic: string;
  category: string;
  kind: Kind;
  items: SkillItem[];
  purpose_levels: Record<Purpose, number>;
  areas: ExamArea[];
  syllabus_url: string | null;
  areas_reviewed: boolean;
}
type Purpose = "exam" | "work" | "basics" | "other";
type Kind = "skill" | "exam";

const PURPOSES: { value: Purpose; label: string }[] = [
  { value: "work", label: "業務で使う" },
  { value: "exam", label: "資格を取る" },
  { value: "basics", label: "基礎を知る" },
  { value: "other", label: "その他" },
];
const MAX_TOPICS = 5;
const WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"];

/** 単元1つ分の入力 */
interface TopicDraft {
  key: number;
  kind: Kind;
  examDate: string; // 空ならプランの終了日
  input: string;
  checklist: Checklist | null;
  loading: boolean;
  error: ApiError | null;
  purpose: Purpose;
  note: string;
  canDo: string[];
  goals: string[];
}

function newDraft(key: number): TopicDraft {
  return { key, kind: "skill", examDate: "", input: "", checklist: null, loading: false, error: null, purpose: "work", note: "", canDo: [], goals: [] };
}

/** 目的に合わせて、最初からチェックを入れる「できるようになりたいこと」 */
function defaultGoals(c: Checklist, purpose: Purpose, canDo: string[]): string[] {
  const upto = c.purpose_levels[purpose] ?? 0;
  return c.items.filter((i) => i.level <= upto && !canDo.includes(i.text)).map((i) => i.text);
}

/** サーバーと同じ計算で、チェックからレベルの目安を出す（表示用） */
function estimate(c: Checklist, canDo: string[], goals: string[]): [number, number] {
  let current = 1;
  for (let lv = 1; lv <= 5; lv++) {
    const below = c.items.filter((i) => i.level <= lv);
    if (below.length > 0 && below.every((i) => canDo.includes(i.text))) current = lv;
    else break;
  }
  const wanted = c.items.filter((i) => goals.includes(i.text)).map((i) => i.level);
  const target = wanted.length ? Math.max(...wanted) : current + 1;
  return [current, Math.max(Math.min(target, 5), current)];
}

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
  const [topics, setTopics] = useState<TopicDraft[]>([newDraft(0)]);
  const [nextKey, setNextKey] = useState(1);
  const [start, setStart] = useState(isoAfter(1));
  const [end, setEnd] = useState(isoAfter(29));
  const [hpd, setHpd] = useState(2);
  const [excluded, setExcluded] = useState<number[]>([5, 6]);
  const [avail, setAvail] = useState<Availability | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    if (!start || !end || end < start) return setAvail(null);
    api<Availability>(
      `/availability?start_date=${start}&end_date=${end}&hours_per_day=${hpd}&excluded_weekdays=${excluded.join(",")}`,
    )
      .then(setAvail)
      .catch(() => setAvail(null));
  }, [start, end, hpd, excluded]);

  const update = (key: number, patch: Partial<TopicDraft>) =>
    setTopics((list) => list.map((t) => (t.key === key ? { ...t, ...patch } : t)));

  const confirmTopic = async (key: number, text: string) => {
    if (!text.trim()) return;
    const kind = topics.find((t) => t.key === key)?.kind ?? "skill";
    update(key, { input: text, loading: true, error: null, checklist: null });
    try {
      const c = await api<Checklist>(`/topics/checklist?topic=${encodeURIComponent(text.trim())}&kind=${kind}`);
      setTopics((list) => {
        if (list.some((t) => t.key !== key && t.checklist?.topic === c.topic)) {
          return list.map((t) =>
            t.key === key ? { ...t, loading: false, error: new ApiError(`「${c.topic}」はすでに入っています`, 422) } : t,
          );
        }
        return list.map((t) =>
          t.key === key
            ? { ...t, input: c.topic, checklist: c, loading: false, canDo: [], goals: defaultGoals(c, t.purpose, []) }
            : t,
        );
      });
    } catch (e) {
      update(key, { loading: false, error: e instanceof ApiError ? e : new ApiError("単元を確認できませんでした", 0) });
    }
  };

  const examDateOk = (t: TopicDraft) => !t.examDate || (t.examDate > start && t.examDate <= end);
  const ready = topics.every((t) => t.checklist && (t.kind === "exam" ? examDateOk(t) : t.goals.length > 0));

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const plan = await api<Plan>("/plans", {
        method: "POST",
        body: JSON.stringify({
          topics: topics.map((t) => ({
            topic: t.checklist?.topic ?? t.input,
            kind: t.kind,
            exam_date: t.kind === "exam" ? t.examDate || null : null,
            purpose: t.kind === "exam" ? "exam" : t.purpose,
            purpose_note: t.purpose === "other" ? t.note || null : null,
            can_do: t.canDo,
            goals: t.goals,
          })),
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
    <div className="flex flex-col gap-6 lg:flex-row">
      <div className="flex min-w-0 flex-1 flex-col gap-5">
        {topics.map((t, i) => (
          <TopicCard
            key={t.key}
            index={i}
            draft={t}
            planStart={start}
            planEnd={end}
            canRemove={topics.length > 1}
            onChange={(patch) => update(t.key, patch)}
            onConfirm={(text) => confirmTopic(t.key, text)}
            onRemove={() => setTopics((list) => list.filter((x) => x.key !== t.key))}
          />
        ))}
        {topics.length < MAX_TOPICS ? (
          <Button
            variant="secondary"
            className="self-start"
            onClick={() => {
              setTopics((list) => [...list, newDraft(nextKey)]);
              setNextKey(nextKey + 1);
            }}
          >
            ＋ 単元を追加（あと {MAX_TOPICS - topics.length} 件）
          </Button>
        ) : (
          <span className="text-xs text-slate-500">単元は {MAX_TOPICS} 件までです</span>
        )}
      </div>

      <div className="flex w-full flex-col gap-5 lg:w-[400px] lg:shrink-0">
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
            <div className="flex flex-wrap gap-2">
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
          <span className="text-xs text-slate-300">
            {topics.length > 1 ? "単元の順番・並行して進めるか・時間配分は" : "学習・復習・予備の配分は"}、教材の参考時間をもとに AI が決めます
          </span>
        </div>

        {error && <Alert tone="orange" title={error.message} />}
        <Alert tone="purple" title="次の画面で AI が提案します">
          単元ごとに教材（公式ドキュメント・記事・動画など）を探し、参考時間を読み取って、学ぶ順番と日別のスケジュールを作ります。
        </Alert>
        {submitting ? (
          <Spinner label="AI が教材を探し、スケジュールを作っています…" />
        ) : (
          <Button className="h-12 text-[15px]" disabled={!ready || !avail?.available_days} onClick={submit}>
            AI に教材とスケジュールを提案してもらう
          </Button>
        )}
        {!ready && (
          <span className="text-xs text-slate-500">
            各単元の「決定」が必要です（技術の単元は、できるようになりたいことのチェックも1つ以上。資格試験の試験日はプランの期間内）
          </span>
        )}
        <AIStatusNote />
      </div>
    </div>
  );
}

function TopicCard({
  index,
  draft,
  planStart,
  planEnd,
  canRemove,
  onChange,
  onConfirm,
  onRemove,
}: {
  index: number;
  draft: TopicDraft;
  planStart: string;
  planEnd: string;
  canRemove: boolean;
  onChange: (patch: Partial<TopicDraft>) => void;
  onConfirm: (text: string) => void;
  onRemove: () => void;
}) {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggest, setShowSuggest] = useState(false);
  const c = draft.checklist;

  useEffect(() => {
    if (c) return;
    const t = setTimeout(() => {
      api<Suggestion[]>(`/topics/suggest?q=${encodeURIComponent(draft.input)}`).then(setSuggestions).catch(() => {});
    }, 200);
    return () => clearTimeout(t);
  }, [draft.input, c]);

  const toggle = (list: string[], text: string) => (list.includes(text) ? list.filter((x) => x !== text) : [...list, text]);
  const [cur, tgt] = c ? estimate(c, draft.canDo, draft.goals) : [0, 0];

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-bold">単元 {index + 1}{c && <span className="ml-2 text-blue-700">{c.topic}</span>}</h2>
        <div className="flex gap-1">
          {c && (
            <Button variant="ghost" className="h-8 px-2" onClick={() => onChange({ checklist: null, canDo: [], goals: [] })}>
              {draft.kind === "exam" ? "試験を変える" : "単元を変える"}
            </Button>
          )}
          {canRemove && (
            <Button variant="ghost" className="h-8 px-2 text-red-600" onClick={onRemove}>
              削除
            </Button>
          )}
        </div>
      </div>

      {!c && (
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-bold">何のための学習ですか？</span>
          <div className="grid grid-cols-2 gap-2">
            {(
              [
                ["skill", "技術・ツールを学ぶ", "業務で使う言語・クラウド・ツールなど"],
                ["exam", "資格試験の対策", "出題範囲をすべて網羅するスケジュール"],
              ] as const
            ).map(([k, label, sub]) => (
              <button
                key={k}
                type="button"
                onClick={() => onChange({ kind: k, error: null })}
                className={`flex flex-col items-start rounded-lg px-3 py-2.5 text-left ${draft.kind === k ? "border-2 border-blue-600 bg-blue-50" : "border border-slate-300 bg-white"}`}
              >
                <b className="text-sm">{label}</b>
                <span className="text-[11px] text-slate-500">{sub}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {!c && (
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-bold">{draft.kind === "exam" ? "資格試験の名前" : "学習したい単元（IT技術）"}</span>
          <div className="flex gap-2">
            <div className="relative min-w-0 flex-1">
              <input
                value={draft.input}
                onChange={(e) => onChange({ input: e.target.value, error: null })}
                onFocus={() => setShowSuggest(true)}
                onBlur={() => setTimeout(() => setShowSuggest(false), 150)}
                onKeyDown={(e) => e.key === "Enter" && onConfirm(draft.input)}
                placeholder={draft.kind === "exam" ? "例：基本情報技術者試験、AWS 認定ソリューションアーキテクト …" : "例：Java、SQL、AWS（EC2・VPC）、Docker、React …"}
                className="h-11 w-full rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-2 focus:border-blue-600"
              />
              {showSuggest && suggestions.length > 0 && (
                <div className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
                  {suggestions.map((s) => (
                    <button
                      key={s.name}
                      type="button"
                      onMouseDown={() => onConfirm(s.name)}
                      className="flex w-full items-center justify-between gap-2 border-b border-slate-100 px-3 py-2.5 text-left text-sm hover:bg-blue-50"
                    >
                      <span className="min-w-0">
                        <b>{s.name}</b> <span className="text-slate-500">（{s.category}）</span>
                      </span>
                      {s.in_catalog ? <Badge tone="blue">カタログあり</Badge> : <Badge tone="purple">AI探索</Badge>}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <Button disabled={!draft.input.trim() || draft.loading} onClick={() => onConfirm(draft.input)}>
              決定
            </Button>
          </div>
          <span className="text-xs text-slate-500">
            {draft.kind === "exam"
              ? "決定すると、試験の出題範囲（分野）の一覧を表示します。試験全体を1つの単元として、全分野を網羅するスケジュールを作ります"
              : "決定すると、この単元の「できること」の一覧を表示します（初めての単元は AI が作ります）"}
          </span>
          {draft.loading && <Spinner label="単元を確認しています…" />}
          {draft.error && (
            <Alert tone="orange" title={draft.error.message}>
              {draft.error.suggestions.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-2">
                  {draft.error.suggestions.map((s) => (
                    <button key={s} onClick={() => onConfirm(s)} className="rounded-full bg-white px-3 py-1 text-xs font-bold text-blue-700">
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </Alert>
          )}
        </div>
      )}

      {c && c.kind === "exam" && (
        <ExamDetail checklist={c} examDate={draft.examDate} planStart={planStart} planEnd={planEnd} onDate={(v) => onChange({ examDate: v })} />
      )}

      {c && c.kind !== "exam" && (
        <>
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-bold">学ぶ目的</span>
            <div className="flex flex-wrap gap-2">
              {PURPOSES.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => onChange({ purpose: p.value, goals: p.value === "other" ? draft.goals : defaultGoals(c, p.value, draft.canDo) })}
                  className={`h-9 rounded-full px-4 text-sm font-bold ${draft.purpose === p.value ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-700"}`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            {draft.purpose === "other" && (
              <input
                value={draft.note}
                maxLength={300}
                onChange={(e) => onChange({ note: e.target.value })}
                placeholder="例：次の案件で EC2 上に Web アプリを構築する"
                className="h-10 rounded-lg border border-slate-300 px-3 text-sm"
              />
            )}
            <span className="text-xs text-slate-500">目的を選ぶと、それに合う「できるようになりたいこと」に最初からチェックが入ります（自由に変えられます）</span>
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-end justify-between gap-2">
              <span className="text-sm font-bold">できること</span>
              <span className="text-xs text-slate-500">
                目安：<b className="text-blue-700">Lv{cur}</b> → <b className="text-green-700">Lv{tgt}</b>
              </span>
            </div>
            <div className="overflow-hidden rounded-lg border border-slate-200">
              <div className="grid grid-cols-[1fr_64px_64px] bg-slate-50 px-3 py-2 text-[11px] font-bold text-slate-500 sm:grid-cols-[1fr_88px_88px]">
                <span>易しい順</span>
                <span className="text-center text-blue-700">今できる</span>
                <span className="text-center text-green-700">できるように<br className="sm:hidden" />なりたい</span>
              </div>
              {c.items.map((item) => {
                const can = draft.canDo.includes(item.text);
                const want = draft.goals.includes(item.text);
                return (
                  <div key={item.text} className="grid grid-cols-[1fr_64px_64px] items-center border-t border-slate-100 px-3 py-2.5 text-sm sm:grid-cols-[1fr_88px_88px]">
                    <span className={`min-w-0 ${can ? "text-slate-400" : ""}`}>{item.text}</span>
                    <span className="flex justify-center">
                      <input
                        type="checkbox"
                        aria-label={`今できる：${item.text}`}
                        className="h-5 w-5 accent-blue-600"
                        checked={can}
                        onChange={() => onChange({ canDo: toggle(draft.canDo, item.text), goals: draft.goals.filter((g) => g !== item.text) })}
                      />
                    </span>
                    <span className="flex justify-center">
                      <input
                        type="checkbox"
                        aria-label={`できるようになりたい：${item.text}`}
                        className="h-5 w-5 accent-green-700 disabled:opacity-30"
                        checked={want}
                        disabled={can}
                        onChange={() => onChange({ goals: toggle(draft.goals, item.text) })}
                      />
                    </span>
                  </div>
                );
              })}
            </div>
            {draft.goals.length === 0 && <span className="text-xs text-orange-700">できるようになりたいことを1つ以上選んでください</span>}
          </div>
        </>
      )}
    </Card>
  );
}

function ExamDetail({
  checklist: c,
  examDate,
  planStart,
  planEnd,
  onDate,
}: {
  checklist: Checklist;
  examDate: string;
  planStart: string;
  planEnd: string;
  onDate: (v: string) => void;
}) {
  const total = c.areas.reduce((s, a) => s + a.est_hours, 0);
  const bad = examDate !== "" && !(examDate > planStart && examDate <= planEnd);
  return (
    <>
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-bold">試験日</span>
        <input
          type="date"
          value={examDate}
          min={planStart}
          max={planEnd}
          onChange={(e) => onDate(e.target.value)}
          className="h-11 rounded-lg border border-slate-300 px-3 text-sm sm:w-60"
        />
        <span className={`text-xs ${bad ? "text-orange-700" : "text-slate-500"}`}>
          {bad ? "試験日はプランの期間内（開始日の翌日〜終了日）にしてください" : "空欄ならプランの終了日を試験日にします。試験日より後には、この試験の予定を入れません"}
        </span>
      </label>
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <span className="text-sm font-bold">出題範囲（{c.areas.length} 分野・すべてスケジュールに入れます）</span>
          <span className="text-xs text-slate-500">目安 合計 {Math.round(total * 10) / 10}h</span>
        </div>
        {c.areas_reviewed ? (
          <Alert tone="green" title="育成担当が確認済みの出題範囲です" />
        ) : (
          <Alert tone="purple" title="AI が作った一覧です（育成担当の確認前）">
            最新のシラバスとずれていることがあります。育成担当が「AI提案レビュー」で確認・修正します
          </Alert>
        )}
        {c.syllabus_url && (
          <a href={c.syllabus_url} target="_blank" rel="noreferrer" className="text-xs font-bold text-blue-600 hover:underline">
            公式のシラバス・出題範囲を見る ↗
          </a>
        )}
        <div className="overflow-hidden rounded-lg border border-slate-200">
          <div className="grid grid-cols-[1fr_56px_56px] bg-slate-50 px-3 py-2 text-[11px] font-bold text-slate-500">
            <span>分野</span>
            <span className="text-right">比重</span>
            <span className="text-right">目安</span>
          </div>
          {c.areas.map((a) => (
            <div key={a.name} className="grid grid-cols-[1fr_56px_56px] items-center border-t border-slate-100 px-3 py-2 text-sm">
              <span className="min-w-0">
                {a.name}
                {a.description && <span className="block text-[11px] text-slate-500">{a.description}</span>}
              </span>
              <span className="text-right text-xs text-slate-600">{a.weight}%</span>
              <span className="text-right text-xs text-slate-600">{a.est_hours}h</span>
            </div>
          ))}
        </div>
        <span className="text-xs text-slate-500">試験日前の期間に、過去問演習と模擬試験も AI が入れます</span>
      </div>
    </>
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
