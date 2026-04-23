import { useState, useEffect, useMemo, useCallback } from "react";
import { X, Save, Eye, EyeOff, Plus, Trash2, Minus, Plus as PlusIcon } from "lucide-react";
import type { ModeConfig, Participant, Provider, GlobalHost } from "@/api/types";
import {
  listProviders,
  listModeConfigs,
  updateParticipant,
  createProvider,
  updateProvider,
  deleteProvider,
  addProviderModel,
  removeProviderModel,
  getGlobalHost,
  updateGlobalHost,
  updateModeConfig,
} from "@/api/config";
import { ansiToHex, hexToAnsi } from "@/lib/colors";

interface Props {
  mode: ModeConfig | null;
  open: boolean;
  onClose: () => void;
}

type Tab = "seats" | "providers" | "host";

export default function ConfigPanel({ mode, open, onClose }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("seats");
  const [seatMode, setSeatMode] = useState<string>(mode?.name || "six_hat");
  const [modes, setModes] = useState<ModeConfig[]>([]);
  const [participantsMap, setParticipantsMap] = useState<Record<string, Participant[]>>({});
  const [originalMap, setOriginalMap] = useState<Record<string, Participant[]>>({});
  const [providers, setProviders] = useState<Provider[]>([]);
  const [saving, setSaving] = useState(false);
  const [globalHost, setGlobalHost] = useState<GlobalHost | null>(null);
  const [hostForm, setHostForm] = useState<Partial<GlobalHost>>({});
  const [hostSaving, setHostSaving] = useState(false);

  useEffect(() => {
    if (open) {
      listProviders().then(setProviders);
      listModeConfigs().then((data) => {
        setModes(data);
        const map: Record<string, Participant[]> = {};
        const orig: Record<string, Participant[]> = {};
        data.forEach((m) => {
          map[m.name] = m.participants;
          orig[m.name] = JSON.parse(JSON.stringify(m.participants));
        });
        setParticipantsMap(map);
        setOriginalMap(orig);
      });
      getGlobalHost().then((h) => {
        setGlobalHost(h);
        setHostForm({ name: h.name, model: h.model });
      });
    }
  }, [open]);

  useEffect(() => {
    if (mode) setSeatMode(mode.name);
  }, [mode]);

  const currentMode = useMemo(
    () => modes.find((m) => m.name === seatMode) || null,
    [modes, seatMode]
  );

  const hostRoleKeys = useMemo(() => {
    if (!currentMode) return new Set<string>();
    const keys = new Set<string>();
    const mj = currentMode.mode_json;
    if (mj?.opening?.speaker) keys.add(mj.opening.speaker);
    if (mj?.rounds?.summary?.speaker) keys.add(mj.rounds.summary.speaker);
    return keys;
  }, [currentMode]);

  const currentParticipants = useMemo(() => {
    const list = participantsMap[seatMode] || [];
    return list.filter((p) => !hostRoleKeys.has(p.role_key));
  }, [participantsMap, seatMode, hostRoleKeys]);

  const changedIds = useMemo(() => {
    const orig = originalMap[seatMode] || [];
    const curr = participantsMap[seatMode] || [];
    const changed = new Set<number>();
    curr.forEach((p) => {
      const o = orig.find((x) => x.id === p.id);
      if (!o) return;
      if (
        p.name !== o.name ||
        p.model !== o.model ||
        p.color !== o.color ||
        p.system_prompt !== o.system_prompt ||
        p.tools_enabled !== o.tools_enabled
      ) {
        changed.add(p.id);
      }
    });
    return changed;
  }, [participantsMap, originalMap, seatMode]);

  const hasUnsavedChanges = changedIds.size > 0;

  const handleChange = (id: number, field: keyof Participant, value: string) => {
    setParticipantsMap((prev) => ({
      ...prev,
      [seatMode]: prev[seatMode].map((p) =>
        p.id === id ? { ...p, [field]: value } : p
      ),
    }));
  };

  const handleBatchSave = async () => {
    if (changedIds.size === 0) return;
    setSaving(true);
    const orig = originalMap[seatMode] || [];
    const curr = participantsMap[seatMode] || [];
    const tasks: Promise<any>[] = [];
    curr.forEach((p) => {
      if (!changedIds.has(p.id)) return;
      const o = orig.find((x) => x.id === p.id);
      if (!o) return;
      const data: Partial<Participant> = {};
      if (p.name !== o.name) data.name = p.name;
      if (p.model !== o.model) data.model = p.model;
      if (p.color !== o.color) data.color = p.color;
      if (p.system_prompt !== o.system_prompt) data.system_prompt = p.system_prompt;
      if (p.tools_enabled !== o.tools_enabled) data.tools_enabled = p.tools_enabled;
      if (Object.keys(data).length > 0) {
        tasks.push(updateParticipant(p.id, data));
      }
    });
    await Promise.all(tasks);
    // 更新原始快照
    setOriginalMap((prev) => ({
      ...prev,
      [seatMode]: JSON.parse(JSON.stringify(participantsMap[seatMode])),
    }));
    setSaving(false);
  };

  const handleSwitchMode = (name: string) => {
    if (hasUnsavedChanges) {
      if (!confirm("当前模式有未保存的更改，切换后将丢失，是否继续？")) return;
    }
    setSeatMode(name);
  };

  const getHostKeysForMode = useCallback((m: ModeConfig) => {
    const keys = new Set<string>();
    const mj = m.mode_json;
    if (mj?.opening?.speaker) keys.add(mj.opening.speaker);
    if (mj?.rounds?.summary?.speaker) keys.add(mj.rounds.summary.speaker);
    return keys;
  }, []);

  const handleSaveHost = async () => {
    if (!globalHost) return;
    setHostSaving(true);
    const data: Partial<Omit<GlobalHost, "id" | "color">> = {};
    if (hostForm.name !== globalHost.name) data.name = hostForm.name;
    if (hostForm.model !== globalHost.model) data.model = hostForm.model;
    if (Object.keys(data).length > 0) {
      const updated = await updateGlobalHost(data as any);
      setGlobalHost(updated);
      // 同步更新前端所有模式中的 host 参与者显示
      setParticipantsMap((prev) => {
        const next: Record<string, Participant[]> = {};
        for (const [modeName, list] of Object.entries(prev)) {
          const modeCfg = modes.find((m) => m.name === modeName);
          const keys = modeCfg ? getHostKeysForMode(modeCfg) : new Set<string>();
          next[modeName] = list.map((p) => {
            if (keys.has(p.role_key)) {
              return { ...p, name: updated.name, model: updated.model, color: updated.color };
            }
            return p;
          });
        }
        return next;
      });
      setOriginalMap((prev) => {
        const next: Record<string, Participant[]> = {};
        for (const [modeName, list] of Object.entries(prev)) {
          const modeCfg = modes.find((m) => m.name === modeName);
          const keys = modeCfg ? getHostKeysForMode(modeCfg) : new Set<string>();
          next[modeName] = list.map((p) => {
            if (keys.has(p.role_key)) {
              return { ...p, name: updated.name, model: updated.model, color: updated.color };
            }
            return p;
          });
        }
        return next;
      });
    }
    setHostSaving(false);
  };

  const modelOptions = useMemo(() => {
    const options: { value: string; label: string }[] = [];
    providers.forEach((provider) => {
      provider.models.forEach((m) => {
        options.push({
          value: m.model_name,
          label: `${provider.name} / ${m.model_name}`,
        });
      });
    });
    return options;
  }, [providers]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-bg-secondary border-l border-border h-full overflow-y-auto">
        <div className="sticky top-0 bg-bg-secondary border-b border-border px-6 py-4 z-10">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-text-secondary">配置</h2>
            <button
              onClick={onClose}
              className="text-text-muted hover:text-text-secondary transition-colors"
            >
              <X size={20} />
            </button>
          </div>
          <div className="flex gap-6 text-sm">
            <button
              onClick={() => setActiveTab("seats")}
              className={`pb-1 transition-colors ${
                activeTab === "seats"
                  ? "text-accent border-b-2 border-accent"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              席位管理
            </button>
            <button
              onClick={() => setActiveTab("host")}
              className={`pb-1 transition-colors ${
                activeTab === "host"
                  ? "text-accent border-b-2 border-accent"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              主持人设置
            </button>
            <button
              onClick={() => setActiveTab("providers")}
              className={`pb-1 transition-colors ${
                activeTab === "providers"
                  ? "text-accent border-b-2 border-accent"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              供应商管理
            </button>
          </div>
        </div>

        {activeTab === "seats" && (
          <>
            <div className="px-6 pt-4 flex gap-4 text-sm">
              {modes.map((m) => (
                <button
                  key={m.name}
                  onClick={() => handleSwitchMode(m.name)}
                  className={`pb-1 transition-colors ${
                    seatMode === m.name
                      ? "text-accent border-b-2 border-accent"
                      : "text-text-muted hover:text-text-secondary"
                  }`}
                >
                  {m.display_name}
                </button>
              ))}
            </div>

            {currentMode && currentMode.mode_json?.rounds?.configurable && (
              <div className="px-6 pt-4 flex items-center gap-3">
                <span className="text-xs text-text-muted">默认轮次</span>
                <div className="flex items-center gap-1.5 bg-bg-primary border border-border rounded px-2 py-1">
                  <button
                    onClick={() => {
                      const minV = currentMode.mode_json.rounds.min ?? 1;
                      const newR = Math.max(minV, (currentMode.default_rounds) - 1);
                      updateModeConfig(currentMode.name, { default_rounds: newR }).then((updated) => {
                        setModes((prev) => prev.map((m) => (m.name === updated.name ? updated : m)));
                      });
                    }}
                    className="text-text-muted hover:text-text-secondary transition-colors p-0.5"
                  >
                    <Minus size={14} />
                  </button>
                  <span className="text-sm text-text-secondary w-6 text-center tabular-nums">
                    {currentMode.default_rounds}
                  </span>
                  <button
                    onClick={() => {
                      const maxV = currentMode.mode_json.rounds.max ?? 10;
                      const newR = Math.min(maxV, (currentMode.default_rounds) + 1);
                      updateModeConfig(currentMode.name, { default_rounds: newR }).then((updated) => {
                        setModes((prev) => prev.map((m) => (m.name === updated.name ? updated : m)));
                      });
                    }}
                    className="text-text-muted hover:text-text-secondary transition-colors p-0.5"
                  >
                    <PlusIcon size={14} />
                  </button>
                </div>
              </div>
            )}

            {currentMode && !currentMode.mode_json?.rounds?.configurable && (
              <div className="px-6 pt-4 flex items-center gap-3">
                <span className="text-xs text-text-muted">默认轮次</span>
                <span className="text-sm text-text-muted tabular-nums">
                  {currentMode.default_rounds}（固定）
                </span>
              </div>
            )}

            <SeatTab
              participants={currentParticipants}
              modelOptions={modelOptions}
              onChange={handleChange}
            />
            <div className="fixed bottom-6 right-6 z-[60]">
              <button
                onClick={handleBatchSave}
                disabled={saving || changedIds.size === 0}
                className="bg-accent hover:bg-accent/90 text-white text-sm px-5 py-2.5 rounded-full shadow-lg shadow-accent/30 flex items-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Save size={14} />
                {saving ? "保存中..." : changedIds.size > 0 ? `保存更改 (${changedIds.size})` : "暂无更改"}
              </button>
            </div>
          </>
        )}

        {activeTab === "host" && globalHost && (
          <HostTab
            host={globalHost}
            form={hostForm}
            onChange={setHostForm}
            onSave={handleSaveHost}
            saving={hostSaving}
            modelOptions={modelOptions}
            modes={modes}
            participantsMap={participantsMap}
            onSavePrompt={async (participantId, prompt) => {
              await updateParticipant(participantId, { system_prompt: prompt });
              setParticipantsMap((prev) => {
                const next: Record<string, Participant[]> = {};
                for (const [modeName, list] of Object.entries(prev)) {
                  next[modeName] = list.map((p) =>
                    p.id === participantId ? { ...p, system_prompt: prompt } : p
                  );
                }
                return next;
              });
              setOriginalMap((prev) => {
                const next: Record<string, Participant[]> = {};
                for (const [modeName, list] of Object.entries(prev)) {
                  next[modeName] = list.map((p) =>
                    p.id === participantId ? { ...p, system_prompt: prompt } : p
                  );
                }
                return next;
              });
            }}
          />
        )}

        {activeTab === "providers" && (
          <ProviderTab
            providers={providers}
            onRefresh={() => listProviders().then(setProviders)}
          />
        )}
      </div>
    </div>
  );
}

// ── Seat Tab ──

function SeatTab({
  participants,
  modelOptions,
  onChange,
}: {
  participants: Participant[];
  modelOptions: { value: string; label: string }[];
  onChange: (id: number, field: keyof Participant, value: string) => void;
}) {
  return (
    <div className="p-6 space-y-6">
      {participants.map((p) => (
        <div key={p.id} className="border border-border rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-1">
              <input
                type="color"
                value={ansiToHex(p.color)}
                onChange={(e) => onChange(p.id, "color", hexToAnsi(e.target.value))}
                className="w-8 h-8 rounded cursor-pointer border border-border bg-transparent shrink-0"
                title="选择颜色"
              />
              <input
                value={p.name}
                onChange={(e) => onChange(p.id, "name", e.target.value)}
                style={{ color: ansiToHex(p.color) }}
                className="flex-1 bg-bg-primary border border-border rounded px-3 py-1.5 text-sm font-medium focus:outline-none focus:border-accent"
              />
            </div>
            <span className="text-xs text-text-muted font-mono ml-3">{p.role_key}</span>
          </div>

          <div className="space-y-2">
            <label className="text-xs text-text-muted block">模型</label>
            {modelOptions.length > 0 ? (
              <select
                value={p.model}
                onChange={(e) => onChange(p.id, "model", e.target.value)}
                className="w-full bg-bg-primary border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
              >
                <option value="">请选择模型</option>
                {modelOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                value={p.model}
                onChange={(e) => onChange(p.id, "model", e.target.value)}
                placeholder="暂无可用模型，请先添加供应商"
                className="w-full bg-bg-primary border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
              />
            )}
          </div>

          <div className="space-y-2">
            <label className="text-xs text-text-muted block">工具</label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={(() => {
                  try {
                    return JSON.parse(p.tools_enabled || "[]").includes("search");
                  } catch {
                    return false;
                  }
                })()}
                onChange={(e) => {
                  const enabled = e.target.checked;
                  onChange(p.id, "tools_enabled", enabled ? JSON.stringify(["search"]) : "");
                }}
                className="w-4 h-4 rounded border-border accent-accent"
              />
              <span className="text-sm text-text-secondary">启用搜索（DuckDuckGo）</span>
            </label>
          </div>

          <div className="space-y-2">
            <label className="text-xs text-text-muted block">System Prompt</label>
            <textarea
              value={p.system_prompt}
              onChange={(e) => onChange(p.id, "system_prompt", e.target.value)}
              rows={8}
              className="w-full bg-bg-primary border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent resize-none"
            />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Host Tab ──

function HostTab({
  host,
  form,
  onChange,
  onSave,
  saving,
  modelOptions,
  modes,
  participantsMap,
  onSavePrompt,
}: {
  host: GlobalHost;
  form: Partial<GlobalHost>;
  onChange: (f: Partial<GlobalHost>) => void;
  onSave: () => void;
  saving: boolean;
  modelOptions: { value: string; label: string }[];
  modes: ModeConfig[];
  participantsMap: Record<string, Participant[]>;
  onSavePrompt: (participantId: number, prompt: string) => Promise<void>;
}) {
  const [promptForms, setPromptForms] = useState<Record<string, string>>({});
  const [promptSaving, setPromptSaving] = useState<Record<string, boolean>>({});

  // 初始化 promptForms
  useEffect(() => {
    const map: Record<string, string> = {};
    modes.forEach((m) => {
      const mj = m.mode_json;
      const hostKeys = new Set<string>();
      if (mj?.opening?.speaker) hostKeys.add(mj.opening.speaker);
      if (mj?.rounds?.summary?.speaker) hostKeys.add(mj.rounds.summary.speaker);
      const list = participantsMap[m.name] || [];
      const hostP = list.find((p) => hostKeys.has(p.role_key));
      if (hostP) {
        map[m.name] = hostP.system_prompt;
      }
    });
    setPromptForms(map);
  }, [modes, participantsMap]);

  const hasHostChanges =
    form.name !== host.name || form.model !== host.model;

  const handlePromptChange = (modeName: string, value: string) => {
    setPromptForms((prev) => ({ ...prev, [modeName]: value }));
  };

  const handlePromptSave = async (modeName: string) => {
    const mj = modes.find((m) => m.name === modeName)?.mode_json;
    if (!mj) return;
    const hostKeys = new Set<string>();
    if (mj?.opening?.speaker) hostKeys.add(mj.opening.speaker);
    if (mj?.rounds?.summary?.speaker) hostKeys.add(mj.rounds.summary.speaker);
    const list = participantsMap[modeName] || [];
    const hostP = list.find((p) => hostKeys.has(p.role_key));
    if (!hostP) return;

    const newPrompt = promptForms[modeName];
    if (newPrompt === hostP.system_prompt) return;

    setPromptSaving((prev) => ({ ...prev, [modeName]: true }));
    await onSavePrompt(hostP.id, newPrompt);
    setPromptSaving((prev) => ({ ...prev, [modeName]: false }));
  };

  return (
    <div className="p-6 space-y-6">
      <div className="border border-accent/30 rounded-lg p-4 bg-accent/5">
        <div className="flex items-center gap-3 mb-2">
          <div
            className="w-6 h-6 rounded-full border border-border"
            style={{ backgroundColor: "#0000AA" }}
          />
          <span className="text-sm font-medium text-text-secondary">全局主持人</span>
        </div>
        <p className="text-xs text-text-muted">
          所有讨论模式共享同一位主持人（名称、模型、颜色统一），但各模式的职责 Prompt 可独立设置。
        </p>
      </div>

      <div className="space-y-2">
        <label className="text-xs text-text-muted block">名称</label>
        <input
          value={form.name || ""}
          onChange={(e) => onChange({ ...form, name: e.target.value })}
          className="w-full bg-bg-primary border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
        />
      </div>

      <div className="space-y-2">
        <label className="text-xs text-text-muted block">模型</label>
        {modelOptions.length > 0 ? (
          <select
            value={form.model || ""}
            onChange={(e) => onChange({ ...form, model: e.target.value })}
            className="w-full bg-bg-primary border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
          >
            <option value="">请选择模型</option>
            {modelOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        ) : (
          <input
            value={form.model || ""}
            onChange={(e) => onChange({ ...form, model: e.target.value })}
            placeholder="暂无可用模型"
            className="w-full bg-bg-primary border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
          />
        )}
      </div>

      <div className="space-y-2">
        <label className="text-xs text-text-muted block">颜色（固定）</label>
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded border border-border"
            style={{ backgroundColor: "#0000AA" }}
          />
          <span className="text-xs text-text-muted">蓝色（所有模式统一）</span>
        </div>
      </div>

      {hasHostChanges && (
        <button
          onClick={onSave}
          disabled={saving}
          className="bg-accent hover:bg-accent/90 text-white text-sm px-4 py-2 rounded flex items-center gap-2 transition-colors disabled:opacity-50"
        >
          <Save size={14} />
          {saving ? "保存中..." : "保存更改"}
        </button>
      )}

      <div className="border-t border-border pt-4 space-y-4">
        <h3 className="text-sm font-medium text-text-secondary">各模式主持人 Prompt</h3>
        {modes.map((m) => {
          const mj = m.mode_json;
          const hostKeys = new Set<string>();
          if (mj?.opening?.speaker) hostKeys.add(mj.opening.speaker);
          if (mj?.rounds?.summary?.speaker) hostKeys.add(mj.rounds.summary.speaker);
          const list = participantsMap[m.name] || [];
          const hostP = list.find((p) => hostKeys.has(p.role_key));

          if (!hostP) {
            return (
              <div key={m.name} className="border border-border rounded-lg p-4">
                <p className="text-xs text-text-muted">
                  {m.display_name}：未找到主持人角色（{Array.from(hostKeys).join(", ")}）
                </p>
              </div>
            );
          }

          const currentPrompt = promptForms[m.name] ?? hostP.system_prompt;
          const hasPromptChange = currentPrompt !== hostP.system_prompt;

          return (
            <div key={m.name} className="border border-border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text-secondary">
                  {m.display_name} · {hostP.name}
                </span>
                <span className="text-xs text-text-muted font-mono">{hostP.role_key}</span>
              </div>
              <textarea
                value={currentPrompt}
                onChange={(e) => handlePromptChange(m.name, e.target.value)}
                rows={8}
                className="w-full bg-bg-primary border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent resize-none"
              />
              {hasPromptChange && (
                <button
                  onClick={() => handlePromptSave(m.name)}
                  disabled={promptSaving[m.name]}
                  className="bg-accent hover:bg-accent/90 text-white text-xs px-3 py-1.5 rounded flex items-center gap-1 transition-colors disabled:opacity-50"
                >
                  <Save size={12} />
                  {promptSaving[m.name] ? "保存中..." : "保存 Prompt"}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Provider Tab ──

function ProviderTab({
  providers,
  onRefresh,
}: {
  providers: Provider[];
  onRefresh: () => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({ name: "", base_url: "", api_key: "" });
  const [modelInputs, setModelInputs] = useState<Record<number, string>>({});

  const handleCreate = async () => {
    if (!form.name.trim() || !form.api_key.trim()) return;
    await createProvider({
      name: form.name.trim(),
      base_url: form.base_url.trim() || undefined,
      api_key: form.api_key.trim(),
    });
    setForm({ name: "", base_url: "", api_key: "" });
    setShowForm(false);
    onRefresh();
  };

  const handleUpdate = async (id: number) => {
    if (!form.name.trim() || !form.api_key.trim()) return;
    await updateProvider(id, {
      name: form.name.trim(),
      base_url: form.base_url.trim() || undefined,
      api_key: form.api_key.trim(),
    });
    setEditingId(null);
    setForm({ name: "", base_url: "", api_key: "" });
    onRefresh();
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确定删除该供应商？关联的模型也将被删除。")) return;
    await deleteProvider(id);
    onRefresh();
  };

  const handleAddModel = async (providerId: number) => {
    const modelName = modelInputs[providerId]?.trim();
    if (!modelName) return;
    await addProviderModel(providerId, modelName);
    setModelInputs((prev) => ({ ...prev, [providerId]: "" }));
    onRefresh();
  };

  const handleRemoveModel = async (providerId: number, modelId: number) => {
    await removeProviderModel(providerId, modelId);
    onRefresh();
  };

  return (
    <div className="p-6 space-y-6">
      <button
        onClick={() => {
          setShowForm(!showForm);
          setEditingId(null);
          setForm({ name: "", base_url: "", api_key: "" });
        }}
        className="w-full bg-accent hover:bg-accent/90 text-white rounded-lg px-4 py-2.5 text-sm font-medium flex items-center justify-center gap-2 transition-colors"
      >
        <Plus size={16} />
        添加供应商
      </button>

      {showForm && (
        <ProviderForm
          form={form}
          onChange={setForm}
          onSubmit={handleCreate}
          onCancel={() => setShowForm(false)}
          submitLabel="创建"
        />
      )}

      {providers.map((provider) => (
        <ProviderCard
          key={provider.id}
          provider={provider}
          isEditing={editingId === provider.id}
          form={form}
          onChange={setForm}
          onEdit={() => {
            setEditingId(provider.id);
            setForm({
              name: provider.name,
              base_url: provider.base_url || "",
              api_key: provider.api_key,
            });
            setShowForm(false);
          }}
          onUpdate={() => handleUpdate(provider.id)}
          onCancelEdit={() => {
            setEditingId(null);
            setForm({ name: "", base_url: "", api_key: "" });
          }}
          onDelete={() => handleDelete(provider.id)}
          modelInput={modelInputs[provider.id] || ""}
          onModelInputChange={(v) =>
            setModelInputs((prev) => ({ ...prev, [provider.id]: v }))
          }
          onAddModel={() => handleAddModel(provider.id)}
          onRemoveModel={(modelId) => handleRemoveModel(provider.id, modelId)}
        />
      ))}

      {providers.length === 0 && (
        <div className="text-center text-text-muted text-sm py-8">
          暂无供应商，请点击上方按钮添加
        </div>
      )}
    </div>
  );
}

// ── Provider Form ──

function ProviderForm({
  form,
  onChange,
  onSubmit,
  onCancel,
  submitLabel,
}: {
  form: { name: string; base_url: string; api_key: string };
  onChange: (f: typeof form) => void;
  onSubmit: () => void;
  onCancel: () => void;
  submitLabel: string;
}) {
  const [showKey, setShowKey] = useState(false);

  return (
    <div className="border border-border rounded-lg p-4 space-y-3">
      <div className="space-y-2">
        <label className="text-xs text-text-muted block">供应商名称</label>
        <input
          value={form.name}
          onChange={(e) => onChange({ ...form, name: e.target.value })}
          placeholder="如：deepseek"
          className="w-full bg-bg-primary border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
        />
      </div>
      <div className="space-y-2">
        <label className="text-xs text-text-muted block">Base URL（可选）</label>
        <input
          value={form.base_url}
          onChange={(e) => onChange({ ...form, base_url: e.target.value })}
          placeholder="如：https://api.deepseek.com"
          className="w-full bg-bg-primary border border-border rounded px-3 py-1.5 text-sm text-text-secondary focus:outline-none focus:border-accent"
        />
      </div>
      <div className="space-y-2">
        <label className="text-xs text-text-muted block">API Key</label>
        <div className="relative">
          <input
            type={showKey ? "text" : "password"}
            value={form.api_key}
            onChange={(e) => onChange({ ...form, api_key: e.target.value })}
            placeholder="sk-..."
            className="w-full bg-bg-primary border border-border rounded px-3 py-1.5 pr-10 text-sm text-text-secondary focus:outline-none focus:border-accent"
          />
          <button
            onClick={() => setShowKey(!showKey)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
          >
            {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
      </div>
      <div className="flex gap-2">
        <button
          onClick={onSubmit}
          className="bg-accent hover:bg-accent/90 text-white px-4 py-1.5 rounded text-sm transition-colors"
        >
          {submitLabel}
        </button>
        <button
          onClick={onCancel}
          className="bg-bg-tertiary hover:bg-bg-primary text-text-secondary px-4 py-1.5 rounded text-sm transition-colors"
        >
          取消
        </button>
      </div>
    </div>
  );
}

// ── Provider Card ──

function ProviderCard({
  provider,
  isEditing,
  form,
  onChange,
  onEdit,
  onUpdate,
  onCancelEdit,
  onDelete,
  modelInput,
  onModelInputChange,
  onAddModel,
  onRemoveModel,
}: {
  provider: Provider;
  isEditing: boolean;
  form: { name: string; base_url: string; api_key: string };
  onChange: (f: typeof form) => void;
  onEdit: () => void;
  onUpdate: () => void;
  onCancelEdit: () => void;
  onDelete: () => void;
  modelInput: string;
  onModelInputChange: (v: string) => void;
  onAddModel: () => void;
  onRemoveModel: (modelId: number) => void;
}) {
  const [showKey, setShowKey] = useState(false);

  if (isEditing) {
    return (
      <div className="border border-accent/50 rounded-lg p-4 space-y-3">
        <ProviderForm
          form={form}
          onChange={onChange}
          onSubmit={onUpdate}
          onCancel={onCancelEdit}
          submitLabel="保存"
        />
      </div>
    );
  }

  return (
    <div className="border border-border rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-text-secondary">{provider.name}</span>
        <div className="flex gap-1">
          <button
            onClick={onEdit}
            className="text-text-muted hover:text-accent p-1 transition-colors text-xs"
          >
            编辑
          </button>
          <button
            onClick={onDelete}
            className="text-text-muted hover:text-red-400 p-1 transition-colors"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {provider.base_url && (
        <div className="text-xs text-text-muted font-mono break-all">{provider.base_url}</div>
      )}

      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <input
            type={showKey ? "text" : "password"}
            value={provider.api_key}
            readOnly
            className="w-full bg-bg-primary border border-border rounded px-3 py-1 pr-10 text-xs text-text-secondary"
          />
          <button
            onClick={() => setShowKey(!showKey)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
          >
            {showKey ? <EyeOff size={12} /> : <Eye size={12} />}
          </button>
        </div>
      </div>

      <div className="space-y-2">
        <div className="text-xs text-text-muted">模型列表</div>
        {provider.models.length === 0 && (
          <div className="text-xs text-text-muted italic">暂无模型</div>
        )}
        {provider.models.map((m) => (
          <div
            key={m.id}
            className="flex items-center justify-between bg-bg-primary rounded px-3 py-1.5"
          >
            <span className="text-xs text-text-secondary font-mono">{m.model_name}</span>
            <button
              onClick={() => onRemoveModel(m.id)}
              className="text-text-muted hover:text-red-400 transition-colors"
            >
              <Trash2 size={12} />
            </button>
          </div>
        ))}

        <div className="flex gap-2">
          <input
            value={modelInput}
            onChange={(e) => onModelInputChange(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onAddModel()}
            placeholder="模型名称，如 deepseek/deepseek-chat"
            className="flex-1 bg-bg-primary border border-border rounded px-3 py-1.5 text-xs text-text-secondary focus:outline-none focus:border-accent"
          />
          <button
            onClick={onAddModel}
            className="bg-bg-tertiary hover:bg-accent/20 text-accent px-3 py-1.5 rounded text-xs transition-colors"
          >
            <Plus size={12} />
          </button>
        </div>
      </div>
    </div>
  );
}
