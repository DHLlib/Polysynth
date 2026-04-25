import { PanelLeft, Palette, Settings, Minus, Plus } from "lucide-react";
import ModeSelector from "./ModeSelector";
import TopicInput from "./TopicInput";
import type { ModeConfig } from "@/api/types";

interface Props {
  modes: ModeConfig[];
  selectedMode: string;
  onModeChange: (mode: string) => void;
  onTopicSubmit: (topic: string, files: File[]) => void;
  onToggleSidebar: () => void;
  onOpenConfig: () => void;
  onToggleTheme: () => void;
  isRunning: boolean;
  isSubmitting?: boolean;
  topicValue?: string;
  topicKey?: number;
  rounds: number;
  onRoundsChange: (r: number) => void;
}

export default function Header({
  modes,
  selectedMode,
  onModeChange,
  onTopicSubmit,
  onToggleSidebar,
  onOpenConfig,
  onToggleTheme,
  isRunning,
  isSubmitting,
  topicValue,
  topicKey,
  rounds,
  onRoundsChange,
}: Props) {
  const currentMode = modes.find((m) => m.name === selectedMode);
  const roundsMeta = currentMode?.mode_json?.rounds;
  const configurable = !!roundsMeta?.configurable;
  const minR = roundsMeta?.min ?? 1;
  const maxR = roundsMeta?.max ?? 10;

  return (
    <header className="bg-bg-secondary border-b border-border px-4 py-3 flex items-center gap-4">
      <button
        onClick={onToggleSidebar}
        className="text-text-muted hover:text-text-secondary transition-colors p-1"
      >
        <PanelLeft size={20} />
      </button>

      <div className="flex items-center gap-4 flex-1">
        <h1 className="text-lg font-bold text-text-primary whitespace-nowrap">
          Polysynth
        </h1>

        <ModeSelector modes={modes} value={selectedMode} onChange={onModeChange} />

        {configurable && (
          <div className="flex items-center gap-1.5 bg-bg-primary border border-border rounded px-2 py-1.5">
            <span className="text-xs text-text-muted whitespace-nowrap">轮次</span>
            <button
              onClick={() => onRoundsChange(Math.max(minR, rounds - 1))}
              disabled={isRunning || rounds <= minR}
              className="text-text-muted hover:text-text-secondary disabled:opacity-30 transition-colors p-0.5"
            >
              <Minus size={14} />
            </button>
            <span className="text-sm text-text-secondary w-6 text-center tabular-nums">
              {rounds}
            </span>
            <button
              onClick={() => onRoundsChange(Math.min(maxR, rounds + 1))}
              disabled={isRunning || rounds >= maxR}
              className="text-text-muted hover:text-text-secondary disabled:opacity-30 transition-colors p-0.5"
            >
              <Plus size={14} />
            </button>
          </div>
        )}

        {!configurable && roundsMeta && (
          <div className="flex items-center gap-1.5 bg-bg-primary/50 border border-border rounded px-2 py-1.5">
            <span className="text-xs text-text-muted whitespace-nowrap">轮次</span>
            <span className="text-sm text-text-muted w-6 text-center tabular-nums">
              {currentMode?.default_rounds ?? rounds}
            </span>
          </div>
        )}

        <TopicInput key={topicKey} onSubmit={onTopicSubmit} disabled={isRunning || !!isSubmitting} value={topicValue} />
      </div>

      <button
        onClick={onToggleTheme}
        className="text-text-muted hover:text-text-secondary transition-colors p-1"
        title="切换主题"
      >
        <Palette size={20} />
      </button>

      <button
        onClick={onOpenConfig}
        className="text-text-muted hover:text-text-secondary transition-colors p-1"
        title="配置"
      >
        <Settings size={20} />
      </button>
    </header>
  );
}
