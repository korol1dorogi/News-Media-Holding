// Mirror of radar/core/models.py and the API (docs: AGENTS.md). Only the lead changes this file.
// datetime fields are ISO 8601 strings.

export type Outlet = "mash" | "life" | "super";
export type Level = "green" | "yellow" | "red";
export type CheckStatus = "ok" | "warn" | "fail" | "n/a";

export interface Channel {
  id: string;
  title: string;
  kind: "public" | "official" | "reader_bot" | "outlet";
  region: string;
}

export interface Post {
  id: string;
  channel_id: string;
  ts: string;
  text: string;
  url: string;
  media: string[];
  forward_from: string | null;
  geo: string | null;
  topic: string | null;
}

export interface Event {
  id: string;
  post_ids: string[];
  first_ts: string;
  title: string;
  geo: string | null;
  topic: string | null;
  scores: Record<string, number>;
}

export interface Check {
  name: string; // provenance | media_archive | weather | official
  status: CheckStatus;
  summary: string;
  evidence: Record<string, unknown>[];
}

export interface Dossier {
  event_id: string;
  level: Level;
  first_source_post_id: string;
  independent_sources: number;
  checks: Check[];
  todo: string[];
}

export interface Claim {
  text: string;
  kind: "number" | "name" | "date" | "place" | "other";
  source_post_ids: string[];
  supported: boolean;
}

export interface Draft {
  event_id: string;
  outlet: Outlet;
  text: string;
  claims: Claim[];
  warnings: string[];
}

export interface GraphNode {
  id: string;
  channel_id: string;
  ts: string;
}

export interface GraphEdge {
  from: string;
  to: string;
  kind: "forward" | "copy";
}

export interface RepostGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// GET /api/events?outlet=...
export interface EventListItem {
  event: Event;
  level: Level;
  score: number;
}

// GET /api/events/{id}
export interface EventDetail {
  event: Event;
  dossier: Dossier;
  posts: Post[];
  graph: RepostGraph;
}

// POST /api/replay/reset
export interface ResetResult {
  events: number;
}

// GET /api/metrics: reports/metrics.json as is, or {}
export type Metrics = Record<string, unknown>;
