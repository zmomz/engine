import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';
import { useAuthStore } from './store/authStore';

// Mock the auth store
const mockLogin = jest.fn();
const mockState = {
  login: mockLogin,
  isAuthenticated: false,
};

jest.mock('./store/authStore', () => ({
  useAuthStore: jest.fn((selector) => {
    if (selector) {
      return selector(mockState);
    }
    return mockState;
  }),
}));

describe('App Routing', () => {
  beforeEach(() => {
    (useAuthStore as jest.Mock).mockClear();
    mockLogin.mockClear();
  });
  test('renders LoginPage on /login route', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <App />
      </MemoryRouter>
    );
expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument();
  });

  test('renders RegistrationPage on /register route', () => {
    render(
      <MemoryRouter initialEntries={['/register']}>
        <App />
      </MemoryRouter>
    );
    // Assuming RegistrationPage has a heading with text "Register"
    expect(screen.getByRole('heading', { name: /register/i })).toBeInTheDocument();
  });

  test('redirects to LoginPage from a protected route when not authenticated', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <App />
      </MemoryRouter>
    );
    // The ProtectedRoute should redirect to /login, so we expect to see the login page
    expect(screen.getByRole('heading', { name: /login/i })).toBeInTheDocument();
  });
});