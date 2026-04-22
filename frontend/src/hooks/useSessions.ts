import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createSession, listSessions, getSession } from "@/api/sessions";
import type { SessionCreate } from "@/api/types";

export const sessionKeys = {
  all: ["sessions"] as const,
  list: () => [...sessionKeys.all, "list"] as const,
  detail: (id: string) => [...sessionKeys.all, "detail", id] as const,
};

export function useSessionList(limit = 50, offset = 0) {
  return useQuery({
    queryKey: sessionKeys.list(),
    queryFn: () => listSessions(limit, offset),
  });
}

export function useSessionDetail(id: string) {
  return useQuery({
    queryKey: sessionKeys.detail(id),
    queryFn: () => getSession(id),
    enabled: !!id,
  });
}

export function useCreateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SessionCreate) => createSession(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sessionKeys.list() });
    },
  });
}
