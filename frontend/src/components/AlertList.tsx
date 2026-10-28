import type { Alert } from "../types";
import { formatTime } from "./labels";

interface Props {
  alerts: Alert[];
  onOpen: (eventId: string) => void;
}

export default function AlertList({ alerts, onOpen }: Props) {
  if (alerts.length === 0) return null;
  return (
    <section className="space-y-2 rounded-lg bg-red-50 p-3 ring-1 ring-red-200">
      <h3 className="font-medium text-red-900">Сторож опровержений</h3>
      <ul className="space-y-1 text-sm">
        {alerts.map((alert) => (
          <li key={`${alert.event_id}-${alert.outlet}-${alert.post_id}`} className="flex gap-2">
            <span>{alert.kind === "denial" ? "⛔" : "ℹ️"}</span>
            <span className="text-red-900">
              {formatTime(alert.ts)} · {alert.summary}{" "}
              <button
                type="button"
                className="underline"
                onClick={() => onOpen(alert.event_id)}
              >
                открыть событие
              </button>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
