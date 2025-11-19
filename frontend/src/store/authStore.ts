import { create } from 'zustand';
import api from '../services/api';

export interface AuthState {
  token: string | null;
  user: any | null; // Replace 'any' with a proper User type later
  isAuthenticated: boolean;
  login: (token: string, user: any) => void;
  logout: () => void;
  register: (email: string, password: string) => Promise<void>;
}

const useAuthStore = create<AuthState>((set) => ({
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
  register: async (email, password) => {
    try {
      // Step 1: Register the user
      const registrationResponse = await api.post('/users/register', { email, username: email, password });
      const user = registrationResponse.data;

      // Step 2: Log the user in to get a token
      const params = new URLSearchParams();
      params.append('username', email);
      params.append('password', password);

      const loginResponse = await api.post('/users/login', params, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });
      
      const { access_token } = loginResponse.data;

      // Step 3: Update the store with user and token
      useAuthStore.getState().login(access_token, user);

    } catch (error) {
      console.error('Registration failed:', error);
      throw error;
    }
  },
}));

export default useAuthStore;
