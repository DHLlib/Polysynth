interface Props {
  name: string;
  color: string;
  content: string;
  isStreaming?: boolean;
}

function ansiToHex(ansi: string): string {
  // Map ANSI codes to hex colors for the web
  const map: Record<string, string> = {
    "[94m": "#60a5fa", // blue
    "[97m": "#f3f4f6", // white
    "[91m": "#f87171", // bright red
    "[31m": "#ef4444", // red
    "[90m": "#9ca3af", // gray/black
    "[93m": "#facc15", // yellow
    "[92m": "#4ade80", // bright green
    "[32m": "#22c55e", // green
    "[96m": "#22d3ee", // cyan
  };
  return map[ansi] || "#a0a0a0";
}

export default function MessageBubble({ name, color, content, isStreaming }: Props) {
  const borderColor = ansiToHex(color);

  return (
    <div className="py-3 px-4">
      <div
        className="rounded-xl p-4 bg-bubble-bg"
        style={{ borderLeft: `3px solid ${borderColor}` }}
      >
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm font-semibold" style={{ color: borderColor }}>
            {name}
          </span>
          {isStreaming && (
            <span className="text-xs text-text-muted animate-pulse">正在发言...</span>
          )}
        </div>
        <div className="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap">
          {content}
        </div>
      </div>
    </div>
  );
}
