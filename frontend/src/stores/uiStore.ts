import { create } from "zustand";

interface UIState {
  sidebarOpen: boolean;
  configPanelOpen: boolean;
  currentSessionId: string | null;
  toggleSidebar: () => void;
  setConfigPanelOpen: (v: boolean) => void;
  setCurrentSessionId: (id: string | null) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  configPanelOpen: false,
  setConfigPanelOpen: (v) => set({ configPanelOpen: v }),
  currentSessionId: null,
  setCurrentSessionId: (id) => set({ currentSessionId: id }),
}));
