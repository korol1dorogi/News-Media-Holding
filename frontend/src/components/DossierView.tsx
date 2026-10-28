import { useState } from "react";
import type { Dossier } from "../types";
import { CHECK_TITLES, LEVELS, STATUSES } from "./labels";

interface Props {
  dossier: Dossier;
  onShowPost: (postId: string) => void;
}

function evidenceText(item: Record<string, unknown>): string {
  return typeof item.note === "string" ? item.note : "";
}

export default function DossierView({ dossier, onShowPost }: Props) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [done, setDone] = useState<Record<number, boolean>>({});
  const level = LEVELS[dossier.level];

  return (
    <section className="space-y-4">
      <div className={`rounded-lg p-4 ring-1 ${level.chip}`}>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`h-3 w-3 rounded-full ${level.dot}`} />
          <span className="font-semibold">{level.title}</span>
          <span className="text-sm">— {level.hint}</span>
        </div>
        <p className="mt-1 text-sm">
          Независимых источников: <b>{dossier.independent_sources}</b> · первоисточник:{" "}
          <button
            type="button"
            className="underline decoration-dotted"
            onClick={() => onShowPost(dossier.first_source_post_id)}
          >
            {dossier.first_source_post_id}
          </button>
        </p>
      </div>

      <ul className="space-y-2">
        {dossier.checks.map((check) => {
          const status = STATUSES[check.status];
          const isOpen = open[check.name] ?? check.status === "fail";
          return (
            <li key={check.name} className="rounded-lg border border-slate-200 bg-white p-3">
              <button
                type="button"
                className="flex w-full items-start justify-between gap-3 text-left"
                onClick={() => setOpen({ ...open, [check.name]: !isOpen })}
              >
                <span>
                  <span className="font-medium">{CHECK_TITLES[check.name] ?? check.name}</span>
                  <span className="block text-sm text-slate-700">{check.summary}</span>
                </span>
                <span className={`shrink-0 rounded px-2 py-0.5 text-xs ring-1 ${status.chip}`}>
                  {status.title}
                </span>
              </button>
              {isOpen && check.evidence.length > 0 && (
                <ul className="mt-2 space-y-1 border-t border-slate-100 pt-2 text-sm">
                  {check.evidence.map((item, index) => (
                    <li key={index} className="flex flex-wrap gap-2">
                      {typeof item.post_id === "string" && (
                        <button
                          type="button"
                          className="font-mono text-xs text-blue-700 underline"
                          onClick={() => onShowPost(item.post_id as string)}
                        >
                          {item.post_id}
                        </button>
                      )}
                      {typeof item.archive_id === "string" && (
                        <span className="font-mono text-xs text-slate-500">{item.archive_id}</span>
                      )}
                      <span className="text-slate-600">{evidenceText(item)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>

      {dossier.todo.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <h3 className="mb-2 font-medium">Что проверить руками</h3>
          <ul className="space-y-1 text-sm">
            {dossier.todo.map((item, index) => (
              <li key={index}>
                <label className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={done[index] ?? false}
                    onChange={() => setDone({ ...done, [index]: !done[index] })}
                  />
                  <span className={done[index] ? "text-slate-400 line-through" : ""}>{item}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
