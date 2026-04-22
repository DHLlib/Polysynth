import { useMemo } from "react";
import MessageBubble from "./MessageBubble";
import type { WSEvent, StreamingMessage } from "@/api/types";

interface Props {
  events: WSEvent[];
  historyMessages?: StreamingMessage[];
}

export default function ChatView({ events, historyMessages }: Props) {
  const messages = useMemo(() => {
    if (historyMessages) return historyMessages;
    const msgs: StreamingMessage[] = [];
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
