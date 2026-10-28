import type { EventListItem } from "../types";
import { LEVELS, formatTime } from "./labels";

interface Props {
  items: EventListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export default function EventList({ items, selectedId, onSelect }: Props) {
  if (items.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">
        Под эти фильтры событий нет. Сбросьте фильтры или пересоберите ленту.
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {items.map((item) => {
        const level = LEVELS[item.level];
        const active = item.event.id === selectedId;
        return (
          <li key={item.event.id}>
            <button
              type="button"
              onClick={() => onSelect(item.event.id)}
              className={`w-full rounded-lg border p-3 text-left transition ${
                active
                  ? "border-slate-900 bg-white shadow"
                  : "border-slate-200 bg-white hover:border-slate-400"
              }`}
            >
              <div className="flex items-start gap-2">
                <span
                  className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${level.dot}`}
                  title={`${level.title}: ${level.hint}`}
                />
                <span className="font-medium leading-snug">{item.event.title}</span>
              </div>
              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 pl-4.5 text-xs text-slate-500">
                <span>первый сигнал {formatTime(item.event.first_ts)}</span>
                <span>постов: {item.event.post_ids.length}</span>
                {item.event.topic && <span>{item.event.topic}</span>}
                <span>новостность {Math.round(item.score * 100)}</span>
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
