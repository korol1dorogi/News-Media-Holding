import { useCallback, useEffect, useMemo, useState } from "react";
import { createDraft, getEvent, getEvents, resetReplay } from "../api";
import DossierView from "../components/DossierView";
import DraftView from "../components/DraftView";
import EventList from "../components/EventList";
import PostList from "../components/PostList";
import RepostGraph from "../components/RepostGraph";
import { LEVELS, OUTLETS } from "../components/labels";
import type { Draft, EventDetail, EventListItem, Level, Outlet } from "../types";

type Load<T> = { status: "idle" | "loading" | "error"; data: T | null; error?: string };

function message(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}

export default function EditorPage() {
  const [outlet, setOutlet] = useState<Outlet>("mash");
  const [levelFilter, setLevelFilter] = useState<Level | "all">("all");
  const [topicFilter, setTopicFilter] = useState<string>("all");
  const [feed, setFeed] = useState<Load<EventListItem[]>>({ status: "loading", data: null });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Load<EventDetail>>({ status: "idle", data: null });
  const [draft, setDraft] = useState<Load<Draft>>({ status: "idle", data: null });
  const [highlightPost, setHighlightPost] = useState<string | null>(null);

  const loadFeed = useCallback(() => {
    setFeed((prev) => ({ status: "loading", data: prev.data }));
    getEvents(outlet)
      .then((data) => setFeed({ status: "idle", data }))
      .catch((reason: unknown) => setFeed({ status: "error", data: null, error: message(reason) }));
  }, [outlet]);

  useEffect(loadFeed, [loadFeed]);

  useEffect(() => {
    setDraft({ status: "idle", data: null });
    setHighlightPost(null);
    if (!selectedId) return;
    setDetail({ status: "loading", data: null });
    getEvent(selectedId)
      .then((data) => setDetail({ status: "idle", data }))
      .catch((reason: unknown) =>
        setDetail({ status: "error", data: null, error: message(reason) }),
      );
  }, [selectedId]);

  useEffect(() => setDraft({ status: "idle", data: null }), [outlet]);

  const topics = useMemo(() => {
    const all = (feed.data ?? []).map((item) => item.event.topic).filter(Boolean) as string[];
    return [...new Set(all)].sort();
  }, [feed.data]);

  const visible = useMemo(
    () =>
      (feed.data ?? []).filter(
        (item) =>
          (levelFilter === "all" || item.level === levelFilter) &&
          (topicFilter === "all" || item.event.topic === topicFilter),
      ),
    [feed.data, levelFilter, topicFilter],
  );

  function showPost(postId: string) {
    setHighlightPost(postId);
    document.getElementById(`post-${postId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function makeDraft() {
    if (!selectedId) return;
    setDraft({ status: "loading", data: null });
    createDraft(selectedId, outlet)
      .then((data) => setDraft({ status: "idle", data }))
      .catch((reason: unknown) => setDraft({ status: "error", data: null, error: message(reason) }));
  }

  function rebuild() {
    setSelectedId(null);
    setDetail({ status: "idle", data: null });
    resetReplay()
      .then(loadFeed)
      .catch((reason: unknown) => setFeed({ status: "error", data: null, error: message(reason) }));
  }

  const outletTitle = OUTLETS.find((item) => item.id === outlet)?.title ?? outlet;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(320px,420px)_1fr]">
      <aside className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5">
            {OUTLETS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setOutlet(item.id)}
                className={`rounded-md px-3 py-1 text-sm ${
                  outlet === item.id ? "bg-slate-900 text-white" : "text-slate-700"
                }`}
              >
                {item.title}
              </button>
            ))}
          </div>
          <select
            value={levelFilter}
            onChange={(e) => setLevelFilter(e.target.value as Level | "all")}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm"
            aria-label="Уровень"
          >
            <option value="all">все уровни</option>
            {(Object.keys(LEVELS) as Level[]).map((level) => (
              <option key={level} value={level}>
                {LEVELS[level].title}
              </option>
            ))}
          </select>
          <select
            value={topicFilter}
            onChange={(e) => setTopicFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm"
            aria-label="Тема"
          >
            <option value="all">все темы</option>
            {topics.map((topic) => (
              <option key={topic} value={topic}>
                {topic}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={rebuild}
            className="ml-auto rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm hover:bg-slate-50"
            title="Пересобрать ленту из синтетики"
          >
            ↻ Пересобрать
          </button>
        </div>
        <p className="text-xs text-slate-500">
          Лента отсортирована по новостности для {outletTitle}. Цвет — уровень досье.
        </p>
        {feed.status === "error" && (
          <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800">
            Не удалось загрузить ленту: {feed.error}
          </p>
        )}
        {feed.status === "loading" && !feed.data && <p className="text-sm">Загружаем ленту…</p>}
        {feed.data && <EventList items={visible} selectedId={selectedId} onSelect={setSelectedId} />}
      </aside>

      <main className="min-w-0 space-y-6">
        {!selectedId && (
          <p className="rounded-lg border border-dashed border-slate-300 p-6 text-slate-500">
            Выберите событие в ленте: справа появится досье с проверкой на фейк, посты-источники
            и черновик под выбранное издание.
          </p>
        )}
        {selectedId && detail.status === "loading" && <p>Загружаем досье…</p>}
        {selectedId && detail.status === "error" && (
          <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800">
            Не удалось загрузить досье: {detail.error}
          </p>
        )}
        {detail.data && (
          <>
            <header>
              <h2 className="text-xl font-semibold leading-snug">{detail.data.event.title}</h2>
              <p className="text-sm text-slate-500">
                {detail.data.event.geo ?? "место не определено"} ·{" "}
                {detail.data.event.topic ?? "тема не определена"}
              </p>
            </header>

            <DossierView dossier={detail.data.dossier} onShowPost={showPost} />

            <section className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <h3 className="font-medium">Черновик</h3>
                <button
                  type="button"
                  onClick={makeDraft}
                  disabled={draft.status === "loading"}
                  className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                >
                  {draft.status === "loading" ? "Готовим…" : `Черновик для ${outletTitle}`}
                </button>
              </div>
              {draft.status === "error" && (
                <p className="text-sm text-red-700">Черновик не получился: {draft.error}</p>
              )}
              {draft.data && <DraftView draft={draft.data} onShowPost={showPost} />}
            </section>

            <section className="space-y-2">
              <h3 className="font-medium">Граф репостов</h3>
              <RepostGraph
                graph={detail.data.graph}
                firstSourceId={detail.data.dossier.first_source_post_id}
                onShowPost={showPost}
              />
            </section>

            <section className="space-y-2">
              <h3 className="font-medium">Посты-источники ({detail.data.posts.length})</h3>
              <PostList
                posts={detail.data.posts}
                highlightId={highlightPost}
                firstSourceId={detail.data.dossier.first_source_post_id}
              />
            </section>
          </>
        )}
      </main>
    </div>
  );
}
