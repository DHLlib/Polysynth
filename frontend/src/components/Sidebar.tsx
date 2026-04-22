import { MessageSquare, Plus } from "lucide-react";
import type { Session } from "@/api/types";

interface Props {
  sessions: Session[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  isOpen: boolean;
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

function statusDot(status: string) {
  switch (status) {
    case "running":
      return "bg-yellow-400";
    case "completed":
      return "bg-green-400";
    case "error":
      return "bg-red-400";
    default:
      return "bg-text-muted";
  }
}

export default function Sidebar({ sessions, activeId, onSelect, onNewChat, isOpen }: Props) {
  return (
    <aside
      className={`bg-bg-secondary border-r border-border flex flex-col transition-all duration-300 ${
        isOpen ? "w-64" : "w-0 overflow-hidden"
      }`}
    >
      <div className="p-4 border-b border-border">
        <button
          onClick={onNewChat}
          className="w-full bg-accent hover:bg-accent/90 text-white rounded-lg px-4 py-2.5 text-sm font-medium flex items-center justify-center gap-2 transition-colors"
        >
          <Plus size={16} />
          新建讨论
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {sessions.length === 0 && (
          <div className="text-center text-text-muted text-sm py-8">
            暂无历史记录
          </div>
        )}
        {sessions.map((s) => (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            className={`w-full text-left rounded-lg px-3 py-2.5 text-sm transition-colors ${
              activeId === s.id
                ? "bg-bg-tertiary text-text-secondary"
                : "text-text-muted hover:bg-bg-tertiary/50 hover:text-text-secondary"
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <MessageSquare size={14} />
              <span className="font-medium truncate flex-1">{s.topic}</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="px-1.5 py-0.5 rounded bg-bg-primary text-text-muted">
                {s.mode}
              </span>
              <span className="text-text-muted">{formatDate(s.created_at)}</span>
              <span className={`w-1.5 h-1.5 rounded-full ${statusDot(s.status)}`} />
            </div>
          </button>
        ))}
      </div>
    </aside>
  );
}
