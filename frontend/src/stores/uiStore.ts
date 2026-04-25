import { create } from "zustand";

interface UIState {
  sidebarOpen: boolean;
  configPanelOpen: boolean;
  currentSessionId: string | null;
  theme: "warm" | "pink" | "ocean";
  toggleSidebar: () => void;
  setConfigPanelOpen: (v: boolean) => void;
  setCurrentSessionId: (id: string | null) => void;
  toggleTheme: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  configPanelOpen: false,
  currentSessionId: null,
  theme: (localStorage.getItem("theme") as "warm" | "pink" | "ocean") || "warm",
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setConfigPanelOpen: (v) => set({ configPanelOpen: v }),
  setCurrentSessionId: (id) => set({ currentSessionId: id }),
  toggleTheme: () =>
    set((s) => {
      const order: Array<"warm" | "pink" | "ocean"> = ["warm", "pink", "ocean"];
      const idx = order.indexOf(s.theme);
      const next = order[(idx + 1) % order.length];
      localStorage.setItem("theme", next);
      return { theme: next };
    }),
}));
