import { useMemo } from "react";
import MessageBubble from "./MessageBubble";
import type { WSEvent, StreamingMessage } from "@/api/types";

interface Props {
  events: WSEvent[];
  historyMessages?: StreamingMessage[];
}

export default function ChatView({ events, historyMessages }: Props) {
  const messages = useMemo(() => {
    const msgs: StreamingMessage[] = historyMessages ? [...historyMessages] : [];
    let current: StreamingMessage | null = null;

    for (const ev of events) {
      switch (ev.type) {
        case "banner": {
          if (current) {
            current.is_complete = true;
            msgs.push(current);
            current = null;
          }
          msgs.push({
            role_key: "__banner__",
            role_name: "",
            color: "",
            tokens: [],
            full_content: ev.payload.text,
            is_complete: true,
          });
          break;
        }
        case "turn_start": {
          if (current) {
            current.is_complete = true;
            msgs.push(current);
          }
          current = {
            role_key: ev.payload.role_key,
            role_name: ev.payload.role_name,
            color: ev.payload.color || "",
            tokens: [],
            full_content: null,
            is_complete: false,
          };
          break;
        }
        case "token": {
          if (current && current.role_key === ev.payload.role_key) {
            current.tokens.push(ev.payload.token);
          }
          break;
        }
        case "turn_end": {
          if (current && current.role_key === ev.payload.role_key) {
            current.full_content = ev.payload.full_content;
            current.is_complete = true;
            msgs.push(current);
            current = null;
          }
          break;
        }
        case "tool_start": {
          msgs.push({
            role_key: "__tool__",
            role_name: "",
            color: "",
            tokens: [],
            full_content: null,
            is_complete: true,
            tool_status: "start",
            tool_name: ev.payload.tool_name,
          });
          break;
        }
        case "tool_end": {
          msgs.push({
            role_key: "__tool__",
            role_name: "",
            color: "",
            tokens: [],
            full_content: null,
            is_complete: true,
            tool_status: "end",
            tool_name: ev.payload.tool_name,
            tool_preview: ev.payload.preview,
          });
          break;
        }
        case "session_end": {
          if (current) {
            current.is_complete = true;
            msgs.push(current);
            current = null;
          }
          break;
        }
      }
    }

    if (current) {
      msgs.push(current);
    }

    return msgs;
  }, [events, historyMessages]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-1">
      {messages.length === 0 && (
        <div className="h-full flex flex-col items-center justify-center text-text-muted">
          <div className="text-4xl mb-4">🎭</div>
          <p className="text-lg mb-2">欢迎来到 Polysynth</p>
          <p className="text-sm">选择模式，输入话题，开始多 Agent 协作讨论</p>
        </div>
      )}

      {messages.map((msg, i) => {
        if (msg.role_key === "__banner__") {
          return (
            <div key={`banner-${i}`} className="py-4 text-center">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-bg-tertiary/50 border border-border">
                <span className="text-accent text-lg">✦</span>
                <span className="text-sm font-medium text-text-secondary">
                  {msg.full_content}
                </span>
              </div>
            </div>
          );
        }

        if (msg.role_key === "__tool__") {
          return (
            <div key={`tool-${i}`} className="py-1 px-4">
              {msg.tool_status === "start" ? (
                <div className="flex items-center gap-2 text-xs text-text-muted animate-pulse">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                  <span>正在使用 {msg.tool_name} 工具...</span>
                </div>
              ) : (
                <details className="text-xs text-text-muted">
                  <summary className="cursor-pointer flex items-center gap-1.5 hover:text-text-secondary transition-colors">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                    <span>{msg.tool_name} 结果预览（点击展开）</span>
                  </summary>
                  <p className="mt-1 pl-3 text-text-secondary leading-relaxed whitespace-pre-wrap">
                    {msg.tool_preview}
                  </p>
                </details>
              )}
            </div>
          );
        }

        const content = msg.is_complete
          ? msg.full_content || ""
          : msg.tokens.join("");

        return (
          <MessageBubble
            key={`${msg.role_key}-${i}`}
            name={msg.role_name}
            color={msg.color}
            content={content}
            isStreaming={!msg.is_complete}
          />
        );
      })}
    </div>
  );
}
