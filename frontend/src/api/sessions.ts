import { api } from "./client";
import type { Session, SessionCreate, Attachment } from "./types";

export const createSession = async (data: SessionCreate): Promise<Session> => {
  const formData = new FormData();
  formData.append("mode", data.mode);
  formData.append("topic", data.topic);
  if (data.rounds !== undefined) {
    formData.append("rounds", String(data.rounds));
  }
  data.files?.forEach((file) => {
    formData.append("files", file);
  });

  const res = await api.post("/api/sessions", formData);
  return res.data;
};

export const getSessionAttachments = async (id: string): Promise<Attachment[]> => {
  const res = await api.get(`/api/sessions/${id}/attachments`);
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
