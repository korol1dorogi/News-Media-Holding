import type { CheckStatus, Level, Outlet } from "../types";

export const OUTLETS: { id: Outlet; title: string }[] = [
  { id: "mash", title: "Mash" },
  { id: "life", title: "Life" },
  { id: "super", title: "Super" },
];

export const LEVELS: Record<Level, { title: string; hint: string; dot: string; chip: string }> = {
  green: {
    title: "Зелёный",
    hint: "Источники подтверждают друг друга",
    dot: "bg-emerald-500",
    chip: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  },
  yellow: {
    title: "Жёлтый",
    hint: "Мало независимых источников, нужна проверка",
    dot: "bg-amber-400",
    chip: "bg-amber-50 text-amber-800 ring-amber-200",
  },
  red: {
    title: "Красный",
    hint: "Есть признаки фейка",
    dot: "bg-red-500",
    chip: "bg-red-50 text-red-800 ring-red-200",
  },
};

export const CHECK_TITLES: Record<string, string> = {
  provenance: "Первоисточник",
  media_archive: "Фото по архиву",
  weather: "Погода на фото",
  official: "Официальные каналы",
};

export const STATUSES: Record<CheckStatus, { title: string; chip: string }> = {
  ok: { title: "в порядке", chip: "bg-emerald-50 text-emerald-800 ring-emerald-200" },
  warn: { title: "внимание", chip: "bg-amber-50 text-amber-800 ring-amber-200" },
  fail: { title: "не прошла", chip: "bg-red-50 text-red-800 ring-red-200" },
  "n/a": { title: "нет данных", chip: "bg-slate-100 text-slate-600 ring-slate-200" },
};

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
