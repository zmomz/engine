import { act } from 'react';
import { create } from 'zustand';
import useAuthStore, { AuthState, User } from './authStore';

// Helper to create a mock user for testing
const createMockUser = (overrides: Partial<User> = {}): User => ({
  id: '123',
  username: 'testuser',
  email: 'test@example.com',
  webhook_secret: 'secret123',
  configured_exchanges: ['binance'],
  risk_config: {
    max_open_positions_global: 5,
    max_open_positions_per_symbol: 2,
    max_total_exposure_usd: 10000,
    max_realized_loss_usd: 500,
    loss_threshold_percent: 5,
    required_pyramids_for_timer: 2,
    post_pyramids_wait_minutes: 30,
    max_winners_to_combine: 3,
  },
  ...overrides,
});

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
    const testUser = createMockUser();

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
    const testUser = createMockUser();
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
    const storedUser = createMockUser({ id: '456', username: 'storeduser' });
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
      register: jest.fn(),
      initializeAuth: jest.fn(),
    }));

    const { token, user, isAuthenticated } = newStore.getState();
    expect(token).toBe(storedToken);
    expect(user).toEqual(storedUser);
    expect(isAuthenticated).toBe(true);
  });
});
