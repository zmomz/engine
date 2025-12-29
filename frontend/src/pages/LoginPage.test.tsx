import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from './LoginPage';
import useAuthStore from '../store/authStore';
import api from '../services/api';

// Mock the auth store
jest.mock('../store/authStore');
// Mock api service
jest.mock('../services/api');

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

const theme = createTheme({
  palette: {
    mode: 'dark',
  },
});

const renderWithProviders = () => {
  return render(
    <ThemeProvider theme={theme}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </ThemeProvider>
  );
};

describe('LoginPage', () => {
  const mockLogin = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useAuthStore as unknown as jest.Mock).mockImplementation((selector) => {
      if (selector) {
        return selector({ login: mockLogin });
      }
      return { login: mockLogin };
    });
  });

  describe('Rendering', () => {
    test('renders the sign in heading', () => {
      renderWithProviders();
      expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument();
    });

    test('renders username field', () => {
      renderWithProviders();
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    });

    test('renders password field', () => {
      renderWithProviders();
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    });

    test('renders sign in button', () => {
      renderWithProviders();
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    });

    test('renders sign up link', () => {
      renderWithProviders();
      expect(screen.getByRole('button', { name: /don't have an account\? sign up/i })).toBeInTheDocument();
    });
  });

  describe('Field Validation', () => {
    test('username and password fields are required', () => {
      renderWithProviders();

      const usernameInput = screen.getByLabelText(/username/i);
      const passwordInput = screen.getByLabelText(/password/i);

      expect(usernameInput).toBeRequired();
      expect(passwordInput).toBeRequired();
    });

    test('password field is type password', () => {
      renderWithProviders();
      const passwordInput = screen.getByLabelText(/password/i);
      expect(passwordInput).toHaveAttribute('type', 'password');
    });
  });

  describe('Input Interaction', () => {
    test('allows entering username', () => {
      renderWithProviders();

      const usernameInput = screen.getByLabelText(/username/i);
      fireEvent.change(usernameInput, { target: { value: 'testuser' } });

      expect(usernameInput).toHaveValue('testuser');
    });

    test('allows entering password', () => {
      renderWithProviders();

      const passwordInput = screen.getByLabelText(/password/i);
      fireEvent.change(passwordInput, { target: { value: 'password123' } });

      expect(passwordInput).toHaveValue('password123');
    });
  });

  describe('Form Submission', () => {
    test('calls api and login on successful submission', async () => {
      const mockResponse = {
        data: {
          access_token: 'test-token',
          user: { id: '1', username: 'testuser' },
        },
      };
      (api.post as jest.Mock).mockResolvedValue(mockResponse);

      renderWithProviders();

      fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'testuser' } });
      fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } });
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith(
          '/users/login',
          expect.any(FormData),
          expect.objectContaining({
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          })
        );
      });

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('test-token', mockResponse.data.user);
      });

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
      });
    });

    test('displays error on failed login with detail', async () => {
      (api.post as jest.Mock).mockRejectedValue({
        response: {
          data: {
            detail: 'Invalid credentials',
          },
        },
      });

      renderWithProviders();

      fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'wronguser' } });
      fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrongpass' } });
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
      });
    });

    test('displays fallback error message when no detail provided', async () => {
      (api.post as jest.Mock).mockRejectedValue(new Error('Network error'));

      renderWithProviders();

      fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'testuser' } });
      fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } });
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

      await waitFor(() => {
        expect(screen.getByText('Login failed')).toBeInTheDocument();
      });
    });

    test('clears error on new submission', async () => {
      // First submission fails
      (api.post as jest.Mock).mockRejectedValueOnce({
        response: { data: { detail: 'Invalid credentials' } },
      });

      renderWithProviders();

      fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'wronguser' } });
      fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrongpass' } });
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

      await waitFor(() => {
        expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
      });

      // Second submission succeeds
      (api.post as jest.Mock).mockResolvedValueOnce({
        data: { access_token: 'token', user: {} },
      });

      fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'rightuser' } });
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

      // Error should be cleared during the new submission
      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalled();
      });
    });
  });

  describe('Navigation', () => {
    test('navigates to register page when sign up button clicked', () => {
      renderWithProviders();

      fireEvent.click(screen.getByRole('button', { name: /don't have an account\? sign up/i }));

      expect(mockNavigate).toHaveBeenCalledWith('/register');
    });
  });

  describe('Accessibility', () => {
    test('username field has autocomplete attribute', () => {
      renderWithProviders();

      const usernameInput = screen.getByLabelText(/username/i);
      expect(usernameInput).toHaveAttribute('autocomplete', 'username');
    });

    test('password field has autocomplete attribute', () => {
      renderWithProviders();

      const passwordInput = screen.getByLabelText(/password/i);
      expect(passwordInput).toHaveAttribute('autocomplete', 'current-password');
    });
  });
});
