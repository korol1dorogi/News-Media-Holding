// API client. VITE_USE_MOCK=true reads src/mock instead of the server, same shapes.
import draftMock from "./mock/draft.json";
import eventDetailMock from "./mock/event_detail.json";
import eventsMock from "./mock/events.json";
import metricsMock from "./mock/metrics.json";
import type {
  Draft,
  EventDetail,
  EventListItem,
  Metrics,
  Outlet,
  ResetResult,
} from "./types";

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function clone<T>(data: unknown): T {
  return structuredClone(data) as T;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Ошибка API ${response.status}: ${path}`);
  }
  return (await response.json()) as T;
}

function mockEvents(outlet: Outlet): EventListItem[] {
  return clone<EventListItem[]>(eventsMock)
    .map((item) => ({ ...item, score: item.event.scores[outlet] ?? item.score }))
    .sort((a, b) => b.score - a.score);
}

function mockDetail(id: string): EventDetail {
  const item = mockEvents("mash").find((candidate) => candidate.event.id === id);
  if (!item) {
    throw new Error("Событие не найдено");
  }
  const detail = clone<EventDetail>(eventDetailMock);
  if (detail.event.id === id) {
    return detail;
  }
  return {
    event: item.event,
    dossier: { ...detail.dossier, event_id: id, level: item.level, checks: [], todo: [] },
    posts: [],
    graph: { nodes: [], edges: [] },
  };
}

export async function getEvents(outlet: Outlet): Promise<EventListItem[]> {
  if (USE_MOCK) return mockEvents(outlet);
  return request(`/api/events?outlet=${encodeURIComponent(outlet)}`);
}

export async function getEvent(id: string): Promise<EventDetail> {
  if (USE_MOCK) return mockDetail(id);
  return request(`/api/events/${encodeURIComponent(id)}`);
}

export async function createDraft(id: string, outlet: Outlet): Promise<Draft> {
  if (USE_MOCK) {
    mockDetail(id);
    return { ...clone<Draft>(draftMock), event_id: id, outlet };
  }
  return request(`/api/events/${encodeURIComponent(id)}/draft`, {
    method: "POST",
    body: JSON.stringify({ outlet }),
  });
}

export async function resetReplay(): Promise<ResetResult> {
  if (USE_MOCK) return { events: mockEvents("mash").length };
  return request("/api/replay/reset", { method: "POST" });
}

export async function getMetrics(): Promise<Metrics> {
  if (USE_MOCK) return clone<Metrics>(metricsMock);
  return request("/api/metrics");
}

export async function ready(): Promise<boolean> {
  if (USE_MOCK) return true;
  const body = await request<{ ok: boolean }>("/api/ready");
  return body.ok;
}
