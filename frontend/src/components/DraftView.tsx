import { useState } from "react";
import type { Claim, Draft } from "../types";

interface Props {
  draft: Draft;
  onShowPost: (postId: string) => void;
}

type Segment = { text: string; claim?: Claim };

// Claims come in text order; each one is matched after the previous match.
function segments(text: string, claims: Claim[]): Segment[] {
  const result: Segment[] = [];
  let cursor = 0;
  for (const claim of claims) {
    const start = text.indexOf(claim.text, cursor);
    if (start < 0) continue;
    if (start > cursor) result.push({ text: text.slice(cursor, start) });
    result.push({ text: claim.text, claim });
    cursor = start + claim.text.length;
  }
  if (cursor < text.length) result.push({ text: text.slice(cursor) });
  return result;
}

export default function DraftView({ draft, onShowPost }: Props) {
  const [copied, setCopied] = useState(false);
  const unsupported = draft.claims.filter((claim) => !claim.supported).length;

  async function copy() {
    try {
      await navigator.clipboard.writeText(draft.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="text-slate-600">
          Утверждений: {draft.claims.length} · не подтверждено:{" "}
          <b className={unsupported ? "text-red-700" : "text-emerald-700"}>{unsupported}</b>
        </span>
        <button
          type="button"
          onClick={copy}
          className="rounded border border-slate-300 bg-white px-3 py-1 hover:bg-slate-50"
        >
          {copied ? "Скопировано" : "Скопировать черновик"}
        </button>
      </div>

      {draft.warnings.length > 0 && (
        <ul className="space-y-1 rounded-lg bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-200">
          {draft.warnings.map((warning, index) => (
            <li key={index}>⚠ {warning}</li>
          ))}
        </ul>
      )}

      <div className="whitespace-pre-line rounded-lg border border-slate-200 bg-white p-4 leading-relaxed">
        {segments(draft.text, draft.claims).map((segment, index) =>
          segment.claim ? (
            <mark
              key={index}
              className={
                segment.claim.supported
                  ? "cursor-pointer rounded bg-emerald-50 underline decoration-emerald-400 decoration-dotted"
                  : "rounded bg-red-200 px-0.5 font-semibold text-red-900"
              }
              title={
                segment.claim.supported
                  ? `Подтверждено: ${segment.claim.source_post_ids.join(", ")}`
                  : "Не найдено ни в одном источнике"
              }
              onClick={() => {
                const first = segment.claim?.source_post_ids[0];
                if (first) onShowPost(first);
              }}
            >
              {segment.text}
            </mark>
          ) : (
            <span key={index}>{segment.text}</span>
          ),
        )}
      </div>
      <p className="text-xs text-slate-500">
        Зелёным подчёркнуты утверждения, найденные в источниках (клик — к посту). Красным —
        не найденные. Публикует только редактор.
      </p>
    </section>
  );
}
