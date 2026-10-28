import type { RepostGraph as Graph } from "../types";

interface Props {
  graph: Graph;
  firstSourceId: string;
  onShowPost?: (postId: string) => void;
}

const COL = 150;
const ROW = 46;
const PAD = 24;

// Depth = number of forward/copy hops from a post with no incoming edge.
function layout(graph: Graph) {
  const incoming = new Map<string, string>();
  for (const edge of graph.edges) incoming.set(edge.to, edge.from);
  const depth = new Map<string, number>();
  const depthOf = (id: string, seen = new Set<string>()): number => {
    const known = depth.get(id);
    if (known !== undefined) return known;
    const parent = incoming.get(id);
    const value = parent && !seen.has(parent) ? depthOf(parent, seen.add(id)) + 1 : 0;
    depth.set(id, value);
    return value;
  };
  const rows = new Map<number, number>();
  const nodes = [...graph.nodes]
    .sort((a, b) => a.ts.localeCompare(b.ts) || a.id.localeCompare(b.id))
    .map((node) => {
      const d = depthOf(node.id);
      const row = rows.get(d) ?? 0;
      rows.set(d, row + 1);
      return { ...node, x: PAD + d * COL, y: PAD + row * ROW };
    });
  return { nodes, byId: new Map(nodes.map((node) => [node.id, node])) };
}

export default function RepostGraph({ graph, firstSourceId, onShowPost }: Props) {
  if (graph.nodes.length === 0) {
    return <p className="text-sm text-slate-500">Граф для этого события не построен.</p>;
  }
  const { nodes, byId } = layout(graph);
  const width = Math.max(...nodes.map((n) => n.x)) + COL;
  const height = Math.max(...nodes.map((n) => n.y)) + ROW;
  const roots = nodes.filter((n) => !graph.edges.some((e) => e.to === n.id)).length;

  return (
    <div className="space-y-2">
      <p className="text-sm text-slate-600">
        Постов: {graph.nodes.length}, ветвей от независимых корней: {roots}. Сплошная линия —
        пересылка, пунктир — копия текста без пересылки.
      </p>
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <svg width={width} height={height} role="img" aria-label="Граф репостов">
          {graph.edges.map((edge) => {
            const from = byId.get(edge.from);
            const to = byId.get(edge.to);
            if (!from || !to) return null;
            return (
              <line
                key={`${edge.from}-${edge.to}`}
                x1={from.x + 110}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke="#94a3b8"
                strokeWidth={1.5}
                strokeDasharray={edge.kind === "copy" ? "4 3" : undefined}
              />
            );
          })}
          {nodes.map((node) => {
            const first = node.id === firstSourceId;
            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y - 14})`}
                className="cursor-pointer"
                onClick={() => onShowPost?.(node.id)}
              >
                <rect
                  width={110}
                  height={28}
                  rx={6}
                  fill={first ? "#fef3c7" : "#f8fafc"}
                  stroke={first ? "#d97706" : "#cbd5e1"}
                  strokeWidth={first ? 2 : 1}
                />
                <text x={8} y={18} fontSize={11} fill="#0f172a">
                  {first ? "★ " : ""}
                  {node.id}
                </text>
                <title>{`${node.channel_id}, ${node.ts}`}</title>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
