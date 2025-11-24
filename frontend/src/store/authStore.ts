import { create } from 'zustand';
import axios from 'axios';

export interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  user: any | null; // You might want to define a more specific user type
  login: (token: string, user: any) => void;
  logout: () => void;
  initializeAuth: () => void;
  register: (username: string, email: string, password: string) => Promise<void>;
}

const getUserFromStorage = () => {
  const item = localStorage.getItem('user');
  if (!item || item === 'undefined') return null;
  try {
    return JSON.parse(item);
  } catch {
    return null;
  }
};

const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem('token'),
  isAuthenticated: !!localStorage.getItem('token'),
  user: getUserFromStorage(),

  login: (token, user) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user || null));
    set({ token, isAuthenticated: true, user });
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    set({ token: null, isAuthenticated: false, user: null });
  },

  initializeAuth: () => {
    const token = localStorage.getItem('token');
    const user = getUserFromStorage();
    set({ token, isAuthenticated: !!token, user });
  },

  register: async (username, email, password) => {
    try {
      // 1. Register
      const registerResponse = await axios.post('/api/v1/users/register', {
        username,
        email,
        password,
      });
      const user = registerResponse.data;

      // 2. Login to get token
      const params = new URLSearchParams();
      params.append('username', username);
      params.append('password', password);

      const loginResponse = await axios.post('/api/v1/users/login', params, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      const token = loginResponse.data.access_token;

      // 3. Update store
      get().login(token, user);

    } catch (error) {
      console.error("Registration failed:", error);
      throw error; // Re-throw for component to handle
    }
  },
}));

// Axios interceptor for JWT
axios.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
      // Optionally redirect to login page here, or handle it in specific components
    }
    return Promise.reject(error);
  }
);

export default useAuthStore;