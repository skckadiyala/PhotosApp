import { create } from 'zustand';

interface UIState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;

  // Photo selection
  selectionMode: boolean;
  selectedPhotoIds: Set<string>;
  enterSelectionMode: (firstId?: string) => void;
  exitSelectionMode: () => void;
  toggleSelect: (id: string) => void;
  clearSelection: () => void;
}

export const useUIStore = create<UIState>()((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  selectionMode: false,
  selectedPhotoIds: new Set<string>(),

  enterSelectionMode: (firstId?: string) =>
    set({
      selectionMode: true,
      selectedPhotoIds: firstId ? new Set([firstId]) : new Set(),
    }),

  exitSelectionMode: () =>
    set({ selectionMode: false, selectedPhotoIds: new Set() }),

  toggleSelect: (id: string) =>
    set((s) => {
      const next = new Set(s.selectedPhotoIds);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return { selectedPhotoIds: next, selectionMode: next.size > 0 };
    }),

  clearSelection: () => set({ selectionMode: false, selectedPhotoIds: new Set() }),
}));
