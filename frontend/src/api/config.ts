import { api } from "./client";
import type { ModeConfig, Provider, GlobalHost } from "./types";

export const listModeConfigs = async (): Promise<ModeConfig[]> => {
  const res = await api.get("/api/config/modes");
  return res.data;
};

export const updateParticipant = async (
  participantId: number,
  data: Partial<{ name: string; model: string; color: string; system_prompt: string }>
): Promise<any> => {
  const res = await api.patch(`/api/config/participants/${participantId}`, data);
  return res.data;
};

// ── Provider CRUD ──

export const listProviders = async (): Promise<Provider[]> => {
  const res = await api.get("/api/config/providers");
  return res.data;
};

export const createProvider = async (data: {
  name: string;
  base_url?: string;
  api_key: string;
}): Promise<Provider> => {
  const res = await api.post("/api/config/providers", data);
  return res.data;
};

export const updateProvider = async (
  id: number,
  data: Partial<{ name: string; base_url?: string; api_key: string }>
): Promise<Provider> => {
  const res = await api.patch(`/api/config/providers/${id}`, data);
  return res.data;
};

export const deleteProvider = async (id: number): Promise<void> => {
  await api.delete(`/api/config/providers/${id}`);
};

export const addProviderModel = async (
  providerId: number,
  modelName: string
): Promise<Provider> => {
  const res = await api.post(`/api/config/providers/${providerId}/models`, {
    model_name: modelName,
  });
  return res.data;
};

export const removeProviderModel = async (
  providerId: number,
  modelId: number
): Promise<void> => {
  await api.delete(`/api/config/providers/${providerId}/models/${modelId}`);
};

// ── Mode Config ──

export const updateModeConfig = async (
  modeName: string,
  data: { default_rounds?: number }
): Promise<ModeConfig> => {
  const res = await api.patch(`/api/config/modes/${modeName}`, data);
  return res.data;
};

// ── Global Host ──

export const getGlobalHost = async (): Promise<GlobalHost> => {
  const res = await api.get("/api/config/host");
  return res.data;
};

export const updateGlobalHost = async (data: Partial<Omit<GlobalHost, "id" | "color">>): Promise<GlobalHost> => {
  const res = await api.put("/api/config/host", data);
  return res.data;
};
