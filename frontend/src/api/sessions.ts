import { api } from "./client";
import type { Session, SessionCreate } from "./types";

export const createSession = async (data: SessionCreate): Promise<Session> => {
  const res = await api.post("/api/sessions", data);
  return res.data;
};

export const listSessions = async (limit = 50, offset = 0): Promise<Session[]> => {
  const res = await api.get("/api/sessions", { params: { limit, offset } });
  return res.data;
};

export const getSession = async (id: string): Promise<Session & { messages: any[] }> => {
  const res = await api.get(`/api/sessions/${id}`);
  return res.data;
};
