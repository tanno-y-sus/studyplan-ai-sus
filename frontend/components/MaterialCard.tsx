import { Badge } from "@/components/ui";
import { SOURCE_LABEL, TYPE_LABEL, type Material } from "@/lib/api";

export function MaterialCard({ m }: { m: Material }) {
  const basisKind = m.reference_basis.startsWith("ページに記載")
    ? "ページに記載"
    : m.reference_basis.startsWith("動画の長さ")
      ? "動画の長さ"
      : "AI推定";
  return (
    <div className="flex gap-3.5 rounded-xl border border-slate-200 bg-white px-3.5 py-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-[11px] font-bold text-slate-600">
        {TYPE_LABEL[m.type] ?? m.type}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-bold">{m.title}</span>
          {m.supplementary && <Badge tone="gray">補助教材</Badge>}
          {m.status === "approved" ? <Badge tone="blue">カタログ</Badge> : <Badge tone="purple">AI提案（未レビュー）</Badge>}
        </div>
        {m.url && (
          <a href={m.url} target="_blank" rel="noreferrer" className="truncate text-xs text-blue-600">
            {m.url}
            {m.source !== "catalog" && ` ・ 取得元：${SOURCE_LABEL[m.source] ?? m.source}`}
          </a>
        )}
        {m.sections.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {m.sections.slice(0, 8).map((s) => (
              <span key={s} className="rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[11px] text-slate-600">
                {s}
              </span>
            ))}
            {m.sections.length > 8 && <span className="text-[11px] text-slate-500">ほか {m.sections.length - 8} 件</span>}
          </div>
        )}
        <span className="text-xs text-slate-500">
          参考時間：<b>{basisKind}</b>（{m.reference_basis}）
        </span>
      </div>
      <div className="whitespace-nowrap text-xl font-bold">{m.reference_hours}h</div>
    </div>
  );
}
