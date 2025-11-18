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

  test('renders PositionsPage for /positions route when authenticated', () => {
    setupMock(true);
    render(
      <MemoryRouter initialEntries={['/positions']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: /positions/i })).toBeInTheDocument();
  });

  test('renders QueuePage for /queue route when authenticated', async () => {
    setupMock(true);
    render(
      <MemoryRouter initialEntries={['/queue']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: /queued signals/i })).toBeInTheDocument();
  });

  test('renders RiskEnginePage for /risk-engine route when authenticated', () => {
    setupMock(true);
    render(
      <MemoryRouter initialEntries={['/risk-engine']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: /risk engine/i })).toBeInTheDocument();
  });

  test('renders LogsPage for /logs route when authenticated', () => {
    setupMock(true);
    render(
      <MemoryRouter initialEntries={['/logs']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: /logs & alerts/i })).toBeInTheDocument();
  });

  test('renders SettingsPage for /settings route when authenticated', () => {
    setupMock(true);
    render(
      <MemoryRouter initialEntries={['/settings']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: /settings/i })).toBeInTheDocument();
  });

  test('renders DashboardPage for default protected route (/) when authenticated', () => {
    setupMock(true);
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: /dashboard/i })).toBeInTheDocument();
  });
});
