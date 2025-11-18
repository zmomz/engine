import React from 'react';
import { render, screen } from '@testing-library/react';
import RegistrationPage from './RegistrationPage';

test('renders registration page', () => {
  render(<RegistrationPage />);
  const linkElement = screen.getByText(/Register/i);
  expect(linkElement).toBeInTheDocument();
});
