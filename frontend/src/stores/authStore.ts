import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  accessToken: string | null;
  setTokens: (access: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      setTokens: (access) => set({ accessToken: access }),
      logout: () => set({ accessToken: null }),
    }),

    {
      name: 'photosapp-auth',
    },
  ),
);
