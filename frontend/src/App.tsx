import { useEffect, useMemo, useState } from "react";
import Header from "@/components/Header";
import Sidebar from "@/components/Sidebar";
import ChatView from "@/components/ChatView";
import ConfigPanel from "@/components/ConfigPanel";
import { useUIStore } from "@/stores/uiStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useCreateSession, useSessionList } from "@/hooks/useSessions";
import { listModeConfigs } from "@/api/config";
import { getSession } from "@/api/sessions";
import type { ModeConfig, StreamingMessage, Message } from "@/api/types";

export default function App() {
  const { sidebarOpen, toggleSidebar, configPanelOpen, setConfigPanelOpen, currentSessionId, setCurrentSessionId } = useUIStore();
  const [modes, setModes] = useState<ModeConfig[]>([]);
  const [selectedMode, setSelectedMode] = useState("six_hat");
  const [rounds, setRounds] = useState(3);
  const [historyMessages, setHistoryMessages] = useState<StreamingMessage[] | null>(null);
  const [displayTopic, setDisplayTopic] = useState("");
  const [topicKey, setTopicKey] = useState(0);
  const { data: sessions, refetch: refetchSessions } = useSessionList();
  const createSession = useCreateSession();
  const { connect, disconnect, events, clearEvents, connected } = useWebSocket();

  // Load mode configs on mount
  useEffect(() => {
    listModeConfigs().then(setModes);
  }, []);

  const currentMode = useMemo(
    () => modes.find((m) => m.name === selectedMode) || null,
    [modes, selectedMode]
  );

  // 模式切换时同步默认轮次
  useEffect(() => {
    if (currentMode) {
      setRounds(currentMode.default_rounds);
    }
  }, [currentMode]);

  const isRunning = useMemo(() => {
    if (!events.length) return false;
    const last = events[events.length - 1];
    return last.type !== "session_end" && last.type !== "error";
  }, [events]);

  const handleStart = async (topic: string) => {
    if (isRunning) return;
    disconnect();
    clearEvents();
    setHistoryMessages(null);
    setDisplayTopic("");

    const session = await createSession.mutateAsync({
      mode: selectedMode as "six_hat" | "debate",
      topic,
      rounds,
    });

    setCurrentSessionId(session.id);
    setTopicKey((k) => k + 1);
    connect(session.id);
  };

  const handleNewChat = () => {
    disconnect();
    clearEvents();
    setHistoryMessages(null);
    setDisplayTopic("");
    setCurrentSessionId(null);
    setTopicKey((k) => k + 1);
  };

  const handleSelectSession = async (id: string) => {
    disconnect();
    clearEvents();
    setHistoryMessages(null);

    try {
      const session = await getSession(id);
      setCurrentSessionId(id);
      setSelectedMode(session.mode);
      setDisplayTopic(session.topic);

      if (session.status === "running") {
        connect(id);
      } else {
        const modeCfg = modes.find((m) => m.name === session.mode);
        const colorMap = new Map(
          modeCfg?.participants.map((p) => [p.role_key, p.color || ""]) ?? []
        );

        const msgs: StreamingMessage[] = (session.messages as Message[]).map((msg) => ({
          role_key: msg.role_key,
          role_name: msg.name,
          color: colorMap.get(msg.role_key) || "",
          tokens: [],
          full_content: msg.content,
          is_complete: true,
        }));
        setHistoryMessages(msgs);
      }
    } catch {
      // ignore fetch error
    }
  };

  // Refetch session list when session ends
  useEffect(() => {
    if (events.some((e) => e.type === "session_end")) {
      refetchSessions();
    }
  }, [events, refetchSessions]);

  return (
    <div className="flex h-screen bg-bg-primary text-text-secondary overflow-hidden">
      <Sidebar
        sessions={sessions || []}
        activeId={currentSessionId}
        onSelect={handleSelectSession}
        onNewChat={handleNewChat}
        isOpen={sidebarOpen}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <Header
          modes={modes}
          selectedMode={selectedMode}
          onModeChange={setSelectedMode}
          onTopicSubmit={handleStart}
          onToggleSidebar={toggleSidebar}
          onOpenConfig={() => setConfigPanelOpen(true)}
          isRunning={isRunning}
          topicValue={historyMessages ? displayTopic : undefined}
          topicKey={topicKey}
          rounds={rounds}
          onRoundsChange={setRounds}
        />

        <ChatView events={events} historyMessages={historyMessages ?? undefined} />

        {connected && (
          <div className="px-4 py-2 bg-bg-secondary border-t border-border text-xs text-text-muted flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            WebSocket 已连接
          </div>
        )}
      </div>

      <ConfigPanel
        mode={currentMode}
        open={configPanelOpen}
        onClose={() => setConfigPanelOpen(false)}
      />
    </div>
  );
}
