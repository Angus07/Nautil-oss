import { useEffect, useRef } from "react";
import { Radio } from "lucide-react";
import type { NautilEvent } from "../types";

interface Props {
  events: NautilEvent[];
  onClickEvent: (nodeId: string) => void;
}

const levelStyle: Record<string, string> = {
  info: "text-slate-400",
  warning: "text-orange-400",
  error: "text-red-400",
  success: "text-emerald-400",
};

export default function EventStream({ events, onClickEvent }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, [events.length]);

  if (!events.length) {
    return (
      <footer className="flex-shrink-0 h-10 border-t border-slate-800 bg-slate-950/80 flex items-center px-4">
        <span className="text-xs text-slate-600 flex items-center gap-1.5">
          <Radio size={10} className="opacity-50" />
          Waiting for events...
        </span>
      </footer>
    );
  }

  return (
    <footer className="flex-shrink-0 border-t border-slate-800 bg-slate-950/80">
      <div ref={scrollRef} className="flex gap-1 overflow-x-auto px-3 py-2 scrollbar-thin">
        {events.map((ev, i) => (
          <button
            key={i}
            onClick={() => ev.node_id && onClickEvent(ev.node_id)}
            className={`flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono transition-colors whitespace-nowrap cursor-pointer ${
              ev.node_id
                ? "hover:bg-slate-800"
                : "cursor-default"
            } ${levelStyle[ev.level] ?? "text-slate-400"}`}
          >
            <span className="text-slate-600">[{ev.timestamp}]</span>
            <span>{ev.message}</span>
          </button>
        ))}
      </div>
    </footer>
  );
}
