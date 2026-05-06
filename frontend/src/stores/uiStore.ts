import { create } from 'zustand';

interface UIState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;

  // Page-level header slot (used by sub-pages to surface their title into the global Header)
  pageTitle: string | null;
  pageSubtitle: string | null;
  setPageHeader: (title: string | null, subtitle?: string | null) => void;

  // Photo selection
  selectionMode: boolean;
  selectedPhotoIds: Set<string>;
  anchorId: string | null;   // last directly-clicked item — start of range
  pivotId: string | null;    // current keyboard cursor — end of range

  enterSelectionMode: (firstId?: string) => void;
  exitSelectionMode: () => void;
  toggleSelect: (id: string) => void;
  clearSelection: () => void;
  selectRange: (anchorId: string, toId: string, allIds: string[]) => void;
  moveCursor: (id: string) => void;
}

export const useUIStore = create<UIState>()((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  pageTitle: null,
  pageSubtitle: null,
  setPageHeader: (title, subtitle = null) => set({ pageTitle: title, pageSubtitle: subtitle }),

  selectionMode: false,
  selectedPhotoIds: new Set<string>(),
  anchorId: null,
  pivotId: null,

  enterSelectionMode: (firstId?: string) =>
    set({
      selectionMode: true,
      selectedPhotoIds: firstId ? new Set([firstId]) : new Set(),
      anchorId: firstId ?? null,
      pivotId: firstId ?? null,
    }),

  exitSelectionMode: () =>
    set({ selectionMode: false, selectedPhotoIds: new Set(), anchorId: null, pivotId: null }),

  toggleSelect: (id: string) =>
    set((s) => {
      const next = new Set(s.selectedPhotoIds);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      // Update anchor so subsequent shift+click/arrow extends from here
      return { selectedPhotoIds: next, selectionMode: next.size > 0, anchorId: id, pivotId: id };
    }),

  clearSelection: () =>
    set({ selectionMode: false, selectedPhotoIds: new Set(), anchorId: null, pivotId: null }),

  selectRange: (anchorId: string, toId: string, allIds: string[]) =>
    set(() => {
      const aIdx = allIds.indexOf(anchorId);
      const tIdx = allIds.indexOf(toId);
      if (aIdx === -1 || tIdx === -1) return {};
      const [lo, hi] = aIdx <= tIdx ? [aIdx, tIdx] : [tIdx, aIdx];
      return {
        selectedPhotoIds: new Set(allIds.slice(lo, hi + 1)),
        selectionMode: true,
        pivotId: toId,
      };
    }),

  // Move the keyboard cursor without changing selection or anchor.
  // Lets users navigate over photos with Arrow keys and pick individually with Space.
  moveCursor: (id: string) => set({ pivotId: id }),
}));
