import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter as Router } from 'react-router-dom';
import RegistrationPage from './RegistrationPage';
import useAuthStore from '../store/authStore';

jest.mock('../store/authStore');

describe('RegistrationPage', () => {
  const mockRegister = jest.fn();

  beforeEach(() => {
    (useAuthStore as any).mockReturnValue({
      register: mockRegister,
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  const renderComponent = () =>
    render(
      <Router>
        <RegistrationPage />
      </Router>
    );

  it('renders the registration form', () => {
    renderComponent();
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign up/i })).toBeInTheDocument();
  });

  it('shows validation errors for empty fields', async () => {
    renderComponent();
    fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

    expect(await screen.findByText(/invalid email address/i)).toBeInTheDocument();
    expect(await screen.findByText(/password must be at least 6 characters/i)).toBeInTheDocument();
  });

  it('calls the register function on successful submission', async () => {
    renderComponent();
    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'password123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign up/i }));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith('test@example.com', 'password123');
    });
  });
});