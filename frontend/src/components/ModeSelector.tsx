import type { ModeConfig } from "@/api/types";

interface Props {
  modes: ModeConfig[];
  value: string;
  onChange: (mode: string) => void;
}

export default function ModeSelector({ modes, value, onChange }: Props) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-sm text-text-muted">模式</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm text-text-secondary focus:outline-none focus:border-accent transition-colors"
      >
        {modes.map((m) => (
          <option key={m.name} value={m.name}>
            {m.display_name}
          </option>
        ))}
      </select>
    </div>
  );
}
