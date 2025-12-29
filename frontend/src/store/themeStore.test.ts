import useThemeStore from './themeStore';

describe('themeStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useThemeStore.setState({ mode: 'dark' });
    // Clear localStorage
    localStorage.clear();
  });

  it('should have dark mode as default', () => {
    expect(useThemeStore.getState().mode).toBe('dark');
  });

  it('should toggle from dark to light', () => {
    useThemeStore.getState().toggleTheme();
    expect(useThemeStore.getState().mode).toBe('light');
  });

  it('should toggle from light to dark', () => {
    useThemeStore.setState({ mode: 'light' });
    useThemeStore.getState().toggleTheme();
    expect(useThemeStore.getState().mode).toBe('dark');
  });

  it('should set theme directly', () => {
    useThemeStore.getState().setTheme('light');
    expect(useThemeStore.getState().mode).toBe('light');

    useThemeStore.getState().setTheme('dark');
    expect(useThemeStore.getState().mode).toBe('dark');
  });

  it('should toggle multiple times correctly', () => {
    expect(useThemeStore.getState().mode).toBe('dark');

    useThemeStore.getState().toggleTheme();
    expect(useThemeStore.getState().mode).toBe('light');

    useThemeStore.getState().toggleTheme();
    expect(useThemeStore.getState().mode).toBe('dark');

    useThemeStore.getState().toggleTheme();
    expect(useThemeStore.getState().mode).toBe('light');
  });
});
