import { useEffect, useRef, useState } from "react";
import { getStream } from "../api";
import { LEVELS, OUTLETS, formatTime } from "../components/labels";
import type { Level, Outlet, ReplayStream } from "../types";

// Model seconds per real second.
const SPEEDS = [
  { value: 60, title: "×60" },
  { value: 600, title: "×600" },
  { value: 3600, title: "×3600" },
];
const TICK_MS = 1000;
const STEP_MS = 60_000;

export default function Live() {
  const [outlet, setOutlet] = useState<Outlet>("mash");
  const [speed, setSpeed] = useState(600);
  const [playing, setPlaying] = useState(false);
  const [bounds, setBounds] = useState<{ start: number; end: number } | null>(null);
  const [until, setUntil] = useState<number | null>(null);
  const [stream, setStream] = useState<ReplayStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [changed, setChanged] = useState<Record<string, Level>>({});
  const levels = useRef<Record<string, Level>>({});

  useEffect(() => {
    getStream(outlet)
      .then((full) => {
        const start = Date.parse(full.start);
        setBounds({ start, end: Date.parse(full.end) });
        setUntil((current) => current ?? start);
      })
      .catch((reason: unknown) => setError(String(reason)));
  }, [outlet]);

  useEffect(() => {
    if (until === null) return;
    let cancelled = false;
    getStream(outlet, new Date(until).toISOString())
      .then((data) => {
        if (cancelled) return;
        const fresh: Record<string, Level> = {};
        for (const item of data.events) {
          const before = levels.current[item.event.id];
          if (before && before !== item.level) fresh[item.event.id] = before;
          levels.current[item.event.id] = item.level;
        }
        setChanged(fresh);
        setStream(data);
      })
      .catch((reason: unknown) => setError(String(reason)));
    return () => {
      cancelled = true;
    };
  }, [outlet, until]);

  useEffect(() => {
    if (!playing || !bounds) return;
    const timer = setInterval(() => {
      setUntil((current) => {
        const next = Math.min((current ?? bounds.start) + speed * TICK_MS, bounds.end);
        if (next >= bounds.end) setPlaying(false);
        return next;
      });
    }, TICK_MS);
    return () => clearInterval(timer);
  }, [playing, speed, bounds]);

  function restart() {
    if (!bounds) return;
    levels.current = {};
    setChanged({});
    setUntil(bounds.start);
    setPlaying(true);
  }

  if (error) {
    return <p className="rounded-lg bg-red-50 p-3 text-red-800">Поток недоступен: {error}</p>;
  }
  if (!bounds || until === null) return <p>Загружаем поток…</p>;

  const items = [...(stream?.events ?? [])].sort((a, b) => b.rose_at.localeCompare(a.rose_at));

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        Проигрываем 48 часов синтетического потока по модельному времени. События появляются,
        когда о них пишет второй пост, и меняют цвет, когда приходят новые проверки.
      </p>

      <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-mono text-2xl font-semibold">
            {formatTime(new Date(until).toISOString())}
          </span>
          <button
            type="button"
            onClick={() => (until >= bounds.end ? restart() : setPlaying(!playing))}
            className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm text-white"
          >
            {playing ? "⏸ Пауза" : until >= bounds.end ? "↺ Сначала" : "▶ Играть"}
          </button>
          <div className="inline-flex rounded-lg border border-slate-300 p-0.5">
            {SPEEDS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setSpeed(item.value)}
                className={`rounded-md px-2 py-0.5 text-sm ${
                  speed === item.value ? "bg-slate-900 text-white" : "text-slate-700"
                }`}
              >
                {item.title}
              </button>
            ))}
          </div>
          <div className="inline-flex rounded-lg border border-slate-300 p-0.5">
            {OUTLETS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setOutlet(item.id)}
                className={`rounded-md px-2 py-0.5 text-sm ${
                  outlet === item.id ? "bg-slate-900 text-white" : "text-slate-700"
                }`}
              >
                {item.title}
              </button>
            ))}
          </div>
        </div>
        <input
          type="range"
          className="w-full"
          min={bounds.start}
          max={bounds.end}
          step={STEP_MS}
          value={until}
          onChange={(e) => {
            setPlaying(false);
            setUntil(Number(e.target.value));
          }}
          aria-label="Модельное время"
        />
      </div>

      {items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-6 text-slate-500">
          Пока тихо: ни одно событие не набрало двух постов.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => {
            const level = LEVELS[item.level];
            const before = changed[item.event.id];
            return (
              <li
                key={item.event.id}
                className={`rounded-lg border bg-white p-3 transition ${
                  before ? "border-red-400 ring-2 ring-red-200" : "border-slate-200"
                }`}
              >
                <div className="flex items-start gap-2">
                  <span className={`mt-1.5 h-3 w-3 shrink-0 rounded-full ${level.dot}`} />
                  <div className="min-w-0">
                    <div className="font-medium leading-snug">{item.event.title}</div>
                    <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-slate-500">
                      <span>
                        поднялось через {item.minutes_to_signal} мин после первого поста (
                        {formatTime(item.rose_at)})
                      </span>
                      <span>постов: {item.event.post_ids.length}</span>
                      <span>
                        {level.title}
                        {before && ` — был ${LEVELS[before].title.toLowerCase()}`}
                      </span>
                    </div>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
