
import axios from 'axios';
import useAuthStore from '../authStore';
import { act } from '@testing-library/react';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock localStorage
const localStorageMock = (function () {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString();
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

describe('authStore', () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.setState({
      token: null,
      isAuthenticated: false,
      user: null,
    });
    jest.clearAllMocks();
  });

  it('should initialize with default state', () => {
    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
  });

  it('should login and set state', () => {
    const user = { id: 1, username: 'testuser' };
    const token = 'fake-token';

    act(() => {
      useAuthStore.getState().login(token, user);
    });

    const state = useAuthStore.getState();
    expect(state.token).toBe(token);
    expect(state.isAuthenticated).toBe(true);
    expect(state.user).toEqual(user);
    expect(localStorage.getItem('token')).toBe(token);
  });

  it('should logout and clear state', () => {
    // Setup initial logged in state
    localStorage.setItem('token', 'token');
    useAuthStore.setState({ token: 'token', isAuthenticated: true, user: { id: 1 } });

    act(() => {
      useAuthStore.getState().logout();
    });

    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(localStorage.getItem('token')).toBeNull();
  });

  it('should initialize auth from local storage', () => {
    const token = 'stored-token';
    const user = { id: 123, username: 'stored-user' };
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));

    act(() => {
      useAuthStore.getState().initializeAuth();
    });

    const state = useAuthStore.getState();
    expect(state.token).toBe(token);
    expect(state.isAuthenticated).toBe(true);
    expect(state.user).toEqual(user);
  });

  it('should register successfully', async () => {
    const userData = { id: 1, username: 'newuser', email: 'test@example.com' };
    const token = 'new-token';

    // Mock register response
    mockedAxios.post.mockResolvedValueOnce({ data: userData });
    // Mock login response (called inside register)
    mockedAxios.post.mockResolvedValueOnce({ data: { access_token: token } });

    await act(async () => {
      await useAuthStore.getState().register('newuser', 'test@example.com', 'password');
    });

    const state = useAuthStore.getState();
    expect(state.token).toBe(token);
    expect(state.user).toEqual(userData);
    expect(state.isAuthenticated).toBe(true);
    
    expect(mockedAxios.post).toHaveBeenCalledTimes(2);
  });

  it('should handle registration failure', async () => {
    const error = new Error('Registration failed');
    mockedAxios.post.mockRejectedValueOnce(error);

    await expect(
      useAuthStore.getState().register('fail', 'fail@example.com', 'pass')
    ).rejects.toThrow('Registration failed');

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
  });
});
