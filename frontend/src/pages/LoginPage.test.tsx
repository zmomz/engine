import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter as Router } from 'react-router-dom';
import LoginPage from './LoginPage';
import useAuthStore from '../store/authStore';
import axios from 'axios';

// Mock the auth store
jest.mock('../store/authStore');
// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('LoginPage', () => {
  const mockLogin = jest.fn();

  beforeEach(() => {
    (useAuthStore as unknown as jest.Mock).mockImplementation((selector) => {
        if (selector) {
            return selector({ login: mockLogin });
        }
        return { login: mockLogin };
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  const renderComponent = () =>
    render(
      <Router>
        <LoginPage />
      </Router>
    );

  it('renders the login form', () => {
    renderComponent();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('shows validation errors for empty fields', async () => {
    // Note: HTML5 validation prevents submission of empty required fields, 
    // so we might not see custom error messages unless we bypass that or check for 'required' attribute.
    // However, the component uses Material UI TextField required prop.
    renderComponent();
    
    const usernameInput = screen.getByLabelText(/username/i);
    const passwordInput = screen.getByLabelText(/password/i);

    expect(usernameInput).toBeRequired();
    expect(passwordInput).toBeRequired();
  });

  it('calls the login function on successful submission', async () => {
    mockedAxios.post.mockResolvedValue({
      data: { access_token: 'fake_token', user: { id: '1', username: 'testuser' } },
    });

    renderComponent();
    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: 'testuser' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'password123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith('/users/login', expect.any(FormData), expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/x-www-form-urlencoded'
        })
      }));
      expect(mockLogin).toHaveBeenCalledWith('fake_token', { id: '1', username: 'testuser' });
    });
  });

  it('shows error message on failed login', async () => {
    mockedAxios.post.mockRejectedValue({
      response: { data: { detail: 'Invalid credentials' } },
    });

    renderComponent();
    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: 'testuser' },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'wrongpassword' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
    });
  });
});
