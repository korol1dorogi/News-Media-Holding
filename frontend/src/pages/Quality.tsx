import { useEffect, useState } from "react";
import { getMetrics } from "../api";
import type { Metrics } from "../types";

// Shapes written by scripts/eval.py (task S2). Every field is optional: the page must
// survive an empty {} before make eval.
interface Summary {
  posts?: number;
  events_in_feed?: number;
  truth_events?: number;
  truth_events_found?: number;
  posts_per_event?: number;
  posts_left_as_noise?: number;
  cluster_recall_mean?: number;
  cluster_purity_mean?: number;
  minutes_to_signal_median?: number;
  minutes_to_signal_max?: number;
  dossier_level_accuracy?: number;
  expected_fail_accuracy?: number;
  first_source_accuracy?: number;
  independent_sources_accuracy?: number;
  llm_calls_feed_per_100_posts?: number;
  llm_calls_per_draft?: number;
  claim_check_injected_caught?: string;
  claim_check_false_alarms?: number;
}

interface EventRow {
  key: string;
  found: boolean;
  level?: string;
  expected_level?: string | null;
  level_ok?: boolean;
  fail_ok?: boolean;
  minutes_to_signal?: number;
  independent?: number;
  independent_ok?: boolean;
  first_source_ok?: boolean;
}

interface Ablation {
  without: string;
  level_accuracy: number | null;
  changed?: string[];
}

interface Scoring {
  outlet: string;
  manual_auc: number;
  learned_auc: number;
  learned_weights: Record<string, number>;
}

const CHECK_TITLES: Record<string, string> = {
  provenance: "Первоисточник и независимые источники",
  media_archive: "Фото по архиву",
  weather: "Погода на фото",
  official: "Официальные каналы",
};

function percent(value: number | undefined): string {
  return value === undefined ? "—" : `${Math.round(value * 100)}%`;
}

function Stat({ title, value, hint }: { title: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-sm text-slate-700">{title}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export default function Quality() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMetrics()
      .then(setMetrics)
      .catch((reason: unknown) => setError(String(reason)));
  }, []);

  if (error) {
    return <p className="rounded-lg bg-red-50 p-3 text-red-800">Не удалось загрузить замеры: {error}</p>;
  }
  if (!metrics) return <p>Загружаем замеры…</p>;

  const summary = (metrics.summary ?? null) as Summary | null;
  if (!summary) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 p-6 text-slate-500">
        Замеров пока нет. Запустите <code>make eval</code> — отчёт появится здесь.
      </p>
    );
  }
  const events = (metrics.events ?? []) as EventRow[];
  const ablations = (metrics.ablations ?? []) as Ablation[];
  const scoring = (metrics.scoring ?? []) as Scoring[];
  const dataDir = typeof metrics.data_dir === "string" ? metrics.data_dir : "";

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-600">
        Замеры по разметке <code>truth.yaml</code> на синтетических данных ({dataDir}). Источник —{" "}
        <code>reports/metrics.json</code>, его пишет <code>make eval</code>.
      </p>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          title="минут от первого поста до ленты"
          value={`${summary.minutes_to_signal_median ?? "—"}`}
          hint={`медиана, максимум ${summary.minutes_to_signal_max ?? "—"}`}
        />
        <Stat
          title="точность уровня досье"
          value={percent(summary.dossier_level_accuracy)}
          hint={`демо-событий найдено ${summary.truth_events_found ?? "—"} из ${summary.truth_events ?? "—"}`}
        />
        <Stat
          title="сверка утверждений: ошибка поймана"
          value={summary.claim_check_injected_caught ?? "—"}
          hint={`ложных тревог: ${summary.claim_check_false_alarms ?? "—"}`}
        />
        <Stat
          title="вызовов LLM на 100 постов ленты"
          value={`${summary.llm_calls_feed_per_100_posts ?? "—"}`}
          hint={`на один черновик: ${summary.llm_calls_per_draft ?? "—"}`}
        />
        <Stat title="постов в потоке" value={`${summary.posts ?? "—"}`} />
        <Stat
          title="событий в ленте"
          value={`${summary.events_in_feed ?? "—"}`}
          hint={`отсеяно как шум: ${summary.posts_left_as_noise ?? "—"} постов`}
        />
        <Stat
          title="полнота / чистота кластеров"
          value={`${percent(summary.cluster_recall_mean)} / ${percent(summary.cluster_purity_mean)}`}
        />
        <Stat
          title="первоисточник найден верно"
          value={percent(summary.first_source_accuracy)}
          hint={`число источников верно: ${percent(summary.independent_sources_accuracy)}`}
        />
      </section>

      <section className="space-y-2">
        <h3 className="font-medium">Демо-события</h3>
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="p-2">Событие</th>
                <th className="p-2">Уровень</th>
                <th className="p-2">Ожидали</th>
                <th className="p-2">Совпало</th>
                <th className="p-2">Мин. до сигнала</th>
                <th className="p-2">Источников</th>
              </tr>
            </thead>
            <tbody>
              {events.map((row) => (
                <tr key={row.key} className="border-t border-slate-100">
                  <td className="p-2 font-mono text-xs">{row.key}</td>
                  <td className="p-2">{row.found ? row.level : "не найдено"}</td>
                  <td className="p-2">{row.expected_level ?? "—"}</td>
                  <td className="p-2">{row.found && row.level_ok && row.fail_ok ? "✓" : "✗"}</td>
                  <td className="p-2">{row.minutes_to_signal ?? "—"}</td>
                  <td className="p-2">
                    {row.independent ?? "—"} {row.independent_ok === false ? "✗" : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-2">
        <h3 className="font-medium">Абляции: что перестаём ловить без каждой проверки</h3>
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="p-2">Отключили</th>
                <th className="p-2">Точность уровня</th>
                <th className="p-2">Что изменилось</th>
              </tr>
            </thead>
            <tbody>
              {ablations.map((row) => (
                <tr key={row.without} className="border-t border-slate-100">
                  <td className="p-2">{CHECK_TITLES[row.without] ?? row.without}</td>
                  <td className="p-2">{percent(row.level_accuracy ?? undefined)}</td>
                  <td className="p-2">{row.changed?.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {scoring.length > 0 && (
        <section className="space-y-2">
          <h3 className="font-medium">Скоринг: ручные веса и обученная модель</h3>
          <p className="text-sm text-slate-600">
            ROC AUC на отложенных синтетических метках «опубликовано / нет». В продакшене метки
            даёт архив издания и кнопка «Опубликовать».
          </p>
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="p-2">Издание</th>
                  <th className="p-2">Ручные веса</th>
                  <th className="p-2">Обученная модель</th>
                  <th className="p-2">Что модель считает важным</th>
                </tr>
              </thead>
              <tbody>
                {scoring.map((row) => (
                  <tr key={row.outlet} className="border-t border-slate-100">
                    <td className="p-2">{row.outlet}</td>
                    <td className="p-2">{row.manual_auc}</td>
                    <td className="p-2">{row.learned_auc}</td>
                    <td className="p-2 text-xs">
                      {Object.entries(row.learned_weights)
                        .sort((a, b) => b[1] - a[1])
                        .map(([name, value]) => `${name} ${value}`)
                        .join(", ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
