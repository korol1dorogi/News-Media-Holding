import { useState } from "react";
import { USE_MOCK } from "./api";
import EditorPage from "./pages/EditorPage";
import Quality from "./pages/Quality";

type Page = "editor" | "quality";

const PAGES: { id: Page; title: string }[] = [
  { id: "editor", title: "Редактор" },
  { id: "quality", title: "Качество" },
];

export default function App() {
  const [page, setPage] = useState<Page>("editor");

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold">Сигнал · синтетические данные</h1>
            <p className="text-sm text-slate-500">
              Находит событие в потоке постов, проверяет на фейк и готовит черновик. Публикует
              редактор.
              {USE_MOCK && " Режим макета: данные из src/mock."}
            </p>
          </div>
          <nav className="inline-flex rounded-lg border border-slate-300 p-0.5">
            {PAGES.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setPage(item.id)}
                className={`rounded-md px-3 py-1 text-sm ${
                  page === item.id ? "bg-slate-900 text-white" : "text-slate-700"
                }`}
              >
                {item.title}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        {page === "editor" ? <EditorPage /> : <Quality />}
      </div>
    </div>
  );
}
