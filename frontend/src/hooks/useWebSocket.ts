import { useCallback, useEffect, useRef, useState } from "react";
import type { WSEvent } from "@/api/types";

export function useWebSocket() {
  const ws = useRef<WebSocket | null>(null);
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connect = useCallback((sessionId: string) => {
    const url = `ws://localhost:8000/api/sessions/ws/${sessionId}`;
    const socket = new WebSocket(url);
    ws.current = socket;
    setError(null);
    setEvents([]);

    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setError("WebSocket 连接失败");
    socket.onmessage = (msg) => {
      try {
        const data: WSEvent = JSON.parse(msg.data);
        setEvents((prev) => [...prev, data]);
      } catch {
        // ignore non-JSON
      }
    };
  }, []);

  const disconnect = useCallback(() => {
    ws.current?.close();
    ws.current = null;
    setConnected(false);
  }, []);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return { connect, disconnect, events, connected, error, clearEvents };
}
