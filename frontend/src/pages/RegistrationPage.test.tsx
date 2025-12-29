import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { MemoryRouter } from 'react-router-dom';
import RegistrationPage from './RegistrationPage';
import useAuthStore from '../store/authStore';

jest.mock('../store/authStore');

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
        <RegistrationPage />
      </MemoryRouter>
    </ThemeProvider>
  );
};

describe('RegistrationPage', () => {
  const mockRegister = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useAuthStore as any).mockReturnValue({
      register: mockRegister,
    });
  });

  describe('Rendering', () => {
    test('renders the sign up heading', () => {
      renderWithProviders();
      expect(screen.getByRole('heading', { name: /sign up/i })).toBeInTheDocument();
    });

    test('renders username field', () => {
      renderWithProviders();
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    });

    test('renders email field', () => {
      renderWithProviders();
      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    });

    test('renders password field', () => {
      renderWithProviders();
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    });

    test('renders sign up button', () => {
      renderWithProviders();
      expect(screen.getByRole('button', { name: /sign up/i })).toBeInTheDocument();
    });

    test('renders sign in link', () => {
      renderWithProviders();
      expect(screen.getByRole('button', { name: /already have an account\? sign in/i })).toBeInTheDocument();
    });
  });

  describe('Validation', () => {
    test('shows validation errors for empty fields', async () => {
      renderWithProviders();
      fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

      expect(await screen.findByText(/username must be at least 3 characters/i)).toBeInTheDocument();
      expect(await screen.findByText(/invalid email address/i)).toBeInTheDocument();
      expect(await screen.findByText(/password must be at least 6 characters/i)).toBeInTheDocument();
    });

    test('shows error for invalid email', async () => {
      renderWithProviders();

      fireEvent.change(screen.getByLabelText(/username/i), {
        target: { value: 'testuser' },
      });
      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: 'invalid-email' },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: 'password123' },
      });
      fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

      expect(await screen.findByText(/invalid email address/i)).toBeInTheDocument();
    });

    test('shows error for short username', async () => {
      renderWithProviders();

      fireEvent.change(screen.getByLabelText(/username/i), {
        target: { value: 'ab' },
      });
      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: 'password123' },
      });
      fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

      expect(await screen.findByText(/username must be at least 3 characters/i)).toBeInTheDocument();
    });

    test('shows error for short password', async () => {
      renderWithProviders();

      fireEvent.change(screen.getByLabelText(/username/i), {
        target: { value: 'testuser' },
      });
      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: '123' },
      });
      fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

      expect(await screen.findByText(/password must be at least 6 characters/i)).toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    test('calls register function on successful submission', async () => {
      mockRegister.mockResolvedValue(undefined);

      renderWithProviders();

      fireEvent.change(screen.getByLabelText(/username/i), {
        target: { value: 'testuser' },
      });
      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: 'password123' },
      });
      fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalledWith('testuser', 'test@example.com', 'password123');
      });
    });

    test('navigates to dashboard on successful registration', async () => {
      mockRegister.mockResolvedValue(undefined);

      renderWithProviders();

      fireEvent.change(screen.getByLabelText(/username/i), {
        target: { value: 'testuser' },
      });
      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: 'password123' },
      });
      fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
      });
    });

    test('shows button as disabled while submitting', async () => {
      mockRegister.mockImplementation(() => new Promise((resolve) => setTimeout(resolve, 100)));

      renderWithProviders();

      fireEvent.change(screen.getByLabelText(/username/i), {
        target: { value: 'testuser' },
      });
      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: 'password123' },
      });
      fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /signing up/i })).toBeDisabled();
      });
    });

    test('displays error on failed registration with detail', async () => {
      mockRegister.mockRejectedValue({
        response: {
          data: {
            detail: 'Username already exists',
          },
        },
      });

      renderWithProviders();

      fireEvent.change(screen.getByLabelText(/username/i), {
        target: { value: 'existinguser' },
      });
      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: 'password123' },
      });
      fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText('Username already exists')).toBeInTheDocument();
      });
    });

    test('displays fallback error message when no detail provided', async () => {
      mockRegister.mockRejectedValue(new Error('Network error'));

      renderWithProviders();

      fireEvent.change(screen.getByLabelText(/username/i), {
        target: { value: 'testuser' },
      });
      fireEvent.change(screen.getByLabelText(/email address/i), {
        target: { value: 'test@example.com' },
      });
      fireEvent.change(screen.getByLabelText(/password/i), {
        target: { value: 'password123' },
      });
      fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

      await waitFor(() => {
        expect(screen.getByText('An unexpected error occurred.')).toBeInTheDocument();
      });
    });
  });

  describe('Navigation', () => {
    test('navigates to login page when sign in button clicked', () => {
      renderWithProviders();

      fireEvent.click(screen.getByRole('button', { name: /already have an account\? sign in/i }));

      expect(mockNavigate).toHaveBeenCalledWith('/login');
    });
  });

  describe('Input Interaction', () => {
    test('allows entering username', () => {
      renderWithProviders();

      const usernameInput = screen.getByLabelText(/username/i);
      fireEvent.change(usernameInput, { target: { value: 'testuser' } });

      expect(usernameInput).toHaveValue('testuser');
    });

    test('allows entering email', () => {
      renderWithProviders();

      const emailInput = screen.getByLabelText(/email address/i);
      fireEvent.change(emailInput, { target: { value: 'test@example.com' } });

      expect(emailInput).toHaveValue('test@example.com');
    });

    test('allows entering password', () => {
      renderWithProviders();

      const passwordInput = screen.getByLabelText(/password/i);
      fireEvent.change(passwordInput, { target: { value: 'password123' } });

      expect(passwordInput).toHaveValue('password123');
    });

    test('password field is type password', () => {
      renderWithProviders();

      const passwordInput = screen.getByLabelText(/password/i);
      expect(passwordInput).toHaveAttribute('type', 'password');
    });
  });

  describe('Accessibility', () => {
    test('username field has autocomplete attribute', () => {
      renderWithProviders();

      const usernameInput = screen.getByLabelText(/username/i);
      expect(usernameInput).toHaveAttribute('autocomplete', 'username');
    });

    test('email field has autocomplete attribute', () => {
      renderWithProviders();

      const emailInput = screen.getByLabelText(/email address/i);
      expect(emailInput).toHaveAttribute('autocomplete', 'email');
    });

    test('password field has autocomplete attribute', () => {
      renderWithProviders();

      const passwordInput = screen.getByLabelText(/password/i);
      expect(passwordInput).toHaveAttribute('autocomplete', 'new-password');
    });
  });
});