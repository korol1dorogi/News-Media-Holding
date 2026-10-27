import type { RepostGraph as Graph } from "../types";

// TODO(UX2): граф из /api/events/{id}.graph, первоисточник выделен. Готово, когда у «слуха»
// видно, что все ветки идут из одного поста (docs/tasks.md, UX2).
export default function RepostGraph({ graph }: { graph: Graph }) {
  return (
    <p className="text-sm text-slate-500">
      Граф репостов: постов {graph.nodes.length}, связей {graph.edges.length}.
    </p>
  );
}
