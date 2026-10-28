import { USE_MOCK } from "./api";
import EditorPage from "./pages/EditorPage";

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
        <h1 className="text-xl font-semibold">Сигнал · синтетические данные</h1>
        <p className="text-sm text-slate-500">
          Находит событие в потоке постов, проверяет на фейк и готовит черновик. Публикует
          редактор.
          {USE_MOCK && " Режим макета: данные из src/mock."}
        </p>
      </header>
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        <EditorPage />
      </div>
    </div>
  );
}
