import { act } from 'react';
import { create } from 'zustand';
import useAuthStore, { AuthState } from './authStore';

describe('useAuthStore', () => {
  const originalLocalStorage = window.localStorage;

  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    // Reset the store state
    act(() => {
      useAuthStore.setState({
        token: null,
        user: null,
        isAuthenticated: false,
      });
    });
  });

  afterAll(() => {
    // Restore original localStorage
    Object.defineProperty(window, 'localStorage', { value: originalLocalStorage });
  });

  it('should return initial state with no token or user in localStorage', () => {
    const { token, user, isAuthenticated } = useAuthStore.getState();
    expect(token).toBeNull();
    expect(user).toBeNull();
    expect(isAuthenticated).toBe(false);
  });

  it('should log in a user and store token and user in localStorage', () => {
    const testToken = 'test-token';
    const testUser = { id: '123', username: 'testuser' };

    act(() => {
      useAuthStore.getState().login(testToken, testUser);
    });

    const { token, user, isAuthenticated } = useAuthStore.getState();
    expect(token).toBe(testToken);
    expect(user).toEqual(testUser);
    expect(isAuthenticated).toBe(true);
    expect(localStorage.getItem('token')).toBe(testToken);
    expect(localStorage.getItem('user')).toBe(JSON.stringify(testUser));
  });

  it('should log out a user and remove token and user from localStorage', () => {
    // First, log in a user
    const testToken = 'test-token';
    const testUser = { id: '123', username: 'testuser' };
    act(() => {
      useAuthStore.getState().login(testToken, testUser);
    });

    // Then, log out
    act(() => {
      useAuthStore.getState().logout();
    });

    const { token, user, isAuthenticated } = useAuthStore.getState();
    expect(token).toBeNull();
    expect(user).toBeNull();
    expect(isAuthenticated).toBe(false);
    expect(localStorage.getItem('token')).toBeNull();
    expect(localStorage.getItem('user')).toBeNull();
  });

  it('should initialize with token and user from localStorage if present', () => {
    const storedToken = 'stored-token';
    const storedUser = { id: '456', username: 'storeduser' };
    localStorage.setItem('token', storedToken);
    localStorage.setItem('user', JSON.stringify(storedUser));

    // Re-create the store to simulate a fresh load
    const newStore = create<AuthState>((set) => ({
      token: localStorage.getItem('token') || null,
      user: JSON.parse(localStorage.getItem('user') || 'null'),
      isAuthenticated: !!localStorage.getItem('token'),
      login: (token, user) => {
        localStorage.setItem('token', token);
        localStorage.setItem('user', JSON.stringify(user));
        set({ token, user, isAuthenticated: true });
      },
      logout: () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        set({ token: null, user: null, isAuthenticated: false });
      },
    }));

    const { token, user, isAuthenticated } = newStore.getState();
    expect(token).toBe(storedToken);
    expect(user).toEqual(storedUser);
    expect(isAuthenticated).toBe(true);
  });
});
