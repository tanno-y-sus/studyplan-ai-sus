"use client";

// S08 AI提案レビュー（AI が探した教材を育成担当が確認し、承認するとカタログに登録される）

import { useCallback, useEffect, useMemo, useState } from "react";

import { AIStatusNote } from "@/components/AIStatusNote";
import { AppShell } from "@/components/AppShell";
import { ExamAreasReview } from "@/components/ExamAreasReview";
import { Alert, Badge, Bar, Button, Card } from "@/components/ui";
import { api, SOURCE_LABEL, TYPE_LABEL, type ReviewMaterial, type Usage } from "@/lib/api";

const USAGE_LABEL: Record<string, string> = {
  tavily: "Tavily（今月）",
  youtube: "YouTube Data API（今日）",
  qiita: "Qiita API（この1時間）",
  gemini: "AI（Gemini 無料枠・今日）",
  demo: "デモ検索（今日）",
};

export default function ReviewPage() {
  const [items, setItems] = useState<ReviewMaterial[] | null>(null);
  const [usage, setUsage] = useState<Usage[]>([]);
  const [topic, setTopic] = useState<string | null>(null);
  const [comment, setComment] = useState("");

  const load = useCallback(async () => {
    const list = await api<ReviewMaterial[]>("/review/materials");
    setItems(list);
    setUsage(await api<Usage[]>("/usage"));
    setTopic((t) => (t && list.some((m) => m.topic === t) ? t : (list[0]?.topic ?? null)));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const topics = useMemo(() => {
    const map = new Map<string, ReviewMaterial[]>();
    for (const m of items ?? []) map.set(m.topic, [...(map.get(m.topic) ?? []), m]);
    return map;
  }, [items]);
  const selected = topic ? (topics.get(topic) ?? []) : [];

  const decideAll = async (action: "approve" | "reject") => {
    for (const m of selected) {
      await api(`/review/materials/${m.id}/${action}`, { method: "POST", body: JSON.stringify({ comment: comment || null }) });
    }
    setComment("");
    load();
  };

  return (
    <AppShell crumb={<><b className="text-slate-900">AI提案レビュー</b> ／ 教材のレビュー待ち {topics.size} 件</>}>
      <ExamAreasReview />
      <div className="flex flex-col gap-5 lg:flex-row">
        <div className="flex w-full flex-col gap-3.5 lg:w-[330px] lg:shrink-0">
          <Card className="flex flex-col gap-2 p-3">
            <span className="px-2 py-1 text-sm font-bold">レビュー待ち</span>
            {topics.size === 0 && <p className="px-2 text-sm text-slate-500">レビュー待ちはありません</p>}
            {[...topics.entries()].map(([name, list]) => (
              <button
                key={name}
                onClick={() => setTopic(name)}
                className={`flex items-center justify-between rounded-xl border p-3 text-left ${name === topic ? "border-2 border-violet-600 bg-violet-50" : "border-slate-200 bg-white"}`}
              >
                <span>
                  <b className="text-sm">{name}</b>
                  <br />
                  <span className="text-xs text-slate-500">教材 {list.length} 件</span>
                </span>
                <Badge tone="purple">AI</Badge>
              </button>
            ))}
          </Card>
          <Card className="flex flex-col gap-2.5 p-4">
            <span className="text-sm font-bold">API の利用状況（無料枠）</span>
            <AIStatusNote detail />
            {usage.length === 0 && <span className="text-xs text-slate-500">まだ利用はありません</span>}
            {usage.map((u) => (
              <div key={u.provider} className="flex flex-col gap-1 text-xs">
                <div className="flex justify-between">
                  <span>{USAGE_LABEL[u.provider] ?? u.provider}</span>
                  <span className="text-slate-500">{u.count} / {u.limit.toLocaleString()}</span>
                </div>
                <Bar percent={(u.count / u.limit) * 100} color={u.provider === "gemini" ? "bg-violet-600" : "bg-blue-600"} />
              </div>
            ))}
            <span className="text-[11px] text-slate-500">上限に達した検索 API は飛ばして、次の検索 API を使います</span>
          </Card>
        </div>

        <div className="flex flex-1 flex-col gap-4">
          {topic && (
            <>
              <div className="flex items-end justify-between gap-4">
                <h1 className="text-2xl font-bold">{topic}</h1>
                <div className="flex gap-2">
                  <Button variant="danger" onClick={() => decideAll("reject")}>却下</Button>
                  <Button variant="ok" onClick={() => decideAll("approve")}>承認してカタログに登録</Button>
                </div>
              </div>
              <Card className="overflow-hidden p-0">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs text-slate-500">
                    <tr>
                      <th className="px-3 py-2.5">種類</th>
                      <th className="px-3 py-2.5">教材</th>
                      <th className="px-3 py-2.5">取得元</th>
                      <th className="px-3 py-2.5">URL検証</th>
                      <th className="px-3 py-2.5">参考時間（根拠）</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.map((m) => (
                      <tr key={m.id} className="border-b border-slate-100 align-top">
                        <td className="whitespace-nowrap px-3 py-3">{TYPE_LABEL[m.type] ?? m.type}</td>
                        <td className="px-3 py-3">
                          <b>{m.title}</b> {m.supplementary && <Badge tone="gray">補助</Badge>}
                          <br />
                          {m.url && <span className="text-xs text-slate-500">{m.url}</span>}
                          {m.comment && <p className="mt-1 text-xs text-slate-600">{m.comment}</p>}
                          {m.sections.length > 0 && (
                            <p className="mt-1 text-xs text-slate-500">
                              節：{m.sections.map((s) => `${s.title}（${s.est_hours}h・Lv${s.level_from}-${s.level_to}）`).join(" / ")}
                            </p>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-3 py-3 text-xs">{SOURCE_LABEL[m.source] ?? m.source}</td>
                        <td className="px-3 py-3">
                          <Badge tone={m.url_check.includes("OK") ? "green" : m.url_check.includes("デモ") ? "gray" : "orange"}>{m.url_check}</Badge>
                        </td>
                        <td className="px-3 py-3">
                          {m.reference_hours}h
                          <br />
                          <span className="text-xs text-slate-500">{m.reference_basis}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
              <Card className="flex flex-col gap-2">
                <h2 className="font-bold">レビューコメント</h2>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="修正点や承認理由を記入（任意）"
                  className="h-24 rounded-lg border border-slate-300 p-2.5 text-sm"
                />
              </Card>
              <Alert tone="gray">承認すると、この単元の教材としてカタログに登録され、次からはカタログから提案されます。</Alert>
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
