import { render, screen } from '@testing-library/react';
import useAuthStore from './store/authStore';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

jest.mock('./store/authStore');

describe('App Routing', () => {
  const mockLogin = jest.fn();

  afterEach(() => {
    jest.clearAllMocks();
  });

  const setupMock = (isAuthenticated: boolean) => {
    const mockState = {
      login: mockLogin,
      isAuthenticated,
    };
    (useAuthStore as jest.Mock).mockImplementation((selector?: (state: any) => any) => {
      if (selector) {
        return selector(mockState);
      }
      return mockState;
    });
  };

  test('renders LoginPage on /login route', () => {
    setupMock(false);
    render(
      <MemoryRouter initialEntries={['/login']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument();
  });

  test('renders RegistrationPage on /register route', () => {
    setupMock(false);
    render(
      <MemoryRouter initialEntries={['/register']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: /sign up/i })).toBeInTheDocument();
  });

  test('redirects to LoginPage from a protected route when not authenticated', () => {
    setupMock(false);
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument();
  });

  test('renders DashboardPage for a protected route when authenticated', () => {
    setupMock(true);
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: /dashboard/i })).toBeInTheDocument();
  });
});
