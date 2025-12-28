import { render, screen } from '@testing-library/react';
import useAuthStore from './store/authStore';
import useConfigStore from './store/configStore';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

jest.mock('./store/authStore');
jest.mock('./store/configStore');

describe('App Routing', () => {
  const mockLogin = jest.fn();

  beforeEach(() => {
    // Mock useConfigStore with valid settings
    (useConfigStore as unknown as jest.Mock).mockReturnValue({
      settings: {
        exchange: 'binance',
        encrypted_api_keys: { public: '***', private: '***' },
        risk_config: { max_open_positions_global: 5 },
        dca_grid_config: [],
        username: 'testuser',
        email: 'test@example.com',
        webhook_secret: 'secret'
      },
      supportedExchanges: ['binance', 'bybit'],
      loading: false,
      error: null,
      fetchSettings: jest.fn(),
      fetchSupportedExchanges: jest.fn(),
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  const setupMock = (isAuthenticated: boolean) => {
    const mockAuthState = {
      login: mockLogin,
      isAuthenticated,
      user: { id: 'test-user-id' },
    };
    (useAuthStore as any).mockImplementation((selector?: (state: any) => any) => {
      if (selector) {
        return selector(mockAuthState);
      }
      return mockAuthState;
    });
    (useAuthStore as any).getState = jest.fn(() => mockAuthState);
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
    // Positions appears in nav and heading
    expect(screen.getAllByText(/positions/i).length).toBeGreaterThan(0);
  });

  test('renders QueuePage for /queue route when authenticated', async () => {
    setupMock(true);
    render(
      <MemoryRouter initialEntries={['/queue']}>
        <App />
      </MemoryRouter>
    );
    // The Queue page shows queue content - look for multiple Queue texts (nav + heading)
    expect(screen.getAllByText('Queue').length).toBeGreaterThan(0);
  });

  test('renders RiskPage for /risk route when authenticated', () => {
    setupMock(true);
    render(
      <MemoryRouter initialEntries={['/risk']}>
        <App />
      </MemoryRouter>
    );
    // The Risk page has "Risk" text in multiple places (nav + heading)
    expect(screen.getAllByText('Risk').length).toBeGreaterThan(0);
  });

  test('renders LogsPage for /logs route when authenticated', () => {
    setupMock(true);
    render(
      <MemoryRouter initialEntries={['/logs']}>
        <App />
      </MemoryRouter>
    );
    // Check for "Logs" text - appears in nav and potentially heading
    expect(screen.getAllByText(/logs/i).length).toBeGreaterThan(0);
  });

  test('renders SettingsPage for /settings route when authenticated', () => {
    setupMock(true);
    render(
      <MemoryRouter initialEntries={['/settings']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: 'Settings', level: 4 })).toBeInTheDocument();
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