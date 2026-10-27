import { useEffect, useState } from "react";
import { USE_MOCK, getEvents } from "./api";
import type { EventListItem } from "./types";

// TODO(UX1): лента событий с переключателем изданий, досье, посты-источники и черновик
// с подсветкой неподтверждённых утверждений. Готово, когда демо-сценарий проходится
// кликами (docs/tasks.md, UX1).
export default function App() {
  const [items, setItems] = useState<EventListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getEvents("mash")
      .then(setItems)
      .catch((reason: unknown) => setError(String(reason)));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <h1 className="text-xl font-semibold">Сигнал · синтетические данные</h1>
        {USE_MOCK && <p className="text-sm text-slate-500">Режим макета: данные из src/mock</p>}
      </header>
      <main className="p-6">
        {error && <p className="text-red-700">Не удалось загрузить события: {error}</p>}
        {!error && items === null && <p>Загрузка…</p>}
        {items && <p>Событий в ленте: {items.length}</p>}
      </main>
    </div>
  );
}
