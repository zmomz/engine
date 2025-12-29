import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type ThemeMode = 'light' | 'dark';

interface ThemeState {
  mode: ThemeMode;
  toggleTheme: () => void;
  setTheme: (mode: ThemeMode) => void;
}

const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      mode: 'dark', // Default to dark theme (trading terminal style)
      toggleTheme: () =>
        set((state) => ({
          mode: state.mode === 'dark' ? 'light' : 'dark',
        })),
      setTheme: (mode: ThemeMode) => set({ mode }),
    }),
    {
      name: 'theme-storage', // localStorage key
    }
  )
);

export default useThemeStore;
